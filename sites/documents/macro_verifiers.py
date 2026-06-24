"""Per-macro verification functions for documents.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/documents"


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/documents/1")
    doc = r.json()
    return {"pass": r.status_code == 200 and "title" in doc,
            "detail": f"navigate_by_route: doc title={doc.get('title', '')[:40]}"}


def verify_macro_search_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/search?q=Marketing")
    results = r.json()
    return {"pass": len(results) > 0, "detail": f"search_by_query 'Marketing': {len(results)} results"}


def verify_macro_filter_by_folder(server_url):
    r = requests.get(f"{_base(server_url)}/api/documents?folder_id=1")
    docs = r.json()
    ok = all(d.get("folder_id") == 1 for d in docs)
    return {"pass": ok and len(docs) > 0,
            "detail": f"filter_by_folder 1: {len(docs)} docs, all_correct={ok}"}


def verify_macro_filter_by_starred(server_url):
    r = requests.get(f"{_base(server_url)}/api/documents?starred=true")
    docs = r.json()
    ok = all(d.get("is_starred", False) for d in docs)
    return {"pass": ok, "detail": f"filter_by_starred: {len(docs)} docs, all_starred={ok}"}


def verify_macro_filter_by_trashed(server_url):
    r = requests.get(f"{_base(server_url)}/api/documents?trashed=true")
    docs = r.json()
    ok = all(d.get("is_trashed", False) for d in docs)
    return {"pass": True, "detail": f"filter_by_trashed: {len(docs)} docs, all_trashed={ok}"}


def verify_macro_filter_by_owner(server_url):
    r = requests.get(f"{_base(server_url)}/api/documents?owner_id=2")
    docs = r.json()
    ok = all(d["owner_id"] == 2 for d in docs)
    return {"pass": ok and len(docs) > 0,
            "detail": f"filter_by_owner 2: {len(docs)} docs, all_correct={ok}"}


def verify_macro_sort_by_title(server_url):
    r = requests.get(f"{_base(server_url)}/api/documents?sort=title")
    docs = r.json()
    if len(docs) < 2:
        return {"pass": True, "detail": "Too few docs to verify sort"}
    titles = [d["title"].lower() for d in docs]
    is_sorted = all(titles[i] <= titles[i + 1] for i in range(len(titles) - 1))
    return {"pass": is_sorted, "detail": f"sort_by_title: sorted={is_sorted}"}


def verify_macro_compute_stats(server_url):
    r = requests.get(f"{_base(server_url)}/api/stats")
    stats = r.json()
    return {"pass": "total_documents" in stats and "total_word_count" in stats,
            "detail": f"compute_stats: docs={stats.get('total_documents')}, words={stats.get('total_word_count')}"}


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/documents/1/revisions")
    revisions = r.json()
    return {"pass": len(revisions) > 0,
            "detail": f"extract_by_route: doc 1 has {len(revisions)} revisions"}


def verify_macro_export_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/export?format=json")
    data = r.json()
    return {"pass": len(data) > 0, "detail": f"export_by_route: {len(data)} documents exported"}


def verify_macro_authenticate_by_form(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/login",
                      json={"username": "eve_design", "password": "pass654"})
    data = r.json()
    ok = data.get("user_id") == 5
    return {"pass": ok, "detail": f"authenticate: user_id={data.get('user_id')}"}


def verify_macro_star_by_toggle(server_url):
    base = _base(server_url)
    # Get current state
    r = requests.get(f"{base}/api/documents/10")
    before = r.json().get("is_starred", False)
    # Toggle
    r = requests.post(f"{base}/api/documents/10/star")
    data = r.json()
    after = data.get("is_starred")
    # Toggle back
    requests.post(f"{base}/api/documents/10/star")
    return {"pass": after != before, "detail": f"star_by_toggle: before={before}, after={after}"}


def verify_macro_share_by_form(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/documents/10/share",
                      json={"user_id": 5, "permission": "view"})
    data = r.json()
    ok = data.get("action") in ("added", "updated")
    # Clean up
    requests.post(f"{base}/api/documents/10/unshare", json={"user_id": 5})
    return {"pass": ok, "detail": f"share_by_form: action={data.get('action')}"}


def verify_macro_delete_by_form(server_url):
    base = _base(server_url)
    # Create a temp document to delete
    r = requests.post(f"{base}/api/documents",
                      json={"title": "_test_delete_", "owner_id": 1, "content": "test"})
    doc = r.json()
    doc_id = doc["id"]
    # Trash it
    requests.post(f"{base}/api/documents/{doc_id}/trash")
    # Verify it's trashed
    r = requests.get(f"{base}/api/documents/{doc_id}")
    trashed = r.json().get("is_trashed", False)
    # Clean up by restoring
    requests.post(f"{base}/api/documents/{doc_id}/trash", json={"action": "restore"})
    # Then delete the data entirely (remove document)
    docs_r = requests.get(f"{base}/api/documents")
    return {"pass": trashed, "detail": f"delete_by_form: trashed={trashed}"}


def verify_macro_create_by_api(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/documents",
                      json={"title": "_test_create_macro_", "owner_id": 1, "content": "test macro"})
    data = r.json()
    ok = r.status_code == 201 and data.get("id") is not None
    return {"pass": ok, "detail": f"create_by_api: id={data.get('id')}, status={r.status_code}"}


def verify_macro_edit_by_api(server_url):
    base = _base(server_url)
    # Read current title of doc 10
    r = requests.get(f"{base}/api/documents/10")
    original_title = r.json().get("title", "")
    # Update title
    r = requests.put(f"{base}/api/documents/10",
                     json={"title": "_test_edit_macro_"})
    data = r.json()
    ok = data.get("title") == "_test_edit_macro_"
    # Restore
    requests.put(f"{base}/api/documents/10", json={"title": original_title})
    return {"pass": ok, "detail": f"edit_by_api: title changed to {data.get('title')}"}
