"""SkyLodge Travel -- flights & hotels booking site (Expedia / Kayak style).

Data is stored in per-site SQLite tables (flights_hotels_flights,
flights_hotels_hotels, etc.) and queried through app.db.  Session
mutations are isolated per user.
"""
import json
import pathlib
from collections import Counter
from datetime import datetime

from flask import (
    Blueprint, abort, jsonify, redirect, render_template, request,
    session, url_for,
)
from app import db
from app.events import emit

SITE = "flights-hotels"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "flights-hotels",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data helpers — all data lives in SQLite via db.query() / db.save_collection()
# ---------------------------------------------------------------------------

def _fix_amenities(item):
    """Parse JSON amenities field if stored as string."""
    if isinstance(item.get("amenities"), str):
        try:
            item["amenities"] = json.loads(item["amenities"])
        except (json.JSONDecodeError, TypeError):
            item["amenities"] = []
    return item


def _query_flights(*, where=None, sort=None, limit=None, offset=0):
    """Query flights with SQL-level filtering, fix amenities."""
    flights = db.query(SITE, "flights", where=where, sort=sort, limit=limit, offset=offset)
    for f in flights:
        _fix_amenities(f)
    return flights


def _get_flight(flight_id):
    """Get a single flight by ID."""
    f = db.get_item(SITE, "flights", flight_id)
    if f:
        _fix_amenities(f)
    return f


def _query_hotels(*, where=None, sort=None, limit=None, offset=0):
    """Query hotels with SQL-level filtering, fix amenities."""
    hotels = db.query(SITE, "hotels", where=where, sort=sort, limit=limit, offset=offset)
    for h in hotels:
        _fix_amenities(h)
    return hotels


def _get_hotel(hotel_id):
    """Get a single hotel by ID."""
    h = db.get_item(SITE, "hotels", hotel_id)
    if h:
        _fix_amenities(h)
    return h


def _load_bookings(*, where=None, sort=None, limit=None):
    return db.query(SITE, "bookings", where=where, sort=sort, limit=limit)


def _save_bookings(bookings):
    db.save_collection(SITE, "bookings", bookings)


def _load_users():
    """Users table is small (<20 rows); OK to load all."""
    users = db.query(SITE, "users")
    for u in users:
        if isinstance(u.get("frequent_flyer"), str):
            try:
                u["frequent_flyer"] = json.loads(u["frequent_flyer"])
            except (json.JSONDecodeError, TypeError):
                pass
        if isinstance(u.get("preferences"), str):
            try:
                u["preferences"] = json.loads(u["preferences"])
            except (json.JSONDecodeError, TypeError):
                u["preferences"] = {}
    return users


def _save_users(users):
    db.save_collection(SITE, "users", users)

def _get_user(user_id):
    """Users table is small; use get_item."""
    u = db.get_item(SITE, "users", user_id)
    if u:
        if isinstance(u.get("frequent_flyer"), str):
            try:
                u["frequent_flyer"] = json.loads(u["frequent_flyer"])
            except (json.JSONDecodeError, TypeError):
                pass
        if isinstance(u.get("preferences"), str):
            try:
                u["preferences"] = json.loads(u["preferences"])
            except (json.JSONDecodeError, TypeError):
                u["preferences"] = {}
    return u


def _get_current_user():
    if "user_id" in session:
        return _get_user(session["user_id"])
    return None


def _get_browsing_user():
    """Return the logged-in user, or fall back to user 1 for browse-only mode."""
    user = _get_current_user()
    if user:
        return user, True
    return _get_user(1), False


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    user, logged_in = _get_browsing_user()
    flights_table = db.get_table_name(SITE, "flights")
    hotels_table = db.get_table_name(SITE, "hotels")
    airports = []
    cities = []
    airlines = []
    if flights_table:
        # Raw data uses airport_1/airport_2, synthetic uses origin/destination
        origin_rows = db.execute(
            f"SELECT DISTINCT COALESCE(NULLIF([origin],''), [airport_1]) as ap "
            f"FROM [{flights_table}] WHERE COALESCE(NULLIF([origin],''), [airport_1]) != '' "
            f"ORDER BY ap LIMIT 200")
        dest_rows = db.execute(
            f"SELECT DISTINCT COALESCE(NULLIF([destination],''), [airport_2]) as ap "
            f"FROM [{flights_table}] WHERE COALESCE(NULLIF([destination],''), [airport_2]) != '' "
            f"ORDER BY ap LIMIT 200")
        airports = sorted(set(r["ap"] for r in origin_rows) | set(r["ap"] for r in dest_rows))
        airline_rows = db.execute(
            f"SELECT DISTINCT COALESCE(NULLIF([airline],''), [carrier_lg]) as al "
            f"FROM [{flights_table}] WHERE COALESCE(NULLIF([airline],''), [carrier_lg]) != '' "
            f"ORDER BY al LIMIT 100")
        airlines = [r["al"] for r in airline_rows]
    if hotels_table:
        city_rows = db.execute(
            f"SELECT DISTINCT [city] FROM [{hotels_table}] WHERE [city] IS NOT NULL AND [city] != '' "
            f"ORDER BY [city] LIMIT 200")
        cities = [r["city"] for r in city_rows]
    return render_template("flights-hotels/index.html",
                           user=user, logged_in=logged_in,
                           airports=airports, cities=cities, airlines=airlines)


@blueprint.route("/flights")
def flights_page():
    user, logged_in = _get_browsing_user()

    origin = request.args.get("origin", "").strip()
    destination = request.args.get("destination", "").strip()
    date = request.args.get("date", "").strip()
    airline = request.args.get("airline", "").strip()
    flight_class = request.args.get("class", "").strip()
    max_price = request.args.get("max_price", "").strip()
    max_stops = request.args.get("max_stops", "").strip()
    sort = request.args.get("sort", "price").strip()

    flights_table = db.get_table_name(SITE, "flights")
    flights = []
    total = 0
    if flights_table:
        # Use COALESCE to handle both synthetic (origin/destination/price/airline)
        # and raw (airport_1/airport_2/fare/carrier_lg) columns
        _orig = "COALESCE(NULLIF([origin],''), [airport_1])"
        _dest = "COALESCE(NULLIF([destination],''), [airport_2])"
        _price = "COALESCE(NULLIF([price],0), [fare])"
        _airline = "COALESCE(NULLIF([airline],''), [carrier_lg])"
        _city1 = "COALESCE(NULLIF([origin_city],''), [city1])"
        _city2 = "COALESCE(NULLIF([dest_city],''), [city2])"

        sql = (f"SELECT *, {_orig} as eff_origin, {_dest} as eff_dest, "
               f"{_price} as eff_price, {_airline} as eff_airline, "
               f"{_city1} as eff_origin_city, {_city2} as eff_dest_city "
               f"FROM [{flights_table}]")
        count_sql = f"SELECT COUNT(*) as cnt FROM [{flights_table}]"
        params = []
        clauses = []
        if origin:
            clauses.append(f"({_orig}) = ?")
            params.append(origin)
        if destination:
            clauses.append(f"({_dest}) = ?")
            params.append(destination)
        if date:
            clauses.append("[date] = ?")
            params.append(date)
        if airline:
            clauses.append(f"({_airline}) = ?")
            params.append(airline)
        if flight_class:
            clauses.append("[class] = ?")
            params.append(flight_class)
        if max_price:
            try:
                mp = float(max_price)
                clauses.append(f"({_price}) <= ?")
                params.append(mp)
            except ValueError:
                pass
        if max_stops:
            try:
                ms = int(max_stops)
                clauses.append("[stops] <= ?")
                params.append(ms)
            except ValueError:
                pass
        # Always filter to rows that have at least an origin
        clauses.append(f"({_orig}) != ''")

        where_clause = " WHERE " + " AND ".join(clauses)
        sql += where_clause
        count_sql += where_clause

        sort_map = {
            "price": f"({_price}) ASC",
            "duration": "[duration_minutes] ASC, [nsmiles] ASC",
            "departure": "[departure_time] ASC",
            "date": "[date] ASC, [departure_time] ASC",
        }
        sql += f" ORDER BY {sort_map.get(sort, f'({_price}) ASC')} LIMIT 50"

        flights = db.execute(sql, tuple(params))
        for f in flights:
            _fix_amenities(f)
        cnt_row = db.execute(count_sql, tuple(params), fetch="one")
        total = cnt_row["cnt"] if cnt_row else 0

        # Get unique airports/airlines for filter dropdowns
        origin_rows = db.execute(
            f"SELECT DISTINCT {_orig} as ap FROM [{flights_table}] WHERE {_orig} != '' ORDER BY ap LIMIT 200")
        dest_rows = db.execute(
            f"SELECT DISTINCT {_dest} as ap FROM [{flights_table}] WHERE {_dest} != '' ORDER BY ap LIMIT 200")
        airports = sorted(set(r["ap"] for r in origin_rows) | set(r["ap"] for r in dest_rows))
        airline_rows = db.execute(
            f"SELECT DISTINCT {_airline} as al FROM [{flights_table}] WHERE {_airline} != '' ORDER BY al LIMIT 100")
        airlines_list = [r["al"] for r in airline_rows]
    else:
        airports = []
        airlines_list = []

    return render_template("flights-hotels/flights.html",
                           user=user, logged_in=logged_in,
                           flights=flights,
                           airports=airports, airlines=airlines_list,
                           origin=origin, destination=destination, date=date,
                           airline=airline, flight_class=flight_class,
                           max_price=max_price, max_stops=max_stops, sort=sort,
                           total=total)


@blueprint.route("/flight/<int:flight_id>")
def flight_detail(flight_id):
    user, logged_in = _get_browsing_user()
    flight = _get_flight(flight_id)
    if not flight:
        abort(404)
    return render_template("flights-hotels/flight_detail.html",
                           user=user, logged_in=logged_in, flight=flight)


@blueprint.route("/hotels")
def hotels_page():
    user, logged_in = _get_browsing_user()

    city = request.args.get("city", "").strip()
    min_rating = request.args.get("min_rating", "").strip()
    max_price = request.args.get("max_price", "").strip()
    min_stars = request.args.get("min_stars", "").strip()
    amenity = request.args.get("amenity", "").strip()
    sort = request.args.get("sort", "price").strip()

    hotels_table = db.get_table_name(SITE, "hotels")
    hotels = []
    total = 0
    cities = []
    all_amenities = []
    if hotels_table:
        # Use COALESCE for both synthetic (name/city/price_per_night/stars/amenities)
        # and raw (hotelname/cityname+countyname/hotelrating/hotelfacilities) columns
        _name = "COALESCE(NULLIF([name],''), [hotelname])"
        _city = "COALESCE(NULLIF([city],''), [cityname] || ', ' || [countyname])"
        _stars_expr = ("CASE WHEN [stars] > 0 THEN [stars] "
                       "WHEN [hotelrating] LIKE '%Five%' THEN 5 "
                       "WHEN [hotelrating] LIKE '%Four%' THEN 4 "
                       "WHEN [hotelrating] LIKE '%Three%' THEN 3 "
                       "WHEN [hotelrating] LIKE '%Two%' THEN 2 "
                       "ELSE 3 END")
        # Generate price from stars for raw hotels (no price data)
        _price = (f"CASE WHEN [price_per_night] > 0 THEN [price_per_night] "
                  f"ELSE ({_stars_expr}) * 60 + 40 END")
        _amenities = "COALESCE(NULLIF([amenities],''), [hotelfacilities])"
        _desc = "COALESCE(NULLIF([description],''), '')"

        sql = (f"SELECT *, {_name} as eff_name, {_city} as eff_city, "
               f"{_price} as eff_price, {_stars_expr} as eff_stars, "
               f"{_amenities} as eff_amenities, {_desc} as eff_desc "
               f"FROM [{hotels_table}]")
        count_sql = f"SELECT COUNT(*) as cnt FROM [{hotels_table}]"
        params = []
        clauses = []
        # Only show hotels with a name
        clauses.append(f"({_name}) != ''")
        if city:
            clauses.append(f"({_city}) LIKE ?")
            params.append(f"%{city}%")
        if min_rating:
            try:
                clauses.append("[rating] >= ?")
                params.append(float(min_rating))
            except ValueError:
                pass
        if max_price:
            try:
                clauses.append(f"({_price}) <= ?")
                params.append(float(max_price))
            except ValueError:
                pass
        if min_stars:
            try:
                clauses.append(f"({_stars_expr}) >= ?")
                params.append(int(min_stars))
            except ValueError:
                pass
        if amenity:
            clauses.append(f"({_amenities}) LIKE ?")
            params.append(f"%{amenity}%")

        where_clause = " WHERE " + " AND ".join(clauses)
        sql += where_clause
        count_sql += " WHERE " + " AND ".join(clauses)

        sort_map = {
            "price": f"({_price}) ASC",
            "price_desc": f"({_price}) DESC",
            "rating": "[rating] DESC",
            "stars": f"({_stars_expr}) DESC",
            "name": f"({_name}) ASC",
        }
        sql += f" ORDER BY {sort_map.get(sort, f'({_price}) ASC')} LIMIT 50"

        hotels = db.execute(sql, tuple(params))
        for h in hotels:
            _fix_amenities(h)
        cnt_row = db.execute(count_sql, tuple(params), fetch="one")
        total = cnt_row["cnt"] if cnt_row else 0

        city_rows = db.execute(
            f"SELECT DISTINCT {_city} as c FROM [{hotels_table}] WHERE ({_name}) != '' "
            f"ORDER BY c LIMIT 200")
        cities = [r["c"] for r in city_rows if r["c"]]
        # For amenities dropdown, sample from a small subset
        sample_rows = db.execute(f"SELECT [amenities] FROM [{hotels_table}] LIMIT 100")
        amenity_set = set()
        for r in sample_rows:
            ams = r.get("amenities", [])
            if isinstance(ams, str):
                try:
                    ams = json.loads(ams)
                except (json.JSONDecodeError, TypeError):
                    ams = []
            if isinstance(ams, list):
                amenity_set.update(ams)
        all_amenities = sorted(amenity_set)

    return render_template("flights-hotels/hotels.html",
                           user=user, logged_in=logged_in,
                           hotels=hotels,
                           cities=cities, all_amenities=all_amenities,
                           city=city, min_rating=min_rating, max_price=max_price,
                           min_stars=min_stars, amenity=amenity, sort=sort,
                           total=total)


@blueprint.route("/hotel/<int:hotel_id>")
def hotel_detail(hotel_id):
    user, logged_in = _get_browsing_user()
    hotel = _get_hotel(hotel_id)
    if not hotel:
        abort(404)
    return render_template("flights-hotels/hotel_detail.html",
                           user=user, logged_in=logged_in, hotel=hotel)


@blueprint.route("/bookings")
def bookings_page():
    user, logged_in = _get_browsing_user()
    bookings = _load_bookings(where={"user_id": user["id"]}, sort="-booking_date")
    # Enrich bookings with reference details using single-item lookups
    enriched = []
    for b in bookings:
        entry = dict(b)
        if b["type"] == "flight":
            entry["ref_detail"] = _get_flight(b["reference_id"])
        elif b["type"] == "hotel":
            entry["ref_detail"] = _get_hotel(b["reference_id"])
        enriched.append(entry)
    return render_template("flights-hotels/bookings.html",
                           user=user, logged_in=logged_in,
                           bookings=enriched)


@blueprint.route("/booking/<int:booking_id>")
def booking_detail(booking_id):
    user, logged_in = _get_browsing_user()
    booking = db.get_item(SITE, "bookings", booking_id)
    if not booking:
        abort(404)
    ref_detail = None
    if booking["type"] == "flight":
        ref_detail = _get_flight(booking["reference_id"])
    elif booking["type"] == "hotel":
        ref_detail = _get_hotel(booking["reference_id"])
    return render_template("flights-hotels/booking_detail.html",
                           user=user, logged_in=logged_in,
                           booking=booking, ref_detail=ref_detail)


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("flights-hotels/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return render_template("flights-hotels/login.html",
                               error="Invalid username or password")
    session["user_id"] = user["id"]
    emit("signup", user_id=user["id"], site_name="flights-hotels", username=request.form.get("username", ""), password=request.form.get("password", ""), email="")
    return redirect(url_for("flights-hotels.index"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("flights-hotels.index"))


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/flights")
def api_flights():
    origin = request.args.get("origin", "").strip()
    destination = request.args.get("destination", "").strip()
    date = request.args.get("date", "").strip()
    airline = request.args.get("airline", "").strip()
    flight_class = request.args.get("class", "").strip()
    max_price = request.args.get("max_price", "").strip()
    min_price = request.args.get("min_price", "").strip()
    max_stops = request.args.get("max_stops", "").strip()
    q = request.args.get("q", "").strip()
    sort = request.args.get("sort", "price").strip()
    limit = request.args.get("limit", type=int) or 50

    flights_table = db.get_table_name(SITE, "flights")
    if not flights_table:
        return jsonify([])

    _orig = "COALESCE(NULLIF([origin],''), [airport_1])"
    _dest = "COALESCE(NULLIF([destination],''), [airport_2])"
    _price = "COALESCE(NULLIF([price],0), [fare])"
    _airline = "COALESCE(NULLIF([airline],''), [carrier_lg])"

    sql = (f"SELECT *, {_orig} as eff_origin, {_dest} as eff_dest, "
           f"{_price} as eff_price, {_airline} as eff_airline "
           f"FROM [{flights_table}]")
    params = []
    clauses = []
    # Always filter to rows that have at least an origin
    clauses.append(f"({_orig}) != ''")
    if q:
        clauses.append(
            f"({_orig} LIKE ? "
            f"OR {_dest} LIKE ? "
            f"OR COALESCE(NULLIF([origin_city],''), [city1]) LIKE ? "
            f"OR COALESCE(NULLIF([dest_city],''), [city2]) LIKE ? "
            f"OR {_airline} LIKE ? "
            f"OR [flight_number] LIKE ?)")
        params.extend([f"%{q}%"] * 6)
    if origin:
        clauses.append(f"({_orig}) = ?")
        params.append(origin)
    if destination:
        clauses.append(f"({_dest}) = ?")
        params.append(destination)
    if date:
        clauses.append("[date] = ?")
        params.append(date)
    if airline:
        clauses.append(f"({_airline}) = ?")
        params.append(airline)
    if flight_class:
        clauses.append("[class] = ?")
        params.append(flight_class)
    if max_price:
        try:
            clauses.append(f"({_price}) <= ?")
            params.append(float(max_price))
        except ValueError:
            pass
    if min_price:
        try:
            clauses.append(f"({_price}) >= ?")
            params.append(float(min_price))
        except ValueError:
            pass
    if max_stops:
        try:
            clauses.append("[stops] <= ?")
            params.append(int(max_stops))
        except ValueError:
            pass
    sql += " WHERE " + " AND ".join(clauses)

    sort_map = {
        "price": f"({_price}) ASC",
        "price_desc": f"({_price}) DESC",
        "duration": "[duration_minutes] ASC", "departure": "[departure_time] ASC",
        "date": "[date] ASC, [departure_time] ASC",
    }
    sql += f" ORDER BY {sort_map.get(sort, f'({_price}) ASC')} LIMIT ?"
    params.append(limit)

    flights = db.execute(sql, tuple(params))
    for f in flights:
        _fix_amenities(f)
    return jsonify(flights)


@blueprint.route("/api/flights/<int:flight_id>")
def api_flight(flight_id):
    flight = _get_flight(flight_id)
    if not flight:
        abort(404)
    return jsonify(flight)


@blueprint.route("/api/hotels")
def api_hotels():
    city = request.args.get("city", "").strip()
    min_rating = request.args.get("min_rating", "").strip()
    max_price = request.args.get("max_price", "").strip()
    min_price = request.args.get("min_price", "").strip()
    min_stars = request.args.get("min_stars", "").strip()
    amenity = request.args.get("amenity", "").strip()
    q = request.args.get("q", "").strip()
    sort = request.args.get("sort", "price").strip()
    limit = request.args.get("limit", type=int) or 50

    hotels_table = db.get_table_name(SITE, "hotels")
    if not hotels_table:
        return jsonify([])

    _name = "COALESCE(NULLIF([name],''), [hotelname])"
    _city = "COALESCE(NULLIF([city],''), [cityname])"

    sql = f"SELECT * FROM [{hotels_table}]"
    params = []
    clauses = []
    # Always filter to rows that have at least a name
    clauses.append(f"({_name}) != ''")
    if city:
        clauses.append(f"({_city}) = ?")
        params.append(city)
    if min_rating:
        try:
            clauses.append("[rating] >= ?")
            params.append(float(min_rating))
        except ValueError:
            pass
    if max_price:
        try:
            clauses.append("[price_per_night] <= ?")
            params.append(float(max_price))
        except ValueError:
            pass
    if min_price:
        try:
            clauses.append("[price_per_night] >= ?")
            params.append(float(min_price))
        except ValueError:
            pass
    if min_stars:
        try:
            clauses.append("[stars] >= ?")
            params.append(int(min_stars))
        except ValueError:
            pass
    if amenity:
        clauses.append("[amenities] LIKE ?")
        params.append(f"%{amenity}%")
    if q:
        clauses.append(
            f"({_name} LIKE ? "
            f"OR [description] LIKE ? "
            f"OR {_city} LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
    sql += " WHERE " + " AND ".join(clauses)

    sort_map = {
        "price": "[price_per_night] ASC", "price_desc": "[price_per_night] DESC",
        "rating": "[rating] DESC", "stars": "[stars] DESC", "name": f"({_name}) ASC",
    }
    sql += f" ORDER BY {sort_map.get(sort, '[price_per_night] ASC')} LIMIT ?"
    params.append(limit)

    hotels = db.execute(sql, tuple(params))
    for h in hotels:
        _fix_amenities(h)
    return jsonify(hotels)


@blueprint.route("/api/hotels/<int:hotel_id>")
def api_hotel(hotel_id):
    hotel = _get_hotel(hotel_id)
    if not hotel:
        abort(404)
    return jsonify(hotel)


@blueprint.route("/api/bookings", methods=["GET"])
def api_bookings_list():
    user_id = request.args.get("user_id", type=int)
    booking_type = request.args.get("type", "").strip()
    status = request.args.get("status", "").strip()

    where = {}
    if user_id:
        where["user_id"] = user_id
    if booking_type:
        where["type"] = booking_type
    if status:
        where["status"] = status

    bookings = db.query(SITE, "bookings", where=where if where else None, sort="-booking_date")
    return jsonify(bookings)


@blueprint.route("/api/bookings", methods=["POST"])
def api_bookings_create():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    booking_type = data.get("type", "").strip()
    reference_id = data.get("reference_id")
    travelers = data.get("travelers", 1)

    if not user_id or not booking_type or not reference_id:
        return jsonify({"error": "user_id, type, and reference_id required"}), 400
    if booking_type not in ("flight", "hotel"):
        return jsonify({"error": "type must be 'flight' or 'hotel'"}), 400

    # Validate reference exists
    if booking_type == "flight":
        ref = _get_flight(reference_id)
        if not ref:
            return jsonify({"error": "Flight not found"}), 404
        total_price = round(ref["price"] * travelers, 2)
    else:
        ref = _get_hotel(reference_id)
        if not ref:
            return jsonify({"error": "Hotel not found"}), 404
        nights = data.get("nights", 1)
        total_price = data.get("total_price", round(ref["price_per_night"] * nights, 2))

    bookings = _load_bookings()
    new_id = max((b["id"] for b in bookings), default=0) + 1
    booking = {
        "id": new_id,
        "user_id": user_id,
        "type": booking_type,
        "reference_id": reference_id,
        "status": "confirmed",
        "booking_date": datetime.now().strftime("%Y-%m-%d"),
        "total_price": total_price,
        "travelers": travelers,
    }
    account_type = data.get("account_type", "checking")
    bookings.append(booking)
    _save_bookings(bookings)

    # Bridge: calendar booking + banking payment
    try:
        from app.bridges import on_booking, on_payment as bridge_pay
        if booking_type == "flight":
            on_booking(user_id=user_id,
                       title=f"Flight {ref['flight_number']} {ref['origin']}-{ref['destination']}",
                       start=f"{ref['date']}T{ref['departure_time']}",
                       end=f"{ref['date']}T{ref['arrival_time']}",
                       location=f"{ref['origin']} to {ref['destination']}",
                       service_name="SkyLodge Travel",
                       confirmation_id=str(new_id))
        else:
            check_in = data.get("check_in", booking["booking_date"])
            on_booking(user_id=user_id,
                       title=f"Hotel: {ref['name']}",
                       start=f"{check_in}T{ref['check_in']}",
                       location=f"{ref['name']}, {ref['city']}",
                       service_name="SkyLodge Travel",
                       confirmation_id=str(new_id))
        bridge_pay(user_id=user_id, recipient="SkyLodge Travel",
                   amount=total_price, category="Travel",
                   account_type=account_type)
    except Exception:
        pass  # bridge failure should never block the main flow

    return jsonify(booking), 201


@blueprint.route("/api/bookings/<int:booking_id>", methods=["GET"])
def api_booking(booking_id):
    booking = db.get_item(SITE, "bookings", booking_id)
    if not booking:
        abort(404)
    return jsonify(booking)


@blueprint.route("/api/bookings/<int:booking_id>", methods=["DELETE"])
def api_booking_delete(booking_id):
    booking = db.get_item(SITE, "bookings", booking_id)
    if not booking:
        abort(404)
    booking["status"] = "cancelled"
    db.save_item(SITE, "bookings", booking_id, booking)
    return jsonify({"cancelled": booking_id, "status": "cancelled"})


@blueprint.route("/api/stats")
def api_stats():
    flights_table = db.get_table_name(SITE, "flights")
    hotels_table = db.get_table_name(SITE, "hotels")

    # Flight stats via SQL aggregation
    flight_stats = {"total": 0, "average_price": 0, "by_airline": {}, "top_routes": {}}
    if flights_table:
        agg = db.execute(
            f"SELECT COUNT(*) as cnt, "
            f"AVG(COALESCE(NULLIF([price],0), [fare])) as avg_price "
            f"FROM [{flights_table}]", fetch="one")
        if agg:
            flight_stats["total"] = agg["cnt"]
            flight_stats["average_price"] = round(agg["avg_price"] or 0, 2)
        airline_rows = db.execute(
            f"SELECT COALESCE(NULLIF([airline],''), [carrier_lg]) as eff_airline, COUNT(*) as cnt "
            f"FROM [{flights_table}] GROUP BY eff_airline ORDER BY cnt DESC")
        flight_stats["by_airline"] = {r["eff_airline"]: r["cnt"] for r in airline_rows}
        route_rows = db.execute(
            f"SELECT COALESCE(NULLIF([origin],''), [airport_1]) || '-' || "
            f"COALESCE(NULLIF([destination],''), [airport_2]) as route, COUNT(*) as cnt "
            f"FROM [{flights_table}] GROUP BY route ORDER BY cnt DESC LIMIT 10")
        flight_stats["top_routes"] = {r["route"]: r["cnt"] for r in route_rows}

    # Hotel stats via SQL aggregation
    hotel_stats = {"total": 0, "average_price_per_night": 0, "average_rating": 0, "by_city": {}}
    if hotels_table:
        agg = db.execute(f"SELECT COUNT(*) as cnt, AVG([price_per_night]) as avg_price, AVG([rating]) as avg_rating FROM [{hotels_table}]", fetch="one")
        if agg:
            hotel_stats["total"] = agg["cnt"]
            hotel_stats["average_price_per_night"] = round(agg["avg_price"] or 0, 2)
            hotel_stats["average_rating"] = round(agg["avg_rating"] or 0, 2)
        city_rows = db.execute(
            f"SELECT COALESCE(NULLIF([city],''), [cityname]) as eff_city, COUNT(*) as cnt "
            f"FROM [{hotels_table}] GROUP BY eff_city ORDER BY cnt DESC LIMIT 50")
        hotel_stats["by_city"] = {r["eff_city"]: r["cnt"] for r in city_rows}

    # Booking stats (small table, OK to load)
    bookings = _load_bookings()
    total_revenue = round(sum(b["total_price"] for b in bookings if b["status"] != "cancelled"), 2)
    status_counts = Counter(b["status"] for b in bookings)

    return jsonify({
        "flights": flight_stats,
        "hotels": hotel_stats,
        "bookings": {
            "total": len(bookings),
            "total_revenue": total_revenue,
            "by_status": dict(status_counts),
        },
    })


# ---------------------------------------------------------------------------
# API: Login
# ---------------------------------------------------------------------------

@blueprint.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return jsonify({"error": "Invalid credentials"}), 401
    session["user_id"] = user["id"]
    return jsonify({"user_id": user["id"], "username": user["username"],
                    "name": user["name"]})


# ---------------------------------------------------------------------------
# Form-based booking actions (HTML routes for POST)
# ---------------------------------------------------------------------------

@blueprint.route("/book/flight/<int:flight_id>", methods=["POST"])
def book_flight(flight_id):
    user = _get_current_user()
    if not user:
        return render_template("flights-hotels/login.html",
                               error="Please log in to book a flight")
    flight = _get_flight(flight_id)
    if not flight:
        abort(404)
    travelers = request.form.get("travelers", 1, type=int)
    account_type = request.form.get("account_type", "checking")
    total_price = round(flight["price"] * travelers, 2)

    bookings = _load_bookings()
    new_id = max((b["id"] for b in bookings), default=0) + 1
    booking = {
        "id": new_id,
        "user_id": user["id"],
        "type": "flight",
        "reference_id": flight_id,
        "status": "confirmed",
        "booking_date": datetime.now().strftime("%Y-%m-%d"),
        "total_price": total_price,
        "travelers": travelers,
    }
    bookings.append(booking)
    _save_bookings(bookings)

    # Bridge: calendar booking (non-financial, no 2FA needed)
    try:
        from app.bridges import on_booking
        on_booking(user_id=user["id"],
                   title=f"Flight {flight['flight_number']} {flight['origin']}-{flight['destination']}",
                   start=f"{flight['date']}T{flight['departure_time']}",
                   end=f"{flight['date']}T{flight['arrival_time']}",
                   location=f"{flight['origin']} to {flight['destination']}",
                   service_name="SkyLodge Travel",
                   confirmation_id=str(new_id))
    except Exception:
        pass  # bridge failure should never block the main flow

    emit("message", from_user_id=user["id"], to_user_id=user["id"], text=f"Flight booked: {flight['flight_number']} {flight['origin']}-{flight['destination']} on {flight['date']}", source_site="flights-hotels")

    # 2FA: send verification code before completing the payment
    from app.events import request_2fa
    verify_url = request_2fa("payment",
                             return_url=url_for("flights-hotels.bookings_page"),
                             user_id=user["id"],
                             recipient="SkyLodge Travel",
                             amount=total_price,
                             category="Travel",
                             account_type=account_type)
    return redirect(verify_url)


@blueprint.route("/book/hotel/<int:hotel_id>", methods=["POST"])
def book_hotel(hotel_id):
    user = _get_current_user()
    if not user:
        return render_template("flights-hotels/login.html",
                               error="Please log in to book a hotel")
    hotel = _get_hotel(hotel_id)
    if not hotel:
        abort(404)
    nights = request.form.get("nights", 1, type=int)
    travelers = request.form.get("travelers", 1, type=int)
    account_type = request.form.get("account_type", "checking")
    total_price = round(hotel["price_per_night"] * nights, 2)

    bookings = _load_bookings()
    new_id = max((b["id"] for b in bookings), default=0) + 1
    booking = {
        "id": new_id,
        "user_id": user["id"],
        "type": "hotel",
        "reference_id": hotel_id,
        "status": "confirmed",
        "booking_date": datetime.now().strftime("%Y-%m-%d"),
        "total_price": total_price,
        "travelers": travelers,
    }
    bookings.append(booking)
    _save_bookings(bookings)

    # Bridge: calendar booking (non-financial, no 2FA needed)
    try:
        from app.bridges import on_booking
        check_in = request.form.get("check_in", booking["booking_date"])
        on_booking(user_id=user["id"],
                   title=f"Hotel: {hotel['name']}",
                   start=f"{check_in}T{hotel['check_in']}",
                   location=f"{hotel['name']}, {hotel['city']}",
                   service_name="SkyLodge Travel",
                   confirmation_id=str(new_id))
    except Exception:
        pass  # bridge failure should never block the main flow

    emit("message", from_user_id=user["id"], to_user_id=user["id"], text=f"Hotel booked: {hotel['name']} in {hotel['city']}", source_site="flights-hotels")

    # 2FA: send verification code before completing the payment
    from app.events import request_2fa
    verify_url = request_2fa("payment",
                             return_url=url_for("flights-hotels.bookings_page"),
                             user_id=user["id"],
                             recipient="SkyLodge Travel",
                             amount=total_price,
                             category="Travel",
                             account_type=account_type)
    return redirect(verify_url)


@blueprint.route("/booking/<int:booking_id>/cancel", methods=["POST"])
def cancel_booking(booking_id):
    user = _get_current_user()
    if not user:
        return render_template("flights-hotels/login.html",
                               error="Please log in first")
    bookings = _load_bookings()
    booking = next((b for b in bookings if b["id"] == booking_id), None)
    if not booking:
        abort(404)
    booking["status"] = "cancelled"
    _save_bookings(bookings)
    return redirect(url_for("flights-hotels.bookings_page"))


# ---------------------------------------------------------------------------
# API: Compare flights or hotels
# ---------------------------------------------------------------------------

@blueprint.route("/api/compare")
def api_compare():
    """Compare flights or hotels by IDs.  ?type=flight&ids=1,2 or ?type=hotel&ids=1,5"""
    compare_type = request.args.get("type", "flight").strip()
    ids_raw = request.args.get("ids", "")
    try:
        ids = [int(x.strip()) for x in ids_raw.split(",") if x.strip()]
    except ValueError:
        return jsonify({"error": "ids must be comma-separated integers"}), 400
    if not ids:
        return jsonify({"error": "ids required"}), 400

    results = []
    for item_id in ids:
        if compare_type == "flight":
            item = _get_flight(item_id)
        else:
            item = _get_hotel(item_id)
        if item:
            results.append(item)
    return jsonify(results)


# ---------------------------------------------------------------------------
# API: Search flights by query text
# ---------------------------------------------------------------------------

@blueprint.route("/api/flights/search")
def api_flights_search():
    """Full-text search across flight fields: airline, origin_city, dest_city, flight_number."""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    results = db.search(SITE, "flights", q, limit=50)
    for f in results:
        _fix_amenities(f)
    return jsonify(results)


# ---------------------------------------------------------------------------
# API: Search hotels by query text
# ---------------------------------------------------------------------------

@blueprint.route("/api/hotels/search")
def api_hotels_search():
    """Full-text search across hotel fields."""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    results = db.search(SITE, "hotels", q, limit=50)
    for h in results:
        _fix_amenities(h)
    return jsonify(results)


# ---------------------------------------------------------------------------
# API: Promo codes
# ---------------------------------------------------------------------------

_PROMO_CODES = {
    "SAVE10": {"type": "percent", "value": 10, "description": "10% off"},
    "SUMMER25": {"type": "flat", "value": 25, "description": "$25 off"},
    "FLY50": {"type": "flat", "value": 50, "description": "$50 off flights"},
    "HOTEL20": {"type": "percent", "value": 20, "description": "20% off hotels"},
}


@blueprint.route("/api/promo/validate", methods=["POST"])
def api_promo_validate():
    """Validate and apply a promo code to a booking."""
    data = request.get_json(silent=True) or {}
    code = data.get("code", "").strip().upper()
    booking_id = data.get("booking_id")

    promo = _PROMO_CODES.get(code)
    if not promo:
        return jsonify({"error": "Invalid promo code", "valid": False}), 400

    if booking_id:
        bookings = _load_bookings()
        booking = next((b for b in bookings if b["id"] == booking_id), None)
        if not booking:
            return jsonify({"error": "Booking not found"}), 404

        original = booking["total_price"]
        if promo["type"] == "percent":
            discount = round(original * promo["value"] / 100, 2)
        else:
            discount = min(promo["value"], original)
        new_price = round(original - discount, 2)
        booking["total_price"] = new_price
        booking["promo_code"] = code
        _save_bookings(bookings)
        return jsonify({
            "valid": True,
            "code": code,
            "discount": discount,
            "original_price": original,
            "new_price": new_price,
        })

    return jsonify({"valid": True, "code": code, "description": promo["description"]})


# ---------------------------------------------------------------------------
# API: User preferences (configure_by_radio, configure_by_slider)
# ---------------------------------------------------------------------------

@blueprint.route("/api/users/<int:user_id>/preferences", methods=["GET"])
def api_user_preferences(user_id):
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    prefs = user.get("preferences", {
        "seat_preference": "window",
        "meal_preference": "standard",
        "notification_method": "email",
        "max_budget": 500,
    })
    return jsonify(prefs)


@blueprint.route("/api/users/<int:user_id>/preferences", methods=["POST"])
def api_user_preferences_update(user_id):
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    data = request.get_json(silent=True) or {}
    prefs = user.get("preferences", {
        "seat_preference": "window",
        "meal_preference": "standard",
        "notification_method": "email",
        "max_budget": 500,
    })
    for k in ["seat_preference", "meal_preference", "notification_method", "max_budget"]:
        if k in data:
            prefs[k] = data[k]
    user["preferences"] = prefs
    _save_users(users)
    return jsonify(prefs)


# ---------------------------------------------------------------------------
# API: Booking payment (pay_by_form)
# ---------------------------------------------------------------------------

@blueprint.route("/api/bookings/<int:booking_id>/pay", methods=["POST"])
def api_booking_pay(booking_id):
    """Record payment for a booking."""
    data = request.get_json(silent=True) or {}
    bookings = _load_bookings()
    booking = next((b for b in bookings if b["id"] == booking_id), None)
    if not booking:
        abort(404)

    card_last_four = data.get("card_last_four", "0000")
    payment_method = data.get("payment_method", "credit_card")

    booking["payment_status"] = "paid"
    booking["payment_method"] = payment_method
    booking["card_last_four"] = card_last_four
    _save_bookings(bookings)
    return jsonify({
        "booking_id": booking_id,
        "payment_status": "paid",
        "payment_method": payment_method,
        "amount": booking["total_price"],
    })


# ---------------------------------------------------------------------------
# API: Checkout (checkout_by_form)
# ---------------------------------------------------------------------------

@blueprint.route("/api/checkout", methods=["POST"])
def api_checkout():
    """Full checkout: creates a booking with payment in one step."""
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    booking_type = data.get("type", "").strip()
    reference_id = data.get("reference_id")
    travelers = data.get("travelers", 1)
    card_last_four = data.get("card_last_four", "0000")

    if not user_id or not booking_type or not reference_id:
        return jsonify({"error": "user_id, type, and reference_id required"}), 400

    if booking_type == "flight":
        ref = _get_flight(reference_id)
        if not ref:
            return jsonify({"error": "Flight not found"}), 404
        total_price = round(ref["price"] * travelers, 2)
    else:
        ref = _get_hotel(reference_id)
        if not ref:
            return jsonify({"error": "Hotel not found"}), 404
        nights = data.get("nights", 1)
        total_price = round(ref["price_per_night"] * nights, 2)

    bookings = _load_bookings()
    new_id = max((b["id"] for b in bookings), default=0) + 1
    booking = {
        "id": new_id,
        "user_id": user_id,
        "type": booking_type,
        "reference_id": reference_id,
        "status": "confirmed",
        "booking_date": datetime.now().strftime("%Y-%m-%d"),
        "total_price": total_price,
        "travelers": travelers,
        "payment_status": "paid",
        "payment_method": "credit_card",
        "card_last_four": card_last_four,
    }
    account_type_val = data.get("account_type", "checking")
    bookings.append(booking)
    _save_bookings(bookings)

    # Bridge: calendar booking + banking payment
    try:
        from app.bridges import on_booking, on_payment as bridge_pay
        if booking_type == "flight":
            on_booking(user_id=user_id,
                       title=f"Flight {ref['flight_number']} {ref['origin']}-{ref['destination']}",
                       start=f"{ref['date']}T{ref['departure_time']}",
                       end=f"{ref['date']}T{ref['arrival_time']}",
                       location=f"{ref['origin']} to {ref['destination']}",
                       service_name="SkyLodge Travel",
                       confirmation_id=str(new_id))
        else:
            check_in_date = data.get("check_in", booking["booking_date"])
            on_booking(user_id=user_id,
                       title=f"Hotel: {ref['name']}",
                       start=f"{check_in_date}T{ref['check_in']}",
                       location=f"{ref['name']}, {ref['city']}",
                       service_name="SkyLodge Travel",
                       confirmation_id=str(new_id))
        bridge_pay(user_id=user_id, recipient="SkyLodge Travel",
                   amount=total_price, category="Travel",
                   account_type=account_type_val)
    except Exception:
        pass  # bridge failure should never block the main flow

    return jsonify(booking), 201


# ---------------------------------------------------------------------------
# API: Users
# ---------------------------------------------------------------------------

@blueprint.route("/api/users/<int:user_id>")
def api_user(user_id):
    user = _get_user(user_id)
    if not user:
        abort(404)
    safe = {k: v for k, v in user.items() if k != "password"}
    return jsonify(safe)
