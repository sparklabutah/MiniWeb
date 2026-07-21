"""Real Estate Buy/Rent -- Zillow/Redfin-style property listings platform.

Browse, search, and filter residential property listings for sale and rent
in Lakeport, WA. Supports saving listings, sending inquiries to agents,
and viewing market statistics.
"""
import pathlib
from datetime import datetime

from flask import (
    Blueprint, abort, jsonify, redirect, render_template, request,
    session, url_for,
)

from app import db
from app.events import emit

SITE = "real-estate-buy-rent"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "real-estate-buy-rent",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

_property_types = ["house", "apartment", "condo", "townhouse"]
_statuses = ["for_sale", "for_rent", "sold", "rented"]


_LISTINGS_TABLE = "real_estate_buy_rent_listings"


def _query_listings(q="", prop_type="", status="", price_min=None, price_max=None,
                    beds_min=None, baths_min=None, sqft_min=None,
                    sort="date", limit=50, offset=0, features=None,
                    count_only=False):
    """Query listings with all filters in SQL."""
    if q:
        results = db.search(SITE, "listings", q, limit=limit)
        # Post-filter for additional constraints on small FTS result set
        if prop_type:
            results = [l for l in results if l.get("type") == prop_type]
        if status:
            results = [l for l in results if l.get("status") == status]
        if features:
            results = [l for l in results
                       if all(f.lower() in str(l.get("features", "")).lower()
                              for f in features)]
        return len(results) if count_only else results

    clauses = []
    params = []
    if prop_type:
        clauses.append("[type] = ?")
        params.append(prop_type)
    if status:
        clauses.append("[status] = ?")
        params.append(status)
    if price_min is not None:
        clauses.append("[price] >= ?")
        params.append(price_min)
    if price_max is not None:
        clauses.append("[price] <= ?")
        params.append(price_max)
    if beds_min is not None:
        clauses.append("[bedrooms] >= ?")
        params.append(beds_min)
    if baths_min is not None:
        clauses.append("[bathrooms] >= ?")
        params.append(baths_min)
    if sqft_min is not None:
        clauses.append("[sqft] >= ?")
        params.append(sqft_min)
    for feat in (features or []):
        clauses.append("LOWER([features]) LIKE ?")
        params.append(f"%{feat.lower()}%")

    sort_map = {
        "date": "[listed_date] DESC",
        "price_low": "[price] ASC",
        "price_high": "[price] DESC",
        "sqft": "[sqft] DESC",
        "beds": "[bedrooms] DESC",
    }
    order = sort_map.get(sort, "[listed_date] DESC")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    if count_only:
        return db.execute(f"SELECT COUNT(*) FROM [{_LISTINGS_TABLE}]{where}",
                          tuple(params), fetch="val")
    sql = f"SELECT * FROM [{_LISTINGS_TABLE}]{where} ORDER BY {order} LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    return db.execute(sql, tuple(params))


def _load_agents():
    return db.query(SITE, "agents")


def _get_agent(agent_id):
    return db.get_item(SITE, "agents", agent_id)


def _load_users():
    return db.query(SITE, "users")


def _save_users(users):
    db.save_collection(SITE, "users", users)


def _get_user(user_id):
    return db.get_item(SITE, "users", user_id)


def _load_saved():
    return db.query(SITE, "saved")


def _save_saved(data):
    db.save_collection(SITE, "saved", data)


def _load_inquiries():
    return db.query(SITE, "inquiries")


def _save_inquiries(data):
    db.save_collection(SITE, "inquiries", data)



# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    """Homepage with featured listings."""
    featured_sale = _query_listings(status="for_sale", sort="price_high", limit=4)
    featured_rent = _query_listings(status="for_rent", sort="price_high", limit=4)

    stats = db.execute(
        f"SELECT [status], COUNT(*) as cnt, AVG(price) as avg_p "
        f"FROM [{_LISTINGS_TABLE}] WHERE [status] IN ('for_sale','for_rent') "
        f"GROUP BY [status]")
    sale_stats = next((r for r in stats if r["status"] == "for_sale"), None)
    rent_stats = next((r for r in stats if r["status"] == "for_rent"), None)

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template("real-estate-buy-rent/index.html",
                           featured_sale=featured_sale,
                           featured_rent=featured_rent,
                           for_sale_count=sale_stats["cnt"] if sale_stats else 0,
                           for_rent_count=rent_stats["cnt"] if rent_stats else 0,
                           avg_sale=round(sale_stats["avg_p"]) if sale_stats else 0,
                           avg_rent=round(rent_stats["avg_p"]) if rent_stats else 0,
                           property_types=_property_types,
                           user=user)


@blueprint.route("/listings")
def listings_page():
    """Search and filter listings."""
    q = request.args.get("q", "").strip()
    prop_type = request.args.get("type", "").strip()
    status = request.args.get("status", "").strip()
    price_min = request.args.get("price_min", type=int)
    price_max = request.args.get("price_max", type=int)
    beds_min = request.args.get("beds", type=int)
    baths_min = request.args.get("baths", type=int)
    sqft_min = request.args.get("sqft_min", type=int)
    features = [f for f in request.args.getlist("features") if f.strip()]
    sort = request.args.get("sort", "date").strip()

    results = _query_listings(q=q, prop_type=prop_type, status=status,
                              price_min=price_min, price_max=price_max,
                              beds_min=beds_min, baths_min=baths_min,
                              sqft_min=sqft_min, sort=sort, limit=50,
                              features=features)
    total = _query_listings(q=q, prop_type=prop_type, status=status,
                            price_min=price_min, price_max=price_max,
                            beds_min=beds_min, baths_min=baths_min,
                            sqft_min=sqft_min, features=features,
                            count_only=True)

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template("real-estate-buy-rent/listings.html",
                           listings=results, total=total,
                           property_types=_property_types,
                           statuses=_statuses,
                           q=q, prop_type=prop_type, status=status,
                           price_min=price_min, price_max=price_max,
                           beds_min=beds_min, baths_min=baths_min,
                           sqft_min=sqft_min, sort=sort,
                           user=user)


@blueprint.route("/listing/<int:listing_id>")
def listing_detail(listing_id):
    """Single listing detail page."""
    listing = db.get_item(SITE, "listings", listing_id)
    if listing is None:
        abort(404)
    agent = _get_agent(listing.get("agent_id"))
    related = db.query(SITE, "listings", where={"type": listing["type"]}, limit=7)
    related = [l for l in related if l["id"] != listing_id and l.get("status") in ("for_sale", "for_rent")][:6]

    user = None
    is_saved = False
    if "user_id" in session:
        user = _get_user(session["user_id"])
        saved = _load_saved()
        is_saved = any(s["user_id"] == session["user_id"] and s["listing_id"] == listing_id
                       for s in saved)

    return render_template("real-estate-buy-rent/listing_detail.html",
                           listing=listing, agent=agent, related=related,
                           user=user, is_saved=is_saved)


@blueprint.route("/agents")
def agents_page():
    """All agents directory."""
    agents = _load_agents()
    for agent in agents:
        agent["active_listings"] = db.query(SITE, "listings",
                                            where={"agent_id": agent["id"]}, limit=10)
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("real-estate-buy-rent/agents.html",
                           agents=agents, user=user)


@blueprint.route("/agent/<int:agent_id>")
def agent_detail(agent_id):
    """Individual agent profile page."""
    agent = _get_agent(agent_id)
    if agent is None:
        abort(404)
    active = db.execute(
        f"SELECT * FROM [{_LISTINGS_TABLE}] WHERE [agent_id] = ? "
        f"AND [status] IN ('for_sale','for_rent') ORDER BY [listed_date] DESC LIMIT 50",
        (agent_id,))
    sold = db.execute(
        f"SELECT * FROM [{_LISTINGS_TABLE}] WHERE [agent_id] = ? "
        f"AND [status] IN ('sold','rented') ORDER BY [listed_date] DESC LIMIT 50",
        (agent_id,))
    user = None
    is_following = False
    if "user_id" in session:
        user = _get_user(session["user_id"])
        follow = db.get_item(SITE, "agent_follows",
                             f"{session['user_id']}-{agent_id}")
        is_following = bool(follow)
    return render_template("real-estate-buy-rent/agent_detail.html",
                           agent=agent, active_listings=active,
                           sold_listings=sold, user=user,
                           is_following=is_following)


@blueprint.route("/saved")
def saved_page():
    """User's saved listings."""
    if "user_id" not in session:
        return render_template("real-estate-buy-rent/login.html", error=None, mode="login")
    user = _get_user(session["user_id"])
    saved = _load_saved()
    user_saved = [s for s in saved if s["user_id"] == session["user_id"]]
    saved_listings = []
    for s in user_saved:
        listing = db.get_item(SITE, "listings", s["listing_id"])
        if listing:
            saved_listings.append({"saved": s, "listing": listing})
    return render_template("real-estate-buy-rent/saved.html",
                           saved_listings=saved_listings, user=user)


@blueprint.route("/inquiries")
def inquiries_page():
    """User's sent inquiries."""
    if "user_id" not in session:
        return render_template("real-estate-buy-rent/login.html", error=None, mode="login")
    user = _get_user(session["user_id"])
    inquiries = _load_inquiries()
    user_inquiries = [i for i in inquiries if i["user_id"] == session["user_id"]]
    enriched = []
    for inq in user_inquiries:
        listing = db.get_item(SITE, "listings", inq["listing_id"])
        enriched.append({"inquiry": inq, "listing": listing})
    return render_template("real-estate-buy-rent/inquiries.html",
                           inquiries=enriched, user=user)


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("real-estate-buy-rent/login.html", error=None, mode="login")


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return render_template("real-estate-buy-rent/login.html",
                               error="Invalid username or password", mode="login")
    session["user_id"] = user["id"]
    return redirect(url_for("real-estate-buy-rent.index"))


@blueprint.route("/register", methods=["GET"])
def register_page():
    return render_template("real-estate-buy-rent/login.html", error=None, mode="register")


@blueprint.route("/register", methods=["POST"])
def register_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()

    if not username or not password or not name or not email:
        return render_template("real-estate-buy-rent/login.html",
                               error="All fields are required", mode="register")

    users = _load_users()
    if any(u["username"] == username for u in users):
        return render_template("real-estate-buy-rent/login.html",
                               error="Username already taken", mode="register")

    new_id = max(u["id"] for u in users) + 1 if users else 1
    new_user = {
        "id": new_id,
        "username": username,
        "password": password,
        "name": name,
        "email": email,
        "phone": phone,
        "role": "buyer",
        "bio": "",
        "member_since": datetime.now().strftime("%Y-%m-%d"),
    }
    users.append(new_user)
    _save_users(users)
    emit("signup", user_id=new_id, site_name="real-estate-buy-rent",
         username=username, password=password, email=email)
    session["user_id"] = new_user["id"]
    return redirect(url_for("real-estate-buy-rent.index"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("real-estate-buy-rent.index"))


@blueprint.route("/agent/<int:agent_id>/follow", methods=["POST"])
def follow_agent(agent_id):
    """Toggle following an agent (session-overlay collection)."""
    if "user_id" not in session:
        return render_template("real-estate-buy-rent/login.html", error=None, mode="login")
    if _get_agent(agent_id) is None:
        abort(404)
    key = f"{session['user_id']}-{agent_id}"
    if db.get_item(SITE, "agent_follows", key):
        db.delete_item(SITE, "agent_follows", key)
    else:
        db.save_item(SITE, "agent_follows", key, {
            "id": key, "user_id": session["user_id"], "agent_id": agent_id,
            "followed_date": datetime.now().strftime("%Y-%m-%d"),
        })
    return redirect(url_for("real-estate-buy-rent.agent_detail", agent_id=agent_id))


@blueprint.route("/listing/<int:listing_id>/save", methods=["POST"])
def save_listing(listing_id):
    if "user_id" not in session:
        return render_template("real-estate-buy-rent/login.html", error=None, mode="login")
    saved = _load_saved()
    existing = next((s for s in saved
                     if s["user_id"] == session["user_id"] and s["listing_id"] == listing_id), None)
    if existing:
        saved.remove(existing)
    else:
        new_id = max(s["id"] for s in saved) + 1 if saved else 1
        saved.append({
            "id": new_id,
            "user_id": session["user_id"],
            "listing_id": listing_id,
            "saved_date": datetime.now().strftime("%Y-%m-%d"),
            "notes": "",
        })
    _save_saved(saved)
    return redirect(url_for("real-estate-buy-rent.listing_detail", listing_id=listing_id))


@blueprint.route("/listing/<int:listing_id>/inquiry", methods=["POST"])
def submit_inquiry(listing_id):
    if "user_id" not in session:
        return render_template("real-estate-buy-rent/login.html", error=None, mode="login")
    inquiries = _load_inquiries()
    new_id = max(i["id"] for i in inquiries) + 1 if inquiries else 1
    inquiries.append({
        "id": new_id,
        "user_id": session["user_id"],
        "listing_id": listing_id,
        "message": request.form.get("message", "").strip(),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "status": "pending",
    })
    _save_inquiries(inquiries)
    listing = db.get_item(SITE, "listings", listing_id)
    if listing:
        emit("booking", user_id=session["user_id"], title=f"Property viewing: {listing.get('address', 'Listing')}", start=datetime.now().strftime("%Y-%m-%d"), location=listing.get("address", ""))
    return redirect(url_for("real-estate-buy-rent.listing_detail", listing_id=listing_id))


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/listings")
def api_listings():
    q = request.args.get("q", "").strip()
    prop_type = request.args.get("type", "").strip()
    status = request.args.get("status", "").strip()
    price_min = request.args.get("price_min", type=int)
    price_max = request.args.get("price_max", type=int)
    beds_min = request.args.get("beds", type=int)
    baths_min = request.args.get("baths", type=int)
    sqft_min = request.args.get("sqft_min", type=int)
    sort = request.args.get("sort", "date")
    limit = request.args.get("limit", 50, type=int)

    results = _query_listings(q=q, prop_type=prop_type, status=status,
                              price_min=price_min, price_max=price_max,
                              beds_min=beds_min, baths_min=baths_min,
                              sqft_min=sqft_min, sort=sort, limit=min(limit, 200))
    return jsonify(results)


@blueprint.route("/api/listings/<int:listing_id>")
def api_listing(listing_id):
    listing = db.get_item(SITE, "listings", listing_id)
    if listing is None:
        abort(404)
    return jsonify(listing)


@blueprint.route("/api/agents")
def api_agents():
    agents = _load_agents()
    return jsonify(agents)


@blueprint.route("/api/agents/<int:agent_id>")
def api_agent(agent_id):
    agent = _get_agent(agent_id)
    if agent is None:
        abort(404)
    agent_listings = db.query(SITE, "listings", where={"agent_id": agent_id}, limit=50)
    result = dict(agent)
    result["listings"] = agent_listings
    return jsonify(result)


@blueprint.route("/api/saved", methods=["GET"])
def api_saved_get():
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    saved = _load_saved()
    user_saved = [s for s in saved if s["user_id"] == session["user_id"]]
    return jsonify(user_saved)


@blueprint.route("/api/saved", methods=["POST"])
def api_saved_post():
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json(silent=True) or {}
    listing_id = data.get("listing_id")
    if listing_id is None:
        return jsonify({"error": "listing_id required"}), 400

    saved = _load_saved()
    existing = next((s for s in saved
                     if s["user_id"] == session["user_id"] and s["listing_id"] == listing_id), None)
    if existing:
        return jsonify({"error": "Already saved", "saved": existing}), 409

    new_id = max(s["id"] for s in saved) + 1 if saved else 1
    new_saved = {
        "id": new_id,
        "user_id": session["user_id"],
        "listing_id": listing_id,
        "saved_date": datetime.now().strftime("%Y-%m-%d"),
        "notes": data.get("notes", ""),
    }
    saved.append(new_saved)
    _save_saved(saved)
    return jsonify(new_saved), 201


@blueprint.route("/api/saved", methods=["DELETE"])
def api_saved_delete():
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json(silent=True) or {}
    listing_id = data.get("listing_id")
    if listing_id is None:
        return jsonify({"error": "listing_id required"}), 400

    saved = _load_saved()
    before = len(saved)
    saved = [s for s in saved
             if not (s["user_id"] == session["user_id"] and s["listing_id"] == listing_id)]
    if len(saved) == before:
        return jsonify({"error": "Not found"}), 404
    _save_saved(saved)
    return jsonify({"action": "deleted", "listing_id": listing_id})


@blueprint.route("/api/inquiries", methods=["GET"])
def api_inquiries_get():
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    inquiries = _load_inquiries()
    user_inquiries = [i for i in inquiries if i["user_id"] == session["user_id"]]
    return jsonify(user_inquiries)


@blueprint.route("/api/inquiries", methods=["POST"])
def api_inquiries_post():
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json(silent=True) or {}
    listing_id = data.get("listing_id")
    message = data.get("message", "").strip()
    if not listing_id or not message:
        return jsonify({"error": "listing_id and message required"}), 400

    inquiries = _load_inquiries()
    new_id = max(i["id"] for i in inquiries) + 1 if inquiries else 1
    new_inquiry = {
        "id": new_id,
        "user_id": session["user_id"],
        "listing_id": listing_id,
        "message": message,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "status": "pending",
    }
    inquiries.append(new_inquiry)
    _save_inquiries(inquiries)
    return jsonify(new_inquiry), 201


@blueprint.route("/api/stats")
def api_stats():
    # Status counts
    status_rows = db.execute(
        f"SELECT [status], COUNT(*) as cnt FROM [{_LISTINGS_TABLE}] GROUP BY [status]")
    by_status = {r["status"]: r["cnt"] for r in status_rows}
    total = sum(by_status.values())

    # Sale price stats
    sale_row = db.execute(
        f"SELECT COUNT(*) as cnt, AVG([price]) as avg_p, MIN([price]) as min_p, MAX([price]) as max_p "
        f"FROM [{_LISTINGS_TABLE}] WHERE [status] = 'for_sale' AND [price] > 0",
        fetch="one")

    # Rent price stats
    rent_row = db.execute(
        f"SELECT COUNT(*) as cnt, AVG([price]) as avg_p, MIN([price]) as min_p, MAX([price]) as max_p "
        f"FROM [{_LISTINGS_TABLE}] WHERE [status] = 'for_rent' AND [price] > 0",
        fetch="one")

    # Type counts
    type_rows = db.execute(
        f"SELECT [type], COUNT(*) as cnt FROM [{_LISTINGS_TABLE}] GROUP BY [type]")
    by_type = {r["type"]: r["cnt"] for r in type_rows}

    # Median sale price (approximate via SQL)
    median_sale = 0
    sale_count = sale_row["cnt"] if sale_row else 0
    if sale_count > 0:
        median_row = db.execute(
            f"SELECT [price] FROM [{_LISTINGS_TABLE}] WHERE [status] = 'for_sale' AND [price] > 0 "
            f"ORDER BY [price] LIMIT 1 OFFSET ?",
            (sale_count // 2,), fetch="one")
        median_sale = median_row["price"] if median_row else 0

    stats = {
        "total_listings": total,
        "for_sale": by_status.get("for_sale", 0),
        "for_rent": by_status.get("for_rent", 0),
        "sold": by_status.get("sold", 0),
        "rented": by_status.get("rented", 0),
        "avg_sale_price": round(sale_row["avg_p"]) if sale_row and sale_row["avg_p"] else 0,
        "min_sale_price": sale_row["min_p"] if sale_row and sale_row["min_p"] else 0,
        "max_sale_price": sale_row["max_p"] if sale_row and sale_row["max_p"] else 0,
        "median_sale_price": median_sale,
        "avg_rent": round(rent_row["avg_p"]) if rent_row and rent_row["avg_p"] else 0,
        "min_rent": rent_row["min_p"] if rent_row and rent_row["min_p"] else 0,
        "max_rent": rent_row["max_p"] if rent_row and rent_row["max_p"] else 0,
        "by_type": by_type,
        "by_status": by_status,
    }
    return jsonify(stats)


@blueprint.route("/api/compare")
def api_compare():
    """Compare two or more listings by ID."""
    ids_str = request.args.get("ids", "")
    try:
        ids = [int(x.strip()) for x in ids_str.split(",") if x.strip()]
    except ValueError:
        return jsonify({"error": "ids must be comma-separated integers"}), 400
    if not ids or len(ids) > 20:
        return jsonify({"error": "Provide 1-20 ids (comma-separated)"}), 400
    placeholders = ",".join("?" for _ in ids)
    results = db.execute(
        f"SELECT * FROM [{_LISTINGS_TABLE}] WHERE [id] IN ({placeholders})",
        tuple(ids))
    # Add computed price_per_sqft
    for r in results:
        price = r.get("price", 0)
        sqft = r.get("sqft", 0)
        r["price_per_sqft"] = round(price / sqft, 2) if sqft > 0 else 0
    return jsonify(results)


@blueprint.route("/api/stats/by_type")
def api_stats_by_type():
    """Stats broken down by property type (for extract_by_dropdown)."""
    prop_type = request.args.get("type", "").strip()
    where_clause = "WHERE [type] = ?" if prop_type else ""
    params = (prop_type,) if prop_type else ()

    row = db.execute(
        f"SELECT COUNT(*) as cnt, AVG([price]) as avg_p, MIN([price]) as min_p, MAX([price]) as max_p "
        f"FROM [{_LISTINGS_TABLE}] {where_clause + ' AND' if where_clause else 'WHERE'} [price] > 0",
        params, fetch="one")

    # Status sub-counts
    status_sql = (
        f"SELECT [status], COUNT(*) as cnt FROM [{_LISTINGS_TABLE}] "
        f"{where_clause} GROUP BY [status]")
    status_rows = db.execute(status_sql, params)
    by_status = {r["status"]: r["cnt"] for r in status_rows}

    return jsonify({
        "type": prop_type or "all",
        "count": sum(by_status.values()),
        "avg_price": round(row["avg_p"]) if row and row["avg_p"] else 0,
        "min_price": row["min_p"] if row and row["min_p"] else 0,
        "max_price": row["max_p"] if row and row["max_p"] else 0,
        "for_sale": by_status.get("for_sale", 0),
        "for_rent": by_status.get("for_rent", 0),
    })


@blueprint.route("/api/proximity")
def api_proximity():
    """Search listings by address proximity (substring match on address)."""
    address = request.args.get("address", "").strip()
    if not address:
        return jsonify({"error": "address parameter required"}), 400
    pattern = f"%{address}%"
    results = db.execute(
        f"SELECT * FROM [{_LISTINGS_TABLE}] "
        f"WHERE [address] LIKE ? OR [city] LIKE ? OR [zip] LIKE ? "
        f"ORDER BY [listed_date] DESC LIMIT 50",
        (pattern, pattern, pattern))
    return jsonify(results)


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
