"""Control kinds — the macro-specific half of the macro data pipeline.

Every stage of the pipeline is macro-generic except the parts that must know what a
macro's target looks like on a page. Those live here, one Kind per control type:

    discover   crawl time: find this kind's controls in a read-only page scan
    arguments  sampler: the argument space of one control (options, items, values)
    apply      privileged: perform the step with Playwright in a throw-away session
               (site-map probe and feasibility dry run — never recorded)
    check      the expected backend check once the argument is applied
    describe / mentions        what the suggester may say and must mention
    step_spec / script_task / locate / example      the executor's prompt pieces

A kind declares the macros it serves (`macros = {macro: role}`), so adding a macro
family is adding a module here: the registry imports every module in this package.
"""
from __future__ import annotations

import importlib
import pkgutil

REGISTRY: dict = {}
_loaded = False


def register(cls):
    kind = cls()
    REGISTRY[kind.name] = kind
    return cls


def _load():
    global _loaded
    if _loaded:
        return
    _loaded = True
    for mod in pkgutil.iter_modules(__path__):
        if not mod.name.startswith("_") and mod.name != "base":
            importlib.import_module(f"{__name__}.{mod.name}")


def all_kinds():
    _load()
    return list(REGISTRY.values())


def get(name):
    _load()
    return REGISTRY[name]


def of(ctrl):
    return get(ctrl["kind"])


def serving(macro):
    """Kinds whose controls can be the target of `macro`."""
    return [k for k in all_kinds() if macro in k.macros]


def supported_macros():
    return sorted({m for k in all_kinds() for m in k.macros})


def serves(ctrl, macro):
    return of(ctrl).serves(ctrl, macro)


def macro_of(ctrl):
    """The macro a control's step demonstrates (for a mid-chain prefix)."""
    kind = of(ctrl)
    for macro, role in kind.macros.items():
        if role == ctrl.get("role", role):
            return macro
    raise KeyError(f"no macro for {ctrl['kind']}/{ctrl.get('role')}")
