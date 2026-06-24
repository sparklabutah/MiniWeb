"""Per-task HTTP verification functions for documents."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/documents"
    r = requests.get(f"{base}/api/documents")
    docs = r.json()
    count = len(docs)
    return {"pass": count > 0, "detail": f"Non-trashed documents: {count}"}


def verify_002(server_url):
    base = f"{server_url}/sites/documents"
    r = requests.get(f"{base}/api/documents/1")
    doc = r.json()
    title = doc.get("title", "")
    return {"pass": len(title) > 0, "detail": f"Document 1 title: {title}"}


def verify_003(server_url):
    base = f"{server_url}/sites/documents"
    r = requests.get(f"{base}/api/search?q=API")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Search 'API': {count} results"}


def verify_004(server_url):
    base = f"{server_url}/sites/documents"
    r = requests.get(f"{base}/api/folders")
    folders = r.json()
    count = len(folders)
    return {"pass": count > 0, "detail": f"Total folders: {count}"}


def verify_005(server_url):
    base = f"{server_url}/sites/documents"
    r = requests.get(f"{base}/api/documents?folder_id=4")
    docs = r.json()
    count = len(docs)
    return {"pass": count > 0, "detail": f"Engineering Specs folder docs: {count}"}


def verify_006(server_url):
    base = f"{server_url}/sites/documents"
    r = requests.get(f"{base}/api/documents?starred=true")
    docs = r.json()
    count = len(docs)
    return {"pass": count > 0, "detail": f"Starred documents: {count}"}


def verify_007(server_url):
    base = f"{server_url}/sites/documents"
    r = requests.get(f"{base}/api/documents?trashed=true")
    docs = r.json()
    count = len(docs)
    return {"pass": count >= 0, "detail": f"Trashed documents: {count}"}


def verify_008(server_url):
    base = f"{server_url}/sites/documents"
    r = requests.get(f"{base}/api/documents?sort=title")
    docs = r.json()
    if not docs:
        return {"pass": False, "detail": "No documents returned"}
    first_title = docs[0]["title"]
    titles = [d["title"].lower() for d in docs]
    is_sorted = all(titles[i] <= titles[i + 1] for i in range(len(titles) - 1))
    return {"pass": is_sorted, "detail": f"First title (sorted): {first_title}, sorted={is_sorted}"}


def verify_009(server_url):
    base = f"{server_url}/sites/documents"
    r = requests.get(f"{base}/api/stats")
    stats = r.json()
    total = stats.get("total_word_count", 0)
    return {"pass": total > 0, "detail": f"Total word count: {total}"}


def verify_010(server_url):
    base = f"{server_url}/sites/documents"
    r = requests.get(f"{base}/api/documents/1/revisions")
    revisions = r.json()
    count = len(revisions)
    return {"pass": count > 0, "detail": f"Document 1 revisions: {count}"}


def verify_011(server_url):
    base = f"{server_url}/sites/documents"
    r = requests.get(f"{base}/api/documents/13")
    doc = r.json()
    count = len(doc.get("collaborators", []))
    return {"pass": count > 0, "detail": f"Document 13 collaborators: {count}"}


def verify_012(server_url):
    base = f"{server_url}/sites/documents"
    r = requests.get(f"{base}/api/documents?owner_id=1")
    docs = r.json()
    count = len(docs)
    return {"pass": count > 0, "detail": f"Alice's documents: {count}"}


def verify_013(server_url):
    base = f"{server_url}/sites/documents"
    r = requests.get(f"{base}/api/stats")
    stats = r.json()
    avg = stats.get("avg_word_count", 0)
    return {"pass": avg > 0, "detail": f"Average word count: {avg}"}


def verify_014(server_url):
    base = f"{server_url}/sites/documents"
    r = requests.get(f"{base}/api/search?q=Sprint")
    results = r.json()
    if not results:
        return {"pass": False, "detail": "No results for 'Sprint'"}
    title = results[0]["title"]
    return {"pass": len(title) > 0, "detail": f"First 'Sprint' result: {title}"}


def verify_015(server_url):
    base = f"{server_url}/sites/documents"
    r = requests.get(f"{base}/api/export?owner_id=4")
    docs = r.json()
    count = len(docs)
    return {"pass": count > 0, "detail": f"Dan's exported documents: {count}"}


def verify_016(server_url):
    base = f"{server_url}/sites/documents"
    r = requests.get(f"{base}/api/documents/8")
    doc = r.json()
    starred = doc.get("is_starred", False)
    return {"pass": starred is True, "detail": f"Document 8 is_starred: {starred}"}


def verify_017(server_url):
    base = f"{server_url}/sites/documents"
    r = requests.get(f"{base}/api/documents/3")
    doc = r.json()
    collabs = doc.get("collaborators", [])
    user_ids = [c["user_id"] for c in collabs]
    has_user4 = 4 in user_ids
    return {"pass": has_user4, "detail": f"Document 3 collaborators: {len(collabs)}, user4_present={has_user4}"}


def verify_018(server_url):
    base = f"{server_url}/sites/documents"
    r = requests.get(f"{base}/api/documents/19")
    return {"pass": r.status_code == 404, "detail": f"Document 19 status: {r.status_code}"}


def verify_019(server_url):
    base = f"{server_url}/sites/documents"
    r = requests.get(f"{base}/api/documents")
    docs = r.json()
    matching = [d for d in docs if d["title"] == "Team Retrospective Notes"]
    if not matching:
        return {"pass": False, "detail": "Document 'Team Retrospective Notes' not found"}
    doc = matching[0]
    return {"pass": doc["owner_id"] == 3 and doc.get("folder_id") == 2,
            "detail": f"New doc id={doc['id']}, owner={doc['owner_id']}, folder={doc.get('folder_id')}"}


def verify_020(server_url):
    base = f"{server_url}/sites/documents"
    r = requests.get(f"{base}/api/documents/6")
    doc = r.json()
    title = doc.get("title", "")
    return {"pass": title == "Updated Onboarding Checklist 2026",
            "detail": f"Document 6 title: {title}"}
