"""Alex Rivera's Personal Portfolio — developer portfolio, project gallery, resume, blog links.

Data lives in data_sources/personal-portfolio/ and is read through the data overlay
so each browser session gets isolated mutable state.
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

SITE = "personal-portfolio"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "personal-portfolio",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _load_profile():
    rows = db.query(SITE, "profile")
    return rows[0] if rows else {}

def _save_profile(profile):
    db.save_collection(SITE, "profile", [profile])

def _load_projects():
    return db.query(SITE, "projects")

def _save_projects(projects):
    db.save_collection(SITE, "projects", projects)

def _load_resume():
    rows = db.query(SITE, "resume")
    return rows[0] if rows else {}

def _save_resume(resume):
    db.save_collection(SITE, "resume", [resume])

def _load_blog_links():
    return db.query(SITE, "blog_links")

def _save_blog_links(links):
    db.save_collection(SITE, "blog_links", links)

def _load_users():
    return db.query(SITE, "users")

def _get_current_user():
    if "user_id" in session:
        return db.get_item(SITE, "users", session["user_id"])
    return None

def _get_browsing_user():
    """Return the logged-in user, or fall back to user 1 for browse-only mode."""
    user = _get_current_user()
    if user:
        return user, True
    users = _load_users()
    return next((u for u in users if u["id"] == 1), None), False

def _is_owner():
    """Check if the current session user is the portfolio owner."""
    user = _get_current_user()
    return user is not None and user.get("role") == "owner"

# ---------------------------------------------------------------------------
# Contact messages (stored in-memory per session, persisted to data file)
# ---------------------------------------------------------------------------

def _load_contact_messages():
    return db.query(SITE, "contact_messages")

def _save_contact_messages(messages):
    db.save_collection(SITE, "contact_messages", messages)


def _load_subscriptions():
    return db.query(SITE, "subscriptions")


def _save_subscriptions(subs):
    db.save_collection(SITE, "subscriptions", subs)


# ---------------------------------------------------------------------------
# Fuzzy / semantic search helper
# ---------------------------------------------------------------------------

def _semantic_score(query_tokens, text):
    """Simple word-overlap fuzzy scoring for semantic-style search."""
    text_lower = text.lower()
    text_words = set(text_lower.split())
    score = 0
    for token in query_tokens:
        if token in text_lower:
            score += 2  # substring match
        elif any(token in w for w in text_words):
            score += 1  # partial word match
    return score


def _semantic_search(query):
    """Search across projects, blog posts, resume, and profile for a query."""
    tokens = [t.lower() for t in query.strip().split() if t]
    if not tokens:
        return []

    results = []

    # Search projects
    for p in _load_projects():
        text = " ".join([
            p.get("title", ""), p.get("tagline", ""),
            p.get("description", ""), p.get("type", ""),
            " ".join(p.get("technologies", [])),
        ])
        score = _semantic_score(tokens, text)
        if score > 0:
            results.append({
                "type": "project",
                "id": p["id"],
                "title": p["title"],
                "snippet": p.get("tagline", ""),
                "url": f"/project/{p['id']}",
                "score": score,
            })

    # Search blog links
    for b in _load_blog_links():
        text = " ".join([
            b.get("title", ""), b.get("excerpt", ""),
            b.get("category", ""), " ".join(b.get("tags", [])),
        ])
        score = _semantic_score(tokens, text)
        if score > 0:
            results.append({
                "type": "blog",
                "id": b["id"],
                "blog_post_id": b.get("blog_post_id", b["id"]),
                "title": b["title"],
                "snippet": b.get("excerpt", ""),
                "url": b.get("url", ""),
                "score": score,
            })

    # Search profile
    profile = _load_profile()
    profile_text = " ".join([
        profile.get("name", ""), profile.get("tagline", ""),
        profile.get("bio", ""), profile.get("location", ""),
        " ".join(s["name"] for s in profile.get("skills", [])),
        " ".join(profile.get("interests", [])),
    ])
    score = _semantic_score(tokens, profile_text)
    if score > 0:
        results.append({
            "type": "profile",
            "id": 0,
            "title": profile.get("name", ""),
            "snippet": profile.get("tagline", ""),
            "url": "/",
            "score": score,
        })

    # Search resume
    resume = _load_resume()
    resume_text = " ".join([
        resume.get("summary", ""),
        " ".join(resume.get("skills", {}).get("languages", [])),
        " ".join(resume.get("skills", {}).get("frameworks", [])),
        " ".join(resume.get("skills", {}).get("databases", [])),
        " ".join(resume.get("skills", {}).get("infrastructure", [])),
        " ".join(resume.get("skills", {}).get("tools", [])),
    ])
    for exp in resume.get("experience", []):
        resume_text += " " + exp.get("company", "") + " " + exp.get("title", "")
        resume_text += " " + " ".join(exp.get("highlights", []))
    score = _semantic_score(tokens, resume_text)
    if score > 0:
        results.append({
            "type": "resume",
            "id": 0,
            "title": "Resume",
            "snippet": resume.get("summary", "")[:120],
            "url": "/resume",
            "score": score,
        })

    results.sort(key=lambda r: r["score"], reverse=True)
    return results


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    profile = _load_profile()
    projects = _load_projects()
    featured = [p for p in projects if p.get("featured")]

    sort = request.args.get("sort", "newest").strip()
    if sort == "title":
        featured.sort(key=lambda p: p.get("title", "").lower())
    elif sort == "status":
        featured.sort(key=lambda p: p.get("status", ""))
    else:  # newest
        featured.sort(key=lambda p: p.get("date", p.get("created_at", "")), reverse=True)

    user, logged_in = _get_browsing_user()
    return render_template("personal-portfolio/index.html",
                           profile=profile, featured_projects=featured,
                           sort=sort, user=user, logged_in=logged_in)


@blueprint.route("/projects")
def projects_page():
    profile = _load_profile()
    projects = _load_projects()
    user, logged_in = _get_browsing_user()

    # Filtering
    category = request.args.get("category", "").strip()
    tech = request.args.get("tech", "").strip()
    search = request.args.get("q", "").strip().lower()
    status = request.args.get("status", "").strip()

    if category:
        projects = [p for p in projects if p.get("type", "").lower() == category.lower()]
    if tech:
        projects = [p for p in projects
                    if any(t.lower() == tech.lower() for t in p.get("technologies", []))]
    if status:
        projects = [p for p in projects if p.get("status", "").lower() == status.lower()]
    if search:
        projects = [p for p in projects
                    if search in p.get("title", "").lower()
                    or search in p.get("description", "").lower()
                    or search in p.get("tagline", "").lower()
                    or any(search in t.lower() for t in p.get("technologies", []))]

    # Collect unique categories and technologies for filter UI
    all_projects = _load_projects()
    categories = sorted(set(p.get("type", "") for p in all_projects))
    technologies = sorted(set(t for p in all_projects for t in p.get("technologies", [])))

    return render_template("personal-portfolio/projects.html",
                           profile=profile, projects=projects,
                           categories=categories, technologies=technologies,
                           current_category=category, current_tech=tech,
                           current_search=request.args.get("q", ""),
                           current_status=status,
                           user=user, logged_in=logged_in)


@blueprint.route("/project/<int:project_id>")
def project_detail(project_id):
    profile = _load_profile()
    projects = _load_projects()
    project = next((p for p in projects if p["id"] == project_id), None)
    if not project:
        abort(404)
    user, logged_in = _get_browsing_user()
    return render_template("personal-portfolio/project_detail.html",
                           profile=profile, project=project,
                           user=user, logged_in=logged_in)


@blueprint.route("/resume")
def resume_page():
    profile = _load_profile()
    resume = _load_resume()
    user, logged_in = _get_browsing_user()
    return render_template("personal-portfolio/resume.html",
                           profile=profile, resume=resume,
                           user=user, logged_in=logged_in)


@blueprint.route("/blog")
def blog_page():
    profile = _load_profile()
    blog_links = _load_blog_links()
    user, logged_in = _get_browsing_user()

    # Filtering
    category = request.args.get("category", "").strip()
    if category:
        blog_links = [b for b in blog_links if b.get("category", "").lower() == category.lower()]

    all_links = _load_blog_links()
    categories = sorted(set(b.get("category", "") for b in all_links))

    return render_template("personal-portfolio/blog.html",
                           profile=profile, blog_links=blog_links,
                           categories=categories, current_category=category,
                           user=user, logged_in=logged_in)


@blueprint.route("/search")
def search_page():
    profile = _load_profile()
    user, logged_in = _get_browsing_user()
    query = request.args.get("q", "").strip()
    results = _semantic_search(query) if query else []
    return render_template("personal-portfolio/search.html",
                           profile=profile, query=query, results=results,
                           user=user, logged_in=logged_in)


@blueprint.route("/skills")
def skills_page():
    """Skills presented in an HTML table for extract_from_table macro."""
    profile = _load_profile()
    resume = _load_resume()
    user, logged_in = _get_browsing_user()
    return render_template("personal-portfolio/skills.html",
                           profile=profile, resume=resume,
                           user=user, logged_in=logged_in)


@blueprint.route("/contact")
def contact_page():
    profile = _load_profile()
    user, logged_in = _get_browsing_user()
    return render_template("personal-portfolio/index.html",
                           profile=profile,
                           featured_projects=[p for p in _load_projects() if p.get("featured")],
                           user=user, logged_in=logged_in,
                           show_contact=True)


@blueprint.route("/admin")
def admin_page():
    if not _is_owner():
        return redirect(url_for("personal-portfolio.login_page"))
    profile = _load_profile()
    projects = _load_projects()
    resume = _load_resume()
    blog_links = _load_blog_links()
    messages = _load_contact_messages()
    user, logged_in = _get_browsing_user()
    return render_template("personal-portfolio/index.html",
                           profile=profile, featured_projects=projects,
                           user=user, logged_in=logged_in,
                           admin_mode=True, all_projects=projects,
                           resume=resume, blog_links=blog_links,
                           messages=messages)


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("personal-portfolio/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user:
        return render_template("personal-portfolio/login.html",
                               error="Invalid username or password")
    stored_pw = user.get("password", "password")
    if password and password != stored_pw:
        return render_template("personal-portfolio/login.html", error="Invalid password")
    session["user_id"] = user["id"]
    return redirect(url_for("personal-portfolio.index"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("personal-portfolio.index"))


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

# --- Profile ---

@blueprint.route("/api/profile", methods=["GET"])
def api_get_profile():
    profile = _load_profile()
    return jsonify(profile)


@blueprint.route("/api/profile", methods=["PUT"])
def api_update_profile():
    data = request.get_json(silent=True) or {}
    profile = _load_profile()
    updatable = ["name", "tagline", "bio", "location", "avatar_url",
                 "skills", "interests", "contact"]
    for key in updatable:
        if key in data:
            profile[key] = data[key]
    _save_profile(profile)
    return jsonify(profile)


# --- Projects ---

@blueprint.route("/api/projects", methods=["GET"])
def api_list_projects():
    projects = _load_projects()

    # Filtering
    category = request.args.get("category", "").strip()
    tech = request.args.get("tech", "").strip()
    search = request.args.get("q", "").strip().lower()
    status = request.args.get("status", "").strip()
    featured = request.args.get("featured", "").strip()

    if category:
        projects = [p for p in projects if p.get("type", "").lower() == category.lower()]
    if tech:
        projects = [p for p in projects
                    if any(t.lower() == tech.lower() for t in p.get("technologies", []))]
    if status:
        projects = [p for p in projects if p.get("status", "").lower() == status.lower()]
    if featured:
        projects = [p for p in projects if p.get("featured") == (featured.lower() == "true")]
    if search:
        projects = [p for p in projects
                    if search in p.get("title", "").lower()
                    or search in p.get("description", "").lower()
                    or search in p.get("tagline", "").lower()
                    or any(search in t.lower() for t in p.get("technologies", []))]

    return jsonify(projects)


@blueprint.route("/api/projects", methods=["POST"])
def api_create_project():
    data = request.get_json(silent=True) or {}
    if not data.get("title"):
        return jsonify({"error": "Title is required"}), 400

    projects = _load_projects()
    new_id = max((p["id"] for p in projects), default=0) + 1

    project = {
        "id": new_id,
        "title": data["title"],
        "slug": data.get("slug", data["title"].lower().replace(" ", "-")),
        "tagline": data.get("tagline", ""),
        "description": data.get("description", ""),
        "type": data.get("type", "side_project"),
        "status": data.get("status", "active"),
        "collaborators": data.get("collaborators", []),
        "technologies": data.get("technologies", []),
        "github_url": data.get("github_url"),
        "live_url": data.get("live_url"),
        "started": data.get("started", datetime.now().strftime("%Y-%m-%d")),
        "last_updated": datetime.now().strftime("%Y-%m-%d"),
        "image_url": data.get("image_url"),
        "featured": data.get("featured", False),
    }
    projects.append(project)
    _save_projects(projects)
    return jsonify(project), 201


@blueprint.route("/api/projects/<int:project_id>", methods=["GET"])
def api_get_project(project_id):
    projects = _load_projects()
    project = next((p for p in projects if p["id"] == project_id), None)
    if not project:
        return jsonify({"error": "Project not found"}), 404
    return jsonify(project)


@blueprint.route("/api/projects/<int:project_id>", methods=["PUT"])
def api_update_project(project_id):
    data = request.get_json(silent=True) or {}
    projects = _load_projects()
    project = next((p for p in projects if p["id"] == project_id), None)
    if not project:
        return jsonify({"error": "Project not found"}), 404

    updatable = ["title", "slug", "tagline", "description", "type", "status",
                 "collaborators", "technologies", "github_url", "live_url",
                 "image_url", "featured", "started"]
    for key in updatable:
        if key in data:
            project[key] = data[key]
    project["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    _save_projects(projects)
    return jsonify(project)


@blueprint.route("/api/projects/<int:project_id>", methods=["DELETE"])
def api_delete_project(project_id):
    projects = _load_projects()
    project = next((p for p in projects if p["id"] == project_id), None)
    if not project:
        return jsonify({"error": "Project not found"}), 404
    projects = [p for p in projects if p["id"] != project_id]
    _save_projects(projects)
    return jsonify({"status": "deleted", "id": project_id})


# --- Resume ---

@blueprint.route("/api/resume", methods=["GET"])
def api_get_resume():
    resume = _load_resume()
    return jsonify(resume)


@blueprint.route("/api/resume", methods=["PUT"])
def api_update_resume():
    data = request.get_json(silent=True) or {}
    resume = _load_resume()
    updatable = ["header", "summary", "experience", "education", "skills",
                 "certifications", "projects"]
    for key in updatable:
        if key in data:
            resume[key] = data[key]
    resume["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    _save_resume(resume)
    return jsonify(resume)


# --- Blog links ---

@blueprint.route("/api/blog-links", methods=["GET"])
def api_list_blog_links():
    links = _load_blog_links()

    category = request.args.get("category", "").strip()
    if category:
        links = [l for l in links if l.get("category", "").lower() == category.lower()]

    return jsonify(links)


@blueprint.route("/api/blog-links", methods=["POST"])
def api_create_blog_link():
    data = request.get_json(silent=True) or {}
    if not data.get("title") or not data.get("url"):
        return jsonify({"error": "Title and URL are required"}), 400

    links = _load_blog_links()
    new_id = max((l["id"] for l in links), default=0) + 1

    link = {
        "id": new_id,
        "blog_post_id": data.get("blog_post_id", new_id),
        "title": data["title"],
        "url": data["url"],
        "category": data.get("category", "Uncategorized"),
        "date": data.get("date", datetime.now().strftime("%Y-%m-%d")),
        "excerpt": data.get("excerpt", ""),
        "tags": data.get("tags", []),
        "featured": data.get("featured", False),
    }
    links.append(link)
    _save_blog_links(links)
    return jsonify(link), 201


@blueprint.route("/api/blog-links/<int:link_id>", methods=["DELETE"])
def api_delete_blog_link(link_id):
    links = _load_blog_links()
    link = next((l for l in links if l["id"] == link_id), None)
    if not link:
        return jsonify({"error": "Blog link not found"}), 404
    links = [l for l in links if l["id"] != link_id]
    _save_blog_links(links)
    return jsonify({"status": "deleted", "id": link_id})


# --- Contact ---

@blueprint.route("/api/contact", methods=["POST"])
def api_submit_contact():
    data = request.get_json(silent=True) or {}
    if not data.get("name") or not data.get("email") or not data.get("message"):
        return jsonify({"error": "Name, email, and message are required"}), 400

    messages = _load_contact_messages()
    new_id = max((m["id"] for m in messages), default=0) + 1

    message = {
        "id": new_id,
        "name": data["name"],
        "email": data["email"],
        "subject": data.get("subject", ""),
        "message": data["message"],
        "timestamp": datetime.now().isoformat(),
        "read": False,
    }
    messages.append(message)
    _save_contact_messages(messages)
    return jsonify({"status": "sent", "id": new_id}), 201


# --- Stats ---

@blueprint.route("/api/stats", methods=["GET"])
def api_stats():
    profile = _load_profile()
    projects = _load_projects()
    blog_links = _load_blog_links()
    messages = _load_contact_messages()

    # Aggregate technology counts
    tech_counts = {}
    for p in projects:
        for t in p.get("technologies", []):
            tech_counts[t] = tech_counts.get(t, 0) + 1

    # Project type counts
    type_counts = {}
    for p in projects:
        ptype = p.get("type", "other")
        type_counts[ptype] = type_counts.get(ptype, 0) + 1

    return jsonify({
        "total_projects": len(projects),
        "active_projects": sum(1 for p in projects if p.get("status") == "active"),
        "featured_projects": sum(1 for p in projects if p.get("featured")),
        "total_blog_posts": len(blog_links),
        "total_skills": len(profile.get("skills", [])),
        "total_contact_messages": len(messages),
        "unread_messages": sum(1 for m in messages if not m.get("read")),
        "technologies": tech_counts,
        "project_types": type_counts,
        "blog_categories": list(set(b.get("category", "") for b in blog_links)),
    })


# --- Semantic search API (navigate_by_semantic, extract_by_semantic) ---

@blueprint.route("/api/search", methods=["GET"])
def api_search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([])
    results = _semantic_search(query)
    return jsonify(results)


# --- Skills table API (extract_from_table) ---

@blueprint.route("/api/skills", methods=["GET"])
def api_skills():
    """Return skills from both profile and resume as a flat table-ready list."""
    profile = _load_profile()
    resume = _load_resume()

    rows = []
    # Profile skills (with level and years)
    for s in profile.get("skills", []):
        rows.append({
            "name": s["name"],
            "level": s.get("level", ""),
            "years": s.get("years", 0),
            "source": "profile",
        })

    # Resume skills (categorised)
    for category, skill_list in resume.get("skills", {}).items():
        for skill_name in skill_list:
            # Check if already covered by profile skills
            existing = next((r for r in rows if r["name"] == skill_name), None)
            if existing:
                existing["category"] = category
            else:
                rows.append({
                    "name": skill_name,
                    "level": "",
                    "years": 0,
                    "source": "resume",
                    "category": category,
                })

    # Ensure all rows have the category key
    for r in rows:
        if "category" not in r:
            r["category"] = ""

    return jsonify(rows)


# --- Export API (export_by_dropdown) ---

@blueprint.route("/api/export", methods=["GET"])
def api_export():
    """Export resume or projects in JSON or CSV format.

    Query params:
      - type: 'resume' | 'projects' (default: 'projects')
      - format: 'json' | 'csv' (default: 'json')
      - category: filter projects by type (optional, for projects only)
    """
    export_type = request.args.get("type", "projects").strip().lower()
    fmt = request.args.get("format", "json").strip().lower()
    category = request.args.get("category", "").strip()

    if export_type == "resume":
        resume = _load_resume()
        if fmt == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            # Flatten resume into skills CSV
            writer.writerow(["category", "skill"])
            for cat, skills in resume.get("skills", {}).items():
                for skill in skills:
                    writer.writerow([cat, skill])
            return Response(
                output.getvalue(),
                mimetype="text/csv",
                headers={"Content-Disposition": "attachment; filename=resume_skills.csv"},
            )
        else:
            return jsonify(resume)

    else:  # projects
        projects = _load_projects()
        if category:
            projects = [p for p in projects
                        if p.get("type", "").lower() == category.lower()]

        if fmt == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["id", "title", "type", "status", "technologies",
                             "started", "last_updated", "featured"])
            for p in projects:
                writer.writerow([
                    p["id"], p["title"], p.get("type", ""),
                    p.get("status", ""),
                    "; ".join(p.get("technologies", [])),
                    p.get("started", ""), p.get("last_updated", ""),
                    p.get("featured", False),
                ])
            return Response(
                output.getvalue(),
                mimetype="text/csv",
                headers={"Content-Disposition": "attachment; filename=projects.csv"},
            )
        else:
            return jsonify(projects)


# --- Subscribe / newsletter toggle API (subscribe_by_toggle) ---

@blueprint.route("/api/subscribe", methods=["POST"])
def api_subscribe_toggle():
    """Toggle newsletter subscription for an email address.

    JSON body: {"email": "...", "name": "..."}
    If already subscribed, unsubscribes. If not subscribed, subscribes.
    Returns the action taken: 'subscribed' or 'unsubscribed'.
    """
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip()
    if not email:
        return jsonify({"error": "Email is required"}), 400

    subs = _load_subscriptions()
    existing = next((s for s in subs if s["email"].lower() == email.lower()), None)

    if existing:
        existing["subscribed"] = not existing["subscribed"]
        action = "subscribed" if existing["subscribed"] else "unsubscribed"
    else:
        new_id = max((s["id"] for s in subs), default=0) + 1
        subs.append({
            "id": new_id,
            "email": email,
            "name": data.get("name", ""),
            "subscribed": True,
            "created": datetime.now().isoformat(),
        })
        action = "subscribed"

    _save_subscriptions(subs)
    return jsonify({"action": action, "email": email})


@blueprint.route("/api/subscriptions", methods=["GET"])
def api_list_subscriptions():
    """List all subscriptions (admin view)."""
    subs = _load_subscriptions()
    return jsonify(subs)


# --- Contact messages list API ---

@blueprint.route("/api/contact", methods=["GET"])
def api_list_contact_messages():
    """List all contact messages (for verifiers)."""
    messages = _load_contact_messages()
    return jsonify(messages)


# --- Login API ---

@blueprint.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user:
        return jsonify({"error": "Invalid credentials"}), 401
    session["user_id"] = user["id"]
    return jsonify({"user_id": user["id"], "username": user["username"],
                    "display_name": user["display_name"]})


@blueprint.route("/api/logout", methods=["POST"])
def api_logout():
    session.pop("user_id", None)
    return jsonify({"status": "logged_out"})
