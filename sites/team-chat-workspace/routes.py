"""Meridian Systems Team Chat — Slack/Teams-style workspace.

Reads team-chat data (channels, messages, threads, reactions, users) from
DATA_SOURCES_DIR and serves a full chat workspace with channel browsing,
threaded conversations, member directory, and message search.
"""

import pathlib
from datetime import datetime

from flask import (
    Blueprint, Response, abort, jsonify, redirect, render_template, request,
    session, url_for,
)
from app import db
from app.events import emit

SITE = "team-chat-workspace"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "team-chat-workspace",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _users():
    return db.query(SITE, "users")


def _channels():
    return db.query(SITE, "channels")


def _messages():
    return db.query(SITE, "messages")


def _reactions():
    return db.query(SITE, "reactions")


def _threads():
    return db.query(SITE, "threads")


def _user_map():
    """Return dict mapping user id -> user record."""
    return {u["id"]: u for u in _users()}


def _channel_map():
    """Return dict mapping channel id -> channel record."""
    return {c["id"]: c for c in _channels()}


def _current_user():
    """Return the current logged-in user record, or None."""
    uid = session.get("user_id")
    if uid is None:
        return None
    # user_id in session is the root_user_id (integer)
    results = db.query(SITE, "users", where={"root_user_id": uid}, limit=1)
    if results:
        return results[0]
    # fallback: try matching by id string
    user = db.get_item(SITE, "users", uid)
    if user:
        return user
    formatted_id = f"tc-u{uid:03d}"
    user = db.get_item(SITE, "users", formatted_id)
    if user:
        return user
    users = _users()
    return users[0] if users else None


def _reactions_for_message(msg_id):
    """Get reactions for a specific message, grouped by emoji."""
    all_rxn = _reactions()
    user_map = _user_map()
    msg_rxns = [r for r in all_rxn if r["message_id"] == msg_id]
    grouped = {}
    for r in msg_rxns:
        emoji = r["emoji"]
        if emoji not in grouped:
            grouped[emoji] = {"emoji": emoji, "count": 0, "users": []}
        grouped[emoji]["count"] += 1
        u = user_map.get(r["user_id"])
        if u:
            grouped[emoji]["users"].append(u["display_name"])
    return list(grouped.values())


def _thread_for_message(msg_id):
    """Get thread data for a parent message, if any."""
    for t in _threads():
        if t["parent_message_id"] == msg_id:
            return t
    return None


def _enrich_messages(msgs):
    """Add user info, reactions, and thread data to messages."""
    user_map = _user_map()
    enriched = []
    for m in msgs:
        em = dict(m)
        em["user"] = user_map.get(m["user_id"], {})
        em["reactions"] = _reactions_for_message(m["id"])
        em["thread"] = _thread_for_message(m["id"])
        enriched.append(em)
    return enriched


def _format_timestamp(ts_str):
    """Parse ISO timestamp string to datetime."""
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return datetime.now()


# ---------------------------------------------------------------------------
# HTML Routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    """Channel list + default channel view (general)."""
    if not _current_user():
        return redirect(url_for("team-chat-workspace.login_page"))
    channels = _channels()
    user_map = _user_map()
    current_user = _current_user()

    # Get message counts per channel for sidebar
    all_msgs = _messages()
    channel_msg_counts = {}
    channel_latest = {}
    for m in all_msgs:
        cid = m["channel_id"]
        channel_msg_counts[cid] = channel_msg_counts.get(cid, 0) + 1
        ts = m["timestamp"]
        if cid not in channel_latest or ts > channel_latest[cid]:
            channel_latest[cid] = ts

    for c in channels:
        c["message_count"] = channel_msg_counts.get(c["id"], 0)
        c["latest_message"] = channel_latest.get(c["id"], "")

    # Show general channel by default
    default_channel = channels[0] if channels else None
    channel_messages = []
    if default_channel:
        channel_messages = [m for m in all_msgs if m["channel_id"] == default_channel["id"]]
        channel_messages.sort(key=lambda m: m["timestamp"])
        channel_messages = _enrich_messages(channel_messages)

    return render_template(
        "team-chat-workspace/index.html",
        channels=channels,
        active_channel=default_channel,
        messages=channel_messages,
        user_map=user_map,
        current_user=current_user,
    )


@blueprint.route("/channel/<channel_id>")
def channel_view(channel_id):
    """View a specific channel with its messages."""
    if not _current_user():
        return redirect(url_for("team-chat-workspace.login_page"))
    channels = _channels()
    channel_map = _channel_map()
    channel = channel_map.get(channel_id)
    if not channel:
        abort(404)

    user_map = _user_map()
    current_user = _current_user()

    all_msgs = _messages()

    # Sidebar counts
    channel_msg_counts = {}
    channel_latest = {}
    for m in all_msgs:
        cid = m["channel_id"]
        channel_msg_counts[cid] = channel_msg_counts.get(cid, 0) + 1
        ts = m["timestamp"]
        if cid not in channel_latest or ts > channel_latest[cid]:
            channel_latest[cid] = ts
    for c in channels:
        c["message_count"] = channel_msg_counts.get(c["id"], 0)
        c["latest_message"] = channel_latest.get(c["id"], "")

    # Filter messages for this channel
    channel_messages = [m for m in all_msgs if m["channel_id"] == channel_id]

    # Apply date filter
    date_filter = request.args.get("date")
    if date_filter:
        channel_messages = [m for m in channel_messages if m["timestamp"].startswith(date_filter)]

    # Apply user filter
    user_filter = request.args.get("user")
    if user_filter:
        channel_messages = [m for m in channel_messages if m["user_id"] == user_filter]

    channel_messages.sort(key=lambda m: m["timestamp"])
    channel_messages = _enrich_messages(channel_messages)

    return render_template(
        "team-chat-workspace/channel.html",
        channels=channels,
        active_channel=channel,
        messages=channel_messages,
        user_map=user_map,
        current_user=current_user,
        date_filter=date_filter,
        user_filter=user_filter,
    )


@blueprint.route("/threads")
def threads_view():
    """View all threads across channels."""
    if not _current_user():
        return redirect(url_for("team-chat-workspace.login_page"))
    channels = _channels()
    channel_map = _channel_map()
    user_map = _user_map()
    current_user = _current_user()
    all_threads = _threads()
    all_msgs = _messages()
    msg_map = {m["id"]: m for m in all_msgs}

    # Enrich threads with parent message and channel info
    enriched_threads = []
    for t in all_threads:
        et = dict(t)
        parent = msg_map.get(t["parent_message_id"], {})
        et["parent_message"] = parent
        et["parent_user"] = user_map.get(parent.get("user_id", ""), {})
        et["channel"] = channel_map.get(t["channel_id"], {})
        et["reply_count"] = len(t.get("replies", []))
        et["last_reply"] = t["replies"][-1] if t.get("replies") else None
        if et["last_reply"]:
            et["last_reply"]["user"] = user_map.get(et["last_reply"].get("user_id", ""), {})
        # Enrich all replies with user info
        for r in et.get("replies", []):
            r["user"] = user_map.get(r.get("user_id", ""), {})
        enriched_threads.append(et)

    # Sort by latest reply
    enriched_threads.sort(
        key=lambda t: t["last_reply"]["timestamp"] if t.get("last_reply") else "",
        reverse=True,
    )

    # Channel filter
    channel_filter = request.args.get("channel")
    if channel_filter:
        enriched_threads = [t for t in enriched_threads if t["channel_id"] == channel_filter]

    return render_template(
        "team-chat-workspace/threads.html",
        channels=channels,
        threads=enriched_threads,
        user_map=user_map,
        current_user=current_user,
        channel_filter=channel_filter,
    )


@blueprint.route("/thread/<thread_id>")
def thread_detail(thread_id):
    if not _current_user():
        return redirect(url_for("team-chat-workspace.login_page"))
    """View a specific thread with all replies."""
    channels = _channels()
    channel_map = _channel_map()
    user_map = _user_map()
    current_user = _current_user()
    all_threads = _threads()
    all_msgs = _messages()
    msg_map = {m["id"]: m for m in all_msgs}

    thread = None
    for t in all_threads:
        if t["id"] == thread_id:
            thread = dict(t)
            break
    if not thread:
        abort(404)

    parent = msg_map.get(thread["parent_message_id"], {})
    thread["parent_message"] = parent
    thread["parent_user"] = user_map.get(parent.get("user_id", ""), {})
    thread["channel"] = channel_map.get(thread["channel_id"], {})
    thread["parent_reactions"] = _reactions_for_message(parent.get("id", ""))

    # Enrich replies with user info
    for r in thread.get("replies", []):
        r["user"] = user_map.get(r.get("user_id", ""), {})

    return render_template(
        "team-chat-workspace/thread_detail.html",
        channels=channels,
        thread=thread,
        user_map=user_map,
        current_user=current_user,
    )


@blueprint.route("/members")
def members_view():
    """Member directory."""
    if not _current_user():
        return redirect(url_for("team-chat-workspace.login_page"))
    channels = _channels()
    users = _users()
    current_user = _current_user()

    # Department filter
    dept_filter = request.args.get("department")
    if dept_filter:
        users = [u for u in users if u.get("department") == dept_filter]

    # Search filter
    search_q = request.args.get("q", "").strip()
    if search_q:
        q_lower = search_q.lower()
        users = [u for u in users if (
            q_lower in u.get("display_name", "").lower() or
            q_lower in u.get("username", "").lower() or
            q_lower in u.get("title", "").lower() or
            q_lower in u.get("department", "").lower()
        )]

    # Get unique departments for filter
    all_users = _users()
    departments = sorted(set(u.get("department", "") for u in all_users if u.get("department")))

    return render_template(
        "team-chat-workspace/members.html",
        channels=channels,
        users=users,
        departments=departments,
        current_user=current_user,
        dept_filter=dept_filter,
        search_q=search_q,
    )


@blueprint.route("/search")
def search_view():
    """Search messages across all channels."""
    if not _current_user():
        return redirect(url_for("team-chat-workspace.login_page"))
    channels = _channels()
    channel_map = _channel_map()
    user_map = _user_map()
    current_user = _current_user()

    query = request.args.get("q", "").strip()
    channel_filter = request.args.get("channel")
    user_filter = request.args.get("user")
    date_filter = request.args.get("date")

    results = []
    if query:
        q_lower = query.lower()
        all_msgs = _messages()
        for m in all_msgs:
            if q_lower in m.get("text", "").lower():
                results.append(m)

        # Apply channel filter
        if channel_filter:
            results = [m for m in results if m["channel_id"] == channel_filter]

        # Apply user filter
        if user_filter:
            results = [m for m in results if m["user_id"] == user_filter]

        # Apply date filter
        if date_filter:
            results = [m for m in results if m["timestamp"].startswith(date_filter)]

        # Sort by relevance (most recent first)
        results.sort(key=lambda m: m["timestamp"], reverse=True)

        # Enrich results
        for r in results:
            r["user"] = user_map.get(r["user_id"], {})
            r["channel"] = channel_map.get(r["channel_id"], {})

    # Also search thread replies
    thread_results = []
    if query:
        q_lower = query.lower()
        all_threads = _threads()
        for t in all_threads:
            for reply in t.get("replies", []):
                if q_lower in reply.get("text", "").lower():
                    enriched_reply = dict(reply)
                    enriched_reply["user"] = user_map.get(reply.get("user_id", ""), {})
                    enriched_reply["channel"] = channel_map.get(t["channel_id"], {})
                    enriched_reply["thread_id"] = t["id"]
                    enriched_reply["thread_topic"] = t.get("topic", "")
                    thread_results.append(enriched_reply)

    return render_template(
        "team-chat-workspace/search.html",
        channels=channels,
        results=results,
        thread_results=thread_results,
        user_map=user_map,
        current_user=current_user,
        query=query,
        channel_filter=channel_filter,
        user_filter=user_filter,
        date_filter=date_filter,
        all_users=_users(),
    )


@blueprint.route("/login")
def login_page():
    """Login page."""
    return render_template("team-chat-workspace/login.html")


@blueprint.route("/login", methods=["POST"])
def login_submit():
    """Handle login form submission."""
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    if not username:
        return render_template("team-chat-workspace/login.html", error="Username required")
    users = _users()
    user = next((u for u in users if u.get("username") == username or u.get("display_name") == username), None)
    if not user:
        return render_template("team-chat-workspace/login.html", error="User not found")
    stored_pw = user.get("password", "password")
    if password and password != stored_pw:
        return render_template("team-chat-workspace/login.html", error="Invalid password")
    session["user_id"] = user["root_user_id"]
    emit("signup", user_id=user["root_user_id"], site_name="team-chat-workspace", username=username, password=password, email="")
    return redirect(url_for("team-chat-workspace.index"))


@blueprint.route("/logout")
def logout():
    """Log out."""
    session.pop("user_id", None)
    return redirect(url_for("team-chat-workspace.login_page"))


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/channels", methods=["GET"])
def api_channels_list():
    """GET list of all channels."""
    channels = _channels()
    all_msgs = _messages()

    # Add message counts
    channel_msg_counts = {}
    for m in all_msgs:
        cid = m["channel_id"]
        channel_msg_counts[cid] = channel_msg_counts.get(cid, 0) + 1
    for c in channels:
        c["message_count"] = channel_msg_counts.get(c["id"], 0)

    return jsonify(channels)


@blueprint.route("/api/channels", methods=["POST"])
def api_channels_create():
    """POST create a new channel."""
    data = request.get_json(silent=True) or {}
    if not data.get("name"):
        return jsonify({"error": "Channel name is required"}), 400

    channels = _channels()
    current_user = _current_user()

    new_id = f"ch-{data['name'].lower().replace(' ', '-')}"
    # Check for duplicate
    if any(c["id"] == new_id for c in channels):
        return jsonify({"error": "Channel with this name already exists"}), 409

    new_channel = {
        "id": new_id,
        "name": data["name"].lower().replace(" ", "-"),
        "description": data.get("description", ""),
        "is_private": data.get("is_private", False),
        "created_by": current_user["id"] if current_user else "tc-u001",
        "created_date": datetime.now().strftime("%Y-%m-%d"),
        "member_count": 1,
        "topic": data.get("topic", ""),
        "pinned_count": 0,
    }
    channels.append(new_channel)
    db.save_collection(SITE, "channels", channels)
    return jsonify(new_channel), 201


@blueprint.route("/api/channels/<channel_id>", methods=["GET"])
def api_channel_detail(channel_id):
    """GET channel details."""
    channel_map = _channel_map()
    channel = channel_map.get(channel_id)
    if not channel:
        return jsonify({"error": "Channel not found"}), 404

    # Add message count
    all_msgs = _messages()
    channel["message_count"] = sum(1 for m in all_msgs if m["channel_id"] == channel_id)

    return jsonify(channel)


@blueprint.route("/api/channels/<channel_id>/messages", methods=["GET"])
def api_channel_messages(channel_id):
    """GET messages for a channel."""
    channel_map = _channel_map()
    if channel_id not in channel_map:
        return jsonify({"error": "Channel not found"}), 404

    all_msgs = _messages()
    channel_msgs = [m for m in all_msgs if m["channel_id"] == channel_id]

    # Date filter
    date_filter = request.args.get("date")
    if date_filter:
        channel_msgs = [m for m in channel_msgs if m["timestamp"].startswith(date_filter)]

    # User filter
    user_filter = request.args.get("user")
    if user_filter:
        channel_msgs = [m for m in channel_msgs if m["user_id"] == user_filter]

    channel_msgs.sort(key=lambda m: m["timestamp"])
    channel_msgs = _enrich_messages(channel_msgs)

    return jsonify({"channel_id": channel_id, "messages": channel_msgs, "count": len(channel_msgs)})


@blueprint.route("/api/channels/<channel_id>/messages", methods=["POST"])
def api_channel_send_message(channel_id):
    """POST send a message to a channel."""
    channel_map = _channel_map()
    if channel_id not in channel_map:
        return jsonify({"error": "Channel not found"}), 404

    data = request.get_json(silent=True) or {}
    if not data.get("text"):
        return jsonify({"error": "Message text is required"}), 400

    current_user = _current_user()
    all_msgs = _messages()

    new_msg = {
        "id": f"msg-{len(all_msgs) + 1:03d}",
        "channel_id": channel_id,
        "user_id": current_user["id"] if current_user else "tc-u001",
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "text": data["text"],
        "edited": False,
        "reactions_count": 0,
        "thread_count": 0,
    }
    all_msgs.append(new_msg)
    db.save_collection(SITE, "messages", all_msgs)
    if any(kw in data["text"].lower() for kw in ("meeting", "standup", "sync", "call at", "let's meet")):
        emit("booking", user_id=new_msg["user_id"], title=f"Meeting: {data['text'][:40]}", start=datetime.now().strftime("%Y-%m-%d"), location="")
    return jsonify(new_msg), 201


@blueprint.route("/api/threads", methods=["GET"])
def api_threads_list():
    """GET list of all threads."""
    all_threads = _threads()
    user_map = _user_map()
    channel_map = _channel_map()
    msg_map = {m["id"]: m for m in _messages()}

    # Channel filter
    channel_filter = request.args.get("channel")
    if channel_filter:
        all_threads = [t for t in all_threads if t["channel_id"] == channel_filter]

    enriched = []
    for t in all_threads:
        et = dict(t)
        parent = msg_map.get(t["parent_message_id"], {})
        et["parent_message"] = parent
        et["parent_user"] = user_map.get(parent.get("user_id", ""), {})
        et["channel"] = channel_map.get(t["channel_id"], {})
        et["reply_count"] = len(t.get("replies", []))
        for r in et.get("replies", []):
            r["user"] = user_map.get(r.get("user_id", ""), {})
        enriched.append(et)

    return jsonify(enriched)


@blueprint.route("/api/threads/<thread_id>", methods=["GET"])
def api_thread_detail(thread_id):
    """GET a specific thread."""
    all_threads = _threads()
    user_map = _user_map()
    channel_map = _channel_map()
    msg_map = {m["id"]: m for m in _messages()}

    thread = None
    for t in all_threads:
        if t["id"] == thread_id:
            thread = dict(t)
            break
    if not thread:
        return jsonify({"error": "Thread not found"}), 404

    parent = msg_map.get(thread["parent_message_id"], {})
    thread["parent_message"] = parent
    thread["parent_user"] = user_map.get(parent.get("user_id", ""), {})
    thread["channel"] = channel_map.get(thread["channel_id"], {})
    for r in thread.get("replies", []):
        r["user"] = user_map.get(r.get("user_id", ""), {})

    return jsonify(thread)


@blueprint.route("/api/threads/<thread_id>", methods=["POST"])
def api_thread_reply(thread_id):
    """POST a reply to a thread."""
    all_threads = _threads()
    user_map = _user_map()
    current_user = _current_user()

    thread = None
    thread_idx = None
    for i, t in enumerate(all_threads):
        if t["id"] == thread_id:
            thread = t
            thread_idx = i
            break
    if not thread:
        return jsonify({"error": "Thread not found"}), 404

    data = request.get_json(silent=True) or {}
    if not data.get("text"):
        return jsonify({"error": "Reply text is required"}), 400

    reply_num = len(thread.get("replies", [])) + 1
    new_reply = {
        "id": f"{thread_id}-r{reply_num}",
        "user_id": current_user["id"] if current_user else "tc-u001",
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "text": data["text"],
    }
    all_threads[thread_idx]["replies"].append(new_reply)
    db.save_collection(SITE, "threads", all_threads)

    new_reply["user"] = user_map.get(new_reply["user_id"], {})
    return jsonify(new_reply), 201


@blueprint.route("/api/messages/<message_id>/react", methods=["POST"])
def api_message_react(message_id):
    """POST add a reaction to a message."""
    data = request.get_json(silent=True) or {}
    emoji = data.get("emoji")
    if not emoji:
        return jsonify({"error": "Emoji is required"}), 400

    current_user = _current_user()
    reactions = _reactions()

    # Check if user already reacted with this emoji
    existing = None
    for i, r in enumerate(reactions):
        if (r["message_id"] == message_id and
            r["user_id"] == (current_user["id"] if current_user else "tc-u001") and
            r["emoji"] == emoji):
            existing = i
            break

    if existing is not None:
        # Toggle off - remove the reaction
        reactions.pop(existing)
        db.save_collection(SITE, "reactions", reactions)
        return jsonify({"status": "removed", "emoji": emoji})

    new_rxn = {
        "id": f"rxn-{len(reactions) + 1:03d}",
        "message_id": message_id,
        "user_id": current_user["id"] if current_user else "tc-u001",
        "emoji": emoji,
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    reactions.append(new_rxn)
    db.save_collection(SITE, "reactions", reactions)

    # Update message reactions_count
    msgs = _messages()
    for m in msgs:
        if m["id"] == message_id:
            m["reactions_count"] = sum(1 for r in reactions if r["message_id"] == message_id)
            break
    db.save_collection(SITE, "messages", msgs)

    return jsonify({"status": "added", "reaction": new_rxn}), 201


@blueprint.route("/api/messages/search", methods=["GET"])
def api_messages_search():
    """Search messages by query string."""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"results": [], "count": 0})

    q_lower = query.lower()
    all_msgs = _messages()
    user_map = _user_map()
    channel_map = _channel_map()

    results = []
    for m in all_msgs:
        if q_lower in m.get("text", "").lower():
            em = dict(m)
            em["user"] = user_map.get(m["user_id"], {})
            em["channel"] = channel_map.get(m["channel_id"], {})
            results.append(em)

    # Also search thread replies
    thread_results = []
    for t in _threads():
        for reply in t.get("replies", []):
            if q_lower in reply.get("text", "").lower():
                er = dict(reply)
                er["user"] = user_map.get(reply.get("user_id", ""), {})
                er["channel"] = channel_map.get(t["channel_id"], {})
                er["thread_id"] = t["id"]
                thread_results.append(er)

    # Channel filter
    channel_filter = request.args.get("channel")
    if channel_filter:
        results = [r for r in results if r.get("channel_id") == channel_filter]
        thread_results = [r for r in thread_results if r["channel"].get("id") == channel_filter]

    # User filter
    user_filter = request.args.get("user")
    if user_filter:
        results = [r for r in results if r.get("user_id") == user_filter]
        thread_results = [r for r in thread_results if r.get("user_id") == user_filter]

    results.sort(key=lambda m: m.get("timestamp", ""), reverse=True)

    return jsonify({
        "query": query,
        "results": results,
        "thread_results": thread_results,
        "count": len(results) + len(thread_results),
    })


@blueprint.route("/api/members", methods=["GET"])
def api_members():
    """GET list of all members."""
    users = _users()

    # Department filter
    dept = request.args.get("department")
    if dept:
        users = [u for u in users if u.get("department") == dept]

    # Search
    q = request.args.get("q", "").strip()
    if q:
        q_lower = q.lower()
        users = [u for u in users if (
            q_lower in u.get("display_name", "").lower() or
            q_lower in u.get("username", "").lower() or
            q_lower in u.get("title", "").lower()
        )]

    return jsonify(users)


@blueprint.route("/api/stats", methods=["GET"])
def api_stats():
    """GET workspace statistics."""
    channels = _channels()
    users = _users()
    msgs = _messages()
    threads = _threads()
    reactions = _reactions()

    # Most active channels
    channel_activity = {}
    for m in msgs:
        cid = m["channel_id"]
        channel_activity[cid] = channel_activity.get(cid, 0) + 1
    channel_map = _channel_map()
    top_channels = sorted(channel_activity.items(), key=lambda x: x[1], reverse=True)[:5]
    top_channels = [{"channel": channel_map.get(cid, {}), "message_count": cnt} for cid, cnt in top_channels]

    # Most active users
    user_activity = {}
    for m in msgs:
        uid = m["user_id"]
        user_activity[uid] = user_activity.get(uid, 0) + 1
    user_map = _user_map()
    top_users = sorted(user_activity.items(), key=lambda x: x[1], reverse=True)[:5]
    top_users = [{"user": user_map.get(uid, {}), "message_count": cnt} for uid, cnt in top_users]

    # Most reacted messages
    reaction_counts = {}
    for r in reactions:
        mid = r["message_id"]
        reaction_counts[mid] = reaction_counts.get(mid, 0) + 1
    msg_map = {m["id"]: m for m in msgs}
    top_reacted = sorted(reaction_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    top_reacted_msgs = []
    for mid, cnt in top_reacted:
        m = msg_map.get(mid, {})
        top_reacted_msgs.append({
            "message": m,
            "user": user_map.get(m.get("user_id", ""), {}),
            "reaction_count": cnt,
        })

    return jsonify({
        "total_channels": len(channels),
        "total_members": len(users),
        "total_messages": len(msgs),
        "total_threads": len(threads),
        "total_reactions": len(reactions),
        "top_channels": top_channels,
        "top_users": top_users,
        "top_reacted_messages": top_reacted_msgs,
    })


@blueprint.route("/api/messages/<message_id>", methods=["PUT"])
def api_message_edit(message_id):
    """PUT edit a message (edit_by_form macro)."""
    data = request.get_json(silent=True) or {}
    if not data.get("text"):
        return jsonify({"error": "New text is required"}), 400

    msgs = _messages()
    msg = None
    for m in msgs:
        if m["id"] == message_id:
            msg = m
            break
    if not msg:
        return jsonify({"error": "Message not found"}), 404

    msg["text"] = data["text"]
    msg["edited"] = True
    db.save_collection(SITE, "messages", msgs)
    return jsonify(msg)


@blueprint.route("/message/<message_id>/delete", methods=["POST"])
def form_delete_message(message_id):
    """Delete a message via form POST and redirect back."""
    msgs = _messages()
    msg = next((m for m in msgs if m["id"] == message_id), None)
    channel_id = msg["channel_id"] if msg else "ch-general"
    msgs = [m for m in msgs if m["id"] != message_id]
    db.save_collection(SITE, "messages", msgs)
    # Also remove related reactions
    reactions = _reactions()
    reactions = [r for r in reactions if r["message_id"] != message_id]
    db.save_collection(SITE, "reactions", reactions)
    return redirect(url_for("team-chat-workspace.channel_view", channel_id=channel_id))


@blueprint.route("/api/messages/<message_id>", methods=["DELETE"])
def api_message_delete(message_id):
    """DELETE a message (delete_from_table macro)."""
    msgs = _messages()
    msg = None
    for m in msgs:
        if m["id"] == message_id:
            msg = m
            break
    if not msg:
        return jsonify({"error": "Message not found"}), 404

    msgs = [m for m in msgs if m["id"] != message_id]
    db.save_collection(SITE, "messages", msgs)

    # Also remove related reactions
    reactions = _reactions()
    reactions = [r for r in reactions if r["message_id"] != message_id]
    db.save_collection(SITE, "reactions", reactions)

    return jsonify({"status": "deleted", "message_id": message_id})


@blueprint.route("/api/upload", methods=["POST"])
def api_upload():
    """Upload a file to a channel (upload_by_upload macro)."""
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "No file selected"}), 400
    content = f.read()
    channel_id = request.form.get("channel_id", "ch-general")
    current_user = _current_user()

    # Create a message about the upload
    all_msgs = _messages()
    new_msg = {
        "id": f"msg-{len(all_msgs) + 1:03d}",
        "channel_id": channel_id,
        "user_id": current_user["id"] if current_user else "tc-u001",
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "text": f"[File uploaded: {f.filename} ({len(content)} bytes)]",
        "edited": False,
        "reactions_count": 0,
        "thread_count": 0,
    }
    all_msgs.append(new_msg)
    db.save_collection(SITE, "messages", all_msgs)

    # If this is a form submission (not API), redirect back to channel
    if request.content_type and "multipart/form-data" in request.content_type:
        return redirect(url_for("team-chat-workspace.channel_view", channel_id=channel_id))

    return jsonify({
        "status": "uploaded",
        "filename": f.filename,
        "size": len(content),
        "message": new_msg,
    }), 201


@blueprint.route("/api/channels/<channel_id>/follow", methods=["POST"])
def api_channel_follow(channel_id):
    """Toggle follow/unfollow a channel (follow_by_toggle macro)."""
    channel_map = _channel_map()
    if channel_id not in channel_map:
        return jsonify({"error": "Channel not found"}), 404

    current_user = _current_user()
    users = _users()
    user = None
    for u in users:
        if u["id"] == (current_user["id"] if current_user else "tc-u001"):
            user = u
            break
    if not user:
        user = users[0]

    followed = user.get("followed_channels", [])
    if channel_id in followed:
        followed.remove(channel_id)
        action = "unfollowed"
    else:
        followed.append(channel_id)
        action = "followed"
    user["followed_channels"] = followed
    db.save_collection(SITE, "users", users)
    return jsonify({"action": action, "channel_id": channel_id})


@blueprint.route("/api/channels/<channel_id>/join", methods=["POST"])
def api_channel_join(channel_id):
    """Toggle join/leave a channel (join_by_toggle macro)."""
    channels = _channels()
    channel = None
    for c in channels:
        if c["id"] == channel_id:
            channel = c
            break
    if not channel:
        return jsonify({"error": "Channel not found"}), 404

    current_user = _current_user()
    users = _users()
    user = None
    for u in users:
        if u["id"] == (current_user["id"] if current_user else "tc-u001"):
            user = u
            break
    if not user:
        user = users[0]

    joined = user.get("joined_channels", [])
    if channel_id in joined:
        joined.remove(channel_id)
        action = "left"
        channel["member_count"] = max(0, channel.get("member_count", 1) - 1)
    else:
        joined.append(channel_id)
        action = "joined"
        channel["member_count"] = channel.get("member_count", 0) + 1
    user["joined_channels"] = joined
    db.save_collection(SITE, "users", users)
    db.save_collection(SITE, "channels", channels)
    return jsonify({"action": action, "channel_id": channel_id})


@blueprint.route("/api/messages/<message_id>/save", methods=["POST"])
def api_message_save(message_id):
    """Toggle save/unsave a message (save_by_toggle macro)."""
    current_user = _current_user()
    users = _users()
    user = None
    for u in users:
        if u["id"] == (current_user["id"] if current_user else "tc-u001"):
            user = u
            break
    if not user:
        user = users[0]

    saved = user.get("saved_messages", [])
    if message_id in saved:
        saved.remove(message_id)
        action = "unsaved"
    else:
        saved.append(message_id)
        action = "saved"
    user["saved_messages"] = saved
    db.save_collection(SITE, "users", users)
    return jsonify({"action": action, "message_id": message_id})


@blueprint.route("/api/members/<member_id>/block", methods=["POST"])
def api_member_block(member_id):
    """Toggle block/unblock a member (block_by_toggle macro)."""
    current_user = _current_user()
    users = _users()
    user = None
    for u in users:
        if u["id"] == (current_user["id"] if current_user else "tc-u001"):
            user = u
            break
    if not user:
        user = users[0]

    blocked = user.get("blocked_users", [])
    if member_id in blocked:
        blocked.remove(member_id)
        action = "unblocked"
    else:
        blocked.append(member_id)
        action = "blocked"
    user["blocked_users"] = blocked
    db.save_collection(SITE, "users", users)
    return jsonify({"action": action, "member_id": member_id})


@blueprint.route("/channel/<channel_id>/invite", methods=["POST"])
def form_channel_invite(channel_id):
    """Invite a member to a channel via form POST."""
    _email = request.form.get("email", "").strip()
    return redirect(url_for("team-chat-workspace.channel_view", channel_id=channel_id))


@blueprint.route("/api/channels/<channel_id>/invite", methods=["POST"])
def api_channel_invite(channel_id):
    """Invite a member to a channel (invite_by_form macro)."""
    channel_map = _channel_map()
    if channel_id not in channel_map:
        return jsonify({"error": "Channel not found"}), 404

    data = request.get_json(silent=True) or {}
    invitee_id = data.get("user_id")
    if not invitee_id:
        return jsonify({"error": "User ID is required"}), 400

    user_map = _user_map()
    if invitee_id not in user_map:
        return jsonify({"error": "User not found"}), 404

    return jsonify({
        "status": "invited",
        "channel_id": channel_id,
        "user_id": invitee_id,
        "invited_by": _current_user()["id"] if _current_user() else "tc-u001",
    })


@blueprint.route("/api/messages/<message_id>/share", methods=["POST"])
def api_message_share(message_id):
    """Share a message to another channel (share_by_dropdown macro)."""
    data = request.get_json(silent=True) or {}
    target_channel = data.get("channel_id")
    if not target_channel:
        return jsonify({"error": "Target channel is required"}), 400

    channel_map = _channel_map()
    if target_channel not in channel_map:
        return jsonify({"error": "Target channel not found"}), 404

    # Find original message
    msg_map = {m["id"]: m for m in _messages()}
    original = msg_map.get(message_id)
    if not original:
        return jsonify({"error": "Message not found"}), 404

    # Create shared message in target channel
    all_msgs = _messages()
    current_user = _current_user()
    shared_msg = {
        "id": f"msg-{len(all_msgs) + 1:03d}",
        "channel_id": target_channel,
        "user_id": current_user["id"] if current_user else "tc-u001",
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "text": f"[Shared from #{channel_map.get(original['channel_id'], {}).get('name', 'unknown')}] {original['text']}",
        "edited": False,
        "reactions_count": 0,
        "thread_count": 0,
    }
    all_msgs.append(shared_msg)
    db.save_collection(SITE, "messages", all_msgs)

    return jsonify({"status": "shared", "shared_message": shared_msg}), 201


@blueprint.route("/api/users/<user_id>/follow", methods=["POST"])
def api_user_follow(user_id):
    """Follow/unfollow a user (follow_by_dropdown macro)."""
    user_map = _user_map()
    if user_id not in user_map:
        return jsonify({"error": "User not found"}), 404

    current_user = _current_user()
    users = _users()
    me = None
    for u in users:
        if u["id"] == (current_user["id"] if current_user else "tc-u001"):
            me = u
            break
    if not me:
        me = users[0]

    following = me.get("following", [])
    if user_id in following:
        following.remove(user_id)
        action = "unfollowed"
    else:
        following.append(user_id)
        action = "followed"
    me["following"] = following
    db.save_collection(SITE, "users", users)
    return jsonify({"action": action, "user_id": user_id})


@blueprint.route("/api/export")
def api_export():
    """Export channels or messages as JSON or CSV."""
    fmt = request.args.get("format", "json").lower()
    data_type = request.args.get("type", "channels").lower()

    if data_type == "messages":
        data = _messages()
    elif data_type == "members":
        data = _users()
    else:
        data = _channels()

    if fmt == "csv":
        if not data:
            return Response("", mimetype="text/csv")
        keys = list(data[0].keys())
        lines = [",".join(keys)]
        for row in data:
            vals = []
            for k in keys:
                v = str(row.get(k, "")).replace('"', '""')
                vals.append(f'"{v}"')
            lines.append(",".join(vals))
        return Response("\n".join(lines), mimetype="text/csv",
                        headers={"Content-Disposition": f"attachment; filename={data_type}.csv"})
    return jsonify(data)

