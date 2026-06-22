"""Task loading, filtering, verification, and single-task execution."""

import importlib.util
import json
import time
from pathlib import Path

from agents import AgentResult

TASK_TIMEOUT = 180  # seconds per task

SITES_DIR = Path(__file__).resolve().parent.parent / "sites"


def load_tasks(site_id: str) -> list[dict]:
    """Load tasks.json for a given site."""
    tasks_file = SITES_DIR / site_id / "tasks.json"
    if not tasks_file.exists():
        raise FileNotFoundError(f"No tasks.json found at {tasks_file}")
    with open(tasks_file) as f:
        return json.load(f)


def filter_tasks(
    tasks: list[dict],
    task_id: str | None = None,
    difficulty: str | None = None,
) -> list[dict]:
    if task_id:
        ids = [s.strip() for s in task_id.split(",")]
        return [t for t in tasks if t["task_id"] in ids]
    if difficulty:
        return [t for t in tasks if t.get("difficulty") == difficulty]
    return tasks


def load_verifier(site_id: str):
    """Load a site's verifiers.py module and return it."""
    verifier_path = SITES_DIR / site_id / "verifiers.py"
    if not verifier_path.exists():
        raise FileNotFoundError(f"No verifiers.py found at {verifier_path}")
    spec = importlib.util.spec_from_file_location("verifier", str(verifier_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_verifier(verifier_mod, verifier_name: str, server_url: str) -> tuple[bool, str]:
    """Run a single verifier function by name. Returns (passed, message)."""
    fn = getattr(verifier_mod, verifier_name, None)
    if fn is None:
        return False, f"Verifier function '{verifier_name}' not found"
    try:
        result = fn(server_url)
        if isinstance(result, dict):
            return result.get("pass", False), result.get("detail", str(result))
        if isinstance(result, tuple):
            return result[0], result[1] if len(result) > 1 else ""
        return bool(result), str(result)
    except Exception as e:
        return False, f"Verifier exception: {e}"


async def run_task(
    task: dict,
    agent_runner,
    server_url: str,
    site_id: str,
    task_dir: Path,
) -> dict:
    """Run a single task: execute the agent, then verify. Returns result dict."""
    task_id = task["task_id"]

    # Run agent (instruction only -- no answers, no verifier info)
    result: AgentResult = await agent_runner.run(
        task=task["instruction"],
        server_url=f"{server_url}/sites/{site_id}",
        task_dir=task_dir,
    )

    # Verify
    try:
        verifier_mod = load_verifier(site_id)
        passed, verifier_message = run_verifier(
            verifier_mod, task["verifier"], server_url,
        )
    except Exception as e:
        passed, verifier_message = False, f"Verifier load error: {e}"

    task_result = {
        "task_id": task_id,
        "difficulty": task.get("difficulty", ""),
        "instruction": task["instruction"],
        "passed": passed,
        "verifier_message": verifier_message,
        "elapsed": result.elapsed,
        "steps": result.steps,
        "is_done": result.is_done,
        "final_result": result.final_result,
        "errors": result.errors,
    }

    with open(task_dir / "result.json", "w") as f:
        json.dump(task_result, f, indent=2)

    return task_result
