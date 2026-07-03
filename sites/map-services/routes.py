"""CascadiaMaps -- map & navigation service (Google Maps style).

Serves POI listings, directions/routing, saved places, reviews, sharing,
and location search over data sourced from DATA_SOURCES_DIR/map-services/.

Macro coverage (27):
  navigate_by_dropdown, navigate_by_route, search_by_query,
  search_by_semantic, search_by_dropdown, search_by_pan_zoom,
  search_by_proximity, filter_by_dropdown, filter_by_toggle,
  filter_by_slider, sort_by_ranking, extract_by_query,
  extract_by_route, compute_by_route, compare_by_route,
  create_from_free_text, submit_by_query, post_from_free_text,
  select_by_query, configure_by_dropdown, export_by_route,
  rate_by_slider, share_by_query, save_by_query,
  route_by_query, route_by_radio, route_by_route
"""

import json
import math
import pathlib
from datetime import datetime

from flask import (
    Blueprint, Response, abort, jsonify, redirect, render_template, request,
    session, url_for,
)
from app import db
from app.events import emit

SITE = "map-services"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "map-services",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _current_user():
    uid = session.get("user_id")
    if uid is None:
        return None
    return db.get_item(SITE, "users", uid)


def _haversine(lat1, lng1, lat2, lng2):
    """Distance in km between two lat/lng points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _get_categories_from_db():
    """Return sorted unique categories via SQL."""
    table = db.get_table_name(SITE, "locations")
    if not table:
        return []
    rows = db.execute(f"SELECT DISTINCT category FROM [{table}] ORDER BY category")
    return [r["category"] for r in rows]


def _semantic_score(query, loc):
    """Simple keyword-overlap relevance score for semantic search."""
    terms = query.lower().split()
    hours = loc.get("hours", "")
    if not isinstance(hours, str):
        hours = str(hours)
    text = (loc["name"] + " " + loc["address"] + " " + loc["category"] +
            " " + hours).lower()
    return sum(1 for t in terms if t in text)


def _find_loc(query):
    """Find a map location by name or address (partial match)."""
    if not query:
        return None
    table = db.get_table_name(SITE, "locations")
    ql = f"%{query}%"
    # Exact address
    row = db.execute(f"SELECT * FROM [{table}] WHERE [address] = ? LIMIT 1", (query,), fetch="one")
    if row:
        return row
    # Name contains
    row = db.execute(f"SELECT * FROM [{table}] WHERE LOWER([name]) LIKE ? LIMIT 1", (ql.lower(),), fetch="one")
    if row:
        return row
    # Address contains
    row = db.execute(f"SELECT * FROM [{table}] WHERE [address] LIKE ? LIMIT 1", (ql,), fetch="one")
    return row


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    category = request.args.get("category", "")
    q = request.args.get("q", "")
    open_now = request.args.get("open_now", "")        # filter_by_toggle
    min_rating = request.args.get("min_rating", type=float)  # filter_by_slider
    sort = request.args.get("sort", "")                # sort_by_ranking
    # Bounding box for pan/zoom: search_by_pan_zoom
    lat_min = request.args.get("lat_min", type=float)
    lat_max = request.args.get("lat_max", type=float)
    lng_min = request.args.get("lng_min", type=float)
    lng_max = request.args.get("lng_max", type=float)

    # Build SQL query for locations
    table = db.get_table_name(SITE, "locations")
    clauses = []
    params = []

    if category:
        clauses.append("[category] = ?")
        params.append(category)
    if q:
        ql = f"%{q}%"
        clauses.append("(LOWER([name]) LIKE ? OR LOWER([address]) LIKE ? OR LOWER([category]) LIKE ?)")
        params.extend([ql.lower(), ql.lower(), ql.lower()])
    if min_rating is not None:
        clauses.append("[rating] >= ?")
        params.append(min_rating)
    if all(v is not None for v in [lat_min, lat_max, lng_min, lng_max]):
        clauses.append("[lat] >= ? AND [lat] <= ? AND [lng] >= ? AND [lng] <= ?")
        params.extend([lat_min, lat_max, lng_min, lng_max])

    order_clause = ""
    if sort == "rating":
        order_clause = " ORDER BY [rating] DESC"
    elif sort == "name":
        order_clause = " ORDER BY LOWER([name]) ASC"

    # Use FTS5 for text search, SQL for other filters
    if q and not clauses[0].startswith("(LOWER"):
        # Only q was set — use FTS5
        locations = db.search(SITE, "locations", q, limit=100)
    elif q:
        sql = f"SELECT * FROM [{table}]"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += order_clause + " LIMIT 100"
        locations = db.execute(sql, tuple(params))
    else:
        sql = f"SELECT * FROM [{table}]"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += order_clause + " LIMIT 100"
        locations = db.execute(sql, tuple(params))

    # open_now filter requires Python (checking for "closed" in hours text)
    if open_now == "1":
        def _hours_to_str(h):
            return str(h) if not isinstance(h, str) else h
        locations = [l for l in locations if l.get("hours") and "closed" not in _hours_to_str(l["hours"]).lower()]

    # Also search saved places if user is logged in and has a query
    user = _current_user()
    if q and user:
        ql = f"%{q.lower()}%"
        saved = db.execute(
            "SELECT * FROM map_services_saved_places WHERE user_id = ? AND LOWER(name) LIKE ?",
            (user["id"], ql))
        # Convert saved places to location-like dicts and prepend
        for sp in saved:
            locations.insert(0, {
                "id": sp.get("location_id") or sp["id"],
                "name": f"📌 {sp['name']}",
                "category": sp.get("label", "saved"),
                "address": sp.get("address", ""),
                "lat": sp.get("lat", 0),
                "lng": sp.get("lng", 0),
                "phone": "",
                "hours": "",
                "rating": 0,
            })

    categories = _get_categories_from_db()
    return render_template("map-services/index.html",
                           locations=locations, categories=categories,
                           selected_category=category, search_query=q,
                           open_now=open_now, min_rating=min_rating,
                           sort=sort, user=user)


@blueprint.route("/place/<int:place_id>")
def place_detail(place_id):
    place = db.get_item(SITE, "locations", place_id)
    if not place:
        abort(404)
    # Find nearby places (within ~1 km) using SQL bounding box pre-filter
    delta = 0.01  # ~1 km
    table = db.get_table_name(SITE, "locations")
    nearby_candidates = db.execute(
        f"SELECT * FROM [{table}] WHERE id != ? AND lat BETWEEN ? AND ? AND lng BETWEEN ? AND ? LIMIT 20",
        (place_id, place["lat"] - delta, place["lat"] + delta,
         place["lng"] - delta, place["lng"] + delta))
    nearby = sorted(nearby_candidates,
                    key=lambda l: _haversine(place["lat"], place["lng"], l["lat"], l["lng"]))[:5]
    user = _current_user()
    # Check if saved
    is_saved = False
    if user:
        saved_check = db.query(SITE, "saved_places",
                               where={"user_id": user["id"], "location_id": place_id},
                               limit=1)
        is_saved = len(saved_check) > 0
    # Load reviews for this place
    place_reviews = db.query(SITE, "reviews",
                             where={"location_id": place_id},
                             sort="-timestamp")
    return render_template("map-services/place_detail.html",
                           place=place, nearby=nearby, user=user,
                           is_saved=is_saved, reviews=place_reviews)


@blueprint.route("/directions")
def directions():
    user = _current_user()
    user_routes = []
    if user:
        user_routes = db.query(SITE, "routes",
                               where={"user_id": user["id"]},
                               sort="-last_used")
    locations = db.query(SITE, "locations", limit=200)
    prefill_to = request.args.get("to", "").strip()
    prefill_from = request.args.get("from", "").strip()
    return render_template("map-services/directions.html",
                           user_routes=user_routes, locations=locations,
                           user=user, prefill_to=prefill_to, prefill_from=prefill_from)


@blueprint.route("/route/<int:route_id>")
def route_detail(route_id):
    route = db.get_item(SITE, "routes", route_id)
    if not route:
        abort(404)
    user = _current_user()
    return render_template("map-services/route_detail.html",
                           route=route, user=user)


@blueprint.route("/saved-places")
def saved_places():
    user = _current_user()
    places = []
    if user:
        places = db.query(SITE, "saved_places",
                          where={"user_id": user["id"]},
                          sort="-last_visited")
    return render_template("map-services/saved_places.html",
                           places=places, user=user)


@blueprint.route("/search-history")
def search_history():
    user = _current_user()
    history = []
    if user:
        history = db.query(SITE, "search_history",
                           where={"user_id": user["id"]},
                           sort="-timestamp")
    return render_template("map-services/search.html",
                           history=history, user=user)


@blueprint.route("/compare")
def compare_page():
    """compare_by_route: compare two or more places side by side."""
    ids_str = request.args.get("ids", "")
    selected = []
    if ids_str:
        ids = [int(x) for x in ids_str.split(",") if x.strip().isdigit()]
        selected = [db.get_item(SITE, "locations", lid) for lid in ids]
        selected = [s for s in selected if s]
    locations = db.query(SITE, "locations")
    return render_template("map-services/compare.html",
                           locations=locations, selected=selected, user=_current_user())


@blueprint.route("/settings")
def settings_page():
    """configure_by_dropdown: user settings page."""
    user = _current_user()
    if not user:
        return redirect(url_for("map-services.login_page"))
    return render_template("map-services/settings.html", user=user)


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("map-services/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    # users table is small (<20 rows)
    users = db.query(SITE, "users")
    user = next((u for u in users if u["username"] == username), None)
    if user is None:
        return render_template("map-services/login.html",
                               error="Invalid username. Please try again.")
    stored_pw = user.get("password", "password")
    if password and password != stored_pw:
        return render_template("map-services/login.html", error="Invalid password")
    session["user_id"] = user["id"]
    emit("signup", user_id=user["id"], site_name="map-services", username=request.form.get("username", ""), password=request.form.get("password", ""), email="")
    return redirect(url_for("map-services.index"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("map-services.index"))


# ---------------------------------------------------------------------------
# Form-based mutation routes (for browser automation compatibility)
# ---------------------------------------------------------------------------

@blueprint.route("/place/<int:place_id>/save", methods=["POST"])
def form_save_place(place_id):
    """save_by_query: toggle save for a place."""
    user = _current_user()
    if not user:
        return redirect(url_for("map-services.login_page"))
    existing = db.query(SITE, "saved_places",
                        where={"user_id": user["id"], "location_id": place_id},
                        limit=1)
    if existing:
        db.delete_item(SITE, "saved_places", existing[0]["id"])
    else:
        loc = db.get_item(SITE, "locations", place_id)
        if loc:
            max_id_val = db.execute(
                f"SELECT MAX(id) FROM [{db.get_table_name(SITE, 'saved_places')}]",
                fetch="val") or 0
            new_id = max_id_val + 1
            db.save_item(SITE, "saved_places", new_id, {
                "id": new_id, "user_id": user["id"], "location_id": place_id,
                "name": loc["name"], "label": "favorite",
                "address": loc["address"], "lat": loc["lat"], "lng": loc["lng"],
                "icon": "place", "added_date": datetime.utcnow().strftime("%Y-%m-%d"),
                "visit_count": 0, "last_visited": None,
            })
    return redirect(url_for("map-services.place_detail", place_id=place_id))


@blueprint.route("/place/<int:place_id>/review", methods=["POST"])
def form_post_review(place_id):
    """post_from_free_text: post a review for a place."""
    user = _current_user()
    if not user:
        return redirect(url_for("map-services.login_page"))
    text = request.form.get("text", "").strip()
    rating = request.form.get("rating", type=float, default=5.0)
    if not text:
        return redirect(url_for("map-services.place_detail", place_id=place_id))
    reviews = db.query(SITE, "reviews")
    new_id = max((r["id"] for r in reviews), default=0) + 1
    review = {
        "id": new_id,
        "location_id": place_id,
        "user_id": user["id"],
        "username": user["username"],
        "rating": min(5.0, max(1.0, rating)),
        "text": text,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    reviews.append(review)
    db.save_collection(SITE, "reviews", reviews)
    return redirect(url_for("map-services.place_detail", place_id=place_id))


@blueprint.route("/place/<int:place_id>/share", methods=["POST"])
def form_share_place(place_id):
    """share_by_query: share a place with another user by username."""
    user = _current_user()
    if not user:
        return redirect(url_for("map-services.login_page"))
    target_username = request.form.get("username", "").strip()
    # users table is small
    users = db.query(SITE, "users")
    target = next((u for u in users if u["username"] == target_username), None)
    if not target:
        return redirect(url_for("map-services.place_detail", place_id=place_id))
    loc = db.get_item(SITE, "locations", place_id)
    if not loc:
        abort(404)
    already = db.query(SITE, "saved_places",
                       where={"user_id": target["id"], "location_id": place_id},
                       limit=1)
    if not already:
        max_id_val = db.execute(
            f"SELECT MAX(id) FROM [{db.get_table_name(SITE, 'saved_places')}]",
            fetch="val") or 0
        new_id = max_id_val + 1
        db.save_item(SITE, "saved_places", new_id, {
            "id": new_id, "user_id": target["id"], "location_id": place_id,
            "name": loc["name"], "label": "shared",
            "address": loc["address"], "lat": loc["lat"], "lng": loc["lng"],
            "icon": "shared", "added_date": datetime.utcnow().strftime("%Y-%m-%d"),
            "visit_count": 0, "last_visited": None,
        })
    return redirect(url_for("map-services.place_detail", place_id=place_id))


@blueprint.route("/settings/update", methods=["POST"])
def form_update_settings():
    """configure_by_dropdown: update user settings."""
    user = _current_user()
    if not user:
        return redirect(url_for("map-services.login_page"))
    u = db.get_item(SITE, "users", user["id"])
    if not u:
        return redirect(url_for("map-services.login_page"))
    mode = request.form.get("default_mode", u["default_mode"])
    units = request.form.get("units", u["units"])
    if mode in ("driving", "cycling", "walking", "transit"):
        u["default_mode"] = mode
    if units in ("imperial", "metric"):
        u["units"] = units
    db.save_item(SITE, "users", u["id"], u)
    return redirect(url_for("map-services.settings_page"))


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/login", methods=["POST"])
def api_login():
    """Authenticate by username (no password for this map service)."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    # users table is small
    users = db.query(SITE, "users")
    user = next((u for u in users if u["username"] == username), None)
    if not user:
        return jsonify({"error": "Invalid username"}), 401
    stored_pw = user.get("password", "password")
    if password and password != stored_pw:
        return jsonify({"error": "Invalid password"}), 401
    session["user_id"] = user["id"]
    return jsonify({"user_id": user["id"], "username": user["username"]})


@blueprint.route("/api/locations", methods=["GET"])
def api_locations_list():
    category = request.args.get("category")            # filter_by_dropdown / search_by_dropdown
    q = request.args.get("q")                          # search_by_query
    lat = request.args.get("lat", type=float)
    lng = request.args.get("lng", type=float)
    radius = request.args.get("radius", type=float)    # search_by_proximity
    open_now = request.args.get("open_now")            # filter_by_toggle
    min_rating = request.args.get("min_rating", type=float)  # filter_by_slider
    sort = request.args.get("sort")                    # sort_by_ranking
    # Bounding box for pan/zoom: search_by_pan_zoom
    lat_min = request.args.get("lat_min", type=float)
    lat_max = request.args.get("lat_max", type=float)
    lng_min = request.args.get("lng_min", type=float)
    lng_max = request.args.get("lng_max", type=float)

    table = db.get_table_name(SITE, "locations")
    clauses = []
    params = []

    if category:
        clauses.append("[category] = ?")
        params.append(category)
    if q:
        ql = f"%{q.lower()}%"
        clauses.append("(LOWER([name]) LIKE ? OR LOWER([address]) LIKE ? OR LOWER([category]) LIKE ?)")
        params.extend([ql, ql, ql])
    if min_rating is not None:
        clauses.append("[rating] >= ?")
        params.append(min_rating)
    if all(v is not None for v in [lat_min, lat_max, lng_min, lng_max]):
        clauses.append("[lat] >= ? AND [lat] <= ? AND [lng] >= ? AND [lng] <= ?")
        params.extend([lat_min, lat_max, lng_min, lng_max])

    order_clause = ""
    if sort == "rating":
        order_clause = " ORDER BY [rating] DESC"
    elif sort == "name":
        order_clause = " ORDER BY LOWER([name]) ASC"

    sql = f"SELECT * FROM [{table}]"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += order_clause

    locations = db.execute(sql, tuple(params))

    # Python-side filters that cannot be expressed in simple SQL
    if open_now == "1":
        def _hours_to_str(h):
            return str(h) if not isinstance(h, str) else h
        locations = [l for l in locations if l.get("hours") and "closed" not in _hours_to_str(l["hours"]).lower()]
    if lat is not None and lng is not None and radius is not None:
        locations = [l for l in locations
                     if _haversine(lat, lng, l["lat"], l["lng"]) <= radius]
        for l in locations:
            l["distance_km"] = round(_haversine(lat, lng, l["lat"], l["lng"]), 2)
        locations.sort(key=lambda l: l["distance_km"])

    if sort == "distance" and lat is not None and lng is not None:
        for l in locations:
            if "distance_km" not in l:
                l["distance_km"] = round(_haversine(lat, lng, l["lat"], l["lng"]), 2)
        locations.sort(key=lambda l: l["distance_km"])

    return jsonify(locations)


@blueprint.route("/api/locations/<int:location_id>", methods=["GET"])
def api_location_detail(location_id):
    loc = db.get_item(SITE, "locations", location_id)
    if not loc:
        abort(404)
    return jsonify(loc)


@blueprint.route("/api/locations", methods=["POST"])
def api_location_create():
    """create_from_free_text: add a new location/POI."""
    data = request.get_json(force=True)
    table = db.get_table_name(SITE, "locations")
    max_id = db.execute(f"SELECT MAX(id) FROM [{table}]", fetch="val") or 0
    new_id = max_id + 1
    new_loc = {
        "id": new_id,
        "name": data.get("name", ""),
        "category": data.get("category", "other"),
        "address": data.get("address", ""),
        "lat": data.get("lat", 0.0),
        "lng": data.get("lng", 0.0),
        "phone": data.get("phone"),
        "hours": data.get("hours", ""),
        "rating": data.get("rating", 0.0),
    }
    db.save_item(SITE, "locations", new_id, new_loc)
    return jsonify(new_loc), 201


@blueprint.route("/api/locations/semantic", methods=["GET"])
def api_semantic_search():
    """search_by_semantic: ranked keyword-overlap search."""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    locations = db.query(SITE, "locations")
    scored = [(loc, _semantic_score(q, loc)) for loc in locations]
    scored = [(loc, s) for loc, s in scored if s > 0]
    scored.sort(key=lambda x: -x[1])
    return jsonify([loc for loc, _ in scored])


@blueprint.route("/api/categories", methods=["GET"])
def api_categories():
    """navigate_by_dropdown / search_by_dropdown: list all categories with counts."""
    table = db.get_table_name(SITE, "locations")
    rows = db.execute(
        f"SELECT [category], COUNT(*) as cnt FROM [{table}] GROUP BY [category] ORDER BY [category]")
    return jsonify([{"name": r["category"], "count": r["cnt"]} for r in rows])


@blueprint.route("/api/categories/<path:cat_name>/locations", methods=["GET"])
def api_category_locations(cat_name):
    """search_by_dropdown: get all locations in a category."""
    locations = db.query(SITE, "locations", where={"category": cat_name})
    return jsonify(locations)


@blueprint.route("/api/routes", methods=["GET"])
def api_routes_list():
    user = _current_user()
    user_id = request.args.get("user_id", type=int)
    where = {}
    if user_id:
        where["user_id"] = user_id
    elif user:
        where["user_id"] = user["id"]
    mode = request.args.get("mode")                    # route_by_radio
    if mode:
        where["mode"] = mode
    routes = db.query(SITE, "routes", where=where if where else None)
    return jsonify(routes)


@blueprint.route("/api/routes", methods=["POST"])
def api_route_create():
    """route_by_query / route_by_route: compute and save a route."""
    data = request.get_json(force=True)
    table = db.get_table_name(SITE, "routes")
    max_id = db.execute(f"SELECT MAX(id) FROM [{table}]", fetch="val") or 0
    new_id = max_id + 1
    user = _current_user()
    uid = user["id"] if user else data.get("user_id", 1)

    origin = data.get("origin", "")
    destination = data.get("destination", "")
    mode = data.get("mode", "driving")

    # Search for origin/destination in locations
    origin_loc = _find_loc(origin)
    dest_loc = _find_loc(destination)

    if origin_loc and dest_loc:
        dist = round(_haversine(origin_loc["lat"], origin_loc["lng"],
                                dest_loc["lat"], dest_loc["lng"]), 1)
    else:
        dist = data.get("distance_km", 5.0)

    speed_map = {"driving": 30, "cycling": 15, "walking": 5, "transit": 20}
    speed = speed_map.get(mode, 30)
    duration = max(1, round(dist / speed * 60))

    # Find best matching pre-computed route template for geometry
    geometry = []
    steps = data.get("steps")
    if origin_loc and dest_loc:
        templates = db.execute(
            "SELECT * FROM map_services_route_templates WHERE mode = ? LIMIT 100",
            (mode if mode != "cycling" else "walking",))
        best_dist = float("inf")
        for tmpl in templates:
            d1 = _haversine(origin_loc["lat"], origin_loc["lng"], tmpl["origin_lat"], tmpl["origin_lng"])
            d2 = _haversine(dest_loc["lat"], dest_loc["lng"], tmpl["dest_lat"], tmpl["dest_lng"])
            # Also check reverse direction
            d1r = _haversine(origin_loc["lat"], origin_loc["lng"], tmpl["dest_lat"], tmpl["dest_lng"])
            d2r = _haversine(dest_loc["lat"], dest_loc["lng"], tmpl["origin_lat"], tmpl["origin_lng"])
            total = min(d1 + d2, d1r + d2r)
            if total < best_dist:
                best_dist = total
                import json as _json
                geometry = tmpl.get("geometry", [])
                if isinstance(geometry, str):
                    geometry = _json.loads(geometry)
                tmpl_steps = tmpl.get("steps", [])
                if isinstance(tmpl_steps, str):
                    tmpl_steps = _json.loads(tmpl_steps)
                if not steps and tmpl_steps:
                    steps = tmpl_steps
                dist = tmpl["distance_km"]
                duration = tmpl["duration_minutes"]
                # Reverse geometry if reverse match was better
                if d1r + d2r < d1 + d2:
                    geometry = list(reversed(geometry))

    if not steps:
        steps = [
            {"instruction": f"Head toward {destination}",
             "distance_km": round(dist / 2, 1),
             "duration_minutes": duration // 2},
            {"instruction": f"Arrive at {destination}",
             "distance_km": round(dist / 2, 1),
             "duration_minutes": duration - duration // 2},
        ]

    # Fallback geometry: straight line between origin and destination
    if not geometry and origin_loc and dest_loc:
        geometry = [[origin_loc["lat"], origin_loc["lng"]],
                     [dest_loc["lat"], dest_loc["lng"]]]

    new_route = {
        "id": new_id,
        "user_id": uid,
        "name": data.get("name", f"{origin} to {destination}"),
        "origin": origin,
        "destination": destination,
        "distance_km": dist,
        "duration_minutes": duration,
        "mode": mode,
        "saved_date": datetime.utcnow().strftime("%Y-%m-%d"),
        "last_used": datetime.utcnow().strftime("%Y-%m-%d"),
        "use_count": 1,
        "steps": steps,
        "geometry": geometry,
        "origin_location": {"lat": origin_loc["lat"], "lng": origin_loc["lng"], "name": origin_loc["name"]} if origin_loc else None,
        "destination_location": {"lat": dest_loc["lat"], "lng": dest_loc["lng"], "name": dest_loc["name"]} if dest_loc else None,
    }
    db.save_item(SITE, "routes", new_id, new_route)
    return jsonify(new_route), 201


@blueprint.route("/api/routes/<int:route_id>", methods=["GET"])
def api_route_detail(route_id):
    """route_by_route: get route details by ID."""
    route = db.get_item(SITE, "routes", route_id)
    if not route:
        abort(404)
    return jsonify(route)


@blueprint.route("/api/routes/<int:route_id>", methods=["DELETE"])
def api_route_delete(route_id):
    route = db.get_item(SITE, "routes", route_id)
    if not route:
        abort(404)
    db.delete_item(SITE, "routes", route_id)
    return jsonify({"status": "deleted", "id": route_id})


@blueprint.route("/api/routes/compute", methods=["GET"])
def api_route_compute():
    """compute_by_route: compute distance/duration without saving."""
    origin = request.args.get("origin", "")
    destination = request.args.get("destination", "")
    mode = request.args.get("mode", "driving")
    check_modes = request.args.get("check_modes", "")

    table = db.get_table_name(SITE, "locations")
    origin_loc = _find_loc(origin) if origin else None
    dest_loc = _find_loc(destination) if destination else None

    # Check which modes have pre-computed route templates
    if check_modes and origin_loc and dest_loc:
        templates = db.execute(
            "SELECT DISTINCT mode FROM map_services_route_templates")
        all_modes = [t["mode"] for t in templates]
        # Check which have a close match for this origin/dest pair
        available = []
        for m in all_modes:
            matches = db.execute(
                "SELECT id FROM map_services_route_templates WHERE mode = ? LIMIT 1", (m,))
            if matches:
                # Check if any template is within ~5km of both endpoints
                close = db.execute(
                    "SELECT id FROM map_services_route_templates WHERE mode = ? "
                    "AND ABS(origin_lat - ?) < 0.05 AND ABS(origin_lng - ?) < 0.05 "
                    "AND ABS(dest_lat - ?) < 0.05 AND ABS(dest_lng - ?) < 0.05 LIMIT 1",
                    (m, origin_loc["lat"], origin_loc["lng"], dest_loc["lat"], dest_loc["lng"]))
                if close:
                    available.append(m)
                else:
                    # Also check reverse direction
                    close_rev = db.execute(
                        "SELECT id FROM map_services_route_templates WHERE mode = ? "
                        "AND ABS(dest_lat - ?) < 0.05 AND ABS(dest_lng - ?) < 0.05 "
                        "AND ABS(origin_lat - ?) < 0.05 AND ABS(origin_lng - ?) < 0.05 LIMIT 1",
                        (m, origin_loc["lat"], origin_loc["lng"], dest_loc["lat"], dest_loc["lng"]))
                    if close_rev:
                        available.append(m)
        # Always allow walking/driving as fallback (straight line)
        if "walking" not in available:
            available.append("walking")
        if "driving" not in available:
            available.append("driving")
        return jsonify({"available_modes": available})

    if not origin_loc or not dest_loc:
        return jsonify({"error": "Could not resolve origin or destination"}), 400

    dist = round(_haversine(origin_loc["lat"], origin_loc["lng"],
                            dest_loc["lat"], dest_loc["lng"]), 1)

    speed_map = {"driving": 30, "cycling": 15, "walking": 5, "transit": 20}
    speed = speed_map.get(mode, 30)
    duration = max(1, round(dist / speed * 60))

    return jsonify({
        "origin": origin, "destination": destination, "mode": mode,
        "distance_km": dist, "duration_minutes": duration,
        "origin_location": origin_loc, "destination_location": dest_loc,
    })


@blueprint.route("/api/compare", methods=["GET"])
def api_compare():
    """compare_by_route: compare multiple places side-by-side."""
    ids_str = request.args.get("ids", "")
    ids = [int(x) for x in ids_str.split(",") if x.strip().isdigit()]
    selected = [db.get_item(SITE, "locations", lid) for lid in ids]
    selected = [s for s in selected if s]
    return jsonify(selected)


@blueprint.route("/api/saved-places", methods=["GET"])
def api_saved_places_list():
    user = _current_user()
    user_id = request.args.get("user_id", type=int)
    if user_id:
        saved = db.query(SITE, "saved_places", where={"user_id": user_id})
    elif user:
        saved = db.query(SITE, "saved_places", where={"user_id": user["id"]})
    else:
        saved = db.query(SITE, "saved_places")
    return jsonify(saved)


@blueprint.route("/api/saved-places", methods=["POST"])
def api_saved_place_create():
    """save_by_query: save a place."""
    data = request.get_json(force=True)
    user = _current_user()
    uid = user["id"] if user else data.get("user_id", 1)

    location_id = data.get("location_id")
    loc = None
    if location_id:
        loc = db.get_item(SITE, "locations", location_id)

    # Check if already saved -- toggle behavior
    existing = db.query(SITE, "saved_places",
                        where={"user_id": uid, "location_id": location_id},
                        limit=1)
    if existing:
        db.delete_item(SITE, "saved_places", existing[0]["id"])
        return jsonify({"action": "unsaved", "id": existing[0]["id"], "location_id": location_id})

    table = db.get_table_name(SITE, "saved_places")
    max_id_val = db.execute(f"SELECT MAX(id) FROM [{table}]", fetch="val") or 0
    new_id = max_id_val + 1
    new_saved = {
        "id": new_id,
        "user_id": uid,
        "location_id": location_id,
        "name": data.get("name", loc["name"] if loc else ""),
        "label": data.get("label", "favorite"),
        "address": data.get("address", loc["address"] if loc else ""),
        "lat": data.get("lat", loc["lat"] if loc else 0.0),
        "lng": data.get("lng", loc["lng"] if loc else 0.0),
        "icon": data.get("icon", "place"),
        "added_date": datetime.utcnow().strftime("%Y-%m-%d"),
        "visit_count": 0,
        "last_visited": None,
    }
    db.save_item(SITE, "saved_places", new_id, new_saved)
    return jsonify({"action": "saved", **new_saved}), 201


@blueprint.route("/api/saved-places/<int:place_id>", methods=["DELETE"])
def api_saved_place_delete(place_id):
    place = db.get_item(SITE, "saved_places", place_id)
    if not place:
        abort(404)
    db.delete_item(SITE, "saved_places", place_id)
    return jsonify({"status": "deleted", "id": place_id})


@blueprint.route("/api/search", methods=["GET"])
def api_search():
    """search_by_query: search locations."""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    table = db.get_table_name(SITE, "locations")
    ql = f"%{q.lower()}%"
    results = db.execute(
        f"SELECT * FROM [{table}] WHERE LOWER([name]) LIKE ? OR LOWER([address]) LIKE ? OR LOWER([category]) LIKE ?",
        (ql, ql, ql))

    user = _current_user()
    if user and results:
        sh_table = db.get_table_name(SITE, "search_history")
        max_id_val = db.execute(f"SELECT MAX(id) FROM [{sh_table}]", fetch="val") or 0
        new_id = max_id_val + 1
        db.save_item(SITE, "search_history", new_id, {
            "id": new_id,
            "user_id": user["id"],
            "query": q,
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "result_selected": results[0]["name"],
            "result_address": results[0]["address"],
        })

    return jsonify(results)


@blueprint.route("/api/search-history", methods=["GET"])
def api_search_history():
    user = _current_user()
    if user:
        sh = db.query(SITE, "search_history",
                      where={"user_id": user["id"]},
                      sort="-timestamp")
    else:
        sh = db.query(SITE, "search_history", sort="-timestamp")
    return jsonify(sh)


@blueprint.route("/api/nearby", methods=["GET"])
def api_nearby():
    """search_by_proximity: find places near a point."""
    lat = request.args.get("lat", type=float)
    lng = request.args.get("lng", type=float)
    radius = request.args.get("radius", type=float, default=2.0)
    category = request.args.get("category")
    if lat is None or lng is None:
        return jsonify({"error": "lat and lng are required"}), 400
    if category:
        locations = db.query(SITE, "locations", where={"category": category})
    else:
        locations = db.query(SITE, "locations")
    nearby = []
    for loc in locations:
        d = _haversine(lat, lng, loc["lat"], loc["lng"])
        if d <= radius:
            loc_copy = dict(loc)
            loc_copy["distance_km"] = round(d, 2)
            nearby.append(loc_copy)
    nearby.sort(key=lambda l: l["distance_km"])
    return jsonify(nearby)


@blueprint.route("/api/reviews", methods=["GET"])
def api_reviews_list():
    """List reviews, optionally filtered by location_id."""
    location_id = request.args.get("location_id", type=int)
    if location_id is not None:
        reviews = db.query(SITE, "reviews",
                           where={"location_id": location_id},
                           sort="-timestamp")
    else:
        reviews = db.query(SITE, "reviews", sort="-timestamp")
    return jsonify(reviews)


@blueprint.route("/api/reviews", methods=["POST"])
def api_review_create():
    """post_from_free_text / rate_by_slider: post a review with rating."""
    data = request.get_json(force=True)
    user = _current_user()
    uid = user["id"] if user else data.get("user_id", 1)
    uname = user["username"] if user else data.get("username", "anonymous")

    location_id = data.get("location_id")
    text = data.get("text", "").strip()
    rating = data.get("rating", 5.0)
    if not text:
        return jsonify({"error": "text is required"}), 400

    reviews = db.query(SITE, "reviews")
    new_id = max((r["id"] for r in reviews), default=0) + 1
    review = {
        "id": new_id,
        "location_id": location_id,
        "user_id": uid,
        "username": uname,
        "rating": min(5.0, max(1.0, float(rating))),
        "text": text,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    reviews.append(review)
    db.save_collection(SITE, "reviews", reviews)
    return jsonify(review), 201


@blueprint.route("/api/share", methods=["POST"])
def api_share_place():
    """share_by_query: share a place with another user."""
    data = request.get_json(force=True)
    location_id = data.get("location_id")
    target_username = data.get("username", "").strip()
    if not location_id or not target_username:
        return jsonify({"error": "location_id and username are required"}), 400

    # users table is small
    users = db.query(SITE, "users")
    target = next((u for u in users if u["username"] == target_username), None)
    if not target:
        return jsonify({"error": "User not found"}), 404

    loc = db.get_item(SITE, "locations", location_id)
    if not loc:
        return jsonify({"error": "Location not found"}), 404

    already = db.query(SITE, "saved_places",
                       where={"user_id": target["id"], "location_id": location_id},
                       limit=1)
    if already:
        return jsonify({"action": "already_shared", "location_id": location_id,
                        "target_user": target_username})

    table = db.get_table_name(SITE, "saved_places")
    max_id_val = db.execute(f"SELECT MAX(id) FROM [{table}]", fetch="val") or 0
    new_id = max_id_val + 1
    new_saved = {
        "id": new_id, "user_id": target["id"], "location_id": location_id,
        "name": loc["name"], "label": "shared",
        "address": loc["address"], "lat": loc["lat"], "lng": loc["lng"],
        "icon": "shared", "added_date": datetime.utcnow().strftime("%Y-%m-%d"),
        "visit_count": 0, "last_visited": None,
    }
    db.save_item(SITE, "saved_places", new_id, new_saved)
    return jsonify({"action": "shared", "location_id": location_id,
                    "target_user": target_username, "saved_place_id": new_id}), 201


@blueprint.route("/api/users/<int:user_id>", methods=["GET"])
def api_user_detail(user_id):
    """Get user profile (for verifiers)."""
    user = db.get_item(SITE, "users", user_id)
    if not user:
        abort(404)
    return jsonify(user)


@blueprint.route("/api/users/<int:user_id>/settings", methods=["PUT"])
def api_user_settings(user_id):
    """configure_by_dropdown: update user preferences via API."""
    data = request.get_json(force=True)
    user = db.get_item(SITE, "users", user_id)
    if not user:
        abort(404)
    if "default_mode" in data and data["default_mode"] in ("driving", "cycling", "walking", "transit"):
        user["default_mode"] = data["default_mode"]
    if "units" in data and data["units"] in ("imperial", "metric"):
        user["units"] = data["units"]
    db.save_item(SITE, "users", user_id, user)
    return jsonify(user)


@blueprint.route("/api/export", methods=["GET"])
def api_export():
    """export_by_route: export locations data as JSON or CSV."""
    fmt = request.args.get("format", "json").lower()
    category = request.args.get("category", "").strip()
    if category:
        locations = db.query(SITE, "locations", where={"category": category})
    else:
        locations = db.query(SITE, "locations")

    if fmt == "csv":
        lines = ["id,name,category,address,lat,lng,phone,hours,rating"]
        for loc in locations:
            name = loc["name"].replace('"', '""')
            addr = loc["address"].replace('"', '""')
            phone = str(loc.get("phone") or "").replace('"', '""')
            hours = str(loc.get("hours") or "").replace('"', '""')
            lines.append(f'{loc["id"]},"{name}","{loc["category"]}","{addr}",'
                         f'{loc["lat"]},{loc["lng"]},"{phone}","{hours}",{loc["rating"]}')
        return Response("\n".join(lines), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=locations.csv"})
    return jsonify(locations)


@blueprint.route("/api/stats", methods=["GET"])
def api_stats():
    category = request.args.get("category", "").strip()
    table = db.get_table_name(SITE, "locations")

    if category:
        locations = db.query(SITE, "locations", where={"category": category})
    else:
        locations = db.query(SITE, "locations")

    total_routes = db.count(SITE, "routes")
    total_saved = db.count(SITE, "saved_places")
    total_searches = db.count(SITE, "search_history")
    total_users = db.count(SITE, "users")

    categories = {}
    for loc in locations:
        cat = loc["category"]
        categories[cat] = categories.get(cat, 0) + 1

    avg_rating = sum(l["rating"] for l in locations) / len(locations) if locations else 0
    ratings = [l["rating"] for l in locations]

    return jsonify({
        "total_locations": len(locations),
        "total_routes": total_routes,
        "total_saved_places": total_saved,
        "total_searches": total_searches,
        "total_users": total_users,
        "categories": categories,
        "average_rating": round(avg_rating, 2),
        "min_rating": min(ratings) if ratings else 0,
        "max_rating": max(ratings) if ratings else 0,
    })


@blueprint.route("/api/select", methods=["GET"])
def api_select():
    """select_by_query: select a specific location by name query, returns first match."""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "q is required"}), 400
    table = db.get_table_name(SITE, "locations")
    ql = f"%{q.lower()}%"
    match = db.execute(
        f"SELECT * FROM [{table}] WHERE LOWER([name]) LIKE ? LIMIT 1",
        (ql,), fetch="one")
    if not match:
        return jsonify({"error": "No match found"}), 404
    return jsonify(match)


@blueprint.route("/api/submit-feedback", methods=["POST"])
def api_submit_feedback():
    """submit_by_query: submit feedback about a location (e.g. report wrong info)."""
    data = request.get_json(force=True)
    location_id = data.get("location_id")
    feedback_type = data.get("type", "correction")
    message = data.get("message", "").strip()
    if not location_id or not message:
        return jsonify({"error": "location_id and message are required"}), 400
    # In a real app this would store in a DB; here we just acknowledge
    return jsonify({
        "status": "submitted",
        "location_id": location_id,
        "type": feedback_type,
        "message": message,
    })
