#!/usr/bin/env python
"""Fix the broken news comment feature: create the missing `news_comments`
table, register it in site_registry, and seed realistic comments.

The news site's comment code (form_post_comment / article_detail) queries the
`comments` collection, but no `news_comments` table was ever built — so
db.query short-circuits to [] and posted comments vanish. This creates and
registers the table (additive), then seeds a few comments per article and
aligns each article's comments_count.

Idempotent: re-running skips seeding if the table already has rows. Backs up
the (small) article comments_count values first.
"""
import json
import os
import pathlib
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
# Resolve the DB the running app actually uses (e.g. data/trimmed_miniweb.db),
# not the root stub.
def _resolve_db():
    from app import create_app
    import app.db as _appdb
    create_app()
    return _appdb._DB_PATH
DB = os.environ.get("MINIWEB_DB") or _resolve_db()
SEED = 20260802

BODIES = [
    "Great reporting — thanks for covering this.",
    "I live nearby and this is exactly what our neighborhood needed.",
    "Not sure I agree with the framing here, but interesting read.",
    "Finally! We've been asking about this for years.",
    "Does anyone know when this actually takes effect?",
    "The photos really bring the story to life.",
    "This is a big deal for local families.",
    "Solid piece. Would love a follow-up on the budget details.",
    "Mixed feelings about the cost, but the intent is good.",
    "Shared this with my whole street. Well done.",
    "Curious how this compares to what other towns are doing.",
    "As a small business owner downtown, this affects us a lot.",
    "The council really listened to residents this time.",
    "Hope they keep the community updated as it progresses.",
    "Wonderful to see Lakeport getting attention for this.",
]


def main():
    conn = sqlite3.connect(DB, timeout=60)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # backup comments_count (tiny, reversible)
    rows = cur.execute("SELECT id, comments_count FROM news_articles").fetchall()
    bdir = ROOT / "data" / "backups" / "news-comments-20260802"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "articles_comments_count.json").write_text(
        json.dumps({str(r["id"]): r["comments_count"] for r in rows}, indent=1))

    # 1. create the table (additive)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS news_comments (
            id INTEGER PRIMARY KEY,
            article_id INTEGER,
            user_id INTEGER,
            username TEXT,
            display_name TEXT,
            body TEXT,
            posted_at TEXT
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_news_comments_article ON news_comments(article_id)")

    # 2. register in site_registry so db.get_table_name('news','comments') resolves
    cur.execute(
        "INSERT OR REPLACE INTO site_registry (site, collection, table_name, pk_column) "
        "VALUES ('news', 'comments', 'news_comments', 'id')")

    existing = cur.execute("SELECT COUNT(*) FROM news_comments").fetchone()[0]
    if existing:
        conn.commit(); conn.close()
        print(f"news_comments already has {existing} rows — table/registry ensured, seeding skipped.")
        return

    # 3. seed deterministic comments + align comments_count
    import random
    rnd = random.Random(SEED)
    users = cur.execute("SELECT id, username, display_name FROM news_users ORDER BY id").fetchall()
    users = [dict(u) for u in users]
    arts = cur.execute("SELECT id FROM news_articles").fetchall()
    cid = 1
    total = 0
    for a in arts:
        aid = a["id"]
        r = random.Random(SEED + aid)
        n = r.choice([0, 0, 1, 2, 2, 3, 4, 5])
        day = 1
        for _ in range(n):
            u = r.choice(users)
            hh = r.randint(8, 22)
            cur.execute(
                "INSERT INTO news_comments (id, article_id, user_id, username, display_name, body, posted_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (cid, aid, u["id"], u["username"], u["display_name"], r.choice(BODIES),
                 f"2026-07-{10 + (day % 18):02d}T{hh:02d}:{r.randint(0,59):02d}:00Z"))
            cid += 1; day += 1; total += 1
        cur.execute("UPDATE news_articles SET comments_count = ? WHERE id = ?", (n, aid))

    conn.commit(); conn.close()
    print(f"Created + registered news_comments; seeded {total} comments across {len(arts)} articles.")


if __name__ == "__main__":
    main()
