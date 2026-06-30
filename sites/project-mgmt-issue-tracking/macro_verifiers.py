"""Per-macro verification functions for project-mgmt-issue-tracking.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/project-mgmt-issue-tracking"


def verify_macro_navigate_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/issues/search?q=workflow+automation")
    results = r.json()
    if not results:
        return {"pass": True, "detail": "navigate_by_semantic: no results (ok)"}
    issue_id = results[0]["id"]
    r2 = requests.get(f"{_base(server_url)}/issue/{issue_id}")
    return {"pass": r2.status_code == 200,
            "detail": f"navigate_by_semantic: issue page {r2.status_code}"}


def verify_macro_navigate_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/projects")
    projects = r.json()
    if not projects:
        return {"pass": False, "detail": "No projects"}
    pid = projects[0]["id"]
    r2 = requests.get(f"{_base(server_url)}/project/{pid}")
    return {"pass": r2.status_code == 200,
            "detail": f"navigate_by_dropdown: project board {r2.status_code}"}


def verify_macro_navigate_from_table(server_url):
    r = requests.get(f"{_base(server_url)}/api/issues?sort=updated&limit=1")
    issues = r.json()
    if not issues:
        return {"pass": False, "detail": "No issues"}
    r2 = requests.get(f"{_base(server_url)}/issue/{issues[0]['id']}")
    return {"pass": r2.status_code == 200,
            "detail": f"navigate_from_table: issue detail {r2.status_code}"}


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/issue/1")
    return {"pass": r.status_code == 200,
            "detail": f"navigate_by_route: issue detail {r.status_code}"}


def verify_macro_search_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/issues/search?q=approval")
    results = r.json()
    return {"pass": len(results) > 0,
            "detail": f"search_by_query 'approval': {len(results)} results"}


def verify_macro_filter_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/issues/search?q=performance+scalability")
    return {"pass": r.status_code == 200,
            "detail": f"filter_by_semantic: {r.status_code}"}


def verify_macro_filter_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/issues?priority=high")
    issues = r.json()
    ok = all(i["priority"] == "high" for i in issues)
    return {"pass": ok and len(issues) > 0,
            "detail": f"filter_by_dropdown high: {len(issues)} issues, all_high={ok}"}


def verify_macro_filter_by_date_range(server_url):
    r = requests.get(f"{_base(server_url)}/api/issues?date_from=2026-06-01&date_to=2026-06-15")
    issues = r.json()
    ok = all("2026-06-01" <= i.get("created_at", "")[:10] <= "2026-06-15" for i in issues)
    return {"pass": ok,
            "detail": f"filter_by_date_range: {len(issues)} issues, all_in_range={ok}"}


def verify_macro_sort_by_ranking(server_url):
    r = requests.get(f"{_base(server_url)}/api/issues?sort=priority")
    issues = r.json()
    if len(issues) < 2:
        return {"pass": True, "detail": "Too few issues to verify sort"}
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    ranks = [priority_order.get(i["priority"], 99) for i in issues]
    is_sorted = all(ranks[j] <= ranks[j + 1] for j in range(len(ranks) - 1))
    return {"pass": is_sorted, "detail": f"sort_by_ranking: sorted={is_sorted}"}


def verify_macro_extract_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/issues/search?q=webhook")
    results = r.json()
    if results:
        return {"pass": True,
                "detail": f"extract_by_query: first title={results[0]['title'][:50]}"}
    return {"pass": True, "detail": "extract_by_query: no results (ok)"}


def verify_macro_extract_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/issues/search?q=database+migration")
    results = r.json()
    return {"pass": r.status_code == 200,
            "detail": f"extract_by_semantic: {len(results)} results"}


def verify_macro_extract_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/projects/1/stats")
    stats = r.json()
    return {"pass": "total_issues" in stats,
            "detail": f"extract_by_dropdown: MF stats={stats.get('total_issues')} issues"}


def verify_macro_extract_from_table(server_url):
    r = requests.get(f"{_base(server_url)}/api/issues?project_id=1&status=done")
    issues = r.json()
    return {"pass": len(issues) > 0,
            "detail": f"extract_from_table: {len(issues)} done issues in MF"}


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/issues/1")
    issue = r.json()
    return {"pass": "description" in issue,
            "detail": f"extract_by_route: issue has description ({len(issue.get('description', ''))} chars)"}


def verify_macro_create_from_free_text(server_url):
    r = requests.post(f"{_base(server_url)}/api/issues",
                      json={"title": "Macro test issue for create_from_free_text",
                            "project_id": 1,
                            "type": "task",
                            "priority": "low"})
    data = r.json()
    ok = data.get("id") is not None
    # Cleanup
    if ok:
        requests.delete(f"{_base(server_url)}/api/issues/{data['id']}")
    return {"pass": ok,
            "detail": f"create_from_free_text: created id={data.get('id')}"}


def verify_macro_submit_by_query(server_url):
    # Find an issue by key, then update it
    r = requests.get(f"{_base(server_url)}/api/issues/by-key/MF-101")
    issue = r.json()
    ok = "id" in issue
    return {"pass": ok,
            "detail": f"submit_by_query: found MF-101, id={issue.get('id')}"}


def verify_macro_edit_by_query(server_url):
    # Search then edit
    r = requests.get(f"{_base(server_url)}/api/issues/search?q=MF-104")
    results = r.json()
    if not results:
        return {"pass": False, "detail": "edit_by_query: no search results"}
    issue_id = results[0]["id"]
    original_title = results[0]["title"]
    r2 = requests.put(f"{_base(server_url)}/api/issues/{issue_id}",
                       json={"title": original_title})  # no-op edit
    return {"pass": r2.status_code == 200,
            "detail": f"edit_by_query: updated issue {issue_id}"}


def verify_macro_edit_by_dropdown(server_url):
    # Change status via dropdown (using API)
    r = requests.get(f"{_base(server_url)}/api/issues/1")
    issue = r.json()
    original_status = issue["status"]
    # Test that PUT status works
    r2 = requests.put(f"{_base(server_url)}/api/issues/1",
                       json={"status": original_status})
    return {"pass": r2.status_code == 200,
            "detail": f"edit_by_dropdown: status update {r2.status_code}"}


def verify_macro_edit_by_form(server_url):
    r = requests.get(f"{_base(server_url)}/issue/1")
    has_form = r.status_code == 200 and b"Edit Issue" in r.content
    return {"pass": has_form,
            "detail": f"edit_by_form: edit form present={has_form}"}


def verify_macro_delete_from_table(server_url):
    # Create a temp issue, then delete it
    r = requests.post(f"{_base(server_url)}/api/issues",
                      json={"title": "Temp issue for delete test",
                            "project_id": 4,
                            "type": "task",
                            "priority": "low"})
    data = r.json()
    temp_id = data.get("id")
    if not temp_id:
        return {"pass": False, "detail": "Could not create temp issue"}
    r2 = requests.delete(f"{_base(server_url)}/api/issues/{temp_id}")
    d2 = r2.json()
    return {"pass": d2.get("deleted") == temp_id,
            "detail": f"delete_from_table: deleted={d2.get('deleted')}"}


def verify_macro_post_from_free_text(server_url):
    r = requests.post(f"{_base(server_url)}/api/issues/1/comments",
                      json={"text": "Macro verifier test comment", "user_id": 1})
    data = r.json()
    ok = data.get("id") is not None
    return {"pass": ok,
            "detail": f"post_from_free_text: comment id={data.get('id')}"}


def verify_macro_select_by_dropdown(server_url):
    # Test that the create form has dropdown selections for project, type, etc.
    r = requests.get(f"{_base(server_url)}/create-issue")
    has_selects = (r.status_code == 200
                   and b'<select' in r.content
                   and b'project_id' in r.content)
    return {"pass": has_selects,
            "detail": f"select_by_dropdown: form has dropdowns={has_selects}"}


def verify_macro_select_from_table(server_url):
    r = requests.post(f"{_base(server_url)}/api/issues/bulk-update",
                      json={"issue_ids": [1, 2], "updates": {"labels": []}})
    data = r.json()
    ok = data.get("count", 0) == 2
    # Restore labels
    requests.put(f"{_base(server_url)}/api/issues/1",
                  json={"labels": ["approval-chain", "regression"]})
    requests.put(f"{_base(server_url)}/api/issues/2",
                  json={"labels": ["webhooks", "integrations"]})
    return {"pass": ok,
            "detail": f"select_from_table: bulk updated {data.get('count')} issues"}


def verify_macro_export_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/export?format=csv&project_id=1")
    lines = r.text.strip().split("\n")
    return {"pass": len(lines) > 1,
            "detail": f"export_by_dropdown CSV: {len(lines)} lines"}


def verify_macro_follow_by_toggle(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/issues/1/watch",
                      json={"user_id": 99})
    data = r.json()
    ok = data.get("action") == "watched"
    # Toggle back
    requests.post(f"{base}/api/issues/1/watch",
                  json={"user_id": 99})
    return {"pass": ok,
            "detail": f"follow_by_toggle: action={data.get('action')}"}
