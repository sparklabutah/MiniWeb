"""Lakeport Weather -- local weather portal for Lakeport, WA (fictional PNW city).

Serves current conditions, 7-day forecast, hourly forecast, historical data,
weather alerts, and saved-location management.  Data files live under the
shared data_sources/weather/ directory.
"""

import math
import pathlib

from markupsafe import Markup
from flask import (
    Blueprint,
    Response,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from app import db
from app.handlers.email_handler import _add_email

SITE = "weather"

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SITE_DIR = pathlib.Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Blueprint
# ---------------------------------------------------------------------------

blueprint = Blueprint(
    "weather",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def _current_user():
    """Return the logged-in user dict or None."""
    uid = session.get("weather_user_id")
    if uid is None:
        return None
    return db.get_item(SITE, "users", uid)


def _get_location_by_id(loc_id):
    """Return a location dict by id, or None."""
    return db.get_item(SITE, "locations", loc_id)


def _get_location_by_name(name):
    """Return a location dict whose name matches (case-insensitive)."""
    # locations table is small (<20 rows), OK without limit
    locations = db.query(SITE, "locations")
    name_lower = name.strip().lower()
    for loc in locations:
        if loc["name"].lower() == name_lower:
            return loc
    return None


# ---------------------------------------------------------------------------
# Condition icon helper
# ---------------------------------------------------------------------------

_CONDITION_ICONS = {
    "sunny": "&#9728;&#65039;",          # sun
    "mostly sunny": "&#127780;&#65039;",  # sun behind small cloud
    "partly cloudy": "&#9925;",           # sun behind cloud
    "mostly cloudy": "&#9729;&#65039;",   # cloud
    "overcast": "&#9729;&#65039;",        # cloud
    "cloudy": "&#9729;&#65039;",
    "light rain": "&#127782;&#65039;",    # cloud with rain
    "rain": "&#127783;&#65039;",          # cloud with lightning and rain
    "showers": "&#127782;&#65039;",
    "heavy rain": "&#127783;&#65039;",
    "thunderstorm": "&#9928;&#65039;",
    "snow": "&#127784;&#65039;",
    "fog": "&#127787;&#65039;",
    "clear": "&#127769;",                 # crescent moon
    "mostly clear": "&#127769;",
}


def _icon_for(conditions):
    """Return an HTML entity icon string for a weather condition."""
    return Markup(_CONDITION_ICONS.get(conditions.strip().lower(), "&#9729;&#65039;"))


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------


@blueprint.route("/")
def index():
    """Landing page -- current conditions + 7-day summary."""
    current = db.query(SITE, "current", limit=1)[0]
    # Optional ?location= query navigates to another location's conditions
    location_name = request.args.get("location", "").strip()
    location_error = None
    if location_name:
        loc = _get_location_by_name(location_name)
        if loc:
            current["location"] = loc["name"]
            current["lat"] = loc["lat"]
            current["lng"] = loc["lng"]
        else:
            location_error = f"Location '{location_name}' not found"
    forecast = db.query(SITE, "forecast")  # only 7 rows
    alerts = db.query(SITE, "alerts")      # only 3 rows
    user = _current_user()
    return render_template(
        "weather/index.html",
        current=current,
        forecast=forecast,
        alerts=alerts,
        user=user,
        icon_for=_icon_for,
        location_error=location_error,
    )


@blueprint.route("/forecast")
def forecast_page():
    """Extended 7-day forecast page."""
    forecast = db.query(SITE, "forecast")  # only 7 rows
    user = _current_user()
    return render_template(
        "weather/forecast.html",
        forecast=forecast,
        user=user,
        icon_for=_icon_for,
    )


@blueprint.route("/hourly")
def hourly_page():
    """24-hour hourly forecast page."""
    hourly = db.query(SITE, "hourly")      # only 24 rows
    current = db.query(SITE, "current", limit=1)[0]
    user = _current_user()
    return render_template(
        "weather/hourly.html",
        hourly=hourly,
        current=current,
        user=user,
        icon_for=_icon_for,
    )


@blueprint.route("/history")
def history_page():
    """30-day historical weather page."""
    table = db.get_table_name(SITE, "historical")
    # Compute stats via SQL aggregation
    stats_row = db.execute(
        f"SELECT AVG(high_f) as avg_high, AVG(low_f) as avg_low, "
        f"MAX(high_f) as max_high, MIN(low_f) as min_low, "
        f"SUM(precip_in) as total_precip, "
        f"SUM(CASE WHEN precip_in > 0 THEN 1 ELSE 0 END) as rainy_days "
        f"FROM [{table}]",
        fetch="one")
    # Optional date-range navigation (same pattern as api_historical)
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    if date_from or date_to:
        clauses = []
        params = []
        if date_from:
            clauses.append("[date] >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("[date] <= ?")
            params.append(date_to)
        sql = f"SELECT * FROM [{table}] WHERE " + " AND ".join(clauses) + " ORDER BY [date]"
        historical = db.execute(sql, tuple(params))
    else:
        historical = db.query(SITE, "historical", sort="date")  # 30 rows
    user = _current_user()
    if stats_row and stats_row.get("avg_high") is not None:
        stats = {
            "avg_high": round(stats_row["avg_high"], 1),
            "avg_low": round(stats_row["avg_low"], 1),
            "max_high": stats_row["max_high"],
            "min_low": stats_row["min_low"],
            "total_precip": round(stats_row["total_precip"], 2),
            "rainy_days": stats_row["rainy_days"],
        }
    else:
        stats = {}
    return render_template(
        "weather/history.html",
        historical=historical,
        stats=stats,
        user=user,
    )


@blueprint.route("/alerts")
def alerts_page():
    """Active weather alerts page."""
    alerts = db.query(SITE, "alerts")  # only 3 rows
    user = _current_user()
    return render_template(
        "weather/alerts.html",
        alerts=alerts,
        user=user,
    )


@blueprint.route("/locations")
def locations_page():
    """Saved locations management page (requires login)."""
    user = _current_user()
    if not user:
        return redirect(url_for("weather.login_page", next="locations"))
    # locations table is small (<20 rows)
    locations = db.query(SITE, "locations")
    user_loc_ids = set(user.get("saved_locations", []))
    saved = [loc for loc in locations if loc["id"] in user_loc_ids]
    all_locations = locations
    return render_template(
        "weather/locations.html",
        saved=saved,
        all_locations=all_locations,
        user=user,
    )


@blueprint.route("/login", methods=["GET"])
def login_page():
    """Login page."""
    user = _current_user()
    if user:
        return redirect(url_for("weather.index"))
    return render_template("weather/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    """Handle login form submission."""
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    # users table is small (<20 rows)
    users = db.query(SITE, "users")
    for u in users:
        if u["username"] == username and u["password"] == password:
            session["weather_user_id"] = u["id"]
            next_page = request.args.get("next", "")
            if next_page == "locations":
                return redirect(url_for("weather.locations_page"))
            return redirect(url_for("weather.index"))
    return render_template("weather/login.html", error="Invalid username or password.")


@blueprint.route("/logout")
def logout():
    """Log out the current user."""
    session.pop("weather_user_id", None)
    return redirect(url_for("weather.index"))


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------


@blueprint.route("/api/current")
def api_current():
    """Return current weather conditions.

    Query params:
        location  -- location name (default: Lakeport, WA)
    """
    location_name = request.args.get("location", "Lakeport, WA")
    current = db.query(SITE, "current", limit=1)[0]
    loc = _get_location_by_name(location_name)
    if loc:
        current["location"] = loc["name"]
        current["lat"] = loc["lat"]
        current["lng"] = loc["lng"]
    elif location_name.lower() != current["location"].lower():
        return jsonify({"error": f"Location '{location_name}' not found"}), 404
    return jsonify(current)


@blueprint.route("/api/forecast")
def api_forecast():
    """Return multi-day forecast.

    Query params:
        location -- location name (default: Lakeport, WA)
        days     -- number of days, 1-7 (default: 7)
    """
    location_name = request.args.get("location", "Lakeport, WA")
    days = request.args.get("days", "7")
    try:
        days = max(1, min(7, int(days)))
    except (ValueError, TypeError):
        days = 7
    forecast = db.query(SITE, "forecast", limit=days)
    loc = _get_location_by_name(location_name)
    if loc:
        return jsonify({"location": loc["name"], "forecast": forecast})
    elif location_name.lower() != "lakeport, wa":
        return jsonify({"error": f"Location '{location_name}' not found"}), 404
    return jsonify({"location": "Lakeport, WA", "forecast": forecast})


@blueprint.route("/api/hourly")
def api_hourly():
    """Return 24-hour hourly forecast.

    Query params:
        location -- location name (default: Lakeport, WA)
    """
    location_name = request.args.get("location", "Lakeport, WA")
    hourly = db.query(SITE, "hourly")  # only 24 rows
    loc = _get_location_by_name(location_name)
    if loc:
        return jsonify({"location": loc["name"], "hourly": hourly})
    elif location_name.lower() != "lakeport, wa":
        return jsonify({"error": f"Location '{location_name}' not found"}), 404
    return jsonify({"location": "Lakeport, WA", "hourly": hourly})


@blueprint.route("/api/historical")
def api_historical():
    """Return historical weather data.

    Query params:
        date_from -- start date YYYY-MM-DD (inclusive)
        date_to   -- end date YYYY-MM-DD (inclusive)
    """
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    table = db.get_table_name(SITE, "historical")

    if date_from or date_to:
        clauses = []
        params = []
        if date_from:
            clauses.append("[date] >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("[date] <= ?")
            params.append(date_to)
        sql = f"SELECT * FROM [{table}] WHERE " + " AND ".join(clauses) + " ORDER BY [date]"
        historical = db.execute(sql, tuple(params))
    else:
        historical = db.query(SITE, "historical", sort="date")  # 30 rows

    return jsonify({"location": "Lakeport, WA", "historical": historical})


@blueprint.route("/api/alerts")
def api_alerts():
    """Return active weather alerts."""
    alerts = db.query(SITE, "alerts")  # only 3 rows
    return jsonify({"location": "Lakeport, WA", "alerts": alerts})


@blueprint.route("/api/locations", methods=["GET"])
def api_locations_get():
    """Return all saved locations, or the logged-in user's saved locations."""
    user = _current_user()
    # locations table is small (<20 rows)
    locations = db.query(SITE, "locations")
    if user:
        user_loc_ids = set(user.get("saved_locations", []))
        user_locs = [loc for loc in locations if loc["id"] in user_loc_ids]
        return jsonify({"user": user["username"], "locations": user_locs})
    return jsonify({"locations": locations})


@blueprint.route("/api/locations", methods=["POST"])
def api_locations_post():
    """Add a new saved location.

    Expects JSON body: {"name": "City, ST", "lat": 47.0, "lng": -122.0}
    Requires login.
    """
    user = _current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    lat = data.get("lat")
    lng = data.get("lng")
    if not name:
        return jsonify({"error": "Location name is required"}), 400
    # locations table is small (<20 rows)
    locations = db.query(SITE, "locations")
    # Check duplicate
    if any(loc["name"].lower() == name.lower() for loc in locations):
        # Location exists, just add to user's list
        existing = next(l for l in locations if l["name"].lower() == name.lower())
        u = db.get_item(SITE, "users", user["id"])
        if u and existing["id"] not in u["saved_locations"]:
            u["saved_locations"].append(existing["id"])
            db.save_item(SITE, "users", u["id"], u)
        return jsonify({"message": "Location added to your saved list", "location": existing}), 200
    # Create new location
    max_id = max((loc["id"] for loc in locations), default=0)
    new_loc = {
        "id": max_id + 1,
        "name": name,
        "lat": float(lat) if lat is not None else 0.0,
        "lng": float(lng) if lng is not None else 0.0,
        "is_default": False,
    }
    db.save_item(SITE, "locations", new_loc["id"], new_loc)
    # Add to user's saved list
    u = db.get_item(SITE, "users", user["id"])
    if u:
        u["saved_locations"].append(new_loc["id"])
        db.save_item(SITE, "users", u["id"], u)
    return jsonify({"message": "Location created and saved", "location": new_loc}), 201


@blueprint.route("/api/locations", methods=["DELETE"])
def api_locations_delete():
    """Remove a location from the user's saved list.

    Expects JSON body: {"location_id": 5}
    Requires login.
    """
    user = _current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401
    data = request.get_json(silent=True) or {}
    loc_id = data.get("location_id")
    if loc_id is None:
        return jsonify({"error": "location_id is required"}), 400
    try:
        loc_id = int(loc_id)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid location_id"}), 400
    u = db.get_item(SITE, "users", user["id"])
    if not u:
        return jsonify({"error": "User not found"}), 404
    if loc_id not in u["saved_locations"]:
        return jsonify({"error": "Location not in your saved list"}), 404
    u["saved_locations"].remove(loc_id)
    db.save_item(SITE, "users", u["id"], u)
    return jsonify({"message": "Location removed from saved list"}), 200


@blueprint.route("/api/stats")
def api_stats():
    """Return computed statistics over the historical data.

    Returns avg high/low, max high, min low, total precipitation,
    and number of rainy days.
    """
    table = db.get_table_name(SITE, "historical")
    # Use SQL aggregation instead of loading all rows
    stats_row = db.execute(
        f"SELECT COUNT(*) as cnt, AVG(high_f) as avg_high, AVG(low_f) as avg_low, "
        f"AVG(avg_temp_f) as avg_mean, MAX(high_f) as max_high, MIN(low_f) as min_low, "
        f"SUM(precip_in) as total_precip, MAX(precip_in) as max_precip, "
        f"SUM(CASE WHEN precip_in > 0 THEN 1 ELSE 0 END) as rainy_days, "
        f"SUM(CASE WHEN precip_in = 0 THEN 1 ELSE 0 END) as dry_days, "
        f"MIN([date]) as first_date, MAX([date]) as last_date "
        f"FROM [{table}]",
        fetch="one")
    if not stats_row or stats_row["cnt"] == 0:
        return jsonify({"error": "No historical data available"}), 404

    # Conditions summary via SQL
    cond_rows = db.execute(
        f"SELECT conditions, COUNT(*) as cnt FROM [{table}] "
        f"GROUP BY conditions ORDER BY cnt DESC")
    conditions_summary = {r["conditions"]: r["cnt"] for r in cond_rows}

    stats = {
        "location": "Lakeport, WA",
        "period": {
            "from": stats_row["first_date"],
            "to": stats_row["last_date"],
            "days": stats_row["cnt"],
        },
        "temperature": {
            "avg_high_f": round(stats_row["avg_high"], 1),
            "avg_low_f": round(stats_row["avg_low"], 1),
            "avg_mean_f": round(stats_row["avg_mean"], 1),
            "max_high_f": stats_row["max_high"],
            "min_low_f": stats_row["min_low"],
        },
        "precipitation": {
            "total_in": round(stats_row["total_precip"], 2),
            "avg_daily_in": round(stats_row["total_precip"] / stats_row["cnt"], 3),
            "rainy_days": stats_row["rainy_days"],
            "dry_days": stats_row["dry_days"],
            "max_daily_in": stats_row["max_precip"],
        },
        "conditions_summary": conditions_summary,
    }
    return jsonify(stats)


def _haversine(lat1, lng1, lat2, lng2):
    """Return distance in miles between two lat/lng points."""
    R = 3958.8  # Earth radius in miles
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _f_to_c(f):
    """Convert Fahrenheit to Celsius, rounded to 1 decimal."""
    return round((f - 32) * 5 / 9, 1)


# ---------------------------------------------------------------------------
# API: JSON login (for test-client solutions)
# ---------------------------------------------------------------------------


@blueprint.route("/api/login", methods=["POST"])
def api_login():
    """Authenticate via JSON body.  Returns user_id on success."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "")
    password = data.get("password", "")
    # users table is small (<20 rows)
    users = db.query(SITE, "users")
    for u in users:
        if u["username"] == username and u["password"] == password:
            session["weather_user_id"] = u["id"]
            return jsonify({"user_id": u["id"], "username": u["username"]})
    return jsonify({"error": "Invalid credentials"}), 401


# ---------------------------------------------------------------------------
# API: User info
# ---------------------------------------------------------------------------


@blueprint.route("/api/users/<int:uid>")
def api_user(uid):
    """Return user profile (without password)."""
    u = db.get_item(SITE, "users", uid)
    if not u:
        return jsonify({"error": "User not found"}), 404
    safe = {k: v for k, v in u.items() if k != "password"}
    return jsonify(safe)


# ---------------------------------------------------------------------------
# API: Search locations by query string
# ---------------------------------------------------------------------------


@blueprint.route("/api/search")
def api_search():
    """Search locations by name substring.

    Query params:
        q -- query string (searches location names, case-insensitive)
    """
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"results": []})
    results = db.search(SITE, "locations", q, limit=50)
    return jsonify({"query": q.lower(), "results": results})


# ---------------------------------------------------------------------------
# API: Nearby locations (proximity search)
# ---------------------------------------------------------------------------


@blueprint.route("/api/nearby")
def api_nearby():
    """Find locations within a radius of a given point.

    Query params:
        lat    -- latitude (required)
        lng    -- longitude (required)
        radius -- radius in miles (default: 50)
    """
    try:
        lat = float(request.args.get("lat", ""))
        lng = float(request.args.get("lng", ""))
    except (ValueError, TypeError):
        return jsonify({"error": "lat and lng are required"}), 400
    radius = float(request.args.get("radius", "50"))
    # locations table is small (<20 rows)
    locations = db.query(SITE, "locations")
    nearby = []
    for loc in locations:
        dist = _haversine(lat, lng, loc["lat"], loc["lng"])
        if dist <= radius:
            nearby.append({**loc, "distance_mi": round(dist, 1)})
    nearby.sort(key=lambda x: x["distance_mi"])
    return jsonify({"lat": lat, "lng": lng, "radius_mi": radius, "results": nearby})


# ---------------------------------------------------------------------------
# API: Compare weather between two locations
# ---------------------------------------------------------------------------


@blueprint.route("/api/compare")
def api_compare():
    """Compare current weather between two locations.

    Query params:
        location1 -- first location name (e.g. 'Seattle, WA')
        location2 -- second location name (e.g. 'Portland, OR')
        locations -- pipe-separated location names (legacy, e.g. 'Seattle, WA|Portland, OR')
    """
    loc1 = request.args.get("location1", "").strip()
    loc2 = request.args.get("location2", "").strip()
    if loc1 and loc2:
        names = [loc1, loc2]
    else:
        loc_str = request.args.get("locations", "")
        # Support pipe-separated names to avoid conflict with commas in city names
        if "|" in loc_str:
            names = [n.strip() for n in loc_str.split("|") if n.strip()]
        else:
            names = [n.strip() for n in loc_str.split(",") if n.strip()]
            # Try to reassemble "City, ST" pairs from comma-split tokens
            if len(names) >= 4:
                reassembled = []
                i = 0
                while i < len(names) - 1:
                    # If the next token looks like a state abbreviation (2-3 chars),
                    # join it with the previous token
                    if len(names[i + 1]) <= 3 and names[i + 1].replace(".", "").isalpha():
                        reassembled.append(f"{names[i]}, {names[i + 1]}")
                        i += 2
                    else:
                        reassembled.append(names[i])
                        i += 1
                if i < len(names):
                    reassembled.append(names[i])
                names = reassembled
    if len(names) < 2:
        return jsonify({"error": "Provide at least 2 location names via location1&location2 or locations=Name1|Name2"}), 400
    current = db.query(SITE, "current", limit=1)[0]
    results = []
    for name in names[:5]:  # max 5
        loc = _get_location_by_name(name)
        if not loc:
            results.append({"name": name, "error": "Location not found"})
            continue
        # Simulate slightly different weather per location using id offset
        offset = (loc["id"] - 1) * 2  # small deterministic variation
        entry = {
            "name": loc["name"],
            "lat": loc["lat"],
            "lng": loc["lng"],
            "temp_f": current["temp_f"] + offset,
            "temp_c": _f_to_c(current["temp_f"] + offset),
            "humidity": max(20, min(100, current["humidity"] - offset)),
            "wind_mph": max(0, current["wind_mph"] + offset // 2),
            "conditions": current["conditions"],
        }
        results.append(entry)
    return jsonify({"comparison": results})


# ---------------------------------------------------------------------------
# API: Historical weather for a single date
# ---------------------------------------------------------------------------


@blueprint.route("/api/history/date/<date_str>")
def api_history_date(date_str):
    """Return historical weather for a specific date.

    Path param:
        date_str -- YYYY-MM-DD
    """
    table = db.get_table_name(SITE, "historical")
    d = db.execute(
        f"SELECT * FROM [{table}] WHERE [date] = ? LIMIT 1",
        (date_str,), fetch="one")
    if not d:
        return jsonify({"error": f"No data for date {date_str}"}), 404
    return jsonify(d)


# ---------------------------------------------------------------------------
# API: Locations list (for navigate_by_pan_zoom / map picker)
# ---------------------------------------------------------------------------


@blueprint.route("/api/locations/all")
def api_locations_all():
    """Return all locations with coordinates (for map display)."""
    # locations table is small (<20 rows)
    locations = db.query(SITE, "locations")
    return jsonify({"locations": locations})


# ---------------------------------------------------------------------------
# API: Unit conversion toggle (filter_by_toggle)
# ---------------------------------------------------------------------------


@blueprint.route("/api/current/units")
def api_current_units():
    """Return current conditions in the specified unit system.

    Query params:
        units -- 'imperial' (default) or 'metric'
    """
    units = request.args.get("units", "imperial").lower()
    current = db.query(SITE, "current", limit=1)[0]
    if units == "metric":
        current["display_units"] = "metric"
        current["temp_display"] = current["temp_c"]
        current["feels_like_display"] = _f_to_c(current["feels_like_f"])
        current["wind_display"] = round(current["wind_mph"] * 1.60934, 1)
        current["wind_unit"] = "km/h"
        current["visibility_display"] = round(current["visibility_mi"] * 1.60934, 1)
        current["visibility_unit"] = "km"
        current["pressure_display"] = round(current["pressure_inhg"] * 33.8639, 1)
        current["pressure_unit"] = "hPa"
    else:
        current["display_units"] = "imperial"
        current["temp_display"] = current["temp_f"]
        current["feels_like_display"] = current["feels_like_f"]
        current["wind_display"] = current["wind_mph"]
        current["wind_unit"] = "mph"
        current["visibility_display"] = current["visibility_mi"]
        current["visibility_unit"] = "mi"
        current["pressure_display"] = current["pressure_inhg"]
        current["pressure_unit"] = "inHg"
    return jsonify(current)


# ---------------------------------------------------------------------------
# API: Alerts filtered by severity toggle (filter_by_toggle)
# ---------------------------------------------------------------------------


@blueprint.route("/api/alerts/filter")
def api_alerts_filter():
    """Return alerts filtered by severity.

    Query params:
        severity -- comma-separated severity levels to include
                    e.g. 'Severe,Moderate' (case-insensitive)
                    Default: all severities shown
    """
    sev_str = request.args.get("severity", "")
    alerts = db.query(SITE, "alerts")  # only 3 rows
    if sev_str:
        allowed = {s.strip().lower() for s in sev_str.split(",")}
        alerts = [a for a in alerts if a["severity"].lower() in allowed]
    return jsonify({"alerts": alerts, "count": len(alerts)})


# ---------------------------------------------------------------------------
# API: Extended info toggle (extract_by_toggle)
# ---------------------------------------------------------------------------


@blueprint.route("/api/forecast/extended")
def api_forecast_extended():
    """Return extended forecast with extra detail fields.

    Query params:
        extended -- 'true' to include dew point, UV, pressure estimates
    """
    forecast = db.query(SITE, "forecast")  # only 7 rows
    extended = request.args.get("extended", "false").lower() == "true"
    if extended:
        for i, day in enumerate(forecast):
            day["dew_point_f"] = day["low_f"] - 3
            day["uv_index"] = max(1, 7 - i)
            day["pressure_inhg"] = round(30.1 - i * 0.05, 2)
            day["sunrise"] = "5:15 AM"
            day["sunset"] = "9:10 PM"
    return jsonify({"location": "Lakeport, WA", "extended": extended, "forecast": forecast})


# ---------------------------------------------------------------------------
# API: Subscribe / unsubscribe to weather alerts (subscribe_by_toggle)
# ---------------------------------------------------------------------------


@blueprint.route("/api/users/<int:uid>/subscribe", methods=["POST"])
def api_subscribe(uid):
    """Toggle alert subscription for a user.

    Expects JSON body: {"alert_type": "Wind Advisory"}
    or {"subscribe_all": true/false}
    """
    user = _current_user()
    if not user or user["id"] != uid:
        return jsonify({"error": "Authentication required"}), 401
    data = request.get_json(silent=True) or {}
    u = db.get_item(SITE, "users", uid)
    if not u:
        return jsonify({"error": "User not found"}), 404
    subs = u.get("subscriptions", [])
    if data.get("subscribe_all") is not None:
        if data["subscribe_all"]:
            alerts = db.query(SITE, "alerts")  # only 3 rows
            subs = list({a["type"] for a in alerts})
            u["subscriptions"] = subs
            db.save_item(SITE, "users", uid, u)
            return jsonify({"action": "subscribed_all", "subscriptions": subs})
        else:
            u["subscriptions"] = []
            db.save_item(SITE, "users", uid, u)
            return jsonify({"action": "unsubscribed_all", "subscriptions": []})
    alert_type = data.get("alert_type", "")
    if not alert_type:
        return jsonify({"error": "alert_type is required"}), 400
    if alert_type in subs:
        subs.remove(alert_type)
        action = "unsubscribed"
    else:
        subs.append(alert_type)
        action = "subscribed"
    u["subscriptions"] = subs
    db.save_item(SITE, "users", uid, u)
    if action == "subscribed":
        _add_email(uid, "noreply@weather.lakeport.local",
                   "Weather alert configured",
                   f'You have subscribed to "{alert_type}" weather alerts for Lakeport, WA.')
    return jsonify({"action": action, "alert_type": alert_type,
                    "subscriptions": subs})


# ---------------------------------------------------------------------------
# API: Configure temperature alert thresholds (configure_by_slider)
# ---------------------------------------------------------------------------


@blueprint.route("/api/users/<int:uid>/settings", methods=["GET"])
def api_settings_get(uid):
    """Return user settings including alert thresholds."""
    u = db.get_item(SITE, "users", uid)
    if not u:
        return jsonify({"error": "User not found"}), 404
    settings = u.get("settings", {
        "high_temp_threshold_f": 90,
        "low_temp_threshold_f": 32,
        "wind_threshold_mph": 30,
        "precip_threshold_pct": 70,
    })
    return jsonify({"user_id": uid, "settings": settings})


@blueprint.route("/api/users/<int:uid>/settings", methods=["POST"])
def api_settings_post(uid):
    """Update user alert threshold settings (via slider).

    Expects JSON body with any subset of:
        {"high_temp_threshold_f": 85, "low_temp_threshold_f": 28, ...}
    """
    user = _current_user()
    if not user or user["id"] != uid:
        return jsonify({"error": "Authentication required"}), 401
    data = request.get_json(silent=True) or {}
    u = db.get_item(SITE, "users", uid)
    if not u:
        return jsonify({"error": "User not found"}), 404
    settings = u.get("settings", {
        "high_temp_threshold_f": 90,
        "low_temp_threshold_f": 32,
        "wind_threshold_mph": 30,
        "precip_threshold_pct": 70,
    })
    for key in ("high_temp_threshold_f", "low_temp_threshold_f",
                "wind_threshold_mph", "precip_threshold_pct"):
        if key in data:
            try:
                settings[key] = int(data[key])
            except (ValueError, TypeError):
                pass
    u["settings"] = settings
    db.save_item(SITE, "users", uid, u)
    return jsonify({"message": "Settings updated", "settings": settings})


# ---------------------------------------------------------------------------
# API: Verify temperature reading (verify_by_slider)
# ---------------------------------------------------------------------------


@blueprint.route("/api/verify_temp")
def api_verify_temp():
    """Verify whether a user-supplied temperature matches current conditions.

    Query params:
        temp_f -- the temperature value to check
        tolerance -- acceptable range in degrees F (default: 3)

    Returns whether the supplied temp matches current within tolerance.
    """
    try:
        temp_f = float(request.args.get("temp_f", ""))
    except (ValueError, TypeError):
        return jsonify({"error": "temp_f is required"}), 400
    tolerance = float(request.args.get("tolerance", "3"))
    current = db.query(SITE, "current", limit=1)[0]
    actual = current["temp_f"]
    diff = abs(actual - temp_f)
    match = diff <= tolerance
    return jsonify({
        "submitted_temp_f": temp_f,
        "actual_temp_f": actual,
        "difference_f": round(diff, 1),
        "tolerance_f": tolerance,
        "match": match,
    })


# ---------------------------------------------------------------------------
# API: Save location by query name (save_by_query)
# ---------------------------------------------------------------------------


@blueprint.route("/api/users/<int:uid>/save_location", methods=["POST"])
def api_save_location(uid):
    """Save a location to user's list by searching for it by name.

    Expects JSON body: {"query": "Seattle"}
    Requires login.
    """
    user = _current_user()
    if not user or user["id"] != uid:
        return jsonify({"error": "Authentication required"}), 401
    data = request.get_json(silent=True) or {}
    query = data.get("query", "").strip()
    if not query:
        return jsonify({"error": "query is required"}), 400
    matches = db.search(SITE, "locations", query, limit=1)
    if not matches:
        return jsonify({"error": f"No location matching '{query}'"}), 404
    loc = matches[0]
    u = db.get_item(SITE, "users", uid)
    if not u:
        return jsonify({"error": "User not found"}), 404
    if loc["id"] in u["saved_locations"]:
        return jsonify({"action": "already_saved", "location": loc})
    u["saved_locations"].append(loc["id"])
    db.save_item(SITE, "users", uid, u)
    return jsonify({"action": "saved", "location": loc})
