"""Per-task reference solutions via Flask test client for comparison-aggregators."""
import json


def solve_001(client, base="/sites/comparison-aggregators"):
    r = client.get(f"{base}/api/phones")
    phones = json.loads(r.data)
    return str(len(phones))


def solve_002(client, base="/sites/comparison-aggregators"):
    r = client.get(f"{base}/api/brands")
    brands = json.loads(r.data)
    return str(len(brands))


def solve_003(client, base="/sites/comparison-aggregators"):
    r = client.get(f"{base}/api/phones/1")
    phone = json.loads(r.data)
    return f"{phone['brand']} {phone['name']}"


def solve_004(client, base="/sites/comparison-aggregators"):
    r = client.get(f"{base}/api/stats")
    data = json.loads(r.data)
    return str(data["avg_price"])


def solve_005(client, base="/sites/comparison-aggregators"):
    r = client.get(f"{base}/api/users/1")
    user = json.loads(r.data)
    return user["username"]


def solve_006(client, base="/sites/comparison-aggregators"):
    r = client.get(f"{base}/api/phones?brand=Samsung")
    phones = json.loads(r.data)
    return str(len(phones))


def solve_007(client, base="/sites/comparison-aggregators"):
    r = client.get(f"{base}/api/phones?price_min=500&price_max=1000")
    phones = json.loads(r.data)
    return str(len(phones))


def solve_008(client, base="/sites/comparison-aggregators"):
    r = client.get(f"{base}/api/phones?os=Android")
    phones = json.loads(r.data)
    return str(len(phones))


def solve_009(client, base="/sites/comparison-aggregators"):
    r = client.get(f"{base}/api/phones?sort=price_desc")
    phones = json.loads(r.data)
    priced = [p for p in phones if p["price"] is not None]
    if priced:
        return priced[0]["name"]
    return "None"


def solve_010(client, base="/sites/comparison-aggregators"):
    r = client.get(f"{base}/api/phones?q=iPhone")
    phones = json.loads(r.data)
    return str(len(phones))


def solve_011(client, base="/sites/comparison-aggregators"):
    r = client.get(f"{base}/api/compare?ids=1,2,3")
    phones = json.loads(r.data)
    names = [p["name"] for p in phones]
    return ", ".join(names)


def solve_012(client, base="/sites/comparison-aggregators"):
    r = client.get(f"{base}/api/stats")
    data = json.loads(r.data)
    os_dist = data.get("os_distribution", {})
    if os_dist:
        top_os = max(os_dist, key=os_dist.get)
        return top_os
    return "None"


def solve_013(client, base="/sites/comparison-aggregators"):
    r = client.get(f"{base}/api/phones?sort=battery_desc")
    phones = json.loads(r.data)
    with_bat = [p for p in phones if p["battery_mah"] is not None]
    if with_bat:
        top = with_bat[0]
        return f"{top['name']} {top['battery_mah']}mAh"
    return "None"


def solve_014(client, base="/sites/comparison-aggregators"):
    r = client.get(f"{base}/api/stats?brand=Apple")
    data = json.loads(r.data)
    return str(data.get("count", 0))


def solve_015(client, base="/sites/comparison-aggregators"):
    client.post(f"{base}/api/login",
                json={"username": "techfan_alice", "password": "pass123"},
                content_type="application/json")
    r = client.post(f"{base}/api/users/1/favorite",
                     json={"phone_id": 1},
                     content_type="application/json")
    data = json.loads(r.data)
    return data.get("action", "")


def solve_016(client, base="/sites/comparison-aggregators"):
    client.post(f"{base}/api/login",
                json={"username": "gadget_bob", "password": "pass456"},
                content_type="application/json")
    client.post(f"{base}/api/users/2/compare-list",
                json={"phone_id": 1},
                content_type="application/json")
    r = client.post(f"{base}/api/users/2/compare-list",
                     json={"phone_id": 2},
                     content_type="application/json")
    data = json.loads(r.data)
    return str(data.get("total_in_compare", 0))


def solve_017(client, base="/sites/comparison-aggregators"):
    r = client.get(f"{base}/api/phones?year_from=2023&year_to=2024&battery_min=4000")
    phones = json.loads(r.data)
    return str(len(phones))


def solve_018(client, base="/sites/comparison-aggregators"):
    client.post(f"{base}/api/login",
                json={"username": "mobile_carol", "password": "pass789"},
                content_type="application/json")
    client.post(f"{base}/api/users/3/favorite",
                json={"phone_id": 3},
                content_type="application/json")
    r = client.get(f"{base}/api/users/3")
    user = json.loads(r.data)
    favs = user.get("favorites", [])
    return str(3 in favs)


def solve_019(client, base="/sites/comparison-aggregators"):
    r = client.get(f"{base}/api/phones?sort=price_asc&limit=5")
    phones = json.loads(r.data)
    if phones and phones[0]["price"] is not None:
        top = phones[0]
        return f"{top['name']} ${top['price']}"
    return "None"


def solve_020(client, base="/sites/comparison-aggregators"):
    r = client.get(f"{base}/api/brands")
    brands = json.loads(r.data)
    if brands:
        top_brand = max(brands, key=lambda b: b["count"])
        return f"{top_brand['name']} ({top_brand['count']})"
    return "None"
