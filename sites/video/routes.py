"""StreamHub -- video sharing platform (YouTube-style).

Loads video, comment, playlist, user/channel, and watch-history data from
the shared data-sources directory and serves a full Flask site with both
HTML views and JSON API endpoints.

Supports macros: navigate_by_dropdown, navigate_by_route, search_by_query,
search_by_semantic, filter_by_dropdown, filter_by_slider, filter_by_date_range,
sort_by_ranking, extract_by_query, submit_by_route, upload_by_upload,
select_by_dropdown, configure_by_route, play_by_slider, play_by_date_range,
play_by_playback, post_from_free_text, react_by_toggle, rate_by_slider,
follow_by_toggle, subscribe_by_toggle, share_by_dropdown, save_by_toggle,
report_by_form, authenticate_by_form
"""
import json
import pathlib
from datetime import datetime, timezone

from flask import (
    Blueprint, abort, jsonify, redirect, render_template, request,
    session, url_for,
)
from app import db
from app.events import emit

SITE = "video"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "video",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _videos():
    return db.query(SITE, "videos")

def _comments():
    return db.query(SITE, "comments")

def _playlists():
    return db.query(SITE, "playlists")

def _users():
    return db.query(SITE, "users")

def _history():
    return db.query(SITE, "watch_history")

def _ratings():
    # ratings collection may not exist in schema; return empty list if so
    try:
        return db.query(SITE, "ratings")
    except Exception:
        return []

def _reports():
    # reports collection may not exist in schema; return empty list if so
    try:
        return db.query(SITE, "reports")
    except Exception:
        return []


def _next_id(items):
    if not items:
        return 1
    return max(item["id"] for item in items) + 1


_CATEGORY_COLORS = {
    "Education": ("linear-gradient(135deg, #1a237e 0%, #283593 50%, #1565c0 100%)", "#7986cb"),
    "Entertainment": ("linear-gradient(135deg, #4a148c 0%, #6a1b9a 50%, #8e24aa 100%)", "#ce93d8"),
    "Food & Cooking": ("linear-gradient(135deg, #bf360c 0%, #d84315 50%, #e65100 100%)", "#ff8a65"),
    "Gaming": ("linear-gradient(135deg, #1b5e20 0%, #2e7d32 50%, #388e3c 100%)", "#81c784"),
    "Pets & Animals": ("linear-gradient(135deg, #4e342e 0%, #5d4037 50%, #6d4c41 100%)", "#bcaaa4"),
    "Science & Technology": ("linear-gradient(135deg, #006064 0%, #00838f 50%, #0097a7 100%)", "#80deea"),
    "Sports": ("linear-gradient(135deg, #b71c1c 0%, #c62828 50%, #d32f2f 100%)", "#ef9a9a"),
    "Travel & Outdoors": ("linear-gradient(135deg, #33691e 0%, #558b2f 50%, #689f38 100%)", "#aed581"),
}
_DEFAULT_GRADIENT = ("linear-gradient(135deg, #263238 0%, #37474f 50%, #455a64 100%)", "#90a4ae")


def _thumbnail_gradient(category):
    """Return (gradient, icon_color) pair for a video category."""
    return _CATEGORY_COLORS.get(category, _DEFAULT_GRADIENT)


def _format_duration(seconds):
    """Convert seconds to H:MM:SS or M:SS string."""
    if seconds is None:
        return "0:00"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _format_views(n):
    """Compact view count like 1.2K, 3.4M."""
    if n is None:
        return "0"
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def _time_ago(date_str):
    """Convert date string to relative time (e.g. '3 months ago')."""
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        diff = now - dt
        days = diff.days
        if days < 1:
            hours = diff.seconds // 3600
            if hours < 1:
                return "just now"
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        if days < 30:
            return f"{days} day{'s' if days != 1 else ''} ago"
        months = days // 30
        if months < 12:
            return f"{months} month{'s' if months != 1 else ''} ago"
        years = months // 12
        return f"{years} year{'s' if years != 1 else ''} ago"
    except Exception:
        return date_str


def _current_user_id():
    return session.get("user_id")


def _get_channel_for_video(video, users):
    """Look up the channel/user record for a video."""
    for u in users:
        if u["id"] == video.get("channel_id"):
            return u
    return None


# ---------------------------------------------------------------------------
# Semantic search helper (keyword overlap scoring)
# ---------------------------------------------------------------------------

def _semantic_score(query, video, user_map):
    """Score a video against a multi-word query using term overlap."""
    terms = query.lower().split()
    title = (video.get("title") or "").lower()
    desc = (video.get("description") or "").lower()
    tags = " ".join(video.get("tags", [])).lower()
    channel = user_map.get(video.get("channel_id"), {})
    chan_name = (channel.get("channel_name") or "").lower()
    text = f"{title} {desc} {tags} {chan_name}"
    return sum(1 for t in terms if t in text)


# ---------------------------------------------------------------------------
# Template context processor - inject helpers
# ---------------------------------------------------------------------------

@blueprint.context_processor
def _inject_helpers():
    return dict(
        format_duration=_format_duration,
        format_views=_format_views,
        time_ago=_time_ago,
        thumb_gradient=_thumbnail_gradient,
    )


# ===================================================================
# HTML ROUTES
# ===================================================================

@blueprint.route("/")
def index():
    """Homepage -- trending / recent videos."""
    videos = _videos()
    users = _users()
    user_map = {u["id"]: u for u in users}

    sort = request.args.get("sort", "trending")
    category = request.args.get("category", "")
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    published = [v for v in videos if v.get("status") == "published"]

    if category:
        published = [v for v in published if v.get("category") == category]
    if date_from:
        published = [v for v in published if v.get("upload_date", "")[:10] >= date_from]
    if date_to:
        published = [v for v in published if v.get("upload_date", "")[:10] <= date_to]

    if sort == "latest":
        published.sort(key=lambda v: v.get("upload_date", ""), reverse=True)
    elif sort == "popular":
        published.sort(key=lambda v: v.get("views", 0), reverse=True)
    elif sort == "liked":
        published.sort(key=lambda v: v.get("likes", 0), reverse=True)
    else:  # trending: mix of recency and views
        published.sort(
            key=lambda v: v.get("views", 0) * 0.3 + v.get("likes", 0) * 10,
            reverse=True,
        )

    categories = sorted(set(v.get("category", "") for v in videos if v.get("status") == "published"))

    return render_template(
        "video/index.html",
        videos=published,
        user_map=user_map,
        sort=sort,
        category=category,
        categories=categories,
        date_from=date_from,
        date_to=date_to,
        logged_in=_current_user_id() is not None,
    )


@blueprint.route("/watch/<int:video_id>")
def watch(video_id):
    """Video player page with comments."""
    videos = _videos()
    video = next((v for v in videos if v["id"] == video_id), None)
    if not video:
        abort(404)

    users = _users()
    user_map = {u["id"]: u for u in users}
    channel = _get_channel_for_video(video, users)

    video_comments = db.query(SITE, "comments", where={"video_id": video_id})
    # Build threaded comments: top-level first, replies nested.
    # Data stores parent_comment_id=0 for top-level (not NULL).
    top_comments = [c for c in video_comments if not c.get("parent_comment_id")]
    replies_map = {}
    for c in video_comments:
        pid = c.get("parent_comment_id")
        if pid:
            replies_map.setdefault(pid, []).append(c)
    top_comments.sort(key=lambda c: c.get("likes", 0), reverse=True)

    # Recommended videos (same category, excluding current)
    recommended = [
        v for v in videos
        if v["id"] != video_id
        and v.get("status") == "published"
        and v.get("category") == video.get("category")
    ][:8]
    if len(recommended) < 8:
        extras = [
            v for v in videos
            if v["id"] != video_id
            and v.get("status") == "published"
            and v not in recommended
        ]
        recommended.extend(extras[: 8 - len(recommended)])

    uid = _current_user_id()
    me = user_map.get(uid) if uid is not None else None
    is_subscribed = bool(me and channel and channel["id"] in (me.get("subscriptions") or []))

    return render_template(
        "video/watch.html",
        video=video,
        channel=channel,
        comments=top_comments,
        replies_map=replies_map,
        comment_count=len(video_comments),
        recommended=recommended,
        user_map=user_map,
        logged_in=uid is not None,
        is_subscribed=is_subscribed,
    )


@blueprint.route("/channel/<int:user_id>")
def channel(user_id):
    """Channel page with that user's videos."""
    users = _users()
    chan = next((u for u in users if u["id"] == user_id), None)
    if not chan:
        abort(404)

    videos = _videos()
    channel_videos = [
        v for v in videos
        if v.get("channel_id") == user_id and v.get("status") == "published"
    ]

    sort = request.args.get("sort", "latest")
    if sort == "popular":
        channel_videos.sort(key=lambda v: v.get("views", 0), reverse=True)
    elif sort == "oldest":
        channel_videos.sort(key=lambda v: v.get("upload_date", ""))
    else:
        channel_videos.sort(key=lambda v: v.get("upload_date", ""), reverse=True)

    user_map = {u["id"]: u for u in users}

    uid = _current_user_id()
    me = next((u for u in users if u["id"] == uid), None) if uid is not None else None
    is_subscribed = bool(me and user_id in (me.get("subscriptions") or []))

    return render_template(
        "video/channel.html",
        channel=chan,
        videos=channel_videos,
        user_map=user_map,
        sort=sort,
        logged_in=uid is not None,
        is_subscribed=is_subscribed,
    )


@blueprint.route("/playlists")
def playlists():
    """User playlists overview."""
    all_playlists = _playlists()
    uid = _current_user_id()
    users = _users()
    user_map = {u["id"]: u for u in users}
    videos = _videos()
    video_map = {v["id"]: v for v in videos}

    # Show public playlists, plus private ones owned by logged-in user
    visible = [
        p for p in all_playlists
        if p.get("visibility") == "public"
        or (uid is not None and p.get("user_id") == uid)
    ]

    return render_template(
        "video/playlists.html",
        playlists=visible,
        user_map=user_map,
        video_map=video_map,
        logged_in=uid is not None,
    )


@blueprint.route("/playlist/<int:playlist_id>")
def playlist_detail(playlist_id):
    """Playlist detail -- list of videos."""
    all_playlists = _playlists()
    playlist = next((p for p in all_playlists if p["id"] == playlist_id), None)
    if not playlist:
        abort(404)

    uid = _current_user_id()
    if playlist.get("visibility") == "private" and playlist.get("user_id") != uid:
        abort(403)

    videos = _videos()
    video_map = {v["id"]: v for v in videos}
    users = _users()
    user_map = {u["id"]: u for u in users}

    playlist_videos = []
    for item in sorted(playlist.get("items", []), key=lambda i: i.get("position", 0)):
        vid = video_map.get(item["video_id"])
        if vid:
            playlist_videos.append({**vid, "_added_date": item.get("added_date", "")})

    return render_template(
        "video/playlist_detail.html",
        playlist=playlist,
        videos=playlist_videos,
        user_map=user_map,
        logged_in=uid is not None,
        is_owner=uid is not None and playlist.get("user_id") == uid,
    )


@blueprint.route("/history")
def history():
    """Watch history for the logged-in user."""
    uid = _current_user_id()
    all_history = _history()
    videos = _videos()
    video_map = {v["id"]: v for v in videos}
    users = _users()
    user_map = {u["id"]: u for u in users}

    if uid is not None:
        user_history = [h for h in all_history if h.get("user_id") == uid]
    else:
        # Show all history (user_id=1 as default demo)
        user_history = [h for h in all_history if h.get("user_id") == 1]

    user_history.sort(key=lambda h: h.get("watched_at", ""), reverse=True)

    return render_template(
        "video/history.html",
        history=user_history,
        video_map=video_map,
        user_map=user_map,
        logged_in=uid is not None,
    )


@blueprint.route("/search")
def search():
    """Search results page."""
    q = request.args.get("q", "").strip()
    videos = _videos()
    users = _users()
    user_map = {u["id"]: u for u in users}

    results = []
    if q:
        q_lower = q.lower()
        for v in videos:
            if v.get("status") != "published":
                continue
            title = (v.get("title") or "").lower()
            desc = (v.get("description") or "").lower()
            tags = " ".join(v.get("tags", [])).lower()
            channel = user_map.get(v.get("channel_id"), {})
            chan_name = (channel.get("channel_name") or "").lower()
            if q_lower in title or q_lower in desc or q_lower in tags or q_lower in chan_name:
                # Compute relevance score
                score = 0
                if q_lower in title:
                    score += 10
                if q_lower in chan_name:
                    score += 5
                if q_lower in tags:
                    score += 3
                if q_lower in desc:
                    score += 1
                results.append((score, v))
        results.sort(key=lambda x: (-x[0], -x[1].get("views", 0)))
        results = [v for _, v in results]

    sort = request.args.get("sort", "relevance")
    if sort == "date":
        results.sort(key=lambda v: v.get("upload_date", ""), reverse=True)
    elif sort == "views":
        results.sort(key=lambda v: v.get("views", 0), reverse=True)
    elif sort == "likes":
        results.sort(key=lambda v: v.get("likes", 0), reverse=True)

    return render_template(
        "video/search.html",
        query=q,
        results=results,
        user_map=user_map,
        sort=sort,
        logged_in=_current_user_id() is not None,
    )


@blueprint.route("/upload")
def upload():
    """Upload form page."""
    categories = sorted(set(
        v.get("category", "") for v in _videos() if v.get("status") == "published"
    ))
    return render_template(
        "video/upload.html",
        categories=categories,
        logged_in=_current_user_id() is not None,
    )


@blueprint.route("/settings")
def settings():
    """User settings / preferences page (configure_by_route)."""
    uid = _current_user_id()
    if uid is None:
        return redirect(url_for("video.login"))
    users = _users()
    user = next((u for u in users if u["id"] == uid), None)
    if not user:
        return redirect(url_for("video.login"))
    return render_template(
        "video/settings.html",
        user=user,
        logged_in=True,
    )


@blueprint.route("/login", methods=["GET", "POST"])
def login():
    """Login page (authenticate_by_form)."""
    users = _users()
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        user = next((u for u in users if u["username"] == username), None)
        if user and user.get("password", username) == password:
            session["user_id"] = user["id"]
            emit("signup", user_id=user["id"], site_name="video", username=request.form.get("username", ""), password=request.form.get("password", ""), email="")
            session["username"] = user["username"]
            session["display_name"] = user["display_name"]
            return redirect(url_for("video.index"))
        error = "Invalid username or password."
    return render_template(
        "video/login.html",
        users=users,
        error=error,
        logged_in=_current_user_id() is not None,
    )


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("username", None)
    session.pop("display_name", None)
    return redirect(url_for("video.index"))


# ===================================================================
# FORM-BASED MUTATION ROUTES (browser automation friendly)
# ===================================================================

@blueprint.route("/watch/<int:video_id>/submit", methods=["POST"])
def form_submit_video_edit(video_id):
    """Submit edited video metadata via HTML form (submit_by_route)."""
    videos = _videos()
    video = next((v for v in videos if v["id"] == video_id), None)
    if not video:
        abort(404)
    for field in ("title", "description", "category"):
        val = request.form.get(field)
        if val is not None:
            video[field] = val.strip()
    tags_raw = request.form.get("tags", "")
    if tags_raw:
        video["tags"] = [t.strip() for t in tags_raw.split(",") if t.strip()]
    db.save_collection(SITE, "videos", videos)
    return redirect(url_for("video.watch", video_id=video_id))


@blueprint.route("/watch/<int:video_id>/report", methods=["POST"])
def form_report_video(video_id):
    """Report a video via HTML form (report_by_form)."""
    videos = _videos()
    video = next((v for v in videos if v["id"] == video_id), None)
    if not video:
        abort(404)

    reason = request.form.get("reason", "").strip()
    details = request.form.get("details", "").strip()
    if not reason:
        abort(400)

    reports = _reports()
    new_report = {
        "id": _next_id(reports),
        "video_id": video_id,
        "user_id": _current_user_id(),
        "reason": reason,
        "details": details,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
    }
    reports.append(new_report)
    db.save_collection(SITE, "reports", reports)
    return redirect(url_for("video.watch", video_id=video_id))


@blueprint.route("/channel/<int:user_id>/subscribe", methods=["POST"])
def form_subscribe_channel(user_id):
    """Toggle channel subscription via form (subscribe_by_toggle)."""
    uid = _current_user_id()
    if uid is None:
        return redirect(url_for("video.login"))

    users = _users()
    target = next((u for u in users if u["id"] == user_id), None)
    current = next((u for u in users if u["id"] == uid), None)
    if not target or not current:
        abort(404)

    subscriptions = current.setdefault("subscriptions", [])
    if user_id in subscriptions:
        subscriptions.remove(user_id)
        target["subscriber_count"] = max(0, target.get("subscriber_count", 0) - 1)
        action = "unsubscribed"
    else:
        subscriptions.append(user_id)
        target["subscriber_count"] = target.get("subscriber_count", 0) + 1
        action = "subscribed"

    db.save_collection(SITE, "users", users)
    return redirect(url_for("video.channel", user_id=user_id))


@blueprint.route("/channel/<int:user_id>/follow", methods=["POST"])
def form_follow_channel(user_id):
    """Toggle follow on a channel via form (follow_by_toggle)."""
    uid = _current_user_id()
    if uid is None:
        return redirect(url_for("video.login"))

    users = _users()
    current = next((u for u in users if u["id"] == uid), None)
    if not current:
        abort(404)

    following = current.setdefault("following", [])
    if user_id in following:
        following.remove(user_id)
    else:
        following.append(user_id)

    db.save_collection(SITE, "users", users)
    return redirect(url_for("video.channel", user_id=user_id))


@blueprint.route("/watch/<int:video_id>/save", methods=["POST"])
def form_save_video(video_id):
    """Toggle save/bookmark a video (save_by_toggle)."""
    uid = _current_user_id()
    if uid is None:
        return redirect(url_for("video.login"))

    users = _users()
    current = next((u for u in users if u["id"] == uid), None)
    if not current:
        abort(404)

    saved = current.setdefault("saved_videos", [])
    if video_id in saved:
        saved.remove(video_id)
    else:
        saved.append(video_id)

    db.save_collection(SITE, "users", users)
    return redirect(url_for("video.watch", video_id=video_id))


@blueprint.route("/settings/update", methods=["POST"])
def form_settings_update():
    """Update user settings (configure_by_route)."""
    uid = _current_user_id()
    if uid is None:
        return redirect(url_for("video.login"))

    users = _users()
    user = next((u for u in users if u["id"] == uid), None)
    if not user:
        return redirect(url_for("video.login"))

    prefs = user.setdefault("preferences", {})
    for key in ("autoplay", "default_quality", "playback_speed", "captions",
                "dark_mode", "notifications"):
        val = request.form.get(key)
        if val is not None:
            if val in ("true", "on"):
                prefs[key] = True
            elif val in ("false", "off"):
                prefs[key] = False
            else:
                prefs[key] = val

    db.save_collection(SITE, "users", users)
    return redirect(url_for("video.settings"))


# ===================================================================
# API ROUTES
# ===================================================================

@blueprint.route("/api/videos", methods=["GET"])
def api_videos():
    """List videos with optional filters: channel, category, search, sort,
    duration range (filter_by_slider), date range (filter_by_date_range)."""
    videos = _videos()
    published = [v for v in videos if v.get("status") == "published"]

    # Filters
    channel_id = request.args.get("channel_id", type=int)
    category = request.args.get("category", "")
    q = request.args.get("q", "").strip().lower()
    sort = request.args.get("sort", "date")

    # filter_by_slider: duration range
    duration_min = request.args.get("duration_min", type=int)
    duration_max = request.args.get("duration_max", type=int)

    # filter_by_date_range: upload date range
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    if channel_id:
        published = [v for v in published if v.get("channel_id") == channel_id]
    if category:
        published = [v for v in published if v.get("category") == category]
    if q:
        published = [
            v for v in published
            if q in (v.get("title") or "").lower()
            or q in (v.get("description") or "").lower()
            or q in " ".join(v.get("tags", [])).lower()
        ]
    if duration_min is not None:
        published = [v for v in published if v.get("duration_seconds", 0) >= duration_min]
    if duration_max is not None:
        published = [v for v in published if v.get("duration_seconds", 0) <= duration_max]
    if date_from:
        published = [v for v in published if v.get("upload_date", "") >= date_from]
    if date_to:
        published = [v for v in published if v.get("upload_date", "") <= date_to]

    if sort == "views":
        published.sort(key=lambda v: v.get("views", 0), reverse=True)
    elif sort == "likes":
        published.sort(key=lambda v: v.get("likes", 0), reverse=True)
    elif sort == "oldest":
        published.sort(key=lambda v: v.get("upload_date", ""))
    elif sort == "duration":
        published.sort(key=lambda v: v.get("duration_seconds", 0))
    elif sort == "duration_desc":
        published.sort(key=lambda v: v.get("duration_seconds", 0), reverse=True)
    else:  # date (newest first)
        published.sort(key=lambda v: v.get("upload_date", ""), reverse=True)

    return jsonify(published)


@blueprint.route("/api/videos/<int:video_id>", methods=["GET"])
def api_video_get(video_id):
    """Get a single video."""
    videos = _videos()
    video = next((v for v in videos if v["id"] == video_id), None)
    if not video:
        return jsonify({"error": "Video not found"}), 404
    return jsonify(video)


@blueprint.route("/api/videos/<int:video_id>", methods=["PUT"])
def api_video_update(video_id):
    """Update a video's metadata (submit_by_route)."""
    videos = _videos()
    video = next((v for v in videos if v["id"] == video_id), None)
    if not video:
        return jsonify({"error": "Video not found"}), 404

    data = request.get_json(force=True)
    for field in ("title", "description", "category", "tags", "status"):
        if field in data:
            video[field] = data[field]

    db.save_collection(SITE, "videos", videos)
    return jsonify(video)


@blueprint.route("/api/videos/<int:video_id>", methods=["DELETE"])
def api_video_delete(video_id):
    """Delete a video."""
    videos = _videos()
    idx = next((i for i, v in enumerate(videos) if v["id"] == video_id), None)
    if idx is None:
        return jsonify({"error": "Video not found"}), 404

    deleted = videos.pop(idx)
    db.save_collection(SITE, "videos", videos)

    # Also remove related comments
    comments = _comments()
    comments = [c for c in comments if c["video_id"] != video_id]
    db.save_collection(SITE, "comments", comments)

    return jsonify({"message": "Video deleted", "video": deleted})


@blueprint.route("/api/videos", methods=["POST"])
def api_video_create():
    """Upload / create a new video (upload_by_upload)."""
    data = request.get_json(force=True)
    videos = _videos()

    required = ("title", "channel_id")
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400

    new_video = {
        "id": _next_id(videos),
        "title": data["title"],
        "channel_id": data["channel_id"],
        "user_id": data.get("user_id", data["channel_id"]),
        "description": data.get("description", ""),
        "duration_seconds": data.get("duration_seconds", 0),
        "views": 0,
        "likes": 0,
        "dislikes": 0,
        "upload_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "category": data.get("category", "Entertainment"),
        "tags": data.get("tags", []),
        "thumbnail_url": data.get("thumbnail_url", ""),
        "video_url": data.get("video_url", ""),
        "status": data.get("status", "published"),
    }

    videos.append(new_video)
    db.save_collection(SITE, "videos", videos)
    return jsonify(new_video), 201


@blueprint.route("/api/videos/<int:video_id>/like", methods=["POST"])
def api_video_like(video_id):
    """Toggle like on a video (react_by_toggle)."""
    videos = _videos()
    video = next((v for v in videos if v["id"] == video_id), None)
    if not video:
        return jsonify({"error": "Video not found"}), 404

    data = request.get_json(force=True) if request.is_json else {}
    action = data.get("action", "like")  # "like" or "dislike" or "unlike"

    if action == "like":
        video["likes"] = video.get("likes", 0) + 1
    elif action == "dislike":
        video["dislikes"] = video.get("dislikes", 0) + 1
    elif action == "unlike":
        video["likes"] = max(0, video.get("likes", 0) - 1)

    db.save_collection(SITE, "videos", videos)
    return jsonify({"likes": video["likes"], "dislikes": video["dislikes"]})


@blueprint.route("/api/videos/<int:video_id>/rate", methods=["POST"])
def api_video_rate(video_id):
    """Rate a video 1-5 stars (rate_by_slider)."""
    videos = _videos()
    video = next((v for v in videos if v["id"] == video_id), None)
    if not video:
        return jsonify({"error": "Video not found"}), 404

    data = request.get_json(force=True)
    rating_val = data.get("rating")
    if rating_val is None or not (1 <= int(rating_val) <= 5):
        return jsonify({"error": "Rating must be between 1 and 5"}), 400

    rating_val = int(rating_val)
    uid = data.get("user_id") or _current_user_id() or 1

    ratings = _ratings()
    # Update existing or add new
    existing = next((r for r in ratings
                     if r["video_id"] == video_id and r["user_id"] == uid), None)
    if existing:
        existing["rating"] = rating_val
        existing["timestamp"] = datetime.now(timezone.utc).isoformat()
    else:
        ratings.append({
            "id": _next_id(ratings),
            "video_id": video_id,
            "user_id": uid,
            "rating": rating_val,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    db.save_collection(SITE, "ratings", ratings)

    # Compute average
    video_ratings = [r["rating"] for r in ratings if r["video_id"] == video_id]
    avg = round(sum(video_ratings) / len(video_ratings), 2) if video_ratings else 0
    return jsonify({
        "video_id": video_id,
        "user_rating": rating_val,
        "average_rating": avg,
        "total_ratings": len(video_ratings),
    })


@blueprint.route("/api/videos/<int:video_id>/ratings", methods=["GET"])
def api_video_ratings(video_id):
    """Get rating stats for a video."""
    ratings = _ratings()
    video_ratings = [r for r in ratings if r["video_id"] == video_id]
    vals = [r["rating"] for r in video_ratings]
    avg = round(sum(vals) / len(vals), 2) if vals else 0
    return jsonify({
        "video_id": video_id,
        "average_rating": avg,
        "total_ratings": len(vals),
        "ratings": video_ratings,
    })


@blueprint.route("/api/videos/<int:video_id>/seek", methods=["POST"])
def api_video_seek(video_id):
    """Set playback seek position — the seek bar is a slider (play_by_slider).

    Accepts `position` (seconds) or `position_pct` (0-100). Clamps to the
    duration, persists the resume point (session overlay), and returns a
    formatted label so a scrub is verifiable.
    """
    videos = _videos()
    video = next((v for v in videos if v["id"] == video_id), None)
    if not video:
        return jsonify({"error": "Video not found"}), 404

    data = request.get_json(force=True) or {}
    duration = int(video.get("duration_seconds") or 0)
    position = data.get("position")
    if position is None and data.get("position_pct") is not None:
        position = float(data["position_pct"]) / 100.0 * duration
    try:
        position = int(round(float(position or 0)))
    except (TypeError, ValueError):
        position = 0
    position = max(0, min(position, duration)) if duration > 0 else max(0, position)

    video["playback_position_sec"] = position
    db.save_item(SITE, "videos", video_id, video)

    progress = round((position / duration) * 100, 1) if duration > 0 else 0
    return jsonify({
        "video_id": video_id,
        "position_seconds": position,
        "position_label": f"{position // 60}:{position % 60:02d}",
        "duration_seconds": duration,
        "progress_percent": progress,
    })


@blueprint.route("/api/videos/<int:video_id>/play", methods=["POST"])
def api_video_play(video_id):
    """Start playback (play_by_playback).

    Increments the view count and returns playback details that are only
    revealed once the video is actually played — exact duration, stream
    quality, and chapter markers — making play a verifiable precondition.
    """
    import random as _random
    videos = _videos()
    video = next((v for v in videos if v["id"] == video_id), None)
    if not video:
        return jsonify({"error": "Video not found"}), 404

    video["views"] = (video.get("views") or 0) + 1
    db.save_item(SITE, "videos", video_id, video)

    dur = video.get("duration_seconds") or 0
    rnd = _random.Random(f"video-{video_id}")
    titles = ["Intro", "Overview", "Main segment", "Details & examples",
              "Recap", "Outro"]
    n_chapters = max(2, min(6, dur // 180 + 2)) if dur > 60 else 2
    bounds = sorted(rnd.sample(range(15, max(16, dur - 10)), n_chapters - 1)) if dur > 60 else [max(5, dur // 2)]
    starts = [0] + bounds
    chapters = [{"start_sec": s,
                 "start": f"{s // 60}:{s % 60:02d}",
                 "title": titles[i % len(titles)]}
                for i, s in enumerate(starts)]
    return jsonify({
        "playing": True,
        "video_id": video_id,
        "views": video["views"],
        "exact_duration": f"{dur // 60}:{dur % 60:02d}",
        "stream_quality": rnd.choice(["720p", "1080p", "1440p"]),
        "chapters": chapters,
    })


@blueprint.route("/api/videos/<int:video_id>/playback", methods=["POST"])
def api_video_playback(video_id):
    """Set playback configuration: speed, quality (play_by_playback)."""
    videos = _videos()
    video = next((v for v in videos if v["id"] == video_id), None)
    if not video:
        return jsonify({"error": "Video not found"}), 404

    data = request.get_json(force=True)
    speed = data.get("speed", 1.0)
    quality = data.get("quality", "auto")

    valid_speeds = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]
    valid_qualities = ["auto", "144p", "240p", "360p", "480p", "720p", "1080p", "1440p", "2160p"]

    if speed not in valid_speeds:
        return jsonify({"error": f"Invalid speed. Choose from {valid_speeds}"}), 400
    if quality not in valid_qualities:
        return jsonify({"error": f"Invalid quality. Choose from {valid_qualities}"}), 400

    return jsonify({
        "video_id": video_id,
        "speed": speed,
        "quality": quality,
    })


@blueprint.route("/api/videos/<int:video_id>/share", methods=["POST"])
def api_video_share(video_id):
    """Share a video via a specified platform (share_by_dropdown)."""
    videos = _videos()
    video = next((v for v in videos if v["id"] == video_id), None)
    if not video:
        return jsonify({"error": "Video not found"}), 404

    data = request.get_json(force=True)
    platform = data.get("platform", "link")
    valid_platforms = ["link", "twitter", "facebook", "reddit", "email", "embed"]
    if platform not in valid_platforms:
        return jsonify({"error": f"Invalid platform. Choose from {valid_platforms}"}), 400

    share_url = f"/sites/video/watch/{video_id}"
    if platform == "embed":
        share_content = f'<iframe src="{share_url}" width="560" height="315"></iframe>'
    elif platform == "email":
        share_content = f"Check out this video: {video['title']} - {share_url}"
    else:
        share_content = share_url

    # Track share count
    video["shares"] = video.get("shares", 0) + 1
    db.save_collection(SITE, "videos", videos)

    return jsonify({
        "video_id": video_id,
        "platform": platform,
        "share_url": share_content,
        "total_shares": video["shares"],
    })


@blueprint.route("/api/videos/<int:video_id>/report", methods=["POST"])
def api_video_report(video_id):
    """Report a video for a reason (report_by_form)."""
    videos = _videos()
    video = next((v for v in videos if v["id"] == video_id), None)
    if not video:
        return jsonify({"error": "Video not found"}), 404

    data = request.get_json(force=True)
    reason = data.get("reason", "").strip()
    if not reason:
        return jsonify({"error": "Report reason is required"}), 400

    valid_reasons = ["spam", "harassment", "misinformation", "copyright",
                     "inappropriate", "violence", "other"]
    if reason not in valid_reasons:
        return jsonify({"error": f"Invalid reason. Choose from {valid_reasons}"}), 400

    reports = _reports()
    new_report = {
        "id": _next_id(reports),
        "video_id": video_id,
        "user_id": data.get("user_id") or _current_user_id(),
        "reason": reason,
        "details": data.get("details", ""),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
    }
    reports.append(new_report)
    db.save_collection(SITE, "reports", reports)

    return jsonify(new_report), 201


@blueprint.route("/api/videos/<int:video_id>/save", methods=["POST"])
def api_video_save(video_id):
    """Toggle save/bookmark a video (save_by_toggle)."""
    data = request.get_json(force=True) if request.is_json else {}
    uid = data.get("user_id") or _current_user_id() or 1

    users = _users()
    user = next((u for u in users if u["id"] == uid), None)
    if not user:
        return jsonify({"error": "User not found"}), 404

    saved = user.setdefault("saved_videos", [])
    if video_id in saved:
        saved.remove(video_id)
        action = "unsaved"
    else:
        saved.append(video_id)
        action = "saved"

    db.save_collection(SITE, "users", users)
    return jsonify({
        "action": action,
        "video_id": video_id,
        "total_saved": len(saved),
    })


@blueprint.route("/api/videos/<int:video_id>/comments", methods=["GET"])
def api_video_comments(video_id):
    """Get comments for a video."""
    comments = _comments()
    video_comments = [c for c in comments if c["video_id"] == video_id]
    sort = request.args.get("sort", "likes")
    if sort == "newest":
        video_comments.sort(key=lambda c: c.get("timestamp", ""), reverse=True)
    elif sort == "oldest":
        video_comments.sort(key=lambda c: c.get("timestamp", ""))
    else:
        video_comments.sort(key=lambda c: c.get("likes", 0), reverse=True)
    return jsonify(video_comments)


@blueprint.route("/api/videos/<int:video_id>/comments", methods=["POST"])
def api_video_comment_add(video_id):
    """Add a comment to a video (post_from_free_text)."""
    videos = _videos()
    video = next((v for v in videos if v["id"] == video_id), None)
    if not video:
        return jsonify({"error": "Video not found"}), 404

    data = request.get_json(force=True)
    if not data.get("text"):
        return jsonify({"error": "Comment text is required"}), 400

    comments = _comments()
    users = _users()

    uid = data.get("user_id") or _current_user_id()
    user = next((u for u in users if u["id"] == uid), None)

    new_comment = {
        "id": _next_id(comments),
        "video_id": video_id,
        "user_id": uid,
        "username": user["username"] if user else data.get("username", "anonymous"),
        "display_name": user["display_name"] if user else data.get("display_name", "Anonymous"),
        "text": data["text"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "likes": 0,
        "parent_comment_id": data.get("parent_comment_id"),
    }

    comments.append(new_comment)
    db.save_collection(SITE, "comments", comments)
    return jsonify(new_comment), 201


@blueprint.route("/api/comments/<int:comment_id>", methods=["DELETE"])
def api_comment_delete(comment_id):
    """Delete a comment."""
    comments = _comments()
    idx = next((i for i, c in enumerate(comments) if c["id"] == comment_id), None)
    if idx is None:
        return jsonify({"error": "Comment not found"}), 404
    deleted = comments.pop(idx)
    # Also remove any replies to this comment
    comments = [c for c in comments if c.get("parent_comment_id") != comment_id]
    db.save_collection(SITE, "comments", comments)
    return jsonify({"message": "Comment deleted", "comment": deleted})


@blueprint.route("/api/channels/<int:user_id>", methods=["GET"])
def api_channel(user_id):
    """Get channel info with video list."""
    users = _users()
    chan = next((u for u in users if u["id"] == user_id), None)
    if not chan:
        return jsonify({"error": "Channel not found"}), 404

    videos = _videos()
    channel_videos = [
        v for v in videos
        if v.get("channel_id") == user_id and v.get("status") == "published"
    ]
    channel_videos.sort(key=lambda v: v.get("upload_date", ""), reverse=True)

    result = {**chan, "videos": channel_videos}
    return jsonify(result)


@blueprint.route("/api/channels/<int:user_id>/subscribe", methods=["POST"])
def api_channel_subscribe(user_id):
    """Toggle subscription to a channel (subscribe_by_toggle)."""
    data = request.get_json(force=True) if request.is_json else {}
    uid = data.get("user_id") or _current_user_id() or 1

    users = _users()
    target = next((u for u in users if u["id"] == user_id), None)
    current = next((u for u in users if u["id"] == uid), None)
    if not target:
        return jsonify({"error": "Channel not found"}), 404
    if not current:
        return jsonify({"error": "User not found"}), 404

    subscriptions = current.setdefault("subscriptions", [])
    if user_id in subscriptions:
        subscriptions.remove(user_id)
        target["subscriber_count"] = max(0, target.get("subscriber_count", 0) - 1)
        action = "unsubscribed"
    else:
        subscriptions.append(user_id)
        target["subscriber_count"] = target.get("subscriber_count", 0) + 1
        action = "subscribed"

    db.save_collection(SITE, "users", users)
    return jsonify({
        "action": action,
        "channel_id": user_id,
        "subscriber_count": target["subscriber_count"],
        "total_subscriptions": len(subscriptions),
    })


@blueprint.route("/api/channels/<int:user_id>/follow", methods=["POST"])
def api_channel_follow(user_id):
    """Toggle follow on a channel (follow_by_toggle)."""
    data = request.get_json(force=True) if request.is_json else {}
    uid = data.get("user_id") or _current_user_id() or 1

    users = _users()
    current = next((u for u in users if u["id"] == uid), None)
    if not current:
        return jsonify({"error": "User not found"}), 404
    if not any(u["id"] == user_id for u in users):
        return jsonify({"error": "Channel not found"}), 404

    following = current.setdefault("following", [])
    if user_id in following:
        following.remove(user_id)
        action = "unfollowed"
    else:
        following.append(user_id)
        action = "followed"

    db.save_collection(SITE, "users", users)
    return jsonify({
        "action": action,
        "channel_id": user_id,
        "total_following": len(following),
    })


@blueprint.route("/api/playlists", methods=["GET"])
def api_playlists_list():
    """List playlists. Optionally filter by user_id."""
    playlists = _playlists()
    uid_filter = request.args.get("user_id", type=int)
    if uid_filter:
        playlists = [p for p in playlists if p.get("user_id") == uid_filter]

    # Only show public playlists unless it's the logged-in user's
    current = _current_user_id()
    playlists = [
        p for p in playlists
        if p.get("visibility") == "public"
        or (current is not None and p.get("user_id") == current)
    ]
    return jsonify(playlists)


@blueprint.route("/api/playlists", methods=["POST"])
def api_playlists_create():
    """Create a new playlist."""
    data = request.get_json(force=True)
    playlists = _playlists()

    if not data.get("title"):
        return jsonify({"error": "Playlist title is required"}), 400

    uid = data.get("user_id") or _current_user_id() or 1

    new_playlist = {
        "id": _next_id(playlists),
        "user_id": uid,
        "username": data.get("username", ""),
        "title": data["title"],
        "description": data.get("description", ""),
        "visibility": data.get("visibility", "public"),
        "created_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "updated_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "items": [],
    }

    playlists.append(new_playlist)
    db.save_collection(SITE, "playlists", playlists)
    return jsonify(new_playlist), 201


@blueprint.route("/api/playlists/<int:playlist_id>", methods=["GET"])
def api_playlist_get(playlist_id):
    """Get playlist detail with video info."""
    playlists = _playlists()
    playlist = next((p for p in playlists if p["id"] == playlist_id), None)
    if not playlist:
        return jsonify({"error": "Playlist not found"}), 404

    videos = _videos()
    video_map = {v["id"]: v for v in videos}

    items_with_video = []
    for item in sorted(playlist.get("items", []), key=lambda i: i.get("position", 0)):
        vid = video_map.get(item["video_id"])
        if vid:
            items_with_video.append({**item, "video": vid})

    result = {**playlist, "items_detail": items_with_video}
    return jsonify(result)


@blueprint.route("/api/playlists/<int:playlist_id>", methods=["PUT"])
def api_playlist_update(playlist_id):
    """Update playlist metadata."""
    playlists = _playlists()
    playlist = next((p for p in playlists if p["id"] == playlist_id), None)
    if not playlist:
        return jsonify({"error": "Playlist not found"}), 404

    data = request.get_json(force=True)
    for field in ("title", "description", "visibility"):
        if field in data:
            playlist[field] = data[field]
    playlist["updated_date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    db.save_collection(SITE, "playlists", playlists)
    return jsonify(playlist)


@blueprint.route("/api/playlists/<int:playlist_id>", methods=["DELETE"])
def api_playlist_delete(playlist_id):
    """Delete a playlist."""
    playlists = _playlists()
    idx = next((i for i, p in enumerate(playlists) if p["id"] == playlist_id), None)
    if idx is None:
        return jsonify({"error": "Playlist not found"}), 404

    deleted = playlists.pop(idx)
    db.save_collection(SITE, "playlists", playlists)
    return jsonify({"message": "Playlist deleted", "playlist": deleted})


@blueprint.route("/api/playlists/<int:playlist_id>/add", methods=["POST"])
def api_playlist_add_video(playlist_id):
    """Add a video to a playlist (select_by_dropdown -- select playlist to add to)."""
    playlists = _playlists()
    playlist = next((p for p in playlists if p["id"] == playlist_id), None)
    if not playlist:
        return jsonify({"error": "Playlist not found"}), 404

    data = request.get_json(force=True)
    video_id = data.get("video_id")
    if not video_id:
        return jsonify({"error": "video_id is required"}), 400

    # Check video exists
    videos = _videos()
    if not any(v["id"] == video_id for v in videos):
        return jsonify({"error": "Video not found"}), 404

    # Check if already in playlist
    if any(item["video_id"] == video_id for item in playlist.get("items", [])):
        return jsonify({"error": "Video already in playlist"}), 409

    items = playlist.get("items", [])
    max_pos = max((i.get("position", 0) for i in items), default=0)
    items.append({
        "video_id": video_id,
        "added_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "position": max_pos + 1,
    })
    playlist["items"] = items
    playlist["updated_date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    db.save_collection(SITE, "playlists", playlists)
    return jsonify(playlist)


@blueprint.route("/api/history", methods=["GET"])
def api_history_list():
    """Get watch history. Optionally filter by user_id and date range
    (play_by_date_range)."""
    history = _history()
    uid = request.args.get("user_id", type=int)
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    if uid:
        history = [h for h in history if h.get("user_id") == uid]
    if date_from:
        history = [h for h in history
                   if h.get("watched_at", "")[:10] >= date_from]
    if date_to:
        history = [h for h in history
                   if h.get("watched_at", "")[:10] <= date_to]

    history.sort(key=lambda h: h.get("watched_at", ""), reverse=True)
    return jsonify(history)


@blueprint.route("/api/history", methods=["POST"])
def api_history_log():
    """Log a watch event."""
    data = request.get_json(force=True)
    history = _history()

    video_id = data.get("video_id")
    if not video_id:
        return jsonify({"error": "video_id is required"}), 400

    videos = _videos()
    video = next((v for v in videos if v["id"] == video_id), None)
    if not video:
        return jsonify({"error": "Video not found"}), 404

    users = _users()
    user_map = {u["id"]: u for u in users}
    channel = user_map.get(video.get("channel_id"), {})

    uid = data.get("user_id") or _current_user_id() or 1

    new_entry = {
        "id": _next_id(history),
        "user_id": uid,
        "video_id": video_id,
        "video_title": video.get("title", ""),
        "channel_name": channel.get("channel_name", ""),
        "watched_at": datetime.now(timezone.utc).isoformat(),
        "progress_percent": data.get("progress_percent", 0),
        "duration_seconds": video.get("duration_seconds", 0),
    }

    history.append(new_entry)
    db.save_collection(SITE, "watch_history", history)

    # Increment view count
    video["views"] = video.get("views", 0) + 1
    db.save_collection(SITE, "videos", videos)

    return jsonify(new_entry), 201


@blueprint.route("/api/search", methods=["GET"])
def api_search():
    """Search videos by query string (search_by_query)."""
    q = request.args.get("q", "").strip().lower()
    if not q:
        return jsonify([])

    videos = _videos()
    users = _users()
    user_map = {u["id"]: u for u in users}

    results = []
    for v in videos:
        if v.get("status") != "published":
            continue
        title = (v.get("title") or "").lower()
        desc = (v.get("description") or "").lower()
        tags = " ".join(v.get("tags", [])).lower()
        channel = user_map.get(v.get("channel_id"), {})
        chan_name = (channel.get("channel_name") or "").lower()

        if q in title or q in desc or q in tags or q in chan_name:
            score = 0
            if q in title:
                score += 10
            if q in chan_name:
                score += 5
            if q in tags:
                score += 3
            if q in desc:
                score += 1
            results.append((score, v))

    results.sort(key=lambda x: (-x[0], -x[1].get("views", 0)))
    return jsonify([v for _, v in results])


@blueprint.route("/api/search/semantic", methods=["GET"])
def api_search_semantic():
    """Semantic search: multi-word relevance scoring (search_by_semantic)."""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    videos = _videos()
    users = _users()
    user_map = {u["id"]: u for u in users}

    scored = []
    for v in videos:
        if v.get("status") != "published":
            continue
        s = _semantic_score(q, v, user_map)
        if s > 0:
            scored.append((s, v))

    scored.sort(key=lambda x: (-x[0], -x[1].get("views", 0)))
    return jsonify([v for _, v in scored])


@blueprint.route("/api/categories", methods=["GET"])
def api_categories():
    """List all video categories with counts."""
    videos = _videos()
    published = [v for v in videos if v.get("status") == "published"]
    counts = {}
    for v in published:
        cat = v.get("category", "Unknown")
        counts[cat] = counts.get(cat, 0) + 1
    return jsonify([{"name": c, "count": n} for c, n in sorted(counts.items())])


@blueprint.route("/api/login", methods=["POST"])
def api_login():
    """Authenticate via API (authenticate_by_form)."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    users = _users()
    user = next((u for u in users if u["username"] == username), None)
    # Password defaults to username if not set in data
    if not user or user.get("password", username) != password:
        return jsonify({"error": "Invalid credentials"}), 401
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["display_name"] = user["display_name"]
    return jsonify({
        "user_id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
    })


@blueprint.route("/api/users/<int:user_id>", methods=["GET"])
def api_user_get(user_id):
    """Get user profile (excludes password)."""
    users = _users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({k: v for k, v in user.items() if k != "password"})


@blueprint.route("/api/users/<int:user_id>/settings", methods=["GET"])
def api_user_settings(user_id):
    """Get user settings/preferences (configure_by_route)."""
    users = _users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        return jsonify({"error": "User not found"}), 404
    prefs = user.get("preferences", {
        "autoplay": True,
        "default_quality": "auto",
        "playback_speed": 1.0,
        "captions": False,
        "dark_mode": False,
        "notifications": True,
    })
    return jsonify({"user_id": user_id, "preferences": prefs})


@blueprint.route("/api/users/<int:user_id>/settings", methods=["PUT"])
def api_user_settings_update(user_id):
    """Update user settings/preferences (configure_by_route)."""
    users = _users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json(force=True)
    prefs = user.setdefault("preferences", {})
    for key in ("autoplay", "default_quality", "playback_speed", "captions",
                "dark_mode", "notifications"):
        if key in data:
            prefs[key] = data[key]

    db.save_collection(SITE, "users", users)
    return jsonify({"user_id": user_id, "preferences": prefs})


@blueprint.route("/api/stats", methods=["GET"])
def api_stats():
    """Platform statistics."""
    videos = _videos()
    comments = _comments()
    users = _users()
    playlists = _playlists()
    history = _history()

    published = [v for v in videos if v.get("status") == "published"]
    total_views = sum(v.get("views", 0) for v in published)
    total_likes = sum(v.get("likes", 0) for v in published)

    # Category breakdown
    category_counts = {}
    for v in published:
        cat = v.get("category", "Unknown")
        category_counts[cat] = category_counts.get(cat, 0) + 1

    # Top channels by subscribers
    top_channels = sorted(users, key=lambda u: u.get("subscriber_count", 0), reverse=True)[:5]

    return jsonify({
        "total_videos": len(published),
        "total_channels": len(users),
        "total_comments": len(comments),
        "total_playlists": len(playlists),
        "total_views": total_views,
        "total_likes": total_likes,
        "total_history_entries": len(history),
        "categories": category_counts,
        "top_channels": [
            {"id": c["id"], "name": c["channel_name"], "subscribers": c["subscriber_count"]}
            for c in top_channels
        ],
    })


@blueprint.route("/api/reports", methods=["GET"])
def api_reports_list():
    """List all reports (admin view)."""
    reports = _reports()
    video_id = request.args.get("video_id", type=int)
    if video_id:
        reports = [r for r in reports if r["video_id"] == video_id]
    return jsonify(reports)
