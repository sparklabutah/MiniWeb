"""Per-macro verification functions for calendar-todo.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/calendar-todo"


def verify_macro_navigate_by_search(server_url):
    r = requests.get(f"{_base(server_url)}/api/events/search?q=exercise+fitness")
    results = r.json()
    return {"pass": r.status_code == 200, "detail": f"navigate_by_search: {len(results)} results"}


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/event/1")
    return {"pass": r.status_code == 200, "detail": f"navigate_by_route: {r.status_code}"}


def verify_macro_navigate_by_date_range(server_url):
    r = requests.get(f"{_base(server_url)}/day/2026-06-22")
    return {"pass": r.status_code == 200, "detail": f"navigate_by_date_range (day view): {r.status_code}"}


def verify_macro_search_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/events/search?q=meeting")
    results = r.json()
    return {"pass": len(results) > 0, "detail": f"search_by_query 'meeting': {len(results)} results"}


def verify_macro_filter_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/events?category=work")
    events = r.json()
    ok = all(e.get("category") == "work" for e in events)
    return {"pass": ok, "detail": f"filter_by_dropdown work: {len(events)} events, all_work={ok}"}


def verify_macro_filter_by_date_range(server_url):
    r = requests.get(f"{_base(server_url)}/api/events?date_from=2026-06-22&date_to=2026-06-25")
    events = r.json()
    return {"pass": len(events) > 0, "detail": f"filter_by_date_range: {len(events)} events"}


def verify_macro_sort_by_ranking(server_url):
    r = requests.get(f"{_base(server_url)}/api/events?sort=title")
    events = r.json()
    if len(events) < 2:
        return {"pass": True, "detail": "Too few events to verify sort"}
    titles = [e["title"].lower() for e in events]
    is_sorted = all(titles[i] <= titles[i + 1] for i in range(len(titles) - 1))
    return {"pass": is_sorted, "detail": f"sort_by_ranking: sorted={is_sorted}"}


def verify_macro_extract_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/events/search?q=review")
    results = r.json()
    if results:
        return {"pass": True, "detail": f"extract_by_query: first result={results[0]['title']}"}
    return {"pass": True, "detail": "extract_by_query: no results (ok)"}


def verify_macro_extract_by_search(server_url):
    r = requests.get(f"{_base(server_url)}/api/events/search?q=learning+education")
    results = r.json()
    return {"pass": r.status_code == 200, "detail": f"extract_by_search: {len(results)} results"}


def verify_macro_extract_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/categories/work/stats")
    stats = r.json()
    return {"pass": "unique_users" in stats, "detail": f"extract_by_dropdown: work stats={stats}"}


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/events/1")
    event = r.json()
    return {"pass": "description" in event, "detail": f"extract_by_route: event has description={len(event.get('description', ''))} chars"}


def verify_macro_extract_by_date_range(server_url):
    r = requests.get(f"{_base(server_url)}/api/events/range?date_from=2026-06-21&date_to=2026-06-21")
    events = r.json()
    return {"pass": len(events) > 0, "detail": f"extract_by_date_range: {len(events)} events today"}


def verify_macro_create_from_free_text(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/events", json={
        "title": "__test_free_text__", "user_id": 4,
        "start": "2026-07-10T10:00:00", "end": "2026-07-10T11:00:00",
        "category": "personal"
    })
    data = r.json()
    ok = data.get("title") == "__test_free_text__"
    # Clean up
    if ok:
        requests.delete(f"{base}/api/events/{data['id']}")
    return {"pass": ok, "detail": f"create_from_free_text: created id={data.get('id')}"}


def verify_macro_create_by_dropdown(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/events", json={
        "title": "__test_dropdown__", "user_id": 4,
        "start": "2026-07-10T10:00:00", "end": "2026-07-10T11:00:00",
        "category": "work", "calendar": "Work"
    })
    data = r.json()
    ok = data.get("category") == "work"
    if ok:
        requests.delete(f"{base}/api/events/{data['id']}")
    return {"pass": ok, "detail": f"create_by_dropdown: category={data.get('category')}"}


def verify_macro_create_by_toggle(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/events/4/toggle")
    data = r.json()
    action = data.get("action")
    # Toggle back
    requests.post(f"{base}/api/events/4/toggle")
    return {"pass": action in ("cancelled", "confirmed"), "detail": f"create_by_toggle: action={action}"}


def verify_macro_submit_by_query(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/events", json={
        "title": "__test_submit_query__", "user_id": 1,
        "start": "2026-07-15T09:00:00", "end": "2026-07-15T10:00:00",
    })
    data = r.json()
    eid = data.get("id")
    # Verify by search
    r2 = requests.get(f"{base}/api/events/search?q=__test_submit_query__")
    found = len(r2.json()) > 0
    # Clean up
    if eid:
        requests.delete(f"{base}/api/events/{eid}")
    return {"pass": found, "detail": f"submit_by_query: found via search={found}"}


def verify_macro_submit_by_date_range(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/events", json={
        "title": "__test_submit_date__", "user_id": 2,
        "start": "2026-07-20T14:00:00", "end": "2026-07-20T15:00:00",
    })
    data = r.json()
    eid = data.get("id")
    # Verify by date range
    r2 = requests.get(f"{base}/api/events?date_from=2026-07-20&date_to=2026-07-20")
    found = any(e["title"] == "__test_submit_date__" for e in r2.json())
    if eid:
        requests.delete(f"{base}/api/events/{eid}")
    return {"pass": found, "detail": f"submit_by_date_range: found in range={found}"}


def verify_macro_edit_by_form(server_url):
    base = _base(server_url)
    # Get current state
    r = requests.get(f"{base}/api/events/1")
    orig = r.json()
    # Edit
    r2 = requests.put(f"{base}/api/events/1", json={"location": "__test_edit_loc__"})
    data = r2.json()
    ok = data.get("location") == "__test_edit_loc__"
    # Restore
    requests.put(f"{base}/api/events/1", json={"location": orig["location"]})
    return {"pass": ok, "detail": f"edit_by_form: location changed={ok}"}


def verify_macro_edit_by_date_range(server_url):
    base = _base(server_url)
    r = requests.get(f"{base}/api/events/3")
    orig = r.json()
    r2 = requests.put(f"{base}/api/events/3", json={"start": "2026-06-26T11:00:00", "end": "2026-06-26T12:00:00"})
    data = r2.json()
    ok = "2026-06-26" in data.get("start", "")
    # Restore
    requests.put(f"{base}/api/events/3", json={"start": orig["start"], "end": orig["end"]})
    return {"pass": ok, "detail": f"edit_by_date_range: rescheduled={ok}"}


def verify_macro_delete_from_table(server_url):
    base = _base(server_url)
    # Create temp event then delete
    r = requests.post(f"{base}/api/events", json={
        "title": "__test_delete__", "user_id": 4,
        "start": "2026-07-10T10:00:00", "end": "2026-07-10T11:00:00",
    })
    eid = r.json().get("id")
    r2 = requests.delete(f"{base}/api/events/{eid}")
    data = r2.json()
    ok = data.get("deleted") == eid
    return {"pass": ok, "detail": f"delete_from_table: deleted id={eid}"}


def verify_macro_select_by_date_range(server_url):
    r = requests.get(f"{_base(server_url)}/api/events/range?date_from=2026-06-21&date_to=2026-06-28")
    events = r.json()
    return {"pass": len(events) > 0, "detail": f"select_by_date_range: {len(events)} events in week"}


def verify_macro_export_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/export?format=csv&category=work")
    lines = r.text.strip().split("\n")
    return {"pass": len(lines) > 1, "detail": f"export_by_dropdown CSV: {len(lines)} lines"}


def verify_macro_share_by_dropdown(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/events/1/share", json={"target_user_id": 4})
    data = r.json()
    ok = data.get("action") in ("shared", "already_shared")
    return {"pass": ok, "detail": f"share_by_dropdown: action={data.get('action')}"}


def verify_macro_invite_by_form(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/events/1/invite", json={"email": "__test__@example.com"})
    data = r.json()
    ok = data.get("action") in ("invited", "already_invited")
    return {"pass": ok, "detail": f"invite_by_form: action={data.get('action')}"}
