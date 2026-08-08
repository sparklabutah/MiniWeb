"""Software Marketplace -- App store (Google Play / App Store style).

Data is stored in per-site SQLite tables (software_marketplace_apps,
software_marketplace_reviews, etc.) and queried through app.db.
Session mutations are isolated per user.

Supported macros (20):
  navigate_by_dropdown, navigate_by_route, search_by_query,
  search_by_semantic, filter_by_dropdown, filter_by_slider,
  sort_by_ranking, sort_by_extremum, extract_from_table,
  extract_by_route, compare_from_table, select_by_dropdown,
  configure_by_dropdown, configure_by_slider, export_by_dropdown,
  rate_by_slider, save_by_toggle, add_by_button,
  checkout_by_form, redeem_by_code
"""
import csv
import io
import json
import pathlib
import datetime
from collections import Counter

from flask import (
    Blueprint, Response, abort, jsonify, redirect, render_template,
    request, session, url_for,
)
from app import db
from app.events import emit
from app.handlers.email_handler import _add_email

SITE = "software-marketplace"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "software-marketplace",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data helpers — all data lives in SQLite via db.query() / db.execute()
# ---------------------------------------------------------------------------

# Category icon/color map for frontend display
CATEGORY_ICONS = {
    "GAME": ("joystick", "#e74c3c"),
    "FAMILY": ("people", "#9b59b6"),
    "TOOLS": ("wrench", "#3498db"),
    "MEDICAL": ("heart-pulse", "#e91e63"),
    "BUSINESS": ("briefcase", "#2c3e50"),
    "PRODUCTIVITY": ("lightning", "#f39c12"),
    "PERSONALIZATION": ("palette", "#e67e22"),
    "COMMUNICATION": ("chat", "#1abc9c"),
    "SPORTS": ("trophy", "#27ae60"),
    "LIFESTYLE": ("sun", "#ff6b6b"),
    "FINANCE": ("bank", "#2ecc71"),
    "HEALTH_AND_FITNESS": ("activity", "#00b894"),
    "PHOTOGRAPHY": ("camera", "#6c5ce7"),
    "SOCIAL": ("share", "#fd79a8"),
    "NEWS_AND_MAGAZINES": ("newspaper", "#636e72"),
    "SHOPPING": ("cart", "#00cec9"),
    "TRAVEL_AND_LOCAL": ("globe", "#0984e3"),
    "DATING": ("heart", "#d63031"),
    "BOOKS_AND_REFERENCE": ("book", "#6d4c41"),
    "VIDEO_PLAYERS": ("play-circle", "#e84393"),
    "EDUCATION": ("graduation-cap", "#00b0ff"),
    "ENTERTAINMENT": ("film", "#ff7675"),
    "MAPS_AND_NAVIGATION": ("map-pin", "#55efc4"),
    "FOOD_AND_DRINK": ("coffee", "#fab1a0"),
    "HOUSE_AND_HOME": ("home", "#74b9ff"),
    "AUTO_AND_VEHICLES": ("truck", "#636e72"),
    "LIBRARIES_AND_DEMO": ("archive", "#b2bec3"),
    "WEATHER": ("cloud", "#74b9ff"),
    "ART_AND_DESIGN": ("brush", "#a29bfe"),
    "EVENTS": ("calendar", "#ffeaa7"),
    "COMICS": ("book-open", "#dfe6e9"),
    "PARENTING": ("baby", "#fdcb6e"),
    "BEAUTY": ("sparkles", "#e17055"),
}


def _get_user(user_id):
    return db.get_item(SITE, "users", user_id)


def _get_user_settings(user_id):
    results = db.query(SITE, "settings", where={"user_id": user_id}, limit=1)
    s = results[0] if results else None
    if not s:
        s = {
            "user_id": user_id,
            "theme": "light",
            "language": "English",
            "auto_update": True,
            "notification_frequency": 3,
            "download_wifi_only": True,
            "content_filter": "Everyone",
        }
    return s


def _get_app(app_id):
    app = db.get_item(SITE, "apps", app_id)
    if app and isinstance(app.get("genres"), str):
        try:
            app["genres"] = json.loads(app["genres"])
        except (json.JSONDecodeError, TypeError):
            pass
    return app


def _get_community_reviews(app_name):
    """Get community reviews for an app from the app_reviews table."""
    return db.query(SITE, "app_reviews", where={"app": app_name}, limit=100)


def _installed_app_ids(user_id):
    """Return the set of app_ids the given user has installed (per-user,
    small result set). Used to reflect installed state on listing/grid cards."""
    if not user_id:
        return set()
    # Use db.query (session-overlay aware) so freshly installed/uninstalled
    # apps are reflected; raw db.execute would only read the base table.
    rows = db.query(SITE, "installed", where={"user_id": user_id}, limit=500)
    return {r["app_id"] for r in rows}


def _get_categories_from_db():
    """Get category counts via SQL aggregation."""
    rows = db.execute(
        "SELECT category, COUNT(*) as cnt FROM software_marketplace_apps "
        "WHERE category != '' GROUP BY category ORDER BY category",
        fetch="all",
    )
    return [(r["category"], r["cnt"]) for r in rows]


def _get_genres_from_db():
    """Get genre counts via SQL aggregation."""
    rows = db.execute(
        "SELECT genre, COUNT(*) as cnt FROM software_marketplace_apps "
        "WHERE genre != '' GROUP BY genre ORDER BY genre",
        fetch="all",
    )
    return [(r["genre"], r["cnt"]) for r in rows]


# ---------------------------------------------------------------------------
# SQL query builders for apps
# ---------------------------------------------------------------------------

def _build_sort_clause(sort_key):
    """Map sort key to SQL ORDER BY clause."""
    sort_map = {
        "rating": "rating DESC, reviews_count DESC",
        "rating_asc": "rating ASC",
        "reviews": "reviews_count DESC",
        "name": "name ASC",
        "newest": "last_updated DESC",
        "price_asc": "price ASC",
        "price_desc": "price DESC",
        "installs": "reviews_count DESC",  # proxy for popularity
    }
    return sort_map.get(sort_key, "reviews_count DESC")


def _query_apps(category=None, genre=None, min_rating=None, max_price=None,
                price_type=None, sort="reviews", q=None, limit=24, offset=0):
    """Query apps with all filtering/sorting in SQL. Returns (apps, total_count)."""
    where_clauses = []
    params = []

    if category:
        where_clauses.append("category = ?")
        params.append(category)
    if genre:
        where_clauses.append("genre = ?")
        params.append(genre)
    if min_rating is not None:
        where_clauses.append("rating >= ?")
        params.append(min_rating)
    if max_price is not None:
        where_clauses.append("price <= ?")
        params.append(max_price)
    if price_type == "free":
        where_clauses.append("price = 0")
    elif price_type == "paid":
        where_clauses.append("price > 0")
    if q:
        # Use LIKE for keyword search across name, category, developer, description
        like = f"%{q}%"
        where_clauses.append(
            "(name LIKE ? OR category LIKE ? OR developer LIKE ? OR description LIKE ?)"
        )
        params.extend([like, like, like, like])

    where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
    order_sql = f" ORDER BY {_build_sort_clause(sort)}"

    # Count total results
    count_sql = f"SELECT COUNT(*) FROM software_marketplace_apps{where_sql}"
    total = db.execute(count_sql, tuple(params), fetch="val") or 0

    # Fetch page
    data_sql = (
        f"SELECT * FROM software_marketplace_apps{where_sql}"
        f"{order_sql} LIMIT ? OFFSET ?"
    )
    params.extend([limit, offset])
    apps = db.execute(data_sql, tuple(params), fetch="all")

    return apps, total


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    """Featured / home page -- Google Play style."""

    # Editor's Choice: top-rated apps with many reviews (high quality + popular)
    editors_choice = db.execute(
        "SELECT * FROM software_marketplace_apps "
        "WHERE rating >= 4.5 AND reviews_count >= 100000 "
        "ORDER BY rating DESC, reviews_count DESC LIMIT 6",
        fetch="all",
    )

    # Trending / most popular (most reviews)
    trending = db.execute(
        "SELECT * FROM software_marketplace_apps "
        "ORDER BY reviews_count DESC LIMIT 12",
        fetch="all",
    )

    # Top rated (highest rating with at least some reviews)
    top_rated = db.execute(
        "SELECT * FROM software_marketplace_apps "
        "WHERE reviews_count >= 1000 "
        "ORDER BY rating DESC, reviews_count DESC LIMIT 12",
        fetch="all",
    )

    # New & Updated (most recently updated)
    new_updated = db.execute(
        "SELECT * FROM software_marketplace_apps "
        "ORDER BY last_updated DESC LIMIT 12",
        fetch="all",
    )

    # Top Free
    top_free = db.execute(
        "SELECT * FROM software_marketplace_apps "
        "WHERE price = 0 "
        "ORDER BY reviews_count DESC LIMIT 12",
        fetch="all",
    )

    # Top Paid
    top_paid = db.execute(
        "SELECT * FROM software_marketplace_apps "
        "WHERE price > 0 "
        "ORDER BY reviews_count DESC LIMIT 12",
        fetch="all",
    )

    # Categories with counts
    categories = _get_categories_from_db()

    # Total app count for display
    total_apps = db.execute(
        "SELECT COUNT(*) FROM software_marketplace_apps",
        fetch="val",
    ) or 0

    user = None
    installed_ids = set()
    if "user_id" in session:
        user = _get_user(session["user_id"])
        installed_ids = _installed_app_ids(session["user_id"])

    return render_template(
        "software-marketplace/index.html",
        editors_choice=editors_choice,
        installed_ids=installed_ids,
        trending=trending,
        top_rated=top_rated,
        new_updated=new_updated,
        top_free=top_free,
        top_paid=top_paid,
        categories=categories,
        category_icons=CATEGORY_ICONS,
        total_apps=total_apps,
        user=user,
    )


@blueprint.route("/apps")
def apps_list():
    """Browse + filter apps (supports filter_by_dropdown, filter_by_slider,
    sort_by_ranking, sort_by_extremum)."""

    q = request.args.get("q", "").strip()
    cat = request.args.get("category", "").strip()
    genre = request.args.get("genre", "").strip()
    min_rating = request.args.get("min_rating", type=float)
    max_price = request.args.get("max_price", type=float)
    price_type = request.args.get("price", "").strip()
    sort = request.args.get("sort", "").strip() or "reviews"

    per_page = 24
    page = request.args.get("page", 1, type=int)
    if page < 1:
        page = 1

    offset = (page - 1) * per_page

    # Use FTS search if available, otherwise fall back to SQL LIKE
    if q:
        # Try FTS first via db.search
        apps = db.search(SITE, "apps", q, limit=per_page, offset=offset)
        # Get total via separate count
        total_results = db.execute(
            "SELECT COUNT(*) FROM software_marketplace_apps "
            "WHERE name LIKE ? OR category LIKE ? OR developer LIKE ? OR description LIKE ?",
            (f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%"),
            fetch="val",
        ) or 0
        # If FTS returned results, check if we need filtering
        if cat or min_rating or max_price or price_type:
            apps, total_results = _query_apps(
                category=cat or None, genre=genre or None,
                min_rating=min_rating, max_price=max_price,
                price_type=price_type or None, sort=sort,
                q=q, limit=per_page, offset=offset,
            )
    else:
        apps, total_results = _query_apps(
            category=cat or None, genre=genre or None,
            min_rating=min_rating, max_price=max_price,
            price_type=price_type or None, sort=sort,
            limit=per_page, offset=offset,
        )

    total_pages = max(1, (total_results + per_page - 1) // per_page)
    if page > total_pages:
        page = total_pages

    # Get categories and genres for filter dropdowns
    categories = _get_categories_from_db()
    genres = _get_genres_from_db()

    user = None
    installed_ids = set()
    if "user_id" in session:
        user = _get_user(session["user_id"])
        installed_ids = _installed_app_ids(session["user_id"])

    return render_template(
        "software-marketplace/apps.html",
        apps=apps, categories=categories, genres=genres,
        q=q, cat=cat, genre=genre, min_rating=min_rating,
        max_price=max_price, price=price_type, sort=sort,
        page=page, total_pages=total_pages, total_results=total_results,
        user=user, installed_ids=installed_ids,
    )


@blueprint.route("/app/<int:app_id>")
def app_detail(app_id):
    """App detail page with reviews (extract_by_route, rate_by_slider, add_by_button)."""
    app = _get_app(app_id)
    if not app:
        abort(404)

    # Get reviews for this app via SQL
    app_reviews = db.query(
        SITE, "reviews", where={"app_id": app_id},
        sort="-date", limit=50,
    )

    # Enrich reviews with user display names
    users = db.query(SITE, "users")  # small table (<10 rows)
    user_map = {u["id"]: u["display_name"] for u in users}
    for r in app_reviews:
        r["user_name"] = user_map.get(r["user_id"], "Unknown User")

    # Related apps in same category (SQL query, not load-all)
    related = db.execute(
        "SELECT * FROM software_marketplace_apps "
        "WHERE category = ? AND id != ? "
        "ORDER BY reviews_count DESC LIMIT 6",
        (app["category"], app_id),
        fetch="all",
    )

    # Check if current user has this app installed or in cart
    is_installed = False
    in_cart = False
    in_wishlist = False
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
        uid = session["user_id"]

        # Use db.query (session-overlay aware) so a just-installed app shows
        # its installed state immediately; raw db.execute reads only the base
        # table and would miss overlay mutations.
        is_installed = len(db.query(
            SITE, "installed",
            where={"user_id": uid, "app_id": app_id}, limit=1,
        )) > 0

        in_wishlist = len(db.query(
            SITE, "wishlists",
            where={"user_id": uid, "app_id": app_id}, limit=1,
        )) > 0

    return render_template(
        "software-marketplace/app_detail.html",
        app=app, reviews=app_reviews, related=related,
        is_installed=is_installed, in_cart=in_cart,
        in_wishlist=in_wishlist, user=user,
    )


@blueprint.route("/category/<cat>")
def category_page(cat):
    """Apps filtered by category (navigate_by_dropdown, select_by_dropdown for genre)."""
    genre = request.args.get("genre", "").strip()
    sort = request.args.get("sort", "").strip() or "reviews"
    page = request.args.get("page", 1, type=int)
    per_page = 24
    if page < 1:
        page = 1

    apps, total = _query_apps(
        category=cat, genre=genre or None, sort=sort,
        limit=per_page, offset=(page - 1) * per_page,
    )
    if total == 0 and not genre:
        abort(404)

    total_pages = max(1, (total + per_page - 1) // per_page)

    # Get genres within this category
    genre_rows = db.execute(
        "SELECT genre, COUNT(*) as cnt FROM software_marketplace_apps "
        "WHERE category = ? AND genre != '' GROUP BY genre ORDER BY genre",
        (cat,), fetch="all",
    )
    genre_list = [(r["genre"], r["cnt"]) for r in genre_rows]

    categories = _get_categories_from_db()

    user = None
    installed_ids = set()
    if "user_id" in session:
        user = _get_user(session["user_id"])
        installed_ids = _installed_app_ids(session["user_id"])

    return render_template(
        "software-marketplace/category.html",
        apps=apps, category=cat, categories=categories,
        genres=genre_list, genre=genre, sort=sort, user=user,
        page=page, total_pages=total_pages, total_results=total,
        installed_ids=installed_ids,
    )


@blueprint.route("/compare")
def compare_page():
    """Side-by-side app comparison (compare_from_table, extract_from_table)."""
    ids_param = request.args.get("ids", "")
    app_ids = []
    for s in ids_param.split(","):
        s = s.strip()
        if s.isdigit():
            app_ids.append(int(s))

    compare_apps = []
    for aid in app_ids[:6]:  # limit comparisons to 6
        app = _get_app(aid)
        if app:
            # Get review stats for this app
            review_stats = db.execute(
                "SELECT COUNT(*) as cnt, COALESCE(AVG(rating), 0) as avg_r "
                "FROM software_marketplace_reviews WHERE app_id = ?",
                (aid,), fetch="one",
            )
            app["avg_user_rating"] = round(review_stats["avg_r"], 1) if review_stats else 0
            app["review_count_actual"] = review_stats["cnt"] if review_stats else 0
            compare_apps.append(app)

    # For the "add app" dropdown, get top apps by reviews
    all_apps = db.execute(
        "SELECT id, name FROM software_marketplace_apps ORDER BY reviews_count DESC LIMIT 100",
        fetch="all",
    )

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template(
        "software-marketplace/compare.html",
        apps=compare_apps, user=user, all_apps=all_apps,
    )


@blueprint.route("/settings")
def settings_page():
    """User settings page (configure_by_dropdown, configure_by_slider)."""
    if "user_id" not in session:
        return redirect(url_for("software-marketplace.login_page"))
    user = _get_user(session["user_id"])
    if not user:
        return redirect(url_for("software-marketplace.login_page"))

    user_settings = _get_user_settings(session["user_id"])

    return render_template(
        "software-marketplace/settings.html",
        user=user, settings=user_settings,
    )


@blueprint.route("/settings", methods=["POST"])
def settings_update():
    """Update settings (configure_by_dropdown, configure_by_slider)."""
    if "user_id" not in session:
        return redirect(url_for("software-marketplace.login_page"))

    settings = db.query(SITE, "settings")  # small table
    user_settings = next(
        (s for s in settings if s["user_id"] == session["user_id"]), None
    )
    if not user_settings:
        user_settings = {
            "user_id": session["user_id"],
            "theme": "light",
            "language": "English",
            "auto_update": True,
            "notification_frequency": 3,
            "download_wifi_only": True,
            "content_filter": "Everyone",
        }
        settings.append(user_settings)

    # configure_by_dropdown fields
    if "theme" in request.form:
        user_settings["theme"] = request.form["theme"]
    if "language" in request.form:
        user_settings["language"] = request.form["language"]
    if "content_filter" in request.form:
        user_settings["content_filter"] = request.form["content_filter"]

    # configure_by_slider field
    if "notification_frequency" in request.form:
        freq = int(request.form["notification_frequency"])
        user_settings["notification_frequency"] = max(0, min(10, freq))

    # Checkboxes
    user_settings["auto_update"] = "auto_update" in request.form
    user_settings["download_wifi_only"] = "download_wifi_only" in request.form

    db.save_collection(SITE, "settings", settings)
    return redirect(url_for("software-marketplace.settings_page"))


@blueprint.route("/cart")
def cart_page():
    """Shopping cart page (add_by_button, checkout_by_form)."""
    if "user_id" not in session:
        return redirect(url_for("software-marketplace.login_page"))
    user = _get_user(session["user_id"])
    if not user:
        return redirect(url_for("software-marketplace.login_page"))

    cart = db.query(SITE, "cart", where={"user_id": session["user_id"]}, limit=50)
    cart_items = []
    total = 0.0
    for item in cart:
        app = _get_app(item["app_id"])
        if app:
            cart_items.append({"cart_id": item["id"], "app": app})
            total += app["price"]

    return render_template(
        "software-marketplace/cart.html",
        cart_items=cart_items, total=round(total, 2), user=user,
    )


@blueprint.route("/checkout", methods=["GET", "POST"])
def checkout_page():
    """Checkout page (checkout_by_form, redeem_by_code)."""
    if "user_id" not in session:
        return redirect(url_for("software-marketplace.login_page"))
    user = _get_user(session["user_id"])
    if not user:
        return redirect(url_for("software-marketplace.login_page"))

    cart = db.query(SITE, "cart", where={"user_id": session["user_id"]}, limit=50)
    cart_items = []
    subtotal = 0.0
    for item in cart:
        app = _get_app(item["app_id"])
        if app:
            cart_items.append({"cart_id": item["id"], "app": app})
            subtotal += app["price"]
    subtotal = round(subtotal, 2)

    promo_error = None
    promo_applied = None
    discount = 0.0

    if request.method == "POST":
        action = request.form.get("action", "")

        if action == "apply_promo":
            code = request.form.get("promo_code", "").strip().upper()
            promos = db.query(SITE, "promo_codes")  # small table
            promo = next((p for p in promos if p["code"] == code), None)
            if not promo:
                promo_error = "Invalid promo code"
            elif not promo["active"]:
                promo_error = "This promo code has expired"
            elif promo["uses"] >= promo["max_uses"]:
                promo_error = "This promo code has reached its usage limit"
            else:
                promo_applied = promo
                discount = round(subtotal * promo["discount_percent"] / 100, 2)

        elif action == "complete_purchase":
            promo_code = request.form.get("applied_promo", "").strip().upper()
            card_name = request.form.get("card_name", "").strip()
            card_number = request.form.get("card_number", "").strip()
            card_expiry = request.form.get("card_expiry", "").strip()

            if not card_name or not card_number or not card_expiry:
                return render_template(
                    "software-marketplace/checkout.html",
                    cart_items=cart_items, subtotal=subtotal,
                    discount=0.0, total=subtotal,
                    promo_error="Please fill in all payment fields",
                    promo_applied=None, user=user,
                )

            actual_discount = 0.0
            if promo_code:
                promos = db.query(SITE, "promo_codes")
                promo = next((p for p in promos if p["code"] == promo_code), None)
                if promo and promo["active"] and promo["uses"] < promo["max_uses"]:
                    actual_discount = round(subtotal * promo["discount_percent"] / 100, 2)
                    promo["uses"] += 1
                    db.save_collection(SITE, "promo_codes", promos)

            final_total = round(max(0, subtotal - actual_discount), 2)

            # Loose charge: any card number is accepted, but a recognized
            # SecureBank card must carry the correct CVV (else declined).
            from app.bank_charges import charge_card
            pay = charge_card(card_number, request.form.get("cvv", ""), card_expiry,
                              final_total, "Meridian App Store", category="software",
                              description="App Store purchase", strict=False)
            if not pay["ok"]:
                return render_template(
                    "software-marketplace/checkout.html",
                    cart_items=cart_items, subtotal=subtotal,
                    discount=actual_discount, total=final_total,
                    promo_error=pay["error"], promo_applied=None, user=user,
                )

            purchases = db.query(SITE, "purchases") if db.get_table_name(SITE, "purchases") else []
            installed = db.query(SITE, "installed")
            new_purchase_id = max((p["id"] for p in purchases), default=0) + 1

            purchased_app_ids = []
            for item in cart_items:
                purchases.append({
                    "id": new_purchase_id,
                    "user_id": session["user_id"],
                    "app_id": item["app"]["id"],
                    "app_name": item["app"]["name"],
                    "price": item["app"]["price"],
                    "discount": actual_discount,
                    "promo_code": promo_code or None,
                    "date": datetime.datetime.now().strftime("%Y-%m-%d"),
                })
                new_purchase_id += 1
                purchased_app_ids.append(item["app"]["id"])

                already = any(
                    i["user_id"] == session["user_id"] and i["app_id"] == item["app"]["id"]
                    for i in installed
                )
                if not already:
                    new_install_id = max((i["id"] for i in installed), default=0) + 1
                    installed.append({
                        "id": new_install_id,
                        "user_id": session["user_id"],
                        "app_id": item["app"]["id"],
                        "installed_date": datetime.datetime.now().strftime("%Y-%m-%d"),
                    })

            if db.get_table_name(SITE, "purchases"):
                db.save_collection(SITE, "purchases", purchases)
            db.save_collection(SITE, "installed", installed)

            # Clear cart
            all_cart = db.query(SITE, "cart")
            all_cart = [c for c in all_cart if c["user_id"] != session["user_id"]]
            db.save_collection(SITE, "cart", all_cart)

            emit("purchase", user_id=session["user_id"], amount=final_total, merchant="App Store", item=f"{len(purchased_app_ids)} app(s)")

            return render_template(
                "software-marketplace/checkout_success.html",
                purchased_app_ids=purchased_app_ids,
                total=final_total, user=user,
            )

    total = round(max(0, subtotal - discount), 2)
    return render_template(
        "software-marketplace/checkout.html",
        cart_items=cart_items, subtotal=subtotal,
        discount=discount, total=total,
        promo_error=promo_error, promo_applied=promo_applied,
        user=user,
    )


@blueprint.route("/wishlist")
def wishlist_page():
    """User's wishlisted apps (save_by_toggle)."""
    if "user_id" not in session:
        return redirect(url_for("software-marketplace.login_page"))
    user = _get_user(session["user_id"])
    if not user:
        return redirect(url_for("software-marketplace.login_page"))

    wishlists = db.query(SITE, "wishlists", where={"user_id": session["user_id"]}, limit=50)
    wishlist_apps = []
    for w in wishlists:
        app = _get_app(w["app_id"])
        if app:
            wishlist_apps.append({"app": app, "added_date": w["added_date"]})

    return render_template(
        "software-marketplace/wishlist.html",
        wishlist_apps=wishlist_apps, user=user,
    )


@blueprint.route("/my-apps")
def my_apps():
    """User's installed apps."""
    if "user_id" not in session:
        return redirect(url_for("software-marketplace.login_page"))
    user = _get_user(session["user_id"])
    if not user:
        return redirect(url_for("software-marketplace.login_page"))

    installed = db.query(
        SITE, "installed", where={"user_id": session["user_id"]},
        sort="-installed_date", limit=50,
    )
    installed_apps = []
    for inst in installed:
        app = _get_app(inst["app_id"])
        if app:
            installed_apps.append({
                "app": app,
                "installed_date": inst["installed_date"],
                "install_id": inst["id"],
            })

    return render_template(
        "software-marketplace/my_apps.html",
        installed_apps=installed_apps, user=user,
    )


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("software-marketplace/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = db.query(SITE, "users")  # small table
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return render_template("software-marketplace/login.html",
                               error="Invalid username or password")
    session["user_id"] = user["id"]
    emit("signup", user_id=user["id"], site_name="software-marketplace", username=request.form.get("username", ""), password=request.form.get("password", ""), email="")
    return redirect(url_for("software-marketplace.index"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("software-marketplace.index"))


# ---------------------------------------------------------------------------
# Form-based mutation routes (for HTML forms)
# ---------------------------------------------------------------------------

@blueprint.route("/install/<int:app_id>", methods=["POST"])
def form_install(app_id):
    if "user_id" not in session:
        return redirect(url_for("software-marketplace.login_page"))
    app = _get_app(app_id)
    if not app:
        abort(404)

    installed = db.query(SITE, "installed")
    already = any(
        i["user_id"] == session["user_id"] and i["app_id"] == app_id
        for i in installed
    )
    # Only record + emit on a genuinely new install so repeat installs by the
    # same user never double-count toward the installed total.
    if not already:
        new_id = max((i["id"] for i in installed), default=0) + 1
        installed.append({
            "id": new_id,
            "user_id": session["user_id"],
            "app_id": app_id,
            "installed_date": datetime.datetime.now().strftime("%Y-%m-%d"),
        })
        db.save_collection(SITE, "installed", installed)
        _add_email(session["user_id"], "noreply@software-marketplace.lakeport.local",
                   "Installation confirmed",
                   f'"{app["name"]}" has been installed successfully.')
        emit(
            "file_created",
            user_id=session["user_id"],
            filename=app["name"],
            file_type="app",
            source_site=SITE,
            source_id=str(app_id),
        )

    # Redirect back re-renders the detail page in its installed state, giving
    # immediate feedback without a manual refresh.
    return redirect(url_for("software-marketplace.app_detail", app_id=app_id))


@blueprint.route("/uninstall/<int:app_id>", methods=["POST"])
def form_uninstall(app_id):
    if "user_id" not in session:
        return redirect(url_for("software-marketplace.login_page"))

    installed = db.query(SITE, "installed")
    installed = [
        i for i in installed
        if not (i["user_id"] == session["user_id"] and i["app_id"] == app_id)
    ]
    db.save_collection(SITE, "installed", installed)

    redirect_to = request.form.get("redirect_to", "")
    if redirect_to:
        return redirect(redirect_to)
    return redirect(url_for("software-marketplace.app_detail", app_id=app_id))


@blueprint.route("/review/<int:app_id>", methods=["POST"])
def form_submit_review(app_id):
    """Submit review (rate_by_slider -- accepts slider or select rating)."""
    if "user_id" not in session:
        return redirect(url_for("software-marketplace.login_page"))
    app = _get_app(app_id)
    if not app:
        abort(404)

    rating = request.form.get("rating", type=int)
    text = request.form.get("text", "").strip()
    if not rating or not text:
        return redirect(url_for("software-marketplace.app_detail", app_id=app_id))

    reviews = db.query(SITE, "reviews")
    new_id = max((r["id"] for r in reviews), default=0) + 1
    reviews.append({
        "id": new_id,
        "app_id": app_id,
        "user_id": session["user_id"],
        "rating": min(max(rating, 1), 5),
        "text": text,
        "date": datetime.datetime.now().strftime("%Y-%m-%d"),
        "helpful_count": 0,
    })
    db.save_collection(SITE, "reviews", reviews)
    return redirect(url_for("software-marketplace.app_detail", app_id=app_id))


@blueprint.route("/cart/add/<int:app_id>", methods=["POST"])
def form_add_to_cart(app_id):
    """Add app to cart (add_by_button)."""
    if "user_id" not in session:
        return redirect(url_for("software-marketplace.login_page"))
    app = _get_app(app_id)
    if not app:
        abort(404)

    cart = db.query(SITE, "cart") if db.get_table_name(SITE, "cart") else []
    already = any(
        c["user_id"] == session["user_id"] and c["app_id"] == app_id
        for c in cart
    )
    if not already:
        new_id = max((c["id"] for c in cart), default=0) + 1
        cart.append({
            "id": new_id,
            "user_id": session["user_id"],
            "app_id": app_id,
            "added_date": datetime.datetime.now().strftime("%Y-%m-%d"),
        })
        db.save_collection(SITE, "cart", cart)

    redirect_to = request.form.get("redirect_to", "")
    if redirect_to:
        return redirect(redirect_to)
    return redirect(url_for("software-marketplace.app_detail", app_id=app_id))


@blueprint.route("/cart/remove/<int:app_id>", methods=["POST"])
def form_remove_from_cart(app_id):
    """Remove app from cart."""
    if "user_id" not in session:
        return redirect(url_for("software-marketplace.login_page"))

    cart = db.query(SITE, "cart") if db.get_table_name(SITE, "cart") else []
    cart = [
        c for c in cart
        if not (c["user_id"] == session["user_id"] and c["app_id"] == app_id)
    ]
    db.save_collection(SITE, "cart", cart)

    return redirect(url_for("software-marketplace.cart_page"))


@blueprint.route("/wishlist/toggle/<int:app_id>", methods=["POST"])
def form_toggle_wishlist(app_id):
    """Toggle wishlist (save_by_toggle)."""
    if "user_id" not in session:
        return redirect(url_for("software-marketplace.login_page"))
    app = _get_app(app_id)
    if not app:
        abort(404)

    wishlists = db.query(SITE, "wishlists")
    existing = next(
        (w for w in wishlists
         if w["user_id"] == session["user_id"] and w["app_id"] == app_id),
        None,
    )
    if existing:
        wishlists = [w for w in wishlists if w["id"] != existing["id"]]
        db.save_collection(SITE, "wishlists", wishlists)
    else:
        new_id = max((w["id"] for w in wishlists), default=0) + 1
        wishlists.append({
            "id": new_id,
            "user_id": session["user_id"],
            "app_id": app_id,
            "added_date": datetime.datetime.now().strftime("%Y-%m-%d"),
        })
        db.save_collection(SITE, "wishlists", wishlists)

    redirect_to = request.form.get("redirect_to", "")
    if redirect_to:
        return redirect(redirect_to)
    return redirect(url_for("software-marketplace.app_detail", app_id=app_id))


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/login", methods=["POST"])
def api_login():
    """API login."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    users = db.query(SITE, "users")
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return jsonify({"error": "Invalid credentials"}), 401
    session["user_id"] = user["id"]
    return jsonify({"user_id": user["id"], "display_name": user["display_name"]})


@blueprint.route("/api/apps")
def api_apps():
    """GET apps with optional filters: q, category, genre, min_rating, max_price, price, sort, limit."""
    q = request.args.get("q", "").strip()
    cat = request.args.get("category", "").strip()
    genre = request.args.get("genre", "").strip()
    min_rating = request.args.get("min_rating", type=float)
    max_price = request.args.get("max_price", type=float)
    price_type = request.args.get("price", "").strip()
    sort = request.args.get("sort", "").strip() or "reviews"
    limit = request.args.get("limit", 24, type=int)
    offset = request.args.get("offset", 0, type=int)

    apps, total = _query_apps(
        category=cat or None, genre=genre or None,
        min_rating=min_rating, max_price=max_price,
        price_type=price_type or None, sort=sort,
        q=q or None, limit=min(limit, 100), offset=offset,
    )
    return jsonify({"apps": apps, "total": total})


@blueprint.route("/api/apps/semantic")
def api_semantic_search():
    """Semantic search over app descriptions (search_by_semantic).

    Uses keyword-overlap: each word is searched with OR logic so
    multi-word queries like 'social media chat messaging' return
    results matching any of those terms.
    """
    q = request.args.get("q", "").strip()
    limit = request.args.get("limit", 24, type=int)
    offset = request.args.get("offset", 0, type=int)

    if not q:
        return jsonify([])

    # For semantic search, try each term individually and merge results
    terms = q.split()
    if len(terms) <= 1:
        results = db.search(SITE, "apps", q, limit=min(limit, 100), offset=offset)
    else:
        seen_ids = set()
        results = []
        for term in terms:
            hits = db.search(SITE, "apps", term, limit=100)
            for hit in hits:
                if hit["id"] not in seen_ids:
                    seen_ids.add(hit["id"])
                    results.append(hit)
        results = results[offset:offset + min(limit, 100)]
    return jsonify(results)


@blueprint.route("/api/apps/<int:app_id>")
def api_app(app_id):
    """GET single app by ID (extract_by_route)."""
    app = _get_app(app_id)
    if not app:
        abort(404)
    return jsonify(app)


@blueprint.route("/api/compare")
def api_compare():
    """Compare apps side-by-side (compare_from_table, extract_from_table)."""
    ids_param = request.args.get("ids", "")
    app_ids = []
    for s in ids_param.split(","):
        s = s.strip()
        if s.isdigit():
            app_ids.append(int(s))

    results = []
    for aid in app_ids[:6]:
        app = _get_app(aid)
        if app:
            review_stats = db.execute(
                "SELECT COUNT(*) as cnt, COALESCE(AVG(rating), 0) as avg_r "
                "FROM software_marketplace_reviews WHERE app_id = ?",
                (aid,), fetch="one",
            )
            app_copy = dict(app)
            app_copy["avg_user_rating"] = round(review_stats["avg_r"], 1) if review_stats else 0
            app_copy["review_count_actual"] = review_stats["cnt"] if review_stats else 0
            results.append(app_copy)

    return jsonify(results)


@blueprint.route("/api/apps/<int:app_id>/install", methods=["POST"])
def api_install(app_id):
    """POST install an app for the current user (or user_id in body)."""
    app = _get_app(app_id)
    if not app:
        abort(404)

    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id") or session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    installed = db.query(SITE, "installed")
    already = any(
        i["user_id"] == user_id and i["app_id"] == app_id
        for i in installed
    )
    if already:
        return jsonify({"error": "App already installed"}), 409

    new_id = max((i["id"] for i in installed), default=0) + 1
    record = {
        "id": new_id,
        "user_id": user_id,
        "app_id": app_id,
        "installed_date": datetime.datetime.now().strftime("%Y-%m-%d"),
    }
    installed.append(record)
    db.save_collection(SITE, "installed", installed)
    return jsonify({"action": "installed", "record": record}), 201


@blueprint.route("/api/apps/<int:app_id>/uninstall", methods=["POST"])
def api_uninstall(app_id):
    """POST uninstall an app for the current user (or user_id in body)."""
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id") or session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    installed = db.query(SITE, "installed")
    before = len(installed)
    installed = [
        i for i in installed
        if not (i["user_id"] == user_id and i["app_id"] == app_id)
    ]
    if len(installed) == before:
        return jsonify({"error": "App not installed"}), 404

    db.save_collection(SITE, "installed", installed)
    return jsonify({"action": "uninstalled", "app_id": app_id})


@blueprint.route("/api/apps/<int:app_id>/reviews", methods=["GET"])
def api_app_reviews(app_id):
    """GET reviews for an app."""
    app = _get_app(app_id)
    if not app:
        abort(404)

    app_reviews = db.query(
        SITE, "reviews", where={"app_id": app_id},
        sort="-date", limit=50,
    )

    users = db.query(SITE, "users")
    user_map = {u["id"]: u["display_name"] for u in users}
    for r in app_reviews:
        r["user_name"] = user_map.get(r["user_id"], "Unknown")

    return jsonify(app_reviews)


@blueprint.route("/api/apps/<int:app_id>/reviews", methods=["POST"])
def api_add_review(app_id):
    """POST a new review for an app (rate_by_slider)."""
    app = _get_app(app_id)
    if not app:
        abort(404)

    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id") or session.get("user_id")
    rating = data.get("rating")
    text = data.get("text", "").strip()

    if not user_id:
        return jsonify({"error": "Not logged in"}), 401
    if not rating or not text:
        return jsonify({"error": "rating and text required"}), 400

    reviews = db.query(SITE, "reviews")
    new_id = max((r["id"] for r in reviews), default=0) + 1
    review = {
        "id": new_id,
        "app_id": app_id,
        "user_id": user_id,
        "rating": min(max(int(rating), 1), 5),
        "text": text,
        "date": datetime.datetime.now().strftime("%Y-%m-%d"),
        "helpful_count": 0,
    }
    reviews.append(review)
    db.save_collection(SITE, "reviews", reviews)
    return jsonify({"action": "created", "review": review}), 201


@blueprint.route("/api/reviews/<int:review_id>", methods=["DELETE"])
def api_delete_review(review_id):
    """DELETE a review by ID (only the author can delete)."""
    user_id = session.get("user_id")
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id", user_id)

    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    reviews = db.query(SITE, "reviews")
    review = next((r for r in reviews if r["id"] == review_id), None)
    if not review:
        return jsonify({"error": "Review not found"}), 404
    if review["user_id"] != user_id:
        return jsonify({"error": "Not authorized"}), 403

    reviews = [r for r in reviews if r["id"] != review_id]
    db.save_collection(SITE, "reviews", reviews)
    return jsonify({"action": "deleted", "review_id": review_id})


@blueprint.route("/api/categories")
def api_categories():
    """GET all categories with app counts."""
    categories = _get_categories_from_db()
    return jsonify([{"name": c, "count": n} for c, n in categories])


@blueprint.route("/api/categories/<cat>/apps")
def api_category_apps(cat):
    """GET apps in a specific category."""
    limit = request.args.get("limit", 24, type=int)
    offset = request.args.get("offset", 0, type=int)
    apps, total = _query_apps(category=cat, limit=min(limit, 100), offset=offset)
    return jsonify({"apps": apps, "total": total})


@blueprint.route("/api/genres")
def api_genres():
    """GET all genres with app counts."""
    genres = _get_genres_from_db()
    return jsonify([{"name": g, "count": n} for g, n in genres])


@blueprint.route("/api/installed")
def api_installed():
    """GET installed apps for current user (or user_id param)."""
    user_id = request.args.get("user_id", type=int) or session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    installed = db.query(SITE, "installed", where={"user_id": user_id}, limit=50)
    result = []
    for inst in installed:
        app = _get_app(inst["app_id"])
        if app:
            result.append({
                "install_id": inst["id"],
                "app_id": inst["app_id"],
                "app_name": app["name"],
                "app_category": app["category"],
                "installed_date": inst["installed_date"],
            })
    return jsonify(result)


@blueprint.route("/api/stats")
def api_stats():
    """GET aggregate statistics about the marketplace."""
    total_apps = db.execute(
        "SELECT COUNT(*) FROM software_marketplace_apps",
        fetch="val",
    ) or 0

    avg_rating = db.execute(
        "SELECT AVG(rating) FROM software_marketplace_apps WHERE rating > 0",
        fetch="val",
    ) or 0

    free_count = db.execute(
        "SELECT COUNT(*) FROM software_marketplace_apps WHERE price = 0",
        fetch="val",
    ) or 0

    paid_count = db.execute(
        "SELECT COUNT(*) FROM software_marketplace_apps WHERE price > 0",
        fetch="val",
    ) or 0

    avg_price = db.execute(
        "SELECT AVG(price) FROM software_marketplace_apps WHERE price > 0",
        fetch="val",
    ) or 0

    unique_devs = db.execute(
        "SELECT COUNT(DISTINCT developer) FROM software_marketplace_apps",
        fetch="val",
    ) or 0

    cat_counts = db.execute(
        "SELECT category, COUNT(*) as cnt FROM software_marketplace_apps "
        "GROUP BY category ORDER BY cnt DESC LIMIT 5",
        fetch="all",
    )

    total_reviews = db.count(SITE, "reviews")
    total_installs = db.count(SITE, "installed")

    return jsonify({
        "total_apps": total_apps,
        "total_reviews": total_reviews,
        "total_installs": total_installs,
        "categories": len(_get_categories_from_db()),
        "average_rating": round(avg_rating, 2),
        "free_apps": free_count,
        "paid_apps": paid_count,
        "average_paid_price": round(avg_price, 2),
        "unique_developers": unique_devs,
        "top_categories": [
            {"name": r["category"], "count": r["cnt"]}
            for r in cat_counts
        ],
    })


@blueprint.route("/api/export")
def api_export():
    """Export apps as CSV or JSON (export_by_dropdown)."""
    fmt = request.args.get("format", "json").strip().lower()
    cat = request.args.get("category", "").strip()
    limit = request.args.get("limit", 1000, type=int)

    apps, _ = _query_apps(category=cat or None, sort="reviews", limit=min(limit, 5000))

    if fmt == "csv":
        output = io.StringIO()
        if apps:
            fields = ["id", "name", "category", "genre", "rating",
                       "reviews_count", "price", "developer", "size",
                       "installs", "content_rating", "last_updated"]
            writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for app in apps:
                writer.writerow(app)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=apps.csv"},
        )
    else:
        return jsonify(apps)


@blueprint.route("/api/cart", methods=["GET"])
def api_cart():
    """GET cart items for a user."""
    user_id = request.args.get("user_id", type=int) or session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    cart = db.query(SITE, "cart", where={"user_id": user_id}, limit=50) if db.get_table_name(SITE, "cart") else []
    result = []
    total = 0.0
    for item in cart:
        app = _get_app(item["app_id"])
        if app:
            result.append({
                "cart_id": item["id"],
                "app_id": item["app_id"],
                "app_name": app["name"],
                "price": app["price"],
            })
            total += app["price"]

    return jsonify({"items": result, "total": round(total, 2)})


@blueprint.route("/api/cart/add", methods=["POST"])
def api_cart_add():
    """Add an app to cart (add_by_button)."""
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id") or session.get("user_id")
    app_id = data.get("app_id")

    if not user_id:
        return jsonify({"error": "Not logged in"}), 401
    if not app_id:
        return jsonify({"error": "app_id required"}), 400

    app = _get_app(app_id)
    if not app:
        return jsonify({"error": "App not found"}), 404

    cart = db.query(SITE, "cart") if db.get_table_name(SITE, "cart") else []
    already = any(
        c["user_id"] == user_id and c["app_id"] == app_id for c in cart
    )
    if already:
        return jsonify({"error": "App already in cart"}), 409

    new_id = max((c["id"] for c in cart), default=0) + 1
    record = {
        "id": new_id,
        "user_id": user_id,
        "app_id": app_id,
        "added_date": datetime.datetime.now().strftime("%Y-%m-%d"),
    }
    cart.append(record)
    db.save_collection(SITE, "cart", cart)
    return jsonify({"action": "added", "record": record}), 201


@blueprint.route("/api/cart/remove", methods=["POST"])
def api_cart_remove():
    """Remove an app from cart."""
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id") or session.get("user_id")
    app_id = data.get("app_id")

    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    cart = db.query(SITE, "cart") if db.get_table_name(SITE, "cart") else []
    before = len(cart)
    cart = [
        c for c in cart
        if not (c["user_id"] == user_id and c["app_id"] == app_id)
    ]
    if len(cart) == before:
        return jsonify({"error": "App not in cart"}), 404

    db.save_collection(SITE, "cart", cart)
    return jsonify({"action": "removed", "app_id": app_id})


@blueprint.route("/api/checkout", methods=["POST"])
def api_checkout():
    """Process checkout (checkout_by_form)."""
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id") or session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    card_name = data.get("card_name", "").strip()
    card_number = data.get("card_number", "").strip()
    card_expiry = data.get("card_expiry", "").strip()
    promo_code = data.get("promo_code", "").strip().upper()

    if not card_name or not card_number or not card_expiry:
        return jsonify({"error": "Payment details required"}), 400

    cart = db.query(SITE, "cart", where={"user_id": user_id}, limit=50) if db.get_table_name(SITE, "cart") else []
    if not cart:
        return jsonify({"error": "Cart is empty"}), 400

    subtotal = 0.0
    for c in cart:
        app = _get_app(c["app_id"])
        if app:
            subtotal += app["price"]

    discount = 0.0
    if promo_code:
        promos = db.query(SITE, "promo_codes")
        promo = next((p for p in promos if p["code"] == promo_code), None)
        if promo and promo["active"] and promo["uses"] < promo["max_uses"]:
            discount = round(subtotal * promo["discount_percent"] / 100, 2)
            promo["uses"] += 1
            db.save_collection(SITE, "promo_codes", promos)

    final_total = round(max(0, subtotal - discount), 2)

    purchases = db.query(SITE, "purchases") if db.get_table_name(SITE, "purchases") else []
    installed = db.query(SITE, "installed")
    new_purchase_id = max((p["id"] for p in purchases), default=0) + 1

    purchased = []
    for item in cart:
        app = _get_app(item["app_id"])
        if app:
            purchases.append({
                "id": new_purchase_id,
                "user_id": user_id,
                "app_id": app["id"],
                "app_name": app["name"],
                "price": app["price"],
                "discount": discount,
                "promo_code": promo_code or None,
                "date": datetime.datetime.now().strftime("%Y-%m-%d"),
            })
            purchased.append(app["id"])
            new_purchase_id += 1

            already = any(
                i["user_id"] == user_id and i["app_id"] == app["id"]
                for i in installed
            )
            if not already:
                new_install_id = max((i["id"] for i in installed), default=0) + 1
                installed.append({
                    "id": new_install_id,
                    "user_id": user_id,
                    "app_id": app["id"],
                    "installed_date": datetime.datetime.now().strftime("%Y-%m-%d"),
                })

    if db.get_table_name(SITE, "purchases"):
        db.save_collection(SITE, "purchases", purchases)
    db.save_collection(SITE, "installed", installed)

    all_cart = db.query(SITE, "cart") if db.get_table_name(SITE, "cart") else []
    all_cart = [c for c in all_cart if c["user_id"] != user_id]
    db.save_collection(SITE, "cart", all_cart)

    emit("purchase", user_id=user_id, amount=final_total, merchant="App Store", item=f"{len(purchased)} app(s)")

    return jsonify({
        "action": "purchased",
        "purchased_app_ids": purchased,
        "subtotal": round(subtotal, 2),
        "discount": discount,
        "total": final_total,
    })


@blueprint.route("/api/wishlist", methods=["GET"])
def api_wishlist():
    """GET wishlist for a user (save_by_toggle)."""
    user_id = request.args.get("user_id", type=int) or session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    wishlists = db.query(SITE, "wishlists", where={"user_id": user_id}, limit=50)
    result = []
    for w in wishlists:
        app = _get_app(w["app_id"])
        if app:
            result.append({
                "wishlist_id": w["id"],
                "app_id": w["app_id"],
                "app_name": app["name"],
                "added_date": w["added_date"],
            })
    return jsonify(result)


@blueprint.route("/api/wishlist/toggle", methods=["POST"])
def api_wishlist_toggle():
    """Toggle app in wishlist (save_by_toggle)."""
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id") or session.get("user_id")
    app_id = data.get("app_id")

    if not user_id:
        return jsonify({"error": "Not logged in"}), 401
    if not app_id:
        return jsonify({"error": "app_id required"}), 400

    wishlists = db.query(SITE, "wishlists")
    existing = next(
        (w for w in wishlists
         if w["user_id"] == user_id and w["app_id"] == app_id),
        None,
    )

    if existing:
        wishlists = [w for w in wishlists if w["id"] != existing["id"]]
        db.save_collection(SITE, "wishlists", wishlists)
        return jsonify({"action": "removed", "app_id": app_id})
    else:
        new_id = max((w["id"] for w in wishlists), default=0) + 1
        record = {
            "id": new_id,
            "user_id": user_id,
            "app_id": app_id,
            "added_date": datetime.datetime.now().strftime("%Y-%m-%d"),
        }
        wishlists.append(record)
        db.save_collection(SITE, "wishlists", wishlists)
        return jsonify({"action": "saved", "record": record}), 201


@blueprint.route("/api/promo/validate", methods=["POST"])
def api_promo_validate():
    """Validate a promo code (redeem_by_code)."""
    data = request.get_json(silent=True) or {}
    code = data.get("code", "").strip().upper()

    if not code:
        return jsonify({"error": "Code required"}), 400

    promos = db.query(SITE, "promo_codes")
    promo = next((p for p in promos if p["code"] == code), None)

    if not promo:
        return jsonify({"valid": False, "error": "Invalid promo code"}), 404
    if not promo["active"]:
        return jsonify({"valid": False, "error": "Promo code has expired"}), 410
    if promo["uses"] >= promo["max_uses"]:
        return jsonify({"valid": False, "error": "Promo code usage limit reached"}), 410

    return jsonify({
        "valid": True,
        "code": promo["code"],
        "discount_percent": promo["discount_percent"],
        "description": promo["description"],
    })


@blueprint.route("/api/settings", methods=["GET"])
def api_settings_get():
    """GET user settings (configure_by_dropdown, configure_by_slider)."""
    user_id = request.args.get("user_id", type=int) or session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401
    return jsonify(_get_user_settings(user_id))


@blueprint.route("/api/settings", methods=["POST"])
def api_settings_update():
    """Update user settings (configure_by_dropdown, configure_by_slider)."""
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id") or session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    settings = db.query(SITE, "settings")
    user_settings = next(
        (s for s in settings if s["user_id"] == user_id), None
    )
    if not user_settings:
        user_settings = _get_user_settings(user_id)
        settings.append(user_settings)

    allowed_fields = {"theme", "language", "auto_update",
                      "notification_frequency", "download_wifi_only",
                      "content_filter"}
    for key in allowed_fields:
        if key in data:
            if key == "notification_frequency":
                user_settings[key] = max(0, min(10, int(data[key])))
            else:
                user_settings[key] = data[key]

    db.save_collection(SITE, "settings", settings)
    return jsonify({"action": "updated", "settings": user_settings})


@blueprint.route("/api/purchases")
def api_purchases():
    """GET purchase history for a user."""
    user_id = request.args.get("user_id", type=int) or session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    purchases = db.query(SITE, "purchases", where={"user_id": user_id}, limit=50) if db.get_table_name(SITE, "purchases") else []
    return jsonify(purchases)
