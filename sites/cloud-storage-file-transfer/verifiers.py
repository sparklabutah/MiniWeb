"""Per-task HTTP verification functions for cloud-storage-file-transfer."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/cloud-storage-file-transfer"
    r = requests.get(f"{base}/api/files/1")
    file = r.json()
    size = file.get("size_bytes", 0)
    return {"pass": size == 245760, "detail": f"File 1 size_bytes: {size}"}


def verify_002(server_url):
    base = f"{server_url}/sites/cloud-storage-file-transfer"
    r = requests.get(f"{base}/api/files/10")
    file = r.json()
    name = file.get("name", "")
    return {"pass": name == "Product Roadmap H2 2026.pptx",
            "detail": f"File 10 name: {name}"}


def verify_003(server_url):
    base = f"{server_url}/sites/cloud-storage-file-transfer"
    r = requests.get(f"{base}/api/search?q=Sprint")
    results = r.json()
    count = len(results)
    return {"pass": count > 0, "detail": f"Search 'Sprint': {count} results"}


def verify_004(server_url):
    base = f"{server_url}/sites/cloud-storage-file-transfer"
    r = requests.get(f"{base}/api/search/semantic?q=kubernetes+deployment+infrastructure")
    results = r.json()
    count = len(results)
    return {"pass": count > 0, "detail": f"Semantic 'kubernetes deployment infrastructure': {count} results"}


def verify_005(server_url):
    base = f"{server_url}/sites/cloud-storage-file-transfer"
    r = requests.get(f"{base}/api/files?type=spreadsheet")
    results = r.json()
    count = len(results)
    return {"pass": count > 0, "detail": f"Spreadsheet files: {count}"}


def verify_006(server_url):
    base = f"{server_url}/sites/cloud-storage-file-transfer"
    r = requests.get(f"{base}/api/files/by-date?date_from=2026-06-01&date_to=2026-06-30")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Files modified Jun 2026: {count}"}


def verify_007(server_url):
    base = f"{server_url}/sites/cloud-storage-file-transfer"
    r = requests.get(f"{base}/api/files?sort=name")
    results = r.json()
    if not results:
        return {"pass": False, "detail": "No files returned"}
    first_name = results[0]["name"]
    return {"pass": len(first_name) > 0, "detail": f"First file sorted by name: {first_name}"}


def verify_008(server_url):
    base = f"{server_url}/sites/cloud-storage-file-transfer"
    r = requests.get(f"{base}/api/search/semantic?q=design+wireframe+mockup")
    results = r.json()
    if not results:
        return {"pass": False, "detail": "No semantic results"}
    top_name = results[0]["name"]
    return {"pass": len(top_name) > 0, "detail": f"Top semantic result: {top_name}"}


def verify_009(server_url):
    base = f"{server_url}/sites/cloud-storage-file-transfer"
    r = requests.get(f"{base}/api/files?type=image&sort=size")
    results = r.json()
    count = len(results)
    if not results:
        return {"pass": False, "detail": "No image files"}
    largest = results[0]["name"]
    return {"pass": count > 0, "detail": f"Image files: {count}, largest: {largest}"}


def verify_010(server_url):
    base = f"{server_url}/sites/cloud-storage-file-transfer"
    r = requests.get(f"{base}/api/folders/5")
    folder = r.json()
    files = folder.get("files", [])
    count = len(files)
    return {"pass": count > 0, "detail": f"Platform v3 folder: {count} files"}


def verify_011(server_url):
    base = f"{server_url}/sites/cloud-storage-file-transfer"
    r = requests.get(f"{base}/api/storage-quota?quota_gb=10&user_id=1")
    data = r.json()
    pct = data.get("percent_used", -1)
    return {"pass": pct >= 0, "detail": f"User 1 quota at 10GB: {pct}% used"}


def verify_012(server_url):
    base = f"{server_url}/sites/cloud-storage-file-transfer"
    r = requests.get(f"{base}/api/files?folder_id=3")
    files = r.json()
    created = [f for f in files if f["name"] == "Team Standup Notes.docx"]
    if not created:
        return {"pass": False, "detail": "File 'Team Standup Notes.docx' not found in folder 3"}
    new_file = created[0]
    return {"pass": new_file["size_bytes"] == 51200 and new_file["type"] == "document",
            "detail": f"Created file ID {new_file['id']} in folder 3"}


def verify_013(server_url):
    base = f"{server_url}/sites/cloud-storage-file-transfer"
    r = requests.get(f"{base}/api/shares")
    shares = r.json()
    share1 = next((s for s in shares if s["id"] == 1), None)
    if not share1:
        return {"pass": False, "detail": "Share ID 1 not found"}
    perm = share1["permission"]
    return {"pass": perm == "admin", "detail": f"Share 1 permission: {perm}"}


def verify_014(server_url):
    base = f"{server_url}/sites/cloud-storage-file-transfer"
    r = requests.get(f"{base}/api/files/16")
    file = r.json()
    name = file.get("name", "")
    return {"pass": name == "New Hire Onboarding Guide.docx",
            "detail": f"File 16 name: {name}"}


def verify_015(server_url):
    base = f"{server_url}/sites/cloud-storage-file-transfer"
    r = requests.get(f"{base}/api/files/2")
    file = r.json()
    folder_id = file.get("folder_id")
    path = file.get("path", "")
    return {"pass": folder_id == 4, "detail": f"File 2 folder: {folder_id}, path: {path}"}


def verify_016(server_url):
    base = f"{server_url}/sites/cloud-storage-file-transfer"
    r = requests.get(f"{base}/api/files/34")
    file = r.json()
    is_trashed = file.get("is_trashed", False)
    return {"pass": is_trashed is True, "detail": f"File 34 is_trashed: {is_trashed}"}


def verify_017(server_url):
    base = f"{server_url}/sites/cloud-storage-file-transfer"
    r = requests.get(f"{base}/api/users/1/settings")
    data = r.json()
    dark_mode = data.get("settings", {}).get("dark_mode", False)
    return {"pass": dark_mode is True, "detail": f"User 1 dark_mode: {dark_mode}"}


def verify_018(server_url):
    base = f"{server_url}/sites/cloud-storage-file-transfer"
    r = requests.get(f"{base}/api/export?format=csv&type=code")
    lines = r.text.strip().splitlines()
    # First line is header, rest are data rows
    data_rows = len(lines) - 1 if lines else 0
    return {"pass": data_rows > 0, "detail": f"Code CSV export: {data_rows} data rows"}


def verify_019(server_url):
    base = f"{server_url}/sites/cloud-storage-file-transfer"
    r = requests.get(f"{base}/api/files?folder_id=15")
    files = r.json()
    uploaded = [f for f in files if f["name"] == "deployment_checklist.md"]
    if not uploaded:
        return {"pass": False, "detail": "File 'deployment_checklist.md' not found in folder 15"}
    file = uploaded[0]
    is_starred = file.get("starred", False)
    return {"pass": is_starred is True,
            "detail": f"File '{file['name']}' (id={file['id']}) starred={is_starred}"}


def verify_020(server_url):
    base = f"{server_url}/sites/cloud-storage-file-transfer"
    r = requests.get(f"{base}/api/shares?file_id=24")
    shares = r.json()
    count = len(shares)
    # Should have at least the new share with Priya (user 2) and the invite
    has_priya = any(s.get("shared_with") == 2 and s.get("permission") == "edit" for s in shares)
    has_invite = any(s.get("invited_email") == "auditor@securecorp.com" for s in shares)
    return {"pass": has_priya and has_invite,
            "detail": f"File 24 shares: {count}, priya_edit={has_priya}, auditor_invite={has_invite}"}
