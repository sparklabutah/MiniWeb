#!/usr/bin/env python3
"""Run a browser-use agent against an annotated task and grade it with the
task's macro verifier (verifier.json + evaluation/verifiers.py::verify_task).

This grades the agent's *trajectory* against the per-task macro verifier — the
same spec the annotate UI builds and the gold self-check uses (as opposed to an
LLM-as-judge on expected_outcome).

Pipeline:
  1. locate the task dir + its verifier.json under data/annotations/*/<task_id>/
  2. start the MiniWeb server (fresh -> logs start empty)
  3. run the browser-use agent from the task's starting_url
  4. pull the recorder stream (/_admin/record) + request log (/_admin/log)
     -> assemble a trajectory in the human trajectory.json schema
  5. verify_task(verifier, synthesize_network_events(trajectory), agent_answer)
  6. print PASS/FAIL + per-macro + failed-check reasons; write result.json

Usage:
  python evaluation/run_agent_verify.py --task-id banking_357033 --model gemini-flash
  python evaluation/run_agent_verify.py --task-id banking_357033 --obs visual   # screenshots
  python evaluation/run_agent_verify.py --task-id banking_357033 --obs axtree    # text DOM (default)
  python evaluation/run_agent_verify.py --task-id Minh/qa-knowledge_471ddc --no-headless
  python evaluation/run_agent_verify.py --task-id crm_bf9346 --model mock         # pipeline smoke test

Observation mode (--obs):
  visual        -> use_vision=True: the agent sees page screenshots.
  axtree / html -> use_vision=False: the agent sees browser-use's serialized text
                   DOM only (browser-use has one text representation; both names map
                   to it). Fine-tune its verbosity via the Agent `include_attributes`.
"""
import argparse
import asyncio
import json
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evaluation"))

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from evaluation.trajectory import synthesize_network_events
from evaluation.verifiers import verify_task
from annotation.storage import ANNOTATIONS_DIR

BOLD, DIM, RESET = "\033[1m", "\033[2m", "\033[0m"
GREEN, RED, YELLOW, CYAN = "\033[32m", "\033[31m", "\033[33m", "\033[36m"


# ── task + verifier resolution ────────────────────────────────────────────────

def locate_task(task_id: str):
    """Accept 'banking_357033' or 'Minh/banking_357033'. Returns (task_dir, task, verifier)."""
    if "/" in task_id:
        cand = ANNOTATIONS_DIR / task_id
        matches = [cand] if (cand / "task.json").exists() else []
    else:
        matches = [p.parent for p in ANNOTATIONS_DIR.glob(f"*/{task_id}/task.json")]
    if not matches:
        raise ValueError(f"task '{task_id}' not found under {ANNOTATIONS_DIR}")
    if len(matches) > 1:
        raise ValueError(f"ambiguous task id '{task_id}' — matches "
                         f"{[str(m) for m in matches]}; qualify as <annotator>/<task_id>")
    tdir = matches[0]
    task = json.loads((tdir / "task.json").read_text())
    vf = tdir / "verifier.json"
    if not vf.exists():
        raise ValueError(f"no verifier.json in {tdir} — build one first")
    verifier = json.loads(vf.read_text())
    # a re-recorded task may carry a NEW expected answer; verifier.json froze the
    # old one at build time — sync answer-type leaves before grading
    try:
        from annotation.macro_templates import refresh_expected
        refresh_expected(verifier.get("macros") or {}, task)
    except Exception:
        pass
    return tdir, task, verifier


# ── trajectory assembly from the running server's logs ────────────────────────

def recorded_start_url(tdir):
    """The URL where the human recording actually began — the first observation's
    URL in trajectory.json. This is ground truth for 'where start-record was
    clicked'; the task's starting_url field is often empty or stale (esp. on
    multi-site tasks), so prefer this."""
    try:
        traj = json.loads((Path(tdir) / "trajectory.json").read_text())
    except Exception:
        return None
    for e in traj:
        if e.get("type") == "observation" and e.get("url"):
            return e["url"]
    for e in traj:
        if e.get("type") == "action" and e.get("url"):
            return e["url"]
    return None


def resolve_start_url(base, starting_url, site_id):
    """Map a task's starting_url onto the local server.

    starting_url is often an ABSOLUTE production/localhost URL
    (e.g. https://miniweb-production.up.railway.app/sites/job-sites/) or empty /
    'about:blank'. Take just its /sites/... path (+query) and prepend our base;
    fall back to the site root.
    """
    from urllib.parse import urlparse
    su = (starting_url or "").strip()
    if su.startswith(("http://", "https://")):
        p = urlparse(su)
        path = p.path + (("?" + p.query) if p.query else "")
    elif su.startswith("/"):
        path = su
    else:
        path = ""
    if "/sites/" not in path:
        path = f"/sites/{site_id}/"
    return base + path


def fetch(base, path):
    try:
        with urllib.request.urlopen(base + path, timeout=20) as r:
            return json.loads(r.read())
    except Exception as exc:
        print(f"   {DIM}(could not fetch {path}: {exc}){RESET}")
        return {}


def build_trajectory(base):
    """Assemble a verify_task-ready trajectory from the server's admin logs.

    /_admin/record -> the recorder action+observation stream (human schema)
    /_admin/log    -> the server request log (network); mapped to type=network.
    """
    from urllib.parse import urlencode

    recorded = fetch(base, "/_admin/record?all=1").get("entries", []) or []
    log = fetch(base, "/_admin/log?all=1").get("entries", []) or []
    beacons = fetch(base, "/_admin/beacon?all=1").get("entries", []) or []

    # Keep the recorder's actions + observations, but take NETWORK authoritatively
    # from the server request log — the complete server-side view, which includes
    # native form POSTs and navigations the recorder's fetch/XHR wrapper misses.
    # (The old code only folded in the log when the recorder had zero network, and
    # mapped url=path — dropping the query string, so query-gated search/filter
    # checks false-negatived even though the request was in the log.)
    traj = [e for e in recorded if e.get("type") != "network"]
    if not any(e.get("type") == "action" for e in traj):
        for b in beacons:
            traj.append({"type": "action", **b})
    for e in log:
        url = e.get("path", "")
        query = e.get("query") or {}
        if query:
            url = url + "?" + urlencode(query)
        traj.append({
            "type": "network",
            "method": e.get("method"),
            "url": url,
            "status": e.get("status"),
            "requestBody": e.get("body"),
        })
    return synthesize_network_events(traj), recorded, log, beacons


# ── agent factory (shared build_agent — one factory for every runner) ─────────

def make_agent(model, *, headless, max_steps, timeout, use_vision, native_llm=False,
               harness="browser-use"):
    from agents import build_agent
    from generate_fixtures import ensure_fixtures
    return build_agent(model, native_llm=native_llm, harness=harness, use_vision=use_vision,
                       max_steps=max_steps, timeout=timeout, headless=headless,
                       available_file_paths=ensure_fixtures())


# ── run + grade (one agent on one task) ───────────────────────────────────────

async def run_and_grade(*, task_id, model, obs="axtree", grade="verifier",
                        judge_model="auto", native_llm=False, harness="browser-use",
                        max_steps=50, timeout=300, headless=True, start_from="recorded",
                        port=8099, out=None, verbose=True):
    """Run one agent on one task and grade it. Returns a result dict."""
    from server import start_server, stop_server, wait_for_server
    from helpers.llm import LLMClient

    tdir, task, verifier = locate_task(task_id)
    sites = [s["id"] if isinstance(s, dict) else s for s in task.get("sites", [])]
    site_id = sites[0]
    instruction = task.get("instruction", "")
    expected = task.get("expected_answer", "") or ""

    out = Path(out) if out else (
        ROOT / "evaluation" / "results" / f"agentverify_{tdir.name}_{model.replace('/','-')}_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    out.mkdir(parents=True, exist_ok=True)

    use_vision = obs == "visual"
    if verbose:
        print(f"{BOLD}task{RESET}       : {tdir.parent.name}/{tdir.name}  ({site_id})")
        print(f"{BOLD}instruction{RESET}: {instruction[:100]}")
        print(f"{BOLD}macros{RESET}     : {list(verifier.get('macros', {}).keys())}")
        print(f"{BOLD}model{RESET}      : {model}   {BOLD}obs{RESET}: "
              f"{'visual (screenshots)' if use_vision else 'text DOM ('+obs+')'}\n")

    # authenticate_by_form tasks must start LOGGED OUT — otherwise auto-login
    # (session user_id=1 on any /sites/* request) makes the agent already logged
    # in and the login step is a no-op. All other tasks keep auto-login on.
    needs_login = "authenticate_by_form" in (verifier.get("macros") or {})
    proc = start_server(port, env_extra={"MINIWEB_NO_AUTOLOGIN": "1"} if needs_login else None)
    if not wait_for_server(port, site_id=site_id, timeout=90):
        stop_server(proc)
        raise RuntimeError(f"server did not start on port {port}")
    base = f"http://localhost:{port}"
    task_sites = [s["id"] if isinstance(s, dict) else s for s in (task.get("sites") or [])]
    if len(task_sites) > 1:
        # Cross-site tasks start at the platform homepage: choosing which app to
        # open is part of the task, and the recorded start URL (one of the two
        # sites) would pre-solve that step.
        start_url = base + "/"
    else:
        rec_url = None if start_from == "starting_url" else recorded_start_url(tdir)
        start_url = resolve_start_url(base, rec_url or task.get("starting_url"), site_id)

    tok0 = LLMClient.GLOBAL.as_dict()
    agent = make_agent(model, headless=headless, max_steps=max_steps, timeout=timeout,
                       use_vision=use_vision, native_llm=native_llm, harness=harness)
    result = None
    t0 = datetime.now()
    try:
        await agent.setup(start_url)
        result = await agent.run(task=instruction, server_url=start_url, task_dir=out)
    except asyncio.TimeoutError:
        if verbose: print(f"{YELLOW}!! agent timed out{RESET}")
    except Exception as exc:
        if verbose: print(f"{RED}!! agent error: {exc}{RESET}")
    finally:
        traj, recorded, log, beacons = build_trajectory(base)
        try: await agent.teardown()
        except Exception: pass
        stop_server(proc)
    elapsed = (datetime.now() - t0).total_seconds()

    agent_answer = (getattr(result, "final_result", "") or "") if result else ""
    report = verify_task(verifier, traj, agent_answer, question=instruction)

    judge = None
    if grade in ("judge", "both"):
        from judge import judge_task
        judge = judge_task(
            instruction=instruction,
            trajectory=[e for e in recorded if e.get("type") == "action"],
            expected_answer=expected,
            rubric=task.get("expected_outcome") or "The agent completed the task correctly.",
            agent_answer=agent_answer, model=judge_model)

    g = LLMClient.GLOBAL.as_dict()
    tokens = {k: g[k] - tok0.get(k, 0) for k in g}

    res = {
        "task_id": tdir.name, "annotator": tdir.parent.name, "site": site_id,
        "instruction": instruction, "expected_answer": expected,
        "agent_answer": agent_answer, "model": model, "obs": obs, "grade": grade,
        "elapsed_s": round(elapsed, 1), "steps": getattr(result, "steps", -1),
        "is_done": getattr(result, "is_done", False),
        "passed": report["passed"], "by_macro": report["by_macro"],
        "judge": judge, "llm_tokens": tokens, "artifacts": str(out),
    }
    (out / "trajectory.json").write_text(json.dumps(traj, indent=1, default=str))
    (out / "server_log.json").write_text(json.dumps(log, indent=1))
    (out / "verify_report.json").write_text(json.dumps(report, indent=1, default=str))
    (out / "result.json").write_text(json.dumps(res, indent=2, default=str))

    if verbose:
        n_act = sum(1 for e in traj if e.get("type") == "action")
        n_net = sum(1 for e in traj if e.get("type") == "network")
        badge = f"{GREEN}{BOLD} PASS {RESET}" if report["passed"] else f"{RED}{BOLD} FAIL {RESET}"
        print("\n" + "=" * 64)
        print(f"result        : {badge}   {DIM}{elapsed:.0f}s  {n_act} actions  {n_net} requests{RESET}")
        print(f"agent answer  : {agent_answer[:80]!r}\nexpected      : {expected[:80]!r}")
        print(f"{BOLD}by macro{RESET}:")
        for macro, passed in report["by_macro"].items():
            mark = f"{GREEN}✓{RESET}" if passed else f"{RED}✗{RESET}"
            print(f"   {mark} {macro}")
            if not passed:
                for leaf in _failed_leaves(report["macros"].get(macro, {})):
                    print(f"       {DIM}- {leaf['type']}: {leaf.get('reason','')[:80]}{RESET}")
        if judge is not None:
            jb = f"{GREEN}PASS{RESET}" if judge.get("pass") else f"{RED}FAIL{RESET}"
            print(f"{BOLD}llm judge{RESET}    : {jb} ({judge.get('score')}) {DIM}{(judge.get('reasoning') or '')[:70]}{RESET}")
        print(f"{BOLD}llm tokens{RESET}   : {tokens['total']} ({tokens['prompt']}p+{tokens['completion']}c, {tokens['calls']} calls)")
        print(f"artifacts     : {out}\n" + "=" * 64)
    return res


async def main_async(args):
    res = await run_and_grade(
        task_id=args.task_id, model=args.model, obs=args.obs, grade=args.grade,
        judge_model=args.judge_model, native_llm=args.native_llm, harness=args.harness,
        max_steps=args.max_steps, timeout=args.timeout, headless=not args.no_headless,
        start_from=args.start_from, port=args.port, out=args.out, verbose=True)
    return 0 if res["passed"] else 1


# ── config mode: a matrix of agents × tasks ───────────────────────────────────

def _load_config(path):
    """Config (YAML or JSON):
        agents: [{model: gemini-3.1-pro-preview, obs: visual}, {model: mock}]
        tasks:  [Minh/job-sites_3c5414, software-marketplace_dc52a3, "site:banking"]
        tasks:  all       # or the single token "all" -> every current task w/ a verifier
        grade: verifier   # + max_steps/timeout/headless/start_from/native_llm defaults
    """
    text = Path(path).read_text()
    try:
        import yaml; cfg = yaml.safe_load(text)
    except Exception:
        cfg = json.loads(text)
    return cfg


def _all_task_ids():
    """Every current annotated task that has a verifier (excludes .trash)."""
    return [f"{p.parent.parent.name}/{p.parent.name}"
            for p in sorted(ANNOTATIONS_DIR.glob("*/*/task.json"))
            if (p.parent / "verifier.json").exists() and "/.trash/" not in p.as_posix()]


def _expand_tasks(entries):
    """Task ids, expanding "all" into every current annotated task and "site:<id>"
    into every annotated task on that site. `entries` may be the bare string "all"."""
    if isinstance(entries, str):
        entries = [entries]
    out = []
    for e in entries or []:
        if e == "all":
            out.extend(_all_task_ids())
        elif isinstance(e, str) and e.startswith("site:"):
            sid = e.split(":", 1)[1]
            for p in sorted(ANNOTATIONS_DIR.glob("*/*/task.json")):
                if "/.trash/" in p.as_posix():
                    continue
                t = json.loads(p.read_text())
                sites = [s["id"] if isinstance(s, dict) else s for s in (t.get("sites") or [])]
                if sid in sites and (p.parent / "verifier.json").exists():
                    out.append(f"{p.parent.parent.name}/{p.parent.name}")
        else:
            out.append(e)
    # de-dup, preserve order
    return list(dict.fromkeys(out))


async def run_config(args):
    cfg = _load_config(args.config)
    agents = cfg.get("agents") or [{"model": cfg.get("model", "gemini-flash")}]
    tasks = _expand_tasks(cfg.get("tasks"))
    d = lambda k, dv: cfg.get(k, dv)  # run-wide defaults
    exclude = set(cfg.get("exclude") or [])   # task_ids to skip entirely (e.g. poison tasks)
    resume = cfg.get("resume", True)          # skip tasks whose result.json already exists
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path(cfg.get("out") or (ROOT / "evaluation" / "results" / f"config_{ts}"))
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"{BOLD}{CYAN}config run{RESET}: {len(agents)} agent(s) × {len(tasks)} task(s) = "
          f"{len(agents)*len(tasks)} runs  →  {run_dir}\n")
    results = []
    for ai, a in enumerate(agents):
        model = a["model"]; label = a.get("label", model)
        for ti, task_id in enumerate(tasks):
            tag = f"{DIM}[{label} · {task_id}]{RESET}"
            out_dir = run_dir / f"{label.replace('/','-')}__{task_id.replace('/','-')}"
            if task_id in exclude:
                print(f"  {tag} {DIM}SKIP (excluded){RESET}")
                continue
            if resume and (out_dir / "result.json").exists():
                print(f"  {tag} {DIM}SKIP (done){RESET}")
                continue
            try:
                res = await run_and_grade(
                    task_id=task_id, model=model,
                    obs=a.get("obs", d("obs", "axtree")), grade=a.get("grade", d("grade", "verifier")),
                    judge_model=a.get("judge_model", d("judge_model", "auto")),
                    native_llm=a.get("native_llm", d("native_llm", False)),
                    harness=a.get("harness", d("harness", "browser-use")),
                    max_steps=d("max_steps", 50), timeout=d("timeout", 300),
                    headless=d("headless", True), start_from=d("start_from", "recorded"),
                    port=args.port, out=out_dir,
                    verbose=False)
                res["agent_label"] = label
                mk = f"{GREEN}PASS{RESET}" if res["passed"] else f"{RED}FAIL{RESET}"
                print(f"  {tag} {mk}  {DIM}{res['elapsed_s']:.0f}s  {res['llm_tokens']['total']}tok{RESET}"
                      + ("" if res["judge"] is None else f"  judge={'P' if res['judge'].get('pass') else 'F'}"))
                results.append(res)
            except Exception as exc:
                print(f"  {tag} {RED}ERROR{RESET} {exc}")
                results.append({"agent_label": label, "model": model, "task_id": task_id,
                                "passed": False, "error": str(exc)})

    (run_dir / "results.json").write_text(json.dumps(results, indent=1, default=str))
    _print_matrix(agents, tasks, results, run_dir)
    return 0


def _print_matrix(agents, tasks, results, run_dir):
    by = {(r.get("agent_label", r.get("model")), r["task_id"]): r for r in results}
    labels = [a.get("label", a["model"]) for a in agents]
    tids = list(dict.fromkeys(r["task_id"] for r in results))
    w = max([len(t) for t in tids] + [10])
    print(f"\n{BOLD}results matrix{RESET}  (✓ pass / ✗ fail)")
    print(f"  {'task':<{w}}  " + "  ".join(f"{l[:14]:>14}" for l in labels))
    for t in tids:
        cells = []
        for l in labels:
            r = by.get((l, t))
            cells.append(f"{GREEN}✓{RESET}" if r and r.get("passed") else f"{RED}✗{RESET}")
        print(f"  {t:<{w}}  " + "  ".join(f"{c:>{14+len(GREEN)+len(RESET)}}" for c in cells))
    print(f"\n{BOLD}pass rate{RESET}:")
    for l in labels:
        rs = [r for r in results if r.get("agent_label", r.get("model")) == l]
        p = sum(1 for r in rs if r.get("passed")); tot = len(rs)
        tok = sum((r.get("llm_tokens") or {}).get("total", 0) for r in rs)
        print(f"  {l:<22} {p}/{tot} ({100*p//max(tot,1)}%)   {DIM}{tok} tokens{RESET}")
    print(f"\nresults → {run_dir/'results.json'}")


def _failed_leaves(node, out=None):
    if out is None:
        out = []
    if isinstance(node, dict) and "checks" in node:
        for c in node["checks"]:
            _failed_leaves(c, out)
    elif isinstance(node, dict) and node.get("type") and not node.get("passed"):
        out.append(node)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task-id", help="'<task_id>' or '<annotator>/<task_id>' (single run)")
    ap.add_argument("--config", help="YAML/JSON config for a matrix of agents × tasks "
                    "(agents: [{model, obs?, grade?}], tasks: [ids or 'site:<id>'], + defaults). "
                    "Overrides --task-id.")
    ap.add_argument("--model", default="gemini-flash",
                    help="agent model passed to ChatLLM (e.g. gemini-flash, gpt-4o), or 'mock'")
    ap.add_argument("--obs", choices=["visual", "axtree", "html"], default="axtree",
                    help="agent observation mode: 'visual' feeds screenshots (use_vision=True); "
                         "'axtree'/'html' feed browser-use's text DOM serialization "
                         "(use_vision=False). Default: axtree.")
    ap.add_argument("--grade", choices=["verifier", "judge", "both"], default="verifier",
                    help="how to grade: the macro verifier (default), an LLM judge on "
                         "expected_outcome, or both.")
    ap.add_argument("--judge-model", default="auto",
                    help="model for the LLM judge when --grade includes judge (default: the "
                         "configured default model).")
    ap.add_argument("--harness", choices=["browser-use", "computer-use", "auto"],
                    default="browser-use",
                    help="agent harness: 'browser-use' (DOM/text loop, all providers, default); "
                         "'computer-use' = the provider's NATIVE computer-use tool (screenshots + "
                         "click/type) for commercial models (gemini/openai/anthropic); "
                         "'auto' = computer-use for commercial providers, browser-use otherwise.")
    ap.add_argument("--native-llm", action="store_true",
                    help="drive the agent with browser-use's provider-native LLM (needs that "
                         "provider's API key in env; enables true vision). Default: the unified "
                         "ChatLLM path (text DOM, works with every configured provider incl. Vertex).")
    ap.add_argument("--start-from", choices=["recorded", "starting_url"], default="recorded",
                    help="where the agent starts: 'recorded' = the first observation URL in the "
                         "human trajectory (where start-record was actually clicked; default); "
                         "'starting_url' = the task's starting_url field (often empty/stale).")
    ap.add_argument("--port", type=int, default=8099)
    ap.add_argument("--max-steps", type=int, default=50)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--no-headless", action="store_true", help="show the browser")
    ap.add_argument("--out", default=None, help="artifacts dir (default: evaluation/results/agentverify_*)")
    args = ap.parse_args()
    if args.config:
        raise SystemExit(asyncio.run(run_config(args)))
    if not args.task_id:
        ap.error("one of --task-id or --config is required")
    try:
        raise SystemExit(asyncio.run(main_async(args)))
    except ValueError as e:
        sys.exit(f"{RED}{e}{RESET}")


if __name__ == "__main__":
    main()
