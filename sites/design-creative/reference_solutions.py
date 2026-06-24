"""Per-task reference solutions via Flask test client for design-creative."""
import json


def solve_001(client, base="/sites/design-creative"):
    r = client.get(f"{base}/api/templates")
    templates = json.loads(r.data)
    return str(len(templates))


def solve_002(client, base="/sites/design-creative"):
    r = client.get(f"{base}/api/templates/1")
    data = json.loads(r.data)
    return f"{data['title']} ({data['dimensions']})"


def solve_003(client, base="/sites/design-creative"):
    r = client.get(f"{base}/api/categories")
    cats = json.loads(r.data)
    return str(len(cats))


def solve_004(client, base="/sites/design-creative"):
    r = client.get(f"{base}/api/stats")
    data = json.loads(r.data)
    return data.get("most_popular", "None")


def solve_005(client, base="/sites/design-creative"):
    r = client.get(f"{base}/api/users/1")
    user = json.loads(r.data)
    return user["name"]


def solve_006(client, base="/sites/design-creative"):
    r = client.get(f"{base}/api/templates?category=logo")
    templates = json.loads(r.data)
    return str(len(templates))


def solve_007(client, base="/sites/design-creative"):
    r = client.get(f"{base}/api/templates?sort=popular&limit=5")
    templates = json.loads(r.data)
    titles = [t["title"] for t in templates]
    return ", ".join(titles)


def solve_008(client, base="/sites/design-creative"):
    r = client.get(f"{base}/api/templates?q=instagram")
    templates = json.loads(r.data)
    return str(len(templates))


def solve_009(client, base="/sites/design-creative"):
    r = client.get(f"{base}/api/assets")
    assets = json.loads(r.data)
    return str(len(assets))


def solve_010(client, base="/sites/design-creative"):
    r = client.get(f"{base}/api/projects?owner_id=1")
    projects = json.loads(r.data)
    return str(len(projects))


def solve_011(client, base="/sites/design-creative"):
    r = client.get(f"{base}/api/templates?category=presentation&sort=popular")
    templates = json.loads(r.data)
    if templates:
        return templates[0]["title"]
    return "None"


def solve_012(client, base="/sites/design-creative"):
    r = client.get(f"{base}/api/categories")
    cats = json.loads(r.data)
    if cats:
        top_cat = max(cats, key=lambda c: c["count"])
        return top_cat["name"]
    return "None"


def solve_013(client, base="/sites/design-creative"):
    r = client.get(f"{base}/api/stats")
    data = json.loads(r.data)
    return str(data.get("total_projects", 0))


def solve_014(client, base="/sites/design-creative"):
    r = client.get(f"{base}/api/templates?sort=name")
    templates = json.loads(r.data)
    if templates:
        return templates[0]["title"]
    return "None"


def solve_015(client, base="/sites/design-creative"):
    client.post(f"{base}/api/login",
                json={"username": "alice_design", "password": "design123"},
                content_type="application/json")
    r = client.post(f"{base}/api/projects",
                     json={"owner_id": 1, "template_id": 6, "title": "My Pitch Deck"},
                     content_type="application/json")
    data = json.loads(r.data)
    return str(data.get("id", ""))


def solve_016(client, base="/sites/design-creative"):
    r = client.post(f"{base}/api/projects",
                     json={"owner_id": 2, "title": "Social Media Kit", "dimensions": "1080x1080"},
                     content_type="application/json")
    data = json.loads(r.data)
    pid = data.get("id")
    r2 = client.put(f"{base}/api/projects/{pid}",
                     json={"status": "completed"},
                     content_type="application/json")
    data2 = json.loads(r2.data)
    return data2.get("status", "")


def solve_017(client, base="/sites/design-creative"):
    client.post(f"{base}/api/login",
                json={"username": "bob_creative", "password": "create456"},
                content_type="application/json")
    r = client.post(f"{base}/api/users/2/favorites",
                     json={"template_id": 1},
                     content_type="application/json")
    data = json.loads(r.data)
    return data.get("action", "")


def solve_018(client, base="/sites/design-creative"):
    r = client.post(f"{base}/api/projects",
                     json={"owner_id": 1, "template_id": 14, "title": "My Logo"},
                     content_type="application/json")
    data = json.loads(r.data)
    pid = data.get("id")
    r2 = client.post(f"{base}/api/projects/{pid}/elements",
                      json={"type": "text", "properties": {"text": "Hello World", "x": 100, "y": 100}},
                      content_type="application/json")
    data2 = json.loads(r2.data)
    return str(data2.get("total_elements", 0))


def solve_019(client, base="/sites/design-creative"):
    r = client.post(f"{base}/api/projects/1/duplicate",
                     content_type="application/json")
    data = json.loads(r.data)
    return data.get("title", "")


def solve_020(client, base="/sites/design-creative"):
    r = client.get(f"{base}/api/templates?sort=popular&limit=1")
    templates = json.loads(r.data)
    if not templates:
        return "None"
    top_tmpl = templates[0]
    tmpl_id = top_tmpl["id"]
    r2 = client.post(f"{base}/api/projects",
                      json={"owner_id": 3, "template_id": tmpl_id, "title": f"From {top_tmpl['title']}"},
                      content_type="application/json")
    data = json.loads(r2.data)
    return data.get("dimensions", "")
