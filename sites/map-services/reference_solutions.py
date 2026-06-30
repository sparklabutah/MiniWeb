"""Per-task reference solutions via Flask test client for map-services."""
import json


def solve_001(client, base="/sites/map-services"):
    r = client.get(f"{base}/api/locations?category=restaurant")
    return str(len(json.loads(r.data)))


def solve_002(client, base="/sites/map-services"):
    r = client.get(f"{base}/api/locations/1")
    return json.loads(r.data)["phone"]


def solve_003(client, base="/sites/map-services"):
    r = client.get(f"{base}/api/search?q=sushi")
    results = json.loads(r.data)
    return results[0]["name"] if results else "No results"


def solve_004(client, base="/sites/map-services"):
    r = client.get(f"{base}/api/locations/semantic?q=outdoor+recreation+lake")
    return str(len(json.loads(r.data)))


def solve_005(client, base="/sites/map-services"):
    r = client.get(f"{base}/api/locations?category=grocery")
    return str(len(json.loads(r.data)))


def solve_006(client, base="/sites/map-services"):
    r = client.get(f"{base}/api/locations?lat_min=47.245&lat_max=47.252&lng_min=-122.445&lng_max=-122.435")
    return str(len(json.loads(r.data)))


def solve_007(client, base="/sites/map-services"):
    r = client.get(f"{base}/api/nearby?lat=47.2512&lng=-122.4385&radius=0.5")
    return str(len(json.loads(r.data)))


def solve_008(client, base="/sites/map-services"):
    r = client.get(f"{base}/api/locations?category=park")
    return str(len(json.loads(r.data)))


def solve_009(client, base="/sites/map-services"):
    r = client.get(f"{base}/api/locations?open_now=1")
    return str(len(json.loads(r.data)))


def solve_010(client, base="/sites/map-services"):
    r = client.get(f"{base}/api/locations?min_rating=4.5")
    return str(len(json.loads(r.data)))


def solve_011(client, base="/sites/map-services"):
    r = client.get(f"{base}/api/locations?sort=rating")
    locs = json.loads(r.data)
    return locs[0]["name"] if locs else ""


def solve_012(client, base="/sites/map-services"):
    r = client.get(f"{base}/api/search?q=hardware")
    results = json.loads(r.data)
    return results[0]["address"] if results else "No results"


def solve_013(client, base="/sites/map-services"):
    r = client.get(f"{base}/api/locations/3")
    return str(json.loads(r.data)["rating"])


def solve_014(client, base="/sites/map-services"):
    r = client.get(f"{base}/api/routes/compute?origin=Cascadia+Coffee+Roasters&destination=Harborview+Grill&mode=driving")
    data = json.loads(r.data)
    return str(data["distance_km"])


def solve_015(client, base="/sites/map-services"):
    r = client.get(f"{base}/api/compare?ids=1,3,13")
    places = json.loads(r.data)
    return ", ".join(str(p["rating"]) for p in places)


def solve_016(client, base="/sites/map-services"):
    client.post(f"{base}/api/login", json={"username": "alex_rivera"})
    r = client.post(f"{base}/api/saved-places", json={"location_id": 21, "user_id": 1})
    data = json.loads(r.data)
    return data.get("action", "")


def solve_017(client, base="/sites/map-services"):
    client.post(f"{base}/api/login", json={"username": "alex_rivera"})
    r = client.post(f"{base}/api/reviews", json={
        "location_id": 6, "text": "Great Italian food, cozy atmosphere",
        "rating": 4.0, "user_id": 1
    })
    data = json.loads(r.data)
    return data.get("text", "")


def solve_018(client, base="/sites/map-services"):
    client.post(f"{base}/api/login", json={"username": "alex_rivera"})
    r = client.post(f"{base}/api/share", json={
        "location_id": 1, "username": "marcus_chen"
    })
    data = json.loads(r.data)
    return data.get("action", "")


def solve_019(client, base="/sites/map-services"):
    client.post(f"{base}/api/login", json={"username": "alex_rivera"})
    r = client.put(f"{base}/api/users/1/settings",
                   json={"default_mode": "cycling", "units": "metric"})
    data = json.loads(r.data)
    return f"mode={data.get('default_mode')}, units={data.get('units')}"


def solve_020(client, base="/sites/map-services"):
    r = client.get(f"{base}/api/export?format=csv&category=restaurant")
    lines = r.data.decode().strip().split("\n")
    return str(len(lines) - 1)
