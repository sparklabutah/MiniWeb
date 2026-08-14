"""SkyLodge Travel -- flights & hotels booking site (Expedia / Kayak style).

Data is stored in per-site SQLite tables (flights_hotels_flights,
flights_hotels_hotels, etc.) and queried through app.db.  Session
mutations are isolated per user.
"""
import json
import pathlib
import re
import html as _html
from collections import Counter
from datetime import datetime, date as _date

from flask import (
    Blueprint, abort, jsonify, redirect, render_template, request,
    session, url_for,
)
from app import db
from app.events import emit
from helpers.auth import browsing_user, current_user

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


_CARRIERS = {
    "AA": "American Airlines", "WN": "Southwest Airlines", "DL": "Delta Air Lines",
    "UA": "United Airlines", "B6": "JetBlue", "AS": "Alaska Airlines",
    "NK": "Spirit Airlines", "F9": "Frontier Airlines", "G4": "Allegiant Air",
    "HA": "Hawaiian Airlines", "SY": "Sun Country Airlines", "US": "US Airways",
    "CO": "Continental Airlines", "NW": "Northwest Airlines", "VX": "Virgin America",
}


def _normalize_flight(f):
    """Fill in route/airline/flight number/price for the 50k raw imported flights
    (empty origin/destination/airline/flight_number, price=0 with the real price
    in `fare`), so the detail/seat/review/booking pages show a real itinerary and
    fare instead of ()->() and $0."""
    if not f:
        return f
    if not (f.get("origin") or "").strip():
        f["origin"] = (f.get("airport_1") or "").strip()
    if not (f.get("destination") or "").strip():
        f["destination"] = (f.get("airport_2") or "").strip()
    if not (f.get("origin_city") or "").strip():
        f["origin_city"] = (f.get("city1") or "").strip()
    if not (f.get("dest_city") or "").strip():
        f["dest_city"] = (f.get("city2") or "").strip()
    if not (f.get("airline") or "").strip():
        code = (f.get("carrier_lg") or f.get("carrier_low") or "").strip()
        f["airline"] = _CARRIERS.get(code, (code + " Airlines").strip() or "SkyLodge Air")
    if not (f.get("flight_number") or "").strip():
        code = (f.get("carrier_lg") or "SL").strip() or "SL"
        f["flight_number"] = f"{code}{str(f.get('id', '')).zfill(4)[-4:]}"
    try:
        price = float(f.get("price") or 0)
    except (TypeError, ValueError):
        price = 0
    if price <= 0:
        try:
            price = float(f.get("fare") or f.get("fare_low") or 0)
        except (TypeError, ValueError):
            price = 0
    f["price"] = round(price, 2) if price > 0 else 99.0
    if not (f.get("aircraft") or "").strip():
        f["aircraft"] = "Boeing 737-800"
    if not (f.get("class") or "").strip():
        f["class"] = "Economy"
    return f


def _get_flight(flight_id):
    """Get a single flight by ID (normalized so raw imports have route/airline/price)."""
    f = db.get_item(SITE, "flights", flight_id)
    if f:
        _fix_amenities(f)
        _normalize_flight(f)
    return f


def _query_hotels(*, where=None, sort=None, limit=None, offset=0):
    """Query hotels with SQL-level filtering, fix amenities."""
    hotels = db.query(SITE, "hotels", where=where, sort=sort, limit=limit, offset=offset)
    for h in hotels:
        _fix_amenities(h)
    return hotels


def _hotel_stars(h):
    """Star rating for a hotel, from the synthetic `stars` col or the raw
    `hotelrating` text ('...Four Star...'). Defaults to 3."""
    try:
        if float(h.get("stars") or 0) > 0:
            return int(float(h["stars"]))
    except (TypeError, ValueError):
        pass
    rating = h.get("hotelrating") or ""
    for word, n in (("Five", 5), ("Four", 4), ("Three", 3), ("Two", 2), ("One", 1)):
        if word in rating:
            return n
    return 3


def _clean_description(text):
    """Raw hotel descriptions are HTML with encoding artefacts. Strip tags,
    unescape entities, drop mojibake replacement chars, and tidy whitespace so
    the detail page shows clean prose instead of literal <p> markup."""
    if not text:
        return ""
    t = re.sub(r"(?i)<\s*br\s*/?>", "\n", str(text))
    t = re.sub(r"(?i)</p\s*>", "\n", t)
    t = re.sub(r"<[^>]+>", "", t)
    t = _html.unescape(t).replace("�", "")
    t = re.sub(r"[ \t]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n", t).strip()


def _normalize_hotel(h):
    """Fill in name/city/stars/price/rating/description for the 50k raw imported
    hotels (which have empty name and price_per_night=0), matching how the
    listing page derives them so the DETAIL/booking pages aren't blank/$0."""
    if not h:
        return h
    if not (h.get("name") or "").strip():
        h["name"] = (h.get("hotelname") or "").strip() or "Hotel"
    if not (h.get("city") or "").strip():
        parts = [(h.get("cityname") or "").strip(), (h.get("countyname") or "").strip()]
        h["city"] = ", ".join(p for p in parts if p) or h.get("city", "")
    stars = _hotel_stars(h)
    h["stars"] = stars
    try:
        price = float(h.get("price_per_night") or 0)
    except (TypeError, ValueError):
        price = 0
    h["price_per_night"] = price if price > 0 else stars * 60 + 40   # same rule as the listing
    try:
        if not float(h.get("rating") or 0) > 0:
            h["rating"] = round(3.5 + (stars - 3) * 0.3, 1)
    except (TypeError, ValueError):
        h["rating"] = round(3.5 + (stars - 3) * 0.3, 1)
    h["description"] = _clean_description(h.get("description"))
    return h


def _get_hotel(hotel_id):
    """Get a single hotel by ID (normalized so raw imports have name/price/desc)."""
    h = db.get_item(SITE, "hotels", hotel_id)
    if h:
        _fix_amenities(h)
        _normalize_hotel(h)
    return h


def _load_bookings(*, where=None, sort=None, limit=None):
    return db.query(SITE, "bookings", where=where, sort=sort, limit=limit)


def _save_bookings(bookings):
    db.save_collection(SITE, "bookings", bookings)


def _collect_passenger_names(form, count, lead_field="passenger_name",
                             prefix="passenger_name_"):
    """Collect per-traveler names from the booking form.

    Reads indexed inputs (passenger_name_1, passenger_name_2, ...) plus an
    optional single lead field, returns a de-duplicated ordered list of the
    non-empty names (capped at `count`). Always returns at least the lead
    name if one was supplied.
    """
    names = []
    lead = (form.get(lead_field) or "").strip()
    if lead:
        names.append(lead)
    for i in range(1, max(count, 1) + 1):
        v = (form.get(f"{prefix}{i}") or "").strip()
        if v and v not in names:
            names.append(v)
    return names[:max(count, 1)]


def _nights_between(check_in, check_out):
    """Number of nights between two YYYY-MM-DD dates, or None if not parseable."""
    try:
        ci = datetime.strptime(check_in, "%Y-%m-%d").date()
        co = datetime.strptime(check_out, "%Y-%m-%d").date()
        n = (co - ci).days
        return n if n > 0 else None
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Seat selection (flights) + cabin class + room types (hotels)
# ---------------------------------------------------------------------------

# Boeing 737-800 cabin: single aisle, 3-3 layout. Columns A/B/C | aisle | D/E/F
# across 30 rows -> seats 1A .. 30F. Seats are chosen on their OWN screen after
# the flight-detail form is submitted (staged wizard).
_SEAT_ROWS = list(range(1, 31))
_SEAT_COLS = ["A", "B", "C", "D", "E", "F"]

# Paid-seat zones — a fee is added on top of the fare, once per assigned seat:
#   rows 1-4   -> "Premium"       +$40
#   rows 16-17 -> "Extra legroom" +$25  (exit rows)
#   all others -> "Standard"      free
_SEAT_PREMIUM_ROWS = set(range(1, 5))
_SEAT_LEGROOM_ROWS = {16, 17}
_SEAT_PREMIUM_FEE = 40.0
_SEAT_LEGROOM_FEE = 25.0

# Cabin classes with a price multiplier applied to the flight's base fare.
_CABIN_CLASSES = {
    "economy":  {"label": "Economy",  "mult": 1.0},
    "premium":  {"label": "Premium",  "mult": 1.35},
    "business": {"label": "Business", "mult": 1.9},
}

# Hotel room types with a per-night multiplier applied to the base rate.
_ROOM_TYPES = {
    "standard": {"label": "Standard", "mult": 1.0},
    "deluxe":   {"label": "Deluxe",   "mult": 1.5},
    "suite":    {"label": "Suite",    "mult": 2.0},
}


def _no_store(html):
    """Wrap rendered HTML in a response that browsers must not cache.

    The seat page is a stateful wizard step; without this the browser bfcache
    can restore a stale, frozen copy on "Back" (checkboxes stuck at the max
    count) instead of the live re-entrant map, stranding the user.
    """
    from flask import make_response
    resp = make_response(html)
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


def _all_seats():
    """Every seat label on the 737-800 map, e.g. '1A' .. '30F'."""
    return [f"{r}{c}" for r in _SEAT_ROWS for c in _SEAT_COLS]


def _seat_row_num(seat):
    """Numeric row of a seat label ('2A' -> 2), or 0 if unparseable."""
    m = re.match(r"(\d+)", seat or "")
    return int(m.group(1)) if m else 0


def _seat_zone(seat):
    """(key, label, fee) for a seat: premium / legroom / standard."""
    r = _seat_row_num(seat)
    if r in _SEAT_PREMIUM_ROWS:
        return ("premium", "Premium", _SEAT_PREMIUM_FEE)
    if r in _SEAT_LEGROOM_ROWS:
        return ("legroom", "Extra legroom", _SEAT_LEGROOM_FEE)
    return ("standard", "Standard", 0.0)


def _seat_fee(seat):
    """Paid-seat surcharge for a single seat ($0 for standard)."""
    return _seat_zone(seat)[2]


def _boarding_extras(flight, seats=None):
    """Deterministic boarding-pass filler for the ticket visual.

    Gate / terminal / zone / boarding time are derived from the flight id and
    departure time so they stay stable across page loads. These are cosmetic
    ticket fields (not real operational data), used to make the review /
    confirmation pages read like a real boarding pass.
    """
    fid = int(flight.get("id") or 0)
    terminal = chr(ord("A") + fid % 4)               # A-D
    gate = "%s%d" % (terminal, 1 + fid % 30)          # e.g. B12
    boarding = ""
    dep = (flight.get("departure_time") or "").strip()
    m = re.match(r"^(\d{1,2}):(\d{2})", dep)
    if m:
        total = (int(m.group(1)) * 60 + int(m.group(2)) - 35) % (24 * 60)
        boarding = "%02d:%02d" % (total // 60, total % 60)
    row = _seat_row_num((seats or [""])[0]) if seats else 0
    zone = 1 if 1 <= row <= 6 else (2 if 7 <= row <= 15 else (3 if row else 4))
    return {"terminal": terminal, "gate": gate,
            "boarding_time": boarding, "zone": zone}


def _seat_map(flight_id, selected=None):
    """Structured seat map for rendering: rows -> list of cell dicts.

    Each cell carries the seat label, its zone key/label/fee, and whether it is
    taken (deterministically unavailable for this flight) or currently selected.
    """
    selected = set(s.upper() for s in (selected or []))
    # The user's own pending seats must never render as taken/blocked on
    # re-entry — they belong to THIS booking and must stay re-selectable.
    taken = _taken_seats(flight_id) - selected
    rows = []
    for r in _SEAT_ROWS:
        cells = []
        for c in _SEAT_COLS:
            label = f"{r}{c}"
            zk, zl, fee = _seat_zone(label)
            cells.append({
                "label": label, "col": c, "zone": zk, "zone_label": zl,
                "fee": fee, "taken": label in taken,
                "selected": label in selected,
            })
        rows.append({"row": r, "cells": cells})
    return rows


def _taken_seats(flight_id):
    """Deterministically mark a subset of seats as already booked for a flight.

    Same flight id always yields the same taken set, so a seat that is
    unavailable stays unavailable across page loads and can be reasoned about.
    """
    taken = set()
    for idx, seat in enumerate(_all_seats()):
        if (int(flight_id) * 7 + idx * 3) % 5 == 0:
            taken.add(seat)
    return taken


def _clean_seat_selection(seat_values, flight_id):
    """Validate a list of chosen seat labels against the taken map.

    Returns (seats, bad) where `seats` is the ordered, de-duplicated list of
    valid free seats and `bad` lists any requested seats that are unknown or
    already taken. Case-insensitive; whitespace tolerant.
    """
    valid = set(_all_seats())
    taken = _taken_seats(flight_id)
    raw = [s.strip().upper() for s in seat_values if s and s.strip()]
    seats, seen, bad = [], set(), []
    for s in raw:
        if s not in valid or s in taken:
            bad.append(s)
        elif s not in seen:
            seen.add(s)
            seats.append(s)
    return seats, bad


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
    return current_user(_get_user)


def _get_browsing_user():
    return browsing_user(_get_user, fallback=1)


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
        # Same synthetic->raw fallback as hotels_page(): the synthetic [city]
        # column is empty for nearly all raw rows, so fall back to cityname+county.
        # NULLIF on cityname drops junk like ", Thailand" from blank city names.
        _city = "COALESCE(NULLIF([city],''), NULLIF([cityname],'') || ', ' || [countyname])"
        city_rows = db.execute(
            f"SELECT DISTINCT {_city} as city FROM [{hotels_table}] "
            f"WHERE ({_city}) IS NOT NULL AND ({_city}) != '' "
            f"ORDER BY city LIMIT 200")
        cities = [r["city"] for r in city_rows if r["city"]]
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
    # STEP 1 of the flight wizard: collect cabin class, travelers, passenger
    # names and dates only. Seats are chosen on the next screen; nothing is
    # persisted here.
    return render_template("flights-hotels/flight_detail.html",
                           user=user, logged_in=logged_in, flight=flight,
                           cabin_classes=_CABIN_CLASSES, form_error=None)


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
    # Derive per-night rates for each room type from the hotel's base price.
    room_options = [
        {"key": k, "label": v["label"],
         "rate": round((hotel.get("price_per_night") or 0) * v["mult"], 2)}
        for k, v in _ROOM_TYPES.items()
    ]
    return render_template("flights-hotels/hotel_detail.html",
                           user=user, logged_in=logged_in, hotel=hotel,
                           room_options=room_options, form_error=None)


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
    # Deserialize the per-traveler names captured on the booking.
    pax = booking.get("passengers")
    if isinstance(pax, str) and pax:
        try:
            booking["passengers"] = json.loads(pax)
        except (json.JSONDecodeError, TypeError):
            booking["passengers"] = [pax]
    elif not pax:
        booking["passengers"] = []
    # Deserialize the per-traveler seat list captured on flight bookings.
    seats = booking.get("seats")
    if isinstance(seats, str) and seats:
        try:
            booking["seats"] = json.loads(seats)
        except (json.JSONDecodeError, TypeError):
            booking["seats"] = [seats]
    elif not seats:
        booking["seats"] = []
    # Deserialize the per-seat fee list captured on flight bookings.
    seat_fees = booking.get("seat_fees")
    if isinstance(seat_fees, str) and seat_fees:
        try:
            booking["seat_fees"] = json.loads(seat_fees)
        except (json.JSONDecodeError, TypeError):
            booking["seat_fees"] = []
    elif not seat_fees:
        booking["seat_fees"] = []
    # Pair passengers with their assigned seats + fees for display.
    booking["seat_assignments"] = [
        {"passenger": p, "seat": s,
         "fee": (booking["seat_fees"][i] if i < len(booking["seat_fees"]) else 0)}
        for i, (p, s) in enumerate(zip(booking.get("passengers", []),
                                       booking.get("seats", [])))
    ]
    ref_detail = None
    bp = None
    if booking["type"] == "flight":
        ref_detail = _get_flight(booking["reference_id"])
        if ref_detail:
            bp = _boarding_extras(ref_detail, booking.get("seats"))
    elif booking["type"] == "hotel":
        ref_detail = _get_hotel(booking["reference_id"])
    return render_template("flights-hotels/booking_detail.html",
                           user=user, logged_in=logged_in,
                           booking=booking, ref_detail=ref_detail, bp=bp)


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
    if booking.get("status") == "cancelled":
        refund = booking.get("refund_amount", 0.0)
    else:
        refund = round(booking.get("total_price", 0.0), 2)
    booking["status"] = "cancelled"
    booking["refund_amount"] = refund
    db.save_item(SITE, "bookings", booking_id, booking)
    return jsonify({"cancelled": booking_id, "status": "cancelled",
                    "refund_amount": refund})


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

def _room_options(hotel):
    """Per-night rate for each room type, derived from the hotel's base price."""
    base = float(hotel.get("price_per_night") or 0)
    return [
        {"key": k, "label": v["label"], "mult": v["mult"],
         "rate": round(base * v["mult"], 2)}
        for k, v in _ROOM_TYPES.items()
    ]


def _flight_fare(flight, pending):
    """Full fare breakdown for a pending flight booking.

    total = base * cabin_mult * travelers * legs + seat fees.
    """
    base = round(float(flight.get("price") or 0), 2)
    cabin = _CABIN_CLASSES.get(pending.get("cabin_class"), _CABIN_CLASSES["economy"])
    mult = cabin["mult"]
    travelers = int(pending.get("travelers") or 1)
    legs = 2 if (pending.get("trip_type") == "round_trip"
                 and pending.get("return_date")) else 1
    fare_subtotal = round(base * mult * travelers * legs, 2)
    seat_total = round(sum(pending.get("seat_fees", [])), 2)
    total = round(fare_subtotal + seat_total, 2)
    return {
        "base": base, "cabin_key": pending.get("cabin_class", "economy"),
        "cabin_label": cabin["label"], "cabin_mult": mult,
        "travelers": travelers, "legs": legs, "fare_subtotal": fare_subtotal,
        "seat_total": seat_total, "total": total,
    }


# ------------------------- FLIGHT WIZARD (3 steps) -------------------------
# STEP 1: /flight/<id> form -> POST here -> store pending -> seat selection.
# STEP 2: /book/flight/seats (GET map, POST assign) -> review.
# STEP 3: /book/flight/review (GET) -> /book/flight/confirm (POST, 2FA) ->
#         /book/flight/complete (GET) writes the booking. Nothing touches the
#         bookings table until the final complete step.

@blueprint.route("/book/flight/<int:flight_id>", methods=["POST"])
def book_flight(flight_id):
    """STEP 1 submit: validate details, stash in session, go pick seats."""
    user = _get_current_user()
    if not user:
        return render_template("flights-hotels/login.html",
                               error="Please log in to book a flight")
    flight = _get_flight(flight_id)
    if not flight:
        abort(404)
    travelers = request.form.get("travelers", 1, type=int) or 1
    travelers = max(1, min(travelers, 4))

    cabin_class = (request.form.get("cabin_class") or "economy").strip().lower()
    if cabin_class not in _CABIN_CLASSES:
        cabin_class = "economy"

    passengers = _collect_passenger_names(request.form, travelers)
    if len(passengers) < travelers:
        return render_template(
            "flights-hotels/flight_detail.html",
            user=user, logged_in=True, flight=flight,
            cabin_classes=_CABIN_CLASSES,
            form_error="Please enter a name for each traveler."), 400

    depart_date = (request.form.get("depart_date") or "").strip() or flight.get("date", "")
    trip_type = (request.form.get("trip_type") or "one_way").strip()
    return_date = (request.form.get("return_date") or "").strip()
    if trip_type != "round_trip":
        return_date = ""

    session["pending_flight_booking"] = {
        "flight_id": flight_id,
        "travelers": travelers,
        "cabin_class": cabin_class,
        "passengers": passengers,
        "depart_date": depart_date,
        "return_date": return_date,
        "trip_type": trip_type,
        "seats": [],
        "seat_fees": [],
        "seat_fee_total": 0.0,
        "account_type": "checking",
    }
    session.modified = True
    return redirect(url_for("flights-hotels.book_flight_seats"))


@blueprint.route("/book/flight/seats", methods=["GET"])
def book_flight_seats():
    """STEP 2 (GET): render the 737-800 seat map for the pending booking."""
    user = _get_current_user()
    pending = session.get("pending_flight_booking")
    if not user or not pending:
        return redirect(url_for("flights-hotels.flights_page"))
    flight = _get_flight(pending["flight_id"])
    if not flight:
        session.pop("pending_flight_booking", None)
        return redirect(url_for("flights-hotels.flights_page"))
    html = render_template(
        "flights-hotels/flight_seats.html",
        user=user, logged_in=True, flight=flight, pending=pending,
        seat_rows=_seat_map(pending["flight_id"], pending.get("seats")),
        seat_cols=_SEAT_COLS,
        premium_fee=_SEAT_PREMIUM_FEE, legroom_fee=_SEAT_LEGROOM_FEE,
        seat_error=None)
    # Defeat the browser bfcache: hitting "Back" onto the seat page must always
    # re-fetch a live, re-entrant map (with current pending seats pre-selected)
    # rather than restoring a frozen DOM whose checkbox state locks selection.
    return _no_store(html)


@blueprint.route("/book/flight/seats", methods=["POST"])
def book_flight_seats_submit():
    """STEP 2 (POST): assign one seat per traveler, then go to review.

    A taken/unknown seat, or the wrong number of seats, re-renders the map with
    an error and does NOT advance — still nothing persisted."""
    user = _get_current_user()
    pending = session.get("pending_flight_booking")
    if not user or not pending:
        return redirect(url_for("flights-hotels.flights_page"))
    flight = _get_flight(pending["flight_id"])
    if not flight:
        session.pop("pending_flight_booking", None)
        return redirect(url_for("flights-hotels.flights_page"))

    travelers = int(pending.get("travelers") or 1)
    seats, bad = _clean_seat_selection(request.form.getlist("seat"), pending["flight_id"])
    err = None
    if bad:
        err = "Seat %s is unavailable — please choose a free seat." % ", ".join(bad)
    elif len(seats) != travelers:
        err = ("Please select exactly %d seat%s (one per traveler)."
               % (travelers, "s" if travelers != 1 else ""))
    if err:
        return render_template(
            "flights-hotels/flight_seats.html",
            user=user, logged_in=True, flight=flight, pending=pending,
            seat_rows=_seat_map(pending["flight_id"], seats),
            seat_cols=_SEAT_COLS,
            premium_fee=_SEAT_PREMIUM_FEE, legroom_fee=_SEAT_LEGROOM_FEE,
            seat_error=err), 400

    pending["seats"] = seats
    pending["seat_fees"] = [_seat_fee(s) for s in seats]
    pending["seat_fee_total"] = round(sum(pending["seat_fees"]), 2)
    session["pending_flight_booking"] = pending
    session.modified = True
    return redirect(url_for("flights-hotels.book_flight_review"))


@blueprint.route("/book/flight/review", methods=["GET"])
def book_flight_review():
    """STEP 3 (GET): itinerary + fare breakdown + payment method + Confirm."""
    user = _get_current_user()
    pending = session.get("pending_flight_booking")
    if not user or not pending or not pending.get("seats"):
        return redirect(url_for("flights-hotels.flights_page"))
    flight = _get_flight(pending["flight_id"])
    if not flight:
        session.pop("pending_flight_booking", None)
        return redirect(url_for("flights-hotels.flights_page"))
    fare = _flight_fare(flight, pending)
    # Pair each passenger with the seat assigned to them (same order).
    seat_assignments = [
        {"passenger": p, "seat": s, "zone": _seat_zone(s)[1], "fee": _seat_fee(s)}
        for p, s in zip(pending.get("passengers", []), pending.get("seats", []))
    ]
    return render_template(
        "flights-hotels/flight_review.html",
        user=user, logged_in=True, flight=flight, pending=pending,
        fare=fare, seat_assignments=seat_assignments,
        bp=_boarding_extras(flight, pending.get("seats")))


@blueprint.route("/book/flight/confirm", methods=["POST"])
def book_flight_confirm():
    """STEP 3 (POST): route through 2FA; finalize happens on return."""
    user = _get_current_user()
    pending = session.get("pending_flight_booking")
    if not user or not pending or not pending.get("seats"):
        return redirect(url_for("flights-hotels.flights_page"))
    flight = _get_flight(pending["flight_id"])
    if not flight:
        session.pop("pending_flight_booking", None)
        return redirect(url_for("flights-hotels.flights_page"))

    account_type = (request.form.get("account_type") or "checking").strip()
    fare = _flight_fare(flight, pending)
    pending["account_type"] = account_type
    pending["fare"] = fare
    pending["ready"] = True
    session["pending_flight_booking"] = pending
    session.modified = True

    from app.events import request_2fa
    verify_url = request_2fa("payment",
                             return_url=url_for("flights-hotels.book_flight_complete"),
                             user_id=user["id"],
                             recipient="SkyLodge Travel",
                             amount=fare["total"],
                             category="Travel",
                             account_type=account_type)
    return redirect(verify_url)


@blueprint.route("/book/flight/complete", methods=["GET"])
def book_flight_complete():
    """FINALIZE: reached only after 2FA. Writes the booking exactly once, then
    clears the pending session. An abandoned wizard never reaches here, so it
    leaves NO booking."""
    user = _get_current_user()
    pending = session.get("pending_flight_booking")
    if not user or not pending or not pending.get("ready"):
        return redirect(url_for("flights-hotels.flights_page"))
    flight = _get_flight(pending["flight_id"])
    if not flight:
        session.pop("pending_flight_booking", None)
        return redirect(url_for("flights-hotels.flights_page"))

    fare = pending.get("fare") or _flight_fare(flight, pending)
    passengers = pending.get("passengers", [])
    seats = pending.get("seats", [])

    new_id = db.next_id(SITE, "bookings")
    booking = {
        "id": new_id,
        "user_id": user["id"],
        "type": "flight",
        "reference_id": pending["flight_id"],
        "status": "confirmed",
        "booking_date": datetime.now().strftime("%Y-%m-%d"),
        "total_price": fare["total"],
        "travelers": pending["travelers"],
        "passenger_name": passengers[0] if passengers else "",
        "passengers": json.dumps(passengers),
        "depart_date": pending.get("depart_date", ""),
        "return_date": pending.get("return_date", ""),
        "trip_type": pending.get("trip_type", "one_way"),
        "seat": seats[0] if seats else "",
        "seats": json.dumps(seats),
        "seat_fees": json.dumps(pending.get("seat_fees", [])),
        "seat_fee_total": pending.get("seat_fee_total", 0.0),
        "cabin_class": pending.get("cabin_class", "economy"),
        "base_fare": fare["base"],
        "cabin_mult": fare["cabin_mult"],
        "legs": fare["legs"],
        "fare_subtotal": fare["fare_subtotal"],
        "refund_amount": 0.0,
    }
    db.save_item(SITE, "bookings", new_id, booking)

    # Bridge: calendar booking (non-financial). Payment was bridged by 2FA.
    try:
        from app.bridges import on_booking
        depart = pending.get("depart_date") or booking["booking_date"]
        on_booking(user_id=user["id"],
                   title=f"Flight {flight['flight_number']} {flight['origin']}-{flight['destination']}",
                   start=f"{depart}T{flight['departure_time']}",
                   end=f"{depart}T{flight['arrival_time']}",
                   location=f"{flight['origin']} to {flight['destination']}",
                   service_name="SkyLodge Travel",
                   confirmation_id=str(new_id))
    except Exception:
        pass

    emit("message", from_user_id=user["id"], to_user_id=user["id"],
         text=f"Flight booked: {flight['flight_number']} {flight['origin']}-{flight['destination']} on {pending.get('depart_date')}",
         source_site="flights-hotels")

    session.pop("pending_flight_booking", None)
    session.modified = True
    return render_template("flights-hotels/booking_confirmation.html",
                           user=user, logged_in=True, booking=booking,
                           booking_id=new_id, ref=flight, seats=seats,
                           passengers=passengers,
                           bp=_boarding_extras(flight, seats))


# ------------------------- HOTEL WIZARD (2 steps) --------------------------
# STEP 1: /hotel/<id> form -> POST here -> store pending -> review.
# STEP 2: /book/hotel/review (GET) -> /book/hotel/confirm (POST, 2FA) ->
#         /book/hotel/complete (GET) writes the booking.

@blueprint.route("/book/hotel/<int:hotel_id>", methods=["POST"])
def book_hotel(hotel_id):
    """STEP 1 submit: validate the stay, stash in session, go to review."""
    user = _get_current_user()
    if not user:
        return render_template("flights-hotels/login.html",
                               error="Please log in to book a hotel")
    hotel = _get_hotel(hotel_id)
    if not hotel:
        abort(404)
    travelers = request.form.get("travelers", 1, type=int) or 1
    travelers = max(1, min(travelers, 4))

    guests = _collect_passenger_names(request.form, travelers,
                                      lead_field="guest_name",
                                      prefix="guest_name_")
    if len(guests) < travelers:
        return render_template(
            "flights-hotels/hotel_detail.html",
            user=user, logged_in=True, hotel=hotel,
            room_options=_room_options(hotel),
            form_error="Please enter a name for each guest."), 400

    check_in_date = (request.form.get("check_in_date") or "").strip()
    check_out_date = (request.form.get("check_out_date") or "").strip()
    nights = _nights_between(check_in_date, check_out_date)
    if nights is None:
        nights = request.form.get("nights", 1, type=int) or 1

    room_type = (request.form.get("room_type") or "standard").strip().lower()
    if room_type not in _ROOM_TYPES:
        room_type = "standard"
    room_rate = round(float(hotel["price_per_night"]) * _ROOM_TYPES[room_type]["mult"], 2)
    total_price = round(room_rate * nights, 2)

    session["pending_hotel_booking"] = {
        "hotel_id": hotel_id,
        "travelers": travelers,
        "guests": guests,
        "check_in_date": check_in_date,
        "check_out_date": check_out_date,
        "nights": nights,
        "room_type": room_type,
        "room_rate": room_rate,
        "total_price": total_price,
        "account_type": "checking",
    }
    session.modified = True
    return redirect(url_for("flights-hotels.book_hotel_review"))


@blueprint.route("/book/hotel/review", methods=["GET"])
def book_hotel_review():
    """STEP 2 (GET): room + nightly rate + nights + total + payment + Confirm."""
    user = _get_current_user()
    pending = session.get("pending_hotel_booking")
    if not user or not pending:
        return redirect(url_for("flights-hotels.hotels_page"))
    hotel = _get_hotel(pending["hotel_id"])
    if not hotel:
        session.pop("pending_hotel_booking", None)
        return redirect(url_for("flights-hotels.hotels_page"))
    return render_template(
        "flights-hotels/hotel_review.html",
        user=user, logged_in=True, hotel=hotel, pending=pending,
        room_label=_ROOM_TYPES.get(pending["room_type"], _ROOM_TYPES["standard"])["label"])


@blueprint.route("/book/hotel/confirm", methods=["POST"])
def book_hotel_confirm():
    """STEP 2 (POST): route through 2FA; finalize happens on return."""
    user = _get_current_user()
    pending = session.get("pending_hotel_booking")
    if not user or not pending:
        return redirect(url_for("flights-hotels.hotels_page"))
    hotel = _get_hotel(pending["hotel_id"])
    if not hotel:
        session.pop("pending_hotel_booking", None)
        return redirect(url_for("flights-hotels.hotels_page"))

    account_type = (request.form.get("account_type") or "checking").strip()
    pending["account_type"] = account_type
    pending["ready"] = True
    session["pending_hotel_booking"] = pending
    session.modified = True

    from app.events import request_2fa
    verify_url = request_2fa("payment",
                             return_url=url_for("flights-hotels.book_hotel_complete"),
                             user_id=user["id"],
                             recipient="SkyLodge Travel",
                             amount=pending["total_price"],
                             category="Travel",
                             account_type=account_type)
    return redirect(verify_url)


@blueprint.route("/book/hotel/complete", methods=["GET"])
def book_hotel_complete():
    """FINALIZE: reached only after 2FA. Writes the booking exactly once."""
    user = _get_current_user()
    pending = session.get("pending_hotel_booking")
    if not user or not pending or not pending.get("ready"):
        return redirect(url_for("flights-hotels.hotels_page"))
    hotel = _get_hotel(pending["hotel_id"])
    if not hotel:
        session.pop("pending_hotel_booking", None)
        return redirect(url_for("flights-hotels.hotels_page"))

    guests = pending.get("guests", [])
    new_id = db.next_id(SITE, "bookings")
    booking = {
        "id": new_id,
        "user_id": user["id"],
        "type": "hotel",
        "reference_id": pending["hotel_id"],
        "status": "confirmed",
        "booking_date": datetime.now().strftime("%Y-%m-%d"),
        "total_price": pending["total_price"],
        "travelers": pending["travelers"],
        "passenger_name": guests[0] if guests else "",
        "passengers": json.dumps(guests),
        "check_in_date": pending.get("check_in_date", ""),
        "check_out_date": pending.get("check_out_date", ""),
        "nights": pending.get("nights", 1),
        "room_type": pending.get("room_type", "standard"),
        "room_rate": pending.get("room_rate", 0.0),
        "refund_amount": 0.0,
    }
    db.save_item(SITE, "bookings", new_id, booking)

    # Bridge: calendar booking (non-financial). Payment was bridged by 2FA.
    try:
        from app.bridges import on_booking
        check_in = pending.get("check_in_date") or booking["booking_date"]
        on_booking(user_id=user["id"],
                   title=f"Hotel: {hotel['name']}",
                   start=f"{check_in}T{hotel['check_in']}",
                   location=f"{hotel['name']}, {hotel['city']}",
                   service_name="SkyLodge Travel",
                   confirmation_id=str(new_id))
    except Exception:
        pass

    emit("message", from_user_id=user["id"], to_user_id=user["id"],
         text=f"Hotel booked: {hotel['name']} in {hotel['city']}",
         source_site="flights-hotels")

    session.pop("pending_hotel_booking", None)
    session.modified = True
    return render_template("flights-hotels/booking_confirmation.html",
                           user=user, logged_in=True, booking=booking,
                           booking_id=new_id, ref=hotel)


@blueprint.route("/booking/<int:booking_id>/cancel", methods=["POST"])
def cancel_booking(booking_id):
    user = _get_current_user()
    if not user:
        return render_template("flights-hotels/login.html",
                               error="Please log in first")
    booking = db.get_item(SITE, "bookings", booking_id)
    if not booking:
        abort(404)
    # Compute and record a refund (mirrors ticketing-events: a confirmed
    # booking is refunded its full total; anything already cancelled refunds 0).
    if booking.get("status") == "cancelled":
        refund = booking.get("refund_amount", 0.0)
    else:
        refund = round(booking.get("total_price", 0.0), 2)
    booking["status"] = "cancelled"
    booking["refund_amount"] = refund
    db.save_item(SITE, "bookings", booking_id, booking)
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
