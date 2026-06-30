"""Per-task HTTP verification functions for personal-portfolio."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/personal-portfolio"
    r = requests.get(f"{base}/api/resume")
    resume = r.json()
    title = resume.get("header", {}).get("title", "")
    return {"pass": title == "Software Engineer",
            "detail": f"Resume title: {title}"}


def verify_002(server_url):
    base = f"{server_url}/sites/personal-portfolio"
    r = requests.get(f"{base}/api/projects/1")
    project = r.json()
    techs = project.get("technologies", [])
    return {"pass": len(techs) > 0 and "React" in techs,
            "detail": f"TrailSync technologies: {techs}"}


def verify_003(server_url):
    base = f"{server_url}/sites/personal-portfolio"
    r = requests.get(f"{base}/api/projects?category=side_project")
    projects = r.json()
    count = len(projects)
    return {"pass": count > 0,
            "detail": f"side_project count: {count}"}


def verify_004(server_url):
    base = f"{server_url}/sites/personal-portfolio"
    r = requests.get(f"{base}/api/profile")
    profile = r.json()
    location = profile.get("location", "")
    return {"pass": location == "Lakeport, WA",
            "detail": f"Location: {location}"}


def verify_005(server_url):
    base = f"{server_url}/sites/personal-portfolio"
    r = requests.get(f"{base}/api/skills")
    skills = r.json()
    advanced = [s for s in skills if s.get("level") == "advanced"]
    return {"pass": len(advanced) > 0,
            "detail": f"Advanced skills count: {len(advanced)}"}


def verify_006(server_url):
    base = f"{server_url}/sites/personal-portfolio"
    r = requests.get(f"{base}/api/blog-links?category=Photography")
    links = r.json()
    count = len(links)
    return {"pass": count > 0,
            "detail": f"Photography blog posts: {count}"}


def verify_007(server_url):
    base = f"{server_url}/sites/personal-portfolio"
    r = requests.get(f"{base}/api/search?q=hiking")
    results = r.json()
    count = len(results)
    types = set(res.get("type") for res in results)
    return {"pass": count > 0,
            "detail": f"Search 'hiking': {count} results, types: {types}"}


def verify_008(server_url):
    base = f"{server_url}/sites/personal-portfolio"
    r = requests.get(f"{base}/api/projects?tech=React")
    projects = r.json()
    titles = [p["title"] for p in projects]
    return {"pass": len(projects) > 0,
            "detail": f"React projects: {titles}"}


def verify_009(server_url):
    base = f"{server_url}/sites/personal-portfolio"
    r = requests.get(f"{base}/api/search?q=Rust")
    results = r.json()
    project_results = [res for res in results if res.get("type") == "project"]
    # Also verify snip project has GitHub stars
    r2 = requests.get(f"{base}/api/projects/4")
    snip = r2.json()
    stars = snip.get("github_stars", 0)
    return {"pass": len(project_results) > 0 and stars > 0,
            "detail": f"Rust search project results: {len(project_results)}, snip stars: {stars}"}


def verify_010(server_url):
    base = f"{server_url}/sites/personal-portfolio"
    r = requests.get(f"{base}/api/resume")
    resume = r.json()
    languages = resume.get("skills", {}).get("languages", [])
    return {"pass": len(languages) > 0 and "Python" in languages,
            "detail": f"Resume languages: {languages}"}


def verify_011(server_url):
    base = f"{server_url}/sites/personal-portfolio"
    r = requests.get(f"{base}/api/export?type=projects&format=csv")
    lines = r.text.strip().split("\n")
    data_rows = len(lines) - 1  # minus header
    return {"pass": data_rows > 0,
            "detail": f"CSV export projects: {data_rows} data rows"}


def verify_012(server_url):
    base = f"{server_url}/sites/personal-portfolio"
    r = requests.get(f"{base}/api/skills")
    skills = r.json()
    python = next((s for s in skills if s["name"] == "Python"), None)
    years = python.get("years", 0) if python else 0
    return {"pass": years > 0,
            "detail": f"Python years: {years}"}


def verify_013(server_url):
    base = f"{server_url}/sites/personal-portfolio"
    r = requests.get(f"{base}/api/contact")
    messages = r.json()
    match = [m for m in messages if m.get("email") == "jamie@example.com"
             and m.get("name") == "Jamie Lee"]
    return {"pass": len(match) > 0,
            "detail": f"Contact message from Jamie Lee found: {len(match) > 0}"}


def verify_014(server_url):
    base = f"{server_url}/sites/personal-portfolio"
    r = requests.get(f"{base}/api/subscriptions")
    subs = r.json()
    match = [s for s in subs
             if s.get("email") == "reader@example.com" and s.get("subscribed")]
    return {"pass": len(match) > 0,
            "detail": f"reader@example.com subscribed: {len(match) > 0}"}


def verify_015(server_url):
    base = f"{server_url}/sites/personal-portfolio"
    r = requests.get(f"{base}/api/export?type=projects&format=csv&category=side_project")
    lines = r.text.strip().split("\n")
    data_rows = len(lines) - 1
    # Verify titles present in CSV
    csv_text = r.text
    return {"pass": data_rows > 0 and "TrailSync" in csv_text,
            "detail": f"side_project CSV export: {data_rows} rows"}


def verify_016(server_url):
    base = f"{server_url}/sites/personal-portfolio"
    r = requests.get(f"{base}/api/search?q=photography+film")
    results = r.json()
    blog_results = [res for res in results if res.get("type") == "blog"]
    return {"pass": len(blog_results) > 0,
            "detail": f"photography film blog results: {len(blog_results)}, "
                      f"titles: {[b['title'] for b in blog_results]}"}


def verify_017(server_url):
    base = f"{server_url}/sites/personal-portfolio"
    r = requests.get(f"{base}/api/resume")
    resume = r.json()
    all_skills = set()
    for cat_skills in resume.get("skills", {}).values():
        all_skills.update(cat_skills)
    count = len(all_skills)
    return {"pass": count > 0,
            "detail": f"Total unique resume skills: {count}"}


def verify_018(server_url):
    base = f"{server_url}/sites/personal-portfolio"
    r = requests.get(f"{base}/api/subscriptions")
    subs = r.json()
    match = next((s for s in subs if s.get("email") == "toggle@example.com"), None)
    if not match:
        return {"pass": False, "detail": "toggle@example.com not found in subscriptions"}
    return {"pass": match.get("subscribed") is False,
            "detail": f"toggle@example.com subscribed={match.get('subscribed')}"}


def verify_019(server_url):
    base = f"{server_url}/sites/personal-portfolio"
    # Check contact message was sent
    r = requests.get(f"{base}/api/contact")
    messages = r.json()
    msg_found = any(m.get("email") == "pat@techcorp.com" for m in messages)
    # Check resume export
    r2 = requests.get(f"{base}/api/export?type=resume&format=json")
    resume = r2.json()
    company = resume.get("experience", [{}])[0].get("company", "")
    return {"pass": msg_found and "Meridian" in company,
            "detail": f"Contact msg found: {msg_found}, company: {company}"}


def verify_020(server_url):
    base = f"{server_url}/sites/personal-portfolio"
    # Search for board game
    r = requests.get(f"{base}/api/search?q=board+game")
    results = r.json()
    blog_results = [res for res in results if res.get("type") == "blog"]
    # Check side_project filter for ScoreKeep
    r2 = requests.get(f"{base}/api/projects?category=side_project")
    projects = r2.json()
    scorekeep = next((p for p in projects if p["title"] == "ScoreKeep"), None)
    return {"pass": len(blog_results) > 0 and scorekeep is not None,
            "detail": f"Blog results: {len(blog_results)}, "
                      f"ScoreKeep found: {scorekeep is not None}, "
                      f"status: {scorekeep.get('status') if scorekeep else 'N/A'}"}
