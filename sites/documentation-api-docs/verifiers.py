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
    r = requests.get(f"{base}/api/docs?section=API+Reference")
    docs = r.json()
    count = len(docs)
    return {"pass": count == 12, "detail": f"API Reference section has {count} pages"}


def verify_003(server_url):
    base = f"{server_url}/sites/documentation-api-docs"
    r = requests.get(f"{base}/api/docs/search?q=pods")
    results = r.json()
    count = len(results)
    return {"pass": count > 0, "detail": f"Search 'pods': {count} results"}


def verify_004(server_url):
    base = f"{server_url}/sites/documentation-api-docs"
    r = requests.get(f"{base}/api/docs/3")
    doc = r.json()
    date = doc.get("updated_at", "")
    return {"pass": date == "2026-06-10", "detail": f"Quickstart updated_at: {date}"}


def verify_005(server_url):
    base = f"{server_url}/sites/documentation-api-docs"
    r = requests.get(f"{base}/api/sections")
    sections = r.json()
    count = len(sections)
    return {"pass": count == 5, "detail": f"Total sections: {count}"}


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
    return {"pass": count == 25, "detail": f"Total docs: {count}"}


def verify_008(server_url):
    base = f"{server_url}/sites/documentation-api-docs"
    r = requests.get(f"{base}/api/docs/search?q=deployments")
    results = r.json()
    if not results:
        return {"pass": False, "detail": "No results for 'deployments'"}
    first_title = results[0]["title"]
    return {"pass": "Deployment" in first_title or "deployment" in first_title.lower(),
            "detail": f"First 'deployments' result: {first_title}"}


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
    return {"pass": count == 3, "detail": f"Changelog: {count} entries, latest: {latest_date}"}


def verify_011(server_url):
    base = f"{server_url}/sites/documentation-api-docs"
    r = requests.get(f"{base}/api/docs?tag=pods")
    docs = r.json()
    count = len(docs)
    return {"pass": count > 0, "detail": f"Pages tagged 'pods': {count}"}


def verify_012(server_url):
    base = f"{server_url}/sites/documentation-api-docs"
    r = requests.get(f"{base}/api/docs/2")
    doc = r.json()
    content = doc.get("content", "")
    has_eks = "EKS" in content
    has_gke = "GKE" in content
    has_aks = "AKS" in content
    return {"pass": has_eks and has_gke and has_aks,
            "detail": f"Install page: EKS={has_eks}, GKE={has_gke}, AKS={has_aks}"}


def verify_013(server_url):
    base = f"{server_url}/sites/documentation-api-docs"
    r = requests.get(f"{base}/api/docs/search?q=namespaces")
    results = r.json()
    if not results:
        return {"pass": False, "detail": "No results for 'namespaces'"}
    # Find the Namespaces concept doc
    ns_doc = next((d for d in results if d["title"] == "Namespaces"), None)
    if not ns_doc:
        return {"pass": False, "detail": "Namespaces concept doc not found in results"}
    has_default = "default" in ns_doc["content"]
    has_kube_system = "kube-system" in ns_doc["content"]
    has_kube_public = "kube-public" in ns_doc["content"]
    has_kube_node_lease = "kube-node-lease" in ns_doc["content"]
    all_found = has_default and has_kube_system and has_kube_public and has_kube_node_lease
    return {"pass": all_found, "detail": f"Namespaces doc has all 4 defaults: {all_found}"}


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
    content = doc.get("content", "")
    has_name = "metadata.name" in content and "Yes" in content
    has_containers = "spec.containers" in content
    has_container_name = "spec.containers[].name" in content
    has_image = "spec.containers[].image" in content
    return {"pass": has_name and has_containers and has_container_name and has_image,
            "detail": f"Create Pod params: name={has_name}, containers={has_containers}, container_name={has_container_name}, image={has_image}"}


def verify_016(server_url):
    base = f"{server_url}/sites/documentation-api-docs"
    r = requests.get(f"{base}/api/users/1")
    user = r.json()
    bookmarks = user.get("bookmarked_pages", [])
    return {"pass": 6 in bookmarks, "detail": f"User 1 bookmarks: {bookmarks}"}


def verify_017(server_url):
    base = f"{server_url}/sites/documentation-api-docs"
    r = requests.get(f"{base}/api/users/3")
    user = r.json()
    bookmarks = user.get("bookmarked_pages", [])
    has_all = 2 in bookmarks and 4 in bookmarks and 5 in bookmarks
    return {"pass": has_all and len(bookmarks) == 3,
            "detail": f"User 3 bookmarks: {bookmarks}"}


def verify_018(server_url):
    base = f"{server_url}/sites/documentation-api-docs"
    r = requests.get(f"{base}/api/users/2")
    user = r.json()
    api_key = user.get("api_key", "")
    return {"pass": api_key == "cpk_live_k1l2m3n4o5p6q7r8s9t0",
            "detail": f"User 2 API key: {api_key}"}


def verify_019(server_url):
    base = f"{server_url}/sites/documentation-api-docs"
    r = requests.get(f"{base}/api/docs/search?q=deployments")
    results = r.json()
    titles = [d["title"] for d in results]
    has_concept = any("Deployments" == t for t in titles)
    has_api = any("Deployment" in t and t != "Deployments" for t in titles)
    return {"pass": has_concept and has_api,
            "detail": f"Search 'deployments' titles: {titles}"}


def verify_020(server_url):
    base = f"{server_url}/sites/documentation-api-docs"
    # Check bookmark
    r = requests.get(f"{base}/api/users/4")
    user = r.json()
    bookmarks = user.get("bookmarked_pages", [])
    has_bookmark = 24 in bookmarks
    # Check DELETE endpoints
    r = requests.get(f"{base}/api/endpoints?method=DELETE")
    endpoints = r.json()
    delete_count = len(endpoints)
    return {"pass": has_bookmark and delete_count > 0,
            "detail": f"User 4 has kubectl bookmark={has_bookmark}, DELETE endpoints={delete_count}"}
