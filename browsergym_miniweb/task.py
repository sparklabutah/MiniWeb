"""BrowserGym task wrapper for MiniWeb — PoC (browser-gym branch).

Bridges MiniWeb onto BrowserGym's AbstractBrowserTask:
  setup(page)                 -> reset session, navigate to start URL, return goal
  validate(page, chat)        -> fetch THIS session's trajectory, run verify_task
  teardown()                  -> noop (server is shared)

The grade reuses MiniWeb's existing verifier verbatim; the only new bit is fetching
the trajectory session-scoped THROUGH the browser (page.request carries the
_data_overlay_sid cookie), so many BrowserGym envs can share one MiniWeb server.
"""
import json
import os
import pathlib

from browsergym.core.task import AbstractBrowserTask

from evaluation.verifiers import verify_task
from evaluation.trajectory import synthesize_network_events

ROOT = pathlib.Path(__file__).resolve().parent.parent
ANN = ROOT / "data" / "annotations"


def _start_url(base, tdir, task):
    """Where the agent starts, mapped onto the local server.

    Multi-site tasks start on the PORTAL directory (`/`): crossing between sites
    is part of the task, so neither site's deep page is a fair start. Single-site
    tasks start where the reference recording began — the first OBSERVATION url
    (the page the human was actually on), then the first ACTION url. NEVER a
    network/XHR event — those are API calls (e.g. /api/prices/live?symbols=SPY)
    that render as raw JSON/CSV, not the page.
    """
    if len(task.get("sites") or []) > 1:
        return base + "/"
    tj = tdir / "trajectory.json"
    if tj.exists():
        try:
            traj = json.loads(tj.read_text())
            for kind in ("observation", "action"):
                for e in traj:
                    u = e.get("url")
                    if e.get("type") == kind and u and "/sites/" in u:
                        return base + u[u.find("/sites/"):]
        except (json.JSONDecodeError, OSError):
            pass
    sites = task.get("sites") or []
    sid = (sites[0].get("id") if isinstance(sites[0], dict) else sites[0]) if sites else ""
    return f"{base}/sites/{sid}/"


def _assemble(recorded, log, beacons):
    """Same assembly as run_agent_verify.build_trajectory, but from session-scoped feeds."""
    traj = list(recorded)
    if not any(e.get("type") == "action" for e in traj):
        for b in beacons:
            traj.append({"type": "action", **b})
    if not any(e.get("type") == "network" for e in traj):
        for e in log:
            traj.append({"type": "network", "method": e.get("method"),
                         "url": e.get("path"), "status": e.get("status"),
                         "requestBody": e.get("body")})
    return synthesize_network_events(traj)


def fetch_session_trajectory(page, base):
    """Pull THIS browser session's trajectory (the cookie selects the session)."""
    def entries(path):
        try:
            return page.request.get(base + path).json().get("entries", []) or []
        except Exception:
            return []
    return _assemble(entries("/_admin/record"), entries("/_admin/log"),
                     entries("/_admin/beacon"))


def _site_brand(sid):
    """The site's brand/display name from site.json (falls back to the id)."""
    try:
        return json.loads((pathlib.Path(ROOT) / "sites" / sid / "site.json").read_text()).get("name", sid)
    except Exception:
        return sid


def _nav_preamble(task):
    """Orient the agent: it operates MiniWeb through a browser-style portal and
    navigates with the portal's OWN controls (search bar, site tiles, tab bar) —
    there is no goto tool. Just names the site(s) this task uses."""
    lines = []
    for s in (task.get("sites") or []):
        sid = s.get("id") if isinstance(s, dict) else s
        if sid:
            lines.append(f"  - {_site_brand(sid)}")
    sites_block = (" This task uses these site(s):\n" + "\n".join(lines) + "\n\n"
                   if lines else " ")
    return ("You are operating MiniWeb, a sandbox that hosts many websites inside a "
            "browser-style portal. You start on the portal home; open and switch "
            "between sites using the portal itself — its search bar, the site tiles, "
            "and the tab bar." + sites_block +
            "When you have completed the task and know the answer, call "
            "report_answer(<answer>) to submit it — this ends the task. Use "
            "send_msg_to_user only for progress notes, not for the final answer.\n\n"
            "Task: ")


from browsergym_miniweb.actions import FINAL_ANSWER_PREFIX


def _agent_texts(chat_messages):
    """The messages the AGENT produced this episode. BrowserGym seeds a stock
    assistant greeting ("Hi! I am your UI assistant...") BEFORE the goal, so we take
    only assistant messages that come AFTER the goal (the first user-role message)."""
    msgs = list(chat_messages or [])
    start = 0
    for i, m in enumerate(msgs):
        if isinstance(m, dict) and m.get("role") == "user":
            start = i + 1
            break
    out = []
    for m in msgs[start:]:
        if isinstance(m, dict):
            if m.get("role") in (None, "assistant", "infeasible") and m.get("message"):
                out.append(str(m["message"]))
        elif isinstance(m, str) and m:
            out.append(m)
    return out


def _final_answer(chat_messages):
    """The agent's explicitly-reported final answer via the report_answer tool (last
    marked message, marker stripped). '' if the agent never used the tool."""
    for t in reversed(_agent_texts(chat_messages)):
        if FINAL_ANSWER_PREFIX in t:
            return t.split(FINAL_ANSWER_PREFIX, 1)[1].strip()
    return ""


def _collect_answer(chat_messages):
    """Fallback for agents that don't use report_answer: everything the agent said to
    the human, joined (so a multi-part answer split across messages is graded whole)."""
    return "\n".join(_agent_texts(chat_messages)).strip()


class MiniWebTask(AbstractBrowserTask):
    def __init__(self, seed: int = 0, task_id: str = None, base_url: str = None):
        super().__init__(seed)
        self.task_id = task_id
        self.base = (base_url or os.environ.get("MINIWEB_URL", "http://localhost:8099")).rstrip("/")
        self.tdir = ANN / task_id
        self.task = json.loads((self.tdir / "task.json").read_text())
        self.verifier = json.loads((self.tdir / "verifier.json").read_text())
        self.expected = (self.task.get("expected_answer") or "").strip()

    def setup(self, page):
        # session-scoped reset (safe on a shared server), then land on the start page.
        # authenticate_by_form tasks must start LOGGED OUT: ?no_autologin=1 sets the
        # session flag the auto-login guard honours (per-session equivalent of the
        # native runner's MINIWEB_NO_AUTOLOGIN server env).
        reset = f"{self.base}/_reset_data"
        if "authenticate_by_form" in (self.verifier.get("macros") or {}):
            reset += "?no_autologin=1"
        try:
            page.goto(reset)
        except Exception:
            pass
        page.goto(_start_url(self.base, self.tdir, self.task))
        goal = _nav_preamble(self.task) + self.task["instruction"]
        return goal, {"task_id": self.task_id}

    def validate(self, page, chat_messages):
        # The agent's answer: its explicit report_answer value if used, else its
        # messages to the human (BrowserGym's seed greeting is excluded).
        answer = _final_answer(chat_messages) or _collect_answer(chat_messages)
        traj = fetch_session_trajectory(page, self.base)
        report = verify_task(self.verifier, traj, answer,
                             question=self.task.get("instruction", ""))
        passed = report["passed"]
        # Terminate only when the task is solved; otherwise let the agent run to the
        # step limit (BrowserGym truncates). No clever early-stop heuristics.
        reward = 1.0 if passed else 0.0
        return reward, passed, "", {"task_id": self.task_id,
                                    "by_macro": report["by_macro"]}

    def teardown(self):
        pass
