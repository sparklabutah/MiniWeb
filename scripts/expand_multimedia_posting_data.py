"""Expand multimedia-posting (PixShare) base data.

PixShare ships with 9 users / 600 posts / 1285 comments / 50 follows /
18 stories (1962 rows). Adds a deterministic (seeded) synthetic community:
40 new users (mp-u-010..mp-u-049), ~250 posts authored by those new users,
~2500 comments attached ONLY to the new posts (so stored comments_count
stays consistent), ~300 follow edges, and 25 expired stories.

Safety properties:
- Insert-only; inserted ids recorded under data/backups/ for rollback.
- No new follow rows with follower_id = 'mp-u-001', and no posts by the
  9 existing users, so the default user's feed (/) is unchanged.
- All new posts are dated OLDER than the current newest post
  (2026-06-24), so the top of /explore stays familiar.
- New stories are all is_active=0 / expired, so the story ring and
  /stories page are unchanged.
- image_url / media_url values are REUSED from existing rows (files that
  exist under data/static/generated); no invented filenames.
- Id schemes continue the existing numeric ("601"...) and prefixed
  ("fol-051", "story-019") conventions without colliding with the UI's
  _next_id() logic.

Usage: python scripts/expand_multimedia_posting_data.py [--dry-run]
"""
import datetime
import json
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "trimmed_miniweb.db"
rng = random.Random(20260720)

SITE_PREFIX = "multimedia_posting"
EXISTING_USER_IDS = [f"mp-u-{i:03d}" for i in range(1, 10)]
MAIN_USER = "mp-u-001"

N_USERS = 40
N_POSTS = 250
N_COMMENTS = 2500
N_FOLLOWS = 300
N_STORIES = 25

# Posts must stay older than the current newest post (2026-06-24)
POST_DATE_MIN = datetime.datetime(2025, 2, 15, 6, 0, 0)
POST_DATE_MAX = datetime.datetime(2026, 6, 20, 22, 0, 0)

FIRST_NAMES = [
    "Priya", "Carlos", "Emma", "Jordan", "Aisha", "Tyler", "Nina", "Derek",
    "Hannah", "Marco", "Lena", "Victor", "Grace", "Omar", "Chloe", "Felix",
    "Ruby", "Andre", "Isabel", "Kevin", "Tara", "Diego", "Molly", "Ethan",
    "Zoe", "Brandon", "Layla", "Trevor", "Camille", "Ivan", "Paige", "Russ",
    "Dana", "Miles", "Elise", "Tomas", "Kara", "Julian", "Wendy", "Sean",
]
LAST_NAMES = [
    "Patel", "Mendoza", "Whitfield", "Blake", "Hassan", "Nguyen", "Kowalski",
    "Sanders", "Kim", "Rossi", "Fischer", "Ramos", "Holloway", "Diallo",
    "Bennett", "Weber", "Castillo", "Thompson", "Moreau", "Park", "Singh",
    "Alvarez", "Quinn", "Larsen", "Chang", "Mitchell", "Farah", "Doyle",
    "Vega", "Petrov", "Sutton", "Grady", "Wolfe", "Turner", "Amari", "Novak",
    "Reyes", "Abbott", "Lindqvist", "Connolly",
]
BIO_BITS = [
    "PNW hiker", "Coffee shop explorer", "Weekend photographer", "Home cook",
    "Trail runner", "Craft beer fan", "Bookworm", "Plant parent",
    "Farmers market regular", "Amateur potter", "Vinyl collector",
    "Board game enthusiast", "Kayaker", "Sourdough baker", "Dog person",
    "Lakeport local", "Climbing gym regular", "Film photography nerd",
    "Brunch enthusiast", "Community volunteer", "Live music chaser",
    "Watercolor dabbler", "Cyclist", "Yoga most mornings",
]
BIO_JOBS = [
    "Software engineer", "Teacher", "Nurse", "Barista", "Graphic designer",
    "Product manager @ Meridian Systems", "Carpenter", "Photographer",
    "Data analyst", "Chef", "Librarian", "Real estate agent",
    "Physical therapist", "Marketing coordinator", "Small business owner",
    "Student at UW", "Firefighter", "Accountant",
]

CAPTIONS = [
    # existing bulk vocabulary
    "New personal record today", "Finally finished this project!",
    "Study buddy", "Fresh from the farmers market", "Rainy day reads",
    "First attempt at pottery", "New recipe attempt — verdict below",
    "Game night!", "Coffee first ☕", "Sunset from the pier",
    "Weekend vibes", "City lights", "Trail views from this morning",
    "Little garden update", "Throwback to last summer",
    # same voice, small additions
    "Golden hour never misses", "Saturday market haul",
    "Post-run reward", "Lakeport looking good today",
    "New corner of the apartment", "Slow morning, good light",
    "Finally tried this place", "Pups first trail day",
    "Leftovers never looked so good", "Made it to the top",
    "Quiet night in", "Sketchbook progress", "Best seat in the house",
]
LOCATIONS = [
    "", "", "", "Cedar Park", "Harbor Marina", "Downtown Lakeport",
    "Lakeport Waterfront", "North Shore Trail", "Lakeport Farmers Market",
    "Sunrise Cafe, Lakeport", "Drip Coffee, Lakeport", "Lakeport, WA",
    "Cascadia Lake, WA", "Cedar Falls Trail, WA", "Eagle Point Trail, WA",
    "Seattle Waterfront, WA", "Pioneer Square, Seattle", "Home", "Studio",
]
TAG_POOL = [
    "travel", "fitness", "music", "hiking", "foodie", "photography",
    "coffee", "PNW", "lakeport", "sunset", "weekendvibes", "homemade",
    "cooking", "outdoors", "morning", "friends", "gamenight", "brunch",
    "trailrunning", "citylife", "gardening", "books", "art", "dogsofpixshare",
]
COMMENT_TEXTS = [
    # existing bulk vocabulary
    "Saving this for later", "This made my day", "Teach me your ways",
    "We need to go here together", "Goals!", "Recipe please!",
    "🔥🔥🔥", "Love this!", "Amazing shot", "So good!",
    # same voice, small additions
    "Okay this is stunning", "Adding this to my list",
    "The light in this one!", "Congrats, well earned",
    "How have I never been here", "Take me next time",
    "This looks incredible", "Absolutely frame-worthy",
    "Need the details on this", "Best one yet",
    "Cannot get enough of this view", "Weekend inspiration right here",
    "You make it look easy", "That color palette though",
    "Instant save", "Happy for you!", "Wish I was there",
    "This is the content I follow for", "Chef vibes", "Legend",
]
STORY_CAPTIONS = [
    "Morning coffee situation", "Quick trail break", "Market run",
    "Studio day", "Game night warmup", "Sunset check", "New recipe test",
    "Gym done, brunch next", "Rainy commute", "Weekend mode on",
]


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def rand_dt(rng, lo, hi):
    span = int((hi - lo).total_seconds())
    return lo + datetime.timedelta(seconds=rng.randint(0, span))


def main():
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.row_factory = sqlite3.Row

    # --- pools from existing rows (reuse real asset paths) -----------------
    image_pool = [r[0] for r in db.execute(
        f"SELECT DISTINCT image_url FROM {SITE_PREFIX}_posts "
        "WHERE image_url LIKE '/static/generated/mp_%'")]
    story_media_pool = [r[0] for r in db.execute(
        f"SELECT DISTINCT media_url FROM {SITE_PREFIX}_stories "
        "WHERE media_url LIKE '/static/%'")]
    existing_usernames = {r[0] for r in db.execute(
        f"SELECT username FROM {SITE_PREFIX}_users")}
    existing_pairs = {(r[0], r[1]) for r in db.execute(
        f"SELECT follower_id, following_id FROM {SITE_PREFIX}_follows")}
    assert image_pool and story_media_pool

    # --- users: mp-u-010 .. mp-u-049 ---------------------------------------
    users_new = []
    for i in range(N_USERS):
        uid = f"mp-u-{10 + i:03d}"
        fn, ln = FIRST_NAMES[i], LAST_NAMES[i]
        style = rng.random()
        if style < 0.6:
            username = f"{fn.lower()}.{ln.lower()}"
        elif style < 0.8:
            username = f"{fn.lower()}.{ln.lower()}.{rng.choice(['pnw', 'photo', 'lkpt', 'makes'])}"
        else:
            username = f"{fn.lower()}{ln.lower()}{rng.randint(2, 99)}"
        if username in existing_usernames:
            username = f"{username}.{rng.randint(2, 9)}"
        existing_usernames.add(username)
        created = rand_dt(rng, datetime.datetime(2019, 1, 10),
                          datetime.datetime(2024, 6, 30))
        last_active = rand_dt(rng, datetime.datetime(2026, 5, 1),
                              datetime.datetime(2026, 6, 26))
        users_new.append({
            "id": uid,
            "root_user_id": 0,
            "username": username,
            "handle": f"@{username}",
            "display_name": f"{fn} {ln}",
            "bio": f"{rng.choice(BIO_JOBS)} | "
                   + " | ".join(rng.sample(BIO_BITS, 2)),
            "avatar_url": "",
            "followers_count": 0,   # filled from follow edges below
            "following_count": 0,
            "posts_count": 0,       # filled from posts below
            "is_verified": 1 if rng.random() < 0.05 else 0,
            "is_private": 1 if rng.random() < 0.1 else 0,
            "created_at": iso(created),
            "last_active": iso(last_active),
        })
    new_user_ids = [u["id"] for u in users_new]
    users_by_id = {u["id"]: u for u in users_new}

    # --- posts: numeric ids continuing the bulk scheme ---------------------
    max_numeric_post = db.execute(
        f"SELECT MAX(CAST(id AS INTEGER)) FROM {SITE_PREFIX}_posts "
        "WHERE id GLOB '[0-9]*'").fetchone()[0]
    next_post = max_numeric_post + 1  # 601
    posts_new = []
    for _ in range(N_POSTS):
        author = rng.choice(new_user_ids)
        created = rand_dt(rng, POST_DATE_MIN, POST_DATE_MAX)
        ptype = rng.choices(["image", "photo", "video"],
                            weights=[90, 8, 2])[0]
        post = {
            "id": str(next_post),
            "author_id": author,
            "type": ptype,
            "image_url": rng.choice(image_pool),
            "caption": rng.choice(CAPTIONS),
            "location": rng.choice(LOCATIONS),
            "likes_count": rng.choice([rng.randint(3, 80),
                                       rng.randint(30, 400),
                                       rng.randint(200, 900)]),
            "comments_count": 0,   # set to actual attached count below
            "created_at": iso(created),
            "tags": json.dumps(rng.sample(TAG_POOL, rng.randint(1, 3))),
            "additional_images": "",
            "video_url": (f"https://pixshare.io/videos/post-{next_post}.mp4"
                          if ptype == "video" else ""),
            "_created": created,
        }
        users_by_id[author]["posts_count"] += 1
        posts_new.append(post)
        next_post += 1

    # --- comments: attached ONLY to new posts (keeps counts consistent) ----
    max_numeric_cmt = db.execute(
        f"SELECT MAX(CAST(id AS INTEGER)) FROM {SITE_PREFIX}_comments "
        "WHERE id GLOB '[0-9]*'").fetchone()[0]
    next_cmt = max(max_numeric_cmt + 1, 1300)
    all_user_ids = EXISTING_USER_IDS + new_user_ids
    comments_new = []
    for i in range(N_COMMENTS):
        post = rng.choice(posts_new)
        author = rng.choice(all_user_ids)
        cdate = post["_created"] + datetime.timedelta(
            hours=rng.randint(1, 24 * 14), minutes=rng.randint(0, 59))
        cdate = min(cdate, datetime.datetime(2026, 6, 23, 23, 0, 0))
        comments_new.append({
            "id": str(next_cmt),
            "post_id": post["id"],
            "author_id": author,
            "text": rng.choice(COMMENT_TEXTS),
            "likes_count": rng.choices([0, 1, 2, 3, rng.randint(4, 25)],
                                       weights=[40, 25, 15, 10, 10])[0],
            "created_at": iso(cdate),
            "reply_to": "",
        })
        post["comments_count"] += 1
        next_cmt += 1

    # --- follows: fol-051.. ; never with follower mp-u-001 -----------------
    follows_new = []
    pairs = set(existing_pairs)
    next_fol = 51

    def add_follow(follower, following, created):
        nonlocal next_fol
        if follower == following or follower == MAIN_USER:
            return
        if (follower, following) in pairs:
            return
        pairs.add((follower, following))
        follows_new.append({
            "id": f"fol-{next_fol:03d}",
            "follower_id": follower,
            "following_id": following,
            "created_at": iso(created),
        })
        next_fol += 1

    # each new user follows a handful of existing accounts + peers
    for u in users_new:
        joined = datetime.datetime.strptime(u["created_at"],
                                            "%Y-%m-%dT%H:%M:%SZ")
        targets = (rng.sample(EXISTING_USER_IDS, rng.randint(2, 5))
                   + rng.sample(new_user_ids, rng.randint(2, 6)))
        for t in targets:
            add_follow(u["id"], t,
                       rand_dt(rng, joined, datetime.datetime(2026, 6, 20)))
    # some existing users (not mp-u-001) follow back
    for follower in EXISTING_USER_IDS[1:]:
        for t in rng.sample(new_user_ids, rng.randint(3, 8)):
            add_follow(follower, t,
                       rand_dt(rng, datetime.datetime(2024, 7, 1),
                               datetime.datetime(2026, 6, 20)))
    # top up with random new-user pairs to reach the target
    attempts = 0
    while len(follows_new) < N_FOLLOWS and attempts < 5000:
        attempts += 1
        add_follow(rng.choice(new_user_ids), rng.choice(all_user_ids),
                   rand_dt(rng, datetime.datetime(2024, 7, 1),
                           datetime.datetime(2026, 6, 20)))
    follows_new = follows_new[:N_FOLLOWS]

    # reflect edges in the stored counters for the NEW users only
    for f in follows_new:
        if f["follower_id"] in users_by_id:
            users_by_id[f["follower_id"]]["following_count"] += 1
        if f["following_id"] in users_by_id:
            users_by_id[f["following_id"]]["followers_count"] += 1

    # --- stories: story-019.. ; all expired/inactive -----------------------
    stories_new = []
    for i in range(N_STORIES):
        author = rng.choice(new_user_ids + EXISTING_USER_IDS[1:])
        created = rand_dt(rng, datetime.datetime(2026, 5, 1, 7, 0),
                          datetime.datetime(2026, 6, 20, 21, 0))
        stories_new.append({
            "id": f"story-{19 + i:03d}",
            "author_id": author,
            "type": rng.choices(["photo", "video"], weights=[85, 15])[0],
            "media_url": rng.choice(story_media_pool),
            "caption": rng.choice(STORY_CAPTIONS),
            "views_count": rng.randint(10, 220),
            "created_at": iso(created),
            "expires_at": iso(created + datetime.timedelta(hours=24)),
            "is_active": 0,
        })

    for p in posts_new:
        del p["_created"]

    print(f"users: +{len(users_new)}, posts: +{len(posts_new)}, "
          f"comments: +{len(comments_new)}, follows: +{len(follows_new)}, "
          f"stories: +{len(stories_new)}  "
          f"(total +{len(users_new) + len(posts_new) + len(comments_new) + len(follows_new) + len(stories_new)})")
    if dry:
        for u in users_new[:3]:
            print(" user", u["id"], u["username"], "|", u["bio"][:60])
        for p in posts_new[:5]:
            print(" post", p["id"], p["author_id"], p["created_at"],
                  p["comments_count"], "|", p["caption"][:40], p["image_url"])
        for c in comments_new[:3]:
            print(" cmt", c["id"], c["post_id"], c["author_id"], "|", c["text"])
        for f in follows_new[:3]:
            print(" fol", f["id"], f["follower_id"], "->", f["following_id"])
        for s in stories_new[:3]:
            print(" story", s["id"], s["author_id"], s["is_active"], s["media_url"])
        return

    bdir = ROOT / "data" / "backups" / "multimedia-posting-expansion-2026-07-20"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "inserted_ids.json").write_text(json.dumps({
        "users": [u["id"] for u in users_new],
        "posts": [p["id"] for p in posts_new],
        "comments": [c["id"] for c in comments_new],
        "follows": [f["id"] for f in follows_new],
        "stories": [s["id"] for s in stories_new]}, indent=1))

    for table, rows in (("users", users_new), ("posts", posts_new),
                        ("comments", comments_new), ("follows", follows_new),
                        ("stories", stories_new)):
        if not rows:
            continue
        cols = list(rows[0].keys())
        db.executemany(
            f"INSERT INTO {SITE_PREFIX}_{table} ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' * len(cols))})",
            [[r[c] for c in cols] for r in rows])

    # keep FTS indexes in sync (users has no fts table)
    for table in ("posts", "comments", "follows", "stories"):
        fts = f"fts_{SITE_PREFIX}_{table}"
        exists = db.execute(
            "SELECT name FROM sqlite_master WHERE name = ?", (fts,)).fetchone()
        if exists:
            db.execute(f"INSERT INTO {fts}({fts}) VALUES('rebuild')")

    db.commit()
    print(f"inserted; rollback ids at {bdir}/inserted_ids.json")


if __name__ == "__main__":
    main()
