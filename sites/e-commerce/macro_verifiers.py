"""Per-macro verification functions for e-commerce.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/e-commerce"


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/products/1")
    data = r.json()
    return {"pass": "name" in data and "price" in data and "brand" in data,
            "detail": f"Product data keys: {list(data.keys())[:6]}"}


def verify_macro_filter_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/products?min_rating=4.0")
    products = r.json()
    ok = all(p["rating"] >= 4.0 for p in products)
    return {"pass": ok and len(products) > 0,
            "detail": f"Rating>=4.0 filter: {len(products)} products, all_valid={ok}"}


def verify_macro_sort_by_ranking(server_url):
    r = requests.get(f"{_base(server_url)}/api/products?sort=price_desc")
    products = r.json()
    if len(products) < 2:
        return {"pass": True, "detail": "Too few products to verify sort"}
    is_sorted = all(products[i]["price"] >= products[i+1]["price"]
                    for i in range(min(len(products)-1, 50)))
    return {"pass": is_sorted, "detail": f"Sort price desc: sorted={is_sorted}"}


def verify_macro_authenticate_by_form(server_url):
    s = requests.Session()
    r = s.post(f"{_base(server_url)}/api/login",
               json={"username": "shopper_alice", "password": "pass123"})
    data = r.json()
    ok = data.get("user_id") == 1
    return {"pass": ok, "detail": f"authenticate: user_id={data.get('user_id')}"}


def verify_macro_submit_form(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/cart/4", json={"product_id": 2, "quantity": 1})
    data = r.json()
    ok = data.get("action") == "added"
    return {"pass": ok, "detail": f"submit_form: add to cart action={data.get('action')}"}


def verify_macro_toggle_by_api(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/wishlist/4", json={"product_id": 1})
    data = r.json()
    action = data.get("action")
    # Toggle back
    requests.post(f"{base}/api/wishlist/4", json={"product_id": 1})
    return {"pass": action in ("added", "removed"),
            "detail": f"toggle_by_api: action={action}"}


def verify_macro_compute_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/cart/4")
    data = r.json()
    return {"pass": "total" in data and "items" in data,
            "detail": f"Cart: total=${data.get('total')}, items={len(data.get('items', []))}"}
