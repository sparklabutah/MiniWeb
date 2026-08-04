"""LakeReview — local business review platform (Yelp / Google Reviews style).

Reads businesses, reviews, photos, and users from the rating-review data source
and serves them through Flask routes with search, filter, and CRUD capabilities.
"""

import pathlib
from datetime import datetime

from flask import (
    Blueprint, abort, jsonify, redirect, render_template, request,
    session, url_for,
)
from app import db
from app.events import emit

SITE = "rating-review"
SITE_DIR = pathlib.Path(__file__).resolve().parent

# SQL table + FTS index names for the businesses collection, and how many
# businesses to show per page on the browse listing.
BIZ_TABLE = "rating_review_businesses"
FTS_BIZ_TABLE = "fts_rating_review_businesses"
PER_PAGE = 24

blueprint = Blueprint(
    "rating-review",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _businesses():
    return db.query(SITE, "businesses")


def _reviews():
    return db.query(SITE, "reviews")


def _photos():
    return db.query(SITE, "photos")


def _users():
    return db.query(SITE, "users")


def _current_user():
    uid = session.get("user_id")
    if uid is None:
        return None
    return db.get_item(SITE, "users", uid)


def _business_by_id(bid):
    return db.get_item(SITE, "businesses", bid)


def _reviews_for_business(bid):
    return db.query(SITE, "reviews", where={"business_id": bid})


def _reviews_by_user(uid):
    return db.query(SITE, "reviews", where={"user_id": uid})


def _photos_for_business(bid):
    return db.query(SITE, "photos", where={"business_id": bid})


def _photos_for_review(rid):
    return db.query(SITE, "photos", where={"review_id": rid})


def _user_by_id(uid):
    return db.get_item(SITE, "users", uid)


def _compute_rating_distribution(reviews_list):
    """Return dict {1: count, 2: count, ...5: count} for a list of reviews."""
    dist = {i: 0 for i in range(1, 6)}
    for r in reviews_list:
        rating = r.get("rating", 0)
        if 1 <= rating <= 5:
            dist[rating] += 1
    return dist


def _all_categories():
    rows = db.execute(
        f"SELECT DISTINCT category FROM {BIZ_TABLE} "
        f"WHERE category IS NOT NULL AND category != '' ORDER BY category"
    )
    return [r["category"] for r in rows]


def _category_counts():
    """(category, count) pairs, most populous first — real counts for browse
    pills and the category filter (Restaurants -> 86, etc.). SQL GROUP BY, so
    the table is never loaded into Python."""
    rows = db.execute(
        f"SELECT category, COUNT(*) AS n FROM {BIZ_TABLE} "
        f"WHERE category IS NOT NULL AND category != '' "
        f"GROUP BY category ORDER BY n DESC, category ASC"
    )
    return [(r["category"], r["n"]) for r in rows]


def _all_price_ranges():
    return ["$", "$$", "$$$", "$$$$", "Free"]


def _search_businesses(*, category="", price="", min_rating="", search="",
                       sort="rating", limit=PER_PAGE, offset=0):
    """SQL-level filtered / sorted / paginated business query.

    Returns ``(rows, total_count)``. All filtering, sorting, pagination and
    full-text search happen in SQL — the full 175-row table is never loaded
    into Python. When ``search`` is given, matches are found across the whole
    table via the FTS5 index (not just the first slice) and ranked by
    relevance unless the caller asks for an explicit sort.
    """
    filt_clauses, filt_params = [], []
    if category:
        filt_clauses.append("category = ?")
        filt_params.append(category)
    if price:
        filt_clauses.append("price_range = ?")
        filt_params.append(price)
    if min_rating not in (None, ""):
        try:
            mr = float(min_rating)
        except (TypeError, ValueError):
            mr = None
        if mr is not None:
            filt_clauses.append("overall_rating >= ?")
            filt_params.append(mr)

    search = (search or "").strip()

    if search:
        fts_query = " ".join(f'"{t}"*' for t in search.split() if t)
        base = (
            f" FROM {BIZ_TABLE} t "
            f"JOIN {FTS_BIZ_TABLE} f ON t.id = f.rowid "
            f"WHERE {FTS_BIZ_TABLE} MATCH ?"
        )
        params = [fts_query]
        for clause, val in zip(filt_clauses, filt_params):
            base += f" AND t.{clause}"
            params.append(val)
        total = db.execute(f"SELECT COUNT(*){base}", tuple(params), fetch="val") or 0
        order = {
            "reviews": "t.review_count DESC",
            "name": "t.name COLLATE NOCASE ASC",
        }.get(sort, "f.rank")  # default: relevance
        rows = db.execute(
            f"SELECT t.*{base} ORDER BY {order} LIMIT ? OFFSET ?",
            tuple(params) + (limit, offset),
        )
    else:
        where_sql = (" WHERE " + " AND ".join(filt_clauses)) if filt_clauses else ""
        total = db.execute(
            f"SELECT COUNT(*) FROM {BIZ_TABLE}{where_sql}",
            tuple(filt_params), fetch="val",
        ) or 0
        order = {
            "reviews": "review_count DESC",
            "name": "name COLLATE NOCASE ASC",
        }.get(sort, "overall_rating DESC")
        rows = db.execute(
            f"SELECT * FROM {BIZ_TABLE}{where_sql} ORDER BY {order} LIMIT ? OFFSET ?",
            tuple(filt_params) + (limit, offset),
        )

    return rows, total


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    """Homepage: featured businesses + search bar."""
    # Featured: top-rated businesses (rating >= 4.5), most-reviewed first.
    featured = db.execute(
        f"SELECT * FROM {BIZ_TABLE} WHERE overall_rating >= 4.5 "
        f"ORDER BY review_count DESC LIMIT 6"
    )

    # Recent reviews, newest first — enrich the handful shown with biz + user.
    recent_reviews = db.execute(
        "SELECT * FROM rating_review_reviews ORDER BY date DESC LIMIT 5"
    )
    for r in recent_reviews:
        r["_business"] = db.get_item(SITE, "businesses", r.get("business_id"))
        r["_user"] = db.get_item(SITE, "users", r.get("user_id"))

    # Real counts via SQL — never len() of a full table load.
    stats = {
        "business_count": db.count(SITE, "businesses"),
        "review_count": db.count(SITE, "reviews"),
        "photo_count": db.count(SITE, "photos"),
        "user_count": db.count(SITE, "users"),
    }

    return render_template(
        "rating-review/index.html",
        featured=featured,
        recent_reviews=recent_reviews,
        categories=_all_categories(),
        category_counts=_category_counts(),
        stats=stats,
        user=_current_user(),
    )


@blueprint.route("/businesses")
def businesses_list():
    """Browse businesses — SQL-level filtering, full-text search, pagination.

    Every matching business is reachable by paging (LIMIT/OFFSET at the SQL
    level); the page shows the true total so the full catalogue's breadth is
    visible rather than a tiny fixed subset.
    """
    category = request.args.get("category", "")
    price = request.args.get("price", "")
    min_rating = request.args.get("min_rating", "", type=str)
    search = (request.args.get("search", "") or "").strip()
    sort_by = request.args.get("sort", "rating")  # rating, reviews, name

    try:
        page = int(request.args.get("page", "1"))
    except (TypeError, ValueError):
        page = 1
    if page < 1:
        page = 1
    offset = (page - 1) * PER_PAGE

    rows, total = _search_businesses(
        category=category, price=price, min_rating=min_rating,
        search=search, sort=sort_by, limit=PER_PAGE, offset=offset,
    )

    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    if page > total_pages:
        page = total_pages

    return render_template(
        "rating-review/businesses.html",
        businesses=rows,
        total=total,
        page=page,
        total_pages=total_pages,
        per_page=PER_PAGE,
        start_index=offset,
        categories=_all_categories(),
        category_counts=_category_counts(),
        price_ranges=_all_price_ranges(),
        filters={"category": category, "price": price, "min_rating": min_rating,
                 "search": search, "sort": sort_by},
        user=_current_user(),
    )


@blueprint.route("/business/<int:business_id>")
def business_detail(business_id):
    """Business detail page with reviews."""
    biz = _business_by_id(business_id)
    if not biz:
        abort(404)

    reviews = _reviews_for_business(business_id)
    photos = _photos_for_business(business_id)
    user_map = {u["id"]: u for u in _users()}
    for r in reviews:
        r["_user"] = user_map.get(r["user_id"])
        r["_photos"] = [p for p in photos if p.get("review_id") == r["id"]]

    # Sort reviews: most recent first
    sort_by = request.args.get("sort", "date")
    if sort_by == "rating_high":
        reviews.sort(key=lambda r: r.get("rating", 0), reverse=True)
    elif sort_by == "rating_low":
        reviews.sort(key=lambda r: r.get("rating", 0))
    elif sort_by == "useful":
        reviews.sort(key=lambda r: r.get("useful_count", 0), reverse=True)
    else:
        reviews.sort(key=lambda r: r.get("date", ""), reverse=True)

    rating_dist = _compute_rating_distribution(reviews)

    return render_template(
        "rating-review/business_detail.html",
        business=biz,
        reviews=reviews,
        photos=photos,
        rating_distribution=rating_dist,
        review_count=len(reviews),
        user=_current_user(),
        sort=sort_by,
    )


@blueprint.route("/write-review/<int:business_id>")
def write_review(business_id):
    """Review form page."""
    biz = _business_by_id(business_id)
    if not biz:
        abort(404)
    user = _current_user()
    if not user:
        return redirect(url_for("rating-review.login", next=request.url))
    return render_template(
        "rating-review/write_review.html",
        business=biz,
        user=user,
    )


@blueprint.route("/my-reviews")
def my_reviews():
    """Current user's reviews."""
    user = _current_user()
    if not user:
        return redirect(url_for("rating-review.login", next=request.url))
    reviews = _reviews_by_user(user["id"])
    biz_map = {b["id"]: b for b in _businesses()}
    for r in reviews:
        r["_business"] = biz_map.get(r["business_id"])
    reviews.sort(key=lambda r: r.get("date", ""), reverse=True)
    return render_template(
        "rating-review/my_reviews.html",
        reviews=reviews,
        user=user,
    )


@blueprint.route("/photos")
def photo_gallery():
    """Photo gallery page."""
    photos = _photos()
    biz_map = {b["id"]: b for b in _businesses()}
    user_map = {u["id"]: u for u in _users()}

    business_id = request.args.get("business_id", "", type=str)
    if business_id:
        try:
            bid = int(business_id)
            photos = [p for p in photos if p["business_id"] == bid]
        except ValueError:
            pass

    for p in photos:
        p["_business"] = biz_map.get(p["business_id"])
        p["_user"] = user_map.get(p["user_id"])

    return render_template(
        "rating-review/photos.html",
        photos=photos,
        businesses=_businesses(),
        user=_current_user(),
        filter_business_id=business_id,
    )


@blueprint.route("/login", methods=["GET", "POST"])
def login():
    """Login page."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        users = _users()
        user = next((u for u in users if u["username"] == username), None)
        if user:
            stored_pw = user.get("password", "password")
            if password and password != stored_pw:
                return render_template("rating-review/login.html", error="Invalid password")
            session["user_id"] = user["id"]
            emit("signup", user_id=user["id"], site_name="rating-review", username=request.form.get("username", ""), password=request.form.get("password", ""), email="")
            next_url = request.form.get("next") or request.args.get("next") or url_for("rating-review.index")
            return redirect(next_url)
        return render_template(
            "rating-review/login.html",
            error="User not found. Please check your username.",
            next_url=request.args.get("next", ""),
            user=None,
        )
    return render_template(
        "rating-review/login.html",
        error=None,
        next_url=request.args.get("next", ""),
        user=_current_user(),
    )


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("rating-review.index"))


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/businesses")
def api_businesses():
    """GET businesses with optional filters (SQL-level, paginated)."""
    try:
        limit = min(max(int(request.args.get("limit", PER_PAGE)), 1), 200)
    except (TypeError, ValueError):
        limit = PER_PAGE
    try:
        offset = max(int(request.args.get("offset", 0)), 0)
    except (TypeError, ValueError):
        offset = 0

    rows, total = _search_businesses(
        category=request.args.get("category", "") or "",
        price=request.args.get("price", "") or "",
        min_rating=request.args.get("min_rating", "") or "",
        search=request.args.get("search", "") or "",
        sort=request.args.get("sort", "rating"),
        limit=limit, offset=offset,
    )
    return jsonify({
        "businesses": rows,
        "total": total,
        "limit": limit,
        "offset": offset,
    })


@blueprint.route("/api/businesses/<int:business_id>")
def api_business_detail(business_id):
    """GET single business by ID."""
    biz = _business_by_id(business_id)
    if not biz:
        return jsonify({"error": "Business not found"}), 404
    biz_reviews = _reviews_for_business(business_id)
    biz["_reviews"] = biz_reviews
    biz["_photos"] = _photos_for_business(business_id)
    biz["_rating_distribution"] = _compute_rating_distribution(biz_reviews)
    return jsonify(biz)


@blueprint.route("/api/reviews", methods=["GET"])
def api_reviews_list():
    """GET reviews with optional filters."""
    reviews = _reviews()

    business_id = request.args.get("business_id", type=int)
    user_id = request.args.get("user_id", type=int)
    min_rating = request.args.get("min_rating", type=int)
    max_rating = request.args.get("max_rating", type=int)

    if business_id is not None:
        reviews = [r for r in reviews if r["business_id"] == business_id]
    if user_id is not None:
        reviews = [r for r in reviews if r["user_id"] == user_id]
    if min_rating is not None:
        reviews = [r for r in reviews if r.get("rating", 0) >= min_rating]
    if max_rating is not None:
        reviews = [r for r in reviews if r.get("rating", 0) <= max_rating]

    return jsonify(reviews)


@blueprint.route("/api/reviews", methods=["POST"])
def api_reviews_create():
    """POST create a new review."""
    user = _current_user()
    if not user:
        return jsonify({"error": "Login required"}), 401

    data = request.get_json(silent=True) or {}
    business_id = data.get("business_id")
    rating = data.get("rating")
    title = data.get("title", "")
    text = data.get("text", "")

    if not business_id or not rating:
        return jsonify({"error": "business_id and rating are required"}), 400

    biz = _business_by_id(business_id)
    if not biz:
        return jsonify({"error": "Business not found"}), 404

    if not isinstance(rating, int) or rating < 1 or rating > 5:
        return jsonify({"error": "Rating must be an integer 1-5"}), 400

    reviews = _reviews()
    new_id = max((r["id"] for r in reviews), default=0) + 1
    new_review = {
        "id": new_id,
        "business_id": business_id,
        "user_id": user["id"],
        "rating": rating,
        "title": title,
        "text": text,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "useful_count": 0,
        "funny_count": 0,
        "cool_count": 0,
        "photos": [],
    }
    reviews.append(new_review)
    db.save_collection(SITE, "reviews", reviews)

    # Update business review count and overall rating
    businesses = _businesses()
    for b in businesses:
        if b["id"] == business_id:
            biz_reviews = [r for r in reviews if r["business_id"] == business_id]
            b["review_count"] = len(biz_reviews)
            if biz_reviews:
                b["overall_rating"] = round(
                    sum(r["rating"] for r in biz_reviews) / len(biz_reviews), 1
                )
            break
    db.save_collection(SITE, "businesses", businesses)

    return jsonify(new_review), 201


@blueprint.route("/api/reviews/<int:review_id>", methods=["GET"])
def api_review_detail(review_id):
    """GET single review."""
    for r in _reviews():
        if r["id"] == review_id:
            biz_map = {b["id"]: b for b in _businesses()}
            user_map = {u["id"]: u for u in _users()}
            r["_business"] = biz_map.get(r["business_id"])
            r["_user"] = user_map.get(r["user_id"])
            return jsonify(r)
    return jsonify({"error": "Review not found"}), 404


@blueprint.route("/api/reviews/<int:review_id>", methods=["PUT"])
def api_review_update(review_id):
    """PUT update a review."""
    user = _current_user()
    if not user:
        return jsonify({"error": "Login required"}), 401

    reviews = _reviews()
    review = None
    for r in reviews:
        if r["id"] == review_id:
            review = r
            break
    if not review:
        return jsonify({"error": "Review not found"}), 404
    if review["user_id"] != user["id"]:
        return jsonify({"error": "Not authorized to edit this review"}), 403

    data = request.get_json(silent=True) or {}
    if "rating" in data:
        rating = data["rating"]
        if not isinstance(rating, int) or rating < 1 or rating > 5:
            return jsonify({"error": "Rating must be an integer 1-5"}), 400
        review["rating"] = rating
    if "title" in data:
        review["title"] = data["title"]
    if "text" in data:
        review["text"] = data["text"]

    db.save_collection(SITE, "reviews", reviews)

    # Recalculate business rating
    businesses = _businesses()
    for b in businesses:
        if b["id"] == review["business_id"]:
            biz_reviews = [r for r in reviews if r["business_id"] == review["business_id"]]
            if biz_reviews:
                b["overall_rating"] = round(
                    sum(r["rating"] for r in biz_reviews) / len(biz_reviews), 1
                )
            break
    db.save_collection(SITE, "businesses", businesses)

    return jsonify(review)


@blueprint.route("/api/reviews/<int:review_id>", methods=["DELETE"])
def api_review_delete(review_id):
    """DELETE a review."""
    user = _current_user()
    if not user:
        return jsonify({"error": "Login required"}), 401

    reviews = _reviews()
    review = None
    for i, r in enumerate(reviews):
        if r["id"] == review_id:
            review = r
            break
    if not review:
        return jsonify({"error": "Review not found"}), 404
    if review["user_id"] != user["id"]:
        return jsonify({"error": "Not authorized to delete this review"}), 403

    business_id = review["business_id"]
    reviews = [r for r in reviews if r["id"] != review_id]
    db.save_collection(SITE, "reviews", reviews)

    # Remove associated photos
    photos = _photos()
    photos = [p for p in photos if p.get("review_id") != review_id]
    db.save_collection(SITE, "photos", photos)

    # Recalculate business stats
    businesses = _businesses()
    for b in businesses:
        if b["id"] == business_id:
            biz_reviews = [r for r in reviews if r["business_id"] == business_id]
            b["review_count"] = len(biz_reviews)
            if biz_reviews:
                b["overall_rating"] = round(
                    sum(r["rating"] for r in biz_reviews) / len(biz_reviews), 1
                )
            else:
                b["overall_rating"] = 0.0
            break
    db.save_collection(SITE, "businesses", businesses)

    return jsonify({"success": True, "deleted_id": review_id})


@blueprint.route("/api/reviews/<int:review_id>/helpful", methods=["POST"])
def api_review_helpful(review_id):
    """POST vote a review as helpful (useful/funny/cool)."""
    data = request.get_json(silent=True) or {}
    vote_type = data.get("type", "useful")
    if vote_type not in ("useful", "funny", "cool"):
        return jsonify({"error": "Vote type must be useful, funny, or cool"}), 400

    reviews = _reviews()
    for r in reviews:
        if r["id"] == review_id:
            key = f"{vote_type}_count"
            r[key] = r.get(key, 0) + 1
            db.save_collection(SITE, "reviews", reviews)
            return jsonify({"success": True, "review_id": review_id, key: r[key]})
    return jsonify({"error": "Review not found"}), 404


@blueprint.route("/api/photos", methods=["GET"])
def api_photos_list():
    """GET photos with optional filters."""
    photos = _photos()
    business_id = request.args.get("business_id", type=int)
    user_id = request.args.get("user_id", type=int)
    review_id = request.args.get("review_id", type=int)

    if business_id is not None:
        photos = [p for p in photos if p["business_id"] == business_id]
    if user_id is not None:
        photos = [p for p in photos if p["user_id"] == user_id]
    if review_id is not None:
        photos = [p for p in photos if p["review_id"] == review_id]

    return jsonify(photos)


@blueprint.route("/api/photos", methods=["POST"])
def api_photos_create():
    """POST add a photo."""
    user = _current_user()
    if not user:
        return jsonify({"error": "Login required"}), 401

    data = request.get_json(silent=True) or {}
    review_id = data.get("review_id")
    business_id = data.get("business_id")
    caption = data.get("caption", "")
    url = data.get("url", "")

    if not business_id:
        return jsonify({"error": "business_id is required"}), 400

    photos = _photos()
    existing_ids = [p["id"] for p in photos]
    # Generate next photo ID (ph-NNN format)
    numeric_ids = []
    for pid in existing_ids:
        if isinstance(pid, str) and pid.startswith("ph-"):
            try:
                numeric_ids.append(int(pid.split("-")[1]))
            except ValueError:
                pass
    next_num = max(numeric_ids, default=0) + 1
    new_id = f"ph-{next_num:03d}"

    new_photo = {
        "id": new_id,
        "review_id": review_id,
        "user_id": user["id"],
        "business_id": business_id,
        "caption": caption,
        "url": url,
        "uploaded_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "width": data.get("width", 1200),
        "height": data.get("height", 900),
    }
    photos.append(new_photo)
    db.save_collection(SITE, "photos", photos)

    # If linked to a review, add photo id to review's photos list
    if review_id:
        reviews = _reviews()
        for r in reviews:
            if r["id"] == review_id:
                if new_id not in r.get("photos", []):
                    r.setdefault("photos", []).append(new_id)
                break
        db.save_collection(SITE, "reviews", reviews)

    return jsonify(new_photo), 201


@blueprint.route("/api/stats")
def api_stats():
    """GET platform statistics."""
    businesses = _businesses()
    reviews = _reviews()
    photos = _photos()
    users = _users()

    # Category breakdown
    category_counts = {}
    for b in businesses:
        cat = b.get("category", "Other")
        category_counts[cat] = category_counts.get(cat, 0) + 1

    # Price range breakdown
    price_counts = {}
    for b in businesses:
        pr = b.get("price_range", "Unknown")
        price_counts[pr] = price_counts.get(pr, 0) + 1

    # Rating distribution across all reviews
    rating_dist = _compute_rating_distribution(reviews)

    # Average rating across all businesses
    ratings = [b.get("overall_rating", 0) for b in businesses if b.get("overall_rating")]
    avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else 0

    # Most reviewed businesses
    most_reviewed = sorted(businesses, key=lambda b: b.get("review_count", 0), reverse=True)[:5]
    most_reviewed_summary = [
        {"id": b["id"], "name": b["name"], "review_count": b["review_count"]}
        for b in most_reviewed
    ]

    # Top rated businesses
    top_rated = sorted(businesses, key=lambda b: b.get("overall_rating", 0), reverse=True)[:5]
    top_rated_summary = [
        {"id": b["id"], "name": b["name"], "overall_rating": b["overall_rating"]}
        for b in top_rated
    ]

    # Top reviewers
    user_review_counts = {}
    for r in reviews:
        uid = r["user_id"]
        user_review_counts[uid] = user_review_counts.get(uid, 0) + 1
    user_map = {u["id"]: u for u in users}
    top_reviewers = sorted(user_review_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    top_reviewers_summary = [
        {"user_id": uid, "display_name": user_map.get(uid, {}).get("display_name", "Unknown"),
         "review_count": count}
        for uid, count in top_reviewers
    ]

    return jsonify({
        "total_businesses": len(businesses),
        "total_reviews": len(reviews),
        "total_photos": len(photos),
        "total_users": len(users),
        "average_rating": avg_rating,
        "category_breakdown": category_counts,
        "price_range_breakdown": price_counts,
        "rating_distribution": rating_dist,
        "most_reviewed": most_reviewed_summary,
        "top_rated": top_rated_summary,
        "top_reviewers": top_reviewers_summary,
    })


# ---------------------------------------------------------------------------
# API routes - Search (search_by_query, search_by_semantic)
# ---------------------------------------------------------------------------

@blueprint.route("/api/search")
def api_search():
    """search_by_query: keyword search across businesses and reviews.

    Uses the FTS5 indexes so matches are found across the whole tables, then
    returns a page of results (limit/offset) plus true total counts.
    """
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify({"error": "Query parameter 'q' is required"}), 400

    try:
        limit = min(max(int(request.args.get("limit", 50)), 1), 200)
    except (TypeError, ValueError):
        limit = 50
    try:
        offset = max(int(request.args.get("offset", 0)), 0)
    except (TypeError, ValueError):
        offset = 0

    fts_query = " ".join(f'"{t}"*' for t in q.split() if t)

    biz_results = db.search(SITE, "businesses", q, limit=limit, offset=offset)
    review_results = db.search(SITE, "reviews", q, limit=limit, offset=offset)

    biz_total = db.execute(
        f"SELECT COUNT(*) FROM {BIZ_TABLE} t "
        f"JOIN {FTS_BIZ_TABLE} f ON t.id = f.rowid "
        f"WHERE {FTS_BIZ_TABLE} MATCH ?",
        (fts_query,), fetch="val",
    ) or 0
    review_total = db.execute(
        "SELECT COUNT(*) FROM rating_review_reviews t "
        "JOIN fts_rating_review_reviews f ON t.id = f.rowid "
        "WHERE fts_rating_review_reviews MATCH ?",
        (fts_query,), fetch="val",
    ) or 0

    return jsonify({
        "query": q,
        "businesses": biz_results,
        "reviews": review_results,
        "business_count": biz_total,
        "review_count": review_total,
        "limit": limit,
        "offset": offset,
    })


@blueprint.route("/api/search/semantic")
def api_search_semantic():
    """search_by_semantic: keyword-overlap semantic search."""
    q = (request.args.get("q") or "").strip().lower()
    if not q:
        return jsonify({"error": "Query parameter 'q' is required"}), 400

    query_tokens = q.split()
    businesses = _businesses()

    scored = []
    for b in businesses:
        text = f"{b.get('name', '')} {b.get('category', '')} {b.get('subcategory', '')} {' '.join(b.get('attributes', []))}".lower()
        score = sum(2 if t in text else 0 for t in query_tokens)
        if score > 0:
            scored.append((score, b))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = [b for _, b in scored]
    return jsonify({"query": q, "count": len(results), "businesses": results})


# ---------------------------------------------------------------------------
# API routes - User social features (save, follow, report)
# ---------------------------------------------------------------------------

def _load_user_state():
    """Load user state (saved businesses, followed users, reports)."""
    state = db.get_item(SITE, "user_state", "state")
    if state:
        return state
    return {"saved": {}, "followed": {}, "reports": []}


def _save_user_state(state):
    db.save_item(SITE, "user_state", "state", state)


@blueprint.route("/api/users/<int:user_id>/save", methods=["POST"])
def api_user_save(user_id):
    """save_by_toggle: save/unsave a business for a user."""
    user = _current_user()
    if not user:
        return jsonify({"error": "Login required"}), 401

    data = request.get_json(silent=True) or {}
    business_id = data.get("business_id")
    if not business_id:
        return jsonify({"error": "business_id is required"}), 400

    state = _load_user_state()
    uid_key = str(user["id"])
    saved = state.get("saved", {}).get(uid_key, [])

    if business_id in saved:
        saved.remove(business_id)
        action = "unsaved"
    else:
        saved.append(business_id)
        action = "saved"

    state.setdefault("saved", {})[uid_key] = saved
    _save_user_state(state)
    return jsonify({"action": action, "business_id": business_id, "saved": saved})


@blueprint.route("/api/users/<int:user_id>/saved")
def api_user_saved(user_id):
    """Get saved businesses for a user."""
    state = _load_user_state()
    saved_ids = state.get("saved", {}).get(str(user_id), [])
    businesses = _businesses()
    saved_biz = [b for b in businesses if b["id"] in saved_ids]
    return jsonify(saved_biz)


@blueprint.route("/api/users/<int:user_id>/follow", methods=["POST"])
def api_user_follow(user_id):
    """follow_by_toggle: follow/unfollow another user."""
    user = _current_user()
    if not user:
        return jsonify({"error": "Login required"}), 401

    data = request.get_json(silent=True) or {}
    target_user_id = data.get("target_user_id", user_id)

    state = _load_user_state()
    uid_key = str(user["id"])
    followed = state.get("followed", {}).get(uid_key, [])

    if target_user_id in followed:
        followed.remove(target_user_id)
        action = "unfollowed"
    else:
        followed.append(target_user_id)
        action = "followed"

    state.setdefault("followed", {})[uid_key] = followed
    _save_user_state(state)
    return jsonify({"action": action, "target_user_id": target_user_id, "followed": followed})


@blueprint.route("/api/report", methods=["POST"])
def api_report():
    """report_by_form: report a business or review."""
    user = _current_user()
    if not user:
        return jsonify({"error": "Login required"}), 401

    data = request.get_json(silent=True) or {}
    target_type = data.get("target_type", "business")
    target_id = data.get("target_id")
    reason = (data.get("reason") or "").strip()

    if not target_id:
        return jsonify({"error": "target_id is required"}), 400
    if not reason:
        return jsonify({"error": "reason is required"}), 400

    state = _load_user_state()
    reports = state.get("reports", [])
    report = {
        "id": len(reports) + 1,
        "reporter_id": user["id"],
        "target_type": target_type,
        "target_id": target_id,
        "reason": reason,
        "description": data.get("description", ""),
        "created_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "pending",
    }
    reports.append(report)
    state["reports"] = reports
    _save_user_state(state)
    return jsonify(report), 201


# ---------------------------------------------------------------------------
# API routes - Compare, Compute, Rate
# ---------------------------------------------------------------------------

@blueprint.route("/api/compare")
def api_compare():
    """compare_by_slider: compare two businesses side by side."""
    ids_str = request.args.get("ids", "")
    if not ids_str:
        return jsonify({"error": "ids parameter required (comma-separated)"}), 400

    try:
        ids = [int(x.strip()) for x in ids_str.split(",")]
    except ValueError:
        return jsonify({"error": "ids must be integers"}), 400

    businesses = _businesses()
    reviews = _reviews()
    results = []
    for bid in ids:
        biz = next((b for b in businesses if b["id"] == bid), None)
        if biz:
            biz_reviews = [r for r in reviews if r["business_id"] == bid]
            biz["_review_count"] = len(biz_reviews)
            biz["_rating_distribution"] = _compute_rating_distribution(biz_reviews)
            results.append(biz)

    return jsonify(results)


@blueprint.route("/api/compute")
def api_compute():
    """compute_by_dropdown: compute aggregated statistics for a category."""
    category = request.args.get("category")
    if not category:
        return jsonify({"error": "category parameter is required"}), 400

    businesses = _businesses()
    reviews = _reviews()
    cat_biz = [b for b in businesses if b.get("category") == category]

    if not cat_biz:
        return jsonify({"error": f"No businesses found in category '{category}'"}), 404

    cat_biz_ids = {b["id"] for b in cat_biz}
    cat_reviews = [r for r in reviews if r["business_id"] in cat_biz_ids]

    avg_rating = round(sum(b.get("overall_rating", 0) for b in cat_biz) / len(cat_biz), 2) if cat_biz else 0
    avg_review_rating = round(sum(r.get("rating", 0) for r in cat_reviews) / len(cat_reviews), 2) if cat_reviews else 0

    return jsonify({
        "category": category,
        "business_count": len(cat_biz),
        "review_count": len(cat_reviews),
        "avg_business_rating": avg_rating,
        "avg_review_rating": avg_review_rating,
        "price_breakdown": {pr: sum(1 for b in cat_biz if b.get("price_range") == pr)
                           for pr in set(b.get("price_range", "") for b in cat_biz)},
    })


@blueprint.route("/api/reviews/<int:review_id>/rate", methods=["POST"])
def api_rate_review(review_id):
    """rate_by_slider: react to a review with a helpfulness rating."""
    data = request.get_json(silent=True) or {}
    rating = data.get("rating")
    if rating is None:
        return jsonify({"error": "rating is required (1-5)"}), 400
    try:
        rating = int(rating)
        if rating < 1 or rating > 5:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "rating must be integer 1-5"}), 400

    reviews = _reviews()
    for r in reviews:
        if r["id"] == review_id:
            r["useful_count"] = r.get("useful_count", 0) + rating
            db.save_collection(SITE, "reviews", reviews)
            return jsonify({"success": True, "review_id": review_id,
                          "useful_count": r["useful_count"], "rating_added": rating})

    return jsonify({"error": "Review not found"}), 404


# ---------------------------------------------------------------------------
# API routes - Login
# ---------------------------------------------------------------------------

@blueprint.route("/api/login", methods=["POST"])
def api_login():
    """authenticate by API."""
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    users = _users()
    user = next((u for u in users if u["username"] == username), None)
    if not user:
        return jsonify({"error": "User not found"}), 404
    session["user_id"] = user["id"]
    return jsonify({"user_id": user["id"], "username": user["username"]})


@blueprint.route("/api/users/<int:user_id>")
def api_user_detail(user_id):
    """GET user details."""
    user = _user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    reviews = _reviews_by_user(user_id)
    state = _load_user_state()
    saved = state.get("saved", {}).get(str(user_id), [])
    followed = state.get("followed", {}).get(str(user_id), [])
    return jsonify({
        **{k: v for k, v in user.items() if k != "password"},
        "review_count": len(reviews),
        "saved_businesses": saved,
        "followed_users": followed,
    })


@blueprint.route("/api/categories")
def api_categories():
    """navigate_by_dropdown: list all categories."""
    return jsonify(_all_categories())
