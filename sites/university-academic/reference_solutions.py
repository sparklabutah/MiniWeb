"""Per-task reference solutions via Flask test client for university-academic."""
import json


def solve_001(client, base="/sites/university-academic"):
    """navigate_by_dropdown: count research areas."""
    r = client.get(f"{base}/api/departments")
    data = json.loads(r.data)
    return str(len(data.get("research_areas", [])))


def solve_002(client, base="/sites/university-academic"):
    """navigate_by_route: CSE 446 instructor."""
    r = client.get(f"{base}/api/courses/cse-446")
    return json.loads(r.data)["instructor"]


def solve_003(client, base="/sites/university-academic"):
    """search_by_query: search 'data'."""
    r = client.get(f"{base}/api/courses?q=data")
    return str(len(json.loads(r.data)))


def solve_004(client, base="/sites/university-academic"):
    """search_by_semantic: first result for 'distributed systems'."""
    r = client.get(f"{base}/api/faculty/search?q=distributed+systems")
    results = json.loads(r.data)
    return results[0]["name"] if results else "No results"


def solve_005(client, base="/sites/university-academic"):
    """search_by_route: search 'programming' via route."""
    r = client.get(f"{base}/api/courses/search/programming")
    return str(len(json.loads(r.data)))


def solve_006(client, base="/sites/university-academic"):
    """filter_by_dropdown: count advanced courses."""
    r = client.get(f"{base}/api/courses?level=advanced")
    return str(len(json.loads(r.data)))


def solve_007(client, base="/sites/university-academic"):
    """filter_by_route: count intermediate courses."""
    r = client.get(f"{base}/api/courses/level/intermediate")
    return str(len(json.loads(r.data)))


def solve_008(client, base="/sites/university-academic"):
    """extract_by_query: count ML faculty."""
    r = client.get(f"{base}/api/faculty?area=machine+learning")
    return str(len(json.loads(r.data)))


def solve_009(client, base="/sites/university-academic"):
    """extract_by_checkbox: introductory + advanced courses."""
    r = client.get(f"{base}/api/courses?levels=introductory&levels=advanced")
    return str(len(json.loads(r.data)))


def solve_010(client, base="/sites/university-academic"):
    """extract_from_table + compare_from_table: CSE 446 max enrollment."""
    r = client.get(f"{base}/api/compare?ids=cse-446,cse-473")
    courses = json.loads(r.data)
    cse446 = next((c for c in courses if c["id"] == "cse-446"), None)
    return str(cse446["max_enrollment"]) if cse446 else "N/A"


def solve_011(client, base="/sites/university-academic"):
    """extract_by_route: Dr. David Liu office."""
    r = client.get(f"{base}/api/faculty/fac-004")
    return json.loads(r.data)["office"]


def solve_012(client, base="/sites/university-academic"):
    """extract_by_date_range: events between 2025-10-01 and 2026-01-31."""
    r = client.get(f"{base}/api/events?date=2025-10-01&date_to=2026-01-31")
    return str(len(json.loads(r.data)))


def solve_013(client, base="/sites/university-academic"):
    """compare_from_table: which course has higher enrollment."""
    r = client.get(f"{base}/api/compare?ids=cse-452,cse-461")
    courses = json.loads(r.data)
    c452 = next((c for c in courses if c["id"] == "cse-452"), None)
    c461 = next((c for c in courses if c["id"] == "cse-461"), None)
    if c452 and c461:
        return "CSE 461" if c461["max_enrollment"] > c452["max_enrollment"] else "CSE 452"
    return "N/A"


def solve_014(client, base="/sites/university-academic"):
    """submit_by_query: submit contact form."""
    r = client.post(f"{base}/api/submit",
                    json={"subject": "Course Availability",
                          "message": "When will CSE 452 be offered next?"})
    data = json.loads(r.data)
    return data.get("status", "")


def solve_015(client, base="/sites/university-academic"):
    """apply_by_form: submit application."""
    r = client.post(f"{base}/api/apply",
                    json={"applicant_name": "Jane Doe",
                          "applicant_email": "jane@example.com",
                          "program": "machine-learning",
                          "statement": "I am interested in ML."})
    data = json.loads(r.data)
    return data.get("status", "")


def solve_016(client, base="/sites/university-academic"):
    """export_by_dropdown: CSV data row count."""
    r = client.get(f"{base}/api/export?format=csv&type=courses")
    lines = r.data.decode().strip().split("\n")
    return str(len(lines) - 1)


def solve_017(client, base="/sites/university-academic"):
    """subscribe_by_toggle: subscribe to systems."""
    # Login
    client.post(f"{base}/api/login", json={"net_id": "arivera"})
    # Subscribe
    r = client.post(f"{base}/api/subscribe/systems")
    data = json.loads(r.data)
    action = data.get("action", "")
    # Clean up
    client.post(f"{base}/api/subscribe/systems")
    return action


def solve_018(client, base="/sites/university-academic"):
    """navigate_by_semantic: ML active projects."""
    r = client.get(f"{base}/api/departments/machine-learning")
    return str(json.loads(r.data).get("active_projects", 0))


def solve_019(client, base="/sites/university-academic"):
    """filter_by_dropdown: count systems courses."""
    r = client.get(f"{base}/api/courses?dept=systems")
    return str(len(json.loads(r.data)))


def solve_020(client, base="/sites/university-academic"):
    """apply_by_form: submit application as nkim."""
    # Login as nkim
    client.post(f"{base}/api/login", json={"net_id": "nkim"})
    # Submit application
    r = client.post(f"{base}/api/apply",
                    json={"applicant_name": "Natalie Kim",
                          "applicant_email": "nkim@uw.edu",
                          "program": "security",
                          "statement": "I want to research browser security"})
    data = json.loads(r.data)
    return data.get("status", "")
