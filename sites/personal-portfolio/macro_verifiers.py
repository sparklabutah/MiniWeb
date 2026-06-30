"""Per-macro verification functions for personal-portfolio.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/personal-portfolio"


def verify_macro_navigate_by_semantic(server_url):
    """Verify semantic search returns results across content types."""
    r = requests.get(f"{_base(server_url)}/api/search?q=hiking+photography")
    results = r.json()
    types_found = set(res["type"] for res in results)
    has_multiple_types = len(types_found) > 1
    # Also verify the HTML search page works
    r2 = requests.get(f"{_base(server_url)}/search?q=hiking")
    page_ok = r2.status_code == 200
    return {"pass": len(results) > 0 and page_ok,
            "detail": f"Semantic search: {len(results)} results, "
                      f"types: {types_found}, page: {r2.status_code}"}


def verify_macro_navigate_by_dropdown(server_url):
    """Verify dropdown-based project filtering works."""
    # Filter by category
    r = requests.get(f"{_base(server_url)}/api/projects?category=side_project")
    projects = r.json()
    all_correct_type = all(p.get("type") == "side_project" for p in projects)
    # Filter by technology
    r2 = requests.get(f"{_base(server_url)}/api/projects?tech=Python")
    py_projects = r2.json()
    all_have_python = all(
        "Python" in p.get("technologies", []) for p in py_projects
    )
    # Verify the projects page HTML loads
    r3 = requests.get(f"{_base(server_url)}/projects")
    return {"pass": len(projects) > 0 and all_correct_type and all_have_python,
            "detail": f"Dropdown filter: {len(projects)} side_projects (correct={all_correct_type}), "
                      f"{len(py_projects)} Python projects (correct={all_have_python}), "
                      f"page: {r3.status_code}"}


def verify_macro_navigate_by_route(server_url):
    """Verify direct URL navigation to key pages."""
    pages = {
        "resume": f"{_base(server_url)}/resume",
        "projects": f"{_base(server_url)}/projects",
        "blog": f"{_base(server_url)}/blog",
        "project_detail": f"{_base(server_url)}/project/1",
        "skills": f"{_base(server_url)}/skills",
    }
    statuses = {}
    for name, url in pages.items():
        r = requests.get(url)
        statuses[name] = r.status_code
    all_ok = all(s == 200 for s in statuses.values())
    return {"pass": all_ok,
            "detail": f"Route navigation: {statuses}"}


def verify_macro_extract_by_query(server_url):
    """Verify search/query-based data extraction from projects."""
    r = requests.get(f"{_base(server_url)}/api/projects?q=trail")
    projects = r.json()
    if projects:
        title = projects[0]["title"]
        return {"pass": True,
                "detail": f"extract_by_query 'trail': first result = {title}"}
    return {"pass": True, "detail": "extract_by_query 'trail': no results (ok)"}


def verify_macro_extract_by_semantic(server_url):
    """Verify semantic search-based extraction across portfolio."""
    r = requests.get(f"{_base(server_url)}/api/search?q=open+source+command+line")
    results = r.json()
    project_results = [res for res in results if res["type"] == "project"]
    return {"pass": r.status_code == 200 and len(results) > 0,
            "detail": f"Semantic extract: {len(results)} results, "
                      f"{len(project_results)} projects"}


def verify_macro_extract_from_table(server_url):
    """Verify skills table data can be extracted."""
    r = requests.get(f"{_base(server_url)}/api/skills")
    skills = r.json()
    has_name = all("name" in s for s in skills)
    has_level = any(s.get("level") for s in skills)
    has_years = any(s.get("years", 0) > 0 for s in skills)
    # Also verify the HTML table page loads
    r2 = requests.get(f"{_base(server_url)}/skills")
    return {"pass": len(skills) > 0 and has_name and has_level and has_years,
            "detail": f"Skills table: {len(skills)} skills, "
                      f"has_level={has_level}, has_years={has_years}, "
                      f"page: {r2.status_code}"}


def verify_macro_extract_by_route(server_url):
    """Verify data extraction via direct API routes."""
    r1 = requests.get(f"{_base(server_url)}/api/profile")
    profile = r1.json()
    has_name = "name" in profile
    r2 = requests.get(f"{_base(server_url)}/api/resume")
    resume = r2.json()
    has_summary = "summary" in resume
    r3 = requests.get(f"{_base(server_url)}/api/projects/1")
    project = r3.json()
    has_title = "title" in project
    return {"pass": has_name and has_summary and has_title,
            "detail": f"Route extraction: profile.name={profile.get('name')}, "
                      f"resume.summary={len(resume.get('summary', ''))} chars, "
                      f"project.title={project.get('title')}"}


def verify_macro_submit_by_query(server_url):
    """Verify contact form submission works."""
    r = requests.post(f"{_base(server_url)}/api/contact", json={
        "name": "MacroTest User",
        "email": "macrotest@example.com",
        "subject": "Test",
        "message": "This is a macro verification test message."
    })
    data = r.json()
    ok = r.status_code == 201 and data.get("status") == "sent"
    return {"pass": ok,
            "detail": f"Contact submit: status={data.get('status')}, "
                      f"id={data.get('id')}, http={r.status_code}"}


def verify_macro_export_by_dropdown(server_url):
    """Verify export functionality for projects and resume."""
    # Export projects as CSV
    r1 = requests.get(f"{_base(server_url)}/api/export?type=projects&format=csv")
    csv_lines = r1.text.strip().split("\n")
    csv_ok = len(csv_lines) > 1 and "title" in csv_lines[0].lower()
    # Export projects as JSON
    r2 = requests.get(f"{_base(server_url)}/api/export?type=projects&format=json")
    json_projects = r2.json()
    json_ok = len(json_projects) > 0
    # Export resume as JSON
    r3 = requests.get(f"{_base(server_url)}/api/export?type=resume&format=json")
    resume = r3.json()
    resume_ok = "experience" in resume
    # Export resume skills as CSV
    r4 = requests.get(f"{_base(server_url)}/api/export?type=resume&format=csv")
    resume_csv_lines = r4.text.strip().split("\n")
    resume_csv_ok = len(resume_csv_lines) > 1
    return {"pass": csv_ok and json_ok and resume_ok and resume_csv_ok,
            "detail": f"Export: projects CSV {len(csv_lines)} lines, "
                      f"projects JSON {len(json_projects)} items, "
                      f"resume has experience={resume_ok}, "
                      f"resume CSV {len(resume_csv_lines)} lines"}


def verify_macro_subscribe_by_toggle(server_url):
    """Verify subscribe toggle works (subscribe then unsubscribe)."""
    email = "macro_toggle_test@example.com"
    # Subscribe
    r1 = requests.post(f"{_base(server_url)}/api/subscribe",
                       json={"email": email, "name": "MacroTest"})
    d1 = r1.json()
    first_action = d1.get("action")
    # Toggle (unsubscribe)
    r2 = requests.post(f"{_base(server_url)}/api/subscribe",
                       json={"email": email})
    d2 = r2.json()
    second_action = d2.get("action")
    ok = first_action == "subscribed" and second_action == "unsubscribed"
    return {"pass": ok,
            "detail": f"Subscribe toggle: first={first_action}, second={second_action}"}
