"""Give every weather location its own 7-day forecast.

Root problem: `weather_forecast` had no location column, so all 18 locations
rendered the same 7 Lakeport rows. This adds a `location_id` column, pins the
existing 7 rows to Lakeport (id=1) so the default view is unchanged, and
generates a seeded, climate-plausible 7-day forecast for the other 17
locations (same day/date grid, temps/conditions varied by regional climate).

Insert-only for the new locations; the original 7 rows keep their row_id and
values. Idempotent: refuses to double-insert if per-location rows already exist.

Usage:
  python scripts/weather_per_location_forecast.py --dry-run
  python scripts/weather_per_location_forecast.py
"""
import argparse
import random
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "trimmed_miniweb.db"
SEED = 20260728

# Regional climate profiles applied as offsets to the Lakeport baseline.
# (high_off, low_off, precip_mult, precip_off, humidity_off, wind_off, drier)
#   drier=True nudges rainy conditions toward dry ones (inland east of Cascades).
COASTAL = dict(high_off=-4, low_off=+2, precip_mult=1.4, precip_off=12,
               humidity_off=+10, wind_off=+5, drier=False)
INLAND = dict(high_off=+11, low_off=-7, precip_mult=0.4, precip_off=-15,
              humidity_off=-18, wind_off=-1, drier=True)
VALLEY = dict(high_off=+3, low_off=-1, precip_mult=0.9, precip_off=-2,
              humidity_off=-3, wind_off=0, drier=False)

# location_id -> profile (id 1 = Lakeport = baseline, untouched)
PROFILES = {
    2: VALLEY,    # Seattle, WA
    3: VALLEY,    # Portland, OR
    4: VALLEY,    # Tacoma, WA
    5: VALLEY,    # Olympia, WA
    6: COASTAL,   # Bellingham, WA
    7: INLAND,    # Spokane, WA
    8: VALLEY,    # Eugene, OR
    9: COASTAL,   # Vancouver, BC
    10: INLAND,   # Bend, OR
    11: VALLEY,   # Everett, WA
    12: VALLEY,   # Salem, OR
    13: INLAND,   # Yakima, WA
    14: INLAND,   # Boise, ID
    15: COASTAL,  # Victoria, BC
    16: COASTAL,  # Astoria, OR
    17: COASTAL,  # Port Angeles, WA
    18: INLAND,   # Wenatchee, WA
}

# When a profile is "drier", wet conditions collapse toward these dry ones.
_DRY_MAP = {
    "Light Rain": "Partly Cloudy",
    "Showers": "Mostly Sunny",
    "Overcast": "Partly Cloudy",
    "Rain": "Overcast",
}
# When a profile is coastal/wet, sunny days cloud over a little.
_WET_MAP = {
    "Sunny": "Partly Cloudy",
    "Mostly Sunny": "Partly Cloudy",
    "Partly Cloudy": "Overcast",
}


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def build_rows(baseline):
    """Return list of (location_id, day, date, high, low, cond, precip, wind, hum)."""
    rng = random.Random(SEED)
    out = []
    for loc_id, prof in PROFILES.items():
        for b in baseline:
            high = b["high_f"] + prof["high_off"] + rng.randint(-3, 3)
            low = b["low_f"] + prof["low_off"] + rng.randint(-3, 3)
            if low >= high:                       # keep low strictly below high
                low = high - rng.randint(6, 12)
            precip = int(b["precip_pct"] * prof["precip_mult"]) + prof["precip_off"]
            precip = clamp(precip + rng.randint(-5, 5), 0, 100)
            humidity = clamp(b["humidity"] + prof["humidity_off"] + rng.randint(-4, 4),
                             20, 98)
            wind = clamp(b["wind_mph"] + prof["wind_off"] + rng.randint(-2, 2), 1, 35)
            cond = b["conditions"]
            if prof["drier"]:
                cond = _DRY_MAP.get(cond, cond)
                if precip < 15 and cond in ("Overcast",):
                    cond = "Mostly Sunny"
            elif prof["precip_mult"] > 1.2:       # coastal/wet
                if precip > 40:
                    cond = _WET_MAP.get(cond, cond)
            out.append((loc_id, b["day"], b["date"], high, low, cond,
                        precip, wind, humidity))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    con = sqlite3.connect(str(DB), timeout=60)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cols = [r["name"] for r in cur.execute("PRAGMA table_info(weather_forecast)")]
    has_loc = "location_id" in cols

    baseline = [dict(r) for r in
                cur.execute("SELECT * FROM weather_forecast ORDER BY row_id LIMIT 7")]
    if len(baseline) < 7:
        raise SystemExit(f"expected >=7 baseline rows, found {len(baseline)}")

    rows = build_rows(baseline)
    print(f"baseline days: {[b['day'] for b in baseline]}")
    print(f"location_id column present: {has_loc}")
    print(f"generating {len(rows)} rows for {len(PROFILES)} locations")
    # sample
    for r in rows[:3] + rows[-2:]:
        print("  ", r)

    if args.dry_run:
        print("\n[dry-run] no changes written")
        con.close()
        return

    stamp = datetime.now().strftime("%Y%m%d")
    bdir = DB.parent / "backups" / f"weather-forecast-{stamp}"
    bdir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DB, bdir / "trimmed_miniweb.db.bak")
    print(f"backup -> {bdir/'trimmed_miniweb.db.bak'}")

    if not has_loc:
        cur.execute("ALTER TABLE weather_forecast ADD COLUMN location_id INTEGER DEFAULT 1")
        cur.execute("UPDATE weather_forecast SET location_id=1 WHERE location_id IS NULL")
        print("added location_id column; pinned existing rows to Lakeport (id=1)")

    # idempotency guard: bail if non-default location rows already exist
    n_extra = cur.execute(
        "SELECT COUNT(*) FROM weather_forecast WHERE location_id != 1").fetchone()[0]
    if n_extra:
        print(f"already have {n_extra} non-default rows; skipping insert")
        con.commit()
        con.close()
        return

    cur.executemany(
        "INSERT INTO weather_forecast "
        "(location_id, day, date, high_f, low_f, conditions, precip_pct, wind_mph, humidity) "
        "VALUES (?,?,?,?,?,?,?,?,?)", rows)
    con.commit()

    total = cur.execute("SELECT COUNT(*) FROM weather_forecast").fetchone()[0]
    distinct = cur.execute(
        "SELECT COUNT(DISTINCT location_id) FROM weather_forecast").fetchone()[0]
    print(f"inserted {len(rows)} rows; forecast now {total} rows across "
          f"{distinct} locations")
    con.close()


if __name__ == "__main__":
    main()
