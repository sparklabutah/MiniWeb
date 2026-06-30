"""Per-task reference solutions via Flask test client for calendar-todo."""
import json


def solve_001(client, base="/sites/calendar-todo"):
    r = client.get(f"{base}/api/events/search?q=sprint")
    results = json.loads(r.data)
    event = next((e for e in results if "Sprint Planning" in e["title"]), None)
    return event["location"] if event else "Not found"


def solve_002(client, base="/sites/calendar-todo"):
    r = client.get(f"{base}/api/events/4")
    event = json.loads(r.data)
    return event["title"]


def solve_003(client, base="/sites/calendar-todo"):
    r = client.get(f"{base}/api/events?category=health")
    return str(len(json.loads(r.data)))


def solve_004(client, base="/sites/calendar-todo"):
    r = client.get(f"{base}/api/events/date/2026-06-22")
    return str(len(json.loads(r.data)))


def solve_005(client, base="/sites/calendar-todo"):
    r = client.get(f"{base}/api/events/search?q=fitness+exercise+workout")
    results = json.loads(r.data)
    return results[0]["title"] if results else "No results"


def solve_006(client, base="/sites/calendar-todo"):
    r = client.get(f"{base}/api/events?sort=title")
    events = json.loads(r.data)
    return events[0]["title"] if events else ""


def solve_007(client, base="/sites/calendar-todo"):
    r = client.get(f"{base}/api/events?date_from=2026-06-24&date_to=2026-06-26")
    return str(len(json.loads(r.data)))


def solve_008(client, base="/sites/calendar-todo"):
    r = client.get(f"{base}/api/events/search?q=meeting")
    results = json.loads(r.data)
    return results[0]["title"] if results else "No results"


def solve_009(client, base="/sites/calendar-todo"):
    r = client.get(f"{base}/api/events/search?q=career+development+mentoring")
    results = json.loads(r.data)
    titles = [e["title"] for e in results]
    return ", ".join(titles) if titles else "No results"


def solve_010(client, base="/sites/calendar-todo"):
    r = client.get(f"{base}/api/categories/work/stats")
    stats = json.loads(r.data)
    return f"count={stats['count']}, unique_users={stats['unique_users']}"


def solve_011(client, base="/sites/calendar-todo"):
    r = client.get(f"{base}/api/events/9")
    event = json.loads(r.data)
    return event["description"]


def solve_012(client, base="/sites/calendar-todo"):
    r = client.get(f"{base}/api/events?date_from=2026-06-21&date_to=2026-06-21")
    events = json.loads(r.data)
    high = sum(1 for e in events if e.get("priority") == "high")
    return f"total={len(events)}, high_priority={high}"


def solve_013(client, base="/sites/calendar-todo"):
    r = client.post(f"{base}/api/events",
                    json={
                        "title": "Team Lunch",
                        "category": "personal",
                        "calendar": "Personal",
                        "start": "2026-06-23T12:00:00",
                        "end": "2026-06-23T13:00:00",
                        "location": "Cafe Downtown",
                        "priority": "medium",
                        "user_id": 1
                    },
                    content_type="application/json")
    data = json.loads(r.data)
    return f"Created event id={data.get('id')}"


def solve_014(client, base="/sites/calendar-todo"):
    r = client.post(f"{base}/api/events",
                    json={
                        "title": "Budget Review",
                        "category": "work",
                        "calendar": "Work",
                        "start": "2026-06-30T10:00:00",
                        "end": "2026-06-30T11:00:00",
                        "priority": "high",
                        "user_id": 5
                    },
                    content_type="application/json")
    data = json.loads(r.data)
    return str(data.get("id", ""))


def solve_015(client, base="/sites/calendar-todo"):
    r = client.post(f"{base}/api/events/4/toggle")
    data = json.loads(r.data)
    return data.get("action", "")


def solve_016(client, base="/sites/calendar-todo"):
    # Login
    client.post(f"{base}/api/login",
                json={"username": "alice_manager", "password": "pass123"},
                content_type="application/json")
    # Create event
    client.post(f"{base}/api/events",
                json={
                    "title": "Quarterly Planning",
                    "category": "work",
                    "calendar": "Work",
                    "start": "2026-07-01T09:00:00",
                    "end": "2026-07-01T12:00:00",
                    "priority": "high",
                    "user_id": 1
                },
                content_type="application/json")
    # Verify
    r = client.get(f"{base}/api/events/search?q=Quarterly+Planning")
    results = json.loads(r.data)
    return f"Found: {len(results) > 0}"


def solve_017(client, base="/sites/calendar-todo"):
    # Create event
    client.post(f"{base}/api/events",
                json={
                    "title": "Sprint Demo",
                    "category": "work",
                    "calendar": "Work",
                    "start": "2026-06-27T14:00:00",
                    "end": "2026-06-27T15:00:00",
                    "priority": "medium",
                    "user_id": 2
                },
                content_type="application/json")
    # Verify in date range
    r = client.get(f"{base}/api/events?date_from=2026-06-27&date_to=2026-06-27")
    events = json.loads(r.data)
    found = any(e["title"] == "Sprint Demo" for e in events)
    return f"Sprint Demo on 2026-06-27: {found}, total: {len(events)}"


def solve_018(client, base="/sites/calendar-todo"):
    r = client.put(f"{base}/api/events/3",
                   json={"location": "Uptown Dental Office", "priority": "high"},
                   content_type="application/json")
    data = json.loads(r.data)
    return f"location={data.get('location')}, priority={data.get('priority')}"


def solve_019(client, base="/sites/calendar-todo"):
    r = client.delete(f"{base}/api/events/37")
    data = json.loads(r.data)
    return str(data.get("remaining", ""))


def solve_020(client, base="/sites/calendar-todo"):
    # Export CSV
    r = client.get(f"{base}/api/export?format=csv&category=work")
    lines = r.data.decode().strip().split("\n")
    csv_rows = len(lines) - 1

    # Share event 1 to user 3
    client.post(f"{base}/api/events/1/share",
                json={"target_user_id": 3},
                content_type="application/json")

    # Invite to event 5
    client.post(f"{base}/api/events/5/invite",
                json={"email": "new.person@example.com"},
                content_type="application/json")

    return f"CSV rows: {csv_rows}"
