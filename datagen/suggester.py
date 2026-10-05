"""Stage 3 — suggester. Writes the natural-language task around the SAMPLED parameters
(it never chooses them) and attaches the expected backend check.

The LLM sees the site map context (site, page, the control's label and a few options,
what else is set) and only writes wording: the full instruction and one subtask line per
step. The expected check comes from the sampler (the probed signature), and is emitted
both as the datagen check and as an evaluation/verifiers.py spec.
"""
from __future__ import annotations

import hashlib
import json
import re

from datagen import checks, config
from datagen.browser import site_name

SYSTEM = ("You write realistic instructions a person would give a web assistant. You are given the exact "
          "parameters of the task (which control, which option); do not change, add or drop any. Mention "
          "every option by its visible text (you may drop punctuation/casing, not words). Never mention "
          "HTML, CSS, URL parameters, field names in snake_case, or the word 'dropdown' unless natural. "
          "Reply ONLY JSON.")

STYLE = {"imperative": "a short direct command (5-15 words)",
         "goal": "state the goal/reason, then what to do (1-2 sentences)",
         "conversational": "a casual request as if typed to an assistant (1-2 sentences)"}


def _control_desc(ctrl):
    from datagen import kinds
    return kinds.of(ctrl).describe(ctrl)


def _say(ctrl, arg):
    from datagen import kinds
    return kinds.of(ctrl).say(ctrl, arg) if ctrl else arg["text"]


def _mentions_of(ctrl, arg):
    from datagen import kinds
    return kinds.of(ctrl).mentions(arg) if ctrl else [arg["text"]]


def _forbidden_of(ctrl, arg):
    from datagen import kinds
    return kinds.of(ctrl).forbidden(arg) if ctrl else []


def _tokens(s):
    return [w for w in re.findall(r"[a-z0-9]+", str(s).casefold()) if len(w) > 1 or w.isdigit()]


def mentions(instruction, option_text):
    """Every word of the option's visible text appears in the instruction (order-free)."""
    have = set(_tokens(instruction))
    want = _tokens(option_text)
    return bool(want) and all(w in have for w in want)


def validate(t, out):
    ins = (out or {}).get("instruction", "")
    if not ins or len(ins) > 400:
        return "instruction missing or too long"
    for text in _mentions_of(t.get("control"), t["option"]):
        if not mentions(ins, text):
            return f"instruction must mention the option {text!r}"
    pre = t["start"].get("prefix")
    if pre:
        for text in _mentions_of(pre.get("control"), pre["option"]):
            if not mentions(ins, text):
                return f"instruction must also mention {text!r}"
    for text in _forbidden_of(t.get("control"), t["option"]):
        if _tokens(text) and re.search(r"(^|\W)" + re.escape(text.casefold()) + r"($|\W)", ins.casefold()):
            return f"instruction must not give away the answer {text!r}"
    bare = ins
    for text in _mentions_of(t.get("control"), t["option"]):         # a value may contain '_' (a username)
        bare = re.sub(re.escape(str(text)), " ", bare, flags=re.I)
    if re.search(r"\b\w+_\w+\b|\[name=|<select|\?[a-z_]+=", bare):
        return "instruction leaks field names / markup"
    return None


def suggest(t, model=config.MODEL_SUGGEST, tries=3):
    from annotation import macros as registry
    from helpers.llm import call_llm
    site = t["site"]
    steps = []
    pre = t["start"].get("prefix")
    if pre:
        steps.append({"step": "first", "macro": pre["macro"], "control": _control_desc(pre["control"]),
                      "option": _say(pre["control"], pre["option"])})
    steps.append({"step": "then" if pre else "only", "macro": t["macro"], "control": _control_desc(t["control"]),
                  "option": _say(t["control"], t["option"])})
    ctx = {"site": site_name(site), "page_title": t["control"].get("page_title", ""),
           "macro_meanings": {s["macro"]: registry.describe(s["macro"]).get("description") for s in steps},
           "steps": steps, "style": STYLE[t.get("phrasing", "imperative")]}
    if t["start"]["kind"] == "preset":
        p = t["start"]["preset"]
        ctx["already_set_on_page"] = {"control": _control_desc(p["control"])["label"], "option": p["option"]["text"],
                                      "note": "already applied when the user starts; keep it, you may mention it or not"}
    prompt = json.dumps({**ctx, "output": {"instruction": "the full instruction covering all steps in order",
                                           "subtasks": ["one short imperative line per step, same order"]}},
                        ensure_ascii=False)
    feedback = ""
    for _ in range(tries):
        raw = call_llm(prompt + feedback, system=SYSTEM, json_mode=True, model=model, max_tokens=2000,
                       temperature=0.9)
        try:
            out = json.loads(raw or "")
        except ValueError:
            out = None
        err = validate(t, out) if isinstance(out, dict) else "not JSON"
        if not err:
            subs = out.get("subtasks") or []
            if len(subs) != len(steps):
                subs = [f"Set {s['control']['label'] or 'the control'} to {s['option']}" for s in steps]
            return out["instruction"].strip(), [str(s).strip() for s in subs]
        feedback = f"\n\nYour previous answer was rejected: {err}. Fix it."
    return None, None


def make_task(t, run_id, model=config.MODEL_SUGGEST):
    """Tuple -> task dict (or None if no valid wording)."""
    instruction, subtasks = suggest(t, model=model)
    if not instruction:
        return None
    tid = f"{t['macro']}-{t['site']}-" + hashlib.sha1((t["param_id"] + run_id).encode()).hexdigest()[:8]
    task = {"task_id": tid, "run_id": run_id, **t, "instruction": instruction,
            "subtask": subtasks[-1], "prefix_subtask": subtasks[0] if len(subtasks) > 1 else None,
            "verifier": checks.verifier_spec(tid, t["macro"], t["check"])}
    if t["start"].get("prefix"):
        pre = t["start"]["prefix"]
        pre["check"] = checks.build_check(pre["control"]["signature"], pre["option"]["value"])
    return task
