"""Single source of truth for macro identity, metadata and aliases.

Loads the refined two-axis registry (data/macros.yaml, version 2) and exposes the
accessors every other module derives from. A tag is a **base macro** (physical
interaction) plus an optional **operation** (reasoning: read/extremum/count/
compute/compare/verify). Retired flat `verb_by_modality` names are folded in as
`aliases`, so `canon()` migrates them to their new base.
"""
import functools
import os
import shutil

import yaml

# Repo-bundled defaults (seed copies).
_REPO_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def macro_data_dir():
    """Directory that holds the macro YAMLs.

    Set ``MINIWEB_MACRO_DIR`` to a persistent volume in deployment so that
    annotator-registered macros (written to macros.yaml) and per-site locations
    survive redeploys. Defaults to the repo's ``data/`` directory.
    """
    return os.environ.get("MINIWEB_MACRO_DIR", _REPO_DATA_DIR)


def macro_data_path(filename, file_env=None):
    """Resolve a macro YAML path, seeding a fresh persistent dir from the repo.

    Precedence: an explicit full-path override in ``file_env`` (if set), else
    ``<MINIWEB_MACRO_DIR>/<filename>``. If the resolved file doesn't exist yet
    (e.g. a brand-new volume), it is seeded by copying the repo's bundled copy.
    """
    path = (os.environ.get(file_env) if file_env else None) or os.path.join(macro_data_dir(), filename)
    if not os.path.exists(path):
        seed = os.path.join(_REPO_DATA_DIR, filename)
        if os.path.exists(seed) and os.path.abspath(path) != os.path.abspath(seed):
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            shutil.copy2(seed, path)
    return path


# macros.yaml — MINIWEB_MACROS overrides the exact path; otherwise it lives in
# MINIWEB_MACRO_DIR (persistent volume) or the repo's data/ dir.
REGISTRY_PATH = macro_data_path("macros.yaml", "MINIWEB_MACROS")


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


def register_macro(name, group, description, span_start="", span_end="", example=""):
    """Append a new base macro to data/macros.yaml and hot-reload the registry.

    Raises ValueError if the name collides (as a macro or alias) or the group is
    unknown. The YAML file is edited by appending under the `macros:` block
    (which is last in the file), so existing comments/formatting are preserved.
    """
    name = (name or "").strip()
    if not name:
        raise ValueError("macro name required")
    group = group or "unassigned"   # family assigned later
    macros, groups, alias = _load()
    if name in macros:
        raise ValueError(f"{name!r} is already a macro")
    if name in alias:
        raise ValueError(f"{name!r} is an alias of {alias[name]!r}")
    if group not in groups:
        raise ValueError(f"unknown group {group!r} (expected one of {sorted(groups)})")
    if not (description or "").strip():
        raise ValueError("description required")

    entry = {"group": group, "description": description.strip()}
    if example:
        entry["example"] = example.strip()
    if span_start:
        entry["span_start"] = span_start.strip()
    if span_end:
        entry["span_end"] = span_end.strip()

    block = yaml.safe_dump({name: entry}, sort_keys=False, allow_unicode=True,
                           default_flow_style=False, width=1000)
    indented = "".join("  " + line + "\n" for line in block.splitlines())
    with open(REGISTRY_PATH) as f:
        cur = f.read()
    if not cur.endswith("\n"):
        cur += "\n"
    with open(REGISTRY_PATH, "w") as f:
        f.write(cur + indented)
    reload()
    return name


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


_DESC_FIELDS = ("description", "example", "group", "span_start", "span_end", "warning")


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
