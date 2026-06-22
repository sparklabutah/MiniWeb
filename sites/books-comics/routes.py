"""Books & Comics — digital platform for discovering, reading, and organizing books/comics.

Data interpreter: reads the pressbooks gzipped JSONL snapshot, samples based on
config/config.json, and serves through Flask routes. The raw data file is
never modified.
"""
import gzip
import hashlib
import json
import pathlib
import random
import re
from collections import Counter

from flask import Blueprint, Response, abort, jsonify, render_template, request, session

SITE_DIR = pathlib.Path(__file__).resolve().parent
CONFIG_FILE = SITE_DIR / "config" / "config.json"
USERS_FILE = SITE_DIR / "data" / "users.json"
REVIEWS_FILE = SITE_DIR / "data" / "reviews.json"
CART_FILE = SITE_DIR / "data" / "cart.json"
CATEGORIES_FILE = SITE_DIR / "data" / "categories.json"

blueprint = Blueprint(
    "books-comics",
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
# Data interpreter — reads gzipped JSONL, parses metadata, samples
# ---------------------------------------------------------------------------

def _parse_authors(author_str):
    """Parse author string like 'John Smith, Jane Doe' into a list."""
    if not author_str:
        return ["Unknown Author"]
    authors = [a.strip() for a in author_str.split(",") if a.strip()]
    return authors if authors else ["Unknown Author"]


def _extract_year(created_str):
    """Extract year from created field like '09-30-2024'."""
    if not created_str:
        return 2020
    m = re.search(r'\b(19|20)\d{2}\b', created_str)
    if m:
        return int(m.group())
    return 2020


def _classify_subject(subject_str):
    """Map a pressbooks subject string to one of our category slugs."""
    if not subject_str:
        return "reference"
    s = subject_str.lower()
    if any(w in s for w in ["comic", "graphic novel", "manga", "sequential art"]):
        return "comics"
    if any(w in s for w in ["fiction", "novel", "story", "literary", "poetry", "drama"]):
        return "fiction"
    if any(w in s for w in ["science", "physics", "chemistry", "biology", "engineering",
                             "computer", "technology", "math", "statistics"]):
        return "science"
    if any(w in s for w in ["history", "philosophy", "sociology", "psychology",
                             "political", "anthropology", "cultural", "social"]):
        return "humanities"
    if any(w in s for w in ["education", "teaching", "pedagogy", "curriculum",
                             "learning", "student"]):
        return "education"
    if any(w in s for w in ["health", "medicine", "nursing", "medical", "clinical",
                             "anatomy", "physiology"]):
        return "health"
    if any(w in s for w in ["business", "economics", "finance", "management",
                             "marketing", "accounting"]):
        return "business"
    if any(w in s for w in ["art", "design", "music", "visual", "creative",
                             "film", "media", "photography"]):
        return "arts"
    if any(w in s for w in ["language", "linguistic", "english", "writing",
                             "grammar", "literature", "composition", "rhetoric"]):
        return "language"
    return "reference"


def _generate_chapters(text, book_id):
    """Split text into chapters/pages for the reader."""
    if not text:
        return [{"chapter": 1, "title": "Chapter 1", "content": "Content not available."}]
    # Split on common chapter markers or just by paragraph blocks
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    if not paragraphs:
        return [{"chapter": 1, "title": "Chapter 1", "content": text[:2000]}]

    # Group paragraphs into chapters of ~500 words each
    chapters = []
    current_content = []
    word_count = 0
    ch_num = 1

    for para in paragraphs:
        current_content.append(para)
        word_count += len(para.split())
        if word_count >= 500:
            chapters.append({
                "chapter": ch_num,
                "title": f"Chapter {ch_num}",
                "content": "\n\n".join(current_content)
            })
            ch_num += 1
            current_content = []
            word_count = 0

    if current_content:
        chapters.append({
            "chapter": ch_num,
            "title": f"Chapter {ch_num}",
            "content": "\n\n".join(current_content)
        })

    return chapters if chapters else [{"chapter": 1, "title": "Chapter 1", "content": text[:2000]}]


def _generate_price(seed_val):
    """Generate a deterministic price for a book."""
    rng = random.Random(seed_val)
    base = rng.choice([0.0, 0.0, 0.0, 2.99, 4.99, 7.99, 9.99, 12.99, 14.99, 19.99])
    return base


def _interpret_record(raw, idx):
    """Convert a raw pressbooks JSONL record into our book data model."""
    metadata = raw.get("metadata", {})
    author_str = metadata.get("author", "")
    authors = _parse_authors(author_str)
    title = metadata.get("title", "Untitled Book")
    title = re.sub(r'\s+', ' ', title.replace("\n", " ")).strip()
    if not title:
        title = "Untitled Book"
    subject = metadata.get("subject", "")
    category = _classify_subject(subject)
    year = _extract_year(raw.get("created", ""))
    text = raw.get("text", "")
    # Create a short description from the first ~200 chars of text
    description = re.sub(r'\s+', ' ', text[:500]).strip()
    if len(description) > 200:
        description = description[:200] + "..."
    chapters = _generate_chapters(text, idx)
    price = _generate_price(idx * 7 + 13)
    institution = metadata.get("institution", "")
    license_info = metadata.get("license", "")
    book_url = metadata.get("book_url", raw.get("id", ""))

    # Generate a rating based on text length and seed
    rng = random.Random(idx * 31 + 7)
    rating = round(rng.uniform(2.5, 5.0), 1)
    rating_count = rng.randint(3, 250)

    # Deterministic cover image from picsum using a hash of the title
    title_hash = hashlib.md5(title.encode()).hexdigest()[:10]
    cover_url = f"https://placehold.co/200x280/EEE/999?text={title_hash}"

    return {
        "id": idx,
        "title": title,
        "authors": authors,
        "authors_str": ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else ""),
        "description": description,
        "category": category,
        "subject": subject,
        "year": year,
        "chapters": chapters,
        "num_chapters": len(chapters),
        "price": price,
        "price_str": "Free" if price == 0.0 else f"${price:.2f}",
        "rating": rating,
        "rating_count": rating_count,
        "institution": institution,
        "license": license_info,
        "source_url": book_url,
        "word_count": len(text.split()) if text else 0,
        "cover_url": cover_url,
    }


def _load_books():
    """Read gzipped JSONL dataset with reservoir sampling."""
    config = _load_config()
    n = config.get("num_data_points", -1)
    seed = config.get("random_seed", 42)
    data_path = config.get("pressbooks_data_path", "")
    rng = random.Random(seed)

    if not data_path:
        return []

    if n > 0:
        # Reservoir sampling
        reservoir = []
        with gzip.open(data_path, "rt", encoding="utf-8") as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if len(reservoir) < n:
                    reservoir.append(raw)
                else:
                    j = rng.randint(0, i)
                    if j < n:
                        reservoir[j] = raw
        selected = reservoir
    else:
        selected = []
        with gzip.open(data_path, "rt", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    selected.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    # De-duplicate by title (pressbooks has multiple chapters per book)
    seen_titles = {}
    unique = []
    for raw in selected:
        t = raw.get("metadata", {}).get("title", "")
        if t and t in seen_titles:
            # Merge: append text to existing
            existing = seen_titles[t]
            existing["text"] = existing.get("text", "") + "\n\n" + raw.get("text", "")
        else:
            seen_titles[t] = raw
            unique.append(raw)

    books = []
    for idx, raw in enumerate(unique, 1):
        books.append(_interpret_record(raw, idx))

    books.sort(key=lambda b: (-b["year"], b["title"]))
    for i, b in enumerate(books, 1):
        b["id"] = i

    return books


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------

_books = None
_categories_data = None


def _ensure_loaded():
    global _books, _categories_data
    if _books is None:
        _books = _load_books()
        if CATEGORIES_FILE.exists():
            _categories_data = json.loads(CATEGORIES_FILE.read_text())
        else:
            _categories_data = []


def _get_books():
    _ensure_loaded()
    return _books


def _get_categories():
    _ensure_loaded()
    return _categories_data


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
# Reviews (mutable state)
# ---------------------------------------------------------------------------

def _load_reviews():
    if REVIEWS_FILE.exists():
        return json.loads(REVIEWS_FILE.read_text())
    return []


def _save_reviews(reviews):
    REVIEWS_FILE.write_text(json.dumps(reviews, indent=2))


# ---------------------------------------------------------------------------
# Search helpers
# ---------------------------------------------------------------------------

def _keyword_score(query, book):
    terms = query.lower().split()
    text = (book["title"] + " " + book["description"] + " " +
            " ".join(book["authors"]) + " " + book["category"] + " " +
            book.get("subject", "")).lower()
    return sum(1 for t in terms if t in text)


def _search_books(books, query, semantic=False):
    if not query:
        return books
    q = query.lower().strip()
    if semantic:
        scored = [(b, _keyword_score(q, b)) for b in books]
        scored = [(b, s) for b, s in scored if s > 0]
        scored.sort(key=lambda x: -x[1])
        return [b for b, _ in scored]
    else:
        return [b for b in books if q in b["title"].lower() or
                q in b["authors_str"].lower() or
                q in b["category"].lower()]


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    books = _get_books()
    categories = _get_categories()
    q = request.args.get("q", "").strip()
    cat = request.args.get("category", "").strip()
    min_rating = request.args.get("min_rating", "").strip()
    sort = request.args.get("sort", "newest").strip()
    price_filter = request.args.get("price", "").strip()

    results = list(books)

    if q:
        results = _search_books(results, q)
    if cat:
        results = [b for b in results if b["category"] == cat]
    if min_rating:
        try:
            mr = float(min_rating)
            results = [b for b in results if b["rating"] >= mr]
        except ValueError:
            pass
    if price_filter == "free":
        results = [b for b in results if b["price"] == 0.0]
    elif price_filter == "paid":
        results = [b for b in results if b["price"] > 0.0]

    if sort == "newest":
        results.sort(key=lambda b: (-b["year"], b["title"]))
    elif sort == "title":
        results.sort(key=lambda b: b["title"].lower())
    elif sort == "rating":
        results.sort(key=lambda b: (-b["rating"], b["title"]))
    elif sort == "price_low":
        results.sort(key=lambda b: (b["price"], b["title"]))
    elif sort == "price_high":
        results.sort(key=lambda b: (-b["price"], b["title"]))
    elif sort == "relevance" and q:
        results.sort(key=lambda b: -_keyword_score(q, b))

    # Pagination
    page = request.args.get("page", 1, type=int)
    per_page = 30
    total_results = len(results)
    total_pages = max(1, (total_results + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    paginated = results[(page - 1) * per_page : page * per_page]

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template("books-comics/index.html",
                           books=paginated, categories=categories,
                           q=q, cat=cat, min_rating=min_rating,
                           sort=sort, price_filter=price_filter, user=user,
                           page=page, total_pages=total_pages,
                           total_results=total_results)


@blueprint.route("/book/<int:book_id>")
def book_detail(book_id):
    books = _get_books()
    book = next((b for b in books if b["id"] == book_id), None)
    if book is None:
        abort(404)
    related = [b for b in books if b["category"] == book["category"]
               and b["id"] != book_id][:5]
    reviews = [r for r in _load_reviews() if r.get("book_id") == book_id]
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("books-comics/book.html", book=book,
                           related=related, reviews=reviews, user=user)


@blueprint.route("/book/<int:book_id>/read")
def read_book(book_id):
    books = _get_books()
    book = next((b for b in books if b["id"] == book_id), None)
    if book is None:
        abort(404)
    chapter = request.args.get("chapter", 1, type=int)
    chapters = book.get("chapters", [])
    current = next((c for c in chapters if c["chapter"] == chapter), None)
    if current is None and chapters:
        current = chapters[0]
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("books-comics/reader.html", book=book,
                           chapters=chapters, current=current,
                           chapter_num=chapter, user=user)


@blueprint.route("/category/<slug>")
def category_page(slug):
    books = _get_books()
    categories = _get_categories()
    filtered = [b for b in books if b["category"] == slug]
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
    books = _get_books()
    cart_items = [b for b in books if b["id"] in user.get("cart", [])]
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
    books = _get_books()
    cart_items = [b for b in books if b["id"] in user.get("cart", [])]
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
        return render_template("books-comics/checkout.html", user=user,
                               cart_items=cart_items, total=total,
                               success=True, error=None)

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
    books = _get_books()
    saved = [b for b in books if b["id"] in user.get("saved_books", [])]
    reading = [b for b in books if b["id"] in user.get("reading_list", [])]
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
    books = _get_books()
    saved = [b for b in books if b["id"] in user.get("saved_books", [])]
    reading = [b for b in books if b["id"] in user.get("reading_list", [])]
    return render_template("books-comics/dashboard.html", user=user,
                           saved_books=saved, reading_list=reading,
                           followed_authors=user.get("followed_authors", []),
                           subscriptions=user.get("subscriptions", []))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return render_template("books-comics/login.html", error=None)


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/books")
def api_books():
    books = _get_books()
    q = request.args.get("q", "").strip()
    cat = request.args.get("category", "").strip()
    min_rating = request.args.get("min_rating", type=float)
    max_price = request.args.get("max_price", type=float)
    sort = request.args.get("sort", "newest")
    limit = request.args.get("limit", type=int)

    results = list(books)
    if q:
        results = _search_books(results, q)
    if cat:
        results = [b for b in results if b["category"] == cat]
    if min_rating is not None:
        results = [b for b in results if b["rating"] >= min_rating]
    if max_price is not None:
        results = [b for b in results if b["price"] <= max_price]

    if sort == "newest":
        results.sort(key=lambda b: (-b["year"], b["title"]))
    elif sort == "title":
        results.sort(key=lambda b: b["title"].lower())
    elif sort == "rating":
        results.sort(key=lambda b: (-b["rating"], b["title"]))
    elif sort == "price_low":
        results.sort(key=lambda b: (b["price"], b["title"]))
    elif sort == "relevance" and q:
        results.sort(key=lambda b: -_keyword_score(q, b))

    if limit:
        results = results[:limit]

    # Strip chapters from list response to reduce size
    safe = []
    for b in results:
        entry = {k: v for k, v in b.items() if k != "chapters"}
        safe.append(entry)
    return jsonify(safe)


@blueprint.route("/api/books/<int:book_id>")
def api_book(book_id):
    books = _get_books()
    book = next((b for b in books if b["id"] == book_id), None)
    if book is None:
        abort(404)
    # Return book without full chapter content, but with chapter listing
    result = {k: v for k, v in book.items() if k != "chapters"}
    result["chapters"] = [{"chapter": c["chapter"], "title": c["title"]}
                          for c in book.get("chapters", [])]
    return jsonify(result)


@blueprint.route("/api/books/<int:book_id>/chapters")
def api_book_chapters(book_id):
    books = _get_books()
    book = next((b for b in books if b["id"] == book_id), None)
    if book is None:
        abort(404)
    return jsonify(book.get("chapters", []))


@blueprint.route("/api/books/<int:book_id>/chapters/<int:ch_num>")
def api_book_chapter(book_id, ch_num):
    books = _get_books()
    book = next((b for b in books if b["id"] == book_id), None)
    if book is None:
        abort(404)
    chapters = book.get("chapters", [])
    chapter = next((c for c in chapters if c["chapter"] == ch_num), None)
    if chapter is None:
        abort(404)
    return jsonify(chapter)


@blueprint.route("/api/books/search")
def api_search():
    q = request.args.get("q", "").strip()
    books = _get_books()
    results = _search_books(books, q)
    safe = [{k: v for k, v in b.items() if k != "chapters"} for b in results]
    return jsonify(safe)


@blueprint.route("/api/books/semantic")
def api_semantic_search():
    q = request.args.get("q", "").strip()
    books = _get_books()
    results = _search_books(books, q, semantic=True)
    safe = [{k: v for k, v in b.items() if k != "chapters"} for b in results]
    return jsonify(safe)


@blueprint.route("/api/categories")
def api_categories():
    books = _get_books()
    cats = _get_categories()
    counts = Counter(b["category"] for b in books)
    result = []
    for c in cats:
        result.append({
            "slug": c["slug"],
            "name": c["name"],
            "description": c.get("description", ""),
            "count": counts.get(c["slug"], 0)
        })
    return jsonify(result)


@blueprint.route("/api/categories/<slug>/books")
def api_category_books(slug):
    books = _get_books()
    filtered = [b for b in books if b["category"] == slug]
    safe = [{k: v for k, v in b.items() if k != "chapters"} for b in filtered]
    return jsonify(safe)


@blueprint.route("/api/categories/<slug>/stats")
def api_category_stats(slug):
    books = _get_books()
    filtered = [b for b in books if b["category"] == slug]
    if not filtered:
        return jsonify({"category": slug, "count": 0})
    years = [b["year"] for b in filtered]
    authors = set()
    for b in filtered:
        authors.update(b["authors"])
    ratings = [b["rating"] for b in filtered]
    return jsonify({
        "category": slug,
        "count": len(filtered),
        "earliest_year": min(years),
        "latest_year": max(years),
        "unique_authors": len(authors),
        "avg_rating": round(sum(ratings) / len(ratings), 2),
        "avg_year": round(sum(years) / len(years), 1),
    })


@blueprint.route("/api/stats")
def api_stats():
    books = _get_books()
    cat = request.args.get("category", "").strip()
    if cat:
        books = [b for b in books if b["category"] == cat]
    if not books:
        return jsonify({"count": 0})
    years = [b["year"] for b in books]
    authors = set()
    for b in books:
        authors.update(b["authors"])
    ratings = [b["rating"] for b in books]
    return jsonify({
        "count": len(books),
        "earliest_year": min(years),
        "latest_year": max(years),
        "unique_authors": len(authors),
        "avg_rating": round(sum(ratings) / len(ratings), 2),
        "top_categories": dict(Counter(b["category"] for b in books).most_common(10)),
        "free_count": sum(1 for b in books if b["price"] == 0.0),
        "paid_count": sum(1 for b in books if b["price"] > 0.0),
    })


@blueprint.route("/api/export")
def api_export():
    fmt = request.args.get("format", "json").lower()
    cat = request.args.get("category", "").strip()
    books = list(_get_books())
    if cat:
        books = [b for b in books if b["category"] == cat]

    safe = [{k: v for k, v in b.items() if k != "chapters"} for b in books]

    if fmt == "csv":
        lines = ["id,title,authors,category,year,rating,price"]
        for b in safe:
            title = b["title"].replace('"', '""')
            authors = b["authors_str"].replace('"', '""')
            lines.append(f'{b["id"]},"{title}","{authors}","{b["category"]}",{b["year"]},{b["rating"]},{b["price"]}')
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
    books = _get_books()
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
    books = _get_books()
    cart_items = [b for b in books if b["id"] in cart]
    total = sum(b["price"] for b in cart_items)
    # Move cart items to reading list
    reading = user.setdefault("reading_list", [])
    for bid in cart:
        if bid not in reading:
            reading.append(bid)
    user["cart"] = []
    _save_users(users)
    return jsonify({
        "status": "completed",
        "items_purchased": len(cart_items),
        "total": round(total, 2),
        "reading_list_count": len(reading)
    })


@blueprint.route("/api/reviews/<int:book_id>", methods=["GET"])
def api_get_reviews(book_id):
    reviews = _load_reviews()
    book_reviews = [r for r in reviews if r.get("book_id") == book_id]
    return jsonify(book_reviews)


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
