"""Auctions & P2P Marketplaces — eBay-style auction platform.

Products populated from webshop data at build time into the products table.
"""
import pathlib
from datetime import datetime, timedelta

from flask import Blueprint, Response, abort, jsonify, redirect, render_template, request, session, url_for
from app import db
from app.events import emit

SITE = "auctions-p2p-marketplaces"
SITE_DIR = pathlib.Path(__file__).resolve().parent
_PRODUCTS_TABLE = "auctions_p2p_marketplaces_products"

blueprint = Blueprint(
    "auctions-p2p-marketplaces",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _get_product(product_id):
    return db.get_item(SITE, "products", product_id)


def _get_categories_from_db():
    rows = db.execute(
        f"SELECT DISTINCT category FROM [{_PRODUCTS_TABLE}] WHERE category != '' ORDER BY category")
    return [r["category"] for r in rows]


def _get_conditions_from_db():
    rows = db.execute(
        f"SELECT DISTINCT [condition] FROM [{_PRODUCTS_TABLE}] ORDER BY [condition]")
    return [r["condition"] for r in rows]


def _get_user(user_id):
    """Get a single user by ID."""
    return db.get_item(SITE, "users", user_id)


def _max_id(collection, id_col="id"):
    """Get the max id from a collection via SQL."""
    table = db.get_table_name(SITE, collection)
    if not table:
        return 0
    return db.execute(f"SELECT MAX([{id_col}]) as m FROM [{table}]", fetch="val") or 0


# ---------------------------------------------------------------------------
# Search / filter helpers
# ---------------------------------------------------------------------------

def _keyword_score(query, product):
    terms = query.lower().split()
    parts = [str(product["name"]), str(product.get("description", "")),
             str(product["category"]), str(product.get("brand", ""))]
    text = " ".join(parts).lower()
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
        return [p for p in products if q in str(p["name"]).lower() or
                q in str(p.get("description", "")).lower() or
                q in str(p["category"]).lower() or
                q in str(p.get("brand", "")).lower()]


def _build_product_query(q="", cat="", status="", condition="",
                         min_price=None, max_price=None, sort="ending_soon", limit=50):
    """Query products with filters pushed to SQL.  Uses FTS for text search."""

    sort_map = {
        "ending_soon": "[auction_end] ASC",
        "price_low": "[current_price] ASC",
        "price_high": "[current_price] DESC",
        "most_bids": "[num_bids] DESC",
        "newest": "[auction_start] DESC",
    }

    # Predicate mirroring the SQL filters — used to merge session-overlay
    # items (new/edited listings) into raw execute()/search() results.
    def _overlay_match(p):
        if cat and p.get("category") != cat:
            return False
        if status and p.get("status") != status:
            return False
        if condition and p.get("condition") != condition:
            return False
        price = p.get("current_price") or 0
        if min_price is not None and price < min_price:
            return False
        if max_price is not None and price > max_price:
            return False
        if q:
            text = " ".join(str(p.get(f, ""))
                            for f in ("name", "description", "category", "brand")).lower()
            if not all(t in text for t in q.lower().split()):
                return False
        return True

    # --- Text search path: use FTS5 via db.search() ---
    if q:
        where_eq = {}
        if cat:
            where_eq["category"] = cat
        if status:
            where_eq["status"] = status
        if condition:
            where_eq["condition"] = condition
        results = db.search(SITE, "products", q,
                            where=where_eq if where_eq else None,
                            limit=max(limit, 200))
        # FTS reads the base table only — merge in this session's listings
        results = db.merge_overlay(SITE, "products", results, match=_overlay_match)
        # Post-filter on numeric fields not supported by where=
        if min_price is not None:
            results = [p for p in results if (p.get("current_price") or 0) >= min_price]
        if max_price is not None:
            results = [p for p in results if (p.get("current_price") or 0) <= max_price]
        # Sort (FTS returns by relevance; re-sort if user asked for something else)
        order = sort_map.get(sort)
        if sort != "relevance" and order:
            sort_key_map = {
                "ending_soon": lambda p: p.get("auction_end", ""),
                "price_low": lambda p: p.get("current_price", 0),
                "price_high": lambda p: -(p.get("current_price", 0)),
                "most_bids": lambda p: -(p.get("num_bids", 0)),
                "newest": lambda p: p.get("auction_start", ""),
            }
            key_fn = sort_key_map.get(sort)
            if key_fn:
                reverse = sort in ("newest",)
                results.sort(key=key_fn, reverse=reverse)
        return results[:limit]

    # --- Non-search path: normal SQL filters ---
    clauses = []
    params = []
    if cat:
        clauses.append("[category] = ?")
        params.append(cat)
    if status:
        clauses.append("[status] = ?")
        params.append(status)
    if condition:
        clauses.append("[condition] = ?")
        params.append(condition)
    if min_price is not None:
        clauses.append("[current_price] >= ?")
        params.append(min_price)
    if max_price is not None:
        clauses.append("[current_price] <= ?")
        params.append(max_price)

    now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    if sort == "ending_soon":
        # Auctions still running sort before already-ended ones
        order = f"CASE WHEN [auction_end] >= '{now_iso}' THEN 0 ELSE 1 END, [auction_end] ASC"
    else:
        order = sort_map.get(sort, "[auction_end] ASC")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT * FROM [{_PRODUCTS_TABLE}]{where} ORDER BY {order} LIMIT ?"
    params.append(limit)
    rows = db.execute(sql, tuple(params))

    # Raw SQL reads the base table only — merge in this session's new/edited
    # listings from the overlay, re-sort, and re-apply the limit.
    merged = db.merge_overlay(SITE, "products", rows, match=_overlay_match)
    sort_key_map = {
        "ending_soon": lambda p: ((p.get("auction_end") or "") < now_iso,
                                  p.get("auction_end") or ""),
        "price_low": lambda p: p.get("current_price") or 0,
        "price_high": lambda p: -(p.get("current_price") or 0),
        "most_bids": lambda p: -(p.get("num_bids") or 0),
        "newest": lambda p: p.get("auction_start") or "",
    }
    merged.sort(key=sort_key_map.get(sort, sort_key_map["ending_soon"]),
                reverse=(sort == "newest"))
    return merged[:limit]


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    q = request.args.get("q", "").strip()
    cat = request.args.get("category", "").strip()
    status = request.args.get("status", "").strip()
    condition = request.args.get("condition", "").strip()
    sort = request.args.get("sort", "ending_soon").strip()
    min_price = request.args.get("min_price", "").strip()
    max_price = request.args.get("max_price", "").strip()

    min_p = None
    max_p = None
    if min_price:
        try:
            min_p = float(min_price)
        except ValueError:
            pass
    if max_price:
        try:
            max_p = float(max_price)
        except ValueError:
            pass

    results = _build_product_query(q=q, cat=cat, condition=condition,
                                    min_price=min_p, max_price=max_p, sort=sort)
    if sort == "relevance" and q:
        results.sort(key=lambda p: -_keyword_score(q, p))

    categories = _get_categories_from_db()
    conditions = _get_conditions_from_db()

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template("auctions-p2p-marketplaces/index.html",
                           products=results, categories=categories,
                           conditions=conditions,
                           q=q, cat=cat, status=status, condition_filter=condition,
                           sort=sort, min_price=min_price, max_price=max_price,
                           user=user)


@blueprint.route("/listing/<int:listing_id>")
def listing_detail(listing_id):
    product = _get_product(listing_id)
    if product is None:
        abort(404)
    listing_bids = db.query(SITE, "bids",
                            where={"listing_id": listing_id},
                            sort="-amount")
    related = _build_product_query(cat=product["category"], limit=7)
    related = [p for p in related if p["id"] != listing_id][:6]
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    seller = _get_user(product["seller_id"])
    seller_ratings = db.query(SITE, "ratings",
                              where={"rated_user_id": product["seller_id"]})
    return render_template("auctions-p2p-marketplaces/listing.html",
                           product=product, bids=listing_bids, related=related,
                           user=user, seller=seller, seller_ratings=seller_ratings)


@blueprint.route("/category/<path:cat_name>")
def category_page(cat_name):
    sort = request.args.get("sort", "ending_soon")
    filtered = _build_product_query(cat=cat_name, sort=sort)
    categories = _get_categories_from_db()
    return render_template("auctions-p2p-marketplaces/category.html",
                           products=filtered, category=cat_name,
                           categories=categories, sort=sort)


@blueprint.route("/seller/<int:seller_id>")
def seller_page(seller_id):
    seller = _get_user(seller_id)
    if not seller:
        abort(404)
    listings = db.query(SITE, "products", where={"seller_id": seller_id}, limit=50)
    seller_ratings = db.query(SITE, "ratings",
                              where={"rated_user_id": seller_id})
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

    # Items user is selling
    my_listings = db.query(SITE, "products", where={"seller_id": user["id"]}, limit=50)

    # Items user has bid on — get unique listing IDs from bids
    user_bids = db.query(SITE, "bids", where={"bidder_id": user["id"]})
    my_bid_listing_ids = list(set(b["listing_id"] for b in user_bids))
    if my_bid_listing_ids:
        my_bids = [_get_product(lid) for lid in my_bid_listing_ids]
        my_bids = [p for p in my_bids if p]
    else:
        my_bids = []

    # Watchlist
    my_watchlist = db.query(SITE, "watchlist", where={"user_id": user["id"]})
    my_watchlist_ids = [w["listing_id"] for w in my_watchlist]
    if my_watchlist_ids:
        watched = [_get_product(lid) for lid in my_watchlist_ids]
        watched = [p for p in watched if p]
    else:
        watched = []

    # Messages for this user
    table = db.get_table_name(SITE, "messages")
    my_messages = db.execute(
        f"SELECT * FROM [{table}] WHERE [sender_id] = ? OR [receiver_id] = ? ORDER BY [timestamp] DESC",
        (user["id"], user["id"]))

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
    # users table is small (<20 rows)
    users = db.query(SITE, "users")
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
    # users table is small (<20 rows)
    users = db.query(SITE, "users")
    if any(u["username"] == username for u in users):
        return render_template("auctions-p2p-marketplaces/login.html",
                               error="Username already taken", mode="register")
    new_id = _max_id("users") + 1
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
    db.save_item(SITE, "users", new_id, new_user)
    emit("signup", user_id=new_id, site_name="auctions-p2p-marketplaces",
         username=username, password=password, email=email)
    session["user_id"] = new_id
    return redirect(url_for("auctions-p2p-marketplaces.dashboard"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("auctions-p2p-marketplaces.login_page"))


@blueprint.route("/compare")
def compare_page():
    ids_str = request.args.get("ids", "")
    selected = []
    if ids_str:
        ids = [int(x) for x in ids_str.split(",") if x.strip().isdigit()]
        selected = [_get_product(pid) for pid in ids]
        selected = [s for s in selected if s]
    products = _build_product_query(limit=50)
    return render_template("auctions-p2p-marketplaces/compare.html",
                           products=products, selected=selected)


@blueprint.route("/create-listing", methods=["GET"])
def create_listing_page():
    if "user_id" not in session:
        return render_template("auctions-p2p-marketplaces/login.html", error=None, mode="login")
    user = _get_user(session["user_id"])
    return render_template("auctions-p2p-marketplaces/create_listing.html",
                           user=user, categories=_get_categories_from_db())


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
                               user=user, categories=_get_categories_from_db(),
                               error="Listing name is required")

    new_id = _max_id("products") + 1

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
        "auction_start": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "auction_end": (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ"),
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
    db.save_item(SITE, "products", new_id, new_product)

    return redirect(url_for("auctions-p2p-marketplaces.listing_detail", listing_id=new_id))


@blueprint.route("/edit-listing/<int:listing_id>", methods=["GET"])
def edit_listing_page(listing_id):
    if "user_id" not in session:
        return render_template("auctions-p2p-marketplaces/login.html", error=None, mode="login")
    product = _get_product(listing_id)
    if not product:
        abort(404)
    user = _get_user(session["user_id"])
    return render_template("auctions-p2p-marketplaces/edit_listing.html",
                           user=user, product=product, categories=_get_categories_from_db())


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

    product = _get_product(listing_id)
    if not product or product["status"] != "active" or amount <= product["current_price"]:
        return redirect(url_for("auctions-p2p-marketplaces.listing_detail", listing_id=listing_id))

    new_bid_id = _max_id("bids", "bid_id") + 1
    new_bid = {
        "bid_id": new_bid_id,
        "listing_id": listing_id,
        "bidder_id": user_id,
        "amount": amount,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "auto_bid": False,
    }
    # bids PK is row_id, so we need to use save_collection for append
    bids = db.query(SITE, "bids", limit=50)
    bids.append(new_bid)
    db.save_collection(SITE, "bids", bids)

    product["current_price"] = amount
    product["num_bids"] += 1
    db.save_item(SITE, "products", listing_id, product)

    return redirect(url_for("auctions-p2p-marketplaces.listing_detail", listing_id=listing_id))


@blueprint.route("/edit-listing/<int:listing_id>", methods=["POST"])
def edit_listing_submit(listing_id):
    if "user_id" not in session:
        return redirect(url_for("auctions-p2p-marketplaces.login_page"))

    product = _get_product(listing_id)
    if not product:
        abort(404)

    for field in ["name", "description", "category", "condition", "shipping", "location"]:
        val = request.form.get(field)
        if val is not None:
            product[field] = val.strip()

    db.save_item(SITE, "products", listing_id, product)

    return redirect(url_for("auctions-p2p-marketplaces.listing_detail", listing_id=listing_id))


@blueprint.route("/listing/<int:listing_id>/delete", methods=["POST"])
def delete_listing_form(listing_id):
    if "user_id" not in session:
        return redirect(url_for("auctions-p2p-marketplaces.login_page"))

    product = _get_product(listing_id)
    if product:
        db.delete_item(SITE, "products", listing_id)

    return redirect(url_for("auctions-p2p-marketplaces.dashboard"))


@blueprint.route("/listing/<int:listing_id>/watch", methods=["POST"])
def watch_listing_form(listing_id):
    if "user_id" not in session:
        return redirect(url_for("auctions-p2p-marketplaces.login_page"))
    user_id = session["user_id"]
    existing = db.query(SITE, "watchlist",
                        where={"user_id": user_id, "listing_id": listing_id},
                        limit=1)
    if existing:
        db.delete_item(SITE, "watchlist", existing[0]["id"])
    else:
        new_id = _max_id("watchlist") + 1
        db.save_item(SITE, "watchlist", new_id, {
            "id": new_id, "user_id": user_id, "listing_id": listing_id,
        })
    return redirect(url_for("auctions-p2p-marketplaces.listing_detail", listing_id=listing_id))


@blueprint.route("/listing/<int:listing_id>/save", methods=["POST"])
def save_listing_form(listing_id):
    if "user_id" not in session:
        return redirect(url_for("auctions-p2p-marketplaces.login_page"))
    user_id = session["user_id"]
    user = db.get_item(SITE, "users", user_id)
    if user:
        saved = user.get("saved_listings", []) or []
        if listing_id in saved:
            saved.remove(listing_id)
        else:
            saved.append(listing_id)
        user["saved_listings"] = saved
        db.save_item(SITE, "users", user_id, user)
    return redirect(url_for("auctions-p2p-marketplaces.listing_detail", listing_id=listing_id))


@blueprint.route("/seller/<int:seller_id>/follow", methods=["POST"])
def follow_seller_form(seller_id):
    if "user_id" not in session:
        return redirect(url_for("auctions-p2p-marketplaces.login_page"))
    user_id = session["user_id"]
    user = db.get_item(SITE, "users", user_id)
    if user:
        followed = user.get("followed_sellers", []) or []
        if seller_id in followed:
            followed.remove(seller_id)
        else:
            followed.append(seller_id)
        user["followed_sellers"] = followed
        db.save_item(SITE, "users", user_id, user)
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
        new_id = _max_id("messages") + 1
        db.save_item(SITE, "messages", new_id, {
            "id": new_id,
            "listing_id": listing_id,
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "subject": subject or "No subject",
            "body": body,
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "read": False,
        })

        try:
            from app.bridges import on_message
            on_message(from_user_id=sender_id, to_user_id=receiver_id, text=body, source_site="Auctions")
        except Exception:
            pass

    next_url = request.form.get("next") or request.referrer
    if next_url:
        return redirect(next_url)
    return redirect(url_for("auctions-p2p-marketplaces.dashboard"))


@blueprint.route("/message/<int:msg_id>/delete", methods=["POST"])
def delete_message_form(msg_id):
    if "user_id" not in session:
        return redirect(url_for("auctions-p2p-marketplaces.login_page"))
    msg = db.get_item(SITE, "messages", msg_id)
    if msg:
        db.delete_item(SITE, "messages", msg_id)
    return redirect(url_for("auctions-p2p-marketplaces.dashboard"))


@blueprint.route("/listing/<int:listing_id>/report", methods=["POST"])
def report_listing_form(listing_id):
    if "user_id" not in session:
        return redirect(url_for("auctions-p2p-marketplaces.login_page"))
    reason = request.form.get("reason", "").strip()
    description = request.form.get("description", "").strip()
    if reason:
        new_id = _max_id("reports") + 1
        db.save_item(SITE, "reports", new_id, {
            "id": new_id,
            "listing_id": listing_id,
            "reporter_id": session["user_id"],
            "reason": reason,
            "description": description,
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": "pending",
        })
    return redirect(url_for("auctions-p2p-marketplaces.listing_detail", listing_id=listing_id))


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/listings")
def api_listings():
    q = request.args.get("q", "").strip()
    cat = request.args.get("category", "").strip()
    status = request.args.get("status", "").strip()
    condition = request.args.get("condition", "").strip()
    sort = request.args.get("sort", "ending_soon")
    min_price = request.args.get("min_price", type=float)
    max_price = request.args.get("max_price", type=float)
    limit = request.args.get("limit", type=int)

    results = _build_product_query(q=q, cat=cat, condition=condition,
                                    min_price=min_price, max_price=max_price,
                                    sort=sort, limit=limit or 50)
    if sort == "relevance" and q:
        results.sort(key=lambda p: -_keyword_score(q, p))
    return jsonify(results)


@blueprint.route("/api/listings/<int:listing_id>")
def api_listing(listing_id):
    product = _get_product(listing_id)
    if product is None:
        abort(404)
    return jsonify(product)


@blueprint.route("/api/listings/search")
def api_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    results = _build_product_query(q=q, limit=50)
    return jsonify(results)


@blueprint.route("/api/listings/semantic")
def api_semantic_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    # Semantic search needs Python scoring
    products = _build_product_query(limit=200)
    return jsonify(_search_products(products, q, semantic=True))


@blueprint.route("/api/categories")
def api_categories():
    table = _PRODUCTS_TABLE
    rows = db.execute(
        f"SELECT [category], COUNT(*) as cnt FROM [{table}] GROUP BY [category] ORDER BY [category]")
    return jsonify([{"name": r["category"], "count": r["cnt"]} for r in rows])


@blueprint.route("/api/categories/<path:cat_name>/listings")
def api_category_listings(cat_name):
    return jsonify(_build_product_query(cat=cat_name, limit=50))


@blueprint.route("/api/categories/<path:cat_name>/stats")
def api_category_stats(cat_name):
    stats = db.execute(
        f"SELECT COUNT(*) as cnt, AVG(current_price) as avg_price, "
        f"MIN(current_price) as min_price, MAX(current_price) as max_price, "
        f"SUM(num_bids) as total_bids "
        f"FROM [{_PRODUCTS_TABLE}] WHERE [category] = ?",
        (cat_name,), fetch="one")
    if not stats or stats["cnt"] == 0:
        return jsonify({"category": cat_name, "count": 0})
    return jsonify({
        "category": cat_name,
        "count": stats["cnt"],
        "avg_price": round(stats["avg_price"] or 0, 2),
        "min_price": stats["min_price"] or 0,
        "max_price": stats["max_price"] or 0,
        "total_bids": stats["total_bids"] or 0,
    })


@blueprint.route("/api/stats")
def api_stats():
    cat = request.args.get("category", "").strip()
    where = "WHERE [category] = ?" if cat else ""
    p = (cat,) if cat else ()

    stats = db.execute(
        f"SELECT COUNT(*) as cnt, AVG(current_price) as avg_price, "
        f"SUM(num_bids) as total_bids, "
        f"COUNT(DISTINCT seller_id) as unique_sellers "
        f"FROM [{_PRODUCTS_TABLE}] {where}", p, fetch="one")

    if not stats or stats["cnt"] == 0:
        return jsonify({"count": 0})

    cat_rows = db.execute(
        f"SELECT [category], COUNT(*) as cnt FROM [{_PRODUCTS_TABLE}] "
        + (f"WHERE [category] = ? " if cat else "")
        + f"GROUP BY [category] ORDER BY cnt DESC LIMIT 12", p)
    categories = {r["category"]: r["cnt"] for r in cat_rows}

    return jsonify({
        "count": stats["cnt"],
        "avg_price": round(stats["avg_price"] or 0, 2),
        "total_bids": stats["total_bids"] or 0,
        "unique_sellers": stats["unique_sellers"] or 0,
        "categories": categories,
    })


@blueprint.route("/api/compare")
def api_compare():
    ids_str = request.args.get("ids", "")
    ids = [int(x) for x in ids_str.split(",") if x.strip().isdigit()]
    selected = [_get_product(pid) for pid in ids]
    selected = [s for s in selected if s]
    return jsonify(selected)


@blueprint.route("/api/export")
def api_export():
    fmt = request.args.get("format", "json").lower()
    cat = request.args.get("category", "").strip()
    products = _build_product_query(cat=cat, limit=500)

    if fmt == "csv":
        lines = ["id,name,category,brand,price"]
        for p in products:
            name = p["name"].replace('"', '""')
            brand = p.get("brand", "").replace('"', '""')
            lines.append(f'{p["id"]},"{name}","{p["category"]}","{brand}",{p["current_price"]}')
        return Response("\n".join(lines), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=listings.csv"})
    return jsonify(products)


# ---------------------------------------------------------------------------
# Bid API
# ---------------------------------------------------------------------------

@blueprint.route("/api/listings/<int:listing_id>/bids")
def api_listing_bids(listing_id):
    listing_bids = db.query(SITE, "bids",
                            where={"listing_id": listing_id},
                            sort="-amount")
    return jsonify(listing_bids)


@blueprint.route("/api/listings/<int:listing_id>/bid", methods=["POST"])
def api_place_bid(listing_id):
    data = request.get_json(silent=True) or {}
    amount = data.get("amount")
    bidder_id = data.get("bidder_id")
    if amount is None or bidder_id is None:
        return jsonify({"error": "amount and bidder_id required"}), 400

    product = _get_product(listing_id)
    if not product:
        return jsonify({"error": "Listing not found"}), 404
    if product["status"] != "active":
        return jsonify({"error": "Auction is not active"}), 400
    if float(amount) <= product["current_price"]:
        return jsonify({"error": "Bid must be higher than current price"}), 400

    new_bid_id = _max_id("bids", "bid_id") + 1
    new_bid = {
        "bid_id": new_bid_id,
        "listing_id": listing_id,
        "bidder_id": bidder_id,
        "amount": float(amount),
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "auto_bid": False,
    }
    # bids PK is row_id, append via save_collection
    bids = db.query(SITE, "bids", limit=50)
    bids.append(new_bid)
    db.save_collection(SITE, "bids", bids)

    # Update product
    product["current_price"] = float(amount)
    product["num_bids"] += 1
    db.save_item(SITE, "products", listing_id, product)

    return jsonify({"success": True, "bid_id": new_bid_id, "new_price": float(amount)})


# ---------------------------------------------------------------------------
# User API
# ---------------------------------------------------------------------------

@blueprint.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    # users table is small (<20 rows)
    users = db.query(SITE, "users")
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
    # users table is small (<20 rows)
    users = db.query(SITE, "users")
    if any(u["username"] == username for u in users):
        return jsonify({"error": "Username already taken"}), 409
    new_id = _max_id("users") + 1
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
    db.save_item(SITE, "users", new_id, new_user)
    emit("signup", user_id=new_id, site_name="auctions-p2p-marketplaces",
         username=username, password=password, email=email)
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
    user = db.get_item(SITE, "users", user_id)
    if not user:
        abort(404)
    saved = user.get("saved_listings", []) or []
    if listing_id in saved:
        saved.remove(listing_id)
        action = "unsaved"
    else:
        saved.append(listing_id)
        action = "saved"
    user["saved_listings"] = saved
    db.save_item(SITE, "users", user_id, user)
    return jsonify({"action": action, "listing_id": listing_id, "total_saved": len(saved)})


@blueprint.route("/api/users/<int:user_id>/watch", methods=["POST"])
def api_watch_listing(user_id):
    data = request.get_json(silent=True) or {}
    listing_id = data.get("listing_id")
    if listing_id is None:
        return jsonify({"error": "listing_id required"}), 400
    existing = db.query(SITE, "watchlist",
                        where={"user_id": user_id, "listing_id": listing_id},
                        limit=1)
    if existing:
        db.delete_item(SITE, "watchlist", existing[0]["id"])
        action = "unwatched"
    else:
        new_id = _max_id("watchlist") + 1
        db.save_item(SITE, "watchlist", new_id, {
            "id": new_id, "user_id": user_id, "listing_id": listing_id,
        })
        action = "watched"
    return jsonify({"action": action, "listing_id": listing_id})


@blueprint.route("/api/users/<int:user_id>/follow", methods=["POST"])
def api_follow_seller(user_id):
    data = request.get_json(silent=True) or {}
    seller_id = data.get("seller_id")
    if seller_id is None:
        return jsonify({"error": "seller_id required"}), 400
    user = db.get_item(SITE, "users", user_id)
    if not user:
        abort(404)
    followed = user.get("followed_sellers", []) or []
    if seller_id in followed:
        followed.remove(seller_id)
        action = "unfollowed"
    else:
        followed.append(seller_id)
        action = "followed"
    user["followed_sellers"] = followed
    db.save_item(SITE, "users", user_id, user)
    return jsonify({"action": action, "seller_id": seller_id, "total_followed": len(followed)})


# ---------------------------------------------------------------------------
# Message API
# ---------------------------------------------------------------------------

@blueprint.route("/api/messages")
def api_messages():
    user_id = request.args.get("user_id", type=int)
    if user_id:
        table = db.get_table_name(SITE, "messages")
        messages = db.execute(
            f"SELECT * FROM [{table}] WHERE [sender_id] = ? OR [receiver_id] = ? "
            f"ORDER BY [timestamp] DESC",
            (user_id, user_id))
    else:
        messages = db.query(SITE, "messages", sort="-timestamp")
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
    new_id = _max_id("messages") + 1
    new_msg = {
        "id": new_id,
        "listing_id": listing_id,
        "sender_id": sender_id,
        "receiver_id": receiver_id,
        "subject": subject or "No subject",
        "body": body,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "read": False,
    }
    db.save_item(SITE, "messages", new_id, new_msg)

    try:
        from app.bridges import on_message
        on_message(from_user_id=sender_id, to_user_id=receiver_id, text=body, source_site="Auctions")
    except Exception:
        pass

    return jsonify({"success": True, "message_id": new_id})


@blueprint.route("/api/messages/<int:msg_id>", methods=["DELETE"])
def api_delete_message(msg_id):
    msg = db.get_item(SITE, "messages", msg_id)
    if not msg:
        return jsonify({"error": "Message not found"}), 404
    db.delete_item(SITE, "messages", msg_id)
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
    new_id = _max_id("reports") + 1
    db.save_item(SITE, "reports", new_id, {
        "id": new_id,
        "listing_id": listing_id,
        "reporter_id": reporter_id,
        "reason": reason,
        "description": description,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "pending",
    })
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
    new_id = _max_id("ratings") + 1
    db.save_item(SITE, "ratings", new_id, {
        "id": new_id,
        "listing_id": listing_id,
        "rater_id": rater_id,
        "rated_user_id": rated_user_id,
        "score": int(score),
        "comment": comment,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    })
    return jsonify({"success": True, "rating_id": new_id})


@blueprint.route("/api/ratings/<int:user_id>")
def api_user_ratings(user_id):
    user_ratings = db.query(SITE, "ratings",
                            where={"rated_user_id": user_id})
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

    new_id = _max_id("products") + 1
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
        "auction_start": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "auction_end": (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ"),
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
    db.save_item(SITE, "products", new_id, new_product)

    return jsonify({"success": True, "listing_id": new_id}), 201


@blueprint.route("/api/listings/<int:listing_id>", methods=["PUT"])
def api_update_listing(listing_id):
    data = request.get_json(silent=True) or {}
    product = _get_product(listing_id)
    if not product:
        return jsonify({"error": "Listing not found"}), 404

    for field in ["name", "description", "category", "condition", "shipping", "location"]:
        if field in data:
            product[field] = data[field]

    db.save_item(SITE, "products", listing_id, product)

    return jsonify({"success": True, "listing_id": listing_id})


@blueprint.route("/api/listings/<int:listing_id>", methods=["DELETE"])
def api_delete_listing(listing_id):
    product = _get_product(listing_id)
    if not product:
        return jsonify({"error": "Listing not found"}), 404
    db.delete_item(SITE, "products", listing_id)

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
    account_type = data.get("account_type", "checking")

    if not listing_id or not buyer_id:
        return jsonify({"error": "listing_id and buyer_id required"}), 400

    product = _get_product(listing_id)
    if not product:
        return jsonify({"error": "Listing not found"}), 404

    # Mark as sold
    product["status"] = "ended"
    product["winner_id"] = buyer_id
    db.save_item(SITE, "products", listing_id, product)

    emit("purchase", user_id=buyer_id, amount=product["current_price"], merchant="BidMarket", item=product["name"], account_type=account_type)

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
