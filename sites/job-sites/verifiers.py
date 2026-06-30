"""Per-task HTTP verification functions for job-sites."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/job-sites"
    r = requests.get(f"{base}/api/jobs?company=Nimbus+Cloud+Technologies")
    jobs = r.json()
    count = len(jobs)
    return {"pass": count == 1, "detail": f"Nimbus Cloud Technologies: {count} jobs"}


def verify_002(server_url):
    base = f"{server_url}/sites/job-sites"
    r = requests.get(f"{base}/api/jobs/5")
    job = r.json()
    title = job.get("job_title", "")
    # Check the detail page is accessible
    r2 = requests.get(f"{base}/job/5")
    return {"pass": r2.status_code == 200 and len(title) > 0, "detail": f"Job 5 title: {title}"}


def verify_003(server_url):
    base = f"{server_url}/sites/job-sites"
    r = requests.get(f"{base}/api/jobs?q=platform")
    jobs = r.json()
    count = len(jobs)
    return {"pass": count > 0, "detail": f"Search 'platform': {count} results"}


def verify_004(server_url):
    base = f"{server_url}/sites/job-sites"
    r = requests.get(f"{base}/api/jobs/semantic?q=cloud+infrastructure+devops")
    jobs = r.json()
    count = len(jobs)
    return {"pass": count >= 0, "detail": f"Semantic 'cloud infrastructure devops': {count} results"}


def verify_005(server_url):
    base = f"{server_url}/sites/job-sites"
    r = requests.get(f"{base}/api/jobs?q=distributed&sort=relevance")
    jobs = r.json()
    if not jobs:
        return {"pass": False, "detail": "No results for 'distributed'"}
    title = jobs[0]["job_title"]
    return {"pass": len(title) > 0, "detail": f"First result for 'distributed': {title}"}


def verify_006(server_url):
    base = f"{server_url}/sites/job-sites"
    r = requests.get(f"{base}/api/jobs/semantic?q=developer+tools+open+source")
    jobs = r.json()
    count = sum(
        1 for j in jobs
        if any("go" in req.lower() or "rust" in req.lower() for req in j.get("requirements", []))
    )
    return {"pass": True, "detail": f"Semantic 'developer tools open source': {count} with Go/Rust in requirements"}


def verify_007(server_url):
    base = f"{server_url}/sites/job-sites"
    r = requests.get(f"{base}/api/jobs?company=Sentry.io")
    jobs = r.json()
    if not jobs:
        return {"pass": False, "detail": "No Sentry.io jobs found"}
    salary = jobs[0].get("salary_range", "")
    return {"pass": len(salary) > 0, "detail": f"Sentry.io salary: {salary}"}


def verify_008(server_url):
    base = f"{server_url}/sites/job-sites"
    r = requests.get(f"{base}/api/jobs?job_type=full-time")
    jobs = r.json()
    count = len(jobs)
    all_ft = all(j.get("job_type", "").lower() == "full-time" for j in jobs)
    return {"pass": count > 0 and all_ft, "detail": f"Full-time: {count} jobs, all_ft={all_ft}"}


def verify_009(server_url):
    base = f"{server_url}/sites/job-sites"
    r = requests.get(f"{base}/api/jobs?salary_min=160000")
    jobs = r.json()
    count = len(jobs)
    return {"pass": count > 0, "detail": f"Salary >= $160k: {count} jobs"}


def verify_010(server_url):
    base = f"{server_url}/sites/job-sites"
    r = requests.get(f"{base}/api/jobs?date_from=2026-05-01&date_to=2026-05-31")
    jobs = r.json()
    count = len(jobs)
    all_may = all("2026-05" in j.get("posted_date", "") for j in jobs)
    return {"pass": count > 0 and all_may, "detail": f"May 2026: {count} jobs, all_may={all_may}"}


def verify_011(server_url):
    base = f"{server_url}/sites/job-sites"
    r = requests.get(f"{base}/api/jobs?sort=salary_desc")
    jobs = r.json()
    if not jobs:
        return {"pass": False, "detail": "No jobs returned"}
    title = jobs[0]["job_title"]
    return {"pass": len(title) > 0, "detail": f"Highest salary job: {title}"}


def verify_012(server_url):
    base = f"{server_url}/sites/job-sites"
    r = requests.get(f"{base}/api/jobs?q=Kubernetes&sort=relevance")
    jobs = r.json()
    if not jobs:
        return {"pass": False, "detail": "No results for 'Kubernetes'"}
    company = jobs[0]["company"]
    return {"pass": len(company) > 0, "detail": f"First 'Kubernetes' result company: {company}"}


def verify_013(server_url):
    base = f"{server_url}/sites/job-sites"
    r = requests.get(f"{base}/api/jobs/semantic?q=machine+learning+data+science")
    jobs = r.json()
    if not jobs:
        return {"pass": False, "detail": "No semantic results for 'machine learning data science'"}
    salary = jobs[0].get("salary_range", "")
    return {"pass": len(salary) > 0, "detail": f"Top ML result salary: {salary}"}


def verify_014(server_url):
    base = f"{server_url}/sites/job-sites"
    r = requests.get(f"{base}/api/companies/Temporal%20Technologies/stats")
    stats = r.json()
    avg = stats.get("avg_min_salary", 0)
    return {"pass": avg > 0, "detail": f"Temporal Technologies avg_min_salary: {avg}"}


def verify_015(server_url):
    base = f"{server_url}/sites/job-sites"
    r = requests.get(f"{base}/api/jobs/3")
    job = r.json()
    company = job.get("company", "")
    return {"pass": company == "Orion Software", "detail": f"Job 3 company: {company}"}


def verify_016(server_url):
    base = f"{server_url}/sites/job-sites"
    r = requests.get(f"{base}/api/alerts")
    alerts = r.json()
    found = any(a for a in alerts if "Backend Engineer Alert" in a.get("alert_name", ""))
    return {"pass": found, "detail": f"Backend Engineer Alert found: {found}, total alerts: {len(alerts)}"}


def verify_017(server_url):
    base = f"{server_url}/sites/job-sites"
    r = requests.get(f"{base}/api/applications")
    apps = r.json()
    applied = any(
        a for a in apps
        if a["company"] == "Cascadia Health Tech" and a["status"] == "applied"
    )
    return {"pass": applied, "detail": f"Applied to Cascadia Health Tech: {applied}"}


def verify_018(server_url):
    base = f"{server_url}/sites/job-sites"
    r = requests.get(f"{base}/api/applications")
    apps = r.json()
    applied = any(
        a for a in apps
        if a["company"] == "DataForge Inc." and a["status"] == "applied"
    )
    return {"pass": applied, "detail": f"Applied to DataForge Inc.: {applied}"}


def verify_019(server_url):
    base = f"{server_url}/sites/job-sites"
    r = requests.get(f"{base}/api/users/1")
    user = r.json()
    followed = user.get("followed_companies", [])
    has_temporal = "Temporal Technologies" in followed
    return {"pass": has_temporal, "detail": f"Following Temporal Technologies: {has_temporal}, followed: {followed}"}


def verify_020(server_url):
    base = f"{server_url}/sites/job-sites"
    r = requests.get(f"{base}/api/alerts")
    alerts = r.json()
    first = next((a for a in alerts if a.get("alert_name") == "Senior SWE - Remote PNW"), None)
    if first is None:
        return {"pass": False, "detail": "Alert 'Senior SWE - Remote PNW' not found"}
    is_active = first.get("is_active", False)
    return {"pass": is_active, "detail": f"Senior SWE alert is_active: {is_active}"}
