"""Per-task HTTP verification functions for university-academic."""
import requests


def _base(server_url):
    return f"{server_url}/sites/university-academic"


def verify_001(server_url):
    """navigate_by_dropdown: Research areas page has 5 areas."""
    r = requests.get(f"{_base(server_url)}/api/departments")
    data = r.json()
    areas = data.get("research_areas", [])
    count = len(areas)
    return {"pass": count == 5, "detail": f"Research areas: {count}"}


def verify_002(server_url):
    """navigate_by_route: CSE 446 instructor is Dr. Ravi Bansal."""
    r = requests.get(f"{_base(server_url)}/api/courses/cse-446")
    course = r.json()
    instructor = course.get("instructor", "")
    return {"pass": instructor == "Dr. Ravi Bansal",
            "detail": f"CSE 446 instructor: {instructor}"}


def verify_003(server_url):
    """search_by_query: searching 'data' returns 2 courses."""
    r = requests.get(f"{_base(server_url)}/api/courses?q=data")
    courses = r.json()
    count = len(courses)
    return {"pass": count == 2, "detail": f"Search 'data': {count} courses"}


def verify_004(server_url):
    """search_by_semantic: first result for 'distributed systems' is Dr. Helen Park."""
    r = requests.get(f"{_base(server_url)}/api/faculty/search?q=distributed+systems")
    results = r.json()
    if not results:
        return {"pass": False, "detail": "No results for 'distributed systems'"}
    first = results[0]["name"]
    return {"pass": first == "Dr. Helen Park",
            "detail": f"First result: {first}"}


def verify_005(server_url):
    """search_by_route: searching 'programming' returns 2 courses."""
    r = requests.get(f"{_base(server_url)}/api/courses/search/programming")
    courses = r.json()
    count = len(courses)
    return {"pass": count == 2, "detail": f"Search 'programming' by route: {count} courses"}


def verify_006(server_url):
    """filter_by_dropdown: 6 advanced courses."""
    r = requests.get(f"{_base(server_url)}/api/courses?level=advanced")
    courses = r.json()
    count = len(courses)
    return {"pass": count == 6, "detail": f"Advanced courses: {count}"}


def verify_007(server_url):
    """filter_by_route: 3 intermediate courses."""
    r = requests.get(f"{_base(server_url)}/api/courses/level/intermediate")
    courses = r.json()
    count = len(courses)
    return {"pass": count == 3, "detail": f"Intermediate courses: {count}"}


def verify_008(server_url):
    """extract_by_query: 2 faculty in machine learning."""
    r = requests.get(f"{_base(server_url)}/api/faculty?area=machine+learning")
    faculty = r.json()
    count = len(faculty)
    return {"pass": count == 2, "detail": f"ML faculty: {count}"}


def verify_009(server_url):
    """extract_by_checkbox: introductory + advanced = 7 courses."""
    r = requests.get(f"{_base(server_url)}/api/courses?levels=introductory&levels=advanced")
    courses = r.json()
    count = len(courses)
    return {"pass": count == 7, "detail": f"Introductory+advanced: {count} courses"}


def verify_010(server_url):
    """extract_from_table + compare_from_table: CSE 446 max enrollment is 120."""
    r = requests.get(f"{_base(server_url)}/api/compare?ids=cse-446,cse-473")
    courses = r.json()
    if len(courses) < 2:
        return {"pass": False, "detail": f"Compare returned {len(courses)} courses, expected 2"}
    cse446 = next((c for c in courses if c["id"] == "cse-446"), None)
    if not cse446:
        return {"pass": False, "detail": "CSE 446 not found in comparison"}
    enrollment = cse446.get("max_enrollment", 0)
    return {"pass": enrollment == 120,
            "detail": f"CSE 446 max enrollment: {enrollment}"}


def verify_011(server_url):
    """extract_by_route: Dr. David Liu office is Gates Center 455."""
    r = requests.get(f"{_base(server_url)}/api/faculty/fac-004")
    member = r.json()
    office = member.get("office", "")
    return {"pass": office == "Gates Center 455",
            "detail": f"Dr. Liu office: {office}"}


def verify_012(server_url):
    """extract_by_date_range: 3 events between 2025-10-01 and 2026-01-31."""
    r = requests.get(f"{_base(server_url)}/api/events?date=2025-10-01&date_to=2026-01-31")
    events = r.json()
    count = len(events)
    ok = all("2025-10-01" <= e["date"] <= "2026-01-31" for e in events)
    return {"pass": count == 3 and ok,
            "detail": f"Events in range: {count}, all_in_range={ok}"}


def verify_013(server_url):
    """compare_from_table: CSE 461 has higher max enrollment than CSE 452."""
    r = requests.get(f"{_base(server_url)}/api/compare?ids=cse-452,cse-461")
    courses = r.json()
    if len(courses) < 2:
        return {"pass": False, "detail": f"Compare returned {len(courses)} courses"}
    c452 = next((c for c in courses if c["id"] == "cse-452"), None)
    c461 = next((c for c in courses if c["id"] == "cse-461"), None)
    if not c452 or not c461:
        return {"pass": False, "detail": "Missing course in comparison"}
    ok = c461["max_enrollment"] > c452["max_enrollment"]
    return {"pass": ok,
            "detail": f"CSE 452 max={c452['max_enrollment']}, CSE 461 max={c461['max_enrollment']}"}


def verify_014(server_url):
    """submit_by_query: contact form submission works."""
    r = requests.post(f"{_base(server_url)}/api/submit",
                      json={"subject": "Course Availability",
                            "message": "When will CSE 452 be offered next?"})
    data = r.json()
    ok = data.get("status") == "submitted"
    return {"pass": ok, "detail": f"Submit status: {data.get('status')}"}


def verify_015(server_url):
    """apply_by_form: application submission works."""
    r = requests.post(f"{_base(server_url)}/api/apply",
                      json={"applicant_name": "Jane Doe",
                            "applicant_email": "jane@example.com",
                            "program": "machine-learning",
                            "statement": "I am interested in ML."})
    data = r.json()
    ok = data.get("status") == "submitted"
    return {"pass": ok, "detail": f"Apply status: {data.get('status')}"}


def verify_016(server_url):
    """export_by_dropdown: CSV export has 10 data rows."""
    r = requests.get(f"{_base(server_url)}/api/export?format=csv&type=courses")
    lines = r.text.strip().split("\n")
    data_rows = len(lines) - 1  # minus header
    return {"pass": data_rows == 10,
            "detail": f"CSV export: {data_rows} data rows"}


def verify_017(server_url):
    """subscribe_by_toggle: user arivera subscribed to systems."""
    s = requests.Session()
    # Login
    s.post(f"{_base(server_url)}/api/login", json={"net_id": "arivera"})
    # Subscribe
    r = s.post(f"{_base(server_url)}/api/subscribe/systems")
    data = r.json()
    ok = data.get("action") == "subscribed" and "systems" in data.get("subscriptions", [])
    # Clean up: unsubscribe
    s.post(f"{_base(server_url)}/api/subscribe/systems")
    return {"pass": ok,
            "detail": f"Subscribe action: {data.get('action')}, subs: {data.get('subscriptions')}"}


def verify_018(server_url):
    """navigate_by_semantic: ML research area has 18 active projects."""
    r = requests.get(f"{_base(server_url)}/api/departments/machine-learning")
    area = r.json()
    projects = area.get("active_projects", 0)
    return {"pass": projects == 18,
            "detail": f"ML active projects: {projects}"}


def verify_019(server_url):
    """filter_by_dropdown: 3 courses in systems area."""
    r = requests.get(f"{_base(server_url)}/api/courses?dept=systems")
    courses = r.json()
    count = len(courses)
    return {"pass": count == 3, "detail": f"Systems courses: {count}"}


def verify_020(server_url):
    """apply_by_form: user nkim's application is recorded."""
    s = requests.Session()
    # Login as nkim
    s.post(f"{_base(server_url)}/api/login", json={"net_id": "nkim"})
    # Submit application
    r = s.post(f"{_base(server_url)}/api/apply",
               json={"applicant_name": "Natalie Kim",
                     "applicant_email": "nkim@uw.edu",
                     "program": "security",
                     "statement": "I want to research browser security"})
    data = r.json()
    ok = data.get("status") == "submitted"
    # Verify user has application
    r2 = s.get(f"{_base(server_url)}/api/users/nkim")
    user = r2.json()
    apps = user.get("applications", [])
    has_app = any(a.get("program") == "security" for a in apps)
    return {"pass": ok and has_app,
            "detail": f"Apply status={data.get('status')}, user has app={has_app}"}
