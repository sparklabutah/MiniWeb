"""Assign the under-review workshop's papers to PeerPortal reviewers.

All seeded review assignments pointed at iclr-2017 (decisions posted in 2017),
so once the console stopped listing dead-deadline assignments as pending, the
reviewers had no actionable tasks. This assigns every miniweb-workshop-2026
(status under_review) paper to the two reviewer users, giving them pending
review tasks whose deadline is coherent with the venue.

Deterministic + idempotent (set-union into assigned_papers, base table).
Re-run after a DB rebuild, then push to railway.

Run: ~/.conda/envs/miniweb/bin/python scripts/seed_peerportal_assignments.py
"""
import json
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from app import create_app  # noqa: E402

REVIEWER_IDS = [1, 2]     # author_arivera, reviewer_psharma (both role=reviewer)


def main():
    app = create_app()
    with app.test_request_context():
        from app import db
        conn = db._get_conn()
        papers = [r["id"] for r in conn.execute(
            "SELECT id FROM conference_review_submission_papers "
            "WHERE venue_id='miniweb-workshop-2026' ORDER BY id")]
        if not papers:
            print("no workshop papers found — nothing to assign")
            return
        users_t = db.get_table_name("conference-review-submission", "users")
        for uid in REVIEWER_IDS:
            row = conn.execute(f"SELECT assigned_papers FROM [{users_t}] WHERE id=?",
                               (uid,)).fetchone()
            if row is None:
                continue
            cur = row["assigned_papers"]
            cur = json.loads(cur) if isinstance(cur, str) and cur else (cur or [])
            merged = list(cur) + [p for p in papers if p not in [str(c) for c in cur] and p not in cur]
            conn.execute(f"UPDATE [{users_t}] SET assigned_papers=? WHERE id=?",
                         (json.dumps(merged), uid))
            print(f"user {uid}: assigned {merged}")
        conn.commit()


if __name__ == "__main__":
    main()
