"""LakeportWiki — collaborative wiki encyclopedia for Lakeport, WA.

Data: reads real Wikipedia articles from the wikis_articles SQLite table,
then merges Lakeport overlay pages on top.  Mutable state (pages, revisions,
users) is persisted via db.save_collection().
"""
import json
import pathlib
import re
from collections import Counter
from datetime import datetime

from flask import (
    Blueprint, abort, jsonify, redirect, render_template, request, session, url_for,
)

from app import db
from app.events import emit

SITE = "wikis"
SITE_DIR = pathlib.Path(__file__).resolve().parent


blueprint = Blueprint(
    "wikis",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Raw data interpreter — converts wiki article records to page dicts
# ---------------------------------------------------------------------------

# Wikipedia categories we recognise in the raw sample.  Used for merging into
# the overlay category list and for browse-by-category.
_WIKIPEDIA_CATEGORIES = [
    "Science", "History", "Geography", "Technology", "Arts",
    "Sports", "Politics", "Society", "Biography", "Nature",
]


def _normalise_slug(title):
    """Convert an article title to a URL-safe slug.

    Underscores become hyphens (ZIM paths use them as word separators) —
    dropping them collapsed "Houston_Street" into "houstonstreet", which the
    reverse lookup could never resolve, so multi-word article links 404ed.
    """
    slug = title.lower().strip()
    slug = slug.replace("_", "-")
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


def _interpret_wiki_article(raw, idx):
    """Convert a raw JSONL record into the page dict shape the templates expect.

    Expected raw fields (from extract_wiki_sample.py):
        title, extract (or content), description, categories, views, pageid
    """
    title = raw.get("title", "").strip()
    content = raw.get("content") or raw.get("extract") or raw.get("description") or ""
    # Truncate very long content (ZIM articles can be 50KB+ of HTML)
    if len(content) > 5000:
        content = content[:5000]
    # ZIM articles have path like "A/Article_Name" — extract slug from it
    path = raw.get("path", "")
    if path.startswith("A/"):
        path = path[2:]
    slug = raw.get("slug") or _normalise_slug(path or title)

    # Pick a category from the raw record or fall back to the first known one
    raw_cats = raw.get("categories", [])
    category = "Wikipedia"
    for rc in raw_cats:
        for wc in _WIKIPEDIA_CATEGORIES:
            if wc.lower() in rc.lower():
                category = wc
                break
        if category != "Wikipedia":
            break

    views = raw.get("views", 0)
    if isinstance(views, str):
        views = int(re.sub(r"[^\d]", "", views) or "0")

    return {
        "id": 100000 + idx,          # high ID range to avoid overlay collisions
        "title": title,
        "slug": slug,
        "content": content,
        "category": category,
        "author_id": 0,              # no specific overlay author
        "created_at": raw.get("timestamp", "2022-05-01T00:00:00"),
        "updated_at": raw.get("timestamp", "2022-05-01T00:00:00"),
        "views": views,
        "linked_pages": [],
        "_source": "wikipedia",       # internal marker (not used by templates)
    }


def _load_raw_wiki(limit=200):
    """Load real Wikipedia articles from the wikis_articles table.

    Returns a list of page dicts in the same shape as the overlay pages.
    Returns an empty list when the table is empty (graceful fallback).
    Capped at `limit` rows to avoid multi-second loads (50K rows x full content).
    """
    try:
        from app.db import _get_conn, _deserialize_row
        conn = _get_conn()
        rows = conn.execute("SELECT * FROM wikis_articles LIMIT ?", (limit,)).fetchall()
    except Exception:
        return []

    pages = []
    for idx, row in enumerate(rows, 1):
        raw = _deserialize_row(row)
        # Parse JSON columns stored as TEXT
        if isinstance(raw.get("categories"), str):
            try:
                raw["categories"] = json.loads(raw["categories"])
            except (json.JSONDecodeError, TypeError):
                raw["categories"] = []
        pages.append(_interpret_wiki_article(raw, idx))
    return pages


def _raw_wiki_count():
    """Return count of raw Wikipedia articles (fast, no content loading)."""
    try:
        from app.db import _get_conn
        conn = _get_conn()
        return conn.execute("SELECT COUNT(*) FROM wikis_articles").fetchone()[0]
    except Exception:
        return 0


def _find_raw_wiki_by_slug(slug):
    """Find a single raw Wikipedia article by slug without loading all articles.

    Searches by title since slugs are derived from titles/paths.
    """
    try:
        from app.db import _get_conn, _deserialize_row
        conn = _get_conn()
        # Normalized-path match: mirror _normalise_slug's transform in SQL so
        # the slug round-trips ("A/Houston_Street" <-> "houston-street"),
        # case-insensitively
        rows = conn.execute(
            "SELECT * FROM wikis_articles WHERE "
            "LOWER(REPLACE(REPLACE(SUBSTR(path, 3), '_', '-'), ' ', '-')) = ? "
            "LIMIT 1",
            (slug,)).fetchall()
        if not rows:
            # Fallback for titles with punctuation the slug strips, e.g.
            # "The Spires (Houston)": narrow by the first word, then compare
            # each candidate's recomputed slug exactly
            first = slug.split("-", 1)[0]
            candidates = conn.execute(
                "SELECT * FROM wikis_articles WHERE LOWER(title) LIKE ? LIMIT 200",
                (f"%{first}%",)).fetchall()
            rows = [r for r in candidates
                    if _normalise_slug(r["path"][2:] if r["path"] else r["title"]) == slug][:1]
        if rows:
            raw = _deserialize_row(rows[0])
            if isinstance(raw.get("categories"), str):
                try:
                    raw["categories"] = json.loads(raw["categories"])
                except (json.JSONDecodeError, TypeError):
                    raw["categories"] = []
            return _interpret_wiki_article(raw, raw.get("row_id", 1))
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _load_pages(include_raw=True, raw_limit=200):
    """Load merged page list: raw Wikipedia base + overlay Lakeport pages.

    Overlay pages (IDs 1-30) always take precedence.  Raw Wikipedia articles
    use IDs starting at 100 000.  The merged list is returned for read
    operations; write operations only touch the overlay collection.

    Set include_raw=False to skip the (slow) raw Wikipedia load.
    """
    overlay_pages = db.query(SITE, "pages")
    if not include_raw:
        return overlay_pages
    raw_pages = _load_raw_wiki(limit=raw_limit)

    if not raw_pages:
        return overlay_pages

    # Deduplicate: overlay slugs win over raw slugs
    overlay_slugs = {p["slug"] for p in overlay_pages}
    merged = list(overlay_pages)
    for rp in raw_pages:
        if rp["slug"] not in overlay_slugs:
            merged.append(rp)

    return merged


def _load_overlay_pages():
    """Load overlay pages only (for mutation operations)."""
    return db.query(SITE, "pages")


def _save_pages(pages):
    """Save overlay pages only.  Caller must ensure no raw Wikipedia pages
    are included — use _load_overlay_pages() for mutation workflows."""
    db.save_collection(SITE, "pages", pages)


def _load_revisions():
    return db.query(SITE, "revisions")


def _save_revisions(revisions):
    db.save_collection(SITE, "revisions", revisions)


def _load_categories():
    """Load categories: overlay categories + Wikipedia category.

    Uses SQL COUNT for overlay page counts (fast) and adds a single
    'Wikipedia' meta-category for the raw article count.
    """
    overlay_cats = db.query(SITE, "categories")

    # Count overlay pages per category via SQL
    table = db.get_table_name(SITE, "pages")
    try:
        cat_rows = db.execute(
            f"SELECT category, COUNT(*) as cnt FROM [{table}] GROUP BY category")
        cat_counts = {r["category"]: r["cnt"] for r in cat_rows}
    except Exception:
        cat_counts = {}

    for c in overlay_cats:
        c["page_count"] = cat_counts.get(c["name"], 0)

    # Add Wikipedia meta-category for raw articles
    raw_count = _raw_wiki_count()
    if raw_count > 0:
        overlay_cats.append({
            "id": 1009,
            "name": "Wikipedia",
            "description": "Articles about Wikipedia from Wikipedia.",
            "page_count": raw_count,
        })

    return overlay_cats


def _save_categories(categories):
    db.save_collection(SITE, "categories", categories)


def _load_users():
    return db.query(SITE, "users")


def _save_users(users):
    db.save_collection(SITE, "users", users)


def _get_user(user_id):
    users = _load_users()
    return next((u for u in users if u["id"] == user_id), None)


def _get_page_by_slug(slug):
    """Find a page by slug: checks overlay pages first (fast), then raw wiki."""
    # Try overlay first (small table, fast)
    overlay = db.query(SITE, "pages")
    page = next((p for p in overlay if p["slug"] == slug), None)
    if page:
        return page
    # Fall back to raw Wikipedia article lookup (targeted, not full scan)
    return _find_raw_wiki_by_slug(slug)


def _recount_categories():
    """Recompute page_count for each category (overlay collection only, via SQL)."""
    table = db.get_table_name(SITE, "pages")
    try:
        cat_rows = db.execute(
            f"SELECT category, COUNT(*) as cnt FROM [{table}] GROUP BY category")
        counts = {r["category"]: r["cnt"] for r in cat_rows}
    except Exception:
        counts = {}
    categories = db.query(SITE, "categories")
    for c in categories:
        c["page_count"] = counts.get(c["name"], 0)
    _save_categories(categories)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def _search_pages(pages, query):
    if not query:
        return pages
    q = query.lower().strip()
    scored = []
    for p in pages:
        text = (p["title"] + " " + p["content"] + " " + p.get("category", "")).lower()
        terms = q.split()
        score = sum(1 for t in terms if t in text)
        if score > 0:
            scored.append((p, score))
    scored.sort(key=lambda x: -x[1])
    return [p for p, _ in scored]


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    # Use overlay pages only for the main page (fast); raw articles are for search
    pages = _load_overlay_pages()
    categories = _load_categories()
    user = _get_user(session.get("user_id")) if "user_id" in session else None
    # Sort by views descending for main page
    featured = sorted(pages, key=lambda p: -p["views"])[:10]
    recent_edits = sorted(pages, key=lambda p: p["updated_at"], reverse=True)[:10]
    return render_template("wikis/index.html",
                           pages=pages, categories=categories,
                           featured=featured, recent_edits=recent_edits,
                           user=user)


@blueprint.route("/wiki/<slug>")
def wiki_page(slug):
    page = _get_page_by_slug(slug)
    if not page:
        abort(404)
    overlay_pages = _load_overlay_pages()
    revisions = _load_revisions()
    page_revisions = [r for r in revisions if r["page_id"] == page["id"]]
    page_revisions.sort(key=lambda r: r["timestamp"], reverse=True)
    users = _load_users()
    author = next((u for u in users if u["id"] == page["author_id"]), None)
    # Resolve linked pages (overlay only -- linked pages are always overlay slugs)
    linked = []
    for lp_slug in page.get("linked_pages", []):
        lp = next((p for p in overlay_pages if p["slug"] == lp_slug), None)
        if lp:
            linked.append(lp)
    user = _get_user(session.get("user_id")) if "user_id" in session else None
    categories = _load_categories()
    return render_template("wikis/article.html",
                           page=page, revisions=page_revisions,
                           author=author, linked=linked, user=user,
                           categories=categories)


@blueprint.route("/edit/<slug>")
def edit_page(slug):
    page = _get_page_by_slug(slug)
    if not page:
        abort(404)
    user = _get_user(session.get("user_id")) if "user_id" in session else None
    categories = _load_categories()
    return render_template("wikis/edit.html", page=page, user=user,
                           categories=categories)


@blueprint.route("/edit/<slug>", methods=["POST"])
def edit_page_submit(slug):
    # For edits we work against the overlay file only.  If the slug belongs
    # to a raw Wikipedia article we promote it into the overlay first.
    overlay_pages = _load_overlay_pages()
    page = next((p for p in overlay_pages if p["slug"] == slug), None)

    if not page:
        # Check if it's a raw Wikipedia page — promote to overlay for editing
        all_pages = _load_pages()
        raw_page = next((p for p in all_pages if p["slug"] == slug), None)
        if not raw_page:
            abort(404)
        # Copy into overlay (strip internal marker)
        promoted = {k: v for k, v in raw_page.items() if not k.startswith("_")}
        overlay_pages.append(promoted)
        page = promoted

    new_content = request.form.get("content", "").strip()
    new_title = request.form.get("title", "").strip() or page["title"]
    new_category = request.form.get("category", "").strip() or page["category"]
    summary = request.form.get("summary", "").strip() or "Updated page"

    if not new_content:
        return "Content is required", 400

    old_lines = page["content"].count("\n")
    new_lines = new_content.count("\n")

    page["content"] = new_content
    page["title"] = new_title
    page["category"] = new_category
    page["updated_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    _save_pages(overlay_pages)

    # Create revision
    revisions = _load_revisions()
    new_rev_id = max((r["id"] for r in revisions), default=0) + 1
    editor_id = session.get("user_id", 1)
    revisions.append({
        "id": new_rev_id,
        "page_id": page["id"],
        "editor_id": editor_id,
        "timestamp": page["updated_at"],
        "summary": summary,
        "diff_lines_added": max(0, new_lines - old_lines + 2),
        "diff_lines_removed": max(0, old_lines - new_lines + 1),
    })
    _save_revisions(revisions)

    # Update user edit count
    users = _load_users()
    editor = next((u for u in users if u["id"] == editor_id), None)
    if editor:
        editor["edit_count"] = editor.get("edit_count", 0) + 1
        _save_users(users)

    _recount_categories()
    return redirect(url_for("wikis.wiki_page", slug=slug))


@blueprint.route("/create")
def create_page():
    user = _get_user(session.get("user_id")) if "user_id" in session else None
    categories = _load_categories()
    return render_template("wikis/create.html", user=user, categories=categories)


@blueprint.route("/create", methods=["POST"])
def create_page_submit():
    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()
    category = request.form.get("category", "").strip()
    slug = request.form.get("slug", "").strip()

    if not title or not content:
        return "Title and content are required", 400

    if not slug:
        slug = title.lower().replace(" ", "-")
        slug = "".join(c for c in slug if c.isalnum() or c == "-")

    # Check slug uniqueness: overlay first, then raw
    if _get_page_by_slug(slug):
        return "A page with that slug already exists", 400

    overlay_pages = _load_overlay_pages()
    new_id = max((p["id"] for p in overlay_pages), default=0) + 1
    editor_id = session.get("user_id", 1)
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    new_page = {
        "id": new_id,
        "title": title,
        "slug": slug,
        "content": content,
        "category": category or "Lakeport City",
        "author_id": editor_id,
        "created_at": now,
        "updated_at": now,
        "views": 0,
        "linked_pages": [],
    }
    # Only append to overlay pages, not the merged list
    overlay_pages = _load_overlay_pages()
    overlay_pages.append(new_page)
    _save_pages(overlay_pages)

    # Create revision
    revisions = _load_revisions()
    new_rev_id = max((r["id"] for r in revisions), default=0) + 1
    revisions.append({
        "id": new_rev_id,
        "page_id": new_id,
        "editor_id": editor_id,
        "timestamp": now,
        "summary": f"Created article: {title}",
        "diff_lines_added": content.count("\n") + 1,
        "diff_lines_removed": 0,
    })
    _save_revisions(revisions)

    # Update user edit count
    users = _load_users()
    editor = next((u for u in users if u["id"] == editor_id), None)
    if editor:
        editor["edit_count"] = editor.get("edit_count", 0) + 1
        _save_users(users)

    _recount_categories()
    return redirect(url_for("wikis.wiki_page", slug=slug))


@blueprint.route("/category/<int:cat_id>")
def category_page(cat_id):
    categories = _load_categories()
    cat = next((c for c in categories if c["id"] == cat_id), None)
    if not cat:
        abort(404)
    # Use SQL filtering for overlay pages; for Wikipedia category, use raw data
    if cat["name"] == "Wikipedia":
        pages = _load_raw_wiki(limit=50)
    else:
        # Overlay pages filtered by category via SQL
        cat_pages = db.query(SITE, "pages", where={"category": cat["name"]}, sort="title")
        pages = cat_pages
    cat_pages = [p for p in pages if p["category"] == cat["name"]]
    cat_pages.sort(key=lambda p: p["title"])
    user = _get_user(session.get("user_id")) if "user_id" in session else None
    return render_template("wikis/category.html", category=cat,
                           pages=cat_pages, categories=categories, user=user)


@blueprint.route("/recent-changes")
def recent_changes():
    revisions = _load_revisions()
    revisions_sorted = sorted(revisions, key=lambda r: r["timestamp"], reverse=True)
    pages = _load_overlay_pages()  # revisions are only for overlay pages
    users = _load_users()
    page_map = {p["id"]: p for p in pages}
    user_map = {u["id"]: u for u in users}
    enriched = []
    for rev in revisions_sorted:
        pg = page_map.get(rev["page_id"])
        editor = user_map.get(rev["editor_id"])
        enriched.append({
            **rev,
            "page_title": pg["title"] if pg else "Unknown",
            "page_slug": pg["slug"] if pg else "",
            "editor_name": editor["display_name"] if editor else "Unknown",
            "editor_username": editor["username"] if editor else "",
        })
    user = _get_user(session.get("user_id")) if "user_id" in session else None
    categories = _load_categories()
    return render_template("wikis/recent_changes.html",
                           revisions=enriched, user=user, categories=categories)


@blueprint.route("/search")
def search():
    q = request.args.get("q", "").strip()
    results = []
    if q:
        # Search overlay pages first
        overlay_results = db.search(SITE, "pages", q, limit=10)
        # Search raw wiki articles via FTS5
        try:
            from app.db import _get_conn, _deserialize_row
            conn = _get_conn()
            terms = q.strip().split()
            fts_query = " ".join(f'"{t}"*' for t in terms if t)
            rows = conn.execute(
                "SELECT a.* FROM wikis_articles a "
                "JOIN fts_wikis_articles fts ON a.row_id = fts.rowid "
                "WHERE fts_wikis_articles MATCH ? ORDER BY fts.rank LIMIT 40",
                (fts_query,)).fetchall()
            wiki_results = [_interpret_wiki_article(_deserialize_row(r), r['row_id']) for r in rows]
        except Exception:
            wiki_results = []
        # Merge: overlay first, then wiki articles, deduplicate by title
        seen = set()
        for p in overlay_results + wiki_results:
            if p["title"] not in seen:
                seen.add(p["title"])
                results.append(p)
    user = _get_user(session.get("user_id")) if "user_id" in session else None
    categories = _load_categories()
    return render_template("wikis/search.html", q=q, results=results,
                           user=user, categories=categories)


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("wikis/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return render_template("wikis/login.html", error="Invalid username or password")
    session["user_id"] = user["id"]
    emit("signup", user_id=user["id"], site_name="wikis", username=request.form.get("username", ""), password=request.form.get("password", ""), email="")
    return redirect(url_for("wikis.index"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("wikis.index"))


# ---------------------------------------------------------------------------
# API routes — read
# ---------------------------------------------------------------------------

@blueprint.route("/api/pages")
def api_pages():
    # Prefer overlay-only for filtered/sorted queries (fast); include raw only for search
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    sort_field = request.args.get("sort", "title").strip()
    limit = request.args.get("limit", type=int)
    include_raw = request.args.get("include_raw", "false").lower() == "true"

    if q:
        # Search needs all pages including raw
        pages = _load_pages(include_raw=True, raw_limit=200)
        pages = _search_pages(pages, q)
    elif category and category != "Wikipedia":
        # Overlay categories: use SQL filter
        pages = db.query(SITE, "pages", where={"category": category})
    elif category == "Wikipedia":
        pages = _load_raw_wiki(limit=50)
    elif include_raw:
        pages = _load_pages(include_raw=True, raw_limit=200)
    else:
        pages = _load_overlay_pages()

    if sort_field == "title":
        pages.sort(key=lambda p: p["title"])
    elif sort_field == "views":
        pages.sort(key=lambda p: -p["views"])
    elif sort_field == "updated":
        pages.sort(key=lambda p: p["updated_at"], reverse=True)
    elif sort_field == "created":
        pages.sort(key=lambda p: p["created_at"], reverse=True)
    if limit:
        pages = pages[:limit]
    return jsonify(pages)


@blueprint.route("/api/pages/<slug>", methods=["GET"])
def api_page_get(slug):
    page = _get_page_by_slug(slug)
    if not page:
        abort(404)
    return jsonify(page)


@blueprint.route("/api/pages/<slug>", methods=["PUT"])
def api_page_update(slug):
    overlay_pages = _load_overlay_pages()
    page = next((p for p in overlay_pages if p["slug"] == slug), None)

    if not page:
        # Promote raw Wikipedia page to overlay for editing
        all_pages = _load_pages()
        raw_page = next((p for p in all_pages if p["slug"] == slug), None)
        if not raw_page:
            abort(404)
        promoted = {k: v for k, v in raw_page.items() if not k.startswith("_")}
        overlay_pages.append(promoted)
        page = promoted

    data = request.get_json(silent=True) or {}
    summary = data.get("summary", "Updated page via API")

    old_lines = page["content"].count("\n")

    if "content" in data:
        page["content"] = data["content"]
    if "title" in data:
        page["title"] = data["title"]
    if "category" in data:
        page["category"] = data["category"]
    if "linked_pages" in data:
        page["linked_pages"] = data["linked_pages"]

    page["updated_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    _save_pages(overlay_pages)

    new_lines = page["content"].count("\n")

    # Create revision
    revisions = _load_revisions()
    new_rev_id = max((r["id"] for r in revisions), default=0) + 1
    editor_id = data.get("editor_id", session.get("user_id", 1))
    revisions.append({
        "id": new_rev_id,
        "page_id": page["id"],
        "editor_id": editor_id,
        "timestamp": page["updated_at"],
        "summary": summary,
        "diff_lines_added": max(0, new_lines - old_lines + 2),
        "diff_lines_removed": max(0, old_lines - new_lines + 1),
    })
    _save_revisions(revisions)

    # Update user edit count
    users = _load_users()
    editor = next((u for u in users if u["id"] == editor_id), None)
    if editor:
        editor["edit_count"] = editor.get("edit_count", 0) + 1
        _save_users(users)

    _recount_categories()
    return jsonify(page)


@blueprint.route("/api/pages", methods=["POST"])
def api_page_create():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    content = data.get("content", "").strip()
    category = data.get("category", "Lakeport City").strip()
    slug = data.get("slug", "").strip()

    if not title or not content:
        return jsonify({"error": "title and content required"}), 400

    if not slug:
        slug = title.lower().replace(" ", "-")
        slug = "".join(c for c in slug if c.isalnum() or c == "-")

    # Check slug uniqueness: overlay first, then raw
    if _get_page_by_slug(slug):
        return jsonify({"error": "slug already exists"}), 400

    overlay_pages = _load_overlay_pages()
    new_id = max((p["id"] for p in overlay_pages), default=0) + 1
    editor_id = data.get("author_id", session.get("user_id", 1))
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    new_page = {
        "id": new_id,
        "title": title,
        "slug": slug,
        "content": content,
        "category": category,
        "author_id": editor_id,
        "created_at": now,
        "updated_at": now,
        "views": 0,
        "linked_pages": data.get("linked_pages", []),
    }
    overlay_pages = _load_overlay_pages()
    overlay_pages.append(new_page)
    _save_pages(overlay_pages)

    # Create revision
    revisions = _load_revisions()
    new_rev_id = max((r["id"] for r in revisions), default=0) + 1
    revisions.append({
        "id": new_rev_id,
        "page_id": new_id,
        "editor_id": editor_id,
        "timestamp": now,
        "summary": f"Created article: {title}",
        "diff_lines_added": content.count("\n") + 1,
        "diff_lines_removed": 0,
    })
    _save_revisions(revisions)

    # Update user edit count
    users = _load_users()
    editor = next((u for u in users if u["id"] == editor_id), None)
    if editor:
        editor["edit_count"] = editor.get("edit_count", 0) + 1
        _save_users(users)

    _recount_categories()
    return jsonify(new_page), 201


@blueprint.route("/api/pages/<slug>/revisions")
def api_page_revisions(slug):
    page = _get_page_by_slug(slug)
    if not page:
        abort(404)
    revisions = _load_revisions()
    page_revisions = [r for r in revisions if r["page_id"] == page["id"]]
    page_revisions.sort(key=lambda r: r["timestamp"], reverse=True)
    return jsonify(page_revisions)


@blueprint.route("/api/categories")
def api_categories():
    categories = _load_categories()
    return jsonify(categories)


@blueprint.route("/api/recent-changes")
def api_recent_changes():
    revisions = _load_revisions()
    revisions_sorted = sorted(revisions, key=lambda r: r["timestamp"], reverse=True)
    limit = request.args.get("limit", type=int)
    if limit:
        revisions_sorted = revisions_sorted[:limit]
    pages = _load_overlay_pages()  # revisions only reference overlay pages
    users = _load_users()
    page_map = {p["id"]: p for p in pages}
    user_map = {u["id"]: u for u in users}
    enriched = []
    for rev in revisions_sorted:
        pg = page_map.get(rev["page_id"])
        editor = user_map.get(rev["editor_id"])
        enriched.append({
            **rev,
            "page_title": pg["title"] if pg else "Unknown",
            "page_slug": pg["slug"] if pg else "",
            "editor_name": editor["display_name"] if editor else "Unknown",
            "editor_username": editor["username"] if editor else "",
        })
    return jsonify(enriched)


@blueprint.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    # Use FTS5 for fast search across 50K articles
    try:
        from app.db import _get_conn, _deserialize_row
        conn = _get_conn()
        terms = q.strip().split()
        fts_query = " ".join(f'"{t}"*' for t in terms if t)
        rows = conn.execute(
            "SELECT a.* FROM wikis_articles a "
            "JOIN fts_wikis_articles fts ON a.row_id = fts.rowid "
            "WHERE fts_wikis_articles MATCH ? ORDER BY fts.rank LIMIT 30",
            (fts_query,)).fetchall()
        results = [_interpret_wiki_article(_deserialize_row(r), r['row_id']) for r in rows]
    except Exception:
        results = []
    # Also search overlay pages
    overlay = db.search(SITE, "pages", q, limit=10)
    seen = {r["title"] for r in results}
    for p in overlay:
        if p["title"] not in seen:
            results.insert(0, p)
    return jsonify(results)


@blueprint.route("/api/semantic-search")
def api_semantic_search():
    """FTS5-powered search with BM25 ranking (replaces Python-side scoring).

    Uses OR logic so articles matching any of the query terms are returned,
    ranked by BM25 relevance score.  Also searches overlay pages.
    """
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    limit = request.args.get("limit", 30, type=int)
    results = []
    try:
        from app.db import _get_conn, _deserialize_row
        conn = _get_conn()
        terms = q.strip().split()
        # Use OR so any matching term contributes — more "semantic"-like
        fts_query = " OR ".join(f'"{t}"*' for t in terms if t)
        rows = conn.execute(
            "SELECT a.* FROM wikis_articles a "
            "JOIN fts_wikis_articles fts ON a.row_id = fts.rowid "
            "WHERE fts_wikis_articles MATCH ? ORDER BY fts.rank LIMIT ?",
            (fts_query, limit)).fetchall()
        results = [_interpret_wiki_article(_deserialize_row(r), r['row_id']) for r in rows]
    except Exception:
        pass
    # Also search overlay pages (Lakeport-specific content) with Python-side scoring
    overlay = _search_pages(_load_overlay_pages(), q)
    seen = {r["title"] for r in results}
    for p in overlay:
        if p["title"] not in seen:
            results.insert(0, p)
            seen.add(p["title"])
    return jsonify(results[:limit])


@blueprint.route("/compare")
def compare_page():
    """Side-by-side comparison of two wiki pages selected via dropdowns."""
    pages = _load_overlay_pages()  # dropdown only shows overlay pages
    categories = _load_categories()
    user = _get_user(session.get("user_id")) if "user_id" in session else None
    slug1 = request.args.get("page1", "").strip()
    slug2 = request.args.get("page2", "").strip()
    page1 = _get_page_by_slug(slug1) if slug1 else None
    page2 = _get_page_by_slug(slug2) if slug2 else None
    return render_template("wikis/compare.html",
                           pages=pages, page1=page1, page2=page2,
                           slug1=slug1, slug2=slug2,
                           categories=categories, user=user)


@blueprint.route("/api/compare")
def api_compare():
    """Compare two pages by slug. Returns a list of two page objects."""
    slugs_param = request.args.get("slugs", "").strip()
    if not slugs_param:
        return jsonify({"error": "Provide ?slugs=slug1,slug2"}), 400
    slugs = [s.strip() for s in slugs_param.split(",") if s.strip()]
    if len(slugs) < 2:
        return jsonify({"error": "Need exactly 2 slugs separated by comma"}), 400
    results = []
    for s in slugs[:2]:
        p = _get_page_by_slug(s)
        if p:
            results.append(p)
    return jsonify(results)


@blueprint.route("/api/verify", methods=["POST"])
def api_verify():
    """Fact-check a claim against wiki page data.

    Accepts JSON: {"slug": "...", "claim": "..."}
    Returns: {"verified": true/false, "evidence": "...", "page_title": "..."}
    """
    data = request.get_json(silent=True) or {}
    slug = data.get("slug", "").strip()
    claim = data.get("claim", "").strip()
    if not slug or not claim:
        return jsonify({"error": "slug and claim required"}), 400

    page = _get_page_by_slug(slug)
    if not page:
        return jsonify({"error": "page not found"}), 404

    # Simple verification: check if claim terms appear in the page content.
    # Filter out common stop-words to focus on meaningful terms.
    stop_words = {"a", "an", "the", "is", "was", "are", "were", "in", "on",
                  "at", "to", "for", "of", "by", "and", "or", "with", "from",
                  "that", "this", "it", "its", "be", "been", "has", "have",
                  "had", "not", "no", "as"}
    content_lower = page["content"].lower()
    raw_terms = claim.lower().split()
    terms = [t for t in raw_terms if t not in stop_words]
    if not terms:
        terms = raw_terms  # fall back to all terms if everything is a stop word
    matched = [t for t in terms if t in content_lower]
    match_ratio = len(matched) / len(terms) if terms else 0

    # Extract the first sentence containing any claim term as evidence
    sentences = page["content"].replace("\n", " ").split(". ")
    evidence = ""
    for sent in sentences:
        if any(t in sent.lower() for t in terms):
            evidence = sent.strip()
            if not evidence.endswith("."):
                evidence += "."
            break

    return jsonify({
        "verified": match_ratio >= 0.5,
        "match_ratio": round(match_ratio, 2),
        "matched_terms": matched,
        "evidence": evidence,
        "page_title": page["title"],
        "page_slug": page["slug"],
    })


@blueprint.route("/api/categories/<int:cat_id>/pages")
def api_category_pages(cat_id):
    """List pages in a category by category ID."""
    categories = _load_categories()
    cat = next((c for c in categories if c["id"] == cat_id), None)
    if not cat:
        abort(404)
    if cat["name"] == "Wikipedia":
        cat_pages = _load_raw_wiki(limit=50)
    else:
        cat_pages = db.query(SITE, "pages", where={"category": cat["name"]})
    cat_pages.sort(key=lambda p: p["title"])
    return jsonify(cat_pages)


@blueprint.route("/api/stats")
def api_stats():
    overlay_pages = _load_overlay_pages()
    raw_count = _raw_wiki_count()
    revisions = _load_revisions()
    categories = _load_categories()
    users = _load_users()
    # Use overlay pages for view-based stats (raw pages have views=0)
    overlay_views = sum(p["views"] for p in overlay_pages)
    total_views = overlay_views
    total_pages = len(overlay_pages) + raw_count
    # Compute most-edited page
    edit_counts = Counter(r["page_id"] for r in revisions)
    most_edited_id = edit_counts.most_common(1)[0][0] if edit_counts else None
    most_edited_page = None
    if most_edited_id:
        me = next((p for p in overlay_pages if p["id"] == most_edited_id), None)
        if me:
            most_edited_page = me["title"]
    return jsonify({
        "total_pages": total_pages,
        "total_revisions": len(revisions),
        "total_categories": len(categories),
        "total_users": len(users),
        "total_views": total_views,
        "most_viewed": sorted(overlay_pages, key=lambda p: -p["views"])[0]["title"] if overlay_pages else None,
        "most_edited_page": most_edited_page,
        "latest_revision": max(revisions, key=lambda r: r["timestamp"])["timestamp"] if revisions else None,
    })


@blueprint.route("/api/contributors")
def api_contributors():
    """Return contributor list with edit counts (no passwords)."""
    users = _load_users()
    contributors = []
    for u in sorted(users, key=lambda x: -x.get("edit_count", 0)):
        contributors.append({
            "id": u["id"],
            "username": u["username"],
            "display_name": u["display_name"],
            "role": u.get("role", "editor"),
            "edit_count": u.get("edit_count", 0),
            "joined": u.get("joined", ""),
        })
    return jsonify(contributors)


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
