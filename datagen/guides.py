"""Stage 1 — guidance summarizer. An LLM reads the human sub-trajectories of ONE macro
(train sites only) and writes a site-agnostic guide: steps, variants, what to watch for.
Written once per macro, reused for every task (data/datagen/guides/<macro>.{json,md}).

The guide is privileged executor context: it shapes how scripts act, but it never
enters a training trajectory (the reasoning stage is told never to mention it).
"""
from __future__ import annotations

import json
import re
import time

from datagen import config

SYSTEM = ("You distill human demonstrations of ONE web-UI macro into a short, site-agnostic procedure "
          "for someone who will drive a browser with mouse and keyboard only. Generalize across sites; "
          "never name a specific site, product, value or CSS selector. Reply ONLY JSON.")

SCHEMA = {
    "summary": "one sentence: what the macro achieves",
    "preconditions": ["what must be true / on screen before starting"],
    "steps": ["ordered, concrete physical steps (look for X, click Y, ...)"],
    "variants": [{"when": "a UI variation seen in the demos", "do": "how to handle it"}],
    "watch_for": ["visual cues that the step worked or went wrong"],
    "completion_signal": "how to tell the macro is done (page/URL/listing change)",
    "pitfalls": ["common mistakes"],
}


def _site_of_span(actions):
    for a in actions:
        m = re.search(r"/sites/([^/?#]+)", a.get("url") or "")
        if m:
            return m.group(1)
    return None


def demonstrations(macro, train_sites, limit=24, context=2):
    """Human occurrences of `macro` whose span happened on a train site."""
    from annotation.macro_browser import index, task_detail
    from annotation.macros import canon
    occs = [o for m, v in index()["macros"].items() if canon(m) == macro for o in v if o.get("span")]
    out, train = [], set(train_sites)
    for o in occs:
        a, t = o["key"].split("/", 1)
        d = task_detail(a, t)
        if not d:
            continue
        lo, hi = o["span"]
        span = d["actions"][lo - 1:hi]
        site = _site_of_span(span)
        if site not in train:
            continue
        before = d["actions"][max(0, lo - 1 - context):lo - 1]
        out.append({"key": o["key"], "instance": o["instance"], "site": site,
                    "instruction": d["instruction"], "subtask": o.get("subtask", ""),
                    "context_before": [_line(x) for x in before], "span": [_line(x) for x in span],
                    "end_frame": (o["key"], span[-1].get("frame")) if span else None})
        if len(out) >= limit:
            break
    return out


def _line(a):
    s = f"{a['action']} {a['target'][:90]}"
    if a.get("value"):
        s += f" = {a['value'][:50]!r}"
    return s


def write_guide(macro, train_sites, model=config.MODEL_GUIDE, frames=3, force=False):
    config.GUIDES_DIR.mkdir(parents=True, exist_ok=True)
    jpath = config.GUIDES_DIR / f"{macro}.json"
    if jpath.exists() and not force:
        return json.loads(jpath.read_text())
    from annotation import macros as registry
    from annotation.storage import ANNOTATIONS_DIR
    from helpers.llm import call_llm
    demos = demonstrations(macro, train_sites)
    desc = registry.describe(macro)
    # no human demonstration on a train site (the macro's only demos are on held-out sites):
    # the guide is written from the registry's description and judge rubric alone
    source = "demonstrations" if demos else "registry"
    prompt = {
        "macro": macro, "description": desc.get("description"), "example": desc.get("example"),
        "starts_at": desc.get("span_start"), "ends_at": desc.get("span_end"),
        "judge_rubric": registry.rubric(macro),
        "demonstrations": [{k: d[k] for k in ("instruction", "subtask", "context_before", "span")} for d in demos],
        "note": ("Each demonstration lists the recorded UI events of one human performing the macro "
                 "(select = an option was chosen in a dropdown; submit = a form was submitted). "
                 "Screenshots attached show end states of a few demonstrations." if demos else
                 "No human demonstration is available: write the procedure from the description, example and "
                 "rubric, for the common ways web apps present this interaction."),
        "output_schema": SCHEMA,
    }
    images = []
    for d in demos[:frames]:
        if d["end_frame"] and d["end_frame"][1]:
            p = ANNOTATIONS_DIR / d["end_frame"][0] / d["end_frame"][1]
            if p.exists():
                images.append(str(p))
    raw = None
    for _ in range(3):
        raw = call_llm(json.dumps(prompt, ensure_ascii=False), system=SYSTEM, json_mode=True,
                       model=model, max_tokens=6000, temperature=0.2, images=images or None)
        try:
            guide = json.loads(raw or "")
            if isinstance(guide, dict) and guide.get("steps"):
                break
        except ValueError:
            guide = None
    if not guide:
        raise RuntimeError(f"guide LLM returned nothing usable for {macro}: {raw!r:.200}")
    guide = {"macro": macro, **{k: guide.get(k) for k in SCHEMA},
             "summary": guide.get("summary") or desc.get("description"),
             "_provenance": {"model": model, "created": time.strftime("%Y-%m-%d"), "train_sites_only": True,
                             "source": source,
                             "n_demos": len(demos), "sources": [f"{d['key']}#{d['instance']}" for d in demos],
                             "frames": len(images)}}
    jpath.write_text(json.dumps(guide, indent=1, ensure_ascii=False))
    (config.GUIDES_DIR / f"{macro}.md").write_text(render_md(guide))
    return guide


def render_md(g):
    lines = [f"# Guide: {g['macro']}", "", g.get("summary") or "", ""]
    for title, key in (("Preconditions", "preconditions"), ("Steps", "steps"), ("Watch for", "watch_for"),
                       ("Pitfalls", "pitfalls")):
        items = g.get(key) or []
        if items:
            lines += [f"## {title}", ""] + [f"{i}. {x}" if key == "steps" else f"- {x}" for i, x in enumerate(items, 1)] + [""]
    if g.get("variants"):
        lines += ["## Variants", ""] + [f"- **{v.get('when')}** — {v.get('do')}" for v in g["variants"]] + [""]
    if g.get("completion_signal"):
        lines += ["## Done when", "", g["completion_signal"], ""]
    p = g.get("_provenance") or {}
    lines += [f"_Distilled by {p.get('model')} on {p.get('created')} from {p.get('n_demos')} human demonstrations "
              f"on train sites only._" if p.get("n_demos") else
              f"_Written by {p.get('model')} on {p.get('created')} from the macro registry (no human demonstration on a "
              f"train site)._", ""]
    return "\n".join(lines)


def load_guide(macro):
    p = config.GUIDES_DIR / f"{macro}.json"
    if not p.exists():
        raise FileNotFoundError(f"no guide for {macro} — run `python -m datagen guide --macro {macro}`")
    return json.loads(p.read_text())


def guide_text(g):
    """The guide as executor prompt text (provenance dropped)."""
    return json.dumps({k: v for k, v in g.items() if not k.startswith("_")}, indent=1, ensure_ascii=False)
