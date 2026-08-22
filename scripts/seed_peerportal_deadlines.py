"""Add a concrete review_deadline to every PeerPortal venue.

Venues always carried submission_deadline and notification_date (never shown in
the UI until now); this adds the reviewer-facing deadline so pending review
tasks have a date an agent can act on (e.g. "add my review deadline to
CalendarTodo"). Deterministic: review_deadline = notification_date - 21 days
for historical venues. The one under-review venue (miniweb-workshop-2026) gets
a coherent post-event proceedings timeline — its seeded notification (July 15)
was already in the past while reviews were still pending, the same conflict
class just fixed in the UI.

Idempotent; re-run after a DB rebuild, then push to railway.
Run: ~/.conda/envs/miniweb/bin/python scripts/seed_peerportal_deadlines.py
"""
import sys
import pathlib
from datetime import datetime, timedelta

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from app import create_app  # noqa: E402

# Post-workshop proceedings round for the one venue still under review.
WORKSHOP_OVERRIDES = {
    "miniweb-workshop-2026": {
        "review_deadline": "September 5, 2026",
        "notification_date": "September 26, 2026",
    }
}

FMT = "%B %d, %Y"


def main():
    app = create_app()
    with app.test_request_context():
        from app import db
        conn = db._get_conn()
        t = db.get_table_name("conference-review-submission", "venues")
        cols = {c["name"] for c in conn.execute(f"PRAGMA table_info({t})")}
        if "review_deadline" not in cols:
            conn.execute(f"ALTER TABLE [{t}] ADD COLUMN review_deadline TEXT")
        for v in conn.execute(f"SELECT id, notification_date FROM [{t}]").fetchall():
            vid = v["id"]
            if vid in WORKSHOP_OVERRIDES:
                o = WORKSHOP_OVERRIDES[vid]
                conn.execute(f"UPDATE [{t}] SET review_deadline=?, notification_date=? WHERE id=?",
                             (o["review_deadline"], o["notification_date"], vid))
                continue
            try:
                notif = datetime.strptime((v["notification_date"] or "").strip(), FMT)
            except ValueError:
                continue
            rd = (notif - timedelta(days=21)).strftime(FMT).replace(" 0", " ")
            conn.execute(f"UPDATE [{t}] SET review_deadline=? WHERE id=?", (rd, vid))
        conn.commit()
        for v in conn.execute(f"SELECT id, review_deadline, notification_date FROM [{t}] LIMIT 6"):
            print(v["id"], "| review due:", v["review_deadline"], "| notify:", v["notification_date"])


if __name__ == "__main__":
    main()
