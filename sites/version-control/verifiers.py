"""Per-task HTTP verification functions for version-control."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/version-control"
    r = requests.get(f"{base}/api/repos?language=Python")
    data = r.json()
    count = data.get("total", 0)
    return {"pass": count > 0, "detail": f"Python repos: {count}"}


def verify_002(server_url):
    base = f"{server_url}/sites/version-control"
    r = requests.get(f"{base}/api/repos/1001")
    repo = r.json()
    branch = repo.get("default_branch", "")
    return {"pass": branch == "main", "detail": f"Repo 1001 default_branch: {branch}"}


def verify_003(server_url):
    base = f"{server_url}/sites/version-control"
    r = requests.get(f"{base}/api/search?q=anomaly")
    data = r.json()
    repo_count = len(data.get("repos", []))
    return {"pass": repo_count > 0, "detail": f"Search 'anomaly': {repo_count} repos"}


def verify_004(server_url):
    base = f"{server_url}/sites/version-control"
    r = requests.get(f"{base}/api/search/semantic?q=workflow+automation+scaling")
    data = r.json()
    repo_count = len(data.get("repos", []))
    return {"pass": repo_count > 0, "detail": f"Semantic 'workflow automation scaling': {repo_count} repos"}


def verify_005(server_url):
    base = f"{server_url}/sites/version-control"
    r = requests.get(f"{base}/api/search/code?q=taskgroup")
    data = r.json()
    results = data.get("results", [])
    has_match = any("meridianflow-api" in res.get("repo", "") for res in results)
    return {"pass": has_match, "detail": f"Code search 'TaskGroup': {len(results)} files, meridianflow-api found={has_match}"}


def verify_006(server_url):
    base = f"{server_url}/sites/version-control"
    r = requests.get(f"{base}/api/repos?language=TypeScript")
    data = r.json()
    count = data.get("total", 0)
    return {"pass": count > 0, "detail": f"TypeScript repos: {count}"}


def verify_007(server_url):
    base = f"{server_url}/sites/version-control"
    r = requests.get(f"{base}/api/repos?sort=name")
    data = r.json()
    repos = data.get("repos", [])
    if not repos:
        return {"pass": False, "detail": "No repos returned"}
    first_name = repos[0]["name"]
    names = [r["name"].lower() for r in repos]
    is_sorted = all(names[i] <= names[i + 1] for i in range(len(names) - 1))
    return {"pass": is_sorted, "detail": f"First repo (sorted): {first_name}, sorted={is_sorted}"}


def verify_008(server_url):
    base = f"{server_url}/sites/version-control"
    r = requests.get(f"{base}/api/search?q=webhook")
    data = r.json()
    activities = data.get("activities", [])
    if not activities:
        return {"pass": False, "detail": "No activities found for 'webhook'"}
    first_msg = activities[0].get("commit_message", "") or activities[0].get("merge_request_title", "")
    return {"pass": len(first_msg) > 0, "detail": f"First 'webhook' activity: {first_msg[:60]}"}


def verify_009(server_url):
    base = f"{server_url}/sites/version-control"
    r = requests.get(f"{base}/api/search/semantic?q=rate+limit")
    data = r.json()
    activities = data.get("activities", [])
    if not activities:
        return {"pass": False, "detail": "No semantic results for 'rate limit'"}
    top = activities[0]
    msg = top.get("merge_request_title", "") or top.get("commit_message", "") or top.get("review_comment", "")
    return {"pass": len(msg) > 0, "detail": f"Top semantic activity: {msg[:60]}"}


def verify_010(server_url):
    base = f"{server_url}/sites/version-control"
    r = requests.get(f"{base}/api/repos/compare?ids=1001,1002")
    data = r.json()
    repos = data.get("repos", [])
    if len(repos) < 2:
        return {"pass": False, "detail": f"Compare returned {len(repos)} repos, expected 2"}
    commits_1001 = next((r["commit_count"] for r in repos if r["id"] == 1001), 0)
    commits_1002 = next((r["commit_count"] for r in repos if r["id"] == 1002), 0)
    more = "meridianflow-api" if commits_1001 > commits_1002 else "meridianvault-engine"
    return {"pass": True, "detail": f"1001 commits: {commits_1001}, 1002 commits: {commits_1002}, more: {more}"}


def verify_011(server_url):
    base = f"{server_url}/sites/version-control"
    r = requests.get(f"{base}/api/repos/1008")
    repo = r.json()
    owner = repo.get("owner_name", "")
    return {"pass": len(owner) > 0, "detail": f"Repo 1008 owner: {owner}"}


def verify_012(server_url):
    base = f"{server_url}/sites/version-control"
    r = requests.get(f"{base}/api/repos")
    data = r.json()
    repos = data.get("repos", [])
    found = any(r["name"] == "test-project" for r in repos)
    return {"pass": found, "detail": f"test-project in repo list: {found}"}


def verify_013(server_url):
    base = f"{server_url}/sites/version-control"
    r = requests.get(f"{base}/api/repos/1001/issues")
    data = r.json()
    issues = data.get("issues", [])
    found = any("batch workflow deletion" in i.get("title", "").lower() for i in issues)
    return {"pass": found, "detail": f"Issue 'batch workflow deletion' found: {found}, total issues: {len(issues)}"}


def verify_014(server_url):
    base = f"{server_url}/sites/version-control"
    r = requests.get(f"{base}/api/repos/1001/issues")
    data = r.json()
    issues = data.get("issues", [])
    issue1 = next((i for i in issues if i["id"] == 1), None)
    if not issue1:
        return {"pass": False, "detail": "Issue #1 not found"}
    state = issue1.get("state", "")
    return {"pass": state == "closed", "detail": f"Issue #1 state: {state}"}


def verify_015(server_url):
    base = f"{server_url}/sites/version-control"
    r = requests.get(f"{base}/api/repos/1001/uploads")
    data = r.json()
    uploads = data.get("uploads", [])
    found = any(u.get("path", "") == "CHANGELOG.md" for u in uploads)
    return {"pass": found, "detail": f"CHANGELOG.md uploaded: {found}, total uploads: {len(uploads)}"}


def verify_016(server_url):
    base = f"{server_url}/sites/version-control"
    r = requests.get(f"{base}/api/repos/1004")
    repo = r.json()
    visibility = repo.get("visibility", "")
    return {"pass": visibility == "public", "detail": f"Repo 1004 visibility: {visibility}"}


def verify_017(server_url):
    base = f"{server_url}/sites/version-control"
    r = requests.get(f"{base}/api/export/repos?format=json")
    data = r.json()
    count = len(data)
    return {"pass": count > 0, "detail": f"JSON export: {count} repos"}


def verify_018(server_url):
    base = f"{server_url}/sites/version-control"
    r = requests.get(f"{base}/api/repos/1001/issues/1/comments")
    data = r.json()
    comments = data.get("comments", [])
    found = any("global timeout" in c.get("body", "").lower() for c in comments)
    return {"pass": found, "detail": f"Comment with 'global timeout' found: {found}, total comments: {len(comments)}"}


def verify_019(server_url):
    base = f"{server_url}/sites/version-control"
    s = requests.Session()
    r = s.post(f"{base}/api/repos/1001/star")
    data = r.json()
    starred = data.get("starred", False)
    # Toggle back to clean up
    s.post(f"{base}/api/repos/1001/star")
    return {"pass": starred is True, "detail": f"Repo 1001 starred: {starred}"}


def verify_020(server_url):
    base = f"{server_url}/sites/version-control"
    r = requests.get(f"{base}/api/search/code?q=async+def")
    data = r.json()
    results = data.get("results", [])
    count = len(results)
    repo_names = list(set(res.get("repo", "") for res in results))
    return {"pass": count > 0, "detail": f"Code search 'async def': {count} files in repos {repo_names}"}
