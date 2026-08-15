"""Per-macro verifier archetypes.

The design (settled 2026-08-10): a macro verifier has two parts —

  * BACKEND GATE (hard): the request the macro's action produces reached the
    server carrying the values the TASK dictated. This decides pass/fail.
  * FRONTEND (advisory): the right affordance was used (form typed + submitted,
    slider dragged, dropdown selected …). Reported, but does NOT gate — a valid
    alternate UI path must not fail a task whose outcome is correct.

Client-only macros (compute-on-page, canvas draw, media scrub, pan/zoom) have no
backend, so their GATE is the on-page OUTCOME (the computed value / a save / the
reached state) and the affordance is still advisory.

Macros map to archetypes by their registry group. `restructure(tree, macro)`
rebuilds an existing (already value-grounded) macro tree into this shape; it does
not invent values — the task-relevant backend fields come from the value-grounded
tree or, better, from the LLM extraction pass (see build_v2_verifiers).
"""
from __future__ import annotations
import re

# registry group  ->  archetype
FORM_MACROS = {  # a form is filled and submitted; the mutation is the gate
    "create_by_form", "edit_by_form", "compare_by_form", "pay_by_form",
    "checkout_by_form", "book_by_form", "cancel_by_form", "configure_by_form",
    "authenticate_by_form", "share_by_form", "sort_by_form", "feedback_by_star",
    "feedback_by_text", "get_nav_route", "save_by_form", "sign_by_text",
}
FILTER_MACROS = {"filter_by_dropdown", "filter_by_date_range", "filter_by_options"}
TOGGLE_MACROS = {"toggle_relationship", "feedback_by_react"}
SEARCH_MACROS = {"search"}
# content actions that hit the server
CONTENT_BACKEND = {"message_from_free_text", "upload_file", "join_meeting", "export",
                   "delete_from_table", "translate_by_query", "write_executable_program",
                   "edit_by_cell"}   # gate = the cell save/autosave call carrying the values
# client-only: no reliable server mutation; outcome/affordance is the check
CLIENT_ONLY = {"compute_by_tool", "edit_by_image", "sign_by_freeformdrawing",
               "reposition_by_drag", "edit_by_ranking", "copy_content",
               "play_by_playback", "search_by_pan_zoom", "search_by_playback",
               "filter_by_slider"}
REPORT_MACROS = {"report_information"}
# navigate_by_route IS graded (its page_visited check confirms the agent reached
# the right page) — we just keep its tree as-is rather than restructure it.
SKIP_MACROS = {"navigate_by_route"}


# ── tree walking ──────────────────────────────────────────────────────────────

def _leaves(node, acc):
    if not isinstance(node, dict):
        return
    if node.get("op") in ("AND", "OR"):
        for c in node.get("checks", []):
            _leaves(c, acc)
    else:
        acc.append(node)


def _by_type(tree):
    ls = []
    _leaves(tree, ls)
    out = {}
    for n in ls:
        out.setdefault(n.get("type"), []).append(n)
    return out


# ── url: make volatile resource ids non-gating ─────────────────────────────────

def id_agnostic_url(url: str) -> str:
    """A '/note/2/save' style path where a numeric segment is a session-specific
    resource id → regex that pins the endpoint but not the id. Left literal when
    there is no id segment (then RequestMade does a plain substring match)."""
    if not url or url.startswith("re:"):
        return url
    path = url.split("?")[0]
    segs = path.split("/")
    if not any(s.isdigit() for s in segs):
        return path
    pat = "/".join(r"\d+" if s.isdigit() else re.escape(s) for s in segs)
    return "re:" + pat


# ── frontend affordance sets (advisory) ────────────────────────────────────────

AFFORDANCE = {
    "form": ["type", "click", "select", "change", "check", "submit", "keypress"],
    "slider": ["drag", "change", "click"],
    "dropdown": ["select", "change", "click"],
    "options": ["check", "click", "change"],
    "toggle": ["click", "check", "change", "submit"],
    "search": ["type", "click", "keypress", "submit"],
    "canvas": ["drag", "click"],
    "media": ["click", "drag", "change"],
    "map": ["drag", "scroll", "click"],
    "grid": ["click", "type", "change", "keypress", "press"],  # data-grid cell editing
    "type": ["type", "keypress", "click", "submit"],
}


def _affordance_group(kinds, existing_targets=None, label="affordance used (advisory)"):
    """OR of action_included over the affordance verbs, target/value OPEN — modality
    only, advisory. If we know the relevant control targets, keep them but still open."""
    checks = [{"type": "action_included", "action": k,
               "target": {"open": True}, "value": {"open": True}} for k in kinds]
    return {"op": "OR", "advisory": True, "label": label, "checks": checks}


def _affordance_for(macro):
    if macro in FORM_MACROS or macro in {"filter_by_date_range"}:
        return AFFORDANCE["form"]
    if macro == "filter_by_slider":
        return AFFORDANCE["slider"]
    if macro == "filter_by_dropdown":
        return AFFORDANCE["dropdown"]
    if macro == "filter_by_options":
        return AFFORDANCE["options"]
    if macro in TOGGLE_MACROS:
        return AFFORDANCE["toggle"]
    if macro in SEARCH_MACROS:
        return AFFORDANCE["search"]
    if macro == "edit_by_cell":
        return AFFORDANCE["grid"]
    if macro in {"edit_by_image", "sign_by_freeformdrawing", "reposition_by_drag"}:
        return AFFORDANCE["canvas"]
    if macro in {"play_by_playback", "search_by_playback"}:
        return AFFORDANCE["media"]
    if macro == "search_by_pan_zoom":
        return AFFORDANCE["map"]
    return AFFORDANCE["type"]


# ── restructure an existing (value-grounded) tree into archetype form ──────────

def restructure(tree, macro):
    """Rebuild a macro's existing check tree into: AND(backend gate, advisory FE
    [, outcome]).  Reuses the values already grounded in `tree`; the LLM-extraction
    build supersedes the backend gate when it has better task-relevant fields.
    """
    if macro in SKIP_MACROS:
        return tree  # not graded; leave as-is
    bt = _by_type(tree)
    reqs = bt.get("request_made", [])
    qas = bt.get("qa_answer", [])
    gates = []

    # backend gate(s): keep grounded method + id-agnostic url + body_fields;
    # drop pinned status (agent may 200 vs 302) — engine leaves it open when absent
    for r in reqs:
        g = {"type": "request_made", "label": r.get("label", "backend call (gate)")}
        if r.get("method") and not _open(r.get("method")):
            g["method"] = r["method"]
        u = r.get("url")
        if u and not _open(u):
            g["url"] = id_agnostic_url(u if not str(u).startswith("re:") else u)
        if r.get("body_fields") and not _open(r.get("body_fields")):
            g["body_fields"] = r["body_fields"]
        gates.append(g)

    # report / compute: the answer is (part of) the gate
    for q in qas:
        gates.append({**q, "mode": q.get("mode", "contains")})

    # grounding: the answer was present where the agent was looking — keep it,
    # dropping it silently (as this pass used to) removes the anti-guessing gate
    for g in bt.get("answer_grounded", []):
        if not (_open(g.get("url")) and _open(g.get("text"))):
            gates.append(g)

    # filters may be applied server-side (a GET param), folded into a search/submit
    # request, OR purely client-side (the control operated). Accept any: the gate
    # becomes OR(backend request, the grounded control action).
    if macro in FILTER_MACROS and gates:
        anchored = _grounded_actions(tree)
        if anchored:
            gates = [{"op": "OR", "label": f"{macro}: filter applied (request or control)",
                      "checks": gates + anchored}]

    # frontend affordance, advisory
    fe = _affordance_group(_affordance_for(macro))

    # client-only with no backend & no answer: the affordance IS the gate. The
    # existing tree is already relevance-anchored (control label / entered value)
    # from the earlier tightening pass — keep it verbatim so its OR/AND structure
    # (and gold pass) is preserved. Only when the tree has nothing concrete do we
    # fall back to a bare affordance gate.
    if not gates:
        if _grounded_actions(tree):
            return tree
        fe_gate = dict(fe); fe_gate["advisory"] = False
        return fe_gate

    return {"op": "AND", "label": f"{macro} (backend gate + advisory FE)",
            "checks": gates + [fe]}


def _open(v):
    return isinstance(v, dict) and v.get("open") is True


def _grounded_actions(tree):
    """action_included leaves that carry a concrete target/value (relevance-anchored
    from the earlier tightening pass) — kept as gates for client-only macros."""
    ls = []
    _leaves(tree, ls)
    out = []
    for n in ls:
        if n.get("type") != "action_included":
            continue
        if not _open(n.get("target")) or not _open(n.get("value")):
            out.append(n)
    return out
