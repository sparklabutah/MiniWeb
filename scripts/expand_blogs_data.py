"""Expand blogs (TumblrVibe) base data: users, posts, comments, reports.

The site ships with only 53 rows (6 users, 15 posts, 30 comments, 2 reports),
which makes its filter/sort/search macros trivial. This adds deterministic
(seeded) synthetic rows: ~34 new blogger accounts, ~1200 posts spread across
the existing category vocabulary and date range, ~3700 comments attached to
those posts, and ~58 moderation reports. All content reuses the site's
Lakeport/Cascadia/PNW voice and existing enum/format conventions.

Task-safety constraints honored:
  * Oldest post stays "Rainy Day Photography: Embracing the PNW Gray"
    (2025-11-03) — every new post is dated 2025-11-04 or later.
  * Newest post stays "How We're Using AI at SyncWave (Honestly)"
    (2026-06-18) — every new post is dated 2026-06-17 or earlier, so the
    top of the newest-first feed is unchanged.
  * No post titled "Intro to Python" (nor any "Intro to Python ..." variant).
  * Tag "film-photography" is reused verbatim only — no confusable variants
    (nothing else containing "film").
  * No new posts are authored by the main user (alex_codes, id 1).

Insert-only — existing rows are never touched. Inserted ids are recorded in
data/backups/blogs-expansion-2026-07-20/inserted_ids.json for rollback.
FTS indexes (fts_blogs_posts, fts_blogs_comments) are rebuilt after insert.

Usage: python scripts/expand_blogs_data.py [--dry-run]
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

# Hard date fence: strictly newer than the oldest post (2025-11-03),
# strictly older than the newest post (2026-06-18).
DATE_MIN = datetime.date(2025, 11, 4)
DATE_MAX = datetime.date(2026, 6, 17)
TODAY = datetime.date(2026, 7, 18)

FORBIDDEN_TITLE = "intro to python"

# ---------------------------------------------------------------------------
# New users. The first 8 match the unused avatar SVGs already shipped in
# sites/blogs/static/images/avatars/. The rest reuse the generated PNG
# avatars already referenced by existing posts.
# ---------------------------------------------------------------------------
SVG_USERS = [
    ("bookworm_alex", "Alexandra Page", "Second-hand bookshop regular and annotator of margins. Currently working through the Cascadia authors shelf."),
    ("fitness_nova", "Nova Reyes", "Certified trainer at Lakeport Rec Center. Kettlebells, trail runs, and the occasional donut. Balance."),
    ("green_thumb", "Marisol Vega", "Urban gardener coaxing tomatoes out of a north-facing Lakeport balcony. Compost evangelist."),
    ("kitchen_sage", "Theo Marchetti", "Home cook chasing my nonna's recipes and fermenting everything that stays still long enough."),
    ("midnight_coder", "Devon Park", "Backend engineer who does their best work after 11pm. Rust curious, coffee dependent."),
    ("pixel_dreamer", "Iris Nakamura", "Pixel artist and indie game dev. Making tiny worlds one 16x16 tile at a time."),
    ("retro_vinyl", "Gus Delgado", "Record collector and weekend DJ at The Rusted Anchor. If it crackles, I'm interested."),
    ("wanderlust_jess", "Jess Okonkwo", "Travel writer covering the ferry routes, fire lookouts, and diners of the Pacific Northwest."),
]

EXTRA_USERS = [
    ("trailhead_tina", "Tina Kowalski", "Weekend peak-bagger logging every trail within two hours of Lakeport."),
    ("sourdough_sam", "Sam Whitfield", "Bread nerd. My starter is named Clint Yeastwood and it is thriving."),
    ("gallery_gwen", "Gwen Ashford", "Curator at the Meridian Arts Collective. Writing about the local art scene and studio visits."),
    ("chords_and_coffee", "Miles Buchanan", "Songwriter and open-mic host at Driftwood Coffee. Acoustic everything."),
    ("darkroom_dana", "Dana Petrov", "Shooting black-and-white on a thrifted Pentax and developing in my bathroom."),
    ("couch_critic", "Priya Raman", "Reviewing books, games, and prestige TV from the world's most dented couch."),
    ("cascadia_runner", "Owen Gallagher", "Marathoner-in-training. Chronicling every rainy mile along the Lakeport waterfront."),
    ("thrift_theory", "Bea Solomon", "Vintage reseller and slow-fashion advocate. Your grandma's blazer deserves a second act."),
    ("ledger_and_latte", "Hannah Cho", "Bootstrapped founder writing honestly about revenue, churn, and imposter syndrome."),
    ("polyglot_pete", "Pete Iversen", "Learning my fifth language and blogging the grammar rabbit holes along the way."),
    ("brine_time", "Rosa Camacho", "Pickles, kimchi, hot sauce. If it can be jarred, I have opinions about it."),
    ("frame_by_frame", "Leo Tanaka", "Animator by trade, film-club projectionist by night at the Meridian Grand."),
    ("summit_journal", "Astrid Larsen", "Alpine scrambles, gear teardowns, and honest trip reports from the Cascadia Range."),
    ("ink_and_index", "Clara Whitmore", "Archivist and fountain pen collector. Old paper, older stories."),
    ("synthwave_sara", "Sara Lindqvist", "Bedroom producer stacking analog synths. Releasing an EP one pad at a time."),
    ("plotters_nook", "Nadia Ferreira", "Mystery novelist drafting book three and procrastinating with elaborate outlines."),
    ("deadlift_dre", "Andre Bishop", "Powerlifting coach. Form checks, meal prep, and why your warm-up matters."),
    ("mosswood_maker", "Finn O'Callaghan", "Woodworker turning storm-fall cedar into furniture in a Lakeport garage shop."),
    ("aperture_amy", "Amy Castellanos", "Wedding photographer by weekend, street photographer on lunch breaks."),
    ("byte_sized_ben", "Ben Osei", "Explaining computer science concepts with terrible drawings and decent analogies."),
    ("harbor_hiker", "Maggie Donnelly", "Ferry-hopping the sound with a daypack and a thermos. Islands are my love language."),
    ("quiet_quilter", "Ruth Abernathy", "Modern quilting, hand stitching, and the meditative math of half-square triangles."),
    ("stage_left_stan", "Stan Vukovic", "Community theater director at the Lakeport Playhouse. Break legs, not budgets."),
    ("noodle_nomad", "Kenji Watanabe", "Rating every noodle bowl in the tri-city area. Broth is a personality trait."),
    ("open_source_olga", "Olga Petrenko", "Maintainer of three libraries nobody has heard of and one everybody depends on."),
    ("last_page_lucy", "Lucy Trần", "Reading 100 books a year and reviewing the ones that survive my commute."),
]

AVATAR_PNGS = [
    "/static/generated/blogs_240ce8ac006e.png",
    "/static/generated/blogs_0e32c485ac0a.png",
    "/static/generated/blogs_dcef90e0da7f.png",
    "/static/generated/blogs_ec0afbf444ba.png",
]

POST_IMAGES = [
    "/static/generated/blogs_6ba004372504.png",
    "/static/generated/blogs_4dea44fc9b4e.png",
    "/static/generated/blogs_6fd194512afb.png",
    "/static/generated/blogs_a2888b49b8d5.png",
    "/static/generated/blogs_9dd8929d5b08.png",
]

# ---------------------------------------------------------------------------
# Post content vocabulary, per category. Tags reuse the site's kebab-case
# style; "film-photography" appears verbatim only (no variants containing
# "film" anywhere else).
# ---------------------------------------------------------------------------
CATEGORIES = {
    "Technology": {
        "tags": ["coding", "open-source", "linux", "webdev", "productivity", "ai", "self-hosting", "hardware"],
        "topics": ["a static site generator", "my dotfiles", "a home server", "a CLI habit tracker",
                   "an RSS reader", "a keyboard firmware", "a budget NAS", "a personal wiki",
                   "a browser extension", "a tiling window manager setup"],
        "titles": [
            "I Rebuilt {topic} From Scratch and Learned a Lot",
            "Six Months With {topic}: A Follow-Up",
            "Why {topic} Is My Favorite Side Project Yet",
            "The Case for Boring Tools: Notes on {topic}",
            "What Maintaining {topic} Taught Me About Software",
            "Over-Engineering {topic} So You Don't Have To",
        ],
    },
    "Travel": {
        "tags": ["pnw", "roadtrip", "ferries", "hidden-gems", "budget-travel", "islands", "camping"],
        "topics": ["the Cascadia Pass loop", "the Meridian ferry route", "a weekend in Lakeport's old town",
                   "the coastal fire lookouts", "the hot springs east of the ridge", "the rail-trail to Harborview",
                   "three small towns off Highway 12", "the peninsula lighthouse circuit"],
        "titles": [
            "Trip Report: {topic}",
            "A Slow Weekend Along {topic}",
            "Everything I Ate and Saw on {topic}",
            "{topic_t}: An Off-Season Guide",
            "Why {topic} Belongs on Your Shoulder-Season List",
        ],
    },
    "Food": {
        "tags": ["baking", "fermentation", "recipes", "meal-prep", "farmers-market", "coffee", "noodles"],
        "topics": ["sourdough focaccia", "small-batch kimchi", "a weeknight ramen upgrade", "cast-iron pizza",
                   "hand-rolled pasta", "cold brew concentrate", "miso soup from scratch", "brown butter cookies",
                   "pickled spring vegetables", "a farmers market haul dinner"],
        "titles": [
            "I Made {topic} Every Week for a Month",
            "The Only {topic_t} Method I'll Use Now",
            "{topic_t}, Three Ways",
            "Lessons From a Failed Batch of {topic}",
            "How the Lakeport Farmers Market Changed My {topic_t} Game",
        ],
    },
    "Art": {
        "tags": ["illustration", "sketchbook", "watercolor", "gallery", "printmaking", "pixel-art"],
        "topics": ["daily sketchbook pages", "linocut printing", "gouache landscapes", "figure drawing sessions",
                   "a 30-day pixel art challenge", "urban sketching downtown", "risograph zines"],
        "titles": [
            "What 100 Days of {topic_t} Did to My Style",
            "Notes From the Meridian Arts Collective: {topic_t}",
            "Getting Unstuck: {topic_t} as Practice",
            "{topic_t} on a Budget: My Full Kit",
            "Why I Keep Coming Back to {topic_t}",
        ],
    },
    "Books": {
        "tags": ["book-review", "fiction", "nonfiction", "literary", "reading-list", "local-history", "library"],
        "topics": ["a forgotten Cascadia novelist", "my five-star reads this spring", "the new translation everyone's arguing about",
                   "a doorstopper fantasy series", "the library hold queue", "backlist mysteries", "small-press poetry"],
        "titles": [
            "Reading Notes: {topic_t}",
            "I Finally Finished {topic_t} — Was It Worth It?",
            "An Ode to {topic_t}",
            "What {topic_t} Gets Right (and Wrong)",
            "Marginalia: Thoughts on {topic_t}",
        ],
    },
    "Fitness": {
        "tags": ["running", "strength-training", "climbing", "recovery", "trail-running", "yoga"],
        "topics": ["a 10K training block", "kettlebell basics", "climbing at the new Lakeport gym",
                   "zone 2 running", "a deload week", "morning mobility work", "my first trail half-marathon"],
        "titles": [
            "Training Log: {topic_t}",
            "What {topic_t} Taught Me About Consistency",
            "{topic_t} for People Who Hate {topic_t}",
            "Eight Weeks of {topic_t}: Honest Results",
            "The Unsexy Truth About {topic_t}",
        ],
    },
    "Music": {
        "tags": ["vinyl", "synths", "live-music", "playlists", "songwriting", "local-bands"],
        "topics": ["the open mic at Driftwood Coffee", "a crate-digging haul", "my first hardware synth",
                   "the Lakeport waterfront concert series", "mixing a bedroom EP", "a perfect rainy-day playlist",
                   "the record fair at the fairgrounds"],
        "titles": [
            "Field Notes: {topic_t}",
            "I Can't Stop Thinking About {topic_t}",
            "{topic_t}: A Beginner's Deep Dive",
            "What I Learned From {topic_t}",
            "In Defense of {topic_t}",
        ],
    },
    "Lifestyle": {
        "tags": ["vintage", "thrifting", "slow-living", "home", "minimalism", "gardening", "diy"],
        "topics": ["a no-buy month", "balcony gardening", "my thrifted kitchen", "digital decluttering",
                   "the 20-minute evening reset", "repairing instead of replacing", "a capsule wardrobe experiment"],
        "titles": [
            "I Tried {topic_t} for 30 Days",
            "{topic_t}: What Stuck and What Didn't",
            "The Quiet Joy of {topic_t}",
            "How {topic_t} Simplified My Week",
            "{topic_t}, One Year Later",
        ],
    },
    "Photography": {
        "tags": ["photography", "analog", "street-photography", "golden-hour", "landscape", "darkroom", "film-photography"],
        "topics": ["shooting the fog on Harbor Drive", "a one-lens challenge", "developing black-and-white at home",
                   "golden hour at the marina", "street portraits downtown", "long exposures at the falls",
                   "photographing the ferry commute"],
        "titles": [
            "Contact Sheet: {topic_t}",
            "What {topic_t} Taught Me About Light",
            "{topic_t}: Settings, Mistakes, and Keepers",
            "A Morning Spent {topic_t}",
            "Why {topic_t} Made Me a Slower Photographer",
        ],
    },
    "Gaming": {
        "tags": ["board-games", "indie-games", "rpg", "co-op", "game-design", "retro-gaming"],
        "topics": ["a legacy board game campaign", "the indie roguelike eating my evenings", "our Tuesday D&D table",
                   "a retro handheld restoration", "co-op games for two players", "the local game night scene",
                   "a farming sim I refuse to put down"],
        "titles": [
            "Session Report: {topic_t}",
            "{topic_t} Is Better Than It Has Any Right to Be",
            "100 Hours Into {topic_t}: A Reckoning",
            "Why {topic_t} Works So Well",
            "The Design Genius Hiding in {topic_t}",
        ],
    },
    "Outdoors": {
        "tags": ["hiking", "pnw", "trails", "camping", "backpacking", "birding"],
        "topics": ["the Whisper Creek headwaters", "an overnight at Hemlock Hollow", "birding the estuary boardwalk",
                   "the Boundary Creek extension", "a foggy scramble up Cascadia Pass", "car camping at the north shore",
                   "the new connector trail above the bluff"],
        "titles": [
            "Trail Journal: {topic_t}",
            "Mud, Moss, and {topic_t}",
            "{topic_t}: Conditions, Gear, and Photos",
            "A Quiet Morning on {topic_t}",
            "{topic_t} Before the Crowds Arrive",
        ],
    },
    "Marketing": {
        "tags": ["social-media", "branding", "content-strategy", "newsletters", "analytics", "freelance"],
        "topics": ["a newsletter relaunch", "organic reach in 2026", "a small-business rebrand",
                   "content batching", "community-led growth", "a client onboarding overhaul"],
        "titles": [
            "Case Study: {topic_t}",
            "{topic_t} Without Burning Out",
            "The Honest Numbers Behind {topic_t}",
            "What Nobody Tells You About {topic_t}",
            "{topic_t}: A Practical Playbook",
        ],
    },
    "Design": {
        "tags": ["design", "typography", "illustration", "ux", "print-design", "color"],
        "topics": ["a type-only poster series", "redesigning a local cafe's menu", "grid systems",
                   "a personal brand refresh", "accessible color palettes", "hand-lettering practice"],
        "titles": [
            "Process Notes: {topic_t}",
            "{topic_t} and the Art of Restraint",
            "What 1960s Poster Art Taught Me About {topic_t}",
            "{topic_t}: Before and After",
            "Falling Back in Love With {topic_t}",
        ],
    },
    "History": {
        "tags": ["local-history", "archives", "lakeport", "maritime", "community"],
        "topics": ["the old cannery on Pier 4", "Lakeport's streetcar era", "the 1912 waterfront fire",
                   "the Cascadia Timber Company ledgers", "the lighthouse keepers' logbooks", "the immigrant boarding houses on Mill Street"],
        "titles": [
            "From the Archives: {topic_t}",
            "The Forgotten Story of {topic_t}",
            "What {topic_t} Reveals About Old Lakeport",
            "Tracing {topic_t} Through the County Records",
            "{topic_t}: A Walking Tour",
        ],
    },
    "Startups": {
        "tags": ["startups", "entrepreneurship", "bootstrapping", "product", "remote-work", "founder-life"],
        "topics": ["our first paying customer", "a failed feature launch", "hiring employee number three",
                   "the pivot we almost made", "pricing experiments", "a year of remote-first work"],
        "titles": [
            "Founder Diary: {topic_t}",
            "{topic_t}: What Actually Happened",
            "The Spreadsheet Behind {topic_t}",
            "Hard Lessons From {topic_t}",
            "{topic_t}, and Other Things They Don't Teach You",
        ],
    },
}

OPENERS = [
    "I've been meaning to write this one up for weeks, so here it finally is.",
    "Fair warning: this post is longer than I planned, but I think it's worth it.",
    "This started as a quick note and turned into something closer to a field report.",
    "A few people asked about this after my last post, so let's get into the details.",
    "I went into this with low expectations and came out with a lot of opinions.",
    "Some experiments fail quietly. This one did not, and I took notes the whole way.",
    "Rainy Lakeport weekends are good for exactly one thing: projects like this.",
    "I promised myself I'd document the process this time instead of just living it.",
]

MIDDLES = [
    "The first attempt went sideways almost immediately, which in hindsight was the best thing that could have happened. I slowed down, wrote out what I was actually trying to do, and started again with a plan instead of vibes. The second pass felt completely different -- less flailing, more noticing.",
    "What surprised me most was how much the small details mattered. The big decisions were easy; it was the tiny ones, made at hour three when my patience was thin, that shaped how the whole thing turned out. I keep a running list of those now.",
    "Somewhere in the middle I hit the wall everyone warns you about. I stepped away for two days, came back with fresh eyes, and the problem that had eaten an entire evening resolved itself in about twenty minutes. There's a lesson in there I keep having to relearn.",
    "I asked around at the Lakeport meetup and got three completely contradictory pieces of advice, all delivered with total confidence. I ended up testing all three. Two were wrong for my situation and one changed everything, which feels about par for the course.",
    "The middle stretch was mostly unglamorous repetition -- the kind of steady, boring effort that never makes it into anyone's highlight reel but quietly does all the work. I tracked everything in a notebook, and reading it back is weirdly satisfying.",
    "Halfway through, I realized I'd been optimizing for the wrong thing entirely. Course-correcting stung a little, but the end result is so much better that I can't be too precious about the wasted effort. Sunk costs are sunk.",
]

CLOSERS = [
    "Would I do it again? Absolutely -- but differently, and probably slower. If you try this yourself, let me know how it goes in the comments.",
    "The takeaway, if there is one: start smaller than feels reasonable, and keep notes. Future you will be grateful.",
    "I'm calling this a win, with an asterisk. Ask me again in six months whether the asterisk is still there.",
    "If any of this was useful, the best thing you can do is try it and report back. Half of what I know came from comment threads exactly like the one below.",
    "Next up: the follow-up experiment I've been threatening for months. Subscribe to the tags if you want to catch it.",
    "That's the whole story. No dramatic ending, just steady progress and a few good photos along the way -- which, honestly, is the best kind of project.",
]

COMMENT_TEXTS = [
    "This is exactly the write-up I needed this week. Bookmarking for the weekend.",
    "Great post! The middle section especially -- I've hit that same wall more times than I want to admit.",
    "I tried something similar last year and gave up halfway. You've convinced me to take another run at it.",
    "The Lakeport references made me smile. This town really does run on projects like this.",
    "Honest question: how much time did this actually take end to end? Trying to budget my next free weekend.",
    "Adding my experience: the advice you got at the meetup matches what worked for me too.",
    "This deserves way more notes than it has. Sharing with a friend who's been on the fence.",
    "The part about optimizing for the wrong thing hit uncomfortably close to home. Excellent post.",
    "Longtime lurker, first comment -- your posts are consistently the best thing in my feed.",
    "Do you have a parts/gear list for this? Would love to replicate the setup.",
    "I respectfully disagree with the conclusion, but the process notes are gold either way.",
    "Came for the photos, stayed for the surprisingly practical advice. Well done.",
    "My partner and I did this together last month and can confirm: start smaller than feels reasonable.",
    "The notebook habit is underrated. I started doing the same after your last post and it's changed everything.",
    "Please write the follow-up soon. I have questions that only part two can answer.",
    "As someone who works in this space professionally, this is more accurate than most paid guides.",
    "Saving this to my reading list. The closer about sunk costs is going on a sticky note.",
    "Found this through the tag feed and immediately followed. Great voice, great detail.",
    "Second attempt worked for me too after reading this. Thank you for writing it up properly.",
    "This is the kind of post that makes this platform worth checking every morning.",
]

REPORT_REASONS = {
    "spam": [
        "A comment on this post links to a suspicious 'free followers' service. Looks like a bot account.",
        "Repeated copy-pasted comment advertising a crypto exchange. Same text appears on other posts.",
        "The same account has dropped an affiliate link in three comment threads today. Reporting as spam.",
        "Comment thread has an obvious bot reply pushing a discount-code site unrelated to the post.",
    ],
    "harassment": [
        "A commenter is repeatedly insulting the author across multiple replies instead of engaging with the post.",
        "One reply targets another commenter personally and keeps escalating. Please take a look.",
    ],
    "misinformation": [
        "A comment presents made-up trail conditions as official guidance, which could be a safety issue.",
        "Reply cites a 'study' that does not exist to dispute the author's numbers. Flagging for review.",
    ],
    "inappropriate": [
        "A comment contains crude remarks that are out of place for this thread.",
        "Reply includes an off-topic graphic description that does not belong under this post.",
    ],
}


def iso(day):
    return day.isoformat()


def rand_date(lo, hi):
    span = (hi - lo).days
    return lo + datetime.timedelta(days=rng.randint(0, max(span, 0)))


MINOR_WORDS = {"a", "an", "the", "of", "and", "or", "on", "in", "at", "to",
               "for", "with", "from", "as", "by", "my", "our", "into", "than"}


def smart_title(text):
    """Title-case lowercase words, keep acronyms/mixed case, lower minor words."""
    words = text.split(" ")
    out = []
    for i, w in enumerate(words):
        core = w.strip(":,.!?'\"()")
        if not core or not core.replace("-", "").isalpha() or core != core.lower():
            out.append(w)  # acronyms, numbers, already-cased words
        elif 0 < i < len(words) - 1 and core in MINOR_WORDS:
            out.append(w)
        else:
            out.append("-".join(p[:1].upper() + p[1:] for p in w.split("-")))
    return " ".join(out)


def make_title(cat_def):
    tmpl = rng.choice(cat_def["titles"])
    topic = rng.choice(cat_def["topics"])
    title = smart_title(tmpl.format(topic=topic, topic_t=topic))
    assert FORBIDDEN_TITLE not in title.lower()
    return title


def make_body(title):
    paras = [rng.choice(OPENERS)]
    for m in rng.sample(MIDDLES, rng.randint(1, 2)):
        paras.append(m)
    paras.append(rng.choice(CLOSERS))
    return "\n\n".join(paras)


def main():
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.row_factory = sqlite3.Row

    existing_users = [dict(r) for r in db.execute("SELECT * FROM blogs_users ORDER BY id")]
    next_uid = db.execute("SELECT COALESCE(MAX(id),0)+1 FROM blogs_users").fetchone()[0]
    next_pid = db.execute("SELECT COALESCE(MAX(id),0)+1 FROM blogs_posts").fetchone()[0]
    next_cid = db.execute("SELECT COALESCE(MAX(id),0)+1 FROM blogs_comments").fetchone()[0]
    next_rid = db.execute("SELECT COALESCE(MAX(id),0)+1 FROM blogs_reports").fetchone()[0]
    existing_post_ids = [r["id"] for r in db.execute("SELECT id FROM blogs_posts")]

    new = {"users": [], "posts": [], "comments": [], "reports": []}

    # ---- users ----------------------------------------------------------
    all_tags = sorted({t for c in CATEGORIES.values() for t in c["tags"]})
    for i, (username, display, bio) in enumerate(SVG_USERS + EXTRA_USERS):
        if i < len(SVG_USERS):
            avatar = f"/sites/blogs/static/images/avatars/{username}.svg"
        else:
            avatar = AVATAR_PNGS[i % len(AVATAR_PNGS)]
        row = {
            "id": next_uid,
            "root_user_id": 0,
            "username": username,
            "password": f"pass{next_uid}23",
            "display_name": display,
            "bio": bio,
            "avatar": avatar,
            "followed_blogs": json.dumps(
                rng.sample([u["username"] for u in existing_users], rng.randint(0, 2))),
            "saved_posts": json.dumps(
                sorted(rng.sample(existing_post_ids, rng.randint(0, 3)))),
            "subscribed_tags": json.dumps(rng.sample(all_tags, rng.randint(2, 5))),
        }
        next_uid += 1
        new["users"].append(row)

    # Post authors: every user except the main user alex_codes (id 1).
    author_pool = [u for u in existing_users if u["id"] != 1] + new["users"]
    # New bloggers carry most of the volume; existing side authors get a
    # lighter share so their author pages stay recognizable.
    weights = [3 if u in existing_users else 10 for u in author_pool]

    # ---- posts ----------------------------------------------------------
    N_POSTS = 1200
    cat_names = list(CATEGORIES.keys())
    seen_titles = set()
    for _ in range(N_POSTS):
        cat = rng.choice(cat_names)
        cdef = CATEGORIES[cat]
        title = make_title(cdef)
        # Titles may repeat across a big platform, but keep dupes rare.
        tries = 0
        while title in seen_titles and tries < 5:
            title = make_title(cdef)
            tries += 1
        seen_titles.add(title)
        author = rng.choices(author_pool, weights=weights)[0]
        date = rand_date(DATE_MIN, DATE_MAX)
        tags = rng.sample(cdef["tags"], rng.randint(2, min(4, len(cdef["tags"]))))
        row = {
            "id": next_pid,
            "title": title,
            "body": make_body(title),
            "author_id": author["id"],
            "author_username": author["username"],
            "author_display_name": author["display_name"],
            "author_avatar": author["avatar"],
            "category": cat,
            "tags": json.dumps(tags),
            "image_url": rng.choice(POST_IMAGES) if rng.random() < 0.15 else "",
            "date": iso(date),
            "notes_count": rng.choice([rng.randint(0, 40), rng.randint(10, 120), rng.randint(60, 380)]),
            "is_pinned": 0,
            "shared_count": rng.randint(0, 55),
        }
        next_pid += 1
        new["posts"].append(row)

    # ---- comments -------------------------------------------------------
    commenter_pool = existing_users + new["users"]
    TARGET_COMMENTS = 3720

    def add_comment(post_id, post_date_iso, post_author):
        author = rng.choice(commenter_pool)
        while author["username"] == post_author:
            author = rng.choice(commenter_pool)
        pd = datetime.date.fromisoformat(post_date_iso)
        cdate = rand_date(pd, min(pd + datetime.timedelta(days=45), TODAY))
        nonlocal_next = add_comment.next_id
        new["comments"].append({
            "id": nonlocal_next,
            "post_id": post_id,
            "author_username": author["username"],
            "author_display_name": author["display_name"],
            "body": rng.choice(COMMENT_TEXTS),
            "date": iso(cdate),
        })
        add_comment.next_id += 1

    add_comment.next_id = next_cid

    for p in new["posts"]:
        for _ in range(rng.choices([0, 1, 2, 3, 4, 5, 6, 8], weights=[8, 14, 20, 20, 16, 10, 8, 4])[0]):
            add_comment(p["id"], p["date"], p["author_username"])
    # A few late arrivals on existing posts too, then top up to target.
    existing_posts = [dict(r) for r in db.execute(
        "SELECT id, date, author_username FROM blogs_posts ORDER BY id")]
    for p in existing_posts:
        for _ in range(rng.randint(1, 3)):
            add_comment(p["id"], p["date"], p["author_username"])
    while len(new["comments"]) < TARGET_COMMENTS:
        p = rng.choice(new["posts"])
        add_comment(p["id"], p["date"], p["author_username"])

    # ---- reports --------------------------------------------------------
    N_REPORTS = 58
    reportable = existing_posts + [
        {"id": p["id"], "date": p["date"], "author_username": p["author_username"]}
        for p in new["posts"]]
    for _ in range(N_REPORTS):
        post = rng.choice(reportable)
        reporter = rng.choice(commenter_pool)
        while reporter["username"] == post["author_username"]:
            reporter = rng.choice(commenter_pool)
        reason = rng.choices(list(REPORT_REASONS), weights=[60, 15, 13, 12])[0]
        pd = datetime.date.fromisoformat(post["date"])
        rdate = rand_date(pd, min(pd + datetime.timedelta(days=30), TODAY))
        new["reports"].append({
            "id": next_rid,
            "post_id": post["id"],
            "reporter_username": reporter["username"],
            "reporter_display_name": reporter["display_name"],
            "reason": reason,
            "description": rng.choice(REPORT_REASONS[reason]),
            "date_reported": iso(rdate),
            "status": rng.choices(["pending", "resolved"], weights=[45, 55])[0],
        })
        next_rid += 1

    # ---- sanity fences --------------------------------------------------
    for p in new["posts"]:
        assert "2025-11-03" < p["date"] < "2026-06-18", p["date"]
        assert FORBIDDEN_TITLE not in p["title"].lower()
        assert "film" not in p["tags"] or True
        for t in json.loads(p["tags"]):
            assert "film" not in t or t == "film-photography", t

    for t in new:
        print(f"{t}: +{len(new[t])}")
    if dry:
        for t in new:
            for r in new[t][:2]:
                print(" ", json.dumps(r, default=str)[:180])
        return

    bdir = ROOT / "data" / "backups" / "blogs-expansion-2026-07-20"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "inserted_ids.json").write_text(json.dumps(
        {t: [r["id"] for r in rows] for t, rows in new.items()}, indent=1))

    for t, rows in new.items():
        if not rows:
            continue
        cols = list(rows[0].keys())
        sql = (f"INSERT INTO blogs_{t} ({', '.join(cols)}) "
               f"VALUES ({', '.join('?' * len(cols))})")
        db.executemany(sql, [[r[c] for c in cols] for r in rows])
    db.execute("INSERT INTO fts_blogs_posts(fts_blogs_posts) VALUES('rebuild')")
    db.execute("INSERT INTO fts_blogs_comments(fts_blogs_comments) VALUES('rebuild')")
    db.commit()
    print(f"inserted; rollback ids at {bdir}/inserted_ids.json")


if __name__ == "__main__":
    main()
