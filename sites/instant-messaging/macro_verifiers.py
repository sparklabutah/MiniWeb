"""Per-macro verification functions for instant-messaging.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/instant-messaging"


def verify_macro_navigate_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/search/semantic?q=basketball")
    data = r.json()
    total = data.get("total", 0)
    return {"pass": r.status_code == 200 and total >= 0,
            "detail": f"navigate_by_semantic 'basketball': {total} results"}


def verify_macro_navigate_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/conversations")
    convs = r.json()
    ok = len(convs) > 0
    return {"pass": ok, "detail": f"navigate_by_dropdown: {len(convs)} conversations listed"}


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/conversation/conv-001")
    return {"pass": r.status_code == 200, "detail": f"navigate_by_route conv-001: {r.status_code}"}


def verify_macro_search_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/messages/search?q=the")
    data = r.json()
    count = data.get("count", 0)
    return {"pass": count > 0, "detail": f"search_by_query 'the': {count} results"}


def verify_macro_search_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/conversations/conv-001/search?q=catan")
    data = r.json()
    count = data.get("count", 0)
    return {"pass": r.status_code == 200 and count >= 0,
            "detail": f"search_by_dropdown 'catan' in conv-001: {count} results"}


def verify_macro_filter_by_toggle(server_url):
    r = requests.get(f"{_base(server_url)}/api/conversations/filter?filter=starred")
    data = r.json()
    count = data.get("count", 0)
    return {"pass": r.status_code == 200 and count >= 0,
            "detail": f"filter_by_toggle starred: {count} conversations"}


def verify_macro_extract_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/stats")
    data = r.json()
    has_total = "total_conversations" in data
    return {"pass": has_total,
            "detail": f"extract_by_query: total_conversations={data.get('total_conversations')}"}


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/conversations/conv-001")
    data = r.json()
    has_msgs = len(data.get("messages", [])) > 0
    return {"pass": has_msgs,
            "detail": f"extract_by_route: conv-001 has {len(data.get('messages', []))} messages"}


def verify_macro_create_from_free_text(server_url):
    r = requests.post(f"{_base(server_url)}/api/conversations",
                      json={"type": "group", "name": "Test Group",
                            "participants": ["im-u001", "im-u003"]})
    data = r.json()
    ok = "id" in data
    # Clean up: we don't need to remove it since data resets
    return {"pass": ok, "detail": f"create_from_free_text: created conv id={data.get('id')}"}


def verify_macro_edit_by_form(server_url):
    # Edit a message Alex sent, then edit it back
    r = requests.get(f"{_base(server_url)}/api/conversations/conv-001")
    msgs = r.json().get("messages", [])
    alex_msg = next((m for m in msgs if m["sender_id"] == "im-u001"), None)
    if not alex_msg:
        return {"pass": False, "detail": "No Alex message found in conv-001"}
    original_text = alex_msg["text"]
    msg_id = alex_msg["id"]
    # Edit
    r2 = requests.put(f"{_base(server_url)}/api/messages/{msg_id}/edit",
                      json={"text": "macro test edit"})
    data = r2.json()
    ok = data.get("action") == "edited"
    # Revert
    requests.put(f"{_base(server_url)}/api/messages/{msg_id}/edit",
                 json={"text": original_text})
    return {"pass": ok, "detail": f"edit_by_form: action={data.get('action')}"}


def verify_macro_delete_from_table(server_url):
    # Send a test message then delete it
    r = requests.post(f"{_base(server_url)}/api/conversations/conv-001/messages",
                      json={"text": "macro_delete_test_message"})
    msg = r.json()
    msg_id = msg.get("id", "")
    # Delete it
    r2 = requests.delete(f"{_base(server_url)}/api/messages/{msg_id}")
    data = r2.json()
    ok = data.get("action") == "deleted"
    return {"pass": ok, "detail": f"delete_from_table: action={data.get('action')}"}


def verify_macro_upload_by_upload(server_url):
    r = requests.post(f"{_base(server_url)}/api/conversations/conv-001/upload",
                      json={"file_name": "test_upload.txt", "type": "file",
                            "file_size_bytes": 100, "caption": "test"})
    data = r.json()
    ok = data.get("action") == "uploaded"
    return {"pass": ok, "detail": f"upload_by_upload: action={data.get('action')}"}


def verify_macro_post_from_free_text(server_url):
    r = requests.post(f"{_base(server_url)}/api/conversations/conv-008/messages",
                      json={"text": "macro_post_test"})
    data = r.json()
    ok = "id" in data and data.get("text") == "macro_post_test"
    return {"pass": ok, "detail": f"post_from_free_text: msg_id={data.get('id')}"}


def verify_macro_message_from_free_text(server_url):
    r = requests.post(f"{_base(server_url)}/api/conversations/conv-001/messages",
                      json={"text": "macro_message_test"})
    data = r.json()
    ok = "id" in data and data.get("text") == "macro_message_test"
    return {"pass": ok, "detail": f"message_from_free_text: msg_id={data.get('id')}"}


def verify_macro_follow_by_toggle(server_url):
    # Pin conv-003 (currently pinned_count=0) then unpin
    r = requests.post(f"{_base(server_url)}/api/conversations/conv-003/pin")
    data = r.json()
    ok = data.get("action") == "pinned"
    # Toggle back
    requests.post(f"{_base(server_url)}/api/conversations/conv-003/pin")
    return {"pass": ok, "detail": f"follow_by_toggle: action={data.get('action')}"}


def verify_macro_join_by_route(server_url):
    # Create a temp group, then join it with a test user
    r = requests.post(f"{_base(server_url)}/api/conversations",
                      json={"type": "group", "name": "Join Test",
                            "participants": ["im-u001"]})
    conv = r.json()
    conv_id = conv.get("id", "")
    # Join as im-u003
    r2 = requests.post(f"{_base(server_url)}/api/conversations/{conv_id}/join",
                       json={"user_id": "im-u003"})
    data = r2.json()
    ok = data.get("action") == "joined"
    return {"pass": ok, "detail": f"join_by_route: action={data.get('action')}"}


def verify_macro_share_by_dropdown(server_url):
    r = requests.post(f"{_base(server_url)}/api/messages/im-msg-001/share",
                      json={"conversation_id": "conv-005"})
    data = r.json()
    ok = data.get("action") == "shared"
    return {"pass": ok, "detail": f"share_by_dropdown: action={data.get('action')}"}


def verify_macro_save_by_toggle(server_url):
    r = requests.post(f"{_base(server_url)}/api/messages/im-msg-001/star")
    data = r.json()
    ok = data.get("action") == "starred"
    # Toggle back
    requests.post(f"{_base(server_url)}/api/messages/im-msg-001/star")
    return {"pass": ok, "detail": f"save_by_toggle: action={data.get('action')}"}


def verify_macro_invite_by_form(server_url):
    # Create a temp group, then invite someone
    r = requests.post(f"{_base(server_url)}/api/conversations",
                      json={"type": "group", "name": "Invite Test",
                            "participants": ["im-u001"]})
    conv = r.json()
    conv_id = conv.get("id", "")
    r2 = requests.post(f"{_base(server_url)}/api/conversations/{conv_id}/invite",
                       json={"user_id": "im-u005"})
    data = r2.json()
    ok = data.get("action") == "invited"
    return {"pass": ok, "detail": f"invite_by_form: action={data.get('action')}"}


def verify_macro_report_by_form(server_url):
    r = requests.post(f"{_base(server_url)}/api/messages/im-msg-001/report",
                      json={"reason": "test report"})
    data = r.json()
    ok = data.get("action") == "reported"
    return {"pass": ok, "detail": f"report_by_form: action={data.get('action')}"}


def verify_macro_block_by_toggle(server_url):
    # Block then unblock
    r = requests.post(f"{_base(server_url)}/api/contacts/im-u008/block")
    data = r.json()
    ok = data.get("action") == "blocked"
    # Toggle back
    requests.post(f"{_base(server_url)}/api/contacts/im-u008/block")
    return {"pass": ok, "detail": f"block_by_toggle: action={data.get('action')}"}


def verify_macro_authenticate_by_form(server_url):
    r = requests.post(f"{_base(server_url)}/api/login",
                      json={"user_id": "im-u002"})
    data = r.json()
    ok = data.get("user_id") == "im-u002"
    return {"pass": ok, "detail": f"authenticate_by_form: user_id={data.get('user_id')}"}
