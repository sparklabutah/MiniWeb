"""SheetDeck -- spreadsheets and presentations platform (Google Sheets/Slides style).

Reads JSON data files for spreadsheets, presentations, templates, and users.
Supports full CRUD, sharing, cell-level editing, slide management, and templates.
"""
import pathlib
from datetime import datetime

from flask import Blueprint, Response, abort, jsonify, redirect, render_template, request, session, url_for
from app import db
from app.events import emit

SITE = "spreadsheets-slides"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "spreadsheets-slides",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def _load_spreadsheets():
    return db.query(SITE, "spreadsheets")


def _save_spreadsheets(items):
    db.save_collection(SITE, "spreadsheets", items)


def _load_presentations():
    return db.query(SITE, "presentations")


def _save_presentations(items):
    db.save_collection(SITE, "presentations", items)


def _load_templates():
    return db.query(SITE, "templates_ss")


def _load_users():
    return db.query(SITE, "users")


# ---------------------------------------------------------------------------
# User helpers
# ---------------------------------------------------------------------------

def _get_user(user_id):
    return db.get_item(SITE, "users", user_id)


def _current_user():
    if "user_id" in session:
        return _get_user(session["user_id"])
    return None


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    """Dashboard / file list showing all spreadsheets and presentations."""
    user = _current_user()
    spreadsheets = _load_spreadsheets()
    presentations = _load_presentations()
    users = _load_users()
    user_map = {u["id"]: u for u in users}

    q = request.args.get("q", "").strip()
    file_type = request.args.get("type", "").strip()
    owner_filter = request.args.get("owner_id", "").strip()
    sort = request.args.get("sort", "updated").strip()

    # Build unified file list
    files = []
    for s in spreadsheets:
        files.append({**s, "file_type": "spreadsheet", "item_count": len(s.get("sheets", []))})
    for p in presentations:
        files.append({**p, "file_type": "presentation", "item_count": p.get("slides_count", 0)})

    # Filter
    if q:
        q_lower = q.lower()
        files = [f for f in files if q_lower in f["title"].lower()]
    if file_type:
        files = [f for f in files if f["file_type"] == file_type]
    if owner_filter:
        try:
            oid = int(owner_filter)
            files = [f for f in files if f["owner_id"] == oid]
        except ValueError:
            pass

    # Sort
    if sort == "title":
        files.sort(key=lambda f: f["title"].lower())
    elif sort == "created":
        files.sort(key=lambda f: f.get("created_at", ""), reverse=True)
    else:
        files.sort(key=lambda f: f.get("updated_at", ""), reverse=True)

    return render_template("spreadsheets-slides/index.html",
                           files=files, user=user, user_map=user_map, users=users,
                           q=q, file_type=file_type, sort=sort, owner_filter=owner_filter)


@blueprint.route("/spreadsheet/<int:sid>")
def spreadsheet_view(sid):
    """View/edit a spreadsheet."""
    ss = db.get_item(SITE, "spreadsheets", sid)
    if ss is None:
        abort(404)
    user = _current_user()
    users = _load_users()
    user_map = {u["id"]: u for u in users}
    sheet_index = request.args.get("sheet", 0, type=int)
    can_edit = user and (ss["owner_id"] == user["id"] or user["id"] in ss.get("shared_with", []))
    return render_template("spreadsheets-slides/spreadsheet.html",
                           ss=ss, user=user, user_map=user_map, users=users,
                           sheet_index=sheet_index, can_edit=can_edit)


@blueprint.route("/presentation/<int:pid>")
def presentation_view(pid):
    """View/edit a presentation."""
    pres = db.get_item(SITE, "presentations", pid)
    if pres is None:
        abort(404)
    user = _current_user()
    users = _load_users()
    user_map = {u["id"]: u for u in users}
    slides = pres.get("slides", [])
    slide_index = request.args.get("slide", 0, type=int)
    # Clamp to valid range
    if slides:
        slide_index = max(0, min(slide_index, len(slides) - 1))
    else:
        slide_index = 0
    can_edit = user and (pres["owner_id"] == user["id"] or user["id"] in pres.get("shared_with", []))
    return render_template("spreadsheets-slides/presentation.html",
                           pres=pres, user=user, user_map=user_map, users=users,
                           slide_index=slide_index, can_edit=can_edit)


@blueprint.route("/create")
def create_page():
    """Form to create a new spreadsheet or presentation."""
    user = _current_user()
    templates = _load_templates()
    users = _load_users()
    return render_template("spreadsheets-slides/create.html",
                           user=user, templates=templates, users=users)


@blueprint.route("/shared")
def shared_page():
    """Show files shared with the current user."""
    user = _current_user()
    if not user:
        return redirect(url_for("spreadsheets-slides.login_page"))

    spreadsheets = _load_spreadsheets()
    presentations = _load_presentations()
    users = _load_users()
    user_map = {u["id"]: u for u in users}

    files = []
    for s in spreadsheets:
        if user["id"] in s.get("shared_with", []):
            files.append({**s, "file_type": "spreadsheet", "item_count": len(s.get("sheets", []))})
    for p in presentations:
        if user["id"] in p.get("shared_with", []):
            files.append({**p, "file_type": "presentation", "item_count": p.get("slides_count", 0)})

    files.sort(key=lambda f: f.get("updated_at", ""), reverse=True)

    return render_template("spreadsheets-slides/shared.html",
                           files=files, user=user, user_map=user_map)


@blueprint.route("/templates")
def templates_page():
    """Browse available templates."""
    user = _current_user()
    templates = _load_templates()
    return render_template("spreadsheets-slides/templates.html",
                           user=user, templates=templates)


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("spreadsheets-slides/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return render_template("spreadsheets-slides/login.html",
                               error="Invalid username or password")
    session["user_id"] = user["id"]
    emit("signup", user_id=user["id"], site_name="spreadsheets-slides", username=request.form.get("username", ""), password=request.form.get("password", ""), email="")
    next_url = request.form.get("next") or request.args.get("next")
    if next_url:
        return redirect(next_url)
    return redirect(url_for("spreadsheets-slides.index"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("spreadsheets-slides.login_page"))


# ---------------------------------------------------------------------------
# Form-based mutation routes (browser automation compatible)
# ---------------------------------------------------------------------------

@blueprint.route("/spreadsheet/create", methods=["POST"])
def form_create_spreadsheet():
    """Create a new spreadsheet via form submission."""
    title = request.form.get("title", "Untitled Spreadsheet").strip()
    owner_id = request.form.get("owner_id", type=int)
    if not owner_id:
        user = _current_user()
        if user:
            owner_id = user["id"]
        else:
            return redirect(url_for("spreadsheets-slides.login_page"))

    spreadsheets = _load_spreadsheets()
    new_id = max((s["id"] for s in spreadsheets), default=0) + 1
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    # Create empty 20x10 grid
    empty_row = [""] * 10
    empty_data = [list(empty_row) for _ in range(20)]

    new_ss = {
        "id": new_id,
        "title": title,
        "owner_id": owner_id,
        "created_at": now,
        "updated_at": now,
        "shared_with": [],
        "rows": 20,
        "cols": 10,
        "sheets": [{"name": "Sheet 1", "data": empty_data}],
    }
    spreadsheets.append(new_ss)
    _save_spreadsheets(spreadsheets)

    emit("file_created", user_id=owner_id, filename=title, file_type="spreadsheet", source_site="spreadsheets-slides", source_id=new_id)

    return redirect(url_for("spreadsheets-slides.spreadsheet_view", sid=new_id))


@blueprint.route("/presentation/create", methods=["POST"])
def form_create_presentation():
    """Create a new presentation via form submission."""
    title = request.form.get("title", "Untitled Presentation").strip()
    owner_id = request.form.get("owner_id", type=int)
    if not owner_id:
        user = _current_user()
        if user:
            owner_id = user["id"]
        else:
            return redirect(url_for("spreadsheets-slides.login_page"))

    presentations = _load_presentations()
    new_id = max((p["id"] for p in presentations), default=0) + 1
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    new_pres = {
        "id": new_id,
        "title": title,
        "owner_id": owner_id,
        "created_at": now,
        "updated_at": now,
        "shared_with": [],
        "slides_count": 1,
        "slides": [{"title": "Title Slide", "content": title, "notes": ""}],
    }
    presentations.append(new_pres)
    _save_presentations(presentations)

    emit("file_created", user_id=owner_id, filename=title, file_type="presentation", source_site="spreadsheets-slides", source_id=new_id)

    return redirect(url_for("spreadsheets-slides.presentation_view", pid=new_id))


@blueprint.route("/spreadsheet/<int:sid>/update", methods=["POST"])
def form_update_spreadsheet(sid):
    """Update spreadsheet title via form."""
    if "user_id" not in session:
        return jsonify({"error": "Authentication required"}), 401
    spreadsheets = _load_spreadsheets()
    ss = next((s for s in spreadsheets if s["id"] == sid), None)
    if not ss:
        abort(404)
    title = request.form.get("title", "").strip()
    if title:
        ss["title"] = title
        ss["updated_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        _save_spreadsheets(spreadsheets)
    return redirect(url_for("spreadsheets-slides.spreadsheet_view", sid=sid))


@blueprint.route("/presentation/<int:pid>/update", methods=["POST"])
def form_update_presentation(pid):
    """Update presentation title via form."""
    if "user_id" not in session:
        return jsonify({"error": "Authentication required"}), 401
    presentations = _load_presentations()
    pres = next((p for p in presentations if p["id"] == pid), None)
    if not pres:
        abort(404)
    title = request.form.get("title", "").strip()
    if title:
        pres["title"] = title
        pres["updated_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        _save_presentations(presentations)
    return redirect(url_for("spreadsheets-slides.presentation_view", pid=pid))


@blueprint.route("/spreadsheet/<int:sid>/share", methods=["POST"])
def form_share_spreadsheet(sid):
    """Share a spreadsheet with a user via form."""
    if "user_id" not in session:
        return jsonify({"error": "Authentication required"}), 401
    spreadsheets = _load_spreadsheets()
    ss = next((s for s in spreadsheets if s["id"] == sid), None)
    if not ss:
        abort(404)
    user_id = request.form.get("user_id", type=int)
    if user_id and user_id not in ss.get("shared_with", []):
        ss.setdefault("shared_with", []).append(user_id)
        ss["updated_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        _save_spreadsheets(spreadsheets)
    return redirect(url_for("spreadsheets-slides.spreadsheet_view", sid=sid))


@blueprint.route("/presentation/<int:pid>/share", methods=["POST"])
def form_share_presentation(pid):
    """Share a presentation with a user via form."""
    if "user_id" not in session:
        return jsonify({"error": "Authentication required"}), 401
    presentations = _load_presentations()
    pres = next((p for p in presentations if p["id"] == pid), None)
    if not pres:
        abort(404)
    user_id = request.form.get("user_id", type=int)
    if user_id and user_id not in pres.get("shared_with", []):
        pres.setdefault("shared_with", []).append(user_id)
        pres["updated_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        _save_presentations(presentations)
    return redirect(url_for("spreadsheets-slides.presentation_view", pid=pid))


# ---------------------------------------------------------------------------
# API routes - Files (unified)
# ---------------------------------------------------------------------------

@blueprint.route("/api/files")
def api_files():
    """List all files (spreadsheets + presentations). Supports: q, type, owner_id, sort."""
    spreadsheets = _load_spreadsheets()
    presentations = _load_presentations()

    q = request.args.get("q", "").strip()
    file_type = request.args.get("type", "").strip()
    owner_id = request.args.get("owner_id", type=int)
    sort = request.args.get("sort", "updated").strip()

    files = []
    for s in spreadsheets:
        files.append({
            "id": s["id"],
            "title": s["title"],
            "file_type": "spreadsheet",
            "owner_id": s["owner_id"],
            "created_at": s.get("created_at", ""),
            "updated_at": s.get("updated_at", ""),
            "shared_with": s.get("shared_with", []),
            "sheets_count": len(s.get("sheets", [])),
        })
    for p in presentations:
        files.append({
            "id": p["id"],
            "title": p["title"],
            "file_type": "presentation",
            "owner_id": p["owner_id"],
            "created_at": p.get("created_at", ""),
            "updated_at": p.get("updated_at", ""),
            "shared_with": p.get("shared_with", []),
            "slides_count": p.get("slides_count", 0),
        })

    if q:
        q_lower = q.lower()
        files = [f for f in files if q_lower in f["title"].lower()]
    if file_type:
        files = [f for f in files if f["file_type"] == file_type]
    if owner_id is not None:
        files = [f for f in files if f["owner_id"] == owner_id]

    if sort == "title":
        files.sort(key=lambda f: f["title"].lower())
    elif sort == "created":
        files.sort(key=lambda f: f.get("created_at", ""), reverse=True)
    else:
        files.sort(key=lambda f: f.get("updated_at", ""), reverse=True)

    return jsonify(files)


# ---------------------------------------------------------------------------
# API routes - Spreadsheets
# ---------------------------------------------------------------------------

@blueprint.route("/api/spreadsheets")
def api_spreadsheets_list():
    """List all spreadsheets. Supports: q, owner_id."""
    spreadsheets = _load_spreadsheets()
    q = request.args.get("q", "").strip()
    owner_id = request.args.get("owner_id", type=int)

    if q:
        q_lower = q.lower()
        spreadsheets = [s for s in spreadsheets if q_lower in s["title"].lower()]
    if owner_id is not None:
        spreadsheets = [s for s in spreadsheets if s["owner_id"] == owner_id]

    # Return lightweight list (no sheet data)
    result = []
    for s in spreadsheets:
        result.append({
            "id": s["id"],
            "title": s["title"],
            "owner_id": s["owner_id"],
            "created_at": s.get("created_at", ""),
            "updated_at": s.get("updated_at", ""),
            "shared_with": s.get("shared_with", []),
            "rows": s.get("rows", 0),
            "cols": s.get("cols", 0),
            "sheets_count": len(s.get("sheets", [])),
            "sheet_names": [sh["name"] for sh in s.get("sheets", [])],
        })
    return jsonify(result)


@blueprint.route("/api/spreadsheets", methods=["POST"])
def api_create_spreadsheet():
    """Create a new spreadsheet."""
    data = request.get_json(silent=True) or {}
    title = data.get("title", "Untitled Spreadsheet").strip()
    owner_id = data.get("owner_id")

    if not owner_id:
        return jsonify({"error": "owner_id required"}), 400

    spreadsheets = _load_spreadsheets()
    new_id = max((s["id"] for s in spreadsheets), default=0) + 1
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    rows = data.get("rows", 20)
    cols = data.get("cols", 10)
    empty_row = [""] * cols
    empty_data = [list(empty_row) for _ in range(rows)]

    new_ss = {
        "id": new_id,
        "title": title,
        "owner_id": owner_id,
        "created_at": now,
        "updated_at": now,
        "shared_with": data.get("shared_with", []),
        "rows": rows,
        "cols": cols,
        "sheets": [{"name": data.get("sheet_name", "Sheet 1"), "data": empty_data}],
    }
    spreadsheets.append(new_ss)
    _save_spreadsheets(spreadsheets)

    emit("file_created", user_id=owner_id, filename=title, file_type="spreadsheet", source_site="spreadsheets-slides", source_id=new_id)

    return jsonify(new_ss), 201


@blueprint.route("/api/spreadsheets/<int:sid>")
def api_spreadsheet_get(sid):
    """Get a single spreadsheet by ID (includes full sheet data)."""
    spreadsheets = _load_spreadsheets()
    ss = next((s for s in spreadsheets if s["id"] == sid), None)
    if ss is None:
        return jsonify({"error": "Spreadsheet not found"}), 404
    return jsonify(ss)


@blueprint.route("/api/spreadsheets/<int:sid>", methods=["PUT"])
def api_spreadsheet_update(sid):
    """Update a spreadsheet (title, shared_with, sheet data)."""
    data = request.get_json(silent=True) or {}
    spreadsheets = _load_spreadsheets()
    ss = next((s for s in spreadsheets if s["id"] == sid), None)
    if ss is None:
        return jsonify({"error": "Spreadsheet not found"}), 404

    changed = False
    if "title" in data:
        ss["title"] = data["title"].strip()
        changed = True
    if "shared_with" in data:
        ss["shared_with"] = data["shared_with"]
        changed = True
    if "sheets" in data:
        ss["sheets"] = data["sheets"]
        changed = True

    if changed:
        ss["updated_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        _save_spreadsheets(spreadsheets)

    return jsonify(ss)


@blueprint.route("/api/spreadsheets/<int:sid>", methods=["DELETE"])
def api_spreadsheet_delete(sid):
    """Delete a spreadsheet."""
    spreadsheets = _load_spreadsheets()
    ss = next((s for s in spreadsheets if s["id"] == sid), None)
    if ss is None:
        return jsonify({"error": "Spreadsheet not found"}), 404
    spreadsheets = [s for s in spreadsheets if s["id"] != sid]
    _save_spreadsheets(spreadsheets)
    return jsonify({"action": "deleted", "id": sid})


@blueprint.route("/api/spreadsheets/<int:sid>/cell", methods=["PUT"])
def api_spreadsheet_cell_update(sid):
    """Update a single cell in a spreadsheet.

    JSON body: {sheet: 0, row: 0, col: 0, value: "new value"}
    """
    data = request.get_json(silent=True) or {}
    sheet_idx = data.get("sheet", 0)
    row = data.get("row")
    col = data.get("col")
    value = data.get("value", "")

    if row is None or col is None:
        return jsonify({"error": "row and col required"}), 400

    spreadsheets = _load_spreadsheets()
    ss = next((s for s in spreadsheets if s["id"] == sid), None)
    if ss is None:
        return jsonify({"error": "Spreadsheet not found"}), 404

    sheets = ss.get("sheets", [])
    if sheet_idx < 0 or sheet_idx >= len(sheets):
        return jsonify({"error": "Invalid sheet index"}), 400

    grid = sheets[sheet_idx]["data"]

    # Expand grid if necessary
    while len(grid) <= row:
        grid.append([""] * ss.get("cols", 10))
    while len(grid[row]) <= col:
        grid[row].append("")

    old_value = grid[row][col]
    grid[row][col] = str(value)
    ss["updated_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    _save_spreadsheets(spreadsheets)

    return jsonify({
        "id": sid,
        "sheet": sheet_idx,
        "row": row,
        "col": col,
        "old_value": old_value,
        "new_value": str(value),
    })


# ---------------------------------------------------------------------------
# API routes - Presentations
# ---------------------------------------------------------------------------

@blueprint.route("/api/presentations")
def api_presentations_list():
    """List all presentations. Supports: q, owner_id."""
    presentations = _load_presentations()
    q = request.args.get("q", "").strip()
    owner_id = request.args.get("owner_id", type=int)

    if q:
        q_lower = q.lower()
        presentations = [p for p in presentations if q_lower in p["title"].lower()]
    if owner_id is not None:
        presentations = [p for p in presentations if p["owner_id"] == owner_id]

    # Return lightweight list (no full slide content)
    result = []
    for p in presentations:
        result.append({
            "id": p["id"],
            "title": p["title"],
            "owner_id": p["owner_id"],
            "created_at": p.get("created_at", ""),
            "updated_at": p.get("updated_at", ""),
            "shared_with": p.get("shared_with", []),
            "slides_count": p.get("slides_count", 0),
            "slide_titles": [sl.get("title", "") for sl in p.get("slides", [])],
        })
    return jsonify(result)


@blueprint.route("/api/presentations", methods=["POST"])
def api_create_presentation():
    """Create a new presentation."""
    data = request.get_json(silent=True) or {}
    title = data.get("title", "Untitled Presentation").strip()
    owner_id = data.get("owner_id")

    if not owner_id:
        return jsonify({"error": "owner_id required"}), 400

    presentations = _load_presentations()
    new_id = max((p["id"] for p in presentations), default=0) + 1
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    initial_slides = data.get("slides", [{"title": "Title Slide", "content": title, "notes": ""}])

    new_pres = {
        "id": new_id,
        "title": title,
        "owner_id": owner_id,
        "created_at": now,
        "updated_at": now,
        "shared_with": data.get("shared_with", []),
        "slides_count": len(initial_slides),
        "slides": initial_slides,
    }
    presentations.append(new_pres)
    _save_presentations(presentations)

    emit("file_created", user_id=owner_id, filename=title, file_type="presentation", source_site="spreadsheets-slides", source_id=new_id)

    return jsonify(new_pres), 201


@blueprint.route("/api/presentations/<int:pid>")
def api_presentation_get(pid):
    """Get a single presentation by ID (includes full slide data)."""
    presentations = _load_presentations()
    pres = next((p for p in presentations if p["id"] == pid), None)
    if pres is None:
        return jsonify({"error": "Presentation not found"}), 404
    return jsonify(pres)


@blueprint.route("/api/presentations/<int:pid>", methods=["PUT"])
def api_presentation_update(pid):
    """Update a presentation (title, shared_with, slides)."""
    data = request.get_json(silent=True) or {}
    presentations = _load_presentations()
    pres = next((p for p in presentations if p["id"] == pid), None)
    if pres is None:
        return jsonify({"error": "Presentation not found"}), 404

    changed = False
    if "title" in data:
        pres["title"] = data["title"].strip()
        changed = True
    if "shared_with" in data:
        pres["shared_with"] = data["shared_with"]
        changed = True
    if "slides" in data:
        pres["slides"] = data["slides"]
        pres["slides_count"] = len(data["slides"])
        changed = True

    if changed:
        pres["updated_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        _save_presentations(presentations)

    return jsonify(pres)


@blueprint.route("/api/presentations/<int:pid>", methods=["DELETE"])
def api_presentation_delete(pid):
    """Delete a presentation."""
    presentations = _load_presentations()
    pres = next((p for p in presentations if p["id"] == pid), None)
    if pres is None:
        return jsonify({"error": "Presentation not found"}), 404
    presentations = [p for p in presentations if p["id"] != pid]
    _save_presentations(presentations)
    return jsonify({"action": "deleted", "id": pid})


@blueprint.route("/api/presentations/<int:pid>/slides", methods=["POST"])
def api_presentation_add_slide(pid):
    """Add a new slide to a presentation.

    JSON body: {title: "...", content: "...", notes: "...", position: N (optional)}
    """
    data = request.get_json(silent=True) or {}
    presentations = _load_presentations()
    pres = next((p for p in presentations if p["id"] == pid), None)
    if pres is None:
        return jsonify({"error": "Presentation not found"}), 404

    new_slide = {
        "title": data.get("title", "New Slide"),
        "content": data.get("content", ""),
        "notes": data.get("notes", ""),
    }

    position = data.get("position")
    slides = pres.get("slides", [])
    if position is not None and 0 <= position <= len(slides):
        slides.insert(position, new_slide)
    else:
        slides.append(new_slide)

    pres["slides"] = slides
    pres["slides_count"] = len(slides)
    pres["updated_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    _save_presentations(presentations)

    return jsonify({
        "id": pid,
        "slides_count": pres["slides_count"],
        "new_slide": new_slide,
        "position": position if position is not None else len(slides) - 1,
    }), 201


# ---------------------------------------------------------------------------
# API routes - Templates
# ---------------------------------------------------------------------------

@blueprint.route("/api/templates")
def api_templates():
    """List all templates. Supports: type (spreadsheet|presentation), category."""
    templates = _load_templates()
    ttype = request.args.get("type", "").strip()
    category = request.args.get("category", "").strip()

    if ttype:
        templates = [t for t in templates if t["type"] == ttype]
    if category:
        cat_lower = category.lower()
        templates = [t for t in templates if cat_lower in t.get("category", "").lower()]

    return jsonify(templates)


# ---------------------------------------------------------------------------
# API routes - Stats
# ---------------------------------------------------------------------------

@blueprint.route("/api/stats")
def api_stats():
    """Aggregate statistics about all files."""
    spreadsheets = _load_spreadsheets()
    presentations = _load_presentations()
    templates = _load_templates()
    users = _load_users()

    total_sheets = sum(len(s.get("sheets", [])) for s in spreadsheets)
    total_slides = sum(p.get("slides_count", 0) for p in presentations)

    # Unique owners
    ss_owners = set(s["owner_id"] for s in spreadsheets)
    pres_owners = set(p["owner_id"] for p in presentations)
    all_owners = ss_owners | pres_owners

    # Shared counts
    shared_ss = sum(1 for s in spreadsheets if s.get("shared_with"))
    shared_pres = sum(1 for p in presentations if p.get("shared_with"))

    return jsonify({
        "total_spreadsheets": len(spreadsheets),
        "total_presentations": len(presentations),
        "total_sheets": total_sheets,
        "total_slides": total_slides,
        "total_templates": len(templates),
        "total_users": len(users),
        "unique_owners": len(all_owners),
        "shared_spreadsheets": shared_ss,
        "shared_presentations": shared_pres,
    })


# ---------------------------------------------------------------------------
# API routes - Auth
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


@blueprint.route("/api/users")
def api_users():
    """List all users (passwords excluded)."""
    users = _load_users()
    return jsonify([{k: v for k, v in u.items() if k != "password"} for u in users])


# ---------------------------------------------------------------------------
# Macro-support routes: navigate_by_semantic
# ---------------------------------------------------------------------------

def _semantic_score(query, text):
    """Simple keyword-overlap score for semantic search."""
    terms = query.lower().split()
    text_lower = text.lower()
    return sum(1 for t in terms if t in text_lower)


@blueprint.route("/api/files/search")
def api_files_search():
    """Semantic search across all files. Supports: q (required).

    Searches file titles and, for spreadsheets, sheet names and cell contents.
    For presentations, searches slide titles and content.
    Returns files ranked by relevance score.
    """
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    spreadsheets = _load_spreadsheets()
    presentations = _load_presentations()

    scored = []
    for s in spreadsheets:
        text_parts = [s["title"]]
        for sh in s.get("sheets", []):
            text_parts.append(sh.get("name", ""))
            for row in sh.get("data", []):
                text_parts.extend(str(c) for c in row if c)
        full_text = " ".join(text_parts)
        score = _semantic_score(q, full_text)
        if score > 0:
            scored.append((score, {
                "id": s["id"],
                "title": s["title"],
                "file_type": "spreadsheet",
                "owner_id": s["owner_id"],
                "relevance_score": score,
            }))

    for p in presentations:
        text_parts = [p["title"]]
        for sl in p.get("slides", []):
            text_parts.append(sl.get("title", ""))
            text_parts.append(sl.get("content", ""))
        full_text = " ".join(text_parts)
        score = _semantic_score(q, full_text)
        if score > 0:
            scored.append((score, {
                "id": p["id"],
                "title": p["title"],
                "file_type": "presentation",
                "owner_id": p["owner_id"],
                "relevance_score": score,
            }))

    scored.sort(key=lambda x: -x[0])
    return jsonify([item for _, item in scored])


# ---------------------------------------------------------------------------
# Macro-support routes: navigate_from_table
# ---------------------------------------------------------------------------

@blueprint.route("/api/spreadsheets/<int:sid>/cell/<int:row>/<int:col>")
def api_spreadsheet_cell_navigate(sid, row, col):
    """Navigate to a specific cell in a spreadsheet and return its value
    along with the row and column context (header).

    Supports navigate_from_table macro: click a cell in a table to drill-down.
    """
    spreadsheets = _load_spreadsheets()
    ss = next((s for s in spreadsheets if s["id"] == sid), None)
    if ss is None:
        return jsonify({"error": "Spreadsheet not found"}), 404

    sheet_idx = request.args.get("sheet", 0, type=int)
    sheets = ss.get("sheets", [])
    if sheet_idx < 0 or sheet_idx >= len(sheets):
        return jsonify({"error": "Invalid sheet index"}), 400

    grid = sheets[sheet_idx]["data"]
    if row < 0 or row >= len(grid):
        return jsonify({"error": "Row out of range"}), 400
    if col < 0 or col >= len(grid[row]):
        return jsonify({"error": "Column out of range"}), 400

    # Build context: header row (row 0) and full row data
    header = grid[0] if len(grid) > 0 else []
    col_header = header[col] if col < len(header) else f"Col {col}"
    row_header = grid[row][0] if len(grid[row]) > 0 else f"Row {row}"

    return jsonify({
        "spreadsheet_id": sid,
        "spreadsheet_title": ss["title"],
        "sheet": sheet_idx,
        "sheet_name": sheets[sheet_idx]["name"],
        "row": row,
        "col": col,
        "cell_ref": f"{chr(65 + col)}{row + 1}" if col < 26 else f"Col{col}Row{row + 1}",
        "value": grid[row][col],
        "column_header": col_header,
        "row_header": row_header,
        "row_data": grid[row],
    })


# ---------------------------------------------------------------------------
# Macro-support routes: extract_by_code (cell reference like A1, B3)
# ---------------------------------------------------------------------------

def _parse_cell_ref(ref):
    """Parse a cell reference like 'A1', 'B3', 'AA10' into (row, col) 0-indexed."""
    import re
    m = re.match(r'^([A-Z]+)(\d+)$', ref.upper().strip())
    if not m:
        return None, None
    col_str = m.group(1)
    row_num = int(m.group(2)) - 1  # 0-indexed

    col_num = 0
    for c in col_str:
        col_num = col_num * 26 + (ord(c) - ord('A') + 1)
    col_num -= 1  # 0-indexed

    return row_num, col_num


@blueprint.route("/api/spreadsheets/<int:sid>/ref/<ref>")
def api_spreadsheet_cell_by_ref(sid, ref):
    """Get a cell value by cell reference code (e.g., A1, B3, C10).

    Supports extract_by_code macro.
    """
    spreadsheets = _load_spreadsheets()
    ss = next((s for s in spreadsheets if s["id"] == sid), None)
    if ss is None:
        return jsonify({"error": "Spreadsheet not found"}), 404

    sheet_idx = request.args.get("sheet", 0, type=int)
    sheets = ss.get("sheets", [])
    if sheet_idx < 0 or sheet_idx >= len(sheets):
        return jsonify({"error": "Invalid sheet index"}), 400

    row, col = _parse_cell_ref(ref)
    if row is None:
        return jsonify({"error": f"Invalid cell reference: {ref}"}), 400

    grid = sheets[sheet_idx]["data"]
    if row < 0 or row >= len(grid) or col < 0 or col >= len(grid[row]):
        return jsonify({"error": f"Cell {ref} is out of range"}), 400

    return jsonify({
        "spreadsheet_id": sid,
        "sheet": sheet_idx,
        "ref": ref.upper(),
        "row": row,
        "col": col,
        "value": grid[row][col],
    })


@blueprint.route("/api/spreadsheets/<int:sid>/range/<range_ref>")
def api_spreadsheet_range(sid, range_ref):
    """Get a range of cell values (e.g., A1:C5, B2:B10).

    Supports extract_by_code macro for ranges.
    """
    spreadsheets = _load_spreadsheets()
    ss = next((s for s in spreadsheets if s["id"] == sid), None)
    if ss is None:
        return jsonify({"error": "Spreadsheet not found"}), 404

    sheet_idx = request.args.get("sheet", 0, type=int)
    sheets = ss.get("sheets", [])
    if sheet_idx < 0 or sheet_idx >= len(sheets):
        return jsonify({"error": "Invalid sheet index"}), 400

    parts = range_ref.upper().split(":")
    if len(parts) != 2:
        return jsonify({"error": "Range must be in format A1:C5"}), 400

    r1, c1 = _parse_cell_ref(parts[0])
    r2, c2 = _parse_cell_ref(parts[1])
    if r1 is None or r2 is None:
        return jsonify({"error": "Invalid cell references in range"}), 400

    grid = sheets[sheet_idx]["data"]
    values = []
    for r in range(r1, min(r2 + 1, len(grid))):
        row_vals = []
        for c in range(c1, min(c2 + 1, len(grid[r]) if r < len(grid) else 0)):
            row_vals.append(grid[r][c])
        values.append(row_vals)

    return jsonify({
        "spreadsheet_id": sid,
        "sheet": sheet_idx,
        "range": range_ref.upper(),
        "values": values,
    })


# ---------------------------------------------------------------------------
# Macro-support routes: extract_by_slider (filter by threshold)
# ---------------------------------------------------------------------------

@blueprint.route("/api/spreadsheets/<int:sid>/filter")
def api_spreadsheet_filter_by_threshold(sid):
    """Filter rows in a spreadsheet by a numeric threshold on a column.

    Query params: column (int, 0-indexed), min_value, max_value, sheet (default 0).
    Supports extract_by_slider macro.
    """
    spreadsheets = _load_spreadsheets()
    ss = next((s for s in spreadsheets if s["id"] == sid), None)
    if ss is None:
        return jsonify({"error": "Spreadsheet not found"}), 404

    sheet_idx = request.args.get("sheet", 0, type=int)
    col = request.args.get("column", type=int)
    min_val = request.args.get("min_value", type=float)
    max_val = request.args.get("max_value", type=float)

    if col is None:
        return jsonify({"error": "column parameter required"}), 400

    sheets = ss.get("sheets", [])
    if sheet_idx < 0 or sheet_idx >= len(sheets):
        return jsonify({"error": "Invalid sheet index"}), 400

    grid = sheets[sheet_idx]["data"]
    header = grid[0] if len(grid) > 0 else []

    matching_rows = []
    for i, row in enumerate(grid[1:], 1):  # skip header
        if col >= len(row) or not row[col]:
            continue
        # Try to parse as numeric
        cell_val = row[col].replace(",", "").replace("$", "").replace("%", "").strip()
        try:
            num = float(cell_val)
        except (ValueError, TypeError):
            continue
        if min_val is not None and num < min_val:
            continue
        if max_val is not None and num > max_val:
            continue
        matching_rows.append({"row_index": i, "data": row, "filter_value": num})

    return jsonify({
        "spreadsheet_id": sid,
        "sheet": sheet_idx,
        "column": col,
        "column_header": header[col] if col < len(header) else f"Col {col}",
        "min_value": min_val,
        "max_value": max_val,
        "matching_count": len(matching_rows),
        "rows": matching_rows,
    })


# ---------------------------------------------------------------------------
# Macro-support routes: compute_by_query (text-based column computation)
# ---------------------------------------------------------------------------

@blueprint.route("/api/spreadsheets/<int:sid>/compute")
def api_spreadsheet_compute(sid):
    """Compute aggregate values on a spreadsheet column.

    Query params:
    - column (int, 0-indexed): column to compute on
    - operation: sum, avg, count, min, max, median
    - sheet (default 0)

    Supports compute_by_query macro.
    """
    spreadsheets = _load_spreadsheets()
    ss = next((s for s in spreadsheets if s["id"] == sid), None)
    if ss is None:
        return jsonify({"error": "Spreadsheet not found"}), 404

    sheet_idx = request.args.get("sheet", 0, type=int)
    col = request.args.get("column", type=int)
    operation = request.args.get("operation", "sum").lower().strip()

    if col is None:
        return jsonify({"error": "column parameter required"}), 400

    sheets = ss.get("sheets", [])
    if sheet_idx < 0 or sheet_idx >= len(sheets):
        return jsonify({"error": "Invalid sheet index"}), 400

    grid = sheets[sheet_idx]["data"]
    header = grid[0] if len(grid) > 0 else []

    # Extract numeric values from the column (skip header row)
    values = []
    for row in grid[1:]:
        if col >= len(row) or not row[col]:
            continue
        cell_val = str(row[col]).replace(",", "").replace("$", "").replace("%", "").strip()
        try:
            values.append(float(cell_val))
        except (ValueError, TypeError):
            continue

    if not values:
        return jsonify({
            "spreadsheet_id": sid,
            "sheet": sheet_idx,
            "column": col,
            "column_header": header[col] if col < len(header) else f"Col {col}",
            "operation": operation,
            "result": None,
            "error": "No numeric values found in column",
        })

    result = None
    if operation == "sum":
        result = sum(values)
    elif operation in ("avg", "average", "mean"):
        result = sum(values) / len(values)
    elif operation == "count":
        result = len(values)
    elif operation == "min":
        result = min(values)
    elif operation == "max":
        result = max(values)
    elif operation == "median":
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        if n % 2 == 0:
            result = (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2
        else:
            result = sorted_vals[n // 2]
    else:
        return jsonify({"error": f"Unknown operation: {operation}"}), 400

    return jsonify({
        "spreadsheet_id": sid,
        "sheet": sheet_idx,
        "column": col,
        "column_header": header[col] if col < len(header) else f"Col {col}",
        "operation": operation,
        "result": round(result, 2) if result is not None else None,
        "value_count": len(values),
    })


# ---------------------------------------------------------------------------
# Macro-support routes: compute_by_extremum (find min/max)
# ---------------------------------------------------------------------------

@blueprint.route("/api/spreadsheets/<int:sid>/extremum")
def api_spreadsheet_extremum(sid):
    """Find the row with the minimum or maximum value in a given column.

    Query params:
    - column (int, 0-indexed)
    - direction: min or max
    - sheet (default 0)

    Supports compute_by_extremum macro.
    """
    spreadsheets = _load_spreadsheets()
    ss = next((s for s in spreadsheets if s["id"] == sid), None)
    if ss is None:
        return jsonify({"error": "Spreadsheet not found"}), 404

    sheet_idx = request.args.get("sheet", 0, type=int)
    col = request.args.get("column", type=int)
    direction = request.args.get("direction", "max").lower().strip()

    if col is None:
        return jsonify({"error": "column parameter required"}), 400

    sheets = ss.get("sheets", [])
    if sheet_idx < 0 or sheet_idx >= len(sheets):
        return jsonify({"error": "Invalid sheet index"}), 400

    grid = sheets[sheet_idx]["data"]
    header = grid[0] if len(grid) > 0 else []

    best_row = None
    best_val = None
    best_idx = None

    for i, row in enumerate(grid[1:], 1):  # skip header
        if col >= len(row) or not row[col]:
            continue
        cell_val = str(row[col]).replace(",", "").replace("$", "").replace("%", "").strip()
        try:
            num = float(cell_val)
        except (ValueError, TypeError):
            continue
        if best_val is None:
            best_val = num
            best_row = row
            best_idx = i
        elif direction == "max" and num > best_val:
            best_val = num
            best_row = row
            best_idx = i
        elif direction == "min" and num < best_val:
            best_val = num
            best_row = row
            best_idx = i

    if best_row is None:
        return jsonify({"error": "No numeric values found"}), 400

    return jsonify({
        "spreadsheet_id": sid,
        "sheet": sheet_idx,
        "column": col,
        "column_header": header[col] if col < len(header) else f"Col {col}",
        "direction": direction,
        "row_index": best_idx,
        "value": best_val,
        "row_data": best_row,
    })


# ---------------------------------------------------------------------------
# Macro-support routes: compute_by_slider (compute at threshold)
# ---------------------------------------------------------------------------

@blueprint.route("/api/spreadsheets/<int:sid>/compute_at_threshold")
def api_spreadsheet_compute_at_threshold(sid):
    """Compute an aggregate on rows that pass a threshold filter.

    Query params:
    - filter_column (int): column to apply threshold on
    - threshold (float): threshold value
    - compare: gte (>=), lte (<=), gt (>), lt (<), eq (==)
    - compute_column (int): column to compute on
    - operation: sum, avg, count, min, max
    - sheet (default 0)

    Supports compute_by_slider macro.
    """
    spreadsheets = _load_spreadsheets()
    ss = next((s for s in spreadsheets if s["id"] == sid), None)
    if ss is None:
        return jsonify({"error": "Spreadsheet not found"}), 404

    sheet_idx = request.args.get("sheet", 0, type=int)
    filter_col = request.args.get("filter_column", type=int)
    threshold = request.args.get("threshold", type=float)
    compare = request.args.get("compare", "gte").lower().strip()
    compute_col = request.args.get("compute_column", type=int)
    operation = request.args.get("operation", "sum").lower().strip()

    if filter_col is None or threshold is None or compute_col is None:
        return jsonify({"error": "filter_column, threshold, and compute_column required"}), 400

    sheets = ss.get("sheets", [])
    if sheet_idx < 0 or sheet_idx >= len(sheets):
        return jsonify({"error": "Invalid sheet index"}), 400

    grid = sheets[sheet_idx]["data"]
    header = grid[0] if len(grid) > 0 else []

    ops = {"gte": lambda v, t: v >= t, "lte": lambda v, t: v <= t,
           "gt": lambda v, t: v > t, "lt": lambda v, t: v < t,
           "eq": lambda v, t: v == t}
    cmp_fn = ops.get(compare)
    if cmp_fn is None:
        return jsonify({"error": f"Unknown compare operator: {compare}"}), 400

    compute_values = []
    for row in grid[1:]:
        if filter_col >= len(row) or not row[filter_col]:
            continue
        try:
            fv = float(str(row[filter_col]).replace(",", "").replace("$", "").replace("%", "").strip())
        except (ValueError, TypeError):
            continue
        if not cmp_fn(fv, threshold):
            continue
        if compute_col >= len(row) or not row[compute_col]:
            continue
        try:
            cv = float(str(row[compute_col]).replace(",", "").replace("$", "").replace("%", "").strip())
        except (ValueError, TypeError):
            continue
        compute_values.append(cv)

    if not compute_values:
        return jsonify({
            "spreadsheet_id": sid,
            "result": None,
            "matching_rows": 0,
            "error": "No matching rows",
        })

    if operation == "sum":
        result = sum(compute_values)
    elif operation in ("avg", "average", "mean"):
        result = sum(compute_values) / len(compute_values)
    elif operation == "count":
        result = len(compute_values)
    elif operation == "min":
        result = min(compute_values)
    elif operation == "max":
        result = max(compute_values)
    else:
        return jsonify({"error": f"Unknown operation: {operation}"}), 400

    return jsonify({
        "spreadsheet_id": sid,
        "sheet": sheet_idx,
        "filter_column": filter_col,
        "filter_header": header[filter_col] if filter_col < len(header) else "",
        "threshold": threshold,
        "compare": compare,
        "compute_column": compute_col,
        "compute_header": header[compute_col] if compute_col < len(header) else "",
        "operation": operation,
        "result": round(result, 2),
        "matching_rows": len(compute_values),
    })


# ---------------------------------------------------------------------------
# Macro-support routes: submit_from_table (batch cell update via form)
# ---------------------------------------------------------------------------

@blueprint.route("/spreadsheet/<int:sid>/submit", methods=["POST"])
def form_submit_spreadsheet(sid):
    """Submit bulk cell edits from a table form.

    Form fields: cell_<row>_<col>=value (e.g., cell_1_3=42)
    Supports submit_from_table macro.
    """
    spreadsheets = _load_spreadsheets()
    ss = next((s for s in spreadsheets if s["id"] == sid), None)
    if not ss:
        abort(404)

    sheet_idx = request.form.get("sheet", 0, type=int)
    sheets = ss.get("sheets", [])
    if sheet_idx < 0 or sheet_idx >= len(sheets):
        abort(400)

    grid = sheets[sheet_idx]["data"]
    changes = 0

    for key, value in request.form.items():
        if key.startswith("cell_"):
            parts = key.split("_")
            if len(parts) == 3:
                try:
                    r, c = int(parts[1]), int(parts[2])
                    while len(grid) <= r:
                        grid.append([""] * ss.get("cols", 10))
                    while len(grid[r]) <= c:
                        grid[r].append("")
                    if grid[r][c] != str(value):
                        grid[r][c] = str(value)
                        changes += 1
                except (ValueError, IndexError):
                    continue

    if changes > 0:
        ss["updated_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        _save_spreadsheets(spreadsheets)

    return redirect(url_for("spreadsheets-slides.spreadsheet_view", sid=sid, sheet=sheet_idx))


@blueprint.route("/api/spreadsheets/<int:sid>/batch", methods=["PUT"])
def api_spreadsheet_batch_update(sid):
    """Batch update multiple cells in a spreadsheet.

    JSON body: {sheet: 0, updates: [{row: 1, col: 2, value: "new"}, ...]}
    Supports submit_from_table macro via API.
    """
    data = request.get_json(silent=True) or {}
    sheet_idx = data.get("sheet", 0)
    updates = data.get("updates", [])

    if not updates:
        return jsonify({"error": "No updates provided"}), 400

    spreadsheets = _load_spreadsheets()
    ss = next((s for s in spreadsheets if s["id"] == sid), None)
    if ss is None:
        return jsonify({"error": "Spreadsheet not found"}), 404

    sheets = ss.get("sheets", [])
    if sheet_idx < 0 or sheet_idx >= len(sheets):
        return jsonify({"error": "Invalid sheet index"}), 400

    grid = sheets[sheet_idx]["data"]
    applied = []

    for upd in updates:
        r, c, v = upd.get("row"), upd.get("col"), upd.get("value", "")
        if r is None or c is None:
            continue
        while len(grid) <= r:
            grid.append([""] * ss.get("cols", 10))
        while len(grid[r]) <= c:
            grid[r].append("")
        old = grid[r][c]
        grid[r][c] = str(v)
        applied.append({"row": r, "col": c, "old": old, "new": str(v)})

    ss["updated_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    _save_spreadsheets(spreadsheets)

    return jsonify({"spreadsheet_id": sid, "sheet": sheet_idx, "changes": applied})


# ---------------------------------------------------------------------------
# Macro-support routes: edit_by_query (edit cell by reference string)
# ---------------------------------------------------------------------------

@blueprint.route("/api/spreadsheets/<int:sid>/edit", methods=["PUT"])
def api_spreadsheet_edit_by_ref(sid):
    """Edit a cell by cell reference string (e.g., A1=42, B3=hello).

    JSON body: {ref: "A1", value: "42", sheet: 0}
    Supports edit_by_query macro.
    """
    data = request.get_json(silent=True) or {}
    ref = data.get("ref", "").strip()
    value = data.get("value", "")
    sheet_idx = data.get("sheet", 0)

    if not ref:
        return jsonify({"error": "ref parameter required (e.g., A1)"}), 400

    row, col = _parse_cell_ref(ref)
    if row is None:
        return jsonify({"error": f"Invalid cell reference: {ref}"}), 400

    spreadsheets = _load_spreadsheets()
    ss = next((s for s in spreadsheets if s["id"] == sid), None)
    if ss is None:
        return jsonify({"error": "Spreadsheet not found"}), 404

    sheets = ss.get("sheets", [])
    if sheet_idx < 0 or sheet_idx >= len(sheets):
        return jsonify({"error": "Invalid sheet index"}), 400

    grid = sheets[sheet_idx]["data"]
    while len(grid) <= row:
        grid.append([""] * ss.get("cols", 10))
    while len(grid[row]) <= col:
        grid[row].append("")

    old_value = grid[row][col]
    grid[row][col] = str(value)
    ss["updated_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    _save_spreadsheets(spreadsheets)

    return jsonify({
        "spreadsheet_id": sid,
        "sheet": sheet_idx,
        "ref": ref.upper(),
        "row": row,
        "col": col,
        "old_value": old_value,
        "new_value": str(value),
    })


# ---------------------------------------------------------------------------
# Macro-support routes: edit_by_form (update presentation slide via form)
# ---------------------------------------------------------------------------

@blueprint.route("/presentation/<int:pid>/slide/<int:slide_idx>/update", methods=["POST"])
def form_update_slide(pid, slide_idx):
    """Update a presentation slide via form submission.

    Form fields: title, content, notes.
    Supports edit_by_form macro.
    """
    presentations = _load_presentations()
    pres = next((p for p in presentations if p["id"] == pid), None)
    if not pres:
        abort(404)
    slides = pres.get("slides", [])
    if slide_idx < 0 or slide_idx >= len(slides):
        abort(400)

    slide = slides[slide_idx]
    title = request.form.get("title")
    content = request.form.get("content")
    notes = request.form.get("notes")

    if title is not None:
        slide["title"] = title.strip()
    if content is not None:
        slide["content"] = content.strip()
    if notes is not None:
        slide["notes"] = notes.strip()

    pres["updated_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    _save_presentations(presentations)

    return redirect(url_for("spreadsheets-slides.presentation_view", pid=pid, slide=slide_idx))


@blueprint.route("/api/presentations/<int:pid>/slides/<int:slide_idx>", methods=["PUT"])
def api_update_slide(pid, slide_idx):
    """Update a single slide by index.

    JSON body: {title: "...", content: "...", notes: "..."}
    Supports edit_by_form macro via API.
    """
    data = request.get_json(silent=True) or {}
    presentations = _load_presentations()
    pres = next((p for p in presentations if p["id"] == pid), None)
    if pres is None:
        return jsonify({"error": "Presentation not found"}), 404

    slides = pres.get("slides", [])
    if slide_idx < 0 or slide_idx >= len(slides):
        return jsonify({"error": "Invalid slide index"}), 400

    slide = slides[slide_idx]
    if "title" in data:
        slide["title"] = data["title"].strip()
    if "content" in data:
        slide["content"] = data["content"].strip()
    if "notes" in data:
        slide["notes"] = data["notes"].strip()

    pres["updated_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    _save_presentations(presentations)

    return jsonify({"presentation_id": pid, "slide_index": slide_idx, "slide": slide})


# ---------------------------------------------------------------------------
# Macro-support routes: delete_from_table (delete a row)
# ---------------------------------------------------------------------------

@blueprint.route("/api/spreadsheets/<int:sid>/row/<int:row_idx>", methods=["DELETE"])
def api_spreadsheet_delete_row(sid, row_idx):
    """Delete a row from a spreadsheet.

    Supports delete_from_table macro.
    """
    spreadsheets = _load_spreadsheets()
    ss = next((s for s in spreadsheets if s["id"] == sid), None)
    if ss is None:
        return jsonify({"error": "Spreadsheet not found"}), 404

    sheet_idx = request.args.get("sheet", 0, type=int)
    sheets = ss.get("sheets", [])
    if sheet_idx < 0 or sheet_idx >= len(sheets):
        return jsonify({"error": "Invalid sheet index"}), 400

    grid = sheets[sheet_idx]["data"]
    if row_idx < 0 or row_idx >= len(grid):
        return jsonify({"error": "Row index out of range"}), 400

    deleted_row = grid.pop(row_idx)
    # Append an empty row at the end to maintain grid size
    grid.append([""] * ss.get("cols", 10))

    ss["updated_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    _save_spreadsheets(spreadsheets)

    return jsonify({
        "spreadsheet_id": sid,
        "sheet": sheet_idx,
        "deleted_row_index": row_idx,
        "deleted_row": deleted_row,
    })


@blueprint.route("/api/presentations/<int:pid>/slides/<int:slide_idx>", methods=["DELETE"])
def api_delete_slide(pid, slide_idx):
    """Delete a slide from a presentation.

    Supports delete_from_table macro for presentations.
    """
    presentations = _load_presentations()
    pres = next((p for p in presentations if p["id"] == pid), None)
    if pres is None:
        return jsonify({"error": "Presentation not found"}), 404

    slides = pres.get("slides", [])
    if slide_idx < 0 or slide_idx >= len(slides):
        return jsonify({"error": "Invalid slide index"}), 400

    deleted = slides.pop(slide_idx)
    pres["slides_count"] = len(slides)
    pres["updated_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    _save_presentations(presentations)

    return jsonify({
        "presentation_id": pid,
        "deleted_slide_index": slide_idx,
        "deleted_slide": deleted,
        "remaining_slides": pres["slides_count"],
    })


# ---------------------------------------------------------------------------
# Macro-support routes: select_from_table (select rows/cells)
# ---------------------------------------------------------------------------

@blueprint.route("/api/spreadsheets/<int:sid>/select")
def api_spreadsheet_select(sid):
    """Select rows from a spreadsheet based on column value matching.

    Query params:
    - column (int): column index to match on
    - value: exact match value
    - contains: substring match
    - sheet (default 0)

    Returns matching rows. Supports select_from_table macro.
    """
    spreadsheets = _load_spreadsheets()
    ss = next((s for s in spreadsheets if s["id"] == sid), None)
    if ss is None:
        return jsonify({"error": "Spreadsheet not found"}), 404

    sheet_idx = request.args.get("sheet", 0, type=int)
    col = request.args.get("column", type=int)
    exact = request.args.get("value", "").strip()
    contains = request.args.get("contains", "").strip()

    if col is None:
        return jsonify({"error": "column parameter required"}), 400

    sheets = ss.get("sheets", [])
    if sheet_idx < 0 or sheet_idx >= len(sheets):
        return jsonify({"error": "Invalid sheet index"}), 400

    grid = sheets[sheet_idx]["data"]
    header = grid[0] if len(grid) > 0 else []

    matching = []
    for i, row in enumerate(grid[1:], 1):  # skip header
        if col >= len(row):
            continue
        cell = str(row[col])
        if exact and cell != exact:
            continue
        if contains and contains.lower() not in cell.lower():
            continue
        if not exact and not contains:
            # Without filters, return all non-empty rows
            if not cell.strip():
                continue
        matching.append({"row_index": i, "data": row})

    return jsonify({
        "spreadsheet_id": sid,
        "sheet": sheet_idx,
        "column": col,
        "column_header": header[col] if col < len(header) else f"Col {col}",
        "filter": {"value": exact, "contains": contains},
        "selected_count": len(matching),
        "rows": matching,
    })


# ---------------------------------------------------------------------------
# Macro-support routes: export_by_dropdown (export spreadsheet as CSV)
# ---------------------------------------------------------------------------

@blueprint.route("/api/spreadsheets/<int:sid>/export")
def api_spreadsheet_export(sid):
    """Export a spreadsheet as CSV or JSON.

    Query params:
    - format: csv (default) or json
    - sheet (default 0)

    Supports export_by_dropdown macro.
    """
    spreadsheets = _load_spreadsheets()
    ss = next((s for s in spreadsheets if s["id"] == sid), None)
    if ss is None:
        return jsonify({"error": "Spreadsheet not found"}), 404

    sheet_idx = request.args.get("sheet", 0, type=int)
    fmt = request.args.get("format", "csv").lower().strip()

    sheets = ss.get("sheets", [])
    if sheet_idx < 0 or sheet_idx >= len(sheets):
        return jsonify({"error": "Invalid sheet index"}), 400

    grid = sheets[sheet_idx]["data"]
    sheet_name = sheets[sheet_idx]["name"]

    if fmt == "csv":
        lines = []
        for row in grid:
            escaped = []
            for cell in row:
                cell_str = str(cell).replace('"', '""')
                if ',' in cell_str or '"' in cell_str or '\n' in cell_str:
                    cell_str = f'"{cell_str}"'
                escaped.append(cell_str)
            lines.append(",".join(escaped))
        filename = f"{ss['title'].replace(' ', '_')}_{sheet_name}.csv"
        return Response(
            "\n".join(lines),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    else:
        # JSON export — list of dicts using header row as keys
        if len(grid) < 2:
            return jsonify([])
        header = grid[0]
        rows = []
        for row in grid[1:]:
            if all(not c for c in row):
                continue
            obj = {}
            for j, h in enumerate(header):
                if h and j < len(row):
                    obj[h] = row[j]
            if obj:
                rows.append(obj)
        return jsonify(rows)


@blueprint.route("/api/export/all")
def api_export_all():
    """Export all files list as JSON or CSV.

    Query params:
    - format: json (default) or csv
    - type: spreadsheet or presentation (optional filter)

    Supports export_by_dropdown macro for full file list.
    """
    spreadsheets = _load_spreadsheets()
    presentations = _load_presentations()
    file_type = request.args.get("type", "").strip()
    fmt = request.args.get("format", "json").lower().strip()

    files = []
    if file_type != "presentation":
        for s in spreadsheets:
            files.append({
                "id": s["id"],
                "title": s["title"],
                "file_type": "spreadsheet",
                "owner_id": s["owner_id"],
                "sheets_count": len(s.get("sheets", [])),
                "created_at": s.get("created_at", ""),
                "updated_at": s.get("updated_at", ""),
            })
    if file_type != "spreadsheet":
        for p in presentations:
            files.append({
                "id": p["id"],
                "title": p["title"],
                "file_type": "presentation",
                "owner_id": p["owner_id"],
                "slides_count": p.get("slides_count", 0),
                "created_at": p.get("created_at", ""),
                "updated_at": p.get("updated_at", ""),
            })

    if fmt == "csv":
        lines = ["id,title,file_type,owner_id,items,created_at,updated_at"]
        for f in files:
            title = f["title"].replace('"', '""')
            items = f.get("sheets_count", f.get("slides_count", 0))
            lines.append(f'{f["id"]},"{title}",{f["file_type"]},{f["owner_id"]},{items},{f["created_at"]},{f["updated_at"]}')
        return Response("\n".join(lines), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=sheetdeck_export.csv"})

    return jsonify(files)

