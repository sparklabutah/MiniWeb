"""StreamHub Live -- Twitch-style live-streaming platform.

Serves live/past streams, chat, clips, channels, and subscriptions using
data from the live-streaming data source directory.

Macros supported (20):
    navigate_by_semantic, navigate_by_dropdown, navigate_by_route,
    search_by_query, filter_by_dropdown, sort_by_dropdown,
    select_by_slider, play_by_timestamp,
    play_by_playback, post_from_free_text, follow_by_toggle,
    share_by_dropdown, report_by_form, subscribe_by_toggle,
    join_by_toggle, pay_by_dropdown, redeem_by_dropdown,
    authenticate_by_form, register_by_form
"""
import json
import pathlib
import uuid
from datetime import datetime

from flask import (
    Blueprint, abort, jsonify, redirect, render_template, request,
    session, url_for,
)
from app import db
from app.events import emit

SITE = "live"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "live",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# House ads promote real MiniWeb sites and link to them (/sites/<id>/).
# Curated for a streaming/entertainment audience. `tagline` (not `copy`) —
# `copy` collides with dict.copy in Jinja attribute lookups.
_AD_POOL = [
    {"site": "music", "brand": "SoundWave", "domain": "soundwave.fm",
     "tagline": "Millions of songs, zero ads on Premium. First month free."},
    {"site": "ticketing-events", "brand": "EventPass", "domain": "eventpass.live",
     "tagline": "Concerts, esports finals & meetups near you. Grab tickets first."},
    {"site": "e-commerce", "brand": "ShopWave", "domain": "shopwave.com",
     "tagline": "Upgrade your streaming setup — mics, cams & lights up to 40% off."},
    {"site": "sports-esports", "brand": "Lakeport Sports", "domain": "lakeportsports.com",
     "tagline": "Live scores, brackets & highlights from every league in one place."},
    {"site": "video", "brand": "StreamTube", "domain": "streamtube.tv",
     "tagline": "On-demand shows and creators. Watch anytime, free to start."},
]


_STREAM_SORT_KEYS = {
    "viewers": (lambda s: s.get("total_views", 0) or 0, True),
    "newest": (lambda s: s.get("started_at", "") or "", True),
    "oldest": (lambda s: s.get("started_at", "") or "", False),
    "duration": (lambda s: s.get("duration_minutes", 0) or 0, True),
}


def _sort_streams(streams, sort):
    """Apply the sort-dropdown order to a list of streams (used for the search
    path, since db.search() ranks by relevance and ignores the SQL sort)."""
    key = _STREAM_SORT_KEYS.get(sort)
    if key:
        streams = sorted(streams, key=key[0], reverse=key[1])
    return streams


def _thumb_gradient(seed):
    """Deterministic colorful 'thumbnail' gradient from a string seed.

    Gives each stream/clip card a distinct simulated preview image without any
    randomness at render time (stable across reloads / reproducible).
    """
    h = 0
    for ch in str(seed):
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    h1 = h % 360
    h2 = (h1 + 40 + (h >> 8) % 80) % 360
    ang = 90 + (h >> 16) % 120
    return (f"linear-gradient({ang}deg, "
            f"hsl({h1},60%,28%) 0%, hsl({h2},55%,16%) 55%, #0e0e10 100%)")


def _live_uptime_seconds(started_at):
    """Seconds a live stream has been broadcasting, for the ticking uptime clock.

    Seeded `started_at` values can be weeks old, which would render an absurd
    uptime. Anchor instead to the most recent occurrence of the stream's
    start time-of-day (UTC) so uptime stays a believable < 24h session that
    still differs per stream and increases in real time.
    """
    from datetime import datetime, timezone, timedelta
    if not started_at:
        return 0
    try:
        sa = datetime.fromisoformat(str(started_at).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return 0
    now = datetime.now(timezone.utc)
    anchor = now.replace(hour=sa.hour, minute=sa.minute,
                         second=sa.second, microsecond=0)
    if anchor > now:
        anchor -= timedelta(days=1)
    return int((now - anchor).total_seconds())


def _avatar_color(seed):
    """Deterministic solid avatar color (Twitch-style initial bubbles)."""
    h = 0
    for ch in str(seed):
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return f"hsl({h % 360}, 55%, 42%)"


def _fmt_count(n):
    """Twitch-style compact count: 8746 -> '8.7K', 1200000 -> '1.2M'."""
    try:
        n = int(n)
    except (ValueError, TypeError):
        return "0"
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M".replace(".0M", "M")
    if n >= 1_000:
        return f"{n/1_000:.1f}K".replace(".0K", "K")
    return str(n)


def _sidebar_channels(limit=8):
    """Top live channels for the left rail (Twitch 'Recommended Channels')."""
    live = db.query(SITE, "streams", where={"status": "live"},
                    sort="-average_viewers", limit=limit)
    out = []
    for s in live:
        u = _get_user(s["channel_id"])
        name = u["display_name"] if u else "Unknown"
        out.append({
            "id": s["channel_id"],
            "name": name,
            "initial": (name[0] if name else "?").upper(),
            "color": _avatar_color(s["channel_id"]),
            "category": s.get("category", ""),
            "live": True,
            "viewers": _fmt_count(s.get("average_viewers", 0)),
        })
    return out


@blueprint.context_processor
def _inject_sidebar():
    """Make the left-rail channel list available to every live/ template."""
    from flask import request as _rq
    if "/api/" in _rq.path:
        return {}
    try:
        return {"sidebar_channels": _sidebar_channels(), "fmt_count": _fmt_count}
    except Exception:
        return {"sidebar_channels": [], "fmt_count": _fmt_count}


# ---------------------------------------------------------------------------
# Data helpers  (all queries use WHERE/LIMIT/OFFSET — never load full tables)
# ---------------------------------------------------------------------------

def _get_user(user_id):
    user = db.get_item(SITE, "users", user_id)
    if not user:
        # Try numeric ID → ls-u-NNN format
        try:
            padded = f"ls-u-{int(user_id):03d}"
            user = db.get_item(SITE, "users", padded)
        except (ValueError, TypeError):
            pass
    return user


def _get_user_by_username(username):
    users = db.query(SITE, "users", where={"username": username}, limit=1)
    return users[0] if users else None


def _get_current_user():
    uid = session.get("live_user_id")
    if uid:
        return _get_user(uid)
    return None


def _get_browsing_user():
    """Return logged-in user or fall back to first user for browse-only."""
    user = _get_current_user()
    if user:
        return user, True
    users = db.query(SITE, "users", limit=1)
    if users:
        return users[0], False
    return None, False


def _get_categories():
    """Return sorted list of unique categories across all streams."""
    rows = db.execute(
        "SELECT DISTINCT category FROM live_streams ORDER BY category",
        fetch="all",
    )
    return [r["category"] for r in rows]


def _get_streamers():
    """Return users who have at least one stream."""
    rows = db.execute(
        "SELECT DISTINCT u.* FROM live_users u "
        "INNER JOIN live_streams s ON u.id = s.channel_id "
        "ORDER BY u.display_name",
        fetch="all",
    )
    return rows


def _get_featured_stream():
    """Pick the stream with the most viewers to feature as 'live now'.

    Returns (stream, streamer_user) or (None, None).
    """
    # Prefer an actually-live stream, fall back to highest-viewed completed one
    featured = db.query(SITE, "streams", where={"status": "live"},
                        sort="-average_viewers", limit=1)
    if not featured:
        featured = db.query(SITE, "streams", sort="-average_viewers", limit=1)
    if not featured:
        return None, None
    stream = featured[0]
    streamer = _get_user(stream["channel_id"])
    return stream, streamer


# ---------------------------------------------------------------------------
# Search / semantic helpers
# ---------------------------------------------------------------------------

def _keyword_score(query, stream):
    """Simple keyword overlap scoring for semantic-style search."""
    terms = query.lower().split()
    text = " ".join([
        stream.get("title", ""),
        stream.get("category", ""),
        " ".join(stream.get("tags", []) if isinstance(stream.get("tags"), list) else []),
    ]).lower()
    return sum(1 for t in terms if t in text)


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    user, logged_in = _get_browsing_user()

    # Featured "Live Now" stream
    featured_stream, featured_streamer = _get_featured_stream()

    # Collect chat message count for the featured stream (used by JS poller)
    featured_chat_count = 0
    if featured_stream:
        featured_chat_count = db.count(
            SITE, "chat_messages",
            where={"stream_id": featured_stream["id"]},
        )
        # If the featured stream has no chat, grab total across all streams
        if featured_chat_count == 0:
            featured_chat_count = db.count(SITE, "chat_messages")

    # Search (search_by_query)
    q = request.args.get("q", "").strip()

    # Filters (filter_by_dropdown)
    category = request.args.get("category", "").strip()
    status = request.args.get("status", "").strip()
    streamer = request.args.get("streamer", "").strip()

    # Build WHERE clause for SQL-level filtering
    where = {}
    if category:
        where["category"] = category
    if status:
        where["status"] = status
    if streamer:
        where["channel_id"] = streamer

    # Sort (sort_by_dropdown)
    sort = request.args.get("sort", "default").strip()
    sort_col = None
    if sort == "viewers":
        sort_col = "-total_views"
    elif sort == "newest":
        sort_col = "-started_at"
    elif sort == "oldest":
        sort_col = "started_at"
    elif sort == "duration":
        sort_col = "-duration_minutes"
    else:
        sort_col = "-started_at"

    if q:
        streams = db.search(SITE, "streams", q, where=where or None, limit=50)
        streams = _sort_streams(streams, sort)   # db.search ignores sort_col
    else:
        streams = db.query(SITE, "streams", where=where, sort=sort_col, limit=50)

    # For default sort, put live streams first (small result set, <50 rows)
    if sort == "default" and not q:
        live_s = [s for s in streams if s["status"] == "live"]
        past_s = [s for s in streams if s["status"] != "live"]
        streams = live_s + past_s

    # Simulated per-stream preview thumbnail (deterministic gradient)
    for s in streams:
        s["thumb_css"] = _thumb_gradient(s.get("id", "") + s.get("category", ""))
    if featured_stream:
        featured_stream["thumb_css"] = _thumb_gradient(
            featured_stream.get("id", "") + featured_stream.get("category", ""))

    # Build user lookup only for the streamers visible on this page
    channel_ids = list(set(s["channel_id"] for s in streams))
    user_map = {}
    for cid in channel_ids:
        u = _get_user(cid)
        if u:
            u["avatar_color"] = _avatar_color(cid)
            user_map[cid] = u

    if featured_streamer:
        featured_streamer["avatar_color"] = _avatar_color(featured_streamer["id"])

    featured_uptime = (_live_uptime_seconds(featured_stream.get("started_at"))
                       if featured_stream and featured_stream.get("status") == "live" else None)

    categories = _get_categories()
    streamers_list = _get_streamers()

    import random
    ad = random.choice(_AD_POOL)

    return render_template(
        "live/index.html",
        user=user, logged_in=logged_in,
        streams=streams, user_map=user_map,
        categories=categories, streamers=streamers_list,
        selected_category=category,
        selected_status=status,
        selected_streamer=streamer,
        selected_sort=sort,
        q=q, ad=ad,
        featured_stream=featured_stream,
        featured_streamer=featured_streamer,
        featured_chat_count=featured_chat_count,
        featured_uptime=featured_uptime,
    )


@blueprint.route("/stream/<stream_id>")
def stream_detail(stream_id):
    user, logged_in = _get_browsing_user()
    stream = db.get_item(SITE, "streams", stream_id)
    if not stream:
        abort(404)

    streamer = _get_user(stream["channel_id"])
    chat = db.query(SITE, "chat_messages",
                    where={"stream_id": stream_id}, sort="timestamp", limit=50)

    # Build user_map from chat user_ids + streamer
    uid_set = set(m["user_id"] for m in chat)
    uid_set.add(stream["channel_id"])
    user_map = {}
    for uid in uid_set:
        u = _get_user(uid)
        if u:
            user_map[uid] = u

    # Check join status via playback_states
    is_joined = False
    if user:
        ps = db.query(SITE, "playback_states",
                      where={"user_id": user["id"], "stream_id": stream_id}, limit=1)
        if ps and ps[0].get("joined", False):
            is_joined = True

    # Check follow status
    is_following = False
    if user and streamer:
        fols = db.query(SITE, "follows",
                        where={"follower_id": user["id"], "channel_id": stream["channel_id"]},
                        limit=1)
        is_following = len(fols) > 0

    chat_count = db.count(SITE, "chat_messages", where={"stream_id": stream_id})

    stream["thumb_css"] = _thumb_gradient(stream.get("id", "") + stream.get("category", ""))
    if streamer:
        streamer["avatar_color"] = _avatar_color(streamer["id"])

    uptime_seconds = _live_uptime_seconds(stream.get("started_at")) if stream["status"] == "live" else None

    import random
    ad = random.choice(_AD_POOL)

    return render_template(
        "live/stream.html",
        user=user, logged_in=logged_in,
        stream=stream, streamer=streamer,
        chat_messages=chat, user_map=user_map,
        chat_count=chat_count, ad=ad,
        uptime_seconds=uptime_seconds,
        is_joined=is_joined, is_following=is_following,
    )


@blueprint.route("/channel/<user_id>")
def channel_page(user_id):
    user, logged_in = _get_browsing_user()
    channel_user = _get_user(user_id)
    if not channel_user:
        abort(404)
    channel_user["avatar_color"] = _avatar_color(user_id)

    streams = db.query(SITE, "streams",
                       where={"channel_id": user_id}, sort="-started_at", limit=50)
    clips = db.query(SITE, "clips",
                     where={"channel_id": user_id}, sort="-views", limit=50)

    # Simulated preview thumbnails (deterministic gradients)
    for s in streams:
        s["thumb_css"] = _thumb_gradient(s.get("id", "") + s.get("category", ""))
    for c in clips:
        c["thumb_css"] = _thumb_gradient(c.get("id", "") + c.get("title", ""))

    # Check if current user is subscribed
    is_subscribed = False
    if user:
        subs = db.query(SITE, "subscriptions",
                        where={"subscriber_id": user["id"], "channel_id": user_id},
                        limit=1)
        is_subscribed = any(s.get("is_active", False) for s in subs)

    # Check if current user follows
    is_following = False
    if user:
        fols = db.query(SITE, "follows",
                        where={"follower_id": user["id"], "channel_id": user_id},
                        limit=1)
        is_following = len(fols) > 0

    sub_count = db.count(SITE, "subscriptions",
                         where={"channel_id": user_id, "is_active": True})
    follower_count = db.count(SITE, "follows", where={"channel_id": user_id})

    # Channel points balance for redeemable rewards
    channel_rewards = db.query(SITE, "channel_points",
                               where={"channel_id": user_id}, limit=50)

    return render_template(
        "live/channel.html",
        user=user, logged_in=logged_in,
        channel_user=channel_user,
        streams=streams, clips=clips,
        is_subscribed=is_subscribed,
        is_following=is_following,
        sub_count=sub_count,
        follower_count=follower_count,
        channel_rewards=channel_rewards,
    )


@blueprint.route("/clips")
def clips_page():
    user, logged_in = _get_browsing_user()

    channel = request.args.get("channel", "").strip()
    q = request.args.get("q", "").strip()
    where = {"channel_id": channel} if channel else None
    if q:
        # FTS5/BM25 title search (search_by_query); channel narrows via WHERE
        clips = db.search(SITE, "clips", q, where=where or None, limit=50)
    else:
        clips = db.query(SITE, "clips", where=where, sort="-views", limit=50)

    # Simulated per-clip preview thumbnail (deterministic gradient)
    for c in clips:
        c["thumb_css"] = _thumb_gradient(c.get("id", "") + c.get("title", ""))

    # Build user_map and stream_map from clip references
    cid_set = set(c["channel_id"] for c in clips)
    sid_set = set(c["stream_id"] for c in clips)
    user_map = {}
    for cid in cid_set:
        u = _get_user(cid)
        if u:
            u["avatar_color"] = _avatar_color(cid)
            user_map[cid] = u
    stream_map = {}
    for sid in sid_set:
        s = db.get_item(SITE, "streams", sid)
        if s:
            stream_map[sid] = s

    streamers_list = _get_streamers()

    return render_template(
        "live/clips.html",
        user=user, logged_in=logged_in,
        clips=clips, user_map=user_map,
        stream_map=stream_map,
        streamers=streamers_list,
        selected_channel=channel, q=q,
    )


@blueprint.route("/clip/<clip_id>")
def clip_detail(clip_id):
    user, logged_in = _get_browsing_user()
    clip = db.get_item(SITE, "clips", clip_id)
    if not clip:
        abort(404)

    clip["thumb_css"] = _thumb_gradient(clip.get("id", "") + clip.get("title", ""))
    stream = db.get_item(SITE, "streams", clip["stream_id"])
    channel_user = _get_user(clip["channel_id"])
    user_map = {}
    if channel_user:
        channel_user["avatar_color"] = _avatar_color(channel_user["id"])
        user_map[channel_user["id"]] = channel_user

    return render_template(
        "live/clip_detail.html",
        user=user, logged_in=logged_in,
        clip=clip, stream=stream,
        channel_user=channel_user, user_map=user_map,
    )


@blueprint.route("/subscriptions")
def subscriptions_page():
    user, logged_in = _get_browsing_user()
    user_subs = db.query(SITE, "subscriptions",
                         where={"subscriber_id": user["id"], "is_active": True},
                         limit=50)

    # Build user_map for channel owners
    cid_set = set(s["channel_id"] for s in user_subs)
    user_map = {}
    for cid in cid_set:
        u = _get_user(cid)
        if u:
            u["avatar_color"] = _avatar_color(cid)
            user_map[cid] = u

    return render_template(
        "live/subscriptions.html",
        user=user, logged_in=logged_in,
        subscriptions=user_subs,
        user_map=user_map,
    )


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("live/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    found = db.query(SITE, "users", where={"username": username}, limit=1)
    if not found:
        return render_template("live/login.html", error="Invalid username or password")
    target_user = found[0]
    if target_user.get("password") and target_user["password"] != password:
        return render_template("live/login.html", error="Invalid username or password")
    session["live_user_id"] = target_user["id"]
    return redirect(url_for("live.index"))


@blueprint.route("/register", methods=["GET"])
def register_page():
    return render_template("live/register.html", error=None)


@blueprint.route("/register", methods=["POST"])
def register_submit():
    """register_by_form: create a new user account."""
    username = request.form.get("username", "").strip()
    display_name = request.form.get("display_name", "").strip()
    password = request.form.get("password", "").strip()
    email = request.form.get("email", "").strip()

    if not username or not password:
        return render_template("live/register.html",
                               error="Username and password are required")

    existing = db.query(SITE, "users", where={"username": username}, limit=1)
    if existing:
        return render_template("live/register.html",
                               error="Username already taken")

    user_count = db.count(SITE, "users")
    new_user = {
        "id": f"ls-u-{uuid.uuid4().hex[:6]}",
        "root_user_id": user_count + 1,
        "username": username,
        "display_name": display_name or username,
        "channel_name": username,
        "avatar_url": f"https://streamhub.tv/avatars/{username}.jpg",
        "bio": "",
        "email": email,
        "password": password,
        "subscriber_count": 0,
        "total_views": 0,
        "is_partner": False,
        "is_affiliate": False,
        "created_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "last_seen": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "offline",
        "channel_points_balance": 500,
    }
    db.save_item(SITE, "users", new_user["id"], new_user)
    emit("signup", user_id=new_user["id"], site_name="live",
         username=username, password=password, email=email)

    session["live_user_id"] = new_user["id"]
    return redirect(url_for("live.index"))


@blueprint.route("/logout")
def logout():
    session.pop("live_user_id", None)
    return redirect(url_for("live.index"))


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/chat/live", methods=["GET"])
def api_chat_live():
    """Return a batch of chat messages for the live-chat poller.

    Query params:
        stream_id  -- restrict to one stream (optional; omit for all)
        offset     -- skip this many rows (default 0)
        limit      -- how many to return (default 5, max 20)

    The JS client polls this endpoint every 1-2 s, incrementing offset
    each time.  When offset >= total count it wraps back to 0, creating
    an infinite-loop live-chat effect.
    """
    stream_id = request.args.get("stream_id", "").strip()
    try:
        offset = max(0, int(request.args.get("offset", 0)))
    except (ValueError, TypeError):
        offset = 0
    try:
        limit = min(20, max(1, int(request.args.get("limit", 5))))
    except (ValueError, TypeError):
        limit = 5

    where = {"stream_id": stream_id} if stream_id else None

    total = db.count(SITE, "chat_messages", where=where)
    if total == 0:
        return jsonify({"messages": [], "total": 0, "next_offset": 0})

    # Wrap offset so the feed loops forever
    effective_offset = offset % total

    messages = db.query(
        SITE, "chat_messages",
        where=where,
        sort="timestamp",
        limit=limit,
        offset=effective_offset,
    )

    next_offset = offset + len(messages)

    # Never attribute rolling (seeded) chat to the logged-in user: their
    # username must only appear when they actually typed a message (those
    # are appended client-side at post time, not via this poller).
    user = _get_current_user()
    if user:
        messages = [m for m in messages if m.get("user_id") != user["id"]]

    return jsonify({
        "messages": messages,
        "total": total,
        "next_offset": next_offset,
    })


@blueprint.route("/api/streams", methods=["GET"])
def api_streams():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    status_filter = request.args.get("status", "").strip()
    streamer = request.args.get("streamer", "").strip()
    sort = request.args.get("sort", "default").strip()

    where = {}
    if category:
        where["category"] = category
    if status_filter:
        where["status"] = status_filter
    if streamer:
        where["channel_id"] = streamer

    sort_col = "-started_at"
    if sort == "viewers":
        sort_col = "-total_views"
    elif sort == "newest":
        sort_col = "-started_at"
    elif sort == "oldest":
        sort_col = "started_at"
    elif sort == "duration":
        sort_col = "-duration_minutes"

    if q:
        streams = db.search(SITE, "streams", q, where=where or None, limit=50)
        streams = _sort_streams(streams, sort)   # db.search ignores sort_col
    else:
        streams = db.query(SITE, "streams", where=where, sort=sort_col, limit=50)

    return jsonify(streams)


@blueprint.route("/api/streams/search", methods=["GET"])
def api_streams_search():
    """search_by_query: keyword search across stream titles, categories, tags."""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    rows = db.search(SITE, "streams", q, limit=50)
    return jsonify(rows)


@blueprint.route("/api/streams/semantic", methods=["GET"])
def api_streams_semantic():
    """navigate_by_semantic: semantic-style keyword overlap search."""
    q = request.args.get("q", "").strip()
    streams = db.query(SITE, "streams", limit=50)
    scored = [(s, _keyword_score(q, s)) for s in streams]
    scored = [(s, sc) for s, sc in scored if sc > 0]
    scored.sort(key=lambda x: -x[1])
    return jsonify([s for s, _ in scored])


@blueprint.route("/api/streams/<stream_id>", methods=["GET"])
def api_stream_detail(stream_id):
    stream = db.get_item(SITE, "streams", stream_id)
    if not stream:
        return jsonify({"error": "Stream not found"}), 404
    return jsonify(stream)


@blueprint.route("/api/streams/<stream_id>/chat", methods=["GET"])
def api_stream_chat_get(stream_id):
    stream = db.get_item(SITE, "streams", stream_id)
    if not stream:
        return jsonify({"error": "Stream not found"}), 404
    messages = db.query(SITE, "chat_messages", where={"stream_id": stream_id}, sort="timestamp")
    return jsonify(messages)


@blueprint.route("/api/streams/<stream_id>/chat", methods=["POST"])
def api_stream_chat_post(stream_id):
    """post_from_free_text: post a chat message to a stream."""
    stream = db.get_item(SITE, "streams", stream_id)
    if not stream:
        return jsonify({"error": "Stream not found"}), 404

    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401

    data = request.get_json(silent=True) or {}
    message_text = data.get("message", "").strip()
    if not message_text:
        return jsonify({"error": "Message cannot be empty"}), 400

    # Check if user is subscriber to channel
    sub_check = db.query(SITE, "subscriptions",
                         where={"subscriber_id": user["id"],
                                "channel_id": stream["channel_id"],
                                "is_active": True},
                         limit=1)
    is_sub = len(sub_check) > 0

    badges = []
    if stream["channel_id"] == user["id"]:
        badges.append("broadcaster")
    if is_sub:
        badges.append("subscriber")

    new_msg = {
        "id": f"chat-{uuid.uuid4().hex[:8]}",
        "stream_id": stream_id,
        "user_id": user["id"],
        "username": user["username"],
        "message": message_text,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        "is_subscriber": is_sub,
        "badges": badges,
    }

    db.save_item(SITE, "chat_messages", new_msg["id"], new_msg)
    return jsonify(new_msg), 201


TIP_AMOUNTS = [100, 500, 1000, 5000]


@blueprint.route("/api/streams/<stream_id>/tip", methods=["POST"])
def api_stream_tip(stream_id):
    """pay_by_dropdown: cheer channel points to the streamer via amount dropdown.

    The tip is paid from the viewer's channel_points_balance (Twitch-bits
    style) and posts a highlighted message into the stream chat.
    Body: {amount: int (one of TIP_AMOUNTS), message: str (optional note)}
    """
    stream = db.get_item(SITE, "streams", stream_id)
    if not stream:
        return jsonify({"error": "Stream not found"}), 404

    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401

    data = request.get_json(silent=True) or {}
    try:
        amount = int(data.get("amount", 0))
    except (ValueError, TypeError):
        amount = 0
    if amount not in TIP_AMOUNTS:
        return jsonify({"error": f"amount must be one of {TIP_AMOUNTS}"}), 400

    note = (data.get("message") or "").strip()

    user_obj = _get_user(user["id"])
    balance = user_obj.get("channel_points_balance", 0) if user_obj else 0
    if balance < amount:
        return jsonify({"error": f"Not enough channel points. Need {amount}, have {balance}"}), 400

    # Deduct points (same wallet as channel point rewards)
    user_obj["channel_points_balance"] = balance - amount
    db.save_item(SITE, "users", user_obj["id"], user_obj)

    text = f"cheered {amount} points" + (f": {note}" if note else "!")
    new_msg = {
        "id": f"chat-{uuid.uuid4().hex[:8]}",
        "stream_id": stream_id,
        "user_id": user["id"],
        "username": user["username"],
        "message": text,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        "is_subscriber": False,
        "badges": ["cheer"],
        "tip_amount": amount,
    }
    db.save_item(SITE, "chat_messages", new_msg["id"], new_msg)

    result = dict(new_msg)
    result["remaining_balance"] = balance - amount
    return jsonify(result), 201


@blueprint.route("/api/clips", methods=["GET"])
def api_clips_get():
    channel = request.args.get("channel", "").strip()
    where = {"channel_id": channel} if channel else None
    clips = db.query(SITE, "clips", where=where, sort="-views", limit=50)
    return jsonify(clips)


@blueprint.route("/api/clips/<clip_id>", methods=["GET"])
def api_clip_detail(clip_id):
    clip = db.get_item(SITE, "clips", clip_id)
    if not clip:
        return jsonify({"error": "Clip not found"}), 404
    return jsonify(clip)


@blueprint.route("/api/channels/<user_id>", methods=["GET"])
def api_channel(user_id):
    channel_user = _get_user(user_id)
    if not channel_user:
        return jsonify({"error": "Channel not found"}), 404

    streams = db.query(SITE, "streams", where={"channel_id": user_id}, sort="-started_at")
    clips = db.query(SITE, "clips", where={"channel_id": user_id})

    sub_count = db.count(SITE, "subscriptions", where={"channel_id": user_id, "is_active": True})

    follower_count = db.count(SITE, "follows", where={"channel_id": user_id})

    return jsonify({
        "channel": channel_user,
        "streams": streams,
        "clips": clips,
        "subscriber_count": sub_count,
        "follower_count": follower_count,
    })


@blueprint.route("/api/channels/<user_id>/subscribe", methods=["POST"])
def api_channel_subscribe(user_id):
    """subscribe_by_toggle: toggle subscription to a channel."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401

    channel_user = _get_user(user_id)
    if not channel_user:
        return jsonify({"error": "Channel not found"}), 404

    if user["id"] == user_id:
        return jsonify({"error": "Cannot subscribe to your own channel"}), 400

    existing_list = db.query(SITE, "subscriptions",
                             where={"subscriber_id": user["id"], "channel_id": user_id},
                             limit=1)

    if existing_list:
        existing = existing_list[0]
        existing["is_active"] = not existing.get("is_active", False)
        if existing["is_active"]:
            existing["renewed_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        db.save_item(SITE, "subscriptions", existing["id"], existing)
        return jsonify({
            "status": "subscribed" if existing["is_active"] else "unsubscribed",
            "subscription": existing,
        })
    else:
        new_sub = {
            "id": f"sub-{uuid.uuid4().hex[:8]}",
            "subscriber_id": user["id"],
            "channel_id": user_id,
            "tier": "tier_1",
            "started_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "renewed_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "is_active": True,
            "is_gift": False,
            "months_subscribed": 1,
            "monthly_price_usd": 4.99,
        }
        db.save_item(SITE, "subscriptions", new_sub["id"], new_sub)
        return jsonify({"status": "subscribed", "subscription": new_sub}), 201


@blueprint.route("/api/channels/<user_id>/follow", methods=["POST"])
def api_channel_follow(user_id):
    """follow_by_toggle: toggle follow on a channel."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401

    channel_user = _get_user(user_id)
    if not channel_user:
        return jsonify({"error": "Channel not found"}), 404

    existing_list = db.query(SITE, "follows",
                             where={"follower_id": user["id"], "channel_id": user_id},
                             limit=1)

    if existing_list:
        db.delete_item(SITE, "follows", existing_list[0]["id"])
        return jsonify({"status": "unfollowed", "channel_id": user_id})
    else:
        new_follow = {
            "id": f"follow-{uuid.uuid4().hex[:8]}",
            "follower_id": user["id"],
            "channel_id": user_id,
            "followed_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        db.save_item(SITE, "follows", new_follow["id"], new_follow)
        return jsonify({"status": "followed", "follow": new_follow}), 201


@blueprint.route("/api/channels/<user_id>/gift", methods=["POST"])
def api_channel_gift_sub(user_id):
    """pay_by_dropdown: gift a subscription to another user via tier dropdown."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401

    channel_user = _get_user(user_id)
    if not channel_user:
        return jsonify({"error": "Channel not found"}), 404

    data = request.get_json(silent=True) or {}
    recipient_username = data.get("recipient_username", "").strip()
    tier = data.get("tier", "tier_1").strip()

    tier_prices = {"tier_1": 4.99, "tier_2": 9.99, "tier_3": 24.99}
    if tier not in tier_prices:
        return jsonify({"error": f"Invalid tier. Choose from: {', '.join(tier_prices)}"}), 400

    if not recipient_username:
        return jsonify({"error": "recipient_username is required"}), 400

    recipient = _get_user_by_username(recipient_username)
    if not recipient:
        return jsonify({"error": "Recipient user not found"}), 404

    if recipient["id"] == user_id:
        return jsonify({"error": "Cannot gift sub to the channel owner"}), 400

    new_sub = {
        "id": f"sub-{uuid.uuid4().hex[:8]}",
        "subscriber_id": recipient["id"],
        "channel_id": user_id,
        "tier": tier,
        "started_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "renewed_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "is_active": True,
        "is_gift": True,
        "gifted_by": user["id"],
        "months_subscribed": 1,
        "monthly_price_usd": tier_prices[tier],
    }
    db.save_item(SITE, "subscriptions", new_sub["id"], new_sub)
    return jsonify({"status": "gifted", "subscription": new_sub}), 201


@blueprint.route("/api/channels/<user_id>/rewards", methods=["GET"])
def api_channel_rewards(user_id):
    """List available channel point rewards for a channel."""
    channel_rewards = db.query(SITE, "channel_points",
                               where={"channel_id": user_id}, limit=50)
    return jsonify(channel_rewards)


@blueprint.route("/api/channels/<user_id>/redeem", methods=["POST"])
def api_channel_redeem(user_id):
    """redeem_by_dropdown: redeem a channel point reward."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401

    data = request.get_json(silent=True) or {}
    reward_id = data.get("reward_id", "").strip()

    if not reward_id:
        return jsonify({"error": "reward_id is required"}), 400

    reward = db.get_item(SITE, "channel_points", reward_id)
    if not reward or reward.get("channel_id") != user_id:
        return jsonify({"error": "Reward not found"}), 404

    cost = reward.get("cost", 0)
    user_obj = _get_user(user["id"])
    balance = user_obj.get("channel_points_balance", 0) if user_obj else 0

    if balance < cost:
        return jsonify({"error": f"Not enough channel points. Need {cost}, have {balance}"}), 400

    # Deduct points
    user_obj["channel_points_balance"] = balance - cost
    db.save_item(SITE, "users", user_obj["id"], user_obj)

    redemption = {
        "id": f"redeem-{uuid.uuid4().hex[:8]}",
        "user_id": user["id"],
        "channel_id": user_id,
        "reward_id": reward_id,
        "reward_name": reward.get("name", ""),
        "cost": cost,
        "redeemed_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "remaining_balance": balance - cost,
    }
    return jsonify({"status": "redeemed", "redemption": redemption}), 201


@blueprint.route("/api/streams/<stream_id>/join", methods=["POST"])
def api_stream_join(stream_id):
    """join_by_toggle: join or leave a stream's chat room."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401

    stream = db.get_item(SITE, "streams", stream_id)
    if not stream:
        return jsonify({"error": "Stream not found"}), 404

    existing_list = db.query(SITE, "playback_states",
                             where={"user_id": user["id"], "stream_id": stream_id},
                             limit=1)

    if existing_list:
        existing = existing_list[0]
        existing["joined"] = not existing.get("joined", False)
        db.save_item(SITE, "playback_states", existing["id"], existing)
        return jsonify({
            "status": "joined" if existing["joined"] else "left",
            "stream_id": stream_id,
        })
    else:
        new_state = {
            "id": f"pb-{uuid.uuid4().hex[:8]}",
            "user_id": user["id"],
            "stream_id": stream_id,
            "joined": True,
            "joined_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "current_timestamp": 0,
            "playback_speed": 1.0,
            "quality": "auto",
            "volume": 100,
        }
        db.save_item(SITE, "playback_states", new_state["id"], new_state)
        return jsonify({"status": "joined", "state": new_state}), 201


@blueprint.route("/api/streams/<stream_id>/playback", methods=["GET"])
def api_stream_playback_get(stream_id):
    """Get current playback state for a stream."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401

    state_list = db.query(SITE, "playback_states",
                          where={"user_id": user["id"], "stream_id": stream_id},
                          limit=1)
    if not state_list:
        return jsonify({
            "stream_id": stream_id,
            "current_timestamp": 0,
            "playback_speed": 1.0,
            "quality": "auto",
            "volume": 100,
        })
    return jsonify(state_list[0])


@blueprint.route("/api/streams/<stream_id>/playback", methods=["POST"])
def api_stream_playback_set(stream_id):
    """play_by_timestamp / play_by_playback / select_by_slider:
    Update playback state (timestamp, speed, quality, volume).
    """
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401

    stream = db.get_item(SITE, "streams", stream_id)
    if not stream:
        return jsonify({"error": "Stream not found"}), 404

    data = request.get_json(silent=True) or {}

    existing_list = db.query(SITE, "playback_states",
                             where={"user_id": user["id"], "stream_id": stream_id},
                             limit=1)
    existing = existing_list[0] if existing_list else None

    if not existing:
        existing = {
            "id": f"pb-{uuid.uuid4().hex[:8]}",
            "user_id": user["id"],
            "stream_id": stream_id,
            "joined": True,
            "current_timestamp": 0,
            "playback_speed": 1.0,
            "quality": "auto",
            "volume": 100,
        }

    # play_by_timestamp: jump to a specific second
    if "timestamp_seconds" in data:
        ts = int(data["timestamp_seconds"])
        max_ts = stream.get("duration_minutes", 0) * 60
        if max_ts > 0 and ts > max_ts:
            ts = max_ts
        existing["current_timestamp"] = ts

    # play_by_playback: change playback speed
    if "playback_speed" in data:
        speed = float(data["playback_speed"])
        allowed = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]
        if speed not in allowed:
            return jsonify({"error": f"Invalid speed. Choose from: {allowed}"}), 400
        existing["playback_speed"] = speed

    # select_by_slider: quality selection
    if "quality" in data:
        quality = data["quality"].strip()
        allowed_q = ["auto", "160p", "360p", "480p", "720p", "1080p"]
        if quality not in allowed_q:
            return jsonify({"error": f"Invalid quality. Choose from: {allowed_q}"}), 400
        existing["quality"] = quality

    # select_by_slider: volume (0-100)
    if "volume" in data:
        vol = int(data["volume"])
        vol = max(0, min(100, vol))
        existing["volume"] = vol

    db.save_item(SITE, "playback_states", existing["id"], existing)
    return jsonify({"status": "updated", "playback": existing})


@blueprint.route("/api/streams/<stream_id>/share", methods=["POST"])
def api_stream_share(stream_id):
    """share_by_dropdown: share a stream via a platform dropdown."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401

    stream = db.get_item(SITE, "streams", stream_id)
    if not stream:
        return jsonify({"error": "Stream not found"}), 404

    data = request.get_json(silent=True) or {}
    platform = data.get("platform", "").strip()
    allowed_platforms = ["twitter", "facebook", "reddit", "discord", "copy_link", "email"]
    if platform not in allowed_platforms:
        return jsonify({"error": f"Invalid platform. Choose from: {', '.join(allowed_platforms)}"}), 400

    new_share = {
        "id": f"share-{uuid.uuid4().hex[:8]}",
        "user_id": user["id"],
        "stream_id": stream_id,
        "platform": platform,
        "share_url": f"https://streamhub.tv/stream/{stream_id}?ref={user['id']}",
        "shared_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    db.save_item(SITE, "shares", new_share["id"], new_share)
    return jsonify({"status": "shared", "share": new_share}), 201


@blueprint.route("/api/report", methods=["POST"])
def api_report():
    """report_by_form: submit a report for a stream or user."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401

    data = request.get_json(silent=True) or {}
    target_type = data.get("target_type", "").strip()  # "stream" or "user"
    target_id = data.get("target_id", "").strip()
    reason = data.get("reason", "").strip()
    description = data.get("description", "").strip()

    allowed_reasons = [
        "harassment", "spam", "hate_speech", "nudity",
        "violence", "misinformation", "copyright", "other",
    ]

    if target_type not in ("stream", "user"):
        return jsonify({"error": "target_type must be 'stream' or 'user'"}), 400
    if not target_id:
        return jsonify({"error": "target_id is required"}), 400
    if reason not in allowed_reasons:
        return jsonify({"error": f"Invalid reason. Choose from: {', '.join(allowed_reasons)}"}), 400

    new_report = {
        "id": f"report-{uuid.uuid4().hex[:8]}",
        "reporter_id": user["id"],
        "target_type": target_type,
        "target_id": target_id,
        "reason": reason,
        "description": description,
        "status": "pending",
        "created_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    db.save_item(SITE, "reports", new_report["id"], new_report)
    return jsonify({"status": "submitted", "report": new_report}), 201


@blueprint.route("/api/shares", methods=["GET"])
def api_shares():
    """List all shares, optionally filtered by stream_id."""
    stream_id = request.args.get("stream_id", "").strip()
    where = {"stream_id": stream_id} if stream_id else None
    shares = db.query(SITE, "shares", where=where, limit=50)
    return jsonify(shares)


@blueprint.route("/api/reports", methods=["GET"])
def api_reports():
    """List all reports."""
    reports = db.query(SITE, "reports", limit=50)
    return jsonify(reports)


@blueprint.route("/api/follows", methods=["GET"])
def api_follows():
    """List all follows, optionally filtered by channel_id or follower_id."""
    channel_id = request.args.get("channel_id", "").strip()
    follower_id = request.args.get("follower_id", "").strip()
    where = {}
    if channel_id:
        where["channel_id"] = channel_id
    if follower_id:
        where["follower_id"] = follower_id
    follows = db.query(SITE, "follows", where=where or None, limit=50)
    return jsonify(follows)


@blueprint.route("/api/subscriptions", methods=["GET"])
def api_subscriptions():
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401

    user_subs = db.query(SITE, "subscriptions",
                         where={"subscriber_id": user["id"], "is_active": True},
                         limit=50)
    return jsonify(user_subs)


@blueprint.route("/api/categories", methods=["GET"])
def api_categories():
    """List all categories with stream counts."""
    rows = db.execute(
        "SELECT category, COUNT(*) as cnt FROM live_streams GROUP BY category ORDER BY category",
        fetch="all",
    )
    return jsonify([{"name": r["category"], "count": r["cnt"]} for r in rows])


@blueprint.route("/api/login", methods=["POST"])
def api_login():
    """authenticate_by_form: log in via API."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    found = db.query(SITE, "users", where={"username": username}, limit=1)
    if not found:
        return jsonify({"error": "Invalid credentials"}), 401
    target_user = found[0]
    if target_user.get("password") and target_user["password"] != password:
        return jsonify({"error": "Invalid credentials"}), 401
    session["live_user_id"] = target_user["id"]
    return jsonify({"user_id": target_user["id"], "username": target_user["username"]})


@blueprint.route("/api/register", methods=["POST"])
def api_register():
    """register_by_form: create a new user account via API."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    display_name = data.get("display_name", "").strip()
    password = data.get("password", "").strip()
    email = data.get("email", "").strip()

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    existing = db.query(SITE, "users", where={"username": username}, limit=1)
    if existing:
        return jsonify({"error": "Username already taken"}), 409

    user_count = db.count(SITE, "users")
    new_user = {
        "id": f"ls-u-{uuid.uuid4().hex[:6]}",
        "root_user_id": user_count + 1,
        "username": username,
        "display_name": display_name or username,
        "channel_name": username,
        "avatar_url": f"https://streamhub.tv/avatars/{username}.jpg",
        "bio": "",
        "email": email,
        "password": password,
        "subscriber_count": 0,
        "total_views": 0,
        "is_partner": False,
        "is_affiliate": False,
        "created_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "last_seen": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "offline",
        "channel_points_balance": 500,
    }
    db.save_item(SITE, "users", new_user["id"], new_user)
    emit("signup", user_id=new_user["id"], site_name="live",
         username=username, password=password, email=email)

    session["live_user_id"] = new_user["id"]
    return jsonify({
        "user_id": new_user["id"],
        "username": new_user["username"],
    }), 201


@blueprint.route("/api/users/<user_id>", methods=["GET"])
def api_user_detail(user_id):
    """Get user profile details."""
    user = _get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    safe = {k: v for k, v in user.items() if k != "password"}
    return jsonify(safe)


@blueprint.route("/api/stats", methods=["GET"])
def api_stats():
    total_streams = db.count(SITE, "streams")
    live_count = db.count(SITE, "streams", where={"status": "live"})
    total_clips = db.count(SITE, "clips")
    total_users = db.count(SITE, "users")
    active_subs = db.count(SITE, "subscriptions", where={"is_active": True})
    total_chat = db.count(SITE, "chat_messages")

    total_views = db.execute(
        "SELECT COALESCE(SUM(total_views), 0) FROM live_streams",
        fetch="val",
    )

    cat_rows = db.execute(
        "SELECT category, COUNT(*) as cnt, COALESCE(SUM(total_views),0) as tv "
        "FROM live_streams GROUP BY category ORDER BY category",
        fetch="all",
    )
    categories = {
        r["category"]: {"stream_count": r["cnt"], "total_views": r["tv"]}
        for r in cat_rows
    }

    return jsonify({
        "total_streams": total_streams,
        "live_streams": live_count,
        "total_clips": total_clips,
        "total_users": total_users,
        "total_views": total_views,
        "active_subscriptions": active_subs,
        "total_chat_messages": total_chat,
        "categories": categories,
    })

