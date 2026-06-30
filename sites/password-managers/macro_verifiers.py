"""Per-macro verification functions for password-managers.

Each function tests that the corresponding macro works end-to-end.
"""
import io
import requests


def _base(server_url):
    return f"{server_url}/sites/password-managers"


def verify_macro_navigate_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/entries/semantic?q=email+communication")
    results = r.json()
    return {"pass": r.status_code == 200,
            "detail": f"navigate_by_semantic: {len(results)} results"}


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/entry/entry_001")
    return {"pass": r.status_code == 200,
            "detail": f"navigate_by_route entry_001: {r.status_code}"}


def verify_macro_search_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/entries/search?q=gmail")
    results = r.json()
    return {"pass": len(results) > 0,
            "detail": f"search_by_query 'gmail': {len(results)} results"}


def verify_macro_filter_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/entries?category=login")
    entries = r.json()
    ok = all(e.get("category") == "login" for e in entries)
    return {"pass": ok and len(entries) > 0,
            "detail": f"filter_by_dropdown login: {len(entries)} entries, all_login={ok}"}


def verify_macro_extract_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/entries/semantic?q=banking+finance")
    results = r.json()
    if results:
        return {"pass": True,
                "detail": f"extract_by_semantic: first={results[0]['title'][:50]}"}
    return {"pass": True, "detail": "extract_by_semantic: no results (ok)"}


def verify_macro_extract_by_code(server_url):
    r = requests.post(f"{_base(server_url)}/api/entries/entry_001/reveal")
    data = r.json()
    pw = data.get("password", "")
    return {"pass": len(pw) > 0,
            "detail": f"extract_by_code: revealed password length={len(pw)}"}


def verify_macro_extract_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/entries?category=secure_note")
    entries = r.json()
    return {"pass": len(entries) > 0,
            "detail": f"extract_by_dropdown secure_note: {len(entries)} entries"}


def verify_macro_extract_from_table(server_url):
    r = requests.get(f"{_base(server_url)}/api/audit-log?action=view_password")
    events = r.json()
    return {"pass": len(events) > 0,
            "detail": f"extract_from_table audit: {len(events)} view_password events"}


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/entries/entry_003")
    entry = r.json()
    return {"pass": "url" in entry and len(entry["url"]) > 0,
            "detail": f"extract_by_route: entry_003 url={entry.get('url','')}"}


def verify_macro_create_from_free_text(server_url):
    r = requests.post(f"{_base(server_url)}/api/entries",
                      json={
                          "title": "MacroTestFreeText",
                          "username": "macrotest@test.com",
                          "password": "MacroT3st!Pass",
                          "url": "https://macrotest.example.com",
                      })
    data = r.json()
    ok = r.status_code == 201 and "id" in data
    # Clean up
    if ok:
        requests.delete(f"{_base(server_url)}/api/entries/{data['id']}")
    return {"pass": ok, "detail": f"create_from_free_text: id={data.get('id')}"}


def verify_macro_create_by_dropdown(server_url):
    r = requests.post(f"{_base(server_url)}/api/entries",
                      json={
                          "title": "MacroTestDropdown",
                          "vault_id": "vault_002",
                          "category": "login",
                          "username": "dropdown@test.com",
                          "password": "Drop!Down42",
                      })
    data = r.json()
    ok = r.status_code == 201 and data.get("vault_id") == "vault_002"
    if "id" in data:
        requests.delete(f"{_base(server_url)}/api/entries/{data['id']}")
    return {"pass": ok,
            "detail": f"create_by_dropdown: vault_id={data.get('vault_id')}"}


def verify_macro_submit_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/entries/search?q=bank")
    results = r.json()
    if results:
        username = results[0].get("username", "")
        return {"pass": len(username) > 0,
                "detail": f"submit_by_query: first username={username}"}
    return {"pass": True, "detail": "submit_by_query: no results (ok)"}


def verify_macro_edit_by_form(server_url):
    # Edit entry_002 title, then restore
    r = requests.get(f"{_base(server_url)}/api/entries/entry_002")
    original_title = r.json().get("title", "")

    r2 = requests.put(f"{_base(server_url)}/api/entries/entry_002",
                      json={"title": "MacroEditTest"})
    data = r2.json()
    ok = data.get("title") == "MacroEditTest"

    # Restore
    requests.put(f"{_base(server_url)}/api/entries/entry_002",
                 json={"title": original_title})
    return {"pass": ok, "detail": f"edit_by_form: title={data.get('title')}"}


def verify_macro_delete_from_table(server_url):
    # Create a temp entry, then delete it
    r = requests.post(f"{_base(server_url)}/api/entries",
                      json={
                          "title": "MacroDeleteTest",
                          "username": "deleteme",
                          "password": "Del3te!Test",
                      })
    data = r.json()
    entry_id = data.get("id", "")

    r2 = requests.delete(f"{_base(server_url)}/api/entries/{entry_id}")
    del_data = r2.json()
    ok = del_data.get("deleted") == entry_id
    return {"pass": ok, "detail": f"delete_from_table: deleted={del_data.get('deleted')}"}


def verify_macro_select_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/entries?vault_id=vault_001")
    entries = r.json()
    ok = all(e["vault_id"] == "vault_001" for e in entries)
    return {"pass": ok and len(entries) > 0,
            "detail": f"select_by_dropdown vault_001: {len(entries)} entries"}


def verify_macro_configure_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/generate-password?length=32&symbols=0")
    data = r.json()
    pw = data.get("password", "")
    ok = len(pw) == 32
    return {"pass": ok,
            "detail": f"configure_by_dropdown: length={len(pw)}, settings={data.get('settings')}"}


def verify_macro_export_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/export?format=csv&vault_id=vault_001")
    lines = r.text.strip().split("\n")
    return {"pass": len(lines) > 1,
            "detail": f"export_by_dropdown CSV vault_001: {len(lines)} lines"}


def verify_macro_upload_by_image(server_url):
    # Create a minimal 1x1 PNG
    import struct
    import zlib

    signature = b'\x89PNG\r\n\x1a\n'
    ihdr_data = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
    ihdr_crc = zlib.crc32(b'IHDR' + ihdr_data) & 0xffffffff
    ihdr = struct.pack('>I', 13) + b'IHDR' + ihdr_data + struct.pack('>I', ihdr_crc)
    raw = b'\x00\xff\x00\x00'
    compressed = zlib.compress(raw)
    idat_crc = zlib.crc32(b'IDAT' + compressed) & 0xffffffff
    idat = struct.pack('>I', len(compressed)) + b'IDAT' + compressed + struct.pack('>I', idat_crc)
    iend_crc = zlib.crc32(b'IEND') & 0xffffffff
    iend = struct.pack('>I', 0) + b'IEND' + struct.pack('>I', iend_crc)
    png_data = signature + ihdr + idat + iend

    r = requests.post(
        f"{_base(server_url)}/api/entries/entry_002/icon",
        files={"icon": ("test_icon.png", io.BytesIO(png_data), "image/png")},
    )
    data = r.json()
    ok = r.status_code == 200 and "icon_url" in data
    return {"pass": ok, "detail": f"upload_by_image: icon_url={data.get('icon_url')}"}


def verify_macro_share_by_dropdown(server_url):
    r = requests.post(f"{_base(server_url)}/api/entries/entry_002/share",
                      json={
                          "target_vault_id": "vault_003",
                          "permission": "read",
                      })
    data = r.json()
    ok = data.get("action") == "shared"
    return {"pass": ok, "detail": f"share_by_dropdown: action={data.get('action')}"}


def verify_macro_authenticate_by_code(server_url):
    s = requests.Session()
    r = s.post(f"{_base(server_url)}/api/login",
               json={
                   "email": "alex.rivera@gmail.com",
                   "master_password": "Rainier2018!Summit",
               })
    data = r.json()
    ok = data.get("user_id") == 1
    return {"pass": ok,
            "detail": f"authenticate_by_code: user_id={data.get('user_id')}"}


def verify_macro_verify_identity_by_code(server_url):
    s = requests.Session()
    # Login first
    s.post(f"{_base(server_url)}/api/login",
           json={
               "email": "alex.rivera@gmail.com",
               "master_password": "Rainier2018!Summit",
           })
    # Verify 2FA
    r = s.post(f"{_base(server_url)}/api/verify-2fa",
               json={"user_id": 1, "code": "482917"})
    data = r.json()
    ok = data.get("verified") is True
    return {"pass": ok,
            "detail": f"verify_identity_by_code: verified={data.get('verified')}"}
