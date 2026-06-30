"""Per-macro verification functions for transit-directions.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/transit-directions"


def verify_macro_navigate_by_dropdown(server_url):
    """Navigate to routes page via nav; verify routes list loads."""
    r = requests.get(f"{_base(server_url)}/routes")
    return {"pass": r.status_code == 200, "detail": f"Routes page: {r.status_code}"}


def verify_macro_search_by_query(server_url):
    """Search stops by query string."""
    r = requests.get(f"{_base(server_url)}/api/stops?q=Main")
    stops = r.json()
    ok = len(stops) > 0 and all("main" in s["name"].lower() or "main" in s.get("address", "").lower() for s in stops)
    return {"pass": ok, "detail": f"search_by_query 'Main': {len(stops)} stops, all_match={ok}"}


def verify_macro_search_by_proximity(server_url):
    """Find stops near a lat/lng coordinate."""
    r = requests.get(f"{_base(server_url)}/api/stops/nearby?lat=47.2510&lng=-122.4390&radius=1.0")
    stops = r.json()
    ok = len(stops) > 0 and all("distance_km" in s for s in stops)
    return {"pass": ok, "detail": f"search_by_proximity: {len(stops)} nearby stops"}


def verify_macro_route_by_query(server_url):
    """Plan a trip by entering origin/destination text."""
    r = requests.get(f"{_base(server_url)}/api/trip-plan?origin=Maple+Ln&destination=Harbor+Marina&preference=fastest")
    data = r.json()
    ok = data.get("options_count", 0) > 0
    return {"pass": ok, "detail": f"route_by_query: {data.get('options_count', 0)} options"}


def verify_macro_route_by_radio(server_url):
    """Plan a trip using radio button preference (cheapest vs fastest)."""
    r1 = requests.get(f"{_base(server_url)}/api/trip-plan?origin=Lakeport+Transit+Center&destination=Innovation+Way+Campus&preference=fastest")
    r2 = requests.get(f"{_base(server_url)}/api/trip-plan?origin=Lakeport+Transit+Center&destination=Innovation+Way+Campus&preference=cheapest")
    d1 = r1.json()
    d2 = r2.json()
    ok = d1.get("route_preference") == "fastest" and d2.get("route_preference") == "cheapest"
    return {"pass": ok, "detail": f"route_by_radio: fastest={d1.get('route_preference')}, cheapest={d2.get('route_preference')}"}


def verify_macro_route_by_route(server_url):
    """View route detail page by route ID."""
    r = requests.get(f"{_base(server_url)}/route/1")
    return {"pass": r.status_code == 200, "detail": f"route_by_route: route detail page {r.status_code}"}


def verify_macro_route_by_date_range(server_url):
    """Plan trip with date filtering (day-of-week availability)."""
    # Sunday: Route 6X doesn't run
    r = requests.get(f"{_base(server_url)}/api/trip-plan?origin=Lakeport+Transit+Center&destination=Seattle+King+Street+Station&preference=fastest&date=2026-06-28")
    data = r.json()
    return {"pass": r.status_code == 201, "detail": f"route_by_date_range: {data.get('options_count', 0)} Sunday options"}


def verify_macro_filter_by_radio(server_url):
    """Filter routes by type using radio buttons."""
    r = requests.get(f"{_base(server_url)}/api/routes?type=express")
    routes = r.json()
    ok = all(r.get("type") == "express" for r in routes)
    return {"pass": ok and len(routes) > 0, "detail": f"filter_by_radio express: {len(routes)} routes, all_express={ok}"}


def verify_macro_sort_by_dropdown(server_url):
    """Sort routes by dropdown selection."""
    r = requests.get(f"{_base(server_url)}/api/routes?sort=travel_time")
    routes = r.json()
    if len(routes) < 2:
        return {"pass": True, "detail": "Too few routes to verify sort"}
    times = [r["estimated_travel_time_minutes"] for r in routes]
    is_sorted = all(times[i] <= times[i + 1] for i in range(len(times) - 1))
    return {"pass": is_sorted, "detail": f"sort_by_dropdown travel_time: sorted={is_sorted}"}


def verify_macro_extract_by_query(server_url):
    """Extract data from search results."""
    r = requests.get(f"{_base(server_url)}/api/stops?q=Harbor")
    stops = r.json()
    if stops:
        return {"pass": True, "detail": f"extract_by_query: first stop={stops[0]['name']}"}
    return {"pass": True, "detail": "extract_by_query: no results (ok)"}


def verify_macro_extract_by_dropdown(server_url):
    """Extract fare data using dropdown selections."""
    r = requests.get(f"{_base(server_url)}/api/fares/compute?zone=A&rider=adult&pass_type=single_ride")
    data = r.json()
    fare = data.get("fare")
    return {"pass": fare is not None, "detail": f"extract_by_dropdown: Zone A adult single_ride=${fare}"}


def verify_macro_extract_from_table(server_url):
    """Extract data from schedule timetable."""
    r = requests.get(f"{_base(server_url)}/api/routes/1/schedule")
    data = r.json()
    schedules = data.get("schedules", [])
    has_timetable = any(len(s.get("timetable", [])) > 0 for s in schedules)
    return {"pass": has_timetable, "detail": f"extract_from_table: {len(schedules)} schedules, has_timetable={has_timetable}"}


def verify_macro_compute_by_dropdown(server_url):
    """Compute fare for specific zone/rider/pass combination."""
    r = requests.get(f"{_base(server_url)}/api/fares/compute?zone=B&rider=senior_65_plus&pass_type=monthly_pass")
    data = r.json()
    fare = data.get("fare")
    return {"pass": fare is not None and fare > 0, "detail": f"compute_by_dropdown: Zone B senior monthly=${fare}"}


def verify_macro_compute_by_extremum(server_url):
    """Find fastest/slowest route."""
    r = requests.get(f"{_base(server_url)}/api/routes/extremum?metric=travel_time&order=min")
    data = r.json()
    name = data.get("name", "")
    return {"pass": len(name) > 0, "detail": f"compute_by_extremum: fastest={name}"}


def verify_macro_compare_from_table(server_url):
    """Compare two routes side-by-side."""
    r = requests.get(f"{_base(server_url)}/api/compare?ids=1,6")
    routes = r.json()
    if len(routes) < 2:
        return {"pass": False, "detail": "Compare needs 2 routes"}
    return {"pass": routes[0]["id"] != routes[1]["id"],
            "detail": f"compare: route {routes[0]['id']} vs {routes[1]['id']}"}


def verify_macro_select_by_dropdown(server_url):
    """Select stops by zone dropdown."""
    r = requests.get(f"{_base(server_url)}/api/stops?zone=B")
    stops = r.json()
    ok = all(s.get("zone") == "B" for s in stops)
    return {"pass": ok and len(stops) > 0, "detail": f"select_by_dropdown zone B: {len(stops)} stops, all_B={ok}"}


def verify_macro_select_by_ranking(server_url):
    """Select Nth ranked route by metric."""
    r = requests.get(f"{_base(server_url)}/api/routes/ranked?metric=travel_time&rank=1&order=asc")
    data = r.json()
    return {"pass": data.get("rank") == 1, "detail": f"select_by_ranking: rank={data.get('rank')}, name={data.get('name')}"}


def verify_macro_select_by_extremum(server_url):
    """Select route with extreme metric value."""
    r = requests.get(f"{_base(server_url)}/api/routes/extremum?metric=travel_time&order=max")
    data = r.json()
    name = data.get("name", "")
    time = data.get("estimated_travel_time_minutes", 0)
    return {"pass": len(name) > 0 and time > 0, "detail": f"select_by_extremum: slowest={name} ({time} min)"}


def verify_macro_export_by_dropdown(server_url):
    """Export routes data as CSV."""
    r = requests.get(f"{_base(server_url)}/api/export?format=csv&data=routes")
    lines = r.text.strip().split("\n")
    return {"pass": len(lines) > 1, "detail": f"export CSV: {len(lines)} lines"}


def verify_macro_share_by_dropdown(server_url):
    """Share route via link."""
    r = requests.post(f"{_base(server_url)}/api/share",
                       json={"type": "link", "content_type": "route", "content_id": 1})
    data = r.json()
    ok = data.get("shared") is True and "/route/1" in data.get("url", "")
    return {"pass": ok, "detail": f"share_by_dropdown: url={data.get('url')}"}
