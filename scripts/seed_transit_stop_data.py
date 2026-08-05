#!/usr/bin/env python3
"""Fill in the missing per-stop data for the transit-directions site.

Every stop had name/address/coords/zone but `routes_served` and `amenities`
were empty (`[]`) for all 451 stops — so 77% of stops showed no routes and
none showed amenities. The 6 curated routes (routes_transit: 1,2,3,4,5,6X)
are what the whole UI displays and filters against, but their Lakeport
street-name "major_stops" don't match the real stop names, so there's no
authentic stop<->route mapping to recover.

This assigns each stop a spatially-coherent set of those 6 routes using
CORRIDOR LINES through the city (so nearby stops share routes and each route
reads as a real corridor), and generates deterministic, plausible amenities.
Both are written to the base table (JSON-encoded), and the stops FTS index is
rebuilt if present. Deterministic + idempotent.

Run: ~/.conda/envs/miniweb/bin/python scripts/seed_transit_stop_data.py
"""
import json
import math
import pathlib
import sqlite3
import sys
import zlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app import create_app
import app.db as adb

create_app()
DB = adb._DB_PATH
STOPS = "transit_directions_stops"

# --- geometry helpers (equirectangular metres about the city centre) --------
def to_xy(lat, lng, clat, clng):
    x = math.radians(lng - clng) * math.cos(math.radians(clat)) * 6371000
    y = math.radians(lat - clat) * 6371000
    return x, y


def perp_dist_to_line(px, py, dx, dy):
    """Perp distance from point to a line through origin with unit dir (dx,dy)."""
    return abs(px * (-dy) + py * dx)


# --- amenities --------------------------------------------------------------
AMENITIES = ["shelter", "bench", "lighting", "real_time_display", "bike_rack",
             "trash_can", "ticket_machine", "accessibility_ramp",
             "security_camera", "route_map", "bike_share", "heated_shelter"]


def _rng(stop_id, key):
    return zlib.crc32(f"{stop_id}|{key}".encode())


def gen_amenities(stop, n_routes):
    name = (stop["name"] or "").lower()
    is_hub = any(k in name for k in ("transit center", "station", "marina",
                                     "medical center", "campus", "hub"))
    sid = stop["id"]
    # more amenities at hubs / busy multi-route stops
    if is_hub:
        count = 6 + _rng(sid, "n") % 4          # 6-9
    elif n_routes >= 3:
        count = 4 + _rng(sid, "n") % 3          # 4-6
    elif n_routes >= 1:
        count = 2 + _rng(sid, "n") % 3          # 2-4
    else:
        count = 1 + _rng(sid, "n") % 2          # 1-2
    # deterministic shuffle of the pool, take `count`
    pool = sorted(AMENITIES, key=lambda a: _rng(sid, a))
    chosen = pool[:count]
    # accessible stops always advertise the ramp; hubs always have shelter+sign
    if str(stop.get("wheelchair_accessible")) in ("1", "True", "true") and "accessibility_ramp" not in chosen:
        chosen.append("accessibility_ramp")
    if is_hub:
        for must in ("shelter", "real_time_display", "route_map"):
            if must not in chosen:
                chosen.append(must)
    # stable order for readability
    return [a for a in AMENITIES if a in chosen]


def main():
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    stops = [dict(r) for r in cur.execute(
        f"SELECT id, name, lat, lng FROM {STOPS}")]
    if not stops:
        print("no stops found"); return

    lats = [float(s["lat"]) for s in stops]
    lngs = [float(s["lng"]) for s in stops]
    clat, clng = (min(lats) + max(lats)) / 2, (min(lngs) + max(lngs)) / 2

    # Route corridors: (route_number, kind, params). Directions are unit
    # vectors in local (east, north). "line" = straight corridor through an
    # offset origin; "loop" = ring; "express" = hub + far corner only.
    def unit(a):  # bearing degrees -> unit vector (E,N)
        r = math.radians(a); return math.sin(r), math.cos(r)
    corridors = [
        ("1",  "line",  {"ox": 0,     "oy": 0,    "dir": unit(90),  "band": 1100, "cap": 9000}),  # E-W Lakeshore
        ("2",  "line",  {"ox": 0,     "oy": 0,    "dir": unit(135), "band": 950,  "cap": 9000}),  # NW-SE Crosstown
        ("3",  "line",  {"ox": -1800, "oy": 0,    "dir": unit(0),   "band": 950,  "cap": 9000}),  # N-S Cedar (west)
        ("4",  "line",  {"ox": 1500,  "oy": 0,    "dir": unit(45),  "band": 950,  "cap": 9000}),  # NE-SW Oak/Medical (east)
        ("5",  "loop",  {"r0": 1400,  "r1": 3600, "band": 700}),                                    # ring / loop
        ("6X", "express", {"hub_r": 900, "far_bearing": 30, "far_r0": 5500}),                       # express
    ]

    def routes_for(stop):
        x, y = to_xy(float(stop["lat"]), float(stop["lng"]), clat, clng)
        served, dists = [], {}
        for num, kind, p in corridors:
            if kind == "line":
                px, py = x - p["ox"], y - p["oy"]
                d = perp_dist_to_line(px, py, p["dir"][0], p["dir"][1])
                dists[num] = d
                # within band and within the corridor's longitudinal extent
                along = px * p["dir"][0] + py * p["dir"][1]
                if d <= p["band"] and abs(along) <= p["cap"]:
                    served.append(num)
            elif kind == "loop":
                r = math.hypot(x, y)
                ring = min(abs(r - p["r0"]), abs(r - p["r1"]))
                dists[num] = ring
                if p["r0"] - p["band"] <= r <= p["r1"] + p["band"]:
                    served.append(num)
            elif kind == "express":
                r = math.hypot(x, y)
                brg = (math.degrees(math.atan2(x, y)) + 360) % 360
                dists[num] = r if r < p["hub_r"] else 1e9
                near_hub = r <= p["hub_r"]
                far = r >= p["far_r0"] and abs((brg - p["far_bearing"] + 180) % 360 - 180) < 40
                if near_hub or far:
                    served.append(num)
        # floor: every stop gets at least its nearest line/loop route
        if not served:
            served = [min(dists, key=dists.get)]
        # cap at 4 for realism, keep canonical order
        order = ["1", "2", "3", "4", "5", "6X"]
        served = [n for n in order if n in served][:4]
        return served

    n_upd = 0
    for s in stops:
        served = routes_for(s)
        amen = gen_amenities(s, len(served))
        cur.execute(
            f"UPDATE {STOPS} SET routes_served=?, amenities=? WHERE id=?",
            (json.dumps(served), json.dumps(amen), s["id"]))
        n_upd += 1
    conn.commit()

    # rebuild FTS if the stops table is full-text indexed
    fts = "fts_" + STOPS
    try:
        cur.execute(f"INSERT INTO {fts}({fts}) VALUES('rebuild')")
        conn.commit()
        print("rebuilt FTS index")
    except sqlite3.Error:
        pass

    # report
    from collections import Counter
    rows = [json.loads(r["routes_served"]) for r in cur.execute(f"SELECT routes_served FROM {STOPS}")]
    perstop = Counter(len(r) for r in rows)
    perroute = Counter(n for r in rows for n in r)
    conn.close()
    print(f"Updated {n_upd} stops.")
    print("routes-per-stop:", dict(sorted(perstop.items())))
    print("stops-per-route:", {k: perroute[k] for k in ['1','2','3','4','5','6X']})


if __name__ == "__main__":
    main()
