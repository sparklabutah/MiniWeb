"""Seed themed posts + comments into the sparse forums subreddits so they aren't
near-empty. Idempotent: re-running replaces the seeded rows (ids prefixed sd_/sdc_).

Reads scratchpad/forums_seed/batch_{A,B,C}.json (produced by the generator agents).
Post-build DB mutation (like the other forums seed deps) — re-run + push to railway
after any DB rebuild.
"""
import sys, json, glob, pathlib
sys.path.insert(0, ".")
from app import db

conn = db._get_conn()

# 1) load all batches -> {subreddit: [post,...]}
data = {}
for f in sorted(glob.glob("scratchpad/forums_seed/batch_*.json")):
    d = json.load(open(f))
    for sub, posts in d.items():
        data.setdefault(sub, []).extend(posts)
print("subreddits to seed:", {s: len(p) for s, p in data.items()})

# 2) idempotent: clear previously-seeded rows
conn.execute("DELETE FROM forums_posts    WHERE id LIKE 'sd\\_%'  ESCAPE '\\'")
conn.execute("DELETE FROM forums_comments WHERE id LIKE 'sdc\\_%' ESCAPE '\\'")

npost = ncom = 0
for sub, posts in data.items():
    for i, p in enumerate(posts, 1):
        pid = f"sd_{sub}_{i:03d}"
        comments = p.get("comments") or []
        conn.execute(
            "INSERT INTO forums_posts (id, author_root_user_id, subreddit, title, body, "
            "score, num_comments, flair, author, created_utc, url, sticky, locked) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (pid, int(p.get("author_root_user_id", 0) or 0), sub, p.get("title", ""),
             p.get("body", ""), int(p.get("score", 0) or 0), len(comments),
             p.get("flair", ""), p.get("author", ""), p.get("created_utc", ""),
             p.get("url", ""), "false", "false"))
        npost += 1
        for j, c in enumerate(comments, 1):
            cid = f"sdc_{sub}_{i:03d}_{j:02d}"
            conn.execute(
                "INSERT INTO forums_comments (id, post_id, author_root_user_id, body, "
                "score, parent_comment_id, author, created_utc) VALUES (?,?,?,?,?,?,?,?)",
                (cid, pid, int(c.get("author_root_user_id", 0) or 0), c.get("body", ""),
                 int(c.get("score", 0) or 0), None, c.get("author", ""),
                 c.get("created_utc", "")))
            ncom += 1

# 3) refresh subreddits table post_count (and ensure each community exists)
maxid = conn.execute("SELECT COALESCE(MAX(id),10000) FROM forums_subreddits").fetchone()[0]
for k, sub in enumerate(sorted(data), 1):
    pc = conn.execute("SELECT COUNT(*) FROM forums_posts WHERE subreddit=?", (sub,)).fetchone()[0]
    row = conn.execute("SELECT 1 FROM forums_subreddits WHERE name=?", (sub,)).fetchone()
    if row:
        conn.execute("UPDATE forums_subreddits SET post_count=? WHERE name=?", (pc, sub))
    else:
        conn.execute("INSERT INTO forums_subreddits (id,name,title,description,sidebar,created_at,post_count) "
                     "VALUES (?,?,?,?,?,?,?)",
                     (maxid + k, sub, sub, f"Community for r/{sub}", "", "2022-10-01 00:00:00+00", pc))

conn.commit()
print(f"seeded {npost} posts + {ncom} comments across {len(data)} subreddits")
for sub in sorted(data):
    pc = conn.execute("SELECT COUNT(*) FROM forums_posts WHERE subreddit=?", (sub,)).fetchone()[0]
    print(f"  r/{sub}: {pc} posts")
