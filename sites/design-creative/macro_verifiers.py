"""Per-macro verification functions for design-creative.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/design-creative"


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/templates/1")
    data = r.json()
    return {"pass": "title" in data and "category" in data and "dimensions" in data,
            "detail": f"Template data keys: {list(data.keys())[:6]}"}


def verify_macro_filter_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/templates?category=logo")
    templates = r.json()
    ok = all(t["category"] == "logo" for t in templates)
    return {"pass": ok and len(templates) > 0,
            "detail": f"Logo filter: {len(templates)} templates, all_logo={ok}"}


def verify_macro_sort_by_ranking(server_url):
    r = requests.get(f"{_base(server_url)}/api/templates?sort=popular")
    templates = r.json()
    if len(templates) < 2:
        return {"pass": True, "detail": "Too few templates to verify sort"}
    is_sorted = all(templates[i]["use_count"] >= templates[i+1]["use_count"]
                    for i in range(len(templates)-1))
    return {"pass": is_sorted, "detail": f"Sort popular: sorted={is_sorted}"}


def verify_macro_authenticate_by_form(server_url):
    s = requests.Session()
    r = s.post(f"{_base(server_url)}/api/login",
               json={"username": "alice_design", "password": "design123"})
    data = r.json()
    ok = data.get("user_id") == 1
    return {"pass": ok, "detail": f"authenticate: user_id={data.get('user_id')}"}


def verify_macro_submit_form(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/projects", json={
        "owner_id": 4,
        "title": "Macro Test Project",
        "dimensions": "500x500"
    })
    data = r.json()
    ok = data.get("id") is not None and data.get("title") == "Macro Test Project"
    return {"pass": ok, "detail": f"submit_form: created project id={data.get('id')}"}


def verify_macro_toggle_by_api(server_url):
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "dan_graphics", "password": "graphic321"})
    r = s.post(f"{base}/api/users/4/favorites", json={"template_id": 1})
    data = r.json()
    action = data.get("action")
    # Toggle back
    s.post(f"{base}/api/users/4/favorites", json={"template_id": 1})
    return {"pass": action in ("favorited", "unfavorited"),
            "detail": f"toggle_by_api: action={action}"}
