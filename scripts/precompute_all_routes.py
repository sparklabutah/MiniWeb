#!/usr/bin/env python3
"""Pre-compute OSRM routes between ALL map locations.

~200 locations × 200 = 40K pairs × 2 modes = ~80K routes.
Run on compute node:

    srun --ntasks=1 --mem=8G --time=4:00:00 --account=kmarino --partition=notchpeak \
        python scripts/precompute_all_routes.py

    # Or smaller test
    python scripts/precompute_all_routes.py --limit 20
"""

import argparse
import json
import os
import pathlib
import sqlite3
import time
import urllib.request

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
DB_PATH = os.environ.get("MINIWEB_DB", str(PROJECT_ROOT / "miniweb.db"))
OSRM_URL = "http://router.project-osrm.org/route/v1"
BATCH_SIZE = 500
DELAY = 0.3  # seconds between OSRM calls


def _parse_osrm_response(data):
    """Parse OSRM route response into our format."""
    if data.get("code") != "Ok" or not data.get("routes"):
        return None
    route = data["routes"][0]
    coords = [[c[1], c[0]] for c in route["geometry"]["coordinates"]]
    steps = []
    for leg in route.get("legs", []):
        for step in leg.get("steps", []):
            maneuver = step.get("maneuver", {})
            instr = f"{maneuver.get('type', '')} {maneuver.get('modifier', '')}".strip()
            name = step.get("name", "")
            if name:
                instr += f" onto {name}"
            steps.append({
                "instruction": instr,
                "distance_km": round(step.get("distance", 0) / 1000, 2),
                "duration_minutes": round(step.get("duration", 0) / 60, 1),
            })
    return {
        "geometry": coords,
        "distance_km": round(route["distance"] / 1000, 2),
        "duration_minutes": int(round(route["duration"] / 60)),
        "steps": steps,
    }


def _call_osrm(coords_str, profile="foot"):
    """Call OSRM and return parsed JSON."""
    url = f"{OSRM_URL}/{profile}/{coords_str}?overview=full&geometries=geojson&steps=true"
    req = urllib.request.Request(url, headers={"User-Agent": "MiniWeb/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


# Transit stops cache (loaded once)
_transit_stops = None

def _get_transit_stops(conn):
    global _transit_stops
    if _transit_stops is None:
        rows = conn.execute("SELECT id, name, lat, lng FROM transit_directions_stops").fetchall()
        _transit_stops = [dict(r) for r in rows]
    return _transit_stops


def _nearest_stop(lat, lng, stops):
    """Find nearest transit stop."""
    import math
    best, best_d = None, float('inf')
    for s in stops:
        dlat = lat - s['lat']
        dlng = lng - s['lng']
        d = math.sqrt(dlat*dlat + dlng*dlng)  # rough euclidean, fine for nearby
        if d < best_d:
            best_d = d
            best = s
    return best, best_d * 111  # rough km conversion


def get_route(lat1, lng1, lat2, lng2, mode="foot", conn=None):
    if mode == "transit" and conn:
        # Transit: walk to nearest stop, bus between stops, walk to destination
        stops = _get_transit_stops(conn)
        if not stops:
            return None
        orig_stop, d1 = _nearest_stop(lat1, lng1, stops)
        dest_stop, d2 = _nearest_stop(lat2, lng2, stops)
        if not orig_stop or not dest_stop or orig_stop['id'] == dest_stop['id']:
            return None

        try:
            # Route: origin -> orig_stop -> dest_stop -> destination (all walking profile)
            coords_str = f"{lng1},{lat1};{orig_stop['lng']},{orig_stop['lat']};{dest_stop['lng']},{dest_stop['lat']};{lng2},{lat2}"
            data = _call_osrm(coords_str, "foot")
            result = _parse_osrm_response(data)
            if not result:
                return None

            # Override steps with transit-style instructions
            walk_speed = 5  # km/h
            result["steps"] = [
                {"instruction": f"Walk to {orig_stop['name']} bus stop",
                 "distance_km": round(d1, 2), "duration_minutes": round(d1 / walk_speed * 60, 0)},
                {"instruction": f"Take bus from {orig_stop['name']} to {dest_stop['name']}",
                 "distance_km": round(result['distance_km'] - d1 - d2, 2),
                 "duration_minutes": round((result['duration_minutes'] - d1/walk_speed*60 - d2/walk_speed*60) * 0.8, 0)},
                {"instruction": f"Walk from {dest_stop['name']} to destination",
                 "distance_km": round(d2, 2), "duration_minutes": round(d2 / walk_speed * 60, 0)},
            ]
            # Add wait time for bus (~5 min average)
            result["duration_minutes"] = int(result["duration_minutes"] * 1.3 + 5)
            result["mode"] = "transit"
            return result
        except Exception:
            return None

    profile = "foot" if mode == "walking" else "car"
    try:
        data = _call_osrm(f"{lng1},{lat1};{lng2},{lat2}", profile)
        return _parse_osrm_response(data)
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--limit", type=int, default=0,
                        help="Limit number of locations (0=all)")
    parser.add_argument("--modes", default="walking,driving,transit",
                        help="Comma-separated modes (default: walking,driving,transit)")
    parser.add_argument("--delay", type=float, default=DELAY,
                        help=f"Seconds between OSRM calls (default: {DELAY})")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip pairs that already have templates")
    args = parser.parse_args()

    t0 = time.time()
    modes = [m.strip() for m in args.modes.split(",")]

    conn = sqlite3.connect(args.db, timeout=120)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.row_factory = sqlite3.Row

    # Get all non-bus-stop locations
    sql = "SELECT id, name, lat, lng FROM map_services_locations WHERE category != 'bus_stop'"
    if args.limit:
        sql += f" LIMIT {args.limit}"
    locations = conn.execute(sql).fetchall()
    locs = [dict(l) for l in locations]
    n = len(locs)
    total_pairs = n * (n - 1) // 2
    total_routes = total_pairs * len(modes)
    print(f"{n} locations, {total_pairs} pairs, {total_routes} routes to compute")
    print(f"Modes: {modes}")
    print(f"Delay: {args.delay}s per call")
    print(f"Estimated time: {total_routes * args.delay / 60:.0f} minutes")

    # Load existing templates to skip
    existing = set()
    if args.skip_existing:
        for r in conn.execute("SELECT origin_lat, origin_lng, dest_lat, dest_lng, mode FROM map_services_route_templates"):
            existing.add((round(r[0], 4), round(r[1], 4), round(r[2], 4), round(r[3], 4), r[4]))
        print(f"Skipping {len(existing)} existing templates")

    max_id = conn.execute("SELECT MAX(id) FROM map_services_route_templates").fetchone()[0] or 0
    next_id = max_id + 1

    computed = 0
    skipped = 0
    failed = 0
    batch = []

    for i in range(n):
        for j in range(i + 1, n):
            for mode in modes:
                # Check if exists
                key = (round(locs[i]["lat"], 4), round(locs[i]["lng"], 4),
                       round(locs[j]["lat"], 4), round(locs[j]["lng"], 4), mode)
                if key in existing:
                    skipped += 1
                    continue

                time.sleep(args.delay)
                result = get_route(locs[i]["lat"], locs[i]["lng"],
                                   locs[j]["lat"], locs[j]["lng"], mode, conn=conn)
                if not result:
                    failed += 1
                    continue

                batch.append((
                    next_id,
                    locs[i]["lat"], locs[i]["lng"],
                    locs[j]["lat"], locs[j]["lng"],
                    locs[i]["name"], locs[j]["name"],
                    mode,
                    result["distance_km"], result["duration_minutes"],
                    json.dumps(result["geometry"]),
                    json.dumps(result["steps"]),
                ))
                next_id += 1
                computed += 1

                if len(batch) >= BATCH_SIZE:
                    conn.executemany(
                        "INSERT INTO map_services_route_templates VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        batch)
                    batch.clear()
                    conn.commit()

                    elapsed = time.time() - t0
                    rate = computed / elapsed if elapsed > 0 else 0
                    remaining = total_routes - computed - skipped - failed
                    eta = remaining / rate / 60 if rate > 0 else 0
                    print(f"  {computed:,} computed, {skipped:,} skipped, {failed:,} failed "
                          f"({elapsed:.0f}s, {rate:.1f}/s, ETA {eta:.0f}min)",
                          flush=True)

    if batch:
        conn.executemany(
            "INSERT INTO map_services_route_templates VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            batch)
    conn.commit()

    elapsed = time.time() - t0
    total_templates = conn.execute("SELECT COUNT(*) FROM map_services_route_templates").fetchone()[0]
    print(f"\n=== Done in {elapsed:.0f}s ({elapsed/60:.1f}min) ===")
    print(f"Computed: {computed:,}, Skipped: {skipped:,}, Failed: {failed:,}")
    print(f"Total route templates: {total_templates:,}")

    # DB size
    db_size = os.path.getsize(args.db)
    print(f"DB size: {db_size / 1024**3:.2f} GB")

    conn.close()


if __name__ == "__main__":
    main()
