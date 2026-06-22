"""Per-task reference solutions via Flask test client for academic-paper-db."""
import json


def solve_001(client, base="/sites/academic-paper-db"):
    r = client.get(f"{base}/api/categories/cs/papers")
    papers = json.loads(r.data)
    return str(len(papers))


def solve_002(client, base="/sites/academic-paper-db"):
    r = client.get(f"{base}/api/papers/1")
    paper = json.loads(r.data)
    return paper["arxiv_id"]


def solve_003(client, base="/sites/academic-paper-db"):
    r = client.get(f"{base}/api/papers/search?q=quantum")
    return str(len(json.loads(r.data)))


def solve_004(client, base="/sites/academic-paper-db"):
    r = client.get(f"{base}/api/papers/semantic?q=machine+learning+optimization")
    return str(len(json.loads(r.data)))


def solve_005(client, base="/sites/academic-paper-db"):
    r1 = client.get(f"{base}/api/papers?category=math")
    r2 = client.get(f"{base}/api/papers?category=cs")
    math_ids = {p["id"] for p in json.loads(r1.data)}
    cs_ids = {p["id"] for p in json.loads(r2.data)}
    return str(len(math_ids | cs_ids))


def solve_006(client, base="/sites/academic-paper-db"):
    r = client.get(f"{base}/api/papers/1")
    return json.loads(r.data)["title"]


def solve_007(client, base="/sites/academic-paper-db"):
    r = client.get(f"{base}/api/papers/semantic?q=gravity")
    results = json.loads(r.data)
    physics_cats = {"gr-qc", "hep-th", "physics", "astro-ph"}
    physics_count = sum(1 for p in results if any(c.split(".")[0] in physics_cats for c in p["categories"]))
    total = len(results)
    if total == 0:
        return "N/A"
    return f"{physics_count}/{total}"


def solve_008(client, base="/sites/academic-paper-db"):
    r = client.get(f"{base}/api/papers?category=math")
    return str(len(json.loads(r.data)))


def solve_009(client, base="/sites/academic-paper-db"):
    r = client.get(f"{base}/api/papers?date_from=2015&date_to=2020")
    return str(len(json.loads(r.data)))


def solve_010(client, base="/sites/academic-paper-db"):
    r = client.get(f"{base}/api/papers?sort=title")
    papers = json.loads(r.data)
    return papers[0]["title"] if papers else ""


def solve_011(client, base="/sites/academic-paper-db"):
    r = client.get(f"{base}/api/papers/search?q=network")
    results = json.loads(r.data)
    return results[0]["title"] if results else "No results"


def solve_012(client, base="/sites/academic-paper-db"):
    r = client.get(f"{base}/api/categories/cs/stats")
    return str(json.loads(r.data).get("unique_authors", 0))


def solve_013(client, base="/sites/academic-paper-db"):
    r = client.get(f"{base}/api/compare?ids=1,2")
    papers = json.loads(r.data)
    cats = [p["primary_category"] for p in papers]
    return ", ".join(cats)


def solve_014(client, base="/sites/academic-paper-db"):
    r = client.get(f"{base}/api/papers/3")
    return str(json.loads(r.data)["year"])


def solve_015(client, base="/sites/academic-paper-db"):
    r = client.get(f"{base}/api/stats")
    return str(json.loads(r.data)["unique_authors"])


def solve_016(client, base="/sites/academic-paper-db"):
    r = client.get(f"{base}/api/export?format=csv&category=cs")
    lines = r.data.decode().strip().split("\n")
    return str(len(lines) - 1)


def solve_017(client, base="/sites/academic-paper-db"):
    r = client.get(f"{base}/api/export?format=json")
    return str(len(json.loads(r.data)))


def solve_018(client, base="/sites/academic-paper-db"):
    client.post(f"{base}/api/login",
                json={"username": "researcher_alice", "password": "pass123"})
    r = client.post(f"{base}/api/users/1/save", json={"paper_id": 5})
    return json.loads(r.data).get("action", "")


def solve_019(client, base="/sites/academic-paper-db"):
    client.post(f"{base}/api/login",
                json={"username": "prof_bob", "password": "pass456"})
    r = client.get(f"{base}/api/papers/1")
    paper = json.loads(r.data)
    author = paper["authors"][0] if paper.get("authors") else ""
    r = client.post(f"{base}/api/users/2/follow", json={"author": author})
    return json.loads(r.data).get("action", "")


def solve_020(client, base="/sites/academic-paper-db"):
    client.post(f"{base}/api/login",
                json={"username": "grad_carol", "password": "pass789"})
    for pid in [1, 2, 3]:
        client.post(f"{base}/api/users/3/save", json={"paper_id": pid})
    r = client.get(f"{base}/api/users/3")
    user = json.loads(r.data)
    return str(len(user.get("saved_papers", [])))
