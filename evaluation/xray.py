"""MiniWeb X-Ray — standalone eval-results inspector (agentlab-xray style).

Browses evaluation/results/<run>/<agent__task>/ directories and shows, per task:
  - instruction, expected vs agent answer, pass/fail, timing
  - the FILLED verifier (verify_report.json check tree: spec + pass/fail + reason)
  - the audit note (note.md, stored IN the result dir — moved out of data/ so
    Railway annotation pulls can never wipe it)
  - step-through screenshots + the actions taken at each step (history.json)
  - a human feedback box, saved to feedback.md in the result dir

Usage:  python evaluation/xray.py [--port 8125]
"""
import argparse
import glob
import html
import json
import os
import re
from pathlib import Path

from flask import Flask, abort, redirect, request, send_from_directory

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "evaluation" / "results"

app = Flask(__name__)

VERDICT_COLORS = {"VERIFIER_OK": "#16a34a", "VERIFIER_SUSPECT": "#d97706",
                  "TASK_BROKEN": "#dc2626", "RECORDING_GAP": "#2563eb"}


# ── helpers ──────────────────────────────────────────────────────────────────

def runs():
    return sorted((d.name for d in RESULTS.iterdir() if d.is_dir()),
                  key=lambda n: (RESULTS / n).stat().st_mtime, reverse=True)


def safe_dir(run, name):
    """Resolve a task dir inside a run, refusing path escapes."""
    d = (RESULTS / run / name).resolve()
    if not str(d).startswith(str((RESULTS / run).resolve())) or not d.is_dir():
        abort(404)
    return d


def read_json(p):
    try:
        return json.loads(Path(p).read_text())
    except (OSError, json.JSONDecodeError):
        return None


def note_verdict(note):
    m = re.search(r"\*\*Verdict:\*\*\s*([A-Z_]+)", note or "")
    return m.group(1) if m else None


def md_lite(text):
    """Tiny markdown renderer: headings, bold, code. Escapes everything else."""
    out = html.escape(text or "")
    out = re.sub(r"^# (.*)$", r'<span class="h">\1</span>', out, flags=re.M)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", out)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    return out


def badge(text, color):
    return (f'<span style="background:{color}1a;color:{color};border:1px solid {color}55;'
            f'padding:.05rem .45rem;border-radius:.3rem;font-size:.72rem;font-weight:600">{text}</span>')


def _cval(v):
    """Human form of one constraint value: open -> any; dict -> value + mode."""
    if isinstance(v, dict):
        if v.get("open"):
            return '<i style="color:#94a3b8">any</i>'
        val = html.escape(json.dumps(v.get("value"))) if "value" in v else html.escape(json.dumps(v))
        mode = v.get("mode")
        return f'<code>{val}</code>' + (f' <span class="adv" style="background:#e0e7ff;color:#4338ca">{html.escape(str(mode))}</span>' if mode else "")
    return f'<code>{html.escape(json.dumps(v))}</code>'


def render_constraints(ctype, spec):
    """Readable constraint table for a check's spec (what the gate REQUIRES)."""
    rows = []
    if ctype == "request_made":
        m, u = spec.get("method"), spec.get("url")
        if m or u:
            rows.append(f'<tr><td>request</td><td><code>{html.escape(str(m or "ANY"))} {html.escape(str(u or "(any url)"))}</code></td></tr>')
        if spec.get("status") not in (None, "", {}):
            rows.append(f'<tr><td>status</td><td>{_cval(spec["status"])}</td></tr>')
        bf = spec.get("body_fields")
        if isinstance(bf, dict) and bf:
            for k, v in bf.items():
                rows.append(f'<tr><td>body.{html.escape(k)}</td><td>{_cval(v)}</td></tr>')
    elif ctype == "page_visited":
        rows.append(f'<tr><td>visit url</td><td>{_cval(spec.get("url", {"open": True}))}</td></tr>')
    elif ctype == "action_included":
        rows.append(f'<tr><td>action</td><td><code>{html.escape(str(spec.get("action") or "any"))}</code></td></tr>')
        for k in ("target", "value"):
            if k in spec:
                rows.append(f'<tr><td>{k}</td><td>{_cval(spec[k])}</td></tr>')
    elif ctype in ("qa_answer", "answer_matches", "reasoning_contains"):
        if spec.get("expected"):
            rows.append(f'<tr><td>expected</td><td><code>{html.escape(str(spec["expected"]))}</code></td></tr>')
    if not rows:
        return ""
    return ('<table class="constraints"><tr><th colspan="2">gate constraints</th></tr>'
            + "".join(rows) + "</table>")


def render_check(node):
    """Recursive HTML for a verify_report check tree node."""
    if not isinstance(node, dict):
        return ""
    if node.get("op"):  # AND/OR group
        inner = "".join(render_check(c) for c in node.get("checks") or [])
        ok = node.get("passed")
        mark = "✓" if ok else "✗"
        col = "#16a34a" if ok else "#dc2626"
        adv = ' <span class="adv">advisory</span>' if node.get("advisory") else ""
        return (f'<div class="grp"><div class="grph" style="color:{col}">{mark} '
                f'{node["op"]}{adv}</div>{inner}</div>')
    ok = node.get("passed")
    mark = "✓" if ok else "✗"
    col = "#16a34a" if ok else "#dc2626"
    adv = ' <span class="adv">advisory</span>' if node.get("advisory") else ""
    label = html.escape(node.get("label") or node.get("type") or "check")
    reason = html.escape(node.get("reason") or "")
    spec = node.get("spec") or {}
    spec_pre = html.escape(json.dumps(spec, indent=1))
    return (f'<div class="chk"><span style="color:{col};font-weight:700">{mark}</span> '
            f'<b>{html.escape(node.get("type") or "")}</b> {label}{adv}'
            f'{render_constraints(node.get("type"), spec)}'
            f'<div class="reason">{reason}</div>'
            f'<details><summary>raw spec</summary><pre>{spec_pre}</pre></details></div>')


STYLE = """<style>
body{font-family:system-ui,sans-serif;margin:0;background:#f8fafc;color:#0f172a;font-size:14px}
a{color:#2563eb;text-decoration:none} a:hover{text-decoration:underline}
.top{background:#0f172a;color:#e2e8f0;padding:.5rem 1rem;display:flex;gap:1rem;align-items:center}
.top select{font-size:.85rem;padding:.15rem}
.wrap{display:flex;min-height:calc(100vh - 42px)}
.side{width:330px;border-right:1px solid #e2e8f0;background:#fff;overflow-y:auto;max-height:calc(100vh - 42px);position:sticky;top:0}
.side .row{display:block;padding:.35rem .6rem;border-bottom:1px solid #f1f5f9;font-size:.78rem;color:#0f172a}
.side .row:hover{background:#f1f5f9} .side .row.active{background:#eef2ff}
.main{flex:1;padding:1rem 1.4rem;max-width:1100px}
.card{background:#fff;border:1px solid #e2e8f0;border-radius:.5rem;padding:.8rem 1rem;margin-bottom:1rem}
.card h3{margin:.1rem 0 .6rem;font-size:.95rem}
.grp{border-left:3px solid #e2e8f0;margin:.3rem 0 .3rem .4rem;padding-left:.6rem}
.grph{font-weight:700;font-size:.78rem}
.chk{margin:.35rem 0;font-size:.8rem}
.chk .reason{color:#64748b;margin-left:1.15rem;font-size:.75rem}
.chk details{margin-left:1.15rem} .chk summary{cursor:pointer;font-size:.7rem;color:#94a3b8}
.chk pre{background:#f8fafc;border:1px solid #e2e8f0;padding:.4rem;font-size:.68rem;overflow-x:auto}
.adv{background:#fef9c3;color:#a16207;font-size:.65rem;padding:0 .3rem;border-radius:.2rem}
.constraints{border-collapse:collapse;margin:.25rem 0 .1rem 1.15rem;font-size:.72rem}
.constraints th{text-align:left;color:#94a3b8;font-weight:600;font-size:.65rem;text-transform:uppercase;padding:.1rem .5rem .1rem 0}
.constraints td{border-top:1px solid #f1f5f9;padding:.15rem .6rem .15rem 0;color:#475569}
.constraints td:first-child{color:#64748b;font-weight:600;white-space:nowrap}
.constraints code{background:#f1f5f9;padding:0 .3rem;border-radius:.2rem}
.note{white-space:pre-wrap;word-break:break-word;font-size:.8rem;line-height:1.55}
.note .h{font-weight:700;font-size:.9rem} .note code{background:#eef2ff;padding:0 .25rem;border-radius:.2rem}
.mono{font-family:ui-monospace,monospace;font-size:.78rem;background:#f8fafc;border:1px solid #e2e8f0;padding:.5rem;border-radius:.3rem;white-space:pre-wrap;word-break:break-word}
.shot{max-width:100%;border:1px solid #e2e8f0;border-radius:.4rem}
.steps{display:flex;gap:.4rem;flex-wrap:wrap;margin-bottom:.5rem}
.steps a{border:1px solid #cbd5e1;border-radius:.3rem;padding:.1rem .45rem;font-size:.75rem}
.steps a.cur{background:#0f172a;color:#fff;border-color:#0f172a}
textarea{width:100%;min-height:110px;font-family:inherit;font-size:.85rem;padding:.5rem;border:1px solid #cbd5e1;border-radius:.4rem;box-sizing:border-box}
button{background:#0f172a;color:#fff;border:0;border-radius:.35rem;padding:.4rem .9rem;font-size:.8rem;cursor:pointer}
.meta{display:flex;gap:1.2rem;flex-wrap:wrap;font-size:.78rem;color:#475569}
</style>"""


def page(body, title="MiniWeb X-Ray"):
    return f"<!doctype html><html><head><meta charset='utf-8'><title>{title}</title>{STYLE}</head><body>{body}</body></html>"


def sidebar(run, active=None, flt=""):
    items = []
    for d in sorted((RESULTS / run).iterdir()):
        if not d.is_dir():
            continue
        res = read_json(d / "result.json") or {}
        note = (d / "note.md").read_text() if (d / "note.md").exists() else ""
        verdict = note_verdict(note)
        fb = (d / "feedback.md").exists()
        passed = res.get("passed")
        pf = badge("PASS", "#16a34a") if passed else (badge("FAIL", "#dc2626") if passed is False else badge("—", "#94a3b8"))
        vb = badge(verdict.replace("VERIFIER_", ""), VERDICT_COLORS[verdict]) if verdict in VERDICT_COLORS else ""
        fbi = " 💬" if fb else ""
        tid = res.get("task_id") or d.name.split("__", 1)[-1]
        if flt and flt.lower() not in (tid + " " + (verdict or "") + (" fail" if passed is False else " pass")).lower():
            continue
        cls = "row active" if d.name == active else "row"
        items.append(f'<a class="{cls}" href="/task/{run}/{d.name}">{pf} {vb}{fbi} {html.escape(tid)}</a>')
    search = (f'<form method="get" action="/run/{run}" style="padding:.4rem .6rem">'
              f'<input name="f" value="{html.escape(flt)}" placeholder="filter: text / fail / SUSPECT" '
              f'style="width:100%;box-sizing:border-box;font-size:.78rem;padding:.25rem"></form>')
    return f'<div class="side">{search}{"".join(items)}</div>'


def topbar(run):
    opts = "".join(f'<option value="{r}" {"selected" if r == run else ""}>{r}</option>' for r in runs())
    return (f'<div class="top"><b>MiniWeb X-Ray</b>'
            f'<form method="get" action="/pickrun">run: <select name="run" onchange="this.form.submit()">{opts}</select></form>'
            f'<span style="font-size:.75rem;color:#94a3b8">verifier + note + feedback inspector</span></div>')


# ── routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    rs = runs()
    if not rs:
        return page("<div class='main'>no runs under evaluation/results/</div>")
    return redirect(f"/run/{rs[0]}")


@app.route("/pickrun")
def pickrun():
    return redirect(f"/run/{request.args.get('run', '')}")


@app.route("/run/<run>")
def run_view(run):
    if run not in runs():
        abort(404)
    flt = request.args.get("f", "")
    res = [read_json(p) for p in glob.glob(str(RESULTS / run / "*/result.json"))]
    res = [r for r in res if r]
    p = sum(1 for r in res if r.get("passed"))
    body = (topbar(run) + '<div class="wrap">' + sidebar(run, flt=flt) +
            f'<div class="main"><div class="card"><h3>{run}</h3>'
            f'<div class="meta"><span>{len(res)} tasks</span>'
            f'<span>pass {p} / fail {len(res) - p}</span>'
            f'<span>rate {100 * p / max(1, len(res)):.1f}%</span></div>'
            f'<p style="font-size:.8rem;color:#64748b">Pick a task on the left. '
            f'💬 = has human feedback. Badges: verdict from the audit note.</p></div></div></div>')
    return page(body)


@app.route("/task/<run>/<name>")
def task_view(run, name):
    d = safe_dir(run, name)
    res = read_json(d / "result.json") or {}
    rep = read_json(d / "verify_report.json") or {}
    note = (d / "note.md").read_text() if (d / "note.md").exists() else None
    feedback = (d / "feedback.md").read_text() if (d / "feedback.md").exists() else ""
    saved = request.args.get("saved")

    passed = res.get("passed")
    pf = badge("PASS", "#16a34a") if passed else (badge("FAIL", "#dc2626") if passed is False else badge("no result", "#94a3b8"))
    head = (f'<div class="card"><h3>{html.escape(res.get("task_id") or name)} {pf}</h3>'
            f'<div class="meta"><span>agent: {html.escape(str(res.get("model") or "?"))}</span>'
            f'<span>steps: {res.get("steps", "?")}</span>'
            f'<span>time: {round(res.get("elapsed_s", 0))}s</span>'
            f'<span>site: {html.escape(str(res.get("site") or ""))}</span></div>'
            f'<p style="margin:.5rem 0 0;font-size:.85rem"><b>Instruction:</b> {html.escape(res.get("instruction") or "")}</p>'
            f'<p style="margin:.3rem 0 0;font-size:.8rem"><b>Expected:</b> <code>{html.escape(str(res.get("expected_answer") or "(none)"))}</code></p>'
            f'<details style="margin-top:.3rem"><summary style="cursor:pointer;font-size:.78rem">agent answer</summary>'
            f'<div class="mono">{html.escape(res.get("agent_answer") or "(none)")}</div></details></div>')

    # filled verifier
    macros_html = ""
    for m, tree in (rep.get("macros") or {}).items():
        ok = (rep.get("by_macro") or {}).get(m)
        mb = badge("✓", "#16a34a") if ok else badge("✗", "#dc2626")
        macros_html += f'<div style="margin:.5rem 0"><b style="font-size:.85rem">{mb} {html.escape(m)}</b>{render_check(tree)}</div>'
    verifier_card = f'<div class="card"><h3>Filled verifier (verify_report.json)</h3>{macros_html or "<i>no report</i>"}</div>'

    # audit note
    note_card = ""
    if note:
        v = note_verdict(note)
        vb = badge(v, VERDICT_COLORS.get(v, "#64748b")) if v else ""
        note_card = f'<div class="card"><h3>Audit note {vb}</h3><div class="note">{md_lite(note)}</div></div>'

    # steps: screenshots + actions
    shots = sorted(glob.glob(str(d / "screenshots" / "step_*.png")),
                   key=lambda p: int(re.search(r"(\d+)", Path(p).name).group(1)))
    hist = read_json(d / "history.json") or {}
    steps = hist.get("history") or []
    cur = max(0, min(int(request.args.get("step", 1)) - 1, len(shots) - 1)) if shots else 0
    steps_card = ""
    if shots:
        # per-step data inlined so Prev/Next (and arrow keys) swap in place — no page reload
        step_data = []
        for i in range(len(shots)):
            s = steps[min(i + 1, len(steps) - 1)] if steps else {}
            mo = (s.get("model_output") or {})
            step_data.append({"img": f"/shot/{run}/{name}/{Path(shots[i]).name}",
                              "acts": json.dumps(mo.get("action") or [], indent=1)[:1500],
                              "think": (mo.get("thinking") or "")[:4000],
                              "eval": (mo.get("evaluation_previous_goal") or "")[:1000],
                              "memory": (mo.get("memory") or "")[:1500],
                              "goal": (mo.get("next_goal") or "")[:1000]})
        steps_card = (f'<div class="card" id="steps"><h3>Steps ({len(shots)} screenshots)</h3>'
                      f'<div style="display:flex;gap:.5rem;align-items:center;margin-bottom:.5rem">'
                      f'<button type="button" onclick="xstep(-1)">&larr; Prev</button>'
                      f'<span id="step-counter" style="font-size:.8rem;color:#475569;min-width:70px;text-align:center"></span>'
                      f'<button type="button" onclick="xstep(1)">Next &rarr;</button>'
                      f'<span style="font-size:.72rem;color:#94a3b8">(or ←/→ keys)</span></div>'
                      f'<img class="shot" id="step-img" src="">'
                      f'<div id="step-reason" style="margin-top:.5rem;font-size:.78rem;line-height:1.5"></div>'
                      f'<details open style="margin-top:.4rem"><summary style="cursor:pointer;font-size:.78rem">actions at this step</summary>'
                      f'<pre class="mono" id="step-acts"></pre></details>'
                      f'<details style="margin-top:.3rem"><summary style="cursor:pointer;font-size:.78rem">full thinking</summary>'
                      f'<div class="mono" id="step-think"></div></details>'
                      f'<script>'
                      f'var XSTEPS={json.dumps(step_data)};var XCUR={cur};'
                      f'function esc(t){{var d=document.createElement("div");d.textContent=t||"";return d.innerHTML;}}'
                      f'function xrender(){{var s=XSTEPS[XCUR];'
                      f'document.getElementById("step-img").src=s.img;'
                      f'document.getElementById("step-acts").textContent=s.acts;'
                      f'document.getElementById("step-think").textContent=s.think||"(none)";'
                      f'var evc=/success/i.test(s.eval)?"#16a34a":(/fail/i.test(s.eval)?"#dc2626":"#64748b");'
                      f'document.getElementById("step-reason").innerHTML='
                      f'(s.eval?"<div><b style=\'color:"+evc+"\'>eval:</b> "+esc(s.eval)+"</div>":"")+'
                      f'(s.goal?"<div><b style=\'color:#4338ca\'>next goal:</b> "+esc(s.goal)+"</div>":"")+'
                      f'(s.memory?"<div style=\'color:#64748b\'><b>memory:</b> "+esc(s.memory)+"</div>":"");'
                      f'document.getElementById("step-counter").textContent=(XCUR+1)+" / "+XSTEPS.length;}}'
                      f'function xstep(d){{XCUR=Math.min(Math.max(XCUR+d,0),XSTEPS.length-1);xrender();}}'
                      f'document.addEventListener("keydown",function(e){{'
                      f'if(e.target.tagName==="TEXTAREA"||e.target.tagName==="INPUT")return;'
                      f'if(e.key==="ArrowLeft")xstep(-1);else if(e.key==="ArrowRight")xstep(1);}});'
                      f'xrender();'
                      f'</script></div>')

    # human feedback
    saved_tag = '<span style="color:#16a34a;font-size:.78rem">saved ✓</span>' if saved else ""
    fb_card = (f'<div class="card"><h3>Human feedback</h3>'
               f'<form method="post" action="/feedback/{run}/{name}">'
               f'<textarea name="text" placeholder="your notes on this task/verifier/run...">{html.escape(feedback)}</textarea>'
               f'<div style="margin-top:.4rem;display:flex;gap:.6rem;align-items:center">'
               f'<button type="submit">Save feedback.md</button>{saved_tag}'
               f'</div></form></div>')

    body = (topbar(run) + '<div class="wrap">' + sidebar(run, active=name) +
            f'<div class="main">{head}{verifier_card}{note_card}{steps_card}{fb_card}</div></div>')
    return page(body, title=res.get("task_id") or name)


@app.route("/feedback/<run>/<name>", methods=["POST"])
def save_feedback(run, name):
    d = safe_dir(run, name)
    text = (request.form.get("text") or "").strip()
    f = d / "feedback.md"
    if text:
        f.write_text(text + "\n")
    elif f.exists():
        f.unlink()  # empty submit clears feedback
    return redirect(f"/task/{run}/{name}?saved=1")


@app.route("/shot/<run>/<name>/<path:fname>")
def shot(run, name, fname):
    d = safe_dir(run, name)
    return send_from_directory(d / "screenshots", fname)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8125)
    args = ap.parse_args()
    print(f"MiniWeb X-Ray → http://localhost:{args.port}")
    app.run(host="0.0.0.0", port=args.port, debug=False)
