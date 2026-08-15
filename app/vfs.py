"""app/vfs.py — universal simulated filesystem (macOS Finder / Windows Explorer style).

The base "local machine" home directory is a REAL directory on disk
(``filesystem/`` at the repo root by default, override with ``MINIWEB_VFS_DIR``) — edit it,
add folders, drop in your own files and they show up in the explorer immediately
(re-scanned per request; no restart). Per-session user mutations (files the agent
downloads / saves / uploads from any site) live in the session overlay under site
``filesystem``, collection ``files`` — isolated per parallel agent and readable by
verifiers via ``/_admin/data/filesystem/files``.
"""
from __future__ import annotations

import os
import pathlib
import posixpath
import time

from flask import Blueprint, jsonify, request, Response, abort, send_file

from app import db

SITE = "filesystem"
COLLECTION = "files"
_TABLE = "filesystem_files"
_ready = False

# Real on-disk root for the base tree. Committed at data/filesystem/; override via env.
VFS_DIR = pathlib.Path(
    os.environ.get(
        "MINIWEB_VFS_DIR",
        str(pathlib.Path(__file__).resolve().parent.parent / "filesystem"),
    )
)

_MIME = {
    ".pdf": "application/pdf", ".txt": "text/plain", ".csv": "text/csv",
    ".json": "application/json", ".md": "text/markdown",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".svg": "image/svg+xml", ".mp4": "video/mp4",
    ".webm": "video/webm", ".mov": "video/quicktime",
    ".mp3": "audio/mpeg", ".wav": "audio/wav", ".zip": "application/zip",
}

# Favorites sidebar order + icon keys (the client maps these to glyphs).
_FAV_ORDER = ["Desktop", "Documents", "Downloads", "Pictures", "Music", "Movies"]


def _ext(name: str) -> str:
    i = name.rfind(".")
    return name[i:].lower() if i > 0 else ""


def mime_for(name: str) -> str:
    return _MIME.get(_ext(name), "application/octet-stream")


# ── Load the base tree from disk (fresh each call so edits appear live) ───────
def _scan() -> tuple[list[dict], dict]:
    base: list[dict] = []
    if VFS_DIR.exists():
        for p in sorted(VFS_DIR.rglob("*"), key=lambda q: str(q).lower()):
            name = p.name
            if name.startswith("."):        # skip .gitkeep / .DS_Store / dotfiles
                continue
            rel = "/" + str(p.relative_to(VFS_DIR)).replace(os.sep, "/")
            parent = posixpath.dirname(rel) or "/"
            try:
                mtime = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(p.stat().st_mtime))
            except OSError:
                mtime = "2026-01-01T00:00:00"
            if p.is_dir():
                base.append({
                    "id": rel, "path": rel, "parent": parent, "name": name,
                    "kind": "folder", "ext": "", "mime": "inode/directory",
                    "size": 0, "modified": mtime, "content": "", "source": "seed",
                    "_disk": str(p),
                })
                continue
            raw = p.read_bytes()
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = None
            mime = mime_for(name)
            if text is not None and text.lstrip().startswith("<svg"):
                mime = "image/svg+xml"       # .jpg/.png holding SVG markup renders
            base.append({
                "id": rel, "path": rel, "parent": parent, "name": name, "kind": "file",
                "ext": _ext(name), "mime": mime, "size": len(raw), "modified": mtime,
                "content": text if text is not None else "", "source": "seed",
                "_disk": str(p), "_binary": text is None,
            })
    by = {r["path"]: r for r in base}
    return base, by


def _favorites(base: list[dict]) -> list[dict]:
    tops = [r for r in base if r["kind"] == "folder" and r["parent"] == "/"]

    def rank(r):
        n = r["name"]
        return (_FAV_ORDER.index(n) if n in _FAV_ORDER else len(_FAV_ORDER), n.lower())

    tops.sort(key=rank)
    return [{"name": r["name"], "path": r["path"], "icon": r["name"].lower()} for r in tops]


def _public(rec: dict) -> dict:
    return {k: rec[k] for k in ("path", "parent", "name", "kind", "ext",
                                "mime", "size", "modified", "source")}


# ── Persistence plumbing (user mutations → session overlay) ───────────────────
def _ensure():
    """Create + register the (empty) base table so overlay writes are queryable."""
    global _ready
    if _ready and db.get_table_name(SITE, COLLECTION):
        return
    conn = db._get_conn()
    conn.execute(
        f"""CREATE TABLE IF NOT EXISTS [{_TABLE}] (
            id TEXT PRIMARY KEY,
            path TEXT, parent TEXT, name TEXT, kind TEXT,
            ext TEXT, mime TEXT, size INTEGER, modified TEXT,
            content TEXT, source TEXT
        )"""
    )
    conn.commit()
    db.register_table(SITE, COLLECTION, _TABLE, "id")
    _ready = True


def _overlay_all() -> list[dict]:
    _ensure()
    return db.query(SITE, COLLECTION, limit=5000)


def _norm(path: str) -> str:
    if not path:
        return "/"
    return posixpath.normpath("/" + path.strip("/"))


def list_dir(parent: str) -> list[dict]:
    """Folders + files directly under ``parent`` (disk base ∪ overlay; overlay wins)."""
    parent = _norm(parent)
    base, _ = _scan()
    merged: dict[str, dict] = {}
    for r in base:
        if r["parent"] == parent:
            merged[r["path"]] = r
    for r in _overlay_all():
        if r.get("parent") == parent:
            merged[r["path"]] = r
    items = list(merged.values())
    items.sort(key=lambda r: (r["kind"] != "folder", r["name"].lower()))
    return items


def get_file(path: str) -> dict | None:
    path = _norm(path)
    if db.get_table_name(SITE, COLLECTION):
        ov = db.get_item(SITE, COLLECTION, path)
        if ov:
            return ov
    _, by = _scan()
    return by.get(path)


def _folder_exists(parent: str) -> bool:
    parent = _norm(parent)
    if parent == "/":
        return True
    _, by = _scan()
    rec = by.get(parent)
    if rec and rec["kind"] == "folder":
        return True
    return bool(db.get_item(SITE, COLLECTION, parent))


def _ensure_parent_chain(parent: str):
    parent = _norm(parent)
    _, by = _scan()
    cur = ""
    for part in [p for p in parent.split("/") if p]:
        cur = cur + "/" + part
        if cur in by:
            continue
        if db.get_item(SITE, COLLECTION, cur):
            continue
        db.save_item(SITE, COLLECTION, cur, {
            "id": cur, "path": cur, "parent": posixpath.dirname(cur) or "/",
            "name": part, "kind": "folder", "ext": "", "mime": "inode/directory",
            "size": 0, "modified": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "content": "", "source": "user",
        })


def save_file(parent: str, name: str, content: str = "", mime: str = "",
              source: str = "download", content_b64: str = "") -> dict:
    """Write a file into the local FS overlay under ``parent`` (session-isolated).

    Binary downloads (PDFs, images, media) arrive base64-encoded in ``content_b64``
    so their real bytes survive the round-trip; text files use ``content``.
    """
    _ensure()
    parent = _norm(parent)
    _ensure_parent_chain(parent)
    name = (name or "untitled").strip().replace("/", "_")
    path = _norm(posixpath.join(parent, name))
    if content_b64:
        import base64
        try:
            size = len(base64.b64decode(content_b64))
        except Exception:
            size = 0
    else:
        size = len((content or "").encode("utf-8"))
    rec = {
        "id": path, "path": path, "parent": parent, "name": name, "kind": "file",
        "ext": _ext(name), "mime": mime or mime_for(name),
        "size": size, "modified": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "content": content or "", "content_b64": content_b64 or "", "source": source,
    }
    db.save_item(SITE, COLLECTION, path, rec)
    return rec


# ── HTTP surface ─────────────────────────────────────────────────────────────
fs_bp = Blueprint("filesystem", __name__)


@fs_bp.route("/list")
def api_list():
    parent = _norm(request.args.get("path", "/"))
    base, _ = _scan()
    items = list_dir(parent)
    return jsonify({
        "path": parent,
        "favorites": _favorites(base),
        "items": [_public(it) for it in items],
    })


@fs_bp.route("/file")
def api_file():
    rec = get_file(request.args.get("path", ""))
    if not rec:
        abort(404)
    out = _public(rec)
    out["content"] = rec.get("content", "")
    return jsonify(out)


@fs_bp.route("/download")
def api_download():
    rec = get_file(request.args.get("path", ""))
    if not rec or rec["kind"] != "file":
        abort(404)
    # Binary file on disk → stream the real bytes.
    if rec.get("_binary") and rec.get("_disk"):
        return send_file(rec["_disk"], mimetype=rec.get("mime"),
                         as_attachment=True, download_name=rec["name"])
    # Saved binary (base64 in the overlay) → decode to real bytes.
    if rec.get("content_b64"):
        import base64
        try:
            data = base64.b64decode(rec["content_b64"])
        except Exception:
            data = b""
    else:
        data = (rec.get("content") or "").encode("utf-8")
    resp = Response(data, mimetype=rec.get("mime") or "application/octet-stream")
    resp.headers["Content-Disposition"] = f'attachment; filename="{rec["name"]}"'
    resp.headers["Content-Length"] = str(len(data))
    return resp


@fs_bp.route("/save", methods=["POST"])
def api_save():
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    folder = _norm(body.get("folder") or "/Downloads")
    if not name:
        return jsonify({"ok": False, "error": "name required"}), 400
    content = body.get("content") or ""
    content_b64 = body.get("content_b64") or ""
    src = body.get("source_path")
    if src and not content and not content_b64:
        s = get_file(src)
        if s:
            content = s.get("content", "")
            content_b64 = s.get("content_b64", "")
    rec = save_file(folder, name, content, body.get("mime", ""),
                    body.get("origin", "download"), content_b64=content_b64)
    return jsonify({"ok": True, "file": {k: rec[k] for k in ("path", "name", "parent", "mime", "size")}})


@fs_bp.route("/upload", methods=["POST"])
def api_upload():
    body = request.get_json(silent=True) or {}
    rec = get_file(_norm(body.get("path", "")))
    if not rec:
        return jsonify({"ok": False, "error": "not found"}), 404
    return jsonify({"ok": True, "file": {"path": rec["path"], "name": rec["name"],
                                         "mime": rec["mime"], "size": rec["size"]}})


def register_fs_routes(app):
    app.register_blueprint(fs_bp, url_prefix="/_fs")
