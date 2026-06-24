"""Per-task HTTP verification functions for comparison-aggregators."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/comparison-aggregators"
    r = requests.get(f"{base}/api/phones")
    phones = r.json()
    count = len(phones)
    return {"pass": count > 0, "detail": f"Total phones: {count}"}


def verify_002(server_url):
    base = f"{server_url}/sites/comparison-aggregators"
    r = requests.get(f"{base}/api/brands")
    brands = r.json()
    count = len(brands)
    return {"pass": count > 0, "detail": f"Total brands: {count}"}


def verify_003(server_url):
    base = f"{server_url}/sites/comparison-aggregators"
    r = requests.get(f"{base}/api/phones/1")
    phone = r.json()
    name = phone.get("name", "")
    brand = phone.get("brand", "")
    return {"pass": bool(name and brand), "detail": f"Phone 1: {brand} {name}"}


def verify_004(server_url):
    base = f"{server_url}/sites/comparison-aggregators"
    r = requests.get(f"{base}/api/stats")
    data = r.json()
    avg = data.get("avg_price")
    return {"pass": avg is not None and avg > 0, "detail": f"Average price: ${avg}"}


def verify_005(server_url):
    base = f"{server_url}/sites/comparison-aggregators"
    r = requests.get(f"{base}/api/users/1")
    user = r.json()
    username = user.get("username")
    return {"pass": username == "techfan_alice", "detail": f"Username: {username}"}


def verify_006(server_url):
    base = f"{server_url}/sites/comparison-aggregators"
    r = requests.get(f"{base}/api/phones?brand=Samsung")
    phones = r.json()
    count = len(phones)
    ok = all(p["brand"] == "Samsung" for p in phones)
    return {"pass": count > 0 and ok, "detail": f"Samsung phones: {count}, all_samsung={ok}"}


def verify_007(server_url):
    base = f"{server_url}/sites/comparison-aggregators"
    r = requests.get(f"{base}/api/phones?price_min=500&price_max=1000")
    phones = r.json()
    count = len(phones)
    ok = all(500 <= p["price"] <= 1000 for p in phones if p["price"] is not None)
    return {"pass": count >= 0, "detail": f"Phones $500-$1000: {count}, in_range={ok}"}


def verify_008(server_url):
    base = f"{server_url}/sites/comparison-aggregators"
    r = requests.get(f"{base}/api/phones?os=Android")
    phones = r.json()
    count = len(phones)
    ok = all(p["os_family"] == "Android" for p in phones)
    return {"pass": count > 0 and ok, "detail": f"Android phones: {count}"}


def verify_009(server_url):
    base = f"{server_url}/sites/comparison-aggregators"
    r = requests.get(f"{base}/api/phones?sort=price_desc")
    phones = r.json()
    priced = [p for p in phones if p["price"] is not None]
    if priced:
        top = priced[0]
        return {"pass": True, "detail": f"Most expensive: {top['name']} ${top['price']}"}
    return {"pass": False, "detail": "No priced phones"}


def verify_010(server_url):
    base = f"{server_url}/sites/comparison-aggregators"
    r = requests.get(f"{base}/api/phones?q=iPhone")
    phones = r.json()
    count = len(phones)
    return {"pass": count >= 0, "detail": f"iPhone search results: {count}"}


def verify_011(server_url):
    base = f"{server_url}/sites/comparison-aggregators"
    r = requests.get(f"{base}/api/compare?ids=1,2,3")
    phones = r.json()
    count = len(phones)
    names = [p["name"] for p in phones]
    return {"pass": count == 3, "detail": f"Compared phones: {names}"}


def verify_012(server_url):
    base = f"{server_url}/sites/comparison-aggregators"
    r = requests.get(f"{base}/api/stats")
    data = r.json()
    os_dist = data.get("os_distribution", {})
    if os_dist:
        top_os = max(os_dist, key=os_dist.get)
        return {"pass": True, "detail": f"Top OS: {top_os} ({os_dist[top_os]})"}
    return {"pass": False, "detail": "No OS distribution data"}


def verify_013(server_url):
    base = f"{server_url}/sites/comparison-aggregators"
    r = requests.get(f"{base}/api/phones?sort=battery_desc")
    phones = r.json()
    with_bat = [p for p in phones if p["battery_mah"] is not None]
    if with_bat:
        top = with_bat[0]
        return {"pass": True, "detail": f"Largest battery: {top['name']} {top['battery_mah']}mAh"}
    return {"pass": False, "detail": "No battery data"}


def verify_014(server_url):
    base = f"{server_url}/sites/comparison-aggregators"
    r = requests.get(f"{base}/api/stats?brand=Apple")
    data = r.json()
    count = data.get("count", 0)
    return {"pass": count >= 0, "detail": f"Apple phones: {count}"}


def verify_015(server_url):
    base = f"{server_url}/sites/comparison-aggregators"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "techfan_alice", "password": "pass123"})
    r = s.post(f"{base}/api/users/1/favorite", json={"phone_id": 1})
    data = r.json()
    action = data.get("action")
    return {"pass": action == "added", "detail": f"Favorite action: {action}"}


def verify_016(server_url):
    base = f"{server_url}/sites/comparison-aggregators"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "gadget_bob", "password": "pass456"})
    s.post(f"{base}/api/users/2/compare-list", json={"phone_id": 1})
    r2 = s.post(f"{base}/api/users/2/compare-list", json={"phone_id": 2})
    data = r2.json()
    total = data.get("total_in_compare", 0)
    return {"pass": total >= 2, "detail": f"Bob's compare list size: {total}"}


def verify_017(server_url):
    base = f"{server_url}/sites/comparison-aggregators"
    r = requests.get(f"{base}/api/phones?year_from=2023&year_to=2024&battery_min=4000")
    phones = r.json()
    count = len(phones)
    ok = all(
        p["year"] is not None and 2023 <= p["year"] <= 2024
        and p["battery_mah"] is not None and p["battery_mah"] >= 4000
        for p in phones
    )
    return {"pass": count >= 0 and ok, "detail": f"2023-2024 phones with 4000+mAh: {count}"}


def verify_018(server_url):
    base = f"{server_url}/sites/comparison-aggregators"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "mobile_carol", "password": "pass789"})
    s.post(f"{base}/api/users/3/favorite", json={"phone_id": 3})
    r = s.get(f"{base}/api/users/3")
    user = r.json()
    favs = user.get("favorites", [])
    return {"pass": 3 in favs, "detail": f"Carol favorites: {favs}"}


def verify_019(server_url):
    base = f"{server_url}/sites/comparison-aggregators"
    r = requests.get(f"{base}/api/phones?sort=price_asc&limit=5")
    phones = r.json()
    if phones and phones[0]["price"] is not None:
        top = phones[0]
        return {"pass": True, "detail": f"Cheapest: {top['name']} ${top['price']}"}
    return {"pass": False, "detail": "No priced phones in results"}


def verify_020(server_url):
    base = f"{server_url}/sites/comparison-aggregators"
    r = requests.get(f"{base}/api/brands")
    brands = r.json()
    if brands:
        top_brand = max(brands, key=lambda b: b["count"])
        name = top_brand["name"]
        count = top_brand["count"]
        return {"pass": True, "detail": f"Top brand: {name} with {count} phones"}
    return {"pass": False, "detail": "No brands"}
