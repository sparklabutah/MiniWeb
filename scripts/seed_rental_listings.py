#!/usr/bin/env python
"""Seed permanent rental inventory into real_estate_buy_rent_listings.

The site advertises Buy AND Rent, but ships with 5,000 for_sale/ready_to_build
listings and zero rentals. This script generates deterministic, realistic
rental rows (status='for_rent' and 'rented') as PERMANENT base data.

Design contract:
  * Writes directly to data/trimmed_miniweb.db via sqlite3 + commit (NOT the
    per-session overlay used by app.db.save_*).
  * IDEMPOTENT: deletes only rows with id > 5000 (the max existing id is
    exactly 5000, all seeded rows this script owns), then re-inserts. Re-running
    never touches the original 5,000 and never doubles counts.
  * DETERMINISTIC: all "random" choices come from zlib.crc32 over a per-row
    salt. No random.random, no time-based values -> fully reproducible.
  * Reuses the real (city, state, zip) geography and listed_date range that
    already exist in the table, so rentals sit in the same market as sales.
"""
import json
import os
import sqlite3
import zlib
from datetime import date, timedelta

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "trimmed_miniweb.db",
)
TABLE = "real_estate_buy_rent_listings"
BASE_ID = 5000          # nothing seeded here has id > this; we own everything above
N_FOR_RENT = 420
N_RENTED = 40

FEATURE_POOL = [
    "In-unit Laundry", "Parking", "Pet Friendly", "Balcony", "Dishwasher",
    "Gym", "Pool", "Central AC", "Hardwood Floors", "Walk-in Closet",
    "Stainless Appliances", "Elevator",
]

# rent base band per bedroom count: (low, high) before city-tier scaling
RENT_BAND = {
    0: (1100, 1800),   # studio
    1: (1500, 2600),
    2: (2000, 3800),
    3: (2800, 5000),
    4: (3500, 6500),
}
SQFT_BAND = {
    0: (450, 650),
    1: (650, 950),
    2: (950, 1350),
    3: (1350, 1800),
    4: (1800, 2400),
}


def h(salt, i):
    """Deterministic 32-bit hash for row i under a named salt."""
    return zlib.crc32(f"{salt}:{i}".encode("utf-8"))


def pick(salt, i, seq):
    return seq[h(salt, i) % len(seq)]


def span(salt, i, lo, hi):
    """Deterministic integer in [lo, hi]."""
    return lo + (h(salt, i) % (hi - lo + 1))


def fmt_baths(b):
    return str(int(b)) if float(b).is_integer() else str(b)


def build_geo_pool(cur):
    """Weighted (city, state, zip) tuples drawn from the real distribution."""
    rows = cur.execute(
        f"SELECT city, state, zip, COUNT(*) c FROM [{TABLE}] "
        f"GROUP BY city, state, zip"
    ).fetchall()
    pool = []
    for city, state, zc, c in rows:
        pool.extend([(city, state, zc)] * c)   # repeat by frequency = weighting
    pool.sort()  # stable ordering so index-based sampling is reproducible
    return pool


def build_city_multipliers(cur):
    """Rent multiplier per (city, state) derived from local sale prices.

    Expensive markets (New York City, Miami, Naples...) scale up; cheap ones
    (Detroit, Erie...) scale down. Clamped to a sane band.
    """
    natl = cur.execute(
        f"SELECT AVG(price) FROM [{TABLE}] WHERE status='for_sale' AND price>0"
    ).fetchone()[0] or 500000.0
    rows = cur.execute(
        f"SELECT city, state, AVG(price) FROM [{TABLE}] "
        f"WHERE status='for_sale' AND price>0 GROUP BY city, state"
    ).fetchall()
    mult = {}
    for city, state, avg in rows:
        ratio = (avg or natl) / natl
        # dampen the spread (sale-price ratios are wilder than rent ratios)
        m = 0.85 + (ratio - 1.0) * 0.35
        mult[(city, state)] = max(0.72, min(1.85, m))
    return mult


def make_row(i, status, geo_pool, city_mult):
    """Build one listing tuple for the given 0-based index i."""
    rid = BASE_ID + 1 + i
    city, state, zc = geo_pool[h("geo", i) % len(geo_pool)]

    # bedrooms: skew toward 1-2BR (0 => studio)
    bedrooms = pick("beds", i, [0, 1, 1, 1, 2, 2, 2, 3, 3, 4])

    if bedrooms == 0:
        ptype = "Studio"
    else:
        ptype = pick("type", i,
                     ["Apartment", "Apartment", "Apartment",
                      "Condo", "Condo", "Townhouse", "House"])

    # bathrooms consistent with size
    if bedrooms <= 1:
        bathrooms = 1.0
    elif bedrooms == 2:
        bathrooms = pick("bath", i, [1.0, 1.5, 2.0])
    elif bedrooms == 3:
        bathrooms = pick("bath", i, [2.0, 2.0, 2.5])
    else:
        bathrooms = pick("bath", i, [2.0, 2.5, 3.0])

    lo, hi = SQFT_BAND[bedrooms]
    sqft = span("sqft", i, lo, hi)

    lot_sqft = 0 if ptype in ("Apartment", "Condo", "Studio") \
        else span("lot", i, 1500, 6000)

    year_built = span("year", i, 1950, 2022)

    # rent: base band position scaled by city tier, rounded to $25
    rlo, rhi = RENT_BAND[bedrooms]
    base = span("rent", i, rlo, rhi)
    mult = city_mult.get((city, state), 1.0)
    rent = int(round(base * mult / 25.0)) * 25
    rent = max(900, min(9000, rent))

    # features: deterministic 2-4 item subset
    n_feat = span("nfeat", i, 2, 4)
    start = h("fstart", i) % len(FEATURE_POOL)
    feats = []
    step = 1 + (h("fstep", i) % 3)
    idx = start
    while len(feats) < n_feat:
        f = FEATURE_POOL[idx % len(FEATURE_POOL)]
        if f not in feats:
            feats.append(f)
        idx += step
    features = json.dumps(feats)

    # title
    if ptype == "Studio":
        title = f"Studio Apartment for Rent in {city}, {state}"
    else:
        title = (f"{bedrooms} Bed / {fmt_baths(bathrooms)} Bath {ptype} "
                 f"for Rent in {city}, {state}")

    # description
    beds_phrase = "studio apartment" if bedrooms == 0 \
        else f"{bedrooms}-bedroom {ptype.lower()}"
    desc = (
        f"Available for rent at ${rent:,}/month, this {beds_phrase} "
        f"offers {sqft:,} sqft with {fmt_baths(bathrooms)} bath"
        f"{'s' if bathrooms != 1.0 else ''} in {city}, {state}. "
        f"Highlights include {feats[0].lower()} and {feats[1].lower()}. "
        f"Contact the listing agent to schedule a tour."
    )

    photos_count = span("photos", i, 3, 8)
    agent_id = 1 + (h("agent", i) % 8)

    return (
        rid, title, f"{city} {state}", city, state, zc, ptype, status,
        0, rent, bedrooms, bathrooms, sqft, lot_sqft, year_built,
        desc, features, agent_id, None, photos_count,
    )  # listed_date filled in by caller (needs date range)


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # sanity: never clobber the original inventory
    max_id = cur.execute(f"SELECT MAX(id) FROM [{TABLE}]").fetchone()[0]
    assert max_id is not None, "table is empty?"

    # IDEMPOTENT reset: only rows this script owns
    cur.execute(f"DELETE FROM [{TABLE}] WHERE id > ?", (BASE_ID,))

    geo_pool = build_geo_pool(cur)
    city_mult = build_city_multipliers(cur)

    # listed_date range from existing rows (site dates are intentionally static)
    dmin, dmax = cur.execute(
        f"SELECT MIN(listed_date), MAX(listed_date) FROM [{TABLE}]"
    ).fetchone()
    d0 = date.fromisoformat(dmin)
    span_days = (date.fromisoformat(dmax) - d0).days

    total = N_FOR_RENT + N_RENTED
    rows = []
    for i in range(total):
        status = "for_rent" if i < N_FOR_RENT else "rented"
        row = list(make_row(i, status, geo_pool, city_mult))
        ld = (d0 + timedelta(days=h("date", i) % (span_days + 1))).isoformat()
        row[18] = ld
        rows.append(tuple(row))

    cur.executemany(
        f"INSERT INTO [{TABLE}] "
        f"(id, title, address, city, state, zip, type, status, price, "
        f" rent_monthly, bedrooms, bathrooms, sqft, lot_sqft, year_built, "
        f" description, features, agent_id, listed_date, photos_count) "
        f"VALUES ({','.join('?' * 20)})",
        rows,
    )
    conn.commit()

    # report
    fr = cur.execute(
        f"SELECT COUNT(*) FROM [{TABLE}] WHERE status='for_rent'").fetchone()[0]
    rt = cur.execute(
        f"SELECT COUNT(*) FROM [{TABLE}] WHERE status='rented'").fetchone()[0]
    fs = cur.execute(
        f"SELECT COUNT(*) FROM [{TABLE}] WHERE status='for_sale'").fetchone()[0]
    tot = cur.execute(f"SELECT COUNT(*) FROM [{TABLE}]").fetchone()[0]
    rmin, rmax = cur.execute(
        f"SELECT MIN(rent_monthly), MAX(rent_monthly) FROM [{TABLE}] "
        f"WHERE status IN ('for_rent','rented')").fetchone()
    print(f"Inserted rentals -> for_rent={fr}, rented={rt}")
    print(f"for_sale (unchanged)={fs}, total={tot}")
    print(f"rent_monthly range: ${rmin:,} - ${rmax:,}")
    conn.close()


if __name__ == "__main__":
    main()
