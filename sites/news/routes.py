"""Lakeport Tribune -- local news site (newspaper / news portal style).

Data is stored in per-site SQLite tables (news_articles, news_users, etc.)
and queried through app.db.  Session mutations are isolated per user.

Supports all 20 target macros:
  navigate_by_dropdown, navigate_by_route, search_by_query, search_by_semantic,
  filter_by_dropdown, filter_by_date_range, sort_by_dropdown,
  extract_by_query, extract_by_semantic, extract_by_dropdown, extract_by_route,
  play_by_playback, post_from_free_text, follow_by_dropdown,
  subscribe_by_toggle, share_by_dropdown, save_by_toggle,
  report_by_form, authenticate_by_form, register_by_form
"""
import json
import pathlib
import re
from datetime import datetime

from flask import (
    Blueprint, Response, abort, jsonify, redirect, render_template, request,
    session, url_for,
)
from app import db
from app.events import emit

SITE = "news"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "news",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data helpers — all data lives in SQLite via db.query() / db.save_collection()
# ---------------------------------------------------------------------------

def _load_articles(**kwargs):
    articles = db.query(SITE, "articles", limit=kwargs.pop("limit", 50), **kwargs)
    # Deserialize tags if stored as JSON string
    for a in articles:
        if isinstance(a.get("tags"), str):
            try:
                a["tags"] = json.loads(a["tags"])
            except (json.JSONDecodeError, TypeError):
                a["tags"] = []
    return articles


def _load_categories():
    return db.query(SITE, "categories")


def _load_bookmarks():
    return db.query(SITE, "bookmarks")


def _load_users():
    users = db.query(SITE, "users")
    for u in users:
        for field in ("newsletter_preferences", "notification_settings"):
            if isinstance(u.get(field), str):
                try:
                    u[field] = json.loads(u[field])
                except (json.JSONDecodeError, TypeError):
                    pass
    return users


def _load_comments():
    return db.query(SITE, "comments")


def _load_follows():
    return db.query(SITE, "follows")


def _load_shares():
    return db.query(SITE, "shares")


def _load_reports():
    return db.query(SITE, "reports")


def _get_user(user_id):
    users = _load_users()
    return next((u for u in users if u["id"] == user_id), None)


def _current_user():
    if "user_id" in session:
        return _get_user(session["user_id"])
    return None


def _semantic_score(article, query):
    """Simple keyword-overlap 'semantic' scoring (bag-of-words similarity)."""
    q_words = set(query.lower().split())
    text = (article["title"] + " " + article.get("body", "") + " " +
            " ".join(article.get("tags", []))).lower()
    text_words = set(text.split())
    overlap = q_words & text_words
    if not overlap:
        return 0
    return len(overlap) / len(q_words)


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

# House ads promote real MiniWeb sites and link to them (/sites/<id>/).
_AD_POOL = [
    {"site": "e-commerce", "brand": "ShopWave", "domain": "shopwave.com",
     "tagline": "Fall sale is on — up to 40% off home, tech & more. Free 2-day shipping."},
    {"site": "video", "brand": "StreamHub", "domain": "streamtube.tv",
     "tagline": "Stream thousands of shows and creators. Start watching free today."},
    {"site": "brokerage", "brand": "TradePulse", "domain": "tradepulse.com",
     "tagline": "Commission-free trading. Open an account and get your first stock on us."},
    {"site": "job-sites", "brand": "JobScout", "domain": "jobscout.careers",
     "tagline": "500+ new local jobs this week in Cascadia County. Find your next role."},
    {"site": "ticketing-events", "brand": "EventPass", "domain": "eventpass.live",
     "tagline": "Concerts, games & festivals near Lakeport. Get tickets before they sell out."},
    {"site": "auctions-p2p-marketplaces", "brand": "BidMarket", "domain": "bidmarket.com",
     "tagline": "Buy and sell locally — thousands of deals from your neighbors."},
    {"site": "insurance-loans", "brand": "Cascadia Insurance & Lending", "domain": "cascadiainsure.com",
     "tagline": "Home, auto & life coverage from a local team. Get a quote in under 5 minutes."},
    {"site": "music", "brand": "SoundWave", "domain": "soundwave.fm",
     "tagline": "Millions of songs, zero ads on Premium. Your first month is free."},
    {"site": "weather", "brand": "Lakeport Weather", "domain": "lakeportweather.com",
     "tagline": "Hyperlocal forecasts and severe-weather alerts for Cascadia County."},
]


@blueprint.route("/")
def index():
    import random
    categories = _load_categories()
    user = _current_user()
    ads = random.sample(_AD_POOL, 2)  # [0] leaderboard, [1] sidebar

    sort_by = request.args.get("sort", "date")

    sort_map = {"popularity": "-comments_count", "title": "title"}
    sql_sort = sort_map.get(sort_by, "-date")
    sorted_articles = _load_articles(sort=sql_sort, limit=50)

    # Featured: top 3 most-commented recent articles
    featured = _load_articles(sort="-comments_count", limit=3)

    # Latest: most recent 10
    latest = _load_articles(sort="-date", limit=10)

    # Group by category for section display
    cat_articles = {}
    for cat in categories:
        cat_slug = cat["slug"]
        cat_articles[cat_slug] = [a for a in sorted_articles if a["category"] == cat_slug][:4]

    # Bookmarked article IDs for current user
    bookmarked_ids = set()
    if user:
        bookmarks = _load_bookmarks()
        bookmarked_ids = {b["article_id"] for b in bookmarks if b["user_id"] == user["id"]}

    return render_template("news/index.html",
                           articles=sorted_articles, featured=featured,
                           latest=latest, categories=categories,
                           cat_articles=cat_articles, user=user,
                           sort=sort_by, ads=ads,
                           bookmarked_ids=bookmarked_ids)


@blueprint.route("/article/<int:article_id>")
def article_detail(article_id):
    article = db.get_item(SITE, "articles", article_id)
    if article is None:
        abort(404)
    if isinstance(article.get("tags"), str):
        try:
            article["tags"] = json.loads(article["tags"])
        except (json.JSONDecodeError, TypeError):
            article["tags"] = []

    categories = _load_categories()
    user = _current_user()

    # Related articles: same category, excluding current
    related = _load_articles(where={"category": article["category"]}, sort="-date", limit=5)
    related = [a for a in related if a["id"] != article_id][:4]

    # Check if bookmarked
    is_bookmarked = False
    bookmark_note = None
    if user:
        bookmarks = _load_bookmarks()
        bm = next((b for b in bookmarks if b["user_id"] == user["id"] and b["article_id"] == article_id), None)
        if bm:
            is_bookmarked = True
            bookmark_note = bm.get("note")

    # Load comments for this article
    comments = _load_comments()
    article_comments = [c for c in comments if c["article_id"] == article_id]
    article_comments.sort(key=lambda c: c.get("posted_at", ""), reverse=True)

    return render_template("news/article.html",
                           article=article, categories=categories,
                           related=related, user=user,
                           is_bookmarked=is_bookmarked, bookmark_note=bookmark_note,
                           comments=article_comments)


@blueprint.route("/category/<slug>")
def category_page(slug):
    categories = _load_categories()
    user = _current_user()

    category = next((c for c in categories if c["slug"] == slug), None)
    if category is None:
        abort(404)

    sort_by = request.args.get("sort", "date")
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    sort_map = {"popularity": "-comments_count", "title": "title"}
    sql_sort = sort_map.get(sort_by, "-date")
    filtered = _load_articles(where={"category": slug}, sort=sql_sort, limit=50)
    # Date range filter on the already-limited result set (same as api_articles)
    if date_from:
        filtered = [a for a in filtered if a.get("date", "") >= date_from]
    if date_to:
        filtered = [a for a in filtered if a.get("date", "") <= date_to]

    bookmarked_ids = set()
    if user:
        bookmarks = _load_bookmarks()
        bookmarked_ids = {b["article_id"] for b in bookmarks if b["user_id"] == user["id"]}

    return render_template("news/category.html",
                           category=category, articles=filtered,
                           categories=categories, user=user,
                           sort=sort_by, bookmarked_ids=bookmarked_ids,
                           date_from=date_from, date_to=date_to)


@blueprint.route("/search")
def search_page():
    categories = _load_categories()
    user = _current_user()

    q = request.args.get("q", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    results = []
    if q:
        rows = db.search(SITE, "articles", q, limit=50)
        for a in rows:
            if isinstance(a.get("tags"), str):
                try:
                    a["tags"] = json.loads(a["tags"])
                except (json.JSONDecodeError, TypeError):
                    a["tags"] = []
        # Date range filter on the already-limited result set (same as api_articles)
        if date_from:
            rows = [a for a in rows if a.get("date", "") >= date_from]
        if date_to:
            rows = [a for a in rows if a.get("date", "") <= date_to]
        results = rows

    bookmarked_ids = set()
    if user:
        bookmarks = _load_bookmarks()
        bookmarked_ids = {b["article_id"] for b in bookmarks if b["user_id"] == user["id"]}

    return render_template("news/search.html",
                           q=q, results=results, categories=categories,
                           user=user, bookmarked_ids=bookmarked_ids,
                           date_from=date_from, date_to=date_to)


@blueprint.route("/bookmarks")
def bookmarks_page():
    user = _current_user()
    categories = _load_categories()
    if not user:
        return redirect(url_for("news.login_page"))

    bookmarks = db.query(SITE, "bookmarks", where={"user_id": user["id"]})
    user_bookmarks = bookmarks
    user_bookmarks.sort(key=lambda b: b.get("bookmarked_at", ""), reverse=True)

    # Attach full article data to each bookmark
    for bm in user_bookmarks:
        bm["article"] = db.get_item(SITE, "articles", bm["article_id"])

    return render_template("news/bookmarks.html",
                           bookmarks=user_bookmarks, categories=categories,
                           user=user)


# ---------------------------------------------------------------------------
# authenticate_by_form
# ---------------------------------------------------------------------------

@blueprint.route("/login", methods=["GET"])
def login_page():
    categories = _load_categories()
    return render_template("news/login.html", error=None, categories=categories)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    categories = _load_categories()
    user = next((u for u in users if u["username"] == username), None)
    if not user:
        return render_template("news/login.html",
                               error="Invalid username or password",
                               categories=categories)
    # Accept any valid username with password "password" (demo site)
    if password != "password":
        return render_template("news/login.html",
                               error="Invalid username or password",
                               categories=categories)
    session["user_id"] = user["id"]
    emit("signup", user_id=user["id"], site_name="news", username=request.form.get("username", ""), password=request.form.get("password", ""), email="")
    next_url = request.args.get("next") or request.form.get("next") or url_for("news.index")
    return redirect(next_url)


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("news.index"))


# ---------------------------------------------------------------------------
# register_by_form
# ---------------------------------------------------------------------------

@blueprint.route("/register", methods=["GET"])
def register_page():
    categories = _load_categories()
    return render_template("news/register.html", error=None, categories=categories)


@blueprint.route("/register", methods=["POST"])
def register_submit():
    username = request.form.get("username", "").strip()
    display_name = request.form.get("display_name", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()
    categories = _load_categories()

    if not username or not email or not password:
        return render_template("news/register.html",
                               error="All fields are required.",
                               categories=categories)

    users = _load_users()
    if any(u["username"] == username for u in users):
        return render_template("news/register.html",
                               error="Username already taken.",
                               categories=categories)

    new_id = max((u["id"] for u in users), default=0) + 1
    new_user = {
        "id": new_id,
        "root_user_id": new_id,
        "username": username,
        "display_name": display_name or username,
        "email": email,
        "subscription_tier": "free",
        "subscribed_since": datetime.utcnow().strftime("%Y-%m-%d"),
        "newsletter_preferences": {
            "daily_digest": request.form.get("newsletter_daily_digest") == "on",
            "breaking_news": request.form.get("newsletter_breaking_news") == "on",
            "weekly_roundup": request.form.get("newsletter_weekly_roundup") == "on",
            "categories": []
        },
        "notification_settings": {
            "push_enabled": False,
            "email_alerts": False
        },
        "reading_history_count": 0,
        "bookmarks_count": 0,
        "comments_count": 0
    }
    users.append(new_user)
    db.save_collection(SITE, "users", users)
    session["user_id"] = new_id
    return redirect(url_for("news.index"))


# ---------------------------------------------------------------------------
# report_by_form
# ---------------------------------------------------------------------------

@blueprint.route("/article/<int:article_id>/report", methods=["GET"])
def report_page(article_id):
    articles = _load_articles()
    article = next((a for a in articles if a["id"] == article_id), None)
    if article is None:
        abort(404)
    categories = _load_categories()
    user = _current_user()
    return render_template("news/report.html",
                           article=article, categories=categories, user=user,
                           success=False)


@blueprint.route("/article/<int:article_id>/report", methods=["POST"])
def report_submit(article_id):
    articles = _load_articles()
    article = next((a for a in articles if a["id"] == article_id), None)
    if article is None:
        abort(404)

    reason = request.form.get("reason", "").strip()
    details = request.form.get("details", "").strip()

    reports = _load_reports()
    new_id = max((r["id"] for r in reports), default=0) + 1
    user = _current_user()
    reports.append({
        "id": new_id,
        "article_id": article_id,
        "article_title": article["title"],
        "user_id": user["id"] if user else None,
        "reason": reason,
        "details": details,
        "submitted_at": datetime.utcnow().isoformat() + "Z",
        "status": "pending"
    })
    db.save_collection(SITE, "reports", reports)

    categories = _load_categories()
    return render_template("news/report.html",
                           article=article, categories=categories, user=user,
                           success=True)


# ---------------------------------------------------------------------------
# API routes -- read
# ---------------------------------------------------------------------------

@blueprint.route("/api/articles")
def api_articles():
    category = request.args.get("category")
    author = request.args.get("author")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    search = request.args.get("q") or request.args.get("search")
    sort_by = request.args.get("sort", "date")

    where_f = {}
    if category:
        where_f["category"] = category
    if author:
        where_f["author"] = author

    sort_map = {"popularity": "-comments_count", "title": "title", "word_count": "-word_count"}
    sql_sort = sort_map.get(sort_by, "-date")

    if search:
        search_where = dict(where_f) if where_f else {}
        articles = db.search(SITE, "articles", search, where=search_where or None, limit=100)
        # Apply date range filters on the (already limited) result set
        if date_from:
            articles = [a for a in articles if a.get("date", "") >= date_from]
        if date_to:
            articles = [a for a in articles if a.get("date", "") <= date_to]
        for a in articles:
            if isinstance(a.get("tags"), str):
                try:
                    a["tags"] = json.loads(a["tags"])
                except (json.JSONDecodeError, TypeError):
                    a["tags"] = []
    else:
        articles = _load_articles(where=where_f if where_f else None, sort=sql_sort, limit=100)
        if date_from:
            articles = [a for a in articles if a["date"] >= date_from]
        if date_to:
            articles = [a for a in articles if a["date"] <= date_to]

    return jsonify(articles)


@blueprint.route("/api/articles/<int:article_id>")
def api_article(article_id):
    article = db.get_item(SITE, "articles", article_id)
    if article is None:
        return jsonify({"error": "Article not found"}), 404
    if isinstance(article.get("tags"), str):
        try:
            article["tags"] = json.loads(article["tags"])
        except (json.JSONDecodeError, TypeError):
            article["tags"] = []
    return jsonify(article)


# ---------------------------------------------------------------------------
# search_by_semantic / extract_by_semantic
# ---------------------------------------------------------------------------

@blueprint.route("/api/articles/semantic")
def api_semantic_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    rows = db.search(SITE, "articles", q, limit=100)
    for a in rows:
        if isinstance(a.get("tags"), str):
            try:
                a["tags"] = json.loads(a["tags"])
            except (json.JSONDecodeError, TypeError):
                a["tags"] = []
    scored = []
    for a in rows:
        s = _semantic_score(a, q)
        if s > 0:
            scored.append({"score": round(s, 4), "article": a})
    scored.sort(key=lambda x: -x["score"])
    return jsonify(scored)


# ---------------------------------------------------------------------------
# extract_by_dropdown -- category stats
# ---------------------------------------------------------------------------

@blueprint.route("/api/categories/<slug>/stats")
def api_category_stats(slug):
    categories = _load_categories()
    cat = next((c for c in categories if c["slug"] == slug), None)
    if cat is None:
        return jsonify({"error": "Category not found"}), 404

    cat_articles = _load_articles(where={"category": slug})
    authors = list(set(a["author"] for a in cat_articles))
    dates = [a["date"] for a in cat_articles if a.get("date")]

    return jsonify({
        "category": slug,
        "name": cat["name"],
        "count": len(cat_articles),
        "unique_authors": len(authors),
        "authors": authors,
        "total_comments": sum(a.get("comments_count") or 0 for a in cat_articles),
        "avg_word_count": round(sum(a.get("word_count") or 0 for a in cat_articles) / len(cat_articles)) if cat_articles else 0,
        "date_range": {
            "earliest": min(dates) if dates else None,
            "latest": max(dates) if dates else None,
        }
    })


# ---------------------------------------------------------------------------
# save_by_toggle (bookmark)
# ---------------------------------------------------------------------------

@blueprint.route("/api/articles/<int:article_id>/bookmark", methods=["POST"])
def api_toggle_bookmark(article_id):
    user = _current_user()
    if not user:
        return jsonify({"error": "Login required"}), 401

    articles = _load_articles()
    article = next((a for a in articles if a["id"] == article_id), None)
    if article is None:
        return jsonify({"error": "Article not found"}), 404

    bookmarks = _load_bookmarks()
    existing = next((b for b in bookmarks if b["user_id"] == user["id"] and b["article_id"] == article_id), None)

    if existing:
        bookmarks = [b for b in bookmarks if not (b["user_id"] == user["id"] and b["article_id"] == article_id)]
        db.save_collection(SITE, "bookmarks", bookmarks)
        return jsonify({"bookmarked": False, "article_id": article_id, "action": "unsaved"})
    else:
        data = request.get_json(silent=True) or {}
        new_id = max((b["id"] for b in bookmarks), default=0) + 1
        new_bookmark = {
            "id": new_id,
            "user_id": user["id"],
            "root_user_id": user.get("root_user_id", user["id"]),
            "article_id": article_id,
            "article_title": article["title"],
            "bookmarked_at": datetime.utcnow().isoformat() + "Z",
            "note": data.get("note")
        }
        bookmarks.append(new_bookmark)
        db.save_collection(SITE, "bookmarks", bookmarks)
        return jsonify({"bookmarked": True, "article_id": article_id,
                        "bookmark": new_bookmark, "action": "saved"})


@blueprint.route("/api/categories")
def api_categories():
    categories = _load_categories()
    return jsonify(categories)


@blueprint.route("/api/bookmarks")
def api_bookmarks():
    user = _current_user()
    if not user:
        return jsonify({"error": "Login required"}), 401

    user_bookmarks = db.query(SITE, "bookmarks", where={"user_id": user["id"]}, sort="-bookmarked_at")
    return jsonify(user_bookmarks)


@blueprint.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    rows = db.search(SITE, "articles", q, limit=50)
    results = []
    for a in rows:
        if isinstance(a.get("tags"), str):
            try:
                a["tags"] = json.loads(a["tags"])
            except (json.JSONDecodeError, TypeError):
                a["tags"] = []
        results.append({"score": 1, "article": a})

    return jsonify(results)


@blueprint.route("/api/stats")
def api_stats():
    articles = _load_articles(limit=5000)  # cap for aggregation
    categories = _load_categories()
    total_bookmarks = db.count(SITE, "bookmarks")
    total_users = db.count(SITE, "users")

    author_counts = {}
    for a in articles:
        author_counts[a["author"]] = author_counts.get(a["author"], 0) + 1

    cat_counts = {}
    for a in articles:
        cat_counts[a["category"]] = cat_counts.get(a["category"], 0) + 1

    dates = [a["date"] for a in articles if a.get("date")]

    return jsonify({
        "total_articles": len(articles),
        "total_categories": len(categories),
        "total_bookmarks": total_bookmarks,
        "total_users": total_users,
        "articles_by_author": author_counts,
        "articles_by_category": cat_counts,
        "date_range": {
            "earliest": min(dates) if dates else None,
            "latest": max(dates) if dates else None,
        },
        "total_comments": sum(a.get("comments_count") or 0 for a in articles),
        "avg_word_count": round(sum(a.get("word_count") or 0 for a in articles) / len(articles)) if articles else 0,
    })


# ---------------------------------------------------------------------------
# post_from_free_text (comment)
# ---------------------------------------------------------------------------

@blueprint.route("/api/articles/<int:article_id>/comment", methods=["POST"])
def api_post_comment(article_id):
    user = _current_user()
    if not user:
        return jsonify({"error": "Login required"}), 401

    articles = _load_articles()
    article = next((a for a in articles if a["id"] == article_id), None)
    if article is None:
        return jsonify({"error": "Article not found"}), 404

    data = request.get_json(silent=True) or {}
    body = data.get("body", "").strip()
    if not body:
        return jsonify({"error": "Comment body is required"}), 400

    comments = _load_comments()
    new_id = max((c["id"] for c in comments), default=0) + 1
    comment = {
        "id": new_id,
        "article_id": article_id,
        "user_id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
        "body": body,
        "posted_at": datetime.utcnow().isoformat() + "Z"
    }
    comments.append(comment)
    db.save_collection(SITE, "comments", comments)
    return jsonify({"action": "posted", "comment": comment}), 201


@blueprint.route("/article/<int:article_id>/comment", methods=["POST"])
def form_post_comment(article_id):
    user = _current_user()
    if not user:
        return redirect(url_for("news.login_page"))

    articles = _load_articles()
    article = next((a for a in articles if a["id"] == article_id), None)
    if article is None:
        abort(404)

    body = request.form.get("body", "").strip()
    if body:
        comments = _load_comments()
        new_id = max((c["id"] for c in comments), default=0) + 1
        comments.append({
            "id": new_id,
            "article_id": article_id,
            "user_id": user["id"],
            "username": user["username"],
            "display_name": user["display_name"],
            "body": body,
            "posted_at": datetime.utcnow().isoformat() + "Z"
        })
        db.save_collection(SITE, "comments", comments)

    return redirect(url_for("news.article_detail", article_id=article_id))


@blueprint.route("/api/articles/<int:article_id>/comments")
def api_article_comments(article_id):
    article_comments = db.query(SITE, "comments", where={"article_id": article_id}, sort="-posted_at")
    return jsonify(article_comments)


# ---------------------------------------------------------------------------
# follow_by_dropdown (follow category or author)
# ---------------------------------------------------------------------------

@blueprint.route("/api/follow", methods=["POST"])
def api_follow():
    user = _current_user()
    if not user:
        return jsonify({"error": "Login required"}), 401

    data = request.get_json(silent=True) or {}
    follow_type = data.get("type", "")  # "category" or "author"
    target = data.get("target", "").strip()

    if not follow_type or not target:
        return jsonify({"error": "type and target required"}), 400

    follows = _load_follows()
    existing = next((f for f in follows
                     if f["user_id"] == user["id"]
                     and f["type"] == follow_type
                     and f["target"] == target), None)

    if existing:
        follows = [f for f in follows if f["id"] != existing["id"]]
        db.save_collection(SITE, "follows", follows)
        return jsonify({"action": "unfollowed", "type": follow_type, "target": target})
    else:
        new_id = max((f["id"] for f in follows), default=0) + 1
        follows.append({
            "id": new_id,
            "user_id": user["id"],
            "type": follow_type,
            "target": target,
            "followed_at": datetime.utcnow().isoformat() + "Z"
        })
        db.save_collection(SITE, "follows", follows)
        return jsonify({"action": "followed", "type": follow_type, "target": target})


@blueprint.route("/api/follows")
def api_follows():
    user = _current_user()
    if not user:
        return jsonify({"error": "Login required"}), 401

    follows = _load_follows()
    user_follows = [f for f in follows if f["user_id"] == user["id"]]
    return jsonify(user_follows)


# ---------------------------------------------------------------------------
# subscribe_by_toggle (newsletter subscription)
# ---------------------------------------------------------------------------

@blueprint.route("/api/subscribe", methods=["POST"])
def api_subscribe_toggle():
    user = _current_user()
    if not user:
        return jsonify({"error": "Login required"}), 401

    data = request.get_json(silent=True) or {}
    newsletter = data.get("newsletter", "")  # daily_digest, breaking_news, weekly_roundup

    if newsletter not in ("daily_digest", "breaking_news", "weekly_roundup"):
        return jsonify({"error": "Invalid newsletter type. Choose: daily_digest, breaking_news, weekly_roundup"}), 400

    users = _load_users()
    u = next((u for u in users if u["id"] == user["id"]), None)
    if not u:
        return jsonify({"error": "User not found"}), 404

    current = u.get("newsletter_preferences", {}).get(newsletter, False)
    u["newsletter_preferences"][newsletter] = not current
    db.save_collection(SITE, "users", users)

    return jsonify({
        "action": "subscribed" if not current else "unsubscribed",
        "newsletter": newsletter,
        "enabled": not current
    })


@blueprint.route("/api/user/profile")
def api_user_profile():
    user = _current_user()
    if not user:
        return jsonify({"error": "Login required"}), 401
    return jsonify(user)


# ---------------------------------------------------------------------------
# share_by_dropdown
# ---------------------------------------------------------------------------

@blueprint.route("/api/articles/<int:article_id>/share", methods=["POST"])
def api_share_article(article_id):
    articles = _load_articles()
    article = next((a for a in articles if a["id"] == article_id), None)
    if article is None:
        return jsonify({"error": "Article not found"}), 404

    data = request.get_json(silent=True) or {}
    platform = data.get("platform", "").strip()  # email, twitter, facebook, linkedin, copy_link

    if platform not in ("email", "twitter", "facebook", "linkedin", "copy_link"):
        return jsonify({"error": "Invalid platform. Choose: email, twitter, facebook, linkedin, copy_link"}), 400

    user = _current_user()
    shares = _load_shares()
    new_id = max((s["id"] for s in shares), default=0) + 1
    share = {
        "id": new_id,
        "article_id": article_id,
        "article_title": article["title"],
        "user_id": user["id"] if user else None,
        "platform": platform,
        "shared_at": datetime.utcnow().isoformat() + "Z"
    }
    shares.append(share)
    db.save_collection(SITE, "shares", shares)

    return jsonify({"action": "shared", "share": share})


# ---------------------------------------------------------------------------
# report_by_form (API)
# ---------------------------------------------------------------------------

@blueprint.route("/api/articles/<int:article_id>/report", methods=["POST"])
def api_report_article(article_id):
    articles = _load_articles()
    article = next((a for a in articles if a["id"] == article_id), None)
    if article is None:
        return jsonify({"error": "Article not found"}), 404

    data = request.get_json(silent=True) or {}
    reason = data.get("reason", "").strip()
    details = data.get("details", "").strip()

    if not reason:
        return jsonify({"error": "Reason is required"}), 400

    reports = _load_reports()
    new_id = max((r["id"] for r in reports), default=0) + 1
    user = _current_user()
    report = {
        "id": new_id,
        "article_id": article_id,
        "article_title": article["title"],
        "user_id": user["id"] if user else None,
        "reason": reason,
        "details": details,
        "submitted_at": datetime.utcnow().isoformat() + "Z",
        "status": "pending"
    }
    reports.append(report)
    db.save_collection(SITE, "reports", reports)
    return jsonify({"action": "reported", "report": report}), 201


# ---------------------------------------------------------------------------
# play_by_playback (audio version -- placeholder)
# ---------------------------------------------------------------------------

@blueprint.route("/api/articles/<int:article_id>/play", methods=["POST"])
def api_play_article(article_id):
    """Start audio playback for an article (placeholder -- returns metadata)."""
    articles = _load_articles()
    article = next((a for a in articles if a["id"] == article_id), None)
    if article is None:
        return jsonify({"error": "Article not found"}), 404

    # Estimate reading duration at ~150 words/min for audio
    wc = article.get("word_count", 0)
    duration_seconds = int((wc / 150) * 60)

    return jsonify({
        "action": "playing",
        "article_id": article_id,
        "title": article["title"],
        "duration_seconds": duration_seconds,
        "audio_url": f"/news/audio/{article_id}.mp3"
    })


# ---------------------------------------------------------------------------
# authenticate_by_form (API)
# ---------------------------------------------------------------------------

@blueprint.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or password != "password":
        return jsonify({"error": "Invalid credentials"}), 401

    session["user_id"] = user["id"]
    return jsonify({"user_id": user["id"], "username": user["username"],
                    "display_name": user["display_name"]})


# ---------------------------------------------------------------------------
# register_by_form (API)
# ---------------------------------------------------------------------------

@blueprint.route("/api/register", methods=["POST"])
def api_register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    display_name = data.get("display_name", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "").strip()

    if not username or not email or not password:
        return jsonify({"error": "username, email, and password are required"}), 400

    users = _load_users()
    if any(u["username"] == username for u in users):
        return jsonify({"error": "Username already taken"}), 409

    new_id = max((u["id"] for u in users), default=0) + 1
    new_user = {
        "id": new_id,
        "root_user_id": new_id,
        "username": username,
        "display_name": display_name or username,
        "email": email,
        "subscription_tier": "free",
        "subscribed_since": datetime.utcnow().strftime("%Y-%m-%d"),
        "newsletter_preferences": {
            "daily_digest": False,
            "breaking_news": False,
            "weekly_roundup": False,
            "categories": []
        },
        "notification_settings": {
            "push_enabled": False,
            "email_alerts": False
        },
        "reading_history_count": 0,
        "bookmarks_count": 0,
        "comments_count": 0
    }
    users.append(new_user)
    db.save_collection(SITE, "users", users)
    session["user_id"] = new_id
    return jsonify({"action": "registered", "user_id": new_id, "username": username}), 201


# ---------------------------------------------------------------------------
# Form-based bookmark toggle (HTML POST)
# ---------------------------------------------------------------------------

@blueprint.route("/article/<int:article_id>/bookmark", methods=["POST"])
def form_toggle_bookmark(article_id):
    user = _current_user()
    if not user:
        return redirect(url_for("news.login_page"))

    articles = _load_articles()
    article = next((a for a in articles if a["id"] == article_id), None)
    if article is None:
        abort(404)

    bookmarks = _load_bookmarks()
    existing = next((b for b in bookmarks if b["user_id"] == user["id"] and b["article_id"] == article_id), None)

    if existing:
        bookmarks = [b for b in bookmarks if not (b["user_id"] == user["id"] and b["article_id"] == article_id)]
    else:
        new_id = max((b["id"] for b in bookmarks), default=0) + 1
        note = request.form.get("note", "").strip() or None
        bookmarks.append({
            "id": new_id,
            "user_id": user["id"],
            "root_user_id": user.get("root_user_id", user["id"]),
            "article_id": article_id,
            "article_title": article["title"],
            "bookmarked_at": datetime.utcnow().isoformat() + "Z",
            "note": note,
        })

    db.save_collection(SITE, "bookmarks", bookmarks)

    next_url = request.form.get("next") or url_for("news.article_detail", article_id=article_id)
    return redirect(next_url)
