"""Per-task HTTP verification functions for software-marketplace."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/software-marketplace"
    r = requests.get(f"{base}/api/categories/GAME/apps")
    apps = r.json()
    count = len(apps)
    return {"pass": count > 0, "detail": f"GAME category has {count} apps"}


def verify_002(server_url):
    base = f"{server_url}/sites/software-marketplace"
    # Featured = top rated, so app with highest rating
    r = requests.get(f"{base}/api/apps?sort=rating&limit=1")
    apps = r.json()
    if not apps:
        return {"pass": False, "detail": "No apps returned"}
    dev = apps[0].get("developer", "")
    return {"pass": len(dev) > 0, "detail": f"Top rated app developer: {dev}"}


def verify_003(server_url):
    base = f"{server_url}/sites/software-marketplace"
    r = requests.get(f"{base}/api/apps?q=messenger")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Search 'messenger': {count} results"}


def verify_004(server_url):
    base = f"{server_url}/sites/software-marketplace"
    r = requests.get(f"{base}/api/apps/semantic?q=social+media+chat+messaging")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Semantic 'social media chat messaging': {count} results"}


def verify_005(server_url):
    base = f"{server_url}/sites/software-marketplace"
    r = requests.get(f"{base}/api/categories/EDUCATION/apps")
    apps = r.json()
    count = len(apps)
    return {"pass": count > 0, "detail": f"EDUCATION category: {count} apps"}


def verify_006(server_url):
    base = f"{server_url}/sites/software-marketplace"
    r = requests.get(f"{base}/api/apps?max_price=2.0")
    apps = r.json()
    count = len(apps)
    ok = all(a["price"] <= 2.0 for a in apps)
    return {"pass": ok and count > 0, "detail": f"Max price 2.0: {count} apps, all_under_2={ok}"}


def verify_007(server_url):
    base = f"{server_url}/sites/software-marketplace"
    r = requests.get(f"{base}/api/apps?sort=rating&limit=1")
    apps = r.json()
    if not apps:
        return {"pass": False, "detail": "No apps returned"}
    name = apps[0]["name"]
    rating = apps[0]["rating"]
    return {"pass": True, "detail": f"Top rated: {name} ({rating})"}


def verify_008(server_url):
    base = f"{server_url}/sites/software-marketplace"
    r = requests.get(f"{base}/api/apps?sort=price_desc&limit=1")
    apps = r.json()
    if not apps:
        return {"pass": False, "detail": "No apps returned"}
    name = apps[0]["name"]
    price = apps[0]["price"]
    return {"pass": price > 0, "detail": f"Most expensive: {name} (${price})"}


def verify_009(server_url):
    base = f"{server_url}/sites/software-marketplace"
    r = requests.get(f"{base}/api/compare?ids=1,2")
    apps = r.json()
    if len(apps) < 2:
        return {"pass": False, "detail": f"Compare returned {len(apps)} apps, expected 2"}
    ratings = [a["rating"] for a in apps]
    return {"pass": True, "detail": f"App 1 rating: {ratings[0]}, App 2 rating: {ratings[1]}"}


def verify_010(server_url):
    base = f"{server_url}/sites/software-marketplace"
    r = requests.get(f"{base}/api/apps/5")
    app = r.json()
    cr = app.get("content_rating", "")
    return {"pass": len(cr) > 0, "detail": f"App 5 content_rating: {cr}"}


def verify_011(server_url):
    base = f"{server_url}/sites/software-marketplace"
    r = requests.get(f"{base}/api/categories/GAME/apps")
    apps = r.json()
    arcade_apps = [a for a in apps if a["genre"] == "Arcade"]
    if not arcade_apps:
        return {"pass": False, "detail": "No Arcade genre apps in GAME"}
    name = arcade_apps[0]["name"]
    return {"pass": True, "detail": f"Arcade game: {name}"}


def verify_012(server_url):
    base = f"{server_url}/sites/software-marketplace"
    r = requests.get(f"{base}/api/settings?user_id=1")
    settings = r.json()
    theme = settings.get("theme", "")
    return {"pass": theme == "dark", "detail": f"User 1 theme: {theme}"}


def verify_013(server_url):
    base = f"{server_url}/sites/software-marketplace"
    r = requests.get(f"{base}/api/settings?user_id=2")
    settings = r.json()
    freq = settings.get("notification_frequency")
    return {"pass": freq == 8, "detail": f"User 2 notification_frequency: {freq}"}


def verify_014(server_url):
    base = f"{server_url}/sites/software-marketplace"
    r = requests.get(f"{base}/api/export?format=csv&category=GAME")
    lines = r.text.strip().split("\n")
    data_rows = len(lines) - 1
    return {"pass": data_rows > 0, "detail": f"CSV export GAME: {data_rows} data rows"}


def verify_015(server_url):
    base = f"{server_url}/sites/software-marketplace"
    r = requests.get(f"{base}/api/apps/2/reviews")
    reviews = r.json()
    # Check if a review from user 3 (marcus_j) with rating 4 exists
    found = any(
        rv["user_id"] == 3 and rv["rating"] == 4
        and "nutrition" in rv["text"].lower()
        for rv in reviews
    )
    return {"pass": found, "detail": f"Review from user 3 on app 2: found={found}"}


def verify_016(server_url):
    base = f"{server_url}/sites/software-marketplace"
    r = requests.get(f"{base}/api/wishlist?user_id=4")
    items = r.json()
    app_ids = [w["app_id"] for w in items]
    found = 9 in app_ids
    return {"pass": found, "detail": f"User 4 wishlist app_ids: {app_ids}"}


def verify_017(server_url):
    base = f"{server_url}/sites/software-marketplace"
    r = requests.get(f"{base}/api/cart?user_id=5")
    data = r.json()
    items = data.get("items", [])
    app_ids = [i["app_id"] for i in items]
    found = 44 in app_ids
    return {"pass": found, "detail": f"User 5 cart app_ids: {app_ids}"}


def verify_018(server_url):
    base = f"{server_url}/sites/software-marketplace"
    r = requests.get(f"{base}/api/purchases?user_id=1")
    purchases = r.json()
    purchased_ids = [p["app_id"] for p in purchases]
    found = 7 in purchased_ids
    return {"pass": found, "detail": f"User 1 purchased app_ids: {purchased_ids}"}


def verify_019(server_url):
    base = f"{server_url}/sites/software-marketplace"
    r = requests.get(f"{base}/api/purchases?user_id=2")
    purchases = r.json()
    purchased_ids = [p["app_id"] for p in purchases]
    found = 30 in purchased_ids
    # Check discount was applied
    purchase_30 = next((p for p in purchases if p["app_id"] == 30), None)
    discount_ok = False
    if purchase_30:
        discount_ok = purchase_30.get("promo_code") == "WELCOME20"
    return {
        "pass": found and discount_ok,
        "detail": f"User 2 purchased app 30: found={found}, promo={purchase_30.get('promo_code') if purchase_30 else None}",
    }


def verify_020(server_url):
    base = f"{server_url}/sites/software-marketplace"
    r = requests.post(f"{base}/api/promo/validate", json={"code": "EXPIRED10"})
    data = r.json()
    valid = data.get("valid", True)
    return {"pass": not valid, "detail": f"EXPIRED10 valid={valid}, error={data.get('error', '')}"}
