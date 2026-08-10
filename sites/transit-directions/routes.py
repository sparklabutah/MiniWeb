"""Lakeport Transit Authority (LTA) -- public transit website (Google Transit style).

Serves transit route information, stop details, schedules, fares, and trip
planning through Flask routes.  Data files live under the central data_sources
directory and are never modified by the web layer.

Macros supported (20):
  navigate_by_dropdown, search_by_query, search_by_proximity,
  route_by_query, route_by_radio, route_by_route, route_by_date_range,
  filter_by_radio, sort_by_dropdown, extract_by_query, extract_by_dropdown,
  extract_from_table, compute_by_dropdown, compute_by_extremum,
  compare_from_table, select_by_dropdown, select_by_ranking,
  select_by_extremum, export_by_dropdown, share_by_dropdown
"""
import csv
import io
import math
import pathlib
from datetime import datetime

from flask import (
    Blueprint, Response, abort, jsonify, redirect, render_template, request, session,
    url_for,
)
from app import db
from helpers.geo import haversine

SITE = "transit-directions"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "transit-directions",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _load_routes():
    return db.query(SITE, "routes_transit")


def _load_stops():
    stops = db.query(SITE, "stops")
    # Populate routes_served if empty by cross-referencing route major_stops
    routes = db.query(SITE, "routes_transit")
    # Build a mapping from major-stop names to route numbers
    # Use fuzzy matching: a stop is served by a route if the stop name
    # shares a significant street/place token with any of the route's major_stops.
    _noise = {"st", "ave", "blvd", "dr", "rd", "ln", "way", "ct", "&", "the",
              "and", "block", "stop", "only", "drop", "off", "east", "west",
              "north", "south", "transit", "center"}
    def _tokens(name):
        return {t for t in name.lower().replace("(", " ").replace(")", " ").split()
                if t not in _noise and len(t) > 1}

    for stop in stops:
        if not stop.get("routes_served"):
            served = []
            stoks = _tokens(stop["name"])
            for route in routes:
                for ms in route.get("major_stops", []):
                    mtoks = _tokens(ms)
                    # Match if the stop shares at least one significant token
                    # with a major stop AND both are on the same street/area
                    overlap = stoks & mtoks
                    if len(overlap) >= 1:
                        served.append(route["route_number"])
                        break
            stop["routes_served"] = sorted(set(served))
    return stops


def _load_schedules():
    return db.query(SITE, "schedules")


def _load_fares():
    rows = db.query(SITE, "fares")
    return rows[0] if rows else {}


def _load_trip_plans():
    return db.query(SITE, "trip_plans")


def _load_users():
    return db.query(SITE, "users")




def _get_user(user_id):
    return db.get_item(SITE, "users", user_id)


def _haversine(lat1, lng1, lat2, lng2):
    return haversine(lat1, lng1, lat2, lng2)


def _get_route_by_id(route_id):
    return db.get_item(SITE, "routes_transit", route_id)


def _get_stop_by_id(stop_id):
    return db.get_item(SITE, "stops", stop_id)


def _get_schedules_for_route(route_id):
    return db.query(SITE, "schedules", where={"route_id": route_id})


def _simulated_next_arrivals(stop, routes_data, schedules_data, count=5):
    """Return simulated upcoming arrivals for a stop based on schedule data."""
    now = datetime.now()
    current_minutes = now.hour * 60 + now.minute
    arrivals = []

    for route_num in stop.get("routes_served", []):
        route = None
        for r in routes_data:
            if r["route_number"] == route_num:
                route = r
                break
        if not route:
            continue

        for sched in schedules_data:
            if sched["route_id"] != route["id"]:
                continue
            for timetable_entry in sched.get("timetable", []):
                if timetable_entry["stop"] == stop["name"]:
                    for time_str in timetable_entry["times"]:
                        parts = time_str.split(":")
                        t_min = int(parts[0]) * 60 + int(parts[1])
                        if t_min > current_minutes:
                            arrivals.append({
                                "route_number": route_num,
                                "route_name": route["name"],
                                "route_color": route.get("color", "#666"),
                                "direction": sched.get("direction_label", ""),
                                "time": time_str,
                                "minutes_away": t_min - current_minutes,
                            })

    arrivals.sort(key=lambda a: a["minutes_away"])
    return arrivals[:count]


# ---------------------------------------------------------------------------
# Trip-planning engine (supports route_by_query, route_by_radio, etc.)
# ---------------------------------------------------------------------------

def _plan_trip(origin, destination, route_pref="fastest", departure_time=None, travel_date=None):
    """Plan a trip and return multiple route options.

    route_pref: fastest | cheapest | fewest_transfers
    travel_date: YYYY-MM-DD string; used to filter routes by day-of-week
    Returns a list of route options sorted by the preference.
    """
    stops = _load_stops()
    routes_data = _load_routes()

    # Filter routes by day of week if travel_date provided (route_by_date_range)
    if travel_date:
        try:
            dt = datetime.strptime(travel_date, "%Y-%m-%d")
            day_name = dt.strftime("%A").lower()
            routes_data = [r for r in routes_data if day_name in r.get("days_of_operation", [])]
        except ValueError:
            pass
    fares = _load_fares()

    # Find closest stops
    origin_stop = None
    dest_stop = None
    for s in stops:
        if origin.lower() in s["name"].lower() or s["name"].lower() in origin.lower():
            origin_stop = s
            break
    for s in stops:
        if destination.lower() in s["name"].lower() or s["name"].lower() in destination.lower():
            dest_stop = s
            break

    if not origin_stop:
        origin_stop = stops[0]
    if not dest_stop:
        dest_stop = stops[-1]

    # Build multiple route options
    options = []

    # Option 1: Direct route (if common route exists)
    common_routes = set(origin_stop.get("routes_served", [])) & set(dest_stop.get("routes_served", []))
    for route_num in sorted(common_routes):
        route_obj = next((r for r in routes_data if r["route_number"] == route_num), None)
        if not route_obj:
            continue
        travel_time = route_obj["estimated_travel_time_minutes"]
        zones = {origin_stop.get("zone", "A"), dest_stop.get("zone", "A")}
        fare_zone = "B" if "B" in zones else "A"
        fare_key = f"zone_{fare_zone}"
        fare_amount = fares.get("single_ride", {}).get(fare_key, {}).get("adult", 2.50)

        legs = [
            {"type": "walk", "from": origin, "to": f"{origin_stop['name']} (Stop {origin_stop['stop_code']})",
             "duration_minutes": 5, "distance_km": 0.3},
            {"type": "bus", "route": f"Route {route_num} - {route_obj['name']}",
             "route_type": route_obj["type"],
             "from_stop": origin_stop["name"], "to_stop": dest_stop["name"],
             "duration_minutes": travel_time, "stops_count": 3},
            {"type": "walk", "from": f"{dest_stop['name']} (Stop {dest_stop['stop_code']})",
             "to": destination, "duration_minutes": 4, "distance_km": 0.2},
        ]
        options.append({
            "option_label": f"Direct via Route {route_num}",
            "route_type": route_obj["type"],
            "total_duration_minutes": 5 + travel_time + 4,
            "transfers": 0,
            "fare": fare_amount,
            "fare_zone": fare_zone,
            "legs": legs,
        })

    # Option 2: Transfer route via Transit Center
    if not common_routes or True:
        transit_center = stops[0]
        origin_routes = set(origin_stop.get("routes_served", []))
        tc_routes = set(transit_center.get("routes_served", []))
        dest_routes = set(dest_stop.get("routes_served", []))

        first_options = sorted(origin_routes & tc_routes) if origin_routes & tc_routes else sorted(origin_routes)
        second_options = sorted(dest_routes & tc_routes) if dest_routes & tc_routes else sorted(dest_routes)

        if first_options and second_options:
            first_route = first_options[0]
            second_route = second_options[0]
            fr_obj = next((r for r in routes_data if r["route_number"] == first_route), None)
            sr_obj = next((r for r in routes_data if r["route_number"] == second_route), None)

            zones = {origin_stop.get("zone", "A"), dest_stop.get("zone", "A"),
                     transit_center.get("zone", "A")}
            fare_zone = "B" if "B" in zones else "A"
            fare_key = f"zone_{fare_zone}"
            fare_amount = fares.get("single_ride", {}).get(fare_key, {}).get("adult", 2.50)

            legs = [
                {"type": "walk", "from": origin, "to": f"{origin_stop['name']} (Stop {origin_stop['stop_code']})",
                 "duration_minutes": 5, "distance_km": 0.3},
                {"type": "bus",
                 "route": f"Route {first_route}" + (f" - {fr_obj['name']}" if fr_obj else ""),
                 "route_type": fr_obj["type"] if fr_obj else "local",
                 "from_stop": origin_stop["name"], "to_stop": transit_center["name"],
                 "duration_minutes": 12, "stops_count": 3},
                {"type": "walk", "from": transit_center["name"], "to": transit_center["name"],
                 "duration_minutes": 3, "distance_km": 0.1},
                {"type": "bus",
                 "route": f"Route {second_route}" + (f" - {sr_obj['name']}" if sr_obj else ""),
                 "route_type": sr_obj["type"] if sr_obj else "local",
                 "from_stop": transit_center["name"], "to_stop": dest_stop["name"],
                 "duration_minutes": 15, "stops_count": 4},
                {"type": "walk", "from": f"{dest_stop['name']} (Stop {dest_stop['stop_code']})",
                 "to": destination, "duration_minutes": 4, "distance_km": 0.2},
            ]
            total_dur = 5 + 12 + 3 + 15 + 4
            options.append({
                "option_label": f"Transfer via Transit Center (Rt {first_route} + Rt {second_route})",
                "route_type": "local",
                "total_duration_minutes": total_dur,
                "transfers": 1,
                "fare": fare_amount,
                "fare_zone": fare_zone,
                "legs": legs,
            })

    # Sort by preference
    if route_pref == "cheapest":
        options.sort(key=lambda o: (o["fare"], o["total_duration_minutes"]))
    elif route_pref == "fewest_transfers":
        options.sort(key=lambda o: (o["transfers"], o["total_duration_minutes"]))
    else:  # fastest
        options.sort(key=lambda o: (o["total_duration_minutes"], o["fare"]))

    return {
        "origin": origin,
        "destination": destination,
        "departure_time": departure_time or datetime.now().strftime("%H:%M"),
        "route_preference": route_pref,
        "options": options,
        "options_count": len(options),
    }


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    import json as _json

    routes = db.query(SITE, "routes_transit", sort="route_number", limit=20)
    fares = _load_fares()

    # Build schedule timetables keyed by route_id
    # Each schedule row has a JSON timetable: [{stop, times}, ...]
    schedules = db.query(SITE, "schedules", limit=50)
    route_schedules = {}
    for sched in schedules:
        rid = sched["route_id"]
        timetable_raw = sched.get("timetable", "[]")
        if isinstance(timetable_raw, str):
            timetable = _json.loads(timetable_raw) if timetable_raw else []
        else:
            timetable = timetable_raw
        # For the index page, show a sampled set of times (every ~6th departure)
        # to fit a readable table — real transit sites show ~12 columns
        sampled = []
        for entry in timetable:
            times = entry.get("times", [])
            # Pick representative times spread across the day
            if len(times) > 12:
                step = max(1, len(times) // 12)
                picked = times[::step][:12]
            else:
                picked = times
            sampled.append({"stop": entry["stop"], "times": picked})
        route_schedules[rid] = {
            "direction_label": sched.get("direction_label", ""),
            "service_type": sched.get("service_type", ""),
            "timetable": sampled,
        }

    total_stops = db.count(SITE, "stops")
    total_routes = db.count(SITE, "routes_transit")

    return render_template(
        "transit-directions/index.html",
        routes=routes,
        fares=fares,
        route_schedules=route_schedules,
        total_stops=total_stops,
        total_routes=total_routes,
    )


@blueprint.route("/routes")
def routes_list():
    routes = _load_routes()
    type_filter = request.args.get("type", "")
    sort_by = request.args.get("sort", "")
    if type_filter:
        routes = [r for r in routes if r.get("type") == type_filter]
    # sort_by_dropdown support
    if sort_by == "name":
        routes.sort(key=lambda r: r["name"].lower())
    elif sort_by == "travel_time":
        routes.sort(key=lambda r: r["estimated_travel_time_minutes"])
    elif sort_by == "frequency":
        routes.sort(key=lambda r: r["frequency_peak_minutes"])
    elif sort_by == "route_number":
        routes.sort(key=lambda r: r["route_number"])

    all_types = sorted(set(r.get("type", "local") for r in _load_routes()))
    return render_template(
        "transit-directions/routes_list.html",
        routes=routes,
        all_types=all_types,
        current_type=type_filter,
        current_sort=sort_by,
    )


@blueprint.route("/route/<int:route_id>")
def route_detail(route_id):
    route = _get_route_by_id(route_id)
    if not route:
        abort(404)
    stops = _load_stops()
    schedules = _get_schedules_for_route(route_id)
    route_stops = [s for s in stops if route["route_number"] in s.get("routes_served", [])]
    return render_template(
        "transit-directions/route_detail.html",
        route=route,
        route_stops=route_stops,
        schedules=schedules,
    )


@blueprint.route("/stops")
def stops_list():
    stops = _load_stops()
    q = request.args.get("q", "").strip().lower()
    zone_filter = request.args.get("zone", "")
    route_filter = request.args.get("route", "")
    sort_by = request.args.get("sort", "")
    if q:
        stops = [s for s in stops if q in s["name"].lower() or q in s.get("address", "").lower()]
    if zone_filter:
        stops = [s for s in stops if s.get("zone") == zone_filter]
    if route_filter:
        stops = [s for s in stops if route_filter in s.get("routes_served", [])]
    # sort_by_dropdown support
    if sort_by == "name":
        stops.sort(key=lambda s: s["name"].lower())
    elif sort_by == "zone":
        stops.sort(key=lambda s: s.get("zone", "A"))
    elif sort_by == "routes_count":
        stops.sort(key=lambda s: -len(s.get("routes_served", [])))
    elif sort_by == "amenities_count":
        stops.sort(key=lambda s: -len(s.get("amenities", [])))

    all_zones = sorted(set(s.get("zone", "A") for s in _load_stops()))
    all_routes_served = sorted(set(r for s in _load_stops() for r in s.get("routes_served", [])))
    return render_template(
        "transit-directions/stops.html",
        stops=stops,
        all_zones=all_zones,
        all_routes=all_routes_served,
        q=request.args.get("q", ""),
        current_zone=zone_filter,
        current_route=route_filter,
        current_sort=sort_by,
    )


@blueprint.route("/stop/<int:stop_id>")
def stop_detail(stop_id):
    stop = _get_stop_by_id(stop_id)
    if not stop:
        abort(404)
    routes_data = _load_routes()
    schedules_data = _load_schedules()
    arrivals = _simulated_next_arrivals(stop, routes_data, schedules_data, count=10)
    served_routes = [r for r in routes_data if r["route_number"] in stop.get("routes_served", [])]
    return render_template(
        "transit-directions/stop_detail.html",
        stop=stop,
        arrivals=arrivals,
        served_routes=served_routes,
    )


@blueprint.route("/trip-planner")
def trip_planner():
    stops = _load_stops()
    routes_data = _load_routes()
    trip_plans = []
    user_id = session.get("user_id")
    if user_id:
        all_plans = _load_trip_plans()
        trip_plans = [tp for tp in all_plans if tp.get("user_id") == user_id]

    # Handle trip-planning form
    origin = request.args.get("from", "").strip()
    destination = request.args.get("to", "").strip()
    route_pref = request.args.get("preference", "fastest")
    departure = request.args.get("departure", "")
    travel_date = request.args.get("date", "")
    plan_result = None
    if origin and destination:
        plan_result = _plan_trip(origin, destination, route_pref, departure, travel_date)

    return render_template(
        "transit-directions/trip_planner.html",
        stops=stops,
        routes=routes_data,
        trip_plans=trip_plans,
        plan_result=plan_result,
        origin=origin,
        destination=destination,
        route_pref=route_pref,
        departure=departure,
        travel_date=travel_date,
    )


@blueprint.route("/fares")
def fares_page():
    fares = _load_fares()
    zone = request.args.get("zone", "")
    rider_type = request.args.get("rider", "")
    pass_type = request.args.get("pass_type", "")
    return render_template(
        "transit-directions/fares.html",
        fares=fares,
        current_zone=zone,
        current_rider=rider_type,
        current_pass=pass_type,
    )


@blueprint.route("/compare")
def compare_page():
    """Compare multiple routes side-by-side (compare_from_table)."""
    ids_str = request.args.get("ids", "")
    route1 = request.args.get("route1", "")
    route2 = request.args.get("route2", "")
    routes_data = _load_routes()
    selected = []
    if ids_str:
        ids = [int(x) for x in ids_str.split(",") if x.strip().isdigit()]
        selected = [r for r in routes_data if r["id"] in ids]
    elif route1 or route2:
        ids = []
        if route1 and route1.isdigit():
            ids.append(int(route1))
        if route2 and route2.isdigit():
            ids.append(int(route2))
        selected = [r for r in routes_data if r["id"] in ids]
    return render_template(
        "transit-directions/compare.html",
        all_routes=routes_data,
        selected=selected,
    )


@blueprint.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        # Authenticate against users.json
        users = _load_users()
        user = next((u for u in users if u["username"] == username), None)
        # Passwords: user1 = transit123, user2 = transit456, user3 = transit789
        demo_passwords = {
            "alex_rivera": "transit123",
            "natalie_kim": "transit456",
            "elena_vasquez": "transit789",
        }
        expected_pw = demo_passwords.get(username, "")
        if user and password == expected_pw:
            session["user_id"] = user["id"]
            session["username"] = username
            session["user_name"] = user["full_name"]
            return render_template(
                "transit-directions/login.html",
                success=True,
                user_name=user["full_name"],
            )
        else:
            error = "Invalid username or password."
    return render_template(
        "transit-directions/login.html",
        error=error,
    )


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("transit-directions.index"))

@blueprint.route("/api/routes", methods=["GET"])
def api_routes_list():
    routes = _load_routes()
    type_filter = request.args.get("type", "")
    sort_by = request.args.get("sort", "")
    if type_filter:
        routes = [r for r in routes if r.get("type") == type_filter]
    if sort_by == "name":
        routes.sort(key=lambda r: r["name"].lower())
    elif sort_by == "travel_time":
        routes.sort(key=lambda r: r["estimated_travel_time_minutes"])
    elif sort_by == "frequency":
        routes.sort(key=lambda r: r["frequency_peak_minutes"])
    elif sort_by == "route_number":
        routes.sort(key=lambda r: r["route_number"])
    return jsonify(routes)


@blueprint.route("/api/routes/<int:route_id>", methods=["GET"])
def api_route_detail(route_id):
    route = _get_route_by_id(route_id)
    if not route:
        abort(404)
    return jsonify(route)


@blueprint.route("/api/routes/<int:route_id>/schedule", methods=["GET"])
def api_route_schedule(route_id):
    route = _get_route_by_id(route_id)
    if not route:
        abort(404)
    schedules = _get_schedules_for_route(route_id)
    direction = request.args.get("direction", "")
    if direction:
        schedules = [s for s in schedules if s.get("direction") == direction]
    return jsonify({"route_id": route_id, "route_name": route["name"], "schedules": schedules})


@blueprint.route("/api/stops", methods=["GET"])
def api_stops_list():
    stops = _load_stops()
    q = request.args.get("q", "").strip().lower()
    zone = request.args.get("zone", "")
    route = request.args.get("route", "")
    sort_by = request.args.get("sort", "")
    if q:
        stops = [s for s in stops if q in s["name"].lower() or q in s.get("address", "").lower()]
    if zone:
        stops = [s for s in stops if s.get("zone") == zone]
    if route:
        stops = [s for s in stops if route in s.get("routes_served", [])]
    if sort_by == "name":
        stops.sort(key=lambda s: s["name"].lower())
    elif sort_by == "zone":
        stops.sort(key=lambda s: s.get("zone", "A"))
    elif sort_by == "routes_count":
        stops.sort(key=lambda s: -len(s.get("routes_served", [])))
    return jsonify(stops)


@blueprint.route("/api/stops/<int:stop_id>", methods=["GET"])
def api_stop_detail(stop_id):
    stop = _get_stop_by_id(stop_id)
    if not stop:
        abort(404)
    routes_data = _load_routes()
    schedules_data = _load_schedules()
    arrivals = _simulated_next_arrivals(stop, routes_data, schedules_data, count=10)
    result = dict(stop)
    result["upcoming_arrivals"] = arrivals
    return jsonify(result)


@blueprint.route("/api/stops/nearby", methods=["GET"])
def api_stops_nearby():
    """search_by_proximity: find stops near a lat/lng coordinate."""
    try:
        lat = float(request.args.get("lat", 0))
        lng = float(request.args.get("lng", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "lat and lng parameters are required and must be numbers"}), 400
    radius_km = float(request.args.get("radius", 1.0))
    stops = _load_stops()
    nearby = []
    for s in stops:
        dist = _haversine(lat, lng, s["lat"], s["lng"])
        if dist <= radius_km:
            entry = dict(s)
            entry["distance_km"] = round(dist, 3)
            nearby.append(entry)
    nearby.sort(key=lambda x: x["distance_km"])
    return jsonify(nearby)


@blueprint.route("/api/trip-plan", methods=["GET", "POST"])
def api_trip_plan():
    """route_by_query + route_by_radio + route_by_date_range: plan a trip."""
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        origin = data.get("origin", "").strip()
        destination = data.get("destination", "").strip()
        route_pref = data.get("preference", "fastest")
        departure = data.get("departure_time", "")
        travel_date = data.get("date", "")
    else:
        origin = request.args.get("origin", "").strip()
        destination = request.args.get("destination", "").strip()
        route_pref = request.args.get("preference", "fastest")
        departure = request.args.get("departure_time", "")
        travel_date = request.args.get("date", "")

    if not origin or not destination:
        return jsonify({"error": "origin and destination are required"}), 400

    result = _plan_trip(origin, destination, route_pref, departure, travel_date)
    return jsonify(result), 201


@blueprint.route("/api/trip-plans", methods=["GET"])
def api_trip_plans():
    plans = _load_trip_plans()
    user_id = request.args.get("user_id")
    if user_id:
        try:
            uid = int(user_id)
            plans = [p for p in plans if p.get("user_id") == uid]
        except ValueError:
            pass
    return jsonify(plans)


@blueprint.route("/api/trip-plans/<int:plan_id>", methods=["GET"])
def api_trip_plan_detail(plan_id):
    plans = _load_trip_plans()
    plan = next((p for p in plans if p["id"] == plan_id), None)
    if not plan:
        abort(404)
    return jsonify(plan)


@blueprint.route("/api/fares", methods=["GET"])
def api_fares():
    """extract_by_dropdown + compute_by_dropdown: get fare info."""
    fares = _load_fares()
    zone = request.args.get("zone", "")
    rider = request.args.get("rider", "")
    pass_type = request.args.get("pass_type", "")

    if zone or rider or pass_type:
        result = {"transit_system": fares.get("transit_system", "")}
        pass_types = ["single_ride", "day_pass", "monthly_pass", "annual_pass"]
        if pass_type:
            pass_types = [pass_type] if pass_type in pass_types else pass_types

        for pt in pass_types:
            pt_data = fares.get(pt, {})
            if zone:
                zone_key = f"zone_{zone}"
                if zone_key in pt_data:
                    zone_data = pt_data[zone_key]
                    if rider:
                        result[pt] = {rider: zone_data.get(rider, "N/A")}
                    else:
                        result[pt] = zone_data
            else:
                if rider:
                    filtered = {}
                    for zk, zv in pt_data.items():
                        if isinstance(zv, dict) and rider in zv:
                            filtered[zk] = {rider: zv[rider]}
                    result[pt] = filtered
                else:
                    result[pt] = pt_data
        return jsonify(result)
    return jsonify(fares)


@blueprint.route("/api/fares/compute", methods=["GET"])
def api_fares_compute():
    """compute_by_dropdown: compute fare for a specific zone/rider/pass combination."""
    zone = request.args.get("zone", "A")
    rider = request.args.get("rider", "adult")
    pass_type = request.args.get("pass_type", "single_ride")

    fares = _load_fares()
    zone_key = f"zone_{zone}"
    pt_data = fares.get(pass_type, {})
    zone_data = pt_data.get(zone_key, {})
    amount = zone_data.get(rider, None)

    return jsonify({
        "zone": zone,
        "rider_type": rider,
        "pass_type": pass_type,
        "fare": amount,
        "currency": fares.get("currency", "USD"),
    })


@blueprint.route("/api/compare", methods=["GET"])
def api_compare():
    """compare_from_table: compare routes by IDs."""
    ids_str = request.args.get("ids", "")
    ids = [int(x) for x in ids_str.split(",") if x.strip().isdigit()]
    routes_data = _load_routes()
    selected = [r for r in routes_data if r["id"] in ids]
    # Add fare info to each route for comparison
    fares = _load_fares()
    for r in selected:
        zone_key = f"zone_{r.get('fare_zone', 'A')}"
        r["fare_adult_single"] = fares.get("single_ride", {}).get(zone_key, {}).get("adult", 0)
        r["fare_adult_monthly"] = fares.get("monthly_pass", {}).get(zone_key, {}).get("adult", 0)
    return jsonify(selected)


@blueprint.route("/api/stats", methods=["GET"])
def api_stats():
    """extract_by_dropdown + compute_by_extremum: aggregate statistics."""
    routes = _load_routes()
    stops = _load_stops()
    fares = _load_fares()
    trip_plans = _load_trip_plans()

    route_types = {}
    for r in routes:
        rtype = r.get("type", "local")
        route_types[rtype] = route_types.get(rtype, 0) + 1

    zones = {}
    for s in stops:
        z = s.get("zone", "A")
        zones[z] = zones.get(z, 0) + 1

    amenity_counts = {}
    for s in stops:
        for a in s.get("amenities", []):
            amenity_counts[a] = amenity_counts.get(a, 0) + 1

    accessible_stops = sum(1 for s in stops if s.get("wheelchair_accessible"))

    # Extremum stats
    fastest_route = min(routes, key=lambda r: r["estimated_travel_time_minutes"])
    slowest_route = max(routes, key=lambda r: r["estimated_travel_time_minutes"])
    most_frequent = min(routes, key=lambda r: r["frequency_peak_minutes"])
    least_frequent = max(routes, key=lambda r: r["frequency_peak_minutes"])

    return jsonify({
        "total_routes": len(routes),
        "total_stops": len(stops),
        "total_trip_plans": len(trip_plans),
        "route_types": route_types,
        "stops_by_zone": zones,
        "amenity_counts": amenity_counts,
        "accessible_stops": accessible_stops,
        "transit_system": fares.get("transit_system", ""),
        "fare_zones": list(fares.get("fare_zones", {}).keys()),
        "fastest_route": {"id": fastest_route["id"], "name": fastest_route["name"],
                          "travel_time": fastest_route["estimated_travel_time_minutes"]},
        "slowest_route": {"id": slowest_route["id"], "name": slowest_route["name"],
                          "travel_time": slowest_route["estimated_travel_time_minutes"]},
        "most_frequent_route": {"id": most_frequent["id"], "name": most_frequent["name"],
                                "frequency_peak": most_frequent["frequency_peak_minutes"]},
    })


@blueprint.route("/api/routes/extremum", methods=["GET"])
def api_routes_extremum():
    """compute_by_extremum + select_by_extremum: find best/worst route by metric."""
    metric = request.args.get("metric", "travel_time")  # travel_time | frequency | fare
    order = request.args.get("order", "min")  # min | max
    type_filter = request.args.get("type", "")

    routes = _load_routes()
    if type_filter:
        routes = [r for r in routes if r.get("type") == type_filter]
    if not routes:
        return jsonify({"error": "No routes match the filter"}), 404

    fares = _load_fares()

    if metric == "travel_time":
        key_fn = lambda r: r["estimated_travel_time_minutes"]
    elif metric == "frequency":
        key_fn = lambda r: r["frequency_peak_minutes"]
    elif metric == "fare":
        def key_fn(r):
            zone_key = f"zone_{r.get('fare_zone', 'A')}"
            return fares.get("single_ride", {}).get(zone_key, {}).get("adult", 0)
    else:
        key_fn = lambda r: r["estimated_travel_time_minutes"]

    if order == "max":
        result = max(routes, key=key_fn)
    else:
        result = min(routes, key=key_fn)

    out = dict(result)
    zone_key = f"zone_{result.get('fare_zone', 'A')}"
    out["fare_adult_single"] = fares.get("single_ride", {}).get(zone_key, {}).get("adult", 0)
    out["metric"] = metric
    out["order"] = order
    out["metric_value"] = key_fn(result)
    return jsonify(out)


@blueprint.route("/api/routes/ranked", methods=["GET"])
def api_routes_ranked():
    """select_by_ranking: rank routes by a metric, return Nth."""
    metric = request.args.get("metric", "travel_time")
    rank = request.args.get("rank", "1", type=int)
    order = request.args.get("order", "asc")  # asc | desc
    type_filter = request.args.get("type", "")

    routes = _load_routes()
    if type_filter:
        routes = [r for r in routes if r.get("type") == type_filter]

    fares = _load_fares()

    if metric == "travel_time":
        key_fn = lambda r: r["estimated_travel_time_minutes"]
    elif metric == "frequency":
        key_fn = lambda r: r["frequency_peak_minutes"]
    elif metric == "fare":
        def key_fn(r):
            zone_key = f"zone_{r.get('fare_zone', 'A')}"
            return fares.get("single_ride", {}).get(zone_key, {}).get("adult", 0)
    else:
        key_fn = lambda r: r["estimated_travel_time_minutes"]

    routes.sort(key=key_fn, reverse=(order == "desc"))

    if rank < 1 or rank > len(routes):
        return jsonify({"error": f"Rank {rank} out of range (1-{len(routes)})"}), 400

    result = dict(routes[rank - 1])
    zone_key = f"zone_{result.get('fare_zone', 'A')}"
    result["fare_adult_single"] = fares.get("single_ride", {}).get(zone_key, {}).get("adult", 0)
    result["rank"] = rank
    result["metric"] = metric
    result["metric_value"] = key_fn(routes[rank - 1])
    result["total_ranked"] = len(routes)
    return jsonify(result)


@blueprint.route("/api/export", methods=["GET"])
def api_export():
    """export_by_dropdown: export routes or stops data."""
    fmt = request.args.get("format", "json").lower()
    data_type = request.args.get("data", "routes")  # routes | stops | fares | trip_plans
    type_filter = request.args.get("type", "")
    zone_filter = request.args.get("zone", "")

    if data_type == "routes":
        data = _load_routes()
        if type_filter:
            data = [r for r in data if r.get("type") == type_filter]
    elif data_type == "stops":
        data = _load_stops()
        if zone_filter:
            data = [s for s in data if s.get("zone") == zone_filter]
    elif data_type == "fares":
        data = _load_fares()
    elif data_type == "trip_plans":
        data = _load_trip_plans()
    else:
        data = _load_routes()

    if fmt == "csv":
        if data_type == "routes":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["id", "route_number", "name", "type", "start_point", "end_point",
                             "travel_time_min", "peak_freq_min", "fare_zone"])
            for r in data:
                writer.writerow([r["id"], r["route_number"], r["name"], r["type"],
                                 r["start_point"], r["end_point"],
                                 r["estimated_travel_time_minutes"],
                                 r["frequency_peak_minutes"], r["fare_zone"]])
            return Response(output.getvalue(), mimetype="text/csv",
                            headers={"Content-Disposition": "attachment; filename=routes.csv"})
        elif data_type == "stops":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["id", "name", "stop_code", "address", "lat", "lng", "zone",
                             "routes_served", "wheelchair_accessible"])
            for s in data:
                writer.writerow([s["id"], s["name"], s["stop_code"], s["address"],
                                 s["lat"], s["lng"], s["zone"],
                                 ";".join(s.get("routes_served", [])),
                                 s.get("wheelchair_accessible", False)])
            return Response(output.getvalue(), mimetype="text/csv",
                            headers={"Content-Disposition": "attachment; filename=stops.csv"})

    return jsonify(data)


@blueprint.route("/api/share", methods=["POST"])
def api_share():
    """share_by_dropdown: share a trip plan or route via email/link."""
    data = request.get_json(silent=True) or {}
    share_type = data.get("type", "link")  # link | email
    content_type = data.get("content_type", "route")  # route | trip_plan | stop
    content_id = data.get("content_id")
    recipient = data.get("recipient", "")

    if content_id is None:
        return jsonify({"error": "content_id is required"}), 400

    # Build share URL
    if content_type == "route":
        share_url = f"/sites/transit-directions/route/{content_id}"
        title = ""
        route = _get_route_by_id(int(content_id))
        if route:
            title = f"Route {route['route_number']} - {route['name']}"
    elif content_type == "stop":
        share_url = f"/sites/transit-directions/stop/{content_id}"
        stop = _get_stop_by_id(int(content_id))
        title = stop["name"] if stop else ""
    elif content_type == "trip_plan":
        share_url = f"/sites/transit-directions/api/trip-plans/{content_id}"
        plans = _load_trip_plans()
        plan = next((p for p in plans if p["id"] == int(content_id)), None)
        title = plan["name"] if plan else ""
    else:
        share_url = f"/sites/transit-directions/"
        title = "Lakeport Transit Authority"

    result = {
        "shared": True,
        "share_type": share_type,
        "content_type": content_type,
        "content_id": content_id,
        "title": title,
        "url": share_url,
    }
    if share_type == "email" and recipient:
        result["recipient"] = recipient
        result["message"] = f"Shared '{title}' via email to {recipient}"
    else:
        result["message"] = f"Share link generated for '{title}'"

    return jsonify(result)


@blueprint.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    demo_passwords = {
        "alex_rivera": "transit123",
        "natalie_kim": "transit456",
        "elena_vasquez": "transit789",
    }
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    expected_pw = demo_passwords.get(username, "")
    if not user or password != expected_pw:
        return jsonify({"error": "Invalid credentials"}), 401
    session["user_id"] = user["id"]
    return jsonify({"user_id": user["id"], "username": user["username"],
                     "full_name": user["full_name"]})


@blueprint.route("/api/users/<int:user_id>", methods=["GET"])
def api_user(user_id):
    user = _get_user(user_id)
    if not user:
        abort(404)
    return jsonify(user)
