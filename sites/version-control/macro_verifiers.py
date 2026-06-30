"""Per-macro verification functions for version-control.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/version-control"


def verify_macro_navigate_by_dropdown(server_url):
    """Navigate to repos page filtered by language dropdown."""
    r = requests.get(f"{_base(server_url)}/api/repos?language=Python")
    data = r.json()
    repos = data.get("repos", [])
    ok = all("Python" in r.get("tech_stack", []) for r in repos)
    return {"pass": ok and len(repos) > 0,
            "detail": f"navigate_by_dropdown: Python filter returned {len(repos)} repos, all_python={ok}"}


def verify_macro_navigate_by_route(server_url):
    """Navigate to a repo detail page by route."""
    r = requests.get(f"{_base(server_url)}/repo/1001")
    return {"pass": r.status_code == 200,
            "detail": f"navigate_by_route: repo detail page status={r.status_code}"}


def verify_macro_search_by_query(server_url):
    """Search across repos, users, activities by keyword."""
    r = requests.get(f"{_base(server_url)}/api/search?q=meridian")
    data = r.json()
    repos = data.get("repos", [])
    return {"pass": len(repos) > 0,
            "detail": f"search_by_query 'meridian': {len(repos)} repos"}


def verify_macro_search_by_semantic(server_url):
    """Semantic search with relevance scoring."""
    r = requests.get(f"{_base(server_url)}/api/search/semantic?q=workflow+automation")
    data = r.json()
    repos = data.get("repos", [])
    has_scores = all("relevance_score" in r for r in repos) if repos else True
    return {"pass": r.status_code == 200 and has_scores,
            "detail": f"search_by_semantic: {len(repos)} repos, all have scores={has_scores}"}


def verify_macro_search_by_code(server_url):
    """Search within file contents across repositories."""
    r = requests.get(f"{_base(server_url)}/api/search/code?q=fastapi")
    data = r.json()
    results = data.get("results", [])
    return {"pass": len(results) > 0,
            "detail": f"search_by_code 'fastapi': {len(results)} file matches"}


def verify_macro_filter_by_dropdown(server_url):
    """Filter repos by language dropdown."""
    r = requests.get(f"{_base(server_url)}/api/repos?language=Go")
    data = r.json()
    repos = data.get("repos", [])
    ok = all("Go" in r.get("tech_stack", []) for r in repos)
    return {"pass": ok,
            "detail": f"filter_by_dropdown Go: {len(repos)} repos, all_go={ok}"}


def verify_macro_sort_by_ranking(server_url):
    """Sort repos by name, stars, or updated."""
    r = requests.get(f"{_base(server_url)}/api/repos?sort=name")
    data = r.json()
    repos = data.get("repos", [])
    if len(repos) < 2:
        return {"pass": True, "detail": "Too few repos to verify sort"}
    names = [r["name"].lower() for r in repos]
    is_sorted = all(names[i] <= names[i + 1] for i in range(len(names) - 1))
    return {"pass": is_sorted,
            "detail": f"sort_by_ranking: sorted by name={is_sorted}"}


def verify_macro_extract_by_query(server_url):
    """Search and extract specific information from results."""
    r = requests.get(f"{_base(server_url)}/api/search?q=webhook")
    data = r.json()
    activities = data.get("activities", [])
    if activities:
        msg = activities[0].get("commit_message", "") or activities[0].get("merge_request_title", "")
        return {"pass": len(msg) > 0,
                "detail": f"extract_by_query: first result msg={msg[:50]}"}
    return {"pass": True, "detail": "extract_by_query: no webhook activities (ok)"}


def verify_macro_extract_by_semantic(server_url):
    """Extract information from semantic search results."""
    r = requests.get(f"{_base(server_url)}/api/search/semantic?q=database+connection+pooling")
    data = r.json()
    repos = data.get("repos", [])
    return {"pass": r.status_code == 200,
            "detail": f"extract_by_semantic: {len(repos)} repos matched"}


def verify_macro_extract_from_table(server_url):
    """Extract data from compare table."""
    r = requests.get(f"{_base(server_url)}/api/repos/compare?ids=1001,1002")
    data = r.json()
    repos = data.get("repos", [])
    return {"pass": len(repos) == 2,
            "detail": f"extract_from_table: compare returned {len(repos)} repos"}


def verify_macro_extract_by_route(server_url):
    """Extract data from a specific route (repo detail)."""
    r = requests.get(f"{_base(server_url)}/api/repos/1001")
    repo = r.json()
    has_fields = "name" in repo and "description" in repo and "commits" in repo
    return {"pass": has_fields,
            "detail": f"extract_by_route: repo 1001 has name/description/commits={has_fields}"}


def verify_macro_compare_from_table(server_url):
    """Compare repos side-by-side."""
    r = requests.get(f"{_base(server_url)}/api/repos/compare?ids=1001,1002")
    data = r.json()
    repos = data.get("repos", [])
    if len(repos) < 2:
        return {"pass": False, "detail": "Compare needs 2 repos"}
    has_metrics = all("commit_count" in r and "open_issues" in r for r in repos)
    return {"pass": repos[0]["id"] != repos[1]["id"] and has_metrics,
            "detail": f"compare_from_table: {repos[0]['name']} vs {repos[1]['name']}, metrics={has_metrics}"}


def verify_macro_create_from_free_text(server_url):
    """Create a new repository."""
    r = requests.post(
        f"{_base(server_url)}/api/repos",
        json={"name": "macro-test-repo", "description": "Macro verifier test", "visibility": "private"},
    )
    data = r.json()
    ok = data.get("name") == "macro-test-repo"
    # Clean up: delete
    if ok:
        requests.delete(f"{_base(server_url)}/api/repos/{data['id']}")
    return {"pass": ok,
            "detail": f"create_from_free_text: created name={data.get('name')}, id={data.get('id')}"}


def verify_macro_submit_by_form(server_url):
    """Submit a new issue via form/API."""
    r = requests.post(
        f"{_base(server_url)}/api/repos/1001/issues",
        json={"title": "Macro test issue", "labels": ["test"]},
    )
    data = r.json()
    ok = data.get("title") == "Macro test issue" and data.get("state") == "open"
    return {"pass": ok,
            "detail": f"submit_by_form: issue id={data.get('id')}, title={data.get('title')}"}


def verify_macro_edit_by_form(server_url):
    """Edit an existing issue."""
    # First create, then edit
    r = requests.post(
        f"{_base(server_url)}/api/repos/1001/issues",
        json={"title": "Edit test issue"},
    )
    issue = r.json()
    issue_id = issue.get("id")

    r2 = requests.put(
        f"{_base(server_url)}/api/repos/1001/issues/{issue_id}",
        json={"state": "closed"},
    )
    updated = r2.json()
    ok = updated.get("state") == "closed"
    return {"pass": ok,
            "detail": f"edit_by_form: issue {issue_id} state={updated.get('state')}"}


def verify_macro_upload_by_upload(server_url):
    """Upload a file to a repository."""
    import io
    files = {"file": ("test_macro.txt", io.BytesIO(b"macro test content"), "text/plain")}
    data = {"path": "test_macro.txt", "commit_message": "Macro verifier upload"}
    r = requests.post(f"{_base(server_url)}/api/repos/1001/upload", files=files, data=data)
    result = r.json()
    ok = result.get("path") == "test_macro.txt"
    return {"pass": ok,
            "detail": f"upload_by_upload: path={result.get('path')}, size={result.get('size')}"}


def verify_macro_select_by_dropdown(server_url):
    """Select a value from dropdown (repo settings)."""
    r = requests.put(
        f"{_base(server_url)}/api/repos/1007/settings",
        json={"visibility": "public"},
    )
    data = r.json()
    changed = data.get("changes", {}).get("visibility", {})
    ok = changed.get("new") == "public"
    # Restore
    requests.put(
        f"{_base(server_url)}/api/repos/1007/settings",
        json={"visibility": "private"},
    )
    return {"pass": ok,
            "detail": f"select_by_dropdown: visibility changed to {changed.get('new')}"}


def verify_macro_export_by_route(server_url):
    """Export data via route (JSON or CSV)."""
    r = requests.get(f"{_base(server_url)}/api/export/repos?format=json")
    data = r.json()
    ok = len(data) > 0
    # Also test CSV
    r2 = requests.get(f"{_base(server_url)}/api/export/repos?format=csv")
    csv_lines = r2.text.strip().split("\n")
    csv_ok = len(csv_lines) > 1
    return {"pass": ok and csv_ok,
            "detail": f"export_by_route: JSON={len(data)} repos, CSV={len(csv_lines)} lines"}


def verify_macro_post_from_free_text(server_url):
    """Post a free-text comment on an issue."""
    r = requests.post(
        f"{_base(server_url)}/api/repos/1001/issues/1/comments",
        json={"body": "Macro verifier test comment", "author": "test_bot"},
    )
    data = r.json()
    ok = "macro verifier test comment" in data.get("body", "").lower()
    return {"pass": ok,
            "detail": f"post_from_free_text: comment id={data.get('id')}, body={data.get('body', '')[:40]}"}


def verify_macro_follow_by_toggle(server_url):
    """Toggle star on a repository."""
    s = requests.Session()
    r = s.post(f"{_base(server_url)}/api/repos/1006/star")
    data = r.json()
    starred = data.get("starred")
    # Toggle back
    s.post(f"{_base(server_url)}/api/repos/1006/star")
    return {"pass": starred is True,
            "detail": f"follow_by_toggle: starred={starred}, stars={data.get('stars')}"}
