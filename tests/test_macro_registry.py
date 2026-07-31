"""Drift guard for the canonical macro registry (data/macros.yaml).

Every place that names a macro must agree with the registry. Run standalone
(`python tests/test_macro_registry.py`) or under pytest. A failure here means a
macro name drifted out of sync — the exact rot this consolidation removed.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import annotation.macros as R  # noqa: E402
import annotation.app as A  # noqa: E402
import annotation.macro_difficulty as MD  # noqa: E402
import annotation.macro_templates as MT  # noqa: E402
from annotation.macro_locations import MACRO_LOCATIONS  # noqa: E402


def test_registry_entries_complete():
    """Every canonical macro carries full metadata and a weighted category."""
    weights = R.category_weights()
    for m in R.all_canonical():
        e = R.entry(m)
        for field in ("verb", "modality", "description", "category"):
            assert e.get(field), f"{m} missing {field}"
        assert e["category"] in weights, f"{m} category {e['category']!r} has no weight"


def test_aliases_resolve_and_dont_collide():
    """Aliases point at real canonicals, never shadow one, and canon is stable."""
    canon = set(R.all_canonical())
    for alias, target in R.alias_map().items():
        assert alias not in canon, f"alias {alias} also a canonical name"
        assert target in canon, f"alias {alias} -> {target} which is not canonical"
        assert R.canon(alias) == target, f"canon({alias}) != {target}"
        assert R.canon(target) == target, f"canon of canonical {target} not idempotent"


def test_macro_locations_all_known():
    """Every macro keyed in MACRO_LOCATIONS is a known canonical or alias."""
    unknown = {}
    for site, macros in MACRO_LOCATIONS.items():
        for m in macros:
            if not R.is_known(m):
                unknown.setdefault(site, []).append(m)
    assert not unknown, f"MACRO_LOCATIONS names unknown to the registry: {unknown}"


def test_edge_hints_are_canonical():
    """Edge hints must be canonical — the consumer matches the canonical pool."""
    bad = {}
    for etype, hints in A._EDGE_MACRO_HINTS.items():
        for h in hints:
            if not R.is_canonical(h):
                bad.setdefault(etype, []).append(h)
    assert not bad, f"_EDGE_MACRO_HINTS has non-canonical names: {bad}"


def test_templates_keys_known():
    """Every verifier template is keyed by a known macro."""
    unknown = [m for m in MT.load_all() if not R.is_known(m)]
    assert not unknown, f"macro_templates.yaml names unknown to the registry: {unknown}"


def test_canon_parity_across_modules():
    """The three canon paths (app, registry, templates) must agree everywhere."""
    names = set(R.all_canonical()) | set(R.alias_map())
    for m in MACRO_LOCATIONS.values():
        names.update(m)
    for m in names:
        assert A._canon(m) == R.canon(m), f"app._canon({m}) != registry.canon"
        assert MT._canon(m) == R.canon(m), f"macro_templates._canon({m}) != registry.canon"


def test_difficulty_shim_matches_registry():
    assert MD.MACRO_CATEGORIES == R.macro_categories()
    assert MD.CATEGORY_WEIGHTS == R.category_weights()


def test_descriptions_shim_matches_registry():
    assert A._MACRO_DESCRIPTIONS == R.descriptions()
    assert A._MACRO_ALIASES == R.alias_map()


def test_every_macro_has_a_known_archetype():
    """Layer 1: every canonical macro's verb maps to a defined archetype."""
    unmapped = [m for m in R.all_canonical() if not R.archetype(m)]
    assert not unmapped, f"macros with no archetype: {unmapped}"
    known = set(R.ARCHETYPES())
    for m in R.all_canonical():
        assert R.archetype(m) in known, f"{m}: unknown archetype {R.archetype(m)!r}"


def test_archetype_collapse_targets_are_real():
    """Each archetype's collapses_to macro (if set) exists in the registry."""
    for a, meta in R.ARCHETYPES().items():
        t = meta.get("collapses_to")
        assert t is None or R.is_known(t), f"archetype {a} collapses_to unknown macro {t!r}"
    # every macro's archetype is a defined archetype
    known = set(R.ARCHETYPES())
    for m in R.all_canonical():
        assert R.archetype(m) in known, f"{m}: archetype {R.archetype(m)!r} not defined"


def test_interaction_primitives_ranked_and_unique():
    """Layer 2: the primitive vocabulary is a unique, fully-ranked list."""
    names = R.primitive_names()
    assert names, "no interaction_primitives in registry"
    assert len(names) == len(set(names)), "duplicate primitive"
    for p in names:
        assert R.difficulty_rank(p) >= 0


def test_interactions_derivation_is_closed():
    """Derived tags are always drawn from the declared vocabulary."""
    sample = [
        {"type": "action", "action": "select", "selector": 'select[name="x"]'},
        {"type": "action", "action": "type", "selector": 'input[name="y"]'},
        {"type": "action", "action": "change", "selector": 'input[type="range"]'},
        {"type": "action", "action": "check", "selector": 'input[type="radio"]'},
        {"type": "action", "action": "drag"},
        {"type": "action", "action": "submit"},          # not a widget -> ignored
        {"type": "observation"},                           # not an action -> ignored
    ]
    got = R.interactions_for(sample)
    assert got <= set(R.primitive_names()), f"tag outside vocabulary: {got - set(R.primitive_names())}"
    assert {"dropdown", "text-field", "slider", "radio", "drag"} <= got


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
