"""TumblrVibe Blogging Platform — Tumblr-style blog with posts, comments, users.

Data is synthesized deterministically from config/config.json (num_data_points, random_seed).
Mutable state (users, comments, reports) lives in data/*.json with .pristine/ backup.
"""
import pathlib
from datetime import datetime

from flask import Blueprint, abort, jsonify, redirect, render_template, request, session, url_for
from app import db
from app.events import emit
from app.handlers.email_handler import _add_email

SITE = "blogs"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "blogs",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

_CATEGORIES = ["Technology", "Travel", "Food", "Art", "Books", "Fitness", "Music", "Lifestyle", "Photography", "Gaming"]

# ---------------------------------------------------------------------------
# Data access helpers
# ---------------------------------------------------------------------------


def _load_posts(category=None, author=None, limit=None, sort="-date"):
    where = {}
    if category:
        where["category"] = category
    if author:
        where["author_username"] = author
    return db.query(SITE, "posts", where=where if where else None, sort=sort, limit=limit)


def _load_users():
    return db.query(SITE, "users")


def _save_users(users):
    db.save_collection(SITE, "users", users)


def _load_comments(post_id=None):
    where = {"post_id": post_id} if post_id is not None else None
    return db.query(SITE, "comments", where=where)


def _save_comments(comments):
    db.save_collection(SITE, "comments", comments)


def _load_reports():
    return db.query(SITE, "reports")


def _save_reports(reports):
    db.save_collection(SITE, "reports", reports)


def _get_user(user_id):
    return db.get_item(SITE, "users", user_id)


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    q = request.args.get("q", "").strip()
    cat = request.args.get("category", "").strip()
    tag = request.args.get("tag", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    sort_param = request.args.get("sort", "date").strip()
    author = request.args.get("author", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = 30
    offset = (page - 1) * per_page

    # Get categories for sidebar (small result set from DISTINCT query)
    cat_rows = db.execute("SELECT DISTINCT [category] FROM [blogs_posts] ORDER BY [category]", ())
    categories = [r["category"] for r in cat_rows]

    # Build WHERE filters for SQL
    where = {}
    if cat:
        where["category"] = cat
    if author:
        where["author_username"] = author

    # Map sort param to db sort string
    sort_map = {"date": "-date", "oldest": "date", "popular": "-notes_count"}
    db_sort = sort_map.get(sort_param, "-date")

    if q:
        # Use FTS5-based search (falls back to LIKE automatically)
        results = db.search(SITE, "posts", q, where=where, limit=per_page + 1, offset=offset)
    else:
        results = db.query(SITE, "posts", where=where if where else None,
                           sort=db_sort, limit=per_page + 1, offset=offset)

    # Apply filters that need raw SQL (date range, tag) — these are on already-limited sets
    # For date range and tag, use db.execute for proper SQL filtering
    if date_from or date_to or tag:
        # Need to re-query with full SQL for complex filters
        clauses = []
        params = []

        if q:
            # For text search with additional filters, use LIKE fallback
            like_param = f"%{q}%"
            clauses.append("([title] LIKE ? OR [body] LIKE ? OR [author_username] LIKE ?)")
            params.extend([like_param, like_param, like_param])

        if cat:
            clauses.append("[category] = ?")
            params.append(cat)
        if author:
            clauses.append("[author_username] = ?")
            params.append(author)
        if date_from:
            clauses.append("[date] >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("[date] <= ?")
            params.append(date_to)
        if tag:
            clauses.append("[tags] LIKE ?")
            params.append(f"%{tag}%")

        where_sql = " AND ".join(clauses) if clauses else "1=1"

        # Sort
        order_sql = {
            "date": "[date] DESC",
            "oldest": "[date] ASC",
            "popular": "[notes_count] DESC",
        }.get(sort_param, "[date] DESC")

        sql = f"SELECT * FROM [blogs_posts] WHERE {where_sql} ORDER BY {order_sql} LIMIT ? OFFSET ?"
        params.extend([per_page + 1, offset])
        results = db.execute(sql, tuple(params))

    # db.search() and the raw-SQL path read the base table only — merge in
    # this session's posts so newly created entries appear in filtered views.
    # (The default db.query() path above is already overlay-aware.)
    if q or date_from or date_to or tag:
        def _overlay_match(p):
            if q:
                text = " ".join(str(p.get(f, ""))
                                for f in ("title", "body", "author_username")).lower()
                if not all(t in text for t in q.lower().split()):
                    return False
            if cat and p.get("category") != cat:
                return False
            if author and p.get("author_username") != author:
                return False
            if date_from and (p.get("date") or "") < date_from:
                return False
            if date_to and (p.get("date") or "") > date_to:
                return False
            if tag and tag not in str(p.get("tags", "")):
                return False
            return True

        results = db.merge_overlay(SITE, "posts", results, match=_overlay_match,
                                   sort=db_sort, limit=per_page + 1)

    # Count total for pagination
    if q and not (date_from or date_to or tag):
        total_count = db.count(SITE, "posts", where=where if where else None)
    elif date_from or date_to or tag:
        count_clauses = []
        count_params = []
        if q:
            like_param = f"%{q}%"
            count_clauses.append("([title] LIKE ? OR [body] LIKE ? OR [author_username] LIKE ?)")
            count_params.extend([like_param, like_param, like_param])
        if cat:
            count_clauses.append("[category] = ?")
            count_params.append(cat)
        if author:
            count_clauses.append("[author_username] = ?")
            count_params.append(author)
        if date_from:
            count_clauses.append("[date] >= ?")
            count_params.append(date_from)
        if date_to:
            count_clauses.append("[date] <= ?")
            count_params.append(date_to)
        if tag:
            count_clauses.append("[tags] LIKE ?")
            count_params.append(f"%{tag}%")
        count_where = " AND ".join(count_clauses) if count_clauses else "1=1"
        total_count = db.execute(
            f"SELECT COUNT(*) AS cnt FROM [blogs_posts] WHERE {count_where}",
            tuple(count_params), fetch="val"
        ) or 0
    else:
        total_count = db.count(SITE, "posts", where=where if where else None)

    # Determine if there are more pages
    has_more = len(results) > per_page
    results = results[:per_page]
    total_pages = (total_count + per_page - 1) // per_page if total_count else 1

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template("blogs/index.html",
                           posts=results, categories=categories,
                           q=q, cat=cat, tag=tag, date_from=date_from,
                           date_to=date_to, sort=sort_param, author=author, user=user,
                           page=page, total_pages=total_pages, per_page=per_page,
                           total_count=total_count)


@blueprint.route("/post/<int:post_id>")
def post_detail(post_id):
    post = db.get_item(SITE, "posts", post_id)
    if post is None:
        abort(404)
    comments = _load_comments(post_id=post_id)
    related = _load_posts(category=post["category"], limit=6)
    related = [p for p in related if p["id"] != post_id][:5]
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("blogs/post.html", post=post, comments=comments,
                           related=related, user=user)


@blueprint.route("/category/<cat_name>")
def category_page(cat_name):
    page = request.args.get("page", 1, type=int)
    per_page = 30
    offset = (page - 1) * per_page
    filtered = db.query(SITE, "posts", where={"category": cat_name},
                        sort="-date", limit=per_page, offset=offset)
    total_count = db.count(SITE, "posts", where={"category": cat_name})
    total_pages = (total_count + per_page - 1) // per_page if total_count else 1
    cat_rows = db.execute("SELECT DISTINCT [category] FROM [blogs_posts] ORDER BY [category]", ())
    categories = [r["category"] for r in cat_rows]
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("blogs/index.html", posts=filtered, categories=categories,
                           q="", cat=cat_name, tag="", date_from="", date_to="",
                           sort="date", author="", user=user,
                           page=page, total_pages=total_pages, per_page=per_page,
                           total_count=total_count)


@blueprint.route("/tag/<tag_name>")
def tag_page(tag_name):
    filtered = db.execute(
        "SELECT * FROM [blogs_posts] WHERE [tags] LIKE ? ORDER BY [date] DESC LIMIT 50",
        (f"%{tag_name}%",)
    )
    cat_rows = db.execute("SELECT DISTINCT [category] FROM [blogs_posts] ORDER BY [category]", ())
    categories = [r["category"] for r in cat_rows]
    total_count = db.execute(
        "SELECT COUNT(*) AS cnt FROM [blogs_posts] WHERE [tags] LIKE ?",
        (f"%{tag_name}%",), fetch="val"
    ) or 0
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("blogs/index.html", posts=filtered, categories=categories,
                           q="", cat="", tag=tag_name, date_from="", date_to="",
                           sort="date", author="", user=user,
                           page=1, total_pages=1, per_page=50,
                           total_count=total_count)


@blueprint.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return render_template("blogs/login.html", error=None, mode="login", next="")
    user = _get_user(session["user_id"])
    if not user:
        return render_template("blogs/login.html", error=None, mode="login", next="")
    # Fetch user's own posts
    my_posts = db.query(SITE, "posts", where={"author_username": user["username"]},
                        sort="-date", limit=50)
    # Fetch saved posts by IDs
    saved_ids = user.get("saved_posts", [])
    saved = []
    if saved_ids:
        placeholders = ",".join("?" * len(saved_ids))
        saved = db.execute(
            f"SELECT * FROM [blogs_posts] WHERE [id] IN ({placeholders}) ORDER BY [date] DESC",
            tuple(saved_ids)
        )
    return render_template("blogs/dashboard.html", user=user,
                           saved_posts=saved, my_posts=my_posts)


def _safe_next(value):
    """Only allow same-site relative redirects."""
    return value if (value and value.startswith("/") and not value.startswith("//")) else None


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("blogs/login.html", error=None, mode="login",
                           next=request.args.get("next", ""))


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    nxt = request.form.get("next", "")
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return render_template("blogs/login.html", error="Invalid username or password",
                               mode="login", next=nxt)
    session["user_id"] = user["id"]
    return redirect(_safe_next(nxt) or url_for("blogs.dashboard"))


@blueprint.route("/register", methods=["GET"])
def register_page():
    return render_template("blogs/login.html", error=None, mode="register",
                           next=request.args.get("next", ""))


@blueprint.route("/register", methods=["POST"])
def register_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    display_name = request.form.get("display_name", "").strip()
    email = request.form.get("email", "").strip()
    nxt = request.form.get("next", "")
    if not username or not password or not email:
        return render_template("blogs/login.html",
                               error="Username, password and email are required",
                               mode="register", next=nxt)
    users = _load_users()
    if any(u["username"] == username for u in users):
        return render_template("blogs/login.html", error="Username already taken",
                               mode="register", next=nxt)
    new_id = (db.execute("SELECT MAX([id]) AS mid FROM [blogs_users]", (), fetch="val") or 0) + 1
    new_user = {
        "id": new_id,
        "root_user_id": new_id,
        "username": username,
        "password": password,
        "display_name": display_name or username,
        "bio": "",
        "avatar": "/sites/blogs/static/images/avatars/default.jpg",
        "followed_blogs": [],
        "saved_posts": [],
        "subscribed_tags": [],
    }
    db.save_item(SITE, "users", new_id, new_user)
    emit("signup", user_id=new_id, site_name="blogs",
         username=username, password=password, email=email)
    session["user_id"] = new_id
    return redirect(_safe_next(nxt) or url_for("blogs.dashboard"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return render_template("blogs/login.html", error=None, mode="login", next="")


@blueprint.route("/compose", methods=["GET"])
def compose_page():
    if "user_id" not in session:
        return redirect(url_for("blogs.login_page", next=request.path))
    categories = _CATEGORIES
    user = _get_user(session["user_id"])
    return render_template("blogs/compose.html", categories=categories, user=user)


@blueprint.route("/compose", methods=["POST"])
def form_create_post():
    """Create post via HTML form POST."""
    if "user_id" not in session:
        return redirect(url_for("blogs.login_page", next=url_for("blogs.compose_page")))
    title = request.form.get("title", "").strip()
    body = request.form.get("body", "").strip()
    category = request.form.get("category", "Lifestyle").strip()
    tags_str = request.form.get("tags", "").strip()
    tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []
    image_url = request.form.get("image_url", "").strip() or None
    author_username = request.form.get("author_username", "").strip()

    if not title or not body:
        return "Title and body required", 400
    if not author_username:
        return "Author username required", 400

    users = _load_users()
    author = next((u for u in users if u["username"] == author_username), None)
    if not author:
        return "Author not found", 404

    max_id = db.execute("SELECT MAX([id]) AS mid FROM [blogs_posts]", (), fetch="val") or 0
    new_id = max_id + 1

    new_post = {
        "id": new_id,
        "title": title,
        "body": body,
        "author_id": author["id"],
        "author_username": author["username"],
        "author_display_name": author["display_name"],
        "author_avatar": author["avatar"],
        "category": category,
        "tags": tags,
        "image_url": image_url,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "notes_count": 0,
        "is_pinned": False,
        "shared_count": 0,
    }

    db.save_item(SITE, "posts", new_id, new_post)
    _add_email(author["id"], "noreply@blogs.lakeport.local",
               "Your post has been published",
               f'Your post "{title}" has been published on TumblrVibe.')
    return redirect(url_for("blogs.post_detail", post_id=new_id))


@blueprint.route("/post/<int:post_id>/comment", methods=["POST"])
def form_add_comment(post_id):
    """Add comment via HTML form POST."""
    body = request.form.get("body", "").strip()
    author_username = request.form.get("author_username", "").strip()

    if not body or not author_username:
        return "Comment body and author required", 400

    post = db.get_item(SITE, "posts", post_id)
    if not post:
        abort(404)

    users = _load_users()
    author = next((u for u in users if u["username"] == author_username), None)
    if not author:
        return "Author not found", 404

    comments = _load_comments()
    new_id = max((c["id"] for c in comments), default=0) + 1
    new_comment = {
        "id": new_id,
        "post_id": post_id,
        "author_username": author["username"],
        "author_display_name": author["display_name"],
        "body": body,
        "date": datetime.now().strftime("%Y-%m-%d"),
    }
    comments.append(new_comment)
    _save_comments(comments)
    return redirect(url_for("blogs.post_detail", post_id=post_id))


@blueprint.route("/post/<int:post_id>/follow", methods=["POST"])
def form_follow_blog(post_id):
    """Follow/unfollow blog author via HTML form POST."""
    if "user_id" not in session:
        return redirect(url_for("blogs.login_page"))
    user_id = session["user_id"]
    blog = request.form.get("blog", "").strip()
    if not blog:
        return "Blog username required", 400

    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)

    followed = user.setdefault("followed_blogs", [])
    if blog in followed:
        followed.remove(blog)
    else:
        followed.append(blog)
    _save_users(users)
    return redirect(url_for("blogs.post_detail", post_id=post_id))


@blueprint.route("/post/<int:post_id>/save", methods=["POST"])
def form_save_post(post_id):
    """Save/unsave post via HTML form POST."""
    if "user_id" not in session:
        return redirect(url_for("blogs.login_page"))
    user_id = session["user_id"]

    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)

    saved = user.setdefault("saved_posts", [])
    if post_id in saved:
        saved.remove(post_id)
    else:
        saved.append(post_id)
    _save_users(users)
    return redirect(url_for("blogs.post_detail", post_id=post_id))


@blueprint.route("/post/<int:post_id>/subscribe", methods=["POST"])
def form_subscribe_tag(post_id):
    """Subscribe/unsubscribe tag via HTML form POST."""
    if "user_id" not in session:
        return redirect(url_for("blogs.login_page"))
    user_id = session["user_id"]
    tag = request.form.get("tag", "").strip()
    if not tag:
        return "Tag required", 400

    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)

    subscribed = user.setdefault("subscribed_tags", [])
    if tag in subscribed:
        subscribed.remove(tag)
    else:
        subscribed.append(tag)
    _save_users(users)
    return redirect(url_for("blogs.post_detail", post_id=post_id))


@blueprint.route("/report/<int:post_id>", methods=["GET"])
def report_page(post_id):
    post = db.get_item(SITE, "posts", post_id)
    if post is None:
        abort(404)
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("blogs/report.html", post=post, user=user)


@blueprint.route("/report/<int:post_id>", methods=["POST"])
def form_report_post(post_id):
    """Report post via HTML form POST."""
    reason = request.form.get("reason", "").strip()
    details = request.form.get("details", "").strip()
    reporter = request.form.get("reporter", "anonymous").strip()

    if not reason:
        return "Reason required", 400

    post = db.get_item(SITE, "posts", post_id)
    if not post:
        abort(404)

    reports = _load_reports()
    new_id = max((r["id"] for r in reports), default=0) + 1
    new_report = {
        "id": new_id,
        "post_id": post_id,
        "reporter_username": reporter,
        "reason": reason,
        "details": details,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "status": "pending",
    }
    reports.append(new_report)
    _save_reports(reports)
    return redirect(url_for("blogs.post_detail", post_id=post_id))


# ---------------------------------------------------------------------------
# API routes — read
# ---------------------------------------------------------------------------

@blueprint.route("/api/posts")
def api_posts():
    q = request.args.get("q", "").strip()
    cat = request.args.get("category", "").strip()
    tag = request.args.get("tag", "").strip()
    author = request.args.get("author", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    sort_param = request.args.get("sort", "date").strip()
    limit = request.args.get("limit", 50, type=int)

    clauses = []
    params = []

    if q:
        like_param = f"%{q}%"
        clauses.append("([title] LIKE ? OR [body] LIKE ? OR [author_username] LIKE ?)")
        params.extend([like_param, like_param, like_param])
    if cat:
        clauses.append("[category] = ?")
        params.append(cat)
    if tag:
        clauses.append("[tags] LIKE ?")
        params.append(f"%{tag}%")
    if author:
        clauses.append("[author_username] = ?")
        params.append(author)
    if date_from:
        clauses.append("[date] >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("[date] <= ?")
        params.append(date_to)

    where_sql = " AND ".join(clauses) if clauses else "1=1"

    order_sql = {
        "date": "[date] DESC",
        "oldest": "[date] ASC",
        "popular": "[notes_count] DESC",
    }.get(sort_param, "[date] DESC")

    sql = f"SELECT * FROM [blogs_posts] WHERE {where_sql} ORDER BY {order_sql} LIMIT ?"
    params.append(limit)
    results = db.execute(sql, tuple(params))
    return jsonify(results)


@blueprint.route("/api/posts/<int:post_id>")
def api_post(post_id):
    post = db.get_item(SITE, "posts", post_id)
    if post is None:
        abort(404)
    return jsonify(post)


@blueprint.route("/api/posts/search")
def api_search():
    q = request.args.get("q", "").strip()
    limit = request.args.get("limit", 50, type=int)
    results = db.search(SITE, "posts", q, limit=limit)
    # Fall back to LIKE search if FTS returns 0 results (FTS index may
    # not cover all columns, or query syntax may mismatch).
    if not results and q:
        like_param = f"%{q}%"
        results = db.execute(
            "SELECT * FROM [blogs_posts] WHERE "
            "([title] LIKE ? OR [body] LIKE ? OR [author_username] LIKE ? "
            "OR [category] LIKE ? OR [tags] LIKE ?) "
            "ORDER BY [date] DESC LIMIT ?",
            (like_param, like_param, like_param, like_param, like_param, limit),
        )
    return jsonify(results)


@blueprint.route("/api/categories")
def api_categories():
    rows = db.execute(
        "SELECT [category] AS name, COUNT(*) AS count FROM [blogs_posts] GROUP BY [category] ORDER BY [category]",
        ()
    )
    return jsonify(rows)


@blueprint.route("/api/tags")
def api_tags():
    # Tags are stored as JSON arrays; extract distinct tags via SQL
    rows = db.execute(
        "SELECT [tags] FROM [blogs_posts] WHERE [tags] != '[]' AND [tags] != '' LIMIT 5000",
        ()
    )
    from collections import Counter
    tag_counts = Counter()
    for r in rows:
        tags = r.get("tags", [])
        if isinstance(tags, list):
            for t in tags:
                tag_counts[t] += 1
    return jsonify([{"name": t, "count": n} for t, n in tag_counts.most_common()])


@blueprint.route("/api/posts/<int:post_id>/comments")
def api_post_comments(post_id):
    return jsonify(_load_comments(post_id=post_id))


@blueprint.route("/api/authors")
def api_authors():
    rows = db.execute(
        "SELECT [author_username] AS username, [author_display_name] AS display_name, "
        "[author_avatar] AS avatar, COUNT(*) AS post_count "
        "FROM [blogs_posts] GROUP BY [author_username] "
        "ORDER BY post_count DESC",
        ()
    )
    return jsonify(rows)


# ---------------------------------------------------------------------------
# API routes — write (mutable state)
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


@blueprint.route("/api/users/<int:user_id>/save", methods=["POST"])
def api_save_post(user_id):
    data = request.get_json(silent=True) or {}
    post_id = data.get("post_id")
    if post_id is None:
        return jsonify({"error": "post_id required"}), 400
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    saved = user.setdefault("saved_posts", [])
    if post_id in saved:
        saved.remove(post_id)
        action = "unsaved"
    else:
        saved.append(post_id)
        action = "saved"
    _save_users(users)
    return jsonify({"action": action, "post_id": post_id, "total_saved": len(saved)})


@blueprint.route("/api/users/<int:user_id>/follow", methods=["POST"])
def api_follow_blog(user_id):
    data = request.get_json(silent=True) or {}
    blog = data.get("blog", "").strip()
    if not blog:
        return jsonify({"error": "blog username required"}), 400
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    followed = user.setdefault("followed_blogs", [])
    if blog in followed:
        followed.remove(blog)
        action = "unfollowed"
    else:
        followed.append(blog)
        action = "followed"
    _save_users(users)
    return jsonify({"action": action, "blog": blog, "total_followed": len(followed)})


@blueprint.route("/api/users/<int:user_id>/subscribe", methods=["POST"])
def api_subscribe_tag(user_id):
    data = request.get_json(silent=True) or {}
    tag = data.get("tag", "").strip()
    if not tag:
        return jsonify({"error": "tag required"}), 400
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    subscribed = user.setdefault("subscribed_tags", [])
    if tag in subscribed:
        subscribed.remove(tag)
        action = "unsubscribed"
    else:
        subscribed.append(tag)
        action = "subscribed"
    _save_users(users)
    return jsonify({"action": action, "tag": tag, "total_subscribed": len(subscribed)})


@blueprint.route("/api/posts/<int:post_id>/share", methods=["POST"])
def api_share_post(post_id):
    data = request.get_json(silent=True) or {}
    platform = data.get("platform", "link").strip()
    post = db.get_item(SITE, "posts", post_id)
    if not post:
        abort(404)
    post["shared_count"] = post.get("shared_count", 0) + 1
    db.save_item(SITE, "posts", post_id, post)
    return jsonify({
        "action": "shared",
        "post_id": post_id,
        "platform": platform,
        "share_url": f"/sites/blogs/post/{post_id}",
        "total_shares": post["shared_count"],
    })


@blueprint.route("/api/posts/create", methods=["POST"])
def api_create_post():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    body = data.get("body", "").strip()
    category = data.get("category", "Lifestyle").strip()
    tags = data.get("tags", [])
    author_username = data.get("author_username", "").strip()
    image_url = data.get("image_url", None)

    if not title or not body:
        return jsonify({"error": "title and body required"}), 400
    if not author_username:
        return jsonify({"error": "author_username required"}), 400

    users = _load_users()
    author = next((u for u in users if u["username"] == author_username), None)
    if not author:
        return jsonify({"error": "author not found"}), 404

    max_id = db.execute("SELECT MAX([id]) AS mid FROM [blogs_posts]", (), fetch="val") or 0
    new_id = max_id + 1

    new_post = {
        "id": new_id,
        "title": title,
        "body": body,
        "author_id": author["id"],
        "author_username": author["username"],
        "author_display_name": author["display_name"],
        "author_avatar": author["avatar"],
        "category": category,
        "tags": tags if isinstance(tags, list) else [tags],
        "image_url": image_url,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "notes_count": 0,
        "is_pinned": False,
        "shared_count": 0,
    }

    db.save_item(SITE, "posts", new_id, new_post)
    return jsonify(new_post), 201


@blueprint.route("/api/posts/<int:post_id>/comment", methods=["POST"])
def api_add_comment(post_id):
    data = request.get_json(silent=True) or {}
    body = data.get("body", "").strip()
    author_username = data.get("author_username", "").strip()

    if not body or not author_username:
        return jsonify({"error": "body and author_username required"}), 400

    post = db.get_item(SITE, "posts", post_id)
    if not post:
        abort(404)

    users = _load_users()
    author = next((u for u in users if u["username"] == author_username), None)
    if not author:
        return jsonify({"error": "author not found"}), 404

    comments = _load_comments()
    new_id = max((c["id"] for c in comments), default=0) + 1
    new_comment = {
        "id": new_id,
        "post_id": post_id,
        "author_username": author["username"],
        "author_display_name": author["display_name"],
        "body": body,
        "date": datetime.now().strftime("%Y-%m-%d"),
    }
    comments.append(new_comment)
    _save_comments(comments)
    return jsonify(new_comment), 201


@blueprint.route("/api/posts/<int:post_id>/report", methods=["POST"])
def api_report_post(post_id):
    data = request.get_json(silent=True) or {}
    reason = data.get("reason", "").strip()
    details = data.get("details", "").strip()
    reporter = data.get("reporter_username", "anonymous").strip()

    if not reason:
        return jsonify({"error": "reason required"}), 400

    post = db.get_item(SITE, "posts", post_id)
    if not post:
        abort(404)

    reports = _load_reports()
    new_id = max((r["id"] for r in reports), default=0) + 1
    new_report = {
        "id": new_id,
        "post_id": post_id,
        "reporter_username": reporter,
        "reason": reason,
        "details": details,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "status": "pending",
    }
    reports.append(new_report)
    _save_reports(reports)
    return jsonify(new_report), 201


@blueprint.route("/api/reports")
def api_reports():
    return jsonify(_load_reports())
