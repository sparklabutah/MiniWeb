"""Task audit: a reviewer's pass over every final task, its demonstration and what the review changed (the original
and repaired versions the release ships side by side).

The index (scripts/build_task_audit.py, uploaded by scripts/upload_db_railway.py --task-audit) is
<ANNOTATIONS_DIR>/.task_audit/_index/index.json: the review order with each task's split, demonstration status and changed
fields. Everything else is read live from the task folder: task.json, verifier.json, before_review.json (the task and
verifier before the review) and the recordings (annotation/macro_browser.py). Labels are appended to
<ANNOTATIONS_DIR>/.task_audit_labels/<labeler>.jsonl; the last record of a task wins.
"""
import json
import re
from datetime import datetime, timezone

from annotation import macro_browser
from annotation.storage import ANNOTATIONS_DIR

TASK_VERDICTS = {"ok", "fix", "broken"}
CHANGE_VERDICTS = {"accept", "reject", "unsure"}
CONTENT_KEYS = ("instruction", "sites", "macros", "macro_edges", "macro_subtasks", "macro_spans", "macro_operations",
                "macro_required", "expected_answer", "answer_type", "alternatives", "expected_outcome", "starting_url",
                "requires_login", "qa_answers")
_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


def _index_file():
    return ANNOTATIONS_DIR / ".task_audit" / "_index" / "index.json"


def _labels_dir():
    return ANNOTATIONS_DIR / ".task_audit_labels"


def _labeler_file(labeler):
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", labeler or "anonymous")[:60]
    return _labels_dir() / f"{safe}.jsonl"


def _index():
    f = _index_file()
    return json.loads(f.read_text()) if f.exists() else {"tasks": [], "families": {}}


def entries():
    """The index rows whose task folder is present, in review order."""
    return [r for r in _index()["tasks"] if (ANNOTATIONS_DIR / r["folder"] / r["task_id"] / "task.json").is_file()]


def entry(task_id):
    if not _ID.match(task_id or ""):
        return None
    return next((r for r in entries() if r["task_id"] == task_id), None)


def modified(row):
    return bool(row["changed_fields"] or row["verifier_repaired"] or row["rerecorded"])


def _read(path):
    return json.loads(path.read_text()) if path.is_file() else {}


def case(task_id):
    """The task now and before the review, both verifiers, and its recordings with their primitive spans."""
    row = entry(task_id)
    if row is None:
        return None
    d = ANNOTATIONS_DIR / row["folder"] / task_id
    task, verifier, before = _read(d / "task.json"), _read(d / "verifier.json"), _read(d / "before_review.json")
    orig_t = before.get("task") or {}
    if task.get("instruction_original") and "instruction" not in orig_t:
        orig_t = {**orig_t, "instruction": task["instruction_original"]}
    families = _index().get("families", {})
    gold = macro_browser.task_detail(row["folder"], task_id, "gold") or {}
    walk = macro_browser.task_detail(row["folder"], task_id, "walk") if row["walk"] else None
    for source, detail in (("gold", gold), ("walk", walk)):
        if detail:
            detail["actions"] = _with_result(_events(row, source), detail.get("actions") or [])
    review = task.get("ai_review") or {}
    return {**row, "modified": modified(row),
            "instruction": task.get("instruction", ""), "expected_answer": task.get("expected_answer"),
            "starting_url": task.get("starting_url"), "rerecorded_at": task.get("rerecorded_at"),
            "current": {k: task.get(k) for k in CONTENT_KEYS if k in task or k in orig_t},
            "original": {k: orig_t.get(k) for k in CONTENT_KEYS if k in orig_t} if orig_t else None,
            "verifier": verifier.get("macros"), "verifier_original": (before.get("verifier") or {}).get("macros"),
            "review": {"recommendation": review.get("recommendation"), "changes": review.get("changes") or []},
            "primitives": [{**t, "family": families.get(t["macro"], "")} for t in gold.get("tags", [])],
            "recordings": {"gold": gold.get("actions", []), "walk": (walk or {}).get("actions")}}


def _events(row, source):
    f = ANNOTATIONS_DIR / row["folder"] / row["task_id"] / ("verification_walk.json" if source == "walk" else "trajectory.json")
    if not f.is_file():
        return []
    t = json.loads(f.read_text())
    return t if isinstance(t, list) else t.get("trajectory", [])


def _final_page(events):
    """The last page a recording captured after its last action, unless it is the frame that action already shows.
    The recorder takes an action's screenshot right after the action, before its effect; the page that results (a
    filtered list, the next page) loads later and is usually captured as HTML only."""
    acts = [i for i, e in enumerate(events) if e.get("type") == "action"]
    after = [e for e in events[acts[-1] + 1:] if e.get("type") == "observation"] if acts else []
    if not after:
        return None
    shown = next((e for e in after if e.get("screenshot")), None)
    last = after[-1]
    return last if last is not shown and (last.get("screenshot") or last.get("snapshot")) else None


def _with_result(events, actions):
    """The recording's steps plus a final "result" step showing the page after the last action, when one was captured."""
    last = _final_page(events) if actions else None
    if last is None:
        return actions
    return actions + [{"index": len(actions) + 1, "action": "result", "target": "the page after the last step", "value": "",
                       "url": re.sub(r"^https?://[^/]+", "", str(last.get("url") or "")), "frame": last.get("screenshot"),
                       "outline": "", "result": True}]


def snapshot(task_id, source, index):
    """The page a recording saw at action `index` (1-based) as its HTML snapshot: the observation recorded with the
    action, else the last one before it (as macro_browser.task_detail pairs frames); index n + 1 is the page after the
    last action. For steps without a screenshot."""
    row = entry(task_id)
    if row is None or source not in ("gold", "walk"):
        return None
    events = _events(row, source)
    if index == sum(e.get("type") == "action" for e in events) + 1:
        last = _final_page(events)
        return last.get("snapshot") if last else None
    k, last = 0, None
    for i, e in enumerate(events):
        if e.get("type") == "observation" and e.get("snapshot"):
            last = e["snapshot"]
        if e.get("type") != "action":
            continue
        k += 1
        if k == index:
            for nxt in events[i + 1:]:
                if nxt.get("type") == "action":
                    break
                if nxt.get("type") == "observation" and nxt.get("snapshot"):
                    return nxt["snapshot"]
            return last
    return None


def _from_file(f):
    out = {}
    for line in f.read_text().splitlines():
        try:
            r = json.loads(line) if line.strip() else None
        except ValueError:
            r = None
        if r:
            out[r.get("task_id")] = r
    return out


def labels(labeler):
    """{task_id: last label record} of one labeler."""
    f = _labeler_file(labeler)
    return _from_file(f) if f.exists() else {}


def all_labels():
    """Every labeler's last label per task."""
    out = []
    d = _labels_dir()
    if d.exists():
        for f in sorted(d.glob("*.jsonl")):
            out += _from_file(f).values()
    return out


def save(labeler, task_id, task_verdict, changes=None, notes=""):
    """Validate and append one review: a verdict on the task and, for a task the review modified, on the changes."""
    row = entry(task_id)
    if row is None:
        raise ValueError(f"unknown task {task_id!r}")
    if task_verdict not in TASK_VERDICTS:
        raise ValueError(f"task verdict must be one of {sorted(TASK_VERDICTS)}")
    if modified(row) and changes not in CHANGE_VERDICTS:
        raise ValueError(f"give the review's changes a verdict: one of {sorted(CHANGE_VERDICTS)}")
    rec = {"labeler": labeler, "task_id": task_id, "task": task_verdict,
           "changes": changes if modified(row) else None, "notes": (notes or "")[:4000],
           "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    f = _labeler_file(labeler)
    f.parent.mkdir(parents=True, exist_ok=True)
    with open(f, "a") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec
