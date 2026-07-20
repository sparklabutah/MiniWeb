"""Expand auctions-p2p-marketplaces (BidMarket) base data.

The site ships with 458 products, an empty bids table, 10 messages, 15 ratings
and 15 watchlist rows. This adds deterministic (seeded) synthetic rows:

- products  +1700  (ids 459..2158) — Amazon-style listings in the existing five
                    categories (beauty / garden / fashion / electronics / grocery),
                    reusing existing image URLs, brand formats ("Brand: X" /
                    "Visit the X Store"), condition enum, shipping / location /
                    return-policy vocab and the ISO "...T%H:00:00Z" date style.
- bids      ~2360  — full bid history for the new listings only; bid count and
                    max(amount) exactly match each new listing's num_bids /
                    current_price.
- messages  +400   — Q&A pairs about new listings between users 2..10.
- ratings   +300   — buyer<->seller feedback on new listings, users 2..10.
- watchlist +150   — users 2..10 watching new listings.

Task-constraint safety (data/annotations/Minh/auctions-p2p-marketplaces_665c9a,
"shoes in Good condition" count): NO new row contains the substring "shoe" in
any text field (asserted at generation time) and no footwear products are
generated at all, so the recorded search q=Shoes + condition=Good matches no
new rows. User 1 (alex_r_photo) gets no new listings, bids, messages, ratings
or watchlist entries, so their dashboard is unchanged. New auctions all start
before 2026-06-20 (older than every existing listing), keeping "newest" sort
output unchanged.

Insert-only — existing rows are never touched. Inserted ids are recorded in
data/backups/auctions-p2p-marketplaces-expansion-2026-07-20/inserted_ids.json.
FTS tables for products/messages/ratings/watchlist are rebuilt after insert.

Usage: ~/.conda/envs/miniweb/bin/python scripts/expand_auctions_p2p_marketplaces_data.py [--dry-run]
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
T = "auctions_p2p_marketplaces"

rng = random.Random(20260720)

N_PRODUCTS = 1700
N_MESSAGE_PAIRS = 200   # -> 400 message rows
N_RATINGS = 300
N_WATCHLIST = 150

# Words that must never appear (recorded task: search "Shoes" + condition Good
# must keep matching only the existing rows). "shoe" also guards horseshoe etc.
BANNED = ["shoe", "sneaker", "sandal", "slipper", "loafer", "moccasin",
          "footwear", "oxford", "cleat", "espadrille"]

CATEGORIES = ["beauty", "garden", "fashion", "electronics", "grocery"]
CAT_WEIGHTS = [24, 23, 22, 21, 10]

# per-category: (brand names, product cores, feature tails, log-price-range)
VOCAB = {
    "beauty": (
        ["Brrnoo", "Yosoo", "Semme", "GlowVeil", "LumiDerm", "PureBloom",
         "Maxbell", "Serenova", "VidaSkin", "AmoVee", "Cliganic", "EcoTools",
         "Herbivore", "Bliss", "Nuxe"],
        ["Vitamin C Facial Serum", "Hydrating Sheet Mask Set", "Argan Oil Hair Treatment",
         "Charcoal Deep Cleansing Face Wash", "Retinol Night Cream", "Jade Facial Roller",
         "Shea Butter Hand Cream", "Matte Liquid Lipstick Set", "Bamboo Makeup Brush Kit",
         "Aloe Vera Soothing Gel", "Keratin Repair Conditioner", "Rose Water Facial Toner",
         "Exfoliating Body Scrub", "Nail Care Manicure Kit", "Eyebrow Grooming Set",
         "Hyaluronic Acid Moisturizer", "Tea Tree Oil Scalp Treatment", "Collagen Eye Patches",
         "Ceramic Hair Straightener", "Ionic Travel Hair Dryer", "Beard Grooming Kit",
         "SPF 50 Mineral Sunscreen", "Lavender Bath Bomb Gift Set", "Cuticle Oil Pen"],
        ["for Sensitive Skin", "with Natural Ingredients", "Travel Size 2-Pack",
         "Dermatologist Tested", "for Daily Use", "Gift Set", "Paraben Free",
         "with Vitamin E", "Salon Grade", "Cruelty Free", "for All Hair Types",
         "3.4oz", "120ml", "Value Pack"],
        (1.5, 90.0),
    ),
    "garden": (
        ["GrowMate", "Fiskars", "TerraLuxe", "Suncast", "VerdeCraft", "Keter",
         "GreenWorks", "PatioPro", "BloomRite", "Yaheetech", "Ohuhu",
         "Gardzen", "VIVOSUN", "Worth Garden"],
        ["Raised Garden Bed Planter Box", "Solar Pathway Lights 8-Pack",
         "Expandable Garden Hose 50ft", "Stainless Steel Pruning Shears",
         "Ceramic Plant Pot Set of 3", "Folding Patio Adirondack Chair",
         "Bird Feeder with Squirrel Guard", "Drip Irrigation Starter Kit",
         "Outdoor Storage Deck Box", "Bamboo Plant Stand 3-Tier",
         "Weed Barrier Landscape Fabric", "Compost Tumbler Bin 43 Gallon",
         "Hanging Macrame Plant Holder", "Garden Kneeler and Seat with Tool Pouch",
         "Wind Chimes Amazing Grace Tuned", "Patio Umbrella with Tilt 9ft",
         "Wooden Console Table for Entryway", "Firewood Log Rack 4ft",
         "Greenhouse Mini Walk-In 4-Tier", "Lawn Aerator Spike Sandless Roller",
         "Terracotta Herb Growing Kit", "Rain Gauge Decorative Glass",
         "Mosquito Netting Canopy for Patio", "Garden Tool Set 10-Piece with Tote"],
        ["Weather Resistant", "for Outdoor Use", "Easy Assembly", "Heavy Duty",
         "with Storage Bag", "UV Protected", "All-Season", "Rust Proof",
         "for Vegetables and Flowers", "Espresso Brown", "Slate Gray", "Natural Wood"],
        (5.0, 380.0),
    ),
    "fashion": (
        ["Wrangler", "EttelLut", "Limsea", "Hanes", "NorthPeak", "Marlowe & Co",
         "UrbanThread", "Coofandy", "Ekouaer", "Zeagoo", "Dokotoo", "Angerella",
         "Levi's", "Dickies"],
        ["Quilted Puffer Vest", "Classic Denim Trucker Jacket", "Cable Knit Beanie Hat",
         "Slim Fit Stretch Chino Pants", "Oversized Flannel Shirt",
         "Faux Leather Crossbody Bag", "Merino Wool Crew Socks 4-Pack",
         "High Waisted Yoga Leggings with Pockets", "Linen Button Down Shirt",
         "Cashmere Blend Infinity Scarf", "Polarized Aviator Sunglasses",
         "Genuine Leather Belt with Removable Buckle", "Fleece Lined Hoodie",
         "Wrap Midi Dress Floral Print", "Ribbed Turtleneck Sweater",
         "Canvas Weekender Duffel Bag", "Silk Satin Pajama Set",
         "Waterproof Rain Jacket Packable", "Corduroy Baseball Cap",
         "Athletic Performance T-Shirt 3-Pack", "Wide Leg Palazzo Pants",
         "Touchscreen Winter Gloves", "Denim Overall Skirt", "Bomber Jacket Lightweight"],
        ["(Multiple Size/Color Options)", "for Women", "for Men", "Unisex",
         "Machine Washable", "S-3XL", "Black", "Navy Blue", "Heather Gray",
         "Vintage Wash", "with Adjustable Strap", "Regular and Plus Size"],
        (0.9, 65.0),
    ),
    "electronics": (
        ["Anker", "TechSurge", "Aukey", "VoltEdge", "Sabrent", "TP-Link",
         "Logitech", "NovaSound", "UGREEN", "Baseus", "Crucial", "SanDisk",
         "Wyze", "Jabra"],
        ["Wireless Earbuds with Charging Case", "USB-C Fast Charger 65W GaN",
         "Mechanical Gaming Keyboard RGB", "1080p Webcam with Privacy Cover",
         "Portable SSD 1TB USB 3.2", "Bluetooth Speaker Waterproof IPX7",
         "Smart WiFi Plug 4-Pack", "Noise Cancelling Over-Ear Headphones",
         "MicroSD Card 256GB with Adapter", "Ergonomic Vertical Wireless Mouse",
         "HDMI 2.1 Cable 6ft Braided", "Laptop Stand Adjustable Aluminum",
         "Ring Light 10in with Tripod", "Power Bank 20000mAh Dual Port",
         "WiFi 6 Router Dual Band", "Digital Photo Frame 10.1in",
         "Dash Cam Front and Rear 4K", "USB Microphone Cardioid Condenser",
         "Smart Watch Fitness Tracker", "Cable Management Sleeve 4-Pack",
         "Wireless Charging Pad 15W", "Mini Projector 1080p Supported",
         "Graphics Drawing Tablet 10x6in", "Clip-On Reading Light Rechargeable"],
        ["with 18-Month Warranty", "Plug and Play", "for PC Mac and Mobile",
         "Low Latency", "2024 Model", "Matte Black", "Space Gray",
         "with Carrying Case", "Certified Refurbished-Grade Tested", "Type-C"],
        (2.5, 420.0),
    ),
    "grocery": (
        ["Alpine Roast", "Nature's Path", "Bob's Red Mill", "Lakeport Pantry",
         "Meridian Farms", "Cascadia Harvest", "Tazo", "Kettle & Fire",
         "Wildway", "Nutiva", "Simple Mills", "Frontier Co-op"],
        ["Organic Whole Bean Coffee Medium Roast 2lb", "Cold Brew Concentrate 32oz",
         "Raw Wildflower Honey 16oz", "Extra Virgin Olive Oil First Press 500ml",
         "Dried Mango Slices No Sugar Added 20oz", "Matcha Green Tea Powder Ceremonial Grade",
         "Quinoa Tricolor Pre-Washed 4lb", "Dark Chocolate Covered Almonds 25oz",
         "Sea Salt Roasted Cashews 30oz", "Herbal Tea Sampler 48 Count",
         "Maple Syrup Grade A Amber 32oz", "Chia Seeds Organic 2lb",
         "Coconut Water Variety Pack 12ct", "Sourdough Crackers Rosemary 3-Pack",
         "Pasta Sauce Tomato Basil 4-Pack", "Almond Butter Creamy No Stir 16oz",
         "Sparkling Water Citrus Variety 24-Pack", "Granola Clusters Vanilla Pecan 22oz",
         "Smoked Paprika Spice Jar 4oz", "Vanilla Extract Pure Madagascar 4oz"],
        ["Non-GMO", "Gluten Free", "Small Batch", "Family Size", "Resealable Bag",
         "Pantry Staple", "Best By 2027", "Single Origin", "Fair Trade Certified"],
        (1.2, 48.0),
    ),
}

DESC_OPENERS = [
    "Up for auction: {name}.",
    "Listing my {core} — {reason}.",
    "You are bidding on a {cond_lower} {core}.",
    "{brand} {core}, {cond_lower} condition.",
    "Clean {core} from a smoke-free home.",
]
DESC_REASONS = [
    "downsizing and it has to go", "bought as a gift and never used",
    "upgrading so my loss is your gain", "closet clean-out",
    "moving across the country and can't take it",
    "received a duplicate", "estate find in great shape",
]
DESC_MIDDLE = {
    "New": ["Factory sealed, never opened.", "Brand new in original packaging with tags.",
            "Unopened — exactly as it left the store."],
    "Like New": ["Opened only to inspect, never used.", "Used once, indistinguishable from new.",
                 "Kept in its box since purchase; looks brand new."],
    "Very Good": ["Light use, no visible wear from arm's length.",
                  "Well cared for, only minor signs of handling.",
                  "Gently used and stored carefully."],
    "Good": ["Normal wear from regular use, fully functional.",
             "Some cosmetic marks but works exactly as intended.",
             "Honest used condition — see photos for details."],
    "Acceptable": ["Heavy cosmetic wear, priced accordingly.",
                   "Works fine but shows its age; great as a spare.",
                   "Scuffs and scratches throughout, still fully usable."],
}
DESC_CLOSERS = [
    "Ships within 1 business day of payment.",
    "Check my other listings to combine shipping.",
    "Message me with any questions before bidding.",
    "No reserve — highest bidder wins.",
    "Payment due within 48 hours of auction end.",
    "Happy to provide extra photos on request.",
]

MSG_QUESTIONS = [
    ("Question about: {name}", "Hi, is the {core} still available? Does it come from a pet-free home?"),
    ("Shipping question", "Would you consider combined shipping if I win this and another of your auctions for the {core}?"),
    ("Condition details?", "Can you share more photos of the {core}? Any flaws not visible in the listing pictures?"),
    ("Question about: {name}", "How old is the {core}? Was it stored indoors?"),
    ("Local pickup?", "I'm in {city} — is local pickup an option for the {core} to save on shipping?"),
    ("Authenticity check", "Do you have the original receipt or packaging for the {core}?"),
]
MSG_REPLIES = [
    "Thanks for your interest! Yes, happy to help — {detail}",
    "Good question. {detail} Let me know if you need anything else before bidding.",
    "Hi! {detail} Good luck with your bid!",
    "Sure thing — {detail}",
]
MSG_DETAILS = [
    "it comes from a clean, smoke-free home and I can add more photos tonight.",
    "I always combine shipping on multiple wins, usually saves a few dollars.",
    "it's about a year old and has been stored in a climate-controlled room.",
    "local pickup works for me on weekends, just message after the auction.",
    "I still have the original box and paperwork, they ship with it.",
    "there are no flaws beyond what's shown; condition grade is conservative.",
]

RATING_GOOD = [
    "Great seller! Item arrived exactly as described and was packed carefully.",
    "Fast shipping and honest condition grading. Would buy from again.",
    "Smooth transaction from start to finish. Recommended seller.",
    "Item was even nicer than the photos. Five stars.",
    "Quick to answer questions and shipped the same day. A+.",
    "Quick payment, great buyer. Pleasure to deal with.",
    "Excellent communication throughout the auction. Thanks!",
]
RATING_MID = [
    "Item as described but shipping took longer than expected.",
    "Decent transaction overall, packaging could have been better.",
    "Fair price, slow to respond to messages but delivered fine.",
]
RATING_BAD = [
    "Condition was graded a bit generously. Usable but disappointed.",
    "Arrived late and the box was damaged, item survived though.",
]

WATCH_NOTES = [
    "Waiting to see if the price stays low", "Possible birthday gift",
    "Compare against the other {core} listings", "Bid in the final hour",
    "Nice {core} — check seller feedback first", "Only if it stays under budget",
    "", "", "",
]

STATUSES = (["active"] * 9) + ["ended"]
NUM_BIDS_POP = [0, 1, 2, 3, 4, 5, 6, 7, 9, 12]
NUM_BIDS_W = [45, 20, 14, 9, 5, 3, 2, 1, 0.7, 0.3]

START_LO = datetime.datetime(2026, 4, 1)
START_HI = datetime.datetime(2026, 6, 19)   # existing listings start 2026-06-20+


def ts(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def hour_ts(dt):
    return dt.replace(minute=0, second=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def check_banned(*texts):
    for t in texts:
        low = str(t).lower()
        for w in BANNED:
            assert w not in low, f"banned word {w!r} in {t!r}"


def main():
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.row_factory = sqlite3.Row

    users = {r["id"]: dict(r) for r in db.execute(f"SELECT * FROM {T}_users")}
    sellers = [u for u in sorted(users) if u != 1]           # never user 1
    cities = [r[0] for r in db.execute(
        f"SELECT DISTINCT location FROM {T}_products WHERE location != ''")]
    shippings = [r[0] for r in db.execute(f"SELECT DISTINCT shipping FROM {T}_products")]
    policies = [r[0] for r in db.execute(f"SELECT DISTINCT return_policy FROM {T}_products")]
    conditions = [r[0] for r in db.execute(f"SELECT DISTINCT [condition] FROM {T}_products")]
    images = {c: [r[0] for r in db.execute(
        f"SELECT image_url FROM {T}_products WHERE category=? AND image_url != ''", (c,))]
        for c in CATEGORIES}
    existing_asins = {r[0] for r in db.execute(f"SELECT asin FROM {T}_products")}

    next_pid = db.execute(f"SELECT MAX(id)+1 FROM {T}_products").fetchone()[0]
    next_mid = db.execute(f"SELECT COALESCE(MAX(id),0)+1 FROM {T}_messages").fetchone()[0]
    next_rid = db.execute(f"SELECT COALESCE(MAX(id),0)+1 FROM {T}_ratings").fetchone()[0]
    next_wid = db.execute(f"SELECT COALESCE(MAX(id),0)+1 FROM {T}_watchlist").fetchone()[0]
    next_bid = db.execute(f"SELECT COALESCE(MAX(bid_id),0)+1 FROM {T}_bids").fetchone()[0]

    new = {"products": [], "bids": [], "messages": [], "ratings": [], "watchlist": []}

    def make_asin():
        while True:
            a = "B0" + "".join(rng.choices(string.ascii_uppercase + string.digits, k=8))
            if a not in existing_asins:
                existing_asins.add(a)
                return a

    # ---- products (+ per-listing bids) ---------------------------------
    for _ in range(N_PRODUCTS):
        cat = rng.choices(CATEGORIES, weights=CAT_WEIGHTS)[0]
        brands, cores, tails, price_r = VOCAB[cat]
        brand_name = rng.choice(brands)
        core = rng.choice(cores)
        name = f"{brand_name} {core} {rng.choice(tails)}"
        brand = rng.choice([f"Brand: {brand_name}", f"Visit the {brand_name} Store"])
        if rng.random() < 0.02:
            brand = ""
        cond = rng.choice(conditions)
        seller_id = rng.choice(sellers)
        seller = users[seller_id]

        # log-uniform start price within the category's observed band
        import math
        lo, hi = price_r
        start_price = round(math.exp(rng.uniform(math.log(lo), math.log(hi))), 2)
        num_bids = rng.choices(NUM_BIDS_POP, weights=NUM_BIDS_W)[0]
        current = start_price if num_bids == 0 else round(
            start_price * (1 + 0.12 * num_bids * rng.uniform(0.7, 1.3)), 2)
        buy_now = round(current * rng.uniform(1.35, 2.1), 2)
        reserve = round(start_price + (buy_now - start_price) * rng.uniform(0.3, 0.6), 2)

        start_dt = START_LO + datetime.timedelta(
            hours=rng.randint(0, int((START_HI - START_LO).total_seconds() // 3600)))
        start_dt = start_dt.replace(minute=0, second=0)
        end_dt = (start_dt + datetime.timedelta(days=rng.randint(3, 10),
                                                hours=rng.randint(0, 23))
                  ).replace(minute=0, second=0)

        status = rng.choice(STATUSES)
        winner = ""
        desc = " ".join([
            rng.choice(DESC_OPENERS).format(
                name=name, core=core, brand=brand_name,
                cond_lower=cond.lower(), reason=rng.choice(DESC_REASONS)),
            rng.choice(DESC_MIDDLE[cond]),
            rng.choice(DESC_CLOSERS),
        ])

        # bid history: exactly num_bids rows, max amount == current_price
        bidders_pool = [u for u in sellers if u != seller_id]
        listing_bids = []
        if num_bids:
            amounts = sorted(round(start_price + (current - start_price) * f, 2)
                             for f in [rng.uniform(0.05, 0.95) for _ in range(num_bids - 1)])
            amounts.append(current)
            # strictly increasing
            for i in range(1, len(amounts)):
                if amounts[i] <= amounts[i - 1]:
                    amounts[i] = round(amounts[i - 1] + 0.5, 2)
            current = amounts[-1]
            span = (end_dt - start_dt).total_seconds()
            offsets = sorted(rng.uniform(0.05, 0.98) for _ in range(num_bids))
            last_bidder = None
            for amt, off in zip(amounts, offsets):
                choices = [u for u in bidders_pool if u != last_bidder] or bidders_pool
                bidder = rng.choice(choices)
                last_bidder = bidder
                listing_bids.append({
                    "bid_id": next_bid, "listing_id": next_pid, "bidder_id": bidder,
                    "amount": amt,
                    "timestamp": ts(start_dt + datetime.timedelta(seconds=span * off)),
                    "auto_bid": 1 if rng.random() < 0.15 else 0,
                })
                next_bid += 1
            if status == "ended":
                winner = str(listing_bids[-1]["bidder_id"])
            buy_now = max(buy_now, round(current * 1.2, 2))

        check_banned(name, brand, desc, cat)
        row = {
            "id": next_pid, "asin": make_asin(), "name": name,
            "image_url": rng.choice(images[cat]), "category": cat, "brand": brand,
            "condition": cond, "description": desc,
            "start_price": start_price, "current_price": current,
            "buy_now_price": buy_now, "reserve_price": reserve,
            "num_bids": num_bids, "seller_id": seller_id,
            "seller_username": seller["username"],
            "seller_rating": seller["rating"],
            "auction_start": hour_ts(start_dt), "auction_end": hour_ts(end_dt),
            "status": status, "winner_id": winner,
            "shipping": rng.choice(shippings), "location": rng.choice(cities),
            "views": rng.randint(10, 500), "watchers": rng.randint(0, 20),
            "color_options": "[]", "size_options": "[]",
            "return_policy": rng.choice(policies),
            "payment_methods": '["Credit Card", "PayPal"]',
        }
        new["products"].append(row)
        new["bids"].extend(listing_bids)
        next_pid += 1

    prods = new["products"]

    # ---- messages (Q&A pairs about new listings, users 2..10 only) ------
    for _ in range(N_MESSAGE_PAIRS):
        p = rng.choice(prods)
        seller_id = p["seller_id"]
        asker = rng.choice([u for u in sellers if u != seller_id])
        _, cores, _, _ = VOCAB[p["category"]]
        core = p["name"].split(" ", 1)[1].rsplit(" ", 1)[0]  # strip brand+tail-ish
        subj_t, body_t = rng.choice(MSG_QUESTIONS)
        subject = subj_t.format(name=p["name"][:60], core=core)
        body = body_t.format(core=core, city=rng.choice(cities).split(",")[0], name=p["name"])
        start = datetime.datetime.strptime(p["auction_start"], "%Y-%m-%dT%H:%M:%SZ")
        end = datetime.datetime.strptime(p["auction_end"], "%Y-%m-%dT%H:%M:%SZ")
        q_dt = start + datetime.timedelta(
            seconds=rng.uniform(0.05, 0.8) * (end - start).total_seconds())
        r_dt = q_dt + datetime.timedelta(minutes=rng.randint(20, 600))
        reply = rng.choice(MSG_REPLIES).format(detail=rng.choice(MSG_DETAILS))
        check_banned(subject, body, reply)
        new["messages"].append({
            "id": next_mid, "listing_id": p["id"], "sender_id": asker,
            "receiver_id": seller_id, "subject": subject, "body": body,
            "timestamp": ts(q_dt), "read": 1})
        next_mid += 1
        new["messages"].append({
            "id": next_mid, "listing_id": p["id"], "sender_id": seller_id,
            "receiver_id": asker, "subject": f"Re: {subject}"[:120], "body": reply,
            "timestamp": ts(r_dt), "read": 1 if rng.random() < 0.8 else 0})
        next_mid += 1

    # ---- ratings (feedback on new listings, users 2..10 only) -----------
    for _ in range(N_RATINGS):
        p = rng.choice(prods)
        seller_id = p["seller_id"]
        buyer = int(p["winner_id"]) if p["winner_id"] else rng.choice(
            [u for u in sellers if u != seller_id])
        score = rng.choices([5, 4, 3, 2], weights=[62, 24, 10, 4])[0]
        comment = rng.choice(RATING_GOOD if score >= 4 else
                             RATING_MID if score == 3 else RATING_BAD)
        # half rate the seller, half rate the buyer
        if rng.random() < 0.5:
            rater, rated = buyer, seller_id
        else:
            rater, rated = seller_id, buyer
        end = datetime.datetime.strptime(p["auction_end"], "%Y-%m-%dT%H:%M:%SZ")
        r_dt = end + datetime.timedelta(days=rng.randint(1, 10),
                                        hours=rng.randint(0, 23))
        check_banned(comment)
        new["ratings"].append({
            "id": next_rid, "listing_id": p["id"], "rater_id": rater,
            "rated_user_id": rated, "score": score, "comment": comment,
            "timestamp": ts(r_dt.replace(minute=0, second=0))})
        next_rid += 1

    # ---- watchlist (users 2..10 only) -----------------------------------
    seen_pairs = set()
    while len(new["watchlist"]) < N_WATCHLIST:
        p = rng.choice(prods)
        uid = rng.choice([u for u in sellers if u != p["seller_id"]])
        if (uid, p["id"]) in seen_pairs:
            continue
        seen_pairs.add((uid, p["id"]))
        start = datetime.datetime.strptime(p["auction_start"], "%Y-%m-%dT%H:%M:%SZ")
        end = datetime.datetime.strptime(p["auction_end"], "%Y-%m-%dT%H:%M:%SZ")
        w_dt = start + datetime.timedelta(
            seconds=rng.uniform(0.02, 0.9) * (end - start).total_seconds())
        core = p["name"].split(" ", 1)[1].rsplit(" ", 1)[0]
        note = rng.choice(WATCH_NOTES).format(core=core)
        check_banned(note)
        new["watchlist"].append({
            "id": next_wid, "user_id": uid, "listing_id": p["id"],
            "added_at": ts(w_dt.replace(minute=0, second=0)), "notes": note})
        next_wid += 1

    for t, rows in new.items():
        print(f"{t}: +{len(rows)}")
    if dry:
        for t, rows in new.items():
            for r in rows[:2]:
                print(" ", json.dumps(r, default=str)[:220])
        return

    bdir = ROOT / "data" / "backups" / "auctions-p2p-marketplaces-expansion-2026-07-20"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "inserted_ids.json").write_text(json.dumps({
        "products": [r["id"] for r in new["products"]],
        "bids": [r["bid_id"] for r in new["bids"]],
        "messages": [r["id"] for r in new["messages"]],
        "ratings": [r["id"] for r in new["ratings"]],
        "watchlist": [r["id"] for r in new["watchlist"]],
    }, indent=1))

    for t, rows in new.items():
        if not rows:
            continue
        cols = list(rows[0].keys())
        sql = (f"INSERT INTO {T}_{t} ({', '.join('['+c+']' for c in cols)}) "
               f"VALUES ({', '.join('?' * len(cols))})")
        db.executemany(sql, [[r[c] for c in cols] for r in rows])

    # rebuild FTS for every touched table that has one
    for t in ("products", "messages", "ratings", "watchlist"):
        fts = f"fts_{T}_{t}"
        if db.execute("SELECT name FROM sqlite_master WHERE name=?", (fts,)).fetchone():
            db.execute(f"INSERT INTO [{fts}]([{fts}]) VALUES('rebuild')")
            print(f"rebuilt {fts}")
    db.commit()
    print(f"inserted; rollback ids at {bdir}/inserted_ids.json")


if __name__ == "__main__":
    main()
