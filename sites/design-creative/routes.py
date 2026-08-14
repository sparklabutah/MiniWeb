"""Design Creative — Canva-inspired design tool platform.

Data interpreter: loads synthesized JSON data files, respects config.
Templates are read-only; projects are mutable copies.
The editor is simplified — positioned HTML divs, not a real canvas.
"""
import pathlib
import copy
from datetime import datetime

from flask import Blueprint, Response, abort, jsonify, redirect, render_template, request, session, url_for
from app import db
from app.events import emit
from app.handlers.email_handler import _add_email
from helpers.auth import current_user

SITE = "design-creative"
SITE_DIR = pathlib.Path(__file__).resolve().parent
blueprint = Blueprint(
    "design-creative",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_templates():
    return db.query(SITE, "templates")


def _load_assets():
    # Stock asset library lives in the design_creative_assets table (a small,
    # <100-row catalog), seeded by sites/design-creative/seed_assets.py.
    # Session-uploaded assets are merged in from the overlay automatically.
    return db.query(SITE, "assets", sort="id")


def _get_asset(asset_id):
    return db.get_item(SITE, "assets", asset_id)


def _load_users():
    return db.query(SITE, "users")


def _save_users(users):
    db.save_collection(SITE, "users", users)


def _load_projects():
    return db.query(SITE, "projects")


def _save_projects(projects):
    db.save_collection(SITE, "projects", projects)


def _get_user(user_id):
    return db.get_item(SITE, "users", user_id)


def _get_current_user():
    return current_user(_get_user)


# ---------------------------------------------------------------------------
# Search helpers
# ---------------------------------------------------------------------------

def _search_templates(templates, query):
    if not query:
        return templates
    q = query.lower().strip()
    results = []
    for t in templates:
        text = (t["title"] + " " + t["description"] + " " + " ".join(t["tags"]) + " " + t["category"]).lower()
        if q in text:
            results.append(t)
    return results


def _search_assets(assets, query):
    if not query:
        return assets
    q = query.lower().strip()
    results = []
    for a in assets:
        text = (a["name"] + " " + a["type"] + " " + a["category"] + " " + " ".join(a["tags"])).lower()
        if q in text:
            results.append(a)
    return results


# ---------------------------------------------------------------------------
# Template categories
# ---------------------------------------------------------------------------

CATEGORIES = ["social-media", "presentation", "poster", "logo", "business-card", "flyer", "banner"]


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    templates = _load_templates()
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    sort = request.args.get("sort", "popular").strip()

    results = list(templates)
    if q:
        results = _search_templates(results, q)
    if category:
        results = [t for t in results if t["category"] == category]

    if sort == "popular":
        results.sort(key=lambda t: -t["use_count"])
    elif sort == "name":
        results.sort(key=lambda t: t["title"].lower())
    elif sort == "newest":
        results.sort(key=lambda t: t["id"], reverse=True)

    user = _get_current_user()
    return render_template("design-creative/index.html",
                           templates=results, categories=CATEGORIES,
                           q=q, category=category, sort=sort, user=user)


@blueprint.route("/template/<int:template_id>")
def template_detail(template_id):
    tmpl = db.get_item(SITE, "templates", template_id)
    if tmpl is None:
        abort(404)
    related = db.query(SITE, "templates", where={"category": tmpl["category"]}, limit=5)
    related = [t for t in related if t["id"] != template_id][:4]
    user = _get_current_user()
    return render_template("design-creative/template.html", template=tmpl,
                           related=related, user=user)


@blueprint.route("/editor/<int:project_id>")
def editor(project_id):
    if "user_id" not in session:
        return redirect(url_for("design-creative.login_page"))
    projects = _load_projects()
    project = next((p for p in projects if p["id"] == project_id), None)
    if project is None:
        abort(404)
    if project["owner_id"] != session["user_id"]:
        abort(403)
    assets = _load_assets()
    user = _get_current_user()
    return render_template("design-creative/editor.html", project=project,
                           assets=assets, user=user)


@blueprint.route("/projects")
def projects_page():
    if "user_id" not in session:
        return redirect(url_for("design-creative.login_page"))
    user = _get_current_user()
    if not user:
        return redirect(url_for("design-creative.login_page"))
    projects = _load_projects()
    user_projects = [p for p in projects if p["owner_id"] == user["id"]]

    status_filter = request.args.get("status", "").strip()
    if status_filter:
        user_projects = [p for p in user_projects if p["status"] == status_filter]

    sort = request.args.get("sort", "modified").strip()
    if sort == "modified":
        user_projects.sort(key=lambda p: p["modified_date"], reverse=True)
    elif sort == "created":
        user_projects.sort(key=lambda p: p["created_date"], reverse=True)
    elif sort == "name":
        user_projects.sort(key=lambda p: p["title"].lower())

    return render_template("design-creative/projects.html", projects=user_projects,
                           user=user, status=status_filter, sort=sort)


@blueprint.route("/project/<int:project_id>")
def project_detail(project_id):
    projects = _load_projects()
    project = next((p for p in projects if p["id"] == project_id), None)
    if project is None:
        abort(404)
    templates = _load_templates()
    tmpl = next((t for t in templates if t["id"] == project.get("template_id")), None)
    user = _get_current_user()
    return render_template("design-creative/project.html", project=project,
                           template=tmpl, user=user)


def _xml_escape(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _build_design_svg(project):
    """Render a project's elements into a standalone, downloadable SVG string.

    Deterministic: text / shape (rect + circle) / image / line elements are laid
    out at their stored design-space coordinates."""
    dims = str(project.get("dimensions", "1080x1080")).lower().split("x")
    try:
        w = int(dims[0]); h = int(dims[1])
    except (ValueError, IndexError):
        w, h = 1080, 1080

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}">',
        f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
    ]
    for el in project.get("elements", []) or []:
        etype = el.get("type")
        p = el.get("properties", {}) or {}
        x = float(p.get("x", 0) or 0); y = float(p.get("y", 0) or 0)
        ew = float(p.get("width", 120) or 120); eh = float(p.get("height", 40) or 40)
        if etype == "text":
            size = float(p.get("size", p.get("fontSize", 24)) or 24)
            color = p.get("color", p.get("fill", "#1a1a2e"))
            font = p.get("font", "Inter")
            parts.append(
                f'<text x="{x}" y="{y + size}" font-size="{size}" '
                f'font-family="{_xml_escape(font)}, sans-serif" '
                f'fill="{_xml_escape(color)}">{_xml_escape(p.get("text", ""))}</text>'
            )
        elif etype == "shape":
            fill = p.get("fill", p.get("color", "#ec4899"))
            if p.get("shape") == "circle":
                r = (p.get("radius") or min(ew, eh) / 2)
                parts.append(
                    f'<circle cx="{x + ew / 2}" cy="{y + eh / 2}" r="{r}" '
                    f'fill="{_xml_escape(fill)}"/>'
                )
            else:
                parts.append(
                    f'<rect x="{x}" y="{y}" width="{ew}" height="{eh}" '
                    f'fill="{_xml_escape(fill)}"/>'
                )
        elif etype == "image":
            src = p.get("src", "")
            if isinstance(src, str) and src.startswith("data:"):
                parts.append(
                    f'<image x="{x}" y="{y}" width="{ew}" height="{eh}" '
                    f'href="{_xml_escape(src)}" preserveAspectRatio="xMidYMid meet"/>'
                )
            else:
                parts.append(
                    f'<rect x="{x}" y="{y}" width="{ew}" height="{eh}" '
                    f'fill="#e2e8f0" stroke="#94a3b8" stroke-dasharray="6 4"/>'
                    f'<text x="{x + ew / 2}" y="{y + eh / 2}" font-size="14" '
                    f'font-family="sans-serif" fill="#64748b" text-anchor="middle">'
                    f'{_xml_escape(src or "image")}</text>'
                )
        elif etype == "line":
            x2 = float(p.get("x2", x + 160) or 0); y2 = float(p.get("y2", y) or 0)
            stroke = p.get("stroke", p.get("color", "#a1a1aa"))
            sw = float(p.get("strokeWidth", 3) or 3)
            parts.append(
                f'<line x1="{x}" y1="{y}" x2="{x2}" y2="{y2}" '
                f'stroke="{_xml_escape(stroke)}" stroke-width="{sw}" '
                f'stroke-linecap="round"/>'
            )
    parts.append("</svg>")
    return "\n".join(parts)


@blueprint.route("/project/<int:project_id>/export")
def export_project(project_id):
    """Export a project as a downloadable SVG rendered from its elements."""
    project = db.get_item(SITE, "projects", project_id)
    if project is None:
        abort(404)
    svg = _build_design_svg(project)
    safe_title = "".join(c if c.isalnum() or c in (" ", "-", "_") else "_"
                         for c in project.get("title", "design")).strip() or "design"
    filename = safe_title.replace(" ", "_") + ".svg"
    return Response(
        svg,
        mimetype="image/svg+xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@blueprint.route("/assets")
def assets_page():
    assets = _load_assets()
    q = request.args.get("q", "").strip()
    asset_type = request.args.get("type", "").strip()

    results = list(assets)
    if q:
        results = _search_assets(results, q)
    if asset_type:
        results = [a for a in results if a["type"] == asset_type]

    user = _get_current_user()
    asset_types = ["icon", "photo", "illustration", "shape", "font", "texture", "video"]
    return render_template("design-creative/assets.html", assets=results,
                           q=q, asset_type=asset_type, asset_types=asset_types, user=user)


@blueprint.route("/asset/<int:asset_id>/use", methods=["POST"])
def use_asset(asset_id):
    """Place a library asset into a design and open the editor.

    Fixes the dead-end /assets gallery: from the library you can now put an asset
    straight onto a design. Adds it to your most recent project (creating a blank
    'Untitled design' if you have none), then redirects into the editor with the
    asset placed on the canvas.
    """
    if "user_id" not in session:
        return redirect(url_for("design-creative.login_page"))
    asset = _get_asset(asset_id)
    if asset is None:
        abort(404)
    uid = session["user_id"]
    recent = db.query(SITE, "projects", where={"owner_id": uid},
                      sort="-modified_date", limit=1)
    if recent:
        project = recent[0]
    else:
        now = datetime.now().strftime("%Y-%m-%d")
        project = {"id": db.next_id(SITE, "projects"), "title": "Untitled design",
                   "owner_id": uid, "template_id": None, "dimensions": "1080x1080",
                   "created_date": now, "modified_date": now,
                   "status": "draft", "elements": []}
    dims = str(project.get("dimensions", "1080x1080")).lower().split("x")
    try:
        dw = int(dims[0]); dh = int(dims[1])
    except (ValueError, IndexError):
        dw = dh = 1080
    ew = max(1, round(dw * 0.3)); eh = max(1, round(dh * 0.3))
    project.setdefault("elements", []).append({
        "type": "image",
        "properties": {
            "src": asset.get("src", ""), "name": asset.get("name", ""),
            "asset_id": asset_id, "asset_type": asset.get("type", ""),
            "x": max(0, round((dw - ew) / 2)), "y": max(0, round((dh - eh) / 2)),
            "width": ew, "height": eh,
        },
    })
    project["modified_date"] = datetime.now().strftime("%Y-%m-%d")
    db.save_item(SITE, "projects", project["id"], project)
    return redirect(url_for("design-creative.editor", project_id=project["id"]))


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("design-creative/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return render_template("design-creative/login.html",
                               error="Invalid username or password")
    session["user_id"] = user["id"]
    emit("signup", user_id=user["id"], site_name="design-creative", username=request.form.get("username", ""), password=request.form.get("password", ""), email="")
    return redirect(url_for("design-creative.projects_page"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("design-creative.index"))


# ---------------------------------------------------------------------------
# Form-based mutation routes
# ---------------------------------------------------------------------------

@blueprint.route("/project/create", methods=["POST"])
def form_create_project():
    if "user_id" not in session:
        return redirect(url_for("design-creative.login_page"))
    template_id = request.form.get("template_id", type=int)
    title = request.form.get("title", "").strip()
    templates = _load_templates()
    projects = _load_projects()
    users = _load_users()

    tmpl = next((t for t in templates if t["id"] == template_id), None) if template_id else None
    if not title:
        title = f"Untitled Design" if not tmpl else f"Copy of {tmpl['title']}"

    new_id = max((p["id"] for p in projects), default=0) + 1
    now = datetime.now().strftime("%Y-%m-%d")

    new_project = {
        "id": new_id,
        "title": title,
        "owner_id": session["user_id"],
        "template_id": template_id,
        "dimensions": tmpl["dimensions"] if tmpl else "1080x1080",
        "created_date": now,
        "modified_date": now,
        "status": "draft",
        "elements": []
    }

    projects.append(new_project)
    _save_projects(projects)

    # Update user's projects list
    user = next((u for u in users if u["id"] == session["user_id"]), None)
    if user:
        user.setdefault("projects", []).append(new_id)
        _save_users(users)

    _add_email(session["user_id"], "noreply@design-creative.lakeport.local",
               "Design shared",
               f'Your design "{title}" has been created and is ready to edit.')
    return redirect(url_for("design-creative.editor", project_id=new_id))


@blueprint.route("/project/<int:project_id>/update", methods=["POST"])
def form_update_project(project_id):
    if "user_id" not in session:
        return redirect(url_for("design-creative.login_page"))
    projects = _load_projects()
    project = next((p for p in projects if p["id"] == project_id), None)
    if not project or project["owner_id"] != session["user_id"]:
        abort(403)

    title = request.form.get("title", "").strip()
    status = request.form.get("status", "").strip()
    if title:
        project["title"] = title
    if status in ("draft", "completed"):
        project["status"] = status
    project["modified_date"] = datetime.now().strftime("%Y-%m-%d")
    _save_projects(projects)
    if status == "completed":
        emit("file_created", user_id=session["user_id"], filename=project["title"], file_type="document", source_site="design-creative", source_id=str(project_id))
    return redirect(url_for("design-creative.project_detail", project_id=project_id))


@blueprint.route("/project/<int:project_id>/duplicate", methods=["POST"])
def form_duplicate_project(project_id):
    if "user_id" not in session:
        return redirect(url_for("design-creative.login_page"))
    projects = _load_projects()
    project = next((p for p in projects if p["id"] == project_id), None)
    if not project:
        abort(404)

    new_id = max((p["id"] for p in projects), default=0) + 1
    now = datetime.now().strftime("%Y-%m-%d")
    new_project = copy.deepcopy(project)
    new_project["id"] = new_id
    new_project["title"] = f"Copy of {project['title']}"
    new_project["owner_id"] = session["user_id"]
    new_project["created_date"] = now
    new_project["modified_date"] = now
    new_project["status"] = "draft"

    projects.append(new_project)
    _save_projects(projects)

    users = _load_users()
    user = next((u for u in users if u["id"] == session["user_id"]), None)
    if user:
        user.setdefault("projects", []).append(new_id)
        _save_users(users)

    return redirect(url_for("design-creative.editor", project_id=new_id))


@blueprint.route("/project/<int:project_id>/invite", methods=["POST"])
def form_invite(project_id):
    """Invite a collaborator to a project via email. Persists the collaborator
    onto the project record (session overlay) and notifies them by email."""
    if "user_id" not in session:
        return redirect(url_for("design-creative.login_page"))
    email = request.form.get("email", "").strip()
    project = db.get_item(SITE, "projects", project_id)
    if project is None:
        abort(404)
    if not email:
        return redirect(url_for("design-creative.project_detail", project_id=project_id))

    collaborators = project.get("collaborators") or []
    # Match by invited email; look up a matching site user if one exists.
    users = _load_users()
    matched = next((u for u in users if u.get("email", "").lower() == email.lower()), None)
    existing = next((c for c in collaborators if c.get("email", "").lower() == email.lower()), None)
    if not existing:
        collaborators.append({
            "email": email,
            "user_id": matched["id"] if matched else None,
            "name": matched["name"] if matched else email.split("@")[0],
            "role": "editor",
            "status": "invited",
            "invited_by": session["user_id"],
            "invited_date": datetime.now().strftime("%Y-%m-%d"),
        })
        project["collaborators"] = collaborators
        project["modified_date"] = datetime.now().strftime("%Y-%m-%d")
        db.save_item(SITE, "projects", project_id, project)
        # If the invitee is a known user, drop them an in-app email.
        if matched:
            _add_email(matched["id"], "noreply@design-creative.lakeport.local",
                       "You've been invited to collaborate",
                       f'You were invited to collaborate on "{project["title"]}".')
    return redirect(url_for("design-creative.project_detail", project_id=project_id))


def _asset_type_from_filename(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in ("svg",):
        return "shape"
    if ext in ("jpg", "jpeg", "png", "gif", "webp", "bmp", "heic"):
        return "photo"
    if ext in ("ai", "eps", "pdf"):
        return "illustration"
    return "icon"


def _upload_placeholder_svg(label):
    initial = (label.strip()[:1] or "?").upper()
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        '<rect width="100" height="100" fill="#7c3aed"/>'
        f'<text x="50" y="62" font-size="48" font-family="sans-serif" '
        f'fill="#fff" text-anchor="middle">{initial}</text></svg>'
    )


@blueprint.route("/assets/upload", methods=["POST"])
def form_upload_asset():
    """Upload a file as an asset. Persists the uploaded asset into the site's
    asset collection (session overlay) so it shows up in the Assets library and
    the editor side panel, then emits a file_created event."""
    if "user_id" not in session:
        return redirect(url_for("design-creative.login_page"))
    filename = request.form.get("filename", "").strip()
    name = request.form.get("name", "").strip() or filename
    asset_type = request.form.get("type", "").strip() or _asset_type_from_filename(filename)
    if filename:
        from urllib.parse import quote
        svg = _upload_placeholder_svg(name)
        asset_id = db.next_id(SITE, "assets")
        asset = {
            "id": asset_id,
            "name": name,
            "type": asset_type,
            "category": "Uploads",
            "tags": ["upload", asset_type, name.lower()],
            "svg": svg,
            "src": "data:image/svg+xml," + quote(svg, safe=""),
            "width": 200,
            "height": 200,
            "filename": filename,
            "uploaded_by": session["user_id"],
        }
        db.save_item(SITE, "assets", asset_id, asset)
        emit("file_created", user_id=session["user_id"], filename=filename,
             file_type=asset_type or "asset", source_site="design-creative",
             source_id=name)
    return redirect(url_for("design-creative.assets_page"))


@blueprint.route("/template/<int:template_id>/favorite", methods=["POST"])
def form_favorite_template(template_id):
    if "user_id" not in session:
        return redirect(url_for("design-creative.login_page"))
    users = _load_users()
    user = next((u for u in users if u["id"] == session["user_id"]), None)
    if not user:
        return redirect(url_for("design-creative.login_page"))
    favs = user.setdefault("favorites", [])
    if template_id in favs:
        favs.remove(template_id)
    else:
        favs.append(template_id)
    _save_users(users)
    return redirect(url_for("design-creative.template_detail", template_id=template_id))


# ---------------------------------------------------------------------------
# API routes — Templates
# ---------------------------------------------------------------------------

@blueprint.route("/api/templates")
def api_templates():
    templates = _load_templates()
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    sort = request.args.get("sort", "popular").strip()
    limit = request.args.get("limit", type=int)

    results = list(templates)
    if q:
        results = _search_templates(results, q)
    if category:
        results = [t for t in results if t["category"] == category]

    if sort == "popular":
        results.sort(key=lambda t: -t["use_count"])
    elif sort == "name":
        results.sort(key=lambda t: t["title"].lower())
    elif sort == "newest":
        results.sort(key=lambda t: t["id"], reverse=True)

    if limit:
        results = results[:limit]
    return jsonify(results)


@blueprint.route("/api/templates/<int:template_id>")
def api_template(template_id):
    tmpl = db.get_item(SITE, "templates", template_id)
    if tmpl is None:
        abort(404)
    return jsonify(tmpl)


# ---------------------------------------------------------------------------
# API routes — Projects
# ---------------------------------------------------------------------------

@blueprint.route("/api/projects")
def api_projects():
    projects = _load_projects()
    owner_id = request.args.get("owner_id", type=int)
    status = request.args.get("status", "").strip()
    sort = request.args.get("sort", "modified").strip()

    results = list(projects)
    if owner_id:
        results = [p for p in results if p["owner_id"] == owner_id]
    if status:
        results = [p for p in results if p["status"] == status]

    if sort == "modified":
        results.sort(key=lambda p: p["modified_date"], reverse=True)
    elif sort == "created":
        results.sort(key=lambda p: p["created_date"], reverse=True)
    elif sort == "name":
        results.sort(key=lambda p: p["title"].lower())

    return jsonify(results)


@blueprint.route("/api/projects/<int:project_id>")
def api_project(project_id):
    project = db.get_item(SITE, "projects", project_id)
    if project is None:
        abort(404)
    return jsonify(project)


@blueprint.route("/api/projects", methods=["POST"])
def api_create_project():
    data = request.get_json(silent=True) or {}
    template_id = data.get("template_id")
    title = data.get("title", "").strip()
    owner_id = data.get("owner_id")

    if not owner_id:
        owner_id = session.get("user_id")
    if not owner_id:
        return jsonify({"error": "owner_id required"}), 400

    templates = _load_templates()
    projects = _load_projects()

    tmpl = next((t for t in templates if t["id"] == template_id), None) if template_id else None
    if not title:
        title = "Untitled Design" if not tmpl else f"Copy of {tmpl['title']}"

    new_id = max((p["id"] for p in projects), default=0) + 1
    now = datetime.now().strftime("%Y-%m-%d")

    new_project = {
        "id": new_id,
        "title": title,
        "owner_id": owner_id,
        "template_id": template_id,
        "dimensions": tmpl["dimensions"] if tmpl else data.get("dimensions", "1080x1080"),
        "created_date": now,
        "modified_date": now,
        "status": "draft",
        "elements": []
    }

    projects.append(new_project)
    _save_projects(projects)

    users = _load_users()
    user = next((u for u in users if u["id"] == owner_id), None)
    if user:
        user.setdefault("projects", []).append(new_id)
        _save_users(users)

    return jsonify(new_project), 201


@blueprint.route("/api/projects/<int:project_id>", methods=["PUT"])
def api_update_project(project_id):
    data = request.get_json(silent=True) or {}
    projects = _load_projects()
    project = next((p for p in projects if p["id"] == project_id), None)
    if project is None:
        abort(404)

    if "title" in data:
        project["title"] = data["title"]
    if "status" in data and data["status"] in ("draft", "completed"):
        project["status"] = data["status"]
    if "elements" in data:
        project["elements"] = data["elements"]
    if "dimensions" in data:
        project["dimensions"] = data["dimensions"]

    project["modified_date"] = datetime.now().strftime("%Y-%m-%d")
    _save_projects(projects)
    return jsonify(project)


@blueprint.route("/api/projects/<int:project_id>/duplicate", methods=["POST"])
def api_duplicate_project(project_id):
    projects = _load_projects()
    project = next((p for p in projects if p["id"] == project_id), None)
    if project is None:
        abort(404)

    owner_id = session.get("user_id", project["owner_id"])
    new_id = max((p["id"] for p in projects), default=0) + 1
    now = datetime.now().strftime("%Y-%m-%d")

    new_project = copy.deepcopy(project)
    new_project["id"] = new_id
    new_project["title"] = f"Copy of {project['title']}"
    new_project["owner_id"] = owner_id
    new_project["created_date"] = now
    new_project["modified_date"] = now
    new_project["status"] = "draft"

    projects.append(new_project)
    _save_projects(projects)

    users = _load_users()
    user = next((u for u in users if u["id"] == owner_id), None)
    if user:
        user.setdefault("projects", []).append(new_id)
        _save_users(users)

    return jsonify(new_project), 201


@blueprint.route("/api/projects/<int:project_id>/elements", methods=["POST"])
def api_add_element(project_id):
    """Add an element to a project.

    Accepts either an explicit {type, properties} element, or an {asset_id}
    which is resolved from the asset library and placed onto the canvas as an
    image element (this is how the editor places a stock/uploaded asset)."""
    data = request.get_json(silent=True) or {}
    project = db.get_item(SITE, "projects", project_id)
    if project is None:
        abort(404)

    asset_id = data.get("asset_id")
    if asset_id is not None:
        asset = _get_asset(asset_id)
        if asset is None:
            return jsonify({"error": "asset not found"}), 404
        dims = str(project.get("dimensions", "1080x1080")).lower().split("x")
        try:
            dw = int(dims[0]); dh = int(dims[1])
        except (ValueError, IndexError):
            dw = dh = 1080
        ew = max(1, round(dw * 0.3)); eh = max(1, round(dh * 0.3))
        element = {
            "type": "image",
            "properties": {
                "src": asset.get("src", ""),
                "name": asset.get("name", ""),
                "asset_id": asset_id,
                "asset_type": asset.get("type", ""),
                "x": max(0, round((dw - ew) / 2)),
                "y": max(0, round((dh - eh) / 2)),
                "width": ew,
                "height": eh,
            },
        }
    else:
        element = {
            "type": data.get("type", "text"),
            "properties": data.get("properties", {}),
        }

    project.setdefault("elements", []).append(element)
    project["modified_date"] = datetime.now().strftime("%Y-%m-%d")
    db.save_item(SITE, "projects", project_id, project)
    return jsonify({"element": element, "total_elements": len(project["elements"])}), 201


@blueprint.route("/api/projects/<int:project_id>/elements/<int:element_index>", methods=["DELETE"])
def api_remove_element(project_id, element_index):
    """Remove an element from a project by index."""
    projects = _load_projects()
    project = next((p for p in projects if p["id"] == project_id), None)
    if project is None:
        abort(404)
    if element_index < 0 or element_index >= len(project["elements"]):
        return jsonify({"error": "Invalid element index"}), 400

    removed = project["elements"].pop(element_index)
    project["modified_date"] = datetime.now().strftime("%Y-%m-%d")
    _save_projects(projects)
    return jsonify({"removed": removed, "total_elements": len(project["elements"])})


# ---------------------------------------------------------------------------
# API routes — Assets
# ---------------------------------------------------------------------------

@blueprint.route("/api/assets")
def api_assets():
    assets = _load_assets()
    q = request.args.get("q", "").strip()
    asset_type = request.args.get("type", "").strip()

    results = list(assets)
    if q:
        results = _search_assets(results, q)
    if asset_type:
        results = [a for a in results if a["type"] == asset_type]

    return jsonify(results)


@blueprint.route("/api/assets/<int:asset_id>")
def api_asset(asset_id):
    assets = _load_assets()
    asset = next((a for a in assets if a["id"] == asset_id), None)
    if asset is None:
        abort(404)
    return jsonify(asset)


# ---------------------------------------------------------------------------
# API routes — Users
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


@blueprint.route("/api/users/<int:user_id>")
def api_user(user_id):
    user = _get_user(user_id)
    if not user:
        abort(404)
    return jsonify({k: v for k, v in user.items() if k != "password"})


@blueprint.route("/api/users/<int:user_id>/favorites", methods=["POST"])
def api_toggle_favorite(user_id):
    data = request.get_json(silent=True) or {}
    template_id = data.get("template_id")
    if template_id is None:
        return jsonify({"error": "template_id required"}), 400
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    favs = user.setdefault("favorites", [])
    if template_id in favs:
        favs.remove(template_id)
        action = "unfavorited"
    else:
        favs.append(template_id)
        action = "favorited"
    _save_users(users)
    return jsonify({"action": action, "template_id": template_id, "total_favorites": len(favs)})


# ---------------------------------------------------------------------------
# API routes — Stats / Categories
# ---------------------------------------------------------------------------

@blueprint.route("/api/categories")
def api_categories():
    templates = _load_templates()
    from collections import Counter
    counts = Counter(t["category"] for t in templates)
    return jsonify([{"name": c, "count": n} for c, n in sorted(counts.items())])


@blueprint.route("/api/stats")
def api_stats():
    templates = _load_templates()
    projects = _load_projects()
    from collections import Counter
    cat_counts = Counter(t["category"] for t in templates)
    return jsonify({
        "total_templates": len(templates),
        "total_projects": len(projects),
        "categories": dict(cat_counts),
        "most_popular": max(templates, key=lambda t: t["use_count"])["title"] if templates else None,
    })
