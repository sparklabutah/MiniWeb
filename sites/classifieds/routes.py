"""Classifieds — KSL/Craigslist-style classified ads platform.

Reads synthesized listing data from data/ directory, serves through Flask
routes. Supports browsing, searching, filtering, sorting, CRUD operations
on listings, messaging between users, and reporting.
"""
import json
import pathlib
from collections import Counter
from datetime import datetime

from flask import (
    Blueprint, Response, abort, jsonify, render_template, request, session,
)

SITE_DIR = pathlib.Path(__file__).resolve().parent
LISTINGS_FILE = SITE_DIR / "data" / "listings.json"
USERS_FILE = SITE_DIR / "data" / "users.json"
MESSAGES_FILE = SITE_DIR / "data" / "messages.json"
REPORTS_FILE = SITE_DIR / "data" / "reports.json"
CONFIG_FILE = SITE_DIR / "config" / "config.json"

blueprint = Blueprint(
    "classifieds",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)

# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def _load_json(path):
    if path.exists():
        return json.loads(path.read_text())
    return []


def _save_json(path, data):
    path.write_text(json.dumps(data, indent=2))


_listings_cache = None
_categories = ["vehicles", "electronics", "furniture", "housing", "jobs", "services"]
_conditions = ["new", "like_new", "used"]


def _load_listings():
    global _listings_cache
    if _listings_cache is None:
        config = _load_config()
        all_listings = _load_json(LISTINGS_FILE)
        n = config.get("num_data_points", -1)
        if n > 0:
            all_listings = all_listings[:n]
        _listings_cache = all_listings
    return _listings_cache


def _reload_listings():
    global _listings_cache
    _listings_cache = None
    return _load_listings()


def _get_listings():
    return _load_listings()


def _load_users():
    return _load_json(USERS_FILE)


def _save_users(users):
    _save_json(USERS_FILE, users)


def _get_user(user_id):
    users = _load_users()
    return next((u for u in users if u["id"] == user_id), None)


def _load_messages():
    return _load_json(MESSAGES_FILE)


def _save_messages(messages):
    _save_json(MESSAGES_FILE, messages)


def _load_reports():
    return _load_json(REPORTS_FILE)


def _save_reports(reports):
    _save_json(REPORTS_FILE, reports)


# ---------------------------------------------------------------------------
# Search / filter helpers
# ---------------------------------------------------------------------------

def _keyword_score(query, listing):
    terms = query.lower().split()
    text = (listing["title"] + " " + listing["description"] + " " +
            listing["category"] + " " + listing.get("subcategory", "") + " " +
            listing.get("location", "")).lower()
    return sum(1 for t in terms if t in text)


def _search_listings(listings, query, semantic=False):
    if not query:
        return listings
    q = query.lower().strip()
    if semantic:
        scored = [(l, _keyword_score(q, l)) for l in listings]
        scored = [(l, s) for l, s in scored if s > 0]
        scored.sort(key=lambda x: -x[1])
        return [l for l, _ in scored]
    else:
        return [l for l in listings if q in l["title"].lower() or
                q in l["description"].lower() or
                q in l["category"].lower() or
                q in l.get("subcategory", "").lower() or
                q in l.get("location", "").lower()]


def _filter_listings(listings, category=None, subcategory=None, condition=None,
                     location=None, price_min=None, price_max=None,
                     status=None):
    result = list(listings)
    if category:
        result = [l for l in result if l["category"] == category]
    if subcategory:
        result = [l for l in result if l.get("subcategory") == subcategory]
    if condition:
        result = [l for l in result if l.get("condition") == condition]
    if location:
        result = [l for l in result if location.lower() in l.get("location", "").lower()]
    if price_min is not None:
        result = [l for l in result if l["price"] >= price_min]
    if price_max is not None:
        result = [l for l in result if l["price"] <= price_max]
    if status:
        result = [l for l in result if l.get("status") == status]
    return result


def _sort_listings(listings, sort_by="date"):
    if sort_by == "date":
        return sorted(listings, key=lambda l: l.get("date_posted", ""), reverse=True)
    elif sort_by == "price_low":
        return sorted(listings, key=lambda l: l["price"])
    elif sort_by == "price_high":
        return sorted(listings, key=lambda l: l["price"], reverse=True)
    elif sort_by == "title":
        return sorted(listings, key=lambda l: l["title"].lower())
    elif sort_by == "views":
        return sorted(listings, key=lambda l: l.get("views", 0), reverse=True)
    return listings


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    listings = _get_listings()
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    subcategory = request.args.get("subcategory", "").strip()
    condition = request.args.get("condition", "").strip()
    location = request.args.get("location", "").strip()
    price_min = request.args.get("price_min", type=int)
    price_max = request.args.get("price_max", type=int)
    sort = request.args.get("sort", "date").strip()

    results = [l for l in listings if l.get("status") == "active"]

    if q:
        results = _search_listings(results, q)

    results = _filter_listings(results, category=category or None,
                               subcategory=subcategory or None,
                               condition=condition or None,
                               location=location or None,
                               price_min=price_min, price_max=price_max)

    results = _sort_listings(results, sort)

    # Get all unique locations for filter
    locations = sorted(set(l.get("location", "") for l in listings if l.get("location")))
    # Get subcategories for selected category
    subcategories = []
    if category:
        subcategories = sorted(set(l.get("subcategory", "") for l in listings
                                   if l["category"] == category and l.get("subcategory")))

    # Featured listings
    featured = [l for l in listings if l.get("featured") and l.get("status") == "active"]

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template("classifieds/index.html",
                           listings=results, featured=featured,
                           categories=_categories, conditions=_conditions,
                           locations=locations, subcategories=subcategories,
                           q=q, category=category, subcategory=subcategory,
                           condition=condition, location=location,
                           price_min=price_min, price_max=price_max,
                           sort=sort, user=user)


@blueprint.route("/listing/<int:listing_id>")
def listing_detail(listing_id):
    listings = _get_listings()
    listing = next((l for l in listings if l["id"] == listing_id), None)
    if listing is None:
        abort(404)
    seller = _get_user(listing.get("seller_id"))
    related = [l for l in listings if l["category"] == listing["category"]
               and l["id"] != listing_id and l.get("status") == "active"][:6]
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("classifieds/listing.html", listing=listing,
                           seller=seller, related=related, user=user)


@blueprint.route("/category/<cat_name>")
def category_page(cat_name):
    listings = _get_listings()
    filtered = [l for l in listings if l["category"] == cat_name
                and l.get("status") == "active"]
    subcategories = sorted(set(l.get("subcategory", "") for l in filtered if l.get("subcategory")))
    sub = request.args.get("subcategory", "").strip()
    if sub:
        filtered = [l for l in filtered if l.get("subcategory") == sub]
    filtered = _sort_listings(filtered, request.args.get("sort", "date"))
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("classifieds/category.html",
                           listings=filtered, category=cat_name,
                           subcategories=subcategories,
                           categories=_categories, sub=sub, user=user)


@blueprint.route("/post", methods=["GET"])
def post_listing_page():
    if "user_id" not in session:
        return render_template("classifieds/login.html", error="Please log in to post a listing.", mode="login")
    user = _get_user(session["user_id"])
    return render_template("classifieds/post.html", user=user,
                           categories=_categories, conditions=_conditions)


@blueprint.route("/post", methods=["POST"])
def post_listing_submit():
    if "user_id" not in session:
        return render_template("classifieds/login.html", error="Please log in to post a listing.", mode="login")

    listings = list(_get_listings())
    new_id = max(l["id"] for l in listings) + 1 if listings else 1

    new_listing = {
        "id": new_id,
        "title": request.form.get("title", "").strip(),
        "description": request.form.get("description", "").strip(),
        "price": int(request.form.get("price", 0)),
        "category": request.form.get("category", "").strip(),
        "subcategory": request.form.get("subcategory", "").strip(),
        "condition": request.form.get("condition", "").strip(),
        "location": request.form.get("location", "").strip(),
        "seller_id": session["user_id"],
        "date_posted": datetime.now().strftime("%Y-%m-%d"),
        "status": "active",
        "featured": False,
        "views": 0,
    }

    listings.append(new_listing)
    _save_json(LISTINGS_FILE, listings)
    _reload_listings()

    user = _get_user(session["user_id"])
    return render_template("classifieds/listing.html", listing=new_listing,
                           seller=user, related=[], user=user,
                           message="Listing created successfully!")


@blueprint.route("/edit/<int:listing_id>", methods=["GET"])
def edit_listing_page(listing_id):
    if "user_id" not in session:
        return render_template("classifieds/login.html", error=None, mode="login")
    listings = _get_listings()
    listing = next((l for l in listings if l["id"] == listing_id), None)
    if not listing:
        abort(404)
    user = _get_user(session["user_id"])
    return render_template("classifieds/edit.html", listing=listing, user=user,
                           categories=_categories, conditions=_conditions)


@blueprint.route("/edit/<int:listing_id>", methods=["POST"])
def edit_listing_submit(listing_id):
    if "user_id" not in session:
        return render_template("classifieds/login.html", error=None, mode="login")

    listings = list(_get_listings())
    listing = next((l for l in listings if l["id"] == listing_id), None)
    if not listing:
        abort(404)

    listing["title"] = request.form.get("title", listing["title"]).strip()
    listing["description"] = request.form.get("description", listing["description"]).strip()
    listing["price"] = int(request.form.get("price", listing["price"]))
    listing["category"] = request.form.get("category", listing["category"]).strip()
    listing["subcategory"] = request.form.get("subcategory", listing.get("subcategory", "")).strip()
    listing["condition"] = request.form.get("condition", listing.get("condition", "")).strip()
    listing["location"] = request.form.get("location", listing.get("location", "")).strip()

    _save_json(LISTINGS_FILE, listings)
    _reload_listings()

    user = _get_user(session["user_id"])
    return render_template("classifieds/listing.html", listing=listing,
                           seller=user, related=[], user=user,
                           message="Listing updated successfully!")


@blueprint.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return render_template("classifieds/login.html", error=None, mode="login")
    user = _get_user(session["user_id"])
    if not user:
        return render_template("classifieds/login.html", error=None, mode="login")
    listings = _get_listings()
    my_listings = [l for l in listings if l.get("seller_id") == user["id"]]
    saved = [l for l in listings if l["id"] in user.get("saved_listings", [])]
    messages = _load_messages()
    my_messages = [m for m in messages if m["recipient_id"] == user["id"]]
    return render_template("classifieds/dashboard.html", user=user,
                           my_listings=my_listings, saved_listings=saved,
                           messages=my_messages, categories=_categories)


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("classifieds/login.html", error=None, mode="login")


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return render_template("classifieds/login.html",
                               error="Invalid username or password", mode="login")
    session["user_id"] = user["id"]
    listings = _get_listings()
    my_listings = [l for l in listings if l.get("seller_id") == user["id"]]
    saved = [l for l in listings if l["id"] in user.get("saved_listings", [])]
    messages = _load_messages()
    my_messages = [m for m in messages if m["recipient_id"] == user["id"]]
    return render_template("classifieds/dashboard.html", user=user,
                           my_listings=my_listings, saved_listings=saved,
                           messages=my_messages, categories=_categories)


@blueprint.route("/register", methods=["GET"])
def register_page():
    return render_template("classifieds/login.html", error=None, mode="register")


@blueprint.route("/register", methods=["POST"])
def register_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    location = request.form.get("location", "").strip()

    if not username or not password or not name or not email:
        return render_template("classifieds/login.html",
                               error="All fields are required", mode="register")

    users = _load_users()
    if any(u["username"] == username for u in users):
        return render_template("classifieds/login.html",
                               error="Username already taken", mode="register")

    new_id = max(u["id"] for u in users) + 1 if users else 1
    new_user = {
        "id": new_id,
        "username": username,
        "password": password,
        "name": name,
        "email": email,
        "phone": phone,
        "location": location,
        "member_since": datetime.now().strftime("%Y-%m-%d"),
        "rating": 0.0,
        "saved_listings": [],
        "role": "buyer",
    }
    users.append(new_user)
    _save_users(users)

    session["user_id"] = new_user["id"]
    return render_template("classifieds/dashboard.html", user=new_user,
                           my_listings=[], saved_listings=[],
                           messages=[], categories=_categories)


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return render_template("classifieds/login.html", error=None, mode="login")


@blueprint.route("/compare")
def compare_page():
    ids_str = request.args.get("ids", "")
    listings = _get_listings()
    selected = []
    if ids_str:
        ids = [int(x) for x in ids_str.split(",") if x.strip().isdigit()]
        selected = [l for l in listings if l["id"] in ids]
    return render_template("classifieds/compare.html", listings=listings,
                           selected=selected, categories=_categories)


@blueprint.route("/messages")
def messages_page():
    if "user_id" not in session:
        return render_template("classifieds/login.html", error=None, mode="login")
    user = _get_user(session["user_id"])
    messages = _load_messages()
    my_messages = [m for m in messages if m["recipient_id"] == user["id"]
                   or m["sender_id"] == user["id"]]
    return render_template("classifieds/messages.html", user=user,
                           messages=my_messages, categories=_categories)


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/listings")
def api_listings():
    listings = _get_listings()
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    subcategory = request.args.get("subcategory", "").strip()
    condition = request.args.get("condition", "").strip()
    location = request.args.get("location", "").strip()
    price_min = request.args.get("price_min", type=int)
    price_max = request.args.get("price_max", type=int)
    sort = request.args.get("sort", "date")
    status = request.args.get("status", "").strip()
    limit = request.args.get("limit", type=int)

    results = list(listings)
    if q:
        results = _search_listings(results, q)
    results = _filter_listings(results, category=category or None,
                               subcategory=subcategory or None,
                               condition=condition or None,
                               location=location or None,
                               price_min=price_min, price_max=price_max,
                               status=status or None)
    results = _sort_listings(results, sort)
    if limit:
        results = results[:limit]
    return jsonify(results)


@blueprint.route("/api/listings/<int:listing_id>")
def api_listing(listing_id):
    listings = _get_listings()
    listing = next((l for l in listings if l["id"] == listing_id), None)
    if listing is None:
        abort(404)
    return jsonify(listing)


@blueprint.route("/api/listings/search")
def api_search():
    q = request.args.get("q", "").strip()
    listings = _get_listings()
    return jsonify(_search_listings(listings, q))


@blueprint.route("/api/listings/semantic")
def api_semantic_search():
    q = request.args.get("q", "").strip()
    listings = _get_listings()
    return jsonify(_search_listings(listings, q, semantic=True))


@blueprint.route("/api/listings", methods=["POST"])
def api_create_listing():
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json(silent=True) or {}
    listings = list(_get_listings())
    new_id = max(l["id"] for l in listings) + 1 if listings else 1
    new_listing = {
        "id": new_id,
        "title": data.get("title", "").strip(),
        "description": data.get("description", "").strip(),
        "price": int(data.get("price", 0)),
        "category": data.get("category", "").strip(),
        "subcategory": data.get("subcategory", "").strip(),
        "condition": data.get("condition", "").strip(),
        "location": data.get("location", "").strip(),
        "seller_id": session["user_id"],
        "date_posted": datetime.now().strftime("%Y-%m-%d"),
        "status": "active",
        "featured": False,
        "views": 0,
    }
    listings.append(new_listing)
    _save_json(LISTINGS_FILE, listings)
    _reload_listings()
    return jsonify(new_listing), 201


@blueprint.route("/api/listings/<int:listing_id>", methods=["PUT"])
def api_update_listing(listing_id):
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json(silent=True) or {}
    listings = list(_get_listings())
    listing = next((l for l in listings if l["id"] == listing_id), None)
    if not listing:
        abort(404)
    for key in ["title", "description", "price", "category", "subcategory",
                "condition", "location", "status"]:
        if key in data:
            listing[key] = data[key]
    _save_json(LISTINGS_FILE, listings)
    _reload_listings()
    return jsonify(listing)


@blueprint.route("/api/listings/<int:listing_id>", methods=["DELETE"])
def api_delete_listing(listing_id):
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    listings = list(_get_listings())
    listing = next((l for l in listings if l["id"] == listing_id), None)
    if not listing:
        abort(404)
    listing["status"] = "deleted"
    _save_json(LISTINGS_FILE, listings)
    _reload_listings()
    return jsonify({"action": "deleted", "listing_id": listing_id})


@blueprint.route("/api/categories")
def api_categories():
    listings = _get_listings()
    counts = Counter(l["category"] for l in listings if l.get("status") == "active")
    return jsonify([{"name": c, "count": counts.get(c, 0)} for c in _categories])


@blueprint.route("/api/categories/<cat_name>/listings")
def api_category_listings(cat_name):
    listings = _get_listings()
    return jsonify([l for l in listings if l["category"] == cat_name
                    and l.get("status") == "active"])


@blueprint.route("/api/categories/<cat_name>/stats")
def api_category_stats(cat_name):
    listings = _get_listings()
    filtered = [l for l in listings if l["category"] == cat_name
                and l.get("status") == "active"]
    if not filtered:
        return jsonify({"category": cat_name, "count": 0})
    prices = [l["price"] for l in filtered]
    locations = set(l.get("location", "") for l in filtered)
    subcats = Counter(l.get("subcategory", "") for l in filtered)
    return jsonify({
        "category": cat_name,
        "count": len(filtered),
        "avg_price": round(sum(prices) / len(prices), 2),
        "min_price": min(prices),
        "max_price": max(prices),
        "unique_locations": len(locations),
        "subcategories": dict(subcats),
    })


@blueprint.route("/api/stats")
def api_stats():
    listings = _get_listings()
    active = [l for l in listings if l.get("status") == "active"]
    category = request.args.get("category", "").strip()
    if category:
        active = [l for l in active if l["category"] == category]
    if not active:
        return jsonify({"count": 0})
    prices = [l["price"] for l in active]
    locations = set(l.get("location", "") for l in active)
    return jsonify({
        "count": len(active),
        "avg_price": round(sum(prices) / len(prices), 2),
        "min_price": min(prices),
        "max_price": max(prices),
        "unique_locations": len(locations),
        "categories": dict(Counter(l["category"] for l in active)),
        "total_views": sum(l.get("views", 0) for l in active),
    })


@blueprint.route("/api/compare")
def api_compare():
    ids_str = request.args.get("ids", "")
    ids = [int(x) for x in ids_str.split(",") if x.strip().isdigit()]
    listings = _get_listings()
    return jsonify([l for l in listings if l["id"] in ids])


@blueprint.route("/api/export")
def api_export():
    fmt = request.args.get("format", "json").lower()
    category = request.args.get("category", "").strip()
    listings = list(_get_listings())
    if category:
        listings = [l for l in listings if l["category"] == category]

    if fmt == "csv":
        lines = ["id,title,price,category,subcategory,condition,location,date_posted,status"]
        for l in listings:
            title = l["title"].replace('"', '""')
            loc = l.get("location", "").replace('"', '""')
            lines.append(
                f'{l["id"]},"{title}",{l["price"]},"{l["category"]}","{l.get("subcategory", "")}",'
                f'"{l.get("condition", "")}","{loc}","{l.get("date_posted", "")}","{l.get("status", "")}"'
            )
        return Response("\n".join(lines), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=listings.csv"})
    return jsonify(listings)


# ---------------------------------------------------------------------------
# User API routes
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


@blueprint.route("/api/register", methods=["POST"])
def api_register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()

    if not username or not password or not name or not email:
        return jsonify({"error": "All fields required"}), 400

    users = _load_users()
    if any(u["username"] == username for u in users):
        return jsonify({"error": "Username already taken"}), 409

    new_id = max(u["id"] for u in users) + 1 if users else 1
    new_user = {
        "id": new_id,
        "username": username,
        "password": password,
        "name": name,
        "email": email,
        "phone": data.get("phone", ""),
        "location": data.get("location", ""),
        "member_since": datetime.now().strftime("%Y-%m-%d"),
        "rating": 0.0,
        "saved_listings": [],
        "role": "buyer",
    }
    users.append(new_user)
    _save_users(users)
    session["user_id"] = new_user["id"]
    return jsonify({"user_id": new_user["id"], "username": new_user["username"]}), 201


@blueprint.route("/api/users/<int:user_id>")
def api_user(user_id):
    user = _get_user(user_id)
    if not user:
        abort(404)
    return jsonify({k: v for k, v in user.items() if k != "password"})


@blueprint.route("/api/users/<int:user_id>/save", methods=["POST"])
def api_save_listing(user_id):
    data = request.get_json(silent=True) or {}
    listing_id = data.get("listing_id")
    if listing_id is None:
        return jsonify({"error": "listing_id required"}), 400
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    saved = user.setdefault("saved_listings", [])
    if listing_id in saved:
        saved.remove(listing_id)
        action = "unsaved"
    else:
        saved.append(listing_id)
        action = "saved"
    _save_users(users)
    return jsonify({"action": action, "listing_id": listing_id, "total_saved": len(saved)})


@blueprint.route("/api/messages", methods=["GET"])
def api_messages():
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    messages = _load_messages()
    user_id = session["user_id"]
    my = [m for m in messages if m["recipient_id"] == user_id or m["sender_id"] == user_id]
    return jsonify(my)


@blueprint.route("/api/messages", methods=["POST"])
def api_send_message():
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json(silent=True) or {}
    messages = _load_messages()
    new_id = max(m["id"] for m in messages) + 1 if messages else 1
    new_msg = {
        "id": new_id,
        "listing_id": data.get("listing_id"),
        "sender_id": session["user_id"],
        "recipient_id": data.get("recipient_id"),
        "subject": data.get("subject", "").strip(),
        "body": data.get("body", "").strip(),
        "date_sent": datetime.now().isoformat(),
        "read": False,
    }
    messages.append(new_msg)
    _save_messages(messages)
    return jsonify(new_msg), 201


@blueprint.route("/api/reports", methods=["POST"])
def api_report():
    data = request.get_json(silent=True) or {}
    reports = _load_reports()
    new_id = max(r["id"] for r in reports) + 1 if reports else 1
    new_report = {
        "id": new_id,
        "listing_id": data.get("listing_id"),
        "reporter_id": data.get("reporter_id") or session.get("user_id"),
        "reason": data.get("reason", "").strip(),
        "description": data.get("description", "").strip(),
        "date_reported": datetime.now().isoformat(),
        "status": "pending",
    }
    reports.append(new_report)
    _save_reports(reports)
    return jsonify(new_report), 201


@blueprint.route("/api/reports")
def api_reports_list():
    reports = _load_reports()
    return jsonify(reports)


@blueprint.route("/api/upload", methods=["POST"])
def api_upload():
    """Handle image upload for listings. Accepts multipart form data."""
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    f = request.files["file"]
    if f.filename == "":
        return jsonify({"error": "No file selected"}), 400
    # In a real app we'd save the file; here we just acknowledge it
    listing_id = request.form.get("listing_id", "")
    return jsonify({
        "action": "uploaded",
        "filename": f.filename,
        "listing_id": listing_id,
        "size": f.content_length or 0,
    })
