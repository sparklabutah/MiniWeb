"""Generate real fixture files mirroring the fake file picker's catalog.

The sites' injected file-picker.js simulates the OS file dialog with a fixed
list of fake files (photo.jpg, letter.docx, ...). Human annotators "upload"
those. Browser agents (browser_use) instead need real files on disk passed
via available_file_paths. This script derives evaluation/fixtures/* from the
FILES array in app/static/file-picker.js so names AND byte content match what
a human upload produces — verifiers that inspect the uploaded POST body see
identical data either way.

Usage:
    python evaluation/generate_fixtures.py          # (re)generate
    from generate_fixtures import ensure_fixtures   # returns list[str] paths
"""

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PICKER_JS = PROJECT_ROOT / "app" / "static" / "file-picker.js"
FIXTURES_DIR = PROJECT_ROOT / "evaluation" / "fixtures"

_ENTRY_RE = re.compile(
    r"\{\s*name:\s*'(?P<name>[^']+)'\s*,\s*type:\s*'[^']*'\s*,\s*"
    r"ext:\s*\[[^\]]*\]\s*,\s*content:\s*'(?P<content>(?:[^'\\]|\\.)*)'"
)


def _unescape_js(s):
    """Interpret escapes inside a single-quoted JS string literal."""
    return (s.replace("\\\\", "\x00")
             .replace("\\n", "\n")
             .replace("\\t", "\t")
             .replace("\\'", "'")
             .replace("\x00", "\\"))


def parse_picker_files():
    src = PICKER_JS.read_text()
    files = {}
    for m in _ENTRY_RE.finditer(src):
        files[m.group("name")] = _unescape_js(m.group("content"))
    if not files:
        raise RuntimeError(f"no FILES entries parsed from {PICKER_JS}")
    return files


def ensure_fixtures():
    """Write fixture files (if missing or stale) and return their paths."""
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, content in parse_picker_files().items():
        p = FIXTURES_DIR / name
        data = content.encode()
        if not p.exists() or p.read_bytes() != data:
            p.write_bytes(data)
        paths.append(str(p))
    return sorted(paths)


if __name__ == "__main__":
    for p in ensure_fixtures():
        print(p)
