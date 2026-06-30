#!/usr/bin/env python3
"""Extract real POIs from Portland, OR via Overpass API + pre-compute routes via OSRM.

Writes directly to miniweb.db. Run once on a machine with internet access.

Usage:
    python scripts/extract_osm_portland.py
    python scripts/extract_osm_portland.py --skip-routes  # skip OSRM calls
"""

import argparse
import hashlib
import json
import os
import pathlib
import sqlite3
import sys
import time
import urllib.request
import urllib.parse

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
DB_PATH = os.environ.get("MINIWEB_DB", str(PROJECT_ROOT / "miniweb.db"))

# Portland bounding box
BBOX = "45.45,-122.80,45.60,-122.55"

# OSM tag -> our category mapping
CATEGORIES = [
    ("restaurant", "amenity", "restaurant", 80),
    ("cafe", "amenity", "cafe", 50),
    ("bar", "amenity", "bar", 30),
    ("fast_food", "amenity", "fast_food", 40),
    ("park", "leisure", "park", 40),
    ("hospital", "amenity", "hospital", 10),
    ("pharmacy", "amenity", "pharmacy", 20),
    ("gas_station", "amenity", "fuel", 25),
    ("grocery", "shop", "supermarket", 25),
    ("bank", "amenity", "bank", 20),
    ("library", "amenity", "library", 10),
    ("school", "amenity", "school", 20),
    ("gym", "leisure", "fitness_centre", 15),
    ("bakery", "shop", "bakery", 15),
    ("brewery", "amenity", "pub", 15),
    ("hotel", "tourism", "hotel", 20),
    ("bookstore", "shop", "books", 10),
    ("post_office", "amenity", "post_office", 5),
    ("fire_station", "amenity", "fire_station", 5),
    ("police", "amenity", "police", 5),
]

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def _query_overpass(osm_key, osm_value, limit):
    """Query Overpass API for POIs in Portland."""
    query = f"""
    [out:json][timeout:30];
    (
      node["{osm_key}"="{osm_value}"]["name"]{BBOX.replace(',', ' ', 1).replace(',', ',', 1)};
      way["{osm_key}"="{osm_value}"]["name"]{BBOX.replace(',', ' ', 1).replace(',', ',', 1)};
    );
    out center {limit};
    """
    # Fix bbox format for Overpass: (south,west,north,east)
    s, w, n, e = BBOX.split(",")
    bbox_str = f"({s},{w},{n},{e})"
    query = f'[out:json][timeout:30];(node["{osm_key}"="{osm_value}"]["name"]{bbox_str};way["{osm_key}"="{osm_value}"]["name"]{bbox_str};);out center {limit};'

    data = urllib.parse.urlencode({"data": query}).encode()
    req = urllib.request.Request(OVERPASS_URL, data=data,
                                 headers={"User-Agent": "MiniWeb/1.0 (research project)"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"  WARNING: Overpass query failed for {osm_key}={osm_value}: {e}")
        return {"elements": []}


def _parse_element(elem, category):
    """Parse an OSM element into a location record."""
    tags = elem.get("tags", {})
    name = tags.get("name", "").strip()
    if not name:
        return None

    # Get coordinates (for ways, use center)
    if elem["type"] == "way":
        lat = elem.get("center", {}).get("lat", 0)
        lng = elem.get("center", {}).get("lon", 0)
    else:
        lat = elem.get("lat", 0)
        lng = elem.get("lon", 0)

    if not lat or not lng:
        return None

    # Build address
    parts = []
    if tags.get("addr:housenumber") and tags.get("addr:street"):
        parts.append(f'{tags["addr:housenumber"]} {tags["addr:street"]}')
    elif tags.get("addr:street"):
        parts.append(tags["addr:street"])
    parts.append("Portland, OR")
    if tags.get("addr:postcode"):
        parts.append(tags["addr:postcode"])
    address = ", ".join(parts)

    # Deterministic rating from OSM ID
    h = int(hashlib.md5(str(elem["id"]).encode()).hexdigest()[:8], 16)
    rating = round(3.0 + (h % 21) / 10.0, 1)  # 3.0 to 5.0

    return {
        "name": name,
        "category": category,
        "address": address,
        "lat": round(lat, 6),
        "lng": round(lng, 6),
        "phone": tags.get("phone", tags.get("contact:phone", "")),
        "hours": tags.get("opening_hours", ""),
        "rating": rating,
        "osm_id": str(elem["id"]),
        "website": tags.get("website", tags.get("contact:website", "")),
        "cuisine": tags.get("cuisine", ""),
    }


def extract_pois():
    """Extract POIs from Overpass API."""
    all_pois = []
    seen_ids = set()

    for category, osm_key, osm_value, target in CATEGORIES:
        print(f"  Querying {category} ({osm_key}={osm_value}, target={target})...")
        result = _query_overpass(osm_key, osm_value, target * 2)
        count = 0
        for elem in result.get("elements", []):
            poi = _parse_element(elem, category)
            if poi and poi["osm_id"] not in seen_ids:
                seen_ids.add(poi["osm_id"])
                all_pois.append(poi)
                count += 1
                if count >= target:
                    break
        print(f"    Got {count} {category} POIs")
        time.sleep(2)  # respect Overpass rate limits

    return all_pois


def _query_osrm(lat1, lng1, lat2, lng2, mode="foot"):
    """Query OSRM demo server for a route."""
    profile = {"foot": "foot", "walking": "foot", "driving": "car", "cycling": "bike"}.get(mode, "foot")
    url = (f"http://router.project-osrm.org/route/v1/{profile}/"
           f"{lng1},{lat1};{lng2},{lat2}?overview=full&geometries=geojson&steps=true")
    req = urllib.request.Request(url, headers={"User-Agent": "MiniWeb/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            if data.get("code") == "Ok" and data.get("routes"):
                route = data["routes"][0]
                geom = route["geometry"]["coordinates"]  # [[lng,lat], ...]
                # Convert to [[lat,lng], ...] for Leaflet
                coords = [[c[1], c[0]] for c in geom]
                legs = route.get("legs", [{}])
                steps = []
                for leg in legs:
                    for step in leg.get("steps", []):
                        steps.append({
                            "instruction": step.get("maneuver", {}).get("type", "") + " " + step.get("name", ""),
                            "distance_km": round(step.get("distance", 0) / 1000, 2),
                            "duration_minutes": round(step.get("duration", 0) / 60, 1),
                        })
                return {
                    "geometry": coords,
                    "distance_km": round(route.get("distance", 0) / 1000, 2),
                    "duration_minutes": round(route.get("duration", 0) / 60, 0),
                    "steps": steps,
                }
    except Exception as e:
        print(f"  WARNING: OSRM query failed: {e}")
    return None


def precompute_routes(pois):
    """Pre-compute routes between landmark pairs."""
    # Pick well-known Portland landmarks from the POIs
    landmarks = []
    target_names = [
        "Powell's", "Voodoo Doughnut", "Providence", "Pioneer", "OMSI",
        "Powell Butte", "Trader Joe", "Fred Meyer", "New Seasons",
        "Stumptown", "McMenamins", "Portland Art Museum",
    ]
    for poi in pois:
        for target in target_names:
            if target.lower() in poi["name"].lower() and len(landmarks) < 20:
                landmarks.append(poi)
                break
    # If not enough landmarks, take highest-rated
    if len(landmarks) < 10:
        by_rating = sorted(pois, key=lambda p: -p["rating"])
        for p in by_rating:
            if p not in landmarks:
                landmarks.append(p)
            if len(landmarks) >= 15:
                break

    routes = []
    pairs_done = set()
    for i, origin in enumerate(landmarks):
        for j, dest in enumerate(landmarks):
            if i == j:
                continue
            pair_key = (min(i, j), max(i, j))
            if pair_key in pairs_done:
                continue
            pairs_done.add(pair_key)

            for mode in ["foot", "car"]:
                print(f"  Route: {origin['name'][:30]} -> {dest['name'][:30]} ({mode})")
                result = _query_osrm(origin["lat"], origin["lng"],
                                     dest["lat"], dest["lng"], mode)
                if result:
                    routes.append({
                        "origin_lat": origin["lat"],
                        "origin_lng": origin["lng"],
                        "dest_lat": dest["lat"],
                        "dest_lng": dest["lng"],
                        "origin_name": origin["name"],
                        "dest_name": dest["name"],
                        "mode": "walking" if mode == "foot" else "driving",
                        **result,
                    })
                time.sleep(1)

            if len(routes) >= 60:
                break
        if len(routes) >= 60:
            break

    return routes


def write_to_db(pois, routes, db_path):
    """Write POIs and routes directly to miniweb.db."""
    conn = sqlite3.connect(db_path, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")

    # Add new columns if missing
    existing_cols = {c[1] for c in conn.execute("PRAGMA table_info(map_services_locations)").fetchall()}
    for col, typ in [("osm_id", "TEXT"), ("website", "TEXT"), ("cuisine", "TEXT")]:
        if col not in existing_cols:
            conn.execute(f'ALTER TABLE map_services_locations ADD COLUMN {col} {typ} NOT NULL DEFAULT ""')

    existing_route_cols = {c[1] for c in conn.execute("PRAGMA table_info(map_services_routes)").fetchall()}
    if "geometry" not in existing_route_cols:
        conn.execute('ALTER TABLE map_services_routes ADD COLUMN geometry TEXT NOT NULL DEFAULT "[]"')

    # Create route_templates table
    conn.execute("""CREATE TABLE IF NOT EXISTS map_services_route_templates (
        id INTEGER PRIMARY KEY,
        origin_lat REAL NOT NULL DEFAULT 0, origin_lng REAL NOT NULL DEFAULT 0,
        dest_lat REAL NOT NULL DEFAULT 0, dest_lng REAL NOT NULL DEFAULT 0,
        origin_name TEXT NOT NULL DEFAULT '', dest_name TEXT NOT NULL DEFAULT '',
        mode TEXT NOT NULL DEFAULT 'walking',
        distance_km REAL NOT NULL DEFAULT 0, duration_minutes INTEGER NOT NULL DEFAULT 0,
        geometry TEXT NOT NULL DEFAULT '[]', steps TEXT NOT NULL DEFAULT '[]'
    )""")

    # Create reviews table if missing
    conn.execute("""CREATE TABLE IF NOT EXISTS map_services_reviews (
        id INTEGER PRIMARY KEY,
        location_id INTEGER NOT NULL DEFAULT 0,
        user_id INTEGER NOT NULL DEFAULT 0,
        username TEXT NOT NULL DEFAULT '',
        rating REAL NOT NULL DEFAULT 0,
        text TEXT NOT NULL DEFAULT '',
        timestamp TEXT NOT NULL DEFAULT ''
    )""")

    # Register new tables
    conn.execute("INSERT OR REPLACE INTO site_registry VALUES (?,?,?,?)",
                 ("map-services", "route_templates", "map_services_route_templates", "id"))
    conn.execute("INSERT OR REPLACE INTO site_registry VALUES (?,?,?,?)",
                 ("map-services", "reviews", "map_services_reviews", "id"))

    # Clear and insert POIs
    conn.execute("DELETE FROM map_services_locations")
    for i, poi in enumerate(pois, 1):
        conn.execute(
            "INSERT INTO map_services_locations (id, name, category, address, lat, lng, phone, hours, rating, osm_id, website, cuisine) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (i, poi["name"], poi["category"], poi["address"], poi["lat"], poi["lng"],
             poi["phone"], poi["hours"], poi["rating"], poi.get("osm_id", ""),
             poi.get("website", ""), poi.get("cuisine", "")))
    print(f"  Inserted {len(pois)} locations")

    # Insert route templates
    conn.execute("DELETE FROM map_services_route_templates")
    for i, rt in enumerate(routes, 1):
        conn.execute(
            "INSERT INTO map_services_route_templates VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (i, rt["origin_lat"], rt["origin_lng"], rt["dest_lat"], rt["dest_lng"],
             rt.get("origin_name", ""), rt.get("dest_name", ""),
             rt["mode"], rt["distance_km"], int(rt["duration_minutes"]),
             json.dumps(rt["geometry"]), json.dumps(rt["steps"])))
    print(f"  Inserted {len(routes)} route templates")

    # Update existing user routes with Portland addresses
    conn.execute("DELETE FROM map_services_routes")
    conn.execute("DELETE FROM map_services_saved_places")
    conn.execute("DELETE FROM map_services_search_history")

    # Update users with Portland addresses
    conn.execute("UPDATE map_services_users SET home_address='1247 SE Hawthorne Blvd, Portland, OR 97214', "
                 "work_address='500 SW 3rd Ave, Portland, OR 97204', phone='(503) 201-3344' WHERE id=1")

    conn.commit()

    # Rebuild FTS
    print("  Rebuilding FTS index...")
    try:
        conn.execute("DROP TABLE IF EXISTS fts_map_services_locations")
        conn.execute("""CREATE VIRTUAL TABLE fts_map_services_locations
            USING fts5(name, category, address, phone, hours, cuisine,
            content=map_services_locations, content_rowid=id)""")
        conn.execute("INSERT INTO fts_map_services_locations(fts_map_services_locations) VALUES('rebuild')")
        conn.commit()
        print("  FTS rebuilt")
    except Exception as e:
        print(f"  FTS warning: {e}")

    conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-routes", action="store_true", help="Skip OSRM route pre-computation")
    parser.add_argument("--db", default=DB_PATH, help=f"Database path (default: {DB_PATH})")
    args = parser.parse_args()

    print("=== Extracting Portland, OR POIs from OpenStreetMap ===")
    pois = extract_pois()
    print(f"\nTotal: {len(pois)} POIs extracted")

    routes = []
    if not args.skip_routes:
        print("\n=== Pre-computing routes via OSRM ===")
        routes = precompute_routes(pois)
        print(f"\nTotal: {len(routes)} route templates computed")
    else:
        print("\nSkipping route pre-computation")

    print(f"\n=== Writing to {args.db} ===")
    write_to_db(pois, routes, args.db)

    # Summary
    print(f"\n=== Done ===")
    cats = {}
    for p in pois:
        cats[p["category"]] = cats.get(p["category"], 0) + 1
    for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")


if __name__ == "__main__":
    main()
