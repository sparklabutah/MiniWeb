"""Paths and defaults for the macro data pipeline (one place to change them)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# data/datagen/ — site_split.json + guides/ are tracked; sitemap/ and runs/ are not.
DATAGEN_DIR = Path(os.environ.get("MINIWEB_DATAGEN_DIR", ROOT / "data" / "datagen")).resolve()
SPLIT_PATH = DATAGEN_DIR / "site_split.json"
GUIDES_DIR = DATAGEN_DIR / "guides"
SITEMAP_DIR = DATAGEN_DIR / "sitemap"
RUNS_DIR = DATAGEN_DIR / "runs"
# kept trajectories a later pipeline change superseded (kept on disk, but no longer counted toward --target,
# excluded from the dedup keys and from the WebMix replay): {"runs": {run: [macro, ...]}, "task_ids": [...]}
RETIRED_PATH = DATAGEN_DIR / "retired.json"


def retired():
    """-> predicate (run, kept row) -> bool."""
    import json
    try:
        r = json.loads(RETIRED_PATH.read_text())
    except (OSError, ValueError):
        return lambda run, row: False
    macros = {run: set(ms) for run, ms in (r.get("runs") or {}).items()}
    ids = set(r.get("task_ids") or [])
    return lambda run, row: row.get("macro") in macros.get(run, ()) or row.get("task_id") in ids

# Gemini for every LLM stage (Vertex creds in .env). The judge defaults to the
# evaluation judge's model so generation and evaluation are scored alike.
MODEL_GUIDE = os.environ.get("DATAGEN_MODEL_GUIDE", "gemini-3.5-flash")
MODEL_SUGGEST = os.environ.get("DATAGEN_MODEL_SUGGEST", "gemini-3.5-flash")
MODEL_EXECUTOR = os.environ.get("DATAGEN_MODEL_EXECUTOR", "gemini-3.5-flash")
MODEL_REASON = os.environ.get("DATAGEN_MODEL_REASON", "gemini-3.5-flash")

# Browser. chromium-1228 (Chrome for Testing 149) never finishes loading http pages
# headless on this machine; 1117 works and renders native <select> popups into
# screenshots (mouse clicks do not reach the popup — keyboard does).
CHROME = os.path.expanduser(os.environ.get(
    "DATAGEN_CHROME", "~/.cache/ms-playwright/chromium-1117/chrome-linux/chrome"))
VIEWPORT = (1280, 800)

# Our own MiniWeb servers. 8200–8211 belong to evaluation runs — never use them.
PORTS = list(range(8300, 8321))
HOST = "localhost"          # not 127.0.0.1 (not a secure context here)

# Coordinate convention of the STUDENT (what the exported actions use).
#   {"mode": "normalized", "scale": 1000}         -> ints in [0, 1000] (Qwen-VL style)
#   {"mode": "pixel", "resolution": [1280, 800]}  -> pixels at that screenshot size
COORD = {"mode": "normalized", "scale": 1000}

# The two macros of the first vertical slice.
SLICE_MACROS = ("filter_by_dropdown", "sort_by_form")
