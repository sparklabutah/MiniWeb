"""Universal per-task verifier scaffolding + the task-graph/trajectory helpers
the Verifier Builder and graders share.

Every macro is verified through the same three canonical components — no
per-macro authoring step exists:

  * page_visited    — the agent was on the relevant page
  * action_included — the FE affordance used (advisory by default: a valid
                      alternate UI path must not fail a correct outcome)
  * request_made    — the backend gate (what the annotator usually pins)

A fresh scaffold ships every param OPEN ({open: true} = not asserted, passes
on anything), so it is a DRAFT, not a verifier: the annotator pins values and
flips advisory flags per task in the Verifier Builder (/annotate/verify).
`report_information` (the terminal report macro) additionally scaffolds a
qa_answer check, pre-seeded from the task's expected answer when available.
"""
from __future__ import annotations

import json


def _canon(m):
    """Canonical macro name — merges retired/consolidated aliases. Task files
    keep original names; everything downstream reads through this."""
    from annotation.app import _canon as canon
    return canon(m)


# ---------------------------------------------------------------------------
# scaffolding — the same 3-component tree for every macro
# ---------------------------------------------------------------------------

def _task_expected(task, macro):
    """The task's expected answer for this macro: its per-macro qa_answer if
    one was recorded, else the task-level expected_answer."""
    qa = (task or {}).get("qa_answers") or {}
    want = qa.get(macro) if isinstance(qa, dict) else None
    want = want or (task or {}).get("expected_answer") or ""
    if not isinstance(want, str):
        want = json.dumps(want)
    return want


def default_scaffold(macro: str, task: dict | None = None) -> dict:
    """The universal verifier draft for one macro: AND of the 3 canonical
    components, all params open. Mirrors the builder's own tvCompLeaf()
    defaults so a server scaffold and a UI-toggled component are identical."""
    checks = [
        {"type": "page_visited", "label": "page visited", "url": {"open": True}},
        {"type": "action_included", "label": "FE affordance", "advisory": True,
         "action": {"open": True}, "target": {"open": True}, "value": {"open": True}},
        {"type": "request_made", "label": "backend gate",
         "method": {"open": True}, "url": {"open": True}},
    ]
    if macro == "report_information":
        expected = _task_expected(task, macro)
        checks.append({"type": "qa_answer", "label": "answer matches",
                       "expected": expected if expected else {"open": True},
                       "mode": "contains"})
    return {"op": "AND", "checks": checks}


def scaffold_task(macros: list, task: dict | None = None) -> dict:
    """Assemble the per-task verifier draft: one universal scaffold per
    (canonical, de-duplicated) macro.

    Returns {macros: {macro: tree}, slots: [{id, macro, path, param,
    check_type, fixed, label, group_labels}]} — every macro scaffolds, so
    unlike the retired template library there is no "missing" set.
    """
    trees, slots = {}, []
    for macro in dict.fromkeys(_canon(m) for m in (macros or [])):
        tree = default_scaffold(macro, task)
        trees[macro] = tree
        for i, s in enumerate(collect_open_slots(tree)):
            slots.append({"id": f"{macro}::{i}", "macro": macro, **s})
    return {"macros": trees, "slots": slots}


# ---------------------------------------------------------------------------
# open-slot mechanics — walk a check tree, list its OPEN params, fill them
# ---------------------------------------------------------------------------

def _walk_leaves(node, path, group_labels):
    """Yield (path, leaf_dict, ancestor_group_labels) for every leaf."""
    if isinstance(node, dict) and "op" in node:
        gl = group_labels + ([node["label"]] if node.get("label") else [])
        for i, ch in enumerate(node.get("checks") or []):
            yield from _walk_leaves(ch, path + [i], gl)
    elif isinstance(node, dict):
        yield path, node, group_labels


def collect_open_slots(tree: dict) -> list:
    """Every OPEN param in a check tree, with fixed siblings and the labels
    (check label + enclosing group labels) as intent for the filler.

    Returns [{path, param, check_type, fixed, label, group_labels}].
    `path` locates the leaf via successive `checks` indices.
    """
    slots = []
    for path, leaf, group_labels in _walk_leaves(tree, [], []):
        ctype = leaf.get("type", "")
        fixed = {k: v for k, v in leaf.items()
                 if k not in ("type", "label")
                 and not (isinstance(v, dict) and v.get("open") is True)}
        for k, v in leaf.items():
            if isinstance(v, dict) and v.get("open") is True:
                slots.append({"path": path, "param": k, "check_type": ctype,
                              "fixed": fixed, "label": leaf.get("label", ""),
                              "group_labels": group_labels})
    return slots


def _node_at(tree: dict, path: list):
    node = tree
    for i in path:
        node = node["checks"][i]
    return node


def fill_open(tree: dict, fills: list) -> dict:
    """Return a deep copy of `tree` with open params set. `fills` is a list of
    {path, param, value}; anything not filled stays {open: true}."""
    import copy
    t = copy.deepcopy(tree)
    for f in fills:
        try:
            _node_at(t, f["path"])[f["param"]] = f["value"]
        except (KeyError, IndexError, TypeError):
            continue
    return t


def reduce_trajectory_for_llm(traj: list) -> list:
    """The whole trajectory, but observations carry ONLY their axtree (no HTML
    snapshot, no screenshot) — the compact structural view for the filler."""
    out = []
    for e in traj or []:
        t = e.get("type")
        if t == "action":
            out.append({k: e[k] for k in
                        ("type", "action", "target", "value", "text",
                         "option_text", "url", "method", "key", "checked")
                        if k in e})
        elif t == "network":
            body = e.get("requestBody")
            if isinstance(body, str) and len(body) > 1000:
                body = body[:1000] + "…"
            out.append({"type": "network", "method": e.get("method"),
                        "url": e.get("url"), "status": e.get("status"),
                        "requestBody": body})
        elif t == "observation":
            out.append({"type": "observation", "url": e.get("url"),
                        "title": e.get("title"), "axtree": e.get("axtree")})
        else:
            out.append({"type": t})
    return out


# ---------------------------------------------------------------------------
# task-graph helpers — resolve qa_answer leaf/chained, keep `expected` fresh
# ---------------------------------------------------------------------------

def leaf_macros(task: dict) -> set:
    """Terminal macros — those with no outgoing edge in the task's macro graph.
    A leaf QA macro's answer is the deliverable; a non-leaf feeds the next macro."""
    edges = task.get("macro_edges") or []
    sources = {e.get("from") for e in edges if isinstance(e, dict)}
    return {m for m in (task.get("macros") or []) if m not in sources}


def _all_leaves(node):
    if isinstance(node, dict) and "op" in node:
        for ch in node.get("checks") or []:
            yield from _all_leaves(ch)
    elif isinstance(node, dict):
        yield node


def inject_qa_leaf(macros_spec: dict, task: dict) -> dict:
    """Set `leaf` on every qa_answer check from the task's macro graph, so the
    conditional (answer vs reasoning) resolves correctly for this task. Also
    carries the task's `alternatives` (equally valid answers) onto terminal
    qa_answer checks so they aren't lost between task.json and verifier.json."""
    leaves = leaf_macros(task)
    alts = task.get("alternatives") or ""
    for macro, tree in (macros_spec or {}).items():
        is_leaf = macro in leaves
        for leaf in _all_leaves(tree):
            if leaf.get("type") == "qa_answer":
                leaf["leaf"] = is_leaf
                if is_leaf and alts and not leaf.get("alternatives"):
                    leaf["alternatives"] = alts
    return macros_spec


def refresh_expected(macros_spec: dict, task: dict) -> list:
    """Sync answer-type leaves' `expected` to the task's CURRENT answers.

    verifier.json freezes `expected` at build time; when a task is re-recorded
    and its expected_answer / qa_answers change, the saved verifier silently
    keeps grading against the old value. Call this wherever a verifier spec is
    loaded next to its task (builder load, sandbox run, eval grading).

    Returns the list of macros whose expected value was updated.
    """
    qa = task.get("qa_answers") or {}
    changed = []
    for macro, tree in (macros_spec or {}).items():
        want = qa.get(macro) if isinstance(qa, dict) and qa.get(macro) else (task.get("expected_answer") or "")
        if not isinstance(want, str):
            want = json.dumps(want)
        if not want:
            continue
        for leaf in _all_leaves(tree):
            if leaf.get("type") in ("qa_answer", "answer_matches", "reasoning_contains"):
                cur = leaf.get("expected")
                if isinstance(cur, str) and cur and cur != want:
                    leaf["expected"] = want
                    if macro not in changed:
                        changed.append(macro)
    return changed


# ---------------------------------------------------------------------------
# span helpers — map a macro's tagged span onto concrete trajectory actions
# ---------------------------------------------------------------------------

def _span_indices(span, n):
    """A macro span is [start, end] inclusive over the action list (occasionally
    a single [i]). Return the concrete action indices it covers."""
    if not isinstance(span, (list, tuple)) or not span:
        return []
    if len(span) == 1:
        return [span[0]] if isinstance(span[0], int) and 0 <= span[0] < n else []
    lo, hi = span[0], span[-1]
    if not (isinstance(lo, int) and isinstance(hi, int)):
        return []
    lo, hi = max(0, min(lo, hi)), min(n - 1, max(lo, hi))
    return list(range(lo, hi + 1))
