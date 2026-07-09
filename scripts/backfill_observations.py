"""Backfill observations (axtree, screenshot, raw html) for recorded trajectories.

Every action event in a trajectory must be followed by an observation event
carrying all three modalities:
    snapshot   — raw HTML of the page (inline string)
    axtree     — Playwright aria-snapshot text (YAML-ish)
    screenshot — relative path to screenshots/step_NNN.png inside the task dir

Backfill strategy, in order of fidelity:
  1. Observation exists with stored HTML -> re-render that exact HTML in a
     JS-disabled browser page (scripts must not mutate the recorded DOM) and
     derive whatever is missing (axtree / screenshot). method: "stored_html"
  2. Observation exists but has no HTML -> navigate a live instance of the app
     to the observation's URL with a fresh session and capture all three.
     Page state is base-DB state, not the annotator's session state, so these
     are flagged. method: "live_url"
  3. No observation at all after an action -> same as 2, using the action's
     URL; the new observation event is inserted right after the action.

Legacy recorder.js axtrees (JSON strings) are preserved under "axtree_json"
and replaced by a regenerated aria-snapshot so the field format is uniform.

Usage:
    python scripts/backfill_observations.py [--dry-run] [--only TASK_SUBSTR]
"""

import argparse
import json
import socket
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ANNOTATIONS_DIR = ROOT / "data" / "annotations"
VIEWPORT = {"width": 1280, "height": 800}


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _start_app(port):
    from app import create_app
    app = create_app()
    thread = threading.Thread(
        target=lambda: app.run(host="127.0.0.1", port=port, debug=False,
                               use_reloader=False, threaded=True),
        daemon=True,
    )
    thread.start()
    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError("app did not start")


def _is_yaml_axtree(ax):
    return bool(ax) and ax.lstrip().startswith("- ")


def _pair_events(events):
    """Yield (action_index, action_event, observation_event_or_None, insert_pos).

    The observation belonging to an action is the first observation event that
    appears after it and before the next action. insert_pos is where a new
    observation should be spliced in when none exists.
    """
    pairs = []
    action_no = -1
    i = 0
    while i < len(events):
        if events[i].get("type") == "action":
            action_no += 1
            obs = None
            j = i + 1
            while j < len(events) and events[j].get("type") != "action":
                if events[j].get("type") == "observation" and obs is None:
                    obs = events[j]
                j += 1
            pairs.append((action_no, events[i], obs, i + 1))
        i += 1
    return pairs


class Capturer:
    def __init__(self, base_url):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch()
        self.base_url = base_url
        # JS off: stored snapshots must render exactly as recorded
        self._static_ctx = self._browser.new_context(
            viewport=VIEWPORT, java_script_enabled=False)
        self._live_ctx = self._browser.new_context(viewport=VIEWPORT)
        self.static_page = self._static_ctx.new_page()
        self.live_page = self._live_ctx.new_page()
        # Relative asset URLs in stored snapshots resolve against the live app
        self.static_page.route(
            "**/*", lambda route: route.continue_())

    def close(self):
        self._browser.close()
        self._pw.stop()

    def render_stored_html(self, html, url):
        """Render stored HTML at its original URL (so relative assets load)."""
        page = self.static_page
        target = self.base_url + url if url and url.startswith("/") else None
        if target:
            handled = {"done": False}

            def fulfill(route):
                if not handled["done"] and route.request.resource_type == "document":
                    handled["done"] = True
                    route.fulfill(status=200, content_type="text/html", body=html)
                else:
                    route.continue_()

            page.unroute("**/*")
            page.route("**/*", fulfill)
            page.goto(target, wait_until="load", timeout=15000)
        else:
            page.set_content(html, wait_until="load", timeout=15000)
        return self._capture(page, html_already=html)

    def capture_live(self, url):
        page = self.live_page
        page.goto(self.base_url + url, wait_until="load", timeout=15000)
        page.wait_for_timeout(300)
        return self._capture(page)

    def _capture(self, page, html_already=None):
        html = html_already if html_already is not None else page.content()
        axtree = page.locator("body").aria_snapshot()
        shot = page.screenshot(full_page=False)
        return html, axtree, shot


def process_task(task_dir, cap, dry_run=False):
    tf = task_dir / "trajectory.json"
    if not tf.exists():
        return {"task": task_dir.name, "error": "no trajectory.json"}
    events = json.loads(tf.read_text())
    shots_dir = task_dir / "screenshots"
    stats = {"task": task_dir.name, "actions": 0, "rendered": 0,
             "created_obs": 0, "filled_axtree": 0, "filled_screenshot": 0,
             "filled_html": 0, "live_url_fallback": 0, "failures": []}
    inserts = []  # (position, event) spliced after the loop

    for action_no, action, obs, insert_pos in _pair_events(events):
        stats["actions"] += 1
        shot_name = f"step_{action_no:03d}.png"
        shot_path = shots_dir / shot_name

        if obs is None:
            obs = {
                "type": "observation",
                "url": action.get("url", ""),
                "title": "",
                "timestamp": action.get("timestamp", ""),
                "snapshot": "", "axtree": "", "screenshot": "",
                "backfilled": True, "backfill_method": "live_url",
            }
            inserts.append((insert_pos, obs))
            stats["created_obs"] += 1

        html = obs.get("snapshot") or ""
        ax = obs.get("axtree") or ""
        needs_ax = not _is_yaml_axtree(ax)
        needs_shot = not obs.get("screenshot") or not shot_path.exists()
        needs_html = not html

        if not (needs_ax or needs_shot or needs_html):
            continue
        if dry_run:
            stats["rendered"] += 1
            continue

        try:
            if html:
                new_html, new_ax, shot = cap.render_stored_html(html, obs.get("url", ""))
                method = "stored_html"
            else:
                url = obs.get("url") or action.get("url") or ""
                if not url:
                    raise ValueError("no URL to capture from")
                new_html, new_ax, shot = cap.capture_live(url)
                method = "live_url"
                stats["live_url_fallback"] += 1
        except Exception as e:  # noqa: BLE001 — record and move on
            stats["failures"].append({"action": action_no, "error": str(e)[:200]})
            continue

        if needs_html:
            obs["snapshot"] = new_html
            obs["backfilled"] = True
            obs["backfill_method"] = method
            stats["filled_html"] += 1
        if needs_ax:
            if ax and not _is_yaml_axtree(ax):
                obs["axtree_json"] = ax  # preserve legacy recorder.js format
            obs["axtree"] = new_ax
            stats["filled_axtree"] += 1
        if needs_shot:
            shots_dir.mkdir(exist_ok=True)
            shot_path.write_bytes(shot)
            obs["screenshot"] = f"screenshots/{shot_name}"
            stats["filled_screenshot"] += 1
        stats["rendered"] += 1

    if not dry_run and (inserts or stats["rendered"]):
        for pos, ev in sorted(inserts, key=lambda x: -x[0]):
            events.insert(pos, ev)
        tf.write_text(json.dumps(events, ensure_ascii=False))
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", default="", help="substring filter on task dir name")
    args = ap.parse_args()

    task_dirs = sorted(
        d for a in ANNOTATIONS_DIR.iterdir() if a.is_dir() and a.name != "reviews"
        for d in a.iterdir() if d.is_dir()
    )
    if args.only:
        task_dirs = [d for d in task_dirs if args.only in d.name]
    print(f"{len(task_dirs)} task(s) to process")

    cap = None
    if not args.dry_run:
        port = _free_port()
        print(f"starting app on :{port} ...")
        _start_app(port)
        cap = Capturer(f"http://127.0.0.1:{port}")

    all_stats = []
    try:
        for d in task_dirs:
            s = process_task(d, cap, dry_run=args.dry_run)
            all_stats.append(s)
            flag = " !" if s.get("failures") or s.get("error") else ""
            print(f"  {s['task']}: rendered={s.get('rendered', 0)} "
                  f"new_obs={s.get('created_obs', 0)} ax={s.get('filled_axtree', 0)} "
                  f"shots={s.get('filled_screenshot', 0)} html={s.get('filled_html', 0)}{flag}")
    finally:
        if cap:
            cap.close()

    report = ANNOTATIONS_DIR / "backfill_report.json"
    report.write_text(json.dumps(all_stats, indent=1))
    tot = lambda k: sum(s.get(k, 0) for s in all_stats if isinstance(s.get(k, 0), int))
    fails = sum(len(s.get("failures", [])) for s in all_stats)
    print(f"\nTotals: actions={tot('actions')} rendered={tot('rendered')} "
          f"new_obs={tot('created_obs')} axtrees={tot('filled_axtree')} "
          f"screenshots={tot('filled_screenshot')} html={tot('filled_html')} "
          f"failures={fails}")
    print(f"report: {report}")


if __name__ == "__main__":
    main()
