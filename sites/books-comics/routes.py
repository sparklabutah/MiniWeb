"""Books & Comics — digital platform for discovering, reading, and organizing books/comics.

Data: 1,892 books from pressbooks dataset stored in SQLite.
"""
import pathlib

from flask import Blueprint, Response, abort, jsonify, redirect, render_template, request, session, url_for

from app import db
from app.events import emit

SITE = "books-comics"
SITE_DIR = pathlib.Path(__file__).resolve().parent
_BOOKS_TABLE = "books_comics_books"

blueprint = Blueprint(
    "books-comics",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data helpers — all data lives in SQLite via db.query()
# ---------------------------------------------------------------------------

def _get_categories():
    return db.query(SITE, "categories")


# ---------------------------------------------------------------------------
# Users (mutable state)
# ---------------------------------------------------------------------------

def _normalize_cart(cart):
    """Normalize cart to a flat list of int book IDs.

    Overlay data may store cart as [{book_id: 10, ...}, ...] (dicts) or [10, 9]
    (ints).  The rest of the code expects [int, ...].
    """
    if not cart:
        return []
    normalized = []
    for item in cart:
        if isinstance(item, dict):
            bid = item.get("book_id")
            if bid is not None:
                normalized.append(bid)
        else:
            normalized.append(item)
    return normalized


def _load_users():
    users = db.query(SITE, "users")
    for u in users:
        u["cart"] = _normalize_cart(u.get("cart", []))
    return users


def _save_users(users):
    db.save_collection(SITE, "users", users)


def _get_user(user_id):
    user = db.get_item(SITE, "users", user_id)
    if user:
        user["cart"] = _normalize_cart(user.get("cart", []))
    return user


# ---------------------------------------------------------------------------
# Reviews (mutable state)
# ---------------------------------------------------------------------------

def _load_reviews(book_id=None):
    where = {"book_id": book_id} if book_id is not None else None
    return db.query(SITE, "reviews", where=where)


def _save_reviews(reviews):
    db.save_collection(SITE, "reviews", reviews)


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def _query_books(q="", cat="", min_rating=None, sort="newest", limit=30, offset=0):
    """Query books with filters pushed to SQL. Uses FTS5 for text search."""
    if q:
        results = db.search(SITE, "books", q, where={"category": cat} if cat else None,
                            limit=limit, offset=offset)
        # FTS5 already ranks by relevance; re-sort only if user wants different order
        if sort != "relevance":
            sort_map = {
                "newest": lambda b: (-b["year"], b["title"]),
                "title": lambda b: b["title"].lower(),
                "rating": lambda b: (-b["rating"], b["title"]),
                "price_low": lambda b: (b["price"], b["title"]),
                "price_high": lambda b: (-b["price"], b["title"]),
            }
            if sort in sort_map:
                results.sort(key=sort_map[sort])
        return results

    clauses = []
    params = []
    if cat:
        clauses.append("[category] = ?")
        params.append(cat)
    if min_rating is not None:
        clauses.append("[rating] >= ?")
        params.append(min_rating)

    sort_map = {
        "newest": "[year] DESC, [title] ASC",
        "title": "[title] ASC",
        "rating": "[rating] DESC, [title] ASC",
        "price_low": "[price] ASC, [title] ASC",
        "price_high": "[price] DESC, [title] ASC",
    }
    order = sort_map.get(sort, "[year] DESC, [title] ASC")

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT * FROM [{_BOOKS_TABLE}]{where} ORDER BY {order} LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    return db.execute(sql, tuple(params))


def _count_books(cat="", min_rating=None):
    clauses = []
    params = []
    if cat:
        clauses.append("[category] = ?")
        params.append(cat)
    if min_rating is not None:
        clauses.append("[rating] >= ?")
        params.append(min_rating)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return db.execute(f"SELECT COUNT(*) FROM [{_BOOKS_TABLE}]{where}", tuple(params), fetch="val") or 0


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    categories = _get_categories()
    q = request.args.get("q", "").strip()
    cat = request.args.get("category", "").strip()
    min_rating = request.args.get("min_rating", "").strip()
    sort = request.args.get("sort", "newest").strip()

    mr = None
    if min_rating:
        try:
            mr = float(min_rating)
        except ValueError:
            pass

    page = request.args.get("page", 1, type=int)
    per_page = 30
    total_results = _count_books(cat=cat, min_rating=mr) if not q else 0
    offset = (max(1, page) - 1) * per_page

    results = _query_books(q=q, cat=cat, min_rating=mr, sort=sort,
                           limit=per_page, offset=offset)

    if q:
        total_results = len(results) if len(results) < per_page else per_page * 10

    total_pages = max(1, (total_results + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template("books-comics/index.html",
                           books=results, categories=categories,
                           q=q, cat=cat, min_rating=min_rating,
                           sort=sort, price_filter="", user=user,
                           page=page, total_pages=total_pages,
                           total_results=total_results)


@blueprint.route("/book/<int:book_id>")
def book_detail(book_id):
    book = db.get_item(SITE, "books", book_id)
    if book is None:
        abort(404)
    related = db.query(SITE, "books", where={"category": book["category"]}, limit=6)
    related = [b for b in related if b["id"] != book_id][:5]
    reviews = _load_reviews(book_id=book_id)
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("books-comics/book.html", book=book,
                           related=related, reviews=reviews, user=user)


@blueprint.route("/book/<int:book_id>/read")
def read_book(book_id):
    book = db.get_item(SITE, "books", book_id)
    if book is None:
        abort(404)
    chapter = request.args.get("chapter", 1, type=int)
    # Fetch chapter list from chapters table
    chapters = db.execute(
        "SELECT chapter_num as chapter, title FROM books_comics_chapters "
        "WHERE book_id = ? ORDER BY chapter_num", (book_id,))
    # Fetch current chapter content
    current = db.execute(
        "SELECT chapter_num as chapter, title, body FROM books_comics_chapters "
        "WHERE book_id = ? AND chapter_num = ?", (book_id, chapter), fetch="one")
    if current is None and chapters:
        current = db.execute(
            "SELECT chapter_num as chapter, title, body FROM books_comics_chapters "
            "WHERE book_id = ? ORDER BY chapter_num LIMIT 1", (book_id,), fetch="one")
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("books-comics/reader.html", book=book,
                           chapters=chapters, current=current,
                           chapter_num=chapter, user=user)


@blueprint.route("/category/<slug>")
def category_page(slug):
    categories = _get_categories()
    filtered = db.query(SITE, "books", where={"category": slug}, limit=50)
    cat_info = next((c for c in categories if c["slug"] == slug), {"slug": slug, "name": slug})
    return render_template("books-comics/category.html",
                           books=filtered, category=cat_info,
                           categories=categories)


@blueprint.route("/cart")
def cart_page():
    if "user_id" not in session:
        return render_template("books-comics/login.html", error=None)
    user = _get_user(session["user_id"])
    if not user:
        return render_template("books-comics/login.html", error=None)
    cart_ids = user.get("cart", [])
    cart_items = [db.get_item(SITE, "books", bid) for bid in cart_ids if bid]
    cart_items = [b for b in cart_items if b]
    total = sum(b["price"] for b in cart_items)
    return render_template("books-comics/cart.html", user=user,
                           cart_items=cart_items, total=total)


@blueprint.route("/checkout", methods=["GET", "POST"])
def checkout_page():
    if "user_id" not in session:
        return render_template("books-comics/login.html", error=None)
    user = _get_user(session["user_id"])
    if not user:
        return render_template("books-comics/login.html", error=None)
    cart_ids = user.get("cart", [])
    cart_items = [db.get_item(SITE, "books", bid) for bid in cart_ids if bid]
    cart_items = [b for b in cart_items if b]
    total = sum(b["price"] for b in cart_items)

    if request.method == "POST":
        # Process checkout
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        card = request.form.get("card", "").strip()
        if not name or not email or not card:
            return render_template("books-comics/checkout.html", user=user,
                                   cart_items=cart_items, total=total,
                                   error="All fields are required.")
        account_type = request.form.get("account_type", "checking")
        # Clear cart after checkout
        users = _load_users()
        u = next((u for u in users if u["id"] == user["id"]), None)
        if u:
            purchased = u.get("cart", [])
            u["cart"] = []
            reading = u.setdefault("reading_list", [])
            for pid in purchased:
                if pid not in reading:
                    reading.append(pid)
            _save_users(users)
        from app.events import request_2fa
        verify_url = request_2fa("purchase",
                                 return_url=url_for("books-comics.dashboard"),
                                 user_id=user["id"],
                                 amount=total,
                                 merchant="BookVerse",
                                 item=f"{len(cart_items)} books",
                                 account_type=account_type)
        return redirect(verify_url)

    return render_template("books-comics/checkout.html", user=user,
                           cart_items=cart_items, total=total,
                           success=False, error=None)


@blueprint.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return render_template("books-comics/login.html", error=None)
    user = _get_user(session["user_id"])
    if not user:
        return render_template("books-comics/login.html", error=None)
    saved_ids = user.get("saved_books", []) or []
    saved = [db.get_item(SITE, "books", bid) for bid in saved_ids if bid]
    saved = [b for b in saved if b]
    reading_ids = user.get("reading_list", []) or []
    reading = [db.get_item(SITE, "books", bid) for bid in reading_ids if bid]
    reading = [b for b in reading if b]
    return render_template("books-comics/dashboard.html", user=user,
                           saved_books=saved, reading_list=reading,
                           followed_authors=user.get("followed_authors", []),
                           subscriptions=user.get("subscriptions", []))


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("books-comics/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return render_template("books-comics/login.html",
                               error="Invalid username or password")
    session["user_id"] = user["id"]
    saved_ids = user.get("saved_books", []) or []
    saved = [db.get_item(SITE, "books", bid) for bid in saved_ids if bid]
    saved = [b for b in saved if b]
    reading_ids = user.get("reading_list", []) or []
    reading = [db.get_item(SITE, "books", bid) for bid in reading_ids if bid]
    reading = [b for b in reading if b]
    return render_template("books-comics/dashboard.html", user=user,
                           saved_books=saved, reading_list=reading,
                           followed_authors=user.get("followed_authors", []),
                           subscriptions=user.get("subscriptions", []))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return render_template("books-comics/login.html", error=None)


# ---------------------------------------------------------------------------
# Form POST routes (for browser-automation-friendly mutations)
# ---------------------------------------------------------------------------

@blueprint.route("/book/<int:book_id>/save", methods=["POST"])
def form_save_book(book_id):
    if "user_id" not in session:
        return redirect(url_for("books-comics.login_page"))
    user_id = session["user_id"]
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        return redirect(url_for("books-comics.login_page"))
    saved = user.setdefault("saved_books", [])
    if book_id in saved:
        saved.remove(book_id)
    else:
        saved.append(book_id)
    _save_users(users)
    return redirect(url_for("books-comics.book_detail", book_id=book_id))


@blueprint.route("/book/<int:book_id>/cart", methods=["POST"])
def form_cart_add(book_id):
    if "user_id" not in session:
        return redirect(url_for("books-comics.login_page"))
    user_id = session["user_id"]
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        return redirect(url_for("books-comics.login_page"))
    cart = user.setdefault("cart", [])
    if book_id in cart:
        cart.remove(book_id)
    else:
        cart.append(book_id)
    _save_users(users)
    return redirect(url_for("books-comics.book_detail", book_id=book_id))


@blueprint.route("/book/<int:book_id>/follow", methods=["POST"])
def form_follow_author(book_id):
    if "user_id" not in session:
        return redirect(url_for("books-comics.login_page"))
    user_id = session["user_id"]
    author = request.form.get("author", "").strip()
    if not author:
        return redirect(url_for("books-comics.book_detail", book_id=book_id))
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        return redirect(url_for("books-comics.login_page"))
    followed = user.setdefault("followed_authors", [])
    if author in followed:
        followed.remove(author)
    else:
        followed.append(author)
    _save_users(users)
    return redirect(url_for("books-comics.book_detail", book_id=book_id))


@blueprint.route("/book/<int:book_id>/subscribe", methods=["POST"])
def form_subscribe_category(book_id):
    if "user_id" not in session:
        return redirect(url_for("books-comics.login_page"))
    user_id = session["user_id"]
    category = request.form.get("category", "").strip()
    if not category:
        return redirect(url_for("books-comics.book_detail", book_id=book_id))
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        return redirect(url_for("books-comics.login_page"))
    subs = user.setdefault("subscriptions", [])
    if category in subs:
        subs.remove(category)
    else:
        subs.append(category)
    _save_users(users)
    return redirect(url_for("books-comics.book_detail", book_id=book_id))


@blueprint.route("/book/<int:book_id>/rate", methods=["POST"])
def form_rate_book(book_id):
    if "user_id" not in session:
        return redirect(url_for("books-comics.login_page"))
    user_id = session["user_id"]
    rating = request.form.get("rating", "4")
    try:
        rating = float(rating)
    except (TypeError, ValueError):
        rating = 4.0
    if rating < 1:
        rating = 1
    if rating > 5:
        rating = 5
    reviews = _load_reviews()
    review = {
        "id": len(reviews) + 1,
        "book_id": book_id,
        "user_id": user_id,
        "text": "",
        "rating": rating,
    }
    reviews.append(review)
    _save_reviews(reviews)
    return redirect(url_for("books-comics.book_detail", book_id=book_id))


@blueprint.route("/book/<int:book_id>/review", methods=["POST"])
def form_post_review(book_id):
    if "user_id" not in session:
        return redirect(url_for("books-comics.login_page"))
    user_id = session["user_id"]
    text = request.form.get("text", "").strip()
    rating = request.form.get("rating", "")
    if not text:
        return redirect(url_for("books-comics.book_detail", book_id=book_id))
    reviews = _load_reviews()
    review = {
        "id": len(reviews) + 1,
        "book_id": book_id,
        "user_id": user_id,
        "text": text,
        "rating": float(rating) if rating else None,
    }
    reviews.append(review)
    _save_reviews(reviews)
    return redirect(url_for("books-comics.book_detail", book_id=book_id))


@blueprint.route("/book/<int:book_id>/react", methods=["POST"])
def form_react_review(book_id):
    review_id = request.form.get("review_id", type=int)
    reaction = request.form.get("reaction", "like")
    reviews = _load_reviews()
    review = next((r for r in reviews if r.get("id") == review_id), None)
    if review:
        reactions = review.setdefault("reactions", {})
        current = reactions.get(reaction, 0)
        reactions[reaction] = current + 1
        _save_reviews(reviews)
    return redirect(url_for("books-comics.book_detail", book_id=book_id))


@blueprint.route("/dashboard/unsave", methods=["POST"])
def form_unsave_book():
    if "user_id" not in session:
        return redirect(url_for("books-comics.login_page"))
    user_id = session["user_id"]
    book_id = request.form.get("book_id", type=int)
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if user and book_id is not None:
        saved = user.get("saved_books", [])
        if book_id in saved:
            saved.remove(book_id)
        _save_users(users)
    return redirect(url_for("books-comics.dashboard"))


@blueprint.route("/dashboard/unfollow", methods=["POST"])
def form_unfollow_author():
    if "user_id" not in session:
        return redirect(url_for("books-comics.login_page"))
    user_id = session["user_id"]
    author = request.form.get("author", "").strip()
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if user and author:
        followed = user.get("followed_authors", [])
        if author in followed:
            followed.remove(author)
        _save_users(users)
    return redirect(url_for("books-comics.dashboard"))


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/books")
def api_books():
    q = request.args.get("q", "").strip()
    cat = request.args.get("category", "").strip()
    min_rating = request.args.get("min_rating", type=float)
    sort = request.args.get("sort", "newest")
    limit = request.args.get("limit", 30, type=int)

    results = _query_books(q=q, cat=cat, min_rating=min_rating, sort=sort, limit=limit)
    safe = [{k: v for k, v in b.items() if k != "chapters"} for b in results]
    return jsonify(safe)


@blueprint.route("/api/books/<int:book_id>")
def api_book(book_id):
    book = db.get_item(SITE, "books", book_id)
    if book is None:
        abort(404)
    # Return book without full chapter content, but with chapter listing
    result = {k: v for k, v in book.items() if k != "chapters"}
    result["chapters"] = [{"chapter": c["chapter"], "title": c["title"]}
                          for c in book.get("chapters", [])]
    return jsonify(result)


@blueprint.route("/api/books/<int:book_id>/chapters")
def api_book_chapters(book_id):
    chapters = db.execute(
        "SELECT chapter_num as chapter, title FROM books_comics_chapters "
        "WHERE book_id = ? ORDER BY chapter_num", (book_id,))
    return jsonify(chapters)


@blueprint.route("/api/books/<int:book_id>/chapters/<int:ch_num>")
def api_book_chapter(book_id, ch_num):
    chapter = db.execute(
        "SELECT chapter_num as chapter, title, body FROM books_comics_chapters "
        "WHERE book_id = ? AND chapter_num = ?", (book_id, ch_num), fetch="one")
    if chapter is None:
        abort(404)
    return jsonify(chapter)


@blueprint.route("/api/books/search")
def api_search():
    q = request.args.get("q", "").strip()
    results = db.search(SITE, "books", q, limit=50) if q else []
    safe = [{k: v for k, v in b.items() if k != "chapters"} for b in results]
    return jsonify(safe)


@blueprint.route("/api/books/semantic")
def api_semantic_search():
    q = request.args.get("q", "").strip()
    results = db.search(SITE, "books", q, limit=50) if q else []
    safe = [{k: v for k, v in b.items() if k != "chapters"} for b in results]
    return jsonify(safe)


@blueprint.route("/api/categories")
def api_categories():
    cats = _get_categories()
    count_rows = db.execute(
        f"SELECT category, COUNT(*) as cnt FROM [{_BOOKS_TABLE}] GROUP BY category")
    counts = {r["category"]: r["cnt"] for r in count_rows}
    result = [{"slug": c["slug"], "name": c["name"],
               "description": c.get("description", ""),
               "count": counts.get(c["slug"], 0)} for c in cats]
    return jsonify(result)


@blueprint.route("/api/categories/<slug>/books")
def api_category_books(slug):
    filtered = db.query(SITE, "books", where={"category": slug}, limit=50)
    safe = [{k: v for k, v in b.items() if k != "chapters"} for b in filtered]
    return jsonify(safe)


@blueprint.route("/api/categories/<slug>/stats")
def api_category_stats(slug):
    stats = db.execute(
        f"SELECT COUNT(*) as cnt, AVG(rating) as avg_r, MIN(year) as min_y, MAX(year) as max_y, "
        f"COUNT(DISTINCT author) as authors FROM [{_BOOKS_TABLE}] WHERE category = ?",
        (slug,), fetch="one")
    if not stats or stats["cnt"] == 0:
        return jsonify({"category": slug, "count": 0})
    return jsonify({
        "category": slug,
        "count": stats["cnt"],
        "earliest_year": stats["min_y"],
        "latest_year": stats["max_y"],
        "unique_authors": stats["authors"],
        "avg_rating": round(stats["avg_r"] or 0, 2),
    })


@blueprint.route("/api/stats")
def api_stats():
    cat = request.args.get("category", "").strip()
    where = "WHERE category = ?" if cat else ""
    p = (cat,) if cat else ()
    stats = db.execute(
        f"SELECT COUNT(*) as cnt, AVG(rating) as avg_r, MIN(year) as min_y, MAX(year) as max_y, "
        f"COUNT(DISTINCT author) as authors FROM [{_BOOKS_TABLE}] {where}", p, fetch="one")
    if not stats or stats["cnt"] == 0:
        return jsonify({"count": 0})
    cat_rows = db.execute(
        f"SELECT category, COUNT(*) as cnt FROM [{_BOOKS_TABLE}] {where} "
        f"GROUP BY category ORDER BY cnt DESC LIMIT 10", p)
    return jsonify({
        "count": stats["cnt"],
        "earliest_year": stats["min_y"],
        "latest_year": stats["max_y"],
        "unique_authors": stats["authors"],
        "avg_rating": round(stats["avg_r"] or 0, 2),
        "top_categories": {r["category"]: r["cnt"] for r in cat_rows},
    })


@blueprint.route("/api/export")
def api_export():
    fmt = request.args.get("format", "json").lower()
    cat = request.args.get("category", "").strip()
    books = _query_books(cat=cat, limit=2000)
    safe = [{k: v for k, v in b.items() if k != "chapters"} for b in books]

    if fmt == "csv":
        lines = ["id,title,author,category,year,rating,price"]
        for b in safe:
            title = b["title"].replace('"', '""')
            author = b.get("author", "").replace('"', '""')
            lines.append(f'{b["id"]},"{title}","{author}","{b["category"]}",{b["year"]},{b["rating"]},{b["price"]}')
        return Response("\n".join(lines), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=books.csv"})
    return jsonify(safe)


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


@blueprint.route("/api/users/<int:user_id>/save", methods=["POST"])
def api_save_book(user_id):
    data = request.get_json(silent=True) or {}
    book_id = data.get("book_id")
    if book_id is None:
        return jsonify({"error": "book_id required"}), 400
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    saved = user.setdefault("saved_books", [])
    if book_id in saved:
        saved.remove(book_id)
        action = "unsaved"
    else:
        saved.append(book_id)
        action = "saved"
    _save_users(users)
    return jsonify({"action": action, "book_id": book_id, "total_saved": len(saved)})


@blueprint.route("/api/users/<int:user_id>/follow", methods=["POST"])
def api_follow_author(user_id):
    data = request.get_json(silent=True) or {}
    author = data.get("author", "").strip()
    if not author:
        return jsonify({"error": "author required"}), 400
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    followed = user.setdefault("followed_authors", [])
    if author in followed:
        followed.remove(author)
        action = "unfollowed"
    else:
        followed.append(author)
        action = "followed"
    _save_users(users)
    return jsonify({"action": action, "author": author, "total_followed": len(followed)})


@blueprint.route("/api/users/<int:user_id>/subscribe", methods=["POST"])
def api_subscribe(user_id):
    data = request.get_json(silent=True) or {}
    category = data.get("category", "").strip()
    if not category:
        return jsonify({"error": "category required"}), 400
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    subs = user.setdefault("subscriptions", [])
    if category in subs:
        subs.remove(category)
        action = "unsubscribed"
    else:
        subs.append(category)
        action = "subscribed"
    _save_users(users)
    return jsonify({"action": action, "category": category, "total_subscriptions": len(subs)})


@blueprint.route("/api/users/<int:user_id>/cart", methods=["POST"])
def api_cart_add(user_id):
    data = request.get_json(silent=True) or {}
    book_id = data.get("book_id")
    if book_id is None:
        return jsonify({"error": "book_id required"}), 400
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    cart = user.setdefault("cart", [])
    if book_id in cart:
        cart.remove(book_id)
        action = "removed"
    else:
        cart.append(book_id)
        action = "added"
    _save_users(users)
    return jsonify({"action": action, "book_id": book_id, "total_cart": len(cart)})


@blueprint.route("/api/users/<int:user_id>/cart", methods=["GET"])
def api_cart_get(user_id):
    user = _get_user(user_id)
    if not user:
        abort(404)
    books = _query_books(limit=2000)
    cart_ids = user.get("cart", [])
    cart_items = [b for b in books if b["id"] in cart_ids]
    safe = [{k: v for k, v in b.items() if k != "chapters"} for b in cart_items]
    total = sum(b["price"] for b in cart_items)
    return jsonify({"items": safe, "total": round(total, 2), "count": len(safe)})


@blueprint.route("/api/users/<int:user_id>/checkout", methods=["POST"])
def api_checkout(user_id):
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    card = data.get("card", "").strip()
    if not name or not email or not card:
        return jsonify({"error": "name, email, and card are required"}), 400
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    cart = user.get("cart", [])
    if not cart:
        return jsonify({"error": "Cart is empty"}), 400
    books = _query_books(limit=2000)
    cart_items = [b for b in books if b["id"] in cart]
    total = sum(b["price"] for b in cart_items)
    # Move cart items to reading list
    reading = user.setdefault("reading_list", [])
    for bid in cart:
        if bid not in reading:
            reading.append(bid)
    account_type = data.get("account_type", "checking")
    user["cart"] = []
    _save_users(users)
    emit("purchase", user_id=user["id"], amount=total, merchant="BookVerse", item=f"{len(cart_items)} books", account_type=account_type)
    return jsonify({
        "status": "completed",
        "items_purchased": len(cart_items),
        "total": round(total, 2),
        "reading_list_count": len(reading)
    })


@blueprint.route("/api/reviews/<int:book_id>", methods=["GET"])
def api_get_reviews(book_id):
    return jsonify(_load_reviews(book_id=book_id))


@blueprint.route("/api/reviews/<int:book_id>", methods=["POST"])
def api_post_review(book_id):
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    rating = data.get("rating")
    user_id = data.get("user_id")
    if not text:
        return jsonify({"error": "text required"}), 400
    reviews = _load_reviews()
    review = {
        "id": len(reviews) + 1,
        "book_id": book_id,
        "user_id": user_id,
        "text": text,
        "rating": rating,
    }
    reviews.append(review)
    _save_reviews(reviews)
    return jsonify(review)


@blueprint.route("/api/reviews/<int:book_id>/react", methods=["POST"])
def api_react_review(book_id):
    data = request.get_json(silent=True) or {}
    review_id = data.get("review_id")
    reaction = data.get("reaction", "like")
    reviews = _load_reviews()
    review = next((r for r in reviews if r.get("id") == review_id), None)
    if not review:
        return jsonify({"error": "Review not found"}), 404
    reactions = review.setdefault("reactions", {})
    current = reactions.get(reaction, 0)
    reactions[reaction] = current + 1
    _save_reviews(reviews)
    return jsonify({"review_id": review_id, "reaction": reaction, "count": reactions[reaction]})


@blueprint.route("/api/books/<int:book_id>/rate", methods=["POST"])
def api_rate_book(book_id):
    data = request.get_json(silent=True) or {}
    rating = data.get("rating")
    user_id = data.get("user_id")
    if rating is None:
        return jsonify({"error": "rating required"}), 400
    try:
        rating = float(rating)
    except (TypeError, ValueError):
        return jsonify({"error": "rating must be a number"}), 400
    if rating < 1 or rating > 5:
        return jsonify({"error": "rating must be between 1 and 5"}), 400
    reviews = _load_reviews()
    review = {
        "id": len(reviews) + 1,
        "book_id": book_id,
        "user_id": user_id,
        "text": "",
        "rating": rating,
    }
    reviews.append(review)
    _save_reviews(reviews)
    return jsonify({"book_id": book_id, "rating": rating, "status": "rated"})


@blueprint.route("/api/users/<int:user_id>/reading-progress", methods=["POST"])
def api_reading_progress(user_id):
    """Track reading progress (play_by_playback)."""
    data = request.get_json(silent=True) or {}
    book_id = data.get("book_id")
    chapter = data.get("chapter", 1)
    progress = data.get("progress", 0)  # 0-100 percent
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    reading_progress = user.setdefault("reading_progress", {})
    reading_progress[str(book_id)] = {
        "chapter": chapter,
        "progress": progress
    }
    _save_users(users)
    return jsonify({
        "book_id": book_id,
        "chapter": chapter,
        "progress": progress,
        "status": "updated"
    })


@blueprint.route("/api/users/<int:user_id>/reading-progress", methods=["GET"])
def api_get_reading_progress(user_id):
    user = _get_user(user_id)
    if not user:
        abort(404)
    return jsonify(user.get("reading_progress", {}))
