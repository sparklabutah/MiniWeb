"""Expand handwritten-notes-whiteboards (NoteCanvas) base data.

NoteCanvas ships with 20 notes / 8 whiteboards / 6 notebooks / 5 users
(39 rows total), which makes search, tag filters, and per-user note lists
nearly empty. Adds deterministic (seeded) synthetic users, notebooks, notes,
and whiteboards themed to the existing vocabulary (work / personal / ideas /
research / meeting notes, sticky-note whiteboards).

Design constraints honoured:
- INSERT-ONLY: no existing row is updated or deleted.
- New notes are attached ONLY to NEW notebooks so existing notebooks'
  notes_count stays accurate.
- All new note/whiteboard dates are OLDER than the oldest existing rows
  (notes >= 2026-05-10, whiteboards >= 2026-05-20), so "most recent"
  orderings for existing data are unchanged.
- No new title contains "standup" (or confusable variants): the task target
  note #16 "Daily Standup Template" stays unique and untouched.
- New notes owned by user 1 (alex) are never pinned, so alex's pinned
  section keeps exactly its two existing notes.
- drawing_data follows the existing column format: '' for most notes, or a
  valid `data:image/png;base64,...` data URL (the note editor renders it via
  <img>/drawImage). A small pool of tiny deterministic PNG scribbles is used.
- whiteboards.elements / shared_with / notes.tags stay JSON strings, matching
  existing rows.
- FTS: rebuilds fts_handwritten_notes_whiteboards_notes after insert.

Inserted ids recorded under
data/backups/handwritten-notes-whiteboards-expansion-2026-07-20/inserted_ids.json

Usage: python scripts/expand_handwritten_notes_whiteboards_data.py [--dry-run]
"""
import base64
import datetime
import json
import random
import sqlite3
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "trimmed_miniweb.db"
rng = random.Random(20260720)

NOTE_DATE_MIN = datetime.datetime(2024, 1, 2, 7, 0, 0)
NOTE_DATE_MAX = datetime.datetime(2026, 4, 30, 21, 0, 0)   # < 2026-05-10 (oldest note)
WB_DATE_MAX = datetime.datetime(2026, 5, 15, 21, 0, 0)     # < 2026-05-20 (oldest whiteboard)

ISO = "%Y-%m-%dT%H:%M:%S"

# ---------------------------------------------------------------------------
# Tiny deterministic PNG scribbles (valid data:image/png;base64 URLs)
# ---------------------------------------------------------------------------

def _png_from_rgba(width, height, pixels):
    """Encode a flat RGBA bytearray as a PNG file (bytes)."""
    raw = bytearray()
    stride = width * 4
    for y in range(height):
        raw.append(0)  # filter type 0
        raw += pixels[y * stride:(y + 1) * stride]

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))


def _draw_line(pixels, width, height, x0, y0, x1, y1, rgba, thickness=2):
    steps = max(abs(x1 - x0), abs(y1 - y0), 1)
    for i in range(steps + 1):
        x = x0 + (x1 - x0) * i / steps
        y = y0 + (y1 - y0) * i / steps
        for dx in range(-thickness, thickness + 1):
            for dy in range(-thickness, thickness + 1):
                if dx * dx + dy * dy > thickness * thickness:
                    continue
                px, py = int(x) + dx, int(y) + dy
                if 0 <= px < width and 0 <= py < height:
                    off = (py * width + px) * 4
                    pixels[off:off + 4] = rgba


def make_scribble(prng):
    """Return a small transparent PNG data URL with a few pen strokes."""
    w, h = 280, 160
    pixels = bytearray(w * h * 4)  # transparent
    palette = [(37, 37, 37, 255), (74, 144, 217, 255), (232, 116, 97, 255),
               (126, 198, 153, 255), (189, 147, 249, 255)]
    for _ in range(prng.randint(2, 4)):
        rgba = bytes(prng.choice(palette))
        x, y = prng.randint(15, w - 15), prng.randint(15, h - 15)
        for _seg in range(prng.randint(3, 6)):
            nx = min(max(x + prng.randint(-60, 60), 8), w - 8)
            ny = min(max(y + prng.randint(-35, 35), 8), h - 8)
            _draw_line(pixels, w, h, x, y, nx, ny, rgba, thickness=2)
            x, y = nx, ny
    data = _png_from_rgba(w, h, pixels)
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


# ---------------------------------------------------------------------------
# Vocabulary (mirrors existing rows; no "standup" anywhere)
# ---------------------------------------------------------------------------

FIRST_NAMES = [
    "riley", "jordan", "avery", "quinn", "rowan", "skyler", "emerson", "finley",
    "harper", "sage", "dakota", "reese", "kendall", "parker", "logan", "blake",
    "hayden", "peyton", "drew", "ellis", "marlow", "campbell", "arden", "lane",
    "remy", "shay", "tatum", "wren", "noel", "kai", "devon", "ash", "corey",
    "jules", "linden", "micah", "nico", "oakley", "phoenix", "river", "sasha",
    "toby", "vale", "winter", "zion",
]
NAME_WORDS = [
    "draws", "ink", "pages", "doodle", "jots", "scribe", "margin", "quill",
    "canvas", "marks", "lines", "paper", "pencil", "layers", "trace", "glyph",
    "sketchy", "drafts", "plans", "maps", "boards", "loops", "dots", "grid",
    "shade", "erase", "frames", "panels", "strokes", "smudge", "outline",
    "vellum", "charcoal", "pastel", "crayon", "brush", "stencil", "etch",
    "scrawl", "ledger", "folio", "memo", "post", "pad", "clip",
]

NOTEBOOK_NAMES = [
    "Work", "Personal", "Ideas", "Meeting Notes", "Research", "Quick Notes",
    "Sketches", "Travel", "Recipes", "Study", "Projects", "Journal",
    "Reading Log", "Fitness", "Finance", "Archive 2024", "Archive 2025",
    "Classes", "Side Projects", "Home", "Garden", "Music", "Photography",
    "Writing", "Interviews", "Planning", "Client Notes", "Design Refs",
]
NOTEBOOK_COLORS = ["#4A90D9", "#E87461", "#F5A623", "#7EC699", "#BD93F9", "#FF6B6B"]

NOTE_COLORS = ["#FFFACD", "#E8F5E9", "#FFF3E0", "#E3F2FD", "#F3E5F5"]

TOPICS = {
    "work": {
        "titles": [
            "Sprint {n} Planning Notes", "1:1 Notes - {name}", "Release {v} Checklist",
            "Bug Triage - {month} {day}", "Code Review Notes - {feature}",
            "Architecture Notes - {feature}", "On-call Handoff - {month} {day}",
            "Roadmap Draft - {quarter}", "Estimation Notes - {feature}",
            "Incident Writeup - {month} {day}", "Interview Debrief - {name}",
            "Weekly Priorities - {month} {day}", "Demo Prep - {feature}",
        ],
        "tags": ["work", "planning", "sprint", "meeting", "checklist", "api",
                 "deployment", "performance", "review", "roadmap"],
        "lines": [
            "Action items:\n- Follow up with the team\n- Update the ticket status\n- Schedule review for next week",
            "Key decisions:\n- Ship behind a feature flag\n- Defer the migration to next sprint",
            "Blockers: waiting on API keys from the platform team.",
            "Estimates: frontend 3d, backend 5d, QA 2d.",
            "Notes from discussion: keep the scope small, iterate weekly.",
            "TODO: write tests, update docs, ping design for final mocks.",
        ],
    },
    "personal": {
        "titles": [
            "Grocery Run - {month} {day}", "Weekend Plans - {month} {day}",
            "Gift Ideas - {name}", "Meal Prep - Week of {month} {day}",
            "Budget Notes - {month}", "Chores Rotation", "Errands - {month} {day}",
            "Packing List - {place}", "Birthday Planning - {name}",
            "Apartment Fixes", "Car Maintenance Log", "Health Notes - {month}",
        ],
        "tags": ["personal", "shopping", "travel", "packing", "home", "budget",
                 "health", "family", "errands"],
        "lines": [
            "- Milk\n- Eggs\n- Sourdough\n- Coffee beans\n- Spinach",
            "Remember to book tickets early and check the weather forecast.",
            "Budget check: groceries on track, dining out slightly over.",
            "Call the landlord about the kitchen faucet.",
            "Ideas: picnic at the lake, farmers market Saturday morning.",
            "Refill prescriptions and schedule a dentist appointment.",
        ],
    },
    "ideas": {
        "titles": [
            "App Idea - {concept}", "Blog Post Draft - {concept}",
            "Brainstorm - {concept}", "Startup Notes - {concept}",
            "Feature Sketch - {concept}", "Naming Ideas - {concept}",
            "Podcast Topics - {month}", "Newsletter Outline - {month} {day}",
            "Side Project Notes - {concept}", "Talk Proposal - {concept}",
        ],
        "tags": ["ideas", "design", "startup", "business", "writing", "brainstorm",
                 "product", "creative"],
        "lines": [
            "Rough concept: start small, validate with 10 users, iterate.",
            "What would make this 10x better than existing tools?",
            "Possible names: brainstormed a dozen, shortlisting three.",
            "Outline:\n1. Hook\n2. Problem\n3. Approach\n4. Results\n5. Takeaways",
            "Target audience: students and freelancers who take visual notes.",
            "Next step: sketch wireframes and share for feedback.",
        ],
    },
    "research": {
        "titles": [
            "Paper Notes - {paper}", "Literature Review - {paper}",
            "Experiment Log - {month} {day}", "Dataset Notes - {paper}",
            "Reading Summary - {paper}", "Methodology Notes - {paper}",
            "Survey Results - {month}", "Benchmark Notes - {paper}",
        ],
        "tags": ["research", "ml", "papers", "database", "analysis", "data",
                 "experiment", "reading"],
        "lines": [
            "Key finding: results replicate only with the larger batch size.",
            "Open questions: how does this scale beyond the benchmark set?",
            "Summary: strong baseline, weak ablations, useful appendix.",
            "Data quality issues found in 3% of samples; documented filters.",
            "Compare against last month's run before drawing conclusions.",
            "Citations to chase: three follow-up papers from the same lab.",
        ],
    },
    "study": {
        "titles": [
            "Lecture {n} - {course}", "Flashcards - {course}",
            "Problem Set {n} Notes", "Exam Prep - {course}",
            "Chapter {n} Summary - {course}", "Lab Notes - {course}",
        ],
        "tags": ["study", "class", "lecture", "exam", "notes", "homework"],
        "lines": [
            "Main theorem covered today; work through examples 3-5 again.",
            "Definitions to memorize before Friday's quiz.",
            "Professor hinted the exam focuses on chapters 4 and 6.",
            "Group session Thursday at the library, 6pm.",
            "Redo problem 7 - my first approach missed an edge case.",
        ],
    },
    "journal": {
        "titles": [
            "Morning Pages - {month} {day}", "Daily Log - {month} {day}",
            "Gratitude List - {month} {day}", "Weekly Reflection - {month} {day}",
            "Dream Journal - {month} {day}", "Habit Tracker - {month}",
        ],
        "tags": ["journal", "reflection", "gratitude", "habits", "morning"],
        "lines": [
            "Slept well, long walk before work, felt focused all morning.",
            "Three good things: sunny weather, finished the book, called mom.",
            "This week: less scrolling, more sketching. It's working.",
            "Energy dipped mid-afternoon; try an earlier lunch tomorrow.",
            "Grateful for quiet mornings and strong coffee.",
        ],
    },
    "hobby": {
        "titles": [
            "Recipe - {dish}", "Sketch Study - {subject}", "Garden Log - {month} {day}",
            "Trip Notes - {place}", "Playlist Draft - {month}", "Photo Walk - {place}",
            "Workout Log - {month} {day}", "Book Notes - {book}",
            "Practice Log - {month} {day}", "Project - {craft}",
        ],
        "tags": ["recipe", "sketch", "garden", "travel", "music", "books",
                 "fitness", "photography", "craft", "personal"],
        "lines": [
            "Ingredients:\n- 2 cloves garlic\n- Olive oil\n- Chili flakes\n- Fresh parsley",
            "Focus on proportions first, shading later.",
            "Tomatoes flowering; basil needs repotting this weekend.",
            "Best light was just after sunrise near the waterfront.",
            "Three sets felt easy - add weight next session.",
            "Favorite quote saved; chapter 6 worth rereading.",
        ],
    },
}

FEATURES = ["search indexing", "offline sync", "the export pipeline", "tag filters",
            "the sharing flow", "canvas rendering", "the mobile editor",
            "notifications", "the onboarding tour", "autosave"]
CONCEPTS = ["habit tracker for sketchers", "recipe box with photos",
            "collaborative mood boards", "voice memos to text notes",
            "flashcards from handwriting", "travel journal generator",
            "minimalist task board", "book club companion", "plant care planner",
            "local events digest"]
PAPERS = ["Attention Mechanisms Survey", "Sketch Recognition CNNs",
          "Handwriting OCR Benchmarks", "Vector Ink Compression",
          "Stroke Segmentation Methods", "Note Retrieval with BM25",
          "Latent Canvas Embeddings", "Gesture Input Studies"]
COURSES = ["Linear Algebra", "Art History", "Data Structures", "Statistics",
           "Typography", "Cognitive Psych", "Watercolor Basics", "Databases"]
DISHES = ["Miso Ramen", "Shakshuka", "Lemon Risotto", "Veggie Chili",
          "Banana Bread", "Pad See Ew", "French Onion Soup", "Falafel Wraps"]
SUBJECTS = ["hands", "oak trees", "city rooftops", "birds in flight",
            "coffee cups", "old bicycles", "harbor boats", "portrait profiles"]
PLACES = ["Lakeport", "Meridian Valley", "Cascadia Coast", "Pine Ridge",
          "Harbor District", "Old Town", "Cedar Falls", "Juniper Canyon"]
BOOKS = ["The Quiet Atlas", "Deep Work", "Ways of Seeing", "The Ink Road",
         "Thinking in Systems", "A Field Guide to Getting Lost"]
CRAFTS = ["bookbinding", "linocut prints", "ceramic mugs", "macrame hanger",
          "leather journal", "birdhouse build"]
NAMES_POOL = ["Sam", "Priya", "Diego", "Mei", "Omar", "Lena", "Kofi", "Ana",
              "Theo", "Ruth", "Ivan", "Noor"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct",
          "Nov", "Dec"]
QUARTERS = ["Q1 2024", "Q2 2024", "Q3 2024", "Q4 2024", "Q1 2025", "Q2 2025",
            "Q3 2025", "Q4 2025", "Q1 2026"]

NOTEBOOK_TOPIC = {
    "Work": "work", "Personal": "personal", "Ideas": "ideas",
    "Meeting Notes": "work", "Research": "research", "Quick Notes": "personal",
    "Sketches": "hobby", "Travel": "hobby", "Recipes": "hobby", "Study": "study",
    "Projects": "work", "Journal": "journal", "Reading Log": "hobby",
    "Fitness": "hobby", "Finance": "personal", "Archive 2024": "journal",
    "Archive 2025": "journal", "Classes": "study", "Side Projects": "ideas",
    "Home": "personal", "Garden": "hobby", "Music": "hobby",
    "Photography": "hobby", "Writing": "ideas", "Interviews": "work",
    "Planning": "work", "Client Notes": "work", "Design Refs": "ideas",
}

WB_TITLES = [
    "Retro Board - Sprint {n}", "Mind Map - {concept}", "Flowchart - {feature}",
    "Wireframe - {feature}", "Kanban Snapshot - {month} {year}",
    "Moodboard - {concept}", "Trip Map - {place}", "Seating Chart - {place} Offsite",
    "Storyboard - {concept}", "Org Chart Draft - {month} {year}",
    "Timeline - {quarter}", "Icebreaker Grid - {month} {year}",
    "Pros and Cons - {concept}", "Budget Board - {quarter}",
    "Party Planning - {name}", "User Flow - {feature}",
    "Feature Matrix - {quarter}", "Lesson Plan - {course}",
]
WB_STICKIES = [
    "Ship it Friday?", "Needs design review", "Blocked on API", "Great feedback here",
    "Move to next sprint", "Talk to Sam about this", "Cut scope", "Users love this",
    "Measure first", "Prototype by Tuesday", "Add to backlog", "Done last week",
    "Risky - needs spike", "Quick win", "Pair on this", "Waiting on legal",
]
WB_TEXTS = ["Goals", "Ideas", "Later", "Now", "Next", "Parking Lot", "Wins",
            "Risks", "Owners", "Timeline", "Notes", "Questions"]
ELEMENT_COLORS = ["#FFFACD", "#E8F5E9", "#FFF3E0", "#E3F2FD", "#F3E5F5",
                  "#4A90D9", "#E87461", "#7EC699"]


def fill(template):
    return template.format(
        n=rng.randint(1, 24),
        v=f"v{rng.randint(1, 4)}.{rng.randint(0, 9)}",
        month=rng.choice(MONTHS),
        day=rng.randint(1, 28),
        year=rng.choice([2024, 2025]),
        quarter=rng.choice(QUARTERS),
        name=rng.choice(NAMES_POOL),
        feature=rng.choice(FEATURES),
        concept=rng.choice(CONCEPTS),
        paper=rng.choice(PAPERS),
        course=rng.choice(COURSES),
        dish=rng.choice(DISHES),
        subject=rng.choice(SUBJECTS),
        place=rng.choice(PLACES),
        book=rng.choice(BOOKS),
        craft=rng.choice(CRAFTS),
    )


def rand_dt(lo, hi):
    span = int((hi - lo).total_seconds())
    return lo + datetime.timedelta(seconds=rng.randint(0, span))


def main():
    dry = "--dry-run" in sys.argv
    conn = sqlite3.connect(DB_PATH, timeout=60)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    U = "handwritten_notes_whiteboards_users"
    NB = "handwritten_notes_whiteboards_notebooks"
    N = "handwritten_notes_whiteboards_notes"
    W = "handwritten_notes_whiteboards_whiteboards"

    max_user = cur.execute(f"SELECT MAX(id) FROM {U}").fetchone()[0]
    max_nb = cur.execute(f"SELECT MAX(id) FROM {NB}").fetchone()[0]
    max_note = cur.execute(f"SELECT MAX(id) FROM {N}").fetchone()[0]
    max_wb = cur.execute(f"SELECT MAX(id) FROM {W}").fetchone()[0]
    existing_users = [r["id"] for r in cur.execute(f"SELECT id FROM {U}")]
    existing_emails = {r["email"] for r in cur.execute(f"SELECT email FROM {U}")}

    # ---- Users (45 new) --------------------------------------------------
    users = []
    words = NAME_WORDS[:]
    rng.shuffle(words)
    for i, first in enumerate(FIRST_NAMES):
        uid = max_user + 1 + i
        word = words[i % len(words)]
        email = f"{first}@example.com"
        if email in existing_emails:
            email = f"{first}.{word}@example.com"
        existing_emails.add(email)
        users.append({
            "id": uid,
            "username": f"{first}_{word}",
            "password": f"pass{uid}23",
            "display_name": f"{first.capitalize()} {word.capitalize()}",
            "email": email,
            "avatar": f"/static/generated/avatar_handwritten_notes_whiteboards_users_{uid}.jpg",
        })
    all_user_ids = existing_users + [u["id"] for u in users]

    # ---- Notebooks (new only; new notes attach ONLY to these) ------------
    notebooks = []
    nb_id = max_nb
    for uid in all_user_ids:
        count = 3 if uid == 1 else rng.randint(2, 3)
        names = rng.sample(NOTEBOOK_NAMES, count)
        for name in names:
            nb_id += 1
            notebooks.append({
                "id": nb_id,
                "name": name,
                "owner_id": uid,
                "color": rng.choice(NOTEBOOK_COLORS),
                "notes_count": 0,  # filled after note assignment
            })

    # ---- Notes -----------------------------------------------------------
    TARGET_NOTES = 4655
    scribbles = [make_scribble(rng) for _ in range(12)]
    notes = []
    note_id = max_note
    nb_cycle = []
    while len(nb_cycle) < TARGET_NOTES:
        nb_cycle.extend(notebooks)
    rng.shuffle(nb_cycle)
    for nb in nb_cycle[:TARGET_NOTES]:
        note_id += 1
        topic = TOPICS[NOTEBOOK_TOPIC[nb["name"]]]
        title = fill(rng.choice(topic["titles"]))
        created = rand_dt(NOTE_DATE_MIN, NOTE_DATE_MAX)
        updated = min(created + datetime.timedelta(
            seconds=rng.randint(0, 45 * 86400)), NOTE_DATE_MAX)
        tags = rng.sample(topic["tags"], rng.randint(1, 3))
        content_parts = rng.sample(topic["lines"], rng.randint(1, 3))
        pinned = 1 if (nb["owner_id"] != 1 and rng.random() < 0.01) else 0
        drawing = scribbles[rng.randrange(len(scribbles))] if rng.random() < 0.08 else ""
        notes.append({
            "id": note_id,
            "title": title,
            "content": "\n\n".join(content_parts),
            "owner_id": nb["owner_id"],
            "created_at": created.strftime(ISO),
            "updated_at": updated.strftime(ISO),
            "tags": json.dumps(tags),
            "notebook_id": nb["id"],
            "is_pinned": pinned,
            "color": rng.choice(NOTE_COLORS),
            "drawing_data": drawing,
        })
        nb["notes_count"] += 1

    # ---- Whiteboards (180 new) -------------------------------------------
    whiteboards = []
    wb_id = max_wb
    for _ in range(180):
        wb_id += 1
        owner = rng.choice(all_user_ids)
        created = rand_dt(NOTE_DATE_MIN, WB_DATE_MAX)
        updated = min(created + datetime.timedelta(
            seconds=rng.randint(0, 30 * 86400)), WB_DATE_MAX)
        shared = rng.sample([u for u in all_user_ids if u != owner],
                            rng.randint(0, 3))
        elements = []
        x, y = 30, 20
        for _e in range(rng.randint(3, 6)):
            etype = rng.choice(["text", "sticky", "sticky", "shape"])
            if etype == "text":
                content = rng.choice(WB_TEXTS)
                wdt, hgt = 160, 35
            elif etype == "sticky":
                content = rng.choice(WB_STICKIES)
                wdt, hgt = rng.choice([140, 160, 180]), rng.choice([60, 80])
            else:
                content = rng.choice(["rectangle", "circle"])
                wdt, hgt = rng.choice([120, 160, 200]), rng.choice([80, 120])
            elements.append({
                "type": etype, "content": content,
                "x": x, "y": y, "width": wdt, "height": hgt,
                "color": rng.choice(ELEMENT_COLORS),
            })
            x += wdt + rng.randint(20, 60)
            if x > 620:
                x = 30
                y += 140
        whiteboards.append({
            "id": wb_id,
            "title": fill(rng.choice(WB_TITLES)),
            "owner_id": owner,
            "created_at": created.strftime(ISO),
            "updated_at": updated.strftime(ISO),
            "shared_with": json.dumps(sorted(shared)),
            "elements": json.dumps(elements),
        })

    # ---- Safety: no title may collide with the task-critical note --------
    for row in notes + whiteboards:
        assert "standup" not in row["title"].lower(), row["title"]

    print(f"Prepared: users={len(users)} notebooks={len(notebooks)} "
          f"notes={len(notes)} whiteboards={len(whiteboards)} "
          f"(total new = {len(users) + len(notebooks) + len(notes) + len(whiteboards)})")

    if dry:
        print("\n-- DRY RUN, nothing written. Samples:")
        for coll, name in ((users, "user"), (notebooks, "notebook"),
                           (notes, "note"), (whiteboards, "whiteboard")):
            for s in coll[:2]:
                trimmed = {k: (v[:90] + "..." if isinstance(v, str) and len(v) > 90 else v)
                           for k, v in s.items()}
                print(f"  {name}: {trimmed}")
        conn.close()
        return

    cur.execute("BEGIN")
    cur.executemany(
        f"INSERT INTO {U} (id, username, password, display_name, email, avatar) "
        "VALUES (:id, :username, :password, :display_name, :email, :avatar)", users)
    cur.executemany(
        f"INSERT INTO {NB} (id, name, owner_id, color, notes_count) "
        "VALUES (:id, :name, :owner_id, :color, :notes_count)", notebooks)
    cur.executemany(
        f"INSERT INTO {N} (id, title, content, owner_id, created_at, updated_at, "
        "tags, notebook_id, is_pinned, color, drawing_data) "
        "VALUES (:id, :title, :content, :owner_id, :created_at, :updated_at, "
        ":tags, :notebook_id, :is_pinned, :color, :drawing_data)", notes)
    cur.executemany(
        f"INSERT INTO {W} (id, title, owner_id, created_at, updated_at, "
        "shared_with, elements) "
        "VALUES (:id, :title, :owner_id, :created_at, :updated_at, "
        ":shared_with, :elements)", whiteboards)
    # FTS sync (external-content table over notes)
    cur.execute(f"INSERT INTO fts_{N}(fts_{N}) VALUES('rebuild')")
    conn.commit()

    bdir = ROOT / "data" / "backups" / "handwritten-notes-whiteboards-expansion-2026-07-20"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "inserted_ids.json").write_text(json.dumps({
        "users": [u["id"] for u in users],
        "notebooks": [n["id"] for n in notebooks],
        "notes": [n["id"] for n in notes],
        "whiteboards": [w["id"] for w in whiteboards],
    }, indent=2))

    for tbl in (U, NB, N, W):
        print(tbl, cur.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0])
    conn.close()
    print("Done. Backup at", bdir / "inserted_ids.json")


if __name__ == "__main__":
    main()
