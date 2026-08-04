#!/usr/bin/env python
"""Bulk-mark every saved annotation task as 'stale' in the verifier builder.

Mirrors what /annotate/api/update_task_field does per task: sets
task.json["review_tag"] = {"tag": "stale", "by": ..., "at": ...} and rewrites
with json.dumps(indent=2, default=str). Skips the .trash folder. Backs up the
prior review_tag of every task first so it's reversible.

Usage:  python scripts/mark_tasks_stale.py [--by NAME]
"""
import argparse
import json
import pathlib
import sys
from collections import Counter
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from annotation import storage


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--by", default="bulk", help="'by' name recorded on the tag")
    args = ap.parse_args()

    base = storage.ANNOTATIONS_DIR
    if not base.exists():
        sys.exit(f"annotations dir not found: {base}")

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    tag = {"tag": "stale", "by": args.by, "at": now}

    files = [f for f in base.glob("*/*/task.json") if ".trash" not in f.parts]
    backup = {}
    per_ann = Counter()

    for f in files:
        data = json.loads(f.read_text())
        rel = str(f.relative_to(base))
        backup[rel] = data.get("review_tag")          # prior tag (may be None)
        data["review_tag"] = dict(tag)
        f.write_text(json.dumps(data, indent=2, default=str))
        per_ann[f.parts[-3]] += 1

    bdir = ROOT / "data" / "backups"
    bdir.mkdir(parents=True, exist_ok=True)
    bpath = bdir / f"review-tags-before-stale-{now[:10]}.json"
    bpath.write_text(json.dumps(backup, indent=2))

    print(f"Marked {len(files)} tasks as STALE (by='{args.by}', at={now}).")
    print("Per annotator:", dict(per_ann))
    print(f"Prior review_tags backed up -> {bpath}")


if __name__ == "__main__":
    main()
