"""QuickChat — instant-messaging web app (WhatsApp Web / Telegram style).

Serves conversations, messages, contacts, and shared media from JSON data
files located in DATA_SOURCES_DIR/instant-messaging/.
"""
import base64
import hashlib
import html as html_lib
import json
import mimetypes
import pathlib
import urllib.parse
import uuid
from datetime import datetime

from flask import (
    Blueprint, Response, abort, jsonify, redirect, render_template, request, session, url_for,
)
from app import db
from app.events import emit

SITE = "instant-messaging"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "instant-messaging",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

CURRENT_USER_ID = "im-u001"  # Alex Rivera is the logged-in user

# A conversation thread is paginated at the SQL level so we never load a whole
# 300+ message history into Python (see CLAUDE.md DB rules). Page 1 = newest.
MESSAGES_PER_PAGE = 30

# Cap how many bytes of an uploaded file we inline as a data-URI. Real media
# apps offload to object storage; here we persist the bytes into the session
# overlay so the image actually renders back, but we refuse to balloon the
# overlay with huge blobs.
MAX_INLINE_MEDIA_BYTES = 2 * 1024 * 1024  # 2 MB


@blueprint.before_request
def _auto_login_im():
    """Default to Alex Rivera, mirroring the global /sites/* auto-login.

    The global before_request in app/__init__.py sets session["user_id"],
    but this site keys its login on "im_user_id" — so without this hook the
    site always lands on the login page. Same opt-outs as the global hook.
    """
    import os
    if os.environ.get("MINIWEB_NO_AUTOLOGIN") or session.get("_no_autologin"):
        return
    if "im_user_id" not in session and request.endpoint != "instant-messaging.logout":
        session["im_user_id"] = CURRENT_USER_ID

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _get_conversations(**kwargs):
    return db.query(SITE, "conversations", **kwargs)


def _get_messages(**kwargs):
    return db.query(SITE, "messages", **kwargs)


def _get_media(**kwargs):
    return db.query(SITE, "media", **kwargs)


def _get_users():
    return db.query(SITE, "users")


def _user_map():
    """Return dict mapping user id -> user record."""
    return {u["id"]: u for u in _get_users()}


def _format_file_size(size_bytes):
    """Format bytes into human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def _media_kind(media):
    """Classify a media row as image / video / audio / file for rendering."""
    mtype = (media.get("type") or "").lower()
    if mtype in ("image", "video", "audio"):
        return mtype
    mime = (media.get("mime_type") or "").lower()
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("video/"):
        return "video"
    if mime.startswith("audio/"):
        return "audio"
    return "file"


def _placeholder_data_uri(media, kind):
    """Deterministic inline SVG stand-in for seeded media that carries no bytes.

    The 55 seeded media rows only store a file_path pointing at storage we don't
    have, so there is nothing to decode. Rather than fall back to a bare filename
    chip, we synthesize a stable, per-file gradient thumbnail (a classic photo/
    play/file glyph) so an <img> actually renders in the thread.
    """
    seed = hashlib.md5((media.get("id", "") or media.get("file_name", "")).encode()).hexdigest()
    c1, c2 = "#" + seed[:6], "#" + seed[8:14]
    label = html_lib.escape((media.get("file_name") or "attachment")[:26])
    if kind == "video":
        glyph = "<polygon points='150,80 150,120 185,100' fill='#ffffff'/>"
    elif kind == "audio":
        glyph = ("<rect x='142' y='82' width='8' height='30' fill='#fff'/>"
                 "<circle cx='140' cy='112' r='9' fill='#fff'/>"
                 "<rect x='170' y='74' width='8' height='30' fill='#fff'/>"
                 "<circle cx='168' cy='104' r='9' fill='#fff'/>")
    elif kind == "image":
        glyph = ("<circle cx='128' cy='84' r='12' fill='#ffffff'/>"
                 "<polygon points='108,124 138,92 160,124' fill='#ffffff'/>"
                 "<polygon points='150,124 176,100 196,124' fill='#ffffff' opacity='.85'/>")
    else:
        glyph = ("<rect x='132' y='74' width='36' height='46' rx='3' fill='#ffffff'/>"
                 "<rect x='140' y='84' width='20' height='4' fill='" + c1 + "'/>"
                 "<rect x='140' y='94' width='20' height='4' fill='" + c1 + "'/>"
                 "<rect x='140' y='104' width='14' height='4' fill='" + c1 + "'/>")
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' width='300' height='200'>"
        f"<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>"
        f"<stop offset='0' stop-color='{c1}'/><stop offset='1' stop-color='{c2}'/>"
        "</linearGradient></defs>"
        "<rect width='300' height='200' fill='url(#g)'/>"
        f"{glyph}"
        f"<text x='150' y='160' font-size='13' fill='#ffffff' text-anchor='middle' "
        f"font-family='sans-serif'>{label}</text>"
        "</svg>"
    )
    return "data:image/svg+xml;utf8," + urllib.parse.quote(svg)


def _enrich_media(media):
    """Attach render_kind + render_src to a media dict for inline display.

    render_src is the uploaded data-URI when we persisted the real bytes,
    otherwise a synthesized placeholder thumbnail. render_is_real flags whether
    the bytes are genuine (drives <img>/<video> vs. placeholder styling).
    """
    if not media:
        return media
    kind = _media_kind(media)
    data_uri = media.get("data_uri")
    enriched = {
        **media,
        "render_kind": kind,
        "render_is_real": bool(data_uri),
        "render_src": data_uri or _placeholder_data_uri(media, kind),
    }
    return enriched


def _conversation_display_name(conv, users_map):
    """Return display name for a conversation from the perspective of the current user."""
    if conv["type"] == "group":
        return conv.get("name", "Group Chat")
    # For direct chats, show the other person's name
    for pid in conv["participants"]:
        if pid != CURRENT_USER_ID:
            user = users_map.get(pid)
            if user:
                return user["display_name"]
    return "Unknown"


def _conversation_avatar_status(conv, users_map):
    """Return (about, status) for a conversation."""
    if conv["type"] == "group":
        return ("Group", "group")
    for pid in conv["participants"]:
        if pid != CURRENT_USER_ID:
            user = users_map.get(pid)
            if user:
                return (user.get("about", ""), user.get("status", "offline"))
    return ("", "offline")


def _get_last_message_for_conv(conv_id, messages):
    """Return the last message in a conversation."""
    conv_msgs = [m for m in messages if m["conversation_id"] == conv_id]
    if not conv_msgs:
        return None
    conv_msgs.sort(key=lambda m: m["timestamp"])
    return conv_msgs[-1]


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    if "im_user_id" not in session:
        return redirect(url_for("instant-messaging.login_page"))
    conversations = _get_conversations()
    messages = _get_messages()
    users_map = _user_map()

    # Sidebar controls: sort order + message-date range filter.
    sort_by = request.args.get("sort", "recent").strip().lower()
    date_from = request.args.get("from", "").strip()
    date_to = request.args.get("to", "").strip()

    # Date filter (SQL-level): restrict the list to conversations that have at
    # least one message inside the [from, to] range. The date inputs emit
    # YYYY-MM-DD; make `to` inclusive of the whole day.
    date_filtered_ids = None
    if date_from or date_to:
        clauses, params = [], []
        if date_from:
            clauses.append("[timestamp] >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("[timestamp] <= ?")
            params.append(date_to + "T23:59:59Z")
        rows = db.execute(
            "SELECT DISTINCT conversation_id FROM instant_messaging_messages "
            "WHERE " + " AND ".join(clauses),
            tuple(params),
        )
        date_filtered_ids = {r["conversation_id"] for r in rows}

    # Build unread counts per conversation
    unread_counts = {}
    for msg in messages:
        if not msg.get("read") and msg.get("sender_id") != CURRENT_USER_ID:
            cid = msg.get("conversation_id", "")
            unread_counts[cid] = unread_counts.get(cid, 0) + 1

    # Enrich conversations with display info
    conv_list = []
    for conv in conversations:
        if date_filtered_ids is not None and conv["id"] not in date_filtered_ids:
            continue
        name = _conversation_display_name(conv, users_map)
        about, status = _conversation_avatar_status(conv, users_map)
        last_msg = _get_last_message_for_conv(conv["id"], messages)
        last_text = last_msg["text"][:60] + "..." if last_msg and len(last_msg["text"]) > 60 else (last_msg["text"] if last_msg else "")
        last_time = last_msg["timestamp"] if last_msg else conv.get("last_message", "")
        # Format time
        try:
            dt = datetime.fromisoformat(last_time.replace("Z", "+00:00"))
            time_display = dt.strftime("%I:%M %p")
        except (ValueError, AttributeError):
            time_display = ""
        conv_list.append({
            **conv,
            "display_name": name,
            "about": about,
            "status": status,
            "last_text": last_text,
            "last_time": time_display,
            "last_timestamp": last_time,
            "unread_count": unread_counts.get(conv["id"], 0),
        })

    # Order the list per the selected sort option.
    #   recent -> most recent message first (default)
    #   name   -> alphabetical by display name
    #   unread -> most unread first, recency as tiebreaker
    # recency wins the default ordering — a conversation that just received a
    # message must surface on top; pinned conversations keep their badge, not
    # their rank. conv_list is <100 rows and sort keys are derived (not columns),
    # so the ordering is done here rather than in SQL.
    if sort_by == "name":
        conv_list.sort(key=lambda c: c.get("display_name", "").lower())
    elif sort_by == "unread":
        conv_list.sort(
            key=lambda c: (c.get("unread_count", 0), c.get("last_timestamp", "")),
            reverse=True,
        )
    else:
        sort_by = "recent"
        conv_list.sort(key=lambda c: c.get("last_timestamp", ""), reverse=True)

    return render_template(
        "instant-messaging/index.html",
        conversations=conv_list,
        current_user_id=CURRENT_USER_ID,
        users_map=users_map,
        sort_by=sort_by,
        date_from=date_from,
        date_to=date_to,
    )


@blueprint.route("/conversation/<conv_id>")
def conversation_page(conv_id):
    if "im_user_id" not in session:
        return redirect(url_for("instant-messaging.login_page"))
    conversations = _get_conversations()
    all_messages = _get_messages()
    users_map = _user_map()

    conv = next((c for c in conversations if c["id"] == conv_id), None)
    if not conv:
        abort(404)

    # --- Message pagination (SQL LIMIT/OFFSET) -----------------------------
    # Threads run to hundreds of messages, so never load the whole history.
    # Page 1 is the newest window; higher pages walk further back in time.
    total_messages = db.count(SITE, "messages", where={"conversation_id": conv_id})
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    offset = (page - 1) * MESSAGES_PER_PAGE
    # Fetch newest-first at the SQL level, then flip to chronological for display.
    page_desc = db.query(
        SITE, "messages",
        where={"conversation_id": conv_id},
        sort="-timestamp",
        limit=MESSAGES_PER_PAGE,
        offset=offset,
    )
    conv_messages = list(reversed(page_desc))
    has_older = offset + MESSAGES_PER_PAGE < total_messages
    has_newer = page > 1

    # Media only for the messages actually shown on this page (small set).
    media_ids = [m.get("media_id") for m in conv_messages if m.get("media_id")]
    media_map = {}
    for mid in set(media_ids):
        rec = db.get_item(SITE, "media", mid)
        if rec:
            media_map[mid] = rec

    # Receipts: mark the recipient's messages we can now see as read, and flip
    # OUR delivered messages to read (the recipient has "seen" this thread), so
    # the other side is not fully inert. Bounded to the displayed page.
    for msg in conv_messages:
        if msg.get("read"):
            continue
        msg["read"] = 1
        db.save_item(SITE, "messages", msg["id"], msg)

    # Enrich messages with sender info and media
    enriched_messages = []
    for msg in conv_messages:
        sender = users_map.get(msg["sender_id"], {})
        media = _enrich_media(media_map.get(msg.get("media_id"))) if msg.get("media_id") else None
        try:
            dt = datetime.fromisoformat(msg["timestamp"].replace("Z", "+00:00"))
            time_display = dt.strftime("%b %d, %I:%M %p")
        except (ValueError, AttributeError):
            time_display = msg["timestamp"]
        enriched_messages.append({
            **msg,
            "sender_name": sender.get("display_name", "Unknown"),
            "sender_photo": sender.get("profile_photo", ""),
            "time_display": time_display,
            "is_current_user": msg["sender_id"] == CURRENT_USER_ID,
            "media": media,
        })

    name = _conversation_display_name(conv, users_map)
    about, status = _conversation_avatar_status(conv, users_map)

    # Build unread counts for sidebar
    unread_counts = {}
    for msg in all_messages:
        if not msg.get("read") and msg.get("sender_id") != CURRENT_USER_ID:
            cid = msg.get("conversation_id", "")
            unread_counts[cid] = unread_counts.get(cid, 0) + 1

    # Build conversation list for sidebar
    conv_list = []
    for c in conversations:
        cname = _conversation_display_name(c, users_map)
        _, cstatus = _conversation_avatar_status(c, users_map)
        last_msg = _get_last_message_for_conv(c["id"], all_messages)
        last_text = last_msg["text"][:40] + "..." if last_msg and len(last_msg["text"]) > 40 else (last_msg["text"] if last_msg else "")
        try:
            dt = datetime.fromisoformat((last_msg["timestamp"] if last_msg else c.get("last_message", "")).replace("Z", "+00:00"))
            t_display = dt.strftime("%I:%M %p")
        except (ValueError, AttributeError):
            t_display = ""
        conv_list.append({
            **c,
            "display_name": cname,
            "status": cstatus,
            "last_text": last_text,
            "last_time": t_display,
            "last_timestamp": last_msg["timestamp"] if last_msg else c.get("last_message", ""),
            "unread_count": unread_counts.get(c["id"], 0),
        })
    # recency wins the ordering — a conversation that just received a message
    # must surface on top; pinned conversations keep their badge, not their rank
    conv_list.sort(key=lambda c: c.get("last_timestamp", ""), reverse=True)

    return render_template(
        "instant-messaging/conversation.html",
        conversation=conv,
        conv_name=name,
        conv_about=about,
        conv_status=status,
        messages=enriched_messages,
        conversations=conv_list,
        current_user_id=CURRENT_USER_ID,
        users_map=users_map,
        active_conv_id=conv_id,
        page=page,
        has_older=has_older,
        has_newer=has_newer,
        total_messages=total_messages,
        messages_per_page=MESSAGES_PER_PAGE,
    )


@blueprint.route("/message/<user_id>")
def open_with(user_id):
    """Open (or create) a direct conversation with a contact, then show it.

    Clicking a contact should start messaging them: reuse the existing direct
    thread if one exists, otherwise create it, then land on the chat.
    """
    if "im_user_id" not in session:
        return redirect(url_for("instant-messaging.login_page"))

    target = next((u for u in _get_users() if u["id"] == user_id), None)
    if not target:
        abort(404)

    conversations = _get_conversations()
    want = {CURRENT_USER_ID, user_id}
    existing = next(
        (c for c in conversations
         if c.get("type") == "direct" and set(c.get("participants", [])) == want),
        None,
    )
    if existing:
        return redirect(url_for("instant-messaging.conversation_page", conv_id=existing["id"]))

    users_map = _user_map()
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    new_conv = {
        "id": f"conv-{uuid.uuid4().hex[:6]}",
        "type": "direct",
        "participants": [CURRENT_USER_ID, user_id],
        "participant_names": [users_map[p]["display_name"]
                              for p in (CURRENT_USER_ID, user_id) if p in users_map],
        "created": now,
        "last_message": now,
        "message_count": 0,
        "pinned_count": 0,
        "muted": False,
    }
    conversations.append(new_conv)
    db.save_collection(SITE, "conversations", conversations)
    return redirect(url_for("instant-messaging.conversation_page", conv_id=new_conv["id"]))


@blueprint.route("/contacts")
def contacts_page():
    if "im_user_id" not in session:
        return redirect(url_for("instant-messaging.login_page"))
    users = _get_users()
    conversations = _get_conversations()
    users_map = _user_map()

    # Build conversation list for sidebar nav
    all_messages = _get_messages()
    conv_list = []
    for c in conversations:
        cname = _conversation_display_name(c, users_map)
        _, cstatus = _conversation_avatar_status(c, users_map)
        last_msg = _get_last_message_for_conv(c["id"], all_messages)
        last_text = last_msg["text"][:40] + "..." if last_msg and len(last_msg["text"]) > 40 else (last_msg["text"] if last_msg else "")
        try:
            dt = datetime.fromisoformat((last_msg["timestamp"] if last_msg else c.get("last_message", "")).replace("Z", "+00:00"))
            t_display = dt.strftime("%I:%M %p")
        except (ValueError, AttributeError):
            t_display = ""
        conv_list.append({
            **c,
            "display_name": cname,
            "status": cstatus,
            "last_text": last_text,
            "last_time": t_display,
            "last_timestamp": last_msg["timestamp"] if last_msg else c.get("last_message", ""),
        })
    # recency wins the ordering — a conversation that just received a message
    # must surface on top; pinned conversations keep their badge, not their rank
    conv_list.sort(key=lambda c: c.get("last_timestamp", ""), reverse=True)

    # Exclude current user from contacts
    contacts = [u for u in users if u["id"] != CURRENT_USER_ID]

    return render_template(
        "instant-messaging/contacts.html",
        contacts=contacts,
        conversations=conv_list,
        current_user_id=CURRENT_USER_ID,
        users_map=users_map,
        added=request.args.get("added"),
    )


@blueprint.route("/contact/<user_id>")
def contact_detail_page(user_id):
    """View a single contact's details (with an inline edit form)."""
    if "im_user_id" not in session:
        return redirect(url_for("instant-messaging.login_page"))
    users_map = _user_map()
    contact = users_map.get(user_id)
    if not contact or user_id == CURRENT_USER_ID:
        abort(404)
    return render_template(
        "instant-messaging/contact_detail.html",
        contact=contact,
        current_user_id=CURRENT_USER_ID,
        users_map=users_map,
        saved=request.args.get("saved"),
    )


@blueprint.route("/contact/<user_id>/edit", methods=["POST"])
def contact_edit(user_id):
    """Persist basic edits to a contact (display name, phone, about/status)."""
    if "im_user_id" not in session:
        return redirect(url_for("instant-messaging.login_page"))
    user = next((u for u in _get_users() if u["id"] == user_id), None)
    if not user or user_id == CURRENT_USER_ID:
        abort(404)
    display_name = request.form.get("display_name", "").strip()
    if display_name:
        user["display_name"] = display_name
    user["phone"] = request.form.get("phone", "").strip()
    user["about"] = request.form.get("about", "").strip()
    # Small table (users); save_item upserts one row into the session overlay.
    db.save_item(SITE, "users", user_id, user)
    return redirect(url_for("instant-messaging.contact_detail_page", user_id=user_id, saved=1))


@blueprint.route("/login")
def login_page():
    return render_template("instant-messaging/login.html")


@blueprint.route("/add-contact", methods=["POST"])
def form_add_contact():
    """Add/invite a contact via form POST.

    Persists a contact (reusing an existing user when the email/name/phone
    already matches one, otherwise creating a new user row) and links a direct
    conversation with them, mirroring the `open_with` flow. Redirects back to
    the contacts page with a success flag.
    """
    if "im_user_id" not in session:
        return redirect(url_for("instant-messaging.login_page"))
    raw = request.form.get("email", "").strip()
    if not raw:
        return redirect(url_for("instant-messaging.contacts_page"))

    users = _get_users()
    key = raw.lower()
    existing = next(
        (u for u in users if u["id"] != CURRENT_USER_ID and (
            u.get("email", "").lower() == key
            or u.get("display_name", "").lower() == key
            or u.get("phone", "") == raw)),
        None,
    )
    if existing:
        contact_id = existing["id"]
    else:
        contact_id = f"im-u-{uuid.uuid4().hex[:6]}"
        is_email = "@" in raw
        display_name = raw.split("@")[0].replace(".", " ").title() if is_email else raw
        new_user = {
            "id": contact_id,
            "root_user_id": 0,
            "display_name": display_name,
            "phone": "" if is_email else raw,
            "email": raw if is_email else "",
            "status": "offline",
            "last_seen": "",
            "profile_photo": "",
            "about": "",
        }
        # Small table (users); save_item upserts one row into the session overlay.
        db.save_item(SITE, "users", contact_id, new_user)

    # Link a direct conversation with the contact (create if none exists).
    conversations = _get_conversations()
    want = {CURRENT_USER_ID, contact_id}
    conv = next(
        (c for c in conversations
         if c.get("type") == "direct" and set(c.get("participants", [])) == want),
        None,
    )
    if conv is None:
        users_map = _user_map()  # reflects the just-saved contact
        now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        new_conv = {
            "id": f"conv-{uuid.uuid4().hex[:6]}",
            "type": "direct",
            "participants": [CURRENT_USER_ID, contact_id],
            "participant_names": [users_map[p]["display_name"]
                                  for p in (CURRENT_USER_ID, contact_id) if p in users_map],
            "created": now,
            "last_message": now,
            "message_count": 0,
            "pinned_count": 0,
            "muted": False,
        }
        conversations.append(new_conv)
        db.save_collection(SITE, "conversations", conversations)

    return redirect(url_for("instant-messaging.contacts_page", added=1))


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _get_users()
    user = next((u for u in users if u.get("username") == username or u.get("display_name") == username or u.get("phone") == username), None)
    if not user:
        return render_template("instant-messaging/login.html", error="User not found.")
    stored_pw = user.get("password", "password")
    if password and password != stored_pw:
        return render_template("instant-messaging/login.html", error="Invalid password.")
    session["im_user_id"] = user["id"]
    emit("signup", user_id=user["id"], site_name="instant-messaging", username=username, password=password, email="")
    return redirect(url_for("instant-messaging.index"))


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------


@blueprint.route("/logout")
def logout():
    session.pop("im_user_id", None)
    return redirect(url_for("instant-messaging.login_page"))

@blueprint.route("/api/conversations", methods=["GET"])
def api_conversations_list():
    conversations = _get_conversations()
    messages = _get_messages()
    users_map = _user_map()

    q = request.args.get("q", "").strip().lower()
    conv_type = request.args.get("type", "").strip().lower()  # "direct" or "group"

    results = []
    for conv in conversations:
        name = _conversation_display_name(conv, users_map)
        _, status = _conversation_avatar_status(conv, users_map)
        last_msg = _get_last_message_for_conv(conv["id"], messages)

        # Filter by type
        if conv_type and conv["type"] != conv_type:
            continue

        # Filter by search query (matches conversation name or participant names)
        if q:
            searchable = name.lower() + " " + " ".join(
                n.lower() for n in conv.get("participant_names", [])
            )
            if q not in searchable:
                continue

        results.append({
            "id": conv["id"],
            "type": conv["type"],
            "name": conv.get("name"),
            "display_name": name,
            "participants": conv["participants"],
            "participant_names": conv.get("participant_names", []),
            "created": conv["created"],
            "last_message": conv["last_message"],
            "last_message_text": last_msg["text"] if last_msg else None,
            "message_count": conv["message_count"],
            "pinned_count": conv["pinned_count"],
            "muted": conv["muted"],
            "status": status,
        })

    results.sort(key=lambda c: c.get("last_message", ""), reverse=True)
    return jsonify(results)


@blueprint.route("/api/conversations/<conv_id>", methods=["GET"])
def api_conversation_detail(conv_id):
    conversations = _get_conversations()
    all_messages = _get_messages()
    media_list = _get_media()
    users_map = _user_map()

    conv = next((c for c in conversations if c["id"] == conv_id), None)
    if not conv:
        abort(404)

    # Optional SQL pagination (page 1 = newest) so the API can page a long
    # thread just like the HTML view; defaults to the newest window.
    total_messages = db.count(SITE, "messages", where={"conversation_id": conv_id})
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    per_page = MESSAGES_PER_PAGE
    offset = (page - 1) * per_page
    page_desc = db.query(
        SITE, "messages",
        where={"conversation_id": conv_id},
        sort="-timestamp",
        limit=per_page,
        offset=offset,
    )
    conv_messages = list(reversed(page_desc))

    # Apply date filter if provided (within the page window)
    date_from = request.args.get("from")
    date_to = request.args.get("to")
    if date_from:
        conv_messages = [m for m in conv_messages if m["timestamp"] >= date_from]
    if date_to:
        conv_messages = [m for m in conv_messages if m["timestamp"] <= date_to]

    # Build media map for just the shown messages
    media_map = {m["id"]: m for m in media_list}

    enriched = []
    for msg in conv_messages:
        sender = users_map.get(msg["sender_id"], {})
        media = _enrich_media(media_map.get(msg.get("media_id"))) if msg.get("media_id") else None
        enriched.append({
            "id": msg["id"],
            "sender_id": msg["sender_id"],
            "sender_name": sender.get("display_name", "Unknown"),
            "timestamp": msg["timestamp"],
            "text": msg["text"],
            "read": msg["read"],
            "media": media,
        })

    name = _conversation_display_name(conv, users_map)

    return jsonify({
        "id": conv["id"],
        "type": conv["type"],
        "name": conv.get("name"),
        "display_name": name,
        "participants": conv["participants"],
        "participant_names": conv.get("participant_names", []),
        "created": conv["created"],
        "message_count": conv["message_count"],
        "page": page,
        "per_page": per_page,
        "total_messages": total_messages,
        "has_older": offset + per_page < total_messages,
        "has_newer": page > 1,
        "messages": enriched,
    })


@blueprint.route("/api/conversations/<conv_id>/messages", methods=["POST"])
def api_send_message(conv_id):
    conversations = _get_conversations()
    conv = next((c for c in conversations if c["id"] == conv_id), None)
    if not conv:
        abort(404)

    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "Message text is required"}), 400

    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    new_msg = {
        "id": f"im-msg-{uuid.uuid4().hex[:8]}",
        "conversation_id": conv_id,
        "sender_id": CURRENT_USER_ID,
        "timestamp": now,
        "text": text,
        "read": False,
        "media_id": None,
    }

    # Single-row upsert into the session overlay — never rewrite the whole
    # (5000+ row) messages collection just to append one bubble.
    db.save_item(SITE, "messages", new_msg["id"], new_msg)

    # Update conversation last_message timestamp (single-row upsert).
    conv["last_message"] = now
    conv["message_count"] = conv.get("message_count", 0) + 1
    db.save_item(SITE, "conversations", conv_id, conv)

    return jsonify(new_msg), 201


@blueprint.route("/api/share_targets", methods=["GET"])
def api_share_targets():
    """List the current user's conversations so the share modal can pick a recipient."""
    conversations = _get_conversations()
    users_map = _user_map()
    mine = [c for c in conversations if CURRENT_USER_ID in c.get("participants", [])]
    mine.sort(key=lambda c: c.get("last_message", ""), reverse=True)
    targets = [{"id": c["id"], "name": _conversation_display_name(c, users_map)} for c in mine]
    return jsonify({"ok": True, "targets": targets})


@blueprint.route("/api/share", methods=["POST"])
def api_share_receiver():
    """Cross-site share target: post the shared link into a chosen (or most recent) chat."""
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "Shared link").strip()
    url = (data.get("url") or "").strip()
    text = (data.get("text") or "").strip()
    # `text` is the user-edited message; fall back to title + url when empty.
    body = text if text else "\n".join(p for p in [title, url] if p)

    conversations = _get_conversations()
    mine = [c for c in conversations if CURRENT_USER_ID in c.get("participants", [])]
    if not mine:
        return jsonify({"ok": False, "error": "No conversation to share into"}), 400
    conv_id = (data.get("conversation_id") or "").strip()
    conv = next((c for c in mine if c["id"] == conv_id), None) if conv_id else None
    if conv is None:
        mine.sort(key=lambda c: c.get("last_message", ""), reverse=True)
        conv = mine[0]

    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    new_msg = {
        "id": f"im-msg-{uuid.uuid4().hex[:8]}",
        "conversation_id": conv["id"],
        "sender_id": CURRENT_USER_ID,
        "timestamp": now,
        "text": body,
        "read": False,
        "media_id": None,
    }
    messages = _get_messages()
    messages.append(new_msg)
    db.save_collection(SITE, "messages", messages)
    for c in conversations:
        if c["id"] == conv["id"]:
            c["last_message"] = now
            c["message_count"] = c.get("message_count", 0) + 1
            break
    db.save_collection(SITE, "conversations", conversations)
    return jsonify({"ok": True, "label": "Messages",
                    "view_url": url_for("instant-messaging.conversation_page", conv_id=conv["id"])})


@blueprint.route("/api/conversations", methods=["POST"])
def api_create_conversation():
    data = request.get_json(silent=True) or {}
    participant_ids = data.get("participants", [])
    conv_type = data.get("type", "direct")
    group_name = data.get("name")

    if not participant_ids:
        return jsonify({"error": "Participants list is required"}), 400

    # Ensure current user is a participant
    if CURRENT_USER_ID not in participant_ids:
        participant_ids.insert(0, CURRENT_USER_ID)

    users_map = _user_map()
    participant_names = [
        users_map[pid]["display_name"] for pid in participant_ids if pid in users_map
    ]

    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    new_conv = {
        "id": f"conv-{uuid.uuid4().hex[:6]}",
        "type": conv_type,
        "participants": participant_ids,
        "participant_names": participant_names,
        "created": now,
        "last_message": now,
        "message_count": 0,
        "pinned_count": 0,
        "muted": False,
    }
    if conv_type == "group":
        new_conv["name"] = group_name or "New Group"
        new_conv["group_photo"] = None
        new_conv["admin"] = CURRENT_USER_ID

    conversations = _get_conversations()
    conversations.append(new_conv)
    db.save_collection(SITE, "conversations", conversations)

    return jsonify(new_conv), 201


@blueprint.route("/api/messages/search")
def api_search_messages():
    q = request.args.get("q", "").strip().lower()
    conv_id = request.args.get("conversation_id", "").strip()
    date_from = request.args.get("from", "").strip()
    date_to = request.args.get("to", "").strip()

    if not q:
        return jsonify({"error": "Search query 'q' is required"}), 400

    messages = _get_messages()
    users_map = _user_map()

    results = []
    for msg in messages:
        if q not in msg["text"].lower():
            continue
        if conv_id and msg["conversation_id"] != conv_id:
            continue
        if date_from and msg["timestamp"] < date_from:
            continue
        if date_to and msg["timestamp"] > date_to:
            continue
        sender = users_map.get(msg["sender_id"], {})
        results.append({
            "id": msg["id"],
            "conversation_id": msg["conversation_id"],
            "sender_id": msg["sender_id"],
            "sender_name": sender.get("display_name", "Unknown"),
            "timestamp": msg["timestamp"],
            "text": msg["text"],
            "read": msg["read"],
        })

    results.sort(key=lambda m: m["timestamp"], reverse=True)
    return jsonify({"query": q, "count": len(results), "results": results})


@blueprint.route("/api/contacts")
def api_contacts():
    users = _get_users()
    q = request.args.get("q", "").strip().lower()

    contacts = []
    for u in users:
        if u["id"] == CURRENT_USER_ID:
            continue
        if q and q not in u["display_name"].lower() and q not in u.get("about", "").lower():
            continue
        contacts.append(u)

    contacts.sort(key=lambda c: c["display_name"])
    return jsonify(contacts)


@blueprint.route("/api/media")
def api_media():
    conv_id_param = request.args.get("conversation_id", "").strip()
    media_type = request.args.get("type", "").strip()
    users_map = _user_map()
    where_f = {}
    if conv_id_param:
        where_f["conversation_id"] = conv_id_param
    if media_type:
        where_f["type"] = media_type
    media = _get_media(where=where_f if where_f else None)

    results = []
    for m in media:
        sender = users_map.get(m["sender_id"], {})
        results.append({
            **m,
            "sender_name": sender.get("display_name", "Unknown"),
            "file_size_display": _format_file_size(m.get("file_size_bytes", 0)),
        })

    results.sort(key=lambda m: m["timestamp"], reverse=True)
    return jsonify(results)


@blueprint.route("/api/stats")
def api_stats():
    conversations = _get_conversations()
    messages = _get_messages()
    media = _get_media()
    users = _get_users()

    total_messages = len(messages)
    total_media = len(media)
    total_conversations = len(conversations)
    direct_convs = sum(1 for c in conversations if c["type"] == "direct")
    group_convs = sum(1 for c in conversations if c["type"] == "group")

    # Messages per conversation
    msgs_per_conv = {}
    for msg in messages:
        cid = msg["conversation_id"]
        msgs_per_conv[cid] = msgs_per_conv.get(cid, 0) + 1

    # Messages per user
    msgs_per_user = {}
    for msg in messages:
        sid = msg["sender_id"]
        msgs_per_user[sid] = msgs_per_user.get(sid, 0) + 1

    users_map = _user_map()
    top_senders = sorted(
        [{"user_id": uid, "name": users_map.get(uid, {}).get("display_name", "Unknown"), "count": cnt}
         for uid, cnt in msgs_per_user.items()],
        key=lambda x: x["count"], reverse=True
    )

    # Total media size
    total_media_size = sum(m.get("file_size_bytes", 0) for m in media)

    return jsonify({
        "total_conversations": total_conversations,
        "direct_conversations": direct_convs,
        "group_conversations": group_convs,
        "total_messages_in_data": total_messages,
        "total_media_files": total_media,
        "total_media_size": _format_file_size(total_media_size),
        "total_contacts": len(users) - 1,  # exclude current user
        "messages_per_conversation": msgs_per_conv,
        "top_senders": top_senders,
    })


# ---------------------------------------------------------------------------
# API: authenticate_by_form — POST login via JSON API
# ---------------------------------------------------------------------------

@blueprint.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id", "").strip()
    users = _get_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        return jsonify({"error": "Invalid user_id"}), 401
    session["im_user_id"] = user_id
    return jsonify({
        "user_id": user["id"],
        "display_name": user["display_name"],
        "status": user["status"],
    })


# ---------------------------------------------------------------------------
# API: filter_by_toggle — filter conversations by unread/starred/muted
# ---------------------------------------------------------------------------

@blueprint.route("/api/conversations/filter", methods=["GET"])
def api_conversations_filter():
    """Filter conversations. ?filter=unread|starred|muted"""
    conversations = _get_conversations()
    messages = _get_messages()
    users_map = _user_map()
    f = request.args.get("filter", "").strip().lower()

    # Build unread map: a conversation is unread if any message is unread
    unread_convs = set()
    for msg in messages:
        if not msg["read"] and msg["sender_id"] != CURRENT_USER_ID:
            unread_convs.add(msg["conversation_id"])

    results = []
    for conv in conversations:
        if f == "unread" and conv["id"] not in unread_convs:
            continue
        if f == "starred" and conv.get("pinned_count", 0) == 0:
            continue
        if f == "muted" and not conv.get("muted", False):
            continue

        name = _conversation_display_name(conv, users_map)
        results.append({
            "id": conv["id"],
            "type": conv["type"],
            "display_name": name,
            "pinned_count": conv["pinned_count"],
            "muted": conv["muted"],
            "message_count": conv["message_count"],
            "last_message": conv["last_message"],
        })

    results.sort(key=lambda c: c.get("last_message", ""), reverse=True)
    return jsonify({"filter": f, "count": len(results), "conversations": results})


# ---------------------------------------------------------------------------
# API: follow_by_toggle — pin/unpin (star) a conversation
# ---------------------------------------------------------------------------

@blueprint.route("/api/conversations/<conv_id>/pin", methods=["POST"])
def api_pin_conversation(conv_id):
    """Toggle pin (star/follow) on a conversation."""
    conversations = _get_conversations()
    conv = next((c for c in conversations if c["id"] == conv_id), None)
    if not conv:
        abort(404)

    was_pinned = conv.get("pinned_count", 0) > 0
    if was_pinned:
        conv["pinned_count"] = 0
        action = "unpinned"
    else:
        conv["pinned_count"] = 1
        action = "pinned"

    db.save_collection(SITE, "conversations", conversations)
    return jsonify({"conversation_id": conv_id, "action": action, "pinned_count": conv["pinned_count"]})


# ---------------------------------------------------------------------------
# API: save_by_toggle — star/unstar an individual message
# ---------------------------------------------------------------------------

@blueprint.route("/api/messages/<msg_id>/star", methods=["POST"])
def api_star_message(msg_id):
    """Toggle star (save/bookmark) on a message."""
    messages = _get_messages()
    msg = next((m for m in messages if m["id"] == msg_id), None)
    if not msg:
        abort(404)

    was_starred = msg.get("starred", False)
    msg["starred"] = not was_starred
    action = "unstarred" if was_starred else "starred"

    db.save_collection(SITE, "messages", messages)
    return jsonify({"message_id": msg_id, "action": action, "starred": msg["starred"]})


# ---------------------------------------------------------------------------
# API: block_by_toggle — block/unblock a user
# ---------------------------------------------------------------------------

@blueprint.route("/api/contacts/<user_id>/block", methods=["POST"])
def api_block_user(user_id):
    """Toggle block on a user."""
    users = _get_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)

    was_blocked = user.get("blocked", False)
    user["blocked"] = not was_blocked
    action = "unblocked" if was_blocked else "blocked"

    db.save_collection(SITE, "users", users)
    return jsonify({"user_id": user_id, "action": action, "blocked": user["blocked"]})


# ---------------------------------------------------------------------------
# API: invite_by_form — invite a user to a group conversation
# ---------------------------------------------------------------------------

@blueprint.route("/api/conversations/<conv_id>/invite", methods=["POST"])
def api_invite_to_group(conv_id):
    """Invite a user to a group conversation."""
    data = request.get_json(silent=True) or {}
    invitee_id = data.get("user_id", "").strip()

    if not invitee_id:
        return jsonify({"error": "user_id is required"}), 400

    conversations = _get_conversations()
    conv = next((c for c in conversations if c["id"] == conv_id), None)
    if not conv:
        abort(404)
    if conv["type"] != "group":
        return jsonify({"error": "Can only invite to group conversations"}), 400
    if invitee_id in conv["participants"]:
        return jsonify({"error": "User is already a participant"}), 400

    users_map = _user_map()
    invitee = users_map.get(invitee_id)
    if not invitee:
        return jsonify({"error": "User not found"}), 404

    conv["participants"].append(invitee_id)
    conv["participant_names"].append(invitee["display_name"])

    db.save_collection(SITE, "conversations", conversations)
    return jsonify({
        "conversation_id": conv_id,
        "invited_user_id": invitee_id,
        "invited_user_name": invitee["display_name"],
        "action": "invited",
        "participants": conv["participants"],
        "participant_names": conv["participant_names"],
    }), 201


# ---------------------------------------------------------------------------
# API: report_by_form — report a message
# ---------------------------------------------------------------------------

@blueprint.route("/api/messages/<msg_id>/report", methods=["POST"])
def api_report_message(msg_id):
    """Report a message with a reason."""
    data = request.get_json(silent=True) or {}
    reason = data.get("reason", "").strip()

    if not reason:
        return jsonify({"error": "reason is required"}), 400

    messages = _get_messages()
    msg = next((m for m in messages if m["id"] == msg_id), None)
    if not msg:
        abort(404)

    msg["reported"] = True
    msg["report_reason"] = reason
    db.save_collection(SITE, "messages", messages)

    return jsonify({
        "message_id": msg_id,
        "action": "reported",
        "reason": reason,
    })


# ---------------------------------------------------------------------------
# API: join_by_route — join a group conversation via invite link
# ---------------------------------------------------------------------------

@blueprint.route("/api/conversations/<conv_id>/join", methods=["POST"])
def api_join_group(conv_id):
    """Join a group conversation (simulates clicking an invite link)."""
    conversations = _get_conversations()
    conv = next((c for c in conversations if c["id"] == conv_id), None)
    if not conv:
        abort(404)
    if conv["type"] != "group":
        return jsonify({"error": "Can only join group conversations"}), 400

    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id", CURRENT_USER_ID).strip()

    if user_id in conv["participants"]:
        return jsonify({"error": "Already a participant", "conversation_id": conv_id}), 400

    users_map = _user_map()
    user = users_map.get(user_id)
    display_name = user["display_name"] if user else user_id

    conv["participants"].append(user_id)
    conv["participant_names"].append(display_name)

    db.save_collection(SITE, "conversations", conversations)
    return jsonify({
        "conversation_id": conv_id,
        "user_id": user_id,
        "action": "joined",
        "group_name": conv.get("name"),
        "participants": conv["participants"],
    }), 201


@blueprint.route("/join/<conv_id>")
def join_group_link(conv_id):
    """Join a group conversation via invite link (join_by_route)."""
    conversations = _get_conversations()
    conv = next((c for c in conversations if c["id"] == conv_id), None)
    if not conv:
        abort(404)
    uid = session.get("im_user_id", CURRENT_USER_ID)
    if conv["type"] == "group" and uid not in conv["participants"]:
        user = _user_map().get(uid)
        conv["participants"].append(uid)
        conv["participant_names"].append(user["display_name"] if user else uid)
        db.save_collection(SITE, "conversations", conversations)
    return redirect(url_for("instant-messaging.conversation_page", conv_id=conv_id))


# ---------------------------------------------------------------------------
# API: share_by_dropdown — share/forward a message to another conversation
# ---------------------------------------------------------------------------

@blueprint.route("/api/messages/<msg_id>/share", methods=["POST"])
def api_share_message(msg_id):
    """Share/forward a message to another conversation (selected via dropdown)."""
    data = request.get_json(silent=True) or {}
    target_conv_id = data.get("conversation_id", "").strip()

    if not target_conv_id:
        return jsonify({"error": "conversation_id is required"}), 400

    messages = _get_messages()
    original = next((m for m in messages if m["id"] == msg_id), None)
    if not original:
        abort(404)

    conversations = _get_conversations()
    target = next((c for c in conversations if c["id"] == target_conv_id), None)
    if not target:
        return jsonify({"error": "Target conversation not found"}), 404

    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    shared_msg = {
        "id": f"im-msg-{uuid.uuid4().hex[:8]}",
        "conversation_id": target_conv_id,
        "sender_id": CURRENT_USER_ID,
        "timestamp": now,
        "text": f"[Forwarded] {original['text']}",
        "read": False,
        "media_id": original.get("media_id"),
        "forwarded_from": msg_id,
    }

    messages.append(shared_msg)
    db.save_collection(SITE, "messages", messages)

    # Update target conversation timestamp
    for c in conversations:
        if c["id"] == target_conv_id:
            c["last_message"] = now
            c["message_count"] = c.get("message_count", 0) + 1
            break
    db.save_collection(SITE, "conversations", conversations)

    return jsonify({
        "action": "shared",
        "original_message_id": msg_id,
        "new_message": shared_msg,
    }), 201


# ---------------------------------------------------------------------------
# API: edit_by_form — edit a message's text
# ---------------------------------------------------------------------------

@blueprint.route("/api/messages/<msg_id>/edit", methods=["PUT"])
def api_edit_message(msg_id):
    """Edit a message's text."""
    data = request.get_json(silent=True) or {}
    new_text = data.get("text", "").strip()

    if not new_text:
        return jsonify({"error": "text is required"}), 400

    messages = _get_messages()
    msg = next((m for m in messages if m["id"] == msg_id), None)
    if not msg:
        abort(404)

    if msg["sender_id"] != CURRENT_USER_ID:
        return jsonify({"error": "Can only edit your own messages"}), 403

    old_text = msg["text"]
    msg["text"] = new_text
    msg["edited"] = True

    db.save_collection(SITE, "messages", messages)
    return jsonify({
        "message_id": msg_id,
        "action": "edited",
        "old_text": old_text,
        "new_text": new_text,
    })


# ---------------------------------------------------------------------------
# API: delete_from_table — delete a message
# ---------------------------------------------------------------------------

@blueprint.route("/api/messages/<msg_id>", methods=["DELETE"])
def api_delete_message(msg_id):
    """Delete a message."""
    messages = _get_messages()
    msg = next((m for m in messages if m["id"] == msg_id), None)
    if not msg:
        abort(404)

    if msg["sender_id"] != CURRENT_USER_ID:
        return jsonify({"error": "Can only delete your own messages"}), 403

    conv_id = msg["conversation_id"]
    messages = [m for m in messages if m["id"] != msg_id]
    db.save_collection(SITE, "messages", messages)

    # Update conversation message count
    conversations = _get_conversations()
    for c in conversations:
        if c["id"] == conv_id:
            c["message_count"] = max(0, c.get("message_count", 1) - 1)
            break
    db.save_collection(SITE, "conversations", conversations)

    return jsonify({"message_id": msg_id, "action": "deleted"})


@blueprint.route("/conversation/<conv_id>/message/<msg_id>/delete", methods=["POST"])
def form_delete_message(conversation_id=None, conv_id=None, message_id=None, msg_id=None):
    """Delete a message via form POST and redirect back to conversation."""
    cid = conv_id or conversation_id
    mid = msg_id or message_id
    messages = _get_messages()
    messages = [m for m in messages if m["id"] != mid]
    db.save_collection(SITE, "messages", messages)
    return redirect(url_for("instant-messaging.conversation_page", conv_id=cid))


# ---------------------------------------------------------------------------
# API: upload_by_upload — upload a media attachment to a conversation
# ---------------------------------------------------------------------------

@blueprint.route("/api/conversations/<conv_id>/upload", methods=["POST"])
def api_upload_media(conv_id):
    """Upload a media file (simulated). Accepts multipart form or JSON."""
    conversations = _get_conversations()
    conv = next((c for c in conversations if c["id"] == conv_id), None)
    if not conv:
        abort(404)

    # Accept either multipart form-data or JSON.
    raw_bytes = None
    provided_data_uri = None
    if request.content_type and "json" in request.content_type:
        data = request.get_json(silent=True) or {}
        file_name = data.get("file_name", "upload.bin")
        caption = data.get("caption", "")
        media_type = data.get("type", "")
        file_size = data.get("file_size_bytes", 0)
        text = data.get("text", caption or f"Sent {file_name}")
        # A JSON client may hand us the bytes directly as a data-URI / base64.
        provided_data_uri = data.get("data_uri")
        mime_type = data.get("mime_type", "")
    else:
        # Multipart form
        f = request.files.get("file")
        if not f:
            return jsonify({"error": "No file provided"}), 400
        file_name = f.filename or "upload.bin"
        caption = request.form.get("caption", "")
        media_type = request.form.get("type", "")
        raw_bytes = f.read()
        f.seek(0)
        file_size = len(raw_bytes)
        mime_type = f.mimetype or ""
        text = request.form.get("text", caption or f"Sent {file_name}")

    # Resolve a real MIME type and classify the media kind from it.
    if not mime_type:
        mime_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
    if not media_type:
        if mime_type.startswith("image/"):
            media_type = "image"
        elif mime_type.startswith("video/"):
            media_type = "video"
        elif mime_type.startswith("audio/"):
            media_type = "audio"
        else:
            media_type = "file"

    # Persist the actual bytes as a data-URI so the attachment renders back
    # inline instead of being measured and discarded. Cap the inlined size.
    data_uri = provided_data_uri
    if data_uri is None and raw_bytes is not None and 0 < len(raw_bytes) <= MAX_INLINE_MEDIA_BYTES:
        b64 = base64.b64encode(raw_bytes).decode("ascii")
        data_uri = f"data:{mime_type};base64,{b64}"

    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    new_media_id = f"media-{uuid.uuid4().hex[:6]}"

    new_media = {
        "id": new_media_id,
        "conversation_id": conv_id,
        "sender_id": CURRENT_USER_ID,
        "timestamp": now,
        "type": media_type,
        "mime_type": mime_type,
        "file_name": file_name,
        "file_path": f"/media/{CURRENT_USER_ID}/{file_name}",
        "file_size_bytes": file_size,
        "caption": caption,
        "thumbnail_path": None,
    }
    if data_uri:
        new_media["data_uri"] = data_uri

    # Upsert a single overlay row (never rewrite the whole media collection).
    db.save_item(SITE, "media", new_media_id, new_media)

    # Create associated message (single-row upsert, not a full-table replace).
    new_msg = {
        "id": f"im-msg-{uuid.uuid4().hex[:8]}",
        "conversation_id": conv_id,
        "sender_id": CURRENT_USER_ID,
        "timestamp": now,
        "text": text,
        "read": False,
        "media_id": new_media_id,
    }
    db.save_item(SITE, "messages", new_msg["id"], new_msg)

    # Update conversation (single-row upsert).
    conv["last_message"] = now
    conv["message_count"] = conv.get("message_count", 0) + 1
    db.save_item(SITE, "conversations", conv_id, conv)

    return jsonify({
        "action": "uploaded",
        "media": {k: v for k, v in new_media.items() if k != "data_uri"},
        "media_has_bytes": bool(data_uri),
        "message": new_msg,
    }), 201


# ---------------------------------------------------------------------------
# API: search_by_dropdown — search messages within a specific conversation
# ---------------------------------------------------------------------------

@blueprint.route("/api/conversations/<conv_id>/search", methods=["GET"])
def api_search_in_conversation(conv_id):
    """Search messages within a specific conversation (selected via dropdown)."""
    q = request.args.get("q", "").strip().lower()
    if not q:
        return jsonify({"error": "Search query 'q' is required"}), 400

    conversations = _get_conversations()
    conv = next((c for c in conversations if c["id"] == conv_id), None)
    if not conv:
        abort(404)

    conv_messages = db.query(SITE, "messages", where={"conversation_id": conv_id})
    users_map = _user_map()

    results = []
    for msg in conv_messages:
        if q not in msg["text"].lower():
            continue
        sender = users_map.get(msg["sender_id"], {})
        results.append({
            "id": msg["id"],
            "sender_id": msg["sender_id"],
            "sender_name": sender.get("display_name", "Unknown"),
            "timestamp": msg["timestamp"],
            "text": msg["text"],
            "read": msg["read"],
        })

    results.sort(key=lambda m: m["timestamp"], reverse=True)
    name = _conversation_display_name(conv, users_map)
    return jsonify({
        "conversation_id": conv_id,
        "conversation_name": name,
        "query": q,
        "count": len(results),
        "results": results,
    })


# ---------------------------------------------------------------------------
# API: navigate_by_semantic — fuzzy search across contacts/conversations
# ---------------------------------------------------------------------------

@blueprint.route("/api/search/semantic", methods=["GET"])
def api_semantic_search():
    """Fuzzy/semantic search across contacts and conversations by keyword."""
    q = request.args.get("q", "").strip().lower()
    if not q:
        return jsonify({"error": "Query 'q' is required"}), 400

    users = _get_users()
    conversations = _get_conversations()
    users_map = _user_map()

    matching_contacts = []
    for u in users:
        if u["id"] == CURRENT_USER_ID:
            continue
        searchable = f"{u['display_name']} {u.get('about', '')} {u.get('phone', '')}".lower()
        if q in searchable:
            matching_contacts.append({
                "type": "contact",
                "id": u["id"],
                "display_name": u["display_name"],
                "about": u.get("about", ""),
                "status": u["status"],
            })

    matching_convs = []
    for conv in conversations:
        name = _conversation_display_name(conv, users_map)
        searchable = f"{name} {' '.join(conv.get('participant_names', []))}".lower()
        if q in searchable:
            matching_convs.append({
                "type": "conversation",
                "id": conv["id"],
                "display_name": name,
                "conv_type": conv["type"],
                "message_count": conv["message_count"],
            })

    return jsonify({
        "query": q,
        "contacts": matching_contacts,
        "conversations": matching_convs,
        "total": len(matching_contacts) + len(matching_convs),
    })


@blueprint.route("/api/export")
def api_export():
    """Export conversations or messages as JSON or CSV."""
    fmt = request.args.get("format", "json").lower()
    data_type = request.args.get("type", "conversations").lower()

    if data_type == "messages":
        data = _get_messages()
    else:
        data = _get_conversations()

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

