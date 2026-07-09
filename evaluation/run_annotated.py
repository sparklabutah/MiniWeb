#!/usr/bin/env python3
"""Run browser agent against annotated tasks and judge with expected_outcome.

Usage:
    # Run all annotated tasks with expected outcomes (default: gemini-flash)
    python evaluation/run_annotated.py --model gemini-flash

    # Run specific task
    python evaluation/run_annotated.py --model gemini-flash --task-id crm_bf9346

    # Limit number of tasks
    python evaluation/run_annotated.py --model gemini-flash --limit 5

    # Use mock agent (no LLM, for testing the pipeline)
    python evaluation/run_annotated.py --model mock --limit 3
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from agents import AgentResult, BrowserUseAgent, MockAgent, ChatLLM
from server import start_server, stop_server, wait_for_server
from judge import judge_task, format_trajectory

load_dotenv()

# ── Agent factories (same as run_eval.py) ────────────────────────────────────

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
    "gpt": lambda **kw: _make_browser_use_agent(
        lambda: __import__(
            "browser_use.llm.openai.chat", fromlist=["ChatOpenAI"]
        ).ChatOpenAI(model="gpt-4o"),
        **kw,
    ),
    "llm": lambda **kw: _make_browser_use_agent(
        lambda: ChatLLM(),
        **kw,
    ),
    "groq": lambda **kw: _make_browser_use_agent(
        lambda: __import__(
            "browser_use.llm.litellm.chat", fromlist=["ChatLiteLLM"]
        ).ChatLiteLLM(model="groq/meta-llama/llama-4-scout-17b-16e-instruct"),
        **kw,
    ),
    "groq-70b": lambda **kw: _make_browser_use_agent(
        lambda: __import__(
            "browser_use.llm.litellm.chat", fromlist=["ChatLiteLLM"]
        ).ChatLiteLLM(model="groq/llama-3.3-70b-versatile"),
        **kw,
    ),
    "mock": lambda **kw: MockAgent(**kw),
}

# ── Colors ───────────────────────────────────────────────────────────────────

BOLD, DIM, RESET = "\033[1m", "\033[2m", "\033[0m"
GREEN, RED, YELLOW, CYAN = "\033[32m", "\033[31m", "\033[33m", "\033[36m"
BG_GREEN, BG_RED, WHITE = "\033[42m", "\033[41m", "\033[97m"


# ── Load annotated tasks ────────────────────────────────────────────────────

def load_annotated_tasks(task_id=None, limit=None):
    from annotation.storage import list_tasks
    tasks = list_tasks()
    # Only tasks with expected_outcome or expected_answer
    tasks = [t for t in tasks if t.get("expected_outcome", "").strip() or t.get("expected_answer", "").strip()]

    if task_id:
        ids = [s.strip() for s in task_id.split(",")]
        tasks = [t for t in tasks if t.get("task_id") in ids]

    if limit:
        tasks = tasks[:limit]

    return tasks


# ── Main ────────────────────────────────────────────────────────────────────

async def run_eval(args):
    tasks = load_annotated_tasks(task_id=args.task_id, limit=args.limit)
    if not tasks:
        print(f"{RED}No annotated tasks with expected_outcome found.{RESET}")
        sys.exit(1)

    # Start server
    port = args.port
    server_proc = start_server(port)
    first_site = tasks[0]["sites"][0]
    first_site_id = first_site["id"] if isinstance(first_site, dict) else first_site
    if not wait_for_server(port, site_id=first_site_id, timeout=90):
        stop_server(server_proc)
        print(f"{RED}Server failed to start on port {port}{RESET}")
        sys.exit(1)

    server_url = f"http://localhost:{port}"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    mode = "ambiguous" if args.ambiguous else "original"
    results_dir = Path(__file__).resolve().parent.parent / "evaluation" / "results" / f"annotated_{mode}_{args.model}_{timestamp}"
    results_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{BOLD}{CYAN}{'=' * 60}{RESET}")
    print(f"{BOLD}{CYAN}  MiniWeb Annotated Task Evaluation{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 60}{RESET}")
    print(f"  {DIM}Model:{RESET}  {BOLD}{args.model}{RESET}")
    print(f"  {DIM}Tasks:{RESET}  {BOLD}{len(tasks)}{RESET}")
    print(f"  {DIM}Mode:{RESET}   {BOLD}{mode}{RESET}")
    print(f"  {DIM}Judge:{RESET}  {BOLD}{args.judge_model}{RESET}")
    print(f"  {DIM}Output:{RESET} {results_dir}")
    print(f"{CYAN}{'─' * 60}{RESET}\n")

    agent = AGENT_FACTORIES[args.model](
        use_vision=args.use_vision,
        max_steps=args.max_steps,
        timeout=args.timeout,
        headless=not args.no_headless,
    )

    results = []
    try:
        # Setup agent with first site
        await agent.setup(f"{server_url}/sites/{first_site_id}")

        for i, task in enumerate(tasks):
            task_id = task["task_id"]
            sites = task.get("sites", [])
            site_ids = [s["id"] if isinstance(s, dict) else s for s in sites]
            site_id = site_ids[0] if site_ids else "unknown"
            instruction = task.get("instruction", "")
            if args.ambiguous and task.get("instruction_ambiguous", "").strip():
                instruction = task["instruction_ambiguous"]
            expected_outcome = task.get("expected_outcome", "")
            expected_answer = task.get("expected_answer", "")

            task_dir = results_dir / task_id
            task_dir.mkdir(parents=True, exist_ok=True)

            print(f"  [{i+1}/{len(tasks)}] {BOLD}{task_id}{RESET} ({site_id})")
            print(f"    {DIM}{instruction[:80]}...{RESET}")

            try:
                # Use starting_url if available, otherwise site homepage
                start_path = task.get("starting_url", f"/sites/{site_id}/")
                start_url = f"{server_url}{start_path}"

                # Run agent
                result: AgentResult = await agent.run(
                    task=instruction,
                    server_url=start_url,
                    task_dir=task_dir,
                )

                # Load trajectory from saved history.json and convert to judge format
                history_file = task_dir / "history.json"
                trajectory = []
                if history_file.exists():
                    try:
                        raw = json.loads(history_file.read_text())
                        history_items = raw.get("history", raw) if isinstance(raw, dict) else raw
                        for step in history_items:
                            if not isinstance(step, dict):
                                continue
                            mo = step.get("model_output", {})
                            actions = mo.get("action", [])
                            result_list = step.get("result", [])
                            goal = mo.get("next_goal", "")
                            memory = mo.get("memory", "")
                            eval_prev = mo.get("evaluation_previous_goal", "")
                            for act in actions:
                                if isinstance(act, dict):
                                    for verb, params in act.items():
                                        entry = {"action": verb}
                                        if isinstance(params, dict):
                                            entry.update(params)
                                        trajectory.append(entry)
                            # Add result info
                            for r in (result_list or []):
                                if isinstance(r, dict) and r.get("extracted_content"):
                                    trajectory.append({"action": "result", "text": r["extracted_content"][:200]})
                    except (json.JSONDecodeError, OSError):
                        pass

                # Judge with expected_outcome as rubric, fall back to expected_answer
                rubric = expected_outcome
                if not rubric:
                    rubric = f"The agent must produce this answer:\n{expected_answer}"

                verdict = judge_task(
                    instruction=instruction,
                    trajectory=trajectory,
                    expected_answer=expected_answer or "",
                    rubric=rubric,
                    agent_answer=result.final_result or "",
                    model=args.judge_model,
                )

                passed = verdict["pass"]
                badge = f"{BG_GREEN}{WHITE}{BOLD} PASS {RESET}" if passed else f"{BG_RED}{WHITE}{BOLD} FAIL {RESET}"
                print(f"    {badge} {DIM}score={verdict['score']:.1f} | {result.elapsed:.0f}s | {result.steps} steps{RESET}")
                print(f"    {DIM}Judge: {verdict['reasoning'][:100]}{RESET}")

                task_result = {
                    "task_id": task_id,
                    "site": site_id,
                    "instruction": instruction,
                    "expected_outcome": expected_outcome,
                    "expected_answer": expected_answer,
                    "passed": passed,
                    "judge_score": verdict["score"],
                    "judge_reasoning": verdict["reasoning"],
                    "elapsed": result.elapsed,
                    "steps": result.steps,
                    "is_done": result.is_done,
                    "final_result": result.final_result,
                    "errors": result.errors,
                }

            except asyncio.TimeoutError:
                print(f"    {BG_RED}{WHITE}{BOLD} TIME {RESET} {DIM}Timed out{RESET}")
                task_result = {
                    "task_id": task_id, "site": site_id,
                    "instruction": instruction,
                    "expected_outcome": expected_outcome,
                    "passed": False, "judge_score": 0.0,
                    "judge_reasoning": "Timed out",
                    "elapsed": 180, "steps": -1,
                    "is_done": False, "final_result": None,
                    "errors": ["Timeout"],
                }
                # Restart agent
                if hasattr(agent, "restart_session"):
                    try:
                        await agent.restart_session()
                    except Exception:
                        pass

            except Exception as e:
                print(f"    {BG_RED}{WHITE}{BOLD} ERR  {RESET} {DIM}{e}{RESET}")
                task_result = {
                    "task_id": task_id, "site": site_id,
                    "instruction": instruction,
                    "expected_outcome": expected_outcome,
                    "passed": False, "judge_score": 0.0,
                    "judge_reasoning": f"Agent error: {e}",
                    "elapsed": 0, "steps": -1,
                    "is_done": False, "final_result": None,
                    "errors": [str(e)],
                }
                if hasattr(agent, "restart_session"):
                    try:
                        await agent.restart_session()
                    except Exception:
                        pass

            with open(task_dir / "result.json", "w") as f:
                json.dump(task_result, f, indent=2)
            results.append(task_result)

            # Always restart browser between tasks to avoid stale state
            if hasattr(agent, "restart_session") and i < len(tasks) - 1:
                try:
                    await agent.restart_session()
                except Exception:
                    pass
            print()

    finally:
        await agent.teardown()
        stop_server(server_proc)

    # Summary
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    avg_score = sum(r["judge_score"] for r in results) / total if total else 0

    aggregate = {
        "model": args.model,
        "judge_model": args.judge_model,
        "timestamp": timestamp,
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total * 100, 1) if total else 0,
        "avg_score": round(avg_score, 2),
        "tasks": results,
    }
    with open(results_dir / "results.json", "w") as f:
        json.dump(aggregate, f, indent=2)

    pct = aggregate["pass_rate"]
    pct_color = GREEN if pct >= 50 else RED
    print(f"\n{BOLD}{CYAN}{'=' * 60}{RESET}")
    print(f"  {BOLD}Results: {pct_color}{passed}/{total} passed ({pct}%){RESET}")
    print(f"  {BOLD}Avg Judge Score: {avg_score:.2f}{RESET}")
    print()
    for r in results:
        badge = f"{GREEN}PASS{RESET}" if r["passed"] else f"{RED}FAIL{RESET}"
        print(f"    {badge} {r['task_id']} ({r['site']}) score={r['judge_score']:.1f}")
    print()
    print(f"  {DIM}Output:{RESET} {results_dir}")
    print(f"{CYAN}{'=' * 60}{RESET}\n")


def main():
    parser = argparse.ArgumentParser(description="Run annotated tasks with LLM judge")
    parser.add_argument("--model", choices=list(AGENT_FACTORIES.keys()), default="gemini-flash")
    parser.add_argument("--task-id", default=None, help="Comma-separated task IDs")
    parser.add_argument("--limit", type=int, default=None, help="Max tasks to run")
    parser.add_argument("--max-steps", type=int, default=50)
    parser.add_argument("--use-vision", action="store_true")
    parser.add_argument("--no-headless", action="store_true")
    parser.add_argument("--timeout", type=int, default=300, help="Timeout per task in seconds")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--judge-model", default="auto", help="Model for LLM judge")
    parser.add_argument("--ambiguous", action="store_true", help="Use ambiguous instructions instead of original")
    args = parser.parse_args()
    asyncio.run(run_eval(args))


if __name__ == "__main__":
    main()
