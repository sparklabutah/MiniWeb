#!/usr/bin/env python3
"""Prune chain walk trajectories where the agent didn't perform real browser actions.

Marks chains as invalid and removes their generated tasks if:
  1. Bad schema — trajectory entries lack "type" field (agent used wrong format)
  2. Too short — <= 2 entries (agent observed but didn't interact)
  3. API-only — all URLs are /api/ endpoints (no page visits)

Usage:
    python scripts/prune_bad_chains.py [--dry-run]
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = PROJECT_ROOT / "annotation" / "chain_runs"
VALIDATED_DIR = PROJECT_ROOT / "annotation" / "validated"


def check_trajectory(traj):
    """Return (is_bad, reason) for a trajectory."""
    if not traj:
        return True, "empty trajectory"

    # Bad schema: entries don't have 'type' field
    has_type = any(e.get("type") for e in traj)
    if not has_type:
        return True, "bad schema (no type field)"

    # Too short: <= 2 entries means at most 1 action+observation pair
    if len(traj) <= 2:
        return True, "too short (<=2 entries)"

    # API-only: all URLs are /api/ endpoints
    urls = [e.get("url", "") for e in traj if e.get("url")]
    if urls and all("/api/" in u for u in urls):
        return True, "api-only (no page visits)"

    return False, ""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Report only, don't modify files")
    args = parser.parse_args()

    pruned = 0
    kept = 0
    reasons = {}
    pruned_chains = set()

    for site_dir in sorted(RUNS_DIR.iterdir()):
        if not site_dir.is_dir():
            continue
        for chain_dir in sorted(site_dir.iterdir()):
            status_file = chain_dir / "status.json"
            traj_file = chain_dir / "trajectory.json"
            if not status_file.exists():
                continue

            status = json.loads(status_file.read_text())
            if not status.get("valid"):
                continue

            traj = []
            if traj_file.exists():
                try:
                    traj = json.loads(traj_file.read_text())
                except (json.JSONDecodeError, OSError):
                    pass

            is_bad, reason = check_trajectory(traj)

            if is_bad:
                pruned += 1
                reasons[reason] = reasons.get(reason, 0) + 1
                pruned_chains.add(status.get("chain_id", chain_dir.name))

                if not args.dry_run:
                    status["valid"] = False
                    status["failure_reason"] = f"pruned: {reason}"
                    status_file.write_text(json.dumps(status, indent=2))
            else:
                kept += 1

    # Remove pruned chains from validated tasks
    removed_tasks = 0
    if not args.dry_run:
        for task_file in sorted(VALIDATED_DIR.glob("*.json")):
            try:
                tasks = json.loads(task_file.read_text())
                before = len(tasks)
                tasks = [t for t in tasks if t.get("chain_id") not in pruned_chains]
                after = len(tasks)
                if after < before:
                    task_file.write_text(json.dumps(tasks, indent=2))
                    removed_tasks += before - after
            except (json.JSONDecodeError, OSError):
                pass

    print(f"Pruned: {pruned}")
    print(f"Kept:   {kept}")
    for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
        print(f"  {reason}: {count}")
    if not args.dry_run:
        print(f"\nRemoved {removed_tasks} tasks from annotation/validated/")
    else:
        print("\n(dry run — no files modified)")


if __name__ == "__main__":
    main()
