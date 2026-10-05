"""Fara1.5 as released, in Microsoft's own agent loop, on MiniWeb human tasks (EXPERIMENT_PLAN, RQ1; 2026-10-02).

Runs in the `fara` venv (github.com/microsoft/fara, playwright 1.51), not the MiniWeb env, and imports only that package
and the standard library. Tasks come from `python -m webmix.fara_rq1 prep` ({BASE} placeholders); grading happens later in
the MiniWeb env (`python -m webmix.fara_rq1 grade`), from what this saves per task:

    <out>/<task_id>/session.json   {"base", "answer", "status", "rounds", "record": [...], "log": [...], "error"}
    <out>/<task_id>/fara/          Fara's own trajectory folder (screenshots, messages)

Setup mirrors webmix.evaluate.prepare_human: /_admin/session-flags (logged out for a login task), then the start page,
the same task wrapper as our agents (webmix.harness.instruction), clipboard allowed (as webmix.harness.enable_clipboard).
Fara's eval mode: auto_user_reply (its confirmation questions get a fixed reply instead of halting) and no captcha gate.

    /home/u1653932/venvs/fara/bin/python webmix/fara_runner.py --tasks <out>/tasks.json --out <out> \\
        --bases http://127.0.0.1:8306,http://127.0.0.1:8307 --endpoint http://127.0.0.1:8640/v1 --model fara15-4b
"""
import argparse
import asyncio
import json
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from fara.agents.fara.fara15_agent import Fara15Agent, Fara15AgentConfig
from fara.core.data_point import SolverStatus, Task
from fara.core.run_context import RunContext
from fara.environments.playwright import PlaywrightEnvironment


def instruction(task_text, start_url):
    """Same wrapper as webmix.harness.instruction (our agents' task text)."""
    return f"You are interacting with a web application at {start_url}. Your task: {task_text}"


async def admin_get(context, base, path):
    """GET a privileged /_admin endpoint as this browser's session (its cookies), outside the page."""
    host = urlsplit(base).hostname
    cookies = await context.cookies()
    header = "; ".join(f"{c['name']}={c['value']}" for c in cookies if (c.get("domain") or "").lstrip(".") in (host, ""))
    req = urllib.request.Request(base + path, headers={"Cookie": header})

    def fetch():
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    return await asyncio.to_thread(fetch)


async def run_task(t, base, args, out):
    ep = out / t["task_id"]
    ep.mkdir(parents=True, exist_ok=True)
    start = t["start"].replace("{BASE}", base)
    prompt = t["prompt"].replace("{BASE}", base)
    flags = base + "/_admin/session-flags" + ("?logout=1" if t["needs_login"] else "")
    res = {"task_id": t["task_id"], "base": base, "answer": None, "status": None, "rounds": None, "error": None,
           "record": [], "log": [], "seconds": None}
    t0 = time.time()
    env = PlaywrightEnvironment(viewport_width=args.width, viewport_height=args.height, headless=True,
                                browser_channel="chromium", start_page=flags, single_tab_mode=True)
    agent = None
    try:
        await env.initialize()
        await env._context.grant_permissions(["clipboard-read", "clipboard-write"], origin=base)
        await env._page.goto(start, wait_until="domcontentloaded")
        await asyncio.sleep(1.0)
        agent = Fara15Agent(Fara15AgentConfig(
            client_config={"model": args.model, "base_url": args.endpoint, "api_key": "not-needed"},
            max_rounds=args.max_rounds, identity="fara_qwen35", critical_points="fara-1.5",
            save_screenshots=True, viewport_width=args.width, viewport_height=args.height,
            auto_user_reply=True, captcha_timeout_limit=0, raise_on_captcha_timeout=False))
        ctx = RunContext.create(environment=env, task=Task(task_id=t["task_id"], instruction=instruction(prompt, start)),
                                output_dir=ep / "fara")
        await agent.initialize(ctx)
        answer, _, _ = await asyncio.wait_for(agent.run(ctx), timeout=args.timeout)
        res["answer"], res["status"] = answer, str(ctx.solver_log.status)
        res["rounds"] = getattr(getattr(agent, "_state", None), "round", None)
    except Exception as e:                       # a timeout or harness error still keeps whatever the session did
        res["error"] = f"{type(e).__name__}: {str(e)[:300]}"
    try:
        res["record"] = (await admin_get(env._context, base, "/_admin/record")).get("entries", []) or []
        res["log"] = (await admin_get(env._context, base, "/_admin/log")).get("entries", []) or []
    except Exception as e:
        res["error"] = (res["error"] or "") + f" | backend read: {type(e).__name__}: {str(e)[:200]}"
    res["seconds"] = round(time.time() - t0, 1)
    (ep / "session.json").write_text(json.dumps(res, default=str))
    try:
        if agent is not None:
            await agent.close(ctx)
    except Exception:
        pass
    try:
        await env.close()
    except Exception:
        pass
    return res


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--bases", required=True, help="comma list of MiniWeb server bases, e.g. http://127.0.0.1:8306")
    ap.add_argument("--endpoint", required=True, help="vLLM OpenAI endpoint serving Fara1.5")
    ap.add_argument("--model", default="fara15-4b")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--max-rounds", type=int, default=40, help="Fara actions per task (our MiniWeb budget: 40)")
    ap.add_argument("--timeout", type=int, default=2400)
    ap.add_argument("--width", type=int, default=1440, help="Fara's native viewport (1440x900)")
    ap.add_argument("--height", type=int, default=900)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--task-ids", default="")
    args = ap.parse_args()
    out = Path(args.out)
    tasks = json.loads(Path(args.tasks).read_text())
    if args.task_ids:
        keep = set(args.task_ids.split(","))
        tasks = [t for t in tasks if t["task_id"] in keep]
    done = {p.parent.name for p in out.glob("*/session.json")}
    tasks = [t for t in tasks if t["task_id"] not in done]                  # resume
    if args.limit:
        tasks = tasks[:args.limit]
    bases = args.bases.split(",")
    queue = asyncio.Queue()
    for t in tasks:
        queue.put_nowait(t)
    print(f"{len(tasks)} tasks, {args.workers} workers on {len(bases)} MiniWeb servers", flush=True)

    async def worker(i):
        while not queue.empty():
            t = queue.get_nowait()
            r = await run_task(t, bases[i % len(bases)], args, out)
            print(f"{t['task_id']}: status={r['status']} rounds={r['rounds']} {r['seconds']}s err={r['error']}", flush=True)
    await asyncio.gather(*(worker(i) for i in range(args.workers)))


if __name__ == "__main__":
    asyncio.run(main())
