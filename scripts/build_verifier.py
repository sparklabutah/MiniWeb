"""Reconstructed archetype_v2 verifier BUILDER for MiniWeb.

Composes the surviving pieces into the historical pipeline:

    stage 1  assemble   — annotation.macro_templates.build_task_draft(macros)
                          selects each macro's authored skeleton (archetype shape,
                          {open:true} placeholders), canonicalised + de-duped.
    stage 2  fill        — ground the OPEN params per-occurrence from the task's
                          RECORDED reference trajectory (trajectory.json) + answer.
                          Deterministic (the historical "build_verifiers.py
                          (per-occurrence, deterministic grounding)" floor); the
                          194 tasks originally filled by an LLM ("claude-judgement
                          -fill") cannot be reproduced value-for-value.
    stage 3  restructure — evaluation.verifier_archetypes.restructure(tree, macro):
                          backend-gate-hard + advisory-FE, stamps archetype_v2.
    stage 4  flags       — archetype_v2 (always); report_info_fuzzy (report_
                          information present); query_gated (a filter/search query
                          gates the outcome, proxied by a recorded query GET).

Public API:  build_verifier(task_dict, trajectory=None) -> verifier.json dict.

The gate is grounded FROM the reference trajectory's own events, so the generated
verifier passes the task-acceptance gate (verify_task against that same walk) by
construction.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from annotation.macro_templates import (
    build_task_draft, collect_open_slots, inject_qa_leaf, _canon,
)
from evaluation.verifier_archetypes import (
    restructure, id_agnostic_url,
    FORM_MACROS, FILTER_MACROS, SEARCH_MACROS, TOGGLE_MACROS,
    CONTENT_BACKEND,
)

_MUTATION = {"POST", "PUT", "PATCH", "DELETE"}
# macros whose backend gate is a mutation request (server write)
_MUTATION_MACROS = FORM_MACROS | TOGGLE_MACROS | CONTENT_BACKEND
# macros whose gate is a read/query GET (filter/search/sort)
_QUERY_MACROS = FILTER_MACROS | SEARCH_MACROS | {"sort_by_form"}
# filter/search family that can make grading query-gated
_FILTERISH = FILTER_MACROS | SEARCH_MACROS | {"sort_by_form"}


# ── trajectory access ──────────────────────────────────────────────────────

def _events(trajectory):
    return trajectory or []


def _network(traj):
    return [e for e in _events(traj) if e.get("type") == "network"]


def _observations(traj):
    return [e for e in _events(traj) if e.get("type") == "observation"]


def _url_path(url):
    """Path portion of a URL (drops the query string)."""
    return (url or "").split("?")[0]


# ── grounding: fill one macro tree's OPEN params from the trajectory ─────────

def _ground_request(macro, req_pool, site):
    """Return (method, url) for this macro's backend request gate, grounded on a
    real recorded request so the gate matches the reference walk. Pops from the
    per-task request pool so multiple request-needing macros spread over the
    recorded requests; falls back to the site base path."""
    want_mut = macro in _MUTATION_MACROS
    want_get = macro in _QUERY_MACROS

    def take(pred):
        for i, n in enumerate(req_pool):
            if pred(n):
                return req_pool.pop(i)
        return None

    picked = None
    if want_mut:
        picked = take(lambda n: (n.get("method") or "").upper() in _MUTATION)
    elif want_get:
        picked = take(lambda n: (n.get("method") or "").upper() == "GET"
                      and "?" in (n.get("url") or ""))
    if picked is None:                      # any remaining request
        picked = req_pool.pop(0) if req_pool else None

    if picked is None:                      # nothing recorded — site-base fallback
        return None, (f"/sites/{site}" if site else None)
    method = (picked.get("method") or "").upper() or None
    # query macros gate on the endpoint path (query params are volatile); mutation
    # macros keep the id-agnostic full path.
    url = id_agnostic_url(_url_path(picked.get("url") or ""))
    return method, url


def _ground_page(traj, site):
    """A concrete visited URL for a page_visited gate (navigate_by_route): the last
    observation URL that isn't the bare site root, else the site base."""
    obs_urls = [o.get("url") for o in _observations(traj) if o.get("url")]
    root = f"/sites/{site}/" if site else None
    for u in reversed(obs_urls):
        if u and u.rstrip("/") not in ("", root and root.rstrip("/")):
            return u
    return obs_urls[-1] if obs_urls else (f"/sites/{site}" if site else None)


def _expected_for(macro, task):
    """The expected answer/reasoning value for a QA-style slot."""
    qa = task.get("qa_answers") or {}
    if isinstance(qa, dict) and qa.get(macro):
        v = qa[macro]
        return v if isinstance(v, str) else json.dumps(v)
    return task.get("expected_answer") or ""


def _fill_tree(macro, tree, task, req_pool, traj, site):
    """Deep-copy `tree` and set its OPEN params in place. answer_grounded url/text
    and the FE affordance target/value are deliberately LEFT open (restructure drops
    a both-open answer_grounded, and rebuilds the affordance group all-open)."""
    t = copy.deepcopy(tree)
    slots = collect_open_slots(t)
    req_filled = False
    for s in slots:
        node = t
        for i in s["path"]:
            node = node["checks"][i]
        ctype, param = s["check_type"], s["param"]
        if ctype == "request_made" and param in ("method", "url"):
            if not req_filled:
                m, u = _ground_request(macro, req_pool, site)
                node["_m"], node["_u"] = m, u          # stash; assign below
                req_filled = True
            if param == "method" and node.get("_m"):
                node["method"] = node["_m"]
            elif param == "method":
                node.pop("method", None)               # unknown method → not asserted
            if param == "url" and node.get("_u"):
                node["url"] = node["_u"]
            elif param == "url":
                node.pop("url", None)
        elif ctype == "request_made" and param in ("status", "body_fields"):
            node.pop(param, None)                       # relax: never pin these
        elif ctype == "page_visited" and param == "url":
            u = _ground_page(traj, site)
            if u:
                node["url"] = u
            else:
                node.pop("url", None)
        elif ctype in ("qa_answer", "reasoning_contains", "answer_matches") and param == "expected":
            node["expected"] = _expected_for(macro, task)
        # answer_grounded (url/text) and action_included (target/value): leave OPEN
    # strip the temporary stashes
    for s in slots:
        node = t
        for i in s["path"]:
            node = node["checks"][i]
        node.pop("_m", None); node.pop("_u", None)
    return t


# ── query-gated proxy ───────────────────────────────────────────────────────

def _strip_meta(node):
    """Drop authoring artifacts (_source/_suggested) the templates carry but the
    corrected verifiers don't."""
    if isinstance(node, dict):
        return {k: _strip_meta(v) for k, v in node.items()
                if k not in ("_source", "_suggested")}
    if isinstance(node, list):
        return [_strip_meta(c) for c in node]
    return node


def _is_query_gated(canon_macros, traj):
    """The historical queryfix pass marked a task query_gated when a filter/search
    QUERY gates the outcome. Deterministic proxy: the task uses a filter/search
    macro AND the reference walk actually issued a query GET (?...) — i.e. the
    query was materially applied. (Only ~63/108 filterish tasks were marked in the
    ground truth; that final call was a human/LLM judgement this proxy approximates.)"""
    if not (set(canon_macros) & _FILTERISH):
        return False
    return any((n.get("method") or "").upper() == "GET" and "?" in (n.get("url") or "")
               for n in _network(traj))


# ── entry point ─────────────────────────────────────────────────────────────

def build_verifier(task: dict, trajectory: list | None = None) -> dict:
    """Build an archetype_v2 verifier dict for a task. `trajectory` defaults to the
    task's recorded reference walk (task['_trajectory'] or its trajectory.json)."""
    macros_raw = task.get("macros") or []
    canon_macros = list(dict.fromkeys(_canon(m) for m in macros_raw))
    site = task.get("site") or (task.get("sites") or [None])[0]
    traj = trajectory if trajectory is not None else (task.get("_trajectory") or [])

    draft = build_task_draft(macros_raw)
    templates, missing = draft["templates"], draft["missing"]

    # per-task request pool, consumed as macros claim gates (trajectory order)
    req_pool = list(_network(traj))

    macros_spec = {}
    for macro, tree in templates.items():
        filled = _fill_tree(macro, tree, task, req_pool, traj, site)
        macros_spec[macro] = filled

    # set qa leaf/alternatives from the macro graph BEFORE restructure
    inject_qa_leaf(macros_spec, task)

    # stage 3: archetype restructure per macro
    macros_spec = {m: _strip_meta(restructure(tree, m)) for m, tree in macros_spec.items()}

    out = {
        "task_id": task.get("task_id", ""),
        "model": None,
        "built_by": "scripts/build_verifier.py (reconstructed, deterministic grounding)",
        "macros": macros_spec,
        "archetype_v2": True,
    }
    if "report_information" in canon_macros:
        out["report_info_fuzzy"] = True
    if _is_query_gated(canon_macros, traj):
        out["query_gated"] = True
    if missing:
        out["_missing_templates"] = missing
    return out


# ── convenience: load a task dir and build ──────────────────────────────────

def build_from_dir(task_dir) -> dict:
    task_dir = Path(task_dir)
    task = json.loads((task_dir / "task.json").read_text())
    tj = task_dir / "trajectory.json"
    traj = json.loads(tj.read_text()) if tj.exists() else []
    return build_verifier(task, traj)


if __name__ == "__main__":
    import sys
    print(json.dumps(build_from_dir(sys.argv[1]), ensure_ascii=False, indent=1))
