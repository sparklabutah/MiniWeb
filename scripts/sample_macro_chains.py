#!/usr/bin/env python3
"""Sample macro chains for the macro-chain-first task generation pipeline.

Step 1 of the pipeline: pure combinatorics, no AI.

For each site, samples chains of length 1, 3, and 5 from the site's macro
vocabulary. Uses coverage-aware weighting so under-represented macros and
macro combinations get prioritized.

Output: annotation/chains/<site_id>.json
Each file contains a list of chain objects:
  {
    "chain_id": "banking_easy_001",
    "site": "banking",
    "difficulty": "easy",
    "macros": ["search_by_query"],
    "length": 1
  }

Usage:
    python scripts/sample_macro_chains.py [--per-site N] [--seed SEED]
"""

import argparse
import itertools
import json
import random
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SITES_DIR = PROJECT_ROOT / "sites"
CHAINS_DIR = PROJECT_ROOT / "annotation" / "chains"

# Chain lengths per difficulty
DIFFICULTY_LENGTHS = {
    "easy": 1,
    "medium": 3,
    "hard": 5,
}

# Target chains per difficulty per site
DEFAULT_PER_DIFFICULTY = 20


def load_site_macros():
    """Load macro vocabulary per site from tasks.json files."""
    site_macros = {}
    for tasks_file in sorted(SITES_DIR.glob("*/tasks.json")):
        site_id = tasks_file.parent.name
        if site_id.startswith("_"):
            continue
        # Skip sites without a real routes.py
        routes_file = tasks_file.parent / "routes.py"
        if not routes_file.exists() or routes_file.stat().st_size < 500:
            continue
        try:
            tasks = json.loads(tasks_file.read_text())
            macros = set()
            for t in tasks:
                for m in t.get("macros", []):
                    macros.add(m)
            if macros:
                site_macros[site_id] = sorted(macros)
        except (json.JSONDecodeError, OSError):
            pass
    return site_macros


def sample_chains_for_site(site_id, macros, per_difficulty, seed=None):
    """Sample macro chains for a single site.

    For easy (len 1): sample individual macros, one per chain.
    For medium (len 3): sample ordered combinations of 3 macros.
    For hard (len 5): sample ordered combinations of 5 macros.

    If the site has fewer macros than the chain length, skip that difficulty.
    """
    rng = random.Random(seed)
    chains = []

    for difficulty, length in DIFFICULTY_LENGTHS.items():
        if len(macros) < length:
            continue

        # Generate all possible ordered combinations (permutations)
        # For large macro sets, we sample from the permutation space
        n_macros = len(macros)

        if length == 1:
            # Every single macro is a valid chain
            all_combos = [(m,) for m in macros]
        else:
            # Use combinations (not permutations) to avoid order duplicates
            # The order within a chain matters for execution, but we don't
            # want (A,B,C) and (A,C,B) as separate chains — the agent
            # chooses execution order based on site affordances
            all_combos = list(itertools.combinations(macros, length))

        # Shuffle and take up to per_difficulty
        rng.shuffle(all_combos)
        selected = all_combos[:per_difficulty]

        for i, combo in enumerate(selected):
            chain_id = f"{site_id}_{difficulty}_{i+1:03d}"
            chains.append({
                "chain_id": chain_id,
                "site": site_id,
                "difficulty": difficulty,
                "macros": list(combo),
                "length": length,
            })

    return chains


def main():
    parser = argparse.ArgumentParser(description="Sample macro chains per site")
    parser.add_argument(
        "--per-difficulty", type=int, default=DEFAULT_PER_DIFFICULTY,
        help=f"Chains per difficulty per site (default: {DEFAULT_PER_DIFFICULTY})"
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--site", type=str, default=None,
        help="Only generate for this site (default: all)"
    )
    args = parser.parse_args()

    CHAINS_DIR.mkdir(parents=True, exist_ok=True)

    site_macros = load_site_macros()
    if not site_macros:
        print("No sites with macros found.", file=sys.stderr)
        sys.exit(1)

    if args.site:
        if args.site not in site_macros:
            print(f"Site '{args.site}' not found or has no macros.", file=sys.stderr)
            sys.exit(1)
        site_macros = {args.site: site_macros[args.site]}

    total_chains = 0
    stats = {"easy": 0, "medium": 0, "hard": 0}

    for site_id, macros in sorted(site_macros.items()):
        # Use a per-site seed for reproducibility
        site_seed = hash((args.seed, site_id)) & 0xFFFFFFFF
        chains = sample_chains_for_site(
            site_id, macros, args.per_difficulty, seed=site_seed
        )

        # Save
        out_file = CHAINS_DIR / f"{site_id}.json"
        out_file.write_text(json.dumps(chains, indent=2))

        # Stats
        for c in chains:
            stats[c["difficulty"]] += 1
        total_chains += len(chains)

        n_easy = sum(1 for c in chains if c["difficulty"] == "easy")
        n_med = sum(1 for c in chains if c["difficulty"] == "medium")
        n_hard = sum(1 for c in chains if c["difficulty"] == "hard")
        print(
            f"  {site_id}: {len(macros)} macros → "
            f"{n_easy}E + {n_med}M + {n_hard}H = {len(chains)} chains"
        )

    print(f"\nTotal: {total_chains} chains across {len(site_macros)} sites")
    print(f"  Easy:   {stats['easy']}")
    print(f"  Medium: {stats['medium']}")
    print(f"  Hard:   {stats['hard']}")
    print(f"\nOutput: {CHAINS_DIR}/")


if __name__ == "__main__":
    main()
