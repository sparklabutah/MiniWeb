#!/usr/bin/env python3
"""Seed per-location CURRENT conditions and HOURLY forecasts for the weather site.

Background
----------
All 18 weather locations already have their own 7-day forecast (weather_forecast,
keyed by location_id).  But CURRENT conditions (weather_current) and the HOURLY
forecast (weather_hourly) were single shared series, so every city rendered the
same temp / humidity / wind.  This script fills in real, per-location data:

  * weather_current  -- one row per location (keyed by the location NAME),
                        with climate-plausible values that VARY by latitude,
                        longitude (continental vs coastal) and a per-location salt.
  * weather_hourly   -- 24 rows per location (keyed by a new location_id column),
                        a smooth diurnal curve whose afternoon peak is consistent
                        with that location's current temperature.

Design constraints
------------------
  * Writes go to the permanent base DB (data/trimmed_miniweb.db) via sqlite3,
    NOT db.save_* (which only writes a per-session overlay).
  * Fully DETERMINISTIC (seeded by location id / name via zlib.crc32) and
    IDEMPOTENT -- re-running does not duplicate rows or change values.
  * The existing default Lakeport, WA rows are left exactly as-is.
  * weather_historical is intentionally left as a single shared series.

Run:  ~/.conda/envs/miniweb/bin/python scripts/seed_weather_conditions.py
"""

import math
import pathlib
import sqlite3
import zlib

DB_PATH = pathlib.Path(__file__).resolve().parent.parent / "data" / "trimmed_miniweb.db"

DEFAULT_NAME = "Lakeport, WA"
DEFAULT_ID = 1

# Reference climate anchor: Lakeport (lat ~47.52) currently reads 68 F.
REF_LAT = 47.52
REF_TEMP = 68

WIND_DIRS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def _salt(name, key):
    """Deterministic non-negative int derived from the location name + a field key."""
    return zlib.crc32(f"{name}|{key}".encode("utf-8"))


def _jitter(name, key, spread):
    """Deterministic symmetric jitter in [-spread, +spread]."""
    return (_salt(name, key) % (2 * spread + 1)) - spread


def _is_continental(lng):
    """East of the Cascade crest -> drier, hotter summers, bigger diurnal swing."""
    return lng > -121.5


def compute_current(loc):
    """Return a dict of weather_current field values for a location dict."""
    name, lat, lng = loc["name"], loc["lat"], loc["lng"]
    continental = _is_continental(lng)

    # Temperature: colder further north, warmer south; continental interior hotter.
    temp_f = (REF_TEMP
              + (REF_LAT - lat) * 3.2
              + (6 if continental else 0)
              + _jitter(name, "temp", 3))
    temp_f = int(round(temp_f))
    temp_c = int(round((temp_f - 32) * 5 / 9))

    # Humidity: continental interior is drier; coastal/high-lat is damper.
    humidity = (62
                - (22 if continental else 0)
                + (lat - REF_LAT) * 2.0
                + _jitter(name, "humid", 5))
    humidity = int(max(20, min(96, round(humidity))))

    # Cloudiness level from humidity (0 clear .. 3 wet) -> conditions string.
    if continental and humidity < 45:
        cloud = 0
    elif humidity < 58:
        cloud = 1
    elif humidity < 74:
        cloud = 2
    else:
        cloud = 3
    conditions = _current_conditions(name, cloud)

    # Wind: coastal/strait stations breezier; deterministic base + jitter.
    coastal_windy = lng < -123.3 or "Astoria" in name or "Angeles" in name
    wind_mph = 6 + (_salt(name, "wind") % 9) + (4 if coastal_windy else 0)
    wind_mph = int(min(24, wind_mph))
    wind_dir = WIND_DIRS[_salt(name, "dir") % len(WIND_DIRS)]

    # UV: higher south and when skies are clear.
    uv_index = int(max(1, min(10, round(6 + (REF_LAT - lat) * 0.6 - cloud * 1.2
                                        + _jitter(name, "uv", 1)))))

    # Air quality: mostly Good; hot continental interior can tip to Moderate.
    if continental and temp_f >= 88:
        air_quality = "Moderate" if _salt(name, "aq") % 2 else "Good"
    else:
        air_quality = "Good"

    # Feels-like: humid heat feels hotter, breezy cool feels colder.
    feels = temp_f
    if temp_f >= 80 and humidity >= 55:
        feels += 2 + (humidity - 55) // 12
    elif temp_f <= 60 and wind_mph >= 10:
        feels -= 1 + (wind_mph - 10) // 6
    feels_like_f = int(feels)

    # Visibility: reduced when wet/humid.
    visibility_mi = 10 - (3 if cloud >= 3 else 0) - (_salt(name, "vis") % 2)
    visibility_mi = int(max(4, visibility_mi))

    # Pressure: deterministic within a plausible band; wet systems a touch lower.
    pressure_inhg = round(30.15 - cloud * 0.08 + (_salt(name, "pres") % 21 - 10) * 0.01, 2)

    return {
        "temp_f": temp_f,
        "temp_c": temp_c,
        "humidity": humidity,
        "wind_mph": wind_mph,
        "wind_dir": wind_dir,
        "conditions": conditions,
        "uv_index": uv_index,
        "air_quality": air_quality,
        "feels_like_f": feels_like_f,
        "visibility_mi": visibility_mi,
        "pressure_inhg": pressure_inhg,
        "updated": "2026-06-27T14:00:00",
        "_cloud": cloud,
    }


def _current_conditions(name, cloud):
    if cloud == 0:
        return "Sunny" if _salt(name, "cond") % 2 else "Mostly Sunny"
    if cloud == 1:
        return "Partly Cloudy"
    if cloud == 2:
        return "Mostly Cloudy" if _salt(name, "cond") % 2 else "Overcast"
    return "Light Rain" if _salt(name, "cond") % 2 else "Showers"


def compute_hourly(loc, cur):
    """Return a list of 24 hourly row dicts consistent with the current temp."""
    name, lng = loc["name"], loc["lng"]
    continental = _is_continental(lng)
    cur_temp = cur["temp_f"]
    cloud = cur["_cloud"]

    # Diurnal curve: afternoon peak ~= current temp + 4, pre-dawn min lower.
    high = cur_temp + 4
    low = cur_temp - (14 + (4 if continental else 0))
    mean = (high + low) / 2.0
    amp = (high - low) / 2.0

    rows = []
    for i in range(24):
        # cos peaks at hour 15 (3 PM), min at hour 3 (3 AM)
        temp_f = int(round(mean + amp * math.cos(2 * math.pi * (i - 15) / 24.0)))
        is_night = i < 6 or i >= 21

        cond, precip = _hourly_condition(name, cloud, i, is_night)

        # Humidity rises overnight, dips mid-afternoon; anchored to current.
        humidity = int(max(20, min(98, cur["humidity"]
                                   + int(8 * math.cos(2 * math.pi * (i - 3) / 24.0))
                                   + _jitter(name, f"hh{i}", 2))))

        # Wind mild overnight, up in the afternoon; anchored to current wind.
        wind_mph = int(max(1, round(cur["wind_mph"]
                                    - 2 + 3 * max(0.0, math.cos(2 * math.pi * (i - 15) / 24.0)))))

        rows.append({
            "hour": _hour_label(i),
            "temp_f": temp_f,
            "conditions": cond,
            "precip_pct": precip,
            "wind_mph": wind_mph,
            "humidity": humidity,
        })
    return rows


def _hour_label(i):
    ampm = "AM" if i < 12 else "PM"
    h12 = i % 12
    if h12 == 0:
        h12 = 12
    return f"{h12}:00 {ampm}"


def _hourly_condition(name, cloud, i, is_night):
    """Per-hour (conditions, precip_pct) driven by cloud level + time of day."""
    afternoon = 11 <= i <= 17
    if cloud == 0:  # sunny location
        if is_night:
            return ("Clear" if _salt(name, f"n{i}") % 3 else "Mostly Clear"), 0
        return ("Sunny" if not afternoon else "Mostly Sunny"), 0
    if cloud == 1:  # partly cloudy
        if is_night:
            return "Mostly Clear", 0
        return "Partly Cloudy", (5 if afternoon else 0)
    if cloud == 2:  # mostly cloudy
        if is_night:
            return "Cloudy", 0
        return ("Mostly Cloudy" if not afternoon else "Overcast"), (10 if afternoon else 5)
    # cloud == 3: wet
    if is_night:
        return "Cloudy", (20 if _salt(name, f"r{i}") % 2 else 10)
    if afternoon:
        return ("Showers" if _salt(name, f"r{i}") % 2 else "Light Rain"), 35
    return "Mostly Cloudy", 20


def main():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    locations = [dict(r) for r in cur.execute(
        "SELECT id, name, lat, lng, is_default FROM weather_locations ORDER BY id")]
    non_default = [l for l in locations if l["name"] != DEFAULT_NAME]

    # --- weather_current ------------------------------------------------
    # Manage only non-default rows; leave the existing Lakeport row untouched.
    cur.execute("DELETE FROM weather_current WHERE location <> ?", (DEFAULT_NAME,))
    current_added = 0
    for loc in non_default:
        c = compute_current(loc)
        cur.execute(
            "INSERT INTO weather_current "
            "(row_id, location, temp_f, temp_c, humidity, wind_mph, wind_dir, "
            " conditions, uv_index, air_quality, feels_like_f, visibility_mi, "
            " pressure_inhg, updated) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (loc["id"], loc["name"], c["temp_f"], c["temp_c"], c["humidity"],
             c["wind_mph"], c["wind_dir"], c["conditions"], c["uv_index"],
             c["air_quality"], c["feels_like_f"], c["visibility_mi"],
             c["pressure_inhg"], c["updated"]))
        current_added += 1

    # --- weather_hourly -------------------------------------------------
    # 1. Add location_id column if it does not exist yet (idempotent).
    hcols = {r["name"] for r in cur.execute("PRAGMA table_info(weather_hourly)")}
    if "location_id" not in hcols:
        cur.execute("ALTER TABLE weather_hourly ADD COLUMN location_id INTEGER DEFAULT 1")
    # 2. Ensure the original 24 rows belong to the default location.
    cur.execute("UPDATE weather_hourly SET location_id = ? WHERE location_id IS NULL",
                (DEFAULT_ID,))
    cur.execute("UPDATE weather_hourly SET location_id = ? "
                "WHERE row_id BETWEEN 1 AND 24", (DEFAULT_ID,))
    # 3. Reseed the per-location rows (everything except the default series).
    cur.execute("DELETE FROM weather_hourly WHERE location_id <> ?", (DEFAULT_ID,))
    hourly_added = 0
    for loc in non_default:
        c = compute_current(loc)
        for i, row in enumerate(compute_hourly(loc, c)):
            cur.execute(
                "INSERT INTO weather_hourly "
                "(row_id, hour, temp_f, conditions, precip_pct, wind_mph, humidity, location_id) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (loc["id"] * 100 + i, row["hour"], row["temp_f"], row["conditions"],
                 row["precip_pct"], row["wind_mph"], row["humidity"], loc["id"]))
            hourly_added += 1

    conn.commit()

    cur_total = cur.execute("SELECT COUNT(*) FROM weather_current").fetchone()[0]
    hourly_total = cur.execute("SELECT COUNT(*) FROM weather_hourly").fetchone()[0]
    conn.close()

    print(f"weather_current: inserted {current_added} non-default rows "
          f"(total {cur_total}, incl. the untouched {DEFAULT_NAME} row)")
    print(f"weather_hourly:  inserted {hourly_added} non-default rows "
          f"(total {hourly_total}, incl. 24 default rows)")


if __name__ == "__main__":
    main()
