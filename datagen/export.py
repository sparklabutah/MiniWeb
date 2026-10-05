"""Exports of a run — where student-specific choices are made.

    export/train[.<style>].jsonl  one training trajectory per line: instruction, screenshots and
                                  actions in the chosen coordinate convention, plus thoughts of
                                  the chosen style (default: none). No privileged fields.
    audit/<macro>.html            a page to hand-check accepted trajectories (the judge audit,
    audit/<macro>_sample.jsonl    ~30 per macro family), with an empty verdict column to fill.

Neither export reads elements.json (the privileged element side file) — tests enforce that
nothing from it reaches these files.
"""
from __future__ import annotations

import html
import json
import random
from pathlib import Path

from datagen import config
from datagen import trajectory as T
from datagen.actions import CoordConvention, to_student


def _trajectories(run_dir):
    for p in sorted((Path(run_dir) / "accepted").glob("*/trajectory.json")):
        yield p.parent


def export_training(run_dir, coord=None, thought_style="none", out=None):
    """-> (path, n written, {reason: n skipped}). A trajectory without the requested thought
    style, or failing validation, is skipped (and counted), never half-exported."""
    run_dir = Path(run_dir)
    conv = CoordConvention.from_dict(coord or config.COORD)
    style = None if thought_style in (None, "", "none") else thought_style
    out = Path(out) if out else run_dir / "export" / (f"train.{style}.jsonl" if style else "train.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    lines, skipped = [], {}
    for d in _trajectories(run_dir):
        probs = T.validate(d)
        if probs:
            skipped["invalid"] = skipped.get("invalid", 0) + 1
            continue
        t = T.load(d)
        th = T.load_thoughts(d, style) if style else None
        if style and th is None:
            skipped[f"no {style} thoughts"] = skipped.get(f"no {style} thoughts", 0) + 1
            continue
        vp = tuple(t["viewport"])
        base = d.relative_to(run_dir).as_posix()

        def rows(part):
            out_rows = []
            for n, s in enumerate(t[part]):
                row = {"screenshot": f"{base}/{s['screenshot']}", "action": to_student(s["action"], conv, vp)}
                if th:
                    row["thought"] = th[part][n]
                out_rows.append(row)
            return out_rows
        rec = {"id": t["id"], "macro": t["macro"], "op": t.get("op"), "instruction": t["instruction"], "viewport": t["viewport"],
               "coords": conv.to_dict(), "thought_style": style or "none",
               "history": rows("history"), "steps": rows("steps"),
               "final_screenshot": f"{base}/{t['final_screenshot']}" if t.get("final_screenshot") else None}
        lines.append(json.dumps(rec, ensure_ascii=False))
    out.write_text("\n".join(lines) + ("\n" if lines else ""))
    return out, len(lines), skipped


def _fmt_action(a):
    bits = [a["type"]]
    for k in ("x", "y", "x2", "y2", "dx", "dy"):
        if k in a:
            bits.append(f"{k}={a[k]}")
    if "text" in a:
        bits.append(repr(a["text"]))
    if "key" in a:
        bits.append(a["key"])
    if "file" in a:
        bits.append(repr(a["file"]))
    if "url" in a:
        bits.append(a["url"])
    if "index" in a:
        bits.append(f"tab {a['index']}")
    if "strokes" in a:
        bits.append(f"{len(a['strokes'])} strokes")
    return " ".join(bits)


def export_audit(run_dir, macro, n=30, seed=0, thought_style=None):
    """Random sample of accepted trajectories of `macro` -> audit/<macro>.html + _sample.jsonl.
    Shows thoughts of `thought_style` (default: the first style a trajectory has, if any)."""
    run_dir = Path(run_dir)
    kept = {}
    kp = run_dir / "kept.jsonl"
    if kp.exists():
        for line in kp.read_text().split("\n"):
            if line.strip():
                r = json.loads(line)
                kept[r["task_id"]] = r
    trajs = [(d, T.load(d)) for d in _trajectories(run_dir)]
    trajs = [(d, t) for d, t in trajs if t["macro"] == macro]
    random.Random(seed).shuffle(trajs)
    trajs = trajs[:n]
    out = run_dir / "audit"
    out.mkdir(exist_ok=True)
    rows, parts = [], []
    for d, t in trajs:
        k = kept.get(t["id"], {})
        have = T.styles(d)
        style = thought_style if thought_style in have else (have[0] if have and thought_style is None else None)
        th = T.load_thoughts(d, style) if style else None
        rows.append({"id": t["id"], "site": t["site"], "instruction": t["instruction"], "start_kind": t["start_kind"],
                     "judge": k.get("judge"), "backend": k.get("backend"), "dir": d.relative_to(run_dir).as_posix(),
                     "human_verdict": None, "human_notes": ""})
        rel = "../" + d.relative_to(run_dir).as_posix()
        cells = []
        for label in ("history", "steps"):
            for i, s in enumerate(t[label]):
                th_txt = ""
                if th:
                    th_txt = "<br>" + " / ".join(f"<b>{html.escape(k2)}</b>: {html.escape(str(v))}"
                                                 for k2, v in (th[label][i] or {}).items())
                cells.append(f"<figure class='{label}'><a href='{rel}/{s['screenshot']}'><img src='{rel}/{s['screenshot']}'></a>"
                             f"<figcaption><code>{html.escape(_fmt_action(s['action']))}</code>{th_txt}</figcaption></figure>")
        if t.get("final_screenshot"):
            cells.append(f"<figure><a href='{rel}/{t['final_screenshot']}'><img src='{rel}/{t['final_screenshot']}'></a>"
                         f"<figcaption>final screen</figcaption></figure>")
        j = k.get("judge") or {}
        parts.append(f"<section><h2>{html.escape(t['id'])}</h2><p class='ins'>{html.escape(t['instruction'])}</p>"
                     f"<p class='meta'>site {html.escape(t['site'])} · start {t['start_kind']} · thoughts "
                     f"{html.escape(style or 'none')} · judge {j.get('votes', '?')} — {html.escape(str(j.get('why', '')))}"
                     f"<br>backend: {html.escape(str(k.get('backend', '')))}</p><div class='strip'>{''.join(cells)}</div>"
                     f"<p class='verdict'>verdict: ☐ correct ☐ wrong — notes: ____________</p></section>")
    page = ("<!doctype html><meta charset='utf-8'><title>Audit " + html.escape(macro) + "</title><style>"
            "body{font:14px system-ui;margin:16px;background:#fafafa;color:#222}section{background:#fff;margin:0 0 24px;"
            "padding:12px;border:1px solid #ddd;border-radius:8px}.strip{display:flex;gap:8px;overflow-x:auto}"
            "figure{margin:0;min-width:320px;max-width:320px}figure.history{opacity:.65}img{width:320px;border:1px solid #ccc}"
            "figcaption{font-size:12px}.ins{font-size:15px;font-weight:600}.meta{color:#555;font-size:12px}"
            "</style><h1>Judge audit — " + html.escape(macro) + f" ({len(trajs)} accepted trajectories)</h1>"
            "<p>Faded frames are history (the preceding macro of a mid-chain task). Actions are in recording-viewport "
            "pixels. Check that each accepted trajectory really completes the instruction.</p>" + "".join(parts))
    (out / f"{macro}.html").write_text(page)
    (out / f"{macro}_sample.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    return out / f"{macro}.html", len(trajs)
