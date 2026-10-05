"""The kept trajectory, student-neutral (accepted/<task>/).

    trajectory.json      FORMAT datagen.trajectory/v2 — instruction, screenshots and actions in
                         recording-viewport PIXELS; no thoughts, no coordinate convention
    screenshots/         frames (hard links to the episode's shots)
    elements.json        privileged element side file (datagen/elements.py) — never exported
    thoughts/<style>.json  optional, one file per thought style (browser_use, short, ...), each
                         aligned with trajectory.json: {"history": [...], "steps": [...]}

Student-specific choices — thought style, coordinate convention, action space — are applied
at export (datagen/export.py), so several can coexist for the same data.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

from datagen import config, elements

FORMAT = "datagen.trajectory/v2"
THOUGHTS_FORMAT = "datagen.thoughts/v1"
_ACTION_KEYS = ("type", "x", "y", "x2", "y2", "dx", "dy", "text", "key", "button", "path", "strokes", "file", "url", "index")
_NEEDS = {"click": ("x", "y"), "double_click": ("x", "y"), "hover": ("x", "y"), "scroll": ("x", "y", "dy"),
          "type": ("text",), "key": ("key",), "drag": ("x", "y", "x2", "y2"), "draw": ("x", "y", "strokes"),
          "upload": ("x", "y", "file"), "answer": ("text",), "goto": ("url",), "new_tab": ("url",),
          "switch_tab": ("index",)}


def pixel_action(step):
    return {k: step[k] for k in _ACTION_KEYS if k in step}


def _place(src, dst):
    """Hard-link a recorded frame into the trajectory dir (copy across filesystems)."""
    if dst.exists():
        return
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def build(task, rec, attempt_dir, out_dir):
    """Write trajectory.json (+ screenshots, elements.json) for one kept attempt. No LLM."""
    src, out = Path(attempt_dir), Path(out_dir)
    (out / "screenshots").mkdir(parents=True, exist_ok=True)
    parts = {"prefix": [], "target": []}
    for s in rec["steps"]:
        name = Path(s["screenshot"]).name
        _place(src / s["screenshot"], out / "screenshots" / name)
        parts[s.get("span", "target")].append({"i": s["i"], "screenshot": f"screenshots/{name}",
                                               "action": pixel_action(s)})
    final = None
    if rec.get("final_screenshot") and (src / rec["final_screenshot"]).exists():
        _place(src / rec["final_screenshot"], out / "screenshots" / "final.png")
        final = "screenshots/final.png"
    traj = {"format": FORMAT, "id": task["task_id"], "macro": task["macro"], "op": task.get("op"), "site": task["site"],
            "instruction": task["instruction"], "subtask": task["subtask"], "start_kind": task["start"]["kind"],
            "viewport": list(config.VIEWPORT), "history_macro": (task["start"].get("prefix") or {}).get("macro"),
            "history": parts["prefix"], "steps": parts["target"], "final_screenshot": final}
    (out / "trajectory.json").write_text(json.dumps(traj, indent=1, ensure_ascii=False))
    doc = elements.load_attempt(src) or elements.write_attempt(src, rec["steps"])
    (out / "elements.json").write_text(json.dumps(elements.for_trajectory(doc, traj), indent=1,
                                                  ensure_ascii=False, default=str))
    return traj


def load(d):
    return json.loads((Path(d) / "trajectory.json").read_text())


def validate(d):
    """Problems with a trajectory dir ([] = valid). Thoughts are optional."""
    d = Path(d)
    try:
        t = load(d)
    except (OSError, ValueError) as exc:
        return [f"unreadable trajectory.json: {exc}"]
    probs = []
    if t.get("format") != FORMAT:
        probs.append(f"format {t.get('format')!r} != {FORMAT} (run `python -m datagen upgrade`)")
    for k in ("id", "macro", "instruction", "viewport", "history", "steps"):
        if k not in t:
            probs.append(f"missing {k}")
    if not t.get("steps"):
        probs.append("no steps")
    for part in ("history", "steps"):
        for n, s in enumerate(t.get(part) or []):
            a = s.get("action") or {}
            need = _NEEDS.get(a.get("type"))
            if need is None:
                probs.append(f"{part}[{n}]: unknown action {a.get('type')!r}")
            elif any(k not in a for k in need):
                probs.append(f"{part}[{n}]: {a.get('type')} lacks {[k for k in need if k not in a]}")
            if not (d / s.get("screenshot", "")).is_file():
                probs.append(f"{part}[{n}]: missing frame {s.get('screenshot')}")
    for style in styles(d):
        th = load_thoughts(d, style)
        for part in ("history", "steps"):
            if len(th.get(part) or []) != len(t.get(part) or []):
                probs.append(f"thoughts/{style}.json: {part} not aligned")
    return probs


# ── thoughts, one file per style ─────────────────────────────────────────────

def thoughts_path(d, style):
    return Path(d) / "thoughts" / f"{style}.json"


def styles(d):
    return sorted(p.stem for p in (Path(d) / "thoughts").glob("*.json"))


def load_thoughts(d, style):
    p = thoughts_path(d, style)
    return json.loads(p.read_text()) if p.exists() else None


def save_thoughts(d, style, history, steps, model=None, source="generated"):
    p = thoughts_path(d, style)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"format": THOUGHTS_FORMAT, "style": style, "model": model, "source": source,
                             "created": time.strftime("%Y-%m-%d"), "history": history, "steps": steps},
                            indent=1, ensure_ascii=False))
    return p


# ── migration of v1 trajectories (thoughts + converted actions embedded) ─────

def migrate_v1(d, task=None):
    """v1 -> v2 in place: embedded thoughts move VERBATIM to thoughts/<style>.json, actions become
    the logged pixel `raw_action`s; the original file is kept as trajectory.v1.json. Idempotent."""
    d = Path(d)
    t = load(d)
    if t.get("format") == FORMAT:
        return False
    backup = d / "trajectory.v1.json"
    if not backup.exists():
        shutil.copy2(d / "trajectory.json", backup)
    style = t.get("thought_style") or "browser_use"
    hist_th = [s.get("thought") for s in t.get("history", [])]
    step_th = [s.get("thought") for s in t.get("steps", [])]
    if any(hist_th + step_th) and not thoughts_path(d, style).exists():
        save_thoughts(d, style, hist_th, step_th, model=config.MODEL_REASON, source="migrated from trajectory v1")
    idx = iter(range(10 ** 6))

    def conv(s):
        name = Path(s["screenshot"]).name
        return {"i": int(name.split(".")[0]) if name.split(".")[0].isdigit() else next(idx),
                "screenshot": s["screenshot"], "action": dict(s["raw_action"])}
    v2 = {"format": FORMAT, "id": t["id"], "macro": t["macro"], "site": t["site"], "instruction": t["instruction"],
          "subtask": t.get("subtask", ""), "start_kind": t.get("start_kind"), "viewport": t["viewport"],
          "history_macro": t.get("history_macro"), "history": [conv(s) for s in t.get("history", [])],
          "steps": [conv(s) for s in t.get("steps", [])], "final_screenshot": t.get("final_screenshot")}
    (d / "trajectory.json").write_text(json.dumps(v2, indent=1, ensure_ascii=False))
    return True
