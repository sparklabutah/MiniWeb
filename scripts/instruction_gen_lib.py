#!/usr/bin/env python3
"""Helper for Step 3: Generate task instructions from valid chain trajectories.

CLI for Claude Code agents to read chain walk data and save generated tasks.

Usage:
  # List valid chains for a site
  python3 scripts/instruction_gen_lib.py list --site banking

  # Get full context for a chain (trajectory + entity_info + site metadata)
  python3 scripts/instruction_gen_lib.py context --chain-id banking_easy_001 --site banking

  # Save a generated task
  python3 scripts/instruction_gen_lib.py save --site banking --tasks '[{...}, ...]'

  # Check progress
  python3 scripts/instruction_gen_lib.py progress
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SITES_DIR = PROJECT_ROOT / "sites"
CHAINS_DIR = PROJECT_ROOT / "annotation" / "chains"
RUNS_DIR = PROJECT_ROOT / "annotation" / "chain_runs"
VALIDATED_DIR = PROJECT_ROOT / "annotation" / "validated"


def list_valid_chains(site_id):
    """List all valid chain walks for a site."""
    site_dir = RUNS_DIR / site_id
    if not site_dir.exists():
        return []
    chains = []
    for chain_dir in sorted(site_dir.iterdir()):
        status_file = chain_dir / "status.json"
        if not status_file.exists():
            continue
        try:
            status = json.loads(status_file.read_text())
            if status.get("valid"):
                chains.append({
                    "chain_id": status["chain_id"],
                    "site": status["site"],
                    "macros": status["macros"],
                    "difficulty": status["difficulty"],
                    "steps_completed": status.get("steps_completed", 0),
                    "action_summary": status.get("action_summary", ""),
                })
        except (json.JSONDecodeError, OSError, KeyError):
            pass
    return chains


def get_chain_context(chain_id, site_id):
    """Get full context for a chain: status + trajectory + site info."""
    chain_dir = RUNS_DIR / site_id / chain_id
    status = json.loads((chain_dir / "status.json").read_text())
    trajectory = json.loads((chain_dir / "trajectory.json").read_text())

    # Get site name
    site_json = SITES_DIR / site_id / "site.json"
    site_name = site_id
    if site_json.exists():
        meta = json.loads(site_json.read_text())
        site_name = meta.get("name", site_id)

    return {
        "chain_id": chain_id,
        "site_id": site_id,
        "site_name": site_name,
        "difficulty": status["difficulty"],
        "macros": status["macros"],
        "entity_info": status.get("entity_info", {}),
        "action_summary": status.get("action_summary", ""),
        "trajectory": trajectory,
    }


def save_tasks(site_id, tasks):
    """Save generated tasks for a site."""
    VALIDATED_DIR.mkdir(parents=True, exist_ok=True)
    out_file = VALIDATED_DIR / f"{site_id}.json"

    # Merge with existing if any
    existing = []
    if out_file.exists():
        try:
            existing = json.loads(out_file.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    # Deduplicate by chain_id
    existing_ids = {t["chain_id"] for t in existing}
    for t in tasks:
        if t["chain_id"] not in existing_ids:
            existing.append(t)
            existing_ids.add(t["chain_id"])

    out_file.write_text(json.dumps(existing, indent=2))
    return len(existing)


def get_progress():
    """Check instruction generation progress across all sites."""
    results = {}
    for chain_file in sorted(CHAINS_DIR.glob("*.json")):
        site_id = chain_file.stem
        total_chains = len(json.loads(chain_file.read_text()))

        # Count valid walks
        valid_walks = len(list_valid_chains(site_id))

        # Count generated instructions
        validated_file = VALIDATED_DIR / f"{site_id}.json"
        generated = 0
        if validated_file.exists():
            try:
                generated = len(json.loads(validated_file.read_text()))
            except (json.JSONDecodeError, OSError):
                pass

        results[site_id] = {
            "total_chains": total_chains,
            "valid_walks": valid_walks,
            "generated": generated,
        }
    return results


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")

    p_list = sub.add_parser("list", help="List valid chains for a site")
    p_list.add_argument("--site", required=True)

    p_ctx = sub.add_parser("context", help="Get chain context for instruction generation")
    p_ctx.add_argument("--chain-id", required=True)
    p_ctx.add_argument("--site", required=True)

    p_batch = sub.add_parser("batch_context", help="Get contexts for all valid chains of a site")
    p_batch.add_argument("--site", required=True)

    p_save = sub.add_parser("save", help="Save generated tasks")
    p_save.add_argument("--site", required=True)
    p_save.add_argument("--tasks", required=True, help="JSON array of task objects")

    p_prog = sub.add_parser("progress", help="Check progress")

    args = parser.parse_args()

    if args.command == "list":
        chains = list_valid_chains(args.site)
        for c in chains:
            print(json.dumps(c))
        print(f"\nTotal: {len(chains)} valid chains", file=sys.stderr)

    elif args.command == "context":
        ctx = get_chain_context(args.chain_id, args.site)
        print(json.dumps(ctx, indent=2))

    elif args.command == "batch_context":
        chains = list_valid_chains(args.site)
        contexts = []
        for c in chains:
            ctx = get_chain_context(c["chain_id"], args.site)
            # Compact: just the essentials for instruction generation
            contexts.append({
                "chain_id": ctx["chain_id"],
                "difficulty": ctx["difficulty"],
                "macros": ctx["macros"],
                "entity_info": ctx["entity_info"],
                "action_summary": ctx["action_summary"],
                "trajectory_summary": [
                    {
                        "action": e.get("action", e.get("type", "")),
                        "url": e.get("url", ""),
                        "data": e.get("data"),
                        "response_summary": e.get("response_summary", "")[:200] if e.get("response_summary") else "",
                    }
                    for e in ctx["trajectory"]
                ],
            })
        print(json.dumps({"site_id": args.site, "site_name": contexts[0]["chain_id"].rsplit("_",2)[0] if contexts else args.site, "chains": contexts}, indent=2))

    elif args.command == "save":
        tasks = json.loads(args.tasks)
        total = save_tasks(args.site, tasks)
        print(f"Saved. Total tasks for {args.site}: {total}")

    elif args.command == "progress":
        progress = get_progress()
        for site_id, p in sorted(progress.items()):
            status = "DONE" if p["generated"] >= p["valid_walks"] else "TODO" if p["generated"] == 0 else "PARTIAL"
            print(f"  {site_id:35s} {p['generated']:3d}/{p['valid_walks']:3d} generated [{status}]")
        total_gen = sum(p["generated"] for p in progress.values())
        total_valid = sum(p["valid_walks"] for p in progress.values())
        print(f"\nTotal: {total_gen}/{total_valid} instructions generated")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
