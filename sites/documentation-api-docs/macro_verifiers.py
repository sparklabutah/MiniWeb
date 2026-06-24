"""Per-macro verification functions for documentation-api-docs.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/documentation-api-docs"


def verify_macro_navigate_by_sidebar(server_url):
    r = requests.get(f"{_base(server_url)}/api/sections")
    sections = r.json()
    if not sections:
        return {"pass": False, "detail": "No sections returned"}
    first_section = sections[0]
    doc_id = first_section["doc_ids"][0]
    r2 = requests.get(f"{_base(server_url)}/api/docs/{doc_id}")
    doc = r2.json()
    return {"pass": r2.status_code == 200 and "slug" in doc,
            "detail": f"Sidebar nav to '{doc.get('title')}': {r2.status_code}"}


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/page/quickstart")
    return {"pass": r.status_code == 200, "detail": f"Direct route /page/quickstart: {r.status_code}"}


def verify_macro_count_by_section(server_url):
    r = requests.get(f"{_base(server_url)}/api/sections")
    sections = r.json()
    for s in sections:
        if s["name"] == "API Reference":
            return {"pass": s["count"] > 0, "detail": f"API Reference has {s['count']} pages"}
    return {"pass": False, "detail": "API Reference section not found"}


def verify_macro_count_by_api(server_url):
    r = requests.get(f"{_base(server_url)}/api/docs")
    docs = r.json()
    return {"pass": len(docs) == 25, "detail": f"Total docs: {len(docs)}"}


def verify_macro_search_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/docs/search?q=instances")
    results = r.json()
    return {"pass": len(results) > 0, "detail": f"Search 'instances': {len(results)} results"}


def verify_macro_list_by_api(server_url):
    r = requests.get(f"{_base(server_url)}/api/sections")
    sections = r.json()
    names = [s["name"] for s in sections]
    return {"pass": len(names) >= 3, "detail": f"Sections: {names}"}


def verify_macro_filter_by_method(server_url):
    r = requests.get(f"{_base(server_url)}/api/endpoints?method=GET")
    get_eps = r.json()
    r2 = requests.get(f"{_base(server_url)}/api/endpoints?method=POST")
    post_eps = r2.json()
    return {"pass": len(get_eps) > 0 and len(post_eps) > 0,
            "detail": f"GET endpoints: {len(get_eps)}, POST endpoints: {len(post_eps)}"}


def verify_macro_filter_by_tag(server_url):
    r = requests.get(f"{_base(server_url)}/api/docs?tag=instances")
    docs = r.json()
    ok = all("instances" in d.get("tags", []) for d in docs)
    return {"pass": ok and len(docs) > 0,
            "detail": f"Tag 'instances': {len(docs)} docs, all_tagged={ok}"}


def verify_macro_extract_from_changelog(server_url):
    r = requests.get(f"{_base(server_url)}/api/changelog")
    entries = r.json()
    if not entries:
        return {"pass": False, "detail": "No changelog entries"}
    return {"pass": "updated_at" in entries[0] and "title" in entries[0],
            "detail": f"Changelog entries: {len(entries)}, latest: {entries[0]['updated_at']}"}


def verify_macro_extract_from_page(server_url):
    r = requests.get(f"{_base(server_url)}/api/docs/2")
    doc = r.json()
    return {"pass": "content" in doc and len(doc["content"]) > 100,
            "detail": f"Auth page content length: {len(doc.get('content', ''))}"}


def verify_macro_extract_by_api(server_url):
    r = requests.get(f"{_base(server_url)}/api/endpoints")
    endpoints = r.json()
    methods = set(e["method"] for e in endpoints)
    return {"pass": len(methods) >= 2, "detail": f"Unique methods: {sorted(methods)}"}


def verify_macro_extract_from_results(server_url):
    r = requests.get(f"{_base(server_url)}/api/docs/search?q=monitoring")
    results = r.json()
    titles = [d["title"] for d in results]
    return {"pass": len(titles) > 0, "detail": f"Search 'monitoring' returned: {titles}"}


def verify_macro_extract_from_dashboard(server_url):
    base = _base(server_url)
    r = requests.get(f"{base}/api/users/2")
    user = r.json()
    return {"pass": "api_key" in user and user["api_key"].startswith("cpk_"),
            "detail": f"User 2 API key: {user.get('api_key', 'N/A')}"}


def verify_macro_authenticate_by_form(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/login",
                      json={"username": "qa_elena", "password": "elena321"})
    data = r.json()
    ok = data.get("user_id") == 5
    return {"pass": ok, "detail": f"Authenticate qa_elena: user_id={data.get('user_id')}"}


def verify_macro_bookmark_by_toggle(server_url):
    base = _base(server_url)
    # Bookmark doc 1
    r = requests.post(f"{base}/api/users/5/bookmark", json={"doc_id": 1})
    data = r.json()
    ok = data.get("action") == "bookmarked"
    # Toggle back (unbookmark)
    requests.post(f"{base}/api/users/5/bookmark", json={"doc_id": 1})
    return {"pass": ok, "detail": f"bookmark_by_toggle: action={data.get('action')}"}
