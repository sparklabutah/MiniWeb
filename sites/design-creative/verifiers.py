"""Per-task HTTP verification functions for design-creative."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/design-creative"
    r = requests.get(f"{base}/api/templates")
    templates = r.json()
    count = len(templates)
    return {"pass": count > 0, "detail": f"Total templates: {count}"}


def verify_002(server_url):
    base = f"{server_url}/sites/design-creative"
    r = requests.get(f"{base}/api/templates/1")
    data = r.json()
    title = data.get("title", "")
    dims = data.get("dimensions", "")
    return {"pass": bool(title and dims), "detail": f"Template 1: {title} ({dims})"}


def verify_003(server_url):
    base = f"{server_url}/sites/design-creative"
    r = requests.get(f"{base}/api/categories")
    cats = r.json()
    count = len(cats)
    return {"pass": count > 0, "detail": f"Categories: {count}"}


def verify_004(server_url):
    base = f"{server_url}/sites/design-creative"
    r = requests.get(f"{base}/api/stats")
    data = r.json()
    most_popular = data.get("most_popular")
    return {"pass": most_popular is not None, "detail": f"Most popular: {most_popular}"}


def verify_005(server_url):
    base = f"{server_url}/sites/design-creative"
    r = requests.get(f"{base}/api/users/1")
    user = r.json()
    name = user.get("name")
    return {"pass": name == "Alice Rivera", "detail": f"User 1 name: {name}"}


def verify_006(server_url):
    base = f"{server_url}/sites/design-creative"
    r = requests.get(f"{base}/api/templates?category=logo")
    templates = r.json()
    count = len(templates)
    ok = all(t["category"] == "logo" for t in templates)
    return {"pass": count > 0 and ok, "detail": f"Logo templates: {count}"}


def verify_007(server_url):
    base = f"{server_url}/sites/design-creative"
    r = requests.get(f"{base}/api/templates?sort=popular&limit=5")
    templates = r.json()
    count = len(templates)
    titles = [t["title"] for t in templates]
    return {"pass": count == 5, "detail": f"Top 5 popular: {titles}"}


def verify_008(server_url):
    base = f"{server_url}/sites/design-creative"
    r = requests.get(f"{base}/api/templates?q=instagram")
    templates = r.json()
    count = len(templates)
    return {"pass": count > 0, "detail": f"Instagram templates: {count}"}


def verify_009(server_url):
    base = f"{server_url}/sites/design-creative"
    r = requests.get(f"{base}/api/assets")
    assets = r.json()
    count = len(assets)
    return {"pass": count >= 0, "detail": f"Total assets: {count}"}


def verify_010(server_url):
    base = f"{server_url}/sites/design-creative"
    r = requests.get(f"{base}/api/projects?owner_id=1")
    projects = r.json()
    count = len(projects)
    return {"pass": count >= 0, "detail": f"Alice's projects: {count}"}


def verify_011(server_url):
    base = f"{server_url}/sites/design-creative"
    r = requests.get(f"{base}/api/templates?category=presentation&sort=popular")
    templates = r.json()
    if templates:
        top = templates[0]
        return {"pass": True, "detail": f"Top presentation: {top['title']} (uses: {top['use_count']})"}
    return {"pass": False, "detail": "No presentation templates"}


def verify_012(server_url):
    base = f"{server_url}/sites/design-creative"
    r = requests.get(f"{base}/api/categories")
    cats = r.json()
    if cats:
        top_cat = max(cats, key=lambda c: c["count"])
        return {"pass": True, "detail": f"Most templates category: {top_cat['name']} ({top_cat['count']})"}
    return {"pass": False, "detail": "No categories"}


def verify_013(server_url):
    base = f"{server_url}/sites/design-creative"
    r = requests.get(f"{base}/api/stats")
    data = r.json()
    total = data.get("total_projects", 0)
    return {"pass": total >= 0, "detail": f"Total projects: {total}"}


def verify_014(server_url):
    base = f"{server_url}/sites/design-creative"
    r = requests.get(f"{base}/api/templates?sort=name")
    templates = r.json()
    if templates:
        first = templates[0]
        return {"pass": True, "detail": f"First alphabetically: {first['title']}"}
    return {"pass": False, "detail": "No templates"}


def verify_015(server_url):
    base = f"{server_url}/sites/design-creative"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "alice_design", "password": "design123"})
    r = s.post(f"{base}/api/projects", json={
        "owner_id": 1,
        "template_id": 6,
        "title": "My Pitch Deck"
    })
    data = r.json()
    pid = data.get("id")
    ok = pid is not None and data.get("title") == "My Pitch Deck"
    return {"pass": ok, "detail": f"Created project ID: {pid}, title={data.get('title')}"}


def verify_016(server_url):
    base = f"{server_url}/sites/design-creative"
    # Create project
    r = requests.post(f"{base}/api/projects", json={
        "owner_id": 2,
        "title": "Social Media Kit",
        "dimensions": "1080x1080"
    })
    data = r.json()
    pid = data.get("id")
    if not pid:
        return {"pass": False, "detail": "Failed to create project"}
    # Update to completed
    r2 = requests.put(f"{base}/api/projects/{pid}", json={"status": "completed"})
    data2 = r2.json()
    status = data2.get("status")
    return {"pass": status == "completed", "detail": f"Project {pid} status: {status}"}


def verify_017(server_url):
    base = f"{server_url}/sites/design-creative"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "bob_creative", "password": "create456"})
    r = s.post(f"{base}/api/users/2/favorites", json={"template_id": 1})
    data = r.json()
    action = data.get("action")
    return {"pass": action in ("favorited", "unfavorited"),
            "detail": f"Favorite action: {action}"}


def verify_018(server_url):
    base = f"{server_url}/sites/design-creative"
    # Create project
    r = requests.post(f"{base}/api/projects", json={
        "owner_id": 1,
        "template_id": 14,
        "title": "My Logo"
    })
    data = r.json()
    pid = data.get("id")
    if not pid:
        return {"pass": False, "detail": "Failed to create project"}
    # Add element
    r2 = requests.post(f"{base}/api/projects/{pid}/elements", json={
        "type": "text",
        "properties": {"text": "Hello World", "x": 100, "y": 100}
    })
    data2 = r2.json()
    total = data2.get("total_elements", 0)
    return {"pass": total >= 1, "detail": f"Project {pid} elements: {total}"}


def verify_019(server_url):
    base = f"{server_url}/sites/design-creative"
    # Get project 1 title first
    r1 = requests.get(f"{base}/api/projects/1")
    if r1.status_code != 200:
        return {"pass": False, "detail": "Project 1 not found"}
    orig_title = r1.json().get("title", "")
    # Duplicate
    r = requests.post(f"{base}/api/projects/1/duplicate")
    data = r.json()
    new_title = data.get("title", "")
    ok = new_title.startswith("Copy of")
    return {"pass": ok, "detail": f"Duplicated project title: {new_title}"}


def verify_020(server_url):
    base = f"{server_url}/sites/design-creative"
    r = requests.get(f"{base}/api/templates?sort=popular&limit=1")
    templates = r.json()
    if not templates:
        return {"pass": False, "detail": "No templates"}
    top_tmpl = templates[0]
    tmpl_id = top_tmpl["id"]
    # Create project from it
    r2 = requests.post(f"{base}/api/projects", json={
        "owner_id": 3,
        "template_id": tmpl_id,
        "title": f"From {top_tmpl['title']}"
    })
    data = r2.json()
    dims = data.get("dimensions", "")
    ok = dims == top_tmpl["dimensions"]
    return {"pass": ok, "detail": f"Project dimensions: {dims} (expected {top_tmpl['dimensions']})"}
