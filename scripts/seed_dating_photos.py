"""Seed each dating profile with a gallery: original portrait + 3 generated photos.

Idempotent — drops any previously-appended /photo/ URLs and re-appends, so it can
be re-run safely (e.g. after a DB rebuild). Writes to the base dating_users table.
Run: ~/.conda/envs/miniweb/bin/python scratchpad/seed_dating_photos.py
"""
import json
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402

EXTRA = 3

app = create_app()
with app.test_request_context():
    from app import db
    conn = db._get_conn()
    table = db.get_table_name("dating", "users")
    rows = conn.execute(f"SELECT id, photos FROM [{table}]").fetchall()
    updated = 0
    for uid, raw in rows:
        try:
            photos = json.loads(raw) if raw else []
        except (ValueError, TypeError):
            photos = []
        # Keep only the original static portrait(s); drop prior generated URLs.
        portrait = [p for p in photos if isinstance(p, str) and "/static/profiles/" in p]
        gallery = portrait[:1] if portrait else []
        for idx in range(1, EXTRA + 1):
            gallery.append(f"/sites/dating/photo/{uid}/{idx}.svg")
        conn.execute(f"UPDATE [{table}] SET photos = ? WHERE id = ?",
                     (json.dumps(gallery), uid))
        updated += 1
    conn.commit()
    print(f"updated {updated} profiles → {1 + EXTRA} photos each")
    # sanity sample
    for uid in (1, 3):
        r = conn.execute(f"SELECT name, photos FROM [{table}] WHERE id=?", (uid,)).fetchone()
        print(" ", uid, r[0], json.loads(r[1]))
