"""Instant messaging handler — creates messages for cross-site communication."""

import uuid
from datetime import datetime

from app import db
from app.events import on


@on("message")
def handle_message(from_user_id, to_user_id, text, source_site="", **kwargs):
    convs = db.query("instant-messaging", "conversations", limit=200)
    conv_id = None
    for c in convs:
        participants = c.get("participants", [])
        pids = [p.get("user_id") if isinstance(p, dict) else p for p in participants]
        if from_user_id in pids and to_user_id in pids:
            conv_id = c["id"]
            break

    if not conv_id:
        conv_id = f"conv-bridge-{uuid.uuid4().hex[:6]}"

    prefix = f"[via {source_site}] " if source_site else ""
    msg_id = f"im-bridge-{uuid.uuid4().hex[:8]}"
    msg = {
        "id": msg_id,
        "conversation_id": conv_id,
        "sender_id": str(from_user_id),
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S") + "Z",
        "text": prefix + text,
        "read": 0,
        "media_id": "",
    }
    db.save_item("instant-messaging", "messages", msg_id, msg)
