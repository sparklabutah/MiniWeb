"""Server-side observation completion.

At save time, every recorded observation carries a raw HTML snapshot (with
form state mirrored into attributes by recorder.js). This module derives the
other two observation modalities from it, using the same rendering approach
as scripts/backfill_observations.py so all data is format-consistent:

    axtree      — Playwright aria-snapshot text (YAML-ish)
    screenshot  — screenshots/step_NNN.png (NNN = action ordinal)

Runs in a daemon thread after save so the annotator's save request never
blocks on browser work; a module lock serializes runs. If Playwright is not
installed the completion is skipped with a warning — trajectories can be
completed later with scripts/backfill_observations.py.
"""

import json
import sys
import threading
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_VIEWPORT = {"width": 1280, "height": 720}

_lock = threading.Lock()


def complete_task_observations(task_dir, base_url):
    """Fill in axtree + screenshot for observations that have HTML snapshots."""
    from playwright.sync_api import sync_playwright
    from scripts.backfill_observations import _pair_events, _is_yaml_axtree

    task_dir = Path(task_dir)
    tf = task_dir / "trajectory.json"
    if not tf.exists():
        return {"error": "no trajectory.json"}
    events = json.loads(tf.read_text())
    shots_dir = task_dir / "screenshots"

    todo = []
    for action_no, _action, obs, _pos in _pair_events(events):
        if obs is None or not obs.get("snapshot"):
            continue
        needs_ax = not _is_yaml_axtree(obs.get("axtree") or "")
        needs_shot = not obs.get("screenshot") or \
            not (task_dir / obs["screenshot"]).exists()
        if needs_ax or needs_shot:
            todo.append((action_no, obs))
    if not todo:
        return {"completed": 0}

    done = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        # JS off: the snapshot is a post-interaction DOM; page scripts
        # re-running would re-initialize widgets and destroy recorded state.
        ctx = browser.new_context(viewport=DEFAULT_VIEWPORT,
                                  java_script_enabled=False)
        page = ctx.new_page()
        for action_no, obs in todo:
            try:
                vp = obs.get("viewport") or DEFAULT_VIEWPORT
                if page.viewport_size != vp:
                    page.set_viewport_size(vp)
                html = obs["snapshot"]
                url = obs.get("url") or "/"

                # single-arg handler: playwright passes extra args to handlers
                # with a larger signature, so bind html via closure instead
                def make_fulfill(body):
                    state = {"done": False}

                    def fulfill(route):
                        if not state["done"] and \
                                route.request.resource_type == "document":
                            state["done"] = True
                            route.fulfill(status=200,
                                          content_type="text/html", body=body)
                        else:
                            route.continue_()
                    return fulfill

                page.unroute("**/*")
                page.route("**/*", make_fulfill(html))
                page.goto(base_url + url, wait_until="load", timeout=15000)
                if obs.get("scroll_top"):
                    page.evaluate(f"window.scrollTo(0, {int(obs['scroll_top'])})")
                obs["axtree"] = page.locator("body").aria_snapshot()
                shots_dir.mkdir(exist_ok=True)
                shot_name = f"step_{action_no:03d}.png"
                (shots_dir / shot_name).write_bytes(page.screenshot())
                obs["screenshot"] = f"screenshots/{shot_name}"
                done += 1
            except Exception:  # noqa: BLE001 — one bad obs must not kill the rest
                traceback.print_exc()
        browser.close()

    tf.write_text(json.dumps(events, ensure_ascii=False))
    return {"completed": done, "of": len(todo)}


def schedule_completion(annotator, task_id, base_url):
    """Run observation completion for a saved task in a background thread."""
    from annotation.storage import _task_dir
    d = _task_dir(annotator, task_id)

    def run():
        with _lock:  # one browser at a time
            try:
                result = complete_task_observations(d, base_url)
                print(f"[observations] {task_id}: {result}")
            except ImportError:
                print(f"[observations] {task_id}: playwright not installed — "
                      "run scripts/backfill_observations.py later")
            except Exception:  # noqa: BLE001
                traceback.print_exc()

    threading.Thread(target=run, daemon=True).start()
