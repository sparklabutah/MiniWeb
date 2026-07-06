"""Comparison / Aggregators — Phone specs comparison site (GSMArena-style).

Data is stored in SQLite: phones in the comparison_aggregators_phones table,
users in a per-site typed table.  Queried through app.db.
"""
import pathlib
import re
from collections import Counter

from flask import (Blueprint, Response, abort, jsonify, redirect,
                   render_template, request, session, url_for)
from app import db
from app.db import _deserialize_row

SITE = "comparison-aggregators"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "comparison-aggregators",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# DB-backed data access (comparison_aggregators_phones table)
# ---------------------------------------------------------------------------


def _db_conn():
    return db.get_conn()

# ---------------------------------------------------------------------------
# Data interpreter — reads raw CSV row dict, cleans into phone record
# ---------------------------------------------------------------------------

def _parse_price_eur(raw_price):
    """Extract a numeric EUR price from the raw price string.
    Returns None if no EUR price found."""
    if not raw_price:
        return None
    # Patterns: "About 430 EUR", "€ 709.99", "About 100 EUR"
    m = re.search(r'About\s+(\d[\d,]*(?:\.\d+)?)\s*EUR', raw_price, re.IGNORECASE)
    if m:
        return float(m.group(1).replace(",", ""))
    m = re.search(r'[€]\s*(\d[\d,]*(?:\.\d+)?)', raw_price)
    if m:
        return float(m.group(1).replace(",", ""))
    return None


def _parse_price_usd(raw_price):
    """Extract a numeric USD price from the raw price string."""
    if not raw_price:
        return None
    m = re.search(r'\$\s*(\d[\d,]*(?:\.\d+)?)', raw_price)
    if m:
        return float(m.group(1).replace(",", ""))
    return None


def _parse_numeric(val, suffix=""):
    """Extract a numeric value, optionally stripping a suffix like 'mAh' or '"'."""
    if not val:
        return None
    val = val.strip().replace('"', '').replace("'", "")
    if suffix:
        val = val.replace(suffix, "")
    m = re.search(r'(\d[\d,]*(?:\.\d+)?)', val)
    if m:
        return float(m.group(1).replace(",", ""))
    return None


def _extract_year(released_at):
    """Extract a 4-digit year from released_at string."""
    if not released_at:
        return None
    m = re.search(r'\b(19|20)\d{2}\b', released_at)
    if m:
        return int(m.group())
    return None


def _interpret_record(raw, idx):
    """Convert a raw DB row dict into a cleaned phone record."""
    # Per-site table uses lowercase column names; fall back to legacy
    # capitalized keys for backwards compatibility.
    def _g(key):
        """Get field by lowercase key, falling back to original case."""
        val = raw.get(key)
        if val is None:
            val = raw.get(key.capitalize(), "")
        return str(val or "")

    price_raw = _g("price")
    price_eur = _parse_price_eur(price_raw)
    price_usd = _parse_price_usd(price_raw)
    price = price_usd or price_eur  # prefer USD if available
    battery_mah = _parse_numeric(_g("battery_size"), "mAh")
    display_num = _parse_numeric(_g("display_size"))
    camera_num = _parse_numeric(_g("camera_pixels"), "MP")
    ram_num = _parse_numeric(_g("ram"), "GB RAM")
    year = _extract_year(_g("released_at"))

    # Normalise OS to a top-level category
    os_raw = _g("os").strip()
    if "Android" in os_raw:
        os_family = "Android"
    elif "iOS" in os_raw or os_raw.startswith("Apple"):
        os_family = "iOS"
    elif "Windows" in os_raw:
        os_family = "Windows"
    elif "Symbian" in os_raw:
        os_family = "Symbian"
    elif "BlackBerry" in os_raw:
        os_family = "BlackBerry"
    elif os_raw == "Feature phone" or os_raw == "":
        os_family = "Feature phone"
    else:
        os_family = "Other"

    return {
        "id": idx,
        "original_id": int(raw.get("id", 0) or 0),
        "brand": _g("brand").strip(),
        "name": _g("name").strip(),
        "released_at": _g("released_at").strip(),
        "year": year,
        "os": os_raw,
        "os_family": os_family,
        "storage": _g("storage").strip(),
        "display_size": _g("display_size").strip(),
        "display_size_num": display_num,
        "display_resolution": _g("display_resolution").strip(),
        "camera_pixels": _g("camera_pixels").strip(),
        "camera_num": camera_num,
        "ram": _g("ram").strip(),
        "ram_num": ram_num,
        "battery_size": _g("battery_size").strip(),
        "battery_mah": battery_mah,
        "battery_type": _g("battery_type").strip(),
        "chipset": _g("chipset").strip(),
        "price_raw": price_raw.strip(),
        "price": price,
        "body": _g("body").strip(),
        "weight": _g("weight").strip(),
        "sim": _g("sim").strip(),
        "wlan": _g("wlan").strip(),
        "bluetooth": _g("bluetooth").strip(),
        "gps": _g("gps").strip(),
        "usb": _g("usb").strip(),
        "sensors": _g("sensors").strip(),
        "colors": _g("colors").strip(),
        "nfc": _g("nfc").strip(),
    }


# ---------------------------------------------------------------------------
# DB query helpers
# ---------------------------------------------------------------------------

def _db_query_phones(q="", brand=None, os_family=None, price_min=None,
                     price_max=None, battery_min=None, year_from=None,
                     year_to=None, sort="newest", limit=5000, offset=0):
    """Query phones from comparison_aggregators_phones with filters.

    Returns interpreted phone dicts.  Because _interpret_record computes
    derived fields (year, os_family, price, battery_mah) from raw strings,
    we do text-level filtering where feasible and post-filter the rest.
    """

    if q:
        # --- Text search path: use FTS5 via db.search() ---
        where_eq = {}
        if brand:
            where_eq["brand"] = brand
        rows = db.search(SITE, "phones", q,
                         where=where_eq if where_eq else None,
                         limit=max(limit, 5000))
    else:
        # --- Non-search path: normal SQL filters ---
        conn = _db_conn()
        clauses = []
        params = []

        # Brand filter — exact match
        if brand:
            clauses.append("brand = ?")
            params.append(brand)

        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        sql = f"SELECT * FROM comparison_aggregators_phones {where} LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        raw_rows = conn.execute(sql, params).fetchall()
        rows = [_deserialize_row(row) for row in raw_rows]

    # Interpret all rows, then apply post-filters that need computed fields
    phones = []
    for i, raw in enumerate(rows):
        phone = _interpret_record(raw, offset + i + 1)
        phones.append(phone)

    # Post-filter on computed fields
    if os_family:
        phones = [p for p in phones if p["os_family"] == os_family]
    if price_min is not None:
        phones = [p for p in phones if p["price"] is not None and p["price"] >= price_min]
    if price_max is not None:
        phones = [p for p in phones if p["price"] is not None and p["price"] <= price_max]
    if battery_min is not None:
        phones = [p for p in phones if p["battery_mah"] is not None and p["battery_mah"] >= battery_min]
    if year_from is not None:
        phones = [p for p in phones if p["year"] is not None and p["year"] >= year_from]
    if year_to is not None:
        phones = [p for p in phones if p["year"] is not None and p["year"] <= year_to]

    # Sort (when q is present, FTS already ranked by relevance; user can override)
    if not q or sort != "newest":
        phones = _sort_phones(phones, sort)

    return phones


def _db_get_phone_by_item_id(item_id):
    """Look up a single phone by its id in comparison_aggregators_phones."""
    conn = _db_conn()
    row = conn.execute(
        "SELECT * FROM comparison_aggregators_phones WHERE id = ?",
        (item_id,),
    ).fetchone()
    if not row:
        return None
    raw = _deserialize_row(row)
    return _interpret_record(raw, raw.get("id", 0))


def _db_count_phones():
    conn = _db_conn()
    return conn.execute(
        "SELECT COUNT(*) FROM comparison_aggregators_phones"
    ).fetchone()[0]


# Brand and OS family caches (computed once from DB)
_db_brands_cache = None
_db_os_cache = None


def _db_get_brands():
    global _db_brands_cache
    if _db_brands_cache is not None:
        return _db_brands_cache
    conn = _db_conn()
    rows = conn.execute(
        "SELECT DISTINCT brand FROM comparison_aggregators_phones"
    ).fetchall()
    _db_brands_cache = sorted(b[0] for b in rows if b[0] and b[0].strip())
    return _db_brands_cache


def _db_get_os_families():
    """Compute unique OS families from the DB.

    Because os_family is a computed field (not stored in raw data), we sample
    a batch and extract unique values.
    """
    global _db_os_cache
    if _db_os_cache is not None:
        return _db_os_cache
    conn = _db_conn()
    rows = conn.execute(
        "SELECT os FROM comparison_aggregators_phones LIMIT 20000"
    ).fetchall()
    families = set()
    for row in rows:
        os_raw = (row[0] or "").strip()
        if "Android" in os_raw:
            families.add("Android")
        elif "iOS" in os_raw or os_raw.startswith("Apple"):
            families.add("iOS")
        elif "Windows" in os_raw:
            families.add("Windows")
        elif "Symbian" in os_raw:
            families.add("Symbian")
        elif "BlackBerry" in os_raw:
            families.add("BlackBerry")
        elif os_raw == "Feature phone" or os_raw == "":
            families.add("Feature phone")
        else:
            families.add("Other")
    _db_os_cache = sorted(families)
    return _db_os_cache


def _db_related_phones(phone, limit=6):
    """Find phones with the same brand from DB."""
    conn = _db_conn()
    rows = conn.execute(
        "SELECT * FROM comparison_aggregators_phones "
        "WHERE brand = ? AND id != ? LIMIT ?",
        (phone["brand"], phone["original_id"], limit),
    ).fetchall()
    return [_interpret_record(_deserialize_row(r), _deserialize_row(r).get("id", i))
            for i, r in enumerate(rows)]


# ---------------------------------------------------------------------------
# Unified accessors — always use DB
# ---------------------------------------------------------------------------


def _get_brands():
    return _db_get_brands()


def _get_os_families():
    return _db_get_os_families()


# ---------------------------------------------------------------------------
# Users (mutable state — stored in per-site SQLite table)
# ---------------------------------------------------------------------------

def _load_users():
    return db.query(SITE, "users")


def _save_users(users):
    db.save_collection(SITE, "users", users)


def _get_user(user_id):
    return db.get_item(SITE, "users", user_id)


# ---------------------------------------------------------------------------
# Search / filter helpers (used for file-based fallback)
# ---------------------------------------------------------------------------

def _search_phones(phones, query):
    if not query:
        return phones
    q = query.lower().strip()
    return [p for p in phones if q in p["name"].lower() or
            q in p["brand"].lower() or
            q in p["os"].lower() or
            q in p["chipset"].lower()]


def _filter_phones(phones, brand=None, os_family=None, price_min=None,
                   price_max=None, battery_min=None, year_from=None, year_to=None):
    results = list(phones)
    if brand:
        results = [p for p in results if p["brand"] == brand]
    if os_family:
        results = [p for p in results if p["os_family"] == os_family]
    if price_min is not None:
        results = [p for p in results if p["price"] is not None and p["price"] >= price_min]
    if price_max is not None:
        results = [p for p in results if p["price"] is not None and p["price"] <= price_max]
    if battery_min is not None:
        results = [p for p in results if p["battery_mah"] is not None and p["battery_mah"] >= battery_min]
    if year_from is not None:
        results = [p for p in results if p["year"] is not None and p["year"] >= year_from]
    if year_to is not None:
        results = [p for p in results if p["year"] is not None and p["year"] <= year_to]
    return results


def _sort_phones(phones, sort_key):
    if sort_key == "name":
        return sorted(phones, key=lambda p: p["name"].lower())
    elif sort_key == "price_asc":
        with_price = [p for p in phones if p["price"] is not None]
        without_price = [p for p in phones if p["price"] is None]
        return sorted(with_price, key=lambda p: p["price"]) + without_price
    elif sort_key == "price_desc":
        with_price = [p for p in phones if p["price"] is not None]
        without_price = [p for p in phones if p["price"] is None]
        return sorted(with_price, key=lambda p: -p["price"]) + without_price
    elif sort_key == "battery_desc":
        with_bat = [p for p in phones if p["battery_mah"] is not None]
        without_bat = [p for p in phones if p["battery_mah"] is None]
        return sorted(with_bat, key=lambda p: -p["battery_mah"]) + without_bat
    elif sort_key == "display_desc":
        with_disp = [p for p in phones if p["display_size_num"] is not None]
        without_disp = [p for p in phones if p["display_size_num"] is None]
        return sorted(with_disp, key=lambda p: -p["display_size_num"]) + without_disp
    elif sort_key == "camera_desc":
        with_cam = [p for p in phones if p["camera_num"] is not None]
        without_cam = [p for p in phones if p["camera_num"] is None]
        return sorted(with_cam, key=lambda p: -p["camera_num"]) + without_cam
    elif sort_key == "newest":
        return sorted(phones, key=lambda p: (-(p["year"] or 0), p["name"]))
    elif sort_key == "oldest":
        with_year = [p for p in phones if p["year"] is not None]
        without_year = [p for p in phones if p["year"] is None]
        return sorted(with_year, key=lambda p: (p["year"], p["name"])) + without_year
    # default: newest first
    return sorted(phones, key=lambda p: (-(p["year"] or 0), p["name"]))


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    brands = _get_brands()
    os_families = _get_os_families()

    q = request.args.get("q", "").strip()
    brand = request.args.get("brand", "").strip()
    os_fam = request.args.get("os", "").strip()
    sort = request.args.get("sort", "newest").strip()
    price_min = request.args.get("price_min", type=float)
    price_max = request.args.get("price_max", type=float)
    battery_min = request.args.get("battery_min", type=float)

    results = _db_query_phones(
        q=q, brand=brand or None, os_family=os_fam or None,
        sort=sort, price_min=price_min, price_max=price_max,
        battery_min=battery_min,
    )

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template("comparison-aggregators/index.html",
                           phones=results, brands=brands,
                           os_families=os_families,
                           q=q, brand=brand, os_fam=os_fam, sort=sort,
                           price_min=price_min, price_max=price_max,
                           battery_min=battery_min, user=user)


@blueprint.route("/phone/<int:phone_id>")
def phone_detail(phone_id):
    phone = _db_get_phone_by_item_id(phone_id)
    if phone is None:
        abort(404)
    phone["id"] = phone_id
    related = _db_related_phones(phone)

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("comparison-aggregators/phone.html",
                           phone=phone, related=related, user=user)


@blueprint.route("/brand/<path:brand_name>")
def brand_page(brand_name):
    sort = request.args.get("sort", "newest").strip()
    filtered = _db_query_phones(brand=brand_name, sort=sort)
    user = _get_user(session["user_id"]) if "user_id" in session else None
    return render_template("comparison-aggregators/brand.html",
                           phones=filtered, brand_name=brand_name,
                           brands=_get_brands(), sort=sort, user=user)


@blueprint.route("/compare")
def compare_page():
    ids_str = request.args.get("ids", "")
    selected = []

    if ids_str:
        # Explicit IDs from URL
        ids = [int(x) for x in ids_str.split(",") if x.strip().isdigit()]
        for pid in ids:
            phone = _db_get_phone_by_item_id(pid)
            if phone:
                phone["id"] = pid
                selected.append(phone)
    elif "user_id" in session:
        # Load from user's saved compare list
        user = _get_user(session["user_id"])
        if user:
            for pid in user.get("compare_lists", []):
                phone = _db_get_phone_by_item_id(pid)
                if phone:
                    phone["id"] = pid
                    selected.append(phone)

    phones = _db_query_phones(limit=500)
    user = _get_user(session["user_id"]) if "user_id" in session else None

    return render_template("comparison-aggregators/compare.html",
                           phones=phones, selected=selected, user=user)


@blueprint.route("/favorites")
def favorites_page():
    if "user_id" not in session:
        return redirect(url_for("comparison-aggregators.login_page"))
    user = _get_user(session["user_id"])
    if not user:
        return redirect(url_for("comparison-aggregators.login_page"))

    fav_phones = []
    for pid in user.get("favorites", []):
        phone = _db_get_phone_by_item_id(pid)
        if phone:
            phone["id"] = pid
            fav_phones.append(phone)

    return render_template("comparison-aggregators/favorites.html",
                           phones=fav_phones, user=user)


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("comparison-aggregators/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return render_template("comparison-aggregators/login.html",
                               error="Invalid username or password")
    session["user_id"] = user["id"]
    return redirect(url_for("comparison-aggregators.dashboard"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("comparison-aggregators.index"))


@blueprint.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("comparison-aggregators.login_page"))
    user = _get_user(session["user_id"])
    if not user:
        return redirect(url_for("comparison-aggregators.login_page"))

    fav_phones = []
    for pid in user.get("favorites", []):
        phone = _db_get_phone_by_item_id(pid)
        if phone:
            phone["id"] = pid
            fav_phones.append(phone)
    compare_phones = []
    for pid in user.get("compare_lists", []):
        phone = _db_get_phone_by_item_id(pid)
        if phone:
            phone["id"] = pid
            compare_phones.append(phone)

    return render_template("comparison-aggregators/dashboard.html",
                           user=user, fav_phones=fav_phones,
                           compare_phones=compare_phones)


# ---------------------------------------------------------------------------
# Form-based mutation routes (for browser automation compatibility)
# ---------------------------------------------------------------------------

@blueprint.route("/phone/<int:phone_id>/favorite", methods=["POST"])
def form_toggle_favorite(phone_id):
    if "user_id" not in session:
        return redirect(url_for("comparison-aggregators.login_page"))
    users = _load_users()
    user = next((u for u in users if u["id"] == session["user_id"]), None)
    if not user:
        return redirect(url_for("comparison-aggregators.login_page"))
    favs = user.setdefault("favorites", [])
    if phone_id in favs:
        favs.remove(phone_id)
    else:
        favs.append(phone_id)
    _save_users(users)
    return redirect(url_for("comparison-aggregators.phone_detail", phone_id=phone_id))


@blueprint.route("/phone/<int:phone_id>/compare-add", methods=["POST"])
def form_add_compare(phone_id):
    if "user_id" not in session:
        return redirect(url_for("comparison-aggregators.login_page"))
    users = _load_users()
    user = next((u for u in users if u["id"] == session["user_id"]), None)
    if not user:
        return redirect(url_for("comparison-aggregators.login_page"))
    cl = user.setdefault("compare_lists", [])
    if phone_id in cl:
        cl.remove(phone_id)
    else:
        cl.append(phone_id)
    _save_users(users)
    redirect_to = request.form.get("redirect_to", "")
    if redirect_to:
        return redirect(redirect_to)
    return redirect(url_for("comparison-aggregators.phone_detail", phone_id=phone_id))


@blueprint.route("/dashboard/remove-favorite/<int:phone_id>", methods=["POST"])
def form_remove_favorite(phone_id):
    if "user_id" not in session:
        return redirect(url_for("comparison-aggregators.login_page"))
    users = _load_users()
    user = next((u for u in users if u["id"] == session["user_id"]), None)
    if not user:
        return redirect(url_for("comparison-aggregators.login_page"))
    favs = user.setdefault("favorites", [])
    if phone_id in favs:
        favs.remove(phone_id)
    _save_users(users)
    return redirect(url_for("comparison-aggregators.dashboard"))


@blueprint.route("/dashboard/remove-compare/<int:phone_id>", methods=["POST"])
def form_remove_compare(phone_id):
    if "user_id" not in session:
        return redirect(url_for("comparison-aggregators.login_page"))
    users = _load_users()
    user = next((u for u in users if u["id"] == session["user_id"]), None)
    if not user:
        return redirect(url_for("comparison-aggregators.login_page"))
    cl = user.setdefault("compare_lists", [])
    if phone_id in cl:
        cl.remove(phone_id)
    _save_users(users)
    return redirect(url_for("comparison-aggregators.dashboard"))


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/phones")
def api_phones():
    q = request.args.get("q", "").strip()
    brand = request.args.get("brand", "").strip()
    os_fam = request.args.get("os", "").strip()
    sort = request.args.get("sort", "newest").strip()
    price_min = request.args.get("price_min", type=float)
    price_max = request.args.get("price_max", type=float)
    battery_min = request.args.get("battery_min", type=float)
    year_from = request.args.get("year_from", type=int)
    year_to = request.args.get("year_to", type=int)
    limit = request.args.get("limit", type=int)

    results = _db_query_phones(
        q=q, brand=brand or None, os_family=os_fam or None,
        sort=sort, price_min=price_min, price_max=price_max,
        battery_min=battery_min, year_from=year_from, year_to=year_to,
        limit=limit or 5000,
    )

    return jsonify(results)


@blueprint.route("/api/phones/<int:phone_id>")
def api_phone(phone_id):
    phone = _db_get_phone_by_item_id(phone_id)
    if phone is None:
        abort(404)
    phone["id"] = phone_id
    return jsonify(phone)


@blueprint.route("/api/brands")
def api_brands():
    conn = _db_conn()
    rows = conn.execute(
        "SELECT brand, COUNT(*) FROM comparison_aggregators_phones "
        "GROUP BY brand ORDER BY brand"
    ).fetchall()
    return jsonify([{"name": r[0], "count": r[1]} for r in rows if r[0] and r[0].strip()])


@blueprint.route("/api/brands/<path:brand_name>/phones")
def api_brand_phones(brand_name):
    sort = request.args.get("sort", "newest").strip()
    filtered = _db_query_phones(brand=brand_name, sort=sort)
    return jsonify(filtered)


@blueprint.route("/api/compare")
def api_compare():
    ids_str = request.args.get("ids", "")
    ids = [int(x) for x in ids_str.split(",") if x.strip().isdigit()]
    selected = []
    for pid in ids:
        phone = _db_get_phone_by_item_id(pid)
        if phone:
            phone["id"] = pid
            selected.append(phone)
    return jsonify(selected)


@blueprint.route("/api/stats")
def api_stats():
    brand_filter = request.args.get("brand", "").strip()

    phones = _db_query_phones(brand=brand_filter or None, limit=20000)

    if not phones:
        return jsonify({"count": 0})

    priced = [p for p in phones if p["price"] is not None]
    years = [p["year"] for p in phones if p["year"] is not None]
    batteries = [p["battery_mah"] for p in phones if p["battery_mah"] is not None]

    stats = {
        "count": len(phones),
        "brands": len(set(p["brand"] for p in phones)),
        "with_price": len(priced),
        "avg_price": round(sum(p["price"] for p in priced) / len(priced), 2) if priced else None,
        "min_price": min(p["price"] for p in priced) if priced else None,
        "max_price": max(p["price"] for p in priced) if priced else None,
        "os_distribution": dict(Counter(p["os_family"] for p in phones).most_common(10)),
        "top_brands": dict(Counter(p["brand"] for p in phones).most_common(10)),
    }
    if years:
        stats["earliest_year"] = min(years)
        stats["latest_year"] = max(years)
    if batteries:
        stats["avg_battery"] = round(sum(batteries) / len(batteries), 1)
    return jsonify(stats)


# ---------------------------------------------------------------------------
# User API routes (mutable state)
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
    return jsonify({"user_id": user["id"], "username": user["username"]})


@blueprint.route("/api/users/<int:user_id>")
def api_user(user_id):
    user = _get_user(user_id)
    if not user:
        abort(404)
    return jsonify({k: v for k, v in user.items() if k != "password"})


@blueprint.route("/api/users/<int:user_id>/favorite", methods=["POST"])
def api_toggle_favorite(user_id):
    data = request.get_json(silent=True) or {}
    phone_id = data.get("phone_id")
    if phone_id is None:
        return jsonify({"error": "phone_id required"}), 400
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    favs = user.setdefault("favorites", [])
    if phone_id in favs:
        favs.remove(phone_id)
        action = "removed"
    else:
        favs.append(phone_id)
        action = "added"
    _save_users(users)
    return jsonify({"action": action, "phone_id": phone_id,
                    "total_favorites": len(favs)})


@blueprint.route("/api/users/<int:user_id>/compare-list", methods=["POST"])
def api_toggle_compare(user_id):
    data = request.get_json(silent=True) or {}
    phone_id = data.get("phone_id")
    if phone_id is None:
        return jsonify({"error": "phone_id required"}), 400
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    cl = user.setdefault("compare_lists", [])
    if phone_id in cl:
        cl.remove(phone_id)
        action = "removed"
    else:
        cl.append(phone_id)
        action = "added"
    _save_users(users)
    return jsonify({"action": action, "phone_id": phone_id,
                    "total_in_compare": len(cl)})
