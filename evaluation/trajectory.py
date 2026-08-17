"""Trajectory collation helpers.

Two jobs, both pure collation of RECORDED evidence (no synthesis):

  * merge_server_log — union the server-side request log into a trajectory as
    `network` events. The server (`/_admin/log`, Flask after_request) is the
    authoritative witness for requests: client-side recorder.js structurally
    cannot see full-page navigations or native form POSTs (the page unloads
    mid-flight). Client-recorded fetch/XHR network events are KEPT — old server
    logs may lack request bodies that the client did capture — so the result is
    the union of both witnesses. Duplicates are harmless: request_made scans
    for existence.

  * extract_final_reasoning — the agent's final reasoning + answer from the
    harness's own record (history.json / result.json).

The old `synthesize_network_events` (inferring network events from submit /
observation actions) is GONE: a DOM submit event fires even when the submission
is blocked client-side, so synthesized POSTs asserted requests no witness ever
saw. Network events now come only from the server log or the in-page recorder.
"""
from __future__ import annotations

import json
import os


def _parse_ts(ts):
    import datetime as _dt
    try:
        return _dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def trajectory_window(traj: list):
    """(start, end) datetimes of the recording, from the trajectory's own
    event timestamps. (None, None) when the trajectory carries no timestamps."""
    times = [_parse_ts(e.get("timestamp")) for e in (traj or [])]
    times = [t for t in times if t]
    return (min(times), max(times)) if times else (None, None)


def filter_log_to_window(traj: list, server_log: list, margin_s: int = 90) -> list:
    """Drop server-log entries recorded OUTSIDE the trajectory's time window.

    The request log is per browser session, and an annotator's session sees far
    more than one recording — other tasks, free browsing, the annotate UI's own
    playback iframes. Anything outside [first, last trajectory timestamp]
    (± margin) is that other activity, not this recording's evidence.
    Entries without timestamps are kept (can't be placed, so don't judge them).
    """
    import datetime as _dt
    t0, t1 = trajectory_window(traj)
    if not t0:
        return list(server_log or [])
    lo, hi = t0 - _dt.timedelta(seconds=margin_s), t1 + _dt.timedelta(seconds=margin_s)
    out = []
    for e in server_log or []:
        ts = _parse_ts(e.get("timestamp"))
        if ts is None or lo <= ts <= hi:
            out.append(e)
    return out


def merge_server_log(traj: list, server_log) -> list:
    """Return traj + a `network` event per server-log entry (union of witnesses).

    `server_log` is a list of entries as written by the app's request logger
    ({method, path, query, status, body?}) or a path to such a JSON file.
    Entries are appended after the recorded events; existing (client-recorded)
    network events are kept. Log entries outside the trajectory's own time
    window are dropped (session logs accumulate unrelated activity).
    """
    if isinstance(server_log, (str, os.PathLike)):
        try:
            server_log = json.load(open(server_log))
        except (OSError, ValueError):
            server_log = []
    server_log = filter_log_to_window(traj, server_log)
    if not server_log:
        return list(traj or [])

    from urllib.parse import urlencode
    out = list(traj or [])
    for e in server_log:
        url = e.get("path", "") or ""
        query = e.get("query") or {}
        if query:
            url = url + "?" + urlencode(query)
        out.append({
            "type": "network",
            "method": e.get("method"),
            "url": url,
            "status": e.get("status"),
            "requestBody": e.get("body"),
            "_source": "server_log",
        })
    return out


def extract_final_reasoning(result_dir) -> str:
    """The agent's final reasoning + answer, from browser_use history + result.

    Reasoning lives in history.json (per-step model_output) and result.json
    (final_result), NOT in trajectory.json. Returns a single text blob to attach
    to the trajectory as a {type:"reasoning"} event for the reasoning check.
    """
    bits = []
    rp = os.path.join(str(result_dir), "result.json")
    if os.path.exists(rp):
        try:
            r = json.load(open(rp))
            if r.get("final_result"):
                bits.append(str(r["final_result"]))
        except (ValueError, OSError):
            pass
    hp = os.path.join(str(result_dir), "history.json")
    if os.path.exists(hp):
        try:
            hist = (json.load(open(hp)) or {}).get("history") or []
            for step in hist[-2:]:                       # last couple of steps
                mo = step.get("model_output") or {}
                for k in ("thinking", "memory", "evaluation_previous_goal", "next_goal"):
                    if mo.get(k):
                        bits.append(str(mo[k]))
        except (ValueError, OSError):
            pass
    return "\n".join(bits)
