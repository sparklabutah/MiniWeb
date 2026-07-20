"""Expand instant-messaging (QuickChat) base data.

The site ships with 8 users / 8 conversations (all involving Alex Rivera,
im-u001) / 2559 messages / 15 media. This adds a deterministic (seeded)
synthetic community around Alex's contacts: new users, direct and group
conversations strictly AMONG THE NEW USERS, plus their messages and media.

Task-safety design (annotated tasks must keep working):
- Nothing is added to any existing conversation (conv-001..conv-008), so the
  latest message of Alex<->Jake (conv-007), the Elena Vasquez "art gallery"
  message (im-msg-021 in conv-002), and Mia's conversation (conv-006) are
  untouched.
- New conversations involve ONLY new users, so no sidebar entry can display an
  existing contact's name (no second "Jake Morrison" / "Elena Vasquez" chat).
- Every new conversation's last message is dated BEFORE 2026-06-24T18:00Z (the
  oldest last-message of the existing conversations), so the existing 8
  conversations keep their exact positions at the top of the sidebar.
- All new messages are read=1 (no unread badges appear anywhere).
- New message text avoids task-sensitive vocabulary (gallery/exhibit/harbor/
  pickup/puppy/photo.jpg/lake dr and existing contact first names); enforced
  by an assertion.
- Message ids continue the numeric-string convention ('2464', ...), which is
  the only id form the FTS5 external-content index (content_rowid=id) can map.
- fts_instant_messaging_media is intentionally left empty: it has always been
  empty, and because media ids are non-numeric ('media-XXX') a rebuild would
  index nothing joinable while disabling db.search's LIKE fallback.

Insert-only; inserted ids recorded under
data/backups/instant-messaging-expansion-2026-07-20/inserted_ids.json.

Usage: ~/.conda/envs/miniweb/bin/python scripts/expand_instant_messaging_data.py [--dry-run]
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

# Newest allowed timestamp for anything we insert: strictly before the oldest
# existing conversation's last message (conv-008 @ 2026-06-24T18:00:00Z).
LAST_CEILING = datetime.datetime(2026, 6, 20, 23, 0, 0)

# Words that must never appear in new text (annotation-task vocabulary and
# existing contact names that agents search for).
FORBIDDEN = [
    "gallery", "exhibit", "harbor", "lake dr", "pickup", "pick up", "pick you up",
    "puppy", "photo.jpg", "alex", "rivera", "marcus", "elena", "vasquez",
    "sophie", "daniel", "okonkwo", "mia", "torres", "jake", "morrison",
]

FIRST_NAMES = [
    ("Priya", "Sharma", "f"), ("Tomás", "Herrera", "m"), ("Nina", "Kowalski", "f"),
    ("Owen", "Blackwood", "m"), ("Keiko", "Tanaka", "f"), ("Ravi", "Patel", "m"),
    ("Ingrid", "Larsen", "f"), ("Dmitri", "Volkov", "m"), ("Amara", "Diallo", "f"),
    ("Felix", "Nguyen", "m"), ("Rosa", "Delgado", "f"), ("Hugo", "Lindqvist", "m"),
    ("Zoe", "Papadakis", "f"), ("Ben", "Whitfield", "m"), ("Leila", "Haddad", "f"),
    ("Cole", "Brennan", "m"), ("Anya", "Petrova", "f"), ("Theo", "Marchetti", "m"),
    ("Wren", "Calloway", "f"), ("Idris", "Bakare", "m"), ("Maren", "Solberg", "f"),
    ("Kai", "Nakamura", "m"), ("Bianca", "Rossi", "f"), ("Elliot", "Fraser", "m"),
    ("Suki", "Yamamoto", "f"), ("Grant", "Holloway", "m"), ("Petra", "Novak", "f"),
    ("Andre", "Dubois", "m"), ("Freya", "Jensen", "f"), ("Silas", "Thornton", "m"),
    ("Camille", "Beaumont", "f"), ("Ezra", "Goldberg", "m"),
]

ABOUTS = [
    "Coffee first, everything else second", "Trail runner. Sourdough baker.",
    "Ask me about my houseplants", "Live music and late-night ramen",
    "Kayaks, campfires, good books", "Software by day, ceramics by night",
    "Proud cat parent x2", "Chasing powder days all winter",
    "Amateur birder, professional napper", "Board game night regular",
    "Vinyl collector. Rain lover.", "Always down for tacos",
    "Marathon #6 in training", "Weekend woodworker",
    "Plant-based and loving it", "Film photography nerd",
    "Rock climbing and cold brew", "Puget Sound sailor",
    "Learning the banjo, apologies to my neighbors", "Dog park ambassador",
    "Fremont market on Sundays", "Backpacking the Cascades one pass at a time",
    "", "", "",
]

# Topic line pools. Lines alternate naturally between two speakers; the
# generator interleaves them with seeded sender switching.
TOPICS = {
    "hiking": [
        "you free this weekend? thinking of doing the Snow Lake trail",
        "forecast says clear skies saturday, we should go early",
        "trailhead lot fills up by 8 so let's leave at 6:30",
        "i'll bring the stove, you bring the good snacks",
        "that ridge view last time was unreal, want to do it again",
        "my legs are still sore from tiger mountain lol",
        "permits for the enchantments open next week, want to enter the lottery?",
        "ok adding it to the calendar, don't flake on me",
        "we got rained out last time so fingers crossed",
        "bringing the film camera this time for the summit shot",
        "did you break in the new boots yet?",
        "counting me in, i need to get out of the city",
    ],
    "food": [
        "have you tried that new ramen place on 45th?",
        "the tonkotsu there is dangerously good",
        "we should do a dumpling crawl through the ID soon",
        "i made that miso salmon recipe you sent, huge hit",
        "taco tuesday at my place this week?",
        "i'll bring the horchata if you handle the salsa",
        "the farmers market had the best peaches yesterday",
        "trying a 48 hour sourdough this weekend, wish me luck",
        "brunch sunday? the place on ballard ave has no wait before 9",
        "ok that pasta spot lived up to the hype",
        "still thinking about that birria from the truck on rainier",
        "send me the recipe pls, my meal prep is getting sad",
    ],
    "work": [
        "the standup ran 40 minutes again, i need a vacation",
        "did you see the reorg email? wild timing",
        "my presentation went way better than expected",
        "remote wednesdays are saving my sanity honestly",
        "the new hire on my team is great, finally some help",
        "quarterly planning week, send coffee",
        "i finally closed that deal i've been chasing since march",
        "they approved my conference trip to portland!",
        "deadline moved up a week, so that's my weekend gone",
        "congrats on the promotion, drinks on you next time",
        "interviewing candidates all day, my face hurts from smiling",
        "shipped the big release today, team is thrilled",
    ],
    "sports": [
        "kraken game friday, i have an extra ticket",
        "that overtime finish last night was insane",
        "rec league starts up again in two weeks, you in?",
        "my bracket is already busted, every year man",
        "sounders match saturday, meet at the usual spot?",
        "i finally beat my 10k time from last year",
        "pilates is way harder than i expected, everything hurts",
        "the climbing gym has a new comp wall, we have to try it",
        "storm game was electric, we should go again",
        "golf sunday? i promise not to lose all the balls this time",
        "spin class at 6am tomorrow, hold me accountable",
        "league night got moved to thursdays fyi",
    ],
    "plans": [
        "are we still on for saturday?",
        "yep, 7 works for me",
        "might be 10 min late, parking there is rough",
        "no worries, i'll grab us a table",
        "can we push to next week? something came up",
        "sure thing, same time same place",
        "adding it to my calendar now so i don't forget",
        "bring the cards, rematch is happening",
        "i'll text you when i'm leaving",
        "sounds good, see you then!",
        "ok confirmed, don't be late this time",
        "movie night friday? i'll queue up the snacks",
    ],
    "pets": [
        "the cat knocked my monstera off the shelf again",
        "vet visit went fine, just needed a booster shot",
        "we took biscuit's cousin energy to the dog park, chaos",
        "she learned to open the treat drawer, we're doomed",
        "found the best sitter for when we're in leavenworth",
        "adopted! meet mochi, the world's loudest tabby",
        "the trainer says he's making progress, i have doubts lol",
        "your dog is welcome at the cabin btw, fully fenced yard",
        "new leash arrived and he immediately chewed it",
        "cat tax attached, you're welcome",
    ],
    "travel": [
        "flights to denver are cheap in september, road trip pieces?",
        "the cabin at lake chelan is booked for the 12th!",
        "i still owe you photos from the oregon coast trip",
        "leavenworth in october? the larches will be peak",
        "passport renewal took 3 weeks, finally done",
        "vancouver weekend soon? it's been too long",
        "the hot springs were worth every mile of that drive",
        "packing list started, i always overpack anyway",
        "san juans ferry reservation is made, we're set",
        "olympic peninsula loop, three days, who's in?",
    ],
    "neighborhood": [
        "the block party planning meeting is tuesday at 7",
        "someone left a couch on the corner again, classic",
        "the new bakery on the corner is legit, get the morning bun",
        "power was out for two hours last night, fun times",
        "community garden plots open up next month, want one?",
        "the library branch reopens friday after the remodel",
        "street cleaning tomorrow, move your car",
        "farmers market is back on sundays starting this week",
        "lost keys found on maple ln, posted in the lobby",
        "yard sale saturday, come take my junk please",
    ],
}

MEDIA_POOL = [
    # (file_name, type, mime, caption)
    ("snow_lake_summit.jpg", "image", "image/jpeg", "Snow Lake from the saddle. Worth every switchback"),
    ("ramen_45th_st.jpg", "image", "image/jpeg", "The tonkotsu that ruined all other ramen for me"),
    ("mochi_tabby_nap.jpg", "image", "image/jpeg", "Mochi claiming the laundry basket again"),
    ("sourdough_attempt_4.jpg", "image", "image/jpeg", "Attempt #4. The crumb is finally cooperating"),
    ("kraken_game_night.jpg", "image", "image/jpeg", "Section 109! What a finish"),
    ("chelan_cabin_view.jpg", "image", "image/jpeg", "Morning view from the cabin deck"),
    ("community_garden_plot.jpg", "image", "image/jpeg", "Our plot before the great tomato experiment"),
    ("larches_leavenworth.jpg", "image", "image/jpeg", "Golden larches at peak. No filter"),
    ("dumpling_crawl_haul.jpg", "image", "image/jpeg", "Round one of the dumpling crawl"),
    ("rec_league_team.jpg", "image", "image/jpeg", "Team photo before we lost by 20"),
    ("ferry_san_juans.jpg", "image", "image/jpeg", "Ferry deck views heading out to the San Juans"),
    ("morning_bun_bakery.jpg", "image", "image/jpeg", "The famous morning bun. Believe the hype"),
    ("birria_truck_tacos.jpg", "image", "image/jpeg", "Consommé dip in action"),
    ("oregon_coast_haystack.jpg", "image", "image/jpeg", "Haystack Rock at low tide"),
    ("monstera_crime_scene.jpg", "image", "image/jpeg", "The crime scene. She shows no remorse"),
    ("comp_wall_route.png", "image", "image/png", "New comp wall routes. The pink one is evil"),
    ("hot_springs_trail.jpg", "image", "image/jpeg", "Steam rising off the pools at dawn"),
    ("block_party_flyer.png", "image", "image/png", "Draft flyer for this year's block party"),
    ("peaches_market_haul.jpg", "image", "image/jpeg", "Peak peach season at the market"),
    ("sounders_match_south_end.jpg", "image", "image/jpeg", "South end was rocking today"),
]

N_USERS = 32
N_DIRECT = 48
N_GROUP = 6
GROUP_NAMES = [
    "Trail Crew", "Sunday Brunch Club", "Rec League Squad", "Chelan Cabin Trip",
    "Greenwood Book Circle", "Fantasy League Chat",
]


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def check_forbidden(text):
    low = text.lower()
    for w in FORBIDDEN:
        assert w not in low, f"forbidden word {w!r} in {text!r}"


def main():
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.row_factory = sqlite3.Row

    existing_user_ids = {r["id"] for r in db.execute("SELECT id FROM instant_messaging_users")}
    next_msg_id = db.execute(
        "SELECT MAX(CAST(id AS INTEGER)) FROM instant_messaging_messages WHERE id NOT LIKE 'im-msg-%'"
    ).fetchone()[0] + 1
    max_media = db.execute(
        "SELECT MAX(CAST(SUBSTR(id, 7) AS INTEGER)) FROM instant_messaging_media"
    ).fetchone()[0]
    max_conv = db.execute(
        "SELECT MAX(CAST(SUBSTR(id, 6) AS INTEGER)) FROM instant_messaging_conversations"
    ).fetchone()[0]
    max_unum = max(int(u[4:]) for u in existing_user_ids)  # im-uNNN

    # ---- users -----------------------------------------------------------
    users_new = []
    used_phones = set()
    for i in range(N_USERS):
        first, last, _g = FIRST_NAMES[i]
        uid = f"im-u{max_unum + 1 + i:03d}"
        while True:
            phone = f"(555) {rng.randint(200, 799)}-{rng.randint(1000, 9999)}"
            if phone not in used_phones:
                used_phones.add(phone)
                break
        plain_first = (first.replace("á", "a").replace("é", "e").replace("í", "i")
                       .replace("ó", "o").lower())
        email = f"{plain_first}.{last.lower()}@gmail.com"
        status = rng.choices(["online", "offline"], weights=[55, 45])[0]
        last_seen = datetime.datetime(2026, 6, rng.randint(18, 25),
                                      rng.randint(6, 22), rng.choice([0, 15, 30, 45]))
        users_new.append({
            "id": uid, "root_user_id": 0,
            "display_name": f"{first} {last}",
            "phone": phone, "email": email, "status": status,
            "last_seen": iso(last_seen),
            "profile_photo": f"/profiles/{plain_first}_{last.lower()}.jpg",
            "about": rng.choice(ABOUTS),
        })

    new_ids = [u["id"] for u in users_new]
    name_of = {u["id"]: u["display_name"] for u in users_new}

    # ---- conversations ---------------------------------------------------
    convs_new = []
    pairs = set()
    for i in range(N_DIRECT):
        while True:
            a, b = rng.sample(new_ids, 2)
            key = tuple(sorted((a, b)))
            if key not in pairs:
                pairs.add(key)
                break
        created = datetime.datetime(rng.randint(2019, 2025), rng.randint(1, 12),
                                    rng.randint(1, 28))
        convs_new.append({
            "id": f"conv-{max_conv + 1 + i:03d}", "type": "direct",
            "participants": json.dumps([a, b]),
            "participant_names": json.dumps([name_of[a], name_of[b]]),
            "created": iso(created), "last_message": "",  # filled after messages
            "message_count": 0, "pinned_count": 0,
            "muted": 1 if rng.random() < 0.08 else 0,
            "name": "", "group_photo": "", "admin": "", "note": "",
        })
    for j in range(N_GROUP):
        members = rng.sample(new_ids, rng.randint(3, 5))
        created = datetime.datetime(rng.randint(2021, 2025), rng.randint(1, 12),
                                    rng.randint(1, 28))
        convs_new.append({
            "id": f"conv-{max_conv + 1 + N_DIRECT + j:03d}", "type": "group",
            "participants": json.dumps(members),
            "participant_names": json.dumps([name_of[m] for m in members]),
            "created": iso(created), "last_message": "",
            "message_count": 0, "pinned_count": 0, "muted": 0,
            "name": GROUP_NAMES[j], "group_photo": "",
            "admin": members[0], "note": "",
        })

    # ---- messages + media ------------------------------------------------
    messages_new, media_new = [], []
    media_pool = list(MEDIA_POOL)
    rng.shuffle(media_pool)
    media_iter = iter(media_pool * 2)  # 40 media total
    n_media_total = 40
    media_used = 0

    for conv in convs_new:
        members = json.loads(conv["participants"])
        n_msgs = rng.randint(34, 58)
        # conversation activity window: recent months up to a per-conv end
        end = LAST_CEILING - datetime.timedelta(days=rng.randint(0, 50),
                                                hours=rng.randint(0, 12))
        start = end - datetime.timedelta(days=rng.randint(60, 160))
        # timestamps ascending
        ts_list = sorted(
            start + datetime.timedelta(
                seconds=rng.randint(0, int((end - start).total_seconds())))
            for _ in range(n_msgs)
        )
        topics = rng.sample(list(TOPICS), rng.randint(2, 4))
        lines = []
        for t in topics:
            lines.extend(TOPICS[t])
        sender = rng.choice(members)
        conv_media_slots = set()
        if media_used < n_media_total:
            want = 1 if rng.random() < 0.65 else 0
            if conv["type"] == "group" and rng.random() < 0.5:
                want += 1
            want = min(want, n_media_total - media_used)
            conv_media_slots = set(rng.sample(range(n_msgs), want)) if want else set()
            media_used += want

        for k, ts in enumerate(ts_list):
            if rng.random() < 0.62:  # switch speaker
                others = [m for m in members if m != sender]
                sender = rng.choice(others)
            if k in conv_media_slots:
                fname, mtype, mime, caption = next(media_iter)
                media_id = f"media-{max_media + 1 + len(media_new):03d}"
                check_forbidden(caption)
                media_new.append({
                    "id": media_id, "conversation_id": conv["id"],
                    "sender_id": sender, "timestamp": iso(ts),
                    "type": mtype, "mime_type": mime, "file_name": fname,
                    "file_path": f"/media/{sender}/{ts.year}/{ts.month:02d}/{fname}",
                    "file_size_bytes": rng.randint(180_000, 4_800_000),
                    "caption": caption,
                    "thumbnail_path": (f"/media/{sender}/{ts.year}/{ts.month:02d}"
                                       f"/thumbnails/{fname.rsplit('.', 1)[0]}_thumb."
                                       f"{fname.rsplit('.', 1)[1]}"),
                })
                text, media_id_ref = caption, media_id
            else:
                text = rng.choice(lines)
                media_id_ref = ""
            check_forbidden(text)
            messages_new.append({
                "id": str(next_msg_id), "conversation_id": conv["id"],
                "sender_id": sender, "timestamp": iso(ts),
                "text": text, "read": 1, "media_id": media_id_ref,
            })
            next_msg_id += 1
        conv["last_message"] = iso(ts_list[-1])
        conv["message_count"] = n_msgs

    # sanity: everything predates the oldest existing conversation tail
    assert all(c["last_message"] < "2026-06-24T18:00:00Z" for c in convs_new)

    print(f"users: +{len(users_new)}, conversations: +{len(convs_new)}, "
          f"messages: +{len(messages_new)}, media: +{len(media_new)}")
    if dry:
        for c in convs_new[:3]:
            print(" ", c["id"], c["type"], c["participant_names"], c["last_message"], c["message_count"])
        for m in messages_new[:6]:
            print(" ", m["id"], m["conversation_id"], m["sender_id"], m["timestamp"], "|", m["text"][:60])
        for m in media_new[:3]:
            print(" ", m["id"], m["conversation_id"], m["file_name"])
        return

    bdir = ROOT / "data" / "backups" / "instant-messaging-expansion-2026-07-20"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "inserted_ids.json").write_text(json.dumps({
        "users": [u["id"] for u in users_new],
        "conversations": [c["id"] for c in convs_new],
        "messages": [m["id"] for m in messages_new],
        "media": [m["id"] for m in media_new]}, indent=1))

    for table, rows in (("users", users_new), ("conversations", convs_new),
                        ("messages", messages_new), ("media", media_new)):
        cols = list(rows[0].keys())
        db.executemany(
            f"INSERT INTO instant_messaging_{table} ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' * len(cols))})",
            [[r[c] for c in cols] for r in rows])
    # Sync the messages FTS index (external content, content_rowid=id).
    # fts_instant_messaging_media stays empty on purpose (see module docstring).
    db.execute("INSERT INTO fts_instant_messaging_messages(fts_instant_messaging_messages) VALUES('rebuild')")
    db.commit()
    print(f"inserted; rollback ids at {bdir}/inserted_ids.json")


if __name__ == "__main__":
    main()
