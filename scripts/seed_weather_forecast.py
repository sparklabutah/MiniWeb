#!/usr/bin/env python3
"""Seed a per-location 7-DAY FORECAST for the weather site.

Background
----------
`ce78cdb` made CURRENT and HOURLY conditions per-location, and the route +
schema expect `weather_forecast` to be keyed by `location_id` too. But the
shipped/restored `weather_forecast` table is the OLD single global series
(7 rows, no `location_id` column). The route filters by `location_id`, so for
every location the 7-day forecast came back EMPTY.

This fills it in, mirroring seed_weather_conditions.py:

  * Adds a `location_id` column (idempotent) and assigns the existing 7 rows
    to the default location (Lakeport, WA) — their values are left untouched.
  * For every other location, generates its own 7-day forecast over the SAME
    calendar window, anchored to that location's CURRENT temperature and cloud
    level (via compute_current) and to the region's weekly weather pattern
    (the Lakeport template: warm -> mid-week rainy dip -> warm). Continental,
    drier cities run hotter with less precip and a bigger day/night swing;
    damp coastal cities the reverse.

Design constraints (same as seed_weather_conditions.py)
------------------
  * Writes to the permanent base DB (data/trimmed_miniweb.db) via sqlite3.
  * Fully DETERMINISTIC (seeded per location+day) and IDEMPOTENT.
  * The existing default Lakeport rows are left exactly as-is.

Run:  ~/.conda/envs/miniweb/bin/python scripts/seed_weather_forecast.py
"""

import pathlib
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Reuse the exact per-location climate model used for current/hourly.
from scripts.seed_weather_conditions import (
    DEFAULT_NAME, DEFAULT_ID, compute_current, _is_continental, _salt, _jitter,
)

DB_PATH = ROOT / "data" / "trimmed_miniweb.db"


def _day_conditions(cloud, precip):
    """Map a daily cloud level + precip chance to a conditions string."""
    if precip >= 60:
        return "Showers" if precip < 72 else "Light Rain"
    if cloud <= 0:
        return "Sunny"
    if cloud == 1:
        return "Mostly Sunny" if precip < 15 else "Partly Cloudy"
    if cloud == 2:
        return "Partly Cloudy" if precip < 25 else "Overcast"
    return "Overcast"


def build_forecast(loc, template):
    """Return 7 forecast row-dicts for a location, from the Lakeport template.

    `template` is the list of the 7 default (Lakeport) rows. Each city keeps the
    regional week-shape but shifted to its own climate baseline.
    """
    name, lng = loc["name"], loc["lng"]
    continental = _is_continental(lng)
    cur = compute_current(loc)
    cloud = cur["_cloud"]

    # Day-0 high anchored to the city's current temp (hourly peak = cur+4),
    # and the base template's day-0 high used as the reference to shift from.
    base_high0 = template[0]["high_f"]
    city_high0 = cur["temp_f"] + 4
    # Continental interiors swing more between high and low.
    swing_bonus = 4 if continental else 0

    rows = []
    for i, t in enumerate(template):
        # Preserve the regional day-to-day pattern, shift to the city baseline.
        high = city_high0 + (t["high_f"] - base_high0) + _jitter(name, f"fh{i}", 2)
        day_range = (t["high_f"] - t["low_f"]) + swing_bonus
        low = high - day_range + _jitter(name, f"fl{i}", 1)

        # Precip: start from the regional template, damp it for dry/continental
        # cities and lift it for wet coastal ones. Clamp to [0, 95].
        precip = t["precip_pct"]
        precip += (cloud - 1) * 10          # drier locations (cloud 0) -> less
        if continental:
            precip -= 15
        precip += _jitter(name, f"fp{i}", 5)
        precip = max(0, min(95, int(round(precip))))

        conditions = _day_conditions(cloud, precip)

        wind = max(3, int(round(cur["wind_mph"] + (t["wind_mph"] - 8) * 0.5
                                 + _jitter(name, f"fw{i}", 2))))
        humidity = max(20, min(96, int(round(cur["humidity"]
                                             + (t["humidity"] - 62) * 0.5
                                             + _jitter(name, f"fhu{i}", 3)))))

        rows.append({
            "day": t["day"], "date": t["date"],
            "high_f": int(round(high)), "low_f": int(round(low)),
            "conditions": conditions, "precip_pct": precip,
            "wind_mph": wind, "humidity": humidity,
        })
    return rows


def main():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1. Add location_id column if missing (idempotent).
    cols = {r["name"] for r in cur.execute("PRAGMA table_info(weather_forecast)")}
    if "location_id" not in cols:
        cur.execute("ALTER TABLE weather_forecast ADD COLUMN location_id INTEGER DEFAULT 1")

    # 2. The existing rows are Lakeport's — pin them to the default location.
    template = [dict(r) for r in cur.execute(
        "SELECT day, date, high_f, low_f, conditions, precip_pct, wind_mph, humidity "
        "FROM weather_forecast WHERE row_id BETWEEN 1 AND 7 ORDER BY row_id")]
    if len(template) != 7:
        raise SystemExit(f"Expected 7 default forecast rows, found {len(template)}. Aborting.")
    cur.execute("UPDATE weather_forecast SET location_id = ? WHERE row_id BETWEEN 1 AND 7",
                (DEFAULT_ID,))

    # 3. Reseed all non-default per-location forecasts.
    cur.execute("DELETE FROM weather_forecast WHERE location_id <> ?", (DEFAULT_ID,))
    locations = [dict(r) for r in cur.execute(
        "SELECT id, name, lat, lng, is_default FROM weather_locations ORDER BY id")]
    non_default = [l for l in locations if l["name"] != DEFAULT_NAME]

    added = 0
    for loc in non_default:
        for i, row in enumerate(build_forecast(loc, template)):
            cur.execute(
                "INSERT INTO weather_forecast "
                "(row_id, day, date, high_f, low_f, conditions, precip_pct, wind_mph, humidity, location_id) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (loc["id"] * 100 + i, row["day"], row["date"], row["high_f"], row["low_f"],
                 row["conditions"], row["precip_pct"], row["wind_mph"], row["humidity"], loc["id"]))
            added += 1

    conn.commit()
    total = cur.execute("SELECT COUNT(*) FROM weather_forecast").fetchone()[0]
    per_loc = cur.execute(
        "SELECT COUNT(DISTINCT location_id) n FROM weather_forecast").fetchone()["n"]
    conn.close()
    print(f"weather_forecast: inserted {added} non-default rows "
          f"({len(non_default)} locations x 7 days).")
    print(f"Total {total} rows across {per_loc} locations "
          f"(incl. the untouched {DEFAULT_NAME} week).")


if __name__ == "__main__":
    main()
