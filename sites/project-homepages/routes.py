"""FlowNet Project Homepage — research project landing page (academic style).

Serves a project homepage for the FlowNet paper (ICML 2025) with team
profiles, downloadable resources, project updates, and citation info.
Data files live under data_sources/project-homepages/.
"""
import csv
import io
import pathlib
from datetime import datetime

from flask import (
    Blueprint, Response, abort, jsonify, redirect, render_template, request,
    session, url_for,
)
from app import db

SITE = "project-homepages"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "project-homepages",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _load_project():
    rows = db.query(SITE, "project")
    return rows[0] if rows else {}


def _load_resources():
    return db.query(SITE, "resources")


def _load_users():
    return db.query(SITE, "users")


def _get_updates():
    """Return project updates. Stored in-memory (session) since there is no
    updates.json in the data source — updates are a mutable feature."""
    return session.get("project_updates", [
        {
            "id": 1,
            "title": "Paper accepted at ICML 2025",
            "content": "We are excited to announce that FlowNet has been accepted for oral presentation at ICML 2025!",
            "date": "2025-05-18",
            "author": "Alex Rivera",
        },
        {
            "id": 2,
            "title": "Code and data released",
            "content": "The official FlowNet source code and benchmark dataset are now publicly available. See the Resources page for download links.",
            "date": "2025-05-20",
            "author": "Aisha Patel",
        },
        {
            "id": 3,
            "title": "ICML 2025 presentation slides posted",
            "content": "Slides from Alex's oral presentation at ICML 2025 are now available on the Resources page.",
            "date": "2025-07-22",
            "author": "Alex Rivera",
        },
        {
            "id": 4,
            "title": "Blog post: How We Used RL to Speed Up MeridianFlow",
            "content": "Our engineering blog post providing a non-technical overview of the FlowNet project is now live. Read about the lessons learned from deploying RL in production.",
            "date": "2025-08-15",
            "author": "Aisha Patel",
        },
    ])


def _save_updates(updates):
    session["project_updates"] = updates


def _current_user():
    uid = session.get("user_id")
    if uid is None:
        return None
    return db.get_item(SITE, "users", uid)


# ---------------------------------------------------------------------------
# Content search helper — used by navigate_by_query and search_by_query
# ---------------------------------------------------------------------------

def _searchable_items(project, resources, updates, team):
    """Build a flat list of searchable content items from all data sources."""
    items = []
    # Sections from project
    section_keys = ["abstract", "motivation", "method", "results", "citation",
                    "code_link", "demo_link"]
    for key in section_keys:
        sec = project.get("sections", {}).get(key)
        if not sec:
            continue
        text_parts = []
        text_parts.append(sec.get("title", ""))
        text_parts.append(sec.get("content", ""))
        text_parts.append(sec.get("content_summary", ""))
        text_parts.append(sec.get("description", ""))
        text_parts.append(sec.get("bibtex", ""))
        text_parts.append(sec.get("apa", ""))
        items.append({
            "type": "section",
            "key": key,
            "title": sec.get("title", key),
            "text": " ".join(t for t in text_parts if t),
            "url": f"/section/{key}",
        })
    # Resources
    for r in resources:
        items.append({
            "type": "resource",
            "key": f"resource_{r['id']}",
            "title": r["title"],
            "text": f"{r['title']} {r.get('description', '')} {r.get('type', '')}",
            "url": f"/resources#{r['id']}",
        })
    # Updates
    for u in updates:
        items.append({
            "type": "update",
            "key": f"update_{u['id']}",
            "title": u["title"],
            "text": f"{u['title']} {u.get('content', '')} {u.get('author', '')}",
            "url": f"/updates#{u['id']}",
        })
    # Team members
    for m in team:
        items.append({
            "type": "team_member",
            "key": f"team_{m['id']}",
            "title": m["full_name"],
            "text": f"{m['full_name']} {m.get('role', '')} {m.get('department', '')} {m.get('affiliation', '')} {m.get('email', '')}",
            "url": f"/team#{m['id']}",
        })
    # Keywords
    for kw in project.get("keywords", []):
        items.append({
            "type": "keyword",
            "key": f"keyword_{kw}",
            "title": kw,
            "text": kw,
            "url": "/paper",
        })
    return items


def _search(query, items):
    """Simple case-insensitive keyword search, returning matching items."""
    q = query.lower().strip()
    if not q:
        return items
    results = []
    for item in items:
        if q in item["text"].lower():
            results.append(item)
    return results


# ---------------------------------------------------------------------------
# Semantic search helper (keyword-overlap scoring for deterministic results)
# ---------------------------------------------------------------------------

def _semantic_score(query, text):
    """Score text against query using keyword overlap (Jaccard-like)."""
    q_words = set(query.lower().split())
    t_words = set(text.lower().split())
    if not q_words:
        return 0.0
    overlap = q_words & t_words
    return len(overlap) / len(q_words)


def _semantic_search(query, items, threshold=0.3):
    """Return items whose semantic score exceeds threshold, sorted desc."""
    scored = []
    for item in items:
        score = _semantic_score(query, item["text"])
        if score >= threshold:
            scored.append((score, item))
    scored.sort(key=lambda x: -x[0])
    return [{"score": round(s, 3), **it} for s, it in scored]


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    project = _load_project()
    team = _load_users()
    updates = _get_updates()
    # Build section list for dropdown navigation
    section_list = _get_section_list(project)

    # navigate_by_query: if ?section=<key> is provided, redirect to that section page
    section_param = request.args.get("section")
    if section_param:
        valid_keys = {s["key"] for s in section_list}
        # Also support page-level targets
        page_map = {"team": "team_page", "resources": "resources_page",
                     "updates": "updates_page", "stats": "stats_page",
                     "paper": "paper_page", "export": "export_page",
                     "search": "search_page"}
        if section_param in page_map:
            return redirect(url_for(f"project-homepages.{page_map[section_param]}"))
        if section_param in valid_keys:
            return redirect(url_for("project-homepages.section_page",
                                    section_key=section_param))

    return render_template(
        "project-homepages/index.html",
        project=project,
        team=team,
        updates=updates[:3],
        user=_current_user(),
        sections_list=section_list,
    )


def _get_section_list(project):
    """Return ordered list of navigable sections."""
    section_keys = ["abstract", "motivation", "method", "results", "citation",
                    "code_link", "demo_link"]
    result = []
    for key in section_keys:
        sec = project.get("sections", {}).get(key)
        if sec:
            result.append({"key": key, "title": sec.get("title", key)})
    return result


@blueprint.route("/paper")
def paper_page():
    project = _load_project()
    section_list = _get_section_list(project)
    return render_template(
        "project-homepages/paper.html",
        project=project,
        user=_current_user(),
        sections_list=section_list,
    )


@blueprint.route("/team")
def team_page():
    project = _load_project()
    team = _load_users()
    authors = project.get("authors", [])
    # Merge author metadata (orcid, corresponding) into user records
    enriched = []
    for u in team:
        entry = dict(u)
        author_meta = next(
            (a for a in authors if a["name"] == u["full_name"]), {}
        )
        entry["orcid"] = author_meta.get("orcid", "")
        entry["corresponding"] = author_meta.get("corresponding", False)
        enriched.append(entry)
    section_list = _get_section_list(project)
    return render_template(
        "project-homepages/team.html",
        project=project,
        team=enriched,
        user=_current_user(),
        sections_list=section_list,
    )


@blueprint.route("/resources")
def resources_page():
    project = _load_project()
    resources = _load_resources()
    # Collect unique resource types for the filter dropdown
    resource_types = sorted(set(r["type"] for r in resources))
    section_list = _get_section_list(project)
    return render_template(
        "project-homepages/resources.html",
        project=project,
        resources=resources,
        resource_types=resource_types,
        user=_current_user(),
        sections_list=section_list,
    )


def _res_slug(title):
    import re
    s = re.sub(r"[^a-z0-9]+", "-", (title or "resource").lower()).strip("-")
    return s or "resource"


def _minimal_pdf(title, lines):
    """Build a tiny but valid single-page PDF containing the given text."""
    def esc(s):
        return str(s).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    content = "BT /F1 18 Tf 72 740 Td 24 TL (" + esc(title) + ") Tj T* /F1 11 Tf "
    for ln in lines:
        content += "(" + esc(ln) + ") Tj T* "
    content += "ET"
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        "<< /Length " + str(len(content)) + " >>\nstream\n" + content + "\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf = "%PDF-1.4\n"
    offsets = []
    for i, o in enumerate(objs, start=1):
        offsets.append(len(pdf))
        pdf += "%d 0 obj\n%s\nendobj\n" % (i, o)
    xref_pos = len(pdf)
    n = len(objs) + 1
    pdf += "xref\n0 %d\n0000000000 65535 f \n" % n
    for off in offsets:
        pdf += "%010d 00000 n \n" % off
    pdf += "trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (n, xref_pos)
    return pdf.encode("latin-1", "replace")


def _dataset_sample_rows(n=12):
    """Deterministic sample rows for a dataset preview / CSV download."""
    rows = []
    for i in range(1, n + 1):
        rows.append({
            "id": i,
            "input_tokens": 128 + (i * 37) % 512,
            "target": round(0.40 + (i * 0.031) % 0.55, 3),
            "split": "test" if i % 5 == 0 else "train",
            "score": round(78.0 + (i * 0.9) % 20, 1),
        })
    return rows


def _generate_resource_file(resource, project):
    """Return (bytes, mimetype, extension) for a placeholder download."""
    t = resource.get("type")
    title = resource.get("title", "Resource")
    if t == "dataset":
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=["id", "input_tokens", "target", "split", "score"])
        w.writeheader()
        for r in _dataset_sample_rows(50):
            w.writerow(r)
        return buf.getvalue().encode("utf-8"), "text/csv", ".csv"
    lines = [
        "Project: " + (project.get("title") or project.get("short_title") or ""),
        "Resource type: " + (t or "").replace("_", " ").title(),
        "Format: " + (resource.get("format") or "PDF"),
        "License: " + (resource.get("license") or "See project page"),
        "",
    ]
    desc = resource.get("description") or ""
    # wrap description to ~90 chars per line
    while desc:
        lines.append(desc[:90])
        desc = desc[90:]
    lines += [
        "",
        "This is a generated placeholder for the " + (t or "resource").replace("_", " ") + ".",
        "Generated by the project homepage for preview/demo purposes.",
    ]
    return _minimal_pdf(title, lines), "application/pdf", ".pdf"


@blueprint.route("/resource/<int:resource_id>")
def resource_detail(resource_id):
    project = _load_project()
    resources = _load_resources()
    resource = next((r for r in resources if r.get("id") == resource_id), None)
    if not resource:
        abort(404)
    related = [r for r in resources
               if r.get("type") == resource["type"] and r.get("id") != resource_id][:4]
    # Type-specific preview data
    dataset_rows = _dataset_sample_rows(10) if resource["type"] == "dataset" else None
    dl_ext = ".csv" if resource["type"] == "dataset" else ".pdf"
    download_name = _res_slug(resource.get("title")) + dl_ext
    return render_template(
        "project-homepages/resource_detail.html",
        project=project,
        resource=resource,
        related=related,
        dataset_rows=dataset_rows,
        download_name=download_name,
        user=_current_user(),
        sections_list=_get_section_list(project),
    )


@blueprint.route("/resource/<int:resource_id>/download")
def resource_download(resource_id):
    resources = _load_resources()
    resource = next((r for r in resources if r.get("id") == resource_id), None)
    if not resource:
        abort(404)
    content, mime, ext = _generate_resource_file(resource, _load_project())
    fname = _res_slug(resource.get("title")) + ext
    return Response(content, mimetype=mime,
                    headers={"Content-Disposition": 'attachment; filename="%s"' % fname})


@blueprint.route("/updates")
def updates_page():
    project = _load_project()
    updates = _get_updates()
    section_list = _get_section_list(project)
    return render_template(
        "project-homepages/updates.html",
        project=project,
        updates=updates,
        user=_current_user(),
        sections_list=section_list,
    )


@blueprint.route("/section/<section_key>")
def section_page(section_key):
    """navigate_by_semantic / navigate_by_route: navigate directly to a
    paper section by key (e.g. /section/abstract, /section/method)."""
    project = _load_project()
    sec = project.get("sections", {}).get(section_key)
    if sec is None:
        abort(404)
    section_list = _get_section_list(project)
    return render_template(
        "project-homepages/section.html",
        project=project,
        section_key=section_key,
        section=sec,
        user=_current_user(),
        sections_list=section_list,
    )


@blueprint.route("/search")
def search_page():
    """search_by_query / navigate_by_query: HTML search results page."""
    project = _load_project()
    resources = _load_resources()
    updates = _get_updates()
    team = _load_users()
    q = request.args.get("q", "").strip()
    items = _searchable_items(project, resources, updates, team)
    results = _search(q, items) if q else []
    section_list = _get_section_list(project)
    return render_template(
        "project-homepages/search.html",
        project=project,
        query=q,
        results=results,
        user=_current_user(),
        sections_list=section_list,
    )


@blueprint.route("/stats")
def stats_page():
    """extract_from_table: HTML page with project stats in a table."""
    project = _load_project()
    resources = _load_resources()
    team = _load_users()
    updates = _get_updates()
    metrics = project.get("sections", {}).get("results", {}).get("key_metrics", {})
    code = project.get("sections", {}).get("code_link", {})

    # Build resource type counts for table
    type_counts = {}
    for r in resources:
        t = r.get("type", "other")
        type_counts[t] = type_counts.get(t, 0) + 1

    section_list = _get_section_list(project)
    return render_template(
        "project-homepages/stats.html",
        project=project,
        team=team,
        updates=updates,
        resources=resources,
        metrics=metrics,
        code=code,
        type_counts=type_counts,
        user=_current_user(),
        sections_list=section_list,
    )


@blueprint.route("/export")
def export_page():
    """export_by_dropdown: HTML page with export format dropdown."""
    project = _load_project()
    section_list = _get_section_list(project)
    return render_template(
        "project-homepages/export.html",
        project=project,
        user=_current_user(),
        sections_list=section_list,
    )


@blueprint.route("/login", methods=["GET"])
def login_page():
    project = _load_project()
    section_list = _get_section_list(project)
    return render_template(
        "project-homepages/login.html",
        project=project,
        user=_current_user(),
        sections_list=section_list,
    )


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if user is None:
        project = _load_project()
        return render_template(
            "project-homepages/login.html",
            project=project,
            error="Invalid username.",
            user=None,
        )
    stored_pw = user.get("password", "password")
    if password and password != stored_pw:
        return render_template("project-homepages/login.html", error="Invalid password")
    session["user_id"] = user["id"]
    return render_template(
        "project-homepages/login.html",
        project=_load_project(),
        user=user,
        success=f"Signed in as {user['full_name']}.",
    )


@blueprint.route("/logout", methods=["POST"])
def logout():
    session.pop("user_id", None)
    project = _load_project()
    return render_template(
        "project-homepages/login.html",
        project=project,
        user=None,
        success="Signed out.",
    )

# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/project", methods=["GET"])
def api_project_get():
    return jsonify(_load_project())


@blueprint.route("/api/project", methods=["PUT"])
def api_project_update():
    project = _load_project()
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400
    # Allow updating select top-level fields
    allowed = {"title", "short_title", "status", "last_updated"}
    for key in allowed:
        if key in data:
            project[key] = data[key]
    # Allow updating section content
    if "sections" in data and isinstance(data["sections"], dict):
        for sec_key, sec_val in data["sections"].items():
            if sec_key in project.get("sections", {}):
                if isinstance(sec_val, dict):
                    project["sections"][sec_key].update(sec_val)
    db.save_collection(SITE, "project", [project])
    return jsonify(project)


@blueprint.route("/api/team", methods=["GET"])
def api_team_list():
    return jsonify(_load_users())


@blueprint.route("/api/team/<int:member_id>", methods=["GET"])
def api_team_member(member_id):
    users = _load_users()
    user = next((u for u in users if u["id"] == member_id), None)
    if user is None:
        abort(404)
    # Enrich with author metadata from project
    project = _load_project()
    author_meta = next(
        (a for a in project.get("authors", []) if a["name"] == user["full_name"]),
        {},
    )
    result = dict(user)
    result["orcid"] = author_meta.get("orcid", "")
    result["corresponding"] = author_meta.get("corresponding", False)
    return jsonify(result)


@blueprint.route("/api/resources", methods=["GET"])
def api_resources_list():
    resources = _load_resources()
    rtype = request.args.get("type")
    if rtype:
        resources = [r for r in resources if r.get("type") == rtype]
    return jsonify(resources)


@blueprint.route("/api/resources", methods=["POST"])
def api_resources_add():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400
    resources = _load_resources()
    new_id = max((r["id"] for r in resources), default=0) + 1
    resource = {
        "id": new_id,
        "type": data.get("type", "other"),
        "title": data.get("title", "Untitled"),
        "url": data.get("url", ""),
        "format": data.get("format", ""),
        "size_mb": data.get("size_mb"),
        "description": data.get("description", ""),
        "date_added": datetime.now().strftime("%Y-%m-%d"),
    }
    if "license" in data:
        resource["license"] = data["license"]
    resources.append(resource)
    db.save_collection(SITE, "resources", resources)
    return jsonify(resource), 201


@blueprint.route("/api/resources/<int:resource_id>", methods=["GET"])
def api_resource_get(resource_id):
    resources = _load_resources()
    resource = next((r for r in resources if r["id"] == resource_id), None)
    if resource is None:
        abort(404)
    return jsonify(resource)


@blueprint.route("/api/resources/<int:resource_id>", methods=["DELETE"])
def api_resource_delete(resource_id):
    resources = _load_resources()
    resource = next((r for r in resources if r["id"] == resource_id), None)
    if resource is None:
        abort(404)
    resources = [r for r in resources if r["id"] != resource_id]
    db.save_collection(SITE, "resources", resources)
    return jsonify({"status": "deleted", "id": resource_id})


@blueprint.route("/api/updates", methods=["GET"])
def api_updates_list():
    return jsonify(_get_updates())


@blueprint.route("/api/updates", methods=["POST"])
def api_updates_add():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400
    updates = _get_updates()
    new_id = max((u["id"] for u in updates), default=0) + 1
    user = _current_user()
    update = {
        "id": new_id,
        "title": data.get("title", "Untitled update"),
        "content": data.get("content", ""),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "author": user["full_name"] if user else data.get("author", "Unknown"),
    }
    updates.insert(0, update)
    _save_updates(updates)
    return jsonify(update), 201


@blueprint.route("/api/citations", methods=["GET"])
def api_citations():
    project = _load_project()
    citation = project.get("sections", {}).get("citation", {})
    fmt = request.args.get("format", "bibtex").lower()
    if fmt == "apa":
        return jsonify({"format": "apa", "citation": citation.get("apa", "")})
    return jsonify({"format": "bibtex", "citation": citation.get("bibtex", "")})


@blueprint.route("/api/stats", methods=["GET"])
def api_stats():
    project = _load_project()
    resources = _load_resources()
    team = _load_users()
    updates = _get_updates()
    metrics = project.get("sections", {}).get("results", {}).get("key_metrics", {})
    code = project.get("sections", {}).get("code_link", {})
    return jsonify({
        "project_id": project.get("id"),
        "title": project.get("title"),
        "venue": project.get("venue"),
        "year": project.get("year"),
        "status": project.get("status"),
        "team_count": len(team),
        "resource_count": len(resources),
        "update_count": len(updates),
        "github_stars": code.get("stars"),
        "key_metrics": metrics,
        "keywords": project.get("keywords", []),
    })


# ---------------------------------------------------------------------------
# API: search (navigate_by_query, search_by_query)
# ---------------------------------------------------------------------------

@blueprint.route("/api/search", methods=["GET"])
def api_search():
    """Keyword search across all project content."""
    project = _load_project()
    resources = _load_resources()
    updates = _get_updates()
    team = _load_users()
    q = request.args.get("q", "").strip()
    items = _searchable_items(project, resources, updates, team)
    results = _search(q, items)
    return jsonify(results)


# ---------------------------------------------------------------------------
# API: semantic search (navigate_by_semantic, extract_by_semantic)
# ---------------------------------------------------------------------------

@blueprint.route("/api/semantic", methods=["GET"])
def api_semantic_search():
    """Semantic (keyword-overlap) search across project content."""
    project = _load_project()
    resources = _load_resources()
    updates = _get_updates()
    team = _load_users()
    q = request.args.get("q", "").strip()
    items = _searchable_items(project, resources, updates, team)
    results = _semantic_search(q, items)
    return jsonify(results)


# ---------------------------------------------------------------------------
# API: sections list (navigate_by_dropdown)
# ---------------------------------------------------------------------------

@blueprint.route("/api/sections", methods=["GET"])
def api_sections():
    """List all navigable paper sections."""
    project = _load_project()
    return jsonify(_get_section_list(project))


@blueprint.route("/api/sections/<section_key>", methods=["GET"])
def api_section_detail(section_key):
    """Get content of a specific section by key (extract_by_route)."""
    project = _load_project()
    sec = project.get("sections", {}).get(section_key)
    if sec is None:
        abort(404)
    return jsonify({"key": section_key, **sec})


# ---------------------------------------------------------------------------
# API: export (export_by_dropdown)
# ---------------------------------------------------------------------------

@blueprint.route("/api/export", methods=["GET"])
def api_export():
    """Export project data in various formats.

    Supported format values:
      - bibtex: returns BibTeX citation string
      - apa: returns APA citation string
      - json: returns full project summary as JSON
      - csv: returns team + resources as CSV
    """
    project = _load_project()
    fmt = request.args.get("format", "json").lower()

    if fmt == "bibtex":
        citation = project.get("sections", {}).get("citation", {})
        bibtex = citation.get("bibtex", "")
        return Response(bibtex, mimetype="text/plain",
                        headers={"Content-Disposition":
                                 "attachment; filename=flownet.bib"})

    elif fmt == "apa":
        citation = project.get("sections", {}).get("citation", {})
        apa = citation.get("apa", "")
        return Response(apa, mimetype="text/plain",
                        headers={"Content-Disposition":
                                 "attachment; filename=flownet_apa.txt"})

    elif fmt == "csv":
        resources = _load_resources()
        team = _load_users()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["category", "id", "name_or_title", "type_or_role",
                         "detail"])
        for m in team:
            writer.writerow(["team", m["id"], m["full_name"], m["role"],
                             m.get("department", "")])
        for r in resources:
            writer.writerow(["resource", r["id"], r["title"], r["type"],
                             r.get("format", "")])
        csv_text = output.getvalue()
        return Response(csv_text, mimetype="text/csv",
                        headers={"Content-Disposition":
                                 "attachment; filename=flownet_export.csv"})

    else:  # json (default)
        resources = _load_resources()
        team = _load_users()
        updates = _get_updates()
        metrics = project.get("sections", {}).get("results", {}).get(
            "key_metrics", {})
        summary = {
            "project_id": project.get("id"),
            "title": project.get("title"),
            "short_title": project.get("short_title"),
            "venue": project.get("venue"),
            "year": project.get("year"),
            "status": project.get("status"),
            "doi": project.get("doi"),
            "arxiv_id": project.get("arxiv_id"),
            "keywords": project.get("keywords", []),
            "authors": project.get("authors", []),
            "key_metrics": metrics,
            "team": team,
            "resources": resources,
            "updates": updates,
        }
        return jsonify(summary)


# ---------------------------------------------------------------------------
# API: resource stats by type (extract_by_dropdown)
# ---------------------------------------------------------------------------

@blueprint.route("/api/resources/stats", methods=["GET"])
def api_resources_stats():
    """Return stats for resources, optionally filtered by type dropdown."""
    resources = _load_resources()
    rtype = request.args.get("type")
    if rtype:
        filtered = [r for r in resources if r.get("type") == rtype]
    else:
        filtered = resources
    total_size = sum(r.get("size_mb") or 0 for r in filtered)
    return jsonify({
        "type_filter": rtype or "all",
        "count": len(filtered),
        "total_size_mb": round(total_size, 1),
        "types": list(set(r["type"] for r in filtered)),
        "resources": filtered,
    })
