"""RedditLike Forums -- community discussion site (Reddit-style).

Data is stored in per-site SQLite tables (forums_posts, forums_comments,
forums_users) and queried through app.db.  Session mutations are isolated
per user.  Supports 27 macros covering navigation, search, filtering,
extraction, content creation, social interactions, and moderation.
"""
import json
import math
import pathlib
from collections import Counter
from datetime import datetime, timezone

from flask import (
    Blueprint, Response, abort, jsonify, redirect, render_template, request,
    session, url_for,
)
from app import db
from app.events import emit

SITE = "forums"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "forums",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data helpers — all data lives in SQLite via db.query() / db.save_collection()
# ---------------------------------------------------------------------------

def _fix_user_json(u):
    """Deserialize JSON-string list fields on a user dict."""
    for field in ("subscribed_subreddits", "saved_posts", "followed_users", "blocked_users"):
        if isinstance(u.get(field), str):
            try:
                u[field] = json.loads(u[field])
            except (json.JSONDecodeError, TypeError):
                u[field] = []
    return u


def _load_users():
    """Users table is small (<20 rows); OK to load all."""
    users = db.query(SITE, "users")
    for u in users:
        _fix_user_json(u)
    return users


def _get_user_by_username(username):
    """Fetch a single user by username."""
    users = db.query(SITE, "users", where={"username": username}, limit=1)
    if users:
        return _fix_user_json(users[0])
    return None


def _get_user_by_root_id(root_user_id):
    """Fetch a single user by root_user_id."""
    users = db.query(SITE, "users", where={"root_user_id": root_user_id}, limit=1)
    if users:
        return _fix_user_json(users[0])
    return None


def _save_users(users):
    db.save_collection(SITE, "users", users)


def _load_posts(*, where=None, sort=None, limit=None, offset=0):
    return db.query(SITE, "posts", where=where, sort=sort, limit=limit, offset=offset)


def _save_posts(posts):
    db.save_collection(SITE, "posts", posts)


def _get_post(post_id):
    return db.get_item(SITE, "posts", post_id)


def _load_comments(*, where=None, sort=None, limit=None, offset=0):
    return db.query(SITE, "comments", where=where, sort=sort, limit=limit, offset=offset)


def _save_comments(comments):
    db.save_collection(SITE, "comments", comments)


def _get_comment(comment_id):
    return db.get_item(SITE, "comments", comment_id)


def _count_comments(**kwargs):
    return db.count(SITE, "comments", **kwargs)


def _load_messages():
    return db.query(SITE, "messages")


def _save_messages(messages):
    db.save_collection(SITE, "messages", messages)


def _load_reports():
    return db.query(SITE, "reports")


def _save_reports(reports):
    db.save_collection(SITE, "reports", reports)


def _get_current_user():
    """Return the logged-in user dict or None."""
    uid = session.get("user_id")
    if uid is None:
        return None
    return _get_user_by_root_id(uid)


def _get_subreddits():
    """Return sorted list of unique subreddit names from posts.

    Values are stored without ``r/`` prefix in the DB (e.g. ``AskReddit``).
    This helper returns them as-is; templates add the ``r/`` display prefix.
    """
    table = db.get_table_name(SITE, "posts")
    if not table:
        return []
    rows = db.execute(f"SELECT DISTINCT [subreddit] FROM [{table}] ORDER BY [subreddit]")
    return [r["subreddit"] for r in rows if r.get("subreddit")]


def _hot_score(post):
    """Simple hot-ranking: score biased by recency."""
    score = int(post.get("score", 0) or 0)
    try:
        created = datetime.fromisoformat(post["created_utc"].replace("Z", "+00:00"))
        age_hours = (datetime.now(timezone.utc) - created).total_seconds() / 3600
    except (KeyError, ValueError):
        age_hours = 10000
    sign = 1 if score > 0 else (-1 if score < 0 else 0)
    order = math.log10(max(abs(score), 1))
    return sign * order - age_hours / 500


def _sort_posts(posts, sort="hot"):
    if sort == "new":
        return sorted(posts, key=lambda p: p.get("created_utc", ""), reverse=True)
    elif sort == "top":
        return sorted(posts, key=lambda p: p.get("score", 0), reverse=True)
    else:  # hot
        return sorted(posts, key=_hot_score, reverse=True)


def _format_time_ago(iso_str):
    """Convert ISO datetime to a human-readable 'time ago' string."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        diff = datetime.now(timezone.utc) - dt
        seconds = int(diff.total_seconds())
        if seconds < 60:
            return "just now"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        if days < 30:
            return f"{days}d ago"
        months = days // 30
        if months < 12:
            return f"{months}mo ago"
        years = days // 365
        return f"{years}y ago"
    except (ValueError, KeyError):
        return ""


def _build_comment_tree(comments, post_id):
    """Build threaded comment tree for a post."""
    post_comments = [c for c in comments if c["post_id"] == post_id]
    by_id = {c["id"]: {**c, "children": []} for c in post_comments}
    roots = []
    for c in post_comments:
        node = by_id[c["id"]]
        parent_id = c.get("parent_comment_id")
        if parent_id and parent_id in by_id:
            by_id[parent_id]["children"].append(node)
        else:
            roots.append(node)
    def sort_tree(nodes):
        nodes.sort(key=lambda n: n.get("score", 0), reverse=True)
        for n in nodes:
            sort_tree(n["children"])
    sort_tree(roots)
    return roots


def _next_post_id():
    table = db.get_table_name(SITE, "posts")
    if table:
        row = db.execute(f"SELECT MAX([id]) as max_id FROM [{table}]", fetch="one")
        if row and row["max_id"]:
            try:
                max_num = int(row["max_id"].replace("rd_post_", ""))
                return f"rd_post_{max_num + 1:03d}"
            except (ValueError, TypeError):
                pass
    return "rd_post_001"


def _next_comment_id():
    table = db.get_table_name(SITE, "comments")
    if table:
        row = db.execute(f"SELECT MAX([id]) as max_id FROM [{table}]", fetch="one")
        if row and row["max_id"]:
            try:
                max_num = int(row["max_id"].replace("rd_comment_", ""))
                return f"rd_comment_{max_num + 1:03d}"
            except (ValueError, TypeError):
                pass
    return "rd_comment_001"


def _next_message_id():
    messages = _load_messages()
    max_num = 0
    for m in messages:
        try:
            num = int(m["id"].replace("rd_msg_", ""))
            if num > max_num:
                max_num = num
        except (ValueError, KeyError):
            pass
    return f"rd_msg_{max_num + 1:03d}"


def _next_report_id():
    reports = _load_reports()
    max_num = 0
    for r in reports:
        try:
            num = int(r["id"].replace("rd_report_", ""))
            if num > max_num:
                max_num = num
        except (ValueError, KeyError):
            pass
    return f"rd_report_{max_num + 1:03d}"


def _semantic_score(query_tokens, text):
    """Simple keyword-overlap scoring for semantic search."""
    text_lower = text.lower()
    text_tokens = set(text_lower.split())
    score = 0
    for qt in query_tokens:
        if qt in text_lower:
            score += 2  # substring match
        if qt in text_tokens:
            score += 1  # exact token match
    return score


# ---------------------------------------------------------------------------
# Template context
# ---------------------------------------------------------------------------

@blueprint.context_processor
def _inject_helpers():
    return {
        "current_user": _get_current_user(),
        "format_time_ago": _format_time_ago,
        "all_subreddits": _get_subreddits,
    }


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    sort = request.args.get("sort", "hot")
    subreddit_filter = request.args.get("subreddit")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")

    # For date range filters and sorting, use db.execute for more control
    table = db.get_table_name(SITE, "posts")
    if table:
        sql = f"SELECT * FROM [{table}]"
        params = []
        clauses = []
        if subreddit_filter:
            # Try both with and without r/ prefix to match DB data
            clauses.append("([subreddit] = ? OR [subreddit] = ?)")
            if subreddit_filter.startswith("r/"):
                params.extend([subreddit_filter, subreddit_filter[2:]])
            else:
                params.extend([subreddit_filter, f"r/{subreddit_filter}"])
        if date_from:
            clauses.append("[created_utc] >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("[created_utc] <= ?")
            params.append(date_to)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)

        if sort == "new":
            sql += " ORDER BY [created_utc] DESC"
        elif sort == "top":
            sql += " ORDER BY [score] DESC"
        else:
            sql += " ORDER BY [score] DESC"  # hot approximation

        sql += " LIMIT 50"
        posts = db.execute(sql, tuple(params))

        # Raw SQL reads the base table only — merge in this session's posts
        def _overlay_match(p):
            if subreddit_filter:
                sr = subreddit_filter[2:] if subreddit_filter.startswith("r/") else subreddit_filter
                if p.get("subreddit") not in (sr, f"r/{sr}"):
                    return False
            if date_from and (p.get("created_utc") or "") < date_from:
                return False
            if date_to and (p.get("created_utc") or "") > date_to:
                return False
            return True

        posts = db.merge_overlay(
            SITE, "posts", posts, match=_overlay_match,
            sort="-created_utc" if sort == "new" else "-score", limit=50,
        )
    else:
        posts = []

    # num_comments is already a column — use it directly, no per-post DB query
    for p in posts:
        p["_comment_count"] = p.get("num_comments") or 0

    subreddits = _get_subreddits()
    return render_template("forums/index.html", posts=posts, sort=sort,
                           subreddits=subreddits)


@blueprint.route("/r/<subreddit_name>")
def subreddit_view(subreddit_name):
    # Subreddit values are stored without "r/" prefix in the DB.
    sort = request.args.get("sort", "hot")

    sort_col = "score" if sort in ("top", "hot") else "created_utc"
    sub_posts = _load_posts(where={"subreddit": subreddit_name}, sort=f"-{sort_col}", limit=50)
    if not sub_posts:
        abort(404)
    for p in sub_posts:
        p["_comment_count"] = _count_comments(where={"post_id": p["id"]})
    return render_template("forums/subreddit.html", posts=sub_posts, sort=sort,
                           subreddit=subreddit_name)


@blueprint.route("/post/<post_id>")
def post_detail(post_id):
    post = _get_post(post_id)
    if not post:
        abort(404)
    post_comments = _load_comments(where={"post_id": post_id})
    comment_tree = _build_comment_tree(post_comments, post_id)
    post["_comment_count"] = len(post_comments)
    return render_template("forums/post_detail.html", post=post,
                           comment_tree=comment_tree)


@blueprint.route("/user/<username>")
def user_profile(username):
    user = _get_user_by_username(username)
    user_posts = _load_posts(where={"author": username}, sort="-created_utc", limit=50)
    user_comments = _load_comments(where={"author": username}, sort="-created_utc", limit=50)
    if not user:
        # Author exists in posts/comments but not in users table — synthesize a profile
        if not user_posts and not user_comments:
            abort(404)
        earliest = None
        for p in user_posts:
            if p.get("created_utc") and (earliest is None or p["created_utc"] < earliest):
                earliest = p["created_utc"]
        for c in user_comments:
            if c.get("created_utc") and (earliest is None or c["created_utc"] < earliest):
                earliest = c["created_utc"]
        user = {
            "username": username,
            "cake_day": (earliest or "")[:10],
            "karma": 0,
            "subscribed_subreddits": [],
            "biography": "",
            "blocked_users": [],
            "followed_users": [],
        }
    # Enrich comments with parent post info
    for c in user_comments:
        parent_post = _get_post(c["post_id"])
        c["_post_title"] = parent_post["title"] if parent_post else "[deleted]"
        c["_post_subreddit"] = parent_post["subreddit"] if parent_post else ""
    post_karma = sum(p.get("score", 0) for p in user_posts)
    comment_karma = sum(c.get("score", 0) for c in user_comments)
    return render_template("forums/user_profile.html", profile_user=user,
                           user_posts=user_posts, user_comments=user_comments,
                           post_karma=post_karma, comment_karma=comment_karma)


@blueprint.route("/submit")
def submit_page():
    subreddits = _get_subreddits()
    return render_template("forums/submit.html", subreddits=subreddits)


@blueprint.route("/submit", methods=["POST"])
def submit_post_form():
    """submit_by_form: HTML form-based post creation."""
    user = _get_current_user()
    if not user:
        return redirect(url_for("forums.login_page"))
    title = (request.form.get("title") or "").strip()
    body = (request.form.get("body") or "").strip()
    subreddit = (request.form.get("subreddit") or "").strip()
    flair = (request.form.get("flair") or "").strip()
    if not title or not subreddit:
        subreddits = _get_subreddits()
        return render_template("forums/submit.html", subreddits=subreddits,
                               error="Title and subreddit are required.")
    # Strip r/ prefix if present -- DB stores bare names
    if subreddit.startswith("r/"):
        subreddit = subreddit[2:]
    new_post = {
        "id": _next_post_id(),
        "author_root_user_id": user["root_user_id"],
        "author": user["username"],
        "subreddit": subreddit,
        "title": title,
        "body": body,
        "score": 1,
        "num_comments": 0,
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "flair": flair,
    }
    db.save_item(SITE, "posts", new_post["id"], new_post)
    return redirect(url_for("forums.post_detail", post_id=new_post["id"]))


@blueprint.route("/search")
def search_page():
    """HTML search results page."""
    q = (request.args.get("q") or "").strip()
    sort = request.args.get("sort", "top")
    results = []
    if q:
        results = db.search(SITE, "posts", q, limit=50)
    return render_template("forums/search.html", query=q, results=results, sort=sort)


@blueprint.route("/login")
def login_page():
    return render_template("forums/login.html")


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    user = _get_user_by_username(username)
    if not user:
        return render_template("forums/login.html",
                               error="User not found. Check your username.")
    # Password check (simple: password field matches or default "password")
    stored_pw = user.get("password", "password")
    if password and password != stored_pw:
        return render_template("forums/login.html",
                               error="Incorrect password.")
    session["user_id"] = user["root_user_id"]
    return redirect(url_for("forums.index"))


@blueprint.route("/register")
def register_page():
    return render_template("forums/register.html")


@blueprint.route("/register", methods=["POST"])
def register_submit():
    """register_by_form: HTML form-based user registration."""
    username = (request.form.get("username") or "").strip()
    password = (request.form.get("password") or "").strip()
    if not username:
        return render_template("forums/register.html",
                               error="Username is required.")
    if not password:
        return render_template("forums/register.html",
                               error="Password is required.")
    users = _load_users()
    if any(u["username"] == username for u in users):
        return render_template("forums/register.html",
                               error="Username already taken.")
    max_id = max((u["root_user_id"] for u in users), default=0)
    new_user = {
        "root_user_id": max_id + 100,
        "username": username,
        "karma": 0,
        "subscribed_subreddits": [],
        "cake_day": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "password": password,
        "saved_posts": [],
        "followed_users": [],
        "blocked_users": [],
    }
    users.append(new_user)
    _save_users(users)
    emit("signup", user_id=new_user["root_user_id"], site_name="forums",
         username=username, password=password, email="")
    session["user_id"] = new_user["root_user_id"]
    return redirect(url_for("forums.index"))


@blueprint.route("/messages")
def messages_page():
    """Inbox page for direct messages."""
    user = _get_current_user()
    if not user:
        return redirect(url_for("forums.login_page"))
    messages = _load_messages()
    inbox = sorted([m for m in messages if m["to_username"] == user["username"]],
                   key=lambda m: m.get("created_utc", ""), reverse=True)
    sent = sorted([m for m in messages if m["from_username"] == user["username"]],
                  key=lambda m: m.get("created_utc", ""), reverse=True)
    return render_template("forums/messages.html", inbox=inbox, sent=sent)


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("forums.index"))


# ---------------------------------------------------------------------------
# API routes - core CRUD
# ---------------------------------------------------------------------------

@blueprint.route("/api/posts", methods=["GET"])
def api_list_posts():
    sub = request.args.get("subreddit")
    user = request.args.get("user")
    sort = request.args.get("sort", "hot")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    flair = request.args.get("flair")

    table = db.get_table_name(SITE, "posts")
    if not table:
        return jsonify([])

    sql = f"SELECT * FROM [{table}]"
    params = []
    clauses = []
    if sub:
        # Try both with and without r/ prefix to match DB data
        clauses.append("([subreddit] = ? OR [subreddit] = ?)")
        if sub.startswith("r/"):
            params.extend([sub, sub[2:]])
        else:
            params.extend([sub, f"r/{sub}"])
    if user:
        clauses.append("[author] = ?")
        params.append(user)
    if date_from:
        clauses.append("[created_utc] >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("[created_utc] <= ?")
        params.append(date_to)
    if flair:
        clauses.append("LOWER([flair]) = ?")
        params.append(flair.lower())
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)

    if sort == "new":
        sql += " ORDER BY [created_utc] DESC"
    elif sort == "top":
        sql += " ORDER BY [score] DESC"
    else:
        sql += " ORDER BY [score] DESC"

    sql += " LIMIT 50"
    posts = db.execute(sql, tuple(params))
    return jsonify(posts)


@blueprint.route("/api/posts", methods=["POST"])
def api_create_post():
    """submit_by_route: JSON API post creation."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    data = request.get_json(silent=True)
    if not data:
        data = dict(request.form)
    title = (data.get("title") or "").strip()
    body = (data.get("body") or "").strip()
    subreddit = (data.get("subreddit") or "").strip()
    if not title:
        return jsonify({"error": "Title is required"}), 400
    if not subreddit:
        return jsonify({"error": "Subreddit is required"}), 400
    # Strip r/ prefix if present -- DB stores bare names
    if subreddit.startswith("r/"):
        subreddit = subreddit[2:]
    new_post = {
        "id": _next_post_id(),
        "author_root_user_id": user["root_user_id"],
        "author": user["username"],
        "subreddit": subreddit,
        "title": title,
        "body": body,
        "score": 1,
        "num_comments": 0,
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "flair": data.get("flair", ""),
    }
    db.save_item(SITE, "posts", new_post["id"], new_post)
    return jsonify(new_post), 201


@blueprint.route("/api/posts/<post_id>", methods=["GET"])
def api_get_post(post_id):
    post = _get_post(post_id)
    if not post:
        return jsonify({"error": "Post not found"}), 404
    return jsonify(post)


@blueprint.route("/api/posts/<post_id>", methods=["PUT"])
def api_update_post(post_id):
    """edit_by_form: update an existing post."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    post = _get_post(post_id)
    if not post:
        return jsonify({"error": "Post not found"}), 404
    if post["author_root_user_id"] != user["root_user_id"]:
        return jsonify({"error": "Not your post"}), 403
    data = request.get_json(silent=True) or {}
    if "title" in data:
        post["title"] = data["title"].strip()
    if "body" in data:
        post["body"] = data["body"].strip()
    if "flair" in data:
        post["flair"] = data["flair"].strip()
    db.save_item(SITE, "posts", post_id, post)
    return jsonify(post)


@blueprint.route("/api/posts/<post_id>", methods=["DELETE"])
def api_delete_post(post_id):
    """delete_from_table: delete a post and its comments."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    post = _get_post(post_id)
    if not post:
        return jsonify({"error": "Post not found"}), 404
    if post["author_root_user_id"] != user["root_user_id"]:
        return jsonify({"error": "Not your post"}), 403
    db.delete_item(SITE, "posts", post_id)
    # Delete associated comments
    post_comments = _load_comments(where={"post_id": post_id})
    for c in post_comments:
        db.delete_item(SITE, "comments", c["id"])
    return jsonify({"status": "deleted", "id": post_id})


# ---------------------------------------------------------------------------
# API routes - voting (react_by_toggle)
# ---------------------------------------------------------------------------

@blueprint.route("/api/posts/<post_id>/vote", methods=["POST"])
def api_vote_post(post_id):
    """react_by_toggle: upvote/downvote a post."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    data = request.get_json(silent=True) or {}
    direction = data.get("direction", "up")
    post = _get_post(post_id)
    if not post:
        return jsonify({"error": "Post not found"}), 404
    if direction == "up":
        post["score"] = post.get("score", 0) + 1
    elif direction == "down":
        post["score"] = post.get("score", 0) - 1
    else:
        return jsonify({"error": "direction must be 'up' or 'down'"}), 400
    db.save_item(SITE, "posts", post_id, post)
    return jsonify({"id": post_id, "score": post["score"], "direction": direction})


@blueprint.route("/api/comments/<comment_id>/vote", methods=["POST"])
def api_vote_comment(comment_id):
    """react_by_toggle: upvote/downvote a comment."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    data = request.get_json(silent=True) or {}
    direction = data.get("direction", "up")
    comment = _get_comment(comment_id)
    if not comment:
        return jsonify({"error": "Comment not found"}), 404
    if direction == "up":
        comment["score"] = comment.get("score", 0) + 1
    elif direction == "down":
        comment["score"] = comment.get("score", 0) - 1
    else:
        return jsonify({"error": "direction must be 'up' or 'down'"}), 400
    db.save_item(SITE, "comments", comment_id, comment)
    return jsonify({"id": comment_id, "score": comment["score"], "direction": direction})


# ---------------------------------------------------------------------------
# API routes - comments
# ---------------------------------------------------------------------------

@blueprint.route("/api/posts/<post_id>/comments", methods=["GET"])
def api_post_comments(post_id):
    post_comments = _load_comments(where={"post_id": post_id}, sort="-score")
    return jsonify(post_comments)


@blueprint.route("/api/posts/<post_id>/comments", methods=["POST"])
def api_add_comment(post_id):
    """create_from_free_text: add a comment to a post."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    post = _get_post(post_id)
    if not post:
        return jsonify({"error": "Post not found"}), 404
    data = request.get_json(silent=True)
    if not data:
        data = dict(request.form)
    body = (data.get("body") or "").strip()
    if not body:
        return jsonify({"error": "Comment body is required"}), 400
    parent_comment_id = data.get("parent_comment_id") or None
    new_comment = {
        "id": _next_comment_id(),
        "post_id": post_id,
        "author_root_user_id": user["root_user_id"],
        "author": user["username"],
        "body": body,
        "score": 1,
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "parent_comment_id": parent_comment_id,
    }
    db.save_item(SITE, "comments", new_comment["id"], new_comment)
    post["num_comments"] = _count_comments(where={"post_id": post_id})
    db.save_item(SITE, "posts", post_id, post)
    return jsonify(new_comment), 201


@blueprint.route("/api/comments/<comment_id>", methods=["GET"])
def api_get_comment(comment_id):
    comment = _get_comment(comment_id)
    if not comment:
        return jsonify({"error": "Comment not found"}), 404
    return jsonify(comment)


@blueprint.route("/api/comments/<comment_id>", methods=["DELETE"])
def api_delete_comment(comment_id):
    """delete_from_table: delete a comment."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    comment = _get_comment(comment_id)
    if not comment:
        return jsonify({"error": "Comment not found"}), 404
    if comment["author_root_user_id"] != user["root_user_id"]:
        return jsonify({"error": "Not your comment"}), 403
    post_id = comment["post_id"]
    db.delete_item(SITE, "comments", comment_id)
    post = _get_post(post_id)
    if post:
        post["num_comments"] = _count_comments(where={"post_id": post_id})
        db.save_item(SITE, "posts", post_id, post)
    return jsonify({"status": "deleted", "id": comment_id})


# ---------------------------------------------------------------------------
# API routes - subreddits
# ---------------------------------------------------------------------------

@blueprint.route("/api/subreddits", methods=["GET"])
def api_list_subreddits():
    """navigate_by_dropdown / extract_by_dropdown: list all subreddits with stats."""
    posts_table = db.get_table_name(SITE, "posts")
    comments_table = db.get_table_name(SITE, "comments")
    if not posts_table:
        return jsonify([])

    # Use the pre-computed subreddits table if available
    subs_table = db.get_table_name(SITE, "subreddits")
    if subs_table:
        subs = db.execute(
            f"SELECT [name], [post_count], [title], [description] "
            f"FROM [{subs_table}] ORDER BY [post_count] DESC"
        )
        result = []
        for row in subs:
            result.append({
                "name": row["name"],
                "post_count": row["post_count"],
                "title": row.get("title", ""),
                "description": row.get("description", ""),
            })
        return jsonify(result)

    # Fallback: aggregate post stats per subreddit in SQL (no per-sub comment JOINs)
    sub_stats = db.execute(
        f"SELECT [subreddit], COUNT(*) as post_count, "
        f"COALESCE(SUM([score]), 0) as total_score, "
        f"COUNT(DISTINCT [author]) as unique_authors "
        f"FROM [{posts_table}] GROUP BY [subreddit] ORDER BY post_count DESC"
    )

    result = []
    for row in sub_stats:
        result.append({
            "name": row["subreddit"],
            "post_count": row["post_count"],
            "total_score": row["total_score"],
            "unique_authors": row["unique_authors"],
        })
    return jsonify(result)


@blueprint.route("/api/subreddits/<subreddit_name>/stats", methods=["GET"])
def api_subreddit_stats(subreddit_name):
    """extract_by_dropdown: get detailed stats for one subreddit."""
    sub = subreddit_name
    posts_table = db.get_table_name(SITE, "posts")
    comments_table = db.get_table_name(SITE, "comments")
    if not posts_table:
        return jsonify({"error": "Subreddit not found"}), 404

    # Aggregate post stats in SQL
    stats_row = db.execute(
        f"SELECT COUNT(*) as post_count, COALESCE(SUM([score]), 0) as total_score, "
        f"COUNT(DISTINCT [author]) as post_authors "
        f"FROM [{posts_table}] WHERE [subreddit] = ?",
        (sub,), fetch="one"
    )
    if not stats_row or stats_row["post_count"] == 0:
        return jsonify({"error": "Subreddit not found"}), 404

    # Count comments using a subquery on post IDs (avoids full table JOIN)
    comment_count = 0
    if comments_table:
        cc = db.execute(
            f"SELECT COUNT(*) as cnt FROM [{comments_table}] "
            f"WHERE [post_id] IN (SELECT [id] FROM [{posts_table}] WHERE [subreddit] = ? LIMIT 10000)",
            (sub,), fetch="one"
        )
        comment_count = cc["cnt"] if cc else 0

    # Get flairs via SQL
    flair_rows = db.execute(
        f"SELECT [flair], COUNT(*) as cnt FROM [{posts_table}] "
        f"WHERE [subreddit] = ? AND [flair] IS NOT NULL AND [flair] != '' "
        f"GROUP BY [flair] ORDER BY cnt DESC LIMIT 5",
        (sub,)
    )
    top_flairs = {r["flair"]: r["cnt"] for r in flair_rows}

    return jsonify({
        "subreddit": sub,
        "post_count": stats_row["post_count"],
        "comment_count": comment_count,
        "total_score": stats_row["total_score"],
        "unique_authors": stats_row["post_authors"],
        "top_flairs": top_flairs,
        "avg_score": round(stats_row["total_score"] / stats_row["post_count"], 1),
    })


# ---------------------------------------------------------------------------
# API routes - search (search_by_query, search_by_semantic)
# ---------------------------------------------------------------------------

@blueprint.route("/api/search", methods=["GET"])
def api_search():
    """search_by_query: keyword search across posts."""
    q = (request.args.get("q") or "").strip().lower()
    if not q:
        return jsonify({"error": "Query parameter 'q' is required"}), 400
    sort = request.args.get("sort", "top")
    results = db.search(SITE, "posts", q, limit=50)
    return jsonify({"query": q, "count": len(results), "posts": results})


@blueprint.route("/api/search/semantic", methods=["GET"])
def api_search_semantic():
    """search_by_semantic: keyword-overlap semantic search across posts."""
    q = (request.args.get("q") or "").strip().lower()
    if not q:
        return jsonify({"error": "Query parameter 'q' is required"}), 400
    results = db.search(SITE, "posts", q, limit=50)
    return jsonify({"query": q, "count": len(results), "posts": results})


# ---------------------------------------------------------------------------
# API routes - users
# ---------------------------------------------------------------------------

@blueprint.route("/api/users/<username>", methods=["GET"])
def api_get_user(username):
    user = _get_user_by_username(username)
    if not user:
        return jsonify({"error": "User not found"}), 404
    posts_table = db.get_table_name(SITE, "posts")
    comments_table = db.get_table_name(SITE, "comments")
    post_stats = {"post_count": 0, "post_karma": 0}
    comment_stats = {"comment_count": 0, "comment_karma": 0}
    if posts_table:
        row = db.execute(
            f"SELECT COUNT(*) as cnt, COALESCE(SUM([score]), 0) as karma "
            f"FROM [{posts_table}] WHERE [author] = ?",
            (username,), fetch="one"
        )
        if row:
            post_stats = {"post_count": row["cnt"], "post_karma": row["karma"]}
    if comments_table:
        row = db.execute(
            f"SELECT COUNT(*) as cnt, COALESCE(SUM([score]), 0) as karma "
            f"FROM [{comments_table}] WHERE [author] = ?",
            (username,), fetch="one"
        )
        if row:
            comment_stats = {"comment_count": row["cnt"], "comment_karma": row["karma"]}
    return jsonify({**user, **post_stats, **comment_stats})


@blueprint.route("/api/login", methods=["POST"])
def api_login():
    """authenticate_by_form: API login endpoint."""
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    user = _get_user_by_username(username)
    if not user:
        return jsonify({"error": "User not found"}), 404
    stored_pw = user.get("password", "password")
    if password and password != stored_pw:
        return jsonify({"error": "Incorrect password"}), 401
    session["user_id"] = user["root_user_id"]
    return jsonify({"user_id": user["root_user_id"], "username": user["username"]})


@blueprint.route("/api/register", methods=["POST"])
def api_register():
    """register_by_form: API user registration."""
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    if not username:
        return jsonify({"error": "Username is required"}), 400
    if not password:
        return jsonify({"error": "Password is required"}), 400
    users = _load_users()
    if any(u["username"] == username for u in users):
        return jsonify({"error": "Username already taken"}), 409
    max_id = max((u["root_user_id"] for u in users), default=0)
    new_user = {
        "root_user_id": max_id + 100,
        "username": username,
        "karma": 0,
        "subscribed_subreddits": [],
        "cake_day": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "password": password,
        "saved_posts": [],
        "followed_users": [],
        "blocked_users": [],
    }
    users.append(new_user)
    _save_users(users)
    emit("signup", user_id=new_user["root_user_id"], site_name="forums",
         username=username, password=password, email="")
    session["user_id"] = new_user["root_user_id"]
    return jsonify({"user_id": new_user["root_user_id"], "username": username}), 201


# ---------------------------------------------------------------------------
# API routes - social: save, follow, join, share, report, block, message
# ---------------------------------------------------------------------------

@blueprint.route("/api/posts/<post_id>/save", methods=["POST"])
def api_save_post(post_id):
    """save_by_toggle: save/unsave a post for the current user."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    post = _get_post(post_id)
    if not post:
        return jsonify({"error": "Post not found"}), 404
    users = _load_users()
    u = next((u for u in users if u["root_user_id"] == user["root_user_id"]), None)
    saved = u.get("saved_posts", [])
    if post_id in saved:
        saved.remove(post_id)
        action = "unsaved"
    else:
        saved.append(post_id)
        action = "saved"
    u["saved_posts"] = saved
    _save_users(users)
    return jsonify({"action": action, "post_id": post_id, "saved_posts": saved})


@blueprint.route("/api/users/<username>/follow", methods=["POST"])
def api_follow_user(username):
    """follow_by_toggle: follow/unfollow another user."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    # Verify username exists as a post/comment author or registered user
    has_posts = db.count(SITE, "posts", where={"author": username})
    if not has_posts:
        target = _get_user_by_username(username)
        if not target:
            return jsonify({"error": "User not found"}), 404
    users = _load_users()
    me = next((u for u in users if u["root_user_id"] == user["root_user_id"]), None)
    followed = me.get("followed_users", [])
    if username in followed:
        followed.remove(username)
        action = "unfollowed"
    else:
        followed.append(username)
        action = "followed"
    me["followed_users"] = followed
    _save_users(users)
    return jsonify({"action": action, "username": username, "followed_users": followed})


@blueprint.route("/api/subreddits/<subreddit_name>/join", methods=["POST"])
def api_join_subreddit(subreddit_name):
    """join_by_toggle: join/leave a subreddit."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    sub = subreddit_name
    users = _load_users()
    me = next((u for u in users if u["root_user_id"] == user["root_user_id"]), None)
    subs = me.get("subscribed_subreddits", [])
    if sub in subs:
        subs.remove(sub)
        action = "left"
    else:
        subs.append(sub)
        action = "joined"
    me["subscribed_subreddits"] = subs
    _save_users(users)
    return jsonify({"action": action, "subreddit": sub, "subscribed_subreddits": subs})


@blueprint.route("/api/subreddits/<subreddit_name>/follow", methods=["POST"])
def api_follow_subreddit(subreddit_name):
    """follow_by_dropdown: follow a subreddit (alias for join)."""
    return api_join_subreddit(subreddit_name)


@blueprint.route("/api/posts/<post_id>/share", methods=["POST"])
def api_share_post(post_id):
    """share_by_dropdown: share a post via a chosen method."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    post = _get_post(post_id)
    if not post:
        return jsonify({"error": "Post not found"}), 404
    data = request.get_json(silent=True) or {}
    method = data.get("method", "copy_link")  # copy_link, crosspost, dm
    share_url = f"/sites/forums/post/{post_id}"
    result = {"post_id": post_id, "method": method, "share_url": share_url}
    if method == "crosspost":
        target_sub = data.get("target_subreddit", "")
        result["target_subreddit"] = target_sub
    elif method == "dm":
        target_user = data.get("target_user", "")
        result["target_user"] = target_user
        if target_user:
            # Actually create the DM
            messages = _load_messages()
            messages.append({
                "id": _next_message_id(),
                "from_username": user["username"],
                "to_username": target_user,
                "subject": f"Shared post: {post['title']}",
                "body": f"Check out this post: {share_url}",
                "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "read": False,
            })
            _save_messages(messages)
    return jsonify(result)


@blueprint.route("/api/report", methods=["POST"])
def api_report():
    """report_by_form: report a post or comment."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    data = request.get_json(silent=True) or {}
    target_type = data.get("target_type", "post")  # post or comment
    target_id = data.get("target_id", "")
    reason = (data.get("reason") or "").strip()
    description = (data.get("description") or "").strip()
    if not target_id:
        return jsonify({"error": "target_id is required"}), 400
    if not reason:
        return jsonify({"error": "reason is required"}), 400
    report = {
        "id": _next_report_id(),
        "reporter_username": user["username"],
        "target_type": target_type,
        "target_id": target_id,
        "reason": reason,
        "description": description,
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "pending",
    }
    reports = _load_reports()
    reports.append(report)
    _save_reports(reports)
    return jsonify(report), 201


@blueprint.route("/api/users/<username>/block", methods=["POST"])
def api_block_user(username):
    """block_by_toggle: block/unblock another user."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    # Verify username exists as a post/comment author or registered user
    has_posts = db.count(SITE, "posts", where={"author": username})
    if not has_posts:
        target = _get_user_by_username(username)
        if not target:
            return jsonify({"error": "User not found"}), 404
    users = _load_users()
    me = next((u for u in users if u["root_user_id"] == user["root_user_id"]), None)
    blocked = me.get("blocked_users", [])
    if username in blocked:
        blocked.remove(username)
        action = "unblocked"
    else:
        blocked.append(username)
        action = "blocked"
    me["blocked_users"] = blocked
    _save_users(users)
    return jsonify({"action": action, "username": username, "blocked_users": blocked})


@blueprint.route("/api/messages", methods=["GET"])
def api_list_messages():
    """List messages for the current user."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    messages = _load_messages()
    inbox = [m for m in messages if m["to_username"] == user["username"]]
    sent = [m for m in messages if m["from_username"] == user["username"]]
    return jsonify({"inbox": inbox, "sent": sent})


@blueprint.route("/api/messages", methods=["POST"])
def api_send_message():
    """message_from_free_text: send a direct message to another user."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    data = request.get_json(silent=True) or {}
    to_username = (data.get("to") or "").strip()
    subject = (data.get("subject") or "").strip()
    body = (data.get("body") or "").strip()
    if not to_username:
        return jsonify({"error": "'to' username is required"}), 400
    if not body:
        return jsonify({"error": "Message body is required"}), 400
    users = _load_users()
    target = next((u for u in users if u["username"] == to_username), None)
    if not target:
        return jsonify({"error": "Recipient not found"}), 404
    # Check if blocked
    me = next((u for u in users if u["root_user_id"] == user["root_user_id"]), None)
    if to_username in me.get("blocked_users", []):
        return jsonify({"error": "You have blocked this user"}), 403
    if user["username"] in target.get("blocked_users", []):
        return jsonify({"error": "This user has blocked you"}), 403
    msg = {
        "id": _next_message_id(),
        "from_username": user["username"],
        "to_username": to_username,
        "subject": subject or "(no subject)",
        "body": body,
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "read": False,
    }
    messages = _load_messages()
    messages.append(msg)
    _save_messages(messages)
    return jsonify(msg), 201


# ---------------------------------------------------------------------------
# API routes - stats
# ---------------------------------------------------------------------------

@blueprint.route("/api/stats", methods=["GET"])
def api_stats():
    """extract_by_semantic / extract_by_route: aggregate stats."""
    total_posts = db.count(SITE, "posts")
    total_comments = db.count(SITE, "comments")
    total_users = db.count(SITE, "users")
    subreddits = _get_subreddits()
    top_posts = _load_posts(sort="-score", limit=5)
    return jsonify({
        "total_posts": total_posts,
        "total_comments": total_comments,
        "total_users": total_users,
        "total_subreddits": len(subreddits),
        "subreddits": subreddits,
        "top_posts": top_posts,
    })

@blueprint.route("/api/export")
def api_export():
    """Export posts as JSON or CSV."""
    fmt = request.args.get("format", "json").lower()
    subreddit = request.args.get("subreddit", "").strip()
    sort = request.args.get("sort", "score")

    sort_col = "score" if sort in ("top", "score") else "created_utc"
    where = {"subreddit": subreddit} if subreddit else None
    posts = _load_posts(where=where, sort=f"-{sort_col}", limit=500)

    if fmt == "csv":
        lines = ["id,title,author,subreddit,score,num_comments,created_utc"]
        for p in posts:
            title = str(p.get("title", "")).replace('"', '""')
            lines.append(f'{p.get("id", "")},"{title}","{p.get("author", "")}","{p.get("subreddit", "")}",{p.get("score", 0)},{p.get("num_comments", 0)},"{p.get("created_utc", "")}"')
        return Response("\n".join(lines), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=posts.csv"})
    return jsonify(posts)
