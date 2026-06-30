"""Per-task reference solutions via Flask test client for transit-directions."""
import json


def solve_001(client, base="/sites/transit-directions"):
    r = client.get(f"{base}/api/routes")
    return str(len(json.loads(r.data)))


def solve_002(client, base="/sites/transit-directions"):
    r = client.get(f"{base}/api/stops?q=Main")
    return str(len(json.loads(r.data)))


def solve_003(client, base="/sites/transit-directions"):
    r = client.get(f"{base}/api/stops/nearby?lat=47.2510&lng=-122.4390&radius=1.0")
    return str(len(json.loads(r.data)))


def solve_004(client, base="/sites/transit-directions"):
    r = client.get(f"{base}/api/trip-plan?origin=Maple+Ln&destination=Harbor+Marina&preference=fastest")
    data = json.loads(r.data)
    return str(data.get("options_count", 0))


def solve_005(client, base="/sites/transit-directions"):
    r = client.get(f"{base}/api/trip-plan?origin=Lakeport+Transit+Center&destination=Innovation+Way+Campus&preference=cheapest")
    data = json.loads(r.data)
    options = data.get("options", [])
    if options:
        return f"${options[0]['fare']:.2f}"
    return "N/A"


def solve_006(client, base="/sites/transit-directions"):
    r = client.get(f"{base}/api/routes/1")
    route = json.loads(r.data)
    return str(route["estimated_travel_time_minutes"])


def solve_007(client, base="/sites/transit-directions"):
    # Sunday 2026-06-28
    r = client.get(f"{base}/api/trip-plan?origin=Lakeport+Transit+Center&destination=Seattle+King+Street+Station&preference=fastest&date=2026-06-28")
    data = json.loads(r.data)
    return str(data.get("options_count", 0))


def solve_008(client, base="/sites/transit-directions"):
    r = client.get(f"{base}/api/routes?type=express")
    return str(len(json.loads(r.data)))


def solve_009(client, base="/sites/transit-directions"):
    r = client.get(f"{base}/api/routes?sort=travel_time")
    routes = json.loads(r.data)
    return routes[0]["name"] if routes else ""


def solve_010(client, base="/sites/transit-directions"):
    r = client.get(f"{base}/api/stops?q=Oak")
    stops = json.loads(r.data)
    return stops[0]["name"] if stops else "No results"


def solve_011(client, base="/sites/transit-directions"):
    r = client.get(f"{base}/api/fares/compute?zone=A&rider=adult&pass_type=single_ride")
    data = json.loads(r.data)
    return f"${data['fare']:.2f}"


def solve_012(client, base="/sites/transit-directions"):
    r = client.get(f"{base}/api/routes/1/schedule")
    data = json.loads(r.data)
    for sched in data.get("schedules", []):
        if sched.get("direction") == "outbound":
            timetable = sched.get("timetable", [])
            if timetable:
                return timetable[0]["times"][0]
    return "N/A"


def solve_013(client, base="/sites/transit-directions"):
    r = client.get(f"{base}/api/fares/compute?zone=B&rider=youth_6_18&pass_type=monthly_pass")
    data = json.loads(r.data)
    return f"${data['fare']:.2f}"


def solve_014(client, base="/sites/transit-directions"):
    r = client.get(f"{base}/api/routes/extremum?metric=travel_time&order=min")
    data = json.loads(r.data)
    return f"{data['name']} ({data['estimated_travel_time_minutes']} min)"


def solve_015(client, base="/sites/transit-directions"):
    r = client.get(f"{base}/api/compare?ids=1,6")
    routes = json.loads(r.data)
    times = [r["estimated_travel_time_minutes"] for r in routes]
    return str(abs(times[0] - times[1]))


def solve_016(client, base="/sites/transit-directions"):
    r = client.get(f"{base}/api/stops?zone=B")
    return str(len(json.loads(r.data)))


def solve_017(client, base="/sites/transit-directions"):
    r = client.get(f"{base}/api/routes/ranked?metric=frequency&rank=2&order=asc")
    data = json.loads(r.data)
    return data["name"]


def solve_018(client, base="/sites/transit-directions"):
    r = client.get(f"{base}/api/routes/extremum?metric=travel_time&order=max")
    data = json.loads(r.data)
    return data["name"]


def solve_019(client, base="/sites/transit-directions"):
    r = client.get(f"{base}/api/export?format=csv&data=routes")
    lines = r.data.decode().strip().split("\n")
    return str(len(lines) - 1)


def solve_020(client, base="/sites/transit-directions"):
    r = client.post(f"{base}/api/share",
                     json={"type": "link", "content_type": "route", "content_id": 1},
                     content_type="application/json")
    data = json.loads(r.data)
    return data.get("url", "")
