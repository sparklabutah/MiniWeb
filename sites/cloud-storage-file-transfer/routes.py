"""MeridianCloud -- cloud storage and file transfer portal (Google Drive / Dropbox style).

Reads JSON data files for files, folders, users, shares, and transfers.
Supports full CRUD, sharing/permissions, starring, trash, folder browsing,
file transfer, and search.  Data files live under data_sources/ and are
reset from .pristine/ between evaluation runs.
"""
import json
import pathlib
from datetime import datetime, timedelta

from flask import (
    Blueprint, Response, abort, jsonify, redirect, render_template,
    request, session, url_for,
)
from app import db
from app.events import emit
from app.handlers.email_handler import _add_email

SITE = "cloud-storage-file-transfer"
SITE_DIR = pathlib.Path(__file__).resolve().parent

# Cross-site "Open In" URLs for files linked to other MiniWeb sites
OPEN_IN_URLS = {
    "documents": "/sites/documents/editor/{source_id}",
    "spreadsheets-slides": "/sites/spreadsheets-slides/spreadsheet/{source_id}",
    "handwritten-notes-whiteboards": "/sites/handwritten-notes-whiteboards/note/{source_id}",
    "code-editor-execution": "/sites/code-editor-execution/editor?snippet_id={source_id}",
    "design-creative": "/sites/design-creative/project/{source_id}",
    "insurance-loans": "/sites/insurance-loans/",
    "tax-filing-dmv-permits": "/sites/tax-filing-dmv-permits/",
}
# Presentations use a different URL pattern than spreadsheets
OPEN_IN_PRESENTATION_URL = "/sites/spreadsheets-slides/presentation/{source_id}"

OPEN_IN_LABELS = {
    "documents": "DocEdit",
    "spreadsheets-slides": "SheetDeck",
    "handwritten-notes-whiteboards": "NotePad",
    "code-editor-execution": "CodeRunner",
    "design-creative": "CanvasStudio",
    "insurance-loans": "Cascadia Insurance",
    "tax-filing-dmv-permits": "Tax Filing",
}

blueprint = Blueprint(
    "cloud-storage-file-transfer",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _load_files(user_id=None, folder_id=None):
    where = {}
    if user_id is not None:
        where["user_id"] = user_id
    if folder_id is not None:
        where["folder_id"] = folder_id
    return db.query(SITE, "files", where=where if where else None)


def _save_files(files):
    db.save_collection(SITE, "files", files)


def _load_folders(user_id=None, parent_id=None):
    where = {}
    if user_id is not None:
        where["user_id"] = user_id
    if parent_id is not None:
        where["parent_id"] = parent_id
    return db.query(SITE, "folders", where=where if where else None)


def _save_folders(folders):
    db.save_collection(SITE, "folders", folders)


def _load_users():
    return db.query(SITE, "users")


def _load_shares(user_id=None):
    where = {"user_id": user_id} if user_id is not None else None
    return db.query(SITE, "shares", where=where)


def _save_shares(shares):
    db.save_collection(SITE, "shares", shares)


def _load_transfers(user_id=None):
    where = {"user_id": user_id} if user_id is not None else None
    return db.query(SITE, "transfers", where=where)


def _save_transfers(transfers):
    db.save_collection(SITE, "transfers", transfers)


# ---------------------------------------------------------------------------
# User / auth helpers
# ---------------------------------------------------------------------------

def _get_user(user_id):
    return db.get_item(SITE, "users", user_id)


def _current_user():
    if "user_id" in session:
        return _get_user(session["user_id"])
    return None


def _format_size(size_bytes):
    """Human-readable file size."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def _file_icon(file_type):
    """Return an icon/emoji for a file type."""
    icons = {
        "document": "&#128196;",
        "image": "&#128444;",
        "spreadsheet": "&#128202;",
        "presentation": "&#128218;",
        "archive": "&#128230;",
        "code": "&#128187;",
    }
    return icons.get(file_type, "&#128196;")


def _get_folder_path(folder_id, folders):
    """Build the breadcrumb path for a folder."""
    path_parts = []
    current = next((f for f in folders if f["id"] == folder_id), None)
    while current:
        path_parts.insert(0, current)
        if current["parent_id"]:
            current = next((f for f in folders if f["id"] == current["parent_id"]), None)
        else:
            current = None
    return path_parts


def _get_subfolders(folder_id, folders):
    """Get immediate children of a folder."""
    return [f for f in folders if f["parent_id"] == folder_id]


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    """File browser -- shows root folders and recent files.

    Supports ?view= parameter: drive (default), starred, recent, shared, trash.
    """
    user = _current_user()
    files = _load_files()
    folders = _load_folders()
    users = _load_users()
    user_map = {u["id"]: u for u in users}

    q = request.args.get("q", "").strip()
    sort = request.args.get("sort", "modified").strip()
    type_filter = request.args.get("type", "").strip()
    view = request.args.get("view", "drive").strip()

    # Filter by view
    if view == "starred":
        visible = [f for f in files if f.get("starred") and not f.get("is_trashed")]
        page_title = "Starred"
    elif view == "recent":
        visible = [f for f in files if not f.get("is_trashed")]
        visible.sort(key=lambda f: f.get("modified_at", ""), reverse=True)
        visible = visible[:20]
        page_title = "Recent"
    elif view == "shared":
        shares = _load_shares()
        shared_ids = {s["file_id"] for s in shares}
        visible = [f for f in files if f["id"] in shared_ids and not f.get("is_trashed")]
        page_title = "Shared with me"
    elif view == "trash":
        visible = [f for f in files if f.get("is_trashed")]
        page_title = "Trash"
    else:
        visible = [f for f in files if not f.get("is_trashed")]
        page_title = "My Drive"

    if q:
        ql = q.lower()
        visible = [f for f in visible if ql in f["name"].lower() or ql in f.get("path", "").lower()]

    if type_filter:
        visible = [f for f in visible if f["type"] == type_filter]

    # Date range filtering
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    if date_from:
        visible = [f for f in visible if f.get("modified_at", "") >= date_from]
    if date_to:
        date_to_full = date_to + "T23:59:59Z" if len(date_to) == 10 else date_to
        visible = [f for f in visible if f.get("modified_at", "") <= date_to_full]

    # Sorting
    if sort == "name":
        visible.sort(key=lambda f: f["name"].lower())
    elif sort == "size":
        visible.sort(key=lambda f: f["size_bytes"], reverse=True)
    elif sort == "created":
        visible.sort(key=lambda f: f.get("created_at", ""), reverse=True)
    elif view != "recent":  # recent already sorted
        visible.sort(key=lambda f: f.get("modified_at", ""), reverse=True)

    # Root folders (parent_id == null or 0) — only for drive view
    root_folders = [f for f in folders if not f["parent_id"]] if view == "drive" else []

    return render_template(
        "cloud-storage-file-transfer/index.html",
        files=visible, folders=folders, root_folders=root_folders,
        user=user, user_map=user_map, users=users,
        q=q, sort=sort, type_filter=type_filter,
        view=view, page_title=page_title,
        format_size=_format_size, file_icon=_file_icon,
        open_in_urls=OPEN_IN_URLS,
        open_in_presentation_url=OPEN_IN_PRESENTATION_URL,
        open_in_labels=OPEN_IN_LABELS,
    )


@blueprint.route("/folder/<int:folder_id>")
def folder_view(folder_id):
    """Show files and subfolders in a specific folder."""
    folders = _load_folders()
    folder = next((f for f in folders if f["id"] == folder_id), None)
    if folder is None:
        abort(404)

    user = _current_user()
    files = _load_files()
    users = _load_users()
    user_map = {u["id"]: u for u in users}

    # Files in this folder
    folder_files = [f for f in files if f.get("folder_id") == folder_id
                    and not f.get("is_trashed", False)]
    folder_files.sort(key=lambda f: f.get("modified_at", ""), reverse=True)

    # Subfolders
    subfolders = _get_subfolders(folder_id, folders)

    # Breadcrumb path
    breadcrumb = _get_folder_path(folder_id, folders)

    return render_template(
        "cloud-storage-file-transfer/folder.html",
        folder=folder, files=folder_files, subfolders=subfolders,
        breadcrumb=breadcrumb, user=user, user_map=user_map,
        folders=folders, format_size=_format_size, file_icon=_file_icon,
        open_in_urls=OPEN_IN_URLS,
        open_in_presentation_url=OPEN_IN_PRESENTATION_URL,
        open_in_labels=OPEN_IN_LABELS,
    )


@blueprint.route("/file/<int:file_id>")
def file_detail(file_id):
    """File detail/preview page."""
    files = _load_files()
    file = next((f for f in files if f["id"] == file_id), None)
    if file is None:
        abort(404)

    user = _current_user()
    users = _load_users()
    user_map = {u["id"]: u for u in users}
    folders = _load_folders()
    shares = _load_shares()
    transfers = _load_transfers()

    # Shares for this file
    file_shares = [s for s in shares if s["file_id"] == file_id]
    # Transfers for this file
    file_transfers = [t for t in transfers if t["file_id"] == file_id]

    # Breadcrumb
    breadcrumb = []
    if file.get("folder_id"):
        breadcrumb = _get_folder_path(file["folder_id"], folders)

    return render_template(
        "cloud-storage-file-transfer/file_detail.html",
        file=file, user=user, user_map=user_map, folders=folders,
        shares=file_shares, transfers=file_transfers,
        breadcrumb=breadcrumb, format_size=_format_size, file_icon=_file_icon,
        open_in_urls=OPEN_IN_URLS,
        open_in_presentation_url=OPEN_IN_PRESENTATION_URL,
        open_in_labels=OPEN_IN_LABELS,
    )


@blueprint.route("/shared")
def shared():
    return redirect(url_for("cloud-storage-file-transfer.index", view="shared"))


@blueprint.route("/recent")
def recent():
    return redirect(url_for("cloud-storage-file-transfer.index", view="recent"))


@blueprint.route("/starred")
def starred():
    return redirect(url_for("cloud-storage-file-transfer.index", view="starred"))


@blueprint.route("/trash")
def trash():
    return redirect(url_for("cloud-storage-file-transfer.index", view="trash"))


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("cloud-storage-file-transfer/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username and u["password"] == password), None)
    if user:
        session["user_id"] = user["id"]
        emit("signup", user_id=user["id"], site_name="cloud-storage-file-transfer", username=request.form.get("username", ""), password=request.form.get("password", ""), email="")
        return redirect(url_for("cloud-storage-file-transfer.index"))
    return render_template("cloud-storage-file-transfer/login.html",
                           error="Invalid username or password.")


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("cloud-storage-file-transfer.index"))


# ---------------------------------------------------------------------------
# API routes -- Files
# ---------------------------------------------------------------------------

@blueprint.route("/api/files", methods=["GET"])
def api_files_list():
    """List files with optional filtering."""
    files = _load_files()
    files = [f for f in files if not f.get("is_trashed", False)]

    # Filters
    type_filter = request.args.get("type")
    folder_id = request.args.get("folder_id", type=int)
    owner_id = request.args.get("owner_id", type=int)
    starred = request.args.get("starred")

    if type_filter:
        files = [f for f in files if f["type"] == type_filter]
    if folder_id is not None:
        files = [f for f in files if f.get("folder_id") == folder_id]
    if owner_id is not None:
        files = [f for f in files if f["owner_id"] == owner_id]
    if starred is not None:
        starred_bool = starred.lower() in ("true", "1", "yes")
        files = [f for f in files if f.get("starred", False) == starred_bool]

    sort = request.args.get("sort", "modified")
    if sort == "name":
        files.sort(key=lambda f: f["name"].lower())
    elif sort == "size":
        files.sort(key=lambda f: f["size_bytes"], reverse=True)
    elif sort == "created":
        files.sort(key=lambda f: f.get("created_at", ""), reverse=True)
    else:
        files.sort(key=lambda f: f.get("modified_at", ""), reverse=True)

    return jsonify(files)


@blueprint.route("/api/files", methods=["POST"])
def api_files_create():
    """Create a new file."""
    data = request.get_json(force=True)
    files = _load_files()

    new_id = max((f["id"] for f in files), default=0) + 1
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    new_file = {
        "id": new_id,
        "name": data.get("name", "Untitled"),
        "path": data.get("path", f"/{data.get('name', 'Untitled')}"),
        "size_bytes": data.get("size_bytes", 0),
        "type": data.get("type", "document"),
        "mime_type": data.get("mime_type", "application/octet-stream"),
        "owner_id": data.get("owner_id", 1),
        "created_at": now,
        "modified_at": now,
        "shared_with": data.get("shared_with", []),
        "folder_id": data.get("folder_id"),
        "starred": data.get("starred", False),
        "is_trashed": False,
    }

    files.append(new_file)
    _save_files(files)
    return jsonify(new_file), 201


@blueprint.route("/api/files/<int:file_id>", methods=["GET"])
def api_file_get(file_id):
    """Get a single file."""
    files = _load_files()
    file = next((f for f in files if f["id"] == file_id), None)
    if file is None:
        return jsonify({"error": "File not found"}), 404
    return jsonify(file)


@blueprint.route("/api/files/<int:file_id>", methods=["PUT"])
def api_file_update(file_id):
    """Update a file's metadata."""
    data = request.get_json(force=True)
    files = _load_files()
    file = next((f for f in files if f["id"] == file_id), None)
    if file is None:
        return jsonify({"error": "File not found"}), 404

    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    updatable = ["name", "path", "size_bytes", "type", "mime_type",
                 "shared_with", "folder_id", "starred", "is_trashed"]
    for key in updatable:
        if key in data:
            file[key] = data[key]
    file["modified_at"] = now

    _save_files(files)
    return jsonify(file)


@blueprint.route("/api/files/<int:file_id>", methods=["DELETE"])
def api_file_delete(file_id):
    """Move a file to trash (soft delete) or permanently delete if already trashed."""
    files = _load_files()
    file = next((f for f in files if f["id"] == file_id), None)
    if file is None:
        return jsonify({"error": "File not found"}), 404

    if file.get("is_trashed", False):
        # Permanent delete
        files = [f for f in files if f["id"] != file_id]
        _save_files(files)
        return jsonify({"message": "File permanently deleted"})
    else:
        # Soft delete (move to trash)
        file["is_trashed"] = True
        file["modified_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        _save_files(files)
        return jsonify(file)


# ---------------------------------------------------------------------------
# API routes -- Folders
# ---------------------------------------------------------------------------

@blueprint.route("/api/folders", methods=["GET"])
def api_folders_list():
    """List all folders."""
    folders = _load_folders()
    parent_id = request.args.get("parent_id")
    if parent_id is not None:
        if parent_id == "null" or parent_id == "":
            folders = [f for f in folders if f["parent_id"] is None]
        else:
            try:
                pid = int(parent_id)
                folders = [f for f in folders if f["parent_id"] == pid]
            except ValueError:
                pass
    return jsonify(folders)


@blueprint.route("/api/folders", methods=["POST"])
def api_folders_create():
    """Create a new folder."""
    data = request.get_json(force=True)
    folders = _load_folders()

    new_id = max((f["id"] for f in folders), default=0) + 1
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    new_folder = {
        "id": new_id,
        "name": data.get("name", "New Folder"),
        "parent_id": data.get("parent_id"),
        "owner_id": data.get("owner_id", 1),
        "created_at": now,
        "color": data.get("color", "#4285F4"),
    }

    folders.append(new_folder)
    _save_folders(folders)
    return jsonify(new_folder), 201


@blueprint.route("/api/folders/<int:folder_id>", methods=["GET"])
def api_folder_get(folder_id):
    """Get a single folder with its contents."""
    folders = _load_folders()
    folder = next((f for f in folders if f["id"] == folder_id), None)
    if folder is None:
        return jsonify({"error": "Folder not found"}), 404

    files = _load_files()
    folder_files = [f for f in files if f.get("folder_id") == folder_id
                    and not f.get("is_trashed", False)]
    subfolders = [f for f in folders if f["parent_id"] == folder_id]

    result = dict(folder)
    result["files"] = folder_files
    result["subfolders"] = subfolders
    return jsonify(result)


@blueprint.route("/api/folders/<int:folder_id>", methods=["PUT"])
def api_folder_update(folder_id):
    """Update a folder."""
    data = request.get_json(force=True)
    folders = _load_folders()
    folder = next((f for f in folders if f["id"] == folder_id), None)
    if folder is None:
        return jsonify({"error": "Folder not found"}), 404

    for key in ["name", "parent_id", "color"]:
        if key in data:
            folder[key] = data[key]

    _save_folders(folders)
    return jsonify(folder)


@blueprint.route("/api/folders/<int:folder_id>", methods=["DELETE"])
def api_folder_delete(folder_id):
    """Delete a folder (must be empty)."""
    folders = _load_folders()
    files = _load_files()

    folder = next((f for f in folders if f["id"] == folder_id), None)
    if folder is None:
        return jsonify({"error": "Folder not found"}), 404

    # Check for subfolders
    subfolders = [f for f in folders if f["parent_id"] == folder_id]
    if subfolders:
        return jsonify({"error": "Folder is not empty (has subfolders)"}), 400

    # Check for files
    folder_files = [f for f in files if f.get("folder_id") == folder_id]
    if folder_files:
        return jsonify({"error": "Folder is not empty (has files)"}), 400

    folders = [f for f in folders if f["id"] != folder_id]
    _save_folders(folders)
    return jsonify({"message": "Folder deleted"})


# ---------------------------------------------------------------------------
# API routes -- Shares
# ---------------------------------------------------------------------------

@blueprint.route("/api/shares", methods=["GET"])
def api_shares_list():
    """List shares, optionally filtered by file_id."""
    shares = _load_shares()
    file_id = request.args.get("file_id", type=int)
    if file_id is not None:
        shares = [s for s in shares if s["file_id"] == file_id]
    return jsonify(shares)


@blueprint.route("/api/shares", methods=["POST"])
def api_shares_create():
    """Create a new share."""
    data = request.get_json(force=True)
    shares = _load_shares()

    new_id = max((s["id"] for s in shares), default=0) + 1
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    new_share = {
        "id": new_id,
        "file_id": data["file_id"],
        "shared_by": data.get("shared_by", 1),
        "shared_with": data.get("shared_with"),
        "permission": data.get("permission", "view"),
        "created_at": now,
        "link": data.get("link"),
    }

    shares.append(new_share)
    _save_shares(shares)
    _add_email(new_share.get("shared_with", 1) or 1, "noreply@cloud-storage.lakeport.local",
               "A file was shared with you",
               "A file has been shared with you on MeridianCloud. Log in to view it.")

    # Also update the file's shared_with list if sharing with a user
    if new_share["shared_with"] is not None:
        files = _load_files()
        file = next((f for f in files if f["id"] == new_share["file_id"]), None)
        if file and new_share["shared_with"] not in file.get("shared_with", []):
            file.setdefault("shared_with", []).append(new_share["shared_with"])
            _save_files(files)

    return jsonify(new_share), 201


@blueprint.route("/api/shares/<int:share_id>", methods=["DELETE"])
def api_share_delete(share_id):
    """Remove a share."""
    shares = _load_shares()
    share = next((s for s in shares if s["id"] == share_id), None)
    if share is None:
        return jsonify({"error": "Share not found"}), 404

    shares = [s for s in shares if s["id"] != share_id]
    _save_shares(shares)
    return jsonify({"message": "Share removed"})


# ---------------------------------------------------------------------------
# API routes -- Transfers
# ---------------------------------------------------------------------------

@blueprint.route("/api/transfers", methods=["GET"])
def api_transfers_list():
    """List file transfers."""
    transfers = _load_transfers()
    status_filter = request.args.get("status")
    if status_filter:
        transfers = [t for t in transfers if t["status"] == status_filter]
    return jsonify(transfers)


@blueprint.route("/api/transfers", methods=["POST"])
def api_transfers_create():
    """Create a new file transfer."""
    data = request.get_json(force=True)
    transfers = _load_transfers()

    new_id = max((t["id"] for t in transfers), default=0) + 1
    now = datetime.utcnow()
    expires = now + timedelta(days=data.get("expires_days", 7))

    new_transfer = {
        "id": new_id,
        "file_id": data["file_id"],
        "sender_id": data.get("sender_id", 1),
        "recipient_email": data["recipient_email"],
        "status": "active",
        "created_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": expires.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "download_count": 0,
    }

    transfers.append(new_transfer)
    _save_transfers(transfers)
    return jsonify(new_transfer), 201


# ---------------------------------------------------------------------------
# API routes -- Search, Storage, Stats
# ---------------------------------------------------------------------------

@blueprint.route("/api/search")
def api_search():
    """Search files by name or path."""
    q = request.args.get("q", "").strip().lower()
    if not q:
        return jsonify([])

    files = _load_files()
    results = [f for f in files
               if not f.get("is_trashed", False)
               and (q in f["name"].lower() or q in f.get("path", "").lower())]
    results.sort(key=lambda f: f.get("modified_at", ""), reverse=True)
    return jsonify(results)


def _semantic_score(query, file):
    """Score a file against a query using weighted keyword matching."""
    terms = query.lower().split()
    name_lower = file["name"].lower()
    path_lower = file.get("path", "").lower()
    type_lower = file.get("type", "").lower()
    mime_lower = file.get("mime_type", "").lower()
    text = name_lower + " " + path_lower + " " + type_lower + " " + mime_lower
    score = 0
    for t in terms:
        if t in name_lower:
            score += 3  # name matches weighted heavily
        if t in path_lower:
            score += 1
        if t in type_lower:
            score += 2
        if t in mime_lower:
            score += 1
    return score


@blueprint.route("/api/search/semantic")
def api_search_semantic():
    """Semantic/fuzzy search files by relevance-scored keyword matching."""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    files = _load_files()
    active = [f for f in files if not f.get("is_trashed", False)]
    scored = [(f, _semantic_score(q, f)) for f in active]
    scored = [(f, s) for f, s in scored if s > 0]
    scored.sort(key=lambda x: -x[1])
    # Limit to top 10 most relevant results to avoid returning all files
    top_results = scored[:10]
    return jsonify([f for f, _ in top_results])


@blueprint.route("/api/storage-usage")
def api_storage_usage():
    """Storage usage summary."""
    files = _load_files()
    users = _load_users()
    active_files = [f for f in files if not f.get("is_trashed", False)]

    total_size = sum(f["size_bytes"] for f in active_files)
    by_type = {}
    for f in active_files:
        t = f["type"]
        by_type[t] = by_type.get(t, 0) + f["size_bytes"]

    by_user = {}
    for f in active_files:
        uid = f["owner_id"]
        by_user[uid] = by_user.get(uid, 0) + f["size_bytes"]

    user_map = {u["id"]: u["name"] for u in users}
    user_usage = []
    for uid, size in sorted(by_user.items(), key=lambda x: x[1], reverse=True):
        u = next((u for u in users if u["id"] == uid), None)
        user_usage.append({
            "user_id": uid,
            "name": user_map.get(uid, "Unknown"),
            "bytes": size,
            "human": _format_size(size),
            "quota_gb": u["storage_quota_gb"] if u else 50,
        })

    return jsonify({
        "total_bytes": total_size,
        "total_human": _format_size(total_size),
        "file_count": len(active_files),
        "by_type": {t: {"bytes": s, "human": _format_size(s)} for t, s in by_type.items()},
        "by_user": user_usage,
    })


@blueprint.route("/api/stats")
def api_stats():
    """Dashboard statistics."""
    files = _load_files()
    folders = _load_folders()
    shares = _load_shares()
    transfers = _load_transfers()

    active_files = [f for f in files if not f.get("is_trashed", False)]
    trashed_files = [f for f in files if f.get("is_trashed", False)]

    return jsonify({
        "total_files": len(active_files),
        "total_folders": len(folders),
        "total_shares": len(shares),
        "total_transfers": len(transfers),
        "trashed_files": len(trashed_files),
        "starred_files": sum(1 for f in active_files if f.get("starred", False)),
        "total_storage_bytes": sum(f["size_bytes"] for f in active_files),
        "total_storage_human": _format_size(sum(f["size_bytes"] for f in active_files)),
        "active_transfers": sum(1 for t in transfers if t["status"] == "active"),
        "files_by_type": {
            t: sum(1 for f in active_files if f["type"] == t)
            for t in set(f["type"] for f in active_files)
        },
    })


# ---------------------------------------------------------------------------
# API routes -- Date range filtering
# ---------------------------------------------------------------------------

@blueprint.route("/api/files/by-date")
def api_files_by_date():
    """List files filtered by creation/modification date range."""
    files = _load_files()
    active = [f for f in files if not f.get("is_trashed", False)]

    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    date_field = request.args.get("date_field", "modified_at").strip()

    if date_from:
        active = [f for f in active if f.get(date_field, "") >= date_from]
    if date_to:
        # Include the full day
        if len(date_to) == 10:
            date_to_full = date_to + "T23:59:59Z"
        else:
            date_to_full = date_to
        active = [f for f in active if f.get(date_field, "") <= date_to_full]

    active.sort(key=lambda f: f.get(date_field, ""), reverse=True)
    return jsonify(active)


# ---------------------------------------------------------------------------
# API routes -- Starred toggle (save_by_toggle / configure_by_toggle)
# ---------------------------------------------------------------------------

@blueprint.route("/api/files/<int:file_id>/star", methods=["POST"])
def api_file_star_toggle(file_id):
    """Toggle the starred status of a file."""
    files = _load_files()
    file = next((f for f in files if f["id"] == file_id), None)
    if file is None:
        return jsonify({"error": "File not found"}), 404

    file["starred"] = not file.get("starred", False)
    file["modified_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    _save_files(files)
    return jsonify({"file_id": file_id, "starred": file["starred"],
                    "action": "starred" if file["starred"] else "unstarred"})


@blueprint.route("/file/<int:file_id>/delete", methods=["POST"])
def form_file_delete(file_id):
    """Form-based delete (move to trash) for browser automation."""
    files = _load_files()
    file = next((f for f in files if f["id"] == file_id), None)
    if file is None:
        abort(404)
    if file.get("is_trashed", False):
        # Permanent delete
        files = [f for f in files if f["id"] != file_id]
        _save_files(files)
        return redirect(url_for("cloud-storage-file-transfer.trash"))
    else:
        file["is_trashed"] = True
        file["modified_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        _save_files(files)
        return redirect(url_for("cloud-storage-file-transfer.index"))


@blueprint.route("/file/<int:file_id>/invite", methods=["POST"])
def form_invite_to_file(file_id):
    """Invite a user to access a file via form POST."""
    email = request.form.get("email", "").strip()
    if email:
        shares = _load_shares()
        new_id = max((s["id"] for s in shares), default=0) + 1
        shares.append({
            "id": new_id,
            "file_id": file_id,
            "shared_with": None,
            "shared_by": session.get("user_id", 1),
            "permission": "view",
            "link": "",
            "created_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "invited_email": email,
        })
        _save_shares(shares)
    return redirect(url_for("cloud-storage-file-transfer.file_detail", file_id=file_id))


@blueprint.route("/file/<int:file_id>/star", methods=["POST"])
def form_file_star_toggle(file_id):
    """Form-based toggle star for browser automation."""
    files = _load_files()
    file = next((f for f in files if f["id"] == file_id), None)
    if file is None:
        abort(404)
    file["starred"] = not file.get("starred", False)
    file["modified_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    _save_files(files)
    return redirect(url_for("cloud-storage-file-transfer.file_detail", file_id=file_id))


# ---------------------------------------------------------------------------
# API routes -- Move file to folder (edit_by_drag)
# ---------------------------------------------------------------------------

@blueprint.route("/api/files/<int:file_id>/move", methods=["POST"])
def api_file_move(file_id):
    """Move a file to a different folder (simulates drag-and-drop)."""
    data = request.get_json(force=True)
    target_folder_id = data.get("folder_id")

    files = _load_files()
    file = next((f for f in files if f["id"] == file_id), None)
    if file is None:
        return jsonify({"error": "File not found"}), 404

    # Validate target folder exists (if not moving to root)
    if target_folder_id is not None:
        folders = _load_folders()
        target = next((f for f in folders if f["id"] == target_folder_id), None)
        if target is None:
            return jsonify({"error": "Target folder not found"}), 404

    old_folder = file.get("folder_id")
    file["folder_id"] = target_folder_id
    file["modified_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    # Update path to reflect new location
    if target_folder_id is not None:
        folders = _load_folders()
        path_parts = _get_folder_path(target_folder_id, folders)
        folder_path = "/" + "/".join(f["name"] for f in path_parts)
        file["path"] = folder_path + "/" + file["name"]
    else:
        file["path"] = "/" + file["name"]

    _save_files(files)
    return jsonify({"file_id": file_id, "old_folder_id": old_folder,
                    "new_folder_id": target_folder_id, "new_path": file["path"]})


# ---------------------------------------------------------------------------
# API routes -- Storage quota / compute_by_slider
# ---------------------------------------------------------------------------

@blueprint.route("/api/storage-quota")
def api_storage_quota():
    """Compute storage usage relative to a configurable quota limit (slider).
    Pass ?quota_gb=N to see how usage compares to an N GB quota."""
    files = _load_files()
    users = _load_users()
    active_files = [f for f in files if not f.get("is_trashed", False)]

    quota_gb = request.args.get("quota_gb", type=float, default=50.0)
    user_id = request.args.get("user_id", type=int)

    if user_id is not None:
        relevant = [f for f in active_files if f["owner_id"] == user_id]
    else:
        relevant = active_files

    used_bytes = sum(f["size_bytes"] for f in relevant)
    quota_bytes = int(quota_gb * 1024 * 1024 * 1024)
    remaining = quota_bytes - used_bytes
    pct_used = round((used_bytes / quota_bytes) * 100, 2) if quota_bytes > 0 else 0

    return jsonify({
        "quota_gb": quota_gb,
        "quota_bytes": quota_bytes,
        "used_bytes": used_bytes,
        "used_human": _format_size(used_bytes),
        "remaining_bytes": max(remaining, 0),
        "remaining_human": _format_size(max(remaining, 0)),
        "percent_used": pct_used,
        "file_count": len(relevant),
        "over_quota": used_bytes > quota_bytes,
    })


# ---------------------------------------------------------------------------
# API routes -- Export (export_by_dropdown)
# ---------------------------------------------------------------------------

@blueprint.route("/api/export")
def api_export():
    """Export file listing in JSON or CSV format, optionally filtered by type."""
    fmt = request.args.get("format", "json").lower()
    type_filter = request.args.get("type", "").strip()
    folder_id = request.args.get("folder_id", type=int)

    files = _load_files()
    active = [f for f in files if not f.get("is_trashed", False)]

    if type_filter:
        active = [f for f in active if f["type"] == type_filter]
    if folder_id is not None:
        active = [f for f in active if f.get("folder_id") == folder_id]

    if fmt == "csv":
        lines = ["id,name,type,size_bytes,owner_id,folder_id,created_at,modified_at,starred"]
        for f in active:
            name = f["name"].replace('"', '""')
            lines.append(
                f'{f["id"]},"{name}","{f["type"]}",{f["size_bytes"]},{f["owner_id"]},'
                f'{f.get("folder_id", "")},{f["created_at"]},{f["modified_at"]},{f.get("starred", False)}'
            )
        return Response("\n".join(lines), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=files.csv"})
    return jsonify(active)


# ---------------------------------------------------------------------------
# API routes -- Upload (upload_from_table / upload_by_route)
# ---------------------------------------------------------------------------

@blueprint.route("/api/upload", methods=["POST"])
def api_upload():
    """Upload a file (simulated -- creates a file entry with metadata).
    Accepts JSON with name, type, size_bytes, folder_id, owner_id."""
    data = request.get_json(force=True)
    files = _load_files()

    new_id = max((f["id"] for f in files), default=0) + 1
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    name = data.get("name", "uploaded_file")
    folder_id = data.get("folder_id")
    path = "/" + name
    if folder_id is not None:
        folders = _load_folders()
        path_parts = _get_folder_path(folder_id, folders)
        if path_parts:
            folder_path = "/" + "/".join(f["name"] for f in path_parts)
            path = folder_path + "/" + name

    new_file = {
        "id": new_id,
        "name": name,
        "path": path,
        "size_bytes": data.get("size_bytes", 0),
        "type": data.get("type", "document"),
        "mime_type": data.get("mime_type", "application/octet-stream"),
        "owner_id": data.get("owner_id", 1),
        "created_at": now,
        "modified_at": now,
        "shared_with": [],
        "folder_id": folder_id,
        "starred": False,
        "is_trashed": False,
    }

    files.append(new_file)
    _save_files(files)
    return jsonify(new_file), 201


@blueprint.route("/upload/<int:folder_id>", methods=["POST"])
def form_upload_to_folder(folder_id):
    """Form-based upload to a specific folder (upload_by_route)."""
    name = request.form.get("name", "uploaded_file").strip()
    file_type = request.form.get("type", "document").strip()
    size_bytes = int(request.form.get("size_bytes", "0"))

    files = _load_files()
    new_id = max((f["id"] for f in files), default=0) + 1
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    folders = _load_folders()
    path_parts = _get_folder_path(folder_id, folders)
    folder_path = "/" + "/".join(f["name"] for f in path_parts) if path_parts else ""
    path = folder_path + "/" + name

    new_file = {
        "id": new_id,
        "name": name,
        "path": path,
        "size_bytes": size_bytes,
        "type": file_type,
        "mime_type": "application/octet-stream",
        "owner_id": session.get("user_id", 1),
        "created_at": now,
        "modified_at": now,
        "shared_with": [],
        "folder_id": folder_id,
        "starred": False,
        "is_trashed": False,
    }

    files.append(new_file)
    _save_files(files)
    return redirect(url_for("cloud-storage-file-transfer.folder_view", folder_id=folder_id))


# ---------------------------------------------------------------------------
# API routes -- Share by query / share by dropdown
# ---------------------------------------------------------------------------

@blueprint.route("/api/users/search")
def api_users_search():
    """Search users by name or email (share_by_query)."""
    q = request.args.get("q", "").strip().lower()
    users = _load_users()
    if not q:
        return jsonify([{k: v for k, v in u.items() if k != "password"} for u in users])
    results = [u for u in users if q in u["name"].lower() or q in u["email"].lower()
               or q in u["username"].lower()]
    return jsonify([{k: v for k, v in u.items() if k != "password"} for u in results])


@blueprint.route("/api/shares/<int:share_id>/permission", methods=["PUT"])
def api_share_update_permission(share_id):
    """Update share permission level (share_by_dropdown)."""
    data = request.get_json(force=True)
    permission = data.get("permission", "view")
    if permission not in ("view", "edit", "admin"):
        return jsonify({"error": "Invalid permission. Must be view, edit, or admin."}), 400

    shares = _load_shares()
    share = next((s for s in shares if s["id"] == share_id), None)
    if share is None:
        return jsonify({"error": "Share not found"}), 404

    old_perm = share["permission"]
    share["permission"] = permission
    _save_shares(shares)
    return jsonify({"share_id": share_id, "old_permission": old_perm,
                    "new_permission": permission})


# ---------------------------------------------------------------------------
# API routes -- Invite collaborator (invite_by_form)
# ---------------------------------------------------------------------------

@blueprint.route("/api/invite", methods=["POST"])
def api_invite():
    """Invite an external collaborator by email to a file or folder."""
    data = request.get_json(force=True)
    email = data.get("email", "").strip()
    file_id = data.get("file_id")
    permission = data.get("permission", "view")
    message = data.get("message", "")

    if not email:
        return jsonify({"error": "Email is required"}), 400
    if file_id is None:
        return jsonify({"error": "file_id is required"}), 400

    files = _load_files()
    file = next((f for f in files if f["id"] == file_id), None)
    if file is None:
        return jsonify({"error": "File not found"}), 404

    # Check if user exists
    users = _load_users()
    existing_user = next((u for u in users if u["email"] == email), None)

    # Create a share
    shares = _load_shares()
    new_id = max((s["id"] for s in shares), default=0) + 1
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    new_share = {
        "id": new_id,
        "file_id": file_id,
        "shared_by": data.get("sender_id", session.get("user_id", 1)),
        "shared_with": existing_user["id"] if existing_user else None,
        "permission": permission,
        "created_at": now,
        "link": None,
        "invited_email": email,
        "invite_message": message,
    }

    shares.append(new_share)
    _save_shares(shares)

    return jsonify({
        "invite_id": new_id,
        "email": email,
        "file_id": file_id,
        "permission": permission,
        "user_found": existing_user is not None,
        "message": message,
    }), 201


@blueprint.route("/file/<int:file_id>/invite", methods=["POST"])
def form_invite(file_id):
    """Form-based invite collaborator."""
    email = request.form.get("email", "").strip()
    permission = request.form.get("permission", "view")
    message = request.form.get("message", "")

    if not email:
        return redirect(url_for("cloud-storage-file-transfer.file_detail", file_id=file_id))

    files = _load_files()
    file = next((f for f in files if f["id"] == file_id), None)
    if file is None:
        abort(404)

    users = _load_users()
    existing_user = next((u for u in users if u["email"] == email), None)

    shares = _load_shares()
    new_id = max((s["id"] for s in shares), default=0) + 1
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    new_share = {
        "id": new_id,
        "file_id": file_id,
        "shared_by": session.get("user_id", 1),
        "shared_with": existing_user["id"] if existing_user else None,
        "permission": permission,
        "created_at": now,
        "link": None,
        "invited_email": email,
        "invite_message": message,
    }
    shares.append(new_share)
    _save_shares(shares)

    return redirect(url_for("cloud-storage-file-transfer.file_detail", file_id=file_id))


# ---------------------------------------------------------------------------
# API routes -- User settings / configure_by_toggle
# ---------------------------------------------------------------------------

@blueprint.route("/api/users/<int:user_id>/settings", methods=["GET"])
def api_user_settings(user_id):
    """Get user settings."""
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        return jsonify({"error": "User not found"}), 404
    settings = user.get("settings", {
        "notifications_enabled": True,
        "auto_backup": True,
        "dark_mode": False,
        "public_profile": False,
    })
    return jsonify({"user_id": user_id, "settings": settings})


@blueprint.route("/api/users/<int:user_id>/settings", methods=["PUT"])
def api_user_settings_update(user_id):
    """Toggle user settings (configure_by_toggle)."""
    data = request.get_json(force=True)
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        return jsonify({"error": "User not found"}), 404

    settings = user.get("settings", {
        "notifications_enabled": True,
        "auto_backup": True,
        "dark_mode": False,
        "public_profile": False,
    })

    for key in ("notifications_enabled", "auto_backup", "dark_mode", "public_profile"):
        if key in data:
            settings[key] = bool(data[key])

    user["settings"] = settings
    db.save_collection(SITE, "users", users)
    return jsonify({"user_id": user_id, "settings": settings})


# ---------------------------------------------------------------------------
# API routes -- Auth / User API
# ---------------------------------------------------------------------------

@blueprint.route("/api/login", methods=["POST"])
def api_login():
    """API login endpoint."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username and u["password"] == password), None)
    if not user:
        return jsonify({"error": "Invalid credentials"}), 401
    session["user_id"] = user["id"]
    return jsonify({"user_id": user["id"], "username": user["username"], "name": user["name"]})

@blueprint.route("/api/users/<int:user_id>")
def api_user_get(user_id):
    """Get user profile (without password)."""
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({k: v for k, v in user.items() if k != "password"})


@blueprint.route("/api/users")
def api_users_list():
    """List all users (without passwords)."""
    users = _load_users()
    return jsonify([{k: v for k, v in u.items() if k != "password"} for u in users])
