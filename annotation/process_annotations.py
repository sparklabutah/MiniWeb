#!/usr/bin/env python3
"""The annotation reconstruction pipeline — one implementation, three triggers.

For each task it does, in order:

  1. repair form state   — the old recorder serialized outerHTML, which stores
                           ATTRIBUTES, not live DOM properties, so typed text and
                           the chosen <option> were missing from the snapshot.
                           Recover them from the action record and inject them.
  2. reconstruct         — derive the missing observations from the (repaired)
                           HTML: YAML axtree + FULL-PAGE screenshot, with a
                           <select>'s option list drawn open when the action was
                           a select (a native popup is OS-drawn and appears in no
                           page screenshot — real or derived).

Everything is flagged so provenance stays honest:
  form_state_repaired · screenshot_full_page · dropdown_synthesized ·
  backfill_method (stored_html | live_url)

Triggers:
  save time   annotation/observations.py calls process_task() in a thread
  catch-up    python scripts/process_annotations.py            (all incomplete)
  watch       python scripts/process_annotations.py --watch 60 (poll for new)

Idempotent: a task whose observations are already complete is skipped, so it is
safe to run on a cron, after a data pull, or repeatedly.
"""
import argparse
import json
import socket
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from annotation.backfill_observations import (   # noqa: E402
    Capturer, _pair_events, _is_yaml_axtree, _free_port, _start_app,
    ANNOTATIONS_DIR)
from annotation.repair_form_state import repair_task  # noqa: E402


def is_complete(task_dir: Path) -> bool:
    """True when every action already has html + axtree + a screenshot on disk."""
    tf = task_dir / "trajectory.json"
    if not tf.exists():
        return True                      # nothing to do
    try:
        events = json.loads(tf.read_text())
    except json.JSONDecodeError:
        return True
    for _n, _action, obs, _pos in _pair_events(events):
        if obs is None:
            return False
        if not obs.get("snapshot") and not obs.get("url"):
            return False
        if not _is_yaml_axtree(obs.get("axtree") or ""):
            return False
        shot = obs.get("screenshot")
        if not shot or not (task_dir / shot).exists():
            return False
        if not obs.get("screenshot_full_page") and not obs.get("screenshot_captured"):
            return False  # rendered before full-page capture (real captured
            #               frames are viewport-sized and complete as-is)
    return True


def process_task(task_dir: Path, base_url: str, cap: Capturer = None) -> dict:
    """Repair + reconstruct one task. Creates its own browser if `cap` is None."""
    task_dir = Path(task_dir)
    tf = task_dir / "trajectory.json"
    if not tf.exists():
        return {"task": task_dir.name, "error": "no trajectory.json"}

    # 1. repair form state (pure text transform, no browser needed)
    repaired, unmatched = repair_task(str(tf))

    # 2. reconstruct the missing/stale observations
    own_browser = cap is None
    if own_browser:
        cap = Capturer(base_url)
    try:
        from annotation.backfill_observations import process_task as _reconstruct
        stats = _reconstruct(task_dir, cap)
    finally:
        if own_browser:
            cap.close()

    stats["form_state_repaired"] = repaired
    stats["form_state_unmatched"] = unmatched
    return stats


def find_incomplete(annotator: str = "") -> list:
    pattern = f"{annotator}/*" if annotator else "*/*"
    return [d for d in sorted(ANNOTATIONS_DIR.glob(pattern))
            if d.is_dir() and (d / "trajectory.json").exists() and not is_complete(d)]


def run_once(base_url: str, annotator: str = "") -> int:
    todo = find_incomplete(annotator)
    if not todo:
        print("all tasks already complete")
        return 0
    print(f"{len(todo)} task(s) to process")
    cap = Capturer(base_url)
    try:
        for d in todo:
            stats = process_task(d, base_url, cap=cap)
            print(f"  {d.name}: repaired={stats.get('form_state_repaired', 0)} "
                  f"rendered={stats.get('rendered', 0)} "
                  f"new_obs={stats.get('created_obs', 0)}"
                  + (" !" if stats.get("failures") else ""))
    finally:
        cap.close()
    return len(todo)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--annotator", default="", help="limit to one annotator")
    ap.add_argument("--watch", type=int, default=0, metavar="SECONDS",
                    help="keep polling for newly saved tasks every N seconds")
    ap.add_argument("--base-url", default="",
                    help="app to render against (default: start one on a free port)")
    args = ap.parse_args()

    base_url = args.base_url
    if not base_url:
        port = _free_port()
        print(f"starting app on :{port} ...")
        _start_app(port)
        base_url = f"http://127.0.0.1:{port}"

    if not args.watch:
        run_once(base_url, args.annotator)
        return

    print(f"watching {ANNOTATIONS_DIR} every {args.watch}s (ctrl-c to stop)")
    while True:
        try:
            n = run_once(base_url, args.annotator)
            if n:
                print(f"  ({time.strftime('%H:%M:%S')}) processed {n}")
        except Exception:  # noqa: BLE001 — a bad task must not kill the watcher
            import traceback
            traceback.print_exc()
        time.sleep(args.watch)


if __name__ == "__main__":
    main()
