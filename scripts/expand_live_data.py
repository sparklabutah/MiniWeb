"""Expand StreamHub Live (site `live`) base data.

The site ships with only 99 rows (20 streams, 40 chat messages, 8 clips,
10 follows, 10 subscriptions, 5 users, 6 rewards), which makes its
filter/sort/search macros trivial. This adds deterministic (seeded)
synthetic rows: 55 new users (25 streamers + 30 viewers), ~325 completed
streams on the new channels, ~3900 chat messages, 300 clips, 400 follows,
150 subscriptions and 50 channel-point rewards, while keeping referential
integrity (channel_id/stream_id/follower_id always point at real rows) and
reusing the existing vocabulary (categories, id formats, badge JSON,
'-07:00' timestamps for completed streams, 'Z' timestamps for live ones,
ambient chatters with user_id='' like the seed data).

Task-safety choices:
  * All new streams are `status='completed'` and dated 2025-01-01..2026-05-09,
    OLDER than every existing stream (earliest existing: 2026-05-10), so
    "newest"-sort tops, the featured live stream and the live-first default
    grouping are unchanged.
  * duration_minutes capped at 195 (< existing max 210, stream-003), so the
    top of the duration sort ("sorted by length" task) is unchanged.
  * total_views capped below the existing maxima (21000 streams / 8920 clips)
    so "viewers"-sort tops are unchanged.
  * No new rows reference the main user ls-u-001 (alex_rivera): his follows,
    subscriptions and chat history are untouched.
  * Per-channel stream/clip counts stay ~13/12 (channel page + unbounded
    /api/channels/<id> stay small); per-stream chat stays <= 30 rows
    (unbounded /api/streams/<id>/chat stays small).

Insert-only — existing rows are never touched. Inserted ids are recorded in
data/backups/live-expansion-2026-07-20/inserted_ids.json for rollback.

Usage: python scripts/expand_live_data.py [--dry-run]
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

BACKUP_DIR = ROOT / "data" / "backups" / "live-expansion-2026-07-20"

CATEGORIES = ["Software Development", "Gaming", "Fitness & Health",
              "Music & Arts", "Just Chatting"]

# (username, display_name, channel_name, primary category, bio)
NEW_STREAMERS = [
    ("priya_builds", "Priya Sharma", "PriyaBuilds", "Software Development",
     "Frontend engineer live-coding React and design systems from Lakeport."),
    ("dev_dana", "Dana Whitfield", "DanaDotDev", "Software Development",
     "Backend nerd. Rust, Go, and way too many side projects."),
    ("terminal_tessa", "Tessa Nguyen", "TerminalTessa", "Software Development",
     "Linux, vim, and homelab streams. Ask me about my keyboard."),
    ("codewith_omar", "Omar Haddad", "CodeWithOmar", "Software Development",
     "Teaching Python and data engineering one stream at a time."),
    ("ship_it_sam", "Sam Okonkwo", "ShipItSam", "Software Development",
     "Indie SaaS builder. We ship on stream, bugs and all."),
    ("pixel_paige", "Paige Larsen", "PixelPaige", "Gaming",
     "Cozy games, indie gems, and the occasional rage quit."),
    ("frag_felix", "Felix Ortega", "FragFelix", "Gaming",
     "FPS grinder out of Meridian. Ranked or nothing."),
    ("lootgoblin_lena", "Lena Kowalski", "LootGoblinLena", "Gaming",
     "ARPG addict. If it drops loot, I stream it."),
    ("retro_ray", "Ray Donovan", "RetroRayPlays", "Gaming",
     "Retro consoles, speedruns, and CRT talk every week."),
    ("strategy_steve", "Steve Lindqvist", "StrategySteve", "Gaming",
     "Grand strategy and city builders. 400-hour save files welcome."),
    ("mmo_maria", "Maria Castillo", "MMOMaria", "Gaming",
     "Raid leader, guild drama survivor, mount collector."),
    ("coach_camille", "Camille Dubois", "CoachCamille", "Fitness & Health",
     "Certified trainer. Follow-along workouts, zero equipment needed."),
    ("kettlebell_ken", "Ken Yamamoto", "KettlebellKen", "Fitness & Health",
     "Kettlebells, mobility, and honest talk about recovery."),
    ("run_with_rosa", "Rosa Delgado", "RunWithRosa", "Fitness & Health",
     "Marathon training blocks streamed live from Cascadia trails."),
    ("yoga_with_june", "June Park", "YogaWithJune", "Fitness & Health",
     "Slow flows and breathwork for desk workers."),
    ("nutrition_nick", "Nick Adeyemi", "NutritionNick", "Fitness & Health",
     "Meal prep Sundays and evidence-based nutrition Q&A."),
    ("keys_and_kai", "Kai Andersen", "KeysAndKai", "Music & Arts",
     "Piano improv, chord theory, and listener requests."),
    ("violin_vera", "Vera Petrov", "ViolinVera", "Music & Arts",
     "Classical violinist practicing repertoire live. Mistakes included."),
    ("beatlab_bruno", "Bruno Silva", "BeatLabBruno", "Music & Arts",
     "Producing beats live in Ableton. Send me your demos."),
    ("sketchbook_sana", "Sana Qureshi", "SketchbookSana", "Music & Arts",
     "Digital illustration and character design streams."),
    ("cera_paints", "Cera Holloway", "CeraPaints", "Music & Arts",
     "Watercolor landscapes of the Lakeport shoreline, painted live."),
    ("latenight_leo", "Leo Fitzgerald", "LateNightLeo", "Just Chatting",
     "Late night talk, weird internet finds, and community games."),
    ("trivia_tara", "Tara McAllister", "TriviaTara", "Just Chatting",
     "Weekly trivia nights and rabbit-hole deep dives."),
    ("commute_carl", "Carl Bishop", "CommuteCarl", "Just Chatting",
     "IRL streams around Meridian: coffee shops, markets, transit."),
    ("bookclub_bea", "Bea Thompson", "BookclubBea", "Just Chatting",
     "Reading sleeves-rolled-up sci-fi and hosting the chat book club."),
]

NEW_VIEWERS = [
    ("quietlurker88", "Quiet Lurker"), ("gg_hannah", "Hannah Cole"),
    ("midwest_matt", "Matt Reiner"), ("sofia_streams", "Sofia Marino"),
    ("caffeine_cody", "Cody Blake"), ("nightowl_nina", "Nina Vasquez"),
    ("pdx_paul", "Paul Iverson"), ("lurking_lucy", "Lucy Tran"),
    ("gamer_gary_77", "Gary Holt"), ("emily_watches", "Emily Foster"),
    ("dan_the_fan", "Dan Kowalczyk"), ("mod_mia", "Mia Bennett"),
    ("chatty_chuck", "Chuck Ramsey"), ("vod_vic", "Vic Osei"),
    ("subbed_sarah", "Sarah Lindgren"), ("first_time_finn", "Finn Gallagher"),
    ("clip_it_cleo", "Cleo Marsh"), ("weekend_wes", "Wes Calloway"),
    ("tea_and_tina", "Tina Zhao"), ("bg_watcher_bob", "Bob Feldman"),
    ("hype_helen", "Helen Ito"), ("afk_andre", "Andre Boucher"),
    ("scrollin_sky", "Skyler James"), ("meridian_max", "Max Ferreira"),
    ("lakeport_liv", "Liv Sandoval"), ("second_monitor_sid", "Sid Kapoor"),
    ("cascadia_cass", "Cass Whitlock"), ("emote_spam_ed", "Ed Novak"),
    ("study_with_stef", "Stef Okafor"), ("channel_surfer_cy", "Cy Beaumont"),
]

AMBIENT_CHATTERS = [
    "dev_watcher_42", "code_newbie_99", "fullstack_fan", "backend_beginner",
    "night_coder", "fit_life_sarah", "morning_gains", "gym_rat_2024",
    "cardio_queen", "early_bird_mike", "workout_warrior", "typescript_tom",
    "new_to_fitness", "api_enthusiast", "protein_pete", "pog_patrick",
    "lurker_prime", "emote_only_erin", "vod_frog", "chat_goblin",
    "wasd_wendy", "gl_hf_greg", "malding_mal", "copium_carrie",
    "keyboard_cat_ken", "no_scope_nora", "monkas_moe", "kappa_kelly",
]

STREAM_TOPICS = {
    "Software Development": [
        ("Live Coding: {t} - Episode {n}",
         ["Building a CLI tool in Rust", "Refactoring legacy Django",
          "TypeScript monorepo cleanup", "Writing a toy compiler",
          "Postgres query tuning", "Terraform from zero",
          "Building a Discord bot", "WebSockets deep dive",
          "Testing with Playwright", "Docker multi-stage builds"]),
        ("{t} - Q&A and code review",
         ["Junior dev portfolio reviews", "System design practice",
          "Open source triage night", "Advent of Code catch-up",
          "API design office hours"]),
    ],
    "Gaming": [
        ("{t} - Part {n}",
         ["Elden Ring randomizer run", "Stardew Valley perfection save",
          "Baldur's Gate 3 honor mode", "Hades escape attempts",
          "Factorio megabase", "Zelda glitch hunting",
          "Hollow Knight steel soul", "Civilization deity marathon"]),
        ("Ranked grind: {t} - night {n}",
         ["Apex Legends solo queue", "Rocket League to Champ",
          "Valorant placements", "Street Fighter 6 ranked set"]),
    ],
    "Fitness & Health": [
        ("{t} - follow along, day {n}",
         ["30-minute HIIT burner", "Kettlebell strength circuit",
          "Mobility and stretch session", "5k training block",
          "Core and stability work", "Low-impact cardio",
          "Sunrise yoga flow", "Posture reset for desk workers"]),
        ("{t} - live Q&A",
         ["Meal prep and macros", "Recovery and sleep habits",
          "Marathon week check-in", "Beginner lifting form"]),
    ],
    "Music & Arts": [
        ("{t} - session {n}",
         ["Lo-fi beat making in Ableton", "Piano improv requests",
          "Violin repertoire practice", "Character sketch commissions",
          "Watercolor landscape study", "Mixing a listener demo",
          "Chord theory workshop", "Inktober catch-up drawing"]),
    ],
    "Just Chatting": [
        ("{t} - episode {n}",
         ["Community trivia night", "Late night talk and tangents",
          "IRL market walk in Meridian", "Book club discussion",
          "Reacting to weird internet finds", "Viewer story submissions",
          "Coffee and morning news", "Planning the next community event"]),
    ],
}

TAG_POOL = {
    "Software Development": ["livecoding", "backend", "frontend", "rust",
                             "python", "typescript", "devops", "opensource",
                             "tutorial", "debugging"],
    "Gaming": ["gaming", "ranked", "speedrun", "indie", "rpg", "fps",
               "strategy", "coop", "blind", "grind"],
    "Fitness & Health": ["workout", "followalong", "hiit", "yoga", "strength",
                         "mobility", "running", "health", "nutrition"],
    "Music & Arts": ["music", "art", "ableton", "piano", "violin",
                     "illustration", "watercolor", "practice", "requests"],
    "Just Chatting": ["justchatting", "irl", "community", "trivia", "talk",
                      "react", "books", "qa"],
}

CHAT_GENERIC = [
    "Hey everyone, just got here. What did I miss?",
    "This stream is exactly what I needed today.",
    "Wait, can you go back a second? Missed that part.",
    "First time catching you live, love the channel!",
    "The audio sounds way better than last week.",
    "How long are you streaming tonight?",
    "Chat is moving so fast today lol",
    "Clipped that, no way that just happened.",
    "Hello from the east coast, it is way too late here.",
    "Been following since the first stream. Proud of this channel!",
    "Anyone got a link to the schedule?",
    "brb grabbing a snack, don't do anything cool without me",
    "That transition was smooth.",
    "Can you do a quick recap for the late gang?",
    "The VOD from last time was great, watched the whole thing.",
    "What's the song playing in the background?",
    "This channel is so underrated honestly.",
    "Lurking while I work, good vibes as always.",
    "W stream so far",
    "ok that was actually impressive",
]

CHAT_BY_CAT = {
    "Software Development": [
        "Why not use a map here instead of the nested loop?",
        "You forgot to await that call, line 42.",
        "Tabs or spaces? Asking for a friend.",
        "This is better than my CS lectures, not even joking.",
        "What extensions are you using in your editor?",
        "Would this scale past like 10k requests?",
        "Rewrite it in Rust! (sorry, had to)",
        "The test suite passing first try is sus.",
        "Can you zoom the font a bit for mobile viewers?",
        "That error message is lying to you, check the import.",
        "How did you learn all this? Any course recs?",
        "Deploy it live, what could go wrong.",
    ],
    "Gaming": [
        "That dodge was frame perfect, clip it.",
        "You died to THAT? Unlucky.",
        "Go left, the chest is behind the waterfall.",
        "This boss took me 40 tries, good luck.",
        "What sensitivity are you playing on?",
        "The pathing on that build is so clean.",
        "One more game? It's only midnight.",
        "Chat, we do not tilt, we learn.",
        "You should try the randomizer mod next.",
        "That loot is actually insane for this early.",
    ],
    "Fitness & Health": [
        "My legs are shaking and we're only 10 minutes in.",
        "Form check on the last rep please!",
        "Doing this from my living room, dying quietly.",
        "How many rounds left? Asking for my lungs.",
        "The modification options are so helpful, thank you.",
        "Water break crew, check in.",
        "Did this workout yesterday, sore in muscles I didn't know existed.",
        "What do you eat before morning sessions?",
        "This is my third week following along. Down 2 kg!",
    ],
    "Music & Arts": [
        "That chord change is gorgeous.",
        "Can you play it slower once so I can follow?",
        "The blending on that sky is unreal.",
        "What brush are you using for the texture?",
        "Requesting something in a minor key next!",
        "I could listen to this all night.",
        "The way you fixed that mistake was so smooth.",
        "Practice streams like this are so motivating.",
        "That melody has been stuck in my head since last stream.",
    ],
    "Just Chatting": [
        "This story keeps getting better, go on.",
        "Trivia answer is B, I'm calling it now.",
        "The market looks so nice this time of year.",
        "Chat, vote in the poll, it's close!",
        "I read that book last month, no spoilers please.",
        "Your take on this is actually so reasonable.",
        "Greetings from the night shift, keep me company.",
        "The community here is the best part honestly.",
    ],
}

BROADCASTER_LINES = [
    "Welcome in everyone, glad you made it!",
    "Good question, let me show you what I mean.",
    "Thanks for the follow, welcome to the community!",
    "We'll take a short break in a few minutes, stay tuned.",
    "Drop your questions in chat, I'll get to them all.",
    "Okay chat, you convinced me, let's try it your way.",
    "Appreciate everyone hanging out tonight, seriously.",
    "If you're enjoying this, the follow button is right there.",
]

CLIP_TITLES = {
    "Software Development": [
        "{name} fixes a prod bug in 90 seconds", "The cleanest refactor you'll see today",
        "When the tests pass on the first try", "{name} explains the bug perfectly",
        "Live deploy with zero downtime", "The rubber duck moment, immortalized",
    ],
    "Gaming": [
        "{name} hits an insane clutch", "The boss kill after 30 attempts",
        "Perfectly timed dodge, chat lost it", "The luckiest drop of the season",
        "{name}'s reaction to the plot twist", "1v3 clutch with 10 HP left",
    ],
    "Fitness & Health": [
        "{name}'s form breakdown in 60 seconds", "The burpee finisher that broke chat",
        "New personal best, caught live", "The stretch everyone needed",
        "{name} answers the protein question once and for all",
    ],
    "Music & Arts": [
        "{name} improvises from a chat request", "The chord change that gave chills",
        "Painting the sky in 2 minutes", "From sketch to finished in one clip",
        "{name} nails the hardest passage",
    ],
    "Just Chatting": [
        "{name}'s wildest story yet", "Trivia answer that shocked everyone",
        "The market vendor stole the show", "Chat's book hot take, rated",
        "{name} can't stop laughing for a full minute",
    ],
}

REWARD_POOL = [
    ("Highlight My Message", "Your message gets highlighted in chat for 30 seconds", 500, 5),
    ("Choose Next Topic", "Pick what the streamer does next", 2000, 1),
    ("Hydrate!", "Make the streamer take a water break", 300, 10),
    ("Song Request", "Request a song for the stream playlist", 800, 5),
    ("Emote Only Chat", "Turn on emote-only mode for 2 minutes", 1500, 2),
    ("Stretch Break", "Everyone stretches for one minute", 400, 6),
    ("First!", "Claim the first redemption of the stream", 100, 1),
    ("VIP for a Day", "Get the VIP badge until end of stream", 5000, 1),
    ("Ask Me Anything", "The streamer must answer one question honestly", 1200, 3),
    ("Timeout a Friend", "Timeout another viewer for 60 seconds (with consent!)", 2500, 2),
]

EXISTING_STREAMERS = ["ls-u-001", "ls-u-002", "ls-u-003", "ls-u-004", "ls-u-005"]

# Existing completed streams without chat: (id, category, start iso, duration min)
EXISTING_QUIET_STREAMS = [
    ("stream-002", "ls-u-002", "Software Development", "2026-06-17T18:30:00", 195),
    ("stream-003", "ls-u-002", "Gaming", "2026-06-21T22:00:00", 210),
    ("stream-004", "ls-u-002", "Software Development", "2026-06-10T19:00:00", 150),
    ("stream-006", "ls-u-003", "Fitness & Health", "2026-06-18T06:00:00", 75),
    ("stream-007", "ls-u-003", "Fitness & Health", "2026-06-22T10:00:00", 90),
    ("stream-008", "ls-u-004", "Software Development", "2026-06-23T19:00:00", 120),
    ("stream-009", "ls-u-004", "Software Development", "2026-06-16T19:00:00", 150),
    ("stream-010", "ls-u-005", "Software Development", "2026-06-20T18:00:00", 180),
    ("stream-011", "ls-u-005", "Just Chatting", "2026-06-13T19:00:00", 150),
    ("stream-012", "ls-u-001", "Just Chatting", "2026-05-10T19:30:00", 150),
]

# Existing live streams (Z-format timestamps), category guessed from title
EXISTING_LIVE_STREAMS = [
    ("stream-101", "ls-u-001", "Software Development", "2026-06-29T14:00:00"),
    ("stream-102", "ls-u-003", "Gaming", "2026-06-29T15:30:00"),
    ("stream-103", "ls-u-005", "Fitness & Health", "2026-06-29T08:00:00"),
    ("stream-104", "ls-u-002", "Software Development", "2026-06-29T12:00:00"),
    ("stream-105", "ls-u-004", "Just Chatting", "2026-06-29T17:00:00"),
    ("stream-106", "ls-u-001", "Gaming", "2026-06-29T16:00:00"),
    ("stream-107", "ls-u-001", "Music & Arts", "2026-06-29T19:00:00"),
    ("stream-108", "ls-u-003", "Just Chatting", "2026-06-29T20:00:00"),
]

EXISTING_FOLLOW_PAIRS = {
    ("ls-u-001", "ls-u-002"), ("ls-u-001", "ls-u-003"), ("ls-u-001", "ls-u-005"),
    ("ls-u-004", "ls-u-002"), ("ls-u-005", "ls-u-002"), ("ls-u-002", "ls-u-003"),
    ("ls-u-005", "ls-u-003"), ("ls-u-002", "ls-u-005"), ("ls-u-004", "ls-u-005"),
    ("ls-u-004", "ls-u-003"),
}
EXISTING_SUB_PAIRS = {
    ("ls-u-001", "ls-u-002"), ("ls-u-001", "ls-u-003"), ("ls-u-004", "ls-u-002"),
    ("ls-u-005", "ls-u-002"), ("ls-u-001", "ls-u-005"), ("ls-u-002", "ls-u-003"),
    ("ls-u-005", "ls-u-003"), ("ls-u-002", "ls-u-005"), ("ls-u-004", "ls-u-005"),
    ("ls-u-004", "ls-u-003"),
}

TIER_PRICES = {"tier_1": 4.99, "tier_2": 9.99, "tier_3": 24.99}


def pdt(dt):
    """Format a naive datetime in the site's completed-stream style (-07:00)."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S-07:00")


def zulu(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def make_chat(stream_id, category, start_dt, duration_min, n, fmt,
              streamer, user_pool):
    """Generate n chat messages for one stream, timestamps inside its window."""
    msgs = []
    pool = CHAT_GENERIC + CHAT_BY_CAT[category]
    offsets = sorted(rng.sample(range(60, max(duration_min * 60 - 60, 121), 20),
                                min(n, max(1, (duration_min * 60 - 180) // 20))))
    for off in offsets:
        ts = start_dt + datetime.timedelta(seconds=off + rng.randint(0, 19))
        roll = rng.random()
        if roll < 0.12 and streamer is not None:
            uid, uname = streamer["id"], streamer["username"]
            text = rng.choice(BROADCASTER_LINES)
            badges, is_sub = '["broadcaster"]', 0
        elif roll < 0.60:
            u = rng.choice(user_pool)
            uid, uname = u["id"], u["username"]
            text = rng.choice(pool)
            if rng.random() < 0.3:
                badges, is_sub = '["subscriber"]', 1
            else:
                badges, is_sub = "[]", 0
        else:
            uid, uname = "", rng.choice(AMBIENT_CHATTERS)
            text = rng.choice(pool)
            if rng.random() < 0.2:
                badges, is_sub = '["subscriber"]', 1
            else:
                badges, is_sub = "[]", 0
        msgs.append({
            "stream_id": stream_id, "user_id": uid, "username": uname,
            "message": text, "timestamp": fmt(ts),
            "is_subscriber": is_sub, "badges": badges,
        })
    return msgs


def main():
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.row_factory = sqlite3.Row

    new = {"users": [], "streams": [], "chat_messages": [], "clips": [],
           "follows": [], "subscriptions": [], "channel_points": []}

    # ---- users ----------------------------------------------------------
    next_root = db.execute(
        "SELECT COALESCE(MAX(root_user_id),0)+1 FROM live_users").fetchone()[0]
    streamer_users, viewer_users = [], []
    uid_n = 6
    for username, display, channel, cat, bio in NEW_STREAMERS:
        created = datetime.datetime(rng.randint(2021, 2024), rng.randint(1, 12),
                                    rng.randint(1, 28), rng.randint(6, 22))
        row = {
            "id": f"ls-u-{uid_n:03d}", "root_user_id": next_root,
            "username": username, "display_name": display,
            "channel_name": channel,
            "avatar_url": f"https://streamhub.tv/avatars/{username}.jpg",
            "bio": bio,
            "subscriber_count": rng.randint(40, 2600),
            "total_views": rng.randint(4000, 82000),
            "is_partner": 1 if rng.random() < 0.3 else 0,
            "is_affiliate": 1 if rng.random() < 0.4 else 0,
            "created_at": zulu(created),
            "last_seen": zulu(datetime.datetime(2026, 6, rng.randint(20, 25),
                                                rng.randint(6, 23))),
            "status": "offline",
            "password": f"{username.split('_')[0]}2026",
            "channel_points_balance": rng.choice([500, 1000, 2500, 5000]),
            "_category": cat,
        }
        uid_n += 1
        next_root += 1
        streamer_users.append(row)
    for username, display in NEW_VIEWERS:
        created = datetime.datetime(rng.randint(2022, 2025), rng.randint(1, 12),
                                    rng.randint(1, 28), rng.randint(6, 22))
        row = {
            "id": f"ls-u-{uid_n:03d}", "root_user_id": next_root,
            "username": username, "display_name": display,
            "channel_name": display.replace(" ", ""),
            "avatar_url": f"https://streamhub.tv/avatars/{username}.jpg",
            "bio": "",
            "subscriber_count": 0,
            "total_views": rng.randint(0, 300),
            "is_partner": 0, "is_affiliate": 0,
            "created_at": zulu(created),
            "last_seen": zulu(datetime.datetime(2026, 6, rng.randint(18, 25),
                                                rng.randint(6, 23))),
            "status": "offline",
            "password": f"{username.split('_')[0]}watch",
            "channel_points_balance": rng.choice([500, 500, 1000, 2000]),
            "_category": "",
        }
        uid_n += 1
        next_root += 1
        viewer_users.append(row)
    new["users"] = streamer_users + viewer_users
    chat_pool = [u for u in (streamer_users + viewer_users)]  # never ls-u-001

    # ---- streams (all completed, all OLDER than 2026-05-10) -------------
    stream_n = 201
    start_lo = datetime.date(2025, 1, 1)
    start_hi = datetime.date(2026, 5, 9)
    span_days = (start_hi - start_lo).days
    streams_by_channel = {}
    for su in streamer_users:
        cat = su["_category"]
        n_streams = rng.randint(12, 14)
        chan_streams = []
        day_offsets = sorted(rng.sample(range(span_days), n_streams))
        for i, doff in enumerate(day_offsets):
            day = start_lo + datetime.timedelta(days=doff)
            hour = rng.choice([6, 7, 9, 10, 12, 14, 16, 18, 18, 19, 19, 20, 21])
            start = datetime.datetime(day.year, day.month, day.day, hour,
                                      rng.choice([0, 0, 15, 30]))
            duration = rng.choice(range(30, 196, 15))  # capped < 210 (task safety)
            end = start + datetime.timedelta(minutes=duration)
            fmt_tpl, topics = rng.choice(STREAM_TOPICS[cat])
            title = fmt_tpl.format(t=rng.choice(topics), n=i + 1)
            tags = rng.sample(TAG_POOL[cat], 4)
            peak = rng.randint(25, 850)
            avg = int(peak * rng.uniform(0.45, 0.75))
            total = min(int(peak * rng.uniform(3, 14)), 14500)
            sid = f"stream-{stream_n}"
            stream_n += 1
            row = {
                "id": sid, "channel_id": su["id"], "title": title,
                "category": cat, "tags": json.dumps(tags),
                "started_at": pdt(start), "ended_at": pdt(end),
                "duration_minutes": duration, "peak_viewers": peak,
                "average_viewers": avg, "total_views": total,
                "status": "completed",
                "vod_url": f"https://streamhub.tv/vods/{sid}",
                "_start": start, "_duration": duration,
            }
            chan_streams.append(row)
            new["streams"].append(row)
        streams_by_channel[su["id"]] = chan_streams

    # ---- chat messages --------------------------------------------------
    streamer_by_id = {u["id"]: u for u in streamer_users}
    existing_streamers = {
        "ls-u-001": {"id": "ls-u-001", "username": "alex_rivera"},
        "ls-u-002": {"id": "ls-u-002", "username": "marcus_chen"},
        "ls-u-003": {"id": "ls-u-003", "username": "nate_brooks_fit"},
        "ls-u-004": {"id": "ls-u-004", "username": "natalie_kim"},
        "ls-u-005": {"id": "ls-u-005", "username": "jake_morrison"},
    }
    for s in new["streams"]:
        n = rng.randint(9, 13)
        new["chat_messages"].extend(make_chat(
            s["id"], s["category"], s["_start"], s["_duration"], n, pdt,
            streamer_by_id[s["channel_id"]], chat_pool))
    for sid, chan, cat, start_iso, dur in EXISTING_QUIET_STREAMS:
        start = datetime.datetime.fromisoformat(start_iso)
        # broadcaster None for stream-012 (alex's stream): keep alex untouched
        streamer = None if chan == "ls-u-001" else existing_streamers[chan]
        new["chat_messages"].extend(make_chat(
            sid, cat, start, dur, 15, pdt, streamer, chat_pool))
    for sid, chan, cat, start_iso in EXISTING_LIVE_STREAMS:
        start = datetime.datetime.fromisoformat(start_iso)
        streamer = None if chan == "ls-u-001" else existing_streamers[chan]
        new["chat_messages"].extend(make_chat(
            sid, cat, start, 120, rng.randint(26, 30), zulu, streamer, chat_pool))
    for i, m in enumerate(new["chat_messages"]):
        m["id"] = f"chat-{41 + i:03d}"

    # ---- clips ----------------------------------------------------------
    clip_n = 9
    clipper_pool = [u for u in chat_pool]
    for su in streamer_users:
        first = su["display_name"].split()[0]
        for _ in range(12):
            src = rng.choice(streams_by_channel[su["id"]])
            offset_s = rng.randint(120, max(src["_duration"] * 60 - 120, 240))
            created = src["_start"] + datetime.timedelta(seconds=offset_s + 300)
            cid = f"clip-{clip_n:03d}"
            clip_n += 1
            if rng.random() < 0.6:
                clipper = rng.choice(clipper_pool)
                clipped_by, clipped_by_username = clipper["id"], ""
            else:
                clipped_by, clipped_by_username = "", rng.choice(AMBIENT_CHATTERS)
            title = rng.choice(CLIP_TITLES[su["_category"]]).format(name=first)
            new["clips"].append({
                "id": cid, "stream_id": src["id"], "channel_id": su["id"],
                "title": title, "clipped_by": clipped_by,
                "clip_url": f"https://streamhub.tv/clips/{cid}",
                "thumbnail_url": f"https://streamhub.tv/clips/thumbnails/{cid}.jpg",
                "duration_seconds": rng.randint(15, 120),
                "views": rng.randint(30, 7800),  # < existing max 8920
                "created_at": pdt(created),
                "clipped_by_username": clipped_by_username,
            })

    # ---- follows --------------------------------------------------------
    all_channels = EXISTING_STREAMERS[1:] + [u["id"] for u in streamer_users]
    followers = [u["id"] for u in chat_pool] + EXISTING_STREAMERS[1:]
    candidates = [(f, c) for f in followers for c in all_channels
                  if f != c and (f, c) not in EXISTING_FOLLOW_PAIRS]
    rng.shuffle(candidates)
    follow_n = 11
    for f, c in candidates[:400]:
        followed = datetime.datetime(rng.randint(2023, 2025), rng.randint(1, 12),
                                     rng.randint(1, 28), rng.randint(0, 23))
        new["follows"].append({
            "id": f"follow-{follow_n:03d}", "follower_id": f, "channel_id": c,
            "followed_at": zulu(followed),
        })
        follow_n += 1

    # ---- subscriptions --------------------------------------------------
    sub_candidates = [(s, c) for s, c in candidates[400:]
                      if (s, c) not in EXISTING_SUB_PAIRS]
    rng.shuffle(sub_candidates)
    sub_n = 11
    for s, c in sub_candidates[:150]:
        tier = rng.choices(["tier_1", "tier_2", "tier_3"], weights=[80, 15, 5])[0]
        months = rng.randint(1, 34)
        started = datetime.datetime(2026, 6, 1) - datetime.timedelta(days=30 * months)
        renewed = datetime.datetime(2026, 6, rng.randint(1, 25), started.hour)
        is_gift = 1 if rng.random() < 0.1 else 0
        new["subscriptions"].append({
            "id": f"sub-{sub_n:03d}", "subscriber_id": s, "channel_id": c,
            "tier": tier, "started_at": zulu(started), "renewed_at": zulu(renewed),
            "is_active": 1 if rng.random() < 0.85 else 0,
            "is_gift": is_gift,
            "months_subscribed": months,
            "monthly_price_usd": TIER_PRICES[tier],
        })
        sub_n += 1

    # ---- channel point rewards -----------------------------------------
    reward_n = 7
    for su in streamer_users:
        for name, desc, cost, per in rng.sample(REWARD_POOL, 2):
            new["channel_points"].append({
                "id": f"reward-{reward_n:03d}", "channel_id": su["id"],
                "name": name, "description": desc, "cost": cost,
                "is_enabled": 1, "max_per_stream": per,
            })
            reward_n += 1

    # ---- strip helper keys, report, insert ------------------------------
    for u in new["users"]:
        u.pop("_category")
    for s in new["streams"]:
        s.pop("_start")
        s.pop("_duration")

    for t in new:
        print(f"{t}: +{len(new[t])}")
    print("total new:", sum(len(v) for v in new.values()))
    if dry:
        for t in new:
            for r in new[t][:2]:
                print(" ", json.dumps(r, default=str)[:170])
        return

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    (BACKUP_DIR / "inserted_ids.json").write_text(json.dumps(
        {t: [r["id"] for r in rows] for t, rows in new.items()}, indent=1))

    for t, rows in new.items():
        if not rows:
            continue
        cols = list(rows[0].keys())
        sql = (f"INSERT INTO live_{t} ({', '.join(cols)}) "
               f"VALUES ({', '.join('?' * len(cols))})")
        db.executemany(sql, [[r[c] for c in cols] for r in rows])
    db.commit()

    # FTS sync (external-content tables; harmless no-op gate for db.search,
    # which falls back to LIKE because these fts tables report COUNT 0)
    for ft in ("fts_live_chat_messages", "fts_live_streams",
               "fts_live_follows", "fts_live_subscriptions"):
        try:
            db.execute(f"INSERT INTO {ft}({ft}) VALUES('rebuild')")
            db.commit()
        except sqlite3.Error as e:
            print(f"fts rebuild skipped for {ft}: {e}")

    print(f"inserted; rollback ids at {BACKUP_DIR}/inserted_ids.json")


if __name__ == "__main__":
    main()
