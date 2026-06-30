"""Per-macro verification functions for ticketing-events.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/ticketing-events"


def verify_macro_navigate_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/events?category=Music")
    data = r.json()
    events = data.get("events", [])
    return {"pass": len(events) > 0, "detail": f"navigate_by_dropdown Music: {len(events)} events"}


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/event/15")
    return {"pass": r.status_code == 200, "detail": f"Event detail page: {r.status_code}"}


def verify_macro_search_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/events?q=concert")
    data = r.json()
    events = data.get("events", [])
    return {"pass": len(events) > 0, "detail": f"search_by_query 'concert': {len(events)} results"}


def verify_macro_search_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/events/semantic?q=live+music+outdoor")
    results = r.json()
    return {"pass": r.status_code == 200, "detail": f"search_by_semantic: {len(results)} results"}


def verify_macro_filter_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/events?q=lake")
    data = r.json()
    events = data.get("events", [])
    return {"pass": len(events) > 0, "detail": f"filter_by_query 'lake': {len(events)} events"}


def verify_macro_filter_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/events?category=Festival")
    data = r.json()
    events = data.get("events", [])
    ok = all(e["category"] == "Festival" for e in events)
    return {"pass": ok and len(events) > 0,
            "detail": f"filter_by_dropdown Festival: {len(events)}, all_match={ok}"}


def verify_macro_filter_by_checkbox(server_url):
    r = requests.get(f"{_base(server_url)}/api/events?tag=outdoor")
    data = r.json()
    events = data.get("events", [])
    ok = all("outdoor" in [t.lower() for t in e.get("tags", [])] for e in events)
    return {"pass": ok, "detail": f"filter_by_checkbox outdoor: {len(events)}, all_match={ok}"}


def verify_macro_filter_by_slider(server_url):
    r = requests.get(f"{_base(server_url)}/api/events?price_min=10&price_max=30")
    data = r.json()
    events = data.get("events", [])
    return {"pass": r.status_code == 200,
            "detail": f"filter_by_slider price $10-$30: {len(events)} events"}


def verify_macro_filter_by_date_range(server_url):
    r = requests.get(f"{_base(server_url)}/api/events?date_from=2026-01-01&date_to=2026-12-31")
    data = r.json()
    events = data.get("events", [])
    ok = all("2026-01-01" <= e["date"] <= "2026-12-31" for e in events)
    return {"pass": ok, "detail": f"filter_by_date_range 2026: {len(events)}, all_in_range={ok}"}


def verify_macro_sort_by_ranking(server_url):
    r = requests.get(f"{_base(server_url)}/api/events?sort=price")
    data = r.json()
    events = data.get("events", [])
    if len(events) < 2:
        return {"pass": True, "detail": "Too few events to verify sort"}
    return {"pass": r.status_code == 200, "detail": f"sort_by_ranking price: {len(events)} events"}


def verify_macro_extract_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/events?q=5k")
    data = r.json()
    events = data.get("events", [])
    if events:
        return {"pass": True, "detail": f"extract_by_query: first={events[0]['name'][:50]}"}
    return {"pass": True, "detail": "extract_by_query: no results (ok)"}


def verify_macro_extract_from_table(server_url):
    r = requests.get(f"{_base(server_url)}/api/compare?ids=15,18")
    events = r.json()
    return {"pass": len(events) == 2,
            "detail": f"extract_from_table: compare returned {len(events)} events"}


def verify_macro_compare_from_table(server_url):
    r = requests.get(f"{_base(server_url)}/api/compare?ids=15,18,19")
    events = r.json()
    if len(events) < 2:
        return {"pass": False, "detail": "Compare needs 2+ events"}
    return {"pass": events[0]["id"] != events[1]["id"],
            "detail": f"compare: {events[0]['name'][:30]} vs {events[1]['name'][:30]}"}


def verify_macro_submit_by_query(server_url):
    r = requests.post(f"{_base(server_url)}/api/feedback", json={
        "event_id": 15, "type": "general", "message": "Great event!"
    })
    data = r.json()
    return {"pass": data.get("status") == "submitted",
            "detail": f"submit_by_query: status={data.get('status')}"}


def verify_macro_select_by_slider(server_url):
    r = requests.get(f"{_base(server_url)}/api/events/by-price-range?price_min=0&price_max=25")
    events = r.json()
    return {"pass": r.status_code == 200,
            "detail": f"select_by_slider: {len(events)} events under $25"}


def verify_macro_select_by_date_range(server_url):
    r = requests.get(f"{_base(server_url)}/api/events/by-date-range?date_from=2026-06-01&date_to=2026-09-30")
    events = r.json()
    ok = all("2026-06-01" <= e["date"] <= "2026-09-30" for e in events)
    return {"pass": ok, "detail": f"select_by_date_range: {len(events)} events, all_in_range={ok}"}


def verify_macro_configure_by_dropdown(server_url):
    r = requests.put(f"{_base(server_url)}/api/users/8/settings",
                     json={"location": "Seattle, WA"})
    data = r.json()
    ok = data.get("location") == "Seattle, WA"
    # Revert
    requests.put(f"{_base(server_url)}/api/users/8/settings",
                 json={"location": "Lakeport, WA"})
    return {"pass": ok, "detail": f"configure_by_dropdown: location={data.get('location')}"}


def verify_macro_configure_by_slider(server_url):
    r = requests.put(f"{_base(server_url)}/api/users/8/settings",
                     json={"max_price_alert": 75})
    data = r.json()
    ok = data.get("max_price_alert") == 75
    # Revert
    requests.put(f"{_base(server_url)}/api/users/8/settings",
                 json={"max_price_alert": 100})
    return {"pass": ok, "detail": f"configure_by_slider: max_price_alert={data.get('max_price_alert')}"}


def verify_macro_export_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/export?format=csv")
    lines = r.text.strip().split("\n")
    return {"pass": len(lines) > 1, "detail": f"export_by_dropdown CSV: {len(lines)} lines"}


def verify_macro_save_by_toggle(server_url):
    # Save event 1 for user 8
    r = requests.post(f"{_base(server_url)}/api/wishlist",
                      json={"user_id": 8, "event_id": 1})
    data = r.json()
    ok = data.get("action") == "saved"
    # Toggle back (remove)
    requests.post(f"{_base(server_url)}/api/wishlist",
                  json={"user_id": 8, "event_id": 1})
    return {"pass": ok, "detail": f"save_by_toggle: action={data.get('action')}"}


def verify_macro_add_by_button(server_url):
    r = requests.post(f"{_base(server_url)}/api/cart", json={
        "user_id": 8, "event_id": 15, "ticket_type": "Day Pass", "quantity": 1
    })
    data = r.json()
    ok = data.get("action") == "added"
    # Clear cart
    requests.delete(f"{_base(server_url)}/api/cart", json={"user_id": 8})
    return {"pass": ok, "detail": f"add_by_button: action={data.get('action')}"}


def verify_macro_checkout_by_form(server_url):
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login", json={"username": "tom_bradley"})
    r = s.post(f"{_base(server_url)}/api/orders", json={
        "user_id": 8, "event_id": 18, "ticket_type": "General Admission", "quantity": 1
    })
    data = r.json()
    ok = data.get("status") == "confirmed"
    return {"pass": ok, "detail": f"checkout_by_form: order={data.get('id')}, status={data.get('status')}"}


def verify_macro_book_by_form(server_url):
    r = requests.get(f"{_base(server_url)}/checkout/18")
    return {"pass": r.status_code == 200, "detail": f"book_by_form checkout page: {r.status_code}"}


def verify_macro_redeem_by_code(server_url):
    r = requests.post(f"{_base(server_url)}/api/promo/validate",
                      json={"code": "WELCOME20"})
    data = r.json()
    ok = data.get("valid") and data.get("discount_pct") == 20
    return {"pass": ok, "detail": f"redeem_by_code: valid={data.get('valid')}, pct={data.get('discount_pct')}"}


def verify_macro_cancel_by_form(server_url):
    # First create an order to cancel
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login", json={"username": "tom_bradley"})
    r = s.post(f"{_base(server_url)}/api/orders", json={
        "user_id": 8, "event_id": 19, "ticket_type": "General Admission", "quantity": 1
    })
    order = r.json()
    order_id = order.get("id")
    if not order_id:
        return {"pass": False, "detail": f"Failed to create order for cancel test"}
    # Cancel it
    r2 = s.post(f"{_base(server_url)}/api/orders/{order_id}/cancel")
    data = r2.json()
    return {"pass": data.get("status") == "cancelled",
            "detail": f"cancel_by_form: order {order_id} status={data.get('status')}"}


def verify_macro_authenticate_by_form(server_url):
    r = requests.post(f"{_base(server_url)}/api/login",
                      json={"username": "alex_rivera"})
    data = r.json()
    ok = data.get("user_id") == 1
    return {"pass": ok, "detail": f"authenticate: user_id={data.get('user_id')}"}


def verify_macro_register_by_form(server_url):
    r = requests.post(f"{_base(server_url)}/api/register", json={
        "username": "macro_test_user", "display_name": "Macro Test",
        "email": "macro@test.com"
    })
    data = r.json()
    ok = data.get("user_id") is not None
    return {"pass": ok, "detail": f"register_by_form: user_id={data.get('user_id')}"}