"""Expand rating-review (LakeReview) base data.

LakeReview ships with 25 businesses / 40 reviews / 15 photos / 8 users, which
leaves category pages and business detail pages nearly empty. Adds
deterministic (seeded) synthetic Lakeport-themed businesses across the
existing category/subcategory/price vocabulary, a community of new reviewer
accounts, and a large body of reviews attached ONLY to the new businesses so
that every new business row's stored `overall_rating` / `review_count`
aggregates exactly match its actual review rows (existing rows are untouched;
insert-only).

Design notes (page-render sanity, see routes.py):
- /businesses renders every business unpaginated -> keep total ~175 rows.
- /photos renders every photo unpaginated -> keep total ~300 rows.
- /business/<id> renders all reviews for one business -> cap ~70 per business.
- Homepage "recent reviews" shows the 5 newest -> all new reviews are dated
  before the newest existing review (2026-05-12), so the homepage list keeps
  its current entries near the top.
- /my-reviews shows user 1's reviews -> no new reviews are attached to
  existing users; every new review belongs to a new user whose stored
  review_count / photo_count are computed from the generated rows.

Insert-only; inserted ids recorded under data/backups/ for rollback.

Usage: ~/.conda/envs/miniweb/bin/python scripts/expand_rating_review_data.py [--dry-run]
"""
import json
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "trimmed_miniweb.db"
rng = random.Random(20260720)

N_BUSINESSES = 150   # ids 26..175  (total 175)
N_USERS = 200        # ids 9..208   (total 208)
N_PHOTOS = 285       # ph-016..ph-300 (total 300)

# ---------------------------------------------------------------------------
# Vocabulary sampled from existing rows
# ---------------------------------------------------------------------------

# (category, subcategory, price_range) combos present in the base data,
# weighted roughly toward what a local review site looks like.
CATEGORY_COMBOS = [
    (("Restaurants", "Brewpub", "$$"), 8),
    (("Restaurants", "Fine Dining", "$$$$"), 4),
    (("Restaurants", "Vietnamese", "$"), 5),
    (("Restaurants", "Farm-to-Table", "$$$"), 5),
    (("Restaurants", "Italian", "$$"), 7),
    (("Restaurants", "Mexican", "$"), 7),
    (("Restaurants", "Japanese", "$$$"), 5),
    (("Restaurants", "Chinese", "$$"), 5),
    (("Restaurants", "Breakfast & Brunch", "$"), 7),
    (("Restaurants", "Deli & Sandwiches", "$"), 6),
    (("Restaurants", "Seafood", "$$"), 6),
    (("Coffee & Tea", "Coffee Shop", "$"), 12),
    (("Food", "Bakery", "$"), 8),
    (("Health & Fitness", "Gym", "$$"), 5),
    (("Health & Fitness", "Yoga", "$$"), 4),
    (("Pets", "Veterinarian", "$$"), 3),
    (("Pets", "Pet Store", "$$"), 3),
    (("Beauty & Spa", "Barber", "$"), 5),
    (("Automotive", "Auto Repair", "$$"), 4),
    (("Public Services", "Library", "Free"), 2),
    (("Services", "Laundromat", "$"), 3),
    (("Shopping", "Farmers Market", "$$"), 2),
    (("Shopping", "Hardware Store", "$$"), 3),
    (("Shopping", "Bookstore", "$$"), 4),
    (("Shopping", "Home Goods", "$$$"), 3),
]

PLACES = [
    "Lakeport", "Harbor", "Cedarwood", "Pinehurst", "Mapleview", "Summit",
    "Bayside", "Driftwood", "Meridian", "Cascadia", "Willow", "Birchwood",
    "Alder", "Fernwood", "Heron", "Osprey", "Lakeshore", "Northgate",
    "Stonebridge", "Juniper", "Bluewater", "Foxglove", "Granite", "Hawthorn",
    "Ironwood", "Kingfisher", "Larchmont", "Mistwood", "Nordby", "Overlook",
    "Puget", "Quarry", "Redcedar", "Sandpiper", "Tidewater", "Umber",
    "Vantage", "Wharfside", "Yellowleaf", "Zephyr", "Anchor", "Boulder",
    "Copperline", "Dockside", "Evergreen", "Falls", "Gullwing", "Hilltop",
    "Inlet", "Jetty", "Knoll", "Lantern", "Marina", "Nettle", "Orchard",
    "Pioneer", "Ridgeline", "Saltair", "Timber", "Union",
]

SUFFIXES = {
    "Brewpub": ["Brewing Co.", "Taproom", "Alehouse", "Public House", "Brewery"],
    "Fine Dining": ["Chophouse", "Prime", "Supper Club", "Reserve"],
    "Vietnamese": ["Pho House", "Noodle Bar", "Banh Mi Co.", "Pho Kitchen"],
    "Farm-to-Table": ["Farmhouse", "Harvest Table", "Field & Fork", "Provisions"],
    "Italian": ["Trattoria", "Osteria", "Pasta House", "Cucina", "Pizzeria"],
    "Mexican": ["Taqueria", "Cantina", "Taco Shop", "Cocina"],
    "Japanese": ["Sushi Bar", "Izakaya", "Ramen House", "Sushi Kitchen"],
    "Chinese": ["Dumpling House", "Wok Kitchen", "Noodle House", "Dim Sum Hall"],
    "Breakfast & Brunch": ["Pancake House", "Brunch Cafe", "Griddle", "Morning Kitchen"],
    "Deli & Sandwiches": ["Deli", "Sandwich Shop", "Provisions Deli", "Corner Deli"],
    "Seafood": ["Fish House", "Oyster Bar", "Crab Shack", "Seafood Grill"],
    "Coffee Shop": ["Coffee", "Cafe", "Roasters", "Espresso Bar", "Coffee House"],
    "Bakery": ["Bakery", "Bread Co.", "Patisserie", "Bakehouse"],
    "Gym": ["Fitness", "Strength Club", "Athletic Club", "Training Co."],
    "Yoga": ["Yoga Studio", "Yoga Collective", "Yoga & Wellness"],
    "Veterinarian": ["Animal Hospital", "Veterinary Clinic", "Pet Clinic"],
    "Pet Store": ["Pet Supply", "Pet Goods", "Feed & Pet"],
    "Barber": ["Barbershop", "Barber Co.", "Cuts", "Grooming Lounge"],
    "Auto Repair": ["Auto Care", "Garage", "Auto Works", "Motor Service"],
    "Library": ["Branch Library", "Community Library"],
    "Laundromat": ["Laundry", "Wash House", "Laundry Co."],
    "Farmers Market": ["Farmers Market", "Public Market"],
    "Hardware Store": ["Hardware", "Hardware & Supply", "Tool & Hardware"],
    "Bookstore": ["Books", "Book Shop", "Booksellers", "Used Books"],
    "Home Goods": ["Home & Living", "Home Goods", "Mercantile", "Interiors"],
}

STREETS = [
    "Northwest 23rd Avenue", "Northeast Broadway", "Southwest Spring Street",
    "Northeast 42nd Avenue", "Northwest Vaughn Street", "Northeast Glisan Street",
    "Northwest 6th Avenue", "Southeast Division Street", "North Interstate Avenue",
    "Northwest 21st Avenue", "Northwest 19th Avenue", "Southeast Foster Road",
    "Southeast Belmont Street", "Northeast 57th Avenue", "Southeast Morrison Street",
    "North Fremont Street", "Northeast Rosa Parks Way", "Southwest Harbor Drive",
    "Northeast Alberta Street", "Southeast Hawthorne Boulevard", "North Mississippi Avenue",
    "Southwest Lakefront Way", "Northeast Fremont Street", "Southeast Stark Street",
]
ZIPS = ["97201", "97202", "97206", "97209", "97210", "97211", "97213",
        "97214", "97217", "97218", "97227", "97232"]

ATTRIBUTE_POOL = {
    "food": ["Outdoor Seating", "Takeout", "Delivery", "Reservations",
             "Happy Hour", "Dog Friendly Patio", "Vegetarian Options",
             "Gluten-Free Options", "Full Bar", "Live Music Fridays",
             "Kid Friendly", "Waterfront Views", "Late Night"],
    "coffee": ["Wi-Fi", "Outdoor Seating", "Takeout", "Good for Working",
               "Locally Roasted", "Vegan Options", "Board Games"],
    "service": ["Appointments Available", "Walk-Ins Welcome", "Free Parking",
                "Open Weekends", "Locally Owned", "Free Estimates",
                "Same-Day Service"],
    "shop": ["Locally Owned", "Free Parking", "Curbside Pickup",
             "Gift Wrapping", "Open Weekends", "Loyalty Program"],
    "fitness": ["Showers", "Free Parking", "Classes Included", "24/7 Access",
                "Personal Training", "Beginner Friendly", "Towel Service"],
}
ATTR_KEY = {
    "Brewpub": "food", "Fine Dining": "food", "Vietnamese": "food",
    "Farm-to-Table": "food", "Italian": "food", "Mexican": "food",
    "Japanese": "food", "Chinese": "food", "Breakfast & Brunch": "food",
    "Deli & Sandwiches": "food", "Seafood": "food", "Coffee Shop": "coffee",
    "Bakery": "coffee", "Gym": "fitness", "Yoga": "fitness",
    "Veterinarian": "service", "Pet Store": "shop", "Barber": "service",
    "Auto Repair": "service", "Library": "service", "Laundromat": "service",
    "Farmers Market": "shop", "Hardware Store": "shop", "Bookstore": "shop",
    "Home Goods": "shop",
}

FIRST_NAMES = [
    "Ava", "Ben", "Chloe", "Dev", "Elena", "Finn", "Grace", "Hank", "Isla",
    "Jonas", "Kira", "Liam", "Maya", "Noah", "Opal", "Priya", "Quinn", "Rosa",
    "Sam", "Tara", "Uma", "Victor", "Wren", "Ximena", "Yusuf", "Zoe", "Andre",
    "Bianca", "Caleb", "Dana", "Eli", "Farah", "Gus", "Hana", "Ivan", "June",
    "Kai", "Lena", "Marco", "Nina", "Omar", "Paige", "Reid", "Sana", "Theo",
    "Vera", "Wes", "Yara", "Cora", "Dean", "Esme", "Gil", "Hope", "Ines",
    "Jack", "Kim", "Lars", "Mona", "Nate", "Petra",
]
LAST_NAMES = [
    "Anderson", "Brooks", "Carver", "Delgado", "Ellis", "Foster", "Griffin",
    "Hayes", "Ibarra", "Jensen", "Kimura", "Lund", "Mercer", "Nguyen",
    "Ortega", "Park", "Quist", "Reyes", "Sandoval", "Tran", "Ueda", "Vance",
    "Walsh", "Xu", "Yoon", "Zamora", "Beckett", "Calloway", "Dunn", "Eng",
    "Ferris", "Gale", "Holt", "Irwin", "Joyce", "Keller", "Lowe", "Moss",
    "Nolan", "Osei",
]
USERNAME_TAGS = ["eats", "reviews", "local", "foodie", "explores", "tastes",
                 "wanders", "bites", "lkpt", "nw"]
LOCATIONS = [("Lakeport, WA", 78), ("Meridian, WA", 10), ("Cascadia, WA", 8),
             ("Harbor Falls, WA", 4)]

# ---------------------------------------------------------------------------
# Review text generation
# ---------------------------------------------------------------------------

ITEMS = {
    "Brewpub": ["hazy IPA flight", "smash burger", "pretzel with beer cheese",
                "seasonal porter", "fish and chips"],
    "Fine Dining": ["tasting menu", "duck confit", "wagyu course",
                    "wine pairing", "chocolate soufflé"],
    "Vietnamese": ["pho tai", "banh mi", "spring rolls", "vermicelli bowl",
                   "iced coffee"],
    "Farm-to-Table": ["seasonal vegetable plate", "roast chicken",
                      "heirloom tomato salad", "berry galette"],
    "Italian": ["cacio e pepe", "margherita pizza", "lasagna", "tiramisu",
                "burrata"],
    "Mexican": ["al pastor tacos", "carnitas burrito", "queso fundido",
                "horchata", "chilaquiles"],
    "Japanese": ["omakase", "chirashi bowl", "tonkotsu ramen", "karaage",
                 "matcha cheesecake"],
    "Chinese": ["soup dumplings", "dan dan noodles", "mapo tofu",
                "scallion pancakes", "char siu"],
    "Breakfast & Brunch": ["lemon ricotta pancakes", "breakfast burrito",
                           "eggs benedict", "cold brew", "hash"],
    "Deli & Sandwiches": ["pastrami on rye", "italian sub", "turkey club",
                          "potato salad", "reuben"],
    "Seafood": ["crab cakes", "fish tacos", "clam chowder", "grilled salmon",
                "oysters on the half shell"],
    "Coffee Shop": ["pour-over", "oat milk latte", "cortado",
                    "morning bun", "cold brew"],
    "Bakery": ["sourdough loaf", "almond croissant", "cinnamon roll",
               "seeded rye", "morning bun"],
    "Gym": ["strength class", "rowing machines", "open gym hours",
            "trainer session"],
    "Yoga": ["vinyasa flow class", "restorative session", "hot yoga class",
             "beginner series"],
    "Veterinarian": ["annual checkup", "dental cleaning", "urgent visit"],
    "Pet Store": ["grain-free kibble selection", "self-serve dog wash",
                  "toy aisle"],
    "Barber": ["skin fade", "beard trim", "hot towel shave", "classic cut"],
    "Auto Repair": ["brake job", "oil change", "timing belt replacement",
                    "pre-purchase inspection"],
    "Library": ["reading room", "holds pickup", "kids story hour",
                "maker space"],
    "Laundromat": ["big washers", "wash-and-fold service", "change machine"],
    "Farmers Market": ["produce stalls", "flower stand", "honey vendor",
                       "food trucks"],
    "Hardware Store": ["paint counter", "tool rental", "fastener aisle",
                       "key cutting"],
    "Bookstore": ["used fiction section", "staff picks shelf",
                  "author reading night", "kids corner"],
    "Home Goods": ["ceramics selection", "linen section", "candle wall",
                   "furniture floor"],
}

POS_OPENERS = [
    "Absolutely worth the trip.", "New favorite spot in town.",
    "Came in on a friend's recommendation and it delivered.",
    "This place gets everything right.", "Stopped by on a Saturday and loved it.",
    "Five stars, no hesitation.", "What a find.",
    "Been meaning to try this place for months.",
]
POS_BODIES = [
    "The {item} was outstanding and the staff clearly care about what they do.",
    "Tried the {item} and it might be the best in Lakeport.",
    "The {item} alone is worth coming back for, and the service was warm without being fussy.",
    "Everything about the visit was great, but the {item} stole the show.",
    "You can tell the owners put real thought into this place — the {item} was spot on.",
]
POS_CLOSERS = [
    "Already planning my next visit.", "Highly recommend.",
    "Will be back with friends.", "Lakeport is lucky to have this place.",
    "Do yourself a favor and go.",
]
MID_OPENERS = [
    "Solid, if not spectacular.", "Decent spot with a few rough edges.",
    "Mixed feelings after a couple of visits.", "Good, not great.",
    "Came in with high hopes and left mostly satisfied.",
]
MID_BODIES = [
    "The {item} was good, but the wait was longer than it should have been.",
    "The {item} is reliable, though prices have crept up lately.",
    "Enjoyed the {item}; the space gets loud when it's busy, so plan accordingly.",
    "The {item} was fine — nothing memorable, nothing wrong.",
    "Service was friendly but slow, and the {item} arrived lukewarm.",
]
MID_CLOSERS = [
    "Would give it another shot.", "Fine in a pinch.",
    "Might be better on a weekday.", "Three stars feels right.",
]
NEG_OPENERS = [
    "Wanted to like this place more than I did.", "Disappointing visit.",
    "Not the experience I was hoping for.", "Left underwhelmed.",
]
NEG_BODIES = [
    "The {item} was a letdown and nobody checked on us for twenty minutes.",
    "We waited forty minutes and the {item} still came out wrong.",
    "The {item} was overpriced for what you get, and the room needed a good cleaning.",
    "Staff seemed overwhelmed, and the {item} just wasn't up to par.",
]
NEG_CLOSERS = [
    "Might have been an off night, but I won't rush back.",
    "Hope they sort it out — the neighborhood deserves better.",
    "Two stars because the location is convenient.",
    "Won't be returning anytime soon.",
]
TITLES = {
    5: ["Can't recommend enough", "A Lakeport gem", "Worth every penny",
        "New go-to spot", "Exceeded expectations", "Just go",
        "Best {sub} around", "Blown away"],
    4: ["Really solid", "Great spot with minor quibbles", "Almost perfect",
        "Very good {sub}", "Happy to have this nearby", "Reliably good"],
    3: ["Decent but uneven", "Middle of the road", "Good, not great",
        "Has potential", "Just okay"],
    2: ["Underwhelming", "Needs work", "Not what it used to be",
        "Expected more"],
    1: ["Save your money", "Very disappointing", "Won't be back"],
}

PHOTO_CAPTIONS = [
    "The {item} at {biz}", "{biz} — {item}, highly recommend",
    "Saturday {item} run at {biz}", "First try of the {item} at {biz}",
    "{item} close-up at {biz}", "Patio afternoon at {biz}",
    "Counter view at {biz}", "The famous {item} from {biz}",
]


def slugify(text):
    out = []
    for ch in text.lower():
        if ch.isalnum():
            out.append(ch)
        elif out and out[-1] != "-":
            out.append("-")
    return "".join(out).strip("-")


def rand_date(rng, start_ord, end_ord):
    import datetime
    return datetime.date.fromordinal(rng.randint(start_ord, end_ord))


def main():
    import datetime
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.row_factory = sqlite3.Row

    existing_names = {r["name"] for r in db.execute(
        "SELECT name FROM rating_review_businesses")}
    existing_usernames = {r["username"] for r in db.execute(
        "SELECT username FROM rating_review_users")}
    next_biz = db.execute("SELECT MAX(id)+1 FROM rating_review_businesses").fetchone()[0]
    next_rev = db.execute("SELECT MAX(id)+1 FROM rating_review_reviews").fetchone()[0]
    next_user = db.execute("SELECT MAX(id)+1 FROM rating_review_users").fetchone()[0]
    # photo ids are ph-NNN strings
    max_ph = 0
    for (pid,) in db.execute("SELECT id FROM rating_review_photos"):
        if isinstance(pid, str) and pid.startswith("ph-"):
            try:
                max_ph = max(max_ph, int(pid.split("-")[1]))
            except ValueError:
                pass
    root_user_ids = [r[0] for r in db.execute(
        "SELECT DISTINCT root_user_id FROM rating_review_users")]

    # -- users ------------------------------------------------------------
    users_new = []
    seen_users = set(existing_usernames)
    while len(users_new) < N_USERS:
        fn = rng.choice(FIRST_NAMES)
        ln = rng.choice(LAST_NAMES)
        style = rng.random()
        if style < 0.55:
            uname = f"{fn.lower()}_{ln[0].lower()}"
        elif style < 0.8:
            uname = f"{fn.lower()}_{rng.choice(USERNAME_TAGS)}"
        else:
            uname = f"{fn.lower()}{ln.lower()}{rng.randint(2, 99)}"
        if uname in seen_users:
            uname = f"{uname}{rng.randint(2, 99)}"
            if uname in seen_users:
                continue
        seen_users.add(uname)
        joined = rand_date(rng, datetime.date(2022, 5, 15).toordinal(),
                           datetime.date(2023, 12, 20).toordinal())
        loc = rng.choices([l for l, _ in LOCATIONS],
                          weights=[w for _, w in LOCATIONS])[0]
        users_new.append({
            "id": next_user + len(users_new),
            "root_user_id": rng.choice(root_user_ids),
            "username": uname,
            "display_name": f"{fn} {ln[0]}.",
            "email": f"{fn.lower()}.{ln.lower()}@gmail.com",
            "avatar_url": f"/avatars/{uname}.jpg",
            "joined_date": joined.isoformat(),
            "location": loc,
            "review_count": 0,   # filled in after reviews are generated
            "photo_count": 0,    # filled in after photos are generated
            "friends_count": rng.randint(0, 12),
            "elite_status": 1 if rng.random() < 0.06 else 0,
            "is_verified": 1 if rng.random() < 0.55 else 0,
        })
    new_user_ids = [u["id"] for u in users_new]

    # -- businesses -------------------------------------------------------
    combos = [c for c, w in CATEGORY_COMBOS for _ in range(w)]
    rng.shuffle(combos)
    combos = (combos * ((N_BUSINESSES // len(combos)) + 1))[:N_BUSINESSES]

    businesses_new = []
    seen_names = set(existing_names)
    for i, (cat, sub, price) in enumerate(combos):
        for _ in range(200):
            place = rng.choice(PLACES)
            suffix = rng.choice(SUFFIXES[sub])
            name = f"{place} {suffix}"
            if rng.random() < 0.18:
                name = f"The {name}"
            if name not in seen_names:
                seen_names.add(name)
                break
        else:
            continue
        street_no = rng.randint(100, 6900)
        addr = f"{street_no} {rng.choice(STREETS)}, Lakeport, WA, {rng.choice(ZIPS)}"
        phone = f"(555) {rng.randint(200, 989)}-{rng.randint(1000, 9999)}"
        website = f"https://{slugify(name)}.com"
        if sub == "Library":
            hours = {d: "10:00 AM - 8:00 PM" for d in
                     ("monday", "tuesday", "wednesday", "thursday")}
            hours.update({"friday": "10:00 AM - 6:00 PM",
                          "saturday": "10:00 AM - 5:00 PM", "sunday": "Closed"})
        elif ATTR_KEY[sub] in ("coffee",):
            open_h = rng.choice(["6:00 AM", "6:30 AM", "7:00 AM"])
            close_h = rng.choice(["3:00 PM", "5:00 PM", "6:00 PM"])
            hours = {d: f"{open_h} - {close_h}" for d in
                     ("monday", "tuesday", "wednesday", "thursday", "friday")}
            hours["saturday"] = f"7:00 AM - {close_h}"
            hours["sunday"] = rng.choice([f"7:00 AM - {close_h}", "8:00 AM - 2:00 PM"])
        elif ATTR_KEY[sub] == "food":
            open_h = rng.choice(["11:00 AM", "11:30 AM", "12:00 PM", "4:00 PM"])
            close_h = rng.choice(["9:00 PM", "10:00 PM", "11:00 PM"])
            hours = {d: f"{open_h} - {close_h}" for d in
                     ("tuesday", "wednesday", "thursday", "friday", "saturday")}
            hours["monday"] = rng.choice(["Closed", f"{open_h} - {close_h}"])
            hours["sunday"] = rng.choice(["Closed", f"{open_h} - 9:00 PM"])
        else:
            hours = {d: "9:00 AM - 6:00 PM" for d in
                     ("monday", "tuesday", "wednesday", "thursday", "friday")}
            hours["saturday"] = rng.choice(["9:00 AM - 5:00 PM", "10:00 AM - 4:00 PM"])
            hours["sunday"] = rng.choice(["Closed", "11:00 AM - 4:00 PM"])
        # order hours mon..sun like existing rows
        hours = {d: hours[d] for d in ("monday", "tuesday", "wednesday",
                                       "thursday", "friday", "saturday", "sunday")}
        pool = ATTRIBUTE_POOL[ATTR_KEY[sub]]
        attrs = rng.sample(pool, rng.randint(3, min(5, len(pool))))
        lat = round(47.20 + rng.random() * 0.11, 4)
        lng = round(-122.50 + rng.random() * 0.12, 4)
        businesses_new.append({
            "id": next_biz + i,
            "name": name,
            "category": cat,
            "subcategory": sub,
            "address": addr,
            "phone": phone,
            "website": website,
            "hours": json.dumps(hours),
            "price_range": price,
            "overall_rating": 0.0,   # computed from reviews below
            "review_count": 0,       # computed from reviews below
            "claimed": 1 if rng.random() < 0.6 else 0,
            "attributes": json.dumps(attrs),
            "coordinates": json.dumps({"lat": lat, "lng": lng}),
        })

    # -- reviews (attached ONLY to new businesses) ------------------------
    d_start = datetime.date(2024, 1, 5).toordinal()
    d_end = datetime.date(2025, 3, 10).toordinal()   # before existing max 2026-05-12
    reviews_new = []
    rid = next_rev
    for biz in businesses_new:
        n = rng.randint(18, 44)
        if rng.random() < 0.08:          # a handful of local favorites
            n = rng.randint(50, 68)
        quality = rng.uniform(3.1, 4.7)  # business "true" quality
        total = 0
        for _ in range(n):
            r = quality + rng.gauss(0, 0.9)
            rating = max(1, min(5, int(round(r))))
            total += rating
            item = rng.choice(ITEMS[biz["subcategory"]])
            if rating >= 4:
                text = " ".join([rng.choice(POS_OPENERS),
                                 rng.choice(POS_BODIES).format(item=item),
                                 rng.choice(POS_CLOSERS)])
            elif rating == 3:
                text = " ".join([rng.choice(MID_OPENERS),
                                 rng.choice(MID_BODIES).format(item=item),
                                 rng.choice(MID_CLOSERS)])
            else:
                text = " ".join([rng.choice(NEG_OPENERS),
                                 rng.choice(NEG_BODIES).format(item=item),
                                 rng.choice(NEG_CLOSERS)])
            title = rng.choice(TITLES[rating]).format(
                sub=biz["subcategory"].lower())
            reviews_new.append({
                "id": rid,
                "business_id": biz["id"],
                "user_id": rng.choice(new_user_ids),
                "rating": rating,
                "title": title,
                "text": text,
                "date": rand_date(rng, d_start, d_end).isoformat(),
                "useful_count": rng.choices([0, 1, 2, 3, 5, 8, 12],
                                            weights=[30, 22, 18, 12, 9, 6, 3])[0],
                "funny_count": rng.choices([0, 1, 2], weights=[80, 14, 6])[0],
                "cool_count": rng.choices([0, 1, 2, 4], weights=[60, 22, 12, 6])[0],
                "photos": "[]",   # filled in for photo-bearing reviews below
            })
            rid += 1
        biz["review_count"] = n
        biz["overall_rating"] = round(total / n, 1)

    # -- photos (attached to a sample of the new reviews) -----------------
    biz_by_id = {b["id"]: b for b in businesses_new}
    photo_reviews = rng.sample(reviews_new, N_PHOTOS)
    photos_new = []
    rev_by_id = {r["id"]: r for r in reviews_new}
    for i, rev in enumerate(photo_reviews):
        pid = f"ph-{max_ph + 1 + i:03d}"
        biz = biz_by_id[rev["business_id"]]
        item = rng.choice(ITEMS[biz["subcategory"]])
        caption = rng.choice(PHOTO_CAPTIONS).format(item=item, biz=biz["name"])
        url = f"/photos/reviews/{slugify(biz['name'])}-{slugify(item)}.jpg"
        w, h = rng.choice([(1200, 900), (1200, 800), (1080, 1080), (1600, 1200)])
        photos_new.append({
            "id": pid,
            "review_id": rev["id"],
            "user_id": rev["user_id"],
            "business_id": rev["business_id"],
            "caption": caption,
            "url": url,
            "uploaded_at": f"{rev['date']}T{rng.randint(8, 20):02d}:{rng.randint(0, 59):02d}:00Z",
            "width": w,
            "height": h,
        })
        rev_by_id[rev["id"]]["photos"] = json.dumps([pid])

    # -- user aggregate counts from generated rows ------------------------
    per_user_reviews, per_user_photos = {}, {}
    for r in reviews_new:
        per_user_reviews[r["user_id"]] = per_user_reviews.get(r["user_id"], 0) + 1
    for p in photos_new:
        per_user_photos[p["user_id"]] = per_user_photos.get(p["user_id"], 0) + 1
    for u in users_new:
        u["review_count"] = per_user_reviews.get(u["id"], 0)
        u["photo_count"] = per_user_photos.get(u["id"], 0)

    print(f"users: +{len(users_new)}, businesses: +{len(businesses_new)}, "
          f"reviews: +{len(reviews_new)}, photos: +{len(photos_new)}")
    if dry:
        for b in businesses_new[:5]:
            print(f"  biz {b['id']}: {b['name']} | {b['category']}/{b['subcategory']}"
                  f" | {b['price_range']} | {b['overall_rating']}★ x{b['review_count']}")
        for r in reviews_new[:4]:
            print(f"  rev {r['id']}: biz={r['business_id']} u={r['user_id']}"
                  f" {r['rating']}★ '{r['title']}' :: {r['text'][:70]}")
        for p in photos_new[:3]:
            print(f"  photo {p['id']}: rev={p['review_id']} {p['caption'][:60]}"
                  f" {p['url']}")
        return

    bdir = ROOT / "data" / "backups" / "rating-review-expansion-2026-07-20"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "inserted_ids.json").write_text(json.dumps({
        "users": [u["id"] for u in users_new],
        "businesses": [b["id"] for b in businesses_new],
        "reviews": [r["id"] for r in reviews_new],
        "photos": [p["id"] for p in photos_new]}, indent=1))

    for table, rows in (("users", users_new), ("businesses", businesses_new),
                        ("reviews", reviews_new), ("photos", photos_new)):
        cols = list(rows[0].keys())
        db.executemany(
            f"INSERT INTO rating_review_{table} ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' * len(cols))})",
            [[r[c] for c in cols] for r in rows])
    db.commit()

    # sync FTS indexes (external-content tables need a rebuild)
    for table in ("businesses", "reviews", "photos"):
        fts = f"fts_rating_review_{table}"
        if db.execute("SELECT name FROM sqlite_master WHERE name=?",
                      (fts,)).fetchone():
            db.execute(f"INSERT INTO {fts}({fts}) VALUES('rebuild')")
    db.commit()
    print(f"inserted; rollback ids at {bdir}/inserted_ids.json")


if __name__ == "__main__":
    main()
