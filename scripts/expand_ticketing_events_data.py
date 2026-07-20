"""Expand ticketing-events (Lakeport Events) base data.

The site ships with only 19 events, 17 orders, 25 tickets, and 8 users.
This adds deterministic (seeded) synthetic rows:

  * ~240 new users (ids 9+), Lakeport/Meridian vocabulary, root_user_id = id+100
    (same convention the register route uses).
  * ~280 new events (ids 20+) spread over 2024-03 .. 2026-12. The bulk are
    past ("completed") so the default upcoming/on-sale views stay small.
    Categories reuse the existing enum; Sports gets only a light, past-dated
    share so the recorded "Show me all sports events" view stays recognizable.
  * ~1800 new orders (ORD-018+) and their tickets (TKT-026+), attached to
    users other than the main user (id 1). Order/ticket ids continue the
    existing zero-padded formats so runtime id generation keeps working.

Task-safety:
  * Event 15 "Cascadia Lake Festival 2026" is untouched, its name is never
    duplicated, and no new orders reference it (checkout task).
  * User 1 (alex_rivera) gets no new orders/tickets (my-tickets task view).
  * No promo-code data is touched (promo codes are code-level).

Insert-only — existing rows are never modified. Inserted ids are recorded in
data/backups/ticketing-events-expansion-2026-07-20/inserted_ids.json.

Usage: python scripts/expand_ticketing_events_data.py [--dry-run]
"""
import bisect
import datetime
import json
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "trimmed_miniweb.db"
BACKUP_DIR = ROOT / "data" / "backups" / "ticketing-events-expansion-2026-07-20"

rng = random.Random(20260720)

TODAY = datetime.date(2026, 7, 20)

FIRST_NAMES = [
    "Olivia", "Liam", "Emma", "Noah", "Ava", "Ethan", "Sofia", "Mason",
    "Isabella", "Logan", "Charlotte", "Lucas", "Amelia", "Jackson", "Harper",
    "Aiden", "Evelyn", "Carter", "Abigail", "Owen", "Emily", "Wyatt", "Ella",
    "Julian", "Scarlett", "Levi", "Grace", "Isaac", "Chloe", "Gabriel",
    "Priya", "Diego", "Naomi", "Ravi", "Camila", "Andre", "Lena", "Marco",
    "Yuki", "Omar", "Ines", "Felix", "Tara", "Victor", "Rosa", "Hugo",
    "Amara", "Jonas", "Leila", "Kai",
]
LAST_NAMES = [
    "Anderson", "Bailey", "Carlson", "Dawson", "Ellis", "Foster", "Griffin",
    "Hayes", "Ibarra", "Jensen", "Kim", "Larson", "Mendez", "Nguyen",
    "Ortiz", "Patel", "Quinn", "Reyes", "Sanders", "Tran", "Underwood",
    "Vargas", "Walsh", "Xu", "Yamamoto", "Zimmerman", "Blackwood", "Chandra",
    "Delgado", "Eriksen", "Fitzgerald", "Gustafson", "Holloway", "Iverson",
    "Jimenez", "Kowalski", "Lindqvist", "Moreau", "Novak", "Okafor",
]
EMAIL_DOMAINS = ["gmail.com", "gmail.com", "gmail.com", "outlook.com", "yahoo.com"]
CARD_BRANDS = ["Visa", "Visa", "Mastercard", "Amex"]
LOCATIONS = ["Lakeport, WA"] * 8 + ["Meridian, WA", "Tacoma, WA"]

# venue -> address (reusing existing rows' vocabulary plus a few new Lakeport spots)
VENUES = {
    "Harborside Green Amphitheater": "200 Liberty Park Rd, Lakeport, WA 98401",
    "Lakeside Commons & Marina": "6000 Harbor Dr, Lakeport, WA 98401",
    "Summit Trail Brewing": "520 Main St, Lakeport, WA 98401",
    "Lakeport Civic Hub": "450 Civic Center Dr, Lakeport, WA 98401",
    "Lakeport Public Library (classroom)": "350 Main St, Lakeport, WA 98401",
    "Downtown Lakeport (Main St corridor)": "Main St, Lakeport, WA 98401",
    "Liberty Park Basketball Courts": "200 Liberty Park Rd, Lakeport, WA 98401",
    "Meridian Systems HQ (Event Space)": "500 Innovation Way, Lakeport, WA 98401",
    "Brooks Fitness (start/finish)": "1200 Main St, Lakeport, WA 98401",
    "Lakeport Community Theater": "410 Civic Center Dr, Lakeport, WA 98401",
    "Cedar Hall Convention Center": "800 Cedar Blvd, Lakeport, WA 98401",
    "Lakeview Terrace Ballroom": "75 Lakeview Ter, Lakeport, WA 98401",
    "Pine Ridge Community Center": "2300 Pine Ridge Rd, Lakeport, WA 98401",
}

# category -> list of (series base name, venue, organizer, tags, ticket template key)
# Names get a "- {Month Year}" or "{Year}" suffix so they never collide with the
# existing event names (notably never "Cascadia Lake Festival ...").
SERIES = {
    "Music": [
        ("Lakeport Jazz Nights", "Summit Trail Brewing",
         "Summit Trail Brewing Co. & Lakeport Downtown Association",
         ["music", "jazz", "21+"], "music_small"),
        ("Harborside Acoustic Sessions", "Harborside Green Amphitheater",
         "Lakeport Parks & Recreation", ["music", "outdoor", "acoustic"], "music_mid"),
        ("Meridian Chamber Orchestra Evening", "Lakeport Community Theater",
         "Lakeport Arts Council", ["music", "classical", "indoor"], "music_theater"),
        ("Open Mic Showcase", "Summit Trail Brewing",
         "Summit Trail Brewing Co. & Lakeport Downtown Association",
         ["music", "open-mic", "local"], "music_small"),
        ("Bluegrass on the Green", "Harborside Green Amphitheater",
         "Lakeport Parks & Recreation", ["music", "outdoor", "bluegrass"], "music_mid"),
        ("Lakeport Songwriter Circle", "Lakeport Public Library (classroom)",
         "Lakeport Arts Council", ["music", "songwriting", "community"], "music_small"),
        ("Sunset Strings Quartet", "Lakeview Terrace Ballroom",
         "Lakeport Arts Council", ["music", "classical", "sunset"], "music_theater"),
        ("Lakefront Brass Band Night", "Harborside Green Amphitheater",
         "Lakeport Parks & Recreation", ["music", "outdoor", "brass"], "music_mid"),
    ],
    "Arts & Culture": [
        ("Lakeport Gallery Night", "Downtown Lakeport (Main St corridor)",
         "Lakeport Arts Council", ["art", "walking-tour", "free-form"], "arts"),
        ("Community Theater Showcase", "Lakeport Community Theater",
         "Lakeport Arts Council", ["theater", "performance", "family-friendly"], "music_theater"),
        ("Poetry & Prose Reading", "Lakeport Public Library (classroom)",
         "Lakeport Arts Council", ["literature", "reading", "community"], "arts"),
        ("Lakeport Film Society Screening", "Lakeport Community Theater",
         "Lakeport Arts Council", ["film", "screening", "discussion"], "arts"),
        ("Craft & Makers Market", "Lakeside Commons & Marina",
         "Lakeport Chamber of Commerce", ["crafts", "market", "outdoor"], "arts"),
    ],
    "Workshop": [
        ("Watercolor Basics Workshop", "Lakeport Public Library (classroom)",
         "Lakeport Arts Council", ["workshop", "painting", "beginner"], "workshop"),
        ("Intro to Pottery Wheel", "Pine Ridge Community Center",
         "Lakeport Arts Council", ["workshop", "pottery", "hands-on"], "workshop"),
        ("Sourdough Bread Making", "Pine Ridge Community Center",
         "Lakeport Chamber of Commerce", ["workshop", "baking", "hands-on"], "workshop"),
        ("Smartphone Photography Walk", "Downtown Lakeport (Main St corridor)",
         "Lakeport Arts Council", ["workshop", "photography", "outdoor"], "workshop"),
        ("Creative Writing Intensive", "Lakeport Public Library (classroom)",
         "Lakeport Arts Council", ["workshop", "writing", "small-group"], "workshop"),
    ],
    "Technology": [
        ("Lakeport Tech Meetup", "Meridian Systems HQ (Event Space)",
         "Lakeport Tech Community / Meridian Systems", ["tech", "meetup", "networking"], "tech"),
        ("Code & Coffee Saturday", "Summit Trail Brewing",
         "Lakeport Tech Community / Meridian Systems", ["tech", "coding", "casual"], "tech"),
        ("Intro to Data Analytics", "Meridian Systems HQ (Event Space)",
         "Lakeport Tech Community / Meridian Systems", ["tech", "data", "beginner"], "tech"),
        ("Lakeport Startup Pitch Night", "Cedar Hall Convention Center",
         "Lakeport Chamber of Commerce", ["tech", "startup", "pitch"], "tech"),
    ],
    "Convention": [
        ("Lakeport Comics & Zine Fest", "Cedar Hall Convention Center",
         "Lakeport Tabletop Society", ["convention", "comics", "indoor"], "convention"),
        ("Pacific Northwest Model Rail Expo", "Cedar Hall Convention Center",
         "Lakeport Tabletop Society", ["convention", "hobby", "family-friendly"], "convention"),
        ("Lakeport Home & Garden Show", "Cedar Hall Convention Center",
         "Lakeport Chamber of Commerce", ["convention", "home", "garden"], "convention"),
    ],
    "Festival": [
        ("Lakeport Harvest Festival", "Lakeside Commons & Marina",
         "Lakeport Chamber of Commerce", ["festival", "outdoor", "family-friendly", "food"], "festival"),
        ("Winter Lights on the Lake", "Lakeside Commons & Marina",
         "Lakeport Parks & Recreation", ["festival", "outdoor", "lights", "family-friendly"], "festival"),
        ("Lakeport Food Truck Rally", "Liberty Park Basketball Courts",
         "Lakeport Chamber of Commerce", ["festival", "food-trucks", "outdoor"], "festival"),
        ("Spring Blossom Fair", "Downtown Lakeport (Main St corridor)",
         "Lakeport Downtown Association", ["festival", "spring", "market"], "festival"),
    ],
    "Sports": [
        ("Lakeport Fun Run 5K", "Brooks Fitness (start/finish)",
         "Brooks Fitness / Nathan Brooks", ["sports", "running", "5k"], "sports"),
        ("Liberty Park Volleyball Open", "Liberty Park Basketball Courts",
         "Lakeport Parks & Recreation", ["sports", "volleyball", "tournament"], "sports"),
        ("Lakeport Kayak Sprint Series", "Lakeside Commons & Marina",
         "Lakeport Parks & Recreation", ["sports", "kayak", "water-sports"], "sports"),
    ],
}

# How many NEW events per category (Sports intentionally light and past-only).
CATEGORY_QUOTA = {
    "Music": 82, "Arts & Culture": 46, "Workshop": 38, "Technology": 34,
    "Convention": 22, "Festival": 44, "Sports": 14,
}

# ticket template key -> list of (type, price range, available range)
TICKET_TEMPLATES = {
    "music_small": [("General Admission", (8, 18), (80, 150))],
    "music_mid": [("General Admission", (12, 28), (300, 600)),
                  ("VIP", (40, 65), (30, 60))],
    "music_theater": [("General Admission", (18, 38), (150, 300)),
                      ("Balcony", (12, 22), (60, 120))],
    "arts": [("General Admission", (0, 15), (100, 400))],
    "workshop": [("Workshop Seat", (35, 90), (12, 30))],
    "tech": [("General Admission", (0, 25), (60, 200))],
    "convention": [("Single Day Pass", (10, 25), (400, 900)),
                   ("Weekend Pass", (25, 45), (200, 400))],
    "festival": [("Day Pass", (8, 20), (800, 2000)),
                 ("Family Pass (4)", (25, 45), (150, 300)),
                 ("VIP Experience", (60, 95), (50, 120))],
    "sports": [("Race Entry", (20, 45), (150, 400)),
               ("Spectator", (0, 10), (200, 500))],
}

TIME_SLOTS = [
    ("10:00 AM - 4:00 PM", "9:30 AM"), ("11:00 AM - 5:00 PM", "10:30 AM"),
    ("5:00 PM - 10:00 PM", "4:30 PM"), ("6:00 PM - 9:00 PM", "5:30 PM"),
    ("7:00 PM - 10:00 PM", "6:30 PM"), ("8:00 AM - 12:00 PM", "7:30 AM"),
]

MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July",
               "August", "September", "October", "November", "December"]

DESC_BITS = [
    "A beloved Lakeport gathering with local vendors and community spirit.",
    "Presented in partnership with downtown Lakeport businesses.",
    "Rain or shine. Food and drink available on site.",
    "Limited capacity -- early arrival recommended.",
    "Proceeds support Lakeport community programs.",
    "Free parking available at the Civic Center garage.",
    "All skill levels welcome. Bring a friend.",
    "Featuring rotating local artists and performers.",
]


def slugify(name):
    return "".join(c if c.isalnum() or c == "-" else "-" for c in name.lower().replace(" ", "-")).strip("-")[:48]


def initials(name):
    letters = [w[0] for w in name.replace("-", " ").split() if w[0].isalpha()]
    return "".join(letters[:3]).upper() or "LPE"


def iso_dt(day, hour, minute):
    return f"{day.isoformat()}T{hour:02d}:{minute:02d}:00Z"


def rand_price(rng_, lo, hi):
    if lo <= 0 and rng_.random() < 0.5:
        return 0.0
    return float(rng_.choice([x for x in range(max(1, int(lo)), int(hi) + 1)]))


def main():
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.row_factory = sqlite3.Row

    existing_users = [dict(r) for r in db.execute(
        "SELECT * FROM ticketing_events_users ORDER BY id")]
    existing_events = [dict(r) for r in db.execute(
        "SELECT * FROM ticketing_events_events ORDER BY id")]
    existing_names = {e["name"] for e in existing_events}
    existing_usernames = {u["username"] for u in existing_users}

    max_event_id = max(e["id"] for e in existing_events)
    max_user_id = max(u["id"] for u in existing_users)
    max_ord = db.execute(
        "SELECT MAX(CAST(SUBSTR(id, 5) AS INTEGER)) FROM ticketing_events_orders").fetchone()[0]
    max_tkt = db.execute(
        "SELECT MAX(CAST(SUBSTR(id, 5) AS INTEGER)) FROM ticketing_events_tickets").fetchone()[0]

    new_users, new_events, new_orders, new_tickets = [], [], [], []

    # ---- users ----------------------------------------------------------
    uid = max_user_id
    for _ in range(240):
        uid += 1
        while True:
            first = rng.choice(FIRST_NAMES)
            last = rng.choice(LAST_NAMES)
            username = f"{first.lower()}_{last.lower()}"
            if username not in existing_usernames:
                break
        existing_usernames.add(username)
        joined = datetime.date(2024, 1, 5) + datetime.timedelta(
            days=rng.randint(0, 715))  # 2024-01-05 .. 2025-12-20
        brand = rng.choice(CARD_BRANDS)
        new_users.append({
            "id": uid,
            "root_user_id": uid + 100,
            "username": username,
            "display_name": f"{first} {last}",
            "email": f"{first.lower()}.{last.lower()}{rng.choice(['', '', str(rng.randint(1, 99))])}@{rng.choice(EMAIL_DOMAINS)}",
            "phone": f"(555) {rng.randint(200, 899)}-{rng.randint(1000, 9999)}",
            "joined_date": joined.isoformat(),
            "location": rng.choice(LOCATIONS),
            "payment_methods": json.dumps([{
                "type": "credit_card",
                "last_four": f"{rng.randint(1000, 9999)}",
                "brand": brand,
                "is_default": True,
            }]),
            "notification_preferences": json.dumps({
                "email": True,
                "sms": rng.random() < 0.4,
                "push": rng.random() < 0.5,
            }),
        })

    # buyer pool: all users except main user (id 1), sorted by joined date
    buyers = [u for u in existing_users if u["id"] != 1] + new_users
    buyers.sort(key=lambda u: u["joined_date"])
    joined_keys = [u["joined_date"] for u in buyers]

    def pick_buyer(order_date):
        """Pick a buyer who had already joined by order_date."""
        hi = bisect.bisect_right(joined_keys, order_date.isoformat())
        if hi == 0:
            hi = 1
        return buyers[rng.randrange(hi)]

    # ---- events ---------------------------------------------------------
    eid = max_event_id
    event_plan = []  # (event dict, template key, capacity per type) — sold filled later
    for category, quota in CATEGORY_QUOTA.items():
        series_pool = SERIES[category]
        made = 0
        attempt = 0
        while made < quota and attempt < quota * 30:
            attempt += 1
            base, venue, organizer, tags, tmpl_key = rng.choice(series_pool)
            if category == "Sports":
                # Sports stays past-only so the recorded sports view keeps its
                # existing on-sale events recognizable.
                day = datetime.date(2024, 3, 1) + datetime.timedelta(days=rng.randint(0, 830))
            else:
                day = datetime.date(2024, 3, 1) + datetime.timedelta(days=rng.randint(0, 995))
            if day > datetime.date(2026, 12, 20):
                continue
            if tmpl_key in ("festival", "convention"):
                name = f"{base} {day.year}"
                if day.month <= 6 and rng.random() < 0.5:
                    name = f"{base} - Spring {day.year}"
            else:
                name = f"{base} - {MONTH_NAMES[day.month - 1]} {day.year}"
            if name in existing_names:
                continue
            existing_names.add(name)
            eid += 1
            time_str, doors = rng.choice(TIME_SLOTS)
            is_past = day <= TODAY
            desc = (f"{base} at {venue.split('(')[0].strip()}. "
                    f"{rng.choice(DESC_BITS)} {rng.choice(DESC_BITS)}")
            age = "All Ages"
            if "21+" in tags:
                age = "21+"
            elif category == "Technology" and rng.random() < 0.3:
                age = "16+"
            ttypes = []
            for tname, price_r, avail_r in TICKET_TEMPLATES[tmpl_key]:
                ttypes.append({
                    "type": tname,
                    "price": rand_price(rng, *price_r),
                    "available": rng.randrange(avail_r[0], avail_r[1] + 1, 10) or avail_r[0],
                    "sold": 0,  # finalized after order generation
                })
            ev = {
                "id": eid,
                "name": name,
                "description": desc,
                "category": category,
                "venue": venue,
                "address": VENUES[venue],
                "date": day.isoformat(),
                "time": time_str,
                "doors_open": doors,
                "organizer": organizer,
                "ticket_types": ttypes,  # serialized at insert time
                "age_restriction": age,
                "status": "completed" if is_past else "on_sale",
                "image_url": f"/events/{slugify(name)}.jpg",
                "tags": json.dumps(tags),
            }
            event_plan.append(ev)
            made += 1

    # ---- orders + tickets ----------------------------------------------
    ord_num = max_ord   # continue ORD- numbering (existing max 17)
    tkt_num = max_tkt   # continue TKT- numbering (existing max 25)
    sold_actual = {}    # event id -> {ticket type: qty sold via our orders}

    def add_order(ev, ttypes_list):
        nonlocal ord_num, tkt_num
        ev_date = datetime.date.fromisoformat(ev["date"])
        is_past = ev_date <= TODAY
        if is_past:
            order_day = ev_date - datetime.timedelta(days=rng.randint(1, 75))
        else:
            start = max(datetime.date(2026, 1, 10), TODAY - datetime.timedelta(days=170))
            order_day = start + datetime.timedelta(
                days=rng.randint(0, max(1, (TODAY - start).days)))
        buyer = pick_buyer(order_day)
        joined = datetime.date.fromisoformat(buyer["joined_date"])
        if order_day <= joined:
            order_day = min(joined + datetime.timedelta(days=rng.randint(1, 10)),
                            ev_date - datetime.timedelta(days=1) if is_past else TODAY)
        tt = rng.choice(ttypes_list)
        qty = rng.choices([1, 2, 3, 4], weights=[35, 40, 15, 10])[0]
        price = tt["price"]
        subtotal = round(price * qty, 2)
        fees = round(subtotal * 0.12, 2) if subtotal > 0 else 0.0
        total = round(subtotal + fees, 2)
        pm = json.loads(buyer["payment_methods"]) if isinstance(
            buyer["payment_methods"], str) else buyer["payment_methods"]
        pm0 = pm[0] if pm else {"type": "credit_card", "last_four": "0000", "brand": "Visa"}
        ordered_at = iso_dt(order_day, rng.randint(8, 21), rng.choice([0, 5, 15, 30, 45]))

        ord_num += 1
        order_id = f"ORD-{ord_num:03d}"
        prefix = initials(ev["name"])
        datecode = ev["date"].replace("-", "")
        tids = []
        for _ in range(qty):
            tkt_num += 1
            tid = f"TKT-{tkt_num:03d}"
            tids.append(tid)
            if is_past:
                used = rng.random() < 0.85
                status = "used" if used else "active"
                checked = iso_dt(ev_date, rng.randint(8, 20), rng.choice([5, 10, 20, 40, 55])) if used else ""
            else:
                status = "active"
                checked = ""
            attendee = ""
            if rng.random() < 0.18:
                attendee = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
            new_tickets.append({
                "id": tid,
                "order_id": order_id,
                "event_id": ev["id"],
                "user_id": buyer["id"],
                "ticket_type": tt["type"],
                "price": price,
                "status": status,
                "barcode": f"{prefix}{datecode}{tkt_num:05d}",
                "seat": "",
                "purchased_at": ordered_at,
                "checked_in_at": checked,
                "attendee_name": attendee,
            })
        new_orders.append({
            "id": order_id,
            "user_id": buyer["id"],
            "event_id": ev["id"],
            "event_name": ev["name"],
            "tickets": json.dumps(tids),
            "quantity": qty,
            "subtotal": subtotal,
            "fees": fees,
            "total": total,
            "payment_method": json.dumps({
                "type": pm0["type"], "last_four": pm0["last_four"], "brand": pm0["brand"]}),
            "status": "completed" if is_past else "confirmed",
            "ordered_at": ordered_at,
            "confirmation_email_sent": 1,
            "refund_amount": 0,
        })
        sold_actual.setdefault(ev["id"], {})
        sold_actual[ev["id"]][tt["type"]] = sold_actual[ev["id"]].get(tt["type"], 0) + qty

    # a) orders against EXISTING events (never event 15 — checkout task target)
    for ev in existing_events:
        if ev["id"] == 15:
            continue
        ttypes = json.loads(ev["ticket_types"])
        for _ in range(rng.randint(4, 9)):
            add_order(ev, ttypes)

    # b) orders against NEW events
    for ev in event_plan:
        n = rng.choices([rng.randint(2, 4), rng.randint(5, 8), rng.randint(9, 14)],
                        weights=[35, 45, 20])[0]
        for _ in range(n):
            add_order(ev, ev["ticket_types"])

    # finalize sold counts on new events: our orders + baseline off-ledger sales
    for ev in event_plan:
        is_past = datetime.date.fromisoformat(ev["date"]) <= TODAY
        for tt in ev["ticket_types"]:
            actual = sold_actual.get(ev["id"], {}).get(tt["type"], 0)
            frac = rng.uniform(0.35, 0.9) if is_past else rng.uniform(0.1, 0.5)
            baseline = int(tt["available"] * frac)
            tt["sold"] = min(tt["available"], max(actual, baseline + actual))
        ev["ticket_types"] = json.dumps(ev["ticket_types"])
        new_events.append(ev)

    # ---- report / insert -------------------------------------------------
    print(f"users:   +{len(new_users)}")
    print(f"events:  +{len(new_events)} "
          f"(on_sale {sum(1 for e in new_events if e['status'] == 'on_sale')}, "
          f"sports {sum(1 for e in new_events if e['category'] == 'Sports')})")
    print(f"orders:  +{len(new_orders)}")
    print(f"tickets: +{len(new_tickets)}")
    total_new = len(new_users) + len(new_events) + len(new_orders) + len(new_tickets)
    print(f"total new rows: {total_new}  (existing 69 -> {69 + total_new})")

    if dry:
        for label, rows in (("user", new_users), ("event", new_events),
                            ("order", new_orders), ("ticket", new_tickets)):
            for r in rows[:2]:
                print(f"  sample {label}:", json.dumps(r, default=str)[:220])
        return

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    (BACKUP_DIR / "inserted_ids.json").write_text(json.dumps({
        "users": [u["id"] for u in new_users],
        "events": [e["id"] for e in new_events],
        "orders": [o["id"] for o in new_orders],
        "tickets": [t["id"] for t in new_tickets],
    }, indent=1))

    for table, rows in (("users", new_users), ("events", new_events),
                        ("orders", new_orders), ("tickets", new_tickets)):
        cols = list(rows[0].keys())
        sql = (f"INSERT INTO ticketing_events_{table} ({', '.join(cols)}) "
               f"VALUES ({', '.join('?' * len(cols))})")
        db.executemany(sql, [[r[c] for c in cols] for r in rows])

    # keep FTS indexes in sync (external-content tables -> rebuild)
    for table in ("events", "orders", "tickets"):
        fts = f"fts_ticketing_events_{table}"
        exists = db.execute(
            "SELECT name FROM sqlite_master WHERE name = ?", (fts,)).fetchone()
        if exists:
            db.execute(f"INSERT INTO {fts}({fts}) VALUES('rebuild')")
            print(f"rebuilt {fts}")
    db.commit()
    print(f"inserted; rollback ids at {BACKUP_DIR}/inserted_ids.json")


if __name__ == "__main__":
    main()
