#!/usr/bin/env python3
"""Validate a MiniWeb site by running reference solutions + verifiers per-task.

Usage:
    python scripts/validate_site.py <site-id>
    python scripts/validate_site.py <site-id> --task moocs-008   # single task

Each task runs in isolation: reset -> solve -> verify -> reset.
This ensures write-tasks don't pollute each other's state.
"""

import argparse
import importlib
import importlib.util
import json
import socket
import sys
import threading
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
SITES_DIR = PROJECT_ROOT / "sites"


def load_tasks(site_id):
    tasks_file = SITES_DIR / site_id / "tasks.json"
    if not tasks_file.exists():
        print(f"Error: {tasks_file} not found", file=sys.stderr)
        sys.exit(1)
    return json.loads(tasks_file.read_text())


def load_module(site_id, module_name):
    path = SITES_DIR / site_id / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def reset(site_id):
    import subprocess
    subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "reset_site.py"), site_id],
        check=True, capture_output=True,
    )


def start_server():
    """Start Flask app on a random port. Returns (server_url, app, srv)."""
    from app import create_app
    from werkzeug.serving import make_server

    app = create_app()
    app.config["TESTING"] = True

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    srv = make_server("127.0.0.1", port, app, threaded=True)
    thread = threading.Thread(target=srv.serve_forever)
    thread.daemon = True
    thread.start()

    return f"http://127.0.0.1:{port}", app, srv


def validate_task(task, site_id, ref_mod, ver_mod, client, server_url):
    """Run one task: solve then verify. Returns (task_id, sol_result, passed, detail)."""
    tid = task["task_id"]

    # Run reference solution
    sol_name = task.get("reference_solution")
    sol_result = None
    if sol_name:
        func = getattr(ref_mod, sol_name, None)
        if func:
            try:
                sol_result = func(client)
            except Exception as e:
                sol_result = f"ERROR: {e}"
        else:
            sol_result = f"(missing {sol_name})"
    else:
        sol_result = "(none)"

    # Run verifier
    ver_name = task.get("verifier")
    if ver_name:
        func = getattr(ver_mod, ver_name, None)
        if func:
            try:
                r = func(server_url)
                return tid, sol_result, r["pass"], r["detail"]
            except Exception as e:
                return tid, sol_result, False, f"ERROR: {e}"
        else:
            return tid, sol_result, False, f"(missing {ver_name})"
    else:
        return tid, sol_result, None, "(no verifier)"


def main():
    parser = argparse.ArgumentParser(description="Validate a MiniWeb site")
    parser.add_argument("site_id", help="Site ID to validate")
    parser.add_argument("--task", default=None, help="Run only this task ID")
    parser.add_argument("--no-reset", action="store_true",
                        help="Skip resets between tasks (faster but may have cross-contamination)")
    args = parser.parse_args()

    site_id = args.site_id
    tasks = load_tasks(site_id)
    if args.task:
        tasks = [t for t in tasks if t["task_id"] == args.task]
        if not tasks:
            print(f"Task {args.task} not found", file=sys.stderr)
            sys.exit(1)

    print(f"Validating {site_id}: {len(tasks)} task(s)\n")

    # Load modules
    ref_mod = load_module(site_id, "reference_solutions")
    ver_mod = load_module(site_id, "verifiers")

    # Start server
    server_url, app, srv = start_server()
    client = app.test_client()

    passed = failed = skipped = 0
    for task in tasks:
        tid = task["task_id"]

        # Reset before each task for isolation
        if not args.no_reset:
            reset(site_id)

        _, sol_result, ok, detail = validate_task(
            task, site_id, ref_mod, ver_mod, client, server_url
        )

        if ok is None:
            icon, skipped = "SKIP", skipped + 1
        elif ok:
            icon, passed = "PASS", passed + 1
        else:
            icon, failed = "FAIL", failed + 1

        print(f"  [{icon}] {tid} (sol={sol_result}): {detail}")

    print(f"\nResults: {passed}/{len(tasks)} passed, {failed} failed, {skipped} skipped")

    # Final reset
    if not args.no_reset:
        reset(site_id)

    srv.shutdown()
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
