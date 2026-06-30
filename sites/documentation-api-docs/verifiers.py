"""Per-task HTTP verification functions for documentation-api-docs."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/documentation-api-docs"
    r = requests.get(f"{base}/api/docs?section=Getting+Started")
    docs = r.json()
    if not docs:
        return {"pass": False, "detail": "No Getting Started docs found"}
    first = docs[0]
    return {"pass": len(first["title"]) > 0, "detail": f"First Getting Started page: {first['title']}"}


def verify_002(server_url):
    base = f"{server_url}/sites/documentation-api-docs"
    r = requests.get(f"{base}/api/sections")
    sections = r.json()
    # Find Workflows, Tasks, Webhooks sections (the API-related ones)
    api_count = sum(s["count"] for s in sections if s["name"] in ("Workflows", "Tasks", "Webhooks"))
    return {"pass": api_count > 0, "detail": f"API-related sections have {api_count} pages"}


def verify_003(server_url):
    base = f"{server_url}/sites/documentation-api-docs"
    r = requests.get(f"{base}/api/docs/search?q=workflow")
    results = r.json()
    count = len(results)
    return {"pass": count > 0, "detail": f"Search 'workflow': {count} results"}


def verify_004(server_url):
    base = f"{server_url}/sites/documentation-api-docs"
    r = requests.get(f"{base}/api/docs/1")
    doc = r.json()
    date = doc.get("updated_at", "")
    return {"pass": date == "2026-06-10", "detail": f"Quickstart updated_at: {date}"}


def verify_005(server_url):
    base = f"{server_url}/sites/documentation-api-docs"
    r = requests.get(f"{base}/api/sections")
    sections = r.json()
    count = len(sections)
    return {"pass": count == 6, "detail": f"Total sections: {count}"}


def verify_006(server_url):
    base = f"{server_url}/sites/documentation-api-docs"
    r = requests.get(f"{base}/api/endpoints?method=GET")
    endpoints = r.json()
    count = len(endpoints)
    return {"pass": count > 0, "detail": f"GET endpoints: {count}"}


def verify_007(server_url):
    base = f"{server_url}/sites/documentation-api-docs"
    r = requests.get(f"{base}/api/docs")
    docs = r.json()
    count = len(docs)
    return {"pass": count == 18, "detail": f"Total docs: {count}"}


def verify_008(server_url):
    base = f"{server_url}/sites/documentation-api-docs"
    r = requests.get(f"{base}/api/docs/search?q=webhook")
    results = r.json()
    if not results:
        return {"pass": False, "detail": "No results for 'webhook'"}
    first_title = results[0]["title"]
    return {"pass": "webhook" in first_title.lower(),
            "detail": f"First 'webhook' result: {first_title}"}


def verify_009(server_url):
    base = f"{server_url}/sites/documentation-api-docs"
    r = requests.get(f"{base}/api/endpoints?method=POST")
    endpoints = r.json()
    count = len(endpoints)
    return {"pass": count > 0, "detail": f"POST endpoints: {count}"}


def verify_010(server_url):
    base = f"{server_url}/sites/documentation-api-docs"
    r = requests.get(f"{base}/api/changelog")
    entries = r.json()
    count = len(entries)
    if not entries:
        return {"pass": False, "detail": "No changelog entries"}
    latest_date = entries[0]["updated_at"]
    return {"pass": count == 1, "detail": f"Changelog: {count} entries, latest: {latest_date}"}


def verify_011(server_url):
    base = f"{server_url}/sites/documentation-api-docs"
    r = requests.get(f"{base}/api/docs?tag=workflows")
    docs = r.json()
    count = len(docs)
    return {"pass": count > 0, "detail": f"Pages tagged 'workflows': {count}"}


def verify_012(server_url):
    base = f"{server_url}/sites/documentation-api-docs"
    r = requests.get(f"{base}/api/docs/2")
    doc = r.json()
    content = doc.get("content", "")
    has_auth = "authentication" in content.lower() or "api" in content.lower()
    return {"pass": has_auth,
            "detail": f"Authentication page describes auth method: {has_auth}"}


def verify_013(server_url):
    base = f"{server_url}/sites/documentation-api-docs"
    r = requests.get(f"{base}/api/docs/search?q=webhooks")
    results = r.json()
    if not results:
        return {"pass": False, "detail": "No results for 'webhooks'"}
    # Find the Webhook Events & Payloads doc
    wh_doc = next((d for d in results if "Events" in d["title"] or "Payloads" in d["title"]), None)
    if not wh_doc:
        return {"pass": False, "detail": "Webhook Events & Payloads doc not found in results"}
    has_events = "event" in wh_doc["content"].lower()
    return {"pass": has_events, "detail": f"Webhook events doc found: {has_events}"}


def verify_014(server_url):
    base = f"{server_url}/sites/documentation-api-docs"
    r = requests.get(f"{base}/api/endpoints")
    endpoints = r.json()
    methods = sorted(set(e["method"] for e in endpoints))
    return {"pass": "GET" in methods and "POST" in methods and "DELETE" in methods and "PUT" in methods,
            "detail": f"API methods: {methods}"}


def verify_015(server_url):
    base = f"{server_url}/sites/documentation-api-docs"
    r = requests.get(f"{base}/api/docs/10")
    doc = r.json()
    title = doc.get("title", "")
    content = doc.get("content", "")
    has_assign = "assign" in title.lower() or "assign" in content.lower()
    return {"pass": has_assign,
            "detail": f"Doc 10 is '{title}', has assign info: {has_assign}"}


def verify_016(server_url):
    base = f"{server_url}/sites/documentation-api-docs"
    r = requests.get(f"{base}/api/users/1")
    user = r.json()
    bookmarks = user.get("bookmarked_pages", [])
    return {"pass": 6 in bookmarks, "detail": f"User 1 bookmarks: {bookmarks}"}


def verify_017(server_url):
    base = f"{server_url}/sites/documentation-api-docs"
    r = requests.get(f"{base}/api/users/2")
    user = r.json()
    bookmarks = user.get("bookmarked_pages", [])
    has_all = 2 in bookmarks and 4 in bookmarks and 5 in bookmarks
    return {"pass": has_all and len(bookmarks) == 3,
            "detail": f"User 2 bookmarks: {bookmarks}"}


def verify_018(server_url):
    base = f"{server_url}/sites/documentation-api-docs"
    r = requests.get(f"{base}/api/users/2")
    user = r.json()
    api_key = user.get("api_key", "")
    return {"pass": api_key == "mf_live_k1l2m3n4o5p6q7r8s9t0",
            "detail": f"User 2 API key: {api_key}"}


def verify_019(server_url):
    base = f"{server_url}/sites/documentation-api-docs"
    r = requests.get(f"{base}/api/docs/search?q=workflow")
    results = r.json()
    titles = [d["title"] for d in results]
    has_workflow = any("Workflow" in t for t in titles)
    return {"pass": has_workflow,
            "detail": f"Search 'workflow' titles: {titles}"}


def verify_020(server_url):
    base = f"{server_url}/sites/documentation-api-docs"
    # Check bookmark
    r = requests.get(f"{base}/api/users/3")
    user = r.json()
    bookmarks = user.get("bookmarked_pages", [])
    has_bookmark = 15 in bookmarks
    # Check DELETE endpoints
    r = requests.get(f"{base}/api/endpoints?method=DELETE")
    endpoints = r.json()
    delete_count = len(endpoints)
    return {"pass": has_bookmark and delete_count > 0,
            "detail": f"User 3 has Python SDK bookmark={has_bookmark}, DELETE endpoints={delete_count}"}
