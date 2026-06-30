"""Per-task reference solutions via Flask test client for cloud-storage-file-transfer."""
import json


def solve_001(client, base="/sites/cloud-storage-file-transfer"):
    r = client.get(f"{base}/api/files/1")
    file = json.loads(r.data)
    return str(file["size_bytes"])


def solve_002(client, base="/sites/cloud-storage-file-transfer"):
    r = client.get(f"{base}/api/files/10")
    file = json.loads(r.data)
    return file["name"]


def solve_003(client, base="/sites/cloud-storage-file-transfer"):
    r = client.get(f"{base}/api/search?q=Sprint")
    return str(len(json.loads(r.data)))


def solve_004(client, base="/sites/cloud-storage-file-transfer"):
    r = client.get(f"{base}/api/search/semantic?q=kubernetes+deployment+infrastructure")
    return str(len(json.loads(r.data)))


def solve_005(client, base="/sites/cloud-storage-file-transfer"):
    r = client.get(f"{base}/api/files?type=spreadsheet")
    return str(len(json.loads(r.data)))


def solve_006(client, base="/sites/cloud-storage-file-transfer"):
    r = client.get(f"{base}/api/files/by-date?date_from=2026-06-01&date_to=2026-06-30")
    return str(len(json.loads(r.data)))


def solve_007(client, base="/sites/cloud-storage-file-transfer"):
    r = client.get(f"{base}/api/files?sort=name")
    files = json.loads(r.data)
    return files[0]["name"] if files else "N/A"


def solve_008(client, base="/sites/cloud-storage-file-transfer"):
    r = client.get(f"{base}/api/search/semantic?q=design+wireframe+mockup")
    results = json.loads(r.data)
    return results[0]["name"] if results else "N/A"


def solve_009(client, base="/sites/cloud-storage-file-transfer"):
    r = client.get(f"{base}/api/files?type=image&sort=size")
    files = json.loads(r.data)
    count = len(files)
    largest = files[0]["name"] if files else "N/A"
    return f"{count}, {largest}"


def solve_010(client, base="/sites/cloud-storage-file-transfer"):
    r = client.get(f"{base}/api/folders/5")
    folder = json.loads(r.data)
    return str(len(folder.get("files", [])))


def solve_011(client, base="/sites/cloud-storage-file-transfer"):
    r = client.get(f"{base}/api/storage-quota?quota_gb=10&user_id=1")
    data = json.loads(r.data)
    return str(data["percent_used"])


def solve_012(client, base="/sites/cloud-storage-file-transfer"):
    r = client.post(f"{base}/api/files",
                    json={"name": "Team Standup Notes.docx", "type": "document",
                          "size_bytes": 51200, "folder_id": 3})
    new_file = json.loads(r.data)
    return str(new_file["id"])


def solve_013(client, base="/sites/cloud-storage-file-transfer"):
    # Read current permission
    r = client.get(f"{base}/api/shares")
    shares = json.loads(r.data)
    share1 = next(s for s in shares if s["id"] == 1)
    old_perm = share1["permission"]
    # Update to admin
    client.put(f"{base}/api/shares/1/permission",
               json={"permission": "admin"})
    return old_perm


def solve_014(client, base="/sites/cloud-storage-file-transfer"):
    client.put(f"{base}/api/files/16",
               json={"name": "New Hire Onboarding Guide.docx"})
    r = client.get(f"{base}/api/files/16")
    return json.loads(r.data)["name"]


def solve_015(client, base="/sites/cloud-storage-file-transfer"):
    r = client.post(f"{base}/api/files/2/move",
                    json={"folder_id": 4})
    data = json.loads(r.data)
    return data["new_path"]


def solve_016(client, base="/sites/cloud-storage-file-transfer"):
    client.delete(f"{base}/api/files/34")
    r = client.get(f"{base}/api/files/34")
    file = json.loads(r.data)
    return "trashed" if file.get("is_trashed") else "not trashed"


def solve_017(client, base="/sites/cloud-storage-file-transfer"):
    # Login
    client.post(f"{base}/api/login",
                json={"username": "alex.chen", "password": "meridian111"})
    # Toggle dark mode
    client.put(f"{base}/api/users/1/settings",
               json={"dark_mode": True})
    r = client.get(f"{base}/api/users/1/settings")
    settings = json.loads(r.data)["settings"]
    return str(settings["dark_mode"]).lower()


def solve_018(client, base="/sites/cloud-storage-file-transfer"):
    r = client.get(f"{base}/api/export?format=csv&type=code")
    lines = r.data.decode().strip().splitlines()
    data_rows = len(lines) - 1 if lines else 0
    return str(data_rows)


def solve_019(client, base="/sites/cloud-storage-file-transfer"):
    # Upload file to Kubernetes Configs folder
    r = client.post(f"{base}/api/upload",
                    json={"name": "deployment_checklist.md", "type": "document",
                          "size_bytes": 8192, "folder_id": 15})
    new_file = json.loads(r.data)
    file_id = new_file["id"]
    # Star it
    client.post(f"{base}/api/files/{file_id}/star")
    r = client.get(f"{base}/api/files/{file_id}")
    file = json.loads(r.data)
    return "starred" if file.get("starred") else "not starred"


def solve_020(client, base="/sites/cloud-storage-file-transfer"):
    # Search for user Priya
    r = client.get(f"{base}/api/users/search?q=priya")
    users = json.loads(r.data)
    priya_id = users[0]["id"]  # Should be 2
    # Share file 24 with Priya (edit permission)
    client.post(f"{base}/api/shares",
                json={"file_id": 24, "shared_with": priya_id, "permission": "edit"})
    # Invite external email
    client.post(f"{base}/api/invite",
                json={"email": "auditor@securecorp.com", "file_id": 24,
                      "permission": "view"})
    # Count shares for file 24
    r = client.get(f"{base}/api/shares?file_id=24")
    shares = json.loads(r.data)
    return str(len(shares))
