"""Real files the browser-use agent may upload — sourced from the simulated
file system (the ``src/miniweb/filesystem/`` VFS, the same tree the in-page file explorer
shows). ``available_file_paths`` points at these real files, so a native
``upload_file`` action sends the exact bytes a human upload through the explorer
would, and verifiers that inspect the uploaded body see identical data.

Previously this parsed a fixed catalog out of ``src/miniweb/app/static/file-picker.js`` and
wrote copies under ``src/miniweb/evaluation/fixtures/``. That flat picker was replaced by the
universal file explorer over ``src/miniweb/filesystem/`` (see ``src/miniweb/app/vfs.py``), so we now hand
the agent the real VFS files directly — no fixtures to generate.

Usage:
    from miniweb.evaluation.generate_fixtures import ensure_fixtures   # -> list[str] of abs paths
    python src/miniweb/evaluation/generate_fixtures.py           # print the list
"""
from helpers.paths import REPO_ROOT
import os
from pathlib import Path

PROJECT_ROOT = REPO_ROOT
# Mirror src/miniweb/app/vfs.py's default + MINIWEB_VFS_DIR override so the agent sees the
# same file system the explorer serves.
VFS_DIR = Path(os.environ.get("MINIWEB_VFS_DIR", str(Path(__file__).resolve().parents[1] / "filesystem")))


def ensure_fixtures():
    """Return abs paths of the real files in the VFS the agent may upload."""
    if not VFS_DIR.exists():
        return []
    return sorted(
        str(p) for p in VFS_DIR.rglob("*")
        if p.is_file() and not p.name.startswith(".")
    )


if __name__ == "__main__":
    for p in ensure_fixtures():
        print(p)
