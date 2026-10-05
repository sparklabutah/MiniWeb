"""Browsable pages for WebMix evaluation runs (MiniWeb validation + WebArena-Lite-v2).

    python -m webmix.eval_viewer          # -> data/webmix/viewer/index.html
    cd data/webmix && python3 -m http.server 8766 --bind 127.0.0.1   ->  http://localhost:8766/viewer/

Per run: every task with its instruction, pass/fail and the grader's reason, then each step's screenshot
with the model's memory, its action, which model/adapter served it, and the action's result or error.
Per pair of runs over the same tasks (base vs an adapter): a table of where they differ, linking both.
browser-use keeps step screenshots under /tmp/browser_use_agent_*; they are copied into each task's
folder (screenshots/step_<n>.png) first, so the pages survive a /tmp cleanup.
"""
from __future__ import annotations

import html
import re
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WM = ROOT / "data" / "webmix"
OUT = WM / "viewer"

STYLE = ("body{font:14px system-ui;margin:16px;background:#fafafa;color:#222}a{color:#1a5fd6}"
         "table{border-collapse:collapse;margin:8px 0 20px}td,th{border:1px solid #ddd;padding:4px 8px;text-align:left;"
         "vertical-align:top}th{background:#f0f0f0}section{background:#fff;margin:0 0 20px;padding:12px;"
         "border:1px solid #ddd;border-radius:8px}.ok{color:#137333;font-weight:600}.fail{color:#c5221f;font-weight:600}"
         ".strip{display:flex;gap:10px;overflow-x:auto;padding-bottom:6px}figure{margin:0;min-width:300px;max-width:300px}"
         "img{width:300px;border:1px solid #ccc}figcaption{font-size:12px;word-break:break-word}"
         ".mem{color:#444}.act{font-family:ui-monospace,monospace;font-size:11px;background:#f4f4f4;padding:2px 4px}"
         ".err{color:#c5221f}.meta{color:#555;font-size:12px}.ins{font-size:15px;font-weight:600}"
         "details{font-size:11px;margin-top:4px}summary{cursor:pointer;color:#1a5fd6}"
         "pre{white-space:pre-wrap;word-break:break-word;max-height:360px;overflow:auto;background:#f6f6f6;padding:6px;margin:4px 0}")


def runs():
    """[(key, kind, dir)] of evaluation runs on disk."""
    out = []
    for d in sorted((WM / "eval").glob("*/")):
        if (d / "results.jsonl").exists():
            out.append((f"miniweb_{d.name}", "miniweb", d))
    for d in sorted((WM / "wa").glob("*/")):
        if (d / "results.jsonl").exists() and not d.name.startswith("_"):
            out.append((f"wa_{d.name}", "wa", d))
    return out


def instructions():
    ins = {}
    val = WM / "valgen" / "val_all.jsonl"
    if val.exists():
        for line in val.read_text().split("\n"):
            if line.strip():
                t = json.loads(line)
                ins[("miniweb", t["task_id"])] = t["instruction"]
    for p in (WM / "wa_lite_v2" / "config" / "envs" / "webarena" / "tasks").glob("[0-9]*.json"):
        t = json.loads(p.read_text())
        ins[("wa", str(t["task_id"]))] = t["intent"]
    return ins


def copy_screenshots(task_dir):
    """browser-use's /tmp step screenshots -> task_dir/screenshots; -> {step: relative path}."""
    h = task_dir / "history.json"
    if not h.exists():
        return {}
    shots = {}
    for i, st in enumerate(json.loads(h.read_text()).get("history", [])):
        src = (st.get("state") or {}).get("screenshot_path")
        dst = task_dir / "screenshots" / f"step_{i}.png"
        if not dst.exists() and src and Path(src).exists():
            dst.parent.mkdir(exist_ok=True)
            shutil.copy2(src, dst)
        if dst.exists():
            shots[i] = dst
    return shots


def load_results(d):
    rows = {}
    for line in (d / "results.jsonl").read_text().split("\n"):
        if line.strip():
            r = json.loads(line)
            rows[str(r["task_id"])] = r          # a re-run of a task replaces its earlier line
    return rows


def passed(kind, r):
    return bool(r.get("ok")) if kind == "miniweb" else float(r.get("score") or 0) >= 1.0


def reason(kind, r):
    if r.get("error"):
        return r["error"]
    if kind == "miniweb":
        return r.get("detail") or ""
    parts = r.get("parts")
    return (f"evaluators {parts}; " if parts else "") + f"answer: {r.get('answer') or ''}"


def _fmt_action(acts):
    out = []
    for a in acts or []:
        for name, p in a.items():
            p = {k: v for k, v in (p or {}).items() if v not in (None, [], "")}
            if name == "done":
                p.pop("files_to_display", None)
            out.append(f"{name} {json.dumps(p, ensure_ascii=False)[:220]}")
    return "; ".join(out)


def _prompt_file(task_dir, i, text):
    """A step's full prompt as its own small page (opened on demand; keeps the run pages light)."""
    f = task_dir / "prompts" / f"step_{i}.txt"
    if not f.exists():
        f.parent.mkdir(exist_ok=True)
        f.write_text(text)
    return f


def _element(els):
    """The element an action hit (browser-use's interacted_element), as 'tag "text" #id'."""
    for e in els or []:
        if not e:
            continue
        attrs = e.get("attributes") or {}
        name = attrs.get("aria-label") or attrs.get("name") or attrs.get("placeholder") or attrs.get("title") or ""
        tag = (e.get("node_name") or e.get("tag_name") or "").lower()
        where = "" if name or attrs.get("id") else "/".join((e.get("x_path") or "").split("/")[-3:])
        return " ".join(x for x in (f"<{tag}>" if tag else "", f'"{name[:50]}"' if name else "",
                                    f"#{attrs['id']}" if attrs.get("id") else "", where) if x)
    return ""


def task_section(kind, run_key, tid, r, task_dir, ins, rel):
    shots = copy_screenshots(task_dir)
    hist = json.loads((task_dir / "history.json").read_text()).get("history", []) if (task_dir / "history.json").exists() else []
    trace = json.loads((task_dir / "trace.json").read_text()) if (task_dir / "trace.json").exists() else []
    cells = []
    for i, st in enumerate(hist):
        mo = st.get("model_output") or {}
        res = st.get("result") or []
        err = "; ".join(str(x.get("error")) for x in res if x.get("error"))
        out = "; ".join(str(x.get("extracted_content")) for x in res if x.get("extracted_content"))
        ltm = "; ".join(str(x.get("long_term_memory")) for x in res if x.get("long_term_memory"))
        model = trace[i]["model"] if i < len(trace) else ""
        img = (f"<a href='{rel(shots[i])}'><img loading='lazy' src='{rel(shots[i])}'></a>" if i in shots
               else "<div class='meta'>(no screenshot)</div>")
        state = st.get("state") or {}
        url = state.get("url") or ""
        # non-flash runs also carry thinking / evaluation / next goal; flash mode reasons inside `memory`
        extra = "".join(f"<div class='mem'><b>{lbl}:</b> {html.escape(str(mo[k]))}</div>"
                        for k, lbl in (("thinking", "thinking"), ("evaluation_previous_goal", "evaluation"),
                                       ("next_goal", "next goal")) if mo.get(k))
        sm = st.get("state_message") or ""
        m = re.search(r"<agent_history>(.*?)</agent_history>", sm, re.S)
        agent_hist = (m.group(1).strip() if m else "")
        el = _element(state.get("interacted_element"))
        cells.append(f"<figure>{img}<figcaption><div class='meta'>step {i + 1}{' · ' + html.escape(model) if model else ''}"
                     f" · {html.escape(url[-60:])}</div>{extra}"
                     f"<div class='mem'><b>memory:</b> {html.escape(mo.get('memory') or '')}</div>"
                     f"<div class='act'>{html.escape(_fmt_action(mo.get('action')))}</div>"
                     + (f"<div class='meta'>on {html.escape(el)}</div>" if el else "")
                     + (f"<div class='err'>{html.escape(err[:300])}</div>" if err else
                        f"<div class='meta'>result: {html.escape(out[:200])}</div>")
                     + (f"<div class='meta'>kept in history: {html.escape(ltm[:200])}</div>" if ltm and ltm != out else "")
                     + (f"<details><summary>history browser-use gave the model</summary><pre>{html.escape(agent_hist)}</pre></details>"
                        if agent_hist else "")
                     + (f"<a class='meta' target='_blank' href='{rel(_prompt_file(task_dir, i, sm))}'>full prompt text "
                        f"({len(sm):,} chars)</a>" if sm else "") + "</figcaption></figure>")
    ok = passed(kind, r)
    head = (f"<p class='ins'>{html.escape(ins.get((kind, tid), ''))}</p>"
            f"<p class='meta'><span class='{'ok' if ok else 'fail'}'>{'PASS' if ok else 'FAIL'}</span> · task {html.escape(tid)}"
            f" · {html.escape(str(r.get('macro') or '+'.join(r.get('sites') or [])))} · {r.get('steps')} steps · "
            f"{r.get('duration_s')}s<br>{html.escape(reason(kind, r)[:500])}</p>")
    return f"<section id='t{html.escape(tid)}'>{head}<div class='strip'>{''.join(cells)}</div></section>", ok


def write_run(key, kind, d, ins):
    """The run's table page (viewer/<key>.html) + one page per task (viewer/<key>/<task>.html)."""
    rows = load_results(d)
    (OUT / key).mkdir(exist_ok=True)
    rel = lambda p: "../../" + p.relative_to(WM).as_posix()       # noqa: E731  (from viewer/<key>/)
    table = []
    for tid in sorted(rows, key=lambda t: (passed(kind, rows[t]), t)):
        r = rows[tid]
        sec, ok = task_section(kind, key, tid, r, d / tid, ins, rel)
        (OUT / key / f"{tid}.html").write_text(
            f"<!doctype html><meta charset='utf-8'><title>{html.escape(key)} · {html.escape(tid)}</title><style>{STYLE}</style>"
            f"<p><a href='../{key}.html'>&larr; {html.escape(key)}</a> · <a href='../index.html'>all runs</a></p>{sec}")
        table.append(f"<tr><td><a href='{key}/{html.escape(tid)}.html'>{html.escape(tid)}</a></td><td class='{'ok' if ok else 'fail'}'>"
                     f"{'PASS' if ok else 'FAIL'}</td><td>{html.escape(str(r.get('macro') or '+'.join(r.get('sites') or [])))}</td>"
                     f"<td>{r.get('steps')}</td><td>{html.escape(ins.get((kind, tid), '')[:110])}</td>"
                     f"<td class='meta'>{html.escape(reason(kind, r)[:140])}</td></tr>")
    n_ok = sum(passed(kind, r) for r in rows.values())
    page = (f"<!doctype html><meta charset='utf-8'><title>{html.escape(key)}</title><style>{STYLE}</style>"
            f"<p><a href='index.html'>&larr; all runs</a></p><h1>{html.escape(key)}: {n_ok}/{len(rows)} passed</h1>"
            f"<p class='meta'>Failures first. Click a task for its steps: screenshot, the model's memory (its reasoning in "
            f"flash mode), action, element, result, the history browser-use fed back, and the full prompt.</p>"
            f"<table><tr><th>task</th><th>result</th><th>macro / site</th><th>steps</th><th>instruction</th><th>grader</th></tr>"
            f"{''.join(table)}</table>")
    (OUT / f"{key}.html").write_text(page)
    return len(rows), n_ok


def write_compare(a, b, ins):
    (ka, kind, da), (kb, _, db) = a, b
    ra, rb = load_results(da), load_results(db)
    common = sorted(set(ra) & set(rb), key=lambda t: (passed(kind, ra[t]) == passed(kind, rb[t]), t))
    rows = []
    for t in common:
        pa, pb = passed(kind, ra[t]), passed(kind, rb[t])
        rows.append(f"<tr><td>{html.escape(t)}</td><td>{html.escape(str(ra[t].get('macro') or '+'.join(ra[t].get('sites') or [])))}"
                    f"</td><td class='{'ok' if pa else 'fail'}'><a href='{ka}/{t}.html'>{'PASS' if pa else 'FAIL'}</a> "
                    f"({ra[t].get('steps')} st)</td><td class='{'ok' if pb else 'fail'}'><a href='{kb}/{t}.html'>"
                    f"{'PASS' if pb else 'FAIL'}</a> ({rb[t].get('steps')} st)</td><td>{html.escape(ins.get((kind, t), '')[:110])}</td></tr>")
    both = sum(passed(kind, ra[t]) and passed(kind, rb[t]) for t in common)
    only_a = sum(passed(kind, ra[t]) and not passed(kind, rb[t]) for t in common)
    only_b = sum(passed(kind, rb[t]) and not passed(kind, ra[t]) for t in common)
    name = f"compare_{ka}__{kb}.html"
    (OUT / name).write_text(
        f"<!doctype html><meta charset='utf-8'><title>{ka} vs {kb}</title><style>{STYLE}</style>"
        f"<p><a href='index.html'>&larr; all runs</a></p><h1>{html.escape(ka)} vs {html.escape(kb)}</h1>"
        f"<p>{len(common)} common tasks · both pass {both} · only {html.escape(ka)} {only_a} · only {html.escape(kb)} {only_b}"
        f" (differing tasks listed first)</p><table><tr><th>task</th><th>macro / site</th><th>{html.escape(ka)}</th>"
        f"<th>{html.escape(kb)}</th><th>instruction</th></tr>{''.join(rows)}</table>")
    return name, len(common), both, only_a, only_b


def write_viewer():
    OUT.mkdir(parents=True, exist_ok=True)
    ins = instructions()
    rs = runs()
    items = []
    for key, kind, d in rs:
        n, ok = write_run(key, kind, d, ins)
        items.append(f"<tr><td><a href='{key}.html'>{html.escape(key)}</a></td><td>{kind}</td><td>{ok}/{n}</td></tr>")
    comps = []
    for kind in ("miniweb", "wa"):
        # the reference is the newest base run (fixed harness), else the first one
        base = next((r for name in ("val_base_v2", "base_v2", "val_base", "base_zeroshot")
                     for r in rs if r[1] == kind and r[2].name == name), None)
        for r in rs:
            if base and r[1] == kind and r is not base and "smoke" not in r[2].name:
                name, n, both, oa, ob = write_compare(base, r, ins)
                comps.append(f"<li><a href='{name}'>{html.escape(base[0])} vs {html.escape(r[0])}</a>: {n} common tasks, "
                             f"both pass {both}, only base {oa}, only {html.escape(r[0])} {ob}</li>")
    (OUT / "index.html").write_text(
        f"<!doctype html><meta charset='utf-8'><title>WebMix evaluation runs</title><style>{STYLE}</style>"
        f"<h1>WebMix evaluation runs</h1><table><tr><th>run</th><th>benchmark</th><th>passed</th></tr>{''.join(items)}</table>"
        f"<h2>Comparisons</h2><ul>{''.join(comps)}</ul>")
    return OUT / "index.html", len(rs)


if __name__ == "__main__":
    p, n = write_viewer()
    print(f"{n} runs -> {p}")
