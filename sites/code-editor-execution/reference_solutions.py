"""Per-task reference solutions via Flask test client for code-editor-execution."""
import json


def solve_001(client, base="/sites/code-editor-execution"):
    r = client.get(f"{base}/api/snippets/2")
    snippet = json.loads(r.data)
    return snippet["category"]


def solve_002(client, base="/sites/code-editor-execution"):
    r = client.get(f"{base}/api/snippets/5")
    snippet = json.loads(r.data)
    return snippet["title"]


def solve_003(client, base="/sites/code-editor-execution"):
    r = client.get(f"{base}/api/snippets?q=sort")
    return str(len(json.loads(r.data)))


def solve_004(client, base="/sites/code-editor-execution"):
    r = client.get(f"{base}/api/snippets/1")
    snippet = json.loads(r.data)
    return snippet["expected_output"]


def solve_005(client, base="/sites/code-editor-execution"):
    r = client.post(f"{base}/api/execute",
                    json={"code": "print(2 ** 10)"})
    data = json.loads(r.data)
    return data["stdout"].strip()


def solve_006(client, base="/sites/code-editor-execution"):
    client.post(f"{base}/api/snippets/1/edit",
                json={"title": "Greetings Program"})
    r = client.get(f"{base}/api/snippets/1")
    return json.loads(r.data)["title"]


def solve_007(client, base="/sites/code-editor-execution"):
    # Default tab_size is 4
    return "4"


def solve_008(client, base="/sites/code-editor-execution"):
    r = client.get(f"{base}/api/export?format=csv")
    lines = r.data.decode().strip().split("\n")
    return str(len(lines) - 1)


def solve_009(client, base="/sites/code-editor-execution"):
    r = client.post(f"{base}/api/snippets/upload",
                    json={"title": "Square Numbers",
                          "code": "print([x**2 for x in range(5)])",
                          "description": "Print a list of square numbers",
                          "category": "basics"})
    data = json.loads(r.data)
    return str(data["id"])


def solve_010(client, base="/sites/code-editor-execution"):
    r = client.get(f"{base}/api/share/3")
    data = json.loads(r.data)
    return data["share_token"]


def solve_011(client, base="/sites/code-editor-execution"):
    r = client.get(f"{base}/api/snippets?category=algorithms")
    return str(len(json.loads(r.data)))


def solve_012(client, base="/sites/code-editor-execution"):
    r = client.post(f"{base}/api/snippets/7/run")
    data = json.loads(r.data)
    return str(data["matches_expected"]).lower()


def solve_013(client, base="/sites/code-editor-execution"):
    r = client.post(f"{base}/api/execute",
                    json={"code": "import os"})
    data = json.loads(r.data)
    return data["stderr"]


def solve_014(client, base="/sites/code-editor-execution"):
    r = client.get(f"{base}/api/snippets?q=string&sort=title")
    results = json.loads(r.data)
    return results[0]["title"] if results else "No results"


def solve_015(client, base="/sites/code-editor-execution"):
    r = client.get(f"{base}/api/stats")
    stats = json.loads(r.data)
    return str(stats["difficulty_breakdown"].get("easy", 0))


def solve_016(client, base="/sites/code-editor-execution"):
    r = client.get(f"{base}/api/export?format=json&category=sorting")
    return str(len(json.loads(r.data)))


def solve_017(client, base="/sites/code-editor-execution"):
    client.post(f"{base}/api/login",
                json={"username": "dev_alice", "password": "code123"})
    client.post(f"{base}/api/users/1/save", json={"snippet_id": 4})
    client.post(f"{base}/api/users/1/save", json={"snippet_id": 9})
    r = client.get(f"{base}/api/users/1")
    user = json.loads(r.data)
    return str(len(user.get("saved_snippets", [])))


def solve_018(client, base="/sites/code-editor-execution"):
    client.post(f"{base}/api/login",
                json={"username": "coder_bob", "password": "code456"})
    r = client.post(f"{base}/api/execute",
                    json={"code": "print(sum(range(101)))"})
    data = json.loads(r.data)
    return data["stdout"].strip()


def solve_019(client, base="/sites/code-editor-execution"):
    client.post(f"{base}/api/login",
                json={"username": "hacker_carol", "password": "code789"})
    r = client.post(f"{base}/api/users/3/settings",
                    json={"font_size": 18, "tab_size": 2})
    data = json.loads(r.data)
    settings = data["settings"]
    return f"font_size={settings['font_size']}, tab_size={settings['tab_size']}"


def solve_020(client, base="/sites/code-editor-execution"):
    # Upload triangle pattern snippet
    code = "for i in range(1, 6):\n    print('*' * i)"
    r = client.post(f"{base}/api/snippets/upload",
                    json={"title": "Triangle Pattern",
                          "code": code,
                          "description": "Print a right triangle of asterisks",
                          "category": "basics"})
    data = json.loads(r.data)
    snippet_id = data["id"]
    # Share it
    r2 = client.get(f"{base}/api/share/{snippet_id}")
    share_data = json.loads(r2.data)
    return share_data["share_url"]
