"""Per-task reference solutions via Flask test client for documents."""
import json


def solve_001(client, base="/sites/documents"):
    r = client.get(f"{base}/api/documents")
    docs = json.loads(r.data)
    return str(len(docs))


def solve_002(client, base="/sites/documents"):
    r = client.get(f"{base}/api/documents/1")
    doc = json.loads(r.data)
    return doc["title"]


def solve_003(client, base="/sites/documents"):
    r = client.get(f"{base}/api/search?q=API")
    results = json.loads(r.data)
    return str(len(results))


def solve_004(client, base="/sites/documents"):
    r = client.get(f"{base}/api/folders")
    folders = json.loads(r.data)
    return str(len(folders))


def solve_005(client, base="/sites/documents"):
    r = client.get(f"{base}/api/documents?folder_id=4")
    docs = json.loads(r.data)
    return str(len(docs))


def solve_006(client, base="/sites/documents"):
    r = client.get(f"{base}/api/documents?starred=true")
    docs = json.loads(r.data)
    return str(len(docs))


def solve_007(client, base="/sites/documents"):
    r = client.get(f"{base}/api/documents?trashed=true")
    docs = json.loads(r.data)
    return str(len(docs))


def solve_008(client, base="/sites/documents"):
    r = client.get(f"{base}/api/documents?sort=title")
    docs = json.loads(r.data)
    return docs[0]["title"] if docs else ""


def solve_009(client, base="/sites/documents"):
    r = client.get(f"{base}/api/stats")
    stats = json.loads(r.data)
    return str(stats["total_word_count"])


def solve_010(client, base="/sites/documents"):
    r = client.get(f"{base}/api/documents/1/revisions")
    revisions = json.loads(r.data)
    return str(len(revisions))


def solve_011(client, base="/sites/documents"):
    r = client.get(f"{base}/api/documents/13")
    doc = json.loads(r.data)
    return str(len(doc.get("collaborators", [])))


def solve_012(client, base="/sites/documents"):
    r = client.get(f"{base}/api/documents?owner_id=1")
    docs = json.loads(r.data)
    return str(len(docs))


def solve_013(client, base="/sites/documents"):
    r = client.get(f"{base}/api/stats")
    stats = json.loads(r.data)
    return str(stats["avg_word_count"])


def solve_014(client, base="/sites/documents"):
    r = client.get(f"{base}/api/search?q=Sprint")
    results = json.loads(r.data)
    return results[0]["title"] if results else "No results"


def solve_015(client, base="/sites/documents"):
    r = client.get(f"{base}/api/export?owner_id=4")
    docs = json.loads(r.data)
    return str(len(docs))


def solve_016(client, base="/sites/documents"):
    client.post(f"{base}/api/login",
                json={"username": "alice_writer", "password": "pass123"})
    r = client.post(f"{base}/api/documents/8/star")
    data = json.loads(r.data)
    return str(data.get("is_starred", "")).lower()


def solve_017(client, base="/sites/documents"):
    client.post(f"{base}/api/login",
                json={"username": "bob_editor", "password": "pass456"})
    r = client.post(f"{base}/api/documents/3/share",
                    json={"user_id": 4, "permission": "edit"})
    data = json.loads(r.data)
    return str(data.get("total_collaborators", ""))


def solve_018(client, base="/sites/documents"):
    client.post(f"{base}/api/login",
                json={"username": "bob_editor", "password": "pass456"})
    # Document 19 is already trashed and owned by bob (user 2)
    # Permanently delete by calling the delete endpoint
    # The form route does permanent deletion; via API we trash then verify 404
    client.post(f"{base}/document/19/delete")
    r = client.get(f"{base}/api/documents/19")
    if r.status_code == 404:
        return "deleted"
    return "still_exists"


def solve_019(client, base="/sites/documents"):
    r = client.post(f"{base}/api/documents",
                    json={
                        "title": "Team Retrospective Notes",
                        "content": "Action items from our latest retrospective meeting.",
                        "owner_id": 3,
                        "folder_id": 2
                    })
    doc = json.loads(r.data)
    return str(doc.get("id", ""))


def solve_020(client, base="/sites/documents"):
    client.post(f"{base}/api/login",
                json={"username": "carol_pm", "password": "pass789"})
    r = client.put(f"{base}/api/documents/6",
                   json={"title": "Updated Onboarding Checklist 2026"})
    doc = json.loads(r.data)
    return doc.get("title", "")
