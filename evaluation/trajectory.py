"""Trajectory normalization — reconstruct network events the recorder missed.

recorder.js only logs a `network` event for fetch/XMLHttpRequest. Two gaps
follow:

  * full-page GET navigations (page loads, ?query= filters) are never network
    events — they surface only as `navigate` actions / observation URLs;
  * the verification-walk collector used to drop `network` messages entirely,
    so walks recorded before that fix have no network events at all.

But the information isn't lost: a `submit` action carries {url, method,
formData}, and every page an agent GETs shows up as an observation URL (stored
`navigate` actions are filtered out during processing, so observations are the
reliable GET source). This module derives the corresponding `network` events, so
`request_made` checks work uniformly. Synthesized events are flagged
`_synthesized` for provenance and are only added when no real network event
already covers them (idempotent).
"""
from __future__ import annotations

from urllib.parse import urlsplit


def _path(url: str) -> str:
    """Strip scheme+host, keep path (+query) — matches how real network events
    and page URLs are stored (e.g. '/sites/books-comics/book/1/rate')."""
    if not url:
        return ""
    s = urlsplit(str(url))
    if s.scheme or s.netloc:
        return s.path + (("?" + s.query) if s.query else "")
    return str(url)


def _path_only(url: str) -> str:
    return _path(url).split("?", 1)[0]


def extract_final_reasoning(result_dir) -> str:
    """The agent's final reasoning + answer, from browser_use history + result.

    Reasoning lives in history.json (per-step model_output) and result.json
    (final_result), NOT in trajectory.json. Returns a single text blob to attach
    to the trajectory as a {type:"reasoning"} event for the reasoning check.
    """
    import json
    import os
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


def synthesize_network_events(traj: list, include_get: bool = True) -> list:
    """Return a copy of `traj` with `network` events reconstructed from `submit`
    (POST) and, if include_get, `navigate` (GET) actions. Idempotent."""
    if not traj:
        return traj

    # what real network events already cover, keyed by (method, path-no-query)
    covered = set()
    for e in traj:
        if e.get("type") == "network":
            covered.add(((e.get("method") or "GET").upper(), _path_only(e.get("url"))))

    out = []
    events = list(traj)
    for i, e in enumerate(events):
        out.append(e)
        t = e.get("type")

        if t == "action" and e.get("action") == "submit" and e.get("url"):
            method = (e.get("method") or "POST").upper()
            path = _path(e.get("url"))
            key = (method, _path_only(path))
            if key in covered:
                continue
            covered.add(key)
            # next observation on a different page => redirect-after-POST (302)
            status = 200
            for nxt in events[i + 1:]:
                if nxt.get("type") == "observation":
                    if _path_only(nxt.get("url")) != _path_only(e.get("url")):
                        status = 302
                    break
            out.append({
                "type": "network", "method": method, "url": path,
                "status": status, "requestBody": e.get("formData"),
                "_synthesized": "submit",
            })

        elif include_get and t == "observation" and e.get("url"):
            # each distinct page the agent loaded is a GET to that URL
            path = _path(e.get("url"))
            key = ("GET", _path_only(path))
            if key in covered:
                continue
            covered.add(key)
            out.append({
                "type": "network", "method": "GET", "url": path,
                "status": 200, "_synthesized": "observation",
            })

    return out
