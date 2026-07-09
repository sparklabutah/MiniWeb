"""Replay recorded human trajectories to capture fully-faithful observations.

Unlike backfill_observations.py (which re-renders stored HTML or loads bare
URLs), this script re-executes each recorded action — clicks, typing, selects,
scrolls, drags — in a live browser session, so mid-task state such as text
entered into forms is present in the captured screenshot/axtree/html.

Replacement rules per observation, applied only when the replay step is
VERIFIED (post-action URL matches the recorded one):
  - observation was backfilled via live_url  -> replace html + axtree + screenshot
  - observation kept human-recorded HTML     -> replace axtree + screenshot only
    (recorded outerHTML lacks typed .value state, but it is primary data —
     never overwritten; the replayed screenshot/axtree carry the visible state)

Unverified (diverged) steps keep their existing artifacts and are logged.

Before capture, input/textarea/select state is mirrored into HTML attributes
so the replayed snapshot also shows typed values.

Usage:
    python scripts/replay_trajectories.py [--only TASK_SUBSTR] [--all-tasks]
"""

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.backfill_observations import (  # noqa: E402
    ANNOTATIONS_DIR, _free_port, _start_app, _pair_events)

VIEWPORT = {"width": 1280, "height": 720}  # matches original recordings

MIRROR_VALUES_JS = """
() => {
  document.querySelectorAll('input').forEach(el => {
    if (el.type === 'checkbox' || el.type === 'radio') {
      if (el.checked) el.setAttribute('checked', ''); else el.removeAttribute('checked');
    } else { el.setAttribute('value', el.value); }
  });
  document.querySelectorAll('textarea').forEach(el => { el.textContent = el.value; });
  document.querySelectorAll('select').forEach(el => {
    [...el.options].forEach(o => {
      if (o.selected) o.setAttribute('selected', ''); else o.removeAttribute('selected');
    });
  });
}
"""


def _path_of(url):
    """Normalize a recorded URL (may be absolute) to path?query."""
    if not url:
        return ""
    p = urlparse(url)
    return p.path + ("?" + p.query if p.query else "")


def _parse_target(target):
    """Parse recorder target strings like "link 'History' -> /sites/x"."""
    if not target:
        return None, None, None
    href = None
    m = re.search(r"->\s*(\S+)\s*$", target)
    if m:
        href = m.group(1)
    kind = target.split(" ", 1)[0].split("[", 1)[0]
    name = None
    m = re.search(r"'([^']*)'", target)
    if m:
        name = m.group(1)
    return kind, name, href


ROLE_MAP = {"link": "link", "button": "button", "radio": "radio",
            "checkbox": "checkbox", "tab": "tab", "option": "option"}


class Replayer:
    def __init__(self, browser, base_url):
        self.browser = browser
        self.base_url = base_url
        self.page = None

    def new_session(self):
        if self.page:
            self.page.context.close()
        ctx = self.browser.new_context(viewport=VIEWPORT)
        self.page = ctx.new_page()

    def goto(self, url):
        self.page.goto(self.base_url + _path_of(url), wait_until="load",
                       timeout=15000)
        self.page.wait_for_timeout(200)

    def _find_clickable(self, action):
        page = self.page
        kind, name, href = _parse_target(action.get("target", ""))
        if href:
            href_path = _path_of(href)
            loc = page.locator(f'a[href="{href_path}"], a[href="{href}"]')
            if loc.count():
                return loc.first
        if kind in ROLE_MAP and name:
            loc = page.get_by_role(ROLE_MAP[kind], name=name, exact=True)
            if loc.count():
                return loc.first
            loc = page.get_by_role(ROLE_MAP[kind], name=name)
            if loc.count():
                return loc.first
        sel = action.get("selector", "")
        if sel and sel not in ("a", "input", "button", "form", "body", "div", "span"):
            loc = page.locator(sel)
            if loc.count():
                return loc.first
        return None

    def do_action(self, action):
        page = self.page
        kind = action.get("action")
        sel = action.get("selector", "")

        if kind == "click":
            loc = self._find_clickable(action)
            if loc is not None:
                loc.click(timeout=5000)
            elif action.get("x") is not None:
                page.mouse.click(action["x"], action["y"])
            else:
                raise ValueError("no click strategy")
        elif kind in ("type", "change"):
            text = action.get("text", action.get("value", ""))
            loc = page.locator(sel).first if sel else None
            if loc is None or not loc.count():
                loc = self._find_clickable(action)
            if loc is None:
                raise ValueError("input not found")
            loc.fill(str(text), timeout=5000)
        elif kind == "select":
            loc = page.locator(sel).first
            try:
                loc.select_option(value=action.get("value"), timeout=5000)
            except Exception:  # noqa: BLE001 — fall back to visible label
                loc.select_option(label=action.get("option_text"), timeout=5000)
        elif kind == "check":
            loc = self._find_clickable(action)
            if loc is not None:
                loc.set_checked(bool(action.get("checked", True)), timeout=5000)
            elif action.get("x") is not None:
                page.mouse.click(action["x"], action["y"])
        elif kind == "keypress":
            key = action.get("key", "Enter")
            if sel:
                loc = page.locator(sel).first
                if loc.count():
                    loc.press(key, timeout=5000)
                    return
            page.keyboard.press(key)
        elif kind == "scroll":
            page.evaluate(f"window.scrollTo(0, {int(action.get('scroll_top', 0))})")
        elif kind == "drag":
            fx, fy = action.get("from_x"), action.get("from_y")
            tx, ty = action.get("to_x"), action.get("to_y")
            if None not in (fx, fy, tx, ty):
                page.mouse.move(fx, fy)
                page.mouse.down()
                page.mouse.move(tx, ty, steps=5)
                page.mouse.up()
        elif kind == "submit":
            # The triggering click was recorded separately and already replayed;
            # if the page hasn't navigated yet, submit the form directly.
            expected = _path_of(action.get("url", ""))
            if expected and _path_of(page.url) == expected:
                try:
                    page.locator("form").first.evaluate(
                        "f => f.requestSubmit ? f.requestSubmit() : f.submit()")
                except Exception:  # noqa: BLE001
                    pass
        elif kind == "tab_switch":
            pass  # single-page replay; recorded once, no state effect
        else:
            raise ValueError(f"unknown action kind {kind}")

        try:
            page.wait_for_load_state("load", timeout=5000)
        except Exception:  # noqa: BLE001 — non-navigating actions
            pass
        page.wait_for_timeout(250)

    def capture(self):
        page = self.page
        page.evaluate(MIRROR_VALUES_JS)
        html = page.content()
        axtree = page.locator("body").aria_snapshot()
        shot = page.screenshot(full_page=False)
        return html, axtree, shot


def process_task(task_dir, rp):
    tf = task_dir / "trajectory.json"
    events = json.loads(tf.read_text())
    shots_dir = task_dir / "screenshots"
    pairs = _pair_events(events)
    stats = {"task": task_dir.name, "actions": len(pairs), "replayed": 0,
             "verified": 0, "replaced_full": 0, "replaced_visual": 0,
             "diverged": [], "action_errors": []}

    rp.new_session()
    task_meta = json.loads((task_dir / "task.json").read_text()) \
        if (task_dir / "task.json").exists() else {}
    start = task_meta.get("starting_url") or (pairs and pairs[0][1].get("url")) or ""
    try:
        rp.goto(start)
    except Exception as e:  # noqa: BLE001
        stats["action_errors"].append({"action": -1, "error": f"start: {e}"[:200]})

    for action_no, action, obs, _pos in pairs:
        # realign if the browser drifted from where this action happened;
        # compare paths only — query strings legitimately evolve during replay
        # (a recorded pre-navigation URL lacks the query the replay already has)
        want = _path_of(action.get("url", ""))
        if want and _path_of(rp.page.url).split("?")[0] != want.split("?")[0]:
            try:
                rp.goto(want)
            except Exception as e:  # noqa: BLE001
                stats["action_errors"].append({"action": action_no,
                                               "error": f"realign: {e}"[:200]})
                continue
        try:
            rp.do_action(action)
            stats["replayed"] += 1
        except Exception as e:  # noqa: BLE001
            stats["action_errors"].append({"action": action_no,
                                           "error": str(e)[:200]})
            continue

        if obs is None:
            continue
        # verified iff we ended up where the recording says the next step began
        next_idx = action_no + 1
        expected = _path_of(obs.get("url", "")) or None
        if next_idx < len(pairs):
            expected_next = _path_of(pairs[next_idx][1].get("url", ""))
        else:
            expected_next = None
        here = _path_of(rp.page.url)
        verified = here in {p for p in (expected, expected_next) if p}
        # non-navigating action on same page counts as staying put
        if not verified and expected and here.split("?")[0] == expected.split("?")[0]:
            verified = True
        if not verified:
            stats["diverged"].append({"action": action_no, "at": here,
                                      "expected": expected_next or expected})
            continue
        stats["verified"] += 1

        try:
            html, axtree, shot = rp.capture()
        except Exception as e:  # noqa: BLE001
            stats["action_errors"].append({"action": action_no,
                                           "error": f"capture: {e}"[:200]})
            continue
        shot_name = f"step_{action_no:03d}.png"
        shots_dir.mkdir(exist_ok=True)
        was_live_url = obs.get("backfill_method") in ("live_url", "replay")
        (shots_dir / shot_name).write_bytes(shot)
        obs["screenshot"] = f"screenshots/{shot_name}"
        obs["axtree"] = axtree
        if was_live_url:
            obs["snapshot"] = html  # replaces base-state page with replayed state
            obs["backfill_method"] = "replay"
            stats["replaced_full"] += 1
        else:
            # human-recorded HTML stays; visuals now carry the typed state
            obs["replay_visuals"] = True
            stats["replaced_visual"] += 1
        obs["backfilled"] = True
        obs["replay_verified"] = True

    tf.write_text(json.dumps(events, ensure_ascii=False))
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--all-tasks", action="store_true",
                    help="replay every task, not just ones with backfilled obs")
    args = ap.parse_args()

    report_f = ANNOTATIONS_DIR / "backfill_report.json"
    touched = set()
    if report_f.exists():
        touched = {r["task"] for r in json.loads(report_f.read_text())
                   if r.get("rendered", 0) > 0}

    task_dirs = sorted(
        d for a in ANNOTATIONS_DIR.iterdir() if a.is_dir() and a.name != "reviews"
        for d in a.iterdir() if d.is_dir()
    )
    if not args.all_tasks:
        task_dirs = [d for d in task_dirs if d.name in touched]
    if args.only:
        task_dirs = [d for d in task_dirs if args.only in d.name]
    print(f"{len(task_dirs)} task(s) to replay")

    port = _free_port()
    print(f"starting app on :{port} ...")
    _start_app(port)

    from playwright.sync_api import sync_playwright
    all_stats = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        rp = Replayer(browser, f"http://127.0.0.1:{port}")
        for d in task_dirs:
            try:
                s = process_task(d, rp)
            except Exception as e:  # noqa: BLE001
                s = {"task": d.name, "error": str(e)[:200]}
            all_stats.append(s)
            print(f"  {s['task']}: replayed={s.get('replayed', 0)}/{s.get('actions', 0)} "
                  f"verified={s.get('verified', 0)} full={s.get('replaced_full', 0)} "
                  f"visual={s.get('replaced_visual', 0)} "
                  f"diverged={len(s.get('diverged', []))} "
                  f"errors={len(s.get('action_errors', []))}")
        browser.close()

    report = ANNOTATIONS_DIR / "replay_report.json"
    report.write_text(json.dumps(all_stats, indent=1))
    tot = lambda k: sum(s.get(k, 0) for s in all_stats if isinstance(s.get(k), int))
    print(f"\nTotals: actions={tot('actions')} replayed={tot('replayed')} "
          f"verified={tot('verified')} replaced_full={tot('replaced_full')} "
          f"replaced_visual={tot('replaced_visual')}")
    print(f"report: {report}")


if __name__ == "__main__":
    main()
