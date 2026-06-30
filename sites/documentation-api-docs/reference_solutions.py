"""Per-task reference solutions via Flask test client for documentation-api-docs."""
import json


def solve_001(client, base="/sites/documentation-api-docs"):
    r = client.get(f"{base}/api/docs?section=Getting+Started")
    docs = json.loads(r.data)
    return docs[0]["title"] if docs else ""


def solve_002(client, base="/sites/documentation-api-docs"):
    r = client.get(f"{base}/api/sections")
    sections = json.loads(r.data)
    api_count = sum(s["count"] for s in sections if s["name"] in ("Workflows", "Tasks", "Webhooks"))
    return str(api_count)


def solve_003(client, base="/sites/documentation-api-docs"):
    r = client.get(f"{base}/api/docs/search?q=workflow")
    return str(len(json.loads(r.data)))


def solve_004(client, base="/sites/documentation-api-docs"):
    r = client.get(f"{base}/api/docs/1")
    doc = json.loads(r.data)
    return doc["updated_at"]


def solve_005(client, base="/sites/documentation-api-docs"):
    r = client.get(f"{base}/api/sections")
    return str(len(json.loads(r.data)))


def solve_006(client, base="/sites/documentation-api-docs"):
    r = client.get(f"{base}/api/endpoints?method=GET")
    return str(len(json.loads(r.data)))


def solve_007(client, base="/sites/documentation-api-docs"):
    r = client.get(f"{base}/api/docs")
    return str(len(json.loads(r.data)))


def solve_008(client, base="/sites/documentation-api-docs"):
    r = client.get(f"{base}/api/docs/search?q=webhook")
    results = json.loads(r.data)
    return results[0]["title"] if results else "No results"


def solve_009(client, base="/sites/documentation-api-docs"):
    r = client.get(f"{base}/api/endpoints?method=POST")
    return str(len(json.loads(r.data)))


def solve_010(client, base="/sites/documentation-api-docs"):
    r = client.get(f"{base}/api/changelog")
    entries = json.loads(r.data)
    count = len(entries)
    latest = entries[0]["updated_at"] if entries else "N/A"
    return f"{count} entries, latest: {latest}"


def solve_011(client, base="/sites/documentation-api-docs"):
    r = client.get(f"{base}/api/docs?tag=workflows")
    return str(len(json.loads(r.data)))


def solve_012(client, base="/sites/documentation-api-docs"):
    r = client.get(f"{base}/api/docs/2")
    doc = json.loads(r.data)
    return doc["title"]


def solve_013(client, base="/sites/documentation-api-docs"):
    r = client.get(f"{base}/api/docs/search?q=webhooks")
    results = json.loads(r.data)
    for d in results:
        if "Events" in d["title"]:
            return d["title"]
    return "N/A"


def solve_014(client, base="/sites/documentation-api-docs"):
    r = client.get(f"{base}/api/endpoints")
    endpoints = json.loads(r.data)
    methods = sorted(set(e["method"] for e in endpoints))
    return ", ".join(methods)


def solve_015(client, base="/sites/documentation-api-docs"):
    r = client.get(f"{base}/api/docs/10")
    doc = json.loads(r.data)
    return doc["title"]


def solve_016(client, base="/sites/documentation-api-docs"):
    client.post(f"{base}/api/login",
                json={"username": "dev_alex", "password": "mflow_docs1"})
    r = client.post(f"{base}/api/users/1/bookmark", json={"doc_id": 6})
    return json.loads(r.data).get("action", "")


def solve_017(client, base="/sites/documentation-api-docs"):
    client.post(f"{base}/api/login",
                json={"username": "mgr_priya", "password": "mflow_docs2"})
    for doc_id in [2, 4, 5]:
        client.post(f"{base}/api/users/2/bookmark", json={"doc_id": doc_id})
    r = client.get(f"{base}/api/users/2")
    user = json.loads(r.data)
    return str(len(user.get("bookmarked_pages", [])))


def solve_018(client, base="/sites/documentation-api-docs"):
    client.post(f"{base}/api/login",
                json={"username": "mgr_priya", "password": "mflow_docs2"})
    r = client.get(f"{base}/api/users/2")
    user = json.loads(r.data)
    return user.get("api_key", "")


def solve_019(client, base="/sites/documentation-api-docs"):
    r = client.get(f"{base}/api/docs/search?q=workflow")
    results = json.loads(r.data)
    titles = [d["title"] for d in results]
    return ", ".join(titles)


def solve_020(client, base="/sites/documentation-api-docs"):
    client.post(f"{base}/api/login",
                json={"username": "dev_marcus", "password": "mflow_docs3"})
    r = client.post(f"{base}/api/users/3/bookmark", json={"doc_id": 15})
    bookmark_result = json.loads(r.data)
    r2 = client.get(f"{base}/api/endpoints?method=DELETE")
    delete_eps = json.loads(r2.data)
    return f"bookmark={bookmark_result.get('action')}, DELETE_endpoints={len(delete_eps)}"
