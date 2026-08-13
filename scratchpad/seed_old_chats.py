"""Seed OLDER conversations/messages into two sites so a date filter is meaningful.

  * dating (HeartLink): adds active matches between the logged-in user (id=1,
    Alex Rivera) and other profiles, each with a small thread of OLD messages
    (2024-05 .. 2025-10). Existing user-1 messages start 2025-11, so this gives
    a real spread of past dates for the messages-tab date filter to narrow.
  * instant-messaging (QuickChat): adds OLD messages (2024-08 .. 2025-06) into
    existing direct conversations so the chat history isn't all "current".
    No date filter on this site — just older history.

Deterministic + idempotent: every insert uses a fixed id range / id prefix and
re-running first deletes the previously-seeded rows, so content never changes
per run and no existing rows/dates are mutated.

Post-build DB mutation (like the forums / podcasts seeds) — RE-RUN after any DB
rebuild:  ~/.conda/envs/miniweb/bin/python scratchpad/seed_old_chats.py
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from app import db

conn = db._get_conn()

# ---------------------------------------------------------------------------
# 1) DATING — old matches + message threads for the logged-in user (id=1)
# ---------------------------------------------------------------------------
# id ranges reserved for seeded rows (well above the live max: matches ~416,
# messages ~3511) so idempotent cleanup is a simple range delete.
D_MATCH_BASE = 5001
D_MSG_BASE = 50001

# (partner_user_id, year-month) — one active match per month, oldest first.
DATING_THREADS = [
    (12, "2024-05"),
    (18, "2024-07"),
    (25, "2024-09"),
    (33, "2024-11"),
    (47, "2025-01"),
    (56, "2025-03"),
    (64, "2025-05"),
    (72, "2025-07"),
    (88, "2025-09"),
    (101, "2025-10"),
]

# 4 messages per thread, alternating sender (me, them, me, them).
# Deterministic content pool, indexed by message position.
DATING_LINES = [
    "Hey! Really enjoyed reading your profile — we have a lot in common.",
    "Aw thank you! Likewise, your photos from the coast are gorgeous.",
    "Would love to grab coffee sometime this week if you're free?",
    "I'd like that! Weekends work best for me — let's find a time.",
]
# day-of-month + time for each of the 4 messages
DATING_SLOTS = [
    ("03", "14:05:00"),
    ("05", "09:30:00"),
    ("09", "18:20:00"),
    ("14", "20:10:00"),
]

# idempotent: clear previously-seeded rows
conn.execute("DELETE FROM dating_matches  WHERE id BETWEEN 5001 AND 5099")
conn.execute("DELETE FROM dating_messages WHERE id BETWEEN 50001 AND 59999")

d_matches = 0
d_msgs = 0
mid = D_MSG_BASE
for k, (partner, ym) in enumerate(DATING_THREADS):
    match_id = D_MATCH_BASE + k
    matched_date = f"{ym}-03T13:00:00"
    conn.execute(
        "INSERT INTO dating_matches (id, user1_id, user2_id, matched_date, status, notes) "
        "VALUES (?,?,?,?,?,?)",
        (match_id, 1, partner, matched_date, "active", ""),
    )
    d_matches += 1
    for i, line in enumerate(DATING_LINES):
        day, tm = DATING_SLOTS[i]
        sender = 1 if i % 2 == 0 else partner
        ts = f"{ym}-{day}T{tm}"
        conn.execute(
            "INSERT INTO dating_messages (id, match_id, sender_id, content, timestamp, read) "
            "VALUES (?,?,?,?,?,?)",
            (mid, match_id, sender, line, ts, 1),
        )
        mid += 1
        d_msgs += 1

# ---------------------------------------------------------------------------
# 2) INSTANT-MESSAGING — old messages into existing direct conversations
# ---------------------------------------------------------------------------
# TEXT primary key — use a prefix for idempotent cleanup. No date filter here,
# just older history so the timeline isn't all recent.
IM_ME = "im-u001"

# (conversation_id, other_participant_id, year-month)
IM_THREADS = [
    ("conv-001", "im-u002", "2024-08"),
    ("conv-002", "im-u003", "2024-10"),
    ("conv-003", "im-u004", "2024-12"),
    ("conv-004", "im-u005", "2025-02"),
    ("conv-005", "im-u006", "2025-04"),
    ("conv-007", "im-u008", "2025-06"),
]

IM_LINES = [
    "Hey, been a while! How have you been?",
    "Pretty good! Busy with work but can't complain. You?",
    "Same here. We should catch up properly soon.",
    "Definitely. Free most evenings next week if that works.",
    "Perfect, I'll message you Monday to lock something in.",
]
IM_SLOTS = [
    ("02", "10:15:00"),
    ("05", "13:40:00"),
    ("09", "19:05:00"),
    ("14", "08:50:00"),
    ("20", "21:30:00"),
]

conn.execute("DELETE FROM instant_messaging_messages WHERE id LIKE 'seedold-%'")

im_msgs = 0
n = 0
for conv_id, other, ym in IM_THREADS:
    for i, line in enumerate(IM_LINES):
        day, tm = IM_SLOTS[i]
        sender = IM_ME if i % 2 == 0 else other
        ts = f"{ym}-{day}T{tm}Z"
        msg_id = f"seedold-{n:04d}"
        conn.execute(
            "INSERT INTO instant_messaging_messages "
            "(id, conversation_id, sender_id, timestamp, text, read, media_id) "
            "VALUES (?,?,?,?,?,?,?)",
            (msg_id, conv_id, sender, ts, line, 1, ""),
        )
        n += 1
        im_msgs += 1

conn.commit()

# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------
print(f"[dating] seeded {d_matches} matches + {d_msgs} messages for user 1")
row = conn.execute(
    "SELECT MIN(timestamp), MAX(timestamp) FROM dating_messages WHERE id BETWEEN 50001 AND 59999"
).fetchone()
print(f"[dating] seeded message span: {row[0]} .. {row[1]}")
u1span = conn.execute(
    "SELECT MIN(m.timestamp), MAX(m.timestamp) FROM dating_messages m "
    "JOIN dating_matches ma ON ma.id=m.match_id "
    "WHERE ma.status='active' AND (ma.user1_id=1 OR ma.user2_id=1)"
).fetchone()
print(f"[dating] user-1 conversation message span (all): {u1span[0]} .. {u1span[1]}")

print(f"[instant-messaging] seeded {im_msgs} old messages across {len(IM_THREADS)} conversations")
row = conn.execute(
    "SELECT MIN(timestamp), MAX(timestamp) FROM instant_messaging_messages WHERE id LIKE 'seedold-%'"
).fetchone()
print(f"[instant-messaging] seeded message span: {row[0]} .. {row[1]}")
full = conn.execute(
    "SELECT MIN(timestamp), MAX(timestamp) FROM instant_messaging_messages"
).fetchone()
print(f"[instant-messaging] full message span now: {full[0]} .. {full[1]}")
