"""Task Review mode: review queues and a before/after view of each task.

`before_review.json` (next to task.json) freezes the task as it was before any
correction — instruction, answer, macro tags and verifier. It is written once:
backfilled from the September 2026 review baselines, and otherwise captured
automatically the first time a task is edited through the annotation API.
"""
import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from annotation import macro_browser, quality
from annotation.storage import ANNOTATIONS_DIR

BEFORE_FILE = "before_review.json"
TASK_KEYS = ("instruction", "expected_answer", "answer_type", "alternatives", "expected_outcome", "sites",
             "starting_url", "macros", "macro_instances", "macro_operations", "macro_spans", "macro_subtasks",
             "macro_edges", "qa_answers", "annotator", "saved_at")

# A human tag set before the task's last AI correction counts as no tag: the task
# is back in "To review" until someone tags the corrected version. Why a task needs
# attention (flags, outdated original, changed tags, new pull) is shown as chips,
# and each queue lists the most urgent tasks first.
QUEUES = [
    ("todo", "To review"),
    ("done", "Reviewed"),
    ("all", "All tasks"),
]


def write_before(directory, task, verifier, source):
    """Freeze `task`/`verifier` as the pre-correction version (never overwrites)."""
    path = Path(directory) / BEFORE_FILE
    if path.exists():
        return False
    payload = {"source": source, "captured_at": datetime.now(timezone.utc).isoformat(),
               "task": {k: task.get(k) for k in TASK_KEYS if k in task},
               "verifier": (verifier or {}).get("macros") or {}}
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False))
    return True


def ensure_before(directory):
    """Called before an API edit: the first edit freezes the current version."""
    directory = Path(directory)
    if (directory / BEFORE_FILE).exists() or not (directory / "task.json").is_file():
        return False
    return write_before(directory, quality.read_json(directory / "task.json"),
                        quality.read_json(directory / "verifier.json"), "first API edit")


def _norm(text):
    return " ".join(str(text or "").split())


def _tag_set(task):
    ops = task.get("macro_operations") or {}
    return sorted((macro, ops.get(inst) or "") for inst, macro in macro_browser.instances(task))


def changes(task, verifier, before):
    """Which reviewable parts differ between the frozen version and now."""
    if not before:
        return {}
    old = before.get("task") or {}
    return {"instruction": _norm(old.get("instruction")) != _norm(task.get("instruction")),
            "tags": _tag_set(old) != _tag_set(task),
            "answer": _norm(old.get("expected_answer")) != _norm(task.get("expected_answer")),
            "verifier": (before.get("verifier") or {}) != (verifier or {})}


def _human_tag(task):
    tag = task.get("review_tag")
    return tag if isinstance(tag, dict) else ({"tag": tag} if tag else None)


def _when(value):
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def last_correction(task):
    """Time of the latest AI correction of this task (None if never corrected)."""
    stamps = [_when((task.get(k) or {}).get("reviewed_at")) for k in ("ai_review", "macro_ai_review")]
    stamps = [s for s in stamps if s]
    return max(stamps) if stamps else None


def reviewed_since_correction(task):
    """A human tag newer than the last correction means the current version was reviewed."""
    human, fixed = _human_tag(task) or {}, last_correction(task)
    at = _when(human.get("at"))
    return bool(human.get("tag")) and (fixed is None or (at is not None and at >= fixed))


def _flags(task):
    return ((task.get("macro_ai_review") or {}).get("flags") or []) + ((task.get("ai_review") or {}).get("issues") or [])


def _new_pull(docs):
    return any(str(doc).startswith("data/task_review_railway_") for doc in docs)


def _urgency(t):
    """Most urgent first: needs a decision, original recording outdated, tags/answer changed, reworded."""
    ch = t["changed"]
    return (not t["flags"], t["gold"] is not False, not (ch.get("tags") or ch.get("answer")),
            not ch.get("instruction"), t["key"])


def _signature():
    sig = []
    for path in sorted(ANNOTATIONS_DIR.glob("*/*/task.json")):
        if any(p.startswith(".") for p in path.relative_to(ANNOTATIONS_DIR).parts):
            continue
        extra = [path.parent / "verifier_runs.json", path.parent / "verifier.json", path.parent / BEFORE_FILE]
        sig.append((str(path.parent), path.stat().st_mtime_ns,
                    tuple(p.stat().st_mtime_ns if p.exists() else 0 for p in extra)))
    return tuple(sig)


@lru_cache(maxsize=2)
def _index(signature):
    tasks = []
    for folder, *_ in signature:
        d = Path(folder)
        key = f"{d.parent.name}/{d.name}"
        task = quality.read_json(d / "task.json")
        before = quality.read_json(d / BEFORE_FILE) or None
        diff = changes(task, quality.read_json(d / "verifier.json").get("macros"), before)
        runs = quality.read_json(d / "verifier_runs.json").get("runs", {})
        gold, walk = (runs.get("gold") or {}).get("passed"), (runs.get("walk") or {}).get("passed")
        human = _human_tag(task) or {}
        docs = (task.get("ai_review") or {}).get("documents") or []
        pending = not reviewed_since_correction(task)
        tasks.append({"key": key, "annotator": d.parent.name, "task_id": d.name,
                      "instruction": _norm(task.get("instruction"))[:160], "human": None if pending else human,
                      "ai": (task.get("ai_review") or {}).get("recommendation"), "gold": gold, "walk": walk,
                      "changed": diff, "flags": len(_flags(task)), "reviewed": not pending,
                      "rerecorded": bool(task.get("rerecorded_at")), "new_pull": _new_pull(docs),
                      "queues": ["todo" if pending else "done", "all"]})
    tasks.sort(key=_urgency)
    counts = {q: sum(q in t["queues"] for t in tasks) for q, _ in QUEUES}
    return {"queues": [{"id": q, "label": label, "count": counts[q]} for q, label in QUEUES], "tasks": tasks}


def index():
    return _index(_signature())


def detail(annotator, task_id):
    d = (ANNOTATIONS_DIR / annotator / task_id).resolve()
    if d.parent.parent != ANNOTATIONS_DIR.resolve() or not (d / "task.json").is_file():
        return None
    task = quality.read_json(d / "task.json")
    verifier = quality.read_json(d / "verifier.json").get("macros") or {}
    before = quality.read_json(d / BEFORE_FILE) or None
    ai, macro_ai = task.get("ai_review") or {}, task.get("macro_ai_review") or {}

    def side(t, verifier):
        return {"instruction": t.get("instruction", ""), "expected_answer": t.get("expected_answer", ""),
                "expected_outcome": t.get("expected_outcome", ""), "sites": t.get("sites") or [],
                "tags": macro_browser._tags(t), "verifier": verifier or {}}

    summary = quality.summary(d, task)
    return {"key": f"{annotator}/{task_id}", "annotator": annotator, "task_id": task_id,
            "now": side(task, verifier),
            "before": dict(side(before.get("task") or {}, before.get("verifier")),
                           source=before.get("source"), captured_at=before.get("captured_at")) if before else None,
            "changed": changes(task, verifier, before),
            "ai": {"recommendation": ai.get("recommendation"), "note": ai.get("note", ""),
                   "changes": ai.get("changes") or [], "issues": ai.get("issues") or [],
                   "macro_notes": macro_ai.get("notes") or [], "flags": _flags(task)},
            "human": _human_tag(task) if reviewed_since_correction(task) else None,
            "reviewed": reviewed_since_correction(task),
            "last_correction": (last_correction(task) or "") and last_correction(task).isoformat(), "runs": {r["source"]: {"passed": r.get("passed"), "stale": r.get("stale"),
                                                              "run_at": r.get("run_at")} for r in summary["runs"]},
            "has_walk": (d / "verification_walk.json").exists(), "new_pull": _new_pull(ai.get("documents") or []),
            "walk_by": summary["walk_by"], "rerecorded": summary["rerecorded"]}
