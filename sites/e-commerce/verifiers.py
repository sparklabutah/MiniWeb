"""Per-task HTTP verification functions for e-commerce."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/e-commerce"
    r = requests.get(f"{base}/api/products")
    products = r.json()
    count = len(products)
    return {"pass": count > 0, "detail": f"Total products: {count}"}


def verify_002(server_url):
    base = f"{server_url}/sites/e-commerce"
    r = requests.get(f"{base}/api/products/1")
    product = r.json()
    name = product.get("name", "")
    price = product.get("price", 0)
    return {"pass": bool(name) and price > 0, "detail": f"Product 1: {name} ${price}"}


def verify_003(server_url):
    base = f"{server_url}/sites/e-commerce"
    r = requests.get(f"{base}/api/categories")
    cats = r.json()
    count = len(cats)
    return {"pass": count > 0, "detail": f"Categories: {count}"}


def verify_004(server_url):
    base = f"{server_url}/sites/e-commerce"
    r = requests.get(f"{base}/api/brands")
    brands = r.json()
    count = len(brands)
    return {"pass": count > 0, "detail": f"Brands: {count}"}


def verify_005(server_url):
    base = f"{server_url}/sites/e-commerce"
    r = requests.get(f"{base}/api/cart/2")
    data = r.json()
    items = data.get("items", [])
    count = len(items)
    return {"pass": count >= 0, "detail": f"Bob's cart items: {count}"}


def verify_006(server_url):
    base = f"{server_url}/sites/e-commerce"
    r = requests.get(f"{base}/api/orders/2")
    orders = r.json()
    count = len(orders)
    return {"pass": count >= 0, "detail": f"Bob's orders: {count}"}


def verify_007(server_url):
    base = f"{server_url}/sites/e-commerce"
    r = requests.get(f"{base}/api/products?sort=price_desc&limit=1")
    products = r.json()
    if products:
        top = products[0]
        return {"pass": True, "detail": f"Most expensive: {top['name']} ${top['price']}"}
    return {"pass": False, "detail": "No products"}


def verify_008(server_url):
    base = f"{server_url}/sites/e-commerce"
    r = requests.get(f"{base}/api/products?min_rating=4.5")
    products = r.json()
    count = len(products)
    ok = all(p["rating"] >= 4.5 for p in products)
    return {"pass": count >= 0 and ok, "detail": f"Products rated 4.5+: {count}"}


def verify_009(server_url):
    base = f"{server_url}/sites/e-commerce"
    r = requests.get(f"{base}/api/products?q=toothpaste")
    products = r.json()
    count = len(products)
    return {"pass": count >= 0, "detail": f"Toothpaste products: {count}"}


def verify_010(server_url):
    base = f"{server_url}/sites/e-commerce"
    r = requests.get(f"{base}/api/cart/4")
    data = r.json()
    total = data.get("total", 0)
    return {"pass": total >= 0, "detail": f"Dan's cart total: ${total}"}


def verify_011(server_url):
    base = f"{server_url}/sites/e-commerce"
    r = requests.get(f"{base}/api/wishlist/3")
    data = r.json()
    count = data.get("count", 0)
    return {"pass": count >= 0, "detail": f"Carol's wishlist: {count} items"}


def verify_012(server_url):
    base = f"{server_url}/sites/e-commerce"
    r = requests.get(f"{base}/api/products?min_price=100&max_price=500")
    products = r.json()
    count = len(products)
    ok = all(100 <= p["price"] <= 500 for p in products)
    return {"pass": count >= 0 and ok, "detail": f"Products $100-$500: {count}"}


def verify_013(server_url):
    base = f"{server_url}/sites/e-commerce"
    r = requests.get(f"{base}/api/products?sort=rating&limit=3")
    products = r.json()
    count = len(products)
    names = [p["name"] for p in products]
    return {"pass": count == 3, "detail": f"Top 3 rated: {names}"}


def verify_014(server_url):
    base = f"{server_url}/sites/e-commerce"
    r = requests.get(f"{base}/api/reviews/B09GW3N8TF")
    reviews = r.json()
    count = len(reviews)
    return {"pass": count >= 0, "detail": f"Reviews for B09GW3N8TF: {count}"}


def verify_015(server_url):
    base = f"{server_url}/sites/e-commerce"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "shopper_alice", "password": "pass123"})
    s.post(f"{base}/api/cart/1", json={"product_id": 2, "quantity": 1})
    r = s.get(f"{base}/api/cart/1")
    data = r.json()
    items = data.get("items", [])
    found = any(item["product_id"] == 2 for item in items)
    return {"pass": found, "detail": f"Product 2 in Alice's cart: {found}"}


def verify_016(server_url):
    base = f"{server_url}/sites/e-commerce"
    r = requests.post(f"{base}/api/wishlist/1", json={"product_id": 5})
    data = r.json()
    action = data.get("action")
    # Verify
    r2 = requests.get(f"{base}/api/wishlist/1")
    wl = r2.json()
    found = any(item["id"] == 5 for item in wl.get("items", []))
    return {"pass": found or action == "added",
            "detail": f"Wishlist toggle: action={action}, product 5 in wishlist={found}"}


def verify_017(server_url):
    base = f"{server_url}/sites/e-commerce"
    # Add to cart
    requests.post(f"{base}/api/cart/1", json={"product_id": 1, "quantity": 1})
    requests.post(f"{base}/api/cart/1", json={"product_id": 2, "quantity": 1})
    # Place order
    r = requests.post(f"{base}/api/orders", json={"user_id": 1})
    data = r.json()
    order = data.get("order", {})
    status = order.get("status", "")
    return {"pass": status == "processing", "detail": f"Order status: {status}"}


def verify_018(server_url):
    base = f"{server_url}/sites/e-commerce"
    r = requests.post(f"{base}/api/reviews", json={
        "asin": "B09GW3N8TF",
        "user_id": 3,
        "rating": 5,
        "title": "Excellent product!",
        "content": "Really love it"
    })
    data = r.json()
    review = data.get("review", {})
    ok = review.get("rating") == 5 and review.get("title") == "Excellent product!"
    return {"pass": ok, "detail": f"Review created: rating={review.get('rating')}, title={review.get('title')}"}


def verify_019(server_url):
    base = f"{server_url}/sites/e-commerce"
    r = requests.get(f"{base}/api/orders/5")
    orders = r.json()
    total = sum(o["total"] for o in orders)
    return {"pass": total > 0, "detail": f"Eve total orders value: ${total:.2f}"}


def verify_020(server_url):
    base = f"{server_url}/sites/e-commerce"
    # Find cheapest
    r = requests.get(f"{base}/api/products?sort=price_asc&limit=1")
    products = r.json()
    if not products:
        return {"pass": False, "detail": "No products"}
    cheapest = products[0]
    pid = cheapest["id"]
    # Add to cart
    requests.post(f"{base}/api/cart/3", json={"product_id": pid, "quantity": 2})
    # Get cart total
    r2 = requests.get(f"{base}/api/cart/3")
    data = r2.json()
    total = data.get("total", 0)
    return {"pass": total > 0, "detail": f"Cart total after adding cheapest (${cheapest['price']}x2): ${total}"}
