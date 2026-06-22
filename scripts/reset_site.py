#!/usr/bin/env python3
"""Reset a MiniWeb site's mutable data back to its pristine state.

Usage:
    python scripts/reset_site.py <site-id>          # reset one site
    python scripts/reset_site.py --all               # reset all sites
    python scripts/reset_site.py --snapshot <site-id> # save current state as new pristine baseline

Each site stores its pristine data in  sites/<id>/data/.pristine/.
The reset copies those files back into  sites/<id>/data/, overwriting
any mutations from agent runs or eval harnesses.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SITES_DIR = PROJECT_ROOT / "sites"


def discover_sites():
    """Return list of site-id strings (skip _template and dirs without site.json)."""
    sites = []
    for p in sorted(SITES_DIR.iterdir()):
        if not p.is_dir() or p.name.startswith("_"):
            continue
        if (p / "site.json").exists():
            sites.append(p.name)
    return sites


def reset_site(site_id: str) -> bool:
    """Copy .pristine/*.json back to data/. Returns True on success."""
    pristine = SITES_DIR / site_id / "data" / ".pristine"
    data_dir = SITES_DIR / site_id / "data"

    if not pristine.exists():
        print(f"  SKIP {site_id}: no .pristine/ directory")
        return False

    files = list(pristine.glob("*.json"))
    if not files:
        print(f"  SKIP {site_id}: .pristine/ has no JSON files")
        return False

    for src in files:
        dst = data_dir / src.name
        shutil.copy2(src, dst)

    print(f"  OK   {site_id}: restored {len(files)} file(s)")
    return True


def snapshot_site(site_id: str) -> bool:
    """Save current data/*.json as the new pristine baseline."""
    data_dir = SITES_DIR / site_id / "data"
    pristine = data_dir / ".pristine"

    if not data_dir.exists():
        print(f"  SKIP {site_id}: no data/ directory")
        return False

    pristine.mkdir(exist_ok=True)
    files = [f for f in data_dir.glob("*.json")]
    if not files:
        print(f"  SKIP {site_id}: no JSON files in data/")
        return False

    for src in files:
        shutil.copy2(src, pristine / src.name)

    print(f"  OK   {site_id}: snapshot {len(files)} file(s) to .pristine/")
    return True


def main():
    parser = argparse.ArgumentParser(description="Reset or snapshot MiniWeb site data")
    parser.add_argument("site_id", nargs="?", help="Site ID to reset/snapshot")
    parser.add_argument("--all", action="store_true", help="Reset all discovered sites")
    parser.add_argument("--snapshot", action="store_true",
                        help="Save current data as new pristine baseline (instead of resetting)")
    args = parser.parse_args()

    if not args.site_id and not args.all:
        parser.print_help()
        sys.exit(1)

    if args.all and args.site_id:
        print("Error: cannot combine --all with a specific site-id", file=sys.stderr)
        sys.exit(1)

    sites = discover_sites() if args.all else [args.site_id]

    action = snapshot_site if args.snapshot else reset_site
    verb = "Snapshot" if args.snapshot else "Reset"

    print(f"{verb} ({len(sites)} site{'s' if len(sites) != 1 else ''}):")
    ok = sum(1 for s in sites if action(s))
    print(f"\nDone: {ok}/{len(sites)} succeeded.")

    sys.exit(0 if ok == len(sites) else 1)


if __name__ == "__main__":
    main()
