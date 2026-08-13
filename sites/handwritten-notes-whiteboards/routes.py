"""NoteCanvas -- unified notes platform with text + freeform drawing.

Every item is a "note" that supports both text content and a drawing canvas.
Notebooks and whiteboards are merged into the unified note concept.
Full CRUD via both HTML forms and JSON API.
"""
import json
import pathlib
from datetime import datetime

from flask import (
    Blueprint, abort, jsonify, redirect, render_template,
    request, session, url_for,
)
from app import db
from app.events import emit

from . import images

SITE = "handwritten-notes-whiteboards"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "handwritten-notes-whiteboards",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _load_users():
    return db.query(SITE, "users")


def _get_user(user_id):
    return db.get_item(SITE, "users", user_id)


def _current_user():
    if "user_id" in session:
        return _get_user(session["user_id"])
    return None


def _now_iso():
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _all_tags(limit=50):
    """Return distinct tags from notes (for sidebar filter)."""
    notes = db.query(SITE, "notes", sort="-updated_at", limit=200)
    tag_counts = {}
    for n in notes:
        tags = n.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        for t in tags:
            tag_counts[t] = tag_counts.get(t, 0) + 1
    sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
    return sorted_tags[:limit]


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    """Main notes dashboard with grid/sidebar layout."""
    user = _current_user()
    q = request.args.get("q", "").strip()
    tag_filter = request.args.get("tag", "").strip()
    sort_by = request.args.get("sort", "recent")
    upload_error = request.args.get("upload_error", "").strip()

    # Build query filters
    where = {}
    if user:
        where["owner_id"] = user["id"]

    # Sort mapping
    sort_map = {
        "recent": "-updated_at",
        "title": "title",
        "created": "-created_at",
    }
    sort_col = sort_map.get(sort_by, "-updated_at")

    # Fetch notes with SQL-level filtering
    if q:
        # Use FTS5/BM25 for text search
        search_where = {"owner_id": user["id"]} if user else None
        rows = db.search(SITE, "notes", q, where=search_where, limit=50)
    else:
        rows = db.query(SITE, "notes", where=where if where else None, sort=sort_col, limit=50)

    # Parse tags from string if needed and apply tag filter in Python
    # (already limited to <=50 rows from SQL)
    all_notes = []
    for n in rows:
        tags = n.get("tags", [])
        if isinstance(tags, str):
            n["tags"] = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        all_notes.append(n)

    if tag_filter:
        all_notes = [n for n in all_notes if tag_filter in n.get("tags", [])]

    # Separate pinned notes
    pinned = [n for n in all_notes if n.get("is_pinned")]
    unpinned = [n for n in all_notes if not n.get("is_pinned")]

    # Get tags for sidebar filter
    tags = _all_tags()

    return render_template(
        "handwritten-notes-whiteboards/index.html",
        pinned_notes=pinned, notes=unpinned,
        user=user, tags=tags,
        q=q, tag_filter=tag_filter, sort_by=sort_by,
        upload_error=upload_error,
    )


@blueprint.route("/note/<int:note_id>")
def note_detail(note_id):
    """Unified note editor with text + drawing canvas."""
    user = _current_user()
    note = db.get_item(SITE, "notes", note_id)
    if not note:
        abort(404)
    # Parse tags
    tags = note.get("tags", [])
    if isinstance(tags, str):
        note["tags"] = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    return render_template(
        "handwritten-notes-whiteboards/note.html",
        note=note, user=user,
    )


@blueprint.route("/note/new", methods=["GET"])
def note_new_page():
    """Create a new note and redirect to editor."""
    user = _current_user()
    if not user:
        return redirect(url_for("handwritten-notes-whiteboards.login_page"))

    now = _now_iso()
    # Get next ID
    new_id = db.next_id(SITE, "notes")

    new_note = {
        "id": new_id,
        "title": "Untitled Note",
        "content": "",
        "owner_id": user["id"],
        "created_at": now,
        "updated_at": now,
        "tags": "",
        "notebook_id": 0,
        "is_pinned": False,
        "color": "#FFFACD",
        "drawing_data": "",
    }
    db.save_item(SITE, "notes", new_id, new_note)

    emit("file_created", user_id=user["id"], filename="Untitled Note",
         file_type="note", source_site="handwritten-notes-whiteboards",
         source_id=new_id)

    return redirect(url_for("handwritten-notes-whiteboards.note_detail", note_id=new_id))


@blueprint.route("/note/new", methods=["POST"])
def note_new_submit():
    """Create note via HTML form POST."""
    user = _current_user()
    if not user:
        return redirect(url_for("handwritten-notes-whiteboards.login_page"))

    title = request.form.get("title", "").strip() or "Untitled Note"
    content = request.form.get("content", "").strip()
    tags_str = request.form.get("tags", "").strip()
    color = request.form.get("color", "#FFFACD").strip()
    drawing_data = request.form.get("drawing_data", "").strip()

    now = _now_iso()
    new_id = db.next_id(SITE, "notes")

    new_note = {
        "id": new_id,
        "title": title,
        "content": content,
        "owner_id": user["id"],
        "created_at": now,
        "updated_at": now,
        "tags": tags_str,
        "notebook_id": 0,
        "is_pinned": False,
        "color": color,
        "drawing_data": drawing_data,
    }
    db.save_item(SITE, "notes", new_id, new_note)

    emit("file_created", user_id=user["id"], filename=title,
         file_type="note", source_site="handwritten-notes-whiteboards",
         source_id=new_id)

    return redirect(url_for("handwritten-notes-whiteboards.note_detail", note_id=new_id))


@blueprint.route("/note/<int:note_id>/edit", methods=["POST"])
def note_edit_submit(note_id):
    """Update note via HTML form."""
    user = _current_user()
    if not user:
        return redirect(url_for("handwritten-notes-whiteboards.login_page"))

    note = db.get_item(SITE, "notes", note_id)
    if not note:
        abort(404)

    title = request.form.get("title", "").strip()
    content = request.form.get("content", "")
    tags_str = request.form.get("tags", "").strip()
    color = request.form.get("color", note.get("color", "#FFFACD")).strip()
    is_pinned = request.form.get("is_pinned") == "on"
    drawing_data = request.form.get("drawing_data", note.get("drawing_data", ""))

    if title:
        note["title"] = title
    if content is not None:
        note["content"] = content
    note["tags"] = tags_str
    note["color"] = color
    note["is_pinned"] = is_pinned
    note["drawing_data"] = drawing_data
    note["updated_at"] = _now_iso()

    db.save_item(SITE, "notes", note_id, note)

    return redirect(url_for("handwritten-notes-whiteboards.note_detail", note_id=note_id))


@blueprint.route("/note/<int:note_id>/save", methods=["POST"])
def note_save_ajax(note_id):
    """Save note via AJAX (JSON body) -- used by the editor."""
    user = _current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401

    note = db.get_item(SITE, "notes", note_id)
    if not note:
        abort(404)

    data = request.get_json(silent=True) or {}

    for field in ("title", "content", "tags", "color", "is_pinned", "drawing_data"):
        if field in data:
            note[field] = data[field]
    note["updated_at"] = _now_iso()

    # drawing detector (sign_by_freeformdrawing): a real drawing is a PNG data
    # URL of plausible size, not a blank canvas or stray dot
    drawing = note.get("drawing_data") or ""
    has_drawing = False
    if isinstance(drawing, str) and drawing.startswith("data:image/png;base64,"):
        import base64
        try:
            has_drawing = len(base64.b64decode(drawing.split(",", 1)[1])) > 500
        except Exception:
            has_drawing = False
    note["has_drawing"] = has_drawing

    db.save_item(SITE, "notes", note_id, note)

    return jsonify({"status": "saved", "updated_at": note["updated_at"],
                    "has_drawing": has_drawing})


@blueprint.route("/note/<int:note_id>/delete", methods=["POST"])
def note_delete_submit(note_id):
    """Delete note via HTML form."""
    db.delete_item(SITE, "notes", note_id)
    return redirect(url_for("handwritten-notes-whiteboards.index"))


@blueprint.route("/note/<int:note_id>/invite", methods=["POST"])
def form_invite_to_note(note_id):
    """Invite a user to collaborate on a note via email."""
    _email = request.form.get("email", "").strip()
    return redirect(url_for("handwritten-notes-whiteboards.note_detail", note_id=note_id))


@blueprint.route("/upload-image", methods=["POST"])
def form_upload_image():
    """Upload an image and create a new note from it."""
    user = _current_user()
    if not user:
        return redirect(url_for("handwritten-notes-whiteboards.login_page"))
    f = request.files.get("file")
    # Reject empty uploads: require an actual image file to be selected.
    if not f or not f.filename:
        return redirect(url_for(
            "handwritten-notes-whiteboards.index", upload_error="1",
        ))
    if not (f.mimetype or "").startswith("image/"):
        return redirect(url_for(
            "handwritten-notes-whiteboards.index", upload_error="2",
        ))
    title = f.filename
    now = _now_iso()
    new_id = db.next_id(SITE, "notes")
    # We never keep the raw uploaded bytes -- store a generated placeholder
    # image and reference its served path instead.
    image_url = images.save_upload_placeholder(new_id, f.filename)
    new_note = {
        "id": new_id, "title": title,
        "content": f"[image uploaded: {title}]",
        "owner_id": user["id"], "created_at": now, "updated_at": now,
        "tags": "image", "notebook_id": 0, "is_pinned": False,
        "color": "#FFFACD", "drawing_data": "", "image": image_url,
    }
    db.save_item(SITE, "notes", new_id, new_note)
    emit("file_created", user_id=user["id"], filename=title,
         file_type="note", source_site="handwritten-notes-whiteboards",
         source_id=new_id)
    return redirect(url_for("handwritten-notes-whiteboards.note_detail", note_id=new_id))


# ---------------------------------------------------------------------------
# Image editor -- edit_by_image macro (crop / resize / contrast / vibrance)
# ---------------------------------------------------------------------------

@blueprint.route("/note/<int:note_id>/image/edit", methods=["GET"])
def note_image_edit_page(note_id):
    """Render the basic image editor for a note's image.

    Ensures the note has an image (generating a deterministic placeholder if
    it does not yet have one) so the editor always has something to edit.
    """
    user = _current_user()
    note = db.get_item(SITE, "notes", note_id)
    if not note:
        abort(404)

    image_url = note.get("image")
    local = images.local_path_for_url(image_url) if image_url else None
    if not image_url or not (local and local.is_file()):
        # Generate the base placeholder on demand and persist to the overlay.
        image_url = images.ensure_note_placeholder(
            note_id, note.get("title") or f"Note {note_id}")
        note["image"] = image_url
        note["updated_at"] = _now_iso()
        db.save_item(SITE, "notes", note_id, note)

    return render_template(
        "handwritten-notes-whiteboards/note_image_edit.html",
        note=note, user=user, image_url=note["image"],
        edit_ops=list(images.EDIT_OPS),
    )


@blueprint.route("/note/<int:note_id>/image/edit", methods=["POST"])
def note_image_edit_submit(note_id):
    """Apply an image edit and persist it to the SESSION OVERLAY.

    Body (JSON or form) must include an ``op`` plus its params, e.g.::

        {"op": "crop", "x": 10, "y": 20, "w": 200, "h": 120}
        {"op": "resize", "w": 320, "h": 240}
        {"op": "contrast", "value": 1.4}
        {"op": "vibrance", "value": 1.6}

    The posted params are what a verifier checks (captured by /_admin/log);
    the server also applies the transform with PIL and stores the resulting
    placeholder path on the note overlay record.
    """
    user = _current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401

    note = db.get_item(SITE, "notes", note_id)
    if not note:
        abort(404)

    data = request.get_json(silent=True) or request.form.to_dict() or {}
    op = (data.get("op") or "").strip().lower()
    if op not in images.EDIT_OPS:
        return jsonify({
            "error": "invalid op",
            "allowed": list(images.EDIT_OPS),
        }), 400

    # Collect the recognised params for this op (coerced numerically).
    def _num(key):
        v = data.get(key)
        if v is None or v == "":
            return None
        try:
            return float(v) if ("." in str(v)) else int(v)
        except (TypeError, ValueError):
            return None

    params = {}
    if op == "crop":
        for k in ("x", "y", "w", "h"):
            params[k] = _num(k)
    elif op == "resize":
        for k in ("w", "h"):
            params[k] = _num(k)
    else:  # contrast / vibrance
        params["value"] = _num("value")

    try:
        new_url = images.apply_edit_to_note(note, op, params)
    except Exception as exc:  # pragma: no cover - defensive
        return jsonify({"error": f"edit failed: {exc}"}), 400

    # Persist to the session overlay only (never the base table).
    history = note.get("image_edits") or []
    if isinstance(history, str):
        try:
            history = json.loads(history) if history else []
        except Exception:
            history = []
    history.append({"op": op, "params": params, "at": _now_iso()})
    note["image"] = new_url
    note["image_edits"] = history
    note["updated_at"] = _now_iso()
    db.save_item(SITE, "notes", note_id, note)

    return jsonify({
        "status": "edited",
        "note_id": note_id,
        "op": op,
        "params": params,
        "image": new_url,
        "edit_count": len(history),
    })


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template(
        "handwritten-notes-whiteboards/login.html", error=None,
    )


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return render_template(
            "handwritten-notes-whiteboards/login.html",
            error="Invalid username or password",
        )
    session["user_id"] = user["id"]
    emit("signup", user_id=user["id"], site_name="handwritten-notes-whiteboards", username=request.form.get("username", ""), password=request.form.get("password", ""), email="")
    return redirect(url_for("handwritten-notes-whiteboards.index"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("handwritten-notes-whiteboards.login_page"))


# ---------------------------------------------------------------------------
# Legacy HTML routes -- redirect to unified views
# ---------------------------------------------------------------------------

@blueprint.route("/notebooks")
def notebooks_page():
    return redirect(url_for("handwritten-notes-whiteboards.index"))


@blueprint.route("/notebook/<int:notebook_id>")
def notebook_detail(notebook_id):
    return redirect(url_for("handwritten-notes-whiteboards.index"))


@blueprint.route("/whiteboards")
def whiteboards_page():
    return redirect(url_for("handwritten-notes-whiteboards.index"))


@blueprint.route("/whiteboard/<int:wb_id>")
def whiteboard_detail(wb_id):
    return redirect(url_for("handwritten-notes-whiteboards.index"))


@blueprint.route("/search")
def search_page():
    q = request.args.get("q", "")
    return redirect(url_for("handwritten-notes-whiteboards.index", q=q))


# ---------------------------------------------------------------------------
# API routes -- Notes
# ---------------------------------------------------------------------------

@blueprint.route("/api/notes", methods=["GET"])
def api_notes_list():
    """List notes with SQL-level filtering. Supports: tag, owner_id, is_pinned, q."""
    owner_id = request.args.get("owner_id", type=int)
    tag = request.args.get("tag", "").strip()
    is_pinned = request.args.get("is_pinned")
    q = request.args.get("q", "").strip()
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)

    where = {}
    if owner_id:
        where["owner_id"] = owner_id
    if is_pinned is not None:
        where["is_pinned"] = 1 if is_pinned.lower() in ("true", "1", "yes") else 0

    if q:
        # Use FTS5/BM25 for text search
        search_where = {"owner_id": owner_id} if owner_id else None
        notes = db.search(SITE, "notes", q, where=search_where, limit=limit, offset=offset)
    else:
        notes = db.query(SITE, "notes", where=where if where else None,
                         sort="-updated_at", limit=limit, offset=offset)

    # Parse tags from string
    for n in notes:
        tags = n.get("tags", [])
        if isinstance(tags, str):
            n["tags"] = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    # Apply tag filter in Python (already limited)
    if tag:
        notes = [n for n in notes if tag in n.get("tags", [])]

    return jsonify(notes)


@blueprint.route("/api/notes", methods=["POST"])
def api_notes_create():
    """Create a new note."""
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    content = data.get("content", "").strip()
    owner_id = data.get("owner_id")
    tags = data.get("tags", [])
    is_pinned = data.get("is_pinned", False)
    color = data.get("color", "#FFFACD")
    drawing_data = data.get("drawing_data", "")

    if not title:
        return jsonify({"error": "title is required"}), 400
    if not owner_id:
        if "user_id" in session:
            owner_id = session["user_id"]
        else:
            return jsonify({"error": "owner_id is required"}), 400

    # Normalize tags to comma string for DB
    if isinstance(tags, list):
        tags_str = ", ".join(tags)
    else:
        tags_str = str(tags)

    now = _now_iso()
    new_id = db.next_id(SITE, "notes")

    new_note = {
        "id": new_id,
        "title": title,
        "content": content,
        "owner_id": owner_id,
        "created_at": now,
        "updated_at": now,
        "tags": tags_str,
        "notebook_id": data.get("notebook_id", 0),
        "is_pinned": bool(is_pinned),
        "color": color,
        "drawing_data": drawing_data,
    }
    db.save_item(SITE, "notes", new_id, new_note)

    emit("file_created", user_id=owner_id, filename=title,
         file_type="note", source_site="handwritten-notes-whiteboards",
         source_id=new_id)

    # Return with tags as list for API consumers
    new_note["tags"] = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []
    return jsonify(new_note), 201


@blueprint.route("/api/notes/<int:note_id>", methods=["GET"])
def api_note_get(note_id):
    """Get a single note."""
    note = db.get_item(SITE, "notes", note_id)
    if not note:
        abort(404)
    tags = note.get("tags", [])
    if isinstance(tags, str):
        note["tags"] = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    return jsonify(note)


@blueprint.route("/api/notes/<int:note_id>", methods=["PUT"])
def api_note_update(note_id):
    """Update a note."""
    data = request.get_json(silent=True) or {}
    note = db.get_item(SITE, "notes", note_id)
    if not note:
        abort(404)

    for field in ("title", "content", "notebook_id", "is_pinned", "color", "drawing_data"):
        if field in data:
            note[field] = data[field]
    if "tags" in data:
        tags = data["tags"]
        if isinstance(tags, list):
            note["tags"] = ", ".join(tags)
        else:
            note["tags"] = str(tags)
    note["updated_at"] = _now_iso()
    db.save_item(SITE, "notes", note_id, note)

    # Return with tags as list
    tags = note.get("tags", "")
    if isinstance(tags, str):
        note["tags"] = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    return jsonify(note)


@blueprint.route("/api/notes/<int:note_id>", methods=["DELETE"])
def api_note_delete(note_id):
    """Delete a note."""
    note = db.get_item(SITE, "notes", note_id)
    if not note:
        abort(404)
    db.delete_item(SITE, "notes", note_id)
    return jsonify({"deleted": note_id})


# ---------------------------------------------------------------------------
# API routes -- Notebooks (kept for backward compat)
# ---------------------------------------------------------------------------

@blueprint.route("/api/notebooks", methods=["GET"])
def api_notebooks_list():
    notebooks = db.query(SITE, "notebooks")
    return jsonify(notebooks)


@blueprint.route("/api/notebooks", methods=["POST"])
def api_notebooks_create():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    owner_id = data.get("owner_id")
    color = data.get("color", "#4A90D9")

    if not name:
        return jsonify({"error": "name is required"}), 400
    if not owner_id:
        if "user_id" in session:
            owner_id = session["user_id"]
        else:
            return jsonify({"error": "owner_id is required"}), 400

    notebooks = db.query(SITE, "notebooks")
    new_id = max((nb["id"] for nb in notebooks), default=0) + 1
    new_nb = {
        "id": new_id, "name": name, "owner_id": owner_id,
        "color": color, "notes_count": 0,
    }
    db.save_item(SITE, "notebooks", new_id, new_nb)
    return jsonify(new_nb), 201


@blueprint.route("/api/notebooks/<int:nb_id>", methods=["GET"])
def api_notebook_get(nb_id):
    notebook = db.get_item(SITE, "notebooks", nb_id)
    if not notebook:
        abort(404)
    nb_notes = db.query(SITE, "notes", where={"notebook_id": nb_id}, sort="-updated_at", limit=50)
    result = dict(notebook)
    result["notes"] = nb_notes
    result["notes_count"] = len(nb_notes)
    return jsonify(result)


@blueprint.route("/api/notebooks/<int:nb_id>", methods=["PUT"])
def api_notebook_update(nb_id):
    data = request.get_json(silent=True) or {}
    notebook = db.get_item(SITE, "notebooks", nb_id)
    if not notebook:
        abort(404)
    for field in ("name", "color"):
        if field in data:
            notebook[field] = data[field]
    db.save_item(SITE, "notebooks", nb_id, notebook)
    return jsonify(notebook)


@blueprint.route("/api/notebooks/<int:nb_id>", methods=["DELETE"])
def api_notebook_delete(nb_id):
    notebook = db.get_item(SITE, "notebooks", nb_id)
    if not notebook:
        abort(404)
    db.delete_item(SITE, "notebooks", nb_id)
    return jsonify({"deleted": nb_id})


# ---------------------------------------------------------------------------
# API routes -- Whiteboards (kept for backward compat)
# ---------------------------------------------------------------------------

@blueprint.route("/api/whiteboards", methods=["GET"])
def api_whiteboards_list():
    whiteboards = db.query(SITE, "whiteboards", sort="-updated_at", limit=50)
    return jsonify(whiteboards)


@blueprint.route("/api/whiteboards", methods=["POST"])
def api_whiteboards_create():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    owner_id = data.get("owner_id")
    if not title:
        return jsonify({"error": "title is required"}), 400
    if not owner_id:
        if "user_id" in session:
            owner_id = session["user_id"]
        else:
            return jsonify({"error": "owner_id is required"}), 400

    now = _now_iso()
    whiteboards = db.query(SITE, "whiteboards", sort="-id", limit=1)
    new_id = (whiteboards[0]["id"] + 1) if whiteboards else 1
    new_wb = {
        "id": new_id, "title": title, "owner_id": owner_id,
        "created_at": now, "updated_at": now,
        "shared_with": data.get("shared_with", []),
        "elements": data.get("elements", []),
    }
    db.save_item(SITE, "whiteboards", new_id, new_wb)
    emit("file_created", user_id=owner_id, filename=title,
         file_type="whiteboard", source_site="handwritten-notes-whiteboards",
         source_id=new_id)
    return jsonify(new_wb), 201


@blueprint.route("/api/whiteboards/<int:wb_id>", methods=["GET"])
def api_whiteboard_get(wb_id):
    wb = db.get_item(SITE, "whiteboards", wb_id)
    if not wb:
        abort(404)
    return jsonify(wb)


@blueprint.route("/api/whiteboards/<int:wb_id>", methods=["PUT"])
def api_whiteboard_update(wb_id):
    data = request.get_json(silent=True) or {}
    wb = db.get_item(SITE, "whiteboards", wb_id)
    if not wb:
        abort(404)
    for field in ("title", "shared_with", "elements"):
        if field in data:
            wb[field] = data[field]
    wb["updated_at"] = _now_iso()
    db.save_item(SITE, "whiteboards", wb_id, wb)
    return jsonify(wb)


@blueprint.route("/api/whiteboards/<int:wb_id>", methods=["DELETE"])
def api_whiteboard_delete(wb_id):
    wb = db.get_item(SITE, "whiteboards", wb_id)
    if not wb:
        abort(404)
    db.delete_item(SITE, "whiteboards", wb_id)
    return jsonify({"deleted": wb_id})


# ---------------------------------------------------------------------------
# API routes -- Search & Stats
# ---------------------------------------------------------------------------

@blueprint.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"query": q, "notes": [], "whiteboards": []})
    notes = db.search(SITE, "notes", q, limit=50)
    whiteboards = db.search(SITE, "whiteboards", q, limit=20)
    return jsonify({"query": q, "notes": notes, "whiteboards": whiteboards})


@blueprint.route("/api/stats")
def api_stats():
    note_count = db.execute(
        "SELECT COUNT(*) as cnt FROM handwritten_notes_whiteboards_notes",
        fetch="val",
    ) or 0
    notebook_count = db.execute(
        "SELECT COUNT(*) as cnt FROM handwritten_notes_whiteboards_notebooks",
        fetch="val",
    ) or 0
    wb_count = db.execute(
        "SELECT COUNT(*) as cnt FROM handwritten_notes_whiteboards_whiteboards",
        fetch="val",
    ) or 0
    user_count = db.execute(
        "SELECT COUNT(*) as cnt FROM handwritten_notes_whiteboards_users",
        fetch="val",
    ) or 0
    pinned_count = db.execute(
        "SELECT COUNT(*) as cnt FROM handwritten_notes_whiteboards_notes WHERE is_pinned = 1",
        fetch="val",
    ) or 0

    return jsonify({
        "total_notes": note_count,
        "total_notebooks": notebook_count,
        "total_whiteboards": wb_count,
        "total_users": user_count,
        "pinned_notes": pinned_count,
    })


# ---------------------------------------------------------------------------
# API routes -- Auth
# ---------------------------------------------------------------------------

@blueprint.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return jsonify({"error": "Invalid credentials"}), 401
    session["user_id"] = user["id"]
    return jsonify({"user_id": user["id"], "username": user["username"]})


# ---------------------------------------------------------------------------
# API routes -- Misc (backward compat for tasks/macros)
# ---------------------------------------------------------------------------

@blueprint.route("/api/whiteboards/<int:wb_id>/view", methods=["GET"])
def api_whiteboard_view(wb_id):
    wb = db.get_item(SITE, "whiteboards", wb_id)
    if not wb:
        abort(404)
    zoom = request.args.get("zoom", 1.0, type=float)
    pan_x = request.args.get("pan_x", 0, type=int)
    pan_y = request.args.get("pan_y", 0, type=int)
    return jsonify({
        "whiteboard": wb,
        "view": {"zoom": zoom, "pan_x": pan_x, "pan_y": pan_y},
    })


@blueprint.route("/api/notes/semantic", methods=["GET"])
def api_notes_semantic():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    notes = db.search(SITE, "notes", q, limit=50)
    return jsonify(notes)


@blueprint.route("/api/notes/search_by_image", methods=["POST"])
def api_notes_search_by_image():
    _file = request.files.get("image")
    if not _file:
        return jsonify({"error": "image file is required"}), 400
    return jsonify({"matches": [], "message": "Image search placeholder."})


@blueprint.route("/api/notes/create_by_radio", methods=["POST"])
def api_notes_create_by_radio():
    data = request.get_json(silent=True) or {}
    note_type = data.get("note_type", "text")
    if note_type not in ("text", "checklist", "sketch"):
        return jsonify({"error": "note_type must be text, checklist, or sketch"}), 400
    title = data.get("title", "").strip()
    content = data.get("content", "").strip()
    owner_id = data.get("owner_id") or session.get("user_id")
    if not title:
        return jsonify({"error": "title is required"}), 400
    if not owner_id:
        return jsonify({"error": "owner_id is required"}), 400

    now = _now_iso()
    new_id = db.next_id(SITE, "notes")
    new_note = {
        "id": new_id, "title": title, "content": content,
        "owner_id": owner_id, "created_at": now, "updated_at": now,
        "tags": "", "notebook_id": 0, "is_pinned": False,
        "color": "#FFFACD", "drawing_data": "",
        "note_type": note_type,
    }
    db.save_item(SITE, "notes", new_id, new_note)
    emit("file_created", user_id=owner_id, filename=title,
         file_type="note", source_site="handwritten-notes-whiteboards",
         source_id=new_id)
    return jsonify(new_note), 201


@blueprint.route("/api/create_by_toggle", methods=["POST"])
def api_create_by_toggle():
    data = request.get_json(silent=True) or {}
    mode = data.get("mode", "note")
    title = data.get("title", "").strip()
    owner_id = data.get("owner_id") or session.get("user_id")
    if not title:
        return jsonify({"error": "title is required"}), 400
    if not owner_id:
        return jsonify({"error": "owner_id is required"}), 400

    now = _now_iso()
    if mode == "whiteboard":
        whiteboards = db.query(SITE, "whiteboards", sort="-id", limit=1)
        new_id = (whiteboards[0]["id"] + 1) if whiteboards else 1
        new_wb = {
            "id": new_id, "title": title, "owner_id": owner_id,
            "created_at": now, "updated_at": now,
            "shared_with": data.get("shared_with", []),
            "elements": data.get("elements", []),
        }
        db.save_item(SITE, "whiteboards", new_id, new_wb)
        emit("file_created", user_id=owner_id, filename=title,
             file_type="whiteboard", source_site="handwritten-notes-whiteboards",
             source_id=new_id)
        return jsonify({"created": "whiteboard", "item": new_wb}), 201
    else:
        new_id = db.next_id(SITE, "notes")
        new_note = {
            "id": new_id, "title": title,
            "content": data.get("content", ""),
            "owner_id": owner_id, "created_at": now, "updated_at": now,
            "tags": "", "notebook_id": data.get("notebook_id", 0),
            "is_pinned": False, "color": data.get("color", "#FFFACD"),
            "drawing_data": "",
        }
        db.save_item(SITE, "notes", new_id, new_note)
        emit("file_created", user_id=owner_id, filename=title,
             file_type="note", source_site="handwritten-notes-whiteboards",
             source_id=new_id)
        return jsonify({"created": "note", "item": new_note}), 201


@blueprint.route("/api/whiteboards/<int:wb_id>/elements", methods=["POST"])
def api_whiteboard_add_element(wb_id):
    data = request.get_json(silent=True) or {}
    wb = db.get_item(SITE, "whiteboards", wb_id)
    if not wb:
        abort(404)
    new_elem = {
        "type": data.get("type", "sticky"),
        "content": data.get("content", ""),
        "x": data.get("x", 0), "y": data.get("y", 0),
        "width": data.get("width", 100), "height": data.get("height", 60),
        "color": data.get("color", "#FFFACD"),
    }
    elements = wb.get("elements", [])
    if isinstance(elements, str):
        import json as _json
        elements = _json.loads(elements) if elements else []
    elements.append(new_elem)
    wb["elements"] = elements
    wb["updated_at"] = _now_iso()
    db.save_item(SITE, "whiteboards", wb_id, wb)
    return jsonify({"whiteboard_id": wb_id, "element_index": len(elements) - 1,
                     "element": new_elem}), 201


@blueprint.route("/api/notes/create_by_image", methods=["POST"])
def api_notes_create_by_image():
    img = request.files.get("image")
    if not img:
        return jsonify({"error": "image file is required"}), 400
    title = request.form.get("title", "").strip() or img.filename or "Image Note"
    owner_id = request.form.get("owner_id", type=int) or session.get("user_id")
    if not owner_id:
        return jsonify({"error": "owner_id is required"}), 400

    now = _now_iso()
    new_id = db.next_id(SITE, "notes")
    image_url = images.save_upload_placeholder(new_id, img.filename)
    new_note = {
        "id": new_id, "title": title,
        "content": f"[image uploaded: {img.filename}]",
        "owner_id": owner_id, "created_at": now, "updated_at": now,
        "tags": "image", "notebook_id": 0, "is_pinned": False,
        "color": "#FFFACD", "drawing_data": "", "image": image_url,
    }
    db.save_item(SITE, "notes", new_id, new_note)
    emit("file_created", user_id=owner_id, filename=title,
         file_type="note", source_site="handwritten-notes-whiteboards",
         source_id=new_id)
    return jsonify(new_note), 201


@blueprint.route("/api/notes/reorder", methods=["PUT"])
def api_notes_reorder():
    data = request.get_json(silent=True) or {}
    note_ids = data.get("note_ids", [])
    if not note_ids or not isinstance(note_ids, list):
        return jsonify({"error": "note_ids list is required"}), 400
    now = _now_iso()
    ordered = []
    for rank, nid in enumerate(note_ids):
        note = db.get_item(SITE, "notes", nid)
        if note:
            note["rank"] = rank
            note["updated_at"] = now
            db.save_item(SITE, "notes", nid, note)
            ordered.append(note)
    return jsonify(ordered)


@blueprint.route("/api/whiteboards/<int:wb_id>/elements/<int:elem_idx>/move", methods=["PUT"])
def api_whiteboard_move_element(wb_id, elem_idx):
    data = request.get_json(silent=True) or {}
    wb = db.get_item(SITE, "whiteboards", wb_id)
    if not wb:
        abort(404)
    elements = wb.get("elements", [])
    if isinstance(elements, str):
        import json as _json
        elements = _json.loads(elements) if elements else []
    if elem_idx < 0 or elem_idx >= len(elements):
        return jsonify({"error": "element index out of range"}), 404
    if "x" in data:
        elements[elem_idx]["x"] = data["x"]
    if "y" in data:
        elements[elem_idx]["y"] = data["y"]
    wb["elements"] = elements
    wb["updated_at"] = _now_iso()
    db.save_item(SITE, "whiteboards", wb_id, wb)
    return jsonify({"whiteboard_id": wb_id, "element_index": elem_idx,
                     "element": elements[elem_idx]})


@blueprint.route("/api/notes/<int:note_id>/replace_image", methods=["PUT"])
def api_note_replace_image(note_id):
    img = request.files.get("image")
    if not img:
        return jsonify({"error": "image file is required"}), 400
    note = db.get_item(SITE, "notes", note_id)
    if not note:
        abort(404)
    note["content"] = f"[image replaced: {img.filename}]"
    note["image"] = images.save_upload_placeholder(note_id, img.filename)
    note["updated_at"] = _now_iso()
    db.save_item(SITE, "notes", note_id, note)
    return jsonify(note)


@blueprint.route("/api/upload", methods=["POST"])
def api_upload():
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "file is required"}), 400
    note_id = request.form.get("note_id", type=int)
    result = {
        "filename": f.filename, "size_bytes": 0,
        "attached_to_note": note_id, "uploaded_at": _now_iso(),
    }
    if note_id:
        note = db.get_item(SITE, "notes", note_id)
        if note:
            attachments = note.get("attachments", [])
            if isinstance(attachments, str):
                import json as _json
                attachments = _json.loads(attachments) if attachments else []
            attachments.append(f.filename)
            note["attachments"] = attachments
            note["updated_at"] = _now_iso()
            db.save_item(SITE, "notes", note_id, note)
    return jsonify(result), 201


@blueprint.route("/api/notes/<int:note_id>/pin", methods=["POST"])
def api_note_toggle_pin(note_id):
    note = db.get_item(SITE, "notes", note_id)
    if not note:
        abort(404)
    was_pinned = note.get("is_pinned", False)
    note["is_pinned"] = not was_pinned
    note["updated_at"] = _now_iso()
    db.save_item(SITE, "notes", note_id, note)
    action = "unpinned" if was_pinned else "pinned"
    return jsonify({"note_id": note_id, "is_pinned": note["is_pinned"], "action": action})


@blueprint.route("/api/export", methods=["GET"])
def api_export():
    fmt = request.args.get("format", "json").lower()
    notebook_id = request.args.get("notebook_id", type=int)
    where = {}
    if notebook_id:
        where["notebook_id"] = notebook_id
    notes = db.query(SITE, "notes", where=where if where else None,
                     sort="-updated_at", limit=500)

    if fmt == "csv":
        import csv
        import io
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["id", "title", "content", "owner_id", "notebook_id",
                          "created_at", "updated_at", "tags", "is_pinned", "color"])
        for n in notes:
            writer.writerow([
                n["id"], n["title"], n.get("content", ""), n["owner_id"],
                n.get("notebook_id", ""), n.get("created_at", ""),
                n.get("updated_at", ""), n.get("tags", ""),
                n.get("is_pinned", False), n.get("color", ""),
            ])
        from flask import Response
        return Response(buf.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=notes.csv"})
    elif fmt == "markdown":
        lines = []
        for n in notes:
            lines.append(f"# {n['title']}\n")
            lines.append(f"**Tags**: {n.get('tags', '')}\n")
            lines.append(f"**Created**: {n.get('created_at', '')}\n\n")
            lines.append(n.get("content", "") + "\n\n---\n\n")
        from flask import Response
        return Response("".join(lines), mimetype="text/markdown",
                        headers={"Content-Disposition": "attachment; filename=notes.md"})
    else:
        return jsonify(notes)


@blueprint.route("/api/whiteboards/<int:wb_id>/share", methods=["POST"])
def api_whiteboard_share(wb_id):
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    if user_id is None:
        return jsonify({"error": "user_id is required"}), 400
    wb = db.get_item(SITE, "whiteboards", wb_id)
    if not wb:
        abort(404)
    target = db.get_item(SITE, "users", user_id)
    if not target:
        return jsonify({"error": "user not found"}), 404
    shared = wb.get("shared_with", [])
    if isinstance(shared, str):
        import json as _json
        shared = _json.loads(shared) if shared else []
    if user_id not in shared:
        shared.append(user_id)
        wb["shared_with"] = shared
        wb["updated_at"] = _now_iso()
        db.save_item(SITE, "whiteboards", wb_id, wb)
        action = "shared"
    else:
        action = "already_shared"
    return jsonify({"whiteboard_id": wb_id, "shared_with": shared, "action": action})


@blueprint.route("/api/whiteboards/<int:wb_id>/invite", methods=["POST"])
def api_whiteboard_invite(wb_id):
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip()
    message = data.get("message", "").strip()
    if not email:
        return jsonify({"error": "email is required"}), 400
    wb = db.get_item(SITE, "whiteboards", wb_id)
    if not wb:
        abort(404)
    users = _load_users()
    target = next((u for u in users if u.get("email") == email), None)
    if target:
        shared = wb.get("shared_with", [])
        if isinstance(shared, str):
            import json as _json
            shared = _json.loads(shared) if shared else []
        if target["id"] not in shared:
            shared.append(target["id"])
            wb["shared_with"] = shared
            wb["updated_at"] = _now_iso()
            db.save_item(SITE, "whiteboards", wb_id, wb)
    return jsonify({
        "whiteboard_id": wb_id, "invited_email": email,
        "message": message,
        "resolved_user_id": target["id"] if target else None,
        "status": "invited",
    })


@blueprint.route("/api/notes/translate_by_image", methods=["POST"])
def api_translate_by_image():
    img = request.files.get("image")
    if not img:
        return jsonify({"error": "image file is required"}), 400
    target_lang = request.form.get("target_lang", "en").strip()
    return jsonify({
        "source_filename": img.filename, "target_language": target_lang,
        "ocr_text": "[placeholder: OCR not implemented]",
        "translated_text": "[placeholder: translation not implemented]",
        "status": "placeholder",
    })


@blueprint.route("/api/notes/submit_query", methods=["POST"])
def api_notes_submit_query():
    data = request.get_json(silent=True) or {}
    query = data.get("query", "").strip()
    if not query:
        return jsonify({"error": "query is required"}), 400
    results = db.search(SITE, "notes", query, limit=50)
    return jsonify({"query": query, "result_count": len(results), "results": results})


@blueprint.route("/api/users", methods=["GET"])
def api_users_list():
    users = _load_users()
    safe = [{k: v for k, v in u.items() if k != "password"} for u in users]
    return jsonify(safe)

