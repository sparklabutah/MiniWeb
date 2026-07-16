#!/usr/bin/env python3
"""Run a browser agent on one annotated task and record it like a human.

browser_use drives Chrome over CDP with real Input.dispatchMouseEvent /
dispatchKeyEvent calls, so recorder.js (already injected into every /sites/*
page) sees the agent's clicks and keystrokes as trusted DOM events — exactly
as it sees a human's. recorder.js now posts to /_admin/record when there is
no parent window, so an agent run produces the same action+observation stream
a human annotator does.

This script runs one task and writes, side by side:

    <out>/trajectory.json     recorder stream, human trajectory.json schema
    <out>/history.json        browser_use's own step record (actions + reasoning)
    <out>/beacon_log.json     backend action beacons
    <out>/server_log.json     HTTP request log
    <out>/result.json         task meta, agent answer, timing
    <out>/compare.json        recorder verbs vs. browser_use verbs vs. human's
    <out>/screenshots/        per-step screenshots from browser_use

The point of compare.json: find out which agent actions recorder.js can and
cannot see (clicks/typing should map 1:1; select/scroll/navigate and the
reasoning-only verbs are the open questions).

Usage:
    python evaluation/run_recorded.py --task-id remote-calls_707134
    python evaluation/run_recorded.py --task-id X --out runs/x --model gemini-flash-latest
"""
import argparse
import asyncio
import json
import shutil
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

from agents import BrowserUseAgent, ChatLLM          # noqa: E402
from server import start_server, stop_server, wait_for_server  # noqa: E402


def load_task(task_id):
    from annotation.storage import ANNOTATIONS_DIR
    for p in ANNOTATIONS_DIR.glob(f"*/{task_id}/task.json"):
        task = json.loads(p.read_text())
        task["_dir"] = str(p.parent)
        return task
    raise SystemExit(f"task {task_id} not found under {ANNOTATIONS_DIR}")


def human_verbs(task):
    """Verb counts from the human recording of the same task."""
    traj_file = Path(task["_dir"]) / "trajectory.json"
    if not traj_file.exists():
        return {}
    traj = json.loads(traj_file.read_text())
    return dict(Counter(e.get("action") for e in traj if e.get("type") == "action"))


def browser_use_verbs(history):
    verbs = Counter()
    for step in history.get("history", history if isinstance(history, list) else []):
        if not isinstance(step, dict):
            continue
        mo = step.get("model_output") or {}
        for act in (mo.get("action") or []):
            if isinstance(act, dict):
                for verb in act:
                    verbs[verb] += 1
    return dict(verbs)


async def run(args):
    task = load_task(args.task_id)
    sites = [s["id"] if isinstance(s, dict) else s for s in task.get("sites", [])]
    site_id = sites[0]
    instruction = task.get("instruction", "")

    out = Path(args.out or f"evaluation/results/recorded_{args.task_id}")
    out.mkdir(parents=True, exist_ok=True)

    print(f"task    : {args.task_id}  ({site_id})")
    print(f"instr   : {instruction[:90]}")
    print(f"model   : {args.model}")
    print(f"out     : {out}\n")

    port = args.port
    proc = start_server(port)
    if not wait_for_server(port, site_id=site_id, timeout=90):
        stop_server(proc)
        raise SystemExit("server did not start")
    base = f"http://localhost:{port}"

    from evaluation.generate_fixtures import ensure_fixtures
    agent = BrowserUseAgent(
        ChatLLM(model=args.model),
        use_vision=args.use_vision,
        max_steps=args.max_steps,
        timeout=args.timeout,
        headless=not args.no_headless,
        available_file_paths=ensure_fixtures(),
    )

    start_path = task.get("starting_url") or f"/sites/{site_id}/"
    start_url = base + start_path
    t0 = datetime.now()
    result = None
    try:
        await agent.setup(start_url)
        # the agent's browser shares one Chrome profile/session for the run,
        # so the recorder stream and logs below all belong to this task
        result = await agent.run(task=instruction, server_url=start_url, task_dir=out)
    except asyncio.TimeoutError:
        print("!! agent timed out")
    except Exception as exc:  # noqa: BLE001
        print(f"!! agent error: {exc}")
    finally:
        # ---- collect everything BEFORE tearing the browser down -----------
        import urllib.request

        def fetch(path):
            try:
                with urllib.request.urlopen(base + path, timeout=20) as r:
                    return json.loads(r.read())
            except Exception as exc:  # noqa: BLE001
                print(f"   (could not fetch {path}: {exc})")
                return {}

        recorded = fetch("/_admin/record?all=1").get("entries", [])
        beacons = fetch("/_admin/beacon?all=1").get("entries", [])
        srv_log = fetch("/_admin/log?all=1")

        try:
            await agent.teardown()
        except Exception:  # noqa: BLE001
            pass
        stop_server(proc)

    elapsed = (datetime.now() - t0).total_seconds()

    # ---- write artifacts -------------------------------------------------
    (out / "trajectory.json").write_text(json.dumps(recorded, indent=1))
    (out / "beacon_log.json").write_text(json.dumps(beacons, indent=1))
    (out / "server_log.json").write_text(json.dumps(srv_log, indent=1))

    history = {}
    hist_file = out / "history.json"
    if hist_file.exists():
        try:
            history = json.loads(hist_file.read_text())
        except json.JSONDecodeError:
            history = {}

    rec_actions = [e for e in recorded if e.get("type") == "action"]
    rec_obs = [e for e in recorded if e.get("type") == "observation"]
    rec_verbs = dict(Counter(a.get("action") for a in rec_actions))
    bu_verbs = browser_use_verbs(history)
    hu_verbs = human_verbs(task)

    compare = {
        "task_id": args.task_id,
        "site": site_id,
        "recorder": {"actions": len(rec_actions), "observations": len(rec_obs),
                     "verbs": rec_verbs},
        "browser_use": {"verbs": bu_verbs},
        "human": {"verbs": hu_verbs},
        "seen_by_recorder_only": sorted(set(rec_verbs) - set(bu_verbs)),
        "seen_by_browser_use_only": sorted(set(bu_verbs) - set(rec_verbs)),
        "observations_have_axtree": sum(
            1 for o in rec_obs if o.get("axtree") or o.get("axtree_json")),
        "observations_have_html": sum(1 for o in rec_obs if o.get("snapshot")),
    }
    (out / "compare.json").write_text(json.dumps(compare, indent=1))

    (out / "result.json").write_text(json.dumps({
        "task_id": args.task_id,
        "site": site_id,
        "instruction": instruction,
        "expected_answer": task.get("expected_answer", ""),
        "model": args.model,
        "elapsed_s": round(elapsed, 1),
        "steps": getattr(result, "steps", -1),
        "is_done": getattr(result, "is_done", False),
        "final_result": getattr(result, "final_result", "") or "",
    }, indent=2))

    # ---- report ----------------------------------------------------------
    print("\n" + "=" * 62)
    print(f"recorder captured : {len(rec_actions)} actions, {len(rec_obs)} observations")
    print(f"  verbs           : {rec_verbs or '(none)'}")
    print(f"browser_use verbs : {bu_verbs or '(none)'}")
    print(f"human verbs       : {hu_verbs or '(none)'}")
    print(f"only browser_use  : {compare['seen_by_browser_use_only'] or '(none)'}   <- invisible to recorder")
    print(f"only recorder     : {compare['seen_by_recorder_only'] or '(none)'}")
    print(f"obs with html     : {compare['observations_have_html']}")
    print(f"agent answer      : {(getattr(result, 'final_result', '') or '')[:70]}")
    print(f"expected          : {task.get('expected_answer', '')[:70]}")
    print(f"artifacts         : {out}")
    print("=" * 62)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task-id", required=True, help="e.g. remote-calls_707134")
    ap.add_argument("--out", default="", help="output directory")
    ap.add_argument("--model", default="gemini-flash-latest")
    ap.add_argument("--port", type=int, default=8099)
    ap.add_argument("--max-steps", type=int, default=30)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--use-vision", action="store_true")
    ap.add_argument("--no-headless", action="store_true")
    args = ap.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
