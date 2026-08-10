"""Server-side observation completion — runs on every task save.

There is exactly ONE reconstruction pipeline, in scripts/process_annotations.py:

    repair form state  ->  derive axtree + full-page screenshot (dropdowns drawn)

This module is the *trigger* for it at save time; scripts/process_annotations.py
is the same pipeline as a batch job (for servers without a browser, or to catch
up on tasks recorded elsewhere). Keeping one implementation is deliberate: the
two used to diverge, and half the dataset ended up with viewport-cropped
screenshots and empty dropdowns while the other half didn't.

Runs in a daemon thread so the annotator's save never blocks on browser work.
If Playwright (or its Chromium binary) is missing, completion is skipped with a
warning — run scripts/process_annotations.py later to catch up.
"""

import sys
import threading
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_lock = threading.Lock()   # one browser at a time


def complete_task_observations(task_dir, base_url):
    """Repair + reconstruct observations for one task. Returns a stats dict."""
    from annotation.process_annotations import process_task
    return process_task(Path(task_dir), base_url)


def schedule_completion(annotator, task_id, base_url):
    """Run observation completion for a saved task in a background thread."""
    from annotation.storage import _task_dir
    d = _task_dir(annotator, task_id)

    def run():
        with _lock:
            try:
                result = complete_task_observations(d, base_url)
                print(f"[observations] {task_id}: {result}")
            except ImportError as exc:
                print(f"[observations] {task_id}: skipped ({exc}) — "
                      f"run scripts/process_annotations.py to catch up")
            except Exception:  # noqa: BLE001
                traceback.print_exc()

    threading.Thread(target=run, daemon=True).start()
