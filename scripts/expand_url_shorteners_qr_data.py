"""Expand url-shorteners-qr (SnapLink) base data.

SnapLink ships with only 4 users / 17 links / 30 click_stats rows, so the
links list and every analytics page look nearly empty. Adds deterministic
(seeded) synthetic users, links, and per-click analytics rows themed to the
existing vocabulary (marketing campaigns, dev docs, Meridian/Lakeport/
Cascadia businesses, personal links).

Task-safety constraints honored:
  * No new row contains the substring "(archived)" (a saved task searches for
    it and must keep returning exactly the one pre-existing match, link 10).
  * All new links for the main user (owner_id 1, alice_marketer) are dated
    strictly OLDER than her oldest existing link (2025-06-20T08:00:00) so the
    top of her My Links list (sorted newest-first) is unchanged.
  * New short codes never collide with existing ones (checked against the DB).
  * Extra click_stats rows for EXISTING links never exceed that link's stored
    `clicks` counter (tracked subset stays plausible); the bulk of the click
    volume goes to NEW links spread across many owners and dates, so no
    single link-detail/stats page aggregates an outsized row set.

Insert-only; inserted ids recorded under data/backups/ for rollback.

Usage: ~/.conda/envs/miniweb/bin/python scripts/expand_url_shorteners_qr_data.py [--dry-run]
"""
import datetime
import json
import random
import sqlite3
import string
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "trimmed_miniweb.db"
rng = random.Random(20260720)

TODAY = datetime.datetime(2026, 7, 19, 21, 0, 0)
MAIN_USER_CUTOFF = datetime.datetime(2025, 6, 19, 22, 0, 0)  # < 2025-06-20T08:00

NEW_USERS = [
    # (username, password, name, email, plan)
    ("erin_content",   "pass654", "Erin Walsh",      "erin@example.com",   "pro"),
    ("frank_sales",    "pass987", "Frank Osei",      "frank@example.com",  "free"),
    ("grace_events",   "pass135", "Grace Lindqvist", "grace@example.com",  "pro"),
    ("hiro_product",   "pass246", "Hiro Tanaka",     "hiro@example.com",   "enterprise"),
    ("ivy_nonprofit",  "pass357", "Ivy Delgado",     "ivy@example.com",    "free"),
    ("jamal_podcast",  "pass468", "Jamal Reed",      "jamal@example.com",  "pro"),
    ("kira_realty",    "pass579", "Kira Novak",      "kira@example.com",   "pro"),
    ("leo_fitness",    "pass680", "Leo Moretti",     "leo@example.com",    "free"),
    ("maya_edu",       "pass791", "Maya Krishnan",   "maya@example.com",   "enterprise"),
    ("nate_gamedev",   "pass802", "Nate Bishop",     "nate@example.com",   "free"),
    ("olga_travel",    "pass913", "Olga Petrova",    "olga@example.com",   "pro"),
    ("pete_lakeport",  "pass024", "Pete Sandoval",   "pete@example.com",   "free"),
]

# Per-owner link themes: (owner key, [(title template, url template, tag pool)])
# {n} gets a small serial number so titles stay distinct but greppable.
THEMES = {
    "marketing": (
        ["Spring Sale Teaser {n}", "Email Header CTA {n}", "Retargeting Ad {n}",
         "Landing Page Variant {n}", "Newsletter Feature {n}", "Coupon Drop {n}",
         "Product Hunt Launch {n}", "Influencer Collab {n}", "Holiday Gift Guide {n}",
         "Webinar Signup {n}", "Case Study Download {n}", "Free Trial Promo {n}"],
        ["https://store.example.com/campaigns/{slug}", "https://www.example.com/lp/{slug}",
         "https://promo.example.com/{slug}"],
        ["marketing", "promo", "sales", "email", "social", "ads", "seasonal"],
        [("instagram", "social"), ("facebook", "paid"), ("email", "newsletter"),
         ("linkedin", "social"), ("", "")],
    ),
    "dev": (
        ["Changelog v{n}", "SDK Quickstart {n}", "Status Page Mirror {n}",
         "Bug Bounty Brief {n}", "RFC Draft {n}", "Postmortem Notes {n}",
         "Release Candidate {n}", "Docker Image Notes {n}", "API Sandbox {n}"],
        ["https://docs.example.com/{slug}", "https://github.com/example/{slug}",
         "https://status.example.com/{slug}"],
        ["dev", "docs", "github", "api", "infra", "release"],
        [("team-chat", "internal"), ("", ""), ("", "")],
    ),
    "content": (
        ["Podcast Episode {n}", "YouTube Short {n}", "Blog Roundup {n}",
         "Interview Clip {n}", "Behind the Scenes {n}", "Live Stream Replay {n}",
         "Playlist Update {n}", "Fan Q&A {n}"],
        ["https://youtube.com/watch?v={slug}", "https://blog.example.com/{slug}",
         "https://podcasts.example.com/ep/{slug}"],
        ["content", "youtube", "podcast", "blog", "video", "community"],
        [("twitter", "social"), ("multimedia-posting", "social"), ("", "")],
    ),
    "agency": (
        ["Client Proposal {n}", "Monthly Report {n}", "Brand Audit {n}",
         "Media Kit {n}", "Campaign Recap {n}", "Invoice Portal {n}",
         "Kickoff Deck {n}", "Analytics Snapshot {n}"],
        ["https://agency.example.com/clients/{slug}", "https://reports.example.com/{slug}",
         "https://drive.example.com/share/{slug}"],
        ["client", "reports", "agency", "b2b", "deck"],
        [("crm", "client-share"), ("email", "newsletter"), ("", "")],
    ),
    "local": (
        ["Lakeport Farmers Market {n}", "Meridian Coffee Menu {n}",
         "Cascadia Trail Map {n}", "Harborfest Tickets {n}",
         "Lakeport Library Events {n}", "Cascadia 5K Signup {n}",
         "Meridian Art Walk {n}", "Community Fundraiser {n}"],
        ["https://lakeport.example.org/{slug}", "https://cascadia.example.org/{slug}",
         "https://meridian.example.org/{slug}"],
        ["events", "community", "local", "tickets", "nonprofit"],
        [("email", "newsletter"), ("facebook", "social"), ("", "")],
    ),
    "personal": (
        ["Reading List {n}", "Recipe Collection {n}", "Trip Photos {n}",
         "Resume PDF {n}", "Wishlist {n}", "Side Project Demo {n}",
         "Apartment Listing {n}", "Book Club Notes {n}"],
        ["https://notes.example.com/{slug}", "https://photos.example.com/album/{slug}",
         "https://www.example.com/p/{slug}"],
        ["personal", "notes", "photos", "hobby"],
        [("instant-messaging", "personal"), ("", ""), ("", "")],
    ),
}

OWNER_PLANS = {}          # filled from DB
OWNER_THEME = {2: "dev", 3: "content", 4: "agency"}
NEW_USER_THEMES = ["content", "marketing", "local", "dev", "local", "content",
                   "agency", "personal", "dev", "personal", "content", "local"]

REFERRERS = ["google.com", "twitter.com", "direct", "facebook.com",
             "instagram.com", "github.com", "reddit.com", "youtube.com",
             "email", "linkedin.com", "hacker-news.com"]
REF_WEIGHTS = [22, 12, 25, 10, 8, 5, 5, 4, 5, 3, 1]
COUNTRIES = ["US", "UK", "DE", "BR", "IN", "MX", "CA", "JP", "AU"]
CTRY_WEIGHTS = [38, 12, 9, 7, 9, 5, 10, 6, 4]
DEVICES = ["desktop", "mobile", "tablet"]
DEV_WEIGHTS = [48, 44, 8]

TARGET_NEW_LINKS = 500
TARGET_NEW_CLICKS = 4500
MAIN_USER_NEW_LINKS = 35


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def slugify(title):
    return "".join(c if c.isalnum() else "-" for c in title.lower()).strip("-")


def make_code(used):
    while True:
        code = "".join(rng.choice(string.ascii_lowercase + string.digits)
                       for _ in range(rng.choice([6, 6, 6, 7])))
        if code not in used:
            used.add(code)
            return code


def rand_dt(start, end):
    span = int((end - start).total_seconds())
    return start + datetime.timedelta(seconds=rng.randint(0, max(span, 1)))


def build_link(link_id, owner_id, theme_key, created, used_codes, serial):
    titles, urls, tags, utms = THEMES[theme_key]
    title = rng.choice(titles).format(n=serial)
    assert "(archived)" not in title.lower()
    url = rng.choice(urls).format(slug=slugify(title))
    utm_source, utm_medium = rng.choice(utms)
    utm_campaign = slugify(title.rsplit(" ", 1)[0])[:24] if utm_source else ""
    active = 1 if rng.random() < 0.88 else 0
    expires = ""
    if rng.random() < 0.18:
        expires = iso(created + datetime.timedelta(days=rng.randint(30, 400)))
    clicks = rng.choices([rng.randint(0, 9), rng.randint(10, 80),
                          rng.randint(80, 400), rng.randint(400, 1500)],
                         weights=[30, 40, 22, 8])[0]
    return {
        "id": link_id,
        "short_code": make_code(used_codes),
        "original_url": url,
        "title": title,
        "owner_id": owner_id,
        "created_at": iso(created),
        "clicks": clicks,
        "is_active": active,
        "expires_at": expires,
        "redirect_type": rng.choice(["301", "301", "302"]),
        "tags": json.dumps(rng.sample(tags, rng.randint(1, 3))),
        "qr_enabled": 1 if rng.random() < 0.8 else 0,
        "utm_source": utm_source,
        "utm_medium": utm_medium,
        "utm_campaign": utm_campaign,
    }


def main():
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.row_factory = sqlite3.Row

    used_codes = {r[0] for r in db.execute(
        "SELECT short_code FROM url_shorteners_qr_links")}
    next_user = db.execute("SELECT MAX(id)+1 FROM url_shorteners_qr_users").fetchone()[0]
    next_link = db.execute("SELECT MAX(id)+1 FROM url_shorteners_qr_links").fetchone()[0]
    next_click = db.execute("SELECT MAX(id)+1 FROM url_shorteners_qr_click_stats").fetchone()[0]
    existing_links = [dict(r) for r in db.execute(
        "SELECT id, owner_id, created_at, clicks FROM url_shorteners_qr_links")]
    tracked = dict(db.execute(
        "SELECT link_id, COUNT(*) FROM url_shorteners_qr_click_stats GROUP BY link_id"))

    # ---- users -------------------------------------------------------------
    users_new = []
    for username, password, name, email, plan in NEW_USERS:
        users_new.append({"id": next_user, "username": username,
                          "password": password, "name": name,
                          "email": email, "plan": plan})
        next_user += 1

    # ---- links -------------------------------------------------------------
    links_new = []
    serial = 1

    # Main user: strictly older than her oldest existing link.
    main_start = datetime.datetime(2024, 5, 1, 8, 0, 0)
    for _ in range(MAIN_USER_NEW_LINKS):
        theme = rng.choice(["marketing", "marketing", "personal", "dev"])
        created = rand_dt(main_start, MAIN_USER_CUTOFF)
        links_new.append(build_link(next_link, 1, theme, created,
                                    used_codes, serial))
        next_link += 1
        serial += 1

    # Other owners: existing users 2-4 plus the new users.
    other_owners = []
    for uid, theme in OWNER_THEME.items():
        other_owners.append((uid, theme))
    for u, theme in zip(users_new, NEW_USER_THEMES):
        other_owners.append((u["id"], theme))

    remaining = TARGET_NEW_LINKS - MAIN_USER_NEW_LINKS
    per_owner = remaining // len(other_owners)
    extra = remaining - per_owner * len(other_owners)
    oth_start = datetime.datetime(2024, 2, 1, 8, 0, 0)
    oth_end = datetime.datetime(2026, 6, 30, 20, 0, 0)
    for i, (uid, theme) in enumerate(other_owners):
        n = per_owner + (1 if i < extra else 0)
        for _ in range(n):
            tkey = theme if rng.random() < 0.75 else rng.choice(list(THEMES))
            created = rand_dt(oth_start, oth_end)
            links_new.append(build_link(next_link, uid, tkey, created,
                                        used_codes, serial))
            next_link += 1
            serial += 1

    # ---- click_stats -------------------------------------------------------
    clicks_new = []

    def add_clicks_for(link_id, created_at, n):
        nonlocal next_click
        start = datetime.datetime.fromisoformat(created_at)
        end = min(start + datetime.timedelta(days=420), TODAY)
        if end <= start:
            end = start + datetime.timedelta(hours=6)
        for _ in range(n):
            clicks_new.append({
                "id": next_click,
                "link_id": link_id,
                "timestamp": iso(rand_dt(start, end)),
                "referrer": rng.choices(REFERRERS, weights=REF_WEIGHTS)[0],
                "country": rng.choices(COUNTRIES, weights=CTRY_WEIGHTS)[0],
                "device": rng.choices(DEVICES, weights=DEV_WEIGHTS)[0],
            })
            next_click += 1

    # a) modest backfill for existing links, never exceeding their stored
    #    `clicks` counter, and none for link 10 (the "(archived)" task target).
    budget = TARGET_NEW_CLICKS
    for l in existing_links:
        if l["id"] == 10:
            continue
        cap = l["clicks"] - tracked.get(l["id"], 0)
        n = min(rng.randint(8, 40), max(cap, 0))
        add_clicks_for(l["id"], l["created_at"], n)
        budget -= n

    # b) bulk on new links, proportional to each link's clicks counter but
    #    capped so no per-link stats page aggregates an outsized row set.
    weights = [min(l["clicks"], 400) + 1 for l in links_new]
    total_w = sum(weights)
    for l, w in zip(links_new, weights):
        n = round(budget * w / total_w)
        n = min(n, l["clicks"], 90)
        add_clicks_for(l["id"], l["created_at"], n)
    # top up shortfall (rounding + caps) on the most-clicked new links
    shortfall = TARGET_NEW_CLICKS - len(clicks_new)
    if shortfall > 0:
        eligible = sorted(links_new, key=lambda l: -l["clicks"])
        i = 0
        while shortfall > 0 and eligible:
            l = eligible[i % len(eligible)]
            add_clicks_for(l["id"], l["created_at"], 1)
            shortfall -= 1
            i += 1

    print(f"users: +{len(users_new)}, links: +{len(links_new)}, "
          f"click_stats: +{len(clicks_new)}")
    if dry:
        for l in links_new[:6]:
            print(" ", l["owner_id"], l["created_at"], l["short_code"],
                  "|", l["title"], "|", l["tags"])
        by_owner = {}
        for l in links_new:
            by_owner[l["owner_id"]] = by_owner.get(l["owner_id"], 0) + 1
        print("  links per owner:", dict(sorted(by_owner.items())))
        per_link = {}
        for c in clicks_new:
            per_link[c["link_id"]] = per_link.get(c["link_id"], 0) + 1
        print("  max clicks rows on one link:", max(per_link.values()))
        bad = [l for l in links_new if "(archived)" in
               (l["title"] + l["original_url"] + l["short_code"] + l["tags"]).lower()]
        print("  '(archived)' matches in new rows:", len(bad))
        return

    bdir = ROOT / "data" / "backups" / "url-shorteners-qr-expansion-2026-07-20"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "inserted_ids.json").write_text(json.dumps({
        "users": [u["id"] for u in users_new],
        "links": [l["id"] for l in links_new],
        "click_stats": [c["id"] for c in clicks_new]}, indent=1))

    for table, rows in (("users", users_new), ("links", links_new),
                        ("click_stats", clicks_new)):
        if not rows:
            continue
        cols = list(rows[0].keys())
        db.executemany(
            f"INSERT INTO url_shorteners_qr_{table} ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' * len(cols))})",
            [[r[c] for c in cols] for r in rows])
    for fts in ("fts_url_shorteners_qr_links", "fts_url_shorteners_qr_click_stats"):
        db.execute(f"INSERT INTO {fts}({fts}) VALUES('rebuild')")
    db.commit()
    print(f"inserted; rollback ids at {bdir}/inserted_ids.json")


if __name__ == "__main__":
    main()
