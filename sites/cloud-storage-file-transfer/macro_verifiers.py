"""Per-macro verification functions for cloud-storage-file-transfer.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/cloud-storage-file-transfer"


def verify_macro_navigate_from_table(server_url):
    """Click a file in the listing to navigate to its detail page."""
    r = requests.get(f"{_base(server_url)}/api/files")
    files = r.json()
    if not files:
        return {"pass": False, "detail": "No files returned"}
    file_id = files[0]["id"]
    r2 = requests.get(f"{_base(server_url)}/file/{file_id}")
    return {"pass": r2.status_code == 200,
            "detail": f"File detail page for id={file_id}: {r2.status_code}"}


def verify_macro_navigate_by_route(server_url):
    """Navigate to a folder or file by direct URL."""
    r = requests.get(f"{_base(server_url)}/folder/1")
    r2 = requests.get(f"{_base(server_url)}/file/1")
    ok = r.status_code == 200 and r2.status_code == 200
    return {"pass": ok, "detail": f"Folder page: {r.status_code}, File page: {r2.status_code}"}


def verify_macro_search_by_query(server_url):
    """Keyword search for files."""
    r = requests.get(f"{_base(server_url)}/api/search?q=Sprint")
    results = r.json()
    return {"pass": len(results) > 0,
            "detail": f"search_by_query 'Sprint': {len(results)} results"}


def verify_macro_search_by_semantic(server_url):
    """Semantic/fuzzy search for files."""
    r = requests.get(f"{_base(server_url)}/api/search/semantic?q=kubernetes+deployment")
    results = r.json()
    return {"pass": r.status_code == 200,
            "detail": f"search_by_semantic: {len(results)} results"}


def verify_macro_filter_by_dropdown(server_url):
    """Filter files by type dropdown."""
    r = requests.get(f"{_base(server_url)}/api/files?type=document")
    files = r.json()
    all_docs = all(f["type"] == "document" for f in files)
    return {"pass": all_docs and len(files) > 0,
            "detail": f"filter_by_dropdown document: {len(files)} files, all_docs={all_docs}"}


def verify_macro_filter_by_date_range(server_url):
    """Filter files by date range."""
    r = requests.get(f"{_base(server_url)}/api/files/by-date?date_from=2026-01-01&date_to=2026-12-31")
    files = r.json()
    return {"pass": r.status_code == 200,
            "detail": f"filter_by_date_range 2026: {len(files)} files"}


def verify_macro_sort_by_ranking(server_url):
    """Sort files by name, size, or date."""
    r = requests.get(f"{_base(server_url)}/api/files?sort=name")
    files = r.json()
    if len(files) < 2:
        return {"pass": False, "detail": "Too few files to verify sorting"}
    sorted_ok = files[0]["name"].lower() <= files[1]["name"].lower()
    return {"pass": sorted_ok,
            "detail": f"sort_by_ranking name: first='{files[0]['name']}', second='{files[1]['name']}'"}


def verify_macro_extract_by_semantic(server_url):
    """Extract specific file info from semantic search results."""
    r = requests.get(f"{_base(server_url)}/api/search/semantic?q=architecture+diagram")
    results = r.json()
    if not results:
        return {"pass": False, "detail": "No semantic results for 'architecture diagram'"}
    return {"pass": "name" in results[0],
            "detail": f"extract_by_semantic: top result='{results[0]['name']}'"}


def verify_macro_extract_by_dropdown(server_url):
    """Extract info after filtering by type."""
    r = requests.get(f"{_base(server_url)}/api/files?type=image&sort=size")
    files = r.json()
    if not files:
        return {"pass": False, "detail": "No image files found"}
    largest = files[0]
    return {"pass": "size_bytes" in largest,
            "detail": f"extract_by_dropdown: largest image='{largest['name']}' ({largest['size_bytes']} bytes)"}


def verify_macro_extract_by_route(server_url):
    """Extract file/folder info by navigating to a direct route."""
    r = requests.get(f"{_base(server_url)}/api/folders/5")
    folder = r.json()
    files = folder.get("files", [])
    return {"pass": "name" in folder and len(files) >= 0,
            "detail": f"extract_by_route: folder '{folder['name']}' has {len(files)} files"}


def verify_macro_compute_by_slider(server_url):
    """Compute storage quota usage with configurable quota."""
    r = requests.get(f"{_base(server_url)}/api/storage-quota?quota_gb=5")
    data = r.json()
    return {"pass": "percent_used" in data and "over_quota" in data,
            "detail": f"compute_by_slider: {data['percent_used']}% used at 5GB quota"}


def verify_macro_create_from_free_text(server_url):
    """Create a new file with free-text name."""
    r = requests.post(f"{_base(server_url)}/api/files",
                      json={"name": "macro_test_file.txt", "type": "document",
                            "size_bytes": 100})
    data = r.json()
    ok = r.status_code == 201 and data.get("name") == "macro_test_file.txt"
    return {"pass": ok, "detail": f"create_from_free_text: id={data.get('id')}"}


def verify_macro_edit_by_dropdown(server_url):
    """Edit share permission via dropdown."""
    # Get current shares
    r = requests.get(f"{_base(server_url)}/api/shares")
    shares = r.json()
    if not shares:
        return {"pass": False, "detail": "No shares to edit"}
    share = shares[0]
    old_perm = share["permission"]
    new_perm = "view" if old_perm != "view" else "edit"
    r2 = requests.put(f"{_base(server_url)}/api/shares/{share['id']}/permission",
                      json={"permission": new_perm})
    result = r2.json()
    return {"pass": result.get("new_permission") == new_perm,
            "detail": f"edit_by_dropdown: share {share['id']} {old_perm}->{new_perm}"}


def verify_macro_edit_by_form(server_url):
    """Edit file metadata via form/API."""
    r = requests.put(f"{_base(server_url)}/api/files/16",
                     json={"name": "Edited Onboarding.docx"})
    data = r.json()
    ok = data.get("name") == "Edited Onboarding.docx"
    # Restore original name
    requests.put(f"{_base(server_url)}/api/files/16",
                 json={"name": "Onboarding Checklist.docx"})
    return {"pass": ok, "detail": f"edit_by_form: name={data.get('name')}"}


def verify_macro_edit_by_drag(server_url):
    """Move a file to a different folder (drag-and-drop)."""
    r = requests.post(f"{_base(server_url)}/api/files/2/move",
                      json={"folder_id": 1})
    data = r.json()
    ok = data.get("new_folder_id") == 1
    # Restore
    requests.post(f"{_base(server_url)}/api/files/2/move",
                  json={"folder_id": 6})
    return {"pass": ok, "detail": f"edit_by_drag: moved to folder {data.get('new_folder_id')}"}


def verify_macro_delete_from_table(server_url):
    """Delete (trash) a file."""
    # Create a temp file to delete
    r = requests.post(f"{_base(server_url)}/api/files",
                      json={"name": "delete_test.tmp", "type": "document", "size_bytes": 10})
    new_file = r.json()
    file_id = new_file["id"]
    r2 = requests.delete(f"{_base(server_url)}/api/files/{file_id}")
    # Verify trashed
    r3 = requests.get(f"{_base(server_url)}/api/files/{file_id}")
    file_data = r3.json()
    ok = file_data.get("is_trashed", False) is True
    # Permanently delete
    requests.delete(f"{_base(server_url)}/api/files/{file_id}")
    return {"pass": ok, "detail": f"delete_from_table: file {file_id} trashed={ok}"}


def verify_macro_configure_by_toggle(server_url):
    """Toggle a user setting."""
    r = requests.get(f"{_base(server_url)}/api/users/1/settings")
    old = r.json()["settings"]
    old_dark = old.get("dark_mode", False)
    r2 = requests.put(f"{_base(server_url)}/api/users/1/settings",
                      json={"dark_mode": not old_dark})
    new_settings = r2.json()["settings"]
    ok = new_settings["dark_mode"] == (not old_dark)
    # Restore
    requests.put(f"{_base(server_url)}/api/users/1/settings",
                 json={"dark_mode": old_dark})
    return {"pass": ok,
            "detail": f"configure_by_toggle: dark_mode {old_dark}->{not old_dark}"}


def verify_macro_export_by_dropdown(server_url):
    """Export file listing as CSV."""
    r = requests.get(f"{_base(server_url)}/api/export?format=csv")
    lines = r.text.strip().splitlines()
    ok = len(lines) > 1 and "id,name" in lines[0]
    return {"pass": ok, "detail": f"export_by_dropdown: {len(lines)} lines (incl header)"}


def verify_macro_upload_from_table(server_url):
    """Upload a file via API."""
    r = requests.post(f"{_base(server_url)}/api/upload",
                      json={"name": "upload_macro_test.txt", "type": "document",
                            "size_bytes": 256, "folder_id": 1})
    data = r.json()
    ok = r.status_code == 201 and data.get("name") == "upload_macro_test.txt"
    return {"pass": ok, "detail": f"upload_from_table: id={data.get('id')}"}


def verify_macro_upload_by_route(server_url):
    """Upload a file to a specific folder by route."""
    r = requests.post(f"{_base(server_url)}/upload/1",
                      data={"name": "route_upload_test.txt", "type": "document",
                            "size_bytes": "128"},
                      allow_redirects=False)
    ok = r.status_code in (302, 303, 200, 201)
    return {"pass": ok, "detail": f"upload_by_route: status={r.status_code}"}


def verify_macro_share_by_query(server_url):
    """Search for a user and share a file with them."""
    r = requests.get(f"{_base(server_url)}/api/users/search?q=priya")
    users = r.json()
    if not users:
        return {"pass": False, "detail": "User search 'priya' returned no results"}
    user_id = users[0]["id"]
    r2 = requests.post(f"{_base(server_url)}/api/shares",
                       json={"file_id": 7, "shared_with": user_id, "permission": "view"})
    ok = r2.status_code == 201
    return {"pass": ok,
            "detail": f"share_by_query: shared file 7 with user {user_id} ({users[0]['name']})"}


def verify_macro_share_by_dropdown(server_url):
    """Update share permission level via dropdown."""
    r = requests.get(f"{_base(server_url)}/api/shares")
    shares = r.json()
    if not shares:
        return {"pass": False, "detail": "No shares found"}
    share = shares[0]
    r2 = requests.put(f"{_base(server_url)}/api/shares/{share['id']}/permission",
                      json={"permission": "view"})
    result = r2.json()
    return {"pass": result.get("new_permission") == "view",
            "detail": f"share_by_dropdown: updated share {share['id']} to view"}


def verify_macro_save_by_toggle(server_url):
    """Toggle star (save) on a file."""
    r = requests.get(f"{_base(server_url)}/api/files/2")
    old_starred = r.json().get("starred", False)
    r2 = requests.post(f"{_base(server_url)}/api/files/2/star")
    data = r2.json()
    toggled = data.get("starred") != old_starred
    # Restore
    if toggled:
        requests.post(f"{_base(server_url)}/api/files/2/star")
    return {"pass": toggled, "detail": f"save_by_toggle: starred {old_starred}->{data.get('starred')}"}


def verify_macro_invite_by_form(server_url):
    """Invite an external collaborator by email."""
    r = requests.post(f"{_base(server_url)}/api/invite",
                      json={"email": "macro_test@example.com", "file_id": 1,
                            "permission": "view", "message": "Macro test invite"})
    data = r.json()
    ok = r.status_code == 201 and data.get("email") == "macro_test@example.com"
    return {"pass": ok, "detail": f"invite_by_form: invite_id={data.get('invite_id')}"}


def verify_macro_authenticate_by_form(server_url):
    """Log in via form/API."""
    s = requests.Session()
    r = s.post(f"{_base(server_url)}/api/login",
               json={"username": "alex.chen", "password": "meridian111"})
    data = r.json()
    ok = r.status_code == 200 and data.get("user_id") == 1
    return {"pass": ok,
            "detail": f"authenticate_by_form: user_id={data.get('user_id')}, name={data.get('name')}"}
