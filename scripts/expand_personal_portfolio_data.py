"""Expand personal-portfolio base data (projects, blog links, subscriptions).

Alex Rivera's portfolio ships with only 16 rows total (7 projects, 5 blog
links, 1 subscription, plus singleton profile/resume/user rows). A personal
portfolio cannot realistically carry thousands of rows, so this scales each
collection to its plausible ceiling (~60 rows total): a dozen more side
projects, a fuller blog-link archive, and a small newsletter subscriber list.

Task-safety constraints honored (data/annotations/Minh/personal-portfolio_ddc978,
expected answer "FlowNet" after sorting projects A->Z on the homepage):
  * Every new project title starts with a letter in G..Z, so "FlowNet" still
    sorts first alphabetically.
  * Every new project is featured=0 — the homepage sort dropdown only sorts
    *featured* projects, so the recorded page is byte-for-byte unaffected.
  * No new project mentions machine learning / ML vocabulary, so the semantic
    search ("most relevant to an ML engineer role") still ranks FlowNet first.
  * Profile, resume, and users singletons are untouched. Insert-only.

Inserted ids are recorded in
data/backups/personal-portfolio-expansion-2026-07-20/inserted_ids.json.

Usage: python scripts/expand_personal_portfolio_data.py [--dry-run]
"""
import json
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "trimmed_miniweb.db"
BACKUP_DIR = ROOT / "data" / "backups" / "personal-portfolio-expansion-2026-07-20"

rng = random.Random(4207)

# ---------------------------------------------------------------------------
# New projects — titles deliberately start with G..Z (sort AFTER "FlowNet"),
# featured=0, and none touch ML vocabulary.
# ---------------------------------------------------------------------------
PROJECTS = [
    ("GearCheck", "Pack lists and base-weight tracking for multi-day hikes",
     "A packing checklist app for backpacking trips. Tracks gear weight per item, "
     "computes base weight vs. consumables, and saves reusable pack templates for "
     "different seasons. Built after one too many trips where I forgot my stove fuel.",
     "side_project", "active", ["React", "TypeScript", "IndexedDB", "PWA"],
     "2023-04-12", "2026-02-08", []),
    ("HexPress", "A tiny static blog engine with zero configuration",
     "A minimal static site generator for personal blogs. One binary, one folder of "
     "Markdown files, no config file required. Powers a few friends' blogs and taught "
     "me a lot about template compilation and incremental builds.",
     "open_source", "active", ["Rust", "Markdown", "GitHub Pages"],
     "2022-11-05", "2026-01-19", []),
    ("InkLog", "A film photography shot logbook for the darkroom crowd",
     "A pocket logbook app for film photographers: record camera, lens, film stock, "
     "aperture, and shutter speed per frame, then match notes to scans after "
     "development. Syncs with the LightBox gallery workflow.",
     "side_project", "active", ["Svelte", "TypeScript", "SQLite"],
     "2024-06-18", "2026-03-30", []),
    ("JarBudget", "Envelope-style budgeting without the spreadsheets",
     "A small budgeting web app using the classic envelope (jar) method. Monthly "
     "rollovers, shared jars for household expenses, and CSV import from bank "
     "statements. Built for my own finances; a few friends use it too.",
     "side_project", "paused", ["Python", "Flask", "SQLite", "HTMX"],
     "2021-02-14", "2023-08-09", []),
    ("KneadTimer", "Sourdough bake scheduling with proof-stage alarms",
     "A baking timer that understands sourdough stages: autolyse, bulk ferment, "
     "stretch-and-folds, proof, and bake. Backwards-plans the whole schedule from "
     "your target dinner time. My most-used personal app every weekend.",
     "personal", "active", ["React", "TypeScript", "PWA"],
     "2023-10-02", "2026-05-11", []),
    ("LumenGrid", "A light-metering companion for vintage film cameras",
     "A phone-based incident light meter with exposure tables for cameras that "
     "predate built-in metering. Includes reciprocity failure tables for common "
     "film stocks and a sunny-16 practice mode.",
     "side_project", "archived", ["TypeScript", "React", "PWA"],
     "2020-07-21", "2022-04-03", []),
    ("NightShelf", "A reading tracker for late-night book club sessions",
     "Tracks reading progress, meeting notes, and snack duty rotation for our "
     "neighborhood book club. Generates a printable agenda before each meeting. "
     "Co-built with Jake over two rainy weekends.",
     "side_project", "active", ["Python", "Flask", "Tailwind CSS", "SQLite"],
     "2024-11-30", "2026-04-25", [{"name": "Jake Morrison", "root_user_id": 25,
                                   "role": "co-developer"}]),
    ("PourLog", "Coffee brewing journal with grind and ratio history",
     "Logs pour-over brews: beans, grind setting, water temperature, ratio, and "
     "tasting notes, with a chart of how each variable trends over time. Started "
     "as an excuse to buy a better scale.",
     "personal", "active", ["Svelte", "TypeScript", "IndexedDB"],
     "2025-03-08", "2026-06-02", []),
    ("QuietHours", "A focus timer that mutes notifications across devices",
     "A Pomodoro-style focus timer with a twist: it flips my phone, laptop, and "
     "desktop into do-not-disturb simultaneously over a tiny sync service. Includes "
     "weekly focus reports.",
     "open_source", "active", ["Go", "SQLite", "React"],
     "2023-01-25", "2026-02-27", []),
    ("RidgeLine", "Elevation profile posters generated from GPX tracks",
     "Turns GPX tracks from past hikes into minimalist SVG elevation-profile "
     "posters suitable for printing. Shares its track parser with TrailSync. A few "
     "prints hang in my apartment.",
     "side_project", "active", ["Python", "Pillow", "CSS Grid"],
     "2024-02-10", "2025-12-14", []),
    ("SpokeCount", "Bicycle maintenance log with part wear reminders",
     "A maintenance journal for my gravel bike: chain wear checks, brake pad "
     "replacements, tubeless sealant top-ups. Sends a reminder when a part crosses "
     "its expected service interval.",
     "side_project", "paused", ["Python", "Flask", "SQLite"],
     "2022-05-19", "2024-09-22", []),
    ("WanderLedger", "Shared trip expense splitting for group hikes",
     "Splits shared costs on group trips — gas, campsites, food — with offline "
     "support for trailheads without signal. Settles everyone up with the minimum "
     "number of transfers. Built for the annual Cascadia loop trip.",
     "side_project", "archived", ["React", "TypeScript", "IndexedDB", "PWA"],
     "2021-08-03", "2023-06-17", []),
]

# ---------------------------------------------------------------------------
# New blog links — same voice/categories as the existing five, plus a few
# plausible new categories. blog_post_id continues in a range (16+) that does
# not collide with any existing blogs-site post id.
# ---------------------------------------------------------------------------
BLOG_LINKS = [
    ("Scrambling Sahale Arm Before the Snow Closes In", "Outdoors", "2025-09-14",
     "A late-season push up Sahale Arm, with notes on timing the larch color and dodging the first storms.",
     ["hiking", "pnw", "trip-report"]),
    ("My Sourdough Starter Survived a Two-Week Vacation", "Cooking", "2025-08-21",
     "Everything I learned about putting a starter into cold storage without killing it.",
     ["baking", "sourdough", "recipes"]),
    ("Azul, Cascadia, and the Art of the Tile-Laying Game", "Gaming", "2025-07-30",
     "Why tile-laying games keep hitting the table at our game nights long after the novelty wears off.",
     ["board-games", "tabletop", "review"]),
    ("Shooting Portra 400 at Golden Hour: A Field Guide", "Photography", "2025-06-25",
     "Metering tips and sample frames from a summer of shooting Portra around Lakeport.",
     ["film", "photography", "tutorial"]),
    ("The Case for Boring Technology in Side Projects", "Technology", "2025-05-12",
     "Why my side projects keep shipping faster since I standardized on a small, boring stack.",
     ["coding", "side-project", "opinion"]),
    ("A Weekend on the Olympic Coast: Tide Tables and Camp Spots", "Outdoors", "2025-04-19",
     "Planning notes for the Ozette Triangle, including the tide windows that actually matter.",
     ["hiking", "camping", "pnw"]),
    ("Building QuietHours: Syncing Do-Not-Disturb Across Devices", "Technology", "2025-03-27",
     "The surprisingly gnarly parts of making three operating systems go quiet at the same time.",
     ["coding", "side-project", "go"]),
    ("Wingspan European Expansion: Worth the Table Space?", "Gaming", "2025-02-15",
     "A review after 30 plays of the European expansion with our regular group.",
     ["board-games", "review", "tabletop"]),
    ("Developing Black-and-White Film in My Kitchen", "Photography", "2025-01-24",
     "My full HC-110 workflow, from changing bag fumbling to hanging negatives over the bathtub.",
     ["film", "darkroom", "tutorial"]),
    ("Meal Prep for Trail Weekends: Five Recipes That Pack Well", "Cooking", "2024-12-08",
     "Dehydrator experiments that actually taste good at 5,000 feet.",
     ["recipes", "hiking", "meal-prep"]),
    ("What I Learned Maintaining an Open Source CLI for a Year", "Technology", "2024-11-16",
     "Issue triage, breaking changes, and the kindness of strangers: a year of maintaining snip.",
     ["open-source", "rust", "coding"]),
    ("Snowshoeing Basics: My First Winter on the Trails", "Outdoors", "2024-10-27",
     "Gear, avalanche awareness resources, and beginner-friendly routes near Lakeport.",
     ["hiking", "winter", "pnw"]),
    ("Ranking Every Board Game Cafe in the Lakeport Area", "Gaming", "2024-09-05",
     "Six cafes, one summer, too many house rules. Here's where to actually play.",
     ["board-games", "lakeport", "local"]),
    ("A Beginner's Guide to Scanning Film at Home", "Photography", "2024-08-14",
     "Comparing a flatbed scanner against camera scanning for 35mm negatives.",
     ["film", "photography", "tutorial"]),
    ("How I Organize a Hundred Half-Finished Project Ideas", "Technology", "2024-07-22",
     "My plain-text system for capturing project ideas without feeling guilty about them.",
     ["productivity", "side-project", "coding"]),
    ("Backpacking the Enchantments: Lottery Tips and a Plan B", "Outdoors", "2024-06-09",
     "What to do when you (inevitably) lose the core-zone lottery.",
     ["hiking", "pnw", "trip-report"]),
    ("My Favorite One-Pot Meals for Small Apartments", "Cooking", "2024-05-18",
     "Five weeknight staples that survive my two-burner stove.",
     ["recipes", "cooking", "apartment"]),
    ("Why I Still Print My Photos in 2024", "Photography", "2024-04-02",
     "On shoeboxes, shuffling prints, and why screens flatten everything.",
     ["photography", "film", "opinion"]),
    ("Hosting Game Night for Eight Without Losing Your Mind", "Gaming", "2024-03-11",
     "Logistics, snack strategy, and pickable games for bigger groups.",
     ["board-games", "hosting", "tabletop"]),
    ("A Love Letter to the Lakeport Farmers Market", "Cooking", "2024-02-24",
     "The stalls I hit every Saturday morning and what I cook with the haul.",
     ["cooking", "lakeport", "local"]),
]

# (email, name, subscribed, created)
SUBSCRIPTIONS = [
    ("jake.morrison@gmail.com", "Jake Morrison", 1, "2025-09-03T09:12:00"),
    ("priya.sharma@meridiansystems.com", "Priya Sharma", 1, "2025-09-18T14:41:00"),
    ("marcus.chen@gmail.com", "Marcus Chen", 1, "2025-10-02T20:05:00"),
    ("mia.torres@gmail.com", "Mia Torres", 1, "2025-10-27T11:33:00"),
    ("natalie.kim@meridiansystems.com", "Natalie Kim", 1, "2025-11-09T08:57:00"),
    ("elena.vasquez@gmail.com", "Elena Vasquez", 0, "2025-11-21T17:24:00"),
    ("david.petrov@meridiansystems.com", "David Petrov", 1, "2025-12-05T13:02:00"),
    ("sophie.lin@gmail.com", "Sophie Lin", 1, "2026-01-08T10:46:00"),
    ("daniel.okonkwo@gmail.com", "Daniel Okonkwo", 1, "2026-01-26T19:15:00"),
    ("aisha.patel@meridiansystems.com", "Aisha Patel", 1, "2026-02-12T09:28:00"),
    ("nathan.brooks@gmail.com", "Nathan Brooks", 0, "2026-03-04T21:39:00"),
    ("rachel.kim@gmail.com", "Rachel Kim", 1, "2026-03-29T12:08:00"),
    ("carlos.mendez@gmail.com", "Carlos Mendez", 1, "2026-04-17T16:52:00"),
    ("olivia.johansson@gmail.com", "Olivia Johansson", 1, "2026-05-23T18:20:00"),
]

FORBIDDEN_ML = ("machine", "learning", " ml ", "neural", "reinforcement")


def build_rows(db):
    new = {"projects": [], "blog_links": [], "subscriptions": []}

    next_project = db.execute(
        "SELECT COALESCE(MAX(id),0)+1 FROM personal_portfolio_projects").fetchone()[0]
    for (title, tagline, desc, ptype, status, tech, started, updated,
         collabs) in PROJECTS:
        slug = title.lower()
        # -- task-constraint guards ---------------------------------------
        assert title.lower() > "flownet", f"{title} would sort before FlowNet"
        blob = f" {title} {tagline} {desc} {' '.join(tech)} ".lower()
        assert not any(w in blob for w in FORBIDDEN_ML), \
            f"{title} contains ML vocabulary"
        new["projects"].append({
            "id": next_project, "title": title, "slug": slug,
            "tagline": tagline, "description": desc, "type": ptype,
            "status": status, "collaborators": json.dumps(collabs),
            "technologies": json.dumps(tech),
            "github_url": f"/sites/version-control/repo/alexrivera/{slug}",
            "live_url": "", "started": started, "last_updated": updated,
            "image_url": f"/images/projects/{slug}-screenshot.png",
            "featured": 0, "github_stars": 0, "downloads": 0, "paper_url": "",
        })
        next_project += 1

    next_link = db.execute(
        "SELECT COALESCE(MAX(id),0)+1 FROM personal_portfolio_blog_links").fetchone()[0]
    # blogs-site posts currently occupy ids 1..15; keep the soft reference
    # range clear of them (the column is never dereferenced by the UI).
    next_post_ref = 16
    for title, category, date, excerpt, tags in BLOG_LINKS:
        slug = "-".join("".join(c for c in w if c.isalnum())
                        for w in title.lower().split()[:5])
        new["blog_links"].append({
            "id": next_link, "blog_post_id": next_post_ref, "title": title,
            "url": f"https://blog.alexrivera.dev/{slug}",
            "category": category, "date": date, "excerpt": excerpt,
            "tags": json.dumps(tags),
            "featured": 1 if rng.random() < 0.15 else 0,
        })
        next_link += 1
        next_post_ref += 1

    next_sub = db.execute(
        "SELECT COALESCE(MAX(id),0)+1 FROM personal_portfolio_subscriptions").fetchone()[0]
    for email, name, subscribed, created in SUBSCRIPTIONS:
        new["subscriptions"].append({
            "id": next_sub, "email": email, "name": name,
            "subscribed": subscribed, "created": created,
        })
        next_sub += 1
    return new


def main():
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.row_factory = sqlite3.Row

    new = build_rows(db)
    for t, rows in new.items():
        print(f"{t}: +{len(rows)}")

    if dry:
        for t, rows in new.items():
            for r in rows[:2]:
                print(" ", json.dumps(r, default=str)[:150])
        db.close()
        return

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    (BACKUP_DIR / "inserted_ids.json").write_text(json.dumps(
        {f"personal_portfolio_{t}": [r["id"] for r in rows]
         for t, rows in new.items()}, indent=1))

    for t, rows in new.items():
        cols = list(rows[0].keys())
        sql = (f"INSERT INTO personal_portfolio_{t} ({', '.join(cols)}) "
               f"VALUES ({', '.join('?' * len(cols))})")
        db.executemany(sql, [[r[c] for c in cols] for r in rows])
    db.commit()

    # ---- post-insert task-constraint verification -----------------------
    featured = [r[0] for r in db.execute(
        "SELECT title FROM personal_portfolio_projects WHERE featured=1")]
    featured.sort(key=str.lower)
    assert featured[0] == "FlowNet", f"A->Z featured sort broken: {featured[:3]}"
    first_all = db.execute(
        "SELECT title FROM personal_portfolio_projects "
        "WHERE featured=1 ORDER BY LOWER(title) LIMIT 1").fetchone()[0]
    assert first_all == "FlowNet"
    ml_hits = db.execute(
        "SELECT COUNT(*) FROM personal_portfolio_projects WHERE id > 7 AND ("
        "LOWER(title||' '||tagline||' '||description||' '||technologies) LIKE '%machine%'"
        " OR LOWER(title||' '||tagline||' '||description||' '||technologies) LIKE '%learning%'"
        " OR LOWER(title||' '||tagline||' '||description||' '||technologies) LIKE '%neural%')"
    ).fetchone()[0]
    assert ml_hits == 0, "new project leaks ML vocabulary"
    print("constraint checks passed: FlowNet still first in A->Z featured sort; "
          "no ML vocabulary in new projects")
    print(f"inserted; rollback ids at {BACKUP_DIR}/inserted_ids.json")
    db.close()


if __name__ == "__main__":
    main()
