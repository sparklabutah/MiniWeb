"""Seed the forums DM system with a few running conversation threads.

Creates and registers the ``forums_messages`` base table (it did not exist
in the shipped DB) and inserts several realistic back-and-forth threads for
the auto-login user ``cascadia_coder``. Idempotent: clears prior seeded rows
before inserting. Run with the miniweb conda python.
"""
import sys
sys.path.insert(0, ".")

from app import create_app, db
from sites.forums.schema import TABLES

SITE = "forums"
ME = "cascadia_coder"

# Alternating threads. Each tuple: (partner, subject, [(who, body, iso_ts, read)])
# who = "me" (cascadia_coder -> partner) or "them" (partner -> me).
THREADS = [
    ("CameronKelsey", "Larch Valley sunrise trip", [
        ("them", "Hey! Saw your shot from Maple Pass — the light was unreal. Are you doing the "
                 "Larch Valley hike this fall? Trying to catch peak golden larches.", "2026-07-24T15:12:00Z", 1),
        ("me", "Thanks! Yeah I'm planning it for the last week of September. Larches usually peak "
               "right around then. Want to carpool? I can grab the permits.", "2026-07-24T16:40:00Z", 1),
        ("them", "That'd be perfect. I'll bring the coffee and the wide-angle. Sunrise start?", "2026-07-25T08:03:00Z", 1),
        ("me", "Sunrise it is — trailhead by 5:30 so we beat the crowd at Sentinel Pass. I'll send "
               "the gpx track tonight.", "2026-07-25T09:15:00Z", 1),
        ("them", "You're a legend. Weather's looking clear so far. Fingers crossed it holds.", "2026-07-30T19:22:00Z", 0),
    ]),
    ("SurprisedPotato", "Board game night Friday?", [
        ("me", "We still on for board game night Friday? Thinking Brass: Birmingham then something "
               "lighter to close out.", "2026-07-28T12:30:00Z", 1),
        ("them", "Absolutely. I'll bring Brass and Wingspan. Can you host? Your table fits 6.", "2026-07-28T13:11:00Z", 1),
        ("me", "Yep, my place at 7. I'll do a big pot of chili. Bring anyone from the r/boardgames "
               "meetup if they're around.", "2026-07-28T13:40:00Z", 1),
        ("them", "Nice. Mara and Devin are in — that's 5. Might rope in one more.", "2026-07-29T20:05:00Z", 0),
    ]),
    ("hankmeisterr", "Quick Python review?", [
        ("them", "Do you have 10 min to look at a PR? It's the caching decorator we talked about in "
                 "r/Python — I think the TTL logic is off.", "2026-07-29T10:02:00Z", 1),
        ("me", "Sure, send the diff. If it's the expiry check, remember monotonic time vs wall clock — "
               "that bit us last time.", "2026-07-29T10:18:00Z", 1),
        ("them", "That was exactly it. Swapped to time.monotonic() and the flaky test went green. "
                 "Thanks a ton.", "2026-07-31T14:47:00Z", 0),
    ]),
]


PARTNER_BIOS = {
    "CameronKelsey": "Landscape & astro photographer. PNW wanderer.",
    "SurprisedPotato": "Board games, probability puzzles, and chili recipes.",
    "hankmeisterr": "Backend dev. Python, caches, and flaky-test hunting.",
}


def _ensure_partner_users(conn):
    """Make sure each DM partner exists in forums_users so replies succeed."""
    row = conn.execute("SELECT MAX(id) AS m, MAX(root_user_id) AS r FROM forums_users").fetchone()
    next_id = (row["m"] or 0) + 1
    next_root = (row["r"] or 0) + 1
    added = 0
    for username, bio in PARTNER_BIOS.items():
        exists = conn.execute(
            "SELECT 1 FROM forums_users WHERE username=? LIMIT 1", (username,)
        ).fetchone()
        if exists:
            continue
        conn.execute(
            "INSERT INTO forums_users (root_user_id, karma, subscribed_subreddits, "
            "cake_day, username, id, admin, biography, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (next_root, 1200, "[]", "2019-03-15", username, next_id,
             "false", bio, "2019-03-15"),
        )
        next_id += 1
        next_root += 1
        added += 1
    return added


def main():
    app = create_app()
    with app.app_context():
        spec = TABLES["messages"]
        table = spec["table_name"]
        conn = db._get_conn()

        db.create_site_table(conn, table, spec["columns"], spec.get("indexes"))
        db.register_table(SITE, "messages", table, pk_column="id", conn=conn)

        added = _ensure_partner_users(conn)

        # Clear any prior seed rows involving ME (idempotent re-runs).
        conn.execute(
            f"DELETE FROM [{table}] WHERE from_username=? OR to_username=?", (ME, ME)
        )

        records = []
        n = 0
        for partner, subject, msgs in THREADS:
            for who, body, ts, read in msgs:
                n += 1
                frm, to = (ME, partner) if who == "me" else (partner, ME)
                records.append({
                    "id": f"seedmsg_{n:03d}",
                    "from_username": frm,
                    "to_username": to,
                    "subject": subject,
                    "body": body,
                    "created_utc": ts,
                    "read": read,
                })

        db.bulk_insert(conn, table, spec["columns"], records)
        conn.commit()

        total = db.execute(f"SELECT COUNT(*) AS c FROM [{table}]", fetch="one")["c"]
        inbox = db.execute(
            f"SELECT COUNT(*) AS c FROM [{table}] WHERE to_username=?", (ME,), fetch="one"
        )["c"]
        print(f"Added {added} partner users to forums_users.")
        print(f"Seeded {len(records)} messages across {len(THREADS)} threads.")
        print(f"Table {table}: {total} rows total, {inbox} in {ME}'s inbox.")


if __name__ == "__main__":
    main()
