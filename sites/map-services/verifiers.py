"""Per-task HTTP verification functions for map-services."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/map-services"
    r = requests.get(f"{base}/api/locations?category=restaurant")
    locations = r.json()
    count = len(locations)
    return {"pass": count > 0, "detail": f"restaurant category: {count} locations"}


def verify_002(server_url):
    base = f"{server_url}/sites/map-services"
    r = requests.get(f"{base}/api/locations/1")
    loc = r.json()
    phone = loc.get("phone", "")
    return {"pass": len(phone) > 0, "detail": f"Place 1 phone: {phone}"}


def verify_003(server_url):
    base = f"{server_url}/sites/map-services"
    r = requests.get(f"{base}/api/search?q=sushi")
    results = r.json()
    if not results:
        return {"pass": False, "detail": "No results for 'sushi'"}
    first = results[0]["name"]
    return {"pass": "sushi" in first.lower() or "Sushi" in first,
            "detail": f"First result for 'sushi': {first}"}


def verify_004(server_url):
    base = f"{server_url}/sites/map-services"
    r = requests.get(f"{base}/api/locations/semantic?q=outdoor+recreation+lake")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Semantic 'outdoor recreation lake': {count} results"}


def verify_005(server_url):
    base = f"{server_url}/sites/map-services"
    r = requests.get(f"{base}/api/locations?category=grocery")
    locations = r.json()
    count = len(locations)
    return {"pass": count > 0, "detail": f"grocery category: {count} locations"}


def verify_006(server_url):
    base = f"{server_url}/sites/map-services"
    r = requests.get(f"{base}/api/locations?lat_min=47.245&lat_max=47.252&lng_min=-122.445&lng_max=-122.435")
    locations = r.json()
    count = len(locations)
    return {"pass": count >= 0, "detail": f"Bounding box filter: {count} locations"}


def verify_007(server_url):
    base = f"{server_url}/sites/map-services"
    r = requests.get(f"{base}/api/nearby?lat=47.2512&lng=-122.4385&radius=0.5")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Nearby (0.5km of Coffee Roasters): {count} places"}


def verify_008(server_url):
    base = f"{server_url}/sites/map-services"
    r = requests.get(f"{base}/api/locations?category=park")
    locations = r.json()
    count = len(locations)
    return {"pass": count > 0, "detail": f"park category: {count} locations"}


def verify_009(server_url):
    base = f"{server_url}/sites/map-services"
    r = requests.get(f"{base}/api/locations?open_now=1")
    locations = r.json()
    count = len(locations)
    # Verify none are "closed"
    ok = all("closed" not in l.get("hours", "").lower() for l in locations)
    return {"pass": ok, "detail": f"Open now filter: {count} locations, all_open={ok}"}


def verify_010(server_url):
    base = f"{server_url}/sites/map-services"
    r = requests.get(f"{base}/api/locations?min_rating=4.5")
    locations = r.json()
    count = len(locations)
    ok = all(l["rating"] >= 4.5 for l in locations)
    return {"pass": ok and count > 0, "detail": f"Rating >= 4.5: {count} locations, all_match={ok}"}


def verify_011(server_url):
    base = f"{server_url}/sites/map-services"
    r = requests.get(f"{base}/api/locations?sort=rating")
    locations = r.json()
    if not locations:
        return {"pass": False, "detail": "No locations returned"}
    first = locations[0]["name"]
    # Verify sorted descending
    ratings = [l["rating"] for l in locations]
    is_sorted = all(ratings[i] >= ratings[i+1] for i in range(len(ratings)-1))
    return {"pass": is_sorted, "detail": f"Top-rated: {first} ({locations[0]['rating']}), sorted={is_sorted}"}


def verify_012(server_url):
    base = f"{server_url}/sites/map-services"
    r = requests.get(f"{base}/api/search?q=hardware")
    results = r.json()
    if not results:
        return {"pass": False, "detail": "No results for 'hardware'"}
    address = results[0]["address"]
    return {"pass": len(address) > 0, "detail": f"First 'hardware' result address: {address}"}


def verify_013(server_url):
    base = f"{server_url}/sites/map-services"
    r = requests.get(f"{base}/api/locations/3")
    loc = r.json()
    rating = loc.get("rating")
    return {"pass": rating is not None, "detail": f"Place 3 (Harborview Grill) rating: {rating}"}


def verify_014(server_url):
    base = f"{server_url}/sites/map-services"
    r = requests.get(f"{base}/api/routes/compute?origin=Cascadia+Coffee+Roasters&destination=Harborview+Grill&mode=driving")
    data = r.json()
    dist = data.get("distance_km")
    return {"pass": dist is not None and dist > 0,
            "detail": f"Route distance: {dist} km"}


def verify_015(server_url):
    base = f"{server_url}/sites/map-services"
    r = requests.get(f"{base}/api/compare?ids=1,3,13")
    places = r.json()
    if len(places) != 3:
        return {"pass": False, "detail": f"Compare returned {len(places)} places, expected 3"}
    ratings = [p["rating"] for p in places]
    return {"pass": True, "detail": f"Ratings: {ratings}"}


def verify_016(server_url):
    base = f"{server_url}/sites/map-services"
    r = requests.get(f"{base}/api/saved-places?user_id=1")
    saved = r.json()
    has_library = any(s.get("location_id") == 21 for s in saved)
    return {"pass": has_library,
            "detail": f"User 1 saved places: {len(saved)} items, library_saved={has_library}"}


def verify_017(server_url):
    base = f"{server_url}/sites/map-services"
    r = requests.get(f"{base}/api/reviews?location_id=6")
    reviews = r.json()
    user_review = next((rv for rv in reviews if rv.get("user_id") == 1
                        and "cozy" in rv.get("text", "").lower()), None)
    return {"pass": user_review is not None,
            "detail": f"Review for place 6 by user 1: {'found' if user_review else 'not found'}"}


def verify_018(server_url):
    base = f"{server_url}/sites/map-services"
    r = requests.get(f"{base}/api/saved-places?user_id=2")
    saved = r.json()
    has_coffee = any(s.get("location_id") == 1 and s.get("label") == "shared" for s in saved)
    return {"pass": has_coffee,
            "detail": f"User 2 has shared Coffee Roasters: {has_coffee}"}


def verify_019(server_url):
    base = f"{server_url}/sites/map-services"
    r = requests.get(f"{base}/api/users/1")
    user = r.json()
    mode_ok = user.get("default_mode") == "cycling"
    units_ok = user.get("units") == "metric"
    return {"pass": mode_ok and units_ok,
            "detail": f"User 1 mode={user.get('default_mode')}, units={user.get('units')}"}


def verify_020(server_url):
    base = f"{server_url}/sites/map-services"
    r = requests.get(f"{base}/api/export?format=csv&category=restaurant")
    lines = r.text.strip().split("\n")
    data_rows = len(lines) - 1  # minus header
    return {"pass": data_rows > 0, "detail": f"CSV export restaurant: {data_rows} data rows"}
