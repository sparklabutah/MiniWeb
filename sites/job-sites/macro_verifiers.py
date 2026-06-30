"""Per-macro verification functions for job-sites.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/job-sites"


def verify_macro_navigate_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/companies")
    companies = r.json()
    if not companies:
        return {"pass": False, "detail": "No companies returned"}
    name = companies[0]["name"]
    r2 = requests.get(f"{_base(server_url)}/company/{name}")
    return {"pass": r2.status_code == 200, "detail": f"Company page '{name}': {r2.status_code}"}


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/job/1")
    return {"pass": r.status_code == 200, "detail": f"Job detail page: {r.status_code}"}


def verify_macro_search_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/jobs?q=software")
    results = r.json()
    return {"pass": len(results) > 0, "detail": f"search_by_query 'software': {len(results)} results"}


def verify_macro_search_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/jobs/semantic?q=cloud+computing")
    results = r.json()
    return {"pass": r.status_code == 200, "detail": f"search_by_semantic: {len(results)} results"}


def verify_macro_filter_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/jobs?q=engineer")
    results = r.json()
    ok = all("engineer" in j.get("job_title", "").lower() or "engineer" in _job_text(j).lower() for j in results)
    return {"pass": len(results) > 0, "detail": f"filter_by_query 'engineer': {len(results)} results"}


def verify_macro_filter_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/jobs/semantic?q=infrastructure")
    results = r.json()
    return {"pass": r.status_code == 200, "detail": f"filter_by_semantic: {len(results)} results"}


def verify_macro_filter_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/jobs?company=Sentry.io")
    jobs = r.json()
    ok = all(j["company"] == "Sentry.io" for j in jobs)
    return {"pass": len(jobs) > 0 and ok, "detail": f"filter_by_dropdown Sentry.io: {len(jobs)} jobs, all_match={ok}"}


def verify_macro_filter_by_radio(server_url):
    r = requests.get(f"{_base(server_url)}/api/jobs?job_type=full-time")
    jobs = r.json()
    ok = all(j.get("job_type", "").lower() == "full-time" for j in jobs)
    return {"pass": len(jobs) > 0 and ok, "detail": f"filter_by_radio full-time: {len(jobs)} jobs, all_ft={ok}"}


def verify_macro_filter_by_slider(server_url):
    r = requests.get(f"{_base(server_url)}/api/jobs?salary_min=170000")
    jobs = r.json()
    return {"pass": len(jobs) > 0, "detail": f"filter_by_slider salary>=170k: {len(jobs)} jobs"}


def verify_macro_filter_by_date_range(server_url):
    r = requests.get(f"{_base(server_url)}/api/jobs?date_from=2026-05-01&date_to=2026-06-30")
    jobs = r.json()
    ok = all(j.get("posted_date", "") >= "2026-05-01" and j.get("posted_date", "") <= "2026-06-30" for j in jobs)
    return {"pass": len(jobs) > 0 and ok, "detail": f"filter_by_date_range: {len(jobs)} jobs, all_in_range={ok}"}


def verify_macro_sort_by_ranking(server_url):
    r = requests.get(f"{_base(server_url)}/api/jobs?sort=salary_desc")
    jobs = r.json()
    if len(jobs) < 2:
        return {"pass": False, "detail": "Too few jobs to verify sort"}
    salaries = [_parse_min_salary(j.get("salary_range", "")) for j in jobs]
    is_sorted = all(salaries[i] >= salaries[i + 1] for i in range(len(salaries) - 1))
    return {"pass": is_sorted, "detail": f"sort_by_ranking salary_desc: sorted={is_sorted}"}


def verify_macro_extract_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/jobs?q=platform")
    jobs = r.json()
    if not jobs:
        return {"pass": False, "detail": "No results for 'platform'"}
    has_title = len(jobs[0].get("job_title", "")) > 0
    return {"pass": has_title, "detail": f"extract_by_query: first result title={jobs[0]['job_title'][:50]}"}


def verify_macro_extract_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/jobs/semantic?q=workflow+orchestration")
    jobs = r.json()
    if not jobs:
        return {"pass": False, "detail": "No semantic results for 'workflow orchestration'"}
    has_salary = len(jobs[0].get("salary_range", "")) > 0
    return {"pass": has_salary, "detail": f"extract_by_semantic: top result salary={jobs[0]['salary_range']}"}


def verify_macro_extract_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/companies/Temporal%20Technologies/stats")
    stats = r.json()
    has_salary = stats.get("avg_min_salary", 0) > 0
    return {"pass": has_salary, "detail": f"extract_by_dropdown: Temporal avg_min_salary={stats.get('avg_min_salary')}"}


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/jobs/1")
    job = r.json()
    has_company = len(job.get("company", "")) > 0
    return {"pass": has_company, "detail": f"extract_by_route: job 1 company={job.get('company')}"}


def verify_macro_create_from_free_text(server_url):
    # Create a new alert via free text
    r = requests.post(
        f"{_base(server_url)}/api/alerts",
        json={
            "alert_name": "Test Macro Alert",
            "search_query": "test macro verification",
            "frequency": "weekly",
        },
    )
    data = r.json()
    created = data.get("alert_name") == "Test Macro Alert"
    # Clean up
    if created:
        requests.delete(
            f"{_base(server_url)}/api/alerts",
            json={"id": data["id"]},
        )
    return {"pass": created, "detail": f"create_from_free_text: created={created}"}


def verify_macro_submit_by_query(server_url):
    # Search then apply to a result
    r = requests.get(f"{_base(server_url)}/api/jobs?q=API")
    jobs = r.json()
    if not jobs:
        return {"pass": False, "detail": "No results for 'API'"}
    job_id = jobs[0]["id"]
    r2 = requests.post(
        f"{_base(server_url)}/api/jobs/{job_id}/apply",
        json={"notes": "Macro verification test"},
    )
    ok = r2.status_code in (201, 409)  # 409 if already applied
    return {"pass": ok, "detail": f"submit_by_query: status={r2.status_code}"}


def verify_macro_upload_by_upload(server_url):
    import io
    files = {"resume": ("test_resume.pdf", io.BytesIO(b"test content"), "application/pdf")}
    r = requests.post(f"{_base(server_url)}/api/upload-resume", files=files)
    ok = r.status_code == 201
    return {"pass": ok, "detail": f"upload_by_upload: status={r.status_code}"}


def verify_macro_follow_by_toggle(server_url):
    # Follow a company
    r = requests.post(
        f"{_base(server_url)}/api/follow",
        json={"company": "PeakView Software"},
    )
    data = r.json()
    action = data.get("action")
    # Unfollow to clean up
    if action == "followed":
        requests.post(
            f"{_base(server_url)}/api/follow",
            json={"company": "PeakView Software"},
        )
    return {"pass": action in ("followed", "unfollowed"), "detail": f"follow_by_toggle: action={action}"}


def verify_macro_subscribe_by_toggle(server_url):
    r = requests.get(f"{_base(server_url)}/api/alerts")
    alerts = r.json()
    if not alerts:
        return {"pass": False, "detail": "No alerts to toggle"}
    alert_id = alerts[0]["id"]
    original_active = alerts[0]["is_active"]
    # Toggle
    r2 = requests.post(f"{_base(server_url)}/api/alerts/{alert_id}/toggle")
    data = r2.json()
    toggled = data.get("is_active") != original_active
    # Toggle back
    requests.post(f"{_base(server_url)}/api/alerts/{alert_id}/toggle")
    return {"pass": toggled, "detail": f"subscribe_by_toggle: toggled={toggled}"}


def verify_macro_save_by_toggle(server_url):
    r = requests.get(f"{_base(server_url)}/api/jobs")
    jobs = r.json()
    if not jobs:
        return {"pass": False, "detail": "No jobs to save"}
    job_id = jobs[0]["id"]
    r2 = requests.post(f"{_base(server_url)}/api/jobs/{job_id}/save")
    data = r2.json()
    action = data.get("status")
    # Toggle back
    requests.post(f"{_base(server_url)}/api/jobs/{job_id}/save")
    return {"pass": action in ("saved", "unsaved"), "detail": f"save_by_toggle: status={action}"}


def verify_macro_apply_by_form(server_url):
    # Check the apply form page renders
    r = requests.get(f"{_base(server_url)}/apply/1")
    has_form = r.status_code == 200 and b"cover_letter" in r.content
    return {"pass": has_form, "detail": f"apply_by_form: page={r.status_code}, has_form={has_form}"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _job_text(job):
    parts = [
        job.get("job_title", ""),
        job.get("company", ""),
        job.get("description_snippet", ""),
        job.get("location", ""),
        " ".join(job.get("tags", [])),
        " ".join(job.get("requirements", [])),
    ]
    return " ".join(parts)


def _parse_min_salary(salary_range):
    try:
        low = salary_range.replace("$", "").replace(",", "").split("-")[0].strip()
        return int(low)
    except (ValueError, IndexError, AttributeError):
        return 0
