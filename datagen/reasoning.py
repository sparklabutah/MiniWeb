"""Stage 6 — thoughts (OPTIONAL, off by default). A VLM writes one short thought per step
from a kept trajectory's saved screenshots, its actions and the macro intent, in a chosen
thought style, into accepted/<task>/thoughts/<style>.json — so several styles can coexist and
thoughts can be added long after the run (`python -m datagen thoughts --run-id R --style S`).

The VLM sees only what a student would see (screenshots, the instruction, the action) plus a
marker drawn on its copy of the screenshot to show where the action happened. It is never
given the guide, the DOM, the element side file or the sampled parameters, and thoughts that
mention hidden machinery (guide, script, selector, DOM, coordinates, marker, ...) are rejected.
"""
from __future__ import annotations

import io
import json
import re
from pathlib import Path

from datagen import config
from datagen import trajectory as T

STYLES = {
    # what the current student (browser-use harness, e.g. qwen3.5-4b) emits every step
    "browser_use": {
        "fields": {"evaluation_previous_goal": "one sentence judging whether the previous action worked, from "
                                               "the current screenshot ('First step' on step 1)",
                   "memory": "one or two sentences of progress so far and what remains",
                   "next_goal": "one sentence: the action about to be taken and why"},
    },
    "short": {"fields": {"thought": "one or two first-person sentences: what I see that matters and why I take "
                                    "this action"}},
}
# hidden machinery the student cannot see; "html"/"css" alone are allowed (visible tag names on tech sites)
FORBIDDEN = re.compile(r"\b(guide|script|dom|selector|xpath|bounding box|coordinates?|pixels?|marker|"
                       r"html (element|tag|code|source|attribute)|css (selector|class|rule)|"
                       r"red (dot|circle|cross|mark)|privileged|playwright|hidden info|task parameters|x\s*=|y\s*=)\b",
                       re.I)

SYSTEM = ("You write the inner thoughts of a web agent that sees ONLY screenshots and acts with mouse and "
          "keyboard. For every step you get the screenshot the agent saw before acting and the action it took. "
          "A red marker on the image shows where a mouse action happened — the agent itself does not see the "
          "marker; never mention it. Thoughts must be grounded in what is visible on screen, explain why each "
          "action moves the task forward, stay consistent from step to step, and sound natural and concise. "
          "Never mention markers, guides, scripts, code, HTML/DOM, selectors, coordinates, pixel values or any "
          "information not visible on screen. Reply ONLY JSON.")


def _marked(png_path, step):
    """JPEG of the screenshot with the action's location marked (VLM input only)."""
    from PIL import Image, ImageDraw
    im = Image.open(png_path).convert("RGB")
    d = ImageDraw.Draw(im)
    if "x" in step and "y" in step:
        x, y = step["x"], step["y"]
        d.ellipse([x - 11, y - 11, x + 11, y + 11], outline=(255, 0, 0), width=3)
        d.line([x - 16, y, x + 16, y], fill=(255, 0, 0), width=2)
        d.line([x, y - 16, x, y + 16], fill=(255, 0, 0), width=2)
    if step["type"] == "drag":
        d.line([step["x"], step["y"], step["x2"], step["y2"]], fill=(0, 90, 255), width=3)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=78)
    return buf.getvalue()


def _describe(step):
    t = step["type"]
    if t in ("click", "double_click"):
        return f"{t.replace('_', ' ')} at the marked point"
    if t == "hover":
        return "move the mouse over the marked point"
    if t == "type":
        return f"type {step['text']!r}"
    if t == "key":
        return f"press the {step['key']} key"
    if t == "scroll":
        return f"scroll {'down' if step.get('dy', 0) > 0 else 'up'} (mouse wheel) with the pointer at the marked point"
    if t == "drag":
        return "drag from the marked point along the blue line"
    return t


def write_thoughts(traj_dir, style="browser_use", model=config.MODEL_REASON, tries=3, force=False):
    """thoughts/<style>.json for one kept trajectory, from its saved screenshots. Returns the path."""
    from annotation import macros as registry
    from helpers.llm import call_llm
    if style not in STYLES:
        raise ValueError(f"unknown thought style {style!r} (known: {sorted(STYLES)})")
    d = Path(traj_dir)
    if T.thoughts_path(d, style).exists() and not force:
        return T.thoughts_path(d, style)
    t = T.load(d)
    steps = [("history", s, t.get("history_macro")) for s in t["history"]] + \
            [("steps", s, t["macro"]) for s in t["steps"]]
    images, listing = [], []
    for n, (_part, s, macro) in enumerate(steps, 1):
        images.append(_marked(d / s["screenshot"], s["action"]))
        listing.append({"step": n, "image": len(images), "action": _describe(s["action"]),
                        "sub_goal": registry.describe(macro).get("description")})
    if t.get("final_screenshot") and (d / t["final_screenshot"]).exists():
        from PIL import Image
        buf = io.BytesIO()
        Image.open(d / t["final_screenshot"]).convert("RGB").save(buf, "JPEG", quality=78)
        images.append(buf.getvalue())
    task = {"instruction": t["instruction"]}
    fields = STYLES[style]["fields"]
    prompt = {"task": task["instruction"], "steps": listing,
              "images": f"{len(steps)} before-action screenshots in step order, then the final screen",
              "output": {"thoughts": [{"step": "<n>", **fields}]},
              "rules": ["one entry per step, same order", "each field one or two sentences",
                        "refer to things by their visible text/look (e.g. 'the Category menu')"]}
    feedback = ""
    for _ in range(tries):
        raw = call_llm(json.dumps(prompt, ensure_ascii=False) + feedback, system=SYSTEM, json_mode=True,
                       model=model, max_tokens=8000, temperature=0.4, images=images)
        try:
            out = json.loads(raw or "")
            thoughts = out.get("thoughts") if isinstance(out, dict) else out
        except ValueError:
            thoughts = None
        if isinstance(thoughts, list):
            thoughts = [_unwrap(x, fields) for x in thoughts]
        if isinstance(thoughts, list) and thoughts and isinstance(thoughts[0], dict) and \
                "evaluation_previous_goal" in fields and not str(thoughts[0].get("evaluation_previous_goal") or "").strip():
            thoughts[0]["evaluation_previous_goal"] = "First step of the task."
        err = _validate(thoughts, len(steps), fields)
        if not err:
            clean = [{k: str(x[k]).strip() for k in fields} for x in thoughts]
            nh = len(t["history"])
            return T.save_thoughts(d, style, clean[:nh], clean[nh:], model=model)
        feedback = f"\n\nPrevious answer rejected: {err}. Answer again."
    raise RuntimeError(f"reasoning failed validation: {err}")


def _unwrap(t, fields, depth=0):
    """Some replies nest each entry ({"thoughts": {...}} / {"output": {...}}): find the dict with the fields."""
    if not isinstance(t, dict) or depth > 3:
        return t
    if all(str(t.get(k) or "").strip() for k in fields if k != "evaluation_previous_goal"):
        return t
    for v in t.values():
        if isinstance(v, dict):
            u = _unwrap(v, fields, depth + 1)
            if isinstance(u, dict) and all(k in u for k in fields if k != "evaluation_previous_goal"):
                return u
    return t


def _validate(thoughts, n, fields):
    if not isinstance(thoughts, list) or len(thoughts) != n:
        return f"need exactly {n} thoughts"
    for i, t in enumerate(thoughts, 1):
        if not isinstance(t, dict) or any(not str(t.get(k) or "").strip() for k in fields):
            return f"step {i} is missing a field"
        text = " ".join(str(t[k]) for k in fields)
        m = FORBIDDEN.search(text)
        if m:
            return f"step {i} mentions {m.group(0)!r}, which the agent cannot know or see"
    return None
