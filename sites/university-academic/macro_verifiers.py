"""Per-macro verification functions for university-academic.

Each function tests that the corresponding macro works end-to-end.
One verifier per target macro (18 macros).
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/university-academic"


def verify_macro_navigate_by_semantic(server_url):
    """Homepage links to research areas; clicking one leads to detail page."""
    # Homepage loads
    r = requests.get(f"{_base(server_url)}/")
    if r.status_code != 200:
        return {"pass": False, "detail": f"Homepage: {r.status_code}"}
    # Research area detail pages work
    r2 = requests.get(f"{_base(server_url)}/department/ra-ml")
    return {"pass": r2.status_code == 200,
            "detail": f"ML research area page: {r2.status_code}"}


def verify_macro_navigate_by_dropdown(server_url):
    """Navigation links lead to section pages."""
    pages = ["/courses", "/faculty", "/departments", "/events", "/alumni"]
    for page in pages:
        r = requests.get(f"{_base(server_url)}{page}")
        if r.status_code != 200:
            return {"pass": False, "detail": f"{page}: {r.status_code}"}
    return {"pass": True, "detail": "All nav pages accessible"}


def verify_macro_navigate_by_route(server_url):
    """Direct URL navigation to detail pages."""
    r = requests.get(f"{_base(server_url)}/course/cse-446")
    ok1 = r.status_code == 200
    r2 = requests.get(f"{_base(server_url)}/faculty/fac-001")
    ok2 = r2.status_code == 200
    r3 = requests.get(f"{_base(server_url)}/event/evt-001")
    ok3 = r3.status_code == 200
    return {"pass": ok1 and ok2 and ok3,
            "detail": f"course={ok1}, faculty={ok2}, event={ok3}"}


def verify_macro_search_by_query(server_url):
    """Search courses by keyword query."""
    r = requests.get(f"{_base(server_url)}/api/courses?q=data")
    courses = r.json()
    ok = len(courses) == 2
    return {"pass": ok, "detail": f"search 'data': {len(courses)} courses"}


def verify_macro_search_by_semantic(server_url):
    """Semantic search across faculty."""
    r = requests.get(f"{_base(server_url)}/api/faculty/search?q=machine+learning+deep")
    results = r.json()
    ok = r.status_code == 200 and len(results) > 0
    return {"pass": ok,
            "detail": f"semantic search: {len(results)} results"}


def verify_macro_search_by_route(server_url):
    """Search via URL path segment."""
    r = requests.get(f"{_base(server_url)}/api/courses/search/programming")
    courses = r.json()
    ok = len(courses) == 2
    return {"pass": ok,
            "detail": f"search by route 'programming': {len(courses)} courses"}


def verify_macro_filter_by_dropdown(server_url):
    """Filter using dropdown selections."""
    r = requests.get(f"{_base(server_url)}/api/courses?level=advanced")
    courses = r.json()
    ok = all(c["level"] == "advanced" for c in courses) and len(courses) == 6
    return {"pass": ok,
            "detail": f"filter advanced: {len(courses)} courses, all_correct={ok}"}


def verify_macro_filter_by_route(server_url):
    """Filter via URL path."""
    r = requests.get(f"{_base(server_url)}/api/courses/level/intermediate")
    courses = r.json()
    ok = all(c["level"] == "intermediate" for c in courses) and len(courses) == 3
    return {"pass": ok,
            "detail": f"filter by route intermediate: {len(courses)} courses"}


def verify_macro_extract_by_query(server_url):
    """Extract data using search query."""
    r = requests.get(f"{_base(server_url)}/api/faculty?area=machine+learning")
    faculty = r.json()
    ok = len(faculty) == 2
    names = [f["name"] for f in faculty]
    return {"pass": ok,
            "detail": f"ML faculty: {names}"}


def verify_macro_extract_by_checkbox(server_url):
    """Multi-select checkbox filtering."""
    r = requests.get(f"{_base(server_url)}/api/courses?levels=introductory&levels=advanced")
    courses = r.json()
    ok = len(courses) == 7
    levels = set(c["level"] for c in courses)
    return {"pass": ok and levels <= {"introductory", "advanced"},
            "detail": f"checkbox filter: {len(courses)} courses, levels={levels}"}


def verify_macro_extract_from_table(server_url):
    """Extract data from comparison table."""
    r = requests.get(f"{_base(server_url)}/api/compare?ids=cse-446,cse-473")
    courses = r.json()
    ok = len(courses) == 2
    return {"pass": ok,
            "detail": f"compare table returned {len(courses)} courses"}


def verify_macro_extract_by_route(server_url):
    """Extract data from detail page via route."""
    r = requests.get(f"{_base(server_url)}/api/courses/cse-484")
    course = r.json()
    ok = "description" in course and "instructor" in course
    return {"pass": ok,
            "detail": f"course detail has description={len(course.get('description',''))} chars"}


def verify_macro_extract_by_date_range(server_url):
    """Filter events by date range."""
    r = requests.get(f"{_base(server_url)}/api/events?date=2025-10-01&date_to=2026-01-31")
    events = r.json()
    ok = len(events) == 3
    all_in_range = all("2025-10-01" <= e["date"] <= "2026-01-31" for e in events)
    return {"pass": ok and all_in_range,
            "detail": f"date range: {len(events)} events, in_range={all_in_range}"}


def verify_macro_compare_from_table(server_url):
    """Compare items side-by-side in a table."""
    r = requests.get(f"{_base(server_url)}/api/compare?ids=cse-452,cse-461")
    courses = r.json()
    if len(courses) < 2:
        return {"pass": False, "detail": f"Compare needs 2 courses, got {len(courses)}"}
    ids = {c["id"] for c in courses}
    ok = "cse-452" in ids and "cse-461" in ids
    return {"pass": ok,
            "detail": f"compare: {ids}"}


def verify_macro_submit_by_query(server_url):
    """Submit a form with text content."""
    r = requests.post(f"{_base(server_url)}/api/submit",
                      json={"subject": "Test", "message": "Test message"})
    data = r.json()
    ok = data.get("status") == "submitted"
    return {"pass": ok, "detail": f"submit status: {data.get('status')}"}


def verify_macro_apply_by_form(server_url):
    """Submit an application form."""
    r = requests.post(f"{_base(server_url)}/api/apply",
                      json={"applicant_name": "Test User",
                            "applicant_email": "test@example.com",
                            "program": "systems",
                            "statement": "Test statement"})
    data = r.json()
    ok = data.get("status") == "submitted"
    return {"pass": ok, "detail": f"apply status: {data.get('status')}"}


def verify_macro_export_by_dropdown(server_url):
    """Export data in different formats."""
    # CSV export
    r = requests.get(f"{_base(server_url)}/api/export?format=csv&type=courses")
    lines = r.text.strip().split("\n")
    csv_ok = len(lines) > 1
    # JSON export
    r2 = requests.get(f"{_base(server_url)}/api/export?format=json&type=faculty")
    json_ok = r2.status_code == 200 and len(r2.json()) > 0
    return {"pass": csv_ok and json_ok,
            "detail": f"CSV: {len(lines)} lines, JSON faculty: {len(r2.json())} records"}


def verify_macro_subscribe_by_toggle(server_url):
    """Toggle subscription on/off."""
    s = requests.Session()
    # Login
    s.post(f"{_base(server_url)}/api/login", json={"net_id": "arivera"})
    # Subscribe
    r = s.post(f"{_base(server_url)}/api/subscribe/hci")
    data = r.json()
    ok1 = data.get("action") == "subscribed"
    # Unsubscribe (toggle back)
    r2 = s.post(f"{_base(server_url)}/api/subscribe/hci")
    data2 = r2.json()
    ok2 = data2.get("action") == "unsubscribed"
    return {"pass": ok1 and ok2,
            "detail": f"subscribe={ok1}, unsubscribe={ok2}"}
