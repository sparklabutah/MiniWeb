"""Per-macro verification functions for ai-chatbots.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/ai-chatbots"


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/chat")
    return {"pass": r.status_code == 200, "detail": f"Chat page: {r.status_code}"}


def verify_macro_search_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/knowledge/search?q=python")
    results = r.json()
    return {"pass": len(results) > 0, "detail": f"search_by_query 'python': {len(results)} results"}


def verify_macro_search_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/knowledge/semantic?q=web+development")
    results = r.json()
    return {"pass": r.status_code == 200, "detail": f"search_by_semantic: {len(results)} results"}


def verify_macro_extract_from_table(server_url):
    r = requests.get(f"{_base(server_url)}/api/knowledge")
    entries = r.json()
    return {"pass": len(entries) > 0 and "topic" in entries[0],
            "detail": f"extract_from_table: {len(entries)} KB entries"}


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/knowledge/1")
    entry = r.json()
    return {"pass": "content" in entry,
            "detail": f"extract_by_route: entry topic={entry.get('topic', '')}"}


def verify_macro_create_from_free_text(server_url):
    r = requests.post(f"{_base(server_url)}/api/chat", json={
        "message": "Tell me about databases",
        "bot": "Assistant"
    })
    data = r.json()
    return {"pass": len(data.get("response", "")) > 10,
            "detail": f"create_from_free_text: response length={len(data.get('response', ''))}"}


def verify_macro_submit_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/faq/search?q=chatbot")
    results = r.json()
    return {"pass": r.status_code == 200, "detail": f"submit_by_query: {len(results)} FAQ results"}


def verify_macro_submit_by_radio(server_url):
    r = requests.put(f"{_base(server_url)}/api/users/4/subscription",
                     json={"plan": "pro"})
    data = r.json()
    ok = data.get("subscription") == "pro"
    # Reset
    requests.put(f"{_base(server_url)}/api/users/4/subscription",
                 json={"plan": "free"})
    return {"pass": ok, "detail": f"submit_by_radio: subscription={data.get('subscription')}"}


def verify_macro_edit_by_query(server_url):
    r = requests.put(f"{_base(server_url)}/api/conversations/conv_001",
                     json={"title": "Test Edit Title"})
    data = r.json()
    ok = data.get("title") == "Test Edit Title"
    # Reset
    requests.put(f"{_base(server_url)}/api/conversations/conv_001",
                 json={"title": "Python basics help"})
    return {"pass": ok, "detail": f"edit_by_query: title={data.get('title')}"}


def verify_macro_edit_by_form(server_url):
    r = requests.put(f"{_base(server_url)}/api/users/4/preferences",
                     json={"default_bot": "Creative", "theme": "light"})
    data = r.json()
    prefs = data.get("preferences", {})
    ok = prefs.get("default_bot") == "Creative"
    # Reset
    requests.put(f"{_base(server_url)}/api/users/4/preferences",
                 json={"default_bot": "Assistant", "theme": "dark"})
    return {"pass": ok, "detail": f"edit_by_form: default_bot={prefs.get('default_bot')}"}


def verify_macro_delete_from_table(server_url):
    # Create a temp conversation to delete
    r = requests.post(f"{_base(server_url)}/api/chat", json={
        "message": "temp test", "bot": "Assistant"
    })
    conv_id = r.json().get("conversation_id")
    r2 = requests.delete(f"{_base(server_url)}/api/conversations/{conv_id}")
    data = r2.json()
    return {"pass": data.get("deleted") == conv_id,
            "detail": f"delete_from_table: deleted={data.get('deleted')}"}


def verify_macro_configure_by_query(server_url):
    r = requests.put(f"{_base(server_url)}/api/users/4/preferences",
                     json={"default_bot": "Analyst"})
    data = r.json()
    ok = data.get("preferences", {}).get("default_bot") == "Analyst"
    # Reset
    requests.put(f"{_base(server_url)}/api/users/4/preferences",
                 json={"default_bot": "Assistant"})
    return {"pass": ok, "detail": f"configure_by_query: set bot to Analyst"}


def verify_macro_configure_by_dropdown(server_url):
    r = requests.put(f"{_base(server_url)}/api/users/4/preferences",
                     json={"font_size": "large", "theme": "light"})
    data = r.json()
    prefs = data.get("preferences", {})
    ok = prefs.get("font_size") == "large"
    # Reset
    requests.put(f"{_base(server_url)}/api/users/4/preferences",
                 json={"font_size": "medium", "theme": "dark"})
    return {"pass": ok, "detail": f"configure_by_dropdown: font_size={prefs.get('font_size')}"}


def verify_macro_play_by_playback(server_url):
    r = requests.post(f"{_base(server_url)}/api/chat", json={
        "message": "hello", "bot": "Assistant"
    })
    data = r.json()
    resp = data.get("response", "")
    return {"pass": "hello" in resp.lower() or "hi" in resp.lower(),
            "detail": f"play_by_playback: response={resp[:60]}"}


def verify_macro_export_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/export?type=knowledge&format=csv")
    lines = r.text.strip().split("\n")
    return {"pass": len(lines) > 1, "detail": f"export CSV: {len(lines)} lines"}


def verify_macro_upload_by_upload(server_url):
    r = requests.post(f"{_base(server_url)}/api/upload", json={
        "topic": "Test Upload",
        "category": "test",
        "content": "This is a test upload for macro verification.",
        "keywords": ["test"]
    })
    data = r.json()
    ok = data.get("id") is not None
    return {"pass": ok, "detail": f"upload: id={data.get('id')}"}


def verify_macro_share_by_dropdown(server_url):
    r = requests.post(f"{_base(server_url)}/api/conversations/conv_001/share",
                      json={"share_with": "public"})
    data = r.json()
    ok = data.get("shared") is True
    return {"pass": ok, "detail": f"share: shared={data.get('shared')}"}


def verify_macro_save_by_toggle(server_url):
    r = requests.post(f"{_base(server_url)}/api/users/4/save-prompt",
                      json={"prompt_id": 99})
    data = r.json()
    ok = data.get("action") == "saved"
    # Toggle back
    requests.post(f"{_base(server_url)}/api/users/4/save-prompt",
                  json={"prompt_id": 99})
    return {"pass": ok, "detail": f"save_by_toggle: action={data.get('action')}"}


def verify_macro_subscribe_by_toggle(server_url):
    # Toggle save_history off
    r = requests.put(f"{_base(server_url)}/api/users/4/preferences",
                     json={"save_history": False})
    data = r.json()
    ok = data.get("preferences", {}).get("save_history") is False
    # Toggle back
    requests.put(f"{_base(server_url)}/api/users/4/preferences",
                 json={"save_history": True})
    return {"pass": ok, "detail": f"subscribe_by_toggle: save_history toggled off"}


def verify_macro_authenticate_by_form(server_url):
    r = requests.post(f"{_base(server_url)}/api/login",
                      json={"username": "alice", "password": "pass123"})
    data = r.json()
    ok = data.get("user_id") == 1
    return {"pass": ok, "detail": f"authenticate: user_id={data.get('user_id')}"}


def verify_macro_register_by_form(server_url):
    r = requests.post(f"{_base(server_url)}/api/register", json={
        "username": "macro_test_user",
        "password": "testpass",
        "email": "macro@test.com",
        "display_name": "Macro Test"
    })
    data = r.json()
    ok = data.get("user_id") is not None
    return {"pass": ok, "detail": f"register: user_id={data.get('user_id')}"}
