"""Per-task HTTP verification functions for code-editor-execution."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/code-editor-execution"
    r = requests.get(f"{base}/api/snippets/2")
    snippet = r.json()
    cat = snippet.get("category", "")
    return {"pass": cat == "algorithms", "detail": f"Snippet 2 category: {cat}"}


def verify_002(server_url):
    base = f"{server_url}/sites/code-editor-execution"
    r = requests.get(f"{base}/api/snippets/5")
    snippet = r.json()
    title = snippet.get("title", "")
    return {"pass": len(title) > 0, "detail": f"Snippet 5 title: {title}"}


def verify_003(server_url):
    base = f"{server_url}/sites/code-editor-execution"
    r = requests.get(f"{base}/api/snippets?q=sort")
    results = r.json()
    count = len(results)
    return {"pass": count > 0, "detail": f"Search 'sort': {count} results"}


def verify_004(server_url):
    base = f"{server_url}/sites/code-editor-execution"
    r = requests.get(f"{base}/api/snippets/1")
    snippet = r.json()
    expected = snippet.get("expected_output", "")
    return {"pass": len(expected) > 0, "detail": f"Snippet 1 expected_output: {expected!r}"}


def verify_005(server_url):
    base = f"{server_url}/sites/code-editor-execution"
    r = requests.post(f"{base}/api/execute", json={"code": "print(2 ** 10)"})
    data = r.json()
    stdout = data.get("stdout", "").strip()
    return {"pass": stdout == "1024", "detail": f"Execution output: {stdout}"}


def verify_006(server_url):
    base = f"{server_url}/sites/code-editor-execution"
    r = requests.get(f"{base}/api/snippets/1")
    snippet = r.json()
    title = snippet.get("title", "")
    return {"pass": title == "Greetings Program",
            "detail": f"Snippet 1 title after edit: {title}"}


def verify_007(server_url):
    base = f"{server_url}/sites/code-editor-execution"
    r = requests.get(f"{base}/editor?font_size=20&tab_size=4")
    ok = r.status_code == 200 and "tab_size" in r.text
    return {"pass": ok, "detail": f"Editor page with font_size=20: status={r.status_code}"}


def verify_008(server_url):
    base = f"{server_url}/sites/code-editor-execution"
    r = requests.get(f"{base}/api/export?format=csv")
    lines = r.text.strip().split("\n")
    data_rows = len(lines) - 1
    return {"pass": data_rows > 0, "detail": f"CSV export: {data_rows} data rows"}


def verify_009(server_url):
    base = f"{server_url}/sites/code-editor-execution"
    r = requests.get(f"{base}/api/snippets")
    snippets = r.json()
    found = any(s["title"] == "Square Numbers" for s in snippets)
    return {"pass": found, "detail": f"Upload 'Square Numbers': found={found}, total={len(snippets)}"}


def verify_010(server_url):
    base = f"{server_url}/sites/code-editor-execution"
    r = requests.get(f"{base}/api/share/3")
    data = r.json()
    token = data.get("share_token", "")
    return {"pass": len(token) > 0, "detail": f"Share token for snippet 3: {token}"}


def verify_011(server_url):
    base = f"{server_url}/sites/code-editor-execution"
    r = requests.get(f"{base}/api/snippets?category=algorithms")
    results = r.json()
    count = len(results)
    ok = all(s["category"] == "algorithms" for s in results)
    return {"pass": count > 0 and ok, "detail": f"algorithms filter: {count} snippets, all_algorithms={ok}"}


def verify_012(server_url):
    base = f"{server_url}/sites/code-editor-execution"
    r = requests.post(f"{base}/api/snippets/7/run")
    data = r.json()
    matches = data.get("matches_expected", False)
    return {"pass": matches, "detail": f"FizzBuzz output matches: {matches}"}


def verify_013(server_url):
    base = f"{server_url}/sites/code-editor-execution"
    r = requests.post(f"{base}/api/execute", json={"code": "import os"})
    data = r.json()
    stderr = data.get("stderr", "")
    return {"pass": "Blocked" in stderr or "not allowed" in stderr,
            "detail": f"Dangerous import blocked: {stderr[:100]}"}


def verify_014(server_url):
    base = f"{server_url}/sites/code-editor-execution"
    r = requests.get(f"{base}/api/snippets?q=string&sort=title")
    results = r.json()
    if not results:
        return {"pass": True, "detail": "No results for 'string' (ok)"}
    first = results[0]["title"]
    return {"pass": len(first) > 0, "detail": f"First 'string' result sorted by title: {first}"}


def verify_015(server_url):
    base = f"{server_url}/sites/code-editor-execution"
    r = requests.get(f"{base}/api/stats")
    stats = r.json()
    easy_count = stats.get("difficulty_breakdown", {}).get("easy", 0)
    return {"pass": easy_count > 0, "detail": f"Easy snippets: {easy_count}"}


def verify_016(server_url):
    base = f"{server_url}/sites/code-editor-execution"
    r = requests.get(f"{base}/api/export?format=json&category=sorting")
    data = r.json()
    count = len(data)
    return {"pass": count > 0, "detail": f"Sorting export: {count} snippets"}


def verify_017(server_url):
    base = f"{server_url}/sites/code-editor-execution"
    r = requests.get(f"{base}/api/users/1")
    user = r.json()
    saved = user.get("saved_snippets", [])
    return {"pass": 4 in saved and 9 in saved and len(saved) == 2,
            "detail": f"User 1 saved snippets: {saved}"}


def verify_018(server_url):
    base = f"{server_url}/sites/code-editor-execution"
    r = requests.get(f"{base}/api/users/2")
    user = r.json()
    history = user.get("execution_history", [])
    has_5050 = any("5050" in h.get("stdout", "") for h in history)
    return {"pass": has_5050, "detail": f"User 2 history has 5050: {has_5050}, entries={len(history)}"}


def verify_019(server_url):
    base = f"{server_url}/sites/code-editor-execution"
    r = requests.get(f"{base}/api/users/3")
    user = r.json()
    settings = user.get("settings", {})
    ok = settings.get("font_size") == 18 and settings.get("tab_size") == 2
    return {"pass": ok, "detail": f"User 3 settings: {settings}"}


def verify_020(server_url):
    base = f"{server_url}/sites/code-editor-execution"
    # Check uploaded snippet exists
    r = requests.get(f"{base}/api/snippets")
    snippets = r.json()
    triangle = next((s for s in snippets if s["title"] == "Triangle Pattern"), None)
    if not triangle:
        return {"pass": False, "detail": "Triangle Pattern snippet not found"}
    # Check share works
    r2 = requests.get(f"{base}/api/share/{triangle['id']}")
    data = r2.json()
    has_share = len(data.get("share_token", "")) > 0
    return {"pass": has_share,
            "detail": f"Triangle Pattern id={triangle['id']}, share_token={data.get('share_token')}"}
