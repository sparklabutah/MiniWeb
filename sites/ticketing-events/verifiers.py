"""Per-task HTTP verification functions for ticketing-events."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/ticketing-events"
    r = requests.get(f"{base}/api/events?category=Music")
    data = r.json()
    count = data.get("total", len(data.get("events", [])))
    return {"pass": count > 0, "detail": f"Music category: {count} events"}


def verify_002(server_url):
    base = f"{server_url}/sites/ticketing-events"
    r = requests.get(f"{base}/api/events/15")
    event = r.json()
    venue = event.get("venue", "")
    return {"pass": len(venue) > 0, "detail": f"Event 15 venue: {venue}"}


def verify_003(server_url):
    base = f"{server_url}/sites/ticketing-events"
    r = requests.get(f"{base}/api/events?q=concert")
    data = r.json()
    count = data.get("total", len(data.get("events", [])))
    return {"pass": count > 0, "detail": f"Search 'concert': {count} results"}


def verify_004(server_url):
    base = f"{server_url}/sites/ticketing-events"
    r = requests.get(f"{base}/api/events/semantic?q=outdoor+family+activities")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Semantic 'outdoor family activities': {count} results"}


def verify_005(server_url):
    base = f"{server_url}/sites/ticketing-events"
    r = requests.get(f"{base}/api/events?q=brewing")
    data = r.json()
    count = data.get("total", len(data.get("events", [])))
    return {"pass": count >= 0, "detail": f"Filter 'brewing': {count} events"}


def verify_006(server_url):
    base = f"{server_url}/sites/ticketing-events"
    r = requests.get(f"{base}/api/events?tag=outdoor")
    data = r.json()
    count = data.get("total", len(data.get("events", [])))
    events = data.get("events", [])
    ok = all("outdoor" in [t.lower() for t in e.get("tags", [])] for e in events)
    return {"pass": ok and count > 0, "detail": f"Tag 'outdoor': {count} events, all_match={ok}"}


def verify_007(server_url):
    base = f"{server_url}/sites/ticketing-events"
    r = requests.get(f"{base}/api/events/by-price-range?price_min=10&price_max=30")
    events = r.json()
    count = len(events)
    return {"pass": count >= 0, "detail": f"Price $10-$30: {count} events"}


def verify_008(server_url):
    base = f"{server_url}/sites/ticketing-events"
    r = requests.get(f"{base}/api/events?date_from=2026-06-01&date_to=2026-12-31")
    data = r.json()
    count = data.get("total", len(data.get("events", [])))
    events = data.get("events", [])
    ok = all("2026-06-01" <= e["date"] <= "2026-12-31" for e in events)
    return {"pass": ok, "detail": f"Date 2026-06-2026-12: {count} events, all_in_range={ok}"}


def verify_009(server_url):
    base = f"{server_url}/sites/ticketing-events"
    r = requests.get(f"{base}/api/events?sort=price")
    data = r.json()
    events = data.get("events", [])
    if not events:
        return {"pass": False, "detail": "No events returned"}
    first = events[0]["name"]
    return {"pass": True, "detail": f"First by price: {first}"}


def verify_010(server_url):
    base = f"{server_url}/sites/ticketing-events"
    r = requests.get(f"{base}/api/events?q=festival")
    data = r.json()
    events = data.get("events", [])
    if not events:
        return {"pass": False, "detail": "No results for 'festival'"}
    first = events[0]
    return {"pass": True, "detail": f"First 'festival': {first['name']} on {first['date']}"}


def verify_011(server_url):
    base = f"{server_url}/sites/ticketing-events"
    r = requests.get(f"{base}/api/compare?ids=15,18,19")
    events = r.json()
    if len(events) != 3:
        return {"pass": False, "detail": f"Compare returned {len(events)}, expected 3"}
    cats = [e["category"] for e in events]
    return {"pass": True, "detail": f"Categories: {cats}"}


def verify_012(server_url):
    base = f"{server_url}/sites/ticketing-events"
    r = requests.get(f"{base}/api/events/by-price-range?price_min=20&price_max=60")
    events = r.json()
    count = len(events)
    return {"pass": count >= 0, "detail": f"Price $20-$60: {count} events"}


def verify_013(server_url):
    base = f"{server_url}/sites/ticketing-events"
    r = requests.get(f"{base}/api/events/by-date-range?date_from=2026-08-01&date_to=2026-11-30")
    events = r.json()
    count = len(events)
    ok = all("2026-08-01" <= e["date"] <= "2026-11-30" for e in events)
    return {"pass": ok, "detail": f"Date 2026-08 to 2026-11: {count} events, all_in_range={ok}"}


def verify_014(server_url):
    base = f"{server_url}/sites/ticketing-events"
    r = requests.get(f"{base}/api/export?format=csv&category=Festival")
    lines = r.text.strip().split("\n")
    data_rows = len(lines) - 1
    return {"pass": data_rows > 0, "detail": f"CSV export Festival: {data_rows} rows"}


def verify_015(server_url):
    base = f"{server_url}/sites/ticketing-events"
    r = requests.get(f"{base}/api/wishlist?user_id=1")
    wishlist = r.json()
    has_event = any(w.get("event_id") == 15 for w in wishlist)
    return {"pass": has_event,
            "detail": f"User 1 wishlist has event 15: {has_event}, total={len(wishlist)}"}


def verify_016(server_url):
    base = f"{server_url}/sites/ticketing-events"
    r = requests.get(f"{base}/api/orders?user_id=2&event_id=18")
    orders = r.json()
    confirmed = [o for o in orders if o["status"] == "confirmed"]
    return {"pass": len(confirmed) > 0,
            "detail": f"User 2 confirmed orders for event 18: {len(confirmed)}"}


def verify_017(server_url):
    base = f"{server_url}/sites/ticketing-events"
    r = requests.get(f"{base}/api/cart?user_id=3")
    cart = r.json()
    has_item = any(c.get("event_id") == 15 for c in cart)
    return {"pass": has_item,
            "detail": f"User 3 cart has event 15: {has_item}, total={len(cart)}"}


def verify_018(server_url):
    base = f"{server_url}/sites/ticketing-events"
    r = requests.post(f"{base}/api/promo/validate", json={"code": "SUMMER10"})
    data = r.json()
    valid = data.get("valid", False)
    pct = data.get("discount_pct", 0)
    return {"pass": valid and pct == 10,
            "detail": f"Promo SUMMER10: valid={valid}, discount={pct}%"}


def verify_019(server_url):
    base = f"{server_url}/sites/ticketing-events"
    r = requests.get(f"{base}/api/users/1")
    user = r.json()
    prefs = user.get("notification_preferences", {})
    sms_off = prefs.get("sms") is False
    price_alert = user.get("max_price_alert", 0)
    return {"pass": sms_off and price_alert == 50,
            "detail": f"User 1 sms={prefs.get('sms')}, max_price_alert={price_alert}"}


def verify_020(server_url):
    base = f"{server_url}/sites/ticketing-events"
    r = requests.get(f"{base}/api/users")
    users = r.json()
    new_user = next((u for u in users if u["username"] == "test_user_new"), None)
    return {"pass": new_user is not None,
            "detail": f"User 'test_user_new' exists: {new_user is not None}"}
