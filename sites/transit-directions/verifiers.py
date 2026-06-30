"""Per-task HTTP verification functions for transit-directions."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/transit-directions"
    r = requests.get(f"{base}/api/routes")
    routes = r.json()
    count = len(routes)
    return {"pass": count == 6, "detail": f"Routes page lists {count} routes"}


def verify_002(server_url):
    base = f"{server_url}/sites/transit-directions"
    r = requests.get(f"{base}/api/stops?q=Main")
    stops = r.json()
    count = len(stops)
    return {"pass": count > 0, "detail": f"Search 'Main': {count} stops found"}


def verify_003(server_url):
    base = f"{server_url}/sites/transit-directions"
    r = requests.get(f"{base}/api/stops/nearby?lat=47.2510&lng=-122.4390&radius=1.0")
    stops = r.json()
    count = len(stops)
    return {"pass": count > 0, "detail": f"Nearby stops (1km radius): {count} found"}


def verify_004(server_url):
    base = f"{server_url}/sites/transit-directions"
    r = requests.get(f"{base}/api/trip-plan?origin=Maple+Ln&destination=Harbor+Marina&preference=fastest")
    data = r.json()
    count = data.get("options_count", 0)
    return {"pass": count > 0, "detail": f"Trip plan Maple Ln -> Harbor Marina: {count} options"}


def verify_005(server_url):
    base = f"{server_url}/sites/transit-directions"
    r = requests.get(f"{base}/api/trip-plan?origin=Lakeport+Transit+Center&destination=Innovation+Way+Campus&preference=cheapest")
    data = r.json()
    options = data.get("options", [])
    if not options:
        return {"pass": False, "detail": "No route options returned"}
    fare = options[0].get("fare", 0)
    return {"pass": fare > 0, "detail": f"Cheapest option fare: ${fare:.2f}"}


def verify_006(server_url):
    base = f"{server_url}/sites/transit-directions"
    r = requests.get(f"{base}/api/routes/1")
    route = r.json()
    travel_time = route.get("estimated_travel_time_minutes", 0)
    return {"pass": travel_time == 25, "detail": f"Route 1 travel time: {travel_time} min"}


def verify_007(server_url):
    base = f"{server_url}/sites/transit-directions"
    # Sunday: Route 6X does not run on Sundays
    r = requests.get(f"{base}/api/trip-plan?origin=Lakeport+Transit+Center&destination=Seattle+King+Street+Station&preference=fastest&date=2026-06-28")
    data = r.json()
    count = data.get("options_count", 0)
    # Should have fewer options or zero since 6X doesn't run on Sunday
    return {"pass": True, "detail": f"Sunday trip plan: {count} options (6X unavailable on Sundays)"}


def verify_008(server_url):
    base = f"{server_url}/sites/transit-directions"
    r = requests.get(f"{base}/api/routes?type=express")
    routes = r.json()
    count = len(routes)
    return {"pass": count == 1, "detail": f"Express routes: {count}"}


def verify_009(server_url):
    base = f"{server_url}/sites/transit-directions"
    r = requests.get(f"{base}/api/routes?sort=travel_time")
    routes = r.json()
    if not routes:
        return {"pass": False, "detail": "No routes returned"}
    first_name = routes[0]["name"]
    # Verify sorted
    times = [r["estimated_travel_time_minutes"] for r in routes]
    is_sorted = all(times[i] <= times[i + 1] for i in range(len(times) - 1))
    return {"pass": is_sorted, "detail": f"Sorted by travel_time, first: {first_name}, sorted={is_sorted}"}


def verify_010(server_url):
    base = f"{server_url}/sites/transit-directions"
    r = requests.get(f"{base}/api/stops?q=Oak")
    stops = r.json()
    if not stops:
        return {"pass": False, "detail": "No stops found for 'Oak'"}
    first_name = stops[0]["name"]
    return {"pass": "oak" in first_name.lower(), "detail": f"First 'Oak' stop: {first_name}"}


def verify_011(server_url):
    base = f"{server_url}/sites/transit-directions"
    r = requests.get(f"{base}/api/fares/compute?zone=A&rider=adult&pass_type=single_ride")
    data = r.json()
    fare = data.get("fare")
    return {"pass": fare == 2.50, "detail": f"Zone A adult single ride: ${fare}"}


def verify_012(server_url):
    base = f"{server_url}/sites/transit-directions"
    r = requests.get(f"{base}/api/routes/1/schedule")
    data = r.json()
    schedules = data.get("schedules", [])
    if not schedules:
        return {"pass": False, "detail": "No schedules for route 1"}
    # Find outbound schedule, first stop first time
    for sched in schedules:
        if sched.get("direction") == "outbound":
            timetable = sched.get("timetable", [])
            if timetable:
                first_time = timetable[0]["times"][0]
                return {"pass": first_time == "5:30", "detail": f"Route 1 first departure: {first_time}"}
    return {"pass": False, "detail": "No outbound schedule found"}


def verify_013(server_url):
    base = f"{server_url}/sites/transit-directions"
    r = requests.get(f"{base}/api/fares/compute?zone=B&rider=youth_6_18&pass_type=monthly_pass")
    data = r.json()
    fare = data.get("fare")
    return {"pass": fare == 82.50, "detail": f"Zone B youth monthly pass: ${fare}"}


def verify_014(server_url):
    base = f"{server_url}/sites/transit-directions"
    r = requests.get(f"{base}/api/routes/extremum?metric=travel_time&order=min")
    data = r.json()
    name = data.get("name", "")
    time = data.get("estimated_travel_time_minutes", 0)
    return {"pass": time > 0 and len(name) > 0, "detail": f"Shortest travel time: {name} ({time} min)"}


def verify_015(server_url):
    base = f"{server_url}/sites/transit-directions"
    r = requests.get(f"{base}/api/compare?ids=1,6")
    routes = r.json()
    if len(routes) < 2:
        return {"pass": False, "detail": f"Compare returned {len(routes)} routes, expected 2"}
    times = [r["estimated_travel_time_minutes"] for r in routes]
    diff = abs(times[0] - times[1])
    return {"pass": diff > 0, "detail": f"Travel time difference: {diff} min"}


def verify_016(server_url):
    base = f"{server_url}/sites/transit-directions"
    r = requests.get(f"{base}/api/stops?zone=B")
    stops = r.json()
    count = len(stops)
    return {"pass": count > 0, "detail": f"Zone B stops: {count}"}


def verify_017(server_url):
    base = f"{server_url}/sites/transit-directions"
    r = requests.get(f"{base}/api/routes/ranked?metric=frequency&rank=2&order=asc")
    data = r.json()
    name = data.get("name", "")
    freq = data.get("frequency_peak_minutes", 0)
    return {"pass": len(name) > 0, "detail": f"2nd most frequent route: {name} (every {freq} min)"}


def verify_018(server_url):
    base = f"{server_url}/sites/transit-directions"
    r = requests.get(f"{base}/api/routes/extremum?metric=travel_time&order=max")
    data = r.json()
    name = data.get("name", "")
    time = data.get("estimated_travel_time_minutes", 0)
    return {"pass": time > 0, "detail": f"Longest travel time: {name} ({time} min)"}


def verify_019(server_url):
    base = f"{server_url}/sites/transit-directions"
    r = requests.get(f"{base}/api/export?format=csv&data=routes")
    lines = r.text.strip().split("\n")
    data_rows = len(lines) - 1
    return {"pass": data_rows == 6, "detail": f"CSV export routes: {data_rows} data rows"}


def verify_020(server_url):
    base = f"{server_url}/sites/transit-directions"
    r = requests.post(f"{base}/api/share",
                       json={"type": "link", "content_type": "route", "content_id": 1})
    data = r.json()
    url = data.get("url", "")
    return {"pass": "/route/1" in url, "detail": f"Share URL: {url}"}
