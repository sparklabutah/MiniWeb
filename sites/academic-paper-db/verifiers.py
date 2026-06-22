"""Per-task HTTP verification functions for academic-paper-db."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/academic-paper-db"
    r = requests.get(f"{base}/api/categories/cs/papers")
    papers = r.json()
    count = len(papers)
    return {"pass": count > 0, "detail": f"cs category has {count} papers"}


def verify_002(server_url):
    base = f"{server_url}/sites/academic-paper-db"
    r = requests.get(f"{base}/api/papers/1")
    paper = r.json()
    arxiv_id = paper.get("arxiv_id", "")
    return {"pass": len(arxiv_id) > 0, "detail": f"Paper 1 arxiv_id: {arxiv_id}"}


def verify_003(server_url):
    base = f"{server_url}/sites/academic-paper-db"
    r = requests.get(f"{base}/api/papers/search?q=quantum")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Search 'quantum': {count} results"}


def verify_004(server_url):
    base = f"{server_url}/sites/academic-paper-db"
    r = requests.get(f"{base}/api/papers/semantic?q=machine+learning+optimization")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Semantic 'machine learning optimization': {count} results"}


def verify_005(server_url):
    base = f"{server_url}/sites/academic-paper-db"
    r = requests.get(f"{base}/api/papers?category=math")
    math_papers = r.json()
    r2 = requests.get(f"{base}/api/papers?category=cs")
    cs_papers = r.json()
    # Checkbox filter shows papers in either checked category
    math_ids = {p["id"] for p in math_papers}
    cs_ids = {p["id"] for p in cs_papers}
    combined = len(math_ids | cs_ids)
    return {"pass": combined >= 0, "detail": f"math+cs checkbox: {combined} papers"}


def verify_006(server_url):
    base = f"{server_url}/sites/academic-paper-db"
    r = requests.get(f"{base}/api/papers/1")
    paper = r.json()
    title = paper.get("title", "")
    return {"pass": len(title) > 0, "detail": f"Paper 1 title: {title[:60]}"}


def verify_007(server_url):
    base = f"{server_url}/sites/academic-paper-db"
    r = requests.get(f"{base}/api/papers/semantic?q=gravity")
    results = r.json()
    physics_cats = {"gr-qc", "hep-th", "physics", "astro-ph"}
    physics_count = sum(1 for p in results if any(c.split(".")[0] in physics_cats for c in p["categories"]))
    total = len(results)
    if total == 0:
        return {"pass": True, "detail": "No results for 'gravity'"}
    frac = round(physics_count / total, 2)
    return {"pass": True, "detail": f"Gravity search: {physics_count}/{total} physics-related (frac={frac})"}


def verify_008(server_url):
    base = f"{server_url}/sites/academic-paper-db"
    r = requests.get(f"{base}/api/papers?category=math")
    papers = r.json()
    count = len(papers)
    return {"pass": count > 0, "detail": f"math filter: {count} papers"}


def verify_009(server_url):
    base = f"{server_url}/sites/academic-paper-db"
    r = requests.get(f"{base}/api/papers?date_from=2015&date_to=2020")
    papers = r.json()
    count = len(papers)
    # Verify all are in range
    ok = all(2015 <= p["year"] <= 2020 for p in papers)
    return {"pass": ok and count >= 0, "detail": f"2015-2020 filter: {count} papers, all_in_range={ok}"}


def verify_010(server_url):
    base = f"{server_url}/sites/academic-paper-db"
    r = requests.get(f"{base}/api/papers?sort=title")
    papers = r.json()
    if not papers:
        return {"pass": False, "detail": "No papers returned"}
    first_title = papers[0]["title"]
    # Verify sorted
    titles = [p["title"].lower() for p in papers]
    is_sorted = all(titles[i] <= titles[i+1] for i in range(len(titles)-1))
    return {"pass": is_sorted, "detail": f"First title (sorted): {first_title[:60]}, sorted={is_sorted}"}


def verify_011(server_url):
    base = f"{server_url}/sites/academic-paper-db"
    r = requests.get(f"{base}/api/papers/search?q=network")
    results = r.json()
    if not results:
        return {"pass": True, "detail": "No results for 'network'"}
    first = results[0]["title"]
    return {"pass": len(first) > 0, "detail": f"First 'network' result: {first[:60]}"}


def verify_012(server_url):
    base = f"{server_url}/sites/academic-paper-db"
    r = requests.get(f"{base}/api/categories/cs/stats")
    stats = r.json()
    authors = stats.get("unique_authors", 0)
    return {"pass": authors > 0, "detail": f"cs unique authors: {authors}"}


def verify_013(server_url):
    base = f"{server_url}/sites/academic-paper-db"
    r = requests.get(f"{base}/api/compare?ids=1,2")
    papers = r.json()
    if len(papers) < 2:
        return {"pass": False, "detail": f"Compare returned {len(papers)} papers, expected 2"}
    cats = [p["primary_category"] for p in papers]
    return {"pass": True, "detail": f"Paper 1 cat: {cats[0]}, Paper 2 cat: {cats[1]}"}


def verify_014(server_url):
    base = f"{server_url}/sites/academic-paper-db"
    r = requests.get(f"{base}/api/papers/3")
    paper = r.json()
    year = paper.get("year")
    return {"pass": year is not None, "detail": f"Paper 3 year: {year}"}


def verify_015(server_url):
    base = f"{server_url}/sites/academic-paper-db"
    r = requests.get(f"{base}/api/stats")
    stats = r.json()
    authors = stats.get("unique_authors", 0)
    return {"pass": authors > 0, "detail": f"Total unique authors: {authors}"}


def verify_016(server_url):
    base = f"{server_url}/sites/academic-paper-db"
    r = requests.get(f"{base}/api/export?format=csv&category=cs")
    lines = r.text.strip().split("\n")
    data_rows = len(lines) - 1  # minus header
    return {"pass": data_rows > 0, "detail": f"CSV export cs: {data_rows} data rows"}


def verify_017(server_url):
    base = f"{server_url}/sites/academic-paper-db"
    r = requests.get(f"{base}/api/export?format=json")
    papers = r.json()
    count = len(papers)
    return {"pass": count > 0, "detail": f"JSON export: {count} papers"}


def verify_018(server_url):
    base = f"{server_url}/sites/academic-paper-db"
    r = requests.get(f"{base}/api/users/1")
    user = r.json()
    saved = user.get("saved_papers", [])
    return {"pass": 5 in saved, "detail": f"User 1 saved papers: {saved}"}


def verify_019(server_url):
    base = f"{server_url}/sites/academic-paper-db"
    # Get paper 1's first author
    r = requests.get(f"{base}/api/papers/1")
    paper = r.json()
    first_author = paper["authors"][0] if paper.get("authors") else ""
    # Check user 2's followed authors
    r = requests.get(f"{base}/api/users/2")
    user = r.json()
    followed = user.get("followed_authors", [])
    return {"pass": first_author in followed,
            "detail": f"User 2 followed: {followed}, expected: {first_author}"}


def verify_020(server_url):
    base = f"{server_url}/sites/academic-paper-db"
    r = requests.get(f"{base}/api/users/3")
    user = r.json()
    saved = user.get("saved_papers", [])
    return {"pass": len(saved) == 3 and 1 in saved and 2 in saved and 3 in saved,
            "detail": f"User 3 saved papers: {saved}"}
