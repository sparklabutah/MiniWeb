"""Single source of truth for macro identity, metadata, difficulty and aliases.

Loads the canonical registry (data/macros.yaml) and exposes the accessors every
other module derives from. Before this module the same facts were duplicated
across _MACRO_DESCRIPTIONS, _MACRO_ALIASES, _canon (annotation/app.py) and
MACRO_CATEGORIES / CATEGORY_WEIGHTS (annotation/macro_difficulty.py); those now
delegate here. Per-site UI locations remain in annotation/macro_locations.py,
validated against this registry (see tests/test_macro_registry.py).
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
    """The full parsed registry dict (macros, categories, archetypes,
    interaction_primitives)."""
    with open(REGISTRY_PATH) as f:
        return yaml.safe_load(f) or {}


def _load():
    """(macros, categories, alias_map) — the hot path for identity lookups."""
    data = _data()
    macros = data.get("macros", {}) or {}
    categories = data.get("categories", {}) or {}
    alias_map = {}
    for canonical, entry in macros.items():
        for a in (entry.get("aliases") or []):
            alias_map[a] = canonical
    return macros, categories, alias_map


def reload():
    """Drop the cached parse (tests / after editing the yaml)."""
    _data.cache_clear()


# --- identity / aliases ----------------------------------------------------

def canon(name):
    """Resolve a (possibly retired) macro name to its canonical form."""
    _macros, _cats, alias = _load()
    seen = set()
    while name in alias and name not in seen:
        seen.add(name)
        name = alias[name]
    return name


def is_canonical(name):
    return name in _load()[0]


def is_known(name):
    """True if `name` is a canonical macro or a registered alias."""
    macros, _cats, alias = _load()
    return name in macros or name in alias


def all_canonical():
    return sorted(_load()[0])


def alias_map():
    """Flat {retired_name: canonical}. Replaces app._MACRO_ALIASES."""
    return dict(_load()[2])


# --- metadata --------------------------------------------------------------

def entry(name):
    """The full registry entry for a macro (alias-resolved); {} if unknown."""
    macros, _cats, _alias = _load()
    return macros.get(canon(name), {})


def describe(name):
    """{verb, modality, description, example} for a macro (alias-resolved)."""
    e = entry(name)
    return {k: e.get(k, "") for k in ("verb", "modality", "description", "example")}


def descriptions():
    """Canonical-only {name: {verb,modality,description,example}}.

    Replaces app._MACRO_DESCRIPTIONS (retired-name entries are gone; look them
    up via describe(), which alias-resolves)."""
    macros, _cats, _alias = _load()
    return {c: {k: e.get(k, "") for k in ("verb", "modality", "description", "example")}
            for c, e in macros.items()}


# --- difficulty ------------------------------------------------------------

def macro_categories():
    """Canonical {name: category}. Replaces macro_difficulty.MACRO_CATEGORIES."""
    macros, _cats, _alias = _load()
    return {c: e.get("category", "") for c, e in macros.items()}


def category_weights():
    """{category: weight}. Replaces macro_difficulty.CATEGORY_WEIGHTS."""
    return dict(_load()[1])


def category(name):
    return entry(name).get("category", "")


def weight(name):
    return category_weights().get(category(name), 1.0)


# --- Layer 1: commit archetype (defined in the registry) -------------------
# A task macro is defined by the OUTCOME it commits, not the widget used to
# reach it (that is Layer 2 below). Each macro carries an `archetype:` field in
# data/macros.yaml, and the archetype definitions (with each one's `collapses_to`
# representative) live under the top-level `archetypes:` key. See the commit test
# in docs/macro_taxonomy.md.

def ARCHETYPES():
    """{archetype: {collapses_to, description}} — from the registry."""
    return _data().get("archetypes", {}) or {}


def archetype(name):
    """The commit archetype of a macro. '' if unset."""
    return entry(name).get("archetype", "") or ""


def archetypes():
    """{canonical_macro: archetype} across the registry."""
    return {m: archetype(m) for m in all_canonical()}


def by_archetype():
    """{archetype: [macros]} grouping."""
    out = {}
    for m in all_canonical():
        out.setdefault(archetype(m), []).append(m)
    return out


# --- Layer 2: interaction primitives ---------------------------------------
# WHICH widgets the agent had to operate — the axis visual agents differ on.
# The ranked vocabulary is registry DATA (`interaction_primitives:`, ordered
# easy->hard); the trajectory derivation below is the only logic. Derived, never
# annotated: the recorder already emits typed actions whose type is the widget
# (evaluation/action_vocabulary.py), so the same function scores human and agent
# trajectories identically. See docs/macro_taxonomy.md.

def interaction_primitives():
    """Ordered [{name, desc}] — the ranked Layer-2 vocabulary from the registry."""
    return _data().get("interaction_primitives", []) or []


def primitive_names():
    """Just the primitive names, in easy->hard order."""
    return [p["name"] for p in interaction_primitives()]


def difficulty_rank(primitive):
    """Position on the visual perceptual-motor axis (higher = harder); -1 if unknown."""
    names = primitive_names()
    return names.index(primitive) if primitive in names else -1


def _widget_for_action(a):
    """Map one recorded action to its interaction primitive, or None if it is not
    a widget operation (submit/keypress/scroll/navigate/tab)."""
    act = a.get("action")
    sel = (a.get("selector") or "").lower()
    tgt = (a.get("target") or "").lower()
    if act == "type":
        return "text-field"
    if act == "select":                     # <select> — always a dropdown
        return "dropdown"
    if act == "change":                     # only fires on range|date|number
        if "date" in sel:
            return "date-range"
        if "number" in sel:
            return "number"
        return "slider"
    if act == "check":                      # checkbox / radio
        return "radio" if "radio" in sel else "checkbox"
    if act == "drag":
        return "drag"
    if act == "click":                      # low-signal: best-effort subtyping
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
    """The set of interaction primitives exercised in a recorded trajectory
    (human gold or agent). Always a subset of primitive_names()."""
    out = set()
    for e in trajectory or []:
        if e.get("type") != "action":
            continue
        w = _widget_for_action(e)
        if w:
            out.add(w)
    return out


def peak_difficulty(trajectory):
    """The hardest primitive a task requires — a difficulty proxy grounded in
    what the eyes+cursor must do, not an assumed weight. -1 if none."""
    return max((difficulty_rank(p) for p in interactions_for(trajectory)), default=-1)
