"""Stage 5 judge — an adapter over evaluation/macro_judge.py for GENERATED tasks.

macro_judge builds its reference from a human gold span; generated tasks have none, so
the reference here is the task specification itself: the sampled target (control, option,
state that must survive) and the expected server evidence. Everything else — the system
prompt, rubric principles, the macro's rubric (+ visual criteria), the evidence digest
and best-of-3 voting — is macro_judge's, so generation is judged like evaluation.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlencode

from annotation import macros as registry
from evaluation import macro_judge as mj
from evaluation.trajectory import _parse_ts, merge_server_log


def reference(task):
    """The task specification as the judge's reference: the target in words and the evidence
    the site must show (a request, the data it changes, or the clipboard text)."""
    from datagen import checks, kinds
    c, o, chk = task["control"], task["option"], task["check"]
    if c["kind"] == "link":
        what = f"the sort link {o['text']!r}"
    elif c["kind"] == "select":
        what = f"the {c.get('label') or c.get('placeholder') or c.get('name') or 'select'!r} select menu set to {o['text']!r}"
    else:
        what = f"{kinds.of(c).describe(c).get('type')}: {json.dumps(kinds.of(c).say(c, o), ensure_ascii=False)[:600]}"
    lines = [f"Target: {what} on the page {c['page']} ({c.get('page_title', '')})."]
    if c.get("opener"):
        lines.append(f"The control is revealed by clicking {c['opener'].get('text')!r} first.")
    if chk.get("kind") == "request":
        want = {**chk.get("params", {}), **chk.get("keep", {})}
        lines.append(f"Expected server evidence: {chk['method']} {chk['path']}"
                     f"{'?' + urlencode(want, doseq=True) if want else ''} accepted (2xx/3xx)"
                     + (f", and the last request to {chk['path']} still carries {want}." if chk.get("final", True) and want else "."))
    else:
        lines.append("Expected evidence: " + checks.describe(chk) + ".")
    if chk.get("keep"):
        lines.append(f"State that must stay active: {chk['keep']} (set earlier: "
                     f"{task['start']['kind'].replace('_', ' ')}).")
    return {"source": "task specification (generated task; exact target, no human recording)",
            "digest": "\n".join(lines)}


def data_changes_digest(attempt_dir, site, limit=8):
    """The attempt's data changes (privileged record) in a few lines, for state-checked macros."""
    p = Path(attempt_dir) / "data_changes.json"
    if not p.exists():
        return None
    rows = [c for c in (json.loads(p.read_text()) or []) if c.get("site") == site][:limit]
    out = []
    for c in rows:
        fields = {k: (str(v[1])[:60]) for k, v in (c.get("changed") or {}).items()} if c["op"] != "delete" else {}
        out.append(f"{c['op']} {c['collection']} #{c['item_id']} {json.dumps(fields, ensure_ascii=False)[:300]}")
    return out or ["(no data changed)"]


def evidence_events(steps, entries, final_url="", final_html=""):
    from datagen.executor import action_events
    events = merge_server_log(action_events(steps), entries)
    if final_url:
        last_t = max((e.get("timestamp") or "" for e in events), default="")
        events.append({"type": "observation", "url": final_url, "title": "", "snapshot": final_html,
                       "timestamp": last_t})
    return sorted(events, key=lambda e: str(_parse_ts(e.get("timestamp")) or ""))


def load_evidence(attempt_dir):
    d = Path(attempt_dir)
    rec = json.loads((d / "attempt.json").read_text())
    return {"rec": rec, "entries": json.loads((d / "server_log.json").read_text()),
            "html": (d / "final.html").read_text() if (d / "final.html").exists() else "", "dir": d}


def judge(task, attempt_dir, evidence=None):
    """{passed, why, votes, images} for the target macro of one executed attempt
    (`evidence` overrides what is read from attempt_dir — used by the negative controls)."""
    ev = evidence or load_evidence(attempt_dir)
    d, rec, entries, html = ev["dir"], ev["rec"], ev["entries"], ev["html"]
    events = evidence_events(rec.get("steps", []), entries, rec.get("final_url", ""), html)
    base = registry.canon(task["macro"])
    payload = {
        "principles": registry.rubric_principles(),
        "task_instruction": task["instruction"],
        "macro": base, "macro_description": registry.describe(base).get("description", ""),
        "rubric": registry.rubric(base),
        "subtask": task["subtask"],
        "reference": reference(task),
        "agent_evidence": mj.digest(events),
        "agent_final_answer": rec.get("answer") or "",
    }
    if task["check"].get("kind") == "state":
        payload["agent_data_changes"] = data_changes_digest(d, task["check"].get("site") or task["site"])
    images = None
    if task["check"].get("kind") == "answer":            # what was on screen when the agent answered
        shots = [d / s["screenshot"] for s in rec.get("steps", []) if s.get("type") == "answer"][-1:]
        shots = [p for p in shots if p.exists()]
        if shots:
            images = [mj._jpeg(p) for p in shots]
            payload["images"] = ["AGENT: the screen when it answered"]
    elif payload["rubric"].get("visual"):
        shots = [d / s["screenshot"] for s in rec.get("steps", []) if s.get("span") == "target"][:1]
        shots += [d / rec["final_screenshot"]] if rec.get("final_screenshot") else []
        shots = [p for p in shots if p.exists()]
        if shots:
            images = [mj._jpeg(p) for p in shots]
            payload["images"] = ["AGENT: before the macro"] * (len(shots) - 1) + ["AGENT: final screenshot"]
    verdict = mj.judge_instance(payload, images)
    return {**verdict, "images": len(images or [])}


def controls(run_dir, n=8, seed=0):
    """Negative controls for the judge on kept tasks of a run:
        empty         no actions; only the start-page request; final page = start page
        swapped       another kept task's successful evidence (different target)
        wrong_option  this task's own evidence, but the spec asks for a different option of the
                      same control (instruction and check rewritten to that option)
    A sound judge fails both. Returns {control: {"n", "passed", "rows"}}."""
    import random
    from datagen import config
    run_dir = Path(run_dir)
    tasks = {json.loads(x)["task_id"]: json.loads(x) for x in (run_dir / "tasks.jsonl").read_text().split("\n") if x}
    kept = [json.loads(x) for x in (run_dir / "kept.jsonl").read_text().split("\n") if x]
    rng = random.Random(seed)
    rng.shuffle(kept)
    kept = kept[:n]
    out = {"empty": [], "swapped": [], "wrong_option": []}
    for i, row in enumerate(kept):
        t = tasks[row["task_id"]]
        ev = load_evidence(config.ROOT / row["dir"])
        start = [e for e in ev["entries"] if e.get("method") == "GET"][:1]
        empty = {**ev, "rec": {"steps": [], "final_url": ev["rec"].get("start_url", "")}, "entries": start, "html": ""}
        out["empty"].append((row["task_id"], judge(t, None, evidence=empty)))
        alts = [o for o in t["control"].get("options", []) if str(o.get("value", "")).strip()
                and o["value"] != t["option"]["value"] and o.get("text")]
        if alts:
            alt = rng.choice(alts)
            wrong = json.loads(json.dumps(t))
            wrong["option"] = alt
            wrong["check"]["params"] = {k: alt["value"] for k in t["check"]["params"]}
            for f in ("instruction", "subtask"):
                wrong[f] = t[f].replace(t["option"]["text"], alt["text"])
            if wrong["instruction"] != t["instruction"]:
                out["wrong_option"].append((row["task_id"], judge(wrong, None, evidence=ev)))
        other = kept[(i + 1) % len(kept)]
        if other["task_id"] != row["task_id"]:
            out["swapped"].append((row["task_id"], judge(t, None, evidence=load_evidence(config.ROOT / other["dir"]))))
    return {k: {"n": len(v), "passed": sum(1 for _t, r in v if r["passed"]),
                "rows": [{"task_id": tid, **r} for tid, r in v]} for k, v in out.items()}
