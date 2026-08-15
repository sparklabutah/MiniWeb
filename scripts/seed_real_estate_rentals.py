"""Seed rental listings for real-estate-buy-rent (the site advertised for-sale AND
rent, but 0 listings had status=for_rent, so the Rent tab was empty).

Deterministic + idempotent: flips condo/townhouse/multi-family listings whose id%4==0
to status=for_rent with a realistic monthly rent (~0.5% of price/mo, $1200-$4800).
Re-run safe (same set every time). Writes the base listings table.
Run: ~/.conda/envs/miniweb/bin/python scratchpad/seed_real_estate_rentals.py
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from app import create_app  # noqa: E402

app = create_app()
with app.test_request_context():
    from app import db
    conn = db._get_conn()
    table = db.get_table_name("real-estate-buy-rent", "listings")
    rows = conn.execute(
        f"SELECT id, price, bedrooms FROM [{table}] "
        f"WHERE type IN ('Condo','Townhouse','Multi-Family') AND (id % 4) = 0"
    ).fetchall()
    n = 0
    for lid, price, beds in rows:
        price = price or 0
        rent = int(round((price * 0.005) / 25) * 25)      # ~0.5%/mo, to nearest $25
        rent = max(1200, min(rent, 4800))
        if not rent or rent < 1200:
            rent = 1200 + (beds or 1) * 400
        conn.execute(f"UPDATE [{table}] SET status='for_rent', rent_monthly=? WHERE id=?",
                     (rent, lid))
        n += 1
    conn.commit()
    total = conn.execute(
        f"SELECT COUNT(*) FROM [{table}] WHERE status='for_rent' AND rent_monthly>0"
    ).fetchone()[0]
    sample = conn.execute(
        f"SELECT title, type, rent_monthly FROM [{table}] WHERE status='for_rent' LIMIT 3"
    ).fetchall()
    print(f"converted {n} listings; total for_rent w/ rent: {total}")
    for s in sample:
        print("  ", s[0][:40], "|", s[1], "| $%d/mo" % s[2])
