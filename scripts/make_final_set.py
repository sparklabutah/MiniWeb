"""Write data/final_set.yaml: the paper's final primitives (37) and tasks (376), which lock the annotation tool.

The primitives are the well-covered ones (at least 3 required instances in the human tasks), exactly as the paper's
figures and tables compute them (docs/figures/common/results.py: well_covered). The tasks are every task directory
under data/annotations/<annotator>/<task_id>/task.json, listed by task id.

    python scripts/make_final_set.py [--unlocked]
"""
import argparse, glob, json, os, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "docs", "figures", "common"))
from results import well_covered  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--unlocked", action="store_true", help="write the sets but leave the tool editable")
    args = ap.parse_args()
    prims = sorted(well_covered())
    tasks = sorted(os.path.basename(os.path.dirname(f))          # task ids are unique across annotators
                   for f in glob.glob(os.path.join(ROOT, "data", "annotations", "*", "*", "task.json")))
    assert len(tasks) == len(set(tasks)), "task ids are no longer unique across annotators"
    import yaml
    out = os.path.join(ROOT, "data", "final_set.yaml")
    with open(out, "w") as f:
        f.write("# The paper's final primitive and task sets (scripts/make_final_set.py). With locked: true the annotation\n"
                "# tool is read-only (no macro registration, no task or verifier edits) and shows only these sets; the\n"
                "# grader-audit labels are the one thing it still records.\n")
        yaml.safe_dump({"locked": not args.unlocked, "primitives": prims, "tasks": tasks}, f, sort_keys=False, width=120)
    print(f"wrote {out}: {len(prims)} primitives, {len(tasks)} tasks, locked={not args.unlocked}")


if __name__ == "__main__":
    main()
