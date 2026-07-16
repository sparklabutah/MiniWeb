#!/usr/bin/env python3
"""Prefill the 'refined instruction' field for every task that lacks one.

The verify panel's "Suggest with AI" button rephrases an instruction into a
natural, realistic request (same task, no hand-holding). This runs that same
endpoint over every saved task whose `instruction_ambiguous` is still empty and
writes the suggestion back to task.json, so the box is pre-filled when the
annotator opens the task.

Idempotent: a task that already has a refined instruction is left untouched
(use --overwrite to regenerate). Reuses the live endpoint so the prompt never
drifts from what the button produces.

    python scripts/prefill_refined_instructions.py            # fill empty ones
    python scripts/prefill_refined_instructions.py --overwrite --annotator Kenny
    python scripts/prefill_refined_instructions.py --dry-run
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from annotation.storage import ANNOTATIONS_DIR  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--annotator", default="", help="limit to one annotator")
    ap.add_argument("--overwrite", action="store_true",
                    help="regenerate even tasks that already have a refined instruction")
    ap.add_argument("--dry-run", action="store_true",
                    help="show what would change without calling the LLM or writing")
    args = ap.parse_args()

    pattern = f"{args.annotator}/*/task.json" if args.annotator else "*/*/task.json"
    files = sorted(ANNOTATIONS_DIR.glob(pattern))

    todo = []
    for tf in files:
        try:
            data = json.loads(tf.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if not (data.get("instruction") or "").strip():
            continue
        if (data.get("instruction_ambiguous") or "").strip() and not args.overwrite:
            continue
        todo.append((tf, data))

    print(f"{len(todo)} task(s) to fill "
          f"(of {len(files)} total{'' if not args.annotator else f', annotator={args.annotator}'})")
    if args.dry_run:
        for tf, data in todo:
            print(f"  would fill {tf.parent.parent.name}/{tf.parent.name}: "
                  f"{data['instruction'][:70]}")
        return

    if not todo:
        return

    from app import create_app
    app = create_app()
    app.config["PROPAGATE_EXCEPTIONS"] = True
    client = app.test_client()
    with client.session_transaction() as s:
        s["annotator_authenticated"] = True

    filled = failed = 0
    for tf, data in todo:
        tag = f"{tf.parent.parent.name}/{tf.parent.name}"
        resp = client.post("/annotate/api/make_ambiguous",
                           json={"instruction": data["instruction"]})
        out = resp.get_json() or {}
        refined = (out.get("ambiguous") or "").strip()
        if not refined:
            failed += 1
            print(f"  ! {tag}: {out.get('error') or 'no suggestion returned'}")
            continue
        data["instruction_ambiguous"] = refined
        tf.write_text(json.dumps(data, indent=2, default=str))
        filled += 1
        print(f"  ✓ {tag}: {refined[:80]}")

    print(f"\nfilled {filled}, failed {failed}")


if __name__ == "__main__":
    main()
