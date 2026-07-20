"""Expand design-creative (DesignFlow) base data.

The Canva-style site ships with 30 templates / 10 projects / 3 users, which
leaves the template gallery thin and the projects universe nearly empty.
Adds deterministic (seeded) synthetic templates, designer accounts, and
projects themed to the Lakeport / Meridian / Cascadia universe.

Scaling notes (why these ceilings):
- `/` renders ALL templates unpaginated -> templates capped at 400 total.
- routes load/save the whole `projects` collection per request
  (`db.save_collection`) and `/projects` renders a full per-user list ->
  bulk volume goes into projects spread over 60 new users (<=120 each),
  rows kept lean (1-3 elements). Existing user pages stay recognizable:
  new projects for user 1 (alex_r) are dated older than his existing ones;
  users 2 and 3 get no new projects.
- `use_count` of new templates stays below the existing top-3 so the
  "most popular" ordering is unchanged.

Insert-only; inserted ids recorded under data/backups/ for rollback.

Usage: python scripts/expand_design_creative_data.py [--dry-run]
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

TARGET_TEMPLATES = 400   # total after expansion (index page renders all)
TARGET_USERS = 63        # total after expansion
TARGET_PROJECTS = 4600   # total after expansion
USER1_NEW_PROJECTS = 12  # older items for alex_r (id 1)

# ---------------------------------------------------------------------------
# Template vocabulary (mirrors existing "Base - Style" titles)
# ---------------------------------------------------------------------------

STYLES = ["Bold", "Pastel", "Vintage", "Modern", "Elegant", "Playful",
          "Neon", "Organic", "Geometric", "Monochrome", "Gradient", "Retro",
          "Editorial", "Handcrafted", "Luxe", "Fresh", "Classic", "Dynamic",
          "Soft", "Urban", "Coastal", "Botanical", "Duotone", "Collage"]

# category -> (weight of new rows, [(base, dims), ...])
CATEGORY_BASES = {
    "social-media": (80, [
        ("Instagram Post", "1080x1080"), ("Instagram Story", "1080x1920"),
        ("Instagram Carousel", "1080x1080"), ("Facebook Cover", "820x312"),
        ("Facebook Post", "1080x1080"), ("Twitter Header", "1500x500"),
        ("LinkedIn Banner", "1584x396"),
    ]),
    "presentation": (45, [
        ("Pitch Deck", "1920x1080"), ("Business Presentation", "1920x1080"),
        ("Education Slides", "1920x1080"), ("Workshop Slides", "1920x1080"),
        ("Sales Deck", "1920x1080"), ("Webinar Slides", "1920x1080"),
        ("Portfolio Deck", "1920x1080"), ("Report Slides", "1920x1080"),
    ]),
    "poster": (55, [
        ("Event Poster", "1080x1620"), ("Movie Poster", "2400x3600"),
        ("Concert Poster", "1080x1620"), ("Art Show Poster", "1080x1350"),
        ("Charity Run Poster", "1080x1350"), ("Theater Poster", "2400x3600"),
        ("Exhibition Poster", "1080x1620"), ("Community Poster", "1080x1350"),
    ]),
    "logo": (50, [("Logo", "500x500")]),
    "business-card": (35, [("Business Card", "1050x600")]),
    "flyer": (55, [
        ("Flyer", "1275x1650"), ("Greeting Card", "1275x1650"),
    ]),
    "banner": (50, [
        ("Web Banner", "1200x628"), ("YouTube Thumbnail", "1280x720"),
        ("Email Header", "600x200"), ("Display Ad", "1440x600"),
    ]),
}

LOGO_INDUSTRIES = ["Bakery", "Law Firm", "Yoga Studio", "Barbershop",
                   "Brewery", "Pet Care", "Florist", "Real Estate Group",
                   "Music Label", "Consulting Firm", "Dental Clinic",
                   "Bookstore", "Food Truck", "Esports Team", "Travel Agency",
                   "Landscaping", "Coffee Roaster", "Kayak Rentals",
                   "Wellness Spa", "Craft Distillery", "Tattoo Parlor",
                   "Cycling Club", "Vineyard", "Surf Shop", "Print Shop"]

FLYER_TOPICS = ["Yard Sale", "Open House", "Farmers Market", "Book Club",
                "Community Cleanup", "Car Wash Fundraiser", "Trivia Night",
                "Holiday Bazaar", "Summer Camp", "Cooking Class",
                "Garage Band Show", "Blood Drive", "Bake Sale",
                "Adoption Event", "Wine Tasting", "5K Fun Run",
                "Craft Fair", "Movie Night", "Job Fair", "Plant Swap"]

CARD_STYLES = ["Photography", "Consultant", "Barber", "Florist", "Realtor",
               "Developer", "Illustrator", "Chef", "Musician", "Architect",
               "Copywriter", "Fitness Coach"] + STYLES

# category -> preview_placeholder pool (all tokens already exist in base data)
PREVIEWS = {
    "social-media": ["gradient-square", "square-geo", "square-warm",
                     "square-red", "square-gray", "tall-neon", "tall-sunset",
                     "tall-white", "wide-banner-blue"],
    "presentation": ["slide-teal", "slide-dark", "slide-multicolor",
                     "slide-purple"],
    "poster": ["tall-red", "tall-retro", "tall-neon", "tall-sunset",
               "tall-white"],
    "logo": ["square-geo", "square-warm", "square-red", "square-gray",
             "gradient-square"],
    "business-card": ["card-blue", "card-split", "card-white"],
    "flyer": ["flyer-green", "flyer-cream", "flyer-red", "flyer-gold",
              "flyer-resume"],
    "banner": ["banner-shop", "banner-game", "banner-email", "banner-saas",
               "wide-banner-blue", "wide-banner-orange", "wide-banner-navy"],
}

FEATURES = ["editable text layers", "drag-and-drop photo frames",
            "a bold typographic hierarchy", "soft gradient backgrounds",
            "a flexible grid layout", "matching color swatches",
            "ready-made icon accents", "generous whitespace",
            "a strong call-to-action block", "layered geometric shapes",
            "hand-drawn accents", "print-safe margins",
            "an adaptable header area", "duotone photo treatments"]

TAG_EXTRAS = ["clean", "template", "customizable", "trendy", "simple",
              "colorful", "professional", "creative", "layout", "branding"]

# ---------------------------------------------------------------------------
# User vocabulary
# ---------------------------------------------------------------------------

FIRST = ["Maya", "Jordan", "Priya", "Marcus", "Elena", "Tobias", "Nina",
         "Diego", "Harper", "Kenji", "Amara", "Felix", "Rosa", "Owen",
         "Leila", "Victor", "Ingrid", "Andre", "Camille", "Hassan", "Beatriz",
         "Lars", "Yuki", "Nadia", "Cole", "Simone", "Rafael", "Astrid",
         "Theo", "Wren", "Idris", "Paloma", "Gustav", "Mei", "Callum",
         "Zora", "Emil", "Tessa", "Bram", "Lucia"]
LAST = ["Nguyen", "Okafor", "Silva", "Kowalski", "Tanaka", "Marsh",
        "Delgado", "Femi", "Larsen", "Novak", "Reyes", "Bishop", "Osei",
        "Vargas", "Lindqvist", "Chen", "Moreau", "Petrov", "Ademola",
        "Fitzgerald", "Ruiz", "Nakamura", "Sorensen", "Byrne", "Castillo",
        "Haddad", "Ojeda", "Krause", "Mbeki", "Duval"]
UNAME_SUFFIX = ["", "", "", "_design", "_studio", "_creates", "_art", "_dsgn"]
PW_WORDS = ["design", "create", "pixel", "canvas", "studio", "vector",
            "layout", "artsy", "sketch", "render"]
DOMAINS = ["gmail.com", "outlook.com", "yahoo.com", "protonmail.com"]
PLANS = (["free"] * 6 + ["pro"] * 3 + ["business"])

# ---------------------------------------------------------------------------
# Project vocabulary
# ---------------------------------------------------------------------------

CLIENTS = ["Lakeport Farmers Market", "Lakeport Animal Shelter",
           "Lakeport Jazz Collective", "Lakeport Library Friends",
           "Lakeport Brewing Co", "Lakeport Yoga Loft",
           "Meridian Systems", "Meridian Dev Summit", "MeridianFlow",
           "MeridianVault", "MeridianLens", "Cascadia Trailworks",
           "Cascadia Roasters", "Cascadia Cycle Club", "Cascadia Kayak Co",
           "Cascadia Wellness Spa", "Brooks Fitness", "Okonkwo PT Practice",
           "Harborview Dental", "Northgate Books", "Pinecrest Weddings",
           "Silverline Consulting", "Bluebird Bakery", "Driftwood Surf Shop",
           "Emberline Tattoo", "Foxglove Florists", "Granite Peak Tours",
           "Willow & Sage Catering", "Ironbark Distillery", "Juniper Realty",
           "Kestrel Media", "Larkspur Yarns", "Mosswood Nursery",
           "Nightowl Diner", "Orchard Lane Farms", "Puget Print Co",
           "Quill & Ink Stationery", "Riverbend Music School",
           "Saltgrass Seafood", "Timberline Gear", "Umbra Photography",
           "Verdant Landscaping", "Westwind Sailing", "Yarrow Skincare",
           "Zephyr Bikes", "Alder Street Tacos", "Basalt Climbing Gym",
           "Cedar & Stone Spa", "Dockside Grill", "Evergreen Tutoring",
           "Firefly Candle Co", "Gullwing Charters", "Hazelwood Toys",
           "Inlet Coffee Bar", "Jackrabbit Couriers", "Kelp Forest Divers",
           "Lantern House Theater", "Maple Row Creamery", "Nettle Tea House",
           "Osprey Outfitters", "Pebble Lane Pottery"]

DELIVERABLES = ["Logo Concept", "Logo Refresh", "Instagram Post",
                "Instagram Story Set", "Event Flyer", "Business Card",
                "Pitch Deck", "Banner Ad", "Poster", "Brand Board",
                "Menu Design", "Launch Graphics", "Newsletter Header",
                "Promo Flyer", "Social Media Kit", "Price List",
                "Gift Card Design", "Loyalty Card", "Window Decal",
                "Booth Backdrop", "Web Banner", "YouTube Thumbnail",
                "Holiday Card", "Grand Opening Poster", "Membership Card",
                "Workshop Slides", "Anniversary Graphics", "Merch Mockup",
                "Sponsorship Deck", "Sticker Sheet"]

VARIANTS = ["V2", "V3", "Refresh", "2026", "Spring 2026", "Fall 2025",
            "Q1", "Q2", "Alt", "Final", "Concept B", "Draft 2"]

# personal-flavored titles for alex_r (id 1) — dated OLDER than his existing
USER1_TITLES = ["Rivera Family Reunion Flyer", "Mom's Retirement Card",
                "Apartment Moving Sale Poster", "Trivia Team Logo",
                "Game Night Invite", "Lakeport 5K Bib Design",
                "New Year Party Story", "Dog Park Meetup Flyer",
                "Recipe Card Collection", "Holiday Gift Tags",
                "Concert Road Trip Collage", "Book Swap Poster"]

FONTS = ["Montserrat Bold", "Playfair Display", "Inter", "Poppins Semibold",
         "Lora", "Roboto Condensed", "Bebas Neue", "Raleway",
         "Source Sans Pro", "Merriweather"]
FILLS = ["#E63946", "#2A9D8F", "#264653", "#E9C46A", "#F4A261", "#7C3AED",
         "#1D3557", "#06B6D4", "#F97316", "#10B981", "#DB2777", "#475569"]
GRADIENTS = ["linear-gradient(135deg, #1a1a2e, #16213e)",
             "linear-gradient(135deg, #7C3AED, #DB2777)",
             "linear-gradient(180deg, #FDE68A, #F97316)",
             "linear-gradient(135deg, #0F766E, #06B6D4)"]
SLOGANS = ["GRAND OPENING", "SAVE THE DATE", "JOIN US", "NOW OPEN",
           "LIMITED TIME", "EST. 2019", "FRESH & LOCAL", "BOOK TODAY",
           "SUMMER SALE", "YOU'RE INVITED", "HANDMADE", "SINCE 1998"]


def d(year_lo, year_hi):
    """Random ISO date between Jan 1 of year_lo and Dec 31 of year_hi."""
    start = datetime.date(year_lo, 1, 1).toordinal()
    end = datetime.date(year_hi, 12, 31).toordinal()
    return datetime.date.fromordinal(rng.randint(start, end))


def make_elements(client, dims):
    w, h = (int(x) for x in dims.split("x"))
    slug = client.lower().replace(" ", "-").replace("&", "and").replace("'", "")
    els = []
    if rng.random() < 0.45:  # background
        els.append({"type": "shape", "properties": {
            "shape": "rectangle", "x": 0, "y": 0, "width": w, "height": h,
            "fill": rng.choice(GRADIENTS if rng.random() < 0.4 else FILLS)}})
    # headline text (always)
    text = client.upper() if rng.random() < 0.6 else rng.choice(SLOGANS)
    els.append({"type": "text", "properties": {
        "text": text, "x": rng.randrange(20, max(30, w // 3)),
        "y": rng.randrange(20, max(30, h - 60)),
        "font": rng.choice(FONTS), "size": rng.choice([18, 24, 28, 32, 36, 42, 48, 56])}})
    extra = rng.random()
    if extra < 0.35:
        shape = rng.choice(["circle", "arc"])
        els.append({"type": "shape", "properties": {
            "shape": shape, "x": rng.randrange(40, max(50, w - 40)),
            "y": rng.randrange(40, max(50, h - 40)),
            "radius": rng.choice([40, 60, 80, 100, 120]),
            "fill": rng.choice(FILLS)}})
    elif extra < 0.55:
        kind = rng.choice(["icon.svg", "photo.jpg", "logo.svg"])
        size = rng.choice([80, 120, 160, 200])
        els.append({"type": "image", "properties": {
            "src": f"{slug}-{kind}", "x": rng.randrange(20, max(30, w - size)),
            "y": rng.randrange(20, max(30, h - size)),
            "width": size, "height": size}})
    return els


def main():
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.row_factory = sqlite3.Row

    existing_titles = {r[0] for r in db.execute(
        "SELECT title FROM design_creative_templates")}
    existing_proj_titles = {r[0] for r in db.execute(
        "SELECT title FROM design_creative_projects")}
    existing_unames = {r[0] for r in db.execute(
        "SELECT username FROM design_creative_users")}
    n_tmpl = db.execute("SELECT COUNT(*) FROM design_creative_templates").fetchone()[0]
    n_proj = db.execute("SELECT COUNT(*) FROM design_creative_projects").fetchone()[0]
    n_user = db.execute("SELECT COUNT(*) FROM design_creative_users").fetchone()[0]
    next_tmpl = db.execute("SELECT MAX(id)+1 FROM design_creative_templates").fetchone()[0]
    next_proj = db.execute("SELECT MAX(id)+1 FROM design_creative_projects").fetchone()[0]
    next_user = db.execute("SELECT MAX(id)+1 FROM design_creative_users").fetchone()[0]
    # keep "most popular" template unchanged: stay below the existing top-3
    use_cap = db.execute("SELECT MAX(use_count) FROM design_creative_templates").fetchone()[0]

    # ---------------- templates ----------------
    templates_new = []
    taken = set(existing_titles)
    for cat, (weight, bases) in CATEGORY_BASES.items():
        need = round(weight * (TARGET_TEMPLATES - n_tmpl) / 370)
        # build candidate title pool for this category
        if cat == "logo":
            pool = [(f"Logo - {adj} {ind}" if rng.random() < 0.5 else f"Logo - {ind}",
                     "500x500")
                    for ind in LOGO_INDUSTRIES for adj in rng.sample(STYLES, 4)]
        elif cat == "flyer":
            pool = [(f"{b} - {t}", dims) for b, dims in bases for t in FLYER_TOPICS] + \
                   [(f"{b} - {s}", dims) for b, dims in bases for s in STYLES]
        elif cat == "business-card":
            pool = [(f"Business Card - {s}", "1050x600") for s in CARD_STYLES]
        else:
            pool = [(f"{b} - {s}", dims) for b, dims in bases for s in STYLES]
        rng.shuffle(pool)
        made = 0
        for title, dims in pool:
            if made >= need:
                break
            if title in taken:
                continue
            taken.add(title)
            base_words = [w.lower().strip("-&") for w in title.replace(" - ", " ").split()
                          if len(w) > 2][:3]
            tags = list(dict.fromkeys(base_words + [rng.choice(TAG_EXTRAS)]))[:4]
            templates_new.append({
                "id": next_tmpl,
                "title": title,
                "category": cat,
                "dimensions": dims,
                "description": f"{title.split(' - ')[1]} {title.split(' - ')[0].lower()} "
                               f"template with {rng.choice(FEATURES)}.",
                "tags": json.dumps(tags),
                "use_count": rng.randint(15, use_cap - 2800),
                "preview_placeholder": rng.choice(PREVIEWS[cat]),
            })
            next_tmpl += 1
            made += 1
    all_template_ids = [r[0] for r in db.execute(
        "SELECT id FROM design_creative_templates")] + [t["id"] for t in templates_new]
    tmpl_dims = {t["id"]: t["dimensions"] for t in templates_new}
    for r in db.execute("SELECT id, dimensions FROM design_creative_templates"):
        tmpl_dims[r["id"]] = r["dimensions"]

    # ---------------- users ----------------
    users_new = []
    unames = set(existing_unames)
    people = [(f, l) for f in FIRST for l in LAST]
    rng.shuffle(people)
    for f, l in people:
        if len(users_new) >= TARGET_USERS - n_user:
            break
        uname = f"{f.lower()}_{l.lower()}{rng.choice(UNAME_SUFFIX)}"
        if uname in unames:
            uname = f"{f.lower()}_{l.lower()[0]}{rng.randint(2, 99)}"
        if uname in unames:
            continue
        unames.add(uname)
        users_new.append({
            "id": next_user,
            "root_user_id": 0,
            "username": uname,
            "password": f"{rng.choice(PW_WORDS)}{rng.randint(2017, 2025)}!",
            "name": f"{f} {l}",
            "email": f"{f.lower()}.{l.lower()}{rng.choice(['', '', str(rng.randint(1, 99))])}"
                     f"@{rng.choice(DOMAINS)}",
            "plan": rng.choice(PLANS),
            "projects": [],   # filled below, serialized at insert
            "favorites": json.dumps(sorted(rng.sample(all_template_ids,
                                                      rng.randint(2, 9)))),
        })
        next_user += 1

    # ---------------- projects ----------------
    n_new_projects = TARGET_PROJECTS - n_proj
    new_user_ids = [u["id"] for u in users_new]
    counts = {uid: rng.randint(50, 105) for uid in new_user_ids}
    # exact-total fixup, keep each user in [20, 120]
    remaining = n_new_projects - USER1_NEW_PROJECTS
    while sum(counts.values()) > remaining:
        uid = rng.choice(new_user_ids)
        if counts[uid] > 20:
            counts[uid] -= 1
    while sum(counts.values()) < remaining:
        uid = rng.choice(new_user_ids)
        if counts[uid] < 120:
            counts[uid] += 1

    projects_new = []
    proj_titles = set(existing_proj_titles)

    def unique_title(base):
        if base not in proj_titles:
            return base
        for v in rng.sample(VARIANTS, len(VARIANTS)):
            cand = f"{base} ({v})"
            if cand not in proj_titles:
                return cand
        n = 2
        while f"{base} #{n}" in proj_titles:
            n += 1
        return f"{base} #{n}"

    # alex_r (id 1): a few personal projects, all dated older than his
    # existing ones (created >= 2026-05-25, modified >= 2026-05-30)
    for base in rng.sample(USER1_TITLES, USER1_NEW_PROJECTS):
        title = unique_title(base)
        proj_titles.add(title)
        tid = rng.choice(all_template_ids)
        created = d(2025, 2025) if rng.random() < 0.6 else \
            datetime.date(2026, rng.randint(1, 3), rng.randint(1, 28))
        modified = min(created + datetime.timedelta(days=rng.randint(0, 45)),
                       datetime.date(2026, 5, 18))
        modified = max(modified, created)
        projects_new.append({
            "id": next_proj, "title": title, "owner_id": 1,
            "template_id": tid, "dimensions": tmpl_dims[tid],
            "created_date": created.isoformat(),
            "modified_date": modified.isoformat(),
            "status": rng.choices(["draft", "in_progress", "completed"],
                                  weights=[25, 25, 50])[0],
            "elements": json.dumps(make_elements(
                rng.choice(["Alex Rivera", "Rivera Family", "Lakeport Trivia"]),
                tmpl_dims[tid])),
        })
        next_proj += 1

    for u in users_new:
        # each designer works with a small stable of clients
        stable = rng.sample(CLIENTS, rng.randint(4, 9))
        for _ in range(counts[u["id"]]):
            client = rng.choice(stable)
            base = f"{client} - {rng.choice(DELIVERABLES)}"
            title = unique_title(base)
            proj_titles.add(title)
            tid = rng.choice(all_template_ids) if rng.random() < 0.92 else 0
            dims = tmpl_dims.get(tid) or rng.choice(
                ["1080x1080", "1275x1650", "500x500", "1920x1080"])
            created = d(2024, 2026)
            created = min(created, datetime.date(2026, 6, 20))
            modified = min(created + datetime.timedelta(days=rng.randint(0, 90)),
                           datetime.date(2026, 6, 25))
            projects_new.append({
                "id": next_proj, "title": title, "owner_id": u["id"],
                "template_id": tid, "dimensions": dims,
                "created_date": created.isoformat(),
                "modified_date": modified.isoformat(),
                "status": rng.choices(["draft", "in_progress", "completed"],
                                      weights=[22, 28, 50])[0],
                "elements": json.dumps(make_elements(client, dims)),
            })
            u["projects"].append(next_proj)
            next_proj += 1

    for u in users_new:
        u["projects"] = json.dumps(u["projects"])

    print(f"templates: +{len(templates_new)} (-> {n_tmpl + len(templates_new)}), "
          f"users: +{len(users_new)} (-> {n_user + len(users_new)}), "
          f"projects: +{len(projects_new)} (-> {n_proj + len(projects_new)})")
    if dry:
        for t in templates_new[:4]:
            print("  T:", t["category"], "|", t["title"], "|", t["dimensions"],
                  "|", t["use_count"], "|", t["preview_placeholder"])
        for u in users_new[:3]:
            print("  U:", u["username"], u["plan"], u["email"])
        for p in projects_new[:6]:
            print("  P:", p["owner_id"], p["status"], p["created_date"],
                  "->", p["modified_date"], "|", p["title"][:60])
        per_user = {}
        for p in projects_new:
            per_user[p["owner_id"]] = per_user.get(p["owner_id"], 0) + 1
        print("  max projects/user:", max(per_user.values()),
              "min:", min(per_user.values()))
        return

    bdir = ROOT / "data" / "backups" / "design-creative-expansion-2026-07-20"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "inserted_ids.json").write_text(json.dumps({
        "templates": [t["id"] for t in templates_new],
        "users": [u["id"] for u in users_new],
        "projects": [p["id"] for p in projects_new]}, indent=1))

    for table, rows in (("templates", templates_new), ("users", users_new),
                        ("projects", projects_new)):
        if not rows:
            continue
        cols = list(rows[0].keys())
        db.executemany(
            f"INSERT INTO design_creative_{table} ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' * len(cols))})",
            [[r[c] for c in cols] for r in rows])
    # sync FTS indexes (external-content FTS5)
    for fts in ("fts_design_creative_templates", "fts_design_creative_projects"):
        if db.execute("SELECT name FROM sqlite_master WHERE name = ?", (fts,)).fetchone():
            db.execute(f"INSERT INTO {fts}({fts}) VALUES('rebuild')")
    db.commit()
    print(f"inserted; rollback ids at {bdir}/inserted_ids.json")


if __name__ == "__main__":
    main()
