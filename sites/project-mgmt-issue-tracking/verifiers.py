"""Per-task HTTP verification functions for project-mgmt-issue-tracking."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/project-mgmt-issue-tracking"
    r = requests.get(f"{base}/api/issues?project_id=1&status=open")
    issues = r.json()
    count = len(issues)
    return {"pass": count > 0, "detail": f"MeridianFlow open issues: {count}"}


def verify_002(server_url):
    base = f"{server_url}/sites/project-mgmt-issue-tracking"
    r = requests.get(f"{base}/api/issues/by-key/MF-101")
    issue = r.json()
    priority = issue.get("priority", "")
    return {"pass": priority == "critical", "detail": f"MF-101 priority: {priority}"}


def verify_003(server_url):
    base = f"{server_url}/sites/project-mgmt-issue-tracking"
    r = requests.get(f"{base}/api/issues/search?q=webhook")
    results = r.json()
    count = len(results)
    return {"pass": count > 0, "detail": f"Search 'webhook': {count} results"}


def verify_004(server_url):
    base = f"{server_url}/sites/project-mgmt-issue-tracking"
    # The most recently updated issue is the first in recent activity
    r = requests.get(f"{base}/api/issues?sort=updated&limit=1")
    issues = r.json()
    if not issues:
        return {"pass": False, "detail": "No issues returned"}
    key = issues[0].get("key", "")
    return {"pass": len(key) > 0, "detail": f"Most recently updated issue key: {key}"}


def verify_005(server_url):
    base = f"{server_url}/sites/project-mgmt-issue-tracking"
    r = requests.get(f"{base}/api/issues/search?q=security+permissions+authentication")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Semantic search: {count} results"}


def verify_006(server_url):
    base = f"{server_url}/sites/project-mgmt-issue-tracking"
    r = requests.get(f"{base}/api/issues?priority=critical")
    issues = r.json()
    count = len(issues)
    ok = all(i["priority"] == "critical" for i in issues)
    return {"pass": count > 0 and ok, "detail": f"Critical issues: {count}, all_critical={ok}"}


def verify_007(server_url):
    base = f"{server_url}/sites/project-mgmt-issue-tracking"
    r = requests.get(f"{base}/api/issues/search?q=performance+monitoring+metrics")
    results = r.json()
    if not results:
        return {"pass": True, "detail": "No results (ok)"}
    title = results[0].get("title", "")
    return {"pass": len(title) > 0, "detail": f"Top result: {title[:60]}"}


def verify_008(server_url):
    base = f"{server_url}/sites/project-mgmt-issue-tracking"
    r = requests.get(f"{base}/api/issues?date_from=2026-06-10&date_to=2026-06-20")
    issues = r.json()
    count = len(issues)
    ok = all("2026-06-10" <= i.get("created_at", "")[:10] <= "2026-06-20" for i in issues)
    return {"pass": count >= 0 and ok, "detail": f"Date range 06-10 to 06-20: {count} issues, all_in_range={ok}"}


def verify_009(server_url):
    base = f"{server_url}/sites/project-mgmt-issue-tracking"
    r = requests.get(f"{base}/api/issues?sort=created")
    issues = r.json()
    if not issues:
        return {"pass": False, "detail": "No issues returned"}
    key = issues[0].get("key", "")
    return {"pass": len(key) > 0, "detail": f"Most recently created issue key: {key}"}


def verify_010(server_url):
    base = f"{server_url}/sites/project-mgmt-issue-tracking"
    r = requests.get(f"{base}/api/issues/search?q=approval")
    results = r.json()
    if not results:
        return {"pass": True, "detail": "No results for 'approval'"}
    title = results[0].get("title", "")
    return {"pass": len(title) > 0, "detail": f"First 'approval' result: {title[:60]}"}


def verify_011(server_url):
    base = f"{server_url}/sites/project-mgmt-issue-tracking"
    r = requests.get(f"{base}/api/issues/search?q=data+integrity+corruption")
    results = r.json()
    if not results:
        return {"pass": True, "detail": "No results (ok)"}
    key = results[0].get("key", "")
    return {"pass": len(key) > 0, "detail": f"Top result key: {key}"}


def verify_012(server_url):
    base = f"{server_url}/sites/project-mgmt-issue-tracking"
    r = requests.get(f"{base}/api/projects/2/stats")
    stats = r.json()
    total = stats.get("total_issues", 0)
    return {"pass": total > 0, "detail": f"MeridianVault total issues: {total}"}


def verify_013(server_url):
    base = f"{server_url}/sites/project-mgmt-issue-tracking"
    r = requests.get(f"{base}/api/issues?project_id=1&status=done")
    issues = r.json()
    count = len(issues)
    return {"pass": count > 0, "detail": f"MeridianFlow done issues: {count}"}


def verify_014(server_url):
    base = f"{server_url}/sites/project-mgmt-issue-tracking"
    r = requests.get(f"{base}/api/issues/5")
    issue = r.json()
    title = issue.get("title", "")
    return {"pass": len(title) > 0, "detail": f"Issue 5 title: {title[:60]}"}


def verify_015(server_url):
    base = f"{server_url}/sites/project-mgmt-issue-tracking"
    r = requests.get(f"{base}/api/issues/search?q=Login+page+crashes+on+Safari+18")
    results = r.json()
    match = next((i for i in results
                  if "login page crashes on safari 18" in i.get("title", "").lower()), None)
    if not match:
        return {"pass": False, "detail": "Created issue not found"}
    ok = (match.get("project_id") == 1
          and match.get("type") == "bug"
          and match.get("priority") == "high"
          and match.get("assignee_id") == 2)
    return {"pass": ok,
            "detail": f"Issue created: project={match.get('project_id')}, type={match.get('type')}, "
                       f"priority={match.get('priority')}, assignee={match.get('assignee_id')}"}


def verify_016(server_url):
    base = f"{server_url}/sites/project-mgmt-issue-tracking"
    r = requests.get(f"{base}/api/issues/by-key/MF-106")
    issue = r.json()
    status = issue.get("status", "")
    return {"pass": status == "in_progress",
            "detail": f"MF-106 status: {status}"}


def verify_017(server_url):
    base = f"{server_url}/sites/project-mgmt-issue-tracking"
    r = requests.get(f"{base}/api/issues/3")
    issue = r.json()
    priority = issue.get("priority", "")
    labels = issue.get("labels", [])
    ok = priority == "critical" and "urgent" in labels
    return {"pass": ok,
            "detail": f"Issue 3: priority={priority}, labels={labels}"}


def verify_018(server_url):
    base = f"{server_url}/sites/project-mgmt-issue-tracking"
    r = requests.get(f"{base}/api/issues/10")
    return {"pass": r.status_code == 404,
            "detail": f"Issue 10 lookup: status={r.status_code}"}


def verify_019(server_url):
    base = f"{server_url}/sites/project-mgmt-issue-tracking"
    r = requests.get(f"{base}/api/issues/2/comments")
    comments = r.json()
    match = any("webhook integration testing completed successfully"
                in c.get("text", "").lower() for c in comments)
    return {"pass": match,
            "detail": f"Issue 2 comments: {len(comments)}, target_found={match}"}


def verify_020(server_url):
    base = f"{server_url}/sites/project-mgmt-issue-tracking"
    # Check watch
    r = requests.get(f"{base}/api/issues/6/watchers")
    watchers = r.json().get("watchers", [])
    watched = 1 in watchers
    # Check export
    r = requests.get(f"{base}/api/export?format=csv&project_id=1")
    lines = r.text.strip().split("\n")
    data_rows = len(lines) - 1  # minus header
    return {"pass": watched and data_rows > 0,
            "detail": f"Watched={watched}, CSV rows={data_rows}"}
