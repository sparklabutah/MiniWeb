"""Single source of truth for macro identity, metadata and aliases.

Loads the refined two-axis registry (data/macros.yaml, version 2) and exposes the
accessors every other module derives from. A tag is a **base macro** (physical
interaction) plus an optional **operation** (reasoning: read/extremum/count/
compute/compare/verify). Retired flat `verb_by_modality` names are folded in as
`aliases`, so `canon()` migrates them to their new base.
"""
import functools
import os

import yaml

REGISTRY_PATH = os.environ.get(
    "MINIWEB_MACROS",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "data", "macros.yaml"),
)


@functools.lru_cache(maxsize=1)
def _data():
    with open(REGISTRY_PATH) as f:
        return yaml.safe_load(f) or {}


def _load():
    """(macros, groups, alias_map) — the hot path for identity lookups."""
    data = _data()
    macros = data.get("macros", {}) or {}
    groups = data.get("groups", {}) or {}
    alias_map = {}
    for canonical, entry in macros.items():
        for a in (entry.get("aliases") or []):
            alias_map[a] = canonical
    return macros, groups, alias_map


def reload():
    _data.cache_clear()


# --- identity / aliases ----------------------------------------------------

def canon(name):
    """Resolve a (possibly retired) macro name to its canonical base macro."""
    _macros, _groups, alias = _load()
    seen = set()
    while name in alias and name not in seen:
        seen.add(name)
        name = alias[name]
    return name


def is_canonical(name):
    return name in _load()[0]


def is_known(name):
    macros, _groups, alias = _load()
    return name in macros or name in alias


def all_canonical():
    return sorted(_load()[0])


def alias_map():
    return dict(_load()[2])


# --- metadata --------------------------------------------------------------

def entry(name):
    macros, _groups, _alias = _load()
    return macros.get(canon(name), {})


_DESC_FIELDS = ("description", "example", "group", "span_start", "span_end")


def describe(name):
    """{description, example, group, span_start, span_end} (alias-resolved).

    `verb`/`modality` are kept as '' for backward compatibility with callers that
    still read them; the two-axis system no longer uses them.
    """
    e = entry(name)
    out = {k: e.get(k, "") for k in _DESC_FIELDS}
    out["verb"] = ""
    out["modality"] = ""
    return out


def descriptions():
    macros, _groups, _alias = _load()
    return {c: {**{k: e.get(k, "") for k in _DESC_FIELDS}, "verb": "", "modality": ""}
            for c, e in macros.items()}


# --- operations (the reasoning axis, shown behind a base macro) -------------

def operations():
    """{op: {weight, desc, check}} — the closed reasoning-operation vocabulary."""
    return _data().get("operations", {}) or {}


def operation_names():
    return list(operations().keys())


def is_operation(name):
    return name in operations()


# --- groups / difficulty ---------------------------------------------------

def groups():
    """{group: {weight, desc}} — the base-macro families."""
    return dict(_load()[1])


def group_of(name):
    return entry(name).get("group", "")


def macro_categories():
    """Canonical {name: group}. (group is the difficulty category now.)"""
    macros, _groups, _alias = _load()
    return {c: e.get("group", "") for c, e in macros.items()}


def category_weights():
    """{group: weight}."""
    return {g: (info or {}).get("weight", 1.0) for g, info in groups().items()}


def category(name):
    return group_of(name)


def weight(name):
    """Base-macro group weight + the operation weight when an op is attached
    (name may be 'base' or 'base.op')."""
    base, _, op = name.partition(".")
    w = category_weights().get(group_of(base), 1.0)
    if op:
        w += (operations().get(op, {}) or {}).get("weight", 0)
    return w


# --- backward-compat shims (old Layer-1/Layer-2 API) -----------------------
# The refined registry drops the archetype + interaction-primitive vocabularies.
# These shims keep callers importing/running; archetype() stands in with the
# group, and the trajectory->primitive derivation stays as pure logic.

def ARCHETYPES():
    return {}


def archetype(name):
    return group_of(name)


def archetypes():
    return {m: group_of(m) for m in all_canonical()}


def by_archetype():
    out = {}
    for m in all_canonical():
        out.setdefault(group_of(m), []).append(m)
    return out


def interaction_primitives():
    return _data().get("interaction_primitives", []) or []


def primitive_names():
    return [p["name"] for p in interaction_primitives()]


def difficulty_rank(primitive):
    names = primitive_names()
    return names.index(primitive) if primitive in names else -1


def _widget_for_action(a):
    act = a.get("action")
    sel = (a.get("selector") or "").lower()
    tgt = (a.get("target") or "").lower()
    if act == "type":
        return "text-field"
    if act == "select":
        return "dropdown"
    if act == "change":
        if "date" in sel:
            return "date-range"
        if "number" in sel:
            return "number"
        return "slider"
    if act == "check":
        return "radio" if "radio" in sel else "checkbox"
    if act == "drag":
        return "drag"
    if act == "click":
        if 'role="switch"' in sel or "switch" in sel or "toggle" in sel or "toggle" in tgt:
            return "toggle"
        if "chip" in sel or "chip" in tgt or "tag" in sel:
            return "chip"
        if sel.startswith("td") or sel.startswith("tr") or "table" in sel or "table" in tgt:
            return "table-cell"
        if a.get("href") or sel.startswith("a[") or sel == "a":
            return "link"
        return "button"
    return None


def interactions_for(trajectory):
    out = set()
    for e in trajectory or []:
        if e.get("type") != "action":
            continue
        w = _widget_for_action(e)
        if w:
            out.add(w)
    return out


def peak_difficulty(trajectory):
    return max((difficulty_rank(p) for p in interactions_for(trajectory)), default=-1)
