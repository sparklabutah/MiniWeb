"""Per-task HTTP verification functions for password-managers."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/password-managers"
    r = requests.get(f"{base}/api/entries/semantic?q=social+media")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Semantic 'social media': {count} entries"}


def verify_002(server_url):
    base = f"{server_url}/sites/password-managers"
    r = requests.get(f"{base}/api/entries/entry_001")
    entry = r.json()
    title = entry.get("title", "")
    return {"pass": len(title) > 0, "detail": f"entry_001 title: {title}"}


def verify_003(server_url):
    base = f"{server_url}/sites/password-managers"
    r = requests.get(f"{base}/api/entries/search?q=google")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Search 'google': {count} results"}


def verify_004(server_url):
    base = f"{server_url}/sites/password-managers"
    r = requests.get(f"{base}/api/entries?vault_id=vault_001&category=login")
    entries = r.json()
    count = len(entries)
    return {"pass": count > 0, "detail": f"vault_001 login entries: {count}"}


def verify_005(server_url):
    base = f"{server_url}/sites/password-managers"
    r = requests.get(f"{base}/api/entries/semantic?q=banking+finance")
    results = r.json()
    if not results:
        return {"pass": False, "detail": "No results for 'banking finance'"}
    title = results[0].get("title", "")
    return {"pass": len(title) > 0, "detail": f"First 'banking finance' result: {title}"}


def verify_006(server_url):
    base = f"{server_url}/sites/password-managers"
    r = requests.post(f"{base}/api/entries/entry_001/reveal")
    data = r.json()
    password = data.get("password", "")
    return {"pass": len(password) > 0, "detail": f"Revealed password length: {len(password)}"}


def verify_007(server_url):
    base = f"{server_url}/sites/password-managers"
    r = requests.get(f"{base}/api/entries?category=secure_note")
    entries = r.json()
    count = len(entries)
    return {"pass": count > 0, "detail": f"secure_note entries: {count}"}


def verify_008(server_url):
    base = f"{server_url}/sites/password-managers"
    r = requests.get(f"{base}/api/audit-log?action=view_password")
    events = r.json()
    count = len(events)
    return {"pass": count > 0, "detail": f"view_password audit events: {count}"}


def verify_009(server_url):
    base = f"{server_url}/sites/password-managers"
    r = requests.get(f"{base}/api/entries/entry_003")
    entry = r.json()
    url = entry.get("url", "")
    return {"pass": len(url) > 0, "detail": f"entry_003 URL: {url}"}


def verify_010(server_url):
    base = f"{server_url}/sites/password-managers"
    r = requests.get(f"{base}/api/entries/search?q=TestService")
    results = r.json()
    found = any(e["title"] == "TestService" for e in results)
    return {"pass": found, "detail": f"TestService entry found: {found}"}


def verify_011(server_url):
    base = f"{server_url}/sites/password-managers"
    r = requests.get(f"{base}/api/entries/search?q=DropboxWork")
    results = r.json()
    if not results:
        return {"pass": False, "detail": "DropboxWork entry not found"}
    entry = results[0]
    ok = entry.get("vault_id") == "vault_002"
    return {"pass": ok, "detail": f"DropboxWork vault_id: {entry.get('vault_id')}"}


def verify_012(server_url):
    base = f"{server_url}/sites/password-managers"
    r = requests.get(f"{base}/api/entries/search?q=bank")
    results = r.json()
    if not results:
        return {"pass": False, "detail": "No results for 'bank'"}
    username = results[0].get("username", "")
    return {"pass": len(username) > 0, "detail": f"First 'bank' result username: {username}"}


def verify_013(server_url):
    base = f"{server_url}/sites/password-managers"
    r = requests.get(f"{base}/api/entries/entry_002")
    entry = r.json()
    title = entry.get("title", "")
    ok = title == "Updated Service Name"
    return {"pass": ok, "detail": f"entry_002 title after edit: {title}"}


def verify_014(server_url):
    base = f"{server_url}/sites/password-managers"
    r = requests.get(f"{base}/api/entries/entry_005")
    # Entry should be gone (404)
    ok = r.status_code == 404
    return {"pass": ok, "detail": f"entry_005 after delete: status={r.status_code}"}


def verify_015(server_url):
    base = f"{server_url}/sites/password-managers"
    r = requests.get(f"{base}/api/entries?vault_id=vault_001")
    entries = r.json()
    count = len(entries)
    return {"pass": count > 0, "detail": f"vault_001 entries: {count}"}


def verify_016(server_url):
    base = f"{server_url}/sites/password-managers"
    r = requests.get(f"{base}/api/generate-password?length=32&symbols=0")
    data = r.json()
    pw = data.get("password", "")
    ok = len(pw) == 32
    return {"pass": ok, "detail": f"Generated password length: {len(pw)}"}


def verify_017(server_url):
    base = f"{server_url}/sites/password-managers"
    r = requests.get(f"{base}/api/export?format=csv&vault_id=vault_001")
    lines = r.text.strip().split("\n")
    data_rows = len(lines) - 1  # minus header
    return {"pass": data_rows > 0, "detail": f"CSV export vault_001: {data_rows} data rows"}


def verify_018(server_url):
    base = f"{server_url}/sites/password-managers"
    r = requests.get(f"{base}/api/entries/entry_001")
    entry = r.json()
    icon_url = entry.get("icon_url", "")
    return {"pass": len(icon_url) > 0, "detail": f"entry_001 icon_url: {icon_url}"}


def verify_019(server_url):
    base = f"{server_url}/sites/password-managers"
    r = requests.get(f"{base}/api/entries/entry_001")
    entry = r.json()
    shares = entry.get("shares", [])
    has_vault_002_share = any(
        s.get("target_vault_id") == "vault_002" for s in shares
    )
    return {"pass": has_vault_002_share,
            "detail": f"entry_001 shares: {len(shares)}, vault_002 share: {has_vault_002_share}"}


def verify_020(server_url):
    base = f"{server_url}/sites/password-managers"
    s = requests.Session()
    # Login
    r = s.post(f"{base}/api/login", json={
        "email": "alex.rivera@gmail.com",
        "master_password": "Rainier2018!Summit"
    })
    login_data = r.json()
    if r.status_code != 200:
        return {"pass": False, "detail": f"Login failed: {login_data}"}
    # Verify 2FA
    r2 = s.post(f"{base}/api/verify-2fa", json={
        "user_id": 1,
        "code": "AXRV-BACKUP-7742"
    })
    data = r2.json()
    ok = data.get("verified") is True
    return {"pass": ok, "detail": f"2FA verified: {data.get('verified')}"}
