"""Comparison / Aggregators — Phone specs comparison site (GSMArena-style).

Data interpreter: reads the original phones.csv snapshot, samples based on
config/config.json, and serves through Flask routes.  The raw data file is
never modified.
"""
import csv
import json
import pathlib
import random
import re
from collections import Counter

from flask import (Blueprint, Response, abort, jsonify, redirect,
                   render_template, request, session, url_for)

SITE_DIR = pathlib.Path(__file__).resolve().parent
DATA_FILE = SITE_DIR / "data" / "phones.csv"
USERS_FILE = SITE_DIR / "data" / "users.json"
CONFIG_FILE = SITE_DIR / "config" / "config.json"

blueprint = Blueprint(
    "comparison-aggregators",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)

# ---------------------------------------------------------------------------
# Data interpreter — reads raw CSV, samples, cleans
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
    """Convert a raw CSV row dict into a cleaned phone record."""
    price_eur = _parse_price_eur(raw.get("Price", ""))
    price_usd = _parse_price_usd(raw.get("Price", ""))
    price = price_usd or price_eur  # prefer USD if available
    battery_mah = _parse_numeric(raw.get("battery_size", ""), "mAh")
    display_num = _parse_numeric(raw.get("display_size", ""))
    camera_num = _parse_numeric(raw.get("camera_pixels", ""), "MP")
    ram_num = _parse_numeric(raw.get("ram", ""), "GB RAM")
    year = _extract_year(raw.get("released_at", ""))

    # Normalise OS to a top-level category
    os_raw = raw.get("os", "").strip()
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
        "brand": raw.get("brand", "").strip(),
        "name": raw.get("name", "").strip(),
        "released_at": raw.get("released_at", "").strip(),
        "year": year,
        "os": os_raw,
        "os_family": os_family,
        "storage": raw.get("storage", "").strip(),
        "display_size": raw.get("display_size", "").strip(),
        "display_size_num": display_num,
        "display_resolution": raw.get("display_resolution", "").strip(),
        "camera_pixels": raw.get("camera_pixels", "").strip(),
        "camera_num": camera_num,
        "ram": raw.get("ram", "").strip(),
        "ram_num": ram_num,
        "battery_size": raw.get("battery_size", "").strip(),
        "battery_mah": battery_mah,
        "battery_type": raw.get("battery_type", "").strip(),
        "chipset": raw.get("chipset", "").strip(),
        "price_raw": raw.get("Price", "").strip(),
        "price": price,
        "body": raw.get("body", "").strip(),
        "weight": raw.get("Weight", "").strip(),
        "sim": raw.get("SIM", "").strip(),
        "wlan": raw.get("WLAN", "").strip(),
        "bluetooth": raw.get("Bluetooth", "").strip(),
        "gps": raw.get("GPS", "").strip(),
        "usb": raw.get("USB", "").strip(),
        "sensors": raw.get("Sensors", "").strip(),
        "colors": raw.get("Colors", "").strip(),
        "nfc": raw.get("NFC", "").strip(),
    }


def _load_phones():
    """Read CSV dataset.  num_data_points=-1 loads all records; positive N
    uses reservoir sampling to pick N records uniformly at random."""
    config = _load_config()
    n = config.get("num_data_points", -1)
    seed = config.get("random_seed", 42)
    rng = random.Random(seed)

    rows = []
    with open(DATA_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    if n > 0 and n < len(rows):
        rows = rng.sample(rows, n)

    phones = []
    for idx, raw in enumerate(rows, 1):
        phones.append(_interpret_record(raw, idx))

    # Sort by year descending (newest first), then name
    phones.sort(key=lambda p: (-(p["year"] or 0), p["name"]))
    for i, p in enumerate(phones, 1):
        p["id"] = i

    return phones


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------

_phones = None
_brands = None
_os_families = None


def _ensure_loaded():
    global _phones, _brands, _os_families
    if _phones is None:
        _phones = _load_phones()
        _brands = sorted(set(p["brand"] for p in _phones if p["brand"]))
        _os_families = sorted(set(p["os_family"] for p in _phones))


def _get_phones():
    _ensure_loaded()
    return _phones


def _get_brands():
    _ensure_loaded()
    return _brands


def _get_os_families():
    _ensure_loaded()
    return _os_families


# ---------------------------------------------------------------------------
# Users (mutable state)
# ---------------------------------------------------------------------------

def _load_users():
    if USERS_FILE.exists():
        return json.loads(USERS_FILE.read_text())
    return []


def _save_users(users):
    USERS_FILE.write_text(json.dumps(users, indent=2))


def _get_user(user_id):
    users = _load_users()
    return next((u for u in users if u["id"] == user_id), None)


# ---------------------------------------------------------------------------
# Search / filter helpers
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
    phones = _get_phones()
    brands = _get_brands()
    os_families = _get_os_families()

    q = request.args.get("q", "").strip()
    brand = request.args.get("brand", "").strip()
    os_fam = request.args.get("os", "").strip()
    sort = request.args.get("sort", "newest").strip()
    price_min = request.args.get("price_min", type=float)
    price_max = request.args.get("price_max", type=float)
    battery_min = request.args.get("battery_min", type=float)

    results = list(phones)
    if q:
        results = _search_phones(results, q)
    results = _filter_phones(results, brand=brand or None,
                             os_family=os_fam or None,
                             price_min=price_min, price_max=price_max,
                             battery_min=battery_min)
    results = _sort_phones(results, sort)

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
    phones = _get_phones()
    phone = next((p for p in phones if p["id"] == phone_id), None)
    if phone is None:
        abort(404)
    # Find related phones from same brand
    related = [p for p in phones if p["brand"] == phone["brand"]
               and p["id"] != phone_id][:6]
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("comparison-aggregators/phone.html",
                           phone=phone, related=related, user=user)


@blueprint.route("/brand/<path:brand_name>")
def brand_page(brand_name):
    phones = _get_phones()
    filtered = [p for p in phones if p["brand"] == brand_name]
    sort = request.args.get("sort", "newest").strip()
    filtered = _sort_phones(filtered, sort)
    return render_template("comparison-aggregators/brand.html",
                           phones=filtered, brand_name=brand_name,
                           brands=_get_brands(), sort=sort)


@blueprint.route("/compare")
def compare_page():
    ids_str = request.args.get("ids", "")
    phones = _get_phones()
    selected = []
    if ids_str:
        ids = [int(x) for x in ids_str.split(",") if x.strip().isdigit()]
        selected = [p for p in phones if p["id"] in ids]
        # Preserve the order requested
        id_order = {pid: i for i, pid in enumerate(ids)}
        selected.sort(key=lambda p: id_order.get(p["id"], 999))
    return render_template("comparison-aggregators/compare.html",
                           phones=phones, selected=selected)


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
    phones = _get_phones()
    fav_phones = [p for p in phones if p["id"] in user.get("favorites", [])]
    compare_phones = [p for p in phones if p["id"] in user.get("compare_lists", [])]
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
    phones = _get_phones()
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

    results = list(phones)
    if q:
        results = _search_phones(results, q)
    results = _filter_phones(results, brand=brand or None,
                             os_family=os_fam or None,
                             price_min=price_min, price_max=price_max,
                             battery_min=battery_min,
                             year_from=year_from, year_to=year_to)
    results = _sort_phones(results, sort)
    if limit:
        results = results[:limit]
    return jsonify(results)


@blueprint.route("/api/phones/<int:phone_id>")
def api_phone(phone_id):
    phones = _get_phones()
    phone = next((p for p in phones if p["id"] == phone_id), None)
    if phone is None:
        abort(404)
    return jsonify(phone)


@blueprint.route("/api/brands")
def api_brands():
    phones = _get_phones()
    counts = Counter(p["brand"] for p in phones)
    return jsonify([{"name": b, "count": c} for b, c in sorted(counts.items())])


@blueprint.route("/api/brands/<path:brand_name>/phones")
def api_brand_phones(brand_name):
    phones = _get_phones()
    sort = request.args.get("sort", "newest").strip()
    filtered = [p for p in phones if p["brand"] == brand_name]
    filtered = _sort_phones(filtered, sort)
    return jsonify(filtered)


@blueprint.route("/api/compare")
def api_compare():
    ids_str = request.args.get("ids", "")
    ids = [int(x) for x in ids_str.split(",") if x.strip().isdigit()]
    phones = _get_phones()
    selected = [p for p in phones if p["id"] in ids]
    id_order = {pid: i for i, pid in enumerate(ids)}
    selected.sort(key=lambda p: id_order.get(p["id"], 999))
    return jsonify(selected)


@blueprint.route("/api/stats")
def api_stats():
    phones = _get_phones()
    brand = request.args.get("brand", "").strip()
    if brand:
        phones = [p for p in phones if p["brand"] == brand]
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
