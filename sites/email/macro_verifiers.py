"""Per-macro verification functions for email.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/email"


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/users/1")
    data = r.json()
    return {"pass": "email_address" in data and "name" in data,
            "detail": f"User data keys: {list(data.keys())[:6]}"}


def verify_macro_authenticate_by_form(server_url):
    s = requests.Session()
    r = s.post(f"{_base(server_url)}/api/login",
               json={"username": "lynn_blair", "password": "pass123"})
    data = r.json()
    ok = data.get("user_id") == 1
    return {"pass": ok, "detail": f"authenticate: user_id={data.get('user_id')}"}


def verify_macro_filter_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/messages?user_id=1&folder=inbox")
    data = r.json()
    messages = data.get("messages", [])
    ok = all(m.get("folder") == "inbox" for m in messages)
    return {"pass": ok and len(messages) > 0,
            "detail": f"Inbox filter: {len(messages)} messages, all_inbox={ok}"}


def verify_macro_sort_by_ranking(server_url):
    r = requests.get(f"{_base(server_url)}/api/messages?user_id=1&sort=subject")
    data = r.json()
    messages = data.get("messages", [])
    if len(messages) < 2:
        return {"pass": True, "detail": "Too few messages to verify sort"}
    subjects = [m.get("subject", "").lower() for m in messages]
    is_sorted = all(subjects[i] <= subjects[i+1] for i in range(min(len(subjects)-1, 20)))
    return {"pass": is_sorted, "detail": f"Sort by subject: sorted={is_sorted}"}


def verify_macro_submit_form(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/messages/compose", json={
        "user_id": 5,
        "to": "lynn.blair@enron.com",
        "subject": "Macro Test",
        "body": "Testing compose"
    })
    data = r.json()
    ok = data.get("status") == "sent"
    return {"pass": ok, "detail": f"submit_form: compose status={data.get('status')}"}


def verify_macro_toggle_by_api(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/messages/1/star", json={"user_id": 1})
    data = r.json()
    starred = data.get("is_starred")
    # Toggle back
    requests.post(f"{base}/api/messages/1/star", json={"user_id": 1})
    return {"pass": starred is not None,
            "detail": f"toggle_by_api: is_starred={starred}"}
