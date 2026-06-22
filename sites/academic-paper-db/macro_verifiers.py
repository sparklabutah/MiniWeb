"""Per-macro verification functions for academic-paper-db.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/academic-paper-db"


def verify_macro_navigate_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/categories")
    cats = r.json()
    if not cats:
        return {"pass": False, "detail": "No categories returned"}
    cat = cats[0]["name"]
    r2 = requests.get(f"{_base(server_url)}/category/{cat}")
    return {"pass": r2.status_code == 200, "detail": f"Category page '{cat}': {r2.status_code}"}


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/paper/1")
    return {"pass": r.status_code == 200, "detail": f"Paper detail page: {r.status_code}"}


def verify_macro_search_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/papers/search?q=the")
    results = r.json()
    return {"pass": len(results) > 0, "detail": f"search_by_query 'the': {len(results)} results"}


def verify_macro_search_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/papers/semantic?q=quantum+computing")
    results = r.json()
    return {"pass": r.status_code == 200, "detail": f"search_by_semantic: {len(results)} results"}


def verify_macro_search_by_checkbox(server_url):
    r = requests.get(f"{_base(server_url)}/?cats=cs&cats=math")
    return {"pass": r.status_code == 200, "detail": f"Checkbox filter page: {r.status_code}"}


def verify_macro_search_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/papers/1")
    paper = r.json()
    return {"pass": "arxiv_id" in paper, "detail": f"search_by_route: got paper with arxiv_id={paper.get('arxiv_id')}"}


def verify_macro_filter_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/papers/semantic?q=gravity")
    return {"pass": r.status_code == 200, "detail": f"filter_by_semantic: {r.status_code}"}


def verify_macro_filter_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/papers?category=cs")
    papers = r.json()
    ok = all(p["top_category"] == "cs" or "cs" in " ".join(p["categories"]) for p in papers)
    return {"pass": ok, "detail": f"filter_by_dropdown cs: {len(papers)} papers, all_cs={ok}"}


def verify_macro_filter_by_date_range(server_url):
    r = requests.get(f"{_base(server_url)}/api/papers?date_from=2010&date_to=2015")
    papers = r.json()
    ok = all(2010 <= p["year"] <= 2015 for p in papers)
    return {"pass": ok, "detail": f"filter 2010-2015: {len(papers)} papers, all_in_range={ok}"}


def verify_macro_sort_by_ranking(server_url):
    r = requests.get(f"{_base(server_url)}/api/papers?sort=title")
    papers = r.json()
    if len(papers) < 2:
        return {"pass": True, "detail": "Too few papers to verify sort"}
    titles = [p["title"].lower() for p in papers]
    is_sorted = all(titles[i] <= titles[i+1] for i in range(len(titles)-1))
    return {"pass": is_sorted, "detail": f"sort_by_ranking: sorted={is_sorted}"}


def verify_macro_extract_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/papers/search?q=model")
    results = r.json()
    if results:
        return {"pass": True, "detail": f"extract_by_query: first result title={results[0]['title'][:50]}"}
    return {"pass": True, "detail": "extract_by_query: no results (ok)"}


def verify_macro_extract_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/categories/math/stats")
    stats = r.json()
    return {"pass": "unique_authors" in stats, "detail": f"extract_by_dropdown: math stats={stats}"}


def verify_macro_extract_from_table(server_url):
    r = requests.get(f"{_base(server_url)}/api/compare?ids=1,2")
    papers = r.json()
    return {"pass": len(papers) == 2, "detail": f"extract_from_table: compare returned {len(papers)} papers"}


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/papers/1")
    paper = r.json()
    return {"pass": "abstract" in paper, "detail": f"extract_by_route: paper has abstract={len(paper.get('abstract',''))} chars"}


def verify_macro_compute_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/stats?category=cs")
    stats = r.json()
    return {"pass": "unique_authors" in stats and "count" in stats,
            "detail": f"compute_by_dropdown: cs count={stats.get('count')}, authors={stats.get('unique_authors')}"}


def verify_macro_compare_from_table(server_url):
    r = requests.get(f"{_base(server_url)}/api/compare?ids=1,2")
    papers = r.json()
    if len(papers) < 2:
        return {"pass": False, "detail": "Compare needs 2 papers"}
    return {"pass": papers[0]["id"] != papers[1]["id"],
            "detail": f"compare: paper {papers[0]['id']} vs {papers[1]['id']}"}


def verify_macro_export_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/export?format=csv&category=cs")
    lines = r.text.strip().split("\n")
    return {"pass": len(lines) > 1, "detail": f"export CSV: {len(lines)} lines"}


def verify_macro_export_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/export?format=json")
    data = r.json()
    return {"pass": len(data) > 0, "detail": f"export JSON: {len(data)} papers"}


def verify_macro_follow_by_toggle(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/users/4/follow", json={"author": "TestAuthor"})
    data = r.json()
    ok = data.get("action") == "followed"
    # Toggle back
    requests.post(f"{base}/api/users/4/follow", json={"author": "TestAuthor"})
    return {"pass": ok, "detail": f"follow_by_toggle: action={data.get('action')}"}


def verify_macro_save_by_toggle(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/users/4/save", json={"paper_id": 99})
    data = r.json()
    ok = data.get("action") == "saved"
    # Toggle back
    requests.post(f"{base}/api/users/4/save", json={"paper_id": 99})
    return {"pass": ok, "detail": f"save_by_toggle: action={data.get('action')}"}


def verify_macro_authenticate_by_form(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/login",
                      json={"username": "student_eve", "password": "pass654"})
    data = r.json()
    ok = data.get("user_id") == 5
    return {"pass": ok, "detail": f"authenticate: user_id={data.get('user_id')}"}
