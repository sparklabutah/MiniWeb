"""Per-task reference solutions via Flask test client for version-control."""
import io
import json


def solve_001(client, base="/sites/version-control"):
    r = client.get(f"{base}/api/repos?language=Python")
    data = json.loads(r.data)
    return str(data["total"])


def solve_002(client, base="/sites/version-control"):
    r = client.get(f"{base}/api/repos/1001")
    repo = json.loads(r.data)
    return repo["default_branch"]


def solve_003(client, base="/sites/version-control"):
    r = client.get(f"{base}/api/search?q=anomaly")
    data = json.loads(r.data)
    return str(len(data["repos"]))


def solve_004(client, base="/sites/version-control"):
    r = client.get(f"{base}/api/search/semantic?q=workflow+automation+scaling")
    data = json.loads(r.data)
    return str(len(data["repos"]))


def solve_005(client, base="/sites/version-control"):
    r = client.get(f"{base}/api/search/code?q=taskgroup")
    data = json.loads(r.data)
    results = data["results"]
    repos = list(set(res["repo"] for res in results))
    files = [f"{res['repo']}/{res['file']}" for res in results]
    return f"{len(results)} files: {', '.join(files)}"


def solve_006(client, base="/sites/version-control"):
    r = client.get(f"{base}/api/repos?language=TypeScript")
    data = json.loads(r.data)
    return str(data["total"])


def solve_007(client, base="/sites/version-control"):
    r = client.get(f"{base}/api/repos?sort=name")
    data = json.loads(r.data)
    repos = data["repos"]
    return repos[0]["name"] if repos else ""


def solve_008(client, base="/sites/version-control"):
    r = client.get(f"{base}/api/search?q=webhook")
    data = json.loads(r.data)
    activities = data["activities"]
    if activities:
        first = activities[0]
        return first.get("commit_message", "") or first.get("merge_request_title", "")
    return "No results"


def solve_009(client, base="/sites/version-control"):
    r = client.get(f"{base}/api/search/semantic?q=rate+limit")
    data = json.loads(r.data)
    activities = data.get("activities", [])
    if activities:
        top = activities[0]
        return top.get("merge_request_title", "") or top.get("commit_message", "") or top.get("review_comment", "")
    return "No results"


def solve_010(client, base="/sites/version-control"):
    r = client.get(f"{base}/api/repos/compare?ids=1001,1002")
    data = json.loads(r.data)
    repos = data["repos"]
    info = {r["id"]: r["commit_count"] for r in repos}
    if info.get(1001, 0) > info.get(1002, 0):
        return f"meridianflow-api ({info[1001]} commits vs {info[1002]})"
    else:
        return f"meridianvault-engine ({info[1002]} commits vs {info[1001]})"


def solve_011(client, base="/sites/version-control"):
    r = client.get(f"{base}/api/repos/1008")
    repo = json.loads(r.data)
    return repo.get("owner_name", "")


def solve_012(client, base="/sites/version-control"):
    r = client.post(
        f"{base}/api/repos",
        data=json.dumps({
            "name": "test-project",
            "description": "A test repository",
            "visibility": "public",
        }),
        content_type="application/json",
    )
    repo = json.loads(r.data)
    return f"Created repo id={repo['id']}, name={repo['name']}"


def solve_013(client, base="/sites/version-control"):
    r = client.post(
        f"{base}/api/repos/1001/issues",
        data=json.dumps({
            "title": "Add support for batch workflow deletion",
            "labels": ["enhancement"],
        }),
        content_type="application/json",
    )
    issue = json.loads(r.data)
    return f"Created issue id={issue['id']}, title={issue['title']}"


def solve_014(client, base="/sites/version-control"):
    r = client.put(
        f"{base}/api/repos/1001/issues/1",
        data=json.dumps({"state": "closed"}),
        content_type="application/json",
    )
    issue = json.loads(r.data)
    return issue.get("state", "")


def solve_015(client, base="/sites/version-control"):
    data = {
        "file": (io.BytesIO(b"Initial release"), "CHANGELOG.md"),
        "commit_message": "Add changelog",
        "path": "CHANGELOG.md",
    }
    r = client.post(
        f"{base}/api/repos/1001/upload",
        data=data,
        content_type="multipart/form-data",
    )
    upload = json.loads(r.data)
    return f"Uploaded {upload.get('path', '')} (size={upload.get('size', 0)})"


def solve_016(client, base="/sites/version-control"):
    r = client.put(
        f"{base}/api/repos/1004/settings",
        data=json.dumps({"visibility": "public"}),
        content_type="application/json",
    )
    result = json.loads(r.data)
    return result.get("changes", {}).get("visibility", {}).get("new", "")


def solve_017(client, base="/sites/version-control"):
    r = client.get(f"{base}/api/export/repos?format=json")
    data = json.loads(r.data)
    return str(len(data))


def solve_018(client, base="/sites/version-control"):
    r = client.post(
        f"{base}/api/repos/1001/issues/1/comments",
        data=json.dumps({
            "body": "I can confirm this bug. The global timeout should be enforced at the TaskGroup level.",
        }),
        content_type="application/json",
    )
    comment = json.loads(r.data)
    return f"Comment posted id={comment.get('id', '')}"


def solve_019(client, base="/sites/version-control"):
    r = client.post(f"{base}/api/repos/1001/star")
    data = json.loads(r.data)
    return f"starred={data.get('starred', False)}"


def solve_020(client, base="/sites/version-control"):
    r = client.get(f"{base}/api/search/code?q=async+def")
    data = json.loads(r.data)
    results = data["results"]
    repos = sorted(set(res["repo"] for res in results))
    return f"{len(results)} files in repos: {', '.join(repos)}"
