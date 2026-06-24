"""Session-scoped data overlay for MiniWeb.

Intercepts reads/writes to sites/*/data/*.json so that:
- Writes go to an in-memory session store, never to disk
- Reads check the session store first, fall back to .pristine/ on disk
- Each browser session gets its own isolated copy of mutable state
- The pristine files on disk are never modified during normal operation

This module monkey-patches pathlib.Path.read_text / write_text and
builtins.open at app startup. No site code changes required.
"""

import io
import json
import pathlib
import time
import threading
import builtins
from copy import deepcopy

# ---------------------------------------------------------------------------
# Session store: session_id -> {"files": {path: content}, "last_access": timestamp}
# ---------------------------------------------------------------------------

_stores = {}
_lock = threading.Lock()
_SESSION_TTL = 3600  # seconds — evict sessions idle for 1 hour

# Paths matching this pattern are intercepted
_SITES_DIR = None  # Set by init()


def init(sites_dir: str):
    """Initialize the overlay. Call once at app startup."""
    global _SITES_DIR
    _SITES_DIR = str(pathlib.Path(sites_dir).resolve())
    _patch_pathlib()
    _patch_open()


def _is_data_file(path_str: str) -> bool:
    """Check if a path is a mutable site data file (not pristine, not config)."""
    if _SITES_DIR is None:
        return False
    if not path_str.startswith(_SITES_DIR):
        return False
    rel = path_str[len(_SITES_DIR):]
    parts = rel.split("/")
    if len(parts) < 4:
        return False
    if parts[2] != "data":
        return False
    if ".pristine" in rel:
        return False
    if not path_str.endswith(".json"):
        return False
    return True


def _get_session_id() -> str:
    """Get current session ID, or '_no_session' outside request context."""
    try:
        from flask import session, has_request_context
        if has_request_context():
            sid = session.get("_data_overlay_sid")
            if not sid:
                import uuid
                sid = str(uuid.uuid4())[:12]
                session["_data_overlay_sid"] = sid
            return sid
    except (ImportError, RuntimeError):
        pass
    return "_no_session"


def _get_store(sid: str) -> dict:
    """Get or create the file store for a session. Updates last_access."""
    now = time.time()
    if sid not in _stores:
        with _lock:
            if sid not in _stores:
                _stores[sid] = {"files": {}, "last_access": now}
                _evict_stale()
    entry = _stores[sid]
    entry["last_access"] = now
    return entry["files"]


def _evict_stale():
    """Remove sessions idle longer than TTL. Called under _lock."""
    cutoff = time.time() - _SESSION_TTL
    stale = [sid for sid, entry in _stores.items() if entry["last_access"] < cutoff]
    for sid in stale:
        del _stores[sid]


def reset_session(sid: str = None):
    """Clear a session's overlay (revert to pristine)."""
    if sid is None:
        sid = _get_session_id()
    with _lock:
        _stores.pop(sid, None)


def reset_all():
    """Clear all session overlays."""
    with _lock:
        _stores.clear()


def get_stats() -> dict:
    """Return overlay statistics for debugging."""
    with _lock:
        now = time.time()
        return {
            "sessions": len(_stores),
            "total_files": sum(len(e["files"]) for e in _stores.values()),
            "session_ttl_seconds": _SESSION_TTL,
            "sessions_detail": {
                sid: {
                    "files": len(e["files"]),
                    "idle_seconds": int(now - e["last_access"]),
                }
                for sid, e in _stores.items()
            },
        }


# ---------------------------------------------------------------------------
# Pathlib monkey-patches
# ---------------------------------------------------------------------------

_original_read_text = pathlib.Path.read_text
_original_write_text = pathlib.Path.write_text


def _patched_read_text(self, *args, **kwargs):
    path_str = str(self.resolve())
    if _is_data_file(path_str):
        sid = _get_session_id()
        store = _get_store(sid)
        if path_str in store:
            return store[path_str]
        pristine = self.parent / ".pristine" / self.name
        if pristine.exists():
            return _original_read_text(pristine, *args, **kwargs)
    return _original_read_text(self, *args, **kwargs)


def _patched_write_text(self, data, *args, **kwargs):
    path_str = str(self.resolve())
    if _is_data_file(path_str):
        sid = _get_session_id()
        store = _get_store(sid)
        store[path_str] = data
        return
    return _original_write_text(self, data, *args, **kwargs)


def _patch_pathlib():
    pathlib.Path.read_text = _patched_read_text
    pathlib.Path.write_text = _patched_write_text


# ---------------------------------------------------------------------------
# builtins.open monkey-patch (for sites using open(file, "w") pattern)
# ---------------------------------------------------------------------------

_original_open = builtins.open


def _patched_open(file, mode="r", *args, **kwargs):
    file_str = str(pathlib.Path(file).resolve()) if not isinstance(file, int) else None

    if file_str and _is_data_file(file_str):
        sid = _get_session_id()
        store = _get_store(sid)

        if "w" in mode:
            class _OverlayWriter(io.StringIO):
                def close(self):
                    store[file_str] = self.getvalue()
                    super().close()
                def __enter__(self):
                    return self
                def __exit__(self, *exc):
                    self.close()
                    return False
            return _OverlayWriter()

        elif "r" in mode or mode == "":
            if file_str in store:
                return io.StringIO(store[file_str])
            pristine = pathlib.Path(file).parent / ".pristine" / pathlib.Path(file).name
            if pristine.exists():
                return _original_open(str(pristine), mode, *args, **kwargs)

    return _original_open(file, mode, *args, **kwargs)


def _patch_open():
    builtins.open = _patched_open
