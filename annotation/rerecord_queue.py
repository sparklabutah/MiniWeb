"""Re-record queue: hands the annotator the next task to re-record, so nobody has to look tasks up.

<ANNOTATIONS_DIR>/.rerecord_queue/_queue/queue.json (sent with scripts/upload_db_railway.py --rerecord-queue):
{"since": ISO time, "tasks": [{"task_id", "folder", "start_url", "note", "instruction", "primitives", "answer",
"steps"}]}, in recording order. A task is done once it is re-recorded after `since`: the re-record save stamps
task.json's rerecorded_at. /annotate/rerecord-queue opens the next pending task in the annotator, which then resets the
session, opens the task's start page and shows its steps, and after the save moves on to the next one.
"""
import json

from annotation.storage import ANNOTATIONS_DIR


def _path():
    return ANNOTATIONS_DIR / ".rerecord_queue" / "_queue" / "queue.json"


def load():
    try:
        return json.loads(_path().read_text())
    except (OSError, ValueError):
        return None


def _done(e, since):
    try:
        task = json.loads((ANNOTATIONS_DIR / e["folder"] / e["task_id"] / "task.json").read_text())
    except (OSError, ValueError):
        return True                              # the task is gone: nothing left to re-record
    return (task.get("rerecorded_at") or "") >= since


def status():
    """The queue and the ids already re-recorded, or (None, set()) when there is no queue."""
    q = load()
    if not q:
        return None, set()
    return q, {e["task_id"] for e in q["tasks"] if _done(e, q["since"])}


def next_task(after=""):
    """The first pending task after `after` in queue order, else the first pending one (so skipped tasks come back)."""
    q, finished = status()
    if not q:
        return None
    order = [e["task_id"] for e in q["tasks"]]
    pending = [e for e in q["tasks"] if e["task_id"] not in finished]
    if after in order:
        later = [e for e in pending if order.index(e["task_id"]) > order.index(after)]
        if later:
            return later[0]
    return pending[0] if pending else None


def entry(task_id):
    """task_id's queue entry with its position and the queue's progress, or None."""
    q, finished = status()
    for i, e in enumerate((q or {}).get("tasks", [])):
        if e["task_id"] == task_id:
            return {**e, "position": i + 1, "total": len(q["tasks"]), "done": len(finished)}
    return None
