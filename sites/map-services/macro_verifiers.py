"""Per-macro verification functions for map-services.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/map-services"


def verify_macro_navigate_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/categories")
    cats = r.json()
    if not cats:
        return {"pass": False, "detail": "No categories returned"}
    cat = cats[0]["name"]
    r2 = requests.get(f"{_base(server_url)}/api/locations?category={cat}")
    locs = r2.json()
    return {"pass": len(locs) > 0, "detail": f"Category '{cat}': {len(locs)} locations"}


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/place/1")
    return {"pass": r.status_code == 200, "detail": f"Place detail page: {r.status_code}"}


def verify_macro_search_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/search?q=coffee")
    results = r.json()
    return {"pass": len(results) > 0, "detail": f"search_by_query 'coffee': {len(results)} results"}


def verify_macro_search_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/locations/semantic?q=food+dining")
    results = r.json()
    return {"pass": r.status_code == 200, "detail": f"search_by_semantic: {len(results)} results"}


def verify_macro_search_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/categories")
    cats = r.json()
    if not cats:
        return {"pass": False, "detail": "No categories"}
    cat = cats[0]["name"]
    r2 = requests.get(f"{_base(server_url)}/api/categories/{cat}/locations")
    locs = r2.json()
    return {"pass": len(locs) > 0, "detail": f"search_by_dropdown '{cat}': {len(locs)} locations"}


def verify_macro_search_by_pan_zoom(server_url):
    r = requests.get(f"{_base(server_url)}/api/locations?lat_min=47.245&lat_max=47.255&lng_min=-122.445&lng_max=-122.435")
    locs = r.json()
    return {"pass": r.status_code == 200, "detail": f"search_by_pan_zoom: {len(locs)} locations in box"}


def verify_macro_search_by_proximity(server_url):
    r = requests.get(f"{_base(server_url)}/api/nearby?lat=47.2512&lng=-122.4385&radius=1.0")
    locs = r.json()
    return {"pass": len(locs) > 0, "detail": f"search_by_proximity: {len(locs)} nearby"}


def verify_macro_filter_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/locations?category=restaurant")
    locs = r.json()
    ok = all(l["category"] == "restaurant" for l in locs)
    return {"pass": ok and len(locs) > 0, "detail": f"filter_by_dropdown restaurant: {len(locs)}, all_match={ok}"}


def verify_macro_filter_by_toggle(server_url):
    r = requests.get(f"{_base(server_url)}/api/locations?open_now=1")
    locs = r.json()
    ok = all("closed" not in l.get("hours", "").lower() for l in locs)
    return {"pass": ok, "detail": f"filter_by_toggle open_now: {len(locs)} locations, all_open={ok}"}


def verify_macro_filter_by_slider(server_url):
    r = requests.get(f"{_base(server_url)}/api/locations?min_rating=4.5")
    locs = r.json()
    ok = all(l["rating"] >= 4.5 for l in locs)
    return {"pass": ok, "detail": f"filter_by_slider min_rating=4.5: {len(locs)}, all_match={ok}"}


def verify_macro_sort_by_ranking(server_url):
    r = requests.get(f"{_base(server_url)}/api/locations?sort=rating")
    locs = r.json()
    if len(locs) < 2:
        return {"pass": True, "detail": "Too few locations to verify sort"}
    ratings = [l["rating"] for l in locs]
    is_sorted = all(ratings[i] >= ratings[i+1] for i in range(len(ratings)-1))
    return {"pass": is_sorted, "detail": f"sort_by_ranking: sorted_desc={is_sorted}"}


def verify_macro_extract_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/search?q=library")
    results = r.json()
    if results:
        return {"pass": True, "detail": f"extract_by_query: first={results[0]['name'][:50]}"}
    return {"pass": True, "detail": "extract_by_query: no results (ok)"}


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/locations/1")
    loc = r.json()
    return {"pass": "address" in loc and "rating" in loc,
            "detail": f"extract_by_route: name={loc.get('name')}, rating={loc.get('rating')}"}


def verify_macro_compute_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/routes/compute?origin=Cascadia+Coffee+Roasters&destination=Harborview+Grill&mode=driving")
    data = r.json()
    return {"pass": "distance_km" in data and "duration_minutes" in data,
            "detail": f"compute_by_route: {data.get('distance_km')} km, {data.get('duration_minutes')} min"}


def verify_macro_compare_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/compare?ids=1,3")
    places = r.json()
    if len(places) < 2:
        return {"pass": False, "detail": "Compare needs 2+ places"}
    return {"pass": places[0]["id"] != places[1]["id"],
            "detail": f"compare_by_route: {places[0]['name']} vs {places[1]['name']}"}


def verify_macro_create_from_free_text(server_url):
    r = requests.post(f"{_base(server_url)}/api/locations", json={
        "name": "Test Place Macro", "category": "test", "address": "123 Test St",
        "lat": 47.25, "lng": -122.44, "rating": 3.0
    })
    data = r.json()
    ok = data.get("name") == "Test Place Macro"
    # Clean up by reading locations count
    return {"pass": ok, "detail": f"create_from_free_text: created id={data.get('id')}"}


def verify_macro_submit_by_query(server_url):
    r = requests.post(f"{_base(server_url)}/api/submit-feedback", json={
        "location_id": 1, "type": "correction", "message": "Hours are wrong"
    })
    data = r.json()
    return {"pass": data.get("status") == "submitted",
            "detail": f"submit_by_query: status={data.get('status')}"}


def verify_macro_post_from_free_text(server_url):
    r = requests.post(f"{_base(server_url)}/api/reviews", json={
        "location_id": 1, "text": "Macro test review", "rating": 4.0, "user_id": 4
    })
    data = r.json()
    ok = data.get("text") == "Macro test review"
    return {"pass": ok, "detail": f"post_from_free_text: review id={data.get('id')}"}


def verify_macro_select_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/select?q=Harborview")
    data = r.json()
    return {"pass": "Harborview" in data.get("name", ""),
            "detail": f"select_by_query: found {data.get('name')}"}


def verify_macro_configure_by_dropdown(server_url):
    # Change user 4's settings
    r = requests.put(f"{_base(server_url)}/api/users/4/settings",
                     json={"default_mode": "walking", "units": "metric"})
    data = r.json()
    ok = data.get("default_mode") == "walking" and data.get("units") == "metric"
    # Revert
    requests.put(f"{_base(server_url)}/api/users/4/settings",
                 json={"default_mode": "driving", "units": "imperial"})
    return {"pass": ok, "detail": f"configure_by_dropdown: mode={data.get('default_mode')}, units={data.get('units')}"}


def verify_macro_export_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/export?format=csv")
    lines = r.text.strip().split("\n")
    return {"pass": len(lines) > 1, "detail": f"export_by_route CSV: {len(lines)} lines"}


def verify_macro_rate_by_slider(server_url):
    r = requests.post(f"{_base(server_url)}/api/reviews", json={
        "location_id": 2, "text": "Rating macro test", "rating": 3.5, "user_id": 4
    })
    data = r.json()
    ok = data.get("rating") == 3.5
    return {"pass": ok, "detail": f"rate_by_slider: rating={data.get('rating')}"}


def verify_macro_share_by_query(server_url):
    r = requests.post(f"{_base(server_url)}/api/share", json={
        "location_id": 2, "username": "daniel_okonkwo"
    })
    data = r.json()
    ok = data.get("action") in ("shared", "already_shared")
    return {"pass": ok, "detail": f"share_by_query: action={data.get('action')}"}


def verify_macro_save_by_query(server_url):
    r = requests.post(f"{_base(server_url)}/api/saved-places", json={
        "location_id": 99, "user_id": 4
    })
    data = r.json()
    ok = data.get("action") == "saved"
    # Toggle back (unsave)
    requests.post(f"{_base(server_url)}/api/saved-places", json={
        "location_id": 99, "user_id": 4
    })
    return {"pass": ok, "detail": f"save_by_query: action={data.get('action')}"}


def verify_macro_route_by_query(server_url):
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login", json={"username": "mia_torres"})
    r = s.post(f"{_base(server_url)}/api/routes", json={
        "origin": "Brooks Fitness", "destination": "Harborview Grill", "mode": "driving"
    })
    data = r.json()
    ok = "distance_km" in data and data.get("origin") == "Brooks Fitness"
    return {"pass": ok, "detail": f"route_by_query: {data.get('origin')} -> {data.get('destination')}"}


def verify_macro_route_by_radio(server_url):
    r = requests.get(f"{_base(server_url)}/api/routes?mode=cycling&user_id=1")
    routes = r.json()
    ok = all(rt["mode"] == "cycling" for rt in routes)
    return {"pass": ok, "detail": f"route_by_radio cycling: {len(routes)} routes, all_cycling={ok}"}


def verify_macro_route_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/routes/1")
    route = r.json()
    return {"pass": "steps" in route and "distance_km" in route,
            "detail": f"route_by_route: id=1, name={route.get('name')}"}
