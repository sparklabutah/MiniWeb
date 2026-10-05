"""WebArena-Lite-v2 (154 tasks) through the WebMix browser-use harness.

    python -m webmix.wa --arm base --out data/webmix/wa/base            # 4 instances in parallel
    python -m webmix.wa --arm base --instances 1 --limit 3 --out ...    # smoke test

Tasks, per-instance URL maps and the evaluator are ScaleCUA's WebArenaLiteV2 (OpenGVLab/ScaleCUA,
evaluation/WebArenaLiteV2), copied from the host's checkout into data/webmix/wa_lite_v2. Four
deployments run on 155.98.68.29 (instance i: sites at 8081+100(i-1).., homepage 4398+i; map and
wikipedia shared); each instance runs its share of the tasks in order, as the benchmark recommends
(tasks are not fully independent). Reset the instances first (reset API, one per instance on 8090+i).

Each instance worker is its own process: the evaluator's helpers read site URLs from
config.envs.webarena.init.env_config at import time, so that module is pointed at the instance
before the evaluator is imported. Login: one storage state per site per instance, made with the
benchmark's own login flows, loaded into each episode's browser over CDP. Grading: the benchmark's
evaluator on the agent's final page (Playwright attached to browser-use's Chromium over CDP) and its
done() text as the answer; fuzzy matches use the benchmark's judge (gpt-4o-2024-11-20).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from webmix import harness as H

ROOT = Path(__file__).resolve().parent.parent
WA_DIR = ROOT / "data" / "webmix" / "wa_lite_v2"
TASK_DIR = WA_DIR / "config" / "envs" / "webarena" / "tasks"
HOST = "155.98.68.29"
SPLIT = ROOT / "data" / "webmix" / "wa" / "split_5050.json"   # dev = development evals, test = final (2026-09-29)
URL_KEYS = ("SHOPPING_URL", "SHOPPING_ADMIN_URL", "REDDIT_URL", "GITLAB_URL", "MAP_URL", "WIKIPEDIA_URL", "HOMEPAGE_URL")


def instance_urls(i):
    name = "webarena_url.json" if i == 1 else f"webarena_url_{i}.json"
    return json.loads((WA_DIR / "config" / "envs" / "webarena" / "init" / name).read_text())


def load_tasks():
    tasks = [json.loads(p.read_text()) for p in TASK_DIR.glob("[0-9]*.json")]
    return sorted(tasks, key=lambda t: t["task_id"])


def localize(cfg, i):
    """A task config (written for instance 1) with every site URL moved to instance i's."""
    if i == 1:
        return cfg
    s = json.dumps(cfg)
    one, mine = instance_urls(1), instance_urls(i)
    for k in URL_KEYS:
        a, b = one[k].split("/admin")[0], mine[k].split("/admin")[0]
        if a != b:
            s = s.replace(a, b)
    return json.loads(s)


def _point_env_config(i):
    """Import the benchmark's env_config with instance i's URLs (before its evaluator is imported)."""
    if str(WA_DIR) not in sys.path:
        sys.path.insert(0, str(WA_DIR))
    cwd = os.getcwd()
    os.chdir(WA_DIR)                     # env_config opens its URL file by a path relative to the benchmark root
    try:
        import config.envs.webarena.init.env_config as ec
    finally:
        os.chdir(cwd)
    u = instance_urls(i)
    ec.URL = u
    ec.REDDIT, ec.SHOPPING, ec.SHOPPING_ADMIN = u["REDDIT_URL"], u["SHOPPING_URL"], u["SHOPPING_ADMIN_URL"]
    ec.GITLAB, ec.MAP = u["GITLAB_URL"], u["MAP_URL"]
    ec.WIKIPEDIA, ec.HOMEPAGE = u.get("WIKIPEDIA_URL", ""), u.get("HOMEPAGE_URL", "")
    return ec


# ── login states (the benchmark's auto_login flows, per instance) ─────────────

LOGIN_SITES = ("reddit", "shopping_admin", "gitlab", "shopping")


def make_login_states(i, out_dir, sites=LOGIN_SITES):
    """-> {site: storage-state path} for `sites` (default: shopping, shopping_admin, reddit, gitlab) on instance i."""
    from playwright.sync_api import sync_playwright
    ec = _point_env_config(i)
    acc = ec.ACCOUNTS
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    states = {}
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=H.CHROME, headless=True)
        for site in sites:
            for attempt in range(25):            # a site just restored (GitLab above all) can take 15+ min to serve
                try:
                    states[site] = _login(b, ec, acc, site, out_dir)
                    break
                except Exception as e:
                    print(f"[inst {i}] {site} login attempt {attempt + 1} failed: {type(e).__name__}", flush=True)
                    time.sleep(45)
            else:
                raise RuntimeError(f"instance {i}: could not log in to {site}")
        b.close()
    return states


def _login(b, ec, acc, site, out_dir):
    """One site's login (the benchmark's auto_login flow) in a fresh context -> its storage-state path."""
    ctx = b.new_context()
    try:
        page = ctx.new_page()
        page.set_default_timeout(60000)
        if site == "reddit":
            page.goto(f"{ec.REDDIT}/login")
            page.get_by_label("Username").fill(acc["reddit"]["username"])
            page.get_by_label("Password").fill(acc["reddit"]["password"])
            page.get_by_role("button", name="Log in").click()
        elif site == "shopping_admin":
            page.goto(ec.SHOPPING_ADMIN)
            page.get_by_placeholder("user name").fill(acc["shopping_admin"]["username"])
            page.get_by_placeholder("password").fill(acc["shopping_admin"]["password"])
            page.get_by_role("button", name="Sign in").click()
        elif site == "gitlab":
            page.goto(f"{ec.GITLAB}/users/sign_in")
            page.get_by_test_id("username-field").fill(acc["gitlab"]["username"])
            page.get_by_test_id("password-field").fill(acc["gitlab"]["password"])
            page.get_by_test_id("sign-in-button").click()
        elif site == "shopping":
            page.goto(f"{ec.SHOPPING}/customer/account/login/")
            page.get_by_label("Email", exact=True).fill(acc["shopping"]["username"])
            page.get_by_label("Password", exact=True).fill(acc["shopping"]["password"])
            page.get_by_role("button", name="Sign In").click()
        page.wait_for_load_state("load", timeout=60000)
        time.sleep(1)
        path = Path(out_dir) / f"{site}_state.json"
        ctx.storage_state(path=str(path))
        return str(path)
    finally:
        ctx.close()


async def set_cookies(bs, state_paths):
    cookies = []
    for p in state_paths:
        for c in json.loads(Path(p).read_text()).get("cookies", []):
            cookies.append({k: c[k] for k in ("name", "value", "domain", "path", "expires", "httpOnly", "secure", "sameSite")
                            if k in c and c[k] is not None and not (k == "expires" and c[k] < 0)})
    if cookies:
        await bs.cdp_client.send.Storage.setCookies(params={"cookies": cookies})


# ── grading (the benchmark's evaluator, on the agent's final page) ────────────

def evaluate_sync(cdp_url, cfg, answer, final_url):
    """-> (score, {eval_type: score}) by the benchmark's evaluators on the agent's final page."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(cdp_url)
        pages = [pg for ctx in browser.contexts for pg in ctx.pages]
        page = next((pg for pg in reversed(pages) if pg.url == final_url), pages[-1] if pages else None)
        if page is None:
            page = browser.contexts[0].new_page()
        return score_parts(cfg, answer, page)


def score_parts(cfg, answer, page):
    import envs.web.webarena.evaluation.vab_evaluators as ve
    import envs.web.webarena.evaluation.vab_helper_functions as hf
    # program_html locators are "func:reddit_get_post_url(...)" strings eval()'d in the evaluator module, which
    # imports only a few helpers: expose them all (else NameError -> the task scores 0)
    for name in dir(hf):
        if not name.startswith("_") and not hasattr(ve, name):
            setattr(ve, name, getattr(hf, name))
    webarena_evaluator_router = ve.webarena_evaluator_router
    action_list = [{}, {"name": "response", "parameters": {"answer": answer or ""}}]
    comb = webarena_evaluator_router(cfg)
    parts = {t: float(ev(action_list, cfg, page)) for t, ev in zip(cfg["eval"]["eval_types"], comb.evaluators)}
    total = 1.0
    for v in parts.values():
        total *= v
    return total, parts


def use_judge(model):
    """The fuzzy / unachievable-reason matches through helpers.llm with `model` (the benchmark calls
    gpt-4o-2024-11-20 through OpenAI; 'gpt-4o-2024-11-20' keeps that). Same prompts, temperature 0."""
    import envs.web.webarena.evaluation.vab_helper_functions as hf
    if model == "gpt-4o-2024-11-20":
        return
    from helpers.llm import call_llm

    def generate(messages, model_=None, temperature=0, max_tokens=768, top_p=1.0, context_length=0, stop_token=None, **kw):
        system = next((m["content"] for m in messages if m["role"] == "system"), None)
        user = "\n".join(m["content"] for m in messages if m["role"] == "user")
        for _ in range(3):
            out = call_llm(user, system=system, max_tokens=256, temperature=0, model=model)
            if out:
                return out
        return ""
    hf.generate_from_openai_chat_completion = lambda messages, model=None, **kw: generate(messages, **kw)


# ── one instance's worker ─────────────────────────────────────────────────────

async def run_task(cfg, args, out_dir, states):
    from browser_use import Agent
    t0 = time.time()
    tid = cfg["task_id"]
    res = {"task_id": tid, "sites": cfg["sites"], "arm": args.arm, "instance": args.instance, "score": 0.0}
    ep = out_dir / str(tid)
    ep.mkdir(parents=True, exist_ok=True)
    bs = H.make_session(allowed_domains=(HOST, "localhost", "127.0.0.1"))
    try:
        await bs.start()
        await H.enable_clipboard(bs)
        await set_cookies(bs, [states[s] for s in cfg["sites"] if s in states])
        await H.goto(bs, cfg["start_url"])
        llm = H.make_llm(args.model, base_url=args.vllm, temperature=args.temperature)
        if args.router == "planned_sub":
            hist = await asyncio.wait_for(routed_run(bs, llm, cfg, args, ep), timeout=args.timeout)
        elif args.router == "planner_agent":
            hist = await asyncio.wait_for(agent_run(bs, cfg, args, ep), timeout=args.timeout)
        else:
            agent = Agent(task=H.instruction(cfg["intent"], cfg["start_url"]), llm=llm, browser_session=bs,
                          tools=H.make_tools(), max_failures=3, **H.AGENT_KWARGS)
            H.use_normalized_coordinates(bs)
            hist = await asyncio.wait_for(agent.run(max_steps=args.max_steps or H.MAX_STEPS,
                                                    on_step_start=lambda a: H.enable_clipboard(bs, a)),
                                          timeout=args.timeout)
        answer = hist.final_result() or ""
        final_url = await bs.get_current_page_url()
        hist.save_to_file(ep / "history.json")
        from webmix.eval_viewer import copy_screenshots
        copy_screenshots(ep)                     # out of browser-use's /tmp dir, for webmix.eval_viewer
        res.update(answer=answer, final_url=final_url, steps=len(hist.history), done=hist.is_done(),
                   errors=[e for e in hist.errors() if e][:5])
        res["score"], res["parts"] = await asyncio.to_thread(evaluate_sync, bs.cdp_url, cfg, answer, final_url)
        res["judge"] = args.judge
    except asyncio.TimeoutError:
        res["error"] = "timeout"
    except Exception as e:
        res["error"] = f"{type(e).__name__}: {str(e)[:300]}"
    finally:
        res["duration_s"] = round(time.time() - t0, 1)
        try:
            await bs.kill()
        except Exception:
            pass
    (ep / "result.json").write_text(json.dumps(res, indent=1, default=str))
    return res


async def routed_run(bs, llm, cfg, args, ep):
    """The WebMix router (webmix.evaluate planned_sub): the subtask planner lists the remaining steps (family +
    instruction) from the current screen; each step runs as its own episode on its family's specialist, with the whole
    task as background; the planner re-plans after each. Reasoning steps go to the base model (E3 stage 1)."""
    import base64
    from types import SimpleNamespace
    from openai import AsyncOpenAI
    from webmix import planner as P
    from webmix.evaluate import run_subtasks, sub_model
    pclient, plans = AsyncOpenAI(base_url=args.vllm, api_key="EMPTY"), []
    margs = SimpleNamespace(adapters=set(args.adapters.split(",")) - {"none", ""}, fallback=args.fallback,
                            base_name=args.model, reasoning_to_fallback=False)

    async def replan(done_texts):
        png = await bs.take_screenshot()
        steps = await P.plan_steps(pclient, args.planner_name, cfg["intent"], done_texts,
                                   "data:image/png;base64," + base64.b64encode(png).decode(),
                                   P.fewshot_examples() if args.planner_prompt in ("defined", "closed") else None,
                                   defined=args.planner_prompt == "defined", closed=args.planner_prompt == "closed")
        plans.append({"done": list(done_texts), "steps": steps})
        return steps
    try:
        hist, trace = await run_subtasks(bs, llm, None, lambda f: sub_model(f, margs), None, planner=replan,
                                         sub_cap=args.sub_cap, overall=cfg["intent"],
                                         last_step_budget=args.last_step_budget,
                                         outcome_feedback=args.planner_prompt == "closed")
    finally:
        (ep / "plans.json").write_text(json.dumps(plans, indent=1, ensure_ascii=False))
    (ep / "subtasks.json").write_text(json.dumps({"trace": trace, "plans": plans}, indent=1, default=str,
                                                 ensure_ascii=False))
    return hist


async def agent_run(bs, cfg, args, ep):
    """The planner as a browser-use Agent that delegates each step to a family specialist (webmix.planner_agent)."""
    from types import SimpleNamespace
    from webmix.evaluate import sub_model
    from webmix.planner_agent import run_planner_agent
    margs = SimpleNamespace(adapters=set(args.adapters.split(",")) - {"none", ""}, fallback=args.fallback,
                            base_name=args.model, reasoning_to_fallback=False)
    hist, trace, ph = await run_planner_agent(bs, cfg["intent"], cfg["start_url"], lambda f: sub_model(f, margs),
                                              args.vllm, args.planner_name, sub_cap=args.sub_cap,
                                              max_turns=args.planner_turns, temperature=args.temperature,
                                              version=args.agent_version)
    ph.save_to_file(ep / "planner_history.json")
    (ep / "subtasks.json").write_text(json.dumps({"trace": trace}, indent=1, default=str, ensure_ascii=False))
    return hist


def worker(args):
    """Run this instance's share of the tasks, in order."""
    _point_env_config(args.instance)
    use_judge(args.judge)
    out_dir = Path(args.out)
    states = make_login_states(args.instance, out_dir / "_auth" / f"instance_{args.instance}")
    keep = set(json.loads(SPLIT.read_text())[args.split]) if args.split != "all" else None
    tasks = [t for t in load_tasks() if (not args.task_ids or t["task_id"] in args.task_ids)
             and (keep is None or t["task_id"] in keep)]
    tasks = [t for k, t in enumerate(tasks) if k % args.n_instances == args.slot]      # this instance's share
    if args.limit:
        tasks = tasks[:args.limit]
    done = set()
    res_path = out_dir / "results.jsonl"
    if res_path.exists():
        done = {json.loads(line)["task_id"] for line in res_path.read_text().split("\n") if line.strip()}
    for t in tasks:
        if t["task_id"] in done:
            continue
        # a fresh login per task, as WebArena's own harness does: the saved states are server-side sessions, so one
        # episode that signs out (2026-09-30: task 40) logged out every later task on that instance
        need = [s for s in t["sites"] if s in LOGIN_SITES]
        if need:
            states.update(make_login_states(args.instance, out_dir / "_auth" / f"instance_{args.instance}", need))
        res = asyncio.run(run_task(localize(t, args.instance), args, out_dir, states))
        with open(res_path, "a") as f:
            f.write(json.dumps(res, default=str) + "\n")
        print(f"[inst {args.instance}] task {t['task_id']} ({'+'.join(t['sites'])}) score {res['score']} "
              f"{res.get('steps')} steps {res['duration_s']}s {res.get('error') or ''}", flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m webmix.wa")
    ap.add_argument("--arm", default="base", help="label for the run (the served model is --model)")
    ap.add_argument("--model", default="qwen35-4b", help="served model name: the base, or a LoRA adapter's name")
    ap.add_argument("--vllm", default="http://127.0.0.1:8400/v1")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--max-steps", type=int, default=0,
                    help="single agent: step cap (default harness.MAX_STEPS = 40; review round 1, A3, 2026-10-05)")
    # instances 1-2 are ours; 3-4 belong to the collaborator's runs (user, 2026-09-29: 50/50 by instance)
    ap.add_argument("--instances", type=lambda s: [int(x) for x in s.split(",")], default=[1, 2])
    ap.add_argument("--task-ids", type=lambda s: {int(x) for x in s.split(",")}, default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--split", default="all", choices=["dev", "test", "all"],
                    help="WebArena-Lite-v2 half (data/webmix/wa/split_5050.json): dev for development runs, test only for "
                         "the final comparison")
    ap.add_argument("--out", required=True)
    ap.add_argument("--router", default="none", choices=["none", "planned_sub", "planner_agent"],
                    help="planned_sub: the WebMix router (subtask planner + family specialists, webmix.evaluate)")
    ap.add_argument("--planner-name", default="planner5")
    ap.add_argument("--planner-turns", type=int, default=12, help="planner_agent: the planner agent's own turns")
    ap.add_argument("--agent-version", default="v1", help="planner_agent: version (v1, v2, ...)")
    ap.add_argument("--adapters", default="drag,io,select,rest", help="router: family adapters served")
    ap.add_argument("--fallback", default="pooled_v4", help="router: a family without its adapter")
    ap.add_argument("--sub-cap", type=int, default=15, help="router: steps per subtask (of the 40)")
    ap.add_argument("--last-step-budget", action="store_true", help="router: the last planned step gets all steps left")
    ap.add_argument("--planner-prompt", default="", choices=["", "defined", "closed"],
                    help="router: 'defined' = the base model planning with the family-definitions prompt (planner.SYSTEM_DEF)")
    ap.add_argument("--judge", default="gemini-3.5-flash-lite",
                    help="fuzzy-match judge (user, 2026-09-28: flash-lite for our validation runs; the benchmark's own "
                         "is gpt-4o-2024-11-20)")
    ap.add_argument("--regrade", action="store_true", help="re-score an existing run's answers with --judge")
    # internal: one instance worker
    ap.add_argument("--instance", type=int, default=None)
    ap.add_argument("--slot", type=int, default=0)
    ap.add_argument("--n-instances", type=int, default=1)
    args = ap.parse_args(argv)
    _load_openai_env()
    if args.regrade:
        return regrade(Path(args.out), args.judge)
    if args.instance is not None:
        return worker(args)
    Path(args.out).mkdir(parents=True, exist_ok=True)
    procs = []
    for slot, i in enumerate(args.instances):
        cmd = [sys.executable, "-m", "webmix.wa", "--instance", str(i), "--slot", str(slot),
               "--n-instances", str(len(args.instances)), "--arm", args.arm, "--model", args.model, "--vllm", args.vllm,
               "--temperature", str(args.temperature), "--timeout", str(args.timeout), "--out", args.out,
               "--judge", args.judge, "--split", args.split, "--router", args.router, "--planner-name",
               args.planner_name, "--adapters", args.adapters, "--fallback", args.fallback, "--sub-cap", str(args.sub_cap)]
        if args.last_step_budget:
            cmd += ["--last-step-budget"]
        if args.planner_prompt:
            cmd += ["--planner-prompt", args.planner_prompt]
        cmd += ["--planner-turns", str(args.planner_turns), "--agent-version", args.agent_version]
        if args.max_steps:
            cmd += ["--max-steps", str(args.max_steps)]
        if args.limit:
            cmd += ["--limit", str(args.limit)]
        if args.task_ids:
            cmd += ["--task-ids", ",".join(map(str, sorted(args.task_ids)))]
        log = open(Path(args.out) / f"instance_{i}.log", "a")
        procs.append(subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=str(ROOT)))
    for p in procs:
        p.wait()
    summarize(Path(args.out))


def _load_openai_env():
    """The fuzzy-match judge reads OPENAI_API_KEY / OPENAI_BASE_URL (the repo's .env holds the key)."""
    envf = ROOT / ".env"
    if "OPENAI_API_KEY" not in os.environ and envf.exists():
        for line in envf.read_text().split("\n"):
            if line.startswith("OPENAI_API_KEY="):
                os.environ["OPENAI_API_KEY"] = line.split("=", 1)[1].strip().strip('"')
    os.environ.setdefault("OPENAI_BASE_URL", "https://api.openai.com/v1")


def regrade(out_dir, judge):
    """Re-score a run's fuzzy-match tasks with `judge` from the stored answers (their other evaluator,
    url_match, is recomputed from the stored final URL). Writes results_<judge>.jsonl + summary."""
    _point_env_config(1)
    use_judge(judge)
    from envs.web.webarena.evaluation.vab_helper_functions import PseudoPage
    cfgs = {t["task_id"]: t for t in load_tasks()}
    rows = [json.loads(line) for line in (out_dir / "results.jsonl").read_text().split("\n") if line.strip()]
    out = []
    for r in rows:
        cfg = localize(cfgs[r["task_id"]], r["instance"])
        if "fuzzy_match" in (cfg["eval"].get("reference_answers") or {}) and "error" not in r:
            r = {**r, "score_before": r["score"], "judge_before": r.get("judge", "gpt-4o-2024-11-20")}
            r["score"], r["parts"] = score_parts(cfg, r.get("answer") or "", PseudoPage(None, r.get("final_url") or ""))
            r["judge"] = judge
        out.append(r)
    name = f"results_{judge}.jsonl"
    (out_dir / name).write_text("".join(json.dumps(r, default=str) + "\n" for r in out))
    changed = sum(1 for r in out if "score_before" in r and r["score_before"] != r["score"])
    print(f"regraded {sum('score_before' in r for r in out)} fuzzy tasks with {judge}; {changed} changed")
    summarize(out_dir, name)


def summarize(out_dir, name="results.jsonl"):
    rows = [json.loads(line) for line in (out_dir / name).read_text().split("\n") if line.strip()]
    by = {}
    for r in rows:
        s = "+".join(r["sites"])
        by.setdefault(s, []).append(r["score"])
    total = sum(r["score"] for r in rows)
    lines = [f"{len(rows)} tasks, success {total:.0f} ({100 * total / max(1, len(rows)):.1f}%)"]
    lines += [f"  {s}: {sum(v):.0f}/{len(v)} ({100 * sum(v) / len(v):.1f}%)" for s, v in sorted(by.items())]
    (out_dir / ("summary.txt" if name == "results.jsonl" else f"summary_{name[8:-6]}.txt")).write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
