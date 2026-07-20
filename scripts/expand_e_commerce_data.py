"""Expand e-commerce (ShopHub) base data: users + product reviews.

The site ships with 500 products but only 17 reviews and 5 users, which makes
review-related content trivially sparse. This adds deterministic (seeded)
synthetic shopper accounts and customer reviews attached to the real catalog:

- ~40 new shopper users (root_user_id 0, like other synthetic-user expansions).
- ~4,500 reviews spread across the existing 500 products (roughly 9 each).

Insert-only — existing rows are never touched; NO product rows are added or
modified, so the catalog, the Quick Categories checkbox list, and the
max-price filter results are byte-identical to before. Review counts per
product are capped at the product's stored `total_reviews` figure where one
exists (so the on-site "Customer Reviews (N)" list never exceeds the stored
review count shown in the product header), and the sampled rating mix is
centred on the product's stored `average_rating` so the two never contradict.

Inserted ids are recorded in
data/backups/e-commerce-expansion-2026-07-20/inserted_ids.json for rollback.

Usage: python scripts/expand_e_commerce_data.py [--dry-run]
"""
import json
import random
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "trimmed_miniweb.db"

rng = random.Random(20260720)

# ---------------------------------------------------------------------------
# New shopper users (username/email/password follow existing conventions;
# cart/wishlist/orders stay '[]' like every existing row; root_user_id 0
# marks synthetic users, matching prior expansions e.g. dating_users).
# ---------------------------------------------------------------------------

NEW_USER_NAMES = [
    ("Priya", "Sharma"), ("David", "Petrov"), ("Elena", "Vasquez"),
    ("James", "Osei"), ("Mei", "Wong"), ("Omar", "Haddad"),
    ("Hannah", "Lindqvist"), ("Tobias", "Berg"), ("Grace", "Nakamura"),
    ("Felix", "Moreau"), ("Amara", "Diallo"), ("Lucas", "Ferreira"),
    ("Ingrid", "Sorensen"), ("Ravi", "Patel"), ("Carmen", "Delgado"),
    ("Noah", "Fitzgerald"), ("Yuki", "Tanaka"), ("Samuel", "Adeyemi"),
    ("Clara", "Novak"), ("Mateo", "Rojas"), ("Aisha", "Rahman"),
    ("Henrik", "Dahl"), ("Paula", "Kowalski"), ("Dmitri", "Ivanov"),
    ("Leila", "Nasser"), ("Owen", "Gallagher"), ("Bianca", "Costa"),
    ("Kofi", "Mensah"), ("Sofia", "Lindberg"), ("Erik", "Johansson"),
    ("Nadia", "Petrova"), ("Marco", "Ricci"), ("Tessa", "Vandermeer"),
    ("Jasper", "Whitfield"), ("Rosa", "Herrera"), ("Kenji", "Yamamoto"),
    ("Freya", "Olsen"), ("Andre", "Boateng"), ("Lena", "Fischer"),
    ("Gabriel", "Moreno"),
]

# ---------------------------------------------------------------------------
# Review text generation
# ---------------------------------------------------------------------------

TITLES = {
    5: ["Absolutely love it", "Exceeded my expectations", "Perfect {kw}",
        "Couldn't be happier", "Best purchase this year", "Five stars, easily",
        "Exactly what I was looking for", "Outstanding quality",
        "Buy it, you won't regret it", "Fantastic value for the money",
        "My new favorite", "Works flawlessly", "Impressed from day one",
        "Great {kw}, great price", "Second one I've bought"],
    4: ["Very good with minor quibbles", "Solid {kw}", "Happy with this purchase",
        "Good quality overall", "Almost perfect", "Does the job well",
        "Better than expected", "Nice {kw} for the price", "Would buy again",
        "Reliable so far", "Good, not quite great", "Pleasantly surprised"],
    3: ["It's okay", "Decent but unremarkable", "Middle of the road",
        "Gets the job done, barely", "Mixed feelings", "Average {kw}",
        "Fine for occasional use", "Not bad, not great",
        "Expected a bit more"],
    2: ["Disappointed", "Not as described", "Quality could be better",
        "Wouldn't recommend", "Meh at best", "Had higher hopes",
        "Falls short", "Below average {kw}"],
    1: ["Save your money", "Very poor quality", "Stopped working quickly",
        "Regret this purchase", "Complete letdown", "Do not buy",
        "Arrived damaged and went downhill from there"],
}

OPENERS = {
    5: ["I've been using this {kw} for {dur} now and it has been flawless.",
        "This is hands down the best {kw} I've owned.",
        "Ordered this after a lot of research and it did not disappoint.",
        "I was skeptical at first, but this won me over within days.",
        "Bought this as an upgrade from an older model and the difference is night and day.",
        "This arrived quickly and was exactly as pictured."],
    4: ["I've had this {kw} for {dur} and it's been very dependable.",
        "Solid product overall — a few small things keep it from five stars.",
        "This does almost everything I hoped it would.",
        "Good value for the price point, no major complaints.",
        "Picked this up on a recommendation and I'm mostly pleased."],
    3: ["This {kw} is fine, but nothing special.",
        "It works, though I expected a little more at this price.",
        "After {dur} of use, my feelings are mixed.",
        "Not bad, but there are better options out there."],
    2: ["I wanted to like this {kw}, but it has too many issues.",
        "Quality feels below what the listing suggests.",
        "After {dur}, problems started showing up."],
    1: ["This was a waste of money, plain and simple.",
        "Mine failed after {dur} of light use.",
        "The product I received looks nothing like the photos."],
}

MIDDLES = {
    5: ["The build quality is excellent and every detail feels well thought out.",
        "Setup took minutes and it has worked perfectly ever since.",
        "The materials feel premium and it holds up to daily use without a scratch.",
        "Performance is consistent and it does exactly what the description promises.",
        "The {brand} quality really shows — sturdy, well finished, and reliable.",
        "It handles everyday wear and tear better than pricier alternatives I've tried."],
    4: ["Build quality is good, though the finish shows fingerprints easily.",
        "Everything works as advertised; the instructions could be clearer though.",
        "It performs well day to day, with only the occasional hiccup.",
        "Materials feel durable, if a touch lighter than I expected.",
        "It's comfortable to use, though the sizing runs slightly small."],
    3: ["It functions, but the build feels a bit flimsy in places.",
        "Performance is inconsistent — great some days, sluggish others.",
        "The design is nice, but practicality took a back seat.",
        "Some parts feel cheaper than the product photos suggest."],
    2: ["The stitching started coming loose within weeks.",
        "It scratches and marks far too easily for normal use.",
        "The listed measurements don't match what actually arrived.",
        "Customer support was slow to respond when I reached out about the defect."],
    1: ["It broke during the second use and can't be repaired.",
        "The unit arrived with a defect and the replacement was no better.",
        "The materials are so thin I can't imagine it lasting a month."],
}

CLOSERS = {
    5: ["Highly recommend to anyone on the fence.",
        "Already recommended it to two friends.",
        "Will definitely buy from {brand} again.",
        "Worth every penny.",
        "If it ever wears out, I'll buy the exact same one."],
    4: ["Recommended, with the small caveats above.",
        "For this price, it's hard to complain.",
        "Would purchase again, though I'd watch for a sale.",
        "A safe pick if you need a dependable {kw}."],
    3: ["Might work better for someone with lighter needs.",
        "I'd shop around before settling on this one.",
        "It stays, but I wouldn't buy it twice."],
    2: ["I'll be looking at other brands next time.",
        "Returning it if the issues get worse.",
        "Can't recommend it at this price."],
    1: ["Requested a refund the same week.",
        "Avoid this one — there are far better options.",
        "One star is generous."],
}

DURATIONS = ["two weeks", "a month", "about six weeks", "three months",
             "a couple of months", "almost a year", "several months"]

STOPWORDS = {"the", "a", "an", "for", "of", "and", "with", "'s"}


def _keyword(product):
    """Short lowercase noun for the product, derived from its query field."""
    q = (product["query"] or "").strip()
    if not q:
        return "product"
    words = [w for w in re.split(r"[\s,&]+", q) if w and w.lower() not in STOPWORDS]
    kw = " ".join(words[-2:]) if len(words) > 1 else (words[0] if words else "product")
    kw = kw.lower().rstrip("s") if kw.lower().endswith("ies") is False else kw.lower()
    return kw or "product"


def _clean_brand(brand_str):
    if not brand_str:
        return ""
    brand_str = brand_str.strip()
    if brand_str.startswith("Brand: "):
        return brand_str[7:].strip()
    if brand_str.startswith("Visit the "):
        brand_str = brand_str[10:]
        if brand_str.endswith(" Store"):
            brand_str = brand_str[:-6]
        return brand_str.strip()
    return brand_str


# rating-mix buckets keyed by stored average_rating (weights for 5,4,3,2,1)
def _rating_weights(avg):
    if avg is None:
        return [55, 25, 10, 5, 5]        # typical ~4.2 J-shape
    if avg >= 4.5:
        return [72, 18, 5, 3, 2]
    if avg >= 4.0:
        return [55, 25, 10, 5, 5]
    if avg >= 3.5:
        return [38, 27, 15, 10, 10]
    if avg >= 3.0:
        return [25, 25, 20, 15, 15]
    return [12, 18, 22, 22, 26]


def _rand_date():
    """YYYY-MM-DD between 2024-01-05 and 2026-06-15 (never newer than the
    newest existing review, 2026-06-15)."""
    start = 738890  # datetime.date(2024, 1, 5).toordinal()
    end = 739782    # datetime.date(2026, 6, 15).toordinal()
    import datetime
    return datetime.date.fromordinal(rng.randint(start, end)).isoformat()


def _make_review(rid, product, user_ids):
    avg = product["avg"]
    rating = rng.choices([5, 4, 3, 2, 1], weights=_rating_weights(avg))[0]
    kw = product["kw"]
    brand = product["brand_clean"] or "this brand"
    dur = rng.choice(DURATIONS)
    title = rng.choice(TITLES[rating]).format(kw=kw)
    parts = [rng.choice(OPENERS[rating]).format(kw=kw, dur=dur, brand=brand)]
    parts.append(rng.choice(MIDDLES[rating]).format(kw=kw, brand=brand))
    if rng.random() < 0.85:
        parts.append(rng.choice(CLOSERS[rating]).format(kw=kw, brand=brand))
    return {
        "id": rid,
        "product_asin": product["asin"],
        "product_name": product["name"],
        "user_id": rng.choice(user_ids),
        "rating": rating,
        "title": title,
        "content": " ".join(parts),
        "date": _rand_date(),
    }


def main():
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.row_factory = sqlite3.Row

    # ---- users ----------------------------------------------------------
    existing_users = [dict(r) for r in db.execute(
        "SELECT * FROM e_commerce_users ORDER BY id")]
    existing_usernames = {u["username"] for u in existing_users}
    next_uid = max(u["id"] for u in existing_users) + 1

    new_users = []
    for first, last in NEW_USER_NAMES:
        uname = f"shopper_{first[0].lower()}{last.lower()}"
        if uname in existing_usernames:
            uname = f"shopper_{first.lower()}{last[0].lower()}"
        existing_usernames.add(uname)
        new_users.append({
            "id": next_uid,
            "root_user_id": 0,
            "username": uname,
            "password": f"pass{rng.randint(100, 999)}",
            "name": f"{first} {last}",
            "email": f"{first.lower()}.{last.lower()}@gmail.com",
            "cart": "[]",
            "wishlist": "[]",
            "orders": "[]",
        })
        next_uid += 1

    # Reviewer pool: all non-primary users (never user 1 / Alex Rivera).
    reviewer_ids = [u["id"] for u in existing_users if u["id"] != 1] + \
                   [u["id"] for u in new_users]

    # ---- reviews --------------------------------------------------------
    products = []
    for r in db.execute(
            "SELECT asin, name, brand, query, average_rating, total_reviews "
            "FROM e_commerce_products ORDER BY asin"):
        m = re.search(r"(\d+\.?\d*)", r["average_rating"] or "")
        avg = float(m.group(1)) if m else None
        m = re.search(r"(\d+)", (r["total_reviews"] or "").replace(",", ""))
        stored_count = int(m.group(1)) if m else None
        products.append({
            "asin": r["asin"], "name": r["name"], "query": r["query"],
            "brand_clean": _clean_brand(r["brand"]), "kw": None,
            "avg": avg, "stored_count": stored_count,
        })
    for p in products:
        p["kw"] = _keyword(p)

    next_rid = db.execute(
        "SELECT COALESCE(MAX(id), 0) + 1 FROM e_commerce_reviews").fetchone()[0]
    existing_rev_counts = dict(db.execute(
        "SELECT product_asin, COUNT(*) FROM e_commerce_reviews GROUP BY product_asin"))

    new_reviews = []
    for p in products:
        desired = rng.randint(8, 15)
        cap = p["stored_count"]
        already = existing_rev_counts.get(p["asin"], 0)
        n = desired if cap is None else max(0, min(desired, cap) - already)
        for _ in range(n):
            new_reviews.append(_make_review(next_rid, p, reviewer_ids))
            next_rid += 1

    base_total = sum(db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                     for t in ("e_commerce_products", "e_commerce_reviews",
                               "e_commerce_users"))
    projected = base_total + len(new_users) + len(new_reviews)
    print(f"users: +{len(new_users)}")
    print(f"reviews: +{len(new_reviews)}")
    print(f"projected site total: {base_total} -> {projected}")
    assert projected >= 5000, "projected total below 5000 target"

    if dry:
        for u in new_users[:2]:
            print(" user:", json.dumps(u)[:150])
        for r in new_reviews[:4]:
            print(" review:", json.dumps(r)[:220])
        # per-rating distribution sanity
        from collections import Counter
        print(" rating mix:", Counter(r["rating"] for r in new_reviews))
        return

    bdir = ROOT / "data" / "backups" / "e-commerce-expansion-2026-07-20"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "inserted_ids.json").write_text(json.dumps({
        "e_commerce_users": [u["id"] for u in new_users],
        "e_commerce_reviews": [r["id"] for r in new_reviews],
    }, indent=1))

    ucols = list(new_users[0].keys())
    db.executemany(
        f"INSERT INTO e_commerce_users ({', '.join(ucols)}) "
        f"VALUES ({', '.join('?' * len(ucols))})",
        [[u[c] for c in ucols] for u in new_users])
    rcols = list(new_reviews[0].keys())
    db.executemany(
        f"INSERT INTO e_commerce_reviews ({', '.join(rcols)}) "
        f"VALUES ({', '.join('?' * len(rcols))})",
        [[r[c] for c in rcols] for r in new_reviews])

    # sync the external-content FTS index for reviews
    db.execute("INSERT INTO fts_e_commerce_reviews(fts_e_commerce_reviews) "
               "VALUES('rebuild')")
    db.commit()
    print(f"inserted; rollback ids at {bdir}/inserted_ids.json")


if __name__ == "__main__":
    main()
