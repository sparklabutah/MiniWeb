"""File-based annotation storage.

Layout:
    {ANNOTATIONS_DIR}/{annotator}/{task_id}/task.json
    {ANNOTATIONS_DIR}/{annotator}/{task_id}/trajectory.json

Each task.json contains: instruction, macros, sites, verifiers, expected_answer, etc.
Each trajectory.json contains the full trajectory array (actions, network, observations).
"""

import json
import os
from datetime import datetime
from pathlib import Path

# resolve(): a relative MINIWEB_ANNOTATIONS_DIR (e.g. "data/annotations" in
# .env) would otherwise be resolved against app.root_path by Flask helpers
# like send_from_directory, silently pointing inside the app package.
ANNOTATIONS_DIR = Path(
    os.environ.get("MINIWEB_ANNOTATIONS_DIR",
                   os.path.join(os.path.dirname(__file__), "..", "data", "annotations"))
).resolve()


def _task_dir(annotator: str, task_id: str) -> Path:
    return ANNOTATIONS_DIR / annotator / task_id


def generate_task_id() -> str:
    """Generate a unique task ID based on timestamp."""
    return datetime.now().strftime("task_%Y%m%d_%H%M%S")


def save_task(annotator: str, task_id: str, task_data: dict, trajectory: list):
    """Save a task and all its logs to the file system.

    Saves:
      task.json         — instruction, macros, sites, answer, outcome
      trajectory.json   — actions + network entries from recorder.js
      server_log.json   — HTTP request/response log from /_admin/log
      beacon_log.json   — UI action beacon log from /_admin/beacon
    """
    d = _task_dir(annotator, task_id)
    d.mkdir(parents=True, exist_ok=True)

    # Real captured frames arrive inline as data URLs — write them out as
    # screenshot files before the trajectory is dumped
    _extract_inline_screenshots(d, trajectory)

    # Extract logs and agent data before saving task metadata
    server_log = task_data.pop("server_log", [])
    beacon_log = task_data.pop("beacon_log", [])
    agent_result = task_data.pop("agent_result", None)

    # Save task metadata
    task_data["task_id"] = task_id
    task_data["annotator"] = annotator
    task_data["saved_at"] = datetime.now().isoformat()
    task_data["trajectory_actions"] = sum(1 for e in trajectory if e.get("type") == "action")
    task_data["trajectory_network"] = sum(1 for e in trajectory if e.get("type") == "network")
    with open(d / "task.json", "w") as f:
        json.dump(task_data, f, indent=2, default=str)

    # Save trajectory (actions + network from recorder.js)
    with open(d / "trajectory.json", "w") as f:
        json.dump(trajectory, f, indent=2, default=str)

    # Save server-side logs — trimmed to THIS recording's time window. The
    # session request log accumulates everything the annotator's browser did
    # (other tasks, free browsing, playback iframes); only entries inside the
    # trajectory's own timestamp span are this recording's evidence.
    if server_log:
        try:
            from evaluation.trajectory import filter_log_to_window
            server_log = filter_log_to_window(trajectory, server_log)
        except Exception:
            pass
        with open(d / "server_log.json", "w") as f:
            json.dump(server_log, f, indent=2, default=str)
    if beacon_log:
        with open(d / "beacon_log.json", "w") as f:
            json.dump(beacon_log, f, indent=2, default=str)
    if agent_result:
        with open(d / "agent_result.json", "w") as f:
            json.dump(agent_result, f, indent=2, default=str)


def _extract_inline_screenshots(task_dir: Path, events: list):
    """Write inline captured frames (obs["screenshot_data"] data URLs) to
    screenshots/step_NNN files and reference them from the observation.

    The step number is the ordinal of the action the observation belongs to,
    numbered exactly like backfill_observations._pair_events (each action
    pairs with the first observation before the next action) — the backfill's
    skip-gate matches on the referenced file, so parity keeps real captures
    from being re-rendered over.
    """
    import base64

    action_no = -1
    paired = False   # current action already has its observation
    for e in events:
        if e.get("type") == "action":
            action_no += 1
            paired = False
            continue
        if e.get("type") != "observation":
            continue
        data = e.pop("screenshot_data", None)
        if paired or action_no < 0:
            continue                     # unpaired observation — drop any frame
        paired = True
        if not data:
            continue
        try:
            header, b64 = data.split(",", 1)
            ext = "png" if "png" in header else "jpg"
            raw = base64.b64decode(b64)
            shots = task_dir / "screenshots"
            shots.mkdir(exist_ok=True)
            name = f"step_{action_no:03d}.{ext}"
            (shots / name).write_bytes(raw)
            e["screenshot"] = f"screenshots/{name}"
            e["screenshot_captured"] = True
            e["screenshot_full_page"] = False
        except (ValueError, OSError):
            pass                         # bad frame — derivation covers it


def load_task(annotator: str, task_id: str) -> dict | None:
    """Load a task with all its data."""
    d = _task_dir(annotator, task_id)
    task_file = d / "task.json"
    if not task_file.exists():
        return None

    task = json.loads(task_file.read_text())

    # Load trajectory
    traj_file = d / "trajectory.json"
    task["trajectory"] = json.loads(traj_file.read_text()) if traj_file.exists() else []

    # Load agent result
    agent_file = d / "agent_result.json"
    if agent_file.exists():
        task["agent_result"] = json.loads(agent_file.read_text())

    # Load server logs (for verifier builder)
    for log_name in ("server_log", "beacon_log"):
        log_file = d / f"{log_name}.json"
        if log_file.exists():
            task[log_name] = json.loads(log_file.read_text())

    return task


def list_tasks(annotator: str = None, newest_first: bool = True) -> list[dict]:
    """List all tasks, optionally filtered by annotator.

    Returns lightweight metadata (no trajectory).
    """
    tasks = []
    if annotator:
        annotators = [annotator]
    else:
        if not ANNOTATIONS_DIR.exists():
            return []
        annotators = [
            d.name for d in ANNOTATIONS_DIR.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ]

    for ann in annotators:
        ann_dir = ANNOTATIONS_DIR / ann
        if not ann_dir.exists():
            continue

        for task_dir in sorted(ann_dir.iterdir()):
            task_file = task_dir / "task.json"
            if task_file.exists():
                try:
                    task = json.loads(task_file.read_text())

                    if not task:
                        continue

                    # Don't include trajectory in list view
                    task.pop("trajectory", None)

                    # Directory name is authoritative when task.json lacks it
                    task.setdefault("annotator", ann)

                    tasks.append(task)
                except (json.JSONDecodeError, OSError):
                    pass

    def last_modified(task):
        saved_at = task.get("saved_at", "")
        review_at = (task.get("review_tag") or {}).get("at", "")
        return max(saved_at, review_at)

    return sorted(tasks, key=last_modified, reverse=newest_first)


def delete_task(annotator: str, task_id: str) -> bool:
    """Delete a task and its trajectory."""
    import shutil
    d = _task_dir(annotator, task_id)
    if d.exists():
        shutil.rmtree(d)
        return True
    return False


def trash_task(annotator: str, task_id: str) -> str | None:
    """Move a task dir into the hidden trash (recoverable delete).

    Destination is {ANNOTATIONS_DIR}/.trash/{annotator}/{task_id}-{timestamp};
    the timestamp suffix keeps every generation when a task is trashed more
    than once (e.g. repeated re-records). Returns the destination path, or
    None when the task doesn't exist. The dot-prefix keeps the trash out of
    list_tasks/get_annotators/get_stats.
    """
    import shutil
    d = _task_dir(annotator, task_id)
    if not d.exists():
        return None
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    dest = ANNOTATIONS_DIR / ".trash" / annotator / f"{task_id}-{stamp}"
    n = 0
    while dest.exists():  # same-instant collision: shutil.move would nest
        n += 1
        dest = dest.with_name(f"{task_id}-{stamp}-{n}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(d), str(dest))
    return str(dest)


def get_annotators() -> list[str]:
    """List all annotator names."""
    if not ANNOTATIONS_DIR.exists():
        return []
    return sorted(d.name for d in ANNOTATIONS_DIR.iterdir()
                  if d.is_dir() and not d.name.startswith("."))


def get_stats() -> dict:
    """Get annotation statistics."""
    stats = {"total_tasks": 0, "annotators": {}}
    if not ANNOTATIONS_DIR.exists():
        return stats

    for ann_dir in ANNOTATIONS_DIR.iterdir():
        if not ann_dir.is_dir() or ann_dir.name.startswith("."):
            continue
        count = sum(1 for t in ann_dir.iterdir() if (t / "task.json").exists())
        stats["annotators"][ann_dir.name] = count
        stats["total_tasks"] += count

    return stats
