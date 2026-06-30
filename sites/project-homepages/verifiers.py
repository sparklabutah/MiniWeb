"""Per-task HTTP verification functions for project-homepages."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/project-homepages"
    r = requests.get(f"{base}/api/sections/abstract")
    data = r.json()
    content = data.get("content", "")
    first_sentence = content.split(".")[0] + "." if content else ""
    return {"pass": len(first_sentence) > 10, "detail": f"Abstract first sentence: {first_sentence[:80]}"}


def verify_002(server_url):
    base = f"{server_url}/sites/project-homepages"
    r = requests.get(f"{base}/api/team")
    team = r.json()
    count = len(team)
    return {"pass": count == 2, "detail": f"Team members: {count}"}


def verify_003(server_url):
    base = f"{server_url}/sites/project-homepages"
    r = requests.get(f"{base}/api/search?q=reinforcement+learning")
    results = r.json()
    count = len(results)
    return {"pass": count > 0, "detail": f"Search 'reinforcement learning': {count} results"}


def verify_004(server_url):
    base = f"{server_url}/sites/project-homepages"
    r = requests.get(f"{base}/api/resources")
    resources = r.json()
    count = len(resources)
    return {"pass": count == 8, "detail": f"Total resources: {count}"}


def verify_005(server_url):
    base = f"{server_url}/sites/project-homepages"
    r = requests.get(f"{base}/api/stats")
    stats = r.json()
    metrics = stats.get("key_metrics", {})
    val = metrics.get("median_latency_reduction", "")
    return {"pass": val == "34%", "detail": f"Median latency reduction: {val}"}


def verify_006(server_url):
    base = f"{server_url}/sites/project-homepages"
    r = requests.get(f"{base}/api/project")
    project = r.json()
    arxiv_id = project.get("arxiv_id", "")
    return {"pass": arxiv_id == "2505.14832", "detail": f"arXiv ID: {arxiv_id}"}


def verify_007(server_url):
    base = f"{server_url}/sites/project-homepages"
    # Verify query param navigation works
    r = requests.get(f"{base}/?section=team", allow_redirects=False)
    redirect_ok = r.status_code in (301, 302)
    # Verify team member data
    r2 = requests.get(f"{base}/api/team/1")
    user = r2.json()
    email = user.get("email", "")
    return {"pass": redirect_ok and email == "alex.rivera@meridiansystems.com",
            "detail": f"Query nav redirect: {redirect_ok}, Alex email: {email}"}


def verify_008(server_url):
    base = f"{server_url}/sites/project-homepages"
    r = requests.get(f"{base}/api/semantic?q=graph+neural+network+routing")
    results = r.json()
    if not results:
        return {"pass": False, "detail": "No semantic results for 'graph neural network routing'"}
    top = results[0]
    return {"pass": len(top.get("title", "")) > 0,
            "detail": f"Top semantic result: {top.get('title', '')[:60]}"}


def verify_009(server_url):
    base = f"{server_url}/sites/project-homepages"
    r = requests.get(f"{base}/api/sections/method")
    data = r.json()
    content = data.get("content_summary", "")
    has_ppo = "Proximal Policy Optimization" in content or "PPO" in content
    return {"pass": has_ppo, "detail": f"Method mentions PPO: {has_ppo}"}


def verify_010(server_url):
    base = f"{server_url}/sites/project-homepages"
    r = requests.get(f"{base}/api/search?q=MeridianFlow")
    results = r.json()
    count = len(results)
    return {"pass": count > 0, "detail": f"Search 'MeridianFlow': {count} results"}


def verify_011(server_url):
    base = f"{server_url}/sites/project-homepages"
    r = requests.get(f"{base}/api/semantic?q=production+deployment+latency+improvement")
    results = r.json()
    types = list(set(item.get("type", "") for item in results))
    return {"pass": len(results) > 0,
            "detail": f"Semantic results: {len(results)}, types: {types}"}


def verify_012(server_url):
    base = f"{server_url}/sites/project-homepages"
    r = requests.get(f"{base}/api/resources/stats?type=dataset")
    stats = r.json()
    count = stats.get("count", 0)
    total_size = stats.get("total_size_mb", 0)
    return {"pass": count == 1 and total_size == 2340,
            "detail": f"Dataset resources: count={count}, total_size_mb={total_size}"}


def verify_013(server_url):
    base = f"{server_url}/sites/project-homepages"
    r = requests.get(f"{base}/api/team/2")
    user = r.json()
    dept = user.get("department", "")
    return {"pass": dept == "Data Science", "detail": f"Aisha's department: {dept}"}


def verify_014(server_url):
    base = f"{server_url}/sites/project-homepages"
    r = requests.get(f"{base}/api/sections/results")
    data = r.json()
    metrics = data.get("key_metrics", {})
    before = metrics.get("sla_compliance_before", "")
    after = metrics.get("sla_compliance_after", "")
    return {"pass": before == "91.2%" and after == "98.7%",
            "detail": f"SLA compliance: {before} -> {after}"}


def verify_015(server_url):
    base = f"{server_url}/sites/project-homepages"
    r = requests.get(f"{base}/api/export?format=json")
    data = r.json()
    team_count = len(data.get("team", []))
    resource_count = len(data.get("resources", []))
    return {"pass": team_count == 2 and resource_count == 8,
            "detail": f"JSON export: team={team_count}, resources={resource_count}"}


def verify_016(server_url):
    base = f"{server_url}/sites/project-homepages"
    r = requests.get(f"{base}/api/export?format=csv")
    lines = r.text.strip().split("\n")
    data_rows = len(lines) - 1  # minus header
    return {"pass": data_rows == 10, "detail": f"CSV export: {data_rows} data rows"}


def verify_017(server_url):
    base = f"{server_url}/sites/project-homepages"
    # Verify query param navigation
    r = requests.get(f"{base}/?section=abstract", allow_redirects=False)
    nav_ok = r.status_code in (301, 302)
    # Get abstract content
    r2 = requests.get(f"{base}/api/sections/abstract")
    content = r2.json().get("content", "").lower()
    wf_count = content.count("workflow")
    return {"pass": nav_ok and wf_count > 0,
            "detail": f"Nav redirect: {nav_ok}, 'workflow' count in abstract: {wf_count}"}


def verify_018(server_url):
    base = f"{server_url}/sites/project-homepages"
    r = requests.get(f"{base}/api/semantic?q=benchmark+evaluation+performance")
    sem_ok = r.status_code == 200
    r2 = requests.get(f"{base}/api/stats")
    metrics = r2.json().get("key_metrics", {})
    p99 = metrics.get("p99_latency_reduction", "")
    throughput = metrics.get("peak_throughput_increase", "")
    return {"pass": sem_ok and p99 == "50%" and throughput == "22%",
            "detail": f"P99 reduction: {p99}, throughput increase: {throughput}"}


def verify_019(server_url):
    base = f"{server_url}/sites/project-homepages"
    r = requests.get(f"{base}/api/resources/stats?type=paper_pdf")
    stats = r.json()
    size = stats.get("total_size_mb", 0)
    r2 = requests.get(f"{base}/api/export?format=bibtex")
    bibtex = r2.text
    has_year = "2025" in bibtex
    return {"pass": size == 4.2 and has_year,
            "detail": f"Paper PDF size: {size} MB, BibTeX has 2025: {has_year}"}


def verify_020(server_url):
    base = f"{server_url}/sites/project-homepages"
    r = requests.get(f"{base}/api/search?q=PPO")
    search_ok = len(r.json()) > 0
    r2 = requests.get(f"{base}/api/sections/method")
    method = r2.json()
    content = method.get("content_summary", "")
    has_ppo = "Proximal Policy Optimization" in content
    r3 = requests.get(f"{base}/api/sections")
    sections = r3.json()
    count = len(sections)
    return {"pass": search_ok and has_ppo and count == 7,
            "detail": f"PPO search results: {search_ok}, method has PPO: {has_ppo}, sections: {count}"}
