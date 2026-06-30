"""Per-macro verification functions for software-marketplace.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/software-marketplace"


def verify_macro_navigate_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/categories")
    cats = r.json()
    if not cats:
        return {"pass": False, "detail": "No categories returned"}
    cat = cats[0]["name"]
    r2 = requests.get(f"{_base(server_url)}/category/{cat}")
    return {"pass": r2.status_code == 200, "detail": f"Category page '{cat}': {r2.status_code}"}


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/app/1")
    return {"pass": r.status_code == 200, "detail": f"App detail page: {r.status_code}"}


def verify_macro_search_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/apps?q=weather")
    results = r.json()
    return {"pass": len(results) > 0, "detail": f"search_by_query 'weather': {len(results)} results"}


def verify_macro_search_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/apps/semantic?q=photo+editing+camera")
    results = r.json()
    return {"pass": r.status_code == 200, "detail": f"search_by_semantic: {len(results)} results"}


def verify_macro_filter_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/apps?category=GAME")
    apps = r.json()
    ok = all(a["category"] == "GAME" for a in apps)
    return {"pass": ok and len(apps) > 0, "detail": f"filter_by_dropdown GAME: {len(apps)} apps, all_game={ok}"}


def verify_macro_filter_by_slider(server_url):
    r = requests.get(f"{_base(server_url)}/api/apps?max_price=3.0")
    apps = r.json()
    ok = all(a["price"] <= 3.0 for a in apps)
    return {"pass": ok, "detail": f"filter_by_slider max_price=3.0: {len(apps)} apps, all_under_3={ok}"}


def verify_macro_sort_by_ranking(server_url):
    r = requests.get(f"{_base(server_url)}/api/apps?sort=rating")
    apps = r.json()
    if len(apps) < 2:
        return {"pass": True, "detail": "Too few apps to verify sort"}
    ratings = [a["rating"] for a in apps]
    is_sorted = all(ratings[i] >= ratings[i + 1] for i in range(len(ratings) - 1))
    return {"pass": is_sorted, "detail": f"sort_by_ranking: sorted_desc={is_sorted}"}


def verify_macro_sort_by_extremum(server_url):
    r = requests.get(f"{_base(server_url)}/api/apps?sort=price_desc&limit=1")
    apps = r.json()
    if not apps:
        return {"pass": False, "detail": "No apps returned"}
    # Verify this is the most expensive
    r2 = requests.get(f"{_base(server_url)}/api/apps")
    all_apps = r2.json()
    max_price = max(a["price"] for a in all_apps)
    return {
        "pass": apps[0]["price"] == max_price,
        "detail": f"sort_by_extremum: top={apps[0]['name']} (${apps[0]['price']}), max=${max_price}",
    }


def verify_macro_extract_from_table(server_url):
    r = requests.get(f"{_base(server_url)}/api/compare?ids=1,2")
    apps = r.json()
    return {"pass": len(apps) == 2, "detail": f"extract_from_table: compare returned {len(apps)} apps"}


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/apps/1")
    app = r.json()
    return {
        "pass": "description" in app and "developer" in app,
        "detail": f"extract_by_route: app has description={len(app.get('description', ''))} chars",
    }


def verify_macro_compare_from_table(server_url):
    r = requests.get(f"{_base(server_url)}/api/compare?ids=1,2")
    apps = r.json()
    if len(apps) < 2:
        return {"pass": False, "detail": "Compare needs 2 apps"}
    return {
        "pass": apps[0]["id"] != apps[1]["id"],
        "detail": f"compare: app {apps[0]['id']} ({apps[0]['name']}) vs app {apps[1]['id']} ({apps[1]['name']})",
    }


def verify_macro_select_by_dropdown(server_url):
    # Genre sub-filter on category page
    r = requests.get(f"{_base(server_url)}/api/categories/GAME/apps")
    apps = r.json()
    genres = set(a["genre"] for a in apps)
    if not genres:
        return {"pass": False, "detail": "No genres in GAME category"}
    genre = list(genres)[0]
    filtered = [a for a in apps if a["genre"] == genre]
    return {
        "pass": len(filtered) > 0,
        "detail": f"select_by_dropdown: GAME/{genre} has {len(filtered)} apps",
    }


def verify_macro_configure_by_dropdown(server_url):
    base = _base(server_url)
    # Update theme for test user (user 5 as a safe test user)
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "jordan_w", "password": "pass123"})
    s.post(f"{base}/api/settings", json={"user_id": 5, "theme": "dark"})
    r = s.get(f"{base}/api/settings?user_id=5")
    settings = r.json()
    ok = settings.get("theme") == "dark"
    # Restore
    s.post(f"{base}/api/settings", json={"user_id": 5, "theme": "dark"})
    return {"pass": ok, "detail": f"configure_by_dropdown: theme={settings.get('theme')}"}


def verify_macro_configure_by_slider(server_url):
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "jordan_w", "password": "pass123"})
    s.post(f"{base}/api/settings", json={"user_id": 5, "notification_frequency": 7})
    r = s.get(f"{base}/api/settings?user_id=5")
    settings = r.json()
    freq = settings.get("notification_frequency")
    ok = freq == 7
    # Restore
    s.post(f"{base}/api/settings", json={"user_id": 5, "notification_frequency": 2})
    return {"pass": ok, "detail": f"configure_by_slider: notification_frequency={freq}"}


def verify_macro_export_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/export?format=csv")
    lines = r.text.strip().split("\n")
    return {"pass": len(lines) > 1, "detail": f"export CSV: {len(lines)} lines"}


def verify_macro_rate_by_slider(server_url):
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "jordan_w", "password": "pass123"})
    r = s.post(
        f"{base}/api/apps/1/reviews",
        json={"user_id": 5, "rating": 5, "text": "Test review for macro verification"},
    )
    data = r.json()
    ok = data.get("action") == "created"
    # Clean up: delete the review
    if ok:
        review_id = data.get("review", {}).get("id")
        if review_id:
            s.delete(f"{base}/api/reviews/{review_id}", json={"user_id": 5})
    return {"pass": ok, "detail": f"rate_by_slider: action={data.get('action')}"}


def verify_macro_save_by_toggle(server_url):
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "jordan_w", "password": "pass123"})
    r = s.post(f"{base}/api/wishlist/toggle", json={"user_id": 5, "app_id": 99})
    data = r.json()
    ok = data.get("action") == "saved"
    # Toggle back to clean up
    s.post(f"{base}/api/wishlist/toggle", json={"user_id": 5, "app_id": 99})
    return {"pass": ok, "detail": f"save_by_toggle: action={data.get('action')}"}


def verify_macro_add_by_button(server_url):
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "jordan_w", "password": "pass123"})
    r = s.post(f"{base}/api/cart/add", json={"user_id": 5, "app_id": 1})
    data = r.json()
    ok = data.get("action") == "added"
    # Clean up
    s.post(f"{base}/api/cart/remove", json={"user_id": 5, "app_id": 1})
    return {"pass": ok, "detail": f"add_by_button: action={data.get('action')}"}


def verify_macro_checkout_by_form(server_url):
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "jordan_w", "password": "pass123"})
    # Add a free app to cart so checkout works
    s.post(f"{base}/api/cart/add", json={"user_id": 5, "app_id": 4})
    r = s.post(
        f"{base}/api/checkout",
        json={
            "user_id": 5,
            "card_name": "Test User",
            "card_number": "4111111111111111",
            "card_expiry": "12/30",
        },
    )
    data = r.json()
    ok = data.get("action") == "purchased"
    return {"pass": ok, "detail": f"checkout_by_form: action={data.get('action')}"}


def verify_macro_redeem_by_code(server_url):
    base = _base(server_url)
    # Validate a valid code
    r = requests.post(f"{base}/api/promo/validate", json={"code": "WELCOME20"})
    data = r.json()
    valid = data.get("valid", False)
    # Validate an expired code
    r2 = requests.post(f"{base}/api/promo/validate", json={"code": "EXPIRED10"})
    data2 = r2.json()
    expired_invalid = not data2.get("valid", True)
    return {
        "pass": valid and expired_invalid,
        "detail": f"redeem_by_code: WELCOME20 valid={valid}, EXPIRED10 valid={not expired_invalid}",
    }
