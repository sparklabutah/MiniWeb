"""Expand Lakeport Weather base data (historical daily records, locations, users).

The site ships with only 80 rows total (30 historical days, 10 locations,
5 users, plus the small forecast/hourly/alerts/current tables). This extends
the Lakeport, WA daily historical record back to 2012-10-01 (~4,990 additional
days ending 2026-05-27, the day before the existing 30-day window starts),
adds 8 more Pacific-Northwest saved locations and 5 more portal users.

The synthetic climate is seasonally coherent for a Puget Sound lowland city:
a sinusoidal annual temperature cycle (cool wet winters, warm dry summers)
with an AR(1) day-to-day anomaly so warm/cold and wet spells persist for a
few days, rain probability peaking November-March, high_f > low_f always,
avg_temp_f = round((high+low)/2) half-up, and conditions drawn only from the
site's existing vocabulary (Sunny, Mostly Sunny, Partly Cloudy, Mostly Cloudy,
Overcast, Light Rain, Showers, Rain) consistent with each day's precip_in.

Insert-only -- existing rows are never touched; all new historical dates are
strictly OLDER than the existing 2026-05-28..2026-06-26 window, so the
forecast/hourly/current "today" views and the default 30-day history view
are unchanged. Inserted primary keys are recorded in
data/backups/weather-expansion-2026-07-20/inserted_ids.json for rollback.

After inserting, the FTS5 indexes for the touched tables
(fts_weather_historical, fts_weather_locations) are rebuilt.

Usage: ~/.conda/envs/miniweb/bin/python scripts/expand_weather_data.py [--dry-run]
"""
import datetime
import json
import math
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "trimmed_miniweb.db"

rng = random.Random(20260720)

HIST_START = datetime.date(2012, 10, 1)
HIST_END = datetime.date(2026, 5, 27)   # day before existing min date 2026-05-28

DRY_CONDITIONS = ["Sunny", "Mostly Sunny", "Partly Cloudy", "Mostly Cloudy", "Overcast"]

NEW_LOCATIONS = [
    ("Everett, WA", 47.98, -122.20),
    ("Salem, OR", 44.94, -123.04),
    ("Yakima, WA", 46.60, -120.51),
    ("Boise, ID", 43.62, -116.21),
    ("Victoria, BC", 48.43, -123.37),
    ("Astoria, OR", 46.19, -123.83),
    ("Port Angeles, WA", 48.12, -123.43),
    ("Wenatchee, WA", 47.42, -120.31),
]

# (username, name, password, default_location, saved_locations)
NEW_USERS = [
    ("dfarrell", "Dana Farrell", "stormwatch7", 1, [1, 4, 11]),
    ("rokafor", "Ruth Okafor", "drizzle22", 2, [2, 1, 13]),
    ("lsandoval", "Luis Sandoval", "sunbreaks9", 1, [1, 5, 12, 15]),
    ("hkim", "Hana Kim", "cloudcover4", 3, [3, 1, 16]),
    ("pwhitman", "Paul Whitman", "barometer1", 1, [1, 7, 14, 18]),
]


def seasonal(doy, mean, amp):
    """Annual sinusoid peaking around late July (doy ~205)."""
    return mean + amp * math.sin(2 * math.pi * (doy - 114) / 365.25)


def gen_historical(next_rowid):
    rows = []
    anom = 0.0          # AR(1) temperature anomaly, degrees F
    wet_prev = False    # rain spells persist
    day = HIST_START
    while day <= HIST_END:
        doy = day.timetuple().tm_yday
        anom = 0.72 * anom + rng.gauss(0, 2.6)
        high_mean = seasonal(doy, 61.5, 15.5)      # Jan ~46, late Jul ~77
        spread = seasonal(doy, 14.0, 4.0)          # winter ~10, summer ~18
        p_rain = min(0.85, max(0.05, 0.38 - 0.27 * math.sin(
            2 * math.pi * (doy - 114) / 365.25)))  # Jan ~0.65, Jul-Aug ~0.11
        if wet_prev:
            p_rain = min(0.9, p_rain + 0.22)       # wet spells cluster

        wet = rng.random() < p_rain
        if wet:
            season_scale = 0.10 + 0.16 * p_rain
            precip = round(min(2.5, rng.expovariate(1 / (season_scale * 1.6)) + 0.02), 2)
            precip = max(precip, 0.02)
            high = round(high_mean + anom - rng.uniform(2, 6))
            spread_today = max(6.0, spread - rng.uniform(2, 5))
            if precip >= 0.30:
                cond = rng.choices(["Rain", "Showers"], weights=[75, 25])[0]
            elif precip >= 0.12:
                cond = rng.choices(["Light Rain", "Showers", "Rain"], weights=[45, 35, 20])[0]
            else:
                cond = rng.choices(["Light Rain", "Showers"], weights=[70, 30])[0]
        else:
            cloud = rng.random()
            # dry winter days still lean cloudy; summer leans sunny
            cloud_bias = p_rain  # 0.05 (summer) .. 0.85 (winter)
            mix = 0.5 * cloud + 0.5 * cloud_bias
            if mix < 0.22:
                cond = "Sunny"
            elif mix < 0.38:
                cond = "Mostly Sunny"
            elif mix < 0.55:
                cond = "Partly Cloudy"
            elif mix < 0.72:
                cond = "Mostly Cloudy"
            else:
                cond = "Overcast"
            # trace drizzle on the cloudiest dry-condition days (matches existing
            # rows: Mostly Cloudy up to 0.10", Overcast up to 0.08")
            if cond in ("Mostly Cloudy", "Overcast") and rng.random() < 0.25:
                precip = round(rng.uniform(0.01, 0.09), 2)
            else:
                precip = 0.0
            sun_boost = {"Sunny": 2.5, "Mostly Sunny": 1.5, "Partly Cloudy": 0.5,
                         "Mostly Cloudy": -0.5, "Overcast": -1.5}[cond]
            high = round(high_mean + anom + sun_boost)
            spread_today = spread + rng.uniform(-1, 2)

        low = high - max(6, round(spread_today + rng.gauss(0, 1.2)))
        avg = (high + low + 1) // 2  # half-up, matches existing rows
        rows.append({
            "row_id": next_rowid,
            "date": day.isoformat(),
            "high_f": int(high),
            "low_f": int(low),
            "avg_temp_f": int(avg),
            "precip_in": float(precip),
            "conditions": cond,
        })
        next_rowid += 1
        wet_prev = wet
        day += datetime.timedelta(days=1)
    return rows


def main():
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.row_factory = sqlite3.Row

    # sanity: never collide with existing data
    existing_min = db.execute("SELECT MIN(date) FROM weather_historical").fetchone()[0]
    assert HIST_END.isoformat() < existing_min, "new dates must predate existing window"
    max_hist_rowid = db.execute("SELECT MAX(row_id) FROM weather_historical").fetchone()[0]
    max_loc_id = db.execute("SELECT MAX(id) FROM weather_locations").fetchone()[0]
    max_user_id = db.execute("SELECT MAX(id) FROM weather_users").fetchone()[0]
    existing_loc_names = {r[0].lower() for r in db.execute("SELECT name FROM weather_locations")}
    existing_usernames = {r[0] for r in db.execute("SELECT username FROM weather_users")}

    historical = gen_historical(max_hist_rowid + 1)

    locations = []
    for i, (name, lat, lng) in enumerate(NEW_LOCATIONS):
        assert name.lower() not in existing_loc_names, name
        locations.append({"id": max_loc_id + 1 + i, "name": name,
                          "lat": lat, "lng": lng, "is_default": 0})
    loc_ids = {l["id"] for l in locations} | \
        {r[0] for r in db.execute("SELECT id FROM weather_locations")}

    users = []
    for i, (username, name, password, default_loc, saved) in enumerate(NEW_USERS):
        assert username not in existing_usernames, username
        assert default_loc in loc_ids and all(s in loc_ids for s in saved)
        assert default_loc in saved
        users.append({
            "id": max_user_id + 1 + i,
            "username": username,
            "name": name,
            "email": f"{username}@lakeport.example.com",
            "password": password,
            "default_location": default_loc,
            "saved_locations": json.dumps(saved),
        })

    new = {"historical": historical, "locations": locations, "users": users}
    for t, rows in new.items():
        print(f"{t}: +{len(rows)}")
    wet_days = sum(1 for r in historical if r["precip_in"] > 0)
    print(f"  historical range {historical[0]['date']}..{historical[-1]['date']}, "
          f"{wet_days} wet days ({100 * wet_days // len(historical)}%), "
          f"high range {min(r['high_f'] for r in historical)}..{max(r['high_f'] for r in historical)}")
    assert all(r["high_f"] > r["low_f"] for r in historical)
    assert all(r["low_f"] <= r["avg_temp_f"] <= r["high_f"] for r in historical)
    assert all(0 <= r["precip_in"] <= 2.5 for r in historical)

    if dry:
        for t, rows in new.items():
            for r in rows[:3]:
                print(" ", json.dumps(r))
        print("(dry run -- nothing written)")
        return

    bdir = ROOT / "data" / "backups" / "weather-expansion-2026-07-20"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "inserted_ids.json").write_text(json.dumps({
        "weather_historical": {"pk": "row_id", "ids": [r["row_id"] for r in historical]},
        "weather_locations": {"pk": "id", "ids": [r["id"] for r in locations]},
        "weather_users": {"pk": "id", "ids": [r["id"] for r in users]},
    }, indent=1))

    for table, rows in (("weather_historical", historical),
                        ("weather_locations", locations),
                        ("weather_users", users)):
        cols = list(rows[0].keys())
        sql = (f"INSERT INTO [{table}] ({', '.join(cols)}) "
               f"VALUES ({', '.join('?' * len(cols))})")
        db.executemany(sql, [[r[c] for c in cols] for r in rows])

    # keep FTS5 indexes of touched tables in sync (external-content rebuild)
    db.execute("INSERT INTO fts_weather_historical(fts_weather_historical) VALUES('rebuild')")
    db.execute("INSERT INTO fts_weather_locations(fts_weather_locations) VALUES('rebuild')")
    db.commit()

    total = 0
    for t in ("alerts", "current", "forecast", "historical", "hourly", "locations", "users"):
        total += db.execute(f"SELECT COUNT(*) FROM weather_{t}").fetchone()[0]
    print(f"inserted; weather site total now {total} rows; "
          f"rollback ids at {bdir}/inserted_ids.json")


if __name__ == "__main__":
    main()
