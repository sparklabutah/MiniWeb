"""Expand dating (HeartLink / Spark) synthetic data to ~5000+ total rows.

Second-stage expansion (the first, scripts/expand_dating.py, took the site from
8 to 68 users). This one adds, INSERT-ONLY:

- ~232 new profiles (ids 69+) across the same 7 towns around Lakeport, WA,
  with generated bios/interests drawn from the site's existing vocabulary and
  SVG avatars written to sites/dating/static/profiles/ in the existing style.
- ~400 new matches strictly AMONG the new users (never ids 1-68), each backed
  by a mutual pair of "matched" likes, plus pending/passed likes for depth.
- ~3300 conversation messages inside the new matches.

Task-safety constraints honored (see data/annotations/Minh/dating_*):
- No rows reference user ids 1-68: the main user's (alex_r, id 1) discover
  deck, matches, conversations and Likes-You queue are byte-identical.
- New female profiles never fall in alex's preference window (age 25-34), so
  the discover deck stays fixed even against future like/pass state.
- No generated name/username/bio contains "mia", "daniel" or "okonkwo"
  (case-insensitive), keeping profile search for Mia / Daniel Okonkwo unique.
- New users join no later than 2025-06-30 (existing newest: 2026-05-12), so
  "newest" sorts are unchanged at the top.

Deterministic (random.Random(20260720)). Inserted ids are recorded in
data/backups/dating-expansion-2026-07-20/inserted_ids.json for rollback.

Usage: python scripts/expand_dating_data.py [--dry-run]
"""
import datetime
import json
import pathlib
import random
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "trimmed_miniweb.db"
AVATAR_DIR = ROOT / "sites" / "dating" / "static" / "profiles"
BACKUP_DIR = ROOT / "data" / "backups" / "dating-expansion-2026-07-20"

rng = random.Random(20260720)

FORBIDDEN = ("mia", "daniel", "okonkwo")  # never in a name/username/bio

N_USERS = 232
N_MATCHES = 400
N_EXTRA_LIKES = 320

# ── vocabulary ───────────────────────────────────────────────────────────────

CITIES = {
    "Lakeport, WA":       (47.98, -122.20),
    "Cedar Falls, WA":    (48.10, -122.35),
    "Harbor Springs, WA": (47.85, -122.40),
    "Eastbrook, WA":      (47.95, -121.95),
    "Millhaven, WA":      (48.25, -122.10),
    "Pinecrest, WA":      (47.70, -122.05),
    "Silverton, WA":      (48.45, -122.55),
}
CITY_WEIGHTS = [34, 12, 12, 12, 10, 10, 10]

FEMALE_FIRST = [
    "Sofia", "Isabel", "Lucia", "Valentina", "Renata", "Marisol", "Bianca",
    "Chiara", "Giulia", "Leyla", "Yasmin", "Farah", "Layla", "Nadia", "Lena",
    "Maren", "Imogen", "Fiona", "Gwen", "Holly", "Erin", "Dana", "Carly",
    "Brooke", "Abby", "Sadie", "Piper", "Quinn", "Ruby", "Stella", "Talia",
    "Uma", "Vivian", "Willa", "Ximena", "Yuki", "Zara", "Anya", "Beatriz",
    "Celine", "Daphne", "Esme", "Freya", "Greer", "Hana", "Ingrid", "Josie",
    "Kira", "Leona", "Margot", "Noelle", "Odette", "Paige", "Rosa", "Simone",
    "Tilda", "Astrid", "Bettina", "Coral", "Delphine", "Elsa", "Flora",
    "Gilda", "Helena", "Iona", "Jolene", "Katya", "Linnea", "Maeve", "Nell",
]
MALE_FIRST = [
    "Mateo", "Lucas", "Julian", "Adrian", "Sebastian", "Emil", "Anders",
    "Bjorn", "Caleb", "Dane", "Elias", "Frank", "Gabriel", "Henry", "Ivan",
    "Joel", "Kai", "Lars", "Milo", "Nico", "Otis", "Pablo", "Quentin",
    "Rafael", "Silas", "Tobias", "Ulysses", "Vince", "Wade", "Xavier",
    "Yusuf", "Zane", "Abram", "Boris", "Cedric", "Dominic", "Ezekiel",
    "Franco", "Gideon", "Harvey", "Ira", "Jasper", "Knox", "Leon", "Magnus",
    "Nolan", "Omar", "Preston", "Reuben", "Stefan", "Tristan", "Uriel",
    "Vaughn", "Wilson", "Yannick", "Zachary", "Alvaro", "Benito", "Clyde",
    "Dexter", "Errol", "Fergus", "Grady", "Hugo", "Ignacio", "Jonas",
]
NB_FIRST = ["Ash", "Blair", "Cameron", "Devon", "Ellis", "Frankie", "Gray",
            "Hollis", "Indigo", "Jules", "Kit", "Lane", "Marlow", "Noe"]
LAST = [
    "Whitaker", "Mercer", "Ashford", "Bellamy", "Crane", "Dalton", "Ellison",
    "Fontaine", "Garrity", "Hale", "Ibarra", "Jennings", "Keller", "Lachance",
    "Monroe", "Nakamura", "Ortega", "Petrov", "Rowe", "Sandoval", "Tran",
    "Ueda", "Vargas", "Winslow", "Yates", "Zamora", "Beckett", "Calloway",
    "Duran", "Farrell", "Goldberg", "Hoffman", "Iverson", "Jacobs",
    "Kowalski", "Larsen", "McAllister", "Nguyen", "Oduya", "Pearce",
    "Quimby", "Ramsey", "Sorensen", "Thatcher", "Underhill", "Vance",
    "Wexler", "Youngblood", "Ziegler", "Abernathy", "Bishop", "Corrigan",
    "Delgado", "Eastman", "Finch", "Gallagher", "Holloway", "Irving",
    "Jimenez", "Kessler", "Lindqvist", "Moreno", "Nash", "Osei", "Pruitt",
    "Reinhart", "Salazar", "Tanaka", "Ulrich", "Villanueva", "Weaver",
]
JOBS = [
    "Elementary school teacher", "ICU nurse", "Carpenter", "Graphic designer",
    "Sous chef", "Accountant at a Cascadia Credit Union branch",
    "Wildlife biologist", "Ferry deckhand", "Barber", "Massage therapist",
    "Electrician", "Brewer at a Lakeport taproom", "Baker", "Paramedic",
    "Land surveyor", "Bookkeeper", "Kayak guide", "Dog trainer",
    "Wedding photographer", "Tattoo artist", "HVAC tech", "Marina manager",
    "Arborist", "Physical therapy aide", "Claims adjuster at Meridian",
    "Radio producer", "Florist", "Machinist", "Park naturalist",
    "School counselor", "Line cook", "Bike mechanic", "Potter",
    "Sailing instructor", "Farmhand", "Optometrist", "Vet assistant",
    "Roofer", "Substitute librarian", "Barista", "Bus driver",
    "Fish hatchery tech", "Sign painter", "Yoga instructor",
]
BIO_CLOSERS = [
    "Looking for someone who laughs easily.",
    "Coffee first, adventures second.",
    "Bonus points if you have a dog.",
    "I promise I'm more fun than my job title suggests.",
    "Small-town pace, big plans.",
    "Ask me about my best worst first date.",
    "Happy to be the navigator if you drive.",
    "Sunday mornings are sacred and slow.",
    "New to the app, patient with it so far.",
    "Tell me something true and I'll match it.",
    "My friends say I'm the planner of the group.",
    "Rain doesn't cancel plans around here.",
]
NOTES_POOL = [
    "", "", "", "", "", "", "", "",
    "Two dates so far. Going well.",
    "Met at the farmers market first, matched after.",
    "Long message streak, no in-person date yet.",
    "First date at the waterfront went long.",
    "They keep rescheduling but the chat is steady.",
]
LIKE_REASONS = [
    "{a} liked {b}. The {i} photos did it.",
    "{a} liked {b}. Fellow {i} person, easy call.",
    "{a} liked {b}. The bio made them laugh.",
    "{a} liked {b}. Shared love of {i}.",
    "{a} liked {b}. Same side of the sound, same hobbies.",
]
OPENERS = [
    "Hey {name}! Saw {i} on your profile — how did you even get into that?",
    "Okay your bio made me laugh. Tell me more about the {i} thing.",
    "{name}! Finally someone else around here who's into {i}.",
    "Hi {name} — your photos are great. Is that the waterfront in {town}?",
    "So, {i}. Convince me in one message.",
    "A fellow {town} person! Small world. How long have you been on here?",
    "Your profile reads like someone who actually likes where they live. Refreshing.",
    "Hey! Quick question: {i} — hobby or lifestyle?",
]
MIDS = [
    "Ha, that's fair. I'm mostly free after work on weekdays.",
    "That spot gets so busy on weekends. Worth it though.",
    "Honestly the rain is half the charm out here.",
    "I've lived in three towns around the sound and this one's the keeper.",
    "You're funnier than your photos suggested, which is saying something.",
    "My schedule is chaos this week but next week opens up.",
    "I tried that once and was spectacularly bad at it. Would try again.",
    "Okay that's a green flag. Continue.",
    "The ferry line on Fridays is my villain origin story.",
    "I can't tell if you're joking but I'm laughing either way.",
    "Fair warning, I will talk about this for hours if you let me.",
    "That's exactly the kind of answer I was hoping for.",
    "You had me at the second sentence of your bio, honestly.",
    "Same! Though I'm strictly a fair-weather version of that.",
    "I need to hear the full story behind that someday.",
    "My sister would say you sound suspiciously normal. She means it well.",
    "Long days this week, but reading these has been the good part.",
    "I keep meaning to try that place on Main. Any good?",
    "It's better at sunrise, trust me. Everything out here is.",
    "You get points for spelling it right. Most people don't.",
]
CLOSERS = [
    "Want to grab coffee at the roastery on Main this weekend?",
    "Let's do it. Saturday morning?",
    "Ok deal — the farmers market, first sunny Saturday.",
    "I'm in. Send me a time and I'll be there early.",
    "Walk along the waterfront Thursday? I'll bring the good thermos.",
    "You pick the trail, I'll bring snacks.",
    "Trivia night at The Anchor next week — you and me, team of two?",
]

# ── helpers ──────────────────────────────────────────────────────────────────

def clean(text):
    low = text.lower()
    return not any(f in low for f in FORBIDDEN)


def coords(city):
    lat, lng = CITIES[city]
    return (round(lat + rng.uniform(-0.03, 0.03), 4),
            round(lng + rng.uniform(-0.04, 0.04), 4))


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def rand_dt(a, b):
    """Random datetime between two datetimes, minute resolution."""
    span = int((b - a).total_seconds() // 60)
    return a + datetime.timedelta(minutes=rng.randint(0, span))


def main():
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(DB, timeout=60)
    db.row_factory = sqlite3.Row

    # ── existing state ───────────────────────────────────────────────────────
    existing_usernames = {r["username"] for r in
                          db.execute("SELECT username FROM dating_users")}
    existing_names = {r["name"].lower() for r in
                      db.execute("SELECT name FROM dating_users")}
    interest_pool = sorted({i for (blob,) in
                            db.execute("SELECT interests FROM dating_users")
                            for i in json.loads(blob)})
    next_uid = db.execute("SELECT MAX(id)+1 FROM dating_users").fetchone()[0]
    next_match = db.execute("SELECT MAX(id)+1 FROM dating_matches").fetchone()[0]
    next_like = db.execute("SELECT MAX(id)+1 FROM dating_likes").fetchone()[0]
    next_msg = db.execute("SELECT MAX(id)+1 FROM dating_messages").fetchone()[0]
    used_pairs = {frozenset((r["from_user_id"], r["to_user_id"]))
                  for r in db.execute("SELECT from_user_id, to_user_id FROM dating_likes")}
    used_pairs |= {frozenset((r["user1_id"], r["user2_id"]))
                   for r in db.execute("SELECT user1_id, user2_id FROM dating_matches")}

    assert next_uid >= 69, "expected first-stage expansion (68 users) to exist"

    # ── users ────────────────────────────────────────────────────────────────
    # Females avoid ages 25-34 so alex_r's (id 1) discover deck cannot change.
    name_combos = []
    combo_seen = set(existing_names)
    pools = [("female", FEMALE_FIRST, 104), ("male", MALE_FIRST, 104),
             ("nonbinary", NB_FIRST, 24)]
    for gender, firsts, want in pools:
        made = 0
        while made < want:
            full = f"{rng.choice(firsts)} {rng.choice(LAST)}"
            if full.lower() in combo_seen or not clean(full):
                continue
            combo_seen.add(full.lower())
            name_combos.append((gender, full))
            made += 1
    rng.shuffle(name_combos)
    name_combos = name_combos[:N_USERS]

    user_rows = []          # tuples for INSERT
    users_by_id = {}        # id -> dict used for pairing
    join_lo = datetime.datetime(2024, 4, 15)
    join_hi = datetime.datetime(2025, 6, 30)
    for gender, full in name_combos:
        uid = next_uid
        next_uid += 1
        first, last = full.split(" ", 1)
        base = f"{first.lower()}_{last[0].lower()}"
        username = base
        n = 2
        while username in existing_usernames:
            username = f"{base}{n}"
            n += 1
        existing_usernames.add(username)

        if gender == "female":
            age = rng.choice(list(range(20, 25)) + list(range(35, 53)))
        else:
            age = rng.randint(21, 55)
        city = rng.choices(list(CITIES), weights=CITY_WEIGHTS, k=1)[0]
        lat, lng = coords(city)
        interests = rng.sample(interest_pool, rng.randint(3, 5))
        looking_for = rng.choices(["relationship", "casual"], [7, 3])[0]
        if gender == "nonbinary":
            gpref = "any"
        else:
            gpref = rng.choices(
                ["female" if gender == "male" else "male", "any"], [8, 2])[0]
        prefs = {"min_age": max(18, age - 10), "max_age": min(60, age + 12),
                 "gender_pref": gpref,
                 "max_distance_miles": rng.choice([20, 25, 30, 40, 50, 60])}
        town = city.split(",")[0]
        bio = "{job} in {town}. Weekends are for {i1} and {i2}. {closer}".format(
            job=rng.choice(JOBS), town=town, i1=interests[0], i2=interests[1],
            closer=rng.choice(BIO_CLOSERS))
        assert clean(bio) and clean(username)
        joined = rand_dt(join_lo, join_hi)
        last_active = rand_dt(datetime.datetime(2026, 5, 1),
                              datetime.datetime(2026, 7, 15))
        pw = f"{interests[0].split()[0].lower().replace('-', '')[:8]}{joined.year}!"
        photo = f"/sites/dating/static/profiles/{username}.svg"
        user_rows.append((
            uid, 0, username, pw, full, age, gender, bio, city,
            json.dumps(interests), looking_for, json.dumps(prefs),
            json.dumps([photo]), 1 if rng.random() < 0.85 else 0,
            iso(last_active), iso(joined), lat, lng))
        users_by_id[uid] = {"id": uid, "name": full, "username": username,
                            "gender": gender, "age": age, "town": town,
                            "interests": interests, "prefs": prefs,
                            "joined": joined}

    new_ids = list(users_by_id)

    # ── matches among NEW users only (never ids 1-68) ────────────────────────
    def compat(a, b):
        pa = a["prefs"]
        if pa["gender_pref"] != "any" and b["gender"] != pa["gender_pref"]:
            return False
        return pa["min_age"] <= b["age"] <= pa["max_age"]

    match_rows, like_rows, msg_rows = [], [], []
    match_lo = datetime.datetime(2025, 7, 15)
    match_hi = datetime.datetime(2026, 6, 30)
    msg_cap = datetime.datetime(2026, 7, 16, 23, 0)
    attempts = 0
    while len(match_rows) < N_MATCHES and attempts < 400_000:
        attempts += 1
        a, b = rng.sample(new_ids, 2)
        key = frozenset((a, b))
        if key in used_pairs:
            continue
        ua, ub = users_by_id[a], users_by_id[b]
        if not (compat(ua, ub) and compat(ub, ua)):
            continue
        used_pairs.add(key)
        mid = next_match
        next_match += 1
        matched = rand_dt(max(match_lo, ua["joined"], ub["joined"]), match_hi)
        status = "active" if rng.random() < 0.85 else "unmatched"
        match_rows.append((mid, a, b, iso(matched), status,
                           rng.choice(NOTES_POOL) if status == "active" else ""))

        # mutual likes behind the match
        first_like = matched - datetime.timedelta(
            hours=rng.randint(3, 96), minutes=rng.randint(0, 59))
        comment = ""
        if rng.random() < 0.35:
            comment = rng.choice(LIKE_REASONS).format(
                a=ub["name"].split()[0], b=ua["name"].split()[0],
                i=rng.choice(ua["interests"]))
        like_rows.append((next_like, b, a, iso(first_like), "matched", comment))
        next_like += 1
        like_rows.append((next_like, a, b, iso(matched), "matched", ""))
        next_like += 1

        # conversation
        n_msgs = rng.randint(4, 14) if status == "active" else rng.randint(2, 6)
        sender, other = (a, b) if rng.random() < 0.5 else (b, a)
        t = matched + datetime.timedelta(minutes=rng.randint(10, 90))
        shared = [i for i in ua["interests"] if i in ub["interests"]]
        for k in range(n_msgs):
            if t > msg_cap:
                break
            if k == 0:
                to = users_by_id[b] if sender == a else users_by_id[a]
                content = rng.choice(OPENERS).format(
                    name=to["name"].split()[0],
                    i=(shared[0] if shared else rng.choice(to["interests"])),
                    town=to["town"])
            elif k == n_msgs - 1 and status == "active" and rng.random() < 0.6:
                content = rng.choice(CLOSERS)
            else:
                content = rng.choice(MIDS)
            msg_rows.append((next_msg, mid, sender, content, iso(t), 1))
            next_msg += 1
            sender, other = other, sender
            t += datetime.timedelta(minutes=rng.randint(8, 60 * 52))
    assert len(match_rows) == N_MATCHES, f"only paired {len(match_rows)}"

    # last message of ~12% of active new threads left unread
    unread_last = set()
    active_mids = [m[0] for m in match_rows if m[4] == "active"]
    for mid in rng.sample(active_mids, int(len(active_mids) * 0.12)):
        last = max((r for r in msg_rows if r[1] == mid), key=lambda r: r[4],
                   default=None)
        if last:
            unread_last.add(last[0])
    msg_rows = [(i, m, s, c, t, 0 if i in unread_last else r)
                for (i, m, s, c, t, r) in msg_rows]

    # ── extra pending / passed likes among new users ─────────────────────────
    pending_per_target = {}
    extra = 0
    attempts = 0
    while extra < N_EXTRA_LIKES and attempts < 200_000:
        attempts += 1
        a, b = rng.sample(new_ids, 2)
        key = frozenset((a, b))
        if key in used_pairs:
            continue
        used_pairs.add(key)
        ua, ub = users_by_id[a], users_by_id[b]
        status = rng.choices(["pending", "passed"], [7, 3])[0]
        if status == "pending":
            if pending_per_target.get(b, 0) >= 6:
                status = "passed"
            else:
                pending_per_target[b] = pending_per_target.get(b, 0) + 1
        when = rand_dt(max(match_lo, ua["joined"], ub["joined"]),
                       datetime.datetime(2026, 7, 10))
        comment = ""
        if status == "pending" and rng.random() < 0.4:
            comment = rng.choice(LIKE_REASONS).format(
                a=ua["name"].split()[0], b=ub["name"].split()[0],
                i=rng.choice(ub["interests"]))
        like_rows.append((next_like, a, b, iso(when), status, comment))
        next_like += 1
        extra += 1

    # ── report / write ───────────────────────────────────────────────────────
    print(f"users: +{len(user_rows)}  matches: +{len(match_rows)}  "
          f"likes: +{len(like_rows)}  messages: +{len(msg_rows)}  "
          f"grand new: {len(user_rows)+len(match_rows)+len(like_rows)+len(msg_rows)}")
    if dry:
        print("\n-- dry run, nothing written. samples:")
        print("user:", user_rows[0])
        print("match:", match_rows[0])
        print("like:", like_rows[0])
        print("msgs:", [m[3] for m in msg_rows[:4]])
        return

    db.executemany(
        "INSERT INTO dating_users (id, root_user_id, username, password, name,"
        " age, gender, bio, location, interests, looking_for, preferences,"
        " photos, verified, last_active, joined_date, lat, lng)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", user_rows)
    db.executemany(
        "INSERT INTO dating_matches (id, user1_id, user2_id, matched_date,"
        " status, notes) VALUES (?,?,?,?,?,?)", match_rows)
    db.executemany(
        "INSERT INTO dating_likes (id, from_user_id, to_user_id, date, status,"
        " comment) VALUES (?,?,?,?,?,?)", like_rows)
    db.executemany(
        "INSERT INTO dating_messages (id, match_id, sender_id, content,"
        " timestamp, read) VALUES (?,?,?,?,?,?)", msg_rows)

    # avatars (same template as the first-stage script; new files only)
    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    palettes = [("#e8475f", "#f4845f"), ("#667eea", "#f093fb"),
                ("#0ea5e9", "#22d3ee"), ("#16a34a", "#84cc16"),
                ("#f59e0b", "#ef4444"), ("#8b5cf6", "#ec4899"),
                ("#0f766e", "#2dd4bf"), ("#b45309", "#fbbf24")]
    written = 0
    for row in user_rows:
        username, name = row[2], row[4]
        path = AVATAR_DIR / f"{username}.svg"
        if path.exists():
            continue
        parts = name.split()
        initials = (parts[0][0] + parts[-1][0]).upper()
        c1, c2 = palettes[sum(ord(ch) for ch in username) % len(palettes)]
        path.write_text(f"""<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400" viewBox="0 0 400 400">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/></linearGradient></defs>
<rect width="400" height="400" fill="url(#g)"/>
<circle cx="200" cy="150" r="70" fill="rgba(255,255,255,0.25)"/>
<ellipse cx="200" cy="330" rx="120" ry="90" fill="rgba(255,255,255,0.25)"/>
<text x="200" y="222" font-family="-apple-system,Segoe UI,Roboto,sans-serif" font-size="96"
 font-weight="700" fill="#ffffff" text-anchor="middle">{initials}</text>
</svg>
""")
        written += 1

    # FTS rebuild (external-content tables, no sync triggers)
    db.execute("INSERT INTO fts_dating_messages(fts_dating_messages) VALUES('rebuild')")
    db.execute("INSERT INTO fts_dating_likes(fts_dating_likes) VALUES('rebuild')")
    db.commit()

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    (BACKUP_DIR / "inserted_ids.json").write_text(json.dumps({
        "dating_users": [r[0] for r in user_rows],
        "dating_matches": [r[0] for r in match_rows],
        "dating_likes": [r[0] for r in like_rows],
        "dating_messages": [r[0] for r in msg_rows],
        "avatar_files": [f"{r[2]}.svg" for r in user_rows],
    }, indent=1))

    print("avatars written:", written)
    for t in ("dating_users", "dating_likes", "dating_matches", "dating_messages"):
        print(t, "->", db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0], "rows")


if __name__ == "__main__":
    main()
