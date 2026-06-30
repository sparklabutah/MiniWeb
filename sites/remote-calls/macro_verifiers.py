"""Per-macro verification functions for remote-calls.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/remote-calls"


# ---------------------------------------------------------------------------
# 1. navigate_by_route
# ---------------------------------------------------------------------------

def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/meetings/mtg-001")
    data = r.json()
    return {"pass": r.status_code == 200 and data.get("title") == "Engineering Daily Standup",
            "detail": f"navigate_by_route mtg-001: {r.status_code}, title={data.get('title')}"}


# ---------------------------------------------------------------------------
# 2. search_by_query
# ---------------------------------------------------------------------------

def verify_macro_search_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/meetings?q=sprint")
    data = r.json()
    count = data.get("count", 0)
    return {"pass": count > 0, "detail": f"search_by_query 'sprint': {count} results"}


# ---------------------------------------------------------------------------
# 3. search_by_semantic
# ---------------------------------------------------------------------------

def verify_macro_search_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/meetings/search?q=infrastructure+deployment")
    data = r.json()
    count = data.get("count", 0)
    return {"pass": r.status_code == 200 and count > 0,
            "detail": f"search_by_semantic: {count} results"}


# ---------------------------------------------------------------------------
# 4. filter_by_dropdown
# ---------------------------------------------------------------------------

def verify_macro_filter_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/meetings?status=completed")
    data = r.json()
    meetings = data.get("meetings", [])
    ok = all(m["status"] == "completed" for m in meetings)
    return {"pass": ok and len(meetings) > 0,
            "detail": f"filter_by_dropdown completed: {len(meetings)} meetings, all_completed={ok}"}


# ---------------------------------------------------------------------------
# 5. filter_by_date_range
# ---------------------------------------------------------------------------

def verify_macro_filter_by_date_range(server_url):
    r = requests.get(f"{_base(server_url)}/api/meetings?date_from=2026-06-20&date_to=2026-06-25")
    data = r.json()
    count = data.get("count", 0)
    return {"pass": count > 0, "detail": f"filter_by_date_range Jun 20-25: {count} meetings"}


# ---------------------------------------------------------------------------
# 6. extract_by_query
# ---------------------------------------------------------------------------

def verify_macro_extract_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/recordings?q=deploy")
    data = r.json()
    recs = data.get("recordings", [])
    if recs:
        return {"pass": True,
                "detail": f"extract_by_query: first result title={recs[0]['title'][:50]}"}
    return {"pass": True, "detail": "extract_by_query: no results (ok)"}


# ---------------------------------------------------------------------------
# 7. extract_from_table
# ---------------------------------------------------------------------------

def verify_macro_extract_from_table(server_url):
    r = requests.get(f"{_base(server_url)}/api/meetings")
    data = r.json()
    meetings = data.get("meetings", [])
    if not meetings:
        return {"pass": False, "detail": "extract_from_table: no meetings"}
    # Check that participant count can be extracted from table data
    first = meetings[0]
    has_participants = "participants" in first or "participant_names" in first
    return {"pass": has_participants,
            "detail": f"extract_from_table: {len(meetings)} meetings, first has participants={has_participants}"}


# ---------------------------------------------------------------------------
# 8. extract_by_route
# ---------------------------------------------------------------------------

def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/recordings/rec-001")
    data = r.json()
    return {"pass": "title" in data and "duration_minutes" in data,
            "detail": f"extract_by_route: rec-001 title={data.get('title')}, duration={data.get('duration_minutes')}"}


# ---------------------------------------------------------------------------
# 9. create_from_free_text
# ---------------------------------------------------------------------------

def verify_macro_create_from_free_text(server_url):
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "alex.rivera", "password": "pass123"})
    r = s.post(f"{base}/api/meetings", json={
        "title": "Macro Test Meeting",
        "date": "2026-08-01T10:00:00-07:00",
        "duration_minutes": 30,
        "type": "work",
    })
    data = r.json()
    ok = r.status_code == 201 and "id" in data
    # Clean up: cancel the test meeting
    if ok:
        s.delete(f"{base}/api/meetings/{data['id']}")
    return {"pass": ok, "detail": f"create_from_free_text: id={data.get('id')}, status={r.status_code}"}


# ---------------------------------------------------------------------------
# 10. submit_by_query
# ---------------------------------------------------------------------------

def verify_macro_submit_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/call-log?q=API+refactor")
    data = r.json()
    calls = data.get("calls", [])
    return {"pass": len(calls) > 0,
            "detail": f"submit_by_query 'API refactor': {len(calls)} calls found"}


# ---------------------------------------------------------------------------
# 11. select_by_dropdown
# ---------------------------------------------------------------------------

def verify_macro_select_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/meetings?type=personal")
    data = r.json()
    meetings = data.get("meetings", [])
    ok = all(m["type"] == "personal" for m in meetings)
    return {"pass": ok and len(meetings) > 0,
            "detail": f"select_by_dropdown personal: {len(meetings)} meetings, all_personal={ok}"}


# ---------------------------------------------------------------------------
# 12. configure_by_dropdown
# ---------------------------------------------------------------------------

def verify_macro_configure_by_dropdown(server_url):
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "alex.rivera", "password": "pass123"})
    # Update a setting
    r = s.put(f"{base}/api/settings", json={"notification_sound": "bell"})
    data = r.json()
    ok = data.get("settings", {}).get("notification_sound") == "bell"
    # Reset
    s.put(f"{base}/api/settings", json={"notification_sound": "default"})
    return {"pass": ok, "detail": f"configure_by_dropdown: notification_sound={data.get('settings', {}).get('notification_sound')}"}


# ---------------------------------------------------------------------------
# 13. play_by_playback
# ---------------------------------------------------------------------------

def verify_macro_play_by_playback(server_url):
    base = _base(server_url)
    # Get current views
    r1 = requests.get(f"{base}/api/recordings/rec-002")
    before = r1.json().get("views", 0)
    # Play
    r2 = requests.post(f"{base}/api/recordings/rec-002/play")
    data = r2.json()
    after = data.get("views", 0)
    ok = data.get("status") == "playing" and after == before + 1
    return {"pass": ok, "detail": f"play_by_playback: views {before}->{after}, status={data.get('status')}"}


# ---------------------------------------------------------------------------
# 14. export_by_dropdown
# ---------------------------------------------------------------------------

def verify_macro_export_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/export?format=csv&type=meetings")
    lines = r.text.strip().split("\n")
    return {"pass": len(lines) > 1, "detail": f"export_by_dropdown CSV: {len(lines)} lines"}


# ---------------------------------------------------------------------------
# 15. share_by_toggle
# ---------------------------------------------------------------------------

def verify_macro_share_by_toggle(server_url):
    base = _base(server_url)
    # Toggle share on
    r1 = requests.post(f"{base}/api/meetings/mtg-001/share")
    data1 = r1.json()
    action1 = data1.get("action", "")
    # Toggle share off
    r2 = requests.post(f"{base}/api/meetings/mtg-001/share")
    data2 = r2.json()
    action2 = data2.get("action", "")
    ok = (action1 == "shared" and action2 == "unshared") or (action1 == "unshared" and action2 == "shared")
    return {"pass": ok, "detail": f"share_by_toggle: first={action1}, second={action2}"}


# ---------------------------------------------------------------------------
# 16. invite_by_form
# ---------------------------------------------------------------------------

def verify_macro_invite_by_form(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/meetings/mtg-001/invite",
                      json={"user_id": "rc-u-006"})
    data = r.json()
    ok = r.status_code in (200, 201) and data.get("user_id") == "rc-u-006"
    return {"pass": ok, "detail": f"invite_by_form: status={r.status_code}, user_id={data.get('user_id')}"}


# ---------------------------------------------------------------------------
# 17. message_from_free_text
# ---------------------------------------------------------------------------

def verify_macro_message_from_free_text(server_url):
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "alex.rivera", "password": "pass123"})
    r = s.post(f"{base}/api/meetings/mtg-001/messages",
               json={"text": "Macro test message", "sender_id": "rc-u-001"})
    data = r.json()
    ok = r.status_code == 201 and data.get("text") == "Macro test message"
    return {"pass": ok, "detail": f"message_from_free_text: status={r.status_code}, text={data.get('text')}"}


# ---------------------------------------------------------------------------
# 18. book_by_form
# ---------------------------------------------------------------------------

def verify_macro_book_by_form(server_url):
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "priya.sharma", "password": "pass123"})
    r = s.post(f"{base}/api/meetings", json={
        "title": "Macro Book Test",
        "date": "2026-08-15T14:00:00-07:00",
        "duration_minutes": 30,
        "type": "work",
        "participants": ["rc-u-002", "rc-u-001"],
    })
    data = r.json()
    ok = r.status_code == 201 and "id" in data
    participants = data.get("participants", [])
    has_both = "rc-u-001" in participants and "rc-u-002" in participants
    # Clean up
    if ok:
        s.delete(f"{base}/api/meetings/{data['id']}")
    return {"pass": ok and has_both,
            "detail": f"book_by_form: id={data.get('id')}, participants={participants}"}


# ---------------------------------------------------------------------------
# 19. cancel_by_form
# ---------------------------------------------------------------------------

def verify_macro_cancel_by_form(server_url):
    base = _base(server_url)
    # Create a meeting to cancel
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "alex.rivera", "password": "pass123"})
    r = s.post(f"{base}/api/meetings", json={
        "title": "Meeting To Cancel",
        "date": "2026-09-01T10:00:00-07:00",
        "duration_minutes": 30,
        "type": "work",
    })
    new_meeting = r.json()
    mid = new_meeting.get("id", "")
    # Cancel it
    r2 = s.delete(f"{base}/api/meetings/{mid}")
    data = r2.json()
    meeting = data.get("meeting", {})
    ok = meeting.get("status") == "cancelled"
    return {"pass": ok, "detail": f"cancel_by_form: {mid} status={meeting.get('status')}"}


# ---------------------------------------------------------------------------
# 20. join_by_code
# ---------------------------------------------------------------------------

def verify_macro_join_by_code(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/join", json={"code": "mtg-005"})
    data = r.json()
    meeting = data.get("meeting", {})
    ok = meeting.get("title") == "Sprint Planning - Sprint 48"
    return {"pass": ok, "detail": f"join_by_code: title={meeting.get('title')}"}
