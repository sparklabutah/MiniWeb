"""One browsable view of every kept synthetic trajectory, across all runs.

`python -m datagen view` writes data/datagen/viewer/: index.html (families -> macros -> counts)
and one page per macro listing all its kept trajectories (instruction, site, run, start kind, the
judge's reason, every step's screenshot with its action, the final screen). Pages reference the
screenshots in place (../runs/<run>/accepted/<task>/...), so serve data/datagen/ over HTTP:

    cd data/datagen && python3 -m http.server 8765    ->  http://localhost:8765/viewer/
"""
from __future__ import annotations

import html
import json
from collections import defaultdict
from pathlib import Path

from datagen import config
from datagen import trajectory as T
from datagen.export import _fmt_action

# visuomotor families: the user's grouping (2026-09-26), with the macros it left unassigned placed
# 2026-09-28 (agreed): compare -> form transaction; feedback_by_text, write_executable_program,
# edit_by_textbox -> text entry; save_by_form, reveal_by_2fa -> out-of-page I/O; search_by_playback ->
# drag & gesture; count_entries -> reasoning; carry_info_cross_site -> navigation. One adapter each.
FAMILIES = {
    "Drag & gesture": ["edit_by_ranking", "reposition_by_drag", "search_by_pan_zoom", "sign_by_freeformdrawing",
                       "filter_by_slider", "search_by_playback"],
    "Discrete selection": ["feedback_by_star", "feedback_by_react", "play_by_playback", "delete_from_table",
                           "filter_by_options", "filter_by_date_range", "sort_by_form", "filter_by_dropdown",
                           "toggle_relationship"],
    "Text entry": ["sign_by_text", "compute_by_tool", "translate_by_query", "edit_by_cell", "message_from_free_text",
                   "search", "feedback_by_text", "write_executable_program", "edit_by_textbox"],
    "Form transaction": ["cancel_by_form", "book_by_form", "checkout_by_form", "share_by_form", "pay_by_form",
                         "configure_by_form", "edit_by_form", "authenticate_by_form", "create_by_form", "compare_by_form"],
    "Navigation": ["get_nav_route", "join_meeting", "navigate_by_route", "carry_info_cross_site"],
    "Out-of-page I/O": ["edit_by_image", "copy_content", "export", "upload_file", "save_by_form", "reveal_by_2fa"],
    "Reasoning base": ["report_information", "count_entries"],
}
FAMILY_OF = {m: f for f, ms in FAMILIES.items() for m in ms}

STYLE = ("body{font:14px system-ui;margin:16px;background:#fafafa;color:#222}a{color:#1a5fd6}"
         "table{border-collapse:collapse;margin:8px 0 20px}td,th{border:1px solid #ddd;padding:4px 10px;text-align:left}"
         "th{background:#f0f0f0}section{background:#fff;margin:0 0 20px;padding:12px;border:1px solid #ddd;"
         "border-radius:8px}.strip{display:flex;gap:8px;overflow-x:auto}figure{margin:0;min-width:260px;max-width:260px}"
         "figure.history{opacity:.6}img{width:260px;border:1px solid #ccc}figcaption{font-size:12px;word-break:break-word}"
         ".ins{font-size:15px;font-weight:600}.meta{color:#555;font-size:12px}")


def _kept_rows(include_retired=False):
    """{task_id: kept row + run} across every run directory (without the retired ones, config.retired)."""
    out = {}
    gone = (lambda run, row: False) if include_retired else config.retired()
    for run in sorted(p for p in config.RUNS_DIR.iterdir() if p.is_dir() and not p.name.startswith("_")):
        kp = run / "kept.jsonl"
        if not kp.exists():
            continue
        for line in kp.read_text().split("\n"):
            if line.strip():
                r = json.loads(line)
                if not gone(run.name, r):
                    out[r["task_id"]] = {**r, "run": run.name}
    return out


def write_viewer(out_dir=None):
    """-> (index path, trajectories listed)."""
    out = Path(out_dir) if out_dir else config.DATAGEN_DIR / "viewer"
    out.mkdir(parents=True, exist_ok=True)
    kept = _kept_rows()
    by_macro = defaultdict(list)
    for tid, r in kept.items():
        d = config.RUNS_DIR / r["run"] / "accepted" / tid
        if (d / "trajectory.json").exists():
            by_macro[r["macro"]].append((d, r))
    for macro, items in by_macro.items():
        items.sort(key=lambda x: (x[1]["site"], x[1]["task_id"]))
        (out / f"{macro}.html").write_text(_macro_page(macro, items, out))
    fam_rows = defaultdict(list)
    for macro, items in by_macro.items():
        fam_rows[FAMILY_OF.get(macro, "Other")].append((macro, len(items), len({r["site"] for _, r in items})))
    order = list(FAMILIES) + ["Other"]
    parts = [f"<h1>Synthetic trajectories ({sum(len(v) for v in by_macro.values())} kept, {len(by_macro)} macros)</h1>",
             "<p>Every kept trajectory across all datagen runs: it passed the backend check and the flash judge. "
             "Click a macro to see all of its trajectories.</p>"]
    for fam in order:
        rows = sorted(fam_rows.get(fam, []))
        if not rows:
            continue
        total = sum(n for _, n, _ in rows)
        parts.append(f"<h2>{html.escape(fam)} ({total})</h2><table><tr><th>Macro</th><th>Kept</th><th>Sites</th></tr>" +
                     "".join(f"<tr><td><a href='{m}.html'>{html.escape(m)}</a></td><td>{n}</td><td>{s}</td></tr>"
                             for m, n, s in rows) + "</table>")
    page = f"<!doctype html><meta charset='utf-8'><title>Synthetic trajectories</title><style>{STYLE}</style>" + "".join(parts)
    (out / "index.html").write_text(page)
    return out / "index.html", sum(len(v) for v in by_macro.values())


def _macro_page(macro, items, out):
    sites = sorted({r["site"] for _, r in items})
    parts = [f"<p><a href='index.html'>&larr; all macros</a></p><h1>{html.escape(macro)} ({len(items)} kept)</h1>",
             "<p class='meta'>Sites: " + ", ".join(f"<a href='#{html.escape(s)}'>{html.escape(s)}</a>" for s in sites) +
             ". Faded frames are the preceding step of a mid-chain task. Actions are in recording-viewport pixels.</p>"]
    seen_site = set()
    for d, r in items:
        t = T.load(d)
        rel = "../" + d.relative_to(config.DATAGEN_DIR).as_posix()
        anchor = "" if r["site"] in seen_site else f" id='{html.escape(r['site'])}'"
        seen_site.add(r["site"])
        cells = []
        for label in ("history", "steps"):
            for s in t[label]:
                src = f"{rel}/{s['screenshot']}"
                cells.append(f"<figure class='{label}'><a href='{src}'><img loading='lazy' src='{src}'></a>"
                             f"<figcaption><code>{html.escape(_fmt_action(s['action']))}</code></figcaption></figure>")
        if t.get("final_screenshot"):
            src = f"{rel}/{t['final_screenshot']}"
            cells.append(f"<figure><a href='{src}'><img loading='lazy' src='{src}'></a><figcaption>final screen</figcaption></figure>")
        j = r.get("judge") or {}
        op = f" · op {html.escape(t['op'])}" if t.get("op") else ""
        parts.append(f"<section{anchor}><p class='ins'>{html.escape(t['instruction'])}</p>"
                     f"<p class='meta'>{html.escape(r['site'])} · run {html.escape(r['run'])} · start {html.escape(t.get('start_kind') or '')}"
                     f"{op} · {len(t['steps'])} steps · <a href='{rel}/trajectory.json'>trajectory.json</a><br>"
                     f"judge: {html.escape(str(j.get('why', ''))[:400])}</p><div class='strip'>{''.join(cells)}</div></section>")
    return (f"<!doctype html><meta charset='utf-8'><title>{html.escape(macro)}</title><style>{STYLE}</style>" + "".join(parts))
