"""Per-task reference solutions via Flask test client for e-commerce."""
import json


def solve_001(client, base="/sites/e-commerce"):
    r = client.get(f"{base}/api/products")
    products = json.loads(r.data)
    return str(len(products))


def solve_002(client, base="/sites/e-commerce"):
    r = client.get(f"{base}/api/products/1")
    product = json.loads(r.data)
    return f"{product['name']} ${product['price']}"


def solve_003(client, base="/sites/e-commerce"):
    r = client.get(f"{base}/api/categories")
    cats = json.loads(r.data)
    return str(len(cats))


def solve_004(client, base="/sites/e-commerce"):
    r = client.get(f"{base}/api/brands")
    brands = json.loads(r.data)
    return str(len(brands))


def solve_005(client, base="/sites/e-commerce"):
    r = client.get(f"{base}/api/cart/2")
    data = json.loads(r.data)
    return str(len(data.get("items", [])))


def solve_006(client, base="/sites/e-commerce"):
    r = client.get(f"{base}/api/orders/2")
    orders = json.loads(r.data)
    return str(len(orders))


def solve_007(client, base="/sites/e-commerce"):
    r = client.get(f"{base}/api/products?sort=price_desc&limit=1")
    products = json.loads(r.data)
    if products:
        top = products[0]
        return f"{top['name']} ${top['price']}"
    return "None"


def solve_008(client, base="/sites/e-commerce"):
    r = client.get(f"{base}/api/products?min_rating=4.5")
    products = json.loads(r.data)
    return str(len(products))


def solve_009(client, base="/sites/e-commerce"):
    r = client.get(f"{base}/api/products?q=toothpaste")
    products = json.loads(r.data)
    return str(len(products))


def solve_010(client, base="/sites/e-commerce"):
    r = client.get(f"{base}/api/cart/4")
    data = json.loads(r.data)
    return f"{data.get('total', 0):.2f}"


def solve_011(client, base="/sites/e-commerce"):
    r = client.get(f"{base}/api/wishlist/3")
    data = json.loads(r.data)
    return str(data.get("count", 0))


def solve_012(client, base="/sites/e-commerce"):
    r = client.get(f"{base}/api/products?min_price=100&max_price=500")
    products = json.loads(r.data)
    return str(len(products))


def solve_013(client, base="/sites/e-commerce"):
    r = client.get(f"{base}/api/products?sort=rating&limit=3")
    products = json.loads(r.data)
    names = [p["name"] for p in products]
    return ", ".join(names)


def solve_014(client, base="/sites/e-commerce"):
    r = client.get(f"{base}/api/reviews/B09GW3N8TF")
    reviews = json.loads(r.data)
    return str(len(reviews))


def solve_015(client, base="/sites/e-commerce"):
    client.post(f"{base}/api/login",
                json={"username": "shopper_alice", "password": "pass123"},
                content_type="application/json")
    r = client.post(f"{base}/api/cart/1",
                     json={"product_id": 2, "quantity": 1},
                     content_type="application/json")
    data = json.loads(r.data)
    return data.get("action", "")


def solve_016(client, base="/sites/e-commerce"):
    r = client.post(f"{base}/api/wishlist/1",
                     json={"product_id": 5},
                     content_type="application/json")
    data = json.loads(r.data)
    return data.get("action", "")


def solve_017(client, base="/sites/e-commerce"):
    client.post(f"{base}/api/cart/1",
                json={"product_id": 1, "quantity": 1},
                content_type="application/json")
    client.post(f"{base}/api/cart/1",
                json={"product_id": 2, "quantity": 1},
                content_type="application/json")
    r = client.post(f"{base}/api/orders",
                     json={"user_id": 1},
                     content_type="application/json")
    data = json.loads(r.data)
    order = data.get("order", {})
    return order.get("status", "")


def solve_018(client, base="/sites/e-commerce"):
    r = client.post(f"{base}/api/reviews",
                     json={
                         "asin": "B09GW3N8TF",
                         "user_id": 3,
                         "rating": 5,
                         "title": "Excellent product!",
                         "content": "Really love it"
                     },
                     content_type="application/json")
    data = json.loads(r.data)
    review = data.get("review", {})
    return str(review.get("id", ""))


def solve_019(client, base="/sites/e-commerce"):
    r = client.get(f"{base}/api/orders/5")
    orders = json.loads(r.data)
    total = sum(o["total"] for o in orders)
    return f"{total:.2f}"


def solve_020(client, base="/sites/e-commerce"):
    r = client.get(f"{base}/api/products?sort=price_asc&limit=1")
    products = json.loads(r.data)
    if not products:
        return "None"
    cheapest = products[0]
    pid = cheapest["id"]
    client.post(f"{base}/api/cart/3",
                json={"product_id": pid, "quantity": 2},
                content_type="application/json")
    r2 = client.get(f"{base}/api/cart/3")
    data = json.loads(r2.data)
    return f"{data.get('total', 0):.2f}"
