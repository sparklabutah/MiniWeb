"""The paper's final primitive and task sets (data/final_set.yaml) and the lock they put on the annotation tool.

With ``locked: true`` the tool is read-only: no macro registration and no task, verifier or review edits; its pickers
offer only the final primitives and its task list shows only the final tasks. The grader-audit labels are the one
thing it still records. Regenerate the file with ``scripts/make_final_set.py``; set ``MINIWEB_UNLOCK=1`` to edit
anyway (e.g. a local fix that the paper's numbers will then have to absorb).
"""
import os
from functools import lru_cache

import yaml

PATH = os.environ.get("MINIWEB_FINAL_SET") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "final_set.yaml")

# write routes that stay open under the lock: sessions, read-only search and the grader-audit labels
OPEN_WRITES = {"/annotate/login", "/annotate/logout", "/annotate/api/auto_login", "/annotate/api/auto_logout",
               "/annotate/api/toggle_2fa", "/annotate/api/macro_search"}
OPEN_PREFIXES = ("/annotate/api/grader_audit/",)


@lru_cache(maxsize=1)
def _data():
    try:
        with open(PATH) as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}


def locked():
    return bool(_data().get("locked")) and os.environ.get("MINIWEB_UNLOCK") != "1"


def primitives():
    return set(_data().get("primitives") or [])


def tasks():
    """{task_id} of the final task set (task ids are unique across annotators)."""
    return set(_data().get("tasks") or [])


def write_allowed(path):
    return path in OPEN_WRITES or path.startswith(OPEN_PREFIXES)


def keep_primitives(names):
    """Filter a macro list to the final primitives when locked (order kept)."""
    if not locked():
        return list(names)
    keep = primitives()
    return [n for n in names if n in keep]


BANNER = ('<div id="final-set-lock" style="position:fixed;right:12px;top:7px;z-index:99999;padding:3px 10px;'
          'border-radius:12px;background:#334155;color:#f8fafc;font:12px/1.4 system-ui,sans-serif;opacity:.85;'
          'pointer-events:none">Final set locked: {n_p} primitives, {n_t} tasks (read-only)</div>')


def banner():
    return BANNER.format(n_p=len(primitives()), n_t=len(tasks()))
