"""Expand calendar-todo (Meridian Calendar) base data.

The site ships with 1033 events / 5 users (1038 rows). Adds deterministic
(seeded) synthetic data to bring the site total to ~5000 rows: 10 new
Meridian Systems coworkers plus ~3960 events spread across users and dates,
reusing the site's existing vocabulary (titles, Lakeport locations,
category/calendar/color triples, attendee-email JSON arrays).

Task-safety guarantees (insert-only, saved annotation tasks unaffected):
  * NO event anywhere in 2026-05-15 .. 2026-08-05 (protects the
    "2 events between Jul 6-19 2026" count, the Jun 22-28 Natalie week,
    the Jun 21 yoga task, and the "next week book club" reschedule).
  * NO events for user 12 (Natalie Kim) and no attendee containing "natalie".
  * NO titles containing yoga / book club / architecture / calibration /
    performance review.
  * User 1 (alex, the default login) additionally gets nothing in
    2026-05-01 .. 2026-08-31 and only +190 events total so his dashboard
    stays under ~450 rendered rows.
  * New event dates stay strictly inside the existing 2025-01-01..2027-12-28
    start range (no new extremums).

Insert-only; inserted ids recorded under data/backups/ for rollback.

Usage: ~/.conda/envs/miniweb/bin/python scripts/expand_calendar_todo_data.py [--dry-run]
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

# ---------------------------------------------------------------- users ----
NEW_USERS = [
    # (username, name, password)
    ("jessica_okafor",  "Jessica Okafor",  "prodmgmt#2024"),
    ("tom_delgado",     "Tom Delgado",     "pineRd4321!"),
    ("rachel_nguyen",   "Rachel Nguyen",   "walnutPl1934"),
    ("karen_whitfield", "Karen Whitfield", "hrLead_2023!"),
    ("omar_haddad",     "Omar Haddad",     "backend0mar!"),
    ("sophie_lindqvist","Sophie Lindqvist","design_sofi24"),
    ("derek_yamamoto",  "Derek Yamamoto",  "qaDerek#77"),
    ("elena_petrova",   "Elena Petrova",   "dataElena_25"),
    ("miguel_santos",   "Miguel Santos",   "devopsMS!2024"),
    ("aisha_bello",     "Aisha Bello",     "uxAisha_2025"),
]
# reuse the unused stock SVG avatars already shipped with the site
AVATARS = ["alice_manager.svg", "bob_dev.svg", "carol_designer.svg",
           "dan_intern.svg", "eve_director.svg"]
SETTINGS = ('{"default_view": "week", "timezone": "America/Los_Angeles", '
            '"week_start": "monday"}')

# --------------------------------------------------------------- events ----
TITLES = {
    "work": [
        "Team sync", "Client call", "Design workshop", "Budget review",
        "1:1 with manager", "Sprint Planning", "Design Review",
        "Customer Demo", "Code Review Block", "Team Retrospective",
        "Incident Postmortem", "Quarterly Roadmap Review", "Bug Triage",
        "Release Planning", "Vendor Call", "Hiring Sync", "Demo Prep",
        "Docs Review", "Onboarding Session", "Data Pipeline Review",
    ],
    "personal": [
        "Dinner with friends", "Movie night", "Grocery Run", "Meal prep",
        "House Cleaning", "Call Parents", "Guitar Practice", "Weekend hike",
        "Board Game Night", "Library Visit", "Car Service", "Haircut",
        "Laundry & Errands", "Coffee Catch-up", "Volunteer Shift",
        "Date Night", "Farmers Market Run", "Plant Watering & Garden Care",
    ],
    "health": [
        "Gym session", "Dentist", "Doctor appointment", "Physiotherapy",
        "Swim Session", "Morning Run", "Pilates Class", "Eye Exam",
        "Therapy Session", "Meditation", "Cycling", "Annual Flu Shot",
    ],
}
# titles that must never be generated (protected by annotation tasks)
BANNED_WORDS = ("yoga", "book club", "architecture", "calibration",
                "performance review", "natalie")

LOCATIONS = {
    "work": [
        "Virtual - Zoom", "Conference Room A - Lakeport HQ",
        "Conference Room B - Lakeport HQ", "Virtual - Slack Huddle",
        "Auditorium - Lakeport HQ", "Board Room - Lakeport HQ",
        "Alex's Desk - Lakeport HQ", "Virtual - Discord",
    ],
    "personal": [
        "Home", "Lakeport Public Library - Meeting Room",
        "Lakeport Waterfront", "Brewed Awakening Coffee",
        "Lakeport Farmers Market - Town Square", "Summit Trail Brewing",
        "Harborview Bistro", "Happy Lemon - Downtown Lakeport",
        "Tiger Mountain Trailhead", "Lakeport Community Center",
    ],
    "health": [
        "Brooks Fitness", "Lakeport Family Dentistry",
        "Lakeport Medical Center - Primary Care",
        "Lakeport Medical Center - PT Wing",
        "Vertical World Lakeport", "Home",
    ],
}
# health appointments happen at type-appropriate places
HEALTH_LOC = {
    "Gym session": ["Brooks Fitness"],
    "Dentist": ["Lakeport Family Dentistry"],
    "Doctor appointment": ["Lakeport Medical Center - Primary Care"],
    "Physiotherapy": ["Lakeport Medical Center - PT Wing"],
    "Swim Session": ["Lakeport Community Center"],
    "Morning Run": ["Lakeport Waterfront", "Tiger Mountain Trailhead"],
    "Pilates Class": ["Brooks Fitness"],
    "Eye Exam": ["Lakeport Medical Center - Primary Care"],
    "Therapy Session": ["Lakeport Medical Center - Primary Care"],
    "Meditation": ["Home"],
    "Cycling": ["Lakeport Waterfront", "Tiger Mountain Trailhead"],
    "Annual Flu Shot": ["Lakeport Medical Center - Primary Care"],
}
DESCS = {
    "work": [
        "Recurring working session with the MeridianFlow team.",
        "Review agenda in the shared doc before the meeting.",
        "Bring open questions; notes go in the team wiki afterwards.",
        "Cross-team session; dial-in details in the invite.",
        "Prep slides the day before and share with attendees.",
    ],
    "personal": [
        "Casual plans - no prep needed.",
        "Remember to confirm the time the day before.",
        "Standing plan; reschedule if anything comes up.",
        "Pick up supplies on the way.",
        "",
    ],
    "health": [
        "Bring insurance card and arrive 10 minutes early.",
        "Standing appointment; confirm 24h ahead.",
        "Pack gym bag the night before.",
        "Routine visit; reschedule online if needed.",
        "",
    ],
}
CAT_META = {  # category -> (calendar, color)
    "work": ("Work", "#4285f4"),
    "personal": ("Personal", "#0b8043"),
    "health": ("Health", "#d50000"),
}
REMINDERS = [5, 10, 15, 15, 30, 30, 60, 120, 720, 1440]
HOURS = {"work": list(range(8, 18)), "personal": list(range(7, 22)),
         "health": list(range(6, 20))}

# global window no new event may touch (task-protected mid-2026 period)
EXCL_LO = datetime.date(2026, 5, 15)
EXCL_HI = datetime.date(2026, 8, 5)
# extra-wide exclusion for the default/main user (id 1)
ALEX_EXCL_LO = datetime.date(2026, 5, 1)
ALEX_EXCL_HI = datetime.date(2026, 8, 31)

SPAN_LO = datetime.date(2025, 1, 15)
SPAN_HI = datetime.date(2027, 12, 15)

# events to add per user (natalie/id 12 gets ZERO — task-protected)
ALLOC = {1: 190, 2: 400, 3: 400, 16: 390}
NEW_USER_EVENTS = [265, 262, 260, 258, 258, 256, 256, 255, 255, 255]  # =2580


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def pick_date(r, user_id):
    lo, hi = (ALEX_EXCL_LO, ALEX_EXCL_HI) if user_id == 1 else (EXCL_LO, EXCL_HI)
    while True:
        d = SPAN_LO + datetime.timedelta(days=r.randint(0, (SPAN_HI - SPAN_LO).days))
        if not (lo <= d <= hi):
            return d


def main():
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.row_factory = sqlite3.Row

    next_uid = db.execute("SELECT MAX(id)+1 FROM calendar_todo_users").fetchone()[0]
    next_eid = db.execute("SELECT MAX(id)+1 FROM calendar_todo_events").fetchone()[0]

    users_new = []
    for i, (username, name, password) in enumerate(NEW_USERS):
        email = username.replace("_", ".") + "@meridiansystems.com"
        users_new.append({
            "id": next_uid + i, "root_user_id": next_uid + i,
            "username": username, "password": password, "name": name,
            "email": email, "calendars": '["Work", "Personal"]',
            "shared_calendars": "[]", "settings": SETTINGS,
            "avatar": "/sites/calendar-todo/static/images/avatars/"
                      + AVATARS[i % len(AVATARS)],
        })

    # attendee pool: real coworker emails, never natalie
    attendee_pool = [
        "alex.rivera@meridiansystems.com", "priya.sharma@meridiansystems.com",
        "marcus.chen@meridiansystems.com", "daniel.okonkwo@gmail.com",
    ] + [u["email"] for u in users_new]

    alloc = dict(ALLOC)
    for u, n in zip(users_new, NEW_USER_EVENTS):
        alloc[u["id"]] = n

    events_new = []
    for user_id, n in alloc.items():
        for _ in range(n):
            cat = rng.choices(["work", "personal", "health"],
                              weights=[38, 38, 24])[0]
            title = rng.choice(TITLES[cat])
            assert not any(b in title.lower() for b in BANNED_WORDS), title
            cal, color = CAT_META[cat]
            d = pick_date(rng, user_id)
            start = datetime.datetime(d.year, d.month, d.day,
                                      rng.choice(HOURS[cat]),
                                      rng.choice([0, 15, 30, 45]))
            end_ = ""
            if rng.random() < 0.30:
                end_ = iso(start + datetime.timedelta(
                    minutes=rng.choice([30, 45, 60, 60, 90, 120])))
            attendees = []
            if cat == "work" and rng.random() < 0.15:
                pool = [a for a in attendee_pool if a != ""]
                attendees = rng.sample(pool, rng.randint(1, 3))
            status = rng.choices(["confirmed", "completed", "cancelled"],
                                 weights=[97, 2, 1])[0]
            if status == "completed" and d >= datetime.date(2026, 7, 20):
                status = "confirmed"
            created = start - datetime.timedelta(days=rng.randint(5, 60),
                                                 hours=rng.randint(0, 9))
            events_new.append({
                "id": next_eid, "user_id": user_id, "title": title,
                "description": rng.choice(DESCS[cat]), "category": cat,
                "calendar": cal, "start": iso(start), "end_": end_,
                "all_day": 0,
                "location": rng.choice(HEALTH_LOC[title] if cat == "health"
                                       else LOCATIONS[cat]),
                "recurring": rng.choices(["", "weekly", "monthly"],
                                         weights=[97, 2, 1])[0],
                "reminder_minutes": rng.choice(REMINDERS),
                "priority": rng.choices(["high", "medium", "low"],
                                        weights=[25, 45, 30])[0],
                "status": status,
                "attendees": json.dumps(attendees), "color": color,
                "created_at": iso(created),
            })
            next_eid += 1

    # safety re-checks before touching the DB
    for e in events_new:
        d = datetime.date.fromisoformat(e["start"][:10])
        assert not (EXCL_LO <= d <= EXCL_HI), e
        assert e["user_id"] != 12
        assert "natalie" not in e["attendees"].lower()
        assert SPAN_LO <= d <= SPAN_HI
        if e["user_id"] == 1:
            assert not (ALEX_EXCL_LO <= d <= ALEX_EXCL_HI), e

    print(f"users: +{len(users_new)}, events: +{len(events_new)}")
    if dry:
        for e in events_new[:6]:
            print(" ", e["user_id"], e["category"], e["start"], "|",
                  e["title"], "|", e["location"])
        by_year = {}
        for e in events_new:
            by_year[e["start"][:4]] = by_year.get(e["start"][:4], 0) + 1
        print("  year spread:", by_year)
        return

    bdir = ROOT / "data" / "backups" / "calendar-todo-expansion-2026-07-20"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "inserted_ids.json").write_text(json.dumps({
        "users": [u["id"] for u in users_new],
        "events": [e["id"] for e in events_new]}, indent=1))

    for table, rows in (("users", users_new), ("events", events_new)):
        cols = list(rows[0].keys())
        db.executemany(
            f"INSERT INTO calendar_todo_{table} ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' * len(cols))})",
            [[r[c] for c in cols] for r in rows])
    # keep the FTS index in sync (index of calendar_todo_events)
    db.execute("INSERT INTO fts_calendar_todo_events(fts_calendar_todo_events) "
               "VALUES('rebuild')")
    db.commit()
    print(f"inserted; rollback ids at {bdir}/inserted_ids.json")


if __name__ == "__main__":
    main()
