"""Index for the Task Audit page (miniweb/annotation/task_audit.py): every final-set task in review order (held-out test tasks
first) with its split, the validity status of its demonstration and what the review changed. The status needs the
evaluator, which the deployed app does not ship, so it is computed here and uploaded; the page reads everything else
live from the task folders.

    python src/miniweb/scripts/build_task_audit.py                                  # -> data/task_audit/index.json
    python src/miniweb/scripts/upload_db_railway.py --url <deployment> --task-audit data/task_audit

Status as the paper's grader validation (and scripts/build_release.py) decides it: `stale` when the task is tagged
stale, else `valid` when the task's current verifier passes the recording, else `verifier_rejected`.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]   # the repository
sys.path.insert(0, str(ROOT / "src"))
from miniweb.annotation import final_set  # noqa: E402
from miniweb.annotation.app import _load_test_trajectory  # noqa: E402
from miniweb.annotation.storage import ANNOTATIONS_DIR  # noqa: E402
from miniwebgen.viewer import FAMILIES  # noqa: E402
from miniwebagent.evaluate import grade_human, human_tasks  # noqa: E402

OUT = ROOT / "data" / "task_audit"
# a task's content fields: an original and a current definition differ in what is graded or shown to the agent
CONTENT_KEYS = ("instruction", "sites", "macros", "macro_edges", "macro_subtasks", "macro_spans", "macro_operations",
                "macro_required", "expected_answer", "answer_type", "alternatives", "expected_outcome", "starting_url",
                "requires_login", "qa_answers")


def main():
    final = final_set.tasks()
    test = {t["task_id"] for t in human_tasks(split="test")}
    train = {t["task_id"] for t in human_tasks(split="train")}
    rows = []
    for t in human_tasks(split="all"):
        tid, (folder, _) = t["task_id"], t["key"].split("/", 1)
        if final and tid not in final:
            continue
        d = ANNOTATIONS_DIR / folder / tid
        task = json.loads((d / "task.json").read_text())
        before = json.loads((d / "before_review.json").read_text()) if (d / "before_review.json").exists() else {}
        orig_t, orig_v = before.get("task") or {}, before.get("verifier") or {}
        changed = [k for k in CONTENT_KEYS if orig_t and k in orig_t and orig_t.get(k) != task.get(k)]
        if (task.get("instruction_original") and task.get("instruction_original") != task.get("instruction")
                and "instruction" not in changed):
            changed.append("instruction")
        if ((task.get("review_tag") or {}).get("tag")) == "stale":
            status = "stale"
        else:
            traj, answer, _ = _load_test_trajectory(folder, tid, "gold")
            status = "valid" if grade_human(t, traj or [], answer)[0] else "verifier_rejected"
        cur_v = json.loads((d / "verifier.json").read_text())
        rows.append({"task_id": tid, "folder": folder, "site": t["site"], "sites": t["sites"],
                     "split": "test" if tid in test else "train" if tid in train else "excluded",
                     "status": status, "changed_fields": changed,
                     "verifier_repaired": bool(orig_v) and orig_v.get("macros") != cur_v.get("macros"),
                     "rerecorded": bool(task.get("rerecorded_at")),
                     "walk": (d / "verification_walk.json").exists()})
    rank = {"test": 0, "train": 1, "excluded": 2}
    rows.sort(key=lambda r: (rank[r["split"]], r["site"], r["task_id"]))
    families = {m: f for f, ms in FAMILIES.items() for m in ms}
    OUT.mkdir(parents=True, exist_ok=True)
    text = json.dumps({"tasks": rows, "families": families}, indent=1, ensure_ascii=False)
    (OUT / "index.json").write_text(text)
    local = ANNOTATIONS_DIR / ".task_audit" / "_index" / "index.json"     # where a local app reads it
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text(text)
    count = lambda k, v: sum(r[k] == v for r in rows)  # noqa: E731
    print(f"{len(rows)} tasks (test {count('split', 'test')}, train {count('split', 'train')}, "
          f"excluded {count('split', 'excluded')}); demonstrations valid {count('status', 'valid')}, "
          f"stale {count('status', 'stale')}, verifier_rejected {count('status', 'verifier_rejected')}; "
          f"task changed {sum(bool(r['changed_fields']) for r in rows)}, verifier changed "
          f"{sum(r['verifier_repaired'] for r in rows)}, re-recorded {sum(r['rerecorded'] for r in rows)}, "
          f"walk-throughs {sum(r['walk'] for r in rows)} -> {OUT / 'index.json'}")


if __name__ == "__main__":
    main()
