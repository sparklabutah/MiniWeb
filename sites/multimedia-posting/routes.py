"""PixShare -- multimedia social media platform (Instagram/Twitter style).

Reads realistic social-media data (users, posts, comments, stories, follows)
from the shared data-sources directory and serves a fully interactive Flask UI
with HTML pages and JSON API endpoints.

Supports 29 macros: navigate_by_dropdown, navigate_by_route, search_by_query,
search_by_semantic, search_by_checkbox, filter_by_radio, sort_by_dropdown,
extract_by_semantic, extract_by_dropdown, extract_by_route, create_from_free_text,
edit_by_form, delete_from_table, post_by_query, post_from_free_text,
select_by_dropdown, configure_by_toggle, play_by_dropdown, play_by_playback,
export_by_dropdown, upload_by_upload, react_by_toggle, follow_by_dropdown,
follow_by_toggle, subscribe_by_toggle, share_by_dropdown, save_by_toggle,
report_by_form, block_by_toggle
"""
import csv
import io
import json
import pathlib
import re
import uuid
from collections import Counter
from datetime import datetime

from flask import (
    Blueprint, Response, abort, jsonify, redirect, render_template, request,
    session, url_for,
)
from app import db
from app.events import emit

SITE = "multimedia-posting"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "multimedia-posting",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _load_posts():
    return db.query(SITE, "posts")

def _save_posts(posts):
    db.save_collection(SITE, "posts", posts)

def _load_comments():
    return db.query(SITE, "comments")

def _save_comments(comments):
    db.save_collection(SITE, "comments", comments)

def _load_stories():
    return db.query(SITE, "stories")

def _save_stories(stories):
    db.save_collection(SITE, "stories", stories)

def _load_follows():
    return db.query(SITE, "follows")

def _save_follows(follows):
    db.save_collection(SITE, "follows", follows)

def _load_users():
    return db.query(SITE, "users")

def _save_users(users):
    db.save_collection(SITE, "users", users)


def _get_user(user_id):
    return db.get_item(SITE, "users", user_id)


def _get_current_user():
    if "user_id" in session:
        u = _get_user(session["user_id"])
        if u:
            return u
        # global autologin stores int 1, but this site's user ids are strings
        # (mp-u-001...), so it never resolved — the owner-gated actions
        # (delete etc.) were unreachable in a normal session
        return _get_user("mp-u-001")
    return None


def _get_browsing_user():
    """Return logged-in user, or fall back to first user for browse-only."""
    user = _get_current_user()
    if user:
        return user, True
    return _get_user("mp-u-001"), False


def _get_following_ids(user_id):
    """Return set of user IDs that user_id follows."""
    follows = db.query(SITE, "follows", where={"follower_id": user_id})
    return {f["following_id"] for f in follows}


def _get_follower_ids(user_id):
    """Return set of user IDs that follow user_id."""
    follows = db.query(SITE, "follows", where={"following_id": user_id})
    return {f["follower_id"] for f in follows}


def _enrich_post(post, users_map, comments=None):
    """Attach author info to a post."""
    author = users_map.get(post["author_id"], {})
    post["author"] = author
    if comments is not None:
        post["comments_list"] = [c for c in comments if c["post_id"] == post["id"]]
        for c in post["comments_list"]:
            c["author"] = users_map.get(c["author_id"], {})
    return post


def _users_map():
    return {u["id"]: u for u in _load_users()}


def _now_iso():
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _next_id(prefix, items):
    nums = []
    for item in items:
        try:
            nums.append(int(item["id"].split("-")[-1]))
        except (ValueError, KeyError):
            pass
    return f"{prefix}-{max(nums, default=0) + 1:03d}"


# ---------------------------------------------------------------------------
# HTML Routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    """Feed -- posts from followed users, reverse chronological."""
    user, logged_in = _get_browsing_user()
    following_ids = _get_following_ids(user["id"])
    # Include own posts in feed
    feed_ids = following_ids | {user["id"]}
    posts = _load_posts()
    comments = _load_comments()
    um = _users_map()
    feed = [_enrich_post(p, um, comments) for p in posts if p["author_id"] in feed_ids]
    feed.sort(key=lambda p: p.get("created_at", ""), reverse=True)
    # Active stories from followed users
    stories = _load_stories()
    active_stories = [s for s in stories if s.get("is_active") and s["author_id"] in feed_ids]
    for s in active_stories:
        s["author"] = um.get(s["author_id"], {})
    # Deduplicate to one per author for the story ring
    seen_authors = set()
    story_ring = []
    for s in sorted(active_stories, key=lambda x: x.get("created_at", ""), reverse=True):
        if s["author_id"] not in seen_authors:
            seen_authors.add(s["author_id"])
            story_ring.append(s)
    return render_template("multimedia-posting/index.html",
                           user=user, posts=feed, stories=story_ring,
                           logged_in=logged_in)


@blueprint.route("/explore")
def explore():
    """Explore -- all posts, newest first. Supports search, type filter, tag filter, sort."""
    user, logged_in = _get_browsing_user()
    posts = _load_posts()
    comments = _load_comments()
    um = _users_map()
    # Apply optional filters
    post_type = request.args.get("type")
    tag = request.args.get("tag")
    q = request.args.get("q", "").strip().lower()
    sort_by = request.args.get("sort", "newest")
    if post_type:
        posts = [p for p in posts if p.get("type") == post_type]
    if tag:
        posts = [p for p in posts if tag.lower() in [t.lower() for t in p.get("tags", [])]]
    if q:
        posts = [p for p in posts if q in p.get("caption", "").lower()
                 or any(q in t.lower() for t in p.get("tags", []))
                 or q in p.get("location", "").lower()]
    enriched = [_enrich_post(p, um, comments) for p in posts]

    # Sort (sort_by_dropdown)
    if sort_by == "oldest":
        enriched.sort(key=lambda p: p.get("created_at", ""))
    elif sort_by == "most_liked":
        enriched.sort(key=lambda p: p.get("likes_count", 0), reverse=True)
    elif sort_by == "most_commented":
        enriched.sort(key=lambda p: p.get("comments_count", 0), reverse=True)
    else:  # newest
        enriched.sort(key=lambda p: p.get("created_at", ""), reverse=True)

    # Collect all tags for sidebar
    all_tags = Counter()
    for p in _load_posts():
        for t in p.get("tags", []):
            all_tags[t] += 1
    popular_tags = all_tags.most_common(20)
    return render_template("multimedia-posting/explore.html",
                           user=user, posts=enriched, popular_tags=popular_tags,
                           current_type=post_type, current_tag=tag, current_q=q,
                           current_sort=sort_by, logged_in=logged_in)


@blueprint.route("/profile/<user_id>")
def profile(user_id):
    """User profile page."""
    profile_user = _get_user(user_id)
    if not profile_user:
        abort(404)
    current_user, logged_in = _get_browsing_user()
    posts = _load_posts()
    comments = _load_comments()
    um = _users_map()
    user_posts = [_enrich_post(p, um, comments) for p in posts if p["author_id"] == user_id]
    user_posts.sort(key=lambda p: p.get("created_at", ""), reverse=True)
    follower_ids = _get_follower_ids(user_id)
    following_ids = _get_following_ids(user_id)
    is_following = current_user["id"] in _get_follower_ids(user_id)
    is_own_profile = current_user["id"] == user_id
    return render_template("multimedia-posting/profile.html",
                           user=current_user, profile_user=profile_user,
                           posts=user_posts, follower_count=len(follower_ids),
                           following_count=len(following_ids),
                           is_following=is_following, is_own_profile=is_own_profile,
                           logged_in=logged_in)


@blueprint.route("/post/<post_id>")
def post_detail(post_id):
    """Single post detail with comments."""
    user, logged_in = _get_browsing_user()
    posts = _load_posts()
    post = next((p for p in posts if p["id"] == post_id), None)
    if not post:
        abort(404)
    comments = _load_comments()
    um = _users_map()
    _enrich_post(post, um, comments)
    # Check if user saved/liked this post
    saved_posts = session.get("saved_posts", [])
    liked_posts = session.get("liked_posts", [])
    is_saved = post_id in saved_posts
    is_liked = post_id in liked_posts
    return render_template("multimedia-posting/post_detail.html",
                           user=user, post=post, logged_in=logged_in,
                           is_saved=is_saved, is_liked=is_liked)


@blueprint.route("/stories")
def stories_page():
    """Stories carousel page."""
    user, logged_in = _get_browsing_user()
    stories = _load_stories()
    um = _users_map()
    active = [s for s in stories if s.get("is_active")]
    active.sort(key=lambda s: s.get("created_at", ""), reverse=True)
    for s in active:
        s["author"] = um.get(s["author_id"], {})
    # Group by author
    grouped = {}
    for s in active:
        aid = s["author_id"]
        if aid not in grouped:
            grouped[aid] = {"author": s["author"], "stories": []}
        grouped[aid]["stories"].append(s)
    return render_template("multimedia-posting/stories.html",
                           user=user, story_groups=grouped, logged_in=logged_in)


@blueprint.route("/create")
def create_page():
    """Create new post form."""
    user, logged_in = _get_browsing_user()
    return render_template("multimedia-posting/create.html",
                           user=user, logged_in=logged_in)


@blueprint.route("/settings")
def settings_page():
    """User settings page (configure_by_toggle)."""
    user, logged_in = _get_browsing_user()
    return render_template("multimedia-posting/settings.html",
                           user=user, logged_in=logged_in)


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("multimedia-posting/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user:
        return render_template("multimedia-posting/login.html",
                               error="User not found")
    stored_pw = user.get("password", "password")
    if password and password != stored_pw:
        return render_template("multimedia-posting/login.html", error="Invalid password")
    session["user_id"] = user["id"]
    emit("signup", user_id=user["id"], site_name="multimedia-posting", username=request.form.get("username", ""), password=request.form.get("password", ""), email="")
    return redirect(url_for("multimedia-posting.index"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("multimedia-posting.index"))


# ---------------------------------------------------------------------------
# API Routes -- Posts
# ---------------------------------------------------------------------------

@blueprint.route("/api/posts", methods=["GET"])
def api_posts_list():
    """GET feed posts with filters. Query params: type, tag, q, user, feed, sort,
    date_from, date_to, saved, has_video."""
    user, _ = _get_browsing_user()
    posts = _load_posts()
    comments = _load_comments()
    um = _users_map()

    # Feed mode: only followed users + self
    if request.args.get("feed") == "true":
        following_ids = _get_following_ids(user["id"])
        feed_ids = following_ids | {user["id"]}
        posts = [p for p in posts if p["author_id"] in feed_ids]

    # Filters
    post_type = request.args.get("type")
    tag = request.args.get("tag")
    q = request.args.get("q", "").strip().lower()
    author_id = request.args.get("user")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    sort_by = request.args.get("sort", "newest")
    has_video = request.args.get("has_video")

    # Checkbox-style multi-type filter (search_by_checkbox)
    types_param = request.args.getlist("types")
    if types_param:
        posts = [p for p in posts if p.get("type") in types_param]
    elif post_type:
        posts = [p for p in posts if p.get("type") == post_type]

    if tag:
        posts = [p for p in posts if tag.lower() in [t.lower() for t in p.get("tags", [])]]
    if q:
        posts = [p for p in posts if q in p.get("caption", "").lower()
                 or any(q in t.lower() for t in p.get("tags", []))
                 or q in p.get("location", "").lower()]
    if author_id:
        posts = [p for p in posts if p["author_id"] == author_id]
    if date_from:
        posts = [p for p in posts if p.get("created_at", "") >= date_from]
    if date_to:
        posts = [p for p in posts if p.get("created_at", "") <= date_to]
    if has_video == "true":
        posts = [p for p in posts if p.get("type") == "video" or p.get("video_url")]

    # Sort (sort_by_dropdown)
    if sort_by == "oldest":
        posts.sort(key=lambda p: p.get("created_at", ""))
    elif sort_by == "most_liked":
        posts.sort(key=lambda p: p.get("likes_count", 0), reverse=True)
    elif sort_by == "most_commented":
        posts.sort(key=lambda p: p.get("comments_count", 0), reverse=True)
    else:
        posts.sort(key=lambda p: p.get("created_at", ""), reverse=True)

    # Enrich
    result = []
    for p in posts:
        post_comments = [c for c in comments if c["post_id"] == p["id"]]
        for c in post_comments:
            c["author"] = um.get(c["author_id"], {})
        author = um.get(p["author_id"], {})
        result.append({**p, "author": author, "comments_list": post_comments})

    return jsonify(result)


@blueprint.route("/api/posts", methods=["POST"])
def api_posts_create():
    """Create a new post (create_from_free_text, post_from_free_text)."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    data = request.get_json(silent=True) or {}
    posts = _load_posts()
    new_id = _next_id("post", posts)
    caption = data.get("caption", "").strip()
    # Extract hashtags from caption
    tags = data.get("tags", [])
    if not tags:
        tags = re.findall(r"#(\w+)", caption)
    post = {
        "id": new_id,
        "author_id": user["id"],
        "type": data.get("type", "photo"),
        "image_url": data.get("image_url", f"https://pixshare.io/photos/{new_id}.jpg"),
        "caption": caption,
        "location": data.get("location", ""),
        "likes_count": 0,
        "comments_count": 0,
        "created_at": _now_iso(),
        "tags": tags,
    }
    if data.get("additional_images"):
        post["additional_images"] = data["additional_images"]
    if data.get("video_url"):
        post["video_url"] = data["video_url"]
    posts.append(post)
    _save_posts(posts)
    return jsonify(post), 201


@blueprint.route("/api/posts/<post_id>", methods=["GET"])
def api_post_get(post_id):
    """Get single post with comments (extract_by_route)."""
    posts = _load_posts()
    post = next((p for p in posts if p["id"] == post_id), None)
    if not post:
        return jsonify({"error": "Post not found"}), 404
    comments = _load_comments()
    um = _users_map()
    post_comments = [c for c in comments if c["post_id"] == post_id]
    for c in post_comments:
        c["author"] = um.get(c["author_id"], {})
    author = um.get(post["author_id"], {})
    return jsonify({**post, "author": author, "comments_list": post_comments})


@blueprint.route("/api/posts/<post_id>", methods=["PUT"])
def api_post_update(post_id):
    """Edit a post (edit_by_form)."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    posts = _load_posts()
    post = next((p for p in posts if p["id"] == post_id), None)
    if not post:
        return jsonify({"error": "Post not found"}), 404
    if post["author_id"] != user["id"]:
        return jsonify({"error": "Forbidden"}), 403
    data = request.get_json(silent=True) or {}
    for key in ["caption", "location", "tags", "type"]:
        if key in data:
            post[key] = data[key]
    _save_posts(posts)
    return jsonify(post)


@blueprint.route("/api/posts/<post_id>", methods=["DELETE"])
def api_post_delete(post_id):
    """Delete a post (delete_from_table)."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    posts = _load_posts()
    post = next((p for p in posts if p["id"] == post_id), None)
    if not post:
        return jsonify({"error": "Post not found"}), 404
    if post["author_id"] != user["id"]:
        return jsonify({"error": "Forbidden"}), 403
    posts = [p for p in posts if p["id"] != post_id]
    _save_posts(posts)
    # Also remove associated comments
    comments = _load_comments()
    comments = [c for c in comments if c["post_id"] != post_id]
    _save_comments(comments)
    return jsonify({"status": "deleted", "id": post_id})


@blueprint.route("/api/posts/<post_id>/like", methods=["POST"])
def api_post_like(post_id):
    """Toggle like on a post (react_by_toggle)."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    posts = _load_posts()
    post = next((p for p in posts if p["id"] == post_id), None)
    if not post:
        return jsonify({"error": "Post not found"}), 404
    # Track likes in session
    liked_posts = session.get("liked_posts", [])
    if post_id in liked_posts:
        liked_posts.remove(post_id)
        post["likes_count"] = max(0, post.get("likes_count", 1) - 1)
        action = "unliked"
    else:
        liked_posts.append(post_id)
        post["likes_count"] = post.get("likes_count", 0) + 1
        action = "liked"
    session["liked_posts"] = liked_posts
    _save_posts(posts)
    return jsonify({"status": action, "likes_count": post["likes_count"],
                    "post_id": post_id})


@blueprint.route("/api/posts/<post_id>/save", methods=["POST"])
def api_post_save(post_id):
    """Toggle save on a post (save_by_toggle)."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    posts = _load_posts()
    post = next((p for p in posts if p["id"] == post_id), None)
    if not post:
        return jsonify({"error": "Post not found"}), 404
    saved_posts = session.get("saved_posts", [])
    if post_id in saved_posts:
        saved_posts.remove(post_id)
        action = "unsaved"
    else:
        saved_posts.append(post_id)
        action = "saved"
    session["saved_posts"] = saved_posts
    return jsonify({"status": action, "post_id": post_id,
                    "saved_posts": saved_posts})


@blueprint.route("/api/posts/<post_id>/share", methods=["POST"])
def api_post_share(post_id):
    """Share a post via selected method (share_by_dropdown)."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    posts = _load_posts()
    post = next((p for p in posts if p["id"] == post_id), None)
    if not post:
        return jsonify({"error": "Post not found"}), 404
    data = request.get_json(silent=True) or {}
    method = data.get("method", "link")  # link, dm, email, embed
    recipient = data.get("recipient", "")
    share_record = {
        "id": str(uuid.uuid4())[:8],
        "post_id": post_id,
        "shared_by": user["id"],
        "method": method,
        "recipient": recipient,
        "shared_at": _now_iso(),
    }
    # Store shares on user in session
    shares = session.get("shares", [])
    shares.append(share_record)
    session["shares"] = shares
    return jsonify(share_record), 201


@blueprint.route("/api/posts/<post_id>/report", methods=["POST"])
def api_post_report(post_id):
    """Report a post (report_by_form)."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    posts = _load_posts()
    post = next((p for p in posts if p["id"] == post_id), None)
    if not post:
        return jsonify({"error": "Post not found"}), 404
    data = request.get_json(silent=True) or {}
    reason = data.get("reason", "").strip()
    details = data.get("details", "").strip()
    if not reason:
        return jsonify({"error": "Reason is required"}), 400
    report = {
        "id": str(uuid.uuid4())[:8],
        "post_id": post_id,
        "reported_by": user["id"],
        "reason": reason,
        "details": details,
        "reported_at": _now_iso(),
        "status": "pending",
    }
    reports = session.get("reports", [])
    reports.append(report)
    session["reports"] = reports
    return jsonify(report), 201


# ---------------------------------------------------------------------------
# API Routes -- Comments
# ---------------------------------------------------------------------------

@blueprint.route("/api/posts/<post_id>/comments", methods=["GET"])
def api_post_comments_list(post_id):
    """Get comments for a post."""
    post_comments = db.query(SITE, "comments", where={"post_id": post_id}, sort="created_at")
    um = _users_map()
    for c in post_comments:
        c["author"] = um.get(c["author_id"], {})
    return jsonify(post_comments)


@blueprint.route("/api/posts/<post_id>/comments", methods=["POST"])
def api_post_comments_add(post_id):
    """Add a comment to a post (post_by_query, post_from_free_text)."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    posts = _load_posts()
    post = next((p for p in posts if p["id"] == post_id), None)
    if not post:
        return jsonify({"error": "Post not found"}), 404
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "Comment text required"}), 400
    comments = _load_comments()
    new_id = _next_id("cmt", comments)
    comment = {
        "id": new_id,
        "post_id": post_id,
        "author_id": user["id"],
        "text": text,
        "likes_count": 0,
        "created_at": _now_iso(),
    }
    if data.get("reply_to"):
        comment["reply_to"] = data["reply_to"]
    comments.append(comment)
    _save_comments(comments)
    # Update comment count on post
    post["comments_count"] = post.get("comments_count", 0) + 1
    _save_posts(posts)
    um = _users_map()
    comment["author"] = um.get(user["id"], {})
    return jsonify(comment), 201


@blueprint.route("/api/comments/<comment_id>", methods=["DELETE"])
def api_comment_delete(comment_id):
    """Delete a comment (owner only)."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    comments = _load_comments()
    comment = next((c for c in comments if c["id"] == comment_id), None)
    if not comment:
        return jsonify({"error": "Comment not found"}), 404
    if comment["author_id"] != user["id"]:
        return jsonify({"error": "Forbidden"}), 403
    post_id = comment["post_id"]
    comments = [c for c in comments if c["id"] != comment_id]
    _save_comments(comments)
    # Update comment count
    posts = _load_posts()
    post = next((p for p in posts if p["id"] == post_id), None)
    if post:
        post["comments_count"] = max(0, post.get("comments_count", 1) - 1)
        _save_posts(posts)
    return jsonify({"status": "deleted", "id": comment_id})


# ---------------------------------------------------------------------------
# API Routes -- Stories
# ---------------------------------------------------------------------------

@blueprint.route("/api/stories", methods=["GET"])
def api_stories_list():
    """Get active stories, optionally filtered by user."""
    stories = _load_stories()
    um = _users_map()
    author_id = request.args.get("user")
    active_only = request.args.get("active", "true").lower() == "true"
    if active_only:
        stories = [s for s in stories if s.get("is_active")]
    if author_id:
        stories = [s for s in stories if s["author_id"] == author_id]
    stories.sort(key=lambda s: s.get("created_at", ""), reverse=True)
    for s in stories:
        s["author"] = um.get(s["author_id"], {})
    return jsonify(stories)


@blueprint.route("/api/stories", methods=["POST"])
def api_stories_create():
    """Create a new story."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    data = request.get_json(silent=True) or {}
    stories = _load_stories()
    new_id = _next_id("story", stories)
    story = {
        "id": new_id,
        "author_id": user["id"],
        "type": data.get("type", "photo"),
        "media_url": data.get("media_url", f"https://pixshare.io/stories/{new_id}.jpg"),
        "caption": data.get("caption", ""),
        "views_count": 0,
        "created_at": _now_iso(),
        "expires_at": data.get("expires_at", ""),
        "is_active": True,
    }
    stories.append(story)
    _save_stories(stories)
    return jsonify(story), 201


@blueprint.route("/api/stories/<story_id>/play", methods=["POST"])
def api_story_play(story_id):
    """Record a story view / play (play_by_playback)."""
    stories = _load_stories()
    story = next((s for s in stories if s["id"] == story_id), None)
    if not story:
        return jsonify({"error": "Story not found"}), 404
    story["views_count"] = story.get("views_count", 0) + 1
    _save_stories(stories)
    return jsonify({"status": "played", "story_id": story_id,
                    "views_count": story["views_count"]})


# ---------------------------------------------------------------------------
# API Routes -- Users
# ---------------------------------------------------------------------------

@blueprint.route("/api/users/<user_id>/follow", methods=["POST"])
def api_follow_toggle(user_id):
    """Toggle follow on a user (follow_by_toggle)."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    if user["id"] == user_id:
        return jsonify({"error": "Cannot follow yourself"}), 400
    target = _get_user(user_id)
    if not target:
        return jsonify({"error": "User not found"}), 404
    follows = _load_follows()
    existing = next((f for f in follows
                     if f["follower_id"] == user["id"] and f["following_id"] == user_id), None)
    if existing:
        follows = [f for f in follows
                   if not (f["follower_id"] == user["id"] and f["following_id"] == user_id)]
        action = "unfollowed"
    else:
        new_id = _next_id("fol", follows)
        follows.append({
            "id": new_id,
            "follower_id": user["id"],
            "following_id": user_id,
            "created_at": _now_iso(),
        })
        action = "followed"
    _save_follows(follows)
    return jsonify({"status": action, "user_id": user_id,
                    "follower_count": len([f for f in follows if f["following_id"] == user_id])})


@blueprint.route("/api/users/<user_id>/block", methods=["POST"])
def api_block_toggle(user_id):
    """Toggle block on a user (block_by_toggle)."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    if user["id"] == user_id:
        return jsonify({"error": "Cannot block yourself"}), 400
    target = _get_user(user_id)
    if not target:
        return jsonify({"error": "User not found"}), 404
    blocked = session.get("blocked_users", [])
    if user_id in blocked:
        blocked.remove(user_id)
        action = "unblocked"
    else:
        blocked.append(user_id)
        action = "blocked"
    session["blocked_users"] = blocked
    return jsonify({"status": action, "user_id": user_id,
                    "blocked_users": blocked})


@blueprint.route("/api/users/<user_id>/subscribe", methods=["POST"])
def api_subscribe_toggle(user_id):
    """Toggle notifications subscription for a user (subscribe_by_toggle)."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    target = _get_user(user_id)
    if not target:
        return jsonify({"error": "User not found"}), 404
    subscribed = session.get("subscribed_users", [])
    if user_id in subscribed:
        subscribed.remove(user_id)
        action = "unsubscribed"
    else:
        subscribed.append(user_id)
        action = "subscribed"
    session["subscribed_users"] = subscribed
    return jsonify({"status": action, "user_id": user_id,
                    "subscribed_users": subscribed})


@blueprint.route("/api/users/<user_id>", methods=["GET"])
def api_user_get(user_id):
    """Get user profile (extract_by_route)."""
    user = _get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    follower_ids = _get_follower_ids(user_id)
    following_ids = _get_following_ids(user_id)
    posts = _load_posts()
    user_posts = [p for p in posts if p["author_id"] == user_id]
    return jsonify({
        **user,
        "follower_count": len(follower_ids),
        "following_count": len(following_ids),
        "post_count": len(user_posts),
    })


@blueprint.route("/api/users", methods=["GET"])
def api_users_list():
    """List all users."""
    users = _load_users()
    return jsonify(users)


@blueprint.route("/api/users/follow-by-dropdown", methods=["POST"])
def api_follow_by_dropdown():
    """Follow a user selected from a dropdown (follow_by_dropdown).
    Expects JSON: {"user_id": "<id>"}
    """
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    data = request.get_json(silent=True) or {}
    target_id = data.get("user_id", "").strip()
    if not target_id:
        return jsonify({"error": "user_id required"}), 400
    if user["id"] == target_id:
        return jsonify({"error": "Cannot follow yourself"}), 400
    target = _get_user(target_id)
    if not target:
        return jsonify({"error": "User not found"}), 404
    follows = _load_follows()
    existing = next((f for f in follows
                     if f["follower_id"] == user["id"] and f["following_id"] == target_id), None)
    if not existing:
        new_id = _next_id("fol", follows)
        follows.append({
            "id": new_id,
            "follower_id": user["id"],
            "following_id": target_id,
            "created_at": _now_iso(),
        })
        _save_follows(follows)
    return jsonify({"status": "followed", "user_id": target_id,
                    "follower_count": len([f for f in follows if f["following_id"] == target_id])})


# ---------------------------------------------------------------------------
# API Routes -- Search
# ---------------------------------------------------------------------------

@blueprint.route("/api/search")
def api_search():
    """Search posts and users (search_by_query). Query param: q."""
    q = request.args.get("q", "").strip().lower()
    if not q:
        return jsonify({"posts": [], "users": []})
    posts = _load_posts()
    users = _load_users()
    um = {u["id"]: u for u in users}
    matched_posts = []
    for p in posts:
        score = 0
        caption = p.get("caption", "").lower()
        tags = [t.lower() for t in p.get("tags", [])]
        location = p.get("location", "").lower()
        if q in caption:
            score += 2
        if any(q in t for t in tags):
            score += 3
        if q in location:
            score += 1
        if score > 0:
            matched_posts.append({**p, "author": um.get(p["author_id"], {}), "_score": score})
    matched_posts.sort(key=lambda p: p["_score"], reverse=True)
    for p in matched_posts:
        p.pop("_score", None)

    matched_users = []
    for u in users:
        if (q in u.get("username", "").lower()
                or q in u.get("display_name", "").lower()
                or q in u.get("bio", "").lower()):
            matched_users.append(u)

    return jsonify({"posts": matched_posts[:20], "users": matched_users[:10]})


@blueprint.route("/api/search/semantic")
def api_search_semantic():
    """Semantic search -- multi-word fuzzy matching across posts (search_by_semantic)."""
    q = request.args.get("q", "").strip().lower()
    if not q:
        return jsonify([])
    words = q.split()
    posts = _load_posts()
    um = _users_map()
    scored = []
    for p in posts:
        text = f"{p.get('caption','')} {' '.join(p.get('tags',[]))} {p.get('location','')}".lower()
        score = sum(1 for w in words if w in text)
        if score > 0:
            scored.append(({**p, "author": um.get(p["author_id"], {})}, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return jsonify([item[0] for item in scored[:20]])


# ---------------------------------------------------------------------------
# API Routes -- Stats & Export
# ---------------------------------------------------------------------------

@blueprint.route("/api/stats")
def api_stats():
    """Platform statistics (extract_by_dropdown when filtered by type)."""
    posts = _load_posts()
    users = _load_users()
    comments = _load_comments()
    stories = _load_stories()
    follows = _load_follows()

    # Optional type filter for extract_by_dropdown
    filter_type = request.args.get("type")
    if filter_type:
        filtered_posts = [p for p in posts if p.get("type") == filter_type]
    else:
        filtered_posts = posts

    # Type breakdown
    type_counts = Counter(p.get("type", "unknown") for p in posts)
    # Tag frequency
    tag_counts = Counter()
    for p in filtered_posts:
        for t in p.get("tags", []):
            tag_counts[t] += 1
    # Most liked
    top_posts = sorted(filtered_posts, key=lambda p: p.get("likes_count", 0), reverse=True)[:5]
    um = _users_map()
    for p in top_posts:
        p["author"] = um.get(p["author_id"], {})
    # Most active users by post count
    user_post_counts = Counter(p["author_id"] for p in filtered_posts)
    top_users = []
    for uid, count in user_post_counts.most_common(5):
        u = um.get(uid, {})
        top_users.append({"user": u, "post_count": count})
    return jsonify({
        "total_posts": len(filtered_posts),
        "total_users": len(users),
        "total_comments": len(comments),
        "total_stories": len(stories),
        "total_follows": len(follows),
        "active_stories": len([s for s in stories if s.get("is_active")]),
        "post_types": dict(type_counts),
        "top_tags": tag_counts.most_common(15),
        "top_posts": top_posts,
        "top_users": top_users,
    })


@blueprint.route("/api/export", methods=["GET"])
def api_export():
    """Export posts as CSV or JSON (export_by_dropdown).
    Query params: format=csv|json, type=photo|video|carousel, user=<user_id>
    """
    posts = _load_posts()
    fmt = request.args.get("format", "json").lower()
    filter_type = request.args.get("type")
    filter_user = request.args.get("user")

    if filter_type:
        posts = [p for p in posts if p.get("type") == filter_type]
    if filter_user:
        posts = [p for p in posts if p["author_id"] == filter_user]

    if fmt == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "author_id", "type", "caption", "location",
                         "likes_count", "comments_count", "created_at", "tags"])
        for p in posts:
            writer.writerow([
                p["id"], p["author_id"], p.get("type", ""),
                p.get("caption", ""), p.get("location", ""),
                p.get("likes_count", 0), p.get("comments_count", 0),
                p.get("created_at", ""),
                "; ".join(p.get("tags", [])),
            ])
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=pixshare_posts.csv"},
        )
    return jsonify(posts)


# ---------------------------------------------------------------------------
# API Routes -- Upload
# ---------------------------------------------------------------------------

@blueprint.route("/api/upload", methods=["POST"])
def api_upload():
    """Upload media file (upload_by_upload). Returns a simulated media URL."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    uploaded = request.files["file"]
    if not uploaded.filename:
        return jsonify({"error": "Empty filename"}), 400
    content = uploaded.read()
    file_id = str(uuid.uuid4())[:8]
    result = {
        "id": file_id,
        "filename": uploaded.filename,
        "size": len(content),
        "media_url": f"https://pixshare.io/uploads/{file_id}_{uploaded.filename}",
        "uploaded_at": _now_iso(),
        "uploaded_by": user["id"],
    }
    uploads = session.get("uploads", [])
    uploads.append(result)
    session["uploads"] = uploads
    return jsonify(result), 201


# ---------------------------------------------------------------------------
# API Routes -- Settings (configure_by_toggle)
# ---------------------------------------------------------------------------

@blueprint.route("/api/settings", methods=["GET"])
def api_settings_get():
    """Get current user settings."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    settings = session.get("user_settings", {
        "notifications_enabled": True,
        "private_account": False,
        "show_activity_status": True,
        "allow_sharing": True,
        "dark_mode": False,
    })
    return jsonify(settings)


@blueprint.route("/api/settings", methods=["PUT"])
def api_settings_update():
    """Update user settings (configure_by_toggle)."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    data = request.get_json(silent=True) or {}
    settings = session.get("user_settings", {
        "notifications_enabled": True,
        "private_account": False,
        "show_activity_status": True,
        "allow_sharing": True,
        "dark_mode": False,
    })
    for key in ["notifications_enabled", "private_account", "show_activity_status",
                "allow_sharing", "dark_mode"]:
        if key in data:
            settings[key] = bool(data[key])
    session["user_settings"] = settings
    return jsonify(settings)


# ---------------------------------------------------------------------------
# API Routes -- Play media (play_by_dropdown)
# ---------------------------------------------------------------------------

@blueprint.route("/api/posts/<post_id>/play", methods=["POST"])
def api_post_play(post_id):
    """Play a video post (play_by_dropdown). Select quality via dropdown."""
    posts = _load_posts()
    post = next((p for p in posts if p["id"] == post_id), None)
    if not post:
        return jsonify({"error": "Post not found"}), 404
    data = request.get_json(silent=True) or {}
    quality = data.get("quality", "720p")  # 360p, 480p, 720p, 1080p
    return jsonify({
        "status": "playing",
        "post_id": post_id,
        "quality": quality,
        "stream_url": f"https://pixshare.io/stream/{post_id}?q={quality}",
    })


# ---------------------------------------------------------------------------
# API Routes -- Login
# ---------------------------------------------------------------------------

@blueprint.route("/api/login", methods=["POST"])
def api_login():
    """Login via API."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user:
        return jsonify({"error": "User not found"}), 401
    session["user_id"] = user["id"]
    return jsonify({"user_id": user["id"], "username": user["username"],
                    "display_name": user["display_name"]})


# ---------------------------------------------------------------------------
# API Routes -- Saved posts, shares
# ---------------------------------------------------------------------------

@blueprint.route("/api/saved", methods=["GET"])
def api_saved_posts():
    """List saved posts for current user."""
    saved_ids = session.get("saved_posts", [])
    posts = _load_posts()
    um = _users_map()
    saved = []
    for p in posts:
        if p["id"] in saved_ids:
            saved.append({**p, "author": um.get(p["author_id"], {})})
    return jsonify(saved)


@blueprint.route("/api/shares", methods=["GET"])
def api_shares():
    """List share records for current user."""
    shares = session.get("shares", [])
    return jsonify(shares)


@blueprint.route("/api/uploads", methods=["GET"])
def api_uploads():
    """List uploads for current user."""
    uploads = session.get("uploads", [])
    return jsonify(uploads)


@blueprint.route("/api/blocked", methods=["GET"])
def api_blocked():
    """List blocked user IDs for current user."""
    blocked = session.get("blocked_users", [])
    return jsonify(blocked)


@blueprint.route("/api/subscriptions", methods=["GET"])
def api_subscriptions():
    """List subscribed user IDs for current user."""
    subscribed = session.get("subscribed_users", [])
    return jsonify(subscribed)


@blueprint.route("/api/reports", methods=["GET"])
def api_reports():
    """List reports filed by current user."""
    reports = session.get("reports", [])
    return jsonify(reports)


# ---------------------------------------------------------------------------
# API Routes -- Post types listing (navigate_by_dropdown)
# ---------------------------------------------------------------------------

@blueprint.route("/api/post-types", methods=["GET"])
def api_post_types():
    """Get available post types for dropdown navigation."""
    return jsonify(["photo", "video", "carousel"])


@blueprint.route("/api/tags", methods=["GET"])
def api_tags():
    """Get all tags with counts."""
    posts = _load_posts()
    tag_counts = Counter()
    for p in posts:
        for t in p.get("tags", []):
            tag_counts[t] += 1
    return jsonify([{"tag": t, "count": c} for t, c in tag_counts.most_common()])
