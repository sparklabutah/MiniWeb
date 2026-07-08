"""E-commerce — Online marketplace (Amazon/eBay style).

Data is stored in SQLite: products in the e_commerce_products table, users and
reviews in per-site typed tables.  Queried through app.db.
"""
import json
import pathlib
import re
import datetime
from collections import Counter

from flask import Blueprint, Response, abort, jsonify, redirect, render_template, request, session, url_for
from app import db
from app.db import _deserialize_row
from app.events import emit

SITE = "e-commerce"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "e-commerce",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

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


# ---------------------------------------------------------------------------
# DB-backed data access  (e_commerce_products table)
# ---------------------------------------------------------------------------


def _db_conn():
    return db.get_conn()


def _db_load_all_products():
    """Load all products from DB, interpret, sort, and assign IDs."""
    conn = _db_conn()
    rows = conn.execute(
        "SELECT * FROM e_commerce_products ORDER BY asin"
    ).fetchall()
    products = []
    for i, row in enumerate(rows):
        raw = _deserialize_row(row)
        # Parse JSON list columns that are stored as TEXT
        for col in ("images", "small_description", "customization_options",
                     "product_information"):
            val = raw.get(col)
            if isinstance(val, str):
                try:
                    raw[col] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    pass
        products.append(_interpret_product(raw, i + 1))
    products.sort(key=lambda p: p["name"].lower())
    for i, p in enumerate(products, 1):
        p["id"] = i
    return products


# DB products cache — loaded once since it's only ~500 records
_db_products = None
_db_top_categories = None
_db_all_brands = None


def _db_ensure_loaded():
    global _db_products, _db_top_categories, _db_all_brands
    if _db_products is None:
        _db_products = _db_load_all_products()
        cat_counts = Counter(p["top_category"] for p in _db_products)
        _db_top_categories = sorted(cat_counts.keys())
        brand_counts = Counter(p["brand"] for p in _db_products if p["brand"])
        _db_all_brands = sorted(brand_counts.keys())


def _db_get_products():
    _db_ensure_loaded()
    return _db_products


def _db_get_top_categories():
    _db_ensure_loaded()
    return _db_top_categories


def _db_get_all_brands():
    _db_ensure_loaded()
    return _db_all_brands


def _db_get_product_by_id(product_id):
    products = _db_get_products()
    return next((p for p in products if p["id"] == product_id), None)


def _db_get_product_by_asin(asin):
    products = _db_get_products()
    return next((p for p in products if p["asin"] == asin), None)


# ---------------------------------------------------------------------------
# Unified accessors — always use DB
# ---------------------------------------------------------------------------

def _get_products():
    return _db_get_products()


def _get_top_categories():
    return _db_get_top_categories()


def _get_all_brands():
    return _db_get_all_brands()


def _get_product_by_id(product_id):
    return _db_get_product_by_id(product_id)


def _get_product_by_asin(asin):
    return _db_get_product_by_asin(asin)


# ---------------------------------------------------------------------------
# Users (mutable state -- stored in per-site SQLite table)
# ---------------------------------------------------------------------------

def _load_users():
    return db.query(SITE, "users")


def _save_users(users):
    db.save_collection(SITE, "users", users)


def _get_user(user_id):
    return db.get_item(SITE, "users", user_id)


# ---------------------------------------------------------------------------
# Reviews (mutable state -- stored in per-site SQLite table)
# ---------------------------------------------------------------------------

def _load_reviews():
    return db.query(SITE, "reviews")


def _save_reviews(reviews):
    db.save_collection(SITE, "reviews", reviews)


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
    product_reviews = db.query(SITE, "reviews", where={"product_asin": product["asin"]}, sort="-date")

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

    promo_code = user.get("promo_code", "")
    discount = round(total * PROMO_CODES.get(promo_code, 0), 2)
    return render_template("e-commerce/cart.html", cart_items=cart_items,
                           total=round(total, 2), user=user,
                           promo_code=promo_code, discount=discount,
                           promo_error=request.args.get("promo_error", ""))


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
    emit("signup", user_id=user["id"], site_name="e-commerce", username=request.form.get("username", ""), password=request.form.get("password", ""), email="")
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


PROMO_CODES = {"SAVE10": 0.10, "WELCOME5": 0.05, "SHOP20": 0.20}


@blueprint.route("/cart/promo", methods=["POST"])
def form_apply_promo():
    if "user_id" not in session:
        return redirect(url_for("e-commerce.login_page"))
    code = request.form.get("promo_code", "").strip().upper()
    users = _load_users()
    user = next((u for u in users if u["id"] == session["user_id"]), None)
    if not user:
        return redirect(url_for("e-commerce.login_page"))
    if code in PROMO_CODES:
        user["promo_code"] = code
        _save_users(users)
        return redirect(url_for("e-commerce.cart_page"))
    return redirect(url_for("e-commerce.cart_page", promo_error="1"))


@blueprint.route("/orders/cancel", methods=["POST"])
def form_cancel_order():
    if "user_id" not in session:
        return redirect(url_for("e-commerce.login_page"))
    order_id = request.form.get("order_id", "")
    users = _load_users()
    user = next((u for u in users if u["id"] == session["user_id"]), None)
    if not user:
        return redirect(url_for("e-commerce.login_page"))
    for order in user.get("orders", []):
        if order.get("id") == order_id and order.get("status") not in ("shipped", "delivered", "cancelled"):
            order["status"] = "cancelled"
    _save_users(users)
    return redirect(url_for("e-commerce.orders_page"))


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


SHIPPING_METHODS = [
    {"id": "standard", "label": "Standard Shipping", "eta": "5-7 business days", "cost": 0.0},
    {"id": "express", "label": "Express Shipping", "eta": "2 business days", "cost": 9.99},
    {"id": "overnight", "label": "Overnight Shipping", "eta": "next business day", "cost": 24.99},
]


def _cart_items_and_total(user):
    """Resolve a user's cart into display items + subtotal."""
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
    return cart_items, round(total, 2)


@blueprint.route("/checkout", methods=["GET"])
def checkout_page():
    """Checkout form: shipping address, shipping method, payment method."""
    if "user_id" not in session:
        return redirect(url_for("e-commerce.login_page"))
    user = _get_user(session["user_id"])
    if not user:
        return redirect(url_for("e-commerce.login_page"))
    cart_items, total = _cart_items_and_total(user)
    if not cart_items:
        return redirect(url_for("e-commerce.cart_page"))
    return render_template("e-commerce/checkout.html", user=user,
                           cart_items=cart_items, total=total,
                           shipping_methods=SHIPPING_METHODS, form={}, error=None)


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

    # Shipping address + method from the checkout form
    form = {k: request.form.get(k, "").strip()
            for k in ("full_name", "street", "city", "state", "zip_code",
                      "shipping_method", "account_type")}
    missing = [f for f in ("full_name", "street", "city", "zip_code") if not form[f]]
    method = next((m for m in SHIPPING_METHODS if m["id"] == form["shipping_method"]),
                  SHIPPING_METHODS[0])
    if missing:
        cart_items, total = _cart_items_and_total(user)
        return render_template("e-commerce/checkout.html", user=user,
                               cart_items=cart_items, total=total,
                               shipping_methods=SHIPPING_METHODS, form=form,
                               error="Please fill in: " + ", ".join(m.replace("_", " ") for m in missing)), 400

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
    total += method["cost"]

    now = datetime.datetime.now()
    order_id = f"ORD-{now.strftime('%Y%m%d')}-{len(user.get('orders', [])) + 1:03d}"
    order = {
        "id": order_id,
        "date": now.strftime("%Y-%m-%d"),
        "items": order_items,
        "total": round(total, 2),
        "status": "processing",
        "shipping_address": {
            "full_name": form["full_name"],
            "street": form["street"],
            "city": form["city"],
            "state": form["state"],
            "zip_code": form["zip_code"],
        },
        "shipping_method": method["id"],
        "shipping_cost": method["cost"],
    }

    account_type = form["account_type"] or "checking"

    user.setdefault("orders", []).append(order)
    user["cart"] = []
    _save_users(users)

    # 2FA: send verification code before completing the purchase
    from app.events import request_2fa
    item_names = ", ".join(i["name"] for i in order_items[:3])
    verify_url = request_2fa("purchase",
                             return_url=url_for("e-commerce.orders_page"),
                             user_id=session.get("user_id", 1),
                             merchant="MiniWeb Store",
                             amount=order["total"],
                             item_description=item_names,
                             order_id=order_id,
                             account_type=account_type)
    return redirect(verify_url)


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

    account_type = data.get("account_type", "checking")

    user.setdefault("orders", []).append(order)
    user["cart"] = []
    _save_users(users)

    # Bridge: notify banking/email of purchase
    try:
        from app.bridges import on_purchase
        item_names = ", ".join(i["name"] for i in order_items[:3])
        on_purchase(user_id=user_id, merchant="MiniWeb Store",
                    amount=order["total"], item_description=item_names,
                    order_id=order_id, account_type=account_type)
    except Exception:
        pass  # bridge failure should never block the main flow

    return jsonify({"action": "placed", "order": order})


@blueprint.route("/api/reviews/<asin>")
def api_get_reviews(asin):
    product_reviews = db.query(SITE, "reviews", where={"product_asin": asin}, sort="-date")
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
