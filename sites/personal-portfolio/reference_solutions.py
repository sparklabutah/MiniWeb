"""Per-task reference solutions via Flask test client for personal-portfolio."""
import json


def solve_001(client, base="/sites/personal-portfolio"):
    r = client.get(f"{base}/api/resume")
    resume = json.loads(r.data)
    return resume["header"]["title"]


def solve_002(client, base="/sites/personal-portfolio"):
    r = client.get(f"{base}/api/projects/1")
    project = json.loads(r.data)
    return ", ".join(project["technologies"])


def solve_003(client, base="/sites/personal-portfolio"):
    r = client.get(f"{base}/api/projects?category=side_project")
    projects = json.loads(r.data)
    return str(len(projects))


def solve_004(client, base="/sites/personal-portfolio"):
    r = client.get(f"{base}/api/profile")
    profile = json.loads(r.data)
    return profile["location"]


def solve_005(client, base="/sites/personal-portfolio"):
    r = client.get(f"{base}/api/skills")
    skills = json.loads(r.data)
    advanced = [s for s in skills if s.get("level") == "advanced"]
    return str(len(advanced))


def solve_006(client, base="/sites/personal-portfolio"):
    r = client.get(f"{base}/api/blog-links?category=Photography")
    links = json.loads(r.data)
    return str(len(links))


def solve_007(client, base="/sites/personal-portfolio"):
    r = client.get(f"{base}/api/search?q=hiking")
    results = json.loads(r.data)
    types = sorted(set(res["type"] for res in results))
    return f"{len(results)} results, types: {', '.join(types)}"


def solve_008(client, base="/sites/personal-portfolio"):
    r = client.get(f"{base}/api/projects?tech=React")
    projects = json.loads(r.data)
    return ", ".join(p["title"] for p in projects)


def solve_009(client, base="/sites/personal-portfolio"):
    r = client.get(f"{base}/api/search?q=Rust")
    results = json.loads(r.data)
    project_results = [res for res in results if res["type"] == "project"]
    # Get snip project details
    r2 = client.get(f"{base}/api/projects/4")
    snip = json.loads(r2.data)
    return f"snip ({snip.get('github_stars', 0)} stars)"


def solve_010(client, base="/sites/personal-portfolio"):
    r = client.get(f"{base}/api/resume")
    resume = json.loads(r.data)
    languages = resume.get("skills", {}).get("languages", [])
    return ", ".join(languages)


def solve_011(client, base="/sites/personal-portfolio"):
    r = client.get(f"{base}/api/export?type=projects&format=csv")
    lines = r.data.decode().strip().split("\n")
    return str(len(lines) - 1)


def solve_012(client, base="/sites/personal-portfolio"):
    r = client.get(f"{base}/api/skills")
    skills = json.loads(r.data)
    python = next((s for s in skills if s["name"] == "Python"), None)
    return str(python["years"]) if python else "0"


def solve_013(client, base="/sites/personal-portfolio"):
    r = client.post(f"{base}/api/contact", json={
        "name": "Jamie Lee",
        "email": "jamie@example.com",
        "subject": "Collaboration",
        "message": "Would love to collaborate on an open source project."
    })
    result = json.loads(r.data)
    return result.get("status", "")


def solve_014(client, base="/sites/personal-portfolio"):
    r = client.post(f"{base}/api/subscribe", json={
        "email": "reader@example.com",
        "name": "Reader"
    })
    result = json.loads(r.data)
    return result.get("action", "")


def solve_015(client, base="/sites/personal-portfolio"):
    r = client.get(f"{base}/api/export?type=projects&format=csv&category=side_project")
    lines = r.data.decode().strip().split("\n")
    data_rows = len(lines) - 1
    # Extract titles from CSV rows (title is column 2)
    titles = []
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) >= 2:
            titles.append(parts[1].strip('"'))
    return f"{data_rows} projects: {', '.join(titles)}"


def solve_016(client, base="/sites/personal-portfolio"):
    r = client.get(f"{base}/api/search?q=photography+film")
    results = json.loads(r.data)
    blog_results = [res for res in results if res["type"] == "blog"]
    return ", ".join(f"{b['title']}" for b in blog_results)


def solve_017(client, base="/sites/personal-portfolio"):
    r = client.get(f"{base}/api/resume")
    resume = json.loads(r.data)
    all_skills = set()
    for cat_skills in resume.get("skills", {}).values():
        all_skills.update(cat_skills)
    return str(len(all_skills))


def solve_018(client, base="/sites/personal-portfolio"):
    # Subscribe
    client.post(f"{base}/api/subscribe", json={"email": "toggle@example.com"})
    # Toggle (unsubscribe)
    r = client.post(f"{base}/api/subscribe", json={"email": "toggle@example.com"})
    result = json.loads(r.data)
    return result.get("action", "")


def solve_019(client, base="/sites/personal-portfolio"):
    # Send contact message
    client.post(f"{base}/api/contact", json={
        "name": "Recruiter Pat",
        "email": "pat@techcorp.com",
        "subject": "Job Opportunity",
        "message": "We have an exciting senior role."
    })
    # Export resume as JSON
    r = client.get(f"{base}/api/export?type=resume&format=json")
    resume = json.loads(r.data)
    company = resume["experience"][0]["company"]
    return company


def solve_020(client, base="/sites/personal-portfolio"):
    # Search for board game
    r = client.get(f"{base}/api/search?q=board+game")
    results = json.loads(r.data)
    blog_results = [res for res in results if res["type"] == "blog"]
    blog_title = blog_results[0]["title"] if blog_results else "None"
    # Filter projects by side_project
    r2 = client.get(f"{base}/api/projects?category=side_project")
    projects = json.loads(r2.data)
    scorekeep = next((p for p in projects if p["title"] == "ScoreKeep"), None)
    status = scorekeep["status"] if scorekeep else "not found"
    return f"Blog: {blog_title}, ScoreKeep status: {status}"
