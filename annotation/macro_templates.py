"""Macro verifier templates — storage + usage/observation stats.

A template is a human-authored, per-macro verifier skeleton: an arbitrarily
nested AND/OR tree of check primitives, where each param is either FIXED (a
concrete value chosen from a real-value dropdown) or OPEN (left for the per-task
filler to populate later). Templates are stored in one YAML file, one entry per
macro. This module owns:

  * load/save of macro_templates.yaml
  * live usage (which tasks / websites use a macro)
  * the observed (action, value-shape) distribution for a macro, so the author
    designs against real recorded data instead of guessing

The check primitives and which params they expose live in CHECK_SCHEMA below,
kept in lockstep with evaluation/verifiers.py. The action dropdown comes from
evaluation/action_vocabulary.py — the single source of truth for action types.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

# Stored next to the annotations so it travels with the dataset volume.
TEMPLATES_PATH = Path(
    os.environ.get("MINIWEB_MACRO_TEMPLATES",
                   str(ROOT / "data" / "macro_templates.yaml")))


def _canon(m):
    """Canonical macro name — merges retired/consolidated aliases. Task files
    keep original names; everything downstream reads through this."""
    from annotation.app import _canon as canon
    return canon(m)


# ---------------------------------------------------------------------------
# check primitives — what the builder can drop into a template.
#   params: name -> {kind, options?, default_open}
#     kind: "enum" (pick from options) | "text" | "dict" | "list"
#     default_open: True if this param is usually left open (filled per task)
# ---------------------------------------------------------------------------

def _http_status_codes():
    return [200, 201, 202, 204, 301, 302, 303, 304, 400, 401, 403, 404, 409, 422, 500]


def _http_methods():
    return ["GET", "POST", "PUT", "PATCH", "DELETE"]


def check_schema():
    """Built lazily so the action vocabulary is imported at call time."""
    from evaluation.action_vocabulary import ASSERTABLE_ACTIONS
    return {
        "action_included": {
            "label": "Action included",
            "help": "An action of this kind is in the trajectory (matched on action + target + value; no selector).",
            "params": {
                "action": {"kind": "enum", "options": ASSERTABLE_ACTIONS, "default_open": False},
                "target": {"kind": "text", "default_open": True},
                "value":  {"kind": "text", "default_open": True},
            },
        },
        "request_made": {
            "label": "Request made",
            "help": "A network request matching method/url (optionally status, and payload fields as a dict-subset compare).",
            "params": {
                "method":      {"kind": "enum", "options": _http_methods(), "default_open": False},
                "url":         {"kind": "text", "default_open": True},
                "status":      {"kind": "enum", "options": _http_status_codes(), "default_open": False},
                "body_fields": {"kind": "dict", "default_open": True},
                "response_fields": {"kind": "dict", "default_open": True},
            },
        },
        "answer_matches": {
            "label": "Answer matches",
            "help": "The agent's answer matches the expected value.",
            "params": {
                "expected":     {"kind": "text", "default_open": True},
                "mode":         {"kind": "enum", "options": ["exact", "includes", "fuzzy"], "default_open": False},
                "alternatives": {"kind": "list", "default_open": True},
            },
        },
        "answer_grounded": {
            "label": "Answer grounded",
            "help": "The value was present on the page the agent answered from (URL and/or text).",
            "params": {
                "url":  {"kind": "text", "default_open": True},
                "text": {"kind": "text", "default_open": True},
            },
        },
        "qa_answer": {
            "label": "QA answer (conditional)",
            "help": "The default QA check. If the macro is a LEAF (terminal) in the task graph it checks the reported answer; if it's chained into a later macro it checks the reasoning trace. Leaf is set automatically per task from macro_edges.",
            "params": {
                "expected": {"kind": "text", "default_open": True},
                "mode": {"kind": "enum", "options": ["fuzzy", "contains"], "default_open": False},
                "alternatives": {"kind": "list", "default_open": True},
            },
        },
        "reasoning_contains": {
            "label": "Reasoning reaches answer",
            "help": "The agent's FINAL reasoning arrives at the expected answer — substring, or (mode 'fuzzy') an LLM judges it's toward the answer. Humans have no reasoning, so it passes on Gold/Walk.",
            "params": {
                "expected": {"kind": "text", "default_open": True},
                "mode": {"kind": "enum", "options": ["fuzzy", "contains"], "default_open": False},
            },
        },
        "page_visited": {
            "label": "Page visited",
            "help": "The agent was on a URL containing this fragment.",
            "params": {
                "url": {"kind": "text", "default_open": True},
            },
        },
    }


# ---------------------------------------------------------------------------
# storage
# ---------------------------------------------------------------------------

def load_all() -> dict:
    if not TEMPLATES_PATH.exists():
        return {}
    try:
        return yaml.safe_load(TEMPLATES_PATH.read_text()) or {}
    except yaml.YAMLError:
        return {}


def load_template(macro: str):
    return load_all().get(macro)


def save_template(macro: str, tree: dict) -> None:
    data = load_all()
    if tree is None:
        data.pop(macro, None)
    else:
        data[macro] = tree
    TEMPLATES_PATH.parent.mkdir(parents=True, exist_ok=True)
    # sort_keys=False keeps macro order stable-ish; default_flow_style=False = block style
    TEMPLATES_PATH.write_text(
        yaml.safe_dump(data, sort_keys=True, default_flow_style=False, allow_unicode=True))


# ---------------------------------------------------------------------------
# usage + observed distribution (live scans — no cache)
# ---------------------------------------------------------------------------

def _sites_for_macro(macro: str) -> list:
    try:
        from annotation.macro_locations import MACRO_LOCATIONS
    except Exception:
        return []
    out = []
    for site, macros in MACRO_LOCATIONS.items():
        if isinstance(macros, dict) and any(_canon(m) == macro for m in macros):
            out.append(site)
    return sorted(out)


def _locations_for_macro(macro: str) -> list:
    """Per-website UI locations for a (canonical) macro, from macro_locations.py.

    Returns [{site, locations:[str, ...]}] — aggregated across any pre-merge
    names that canonicalize to this macro."""
    try:
        from annotation.macro_locations import MACRO_LOCATIONS
    except Exception:
        return []
    out = []
    for site in sorted(MACRO_LOCATIONS):
        macros = MACRO_LOCATIONS[site]
        if not isinstance(macros, dict):
            continue
        locs = []
        for m, l in macros.items():
            if _canon(m) == macro:
                locs.extend([l] if isinstance(l, str) else list(l or []))
        if locs:
            out.append({"site": site, "locations": locs})
    return out


def _macro_meta(macro: str) -> dict:
    from annotation.app import _MACRO_DESCRIPTIONS
    return _MACRO_DESCRIPTIONS.get(macro, {}) or {}


def _iter_task_files():
    from annotation.storage import ANNOTATIONS_DIR
    if not ANNOTATIONS_DIR.exists():
        return
    for tf in sorted(ANNOTATIONS_DIR.glob("*/*/task.json")):
        yield tf


def _classify_value(v) -> str:
    s = str(v or "").strip()
    if not s:
        return "empty"
    if s.replace(".", "", 1).replace("-", "", 1).isdigit():
        return "number"
    if any(sep in s for sep in ("-", "/", ":")) and any(c.isdigit() for c in s) and len(s) <= 25:
        return "date/time"
    return "text"


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


def _load_trajectory(task_dir: Path):
    tj = task_dir / "trajectory.json"
    if not tj.exists():
        return []
    try:
        return json.loads(tj.read_text())
    except (json.JSONDecodeError, OSError):
        return []


def macro_usage(macro: str) -> dict:
    """Which tasks and websites use this macro, plus the observed action/value
    distribution across the actions its spans cover."""
    from evaluation.action_vocabulary import signal as action_signal

    tasks = []
    action_counts = {}          # action -> count
    value_shapes = {}           # action -> {shape: count}
    examples = {}               # action -> [sample values]

    for tf in _iter_task_files():
        try:
            data = json.loads(tf.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if macro not in {_canon(m) for m in (data.get("macros") or [])}:
            continue
        ann, tid = tf.parent.parent.name, tf.parent.name
        tasks.append({"annotator": ann, "task_id": tid})

        acts = [e for e in _load_trajectory(tf.parent) if e.get("type") == "action"]
        # aggregate spans from every pre-merge macro that canonicalizes to `macro`
        for orig, span in (data.get("macro_spans") or {}).items():
            if _canon(orig) != macro:
                continue
            for idx in _span_indices(span, len(acts)):
                a = acts[idx]
                act = a.get("action") or "?"
                action_counts[act] = action_counts.get(act, 0) + 1
                v = a.get("value") or a.get("text") or a.get("option_text")
                shape = _classify_value(v)
                value_shapes.setdefault(act, {})[shape] = value_shapes.setdefault(act, {}).get(shape, 0) + 1
                if v and len(examples.setdefault(act, [])) < 3:
                    examples[act].append(str(v)[:40])

    observed = []
    for act, cnt in sorted(action_counts.items(), key=lambda kv: -kv[1]):
        observed.append({
            "action": act,
            "count": cnt,
            "signal": action_signal(act),
            "value_shapes": value_shapes.get(act, {}),
            "examples": examples.get(act, []),
        })

    meta = _macro_meta(macro)
    sites = _sites_for_macro(macro)
    return {
        "macro": macro,
        "verb": meta.get("verb", ""),
        "modality": meta.get("modality", ""),
        "description": meta.get("description", ""),
        "example": meta.get("example", ""),
        "sites": sites,
        "site_count": len(sites),
        "locations": _locations_for_macro(macro),
        "tasks": tasks,
        "task_count": len(tasks),
        "observed": observed,
    }


# ---------------------------------------------------------------------------
# per-task filling — take the human templates and fill their OPEN params from
# the task's trajectory (via an LLM). These are the pure, LLM-free mechanics;
# the LLM call lives in the endpoint.
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
    """Every OPEN param in a template, with fixed siblings and the human-written
    labels (check label + enclosing group labels) as intent for the filler.

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
    import json as _json
    qa = task.get("qa_answers") or {}
    changed = []
    for macro, tree in (macros_spec or {}).items():
        want = qa.get(macro) if isinstance(qa, dict) and qa.get(macro) else (task.get("expected_answer") or "")
        if not isinstance(want, str):
            want = _json.dumps(want)
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


def build_task_draft(macros: list) -> dict:
    """Assemble the per-task verifier draft from the macros' templates.

    Returns {templates: {macro: tree}, missing: [macros with no template],
             slots: [{id, macro, path, param, check_type, fixed}]}.
    """
    all_templates = load_all()
    templates, missing, slots = {}, [], []
    # canonicalize + de-dup: a task listing two merged macros yields one entry
    for macro in dict.fromkeys(_canon(m) for m in (macros or [])):
        tree = all_templates.get(macro)
        if not tree:
            missing.append(macro)
            continue
        templates[macro] = tree
        for i, s in enumerate(collect_open_slots(tree)):
            slots.append({"id": f"{macro}::{i}", "macro": macro, **s})
    return {"templates": templates, "missing": missing, "slots": slots}


def mapped_macros() -> set:
    """The authoritative active macro set — macros mapped to at least one site in
    macro_locations.py (131). The description registry is broader (169) and
    includes retired aliases / never-used variants we don't build templates for."""
    try:
        from annotation.macro_locations import MACRO_LOCATIONS
    except Exception:
        return set()
    out = set()
    for _site, macros in MACRO_LOCATIONS.items():
        if isinstance(macros, dict):
            out |= {_canon(m) for m in macros}
    return out


def is_suggested(tree) -> bool:
    return bool(isinstance(tree, dict) and tree.get("_suggested"))


def observed_actions_all() -> dict:
    """One pass over all tasks -> {macro: {action: count}} across tagged spans.
    Cheaper than macro_usage() per-macro when scoring the whole macro set."""
    out = {}
    for tf in _iter_task_files():
        try:
            data = json.loads(tf.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        spans = data.get("macro_spans") or {}
        acts = [e for e in _load_trajectory(tf.parent) if e.get("type") == "action"]
        for macro, span in spans.items():
            cm = _canon(macro)
            for idx in _span_indices(span, len(acts)):
                a = acts[idx].get("action") or "?"
                out.setdefault(cm, {})[a] = out.setdefault(cm, {}).get(a, 0) + 1
    return out


def list_macros() -> list:
    """The 131 authoritative (site-mapped) macros with description, verb, template
    state and usage counts — for the builder sidebar. Descriptions come from the
    app registry; the registry's extra 38 retired/unmapped aliases are excluded."""
    from annotation.app import _MACRO_DESCRIPTIONS
    templates = load_all()

    # count tasks per macro in one pass
    task_counts = {}
    for tf in _iter_task_files():
        try:
            data = json.loads(tf.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        for m in {_canon(x) for x in (data.get("macros") or [])}:
            task_counts[m] = task_counts.get(m, 0) + 1

    from annotation import macros as _reg
    # every registry macro (incl. newly proposed/registered ones), plus any
    # site-mapped names, so the builder never hides a real macro.
    all_macros = mapped_macros() | set(_reg.all_canonical())
    out = []
    for macro in all_macros:
        meta = _MACRO_DESCRIPTIONS.get(macro, {})
        tree = templates.get(macro)
        out.append({
            "macro": macro,
            "verb": meta.get("verb", ""),
            "modality": meta.get("modality", ""),
            "description": meta.get("description", ""),
            "has_template": macro in templates,
            "suggested": is_suggested(tree),   # AI-proposed, not yet confirmed
            "task_count": task_counts.get(macro, 0),
            "site_count": len(_sites_for_macro(macro)),
        })
    out.sort(key=lambda m: (m["verb"], m["modality"], m["macro"]))
    return out
