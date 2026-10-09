"""Task-centric MiniWeb data (user, 2026-10-08: "maybe we should do task-centric MiniWeb data instead", plan A): InSTA's
recipe moved onto MiniWeb's training sites, so the skill- vs task-centric comparison holds sites, harness, actor,
verification evidence and size fixed and changes only the unit of data. InSTA proposes whole-task goals per website,
an agent attempts them end to end, and a judge keeps the successes; here

  1. propose   Gemini 3.5 Flash proposes goal-level tasks for each of the 52 training sites from its pages (paths,
               titles, controls, and the visible text of its main pages, so tasks name real items); every task starts
               on the site's home page, as InSTA's start at a website's front page;
  2. attempt   the base Qwen3.5-4B, as one agent with no hint, runs each task in the MiniWeb harness and every
               episode is recorded as rows (python -m miniwebagent.evaluate --tasks <tasks> --arm base --record-rows; the
               task kind "proposed" saves the session's request log, data changes, answer, screen text, final shot);
  3. judge     Gemini 3.5 Flash judges each episode from the screenshots AND the backend evidence (which requests were
               made with which parameters, which rows changed), far more than a live-web judge sees; `validate`
               measures it against the task verifiers on human tasks of the training sites first;
  4. rows      the judged successes, sites interleaved, selected in task order up to the step budget of the
               skill-centric executor (27,644 steps), as a miniwebagent.train rows dir.

    python -m miniwebgen.taskgen propose --out data/webmix/taskgen/tasks.jsonl [--per-site 140] [--sites a,b]
    python -m miniwebgen.taskgen judge <run dir> [--workers 16]            # -> <run dir>_judge/<task_id>.json
    python -m miniwebgen.taskgen validate <human train-split run dir>      # judge vs the verifiers
    python -m miniwebgen.taskgen rows <run dir> --out data/webmix/taskgen/rows_27k [--budget 27644]
"""
from __future__ import annotations

from helpers.paths import REPO_ROOT
import argparse
import hashlib
import html
import json
import random
import re
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = REPO_ROOT
OUT = ROOT / "data" / "webmix" / "taskgen"
MODEL = "gemini-3.5-flash"
BUDGET = 27644                       # the skill-centric executor's training steps (pooled_v4, 3.1K trajectories)


def train_sites():
    from miniwebgen import config
    return json.loads(config.SPLIT_PATH.read_text())["train"]


# ── 1. propose ────────────────────────────────────────────────────────────────

def _text(page_html, cap):
    """The visible text of a page (scripts, styles and tags dropped), whitespace collapsed, at most `cap` chars."""
    s = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", page_html)
    s = re.sub(r"(?s)<[^>]+>", "\n", s)
    lines = [re.sub(r"\s+", " ", html.unescape(x)).strip() for x in s.split("\n")]
    out, n = [], 0
    for x in lines:
        if x and (not out or out[-1] != x):
            out.append(x); n += len(x) + 1
            if n > cap:
                break
    return "\n".join(out)[:cap]


def site_context(site, client, n_pages=6, cap=1800):
    """What the proposer sees of a site: its name, every page (path, title), the controls per page (kind, label,
    a few option texts), and the visible text of its home page and the pages with the most controls."""
    from miniwebgen import config
    sm = json.loads((config.SITEMAP_DIR / f"{site}.json").read_text())
    pages = [p for p in sm["pages"] if p.get("path")]
    ctrls = sm["controls"] if isinstance(sm["controls"], list) else list(sm["controls"].values())
    by_page = {}
    for c in ctrls:
        if c.get("kind") in ("qa", "carry"):
            continue
        opts = [str(o.get("text") or o.get("value") or "")[:40] for o in (c.get("options") or [])[:4]]
        by_page.setdefault(c.get("page"), []).append(f"{c.get('kind')} '{str(c.get('label') or c.get('name') or '')[:40]}'"
                                                    + (f" [{', '.join(o for o in opts if o)}]" if any(opts) else ""))
    home = pages[0]["path"] if pages else f"/sites/{site}/"
    rich = sorted(by_page, key=lambda p: -len(by_page[p]))
    show = [home] + [p for p in rich if p and p != home][:n_pages - 1]
    texts = []
    for path in show:
        try:
            r = client.get(path, follow_redirects=True)
            texts.append(f"--- {path}\n{_text(r.get_data(as_text=True), cap)}")
        except Exception as e:                       # noqa: BLE001
            texts.append(f"--- {path}\n(could not render: {type(e).__name__})")
    page_lines = [f"{p['path']}  {p.get('title') or ''}" for p in pages[:90]]
    ctrl_lines = [f"{p}: " + "; ".join(v[:8]) for p, v in list(by_page.items())[:40] if p]
    return {"site": site, "name": sm.get("name") or site, "home": home, "paths": [p["path"] for p in pages],
            "text": "PAGES\n" + "\n".join(page_lines) + "\n\nCONTROLS BY PAGE\n" + "\n".join(ctrl_lines)
                    + "\n\nPAGE TEXT\n" + "\n\n".join(texts)}


SYSTEM_PROPOSE = """You write tasks for training a web agent, the way InSTA proposes tasks for real websites: realistic goals \
that a real user of this website would have. You see one website: its pages, its controls, and the text of its main pages."""

PROMPT_PROPOSE = """WEBSITE: {name} (all pages under {home})

{context}

Write {n} new tasks for this website. Rules:
- Each task is ONE natural instruction stating the user's goal, the way a person would ask for it ("Find ...", \
"Book ...", "Change my ...", "What is ..."), never click-by-click steps.
- Every task starts on the home page ({home}), as a visitor arriving at the site would, and is doable on this \
website alone in about 3 to 10 browser actions from there. Use real names, values and items that appear above; never \
invent items that are not on the site.
- Mix: about {n_info} information tasks (the answer is a specific fact the site shows; say what to report, e.g. \
"report the price") and {n_act} tasks that do something (search, filter, sort, create, edit, delete, book, buy, send, \
share, save, configure, ...), some of them combining two or three of these.
- {focus}
- The user is already logged in. No passwords, no other websites, no files the user would have to provide.
- Do not repeat these earlier tasks: {avoid}

Return JSON: {{"tasks": [{{"instruction": "...", "kind": "info" | "action"}}]}}"""


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def propose_site(ctx, per_site, batch, seed, model=MODEL):
    from helpers.llm import LLMClient
    llm = LLMClient(model=model, temperature=1.0)
    rng = random.Random(f"{seed}:{ctx['site']}")
    out, seen = [], set()
    focus_pages = [p for p in ctx["paths"] if p != ctx["home"]] or [ctx["home"]]
    for b in range((per_site + batch - 1) // batch + 2):            # +2: room for duplicates and invalid rows
        if len(out) >= per_site:
            break
        pick = rng.sample(focus_pages, min(4, len(focus_pages)))
        focus = ("Most of these tasks should involve these parts of the site: " + ", ".join(pick)) if b % 3 else \
            "Most of these tasks should involve the site's main sections."
        avoid = "; ".join(t["instruction"][:90] for t in out[-40:]) or "(none yet)"
        n = min(batch, per_site - len(out) + 4)
        prompt = PROMPT_PROPOSE.format(name=ctx["name"], home=ctx["home"], context=ctx["text"], n=n,
                                       n_info=round(n * 0.4), n_act=n - round(n * 0.4), focus=focus, avoid=avoid)
        try:
            raw = llm.complete(prompt, system=SYSTEM_PROPOSE, json_mode=True, max_tokens=8192)
            got = json.loads(raw or "{}")
            tasks = (got.get("tasks") if isinstance(got, dict) else got) or []   # a bare list happens too
        except Exception as e:                       # noqa: BLE001
            print(f"  {ctx['site']} batch {b}: {type(e).__name__} {str(e)[:120]}", flush=True)
            continue
        for t in tasks:
            ins = str(t.get("instruction") or "").strip()
            if len(ins) < 15 or _norm(ins) in seen:
                continue
            start = ctx["home"]                      # InSTA's rule: every task starts at the site's front page
            seen.add(_norm(ins))
            tid = f"tg-{ctx['site']}-{hashlib.md5(ins.encode()).hexdigest()[:8]}"
            out.append({"kind": "proposed", "task_id": tid, "site": ctx["site"], "sites": [ctx["site"]],
                        "macro": "proposed", "macros": [], "instruction": ins, "start_path": start,
                        "task_kind": t.get("kind") if t.get("kind") in ("info", "action") else "action",
                        "verifier": None})
    return out[:per_site]


def cmd_propose(a):
    from miniweb.app import create_app
    sites = a.sites.split(",") if a.sites else train_sites()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.exists():                                 # resumable: sites already in the file are kept
        done = {json.loads(l)["site"] for l in out.read_text().split("\n") if l.strip()}
    client = create_app().test_client()
    ctxs = [site_context(s, client) for s in sites if s not in done]
    print(f"proposing for {len(ctxs)} sites ({len(done)} already done), {a.per_site} each", flush=True)
    with ThreadPoolExecutor(a.workers) as ex:
        for ctx, tasks in zip(ctxs, ex.map(lambda c: propose_site(c, a.per_site, a.batch, a.seed), ctxs)):
            with open(out, "a") as f:
                f.write("".join(json.dumps(t, ensure_ascii=False) + "\n" for t in tasks))
            print(f"  {ctx['site']}: {len(tasks)} tasks ({sum(t['task_kind'] == 'info' for t in tasks)} info)", flush=True)


# ── 3. judge ──────────────────────────────────────────────────────────────────

SKIP_PATH = re.compile(r"^/(_admin|static|favicon)|\.(css|js|png|jpg|svg|ico|woff2?)$")

SYSTEM_JUDGE = """You judge whether a web agent completed a task on a website. You get the task, the agent's actions and \
final answer, the server's record of what the agent's session did, and screenshots of the episode (the last one is the \
final state). The server record is authoritative: a search, filter or sort happened only if a request carries it; an item \
was created, edited, deleted, booked, sent or saved only if the data changes show it, with the values the task asks for. \
For a question, the final answer must state the requested fact correctly and completely, as the site shows it. Judge \
the outcome the task asks for, not the route: searching instead of browsing a category is fine when the result is the \
same. A task is successful only if EVERY part of it was done; a partial, wrong or unverifiable result is NOT SUCCESS."""

PROMPT_JUDGE = """TASK: {task}

AGENT'S ACTIONS ({n_act}):
{actions}

AGENT'S FINAL ANSWER: {answer}

SERVER REQUESTS OF THE SESSION (method path, parameters):
{log}

DATA CHANGES OF THE SESSION:
{changes}

TEXT ON SCREEN AT THE END:
{seen}

Screenshots of the episode follow, in order. Split the task into its parts and check each against the evidence. \
Return JSON: {{"parts": [{{"part": "...", "done": true | false, "evidence": "..."}}], "verdict": "SUCCESS" | \
"NOT SUCCESS"}}"""


def _fmt_log(log, cap=60):
    lines = []
    for e in log or []:
        p = str(e.get("path") or "")
        if SKIP_PATH.search(p):
            continue
        q = {k: v for k, v in (e.get("query") or {}).items() if v not in ("", None)}
        b = {k: v for k, v in (e.get("body") or {}).items() if v not in ("", None) and k not in ("csrf_token",)} \
            if isinstance(e.get("body"), dict) else e.get("body")
        lines.append(f"{e.get('method')} {p}" + (f" ?{json.dumps(q, ensure_ascii=False)[:200]}" if q else "")
                     + (f" body {json.dumps(b, ensure_ascii=False)[:300]}" if b else "") + f" -> {e.get('status')}")
    return "\n".join(lines[-cap:]) or "(none)"


def _fmt_changes(changes, cap=30):
    lines = []
    for c in changes or []:
        what = c.get("collection") or c.get("table") or c.get("kind") or "?"
        op = c.get("op") or ("create" if not c.get("before") else "delete" if not c.get("after") else "update")
        ch = c.get("changed") or {}
        item = c.get("after") or c.get("before") or {}
        name = item.get("title") or item.get("name") or item.get("subject") or item.get("id")
        lines.append(f"{op} {what} ({name}): " + json.dumps({k: v for k, v in ch.items()}, ensure_ascii=False, default=str)[:400])
    return "\n".join(lines[:cap]) or "(none)"


def _fmt_actions(acts, cap=40):
    out = []
    for a in acts or []:
        if not isinstance(a, dict) or not a:
            continue
        k = next(iter(a)); v = a[k] or {}
        if k in ("done", "macro_done"):
            continue
        v = {kk: vv for kk, vv in (v.items() if isinstance(v, dict) else []) if vv not in (None, "", False)}
        out.append(f"{k} {json.dumps(v, ensure_ascii=False)[:160]}")
    return out[-cap:]


def _shots(ep, k=10):
    shots = sorted((ep / "screenshots").glob("step_*.png"), key=lambda p: int(p.stem.split("_")[1])) \
        if (ep / "screenshots").exists() else []
    if (ep / "final.png").exists():
        shots.append(ep / "final.png")
    if len(shots) <= k:
        return shots
    head = max(1, k // 4)                            # the start, then the end of the episode
    return shots[:head] + shots[-(k - head):]


def _last_seen(seen):
    """The text of the last page the agent saw; a JSON page (an API response) is kept as JSON text."""
    last = (seen or [""])[-1] or ""
    return last if isinstance(last, str) else json.dumps(last, ensure_ascii=False, default=str)


def judge_episode(ep, instruction, out_dir, model=MODEL):
    dst = out_dir / f"{ep.name}.json"
    if dst.exists():
        return json.loads(dst.read_text())
    gi = ep / "grade_inputs.json"
    if not gi.exists():
        return None
    g = json.loads(gi.read_text())
    acts = _fmt_actions(g.get("actions"))
    prompt = PROMPT_JUDGE.format(task=instruction, n_act=len(acts), actions="\n".join(acts) or "(none)",
                                 answer=(g.get("answer") or "(none)")[:1500], log=_fmt_log(g.get("log")),
                                 changes=_fmt_changes(g.get("changes")),
                                 seen=_last_seen(g.get("seen"))[:2500])
    from helpers.llm import LLMClient
    resp = None
    for _ in range(3):
        try:
            resp = LLMClient(model=model, temperature=0.0).complete(prompt, system=SYSTEM_JUDGE, max_tokens=8192,
                                                                   json_mode=True, images=[str(p) for p in _shots(ep)])
            v = str(json.loads(resp or "{}").get("verdict") or "").strip().upper()
            if v in ("SUCCESS", "NOT SUCCESS"):
                break
        except Exception as e:                       # noqa: BLE001
            resp, v = f"(judge error {type(e).__name__}: {str(e)[:200]})", ""
    ok = v in ("SUCCESS", "NOT SUCCESS")
    rec = {"task_id": ep.name, "predicted_label": int(v == "SUCCESS"), "verdict": ok, "response": resp, "model": model}
    if ok:                                           # no verdict (an error): judged again on the next pass
        dst.write_text(json.dumps(rec, indent=1, ensure_ascii=False))
    return rec


def _instructions(run):
    """task_id -> instruction for a run's episodes (proposed tasks: the run's own tasks file; human tasks: annotations)."""
    out = {}
    for f in (run / "tasks.jsonl", OUT / "tasks.jsonl"):
        if f.exists():
            out.update({t["task_id"]: t["instruction"] for t in map(json.loads, filter(str.strip, f.read_text().split("\n")))})
    if not out or not all((run / tid).exists() for tid in list(out)[:1]):
        from miniwebagent.evaluate import human_tasks
        out.update({t["task_id"]: t["instruction"] for t in human_tasks(split="all")})
    return out


def cmd_judge(a):
    run = Path(a.run)
    out = Path(str(run.rstrip("/") if isinstance(run, str) else run) + "_judge")
    out.mkdir(exist_ok=True)
    ins = _instructions(run)
    eps = [p for p in sorted(run.iterdir()) if p.is_dir() and p.name in ins]
    print(f"judging {len(eps)} episodes of {run} with {a.model} -> {out}", flush=True)
    errors = []

    def one(p):          # one episode's failure is reported, not the end of the run
        try:
            return judge_episode(p, ins[p.name], out, a.model)
        except Exception as e:  # noqa: BLE001
            errors.append(p.name)
            print(f"judge error on {p.name}: {type(e).__name__}: {e}", flush=True)
            return None
    with ThreadPoolExecutor(a.workers) as ex:
        recs = list(ex.map(one, eps))
    recs = [r for r in recs if r]
    k = sum(r["predicted_label"] for r in recs)
    print(json.dumps({"episodes": len(recs), "success": k, "rate": round(k / max(1, len(recs)), 4),
                      "no_verdict": sum(not r["verdict"] for r in recs), "errors": len(errors), "judge": a.model}),
          flush=True)
    if errors:
        sys.exit(f"{len(errors)} episodes not judged; rerun to retry them (judged ones are kept)")


def cmd_validate(a):
    """The judge against the task verifiers on a human-task run (base model, train-split sites): agreement, and the
    precision that matters for training data, P(verifier passes | judge passes)."""
    run = Path(a.run)
    a.workers = a.workers or 16
    cmd_judge(a)
    out = Path(str(run) + "_judge")
    res = {}
    for name in ("results_regraded.jsonl", "results.jsonl"):
        if (run / name).exists():
            res = {json.loads(l)["task_id"]: bool(json.loads(l)["ok"]) for l in (run / name).read_text().split("\n") if l.strip()}
            break
    pairs = [(res[t], json.loads((out / f"{t}.json").read_text())["predicted_label"] == 1) for t in res if (out / f"{t}.json").exists()]
    tp = sum(v and j for v, j in pairs); fp = sum(j and not v for v, j in pairs)
    fn = sum(v and not j for v, j in pairs); tn = sum(not v and not j for v, j in pairs)
    n = len(pairs)
    print(json.dumps({"episodes": n, "agreement": round((tp + tn) / max(1, n), 3), "verifier_pass": tp + fn,
                      "judge_pass": tp + fp, "precision": round(tp / max(1, tp + fp), 3),
                      "recall": round(tp / max(1, tp + fn), 3), "tp": tp, "fp": fp, "fn": fn, "tn": tn}), flush=True)


# ── 4. rows ───────────────────────────────────────────────────────────────────

def cmd_rows(a):
    """The judged successes in task order with sites interleaved (round robin over sites, each site's tasks in file
    order), whole episodes, until --budget steps; copied as <out>/<task_id>/{rows.jsonl, step_*.png, episode.json}."""
    run, out = Path(a.run), Path(a.out)
    judged = Path(str(run) + "_judge")
    tasks = [json.loads(l) for l in Path(a.tasks).read_text().split("\n") if l.strip()]
    by_site = {}
    for t in tasks:
        by_site.setdefault(t["site"], []).append(t)
    order, queues = [], [list(v) for _, v in sorted(by_site.items())]
    while any(queues):
        for q in queues:
            if q:
                order.append(q.pop(0))
    out.mkdir(parents=True, exist_ok=True)
    picked, steps, cand = [], 0, 0
    for t in order:
        j = judged / f"{t['task_id']}.json"
        src = run / t["task_id"] / "rows"
        if not (j.exists() and json.loads(j.read_text())["predicted_label"] == 1 and (src / "rows.jsonl").exists()):
            continue
        n = sum(1 for l in (src / "rows.jsonl").read_text().split("\n") if l.strip())
        cand += 1
        if n == 0:
            continue
        if steps >= a.budget:
            continue
        shutil.copytree(src, out / t["task_id"], dirs_exist_ok=True)
        picked.append(t["task_id"]); steps += n
    rep = {"run": str(run), "candidates": cand, "selected_trajectories": len(picked), "selected_rows": steps,
           "budget": a.budget, "short_by": max(0, a.budget - steps),
           "sites": len({t.split("-", 1)[1].rsplit("-", 1)[0] for t in picked})}
    (out / "_report.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep), flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m miniwebgen.taskgen")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("propose"); p.add_argument("--out", default=str(OUT / "tasks.jsonl"))
    p.add_argument("--per-site", type=int, default=140); p.add_argument("--batch", type=int, default=20)
    p.add_argument("--sites", default=None); p.add_argument("--workers", type=int, default=8)
    p.add_argument("--seed", type=int, default=20261008)
    for name in ("judge", "validate"):
        p = sub.add_parser(name); p.add_argument("run"); p.add_argument("--model", default=MODEL)
        p.add_argument("--workers", type=int, default=16)
    p = sub.add_parser("rows"); p.add_argument("run"); p.add_argument("--out", required=True)
    p.add_argument("--tasks", default=str(OUT / "tasks.jsonl")); p.add_argument("--budget", type=int, default=BUDGET)
    a = ap.parse_args(argv)
    {"propose": cmd_propose, "judge": cmd_judge, "validate": cmd_validate, "rows": cmd_rows}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
