"""E-commerce — Online marketplace (Amazon/eBay style).

Data interpreter: reads products.jsonl line by line, parses each JSON object,
cleans and normalizes fields. The raw data file is never modified.
"""
import json
import pathlib
import random
import re
import datetime
from collections import Counter

from flask import Blueprint, Response, abort, jsonify, redirect, render_template, request, session, url_for

SITE_DIR = pathlib.Path(__file__).resolve().parent
DATA_FILE = SITE_DIR / "data" / "products.jsonl"
USERS_FILE = SITE_DIR / "data" / "users.json"
REVIEWS_FILE = SITE_DIR / "data" / "reviews.json"
CONFIG_FILE = SITE_DIR / "config" / "config.json"

blueprint = Blueprint(
    "e-commerce",
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
# Data interpreter — reads raw JSONL, cleans, normalizes
# ---------------------------------------------------------------------------

def _parse_price(pricing_str):
    """Parse pricing string like '$877.80' or '$22.99$25.99' to float.
    Takes the first price found. Returns 0.0 if unparseable."""
    if not pricing_str:
        return 0.0
    m = re.search(r'\$(\d+(?:\.\d{1,2})?)', str(pricing_str))
    if m:
        return float(m.group(1))
    return 0.0


def _clean_brand(brand_str):
    """Clean brand field: remove 'Brand: ' prefix, 'Visit the X Store' pattern."""
    if not brand_str:
        return ""
    brand_str = brand_str.strip()
    if brand_str.startswith("Brand: "):
        return brand_str[7:].strip()
    if brand_str.startswith("Visit the "):
        brand_str = brand_str[10:]
        if brand_str.endswith(" Store"):
            brand_str = brand_str[:-6]
        return brand_str.strip()
    return brand_str


def _parse_categories(product_category_str):
    """Split 'Beauty & Personal Care > Oral Care > Toothpaste' into list."""
    if not product_category_str:
        return []
    parts = [p.strip() for p in product_category_str.split("\u203a")]
    return [p for p in parts if p]


def _get_description(raw):
    """Build description from full_description and small_description."""
    desc = raw.get("full_description", "") or ""
    if not desc:
        small = raw.get("small_description", [])
        if isinstance(small, list):
            desc = " ".join(s.strip() for s in small if isinstance(s, str) and s.strip())
        elif isinstance(small, str):
            desc = small
    return desc.strip()


def _interpret_product(raw, idx):
    """Convert raw JSONL record to normalized product dict."""
    categories = _parse_categories(raw.get("product_category", ""))
    top_category = categories[0] if categories else "Other"

    rating = raw.get("average_rating")
    if isinstance(rating, str):
        m = re.search(r'(\d+\.?\d*)', rating)
        rating = float(m.group(1)) if m else 0.0
    elif isinstance(rating, (int, float)):
        rating = float(rating)
    else:
        rating = 0.0

    total_reviews = raw.get("total_reviews")
    if isinstance(total_reviews, str):
        m = re.search(r'(\d+)', total_reviews.replace(",", ""))
        total_reviews = int(m.group(1)) if m else 0
    elif isinstance(total_reviews, (int, float)):
        total_reviews = int(total_reviews)
    else:
        total_reviews = 0

    images = raw.get("images", [])
    # Filter out transparent pixel placeholders
    images = [img for img in images if img and "transparent-pixel" not in img]

    availability = raw.get("availability_status", "") or ""
    avail_qty = raw.get("availability_quantity")
    if isinstance(avail_qty, (int, float)):
        avail_qty = int(avail_qty)
    else:
        avail_qty = None

    return {
        "id": idx,
        "asin": raw.get("asin", ""),
        "name": raw.get("name", "").strip(),
        "brand": _clean_brand(raw.get("brand", "")),
        "price": _parse_price(raw.get("pricing", "")),
        "pricing_raw": raw.get("pricing", ""),
        "list_price": raw.get("list_price", ""),
        "categories": categories,
        "top_category": top_category,
        "category_path": raw.get("product_category", ""),
        "description": _get_description(raw),
        "small_description": raw.get("small_description", []),
        "rating": rating,
        "total_reviews": total_reviews,
        "availability": availability,
        "availability_quantity": avail_qty,
        "images": images,
        "seller_name": raw.get("seller_name", "") or "",
        "query": raw.get("query", ""),
    }


def _load_products():
    """Read JSONL dataset, respecting config."""
    config = _load_config()
    n = config.get("num_data_points", -1)
    seed = config.get("random_seed", 42)
    rng = random.Random(seed)

    raw_records = []
    with open(DATA_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                raw_records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if 0 < n < len(raw_records):
        raw_records = rng.sample(raw_records, n)

    products = []
    for idx, raw in enumerate(raw_records, 1):
        products.append(_interpret_product(raw, idx))

    products.sort(key=lambda p: p["name"].lower())
    for i, p in enumerate(products, 1):
        p["id"] = i

    return products


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------

_products = None
_top_categories = None
_all_brands = None


def _ensure_loaded():
    global _products, _top_categories, _all_brands
    if _products is None:
        _products = _load_products()
        cat_counts = Counter(p["top_category"] for p in _products)
        _top_categories = sorted(cat_counts.keys())
        brand_counts = Counter(p["brand"] for p in _products if p["brand"])
        _all_brands = sorted(brand_counts.keys())


def _get_products():
    _ensure_loaded()
    return _products


def _get_top_categories():
    _ensure_loaded()
    return _top_categories


def _get_all_brands():
    _ensure_loaded()
    return _all_brands


def _get_product_by_id(product_id):
    products = _get_products()
    return next((p for p in products if p["id"] == product_id), None)


def _get_product_by_asin(asin):
    products = _get_products()
    return next((p for p in products if p["asin"] == asin), None)


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
# Search / filter helpers
# ---------------------------------------------------------------------------

def _keyword_score(query, product):
    terms = query.lower().split()
    text = (product["name"] + " " + product["brand"] + " " +
            product["description"] + " " + " ".join(product["categories"])).lower()
    return sum(1 for t in terms if t in text)


def _search_products(products, query):
    if not query:
        return products
    q = query.lower().strip()
    scored = [(p, _keyword_score(q, p)) for p in products]
    scored = [(p, s) for p, s in scored if s > 0]
    scored.sort(key=lambda x: -x[1])
    return [p for p, _ in scored]


def _filter_products(products, category=None, brand=None, min_price=None,
                     max_price=None, min_rating=None):
    results = list(products)
    if category:
        results = [p for p in results if p["top_category"] == category or
                   category in p["categories"]]
    if brand:
        results = [p for p in results if p["brand"].lower() == brand.lower()]
    if min_price is not None:
        results = [p for p in results if p["price"] >= min_price]
    if max_price is not None:
        results = [p for p in results if p["price"] <= max_price]
    if min_rating is not None:
        results = [p for p in results if p["rating"] >= min_rating]
    return results


def _sort_products(products, sort_key):
    if sort_key == "price_asc":
        return sorted(products, key=lambda p: p["price"])
    elif sort_key == "price_desc":
        return sorted(products, key=lambda p: -p["price"])
    elif sort_key == "rating":
        return sorted(products, key=lambda p: -p["rating"])
    elif sort_key == "name":
        return sorted(products, key=lambda p: p["name"].lower())
    elif sort_key == "reviews":
        return sorted(products, key=lambda p: -p["total_reviews"])
    return products


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    products = _get_products()
    categories = _get_top_categories()
    brands = _get_all_brands()

    q = request.args.get("q", "").strip()
    cat = request.args.get("category", "").strip()
    brand = request.args.get("brand", "").strip()
    min_price = request.args.get("min_price", type=float)
    max_price = request.args.get("max_price", type=float)
    min_rating = request.args.get("min_rating", type=float)
    sort = request.args.get("sort", "").strip()

    results = list(products)
    if q:
        results = _search_products(results, q)
    results = _filter_products(results, category=cat, brand=brand,
                               min_price=min_price, max_price=max_price,
                               min_rating=min_rating)
    if sort:
        results = _sort_products(results, sort)

    # Pagination
    per_page = 24
    page = request.args.get("page", 1, type=int)
    if page < 1:
        page = 1
    total_results = len(results)
    total_pages = max(1, (total_results + per_page - 1) // per_page)
    if page > total_pages:
        page = total_pages
    start = (page - 1) * per_page
    paged_results = results[start:start + per_page]

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template("e-commerce/index.html",
                           products=paged_results, categories=categories,
                           brands=brands, q=q, cat=cat, brand=brand,
                           min_price=min_price, max_price=max_price,
                           min_rating=min_rating, sort=sort, user=user,
                           page=page, total_pages=total_pages,
                           total_results=total_results)


@blueprint.route("/product/<int:product_id>")
def product_detail(product_id):
    product = _get_product_by_id(product_id)
    if product is None:
        abort(404)
    reviews = _load_reviews()
    product_reviews = [r for r in reviews if r["product_asin"] == product["asin"]]
    product_reviews.sort(key=lambda r: r["date"], reverse=True)

    # Related products in same category
    products = _get_products()
    related = [p for p in products if p["top_category"] == product["top_category"]
               and p["id"] != product_id][:6]

    user = None
    in_wishlist = False
    in_cart = False
    if "user_id" in session:
        user = _get_user(session["user_id"])
        if user:
            in_wishlist = product_id in user.get("wishlist", [])
            in_cart = any(item["product_id"] == product_id for item in user.get("cart", []))

    return render_template("e-commerce/product.html", product=product,
                           reviews=product_reviews, related=related,
                           user=user, in_wishlist=in_wishlist, in_cart=in_cart)


@blueprint.route("/category/<path:cat_name>")
def category_page(cat_name):
    products = _get_products()
    filtered = [p for p in products if p["top_category"] == cat_name or
                cat_name in p["categories"]]

    sort = request.args.get("sort", "").strip()
    if sort:
        filtered = _sort_products(filtered, sort)

    min_price = request.args.get("min_price", type=float)
    max_price = request.args.get("max_price", type=float)
    min_rating = request.args.get("min_rating", type=float)
    filtered = _filter_products(filtered, min_price=min_price,
                                max_price=max_price, min_rating=min_rating)

    # Pagination
    per_page = 24
    page = request.args.get("page", 1, type=int)
    if page < 1:
        page = 1
    total_results = len(filtered)
    total_pages = max(1, (total_results + per_page - 1) // per_page)
    if page > total_pages:
        page = total_pages
    start = (page - 1) * per_page
    paged_results = filtered[start:start + per_page]

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template("e-commerce/category.html",
                           products=paged_results, category=cat_name,
                           categories=_get_top_categories(), sort=sort,
                           min_price=min_price, max_price=max_price,
                           min_rating=min_rating, user=user,
                           page=page, total_pages=total_pages,
                           total_results=total_results)


@blueprint.route("/cart")
def cart_page():
    if "user_id" not in session:
        return redirect(url_for("e-commerce.login_page"))
    user = _get_user(session["user_id"])
    if not user:
        return redirect(url_for("e-commerce.login_page"))

    cart_items = []
    total = 0.0
    for item in user.get("cart", []):
        product = _get_product_by_id(item["product_id"])
        if product:
            subtotal = product["price"] * item["quantity"]
            cart_items.append({
                "product": product,
                "quantity": item["quantity"],
                "subtotal": round(subtotal, 2),
            })
            total += subtotal

    return render_template("e-commerce/cart.html", cart_items=cart_items,
                           total=round(total, 2), user=user)


@blueprint.route("/orders")
def orders_page():
    if "user_id" not in session:
        return redirect(url_for("e-commerce.login_page"))
    user = _get_user(session["user_id"])
    if not user:
        return redirect(url_for("e-commerce.login_page"))
    orders = user.get("orders", [])
    return render_template("e-commerce/orders.html", orders=orders, user=user)


@blueprint.route("/wishlist")
def wishlist_page():
    if "user_id" not in session:
        return redirect(url_for("e-commerce.login_page"))
    user = _get_user(session["user_id"])
    if not user:
        return redirect(url_for("e-commerce.login_page"))

    products = _get_products()
    wishlist_items = [p for p in products if p["id"] in user.get("wishlist", [])]

    return render_template("e-commerce/wishlist.html",
                           wishlist_items=wishlist_items,
                           wishlist_products=wishlist_items, user=user)


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("e-commerce/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return render_template("e-commerce/login.html",
                               error="Invalid username or password")
    session["user_id"] = user["id"]
    return redirect(url_for("e-commerce.index"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("e-commerce.index"))


# ---------------------------------------------------------------------------
# Form-based mutation routes
# ---------------------------------------------------------------------------

@blueprint.route("/cart/add", methods=["POST"])
def form_add_to_cart():
    if "user_id" not in session:
        return redirect(url_for("e-commerce.login_page"))
    product_id = request.form.get("product_id", type=int)
    quantity = request.form.get("quantity", 1, type=int)
    if not product_id or quantity < 1:
        return redirect(url_for("e-commerce.index"))

    users = _load_users()
    user = next((u for u in users if u["id"] == session["user_id"]), None)
    if not user:
        return redirect(url_for("e-commerce.login_page"))

    cart = user.setdefault("cart", [])
    existing = next((item for item in cart if item["product_id"] == product_id), None)
    if existing:
        existing["quantity"] += quantity
    else:
        cart.append({"product_id": product_id, "quantity": quantity})
    _save_users(users)
    redirect_to = request.form.get("redirect_to", "")
    if redirect_to:
        return redirect(redirect_to)
    return redirect(url_for("e-commerce.cart_page"))


@blueprint.route("/cart/remove", methods=["POST"])
def form_remove_from_cart():
    if "user_id" not in session:
        return redirect(url_for("e-commerce.login_page"))
    product_id = request.form.get("product_id", type=int)

    users = _load_users()
    user = next((u for u in users if u["id"] == session["user_id"]), None)
    if not user:
        return redirect(url_for("e-commerce.login_page"))

    cart = user.get("cart", [])
    user["cart"] = [item for item in cart if item["product_id"] != product_id]
    _save_users(users)
    return redirect(url_for("e-commerce.cart_page"))


@blueprint.route("/cart/update", methods=["POST"])
def form_update_cart():
    if "user_id" not in session:
        return redirect(url_for("e-commerce.login_page"))
    product_id = request.form.get("product_id", type=int)
    quantity = request.form.get("quantity", 1, type=int)

    users = _load_users()
    user = next((u for u in users if u["id"] == session["user_id"]), None)
    if not user:
        return redirect(url_for("e-commerce.login_page"))

    cart = user.get("cart", [])
    existing = next((item for item in cart if item["product_id"] == product_id), None)
    if existing:
        if quantity <= 0:
            user["cart"] = [item for item in cart if item["product_id"] != product_id]
        else:
            existing["quantity"] = quantity
    _save_users(users)
    return redirect(url_for("e-commerce.cart_page"))


@blueprint.route("/wishlist/toggle", methods=["POST"])
def form_toggle_wishlist():
    if "user_id" not in session:
        return redirect(url_for("e-commerce.login_page"))
    product_id = request.form.get("product_id", type=int)
    if not product_id:
        return redirect(url_for("e-commerce.index"))

    users = _load_users()
    user = next((u for u in users if u["id"] == session["user_id"]), None)
    if not user:
        return redirect(url_for("e-commerce.login_page"))

    wishlist = user.setdefault("wishlist", [])
    if product_id in wishlist:
        wishlist.remove(product_id)
    else:
        wishlist.append(product_id)
    _save_users(users)

    redirect_to = request.form.get("redirect_to", "")
    if redirect_to:
        return redirect(redirect_to)
    return redirect(url_for("e-commerce.product_detail", product_id=product_id))


@blueprint.route("/checkout", methods=["POST"])
def form_checkout():
    if "user_id" not in session:
        return redirect(url_for("e-commerce.login_page"))

    users = _load_users()
    user = next((u for u in users if u["id"] == session["user_id"]), None)
    if not user:
        return redirect(url_for("e-commerce.login_page"))

    cart = user.get("cart", [])
    if not cart:
        return redirect(url_for("e-commerce.cart_page"))

    # Build order from cart
    order_items = []
    total = 0.0
    for item in cart:
        product = _get_product_by_id(item["product_id"])
        if product:
            subtotal = product["price"] * item["quantity"]
            order_items.append({
                "product_id": item["product_id"],
                "name": product["name"],
                "price": product["price"],
                "quantity": item["quantity"],
            })
            total += subtotal

    now = datetime.datetime.now()
    order_id = f"ORD-{now.strftime('%Y%m%d')}-{len(user.get('orders', [])) + 1:03d}"
    order = {
        "id": order_id,
        "date": now.strftime("%Y-%m-%d"),
        "items": order_items,
        "total": round(total, 2),
        "status": "processing",
    }

    user.setdefault("orders", []).append(order)
    user["cart"] = []
    _save_users(users)
    return redirect(url_for("e-commerce.orders_page"))


@blueprint.route("/review/submit", methods=["POST"])
def form_submit_review():
    if "user_id" not in session:
        return redirect(url_for("e-commerce.login_page"))

    product_id = request.form.get("product_id", type=int)
    rating = request.form.get("rating", type=int)
    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()

    if not product_id or not rating or not title:
        return redirect(url_for("e-commerce.index"))

    product = _get_product_by_id(product_id)
    if not product:
        abort(404)

    reviews = _load_reviews()
    new_id = max((r["id"] for r in reviews), default=0) + 1
    reviews.append({
        "id": new_id,
        "product_asin": product["asin"],
        "user_id": session["user_id"],
        "rating": min(max(rating, 1), 5),
        "title": title,
        "content": content,
        "date": datetime.datetime.now().strftime("%Y-%m-%d"),
    })
    _save_reviews(reviews)
    return redirect(url_for("e-commerce.product_detail", product_id=product_id))


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/products")
def api_products():
    products = _get_products()
    q = request.args.get("q", "").strip()
    cat = request.args.get("category", "").strip()
    brand = request.args.get("brand", "").strip()
    min_price = request.args.get("min_price", type=float)
    max_price = request.args.get("max_price", type=float)
    min_rating = request.args.get("min_rating", type=float)
    sort = request.args.get("sort", "").strip()
    limit = request.args.get("limit", type=int)

    results = list(products)
    if q:
        results = _search_products(results, q)
    results = _filter_products(results, category=cat, brand=brand,
                               min_price=min_price, max_price=max_price,
                               min_rating=min_rating)
    if sort:
        results = _sort_products(results, sort)
    if limit and limit > 0:
        results = results[:limit]
    return jsonify(results)


@blueprint.route("/api/products/<int:product_id>")
def api_product(product_id):
    product = _get_product_by_id(product_id)
    if product is None:
        abort(404)
    return jsonify(product)


@blueprint.route("/api/categories")
def api_categories():
    products = _get_products()
    counts = Counter(p["top_category"] for p in products)
    return jsonify([{"name": c, "count": n} for c, n in sorted(counts.items())])


@blueprint.route("/api/brands")
def api_brands():
    products = _get_products()
    counts = Counter(p["brand"] for p in products if p["brand"])
    return jsonify([{"name": b, "count": n} for b, n in sorted(counts.items())])


@blueprint.route("/api/cart/<int:user_id>", methods=["GET"])
def api_get_cart(user_id):
    user = _get_user(user_id)
    if not user:
        abort(404)
    cart = user.get("cart", [])
    cart_details = []
    total = 0.0
    for item in cart:
        product = _get_product_by_id(item["product_id"])
        if product:
            subtotal = product["price"] * item["quantity"]
            cart_details.append({
                "product_id": item["product_id"],
                "name": product["name"],
                "price": product["price"],
                "quantity": item["quantity"],
                "subtotal": round(subtotal, 2),
            })
            total += subtotal
    return jsonify({"items": cart_details, "total": round(total, 2)})


@blueprint.route("/api/cart/<int:user_id>", methods=["POST"])
def api_add_to_cart(user_id):
    data = request.get_json(silent=True) or {}
    product_id = data.get("product_id")
    quantity = data.get("quantity", 1)
    if product_id is None:
        return jsonify({"error": "product_id required"}), 400

    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)

    cart = user.setdefault("cart", [])
    existing = next((item for item in cart if item["product_id"] == product_id), None)
    if existing:
        existing["quantity"] += quantity
    else:
        cart.append({"product_id": product_id, "quantity": quantity})
    _save_users(users)
    return jsonify({"action": "added", "product_id": product_id,
                     "quantity": quantity, "cart_size": len(cart)})


@blueprint.route("/api/cart/<int:user_id>", methods=["DELETE"])
def api_remove_from_cart(user_id):
    data = request.get_json(silent=True) or {}
    product_id = data.get("product_id")
    if product_id is None:
        return jsonify({"error": "product_id required"}), 400

    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)

    cart = user.get("cart", [])
    user["cart"] = [item for item in cart if item["product_id"] != product_id]
    _save_users(users)
    return jsonify({"action": "removed", "product_id": product_id,
                     "cart_size": len(user["cart"])})


@blueprint.route("/api/wishlist/<int:user_id>", methods=["GET"])
def api_get_wishlist(user_id):
    user = _get_user(user_id)
    if not user:
        abort(404)
    wishlist = user.get("wishlist", [])
    products = _get_products()
    items = [p for p in products if p["id"] in wishlist]
    return jsonify({"items": items, "count": len(items)})


@blueprint.route("/api/wishlist/<int:user_id>", methods=["POST"])
def api_toggle_wishlist(user_id):
    data = request.get_json(silent=True) or {}
    product_id = data.get("product_id")
    if product_id is None:
        return jsonify({"error": "product_id required"}), 400

    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)

    wishlist = user.setdefault("wishlist", [])
    if product_id in wishlist:
        wishlist.remove(product_id)
        action = "removed"
    else:
        wishlist.append(product_id)
        action = "added"
    _save_users(users)
    return jsonify({"action": action, "product_id": product_id,
                     "wishlist_count": len(wishlist)})


@blueprint.route("/api/orders/<int:user_id>")
def api_get_orders(user_id):
    user = _get_user(user_id)
    if not user:
        abort(404)
    return jsonify(user.get("orders", []))


@blueprint.route("/api/orders", methods=["POST"])
def api_place_order():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    if user_id is None:
        return jsonify({"error": "user_id required"}), 400

    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)

    cart = user.get("cart", [])
    if not cart:
        return jsonify({"error": "cart is empty"}), 400

    order_items = []
    total = 0.0
    for item in cart:
        product = _get_product_by_id(item["product_id"])
        if product:
            subtotal = product["price"] * item["quantity"]
            order_items.append({
                "product_id": item["product_id"],
                "name": product["name"],
                "price": product["price"],
                "quantity": item["quantity"],
            })
            total += subtotal

    now = datetime.datetime.now()
    order_id = f"ORD-{now.strftime('%Y%m%d')}-{len(user.get('orders', [])) + 1:03d}"
    order = {
        "id": order_id,
        "date": now.strftime("%Y-%m-%d"),
        "items": order_items,
        "total": round(total, 2),
        "status": "processing",
    }

    user.setdefault("orders", []).append(order)
    user["cart"] = []
    _save_users(users)
    return jsonify({"action": "placed", "order": order})


@blueprint.route("/api/reviews/<asin>")
def api_get_reviews(asin):
    reviews = _load_reviews()
    product_reviews = [r for r in reviews if r["product_asin"] == asin]
    product_reviews.sort(key=lambda r: r["date"], reverse=True)
    return jsonify(product_reviews)


@blueprint.route("/api/reviews", methods=["POST"])
def api_add_review():
    data = request.get_json(silent=True) or {}
    asin = data.get("asin", "").strip()
    user_id = data.get("user_id")
    rating = data.get("rating")
    title = data.get("title", "").strip()
    content = data.get("content", "").strip()

    if not asin or not user_id or not rating or not title:
        return jsonify({"error": "asin, user_id, rating, title required"}), 400

    reviews = _load_reviews()
    new_id = max((r["id"] for r in reviews), default=0) + 1
    review = {
        "id": new_id,
        "product_asin": asin,
        "user_id": user_id,
        "rating": min(max(int(rating), 1), 5),
        "title": title,
        "content": content,
        "date": datetime.datetime.now().strftime("%Y-%m-%d"),
    }
    reviews.append(review)
    _save_reviews(reviews)
    return jsonify({"action": "created", "review": review})


@blueprint.route("/api/users/<int:user_id>")
def api_user(user_id):
    user = _get_user(user_id)
    if not user:
        abort(404)
    return jsonify({k: v for k, v in user.items() if k != "password"})


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
