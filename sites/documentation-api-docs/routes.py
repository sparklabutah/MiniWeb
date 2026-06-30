"""Documentation / API Docs — Technical docs site modeled after Stripe Docs.

Serves structured documentation pages with sidebar navigation, search,
API reference with method badges, changelog, and user bookmarks.
Data is loaded from JSON files in the data/ directory.
"""
import pathlib

from flask import Blueprint, Response, abort, jsonify, redirect, render_template, request, session, url_for
from app import db

SITE = "documentation-api-docs"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "documentation-api-docs",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

_docs = None
_search_index = None
_sections = None
_section_order = ["Getting Started", "Workflows", "Tasks", "Webhooks", "SDKs", "Changelog"]


def _load_docs():
    return db.query(SITE, "docs")


def _load_search_index():
    return db.query(SITE, "search_index")


def _ensure_loaded():
    global _docs, _search_index, _sections
    if _docs is None:
        _docs = _load_docs()
        _docs.sort(key=lambda d: d.get("order_", 0))
        _search_index = _load_search_index()
        _sections = {}
        for doc in _docs:
            sec = doc["section"]
            _sections.setdefault(sec, []).append(doc)


def _get_docs():
    _ensure_loaded()
    return _docs


def _get_sections():
    _ensure_loaded()
    return _sections


def _get_search_index():
    _ensure_loaded()
    return _search_index


def _get_ordered_sections():
    """Return sections in canonical order."""
    sections = _get_sections() or {}
    ordered = []
    for name in _section_order:
        if name in sections:
            ordered.append((name, sections[name]))
    # Include any extra sections not in the predefined order
    for name in sections:
        if name not in _section_order:
            ordered.append((name, sections[name]))
    return ordered


# ---------------------------------------------------------------------------
# Users (mutable state)
# ---------------------------------------------------------------------------

def _load_users():
    return db.query(SITE, "users")


def _save_users(users):
    db.save_collection(SITE, "users", users)


def _get_user(user_id):
    return db.get_item(SITE, "users", user_id)


# ---------------------------------------------------------------------------
# Search helpers
# ---------------------------------------------------------------------------

def _search_docs(query):
    """Search docs by matching query terms against title, content, tags, and search index keywords."""
    if not query:
        return _get_docs()
    q = query.lower().strip()
    terms = q.split()
    docs = _get_docs()
    search_index = _get_search_index()

    # Build keyword lookup from search index
    doc_keywords = {}
    for entry in search_index:
        doc_keywords[entry["doc_id"]] = [kw.lower() for kw in entry["keywords"]]

    scored = []
    for doc in docs:
        score = 0
        title_lower = doc["title"].lower()
        content_lower = doc["content"].lower()
        tags_lower = " ".join(doc.get("tags", [])).lower()
        keywords = doc_keywords.get(doc["id"], [])

        for term in terms:
            if term in title_lower:
                score += 5
            if term in content_lower:
                score += 1
            if term in tags_lower:
                score += 3
            if any(term in kw for kw in keywords):
                score += 2
        if score > 0:
            scored.append((doc, score))

    scored.sort(key=lambda x: -x[1])
    return [doc for doc, _ in scored]


# ---------------------------------------------------------------------------
# Helper: extract API endpoints from docs
# ---------------------------------------------------------------------------

def _extract_endpoints():
    """Extract API endpoint info from API Reference docs."""
    docs = _get_docs()
    endpoints = []
    for doc in docs:
        content = doc["content"]
        # Extract method and path from code blocks like "GET /api/v1/namespaces/..."
        import re
        matches = re.findall(r'\b(GET|POST|PUT|DELETE|PATCH)\s+(/api[s]?/[^\s`\n]+)', content)
        for method, path in matches:
            endpoints.append({
                "method": method,
                "path": path,
                "doc_id": doc["id"],
                "doc_title": doc["title"],
                "doc_slug": doc["slug"],
            })
    return endpoints


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    docs = _get_docs()
    ordered_sections = _get_ordered_sections()
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("documentation-api-docs/index.html",
                           docs=docs, ordered_sections=ordered_sections, user=user)


@blueprint.route("/page/<slug>")
def page(slug):
    docs = _get_docs()
    doc = next((d for d in docs if d["slug"] == slug), None)
    if doc is None:
        abort(404)
    ordered_sections = _get_ordered_sections()
    # Find prev/next
    idx = next((i for i, d in enumerate(docs) if d["id"] == doc["id"]), 0)
    prev_doc = docs[idx - 1] if idx > 0 else None
    next_doc = docs[idx + 1] if idx < len(docs) - 1 else None
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("documentation-api-docs/page.html",
                           doc=doc, ordered_sections=ordered_sections,
                           prev_doc=prev_doc, next_doc=next_doc, user=user)


@blueprint.route("/api-reference")
def api_reference():
    docs = _get_docs()
    api_sections = {"Workflows", "Tasks", "Webhooks"}
    api_docs = [d for d in docs if d["section"] in api_sections]
    endpoints = _extract_endpoints()
    ordered_sections = _get_ordered_sections()
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("documentation-api-docs/api_reference.html",
                           api_docs=api_docs, endpoints=endpoints,
                           ordered_sections=ordered_sections, user=user)


@blueprint.route("/search")
def search_page():
    q = request.args.get("q", "").strip()
    results = _search_docs(q) if q else []
    ordered_sections = _get_ordered_sections()
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("documentation-api-docs/search.html",
                           q=q, results=results,
                           ordered_sections=ordered_sections, user=user)


@blueprint.route("/changelog")
def changelog():
    docs = _get_docs()
    changelog_docs = [d for d in docs if d["section"] == "Changelog"]
    changelog_docs.sort(key=lambda d: d["updated_at"], reverse=True)
    ordered_sections = _get_ordered_sections()
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("documentation-api-docs/changelog.html",
                           changelog_docs=changelog_docs,
                           ordered_sections=ordered_sections, user=user)


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("documentation-api-docs/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return render_template("documentation-api-docs/login.html",
                               error="Invalid username or password")
    session["user_id"] = user["id"]
    return redirect(url_for("documentation-api-docs.dashboard"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("documentation-api-docs.index"))


@blueprint.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("documentation-api-docs.login_page"))
    user = _get_user(session["user_id"])
    if not user:
        return redirect(url_for("documentation-api-docs.login_page"))
    docs = _get_docs()
    bookmarked = [d for d in docs if d["id"] in user.get("bookmarked_pages", [])]
    ordered_sections = _get_ordered_sections()
    return render_template("documentation-api-docs/dashboard.html",
                           user=user, bookmarked=bookmarked,
                           ordered_sections=ordered_sections)


# ---------------------------------------------------------------------------
# Form-based mutation routes (browser automation compatible)
# ---------------------------------------------------------------------------

@blueprint.route("/page/<slug>/bookmark", methods=["POST"])
def form_bookmark_page(slug):
    if "user_id" not in session:
        return redirect(url_for("documentation-api-docs.login_page"))
    docs = _get_docs()
    doc = next((d for d in docs if d["slug"] == slug), None)
    if doc is None:
        abort(404)
    users = _load_users()
    user = next((u for u in users if u["id"] == session["user_id"]), None)
    if not user:
        return redirect(url_for("documentation-api-docs.login_page"))
    bookmarks = user.setdefault("bookmarked_pages", [])
    if doc["id"] in bookmarks:
        bookmarks.remove(doc["id"])
    else:
        bookmarks.append(doc["id"])
    _save_users(users)
    return redirect(url_for("documentation-api-docs.page", slug=slug))


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/docs")
def api_docs_list():
    docs = _get_docs()
    section = request.args.get("section", "").strip()
    tag = request.args.get("tag", "").strip()
    results = list(docs)
    if section:
        results = [d for d in results if d["section"] == section]
    if tag:
        results = [d for d in results if tag in d.get("tags", [])]
    return jsonify(results)


@blueprint.route("/api/docs/<int:doc_id>")
def api_doc_detail(doc_id):
    docs = _get_docs()
    doc = next((d for d in docs if d["id"] == doc_id), None)
    if doc is None:
        abort(404)
    return jsonify(doc)


@blueprint.route("/api/docs/search")
def api_docs_search():
    q = request.args.get("q", "").strip()
    results = _search_docs(q)
    return jsonify(results)


@blueprint.route("/api/sections")
def api_sections():
    sections = _get_sections()
    result = []
    for name in _section_order:
        if name in sections:
            result.append({
                "name": name,
                "count": len(sections[name]),
                "doc_ids": [d["id"] for d in sections[name]],
            })
    for name in sections:
        if name not in _section_order:
            result.append({
                "name": name,
                "count": len(sections[name]),
                "doc_ids": [d["id"] for d in sections[name]],
            })
    return jsonify(result)


@blueprint.route("/api/endpoints")
def api_endpoints():
    endpoints = _extract_endpoints()
    method_filter = request.args.get("method", "").strip().upper()
    if method_filter:
        endpoints = [e for e in endpoints if e["method"] == method_filter]
    return jsonify(endpoints)


@blueprint.route("/api/changelog")
def api_changelog():
    docs = _get_docs()
    changelog_docs = [d for d in docs if d["section"] == "Changelog"]
    changelog_docs.sort(key=lambda d: d["updated_at"], reverse=True)
    return jsonify(changelog_docs)


# ---------------------------------------------------------------------------
# User API routes (mutable state)
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


@blueprint.route("/api/users/<int:user_id>/bookmark", methods=["POST"])
def api_bookmark(user_id):
    data = request.get_json(silent=True) or {}
    doc_id = data.get("doc_id")
    if doc_id is None:
        return jsonify({"error": "doc_id required"}), 400
    # Validate doc exists
    docs = _get_docs()
    doc = next((d for d in docs if d["id"] == doc_id), None)
    if doc is None:
        return jsonify({"error": "doc not found"}), 404
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    bookmarks = user.setdefault("bookmarked_pages", [])
    if doc_id in bookmarks:
        bookmarks.remove(doc_id)
        action = "unbookmarked"
    else:
        bookmarks.append(doc_id)
        action = "bookmarked"
    _save_users(users)
    return jsonify({"action": action, "doc_id": doc_id, "total_bookmarks": len(bookmarks)})
