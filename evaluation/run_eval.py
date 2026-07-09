#!/usr/bin/env python3
"""
Browser-agent evaluation harness for MiniWeb sites.

Runs a browser-use agent (backed by a configurable LLM) against a site's
tasks.json, then verifies each task with the site's verifiers.py.

Usage:
    # Evaluate bookstore with Gemini Flash
    python evaluation/run_eval.py --site bookstore --model gemini-flash

    # Single task, headed browser for debugging
    python evaluation/run_eval.py --site bookstore --model gemini-flash \\
        --task-id bookstore-003 --no-headless

    # Multiple workers, filter by difficulty
    python evaluation/run_eval.py --site bookstore --model gpt \\
        --difficulty easy --workers 2

    # Multiple attempts per task
    python evaluation/run_eval.py --site bookstore --model gemini-flash \\
        --repetitions 3
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv

from agents import AgentResult, BrowserUseAgent, MockAgent, ChatLLM
from server import start_server, stop_server, wait_for_server
from tasks import TASK_TIMEOUT, filter_tasks, load_tasks, run_task

load_dotenv()

# ── Agent factories ──────────────────────────────────────────────────────────

def _make_browser_use_agent(llm_factory, **kw):
    llm = llm_factory()
    return BrowserUseAgent(llm, **kw)


AGENT_FACTORIES = {
    "gemini-flash": lambda **kw: _make_browser_use_agent(
        lambda: __import__(
            "browser_use.llm.google.chat", fromlist=["ChatGoogle"]
        ).ChatGoogle(model="gemini-3-flash-preview"),
        **kw,
    ),
    "gemini-pro": lambda **kw: _make_browser_use_agent(
        lambda: __import__(
            "browser_use.llm.google.chat", fromlist=["ChatGoogle"]
        ).ChatGoogle(model="gemini-3-pro-preview"),
        **kw,
    ),
    "gpt": lambda **kw: _make_browser_use_agent(
        lambda: __import__(
            "browser_use.llm.openai.chat", fromlist=["ChatOpenAI"]
        ).ChatOpenAI(model="gpt-4o"),
        **kw,
    ),
    "gpt-5.4": lambda **kw: _make_browser_use_agent(
        lambda: __import__(
            "browser_use.llm.openai.chat", fromlist=["ChatOpenAI"]
        ).ChatOpenAI(model="gpt-5.4"),
        **kw,
    ),
    "gpt-5.5": lambda **kw: _make_browser_use_agent(
        lambda: __import__(
            "browser_use.llm.openai.chat", fromlist=["ChatOpenAI"]
        ).ChatOpenAI(model="gpt-5.5"),
        **kw,
    ),
    "mock": lambda **kw: MockAgent(**kw),
    "llm": lambda **kw: _make_browser_use_agent(
        lambda: ChatLLM(),
        **kw,
    ),
}

# ── ANSI colors ──────────────────────────────────────────────────────────────

BOLD, DIM, RESET = "\033[1m", "\033[2m", "\033[0m"
GREEN, RED, YELLOW, CYAN, MAGENTA = (
    "\033[32m", "\033[31m", "\033[33m", "\033[36m", "\033[35m",
)
BG_GREEN, BG_RED, BG_YELLOW, WHITE = (
    "\033[42m", "\033[41m", "\033[43m", "\033[97m",
)
DIFF_COLOR = {"easy": GREEN, "medium": YELLOW, "hard": RED}


# ── Worker ───────────────────────────────────────────────────────────────────

async def worker(
    worker_id: int,
    task_queue: asyncio.Queue,
    results: list,
    results_lock: asyncio.Lock,
    *,
    agent_factory,
    server_url: str,
    site_id: str,
    run_dir: Path,
    use_vision: bool,
    max_steps: int,
    headless: bool,
    use_judge: bool = False,
    judge_model: str = "gpt-4.1-nano",
):
    tag = f"{DIM}[W{worker_id}]{RESET}"

    agent = agent_factory(
        use_vision=use_vision,
        max_steps=max_steps,
        timeout=TASK_TIMEOUT,
        headless=headless,
    )

    try:
        await agent.setup(f"{server_url}/sites/{site_id}")
        print(f"  {tag} ready")

        while True:
            try:
                task = task_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            task_id = task["task_id"]
            diff = task.get("difficulty", "")
            dc = DIFF_COLOR.get(diff, "")
            task_dir = run_dir / task_id
            task_dir.mkdir(parents=True, exist_ok=True)

            needs_restart = False
            try:
                result = await run_task(
                    task=task,
                    agent_runner=agent,
                    server_url=server_url,
                    site_id=site_id,
                    task_dir=task_dir,
                    use_judge=use_judge,
                    judge_model=judge_model,
                )
                badge = (
                    f"{BG_GREEN}{WHITE}{BOLD} PASS {RESET}"
                    if result["passed"]
                    else f"{BG_RED}{WHITE}{BOLD} FAIL {RESET}"
                )
                print(
                    f"  {tag} {BOLD}{task_id}{RESET} {dc}{diff}{RESET}  "
                    f"{badge} {DIM}{result['elapsed']}s  {result['steps']} steps{RESET}"
                )
                if result.get("errors"):
                    err_text = " ".join(str(e) for e in result["errors"])
                    if any(
                        k in err_text
                        for k in ("INSUFFICIENT_RESOURCES", "Timeout", "CDP", "consecutive failures")
                    ):
                        needs_restart = True

            except asyncio.TimeoutError:
                print(
                    f"  {tag} {BOLD}{task_id}{RESET} {dc}{diff}{RESET}  "
                    f"{BG_YELLOW}{WHITE}{BOLD} TIME {RESET} {DIM}{TASK_TIMEOUT}s{RESET}"
                )
                result = {
                    "task_id": task_id,
                    "difficulty": diff,
                    "instruction": task["instruction"],
                    "passed": False,
                    "verifier_message": f"Timed out after {TASK_TIMEOUT}s",
                    "elapsed": TASK_TIMEOUT,
                    "steps": -1,
                    "is_done": False,
                    "final_result": None,
                    "errors": [f"Timeout after {TASK_TIMEOUT}s"],
                }
                with open(task_dir / "result.json", "w") as f:
                    json.dump(result, f, indent=2)
                needs_restart = True

            except Exception as e:
                print(
                    f"  {tag} {BOLD}{task_id}{RESET} {dc}{diff}{RESET}  "
                    f"{BG_RED}{WHITE}{BOLD} ERR  {RESET} {DIM}{e}{RESET}"
                )
                result = {
                    "task_id": task_id,
                    "difficulty": diff,
                    "instruction": task["instruction"],
                    "passed": False,
                    "verifier_message": f"Agent crashed: {e}",
                    "elapsed": 0,
                    "steps": -1,
                    "is_done": False,
                    "final_result": None,
                    "errors": [str(e)],
                }
                with open(task_dir / "result.json", "w") as f:
                    json.dump(result, f, indent=2)
                needs_restart = True

            async with results_lock:
                results.append(result)

            if needs_restart and not task_queue.empty() and hasattr(agent, "restart_session"):
                print(f"  {tag} {YELLOW}Restarting browser...{RESET}")
                try:
                    await agent.restart_session()
                except Exception as restart_err:
                    print(f"  {tag} {RED}Restart failed: {restart_err}{RESET}")
                    break

    except Exception as setup_err:
        import traceback
        print(f"  {tag} {RED}Setup failed: {setup_err}{RESET}")
        traceback.print_exc()
    finally:
        await agent.teardown()


# ── Main ─────────────────────────────────────────────────────────────────────

async def run_eval(args):
    site_id = args.site
    tasks = load_tasks(site_id)
    tasks = filter_tasks(tasks, task_id=args.task_id, difficulty=args.difficulty)
    if not tasks:
        print(f"{RED}No tasks matched.{RESET}")
        sys.exit(1)

    # Start MiniWeb server
    port = args.port
    server_proc = start_server(port)
    if not wait_for_server(port, site_id=site_id, timeout=90):
        stop_server(server_proc)
        print(f"{RED}Server failed to start on port {port}{RESET}")
        sys.exit(1)

    server_url = f"http://localhost:{port}"

    num_workers = min(args.workers, len(tasks))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_base = Path(__file__).resolve().parent.parent / "sites" / site_id / "results"
    run_dir = results_base / f"{args.model}_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{BOLD}{CYAN}{'=' * 60}{RESET}")
    print(f"{BOLD}{CYAN}  MiniWeb Evaluation{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 60}{RESET}")
    print(f"  {DIM}Site:{RESET}    {BOLD}{site_id}{RESET}")
    print(f"  {DIM}Model:{RESET}   {BOLD}{args.model}{RESET}")
    print(f"  {DIM}Tasks:{RESET}   {BOLD}{len(tasks)}{RESET}")
    print(f"  {DIM}Workers:{RESET} {BOLD}{num_workers}{RESET}")
    print(f"  {DIM}Vision:{RESET}  {BOLD}{'on' if args.use_vision else 'off'}{RESET}")
    print(f"  {DIM}Output:{RESET}  {run_dir}")
    print(f"{CYAN}{'─' * 60}{RESET}\n")

    all_results = []

    for rep in range(1, args.repetitions + 1):
        if args.repetitions > 1:
            print(f"\n{MAGENTA}── Attempt {rep}/{args.repetitions} ──{RESET}")

        rep_dir = run_dir / f"attempt_{rep}" if args.repetitions > 1 else run_dir

        task_queue: asyncio.Queue = asyncio.Queue()
        for t in tasks:
            await task_queue.put(t)

        results: list[dict] = []
        results_lock = asyncio.Lock()

        STAGGER_DELAY = 3

        async def staggered_worker(i, delay):
            if delay > 0:
                await asyncio.sleep(delay)
            await worker(
                worker_id=i,
                task_queue=task_queue,
                results=results,
                results_lock=results_lock,
                agent_factory=AGENT_FACTORIES[args.model],
                server_url=server_url,
                site_id=site_id,
                run_dir=rep_dir,
                use_vision=args.use_vision,
                max_steps=args.max_steps,
                headless=not args.no_headless,
                use_judge=args.judge,
                judge_model=args.judge_model,
            )

        worker_coros = [staggered_worker(i, i * STAGGER_DELAY) for i in range(num_workers)]
        await asyncio.gather(*worker_coros)

        all_results.append(results)

    stop_server(server_proc)

    # Aggregate: per-task pass rate across repetitions
    task_pass_counts: dict[str, dict] = {}
    for rep_results in all_results:
        for r in rep_results:
            tid = r["task_id"]
            entry = task_pass_counts.setdefault(tid, {"passed": 0, "total": 0, "last": r})
            entry["total"] += 1
            if r["passed"]:
                entry["passed"] += 1
            entry["last"] = r

    final_results = []
    for tid, info in sorted(task_pass_counts.items()):
        r = dict(info["last"])
        r["pass_rate"] = round(info["passed"] / info["total"], 2) if info["total"] else 0
        r["attempts"] = info["total"]
        final_results.append(r)

    total = len(final_results)
    any_passed = sum(1 for r in final_results if r["pass_rate"] > 0)
    by_diff: dict[str, dict] = {}
    for r in final_results:
        d = r.get("difficulty", "")
        if d:
            by_diff.setdefault(d, {"total": 0, "passed": 0})
            by_diff[d]["total"] += 1
            if r["pass_rate"] > 0:
                by_diff[d]["passed"] += 1

    aggregate = {
        "site": site_id,
        "model": args.model,
        "timestamp": timestamp,
        "repetitions": args.repetitions,
        "total": total,
        "passed": any_passed,
        "pass_rate": round(any_passed / total * 100, 1) if total else 0,
        "by_difficulty": by_diff,
        "tasks": final_results,
    }
    with open(run_dir / "results.json", "w") as f:
        json.dump(aggregate, f, indent=2)

    # Summary
    pct = aggregate["pass_rate"]
    pct_color = GREEN if pct >= 50 else RED
    print(f"\n{BOLD}{CYAN}{'=' * 60}{RESET}")
    print(f"  {BOLD}Results: {pct_color}{any_passed}/{total} passed ({pct}%){RESET}")
    if args.repetitions > 1:
        print(f"  {DIM}(pass = succeeded in at least 1 of {args.repetitions} attempts){RESET}")
    print()
    for d in ["easy", "medium", "hard"]:
        if d in by_diff:
            info = by_diff[d]
            dc = DIFF_COLOR.get(d, "")
            ratio_color = GREEN if info["passed"] == info["total"] else (YELLOW if info["passed"] > 0 else RED)
            print(f"    {dc}{d.capitalize():8s}{RESET} {ratio_color}{info['passed']}/{info['total']}{RESET}")
    print()
    print(f"  {DIM}Output:{RESET} {run_dir}")
    print(f"{CYAN}{'=' * 60}{RESET}\n")


def main():
    parser = argparse.ArgumentParser(description="MiniWeb browser-agent evaluation")
    parser.add_argument("--site", required=True, help="Site ID to evaluate (e.g. bookstore)")
    parser.add_argument("--model", choices=list(AGENT_FACTORIES.keys()), default="gemini-flash")
    parser.add_argument("--task-id", default=None, help="Comma-separated task IDs to run")
    parser.add_argument("--difficulty", choices=["easy", "medium", "hard"], default=None)
    parser.add_argument("--workers", type=int, default=1, help="Parallel workers")
    parser.add_argument("--max-steps", type=int, default=50)
    parser.add_argument("--use-vision", action="store_true")
    parser.add_argument("--no-headless", action="store_true", help="Show browser window")
    parser.add_argument("--port", type=int, default=8080, help="Port for MiniWeb server")
    parser.add_argument(
        "--repetitions", type=int, default=1,
        help="Attempt each task N times; report per-task pass rate",
    )
    parser.add_argument(
        "--judge", action="store_true",
        help="Use LLM-as-judge instead of verifiers.py for evaluation",
    )
    parser.add_argument(
        "--judge-model", default="auto",
        help="Model for LLM judge (default: auto = Groq/OpenAI/Gemini, or an OpenAI model name)",
    )
    args = parser.parse_args()
    asyncio.run(run_eval(args))


if __name__ == "__main__":
    main()
