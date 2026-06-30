"""Per-macro verification functions for team-chat-workspace.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/team-chat-workspace"


def verify_macro_navigate_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/search?q=test")
    return {"pass": r.status_code == 200, "detail": f"Search page: {r.status_code}"}


def verify_macro_navigate_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/channel/ch-engineering")
    return {"pass": r.status_code == 200, "detail": f"Engineering channel page: {r.status_code}"}


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/thread/thr-001")
    return {"pass": r.status_code == 200, "detail": f"Thread detail page: {r.status_code}"}


def verify_macro_search_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/messages/search?q=the")
    data = r.json()
    return {"pass": data.get("count", 0) > 0, "detail": f"search 'the': {data.get('count')} results"}


def verify_macro_search_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/messages/search?q=the&channel=ch-general")
    data = r.json()
    results = data.get("results", [])
    ok = all(m.get("channel_id") == "ch-general" for m in results)
    return {"pass": ok, "detail": f"search+channel filter: {len(results)} results, all_general={ok}"}


def verify_macro_filter_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/members?department=Engineering")
    members = r.json()
    ok = all(m.get("department") == "Engineering" for m in members)
    return {"pass": ok and len(members) > 0, "detail": f"filter Engineering: {len(members)} members"}


def verify_macro_filter_by_date_range(server_url):
    r = requests.get(f"{_base(server_url)}/api/channels/ch-general/messages?date=2026-06-23")
    data = r.json()
    msgs = data.get("messages", [])
    ok = all("2026-06-23" in m.get("timestamp", "") for m in msgs)
    return {"pass": ok, "detail": f"filter 2026-06-23: {len(msgs)} messages"}


def verify_macro_extract_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/messages/search?q=birthday")
    data = r.json()
    results = data.get("results", [])
    return {"pass": len(results) > 0, "detail": f"extract 'birthday': {len(results)} results"}


def verify_macro_extract_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/messages/search?q=nginx+error")
    data = r.json()
    total = data.get("count", 0)
    return {"pass": total > 0, "detail": f"semantic 'nginx error': {total} results"}


def verify_macro_extract_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/members?department=Sales")
    members = r.json()
    return {"pass": len(members) > 0, "detail": f"extract Sales: {len(members)} members"}


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/channels/ch-general")
    channel = r.json()
    return {"pass": "member_count" in channel, "detail": f"extract ch-general: members={channel.get('member_count')}"}


def verify_macro_create_from_free_text(server_url):
    r = requests.post(f"{_base(server_url)}/api/channels", json={
        "name": "test-macro-channel",
        "description": "Test channel for macro verification",
    })
    ok = r.status_code in (201, 409)
    return {"pass": ok, "detail": f"create channel: {r.status_code}"}


def verify_macro_submit_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/messages/search?q=All-Hands")
    data = r.json()
    return {"pass": len(data.get("results", [])) > 0, "detail": f"submit query: {data.get('count')} results"}


def verify_macro_edit_by_form(server_url):
    base = _base(server_url)
    # Read original
    r = requests.get(f"{base}/api/channels/ch-general/messages")
    msgs = r.json().get("messages", [])
    if not msgs:
        return {"pass": False, "detail": "No messages to edit"}
    msg_id = msgs[0]["id"]
    original_text = msgs[0]["text"]
    # Edit
    r2 = requests.put(f"{base}/api/messages/{msg_id}", json={"text": "MACRO TEST EDIT"})
    data = r2.json()
    ok = data.get("edited") is True
    # Restore
    requests.put(f"{base}/api/messages/{msg_id}", json={"text": original_text})
    return {"pass": ok, "detail": f"edit {msg_id}: edited={ok}"}


def verify_macro_delete_from_table(server_url):
    base = _base(server_url)
    # Create a throwaway message, then delete it
    r = requests.post(f"{base}/api/channels/ch-random/messages", json={"text": "throwaway for delete test"})
    msg = r.json()
    msg_id = msg.get("id", "")
    r2 = requests.delete(f"{base}/api/messages/{msg_id}")
    data = r2.json()
    return {"pass": data.get("status") == "deleted", "detail": f"delete {msg_id}: {data.get('status')}"}


def verify_macro_upload_by_upload(server_url):
    base = _base(server_url)
    files = {"file": ("test.txt", b"test content", "text/plain")}
    r = requests.post(f"{base}/api/upload", files=files, data={"channel_id": "ch-general"})
    data = r.json()
    return {"pass": data.get("status") == "uploaded", "detail": f"upload: {data.get('filename')}"}


def verify_macro_post_from_free_text(server_url):
    r = requests.post(f"{_base(server_url)}/api/channels/ch-random/messages", json={
        "text": "Test macro post"
    })
    return {"pass": r.status_code == 201, "detail": f"post message: {r.status_code}"}


def verify_macro_react_by_chip(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/messages/msg-001/react", json={"emoji": ":test_macro:"})
    data = r.json()
    ok = data.get("status") in ("added", "removed")
    # Toggle back
    requests.post(f"{base}/api/messages/msg-001/react", json={"emoji": ":test_macro:"})
    return {"pass": ok, "detail": f"react: {data.get('status')}"}


def verify_macro_follow_by_dropdown(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/users/tc-u003/follow", json={})
    data = r.json()
    ok = data.get("action") in ("followed", "unfollowed")
    # Toggle back
    requests.post(f"{base}/api/users/tc-u003/follow", json={})
    return {"pass": ok, "detail": f"follow user: {data.get('action')}"}


def verify_macro_follow_by_toggle(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/channels/ch-sales/follow", json={})
    data = r.json()
    ok = data.get("action") in ("followed", "unfollowed")
    # Toggle back
    requests.post(f"{base}/api/channels/ch-sales/follow", json={})
    return {"pass": ok, "detail": f"follow channel: {data.get('action')}"}


def verify_macro_join_by_toggle(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/channels/ch-board-games/join", json={})
    data = r.json()
    ok = data.get("action") in ("joined", "left")
    # Toggle back
    requests.post(f"{base}/api/channels/ch-board-games/join", json={})
    return {"pass": ok, "detail": f"join channel: {data.get('action')}"}


def verify_macro_share_by_dropdown(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/messages/msg-001/share", json={"channel_id": "ch-random"})
    data = r.json()
    ok = data.get("status") == "shared"
    return {"pass": ok, "detail": f"share message: {data.get('status')}"}


def verify_macro_save_by_toggle(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/messages/msg-003/save", json={})
    data = r.json()
    ok = data.get("action") in ("saved", "unsaved")
    # Toggle back
    requests.post(f"{base}/api/messages/msg-003/save", json={})
    return {"pass": ok, "detail": f"save message: {data.get('action')}"}


def verify_macro_invite_by_form(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/channels/ch-engineering/invite", json={"user_id": "tc-u005"})
    data = r.json()
    ok = data.get("status") == "invited"
    return {"pass": ok, "detail": f"invite: {data.get('status')}"}


def verify_macro_block_by_toggle(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/members/tc-u010/block", json={})
    data = r.json()
    ok = data.get("action") in ("blocked", "unblocked")
    # Toggle back
    requests.post(f"{base}/api/members/tc-u010/block", json={})
    return {"pass": ok, "detail": f"block: {data.get('action')}"}


def verify_macro_message_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/messages/search?q=test")
    return {"pass": r.status_code == 200, "detail": f"message search: {r.status_code}"}


def verify_macro_message_from_free_text(server_url):
    r = requests.post(f"{_base(server_url)}/api/channels/ch-general/messages", json={
        "text": "Macro test message"
    })
    ok = r.status_code == 201
    return {"pass": ok, "detail": f"send message: {r.status_code}"}


def verify_macro_authenticate_by_form(server_url):
    base = _base(server_url)
    s = requests.Session()
    r = s.post(f"{base}/login", data={"user_id": "1"})
    ok = r.status_code in (200, 302)
    return {"pass": ok, "detail": f"login: status={r.status_code}"}
