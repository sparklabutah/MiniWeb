"""Auctions & P2P Marketplaces — eBay-style auction platform.

Data interpreter: reads generated JSON data files (products, users, bids,
messages, etc.) and serves through Flask routes. Products are adapted from
WebShop data format into auction listings. Config controls sampling.
"""
import json
import pathlib
import random
import re
from collections import Counter

from flask import Blueprint, Response, abort, jsonify, redirect, render_template, request, session, url_for

SITE_DIR = pathlib.Path(__file__).resolve().parent
CONFIG_FILE = SITE_DIR / "config" / "config.json"
DATA_DIR = SITE_DIR / "data"
PRODUCTS_FILE = DATA_DIR / "products.json"
USERS_FILE = DATA_DIR / "users.json"
BIDS_FILE = DATA_DIR / "bids.json"
MESSAGES_FILE = DATA_DIR / "messages.json"
REPORTS_FILE = DATA_DIR / "reports.json"
RATINGS_FILE = DATA_DIR / "ratings.json"
WATCHLIST_FILE = DATA_DIR / "watchlist.json"

blueprint = Blueprint(
    "auctions-p2p-marketplaces",
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
# Data loading
# ---------------------------------------------------------------------------

_products = None
_categories = None


def _load_json(path):
    if path.exists():
        return json.loads(path.read_text())
    return []


def _save_json(path, data):
    path.write_text(json.dumps(data, indent=2))


def _load_products():
    config = _load_config()
    n = config.get("num_data_points", -1)
    seed = config.get("random_seed", 42)
    products = _load_json(PRODUCTS_FILE)

    if n > 0 and n < len(products):
        rng = random.Random(seed)
        products = rng.sample(products, n)
        # Re-assign IDs
        for i, p in enumerate(products, 1):
            p["id"] = i

    return products


def _ensure_loaded():
    global _products, _categories
    if _products is None:
        _products = _load_products()
        _categories = sorted(set(p["category"] for p in _products))


def _get_products():
    _ensure_loaded()
    return _products


def _get_categories():
    _ensure_loaded()
    return _categories


# ---------------------------------------------------------------------------
# Users (mutable)
# ---------------------------------------------------------------------------

def _load_users():
    return _load_json(USERS_FILE)


def _save_users(users):
    _save_json(USERS_FILE, users)


def _get_user(user_id):
    users = _load_users()
    return next((u for u in users if u["id"] == user_id), None)


# ---------------------------------------------------------------------------
# Bids (mutable)
# ---------------------------------------------------------------------------

def _load_bids():
    return _load_json(BIDS_FILE)


def _save_bids(bids):
    _save_json(BIDS_FILE, bids)


# ---------------------------------------------------------------------------
# Messages (mutable)
# ---------------------------------------------------------------------------

def _load_messages():
    return _load_json(MESSAGES_FILE)


def _save_messages(messages):
    _save_json(MESSAGES_FILE, messages)


# ---------------------------------------------------------------------------
# Reports (mutable)
# ---------------------------------------------------------------------------

def _load_reports():
    return _load_json(REPORTS_FILE)


def _save_reports(reports):
    _save_json(REPORTS_FILE, reports)


# ---------------------------------------------------------------------------
# Ratings (mutable)
# ---------------------------------------------------------------------------

def _load_ratings():
    return _load_json(RATINGS_FILE)


def _save_ratings(ratings):
    _save_json(RATINGS_FILE, ratings)


# ---------------------------------------------------------------------------
# Watchlist (mutable)
# ---------------------------------------------------------------------------

def _load_watchlist():
    return _load_json(WATCHLIST_FILE)


def _save_watchlist(watchlist):
    _save_json(WATCHLIST_FILE, watchlist)


# ---------------------------------------------------------------------------
# Search / filter helpers
# ---------------------------------------------------------------------------

def _keyword_score(query, product):
    terms = query.lower().split()
    text = (product["name"] + " " + product.get("description", "") + " " +
            product["category"] + " " + product.get("brand", "")).lower()
    return sum(1 for t in terms if t in text)


def _search_products(products, query, semantic=False):
    if not query:
        return products
    q = query.lower().strip()
    if semantic:
        scored = [(p, _keyword_score(q, p)) for p in products]
        scored = [(p, s) for p, s in scored if s > 0]
        scored.sort(key=lambda x: -x[1])
        return [p for p, _ in scored]
    else:
        return [p for p in products if q in p["name"].lower() or
                q in p.get("description", "").lower() or
                q in p["category"].lower() or
                q in p.get("brand", "").lower()]


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    products = _get_products()
    categories = _get_categories()
    q = request.args.get("q", "").strip()
    cat = request.args.get("category", "").strip()
    status = request.args.get("status", "").strip()
    condition = request.args.get("condition", "").strip()
    sort = request.args.get("sort", "ending_soon").strip()
    min_price = request.args.get("min_price", "").strip()
    max_price = request.args.get("max_price", "").strip()

    results = list(products)

    if q:
        results = _search_products(results, q)
    if cat:
        results = [p for p in results if p["category"] == cat]
    if status:
        results = [p for p in results if p["status"] == status]
    if condition:
        results = [p for p in results if p["condition"] == condition]
    if min_price:
        try:
            min_p = float(min_price)
            results = [p for p in results if p["current_price"] >= min_p]
        except ValueError:
            pass
    if max_price:
        try:
            max_p = float(max_price)
            results = [p for p in results if p["current_price"] <= max_p]
        except ValueError:
            pass

    if sort == "ending_soon":
        results.sort(key=lambda p: p["auction_end"])
    elif sort == "price_low":
        results.sort(key=lambda p: p["current_price"])
    elif sort == "price_high":
        results.sort(key=lambda p: -p["current_price"])
    elif sort == "most_bids":
        results.sort(key=lambda p: -p["num_bids"])
    elif sort == "newest":
        results.sort(key=lambda p: p["auction_start"], reverse=True)
    elif sort == "relevance" and q:
        results.sort(key=lambda p: -_keyword_score(q, p))

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    conditions = sorted(set(p["condition"] for p in _get_products()))

    return render_template("auctions-p2p-marketplaces/index.html",
                           products=results, categories=categories,
                           conditions=conditions,
                           q=q, cat=cat, status=status, condition_filter=condition,
                           sort=sort, min_price=min_price, max_price=max_price,
                           user=user)


@blueprint.route("/listing/<int:listing_id>")
def listing_detail(listing_id):
    products = _get_products()
    product = next((p for p in products if p["id"] == listing_id), None)
    if product is None:
        abort(404)
    bids = _load_bids()
    listing_bids = [b for b in bids if b["listing_id"] == listing_id]
    listing_bids.sort(key=lambda b: b["amount"], reverse=True)
    related = [p for p in products if p["category"] == product["category"]
               and p["id"] != listing_id][:6]
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    seller = _get_user(product["seller_id"])
    ratings = _load_ratings()
    seller_ratings = [r for r in ratings if r["rated_user_id"] == product["seller_id"]]
    return render_template("auctions-p2p-marketplaces/listing.html",
                           product=product, bids=listing_bids, related=related,
                           user=user, seller=seller, seller_ratings=seller_ratings)


@blueprint.route("/category/<path:cat_name>")
def category_page(cat_name):
    products = _get_products()
    filtered = [p for p in products if p["category"] == cat_name]
    sort = request.args.get("sort", "ending_soon")
    if sort == "ending_soon":
        filtered.sort(key=lambda p: p["auction_end"])
    elif sort == "price_low":
        filtered.sort(key=lambda p: p["current_price"])
    elif sort == "price_high":
        filtered.sort(key=lambda p: -p["current_price"])
    elif sort == "most_bids":
        filtered.sort(key=lambda p: -p["num_bids"])
    return render_template("auctions-p2p-marketplaces/category.html",
                           products=filtered, category=cat_name,
                           categories=_get_categories(), sort=sort)


@blueprint.route("/seller/<int:seller_id>")
def seller_page(seller_id):
    seller = _get_user(seller_id)
    if not seller:
        abort(404)
    products = _get_products()
    listings = [p for p in products if p["seller_id"] == seller_id]
    ratings = _load_ratings()
    seller_ratings = [r for r in ratings if r["rated_user_id"] == seller_id]
    return render_template("auctions-p2p-marketplaces/seller.html",
                           seller=seller, listings=listings,
                           ratings=seller_ratings)


@blueprint.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return render_template("auctions-p2p-marketplaces/login.html", error=None, mode="login")
    user = _get_user(session["user_id"])
    if not user:
        return render_template("auctions-p2p-marketplaces/login.html", error=None, mode="login")
    products = _get_products()
    bids = _load_bids()
    messages = _load_messages()

    # Items user is selling
    my_listings = [p for p in products if p["seller_id"] == user["id"]]
    # Items user has bid on
    my_bid_listing_ids = list(set(b["listing_id"] for b in bids if b["bidder_id"] == user["id"]))
    my_bids = [p for p in products if p["id"] in my_bid_listing_ids]
    # Watchlist
    watchlist = _load_watchlist()
    my_watchlist_ids = [w["listing_id"] for w in watchlist if w["user_id"] == user["id"]]
    watched = [p for p in products if p["id"] in my_watchlist_ids]
    # Messages
    my_messages = [m for m in messages if m["sender_id"] == user["id"] or m["receiver_id"] == user["id"]]

    return render_template("auctions-p2p-marketplaces/dashboard.html",
                           user=user, my_listings=my_listings, my_bids=my_bids,
                           watched=watched, messages=my_messages)


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("auctions-p2p-marketplaces/login.html", error=None, mode="login")


@blueprint.route("/register", methods=["GET"])
def register_page():
    return render_template("auctions-p2p-marketplaces/login.html", error=None, mode="register")


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return render_template("auctions-p2p-marketplaces/login.html",
                               error="Invalid username or password", mode="login")
    session["user_id"] = user["id"]
    return redirect(url_for("auctions-p2p-marketplaces.dashboard"))


@blueprint.route("/register", methods=["POST"])
def register_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    email = request.form.get("email", "").strip()
    name = request.form.get("name", "").strip()
    if not username or not password or not email:
        return render_template("auctions-p2p-marketplaces/login.html",
                               error="All fields are required", mode="register")
    users = _load_users()
    if any(u["username"] == username for u in users):
        return render_template("auctions-p2p-marketplaces/login.html",
                               error="Username already taken", mode="register")
    new_id = max(u["id"] for u in users) + 1 if users else 1
    new_user = {
        "id": new_id,
        "username": username,
        "password": password,
        "name": name or username,
        "email": email,
        "role": "buyer",
        "location": "",
        "rating": 0.0,
        "total_purchases": 0,
        "member_since": "2026-06",
        "saved_listings": [],
        "watchlist": [],
        "followed_sellers": [],
    }
    users.append(new_user)
    _save_users(users)
    session["user_id"] = new_id
    return redirect(url_for("auctions-p2p-marketplaces.dashboard"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("auctions-p2p-marketplaces.login_page"))


@blueprint.route("/compare")
def compare_page():
    ids_str = request.args.get("ids", "")
    products = _get_products()
    selected = []
    if ids_str:
        ids = [int(x) for x in ids_str.split(",") if x.strip().isdigit()]
        selected = [p for p in products if p["id"] in ids]
    return render_template("auctions-p2p-marketplaces/compare.html",
                           products=products, selected=selected)


@blueprint.route("/create-listing", methods=["GET"])
def create_listing_page():
    if "user_id" not in session:
        return render_template("auctions-p2p-marketplaces/login.html", error=None, mode="login")
    user = _get_user(session["user_id"])
    return render_template("auctions-p2p-marketplaces/create_listing.html",
                           user=user, categories=_get_categories())


@blueprint.route("/create-listing", methods=["POST"])
def create_listing_submit():
    if "user_id" not in session:
        return redirect(url_for("auctions-p2p-marketplaces.login_page"))
    user = _get_user(session["user_id"])
    name = request.form.get("name", "").strip()
    category = request.form.get("category", "").strip()
    description = request.form.get("description", "").strip()
    start_price = request.form.get("start_price", "0")
    condition = request.form.get("condition", "Good")

    if not name:
        return render_template("auctions-p2p-marketplaces/create_listing.html",
                               user=user, categories=_get_categories(),
                               error="Listing name is required")

    products = _load_json(PRODUCTS_FILE)
    new_id = max(p["id"] for p in products) + 1 if products else 1

    new_product = {
        "id": new_id,
        "asin": f"B{new_id:09d}",
        "name": name,
        "category": category or "Electronics",
        "brand": request.form.get("brand", "").strip() or "Unbranded",
        "condition": condition,
        "description": description,
        "start_price": float(start_price),
        "current_price": float(start_price),
        "buy_now_price": None,
        "reserve_price": None,
        "num_bids": 0,
        "seller_id": user["id"],
        "seller_username": user["username"],
        "seller_rating": user.get("rating", 0),
        "auction_start": "2026-06-21T12:00:00Z",
        "auction_end": "2026-06-28T12:00:00Z",
        "status": "active",
        "winner_id": None,
        "shipping": request.form.get("shipping", "Free Shipping"),
        "location": user.get("location", ""),
        "views": 0,
        "watchers": 0,
        "color_options": [],
        "size_options": [],
        "return_policy": "30-day returns",
        "payment_methods": ["Credit Card", "PayPal"],
    }
    products.append(new_product)
    _save_json(PRODUCTS_FILE, products)

    # Invalidate cache
    global _products, _categories
    _products = None
    _categories = None

    return redirect(url_for("auctions-p2p-marketplaces.listing_detail", listing_id=new_id))


@blueprint.route("/edit-listing/<int:listing_id>", methods=["GET"])
def edit_listing_page(listing_id):
    if "user_id" not in session:
        return render_template("auctions-p2p-marketplaces/login.html", error=None, mode="login")
    products = _get_products()
    product = next((p for p in products if p["id"] == listing_id), None)
    if not product:
        abort(404)
    user = _get_user(session["user_id"])
    return render_template("auctions-p2p-marketplaces/edit_listing.html",
                           user=user, product=product, categories=_get_categories())


# ---------------------------------------------------------------------------
# Form-based POST routes (for browser automation compatibility)
# ---------------------------------------------------------------------------

@blueprint.route("/listing/<int:listing_id>/bid", methods=["POST"])
def place_bid_form(listing_id):
    if "user_id" not in session:
        return redirect(url_for("auctions-p2p-marketplaces.login_page"))
    user_id = session["user_id"]
    amount = request.form.get("amount", "")
    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return redirect(url_for("auctions-p2p-marketplaces.listing_detail", listing_id=listing_id))

    products = _load_json(PRODUCTS_FILE)
    product = next((p for p in products if p["id"] == listing_id), None)
    if not product or product["status"] != "active" or amount <= product["current_price"]:
        return redirect(url_for("auctions-p2p-marketplaces.listing_detail", listing_id=listing_id))

    bids = _load_bids()
    new_bid_id = max((b["bid_id"] for b in bids), default=0) + 1
    bids.append({
        "bid_id": new_bid_id,
        "listing_id": listing_id,
        "bidder_id": user_id,
        "amount": amount,
        "timestamp": "2026-06-21T12:00:00Z",
        "auto_bid": False,
    })
    _save_bids(bids)

    product["current_price"] = amount
    product["num_bids"] += 1
    _save_json(PRODUCTS_FILE, products)

    global _products, _categories
    _products = None
    _categories = None

    return redirect(url_for("auctions-p2p-marketplaces.listing_detail", listing_id=listing_id))


@blueprint.route("/edit-listing/<int:listing_id>", methods=["POST"])
def edit_listing_submit(listing_id):
    if "user_id" not in session:
        return redirect(url_for("auctions-p2p-marketplaces.login_page"))

    products = _load_json(PRODUCTS_FILE)
    product = next((p for p in products if p["id"] == listing_id), None)
    if not product:
        abort(404)

    for field in ["name", "description", "category", "condition", "shipping", "location"]:
        val = request.form.get(field)
        if val is not None:
            product[field] = val.strip()

    _save_json(PRODUCTS_FILE, products)

    global _products, _categories
    _products = None
    _categories = None

    return redirect(url_for("auctions-p2p-marketplaces.listing_detail", listing_id=listing_id))


@blueprint.route("/listing/<int:listing_id>/delete", methods=["POST"])
def delete_listing_form(listing_id):
    if "user_id" not in session:
        return redirect(url_for("auctions-p2p-marketplaces.login_page"))

    products = _load_json(PRODUCTS_FILE)
    product = next((p for p in products if p["id"] == listing_id), None)
    if product:
        products.remove(product)
        _save_json(PRODUCTS_FILE, products)

        global _products, _categories
        _products = None
        _categories = None

    return redirect(url_for("auctions-p2p-marketplaces.dashboard"))


@blueprint.route("/listing/<int:listing_id>/watch", methods=["POST"])
def watch_listing_form(listing_id):
    if "user_id" not in session:
        return redirect(url_for("auctions-p2p-marketplaces.login_page"))
    user_id = session["user_id"]
    watchlist = _load_watchlist()
    existing = next((w for w in watchlist if w["user_id"] == user_id and w["listing_id"] == listing_id), None)
    if existing:
        watchlist.remove(existing)
    else:
        watchlist.append({"user_id": user_id, "listing_id": listing_id})
    _save_watchlist(watchlist)
    return redirect(url_for("auctions-p2p-marketplaces.listing_detail", listing_id=listing_id))


@blueprint.route("/listing/<int:listing_id>/save", methods=["POST"])
def save_listing_form(listing_id):
    if "user_id" not in session:
        return redirect(url_for("auctions-p2p-marketplaces.login_page"))
    user_id = session["user_id"]
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if user:
        saved = user.setdefault("saved_listings", [])
        if listing_id in saved:
            saved.remove(listing_id)
        else:
            saved.append(listing_id)
        _save_users(users)
    return redirect(url_for("auctions-p2p-marketplaces.listing_detail", listing_id=listing_id))


@blueprint.route("/seller/<int:seller_id>/follow", methods=["POST"])
def follow_seller_form(seller_id):
    if "user_id" not in session:
        return redirect(url_for("auctions-p2p-marketplaces.login_page"))
    user_id = session["user_id"]
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if user:
        followed = user.setdefault("followed_sellers", [])
        if seller_id in followed:
            followed.remove(seller_id)
        else:
            followed.append(seller_id)
        _save_users(users)
    # Redirect back to the listing page if we came from one, otherwise seller page
    referer = request.form.get("next") or request.referrer
    if referer:
        return redirect(referer)
    return redirect(url_for("auctions-p2p-marketplaces.seller_page", seller_id=seller_id))


@blueprint.route("/send-message", methods=["POST"])
def send_message_form():
    if "user_id" not in session:
        return redirect(url_for("auctions-p2p-marketplaces.login_page"))
    sender_id = session["user_id"]
    receiver_id = request.form.get("receiver_id", type=int)
    listing_id = request.form.get("listing_id", type=int)
    subject = request.form.get("subject", "").strip()
    body = request.form.get("body", "").strip()

    if body and receiver_id:
        messages = _load_messages()
        new_id = max((m["id"] for m in messages), default=0) + 1
        messages.append({
            "id": new_id,
            "listing_id": listing_id,
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "subject": subject or "No subject",
            "body": body,
            "timestamp": "2026-06-21T12:00:00Z",
            "read": False,
        })
        _save_messages(messages)

    next_url = request.form.get("next") or request.referrer
    if next_url:
        return redirect(next_url)
    return redirect(url_for("auctions-p2p-marketplaces.dashboard"))


@blueprint.route("/message/<int:msg_id>/delete", methods=["POST"])
def delete_message_form(msg_id):
    if "user_id" not in session:
        return redirect(url_for("auctions-p2p-marketplaces.login_page"))
    messages = _load_messages()
    msg = next((m for m in messages if m["id"] == msg_id), None)
    if msg:
        messages.remove(msg)
        _save_messages(messages)
    return redirect(url_for("auctions-p2p-marketplaces.dashboard"))


@blueprint.route("/listing/<int:listing_id>/report", methods=["POST"])
def report_listing_form(listing_id):
    if "user_id" not in session:
        return redirect(url_for("auctions-p2p-marketplaces.login_page"))
    reason = request.form.get("reason", "").strip()
    description = request.form.get("description", "").strip()
    if reason:
        reports = _load_reports()
        new_id = max((r["id"] for r in reports), default=0) + 1
        reports.append({
            "id": new_id,
            "listing_id": listing_id,
            "reporter_id": session["user_id"],
            "reason": reason,
            "description": description,
            "timestamp": "2026-06-21T12:00:00Z",
            "status": "pending",
        })
        _save_reports(reports)
    return redirect(url_for("auctions-p2p-marketplaces.listing_detail", listing_id=listing_id))


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/listings")
def api_listings():
    products = _get_products()
    q = request.args.get("q", "").strip()
    cat = request.args.get("category", "").strip()
    status = request.args.get("status", "").strip()
    condition = request.args.get("condition", "").strip()
    sort = request.args.get("sort", "ending_soon")
    min_price = request.args.get("min_price", type=float)
    max_price = request.args.get("max_price", type=float)
    limit = request.args.get("limit", type=int)

    results = list(products)
    if q:
        results = _search_products(results, q)
    if cat:
        results = [p for p in results if p["category"] == cat]
    if status:
        results = [p for p in results if p["status"] == status]
    if condition:
        results = [p for p in results if p["condition"] == condition]
    if min_price is not None:
        results = [p for p in results if p["current_price"] >= min_price]
    if max_price is not None:
        results = [p for p in results if p["current_price"] <= max_price]

    if sort == "ending_soon":
        results.sort(key=lambda p: p["auction_end"])
    elif sort == "price_low":
        results.sort(key=lambda p: p["current_price"])
    elif sort == "price_high":
        results.sort(key=lambda p: -p["current_price"])
    elif sort == "most_bids":
        results.sort(key=lambda p: -p["num_bids"])
    elif sort == "newest":
        results.sort(key=lambda p: p["auction_start"], reverse=True)
    elif sort == "relevance" and q:
        results.sort(key=lambda p: -_keyword_score(q, p))

    if limit:
        results = results[:limit]
    return jsonify(results)


@blueprint.route("/api/listings/<int:listing_id>")
def api_listing(listing_id):
    products = _get_products()
    product = next((p for p in products if p["id"] == listing_id), None)
    if product is None:
        abort(404)
    return jsonify(product)


@blueprint.route("/api/listings/search")
def api_search():
    q = request.args.get("q", "").strip()
    products = _get_products()
    return jsonify(_search_products(products, q))


@blueprint.route("/api/listings/semantic")
def api_semantic_search():
    q = request.args.get("q", "").strip()
    products = _get_products()
    return jsonify(_search_products(products, q, semantic=True))


@blueprint.route("/api/categories")
def api_categories():
    products = _get_products()
    counts = Counter(p["category"] for p in products)
    return jsonify([{"name": c, "count": n} for c, n in sorted(counts.items())])


@blueprint.route("/api/categories/<path:cat_name>/listings")
def api_category_listings(cat_name):
    products = _get_products()
    return jsonify([p for p in products if p["category"] == cat_name])


@blueprint.route("/api/categories/<path:cat_name>/stats")
def api_category_stats(cat_name):
    products = _get_products()
    filtered = [p for p in products if p["category"] == cat_name]
    if not filtered:
        return jsonify({"category": cat_name, "count": 0})
    prices = [p["current_price"] for p in filtered]
    return jsonify({
        "category": cat_name,
        "count": len(filtered),
        "avg_price": round(sum(prices) / len(prices), 2),
        "min_price": min(prices),
        "max_price": max(prices),
        "total_bids": sum(p["num_bids"] for p in filtered),
        "active_count": sum(1 for p in filtered if p["status"] == "active"),
        "ended_count": sum(1 for p in filtered if p["status"] == "ended"),
    })


@blueprint.route("/api/stats")
def api_stats():
    products = _get_products()
    cat = request.args.get("category", "").strip()
    if cat:
        products = [p for p in products if p["category"] == cat]
    if not products:
        return jsonify({"count": 0})
    prices = [p["current_price"] for p in products]
    return jsonify({
        "count": len(products),
        "total_bids": sum(p["num_bids"] for p in products),
        "avg_price": round(sum(prices) / len(prices), 2),
        "active_listings": sum(1 for p in products if p["status"] == "active"),
        "ended_listings": sum(1 for p in products if p["status"] == "ended"),
        "categories": dict(Counter(p["category"] for p in products).most_common(12)),
        "unique_sellers": len(set(p["seller_id"] for p in products)),
    })


@blueprint.route("/api/compare")
def api_compare():
    ids_str = request.args.get("ids", "")
    ids = [int(x) for x in ids_str.split(",") if x.strip().isdigit()]
    products = _get_products()
    return jsonify([p for p in products if p["id"] in ids])


@blueprint.route("/api/export")
def api_export():
    fmt = request.args.get("format", "json").lower()
    cat = request.args.get("category", "").strip()
    products = list(_get_products())
    if cat:
        products = [p for p in products if p["category"] == cat]

    if fmt == "csv":
        lines = ["id,name,category,brand,condition,current_price,num_bids,status,seller"]
        for p in products:
            name = p["name"].replace('"', '""')
            brand = p.get("brand", "").replace('"', '""')
            lines.append(f'{p["id"]},"{name}","{p["category"]}","{brand}","{p["condition"]}",{p["current_price"]},{p["num_bids"]},"{p["status"]}","{p["seller_username"]}"')
        return Response("\n".join(lines), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=listings.csv"})
    return jsonify(products)


# ---------------------------------------------------------------------------
# Bid API
# ---------------------------------------------------------------------------

@blueprint.route("/api/listings/<int:listing_id>/bids")
def api_listing_bids(listing_id):
    bids = _load_bids()
    listing_bids = [b for b in bids if b["listing_id"] == listing_id]
    listing_bids.sort(key=lambda b: -b["amount"])
    return jsonify(listing_bids)


@blueprint.route("/api/listings/<int:listing_id>/bid", methods=["POST"])
def api_place_bid(listing_id):
    data = request.get_json(silent=True) or {}
    amount = data.get("amount")
    bidder_id = data.get("bidder_id")
    if amount is None or bidder_id is None:
        return jsonify({"error": "amount and bidder_id required"}), 400

    products = _load_json(PRODUCTS_FILE)
    product = next((p for p in products if p["id"] == listing_id), None)
    if not product:
        return jsonify({"error": "Listing not found"}), 404
    if product["status"] != "active":
        return jsonify({"error": "Auction is not active"}), 400
    if float(amount) <= product["current_price"]:
        return jsonify({"error": "Bid must be higher than current price"}), 400

    bids = _load_bids()
    new_bid_id = max((b["bid_id"] for b in bids), default=0) + 1
    new_bid = {
        "bid_id": new_bid_id,
        "listing_id": listing_id,
        "bidder_id": bidder_id,
        "amount": float(amount),
        "timestamp": "2026-06-21T12:00:00Z",
        "auto_bid": False,
    }
    bids.append(new_bid)
    _save_bids(bids)

    # Update product
    product["current_price"] = float(amount)
    product["num_bids"] += 1
    _save_json(PRODUCTS_FILE, products)

    # Invalidate cache
    global _products, _categories
    _products = None
    _categories = None

    return jsonify({"success": True, "bid_id": new_bid_id, "new_price": float(amount)})


# ---------------------------------------------------------------------------
# User API
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
    email = data.get("email", "").strip()
    name = data.get("name", "").strip()
    if not username or not password or not email:
        return jsonify({"error": "username, password, email required"}), 400
    users = _load_users()
    if any(u["username"] == username for u in users):
        return jsonify({"error": "Username already taken"}), 409
    new_id = max(u["id"] for u in users) + 1 if users else 1
    new_user = {
        "id": new_id,
        "username": username,
        "password": password,
        "name": name or username,
        "email": email,
        "role": "buyer",
        "location": "",
        "rating": 0.0,
        "total_purchases": 0,
        "member_since": "2026-06",
        "saved_listings": [],
        "watchlist": [],
        "followed_sellers": [],
    }
    users.append(new_user)
    _save_users(users)
    session["user_id"] = new_id
    return jsonify({"user_id": new_id, "username": username}), 201


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


@blueprint.route("/api/users/<int:user_id>/watch", methods=["POST"])
def api_watch_listing(user_id):
    data = request.get_json(silent=True) or {}
    listing_id = data.get("listing_id")
    if listing_id is None:
        return jsonify({"error": "listing_id required"}), 400
    watchlist = _load_watchlist()
    existing = next((w for w in watchlist if w["user_id"] == user_id and w["listing_id"] == listing_id), None)
    if existing:
        watchlist.remove(existing)
        action = "unwatched"
    else:
        watchlist.append({"user_id": user_id, "listing_id": listing_id})
        action = "watched"
    _save_watchlist(watchlist)
    return jsonify({"action": action, "listing_id": listing_id})


@blueprint.route("/api/users/<int:user_id>/follow", methods=["POST"])
def api_follow_seller(user_id):
    data = request.get_json(silent=True) or {}
    seller_id = data.get("seller_id")
    if seller_id is None:
        return jsonify({"error": "seller_id required"}), 400
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    followed = user.setdefault("followed_sellers", [])
    if seller_id in followed:
        followed.remove(seller_id)
        action = "unfollowed"
    else:
        followed.append(seller_id)
        action = "followed"
    _save_users(users)
    return jsonify({"action": action, "seller_id": seller_id, "total_followed": len(followed)})


# ---------------------------------------------------------------------------
# Message API
# ---------------------------------------------------------------------------

@blueprint.route("/api/messages")
def api_messages():
    user_id = request.args.get("user_id", type=int)
    messages = _load_messages()
    if user_id:
        messages = [m for m in messages if m["sender_id"] == user_id or m["receiver_id"] == user_id]
    return jsonify(messages)


@blueprint.route("/api/messages", methods=["POST"])
def api_send_message():
    data = request.get_json(silent=True) or {}
    sender_id = data.get("sender_id")
    receiver_id = data.get("receiver_id")
    listing_id = data.get("listing_id")
    subject = data.get("subject", "").strip()
    body = data.get("body", "").strip()
    if not sender_id or not body:
        return jsonify({"error": "sender_id and body required"}), 400
    messages = _load_messages()
    new_id = max((m["id"] for m in messages), default=0) + 1
    new_msg = {
        "id": new_id,
        "listing_id": listing_id,
        "sender_id": sender_id,
        "receiver_id": receiver_id,
        "subject": subject or "No subject",
        "body": body,
        "timestamp": "2026-06-21T12:00:00Z",
        "read": False,
    }
    messages.append(new_msg)
    _save_messages(messages)
    return jsonify({"success": True, "message_id": new_id})


@blueprint.route("/api/messages/<int:msg_id>", methods=["DELETE"])
def api_delete_message(msg_id):
    messages = _load_messages()
    msg = next((m for m in messages if m["id"] == msg_id), None)
    if not msg:
        return jsonify({"error": "Message not found"}), 404
    messages.remove(msg)
    _save_messages(messages)
    return jsonify({"success": True, "deleted_id": msg_id})


# ---------------------------------------------------------------------------
# Report API
# ---------------------------------------------------------------------------

@blueprint.route("/api/listings/<int:listing_id>/report", methods=["POST"])
def api_report_listing(listing_id):
    data = request.get_json(silent=True) or {}
    reporter_id = data.get("reporter_id")
    reason = data.get("reason", "").strip()
    description = data.get("description", "").strip()
    if not reporter_id or not reason:
        return jsonify({"error": "reporter_id and reason required"}), 400
    reports = _load_reports()
    new_id = max((r["id"] for r in reports), default=0) + 1
    reports.append({
        "id": new_id,
        "listing_id": listing_id,
        "reporter_id": reporter_id,
        "reason": reason,
        "description": description,
        "timestamp": "2026-06-21T12:00:00Z",
        "status": "pending",
    })
    _save_reports(reports)
    return jsonify({"success": True, "report_id": new_id})


# ---------------------------------------------------------------------------
# Rating API
# ---------------------------------------------------------------------------

@blueprint.route("/api/ratings", methods=["POST"])
def api_submit_rating():
    data = request.get_json(silent=True) or {}
    listing_id = data.get("listing_id")
    rater_id = data.get("rater_id")
    rated_user_id = data.get("rated_user_id")
    score = data.get("score")
    comment = data.get("comment", "").strip()
    if not all([listing_id, rater_id, rated_user_id, score]):
        return jsonify({"error": "listing_id, rater_id, rated_user_id, score required"}), 400
    ratings = _load_ratings()
    new_id = max((r["id"] for r in ratings), default=0) + 1
    ratings.append({
        "id": new_id,
        "listing_id": listing_id,
        "rater_id": rater_id,
        "rated_user_id": rated_user_id,
        "score": int(score),
        "comment": comment,
        "timestamp": "2026-06-21T12:00:00Z",
    })
    _save_ratings(ratings)
    return jsonify({"success": True, "rating_id": new_id})


@blueprint.route("/api/ratings/<int:user_id>")
def api_user_ratings(user_id):
    ratings = _load_ratings()
    user_ratings = [r for r in ratings if r["rated_user_id"] == user_id]
    return jsonify(user_ratings)


# ---------------------------------------------------------------------------
# Listing management API
# ---------------------------------------------------------------------------

@blueprint.route("/api/listings", methods=["POST"])
def api_create_listing():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400

    products = _load_json(PRODUCTS_FILE)
    new_id = max(p["id"] for p in products) + 1 if products else 1
    seller_id = data.get("seller_id", session.get("user_id", 1))

    new_product = {
        "id": new_id,
        "asin": f"B{new_id:09d}",
        "name": name,
        "category": data.get("category", "Electronics"),
        "brand": data.get("brand", "Unbranded"),
        "condition": data.get("condition", "Good"),
        "description": data.get("description", ""),
        "start_price": float(data.get("start_price", 9.99)),
        "current_price": float(data.get("start_price", 9.99)),
        "buy_now_price": None,
        "reserve_price": None,
        "num_bids": 0,
        "seller_id": seller_id,
        "seller_username": data.get("seller_username", ""),
        "seller_rating": 0,
        "auction_start": "2026-06-21T12:00:00Z",
        "auction_end": "2026-06-28T12:00:00Z",
        "status": "active",
        "winner_id": None,
        "shipping": data.get("shipping", "Free Shipping"),
        "location": data.get("location", ""),
        "views": 0,
        "watchers": 0,
        "color_options": [],
        "size_options": [],
        "return_policy": "30-day returns",
        "payment_methods": ["Credit Card", "PayPal"],
    }
    products.append(new_product)
    _save_json(PRODUCTS_FILE, products)

    global _products, _categories
    _products = None
    _categories = None

    return jsonify({"success": True, "listing_id": new_id}), 201


@blueprint.route("/api/listings/<int:listing_id>", methods=["PUT"])
def api_update_listing(listing_id):
    data = request.get_json(silent=True) or {}
    products = _load_json(PRODUCTS_FILE)
    product = next((p for p in products if p["id"] == listing_id), None)
    if not product:
        return jsonify({"error": "Listing not found"}), 404

    for field in ["name", "description", "category", "condition", "shipping", "location"]:
        if field in data:
            product[field] = data[field]

    _save_json(PRODUCTS_FILE, products)

    global _products, _categories
    _products = None
    _categories = None

    return jsonify({"success": True, "listing_id": listing_id})


@blueprint.route("/api/listings/<int:listing_id>", methods=["DELETE"])
def api_delete_listing(listing_id):
    products = _load_json(PRODUCTS_FILE)
    product = next((p for p in products if p["id"] == listing_id), None)
    if not product:
        return jsonify({"error": "Listing not found"}), 404
    products.remove(product)
    _save_json(PRODUCTS_FILE, products)

    global _products, _categories
    _products = None
    _categories = None

    return jsonify({"success": True, "deleted_id": listing_id})


# ---------------------------------------------------------------------------
# Upload (image placeholder)
# ---------------------------------------------------------------------------

@blueprint.route("/api/listings/<int:listing_id>/upload", methods=["POST"])
def api_upload_image(listing_id):
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    f = request.files["file"]
    if f.filename == "":
        return jsonify({"error": "No file selected"}), 400
    # In a real app, we'd save the file. Here we just acknowledge it.
    filename = f.filename
    return jsonify({"success": True, "listing_id": listing_id, "filename": filename})


# ---------------------------------------------------------------------------
# Checkout
# ---------------------------------------------------------------------------

@blueprint.route("/api/checkout", methods=["POST"])
def api_checkout():
    data = request.get_json(silent=True) or {}
    listing_id = data.get("listing_id")
    buyer_id = data.get("buyer_id")
    payment_method = data.get("payment_method", "Credit Card")
    shipping_address = data.get("shipping_address", "")

    if not listing_id or not buyer_id:
        return jsonify({"error": "listing_id and buyer_id required"}), 400

    products = _load_json(PRODUCTS_FILE)
    product = next((p for p in products if p["id"] == listing_id), None)
    if not product:
        return jsonify({"error": "Listing not found"}), 404

    # Mark as sold
    product["status"] = "ended"
    product["winner_id"] = buyer_id
    _save_json(PRODUCTS_FILE, products)

    global _products, _categories
    _products = None
    _categories = None

    return jsonify({
        "success": True,
        "order_id": f"ORD-{listing_id}-{buyer_id}",
        "listing_id": listing_id,
        "total": product["current_price"],
        "payment_method": payment_method,
    })


# ---------------------------------------------------------------------------
# Configure bid increment (slider)
# ---------------------------------------------------------------------------

@blueprint.route("/api/settings/bid-increment", methods=["POST"])
def api_configure_bid_increment():
    data = request.get_json(silent=True) or {}
    increment = data.get("increment", 1.0)
    # Store in config (simulated)
    return jsonify({"success": True, "bid_increment": float(increment)})
