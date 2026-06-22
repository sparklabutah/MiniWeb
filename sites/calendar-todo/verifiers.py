"""Per-task HTTP verification functions for calendar-todo."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/calendar-todo"
    r = requests.get(f"{base}/api/events/search?q=sprint")
    results = r.json()
    event = next((e for e in results if "Sprint Planning" in e["title"]), None)
    if not event:
        return {"pass": False, "detail": "Sprint Planning Meeting not found"}
    return {"pass": True, "detail": f"Location: {event['location']}"}


def verify_002(server_url):
    base = f"{server_url}/sites/calendar-todo"
    r = requests.get(f"{base}/api/events/4")
    event = r.json()
    title = event.get("title", "")
    return {"pass": title == "Team Standup", "detail": f"Event 4 title: {title}"}


def verify_003(server_url):
    base = f"{server_url}/sites/calendar-todo"
    r = requests.get(f"{base}/api/events?category=health")
    events = r.json()
    count = len(events)
    return {"pass": count > 0, "detail": f"Health events: {count}"}


def verify_004(server_url):
    base = f"{server_url}/sites/calendar-todo"
    r = requests.get(f"{base}/api/events/date/2026-06-22")
    events = r.json()
    count = len(events)
    return {"pass": count > 0, "detail": f"Events on 2026-06-22: {count}"}


def verify_005(server_url):
    base = f"{server_url}/sites/calendar-todo"
    r = requests.get(f"{base}/api/events/semantic?q=fitness+exercise+workout")
    results = r.json()
    if not results:
        return {"pass": False, "detail": "No semantic results for fitness"}
    return {"pass": True, "detail": f"Top result: {results[0]['title']}"}


def verify_006(server_url):
    base = f"{server_url}/sites/calendar-todo"
    r = requests.get(f"{base}/api/events?sort=title")
    events = r.json()
    if not events:
        return {"pass": False, "detail": "No events"}
    titles = [e["title"].lower() for e in events]
    is_sorted = all(titles[i] <= titles[i + 1] for i in range(len(titles) - 1))
    return {"pass": is_sorted, "detail": f"First title (sorted): {events[0]['title']}, sorted={is_sorted}"}


def verify_007(server_url):
    base = f"{server_url}/sites/calendar-todo"
    r = requests.get(f"{base}/api/events?date_from=2026-06-24&date_to=2026-06-26")
    events = r.json()
    count = len(events)
    return {"pass": count > 0, "detail": f"Events 2026-06-24 to 2026-06-26: {count}"}


def verify_008(server_url):
    base = f"{server_url}/sites/calendar-todo"
    r = requests.get(f"{base}/api/events/search?q=meeting")
    results = r.json()
    if not results:
        return {"pass": False, "detail": "No results for 'meeting'"}
    return {"pass": True, "detail": f"First meeting result: {results[0]['title']}"}


def verify_009(server_url):
    base = f"{server_url}/sites/calendar-todo"
    r = requests.get(f"{base}/api/events/semantic?q=career+development+mentoring")
    results = r.json()
    if not results:
        return {"pass": False, "detail": "No semantic results"}
    titles = [e["title"] for e in results]
    return {"pass": True, "detail": f"Semantic results: {titles[:3]}"}


def verify_010(server_url):
    base = f"{server_url}/sites/calendar-todo"
    r = requests.get(f"{base}/api/categories/work/stats")
    stats = r.json()
    count = stats.get("count", 0)
    users = stats.get("unique_users", 0)
    return {"pass": count > 0 and users > 0,
            "detail": f"Work events: {count}, unique users: {users}"}


def verify_011(server_url):
    base = f"{server_url}/sites/calendar-todo"
    r = requests.get(f"{base}/api/events/9")
    event = r.json()
    desc = event.get("description", "")
    return {"pass": len(desc) > 0, "detail": f"Event 9 description: {desc[:80]}"}


def verify_012(server_url):
    base = f"{server_url}/sites/calendar-todo"
    r = requests.get(f"{base}/api/events?date_from=2026-06-21&date_to=2026-06-21")
    events = r.json()
    count = len(events)
    high_count = sum(1 for e in events if e.get("priority") == "high")
    return {"pass": count > 0, "detail": f"Today's events: {count}, high priority: {high_count}"}


def verify_013(server_url):
    base = f"{server_url}/sites/calendar-todo"
    r = requests.get(f"{base}/api/events/search?q=Team+Lunch")
    results = r.json()
    found = any(e["title"] == "Team Lunch" for e in results)
    return {"pass": found, "detail": f"Team Lunch created: {found}"}


def verify_014(server_url):
    base = f"{server_url}/sites/calendar-todo"
    r = requests.get(f"{base}/api/events/search?q=Budget+Review")
    results = r.json()
    found = next((e for e in results if e["title"] == "Budget Review"), None)
    if not found:
        return {"pass": False, "detail": "Budget Review not found"}
    return {"pass": found["priority"] == "high" and found["category"] == "work",
            "detail": f"Budget Review id={found['id']}, priority={found['priority']}"}


def verify_015(server_url):
    base = f"{server_url}/sites/calendar-todo"
    r = requests.get(f"{base}/api/events/4")
    event = r.json()
    status = event.get("status", "")
    return {"pass": status == "cancelled", "detail": f"Event 4 status: {status}"}


def verify_016(server_url):
    base = f"{server_url}/sites/calendar-todo"
    r = requests.get(f"{base}/api/events/search?q=Quarterly+Planning")
    results = r.json()
    found = any(e["title"] == "Quarterly Planning" for e in results)
    return {"pass": found, "detail": f"Quarterly Planning exists: {found}"}


def verify_017(server_url):
    base = f"{server_url}/sites/calendar-todo"
    r = requests.get(f"{base}/api/events?date_from=2026-06-27&date_to=2026-06-27")
    events = r.json()
    found = any(e["title"] == "Sprint Demo" for e in events)
    return {"pass": found, "detail": f"Sprint Demo on 2026-06-27: {found}, total events that day: {len(events)}"}


def verify_018(server_url):
    base = f"{server_url}/sites/calendar-todo"
    r = requests.get(f"{base}/api/events/3")
    event = r.json()
    loc = event.get("location", "")
    pri = event.get("priority", "")
    ok = loc == "Uptown Dental Office" and pri == "high"
    return {"pass": ok, "detail": f"Event 3 location={loc}, priority={pri}"}


def verify_019(server_url):
    base = f"{server_url}/sites/calendar-todo"
    r = requests.get(f"{base}/api/events")
    events = r.json()
    found = any(e["id"] == 37 for e in events)
    count = len(events)
    return {"pass": not found, "detail": f"Event 37 exists: {found}, total events: {count}"}


def verify_020(server_url):
    base = f"{server_url}/sites/calendar-todo"
    # Check CSV export for work events
    r = requests.get(f"{base}/api/export?format=csv&category=work")
    lines = r.text.strip().split("\n")
    csv_rows = len(lines) - 1

    # Check share
    r2 = requests.get(f"{base}/api/users/3")
    user3 = r2.json()
    shared = user3.get("shared_calendars", [])
    share_ok = any(s.get("event_id") == 1 for s in shared)

    # Check invite
    r3 = requests.get(f"{base}/api/events/5")
    event5 = r3.json()
    invite_ok = "new.person@example.com" in event5.get("attendees", [])

    ok = csv_rows > 0 and share_ok and invite_ok
    return {"pass": ok,
            "detail": f"CSV rows: {csv_rows}, shared event 1 to user 3: {share_ok}, invited to event 5: {invite_ok}"}
