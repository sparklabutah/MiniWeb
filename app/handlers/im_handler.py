"""Instant messaging handler — creates messages for cross-site communication."""

import uuid
from datetime import datetime

from app import db
from app.events import on


def _im_user(root_user_id):
    """Resolve a root user id (1, 3, ...) to the site's im user (im-u001, ...)."""
    users = db.query("instant-messaging", "users")
    return next((u for u in users if u.get("root_user_id") == root_user_id), None)


@on("message")
def handle_message(from_user_id, to_user_id, text, source_site="", **kwargs):
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S") + "Z"

    # Conversations/messages key participants by im-uXXX ids, NOT root user ids —
    # matching on the raw ints never found a conversation, so bridge messages
    # landed in a conversation row that was never created (invisible on the site).
    sender = _im_user(from_user_id)
    recipient = _im_user(to_user_id)
    sender_id = sender["id"] if sender else f"im-ext-{from_user_id}"
    recipient_id = recipient["id"] if recipient else f"im-ext-{to_user_id}"
    want = {sender_id, recipient_id}

    convs = db.query("instant-messaging", "conversations", limit=200)
    conv = None
    for c in convs:
        pids = {p.get("user_id") if isinstance(p, dict) else p
                for p in (c.get("participants") or [])}
        if pids == want:
            conv = c
            break

    if conv is None:
        self_chat = sender_id == recipient_id
        conv = {
            "id": f"conv-bridge-{uuid.uuid4().hex[:6]}",
            # a self-notification stream renders by its `name`; direct chats
            # render by the other participant's display_name
            "type": "group" if self_chat else "direct",
            "participants": sorted(want),
            "participant_names": [u["display_name"] for u in (sender, recipient)
                                  if u][:1 if self_chat else 2] or ["Notifications"],
            "created": now,
            "last_message": now,
            "message_count": 0,
            "pinned_count": 0,
            "muted": 0,
            "name": "Notifications" if self_chat else "",
            "group_photo": "",
            "admin": "",
            "note": f"via {source_site}" if source_site else "",
        }

    # bump recency so the conversation floats to the top of every list that
    # sorts by last_message / the latest message timestamp
    conv["last_message"] = now
    conv["message_count"] = (conv.get("message_count") or 0) + 1
    db.save_item("instant-messaging", "conversations", conv["id"], conv)

    prefix = f"[via {source_site}] " if source_site else ""
    msg_id = f"im-bridge-{uuid.uuid4().hex[:8]}"
    db.save_item("instant-messaging", "messages", msg_id, {
        "id": msg_id,
        "conversation_id": conv["id"],
        "sender_id": sender_id,
        "timestamp": now,
        "text": prefix + text,
        "read": 0,
        "media_id": "",
    })
