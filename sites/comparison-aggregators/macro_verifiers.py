"""Per-macro verification functions for comparison-aggregators.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/comparison-aggregators"


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/phones/1")
    data = r.json()
    return {"pass": "name" in data and "brand" in data,
            "detail": f"Phone data keys: {list(data.keys())[:6]}"}


def verify_macro_filter_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/phones?brand=Samsung")
    phones = r.json()
    ok = all(p["brand"] == "Samsung" for p in phones)
    return {"pass": ok and len(phones) > 0,
            "detail": f"Samsung filter: {len(phones)} phones, all_samsung={ok}"}


def verify_macro_sort_by_ranking(server_url):
    r = requests.get(f"{_base(server_url)}/api/phones?sort=price_desc")
    phones = r.json()
    priced = [p for p in phones if p["price"] is not None]
    if len(priced) < 2:
        return {"pass": True, "detail": "Too few priced phones to verify sort"}
    is_sorted = all(priced[i]["price"] >= priced[i+1]["price"] for i in range(len(priced)-1))
    return {"pass": is_sorted, "detail": f"Sort price desc: sorted={is_sorted}"}


def verify_macro_authenticate_by_form(server_url):
    s = requests.Session()
    r = s.post(f"{_base(server_url)}/api/login",
               json={"username": "techfan_alice", "password": "pass123"})
    data = r.json()
    ok = data.get("user_id") == 1
    return {"pass": ok, "detail": f"authenticate: user_id={data.get('user_id')}"}


def verify_macro_toggle_by_api(server_url):
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "reviewer_dan", "password": "pass321"})
    r = s.post(f"{base}/api/users/4/favorite", json={"phone_id": 1})
    data = r.json()
    action = data.get("action")
    # Toggle back
    s.post(f"{base}/api/users/4/favorite", json={"phone_id": 1})
    return {"pass": action in ("added", "removed"),
            "detail": f"toggle_by_api: action={action}"}
