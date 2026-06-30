"""Per-macro verification functions for live.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/live"


def _login(server_url, username="alex_rivera", password="stream2024"):
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login",
           json={"username": username, "password": password})
    return s


def verify_macro_navigate_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/streams/semantic?q=coding+tutorial")
    results = r.json()
    return {"pass": r.status_code == 200,
            "detail": f"navigate_by_semantic: {len(results)} results"}


def verify_macro_navigate_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/categories")
    cats = r.json()
    if not cats:
        return {"pass": False, "detail": "No categories returned"}
    cat_name = cats[0]["name"]
    r2 = requests.get(f"{_base(server_url)}/?category={cat_name}")
    return {"pass": r2.status_code == 200,
            "detail": f"navigate_by_dropdown: category '{cat_name}' page {r2.status_code}"}


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/stream/stream-001")
    return {"pass": r.status_code == 200,
            "detail": f"navigate_by_route: stream detail page {r.status_code}"}


def verify_macro_search_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/streams/search?q=coding")
    results = r.json()
    return {"pass": len(results) > 0,
            "detail": f"search_by_query 'coding': {len(results)} results"}


def verify_macro_filter_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/streams?category=Gaming")
    streams = r.json()
    ok = all(s["category"] == "Gaming" for s in streams)
    return {"pass": ok and len(streams) > 0,
            "detail": f"filter_by_dropdown Gaming: {len(streams)} streams, all_gaming={ok}"}


def verify_macro_sort_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/streams?sort=viewers")
    streams = r.json()
    if len(streams) < 2:
        return {"pass": True, "detail": "Too few streams to verify sort"}
    views = [s.get("total_views", 0) for s in streams]
    is_sorted = all(views[i] >= views[i + 1] for i in range(len(views) - 1))
    return {"pass": is_sorted,
            "detail": f"sort_by_dropdown: sorted_desc={is_sorted}"}


def verify_macro_create_by_timestamp(server_url):
    s = _login(server_url)
    r = s.post(f"{_base(server_url)}/api/clips",
               json={
                   "stream_id": "stream-001",
                   "title": "Macro test clip",
                   "duration_seconds": 15,
                   "timestamp_seconds": 120,
               })
    data = r.json()
    ok = r.status_code == 201 and data.get("id") is not None
    # Clean up: clips persist but that's fine for testing
    return {"pass": ok,
            "detail": f"create_by_timestamp: status={r.status_code}, clip_id={data.get('id')}"}


def verify_macro_select_by_slider(server_url):
    s = _login(server_url)
    r = s.post(f"{_base(server_url)}/api/streams/stream-001/playback",
               json={"quality": "480p"})
    data = r.json()
    quality = data.get("playback", {}).get("quality", "")
    # Reset
    s.post(f"{_base(server_url)}/api/streams/stream-001/playback",
           json={"quality": "auto"})
    return {"pass": quality == "480p",
            "detail": f"select_by_slider: quality={quality}"}


def verify_macro_play_by_timestamp(server_url):
    s = _login(server_url)
    r = s.post(f"{_base(server_url)}/api/streams/stream-001/playback",
               json={"timestamp_seconds": 300})
    data = r.json()
    ts = data.get("playback", {}).get("current_timestamp", -1)
    # Reset
    s.post(f"{_base(server_url)}/api/streams/stream-001/playback",
           json={"timestamp_seconds": 0})
    return {"pass": ts == 300,
            "detail": f"play_by_timestamp: jumped to {ts}"}


def verify_macro_play_by_playback(server_url):
    s = _login(server_url)
    r = s.post(f"{_base(server_url)}/api/streams/stream-001/playback",
               json={"playback_speed": 2.0})
    data = r.json()
    speed = data.get("playback", {}).get("playback_speed", -1)
    # Reset
    s.post(f"{_base(server_url)}/api/streams/stream-001/playback",
           json={"playback_speed": 1.0})
    return {"pass": speed == 2.0,
            "detail": f"play_by_playback: speed={speed}"}


def verify_macro_post_from_free_text(server_url):
    s = _login(server_url)
    r = s.post(f"{_base(server_url)}/api/streams/stream-001/chat",
               json={"message": "Macro test message"})
    data = r.json()
    ok = r.status_code == 201 and data.get("message") == "Macro test message"
    return {"pass": ok,
            "detail": f"post_from_free_text: status={r.status_code}, msg_id={data.get('id')}"}


def verify_macro_follow_by_toggle(server_url):
    s = _login(server_url, "marcus_chen", "code4life")
    # Marcus follows nathan (ls-u-003) -- check if already following
    # Toggle follow on
    r = s.post(f"{_base(server_url)}/api/channels/ls-u-004/follow")
    data = r.json()
    status1 = data.get("status", "")
    # Toggle back
    r2 = s.post(f"{_base(server_url)}/api/channels/ls-u-004/follow")
    data2 = r2.json()
    status2 = data2.get("status", "")
    ok = (status1 == "followed" and status2 == "unfollowed") or \
         (status1 == "unfollowed" and status2 == "followed")
    return {"pass": ok,
            "detail": f"follow_by_toggle: first={status1}, second={status2}"}


def verify_macro_share_by_dropdown(server_url):
    s = _login(server_url)
    r = s.post(f"{_base(server_url)}/api/streams/stream-001/share",
               json={"platform": "reddit"})
    data = r.json()
    ok = r.status_code == 201 and data.get("status") == "shared"
    return {"pass": ok,
            "detail": f"share_by_dropdown: status={data.get('status')}, platform=reddit"}


def verify_macro_report_by_form(server_url):
    s = _login(server_url)
    r = s.post(f"{_base(server_url)}/api/report",
               json={
                   "target_type": "stream",
                   "target_id": "stream-012",
                   "reason": "other",
                   "description": "Macro test report",
               })
    data = r.json()
    ok = r.status_code == 201 and data.get("status") == "submitted"
    return {"pass": ok,
            "detail": f"report_by_form: status={data.get('status')}"}


def verify_macro_subscribe_by_toggle(server_url):
    s = _login(server_url, "marcus_chen", "code4life")
    # Marcus subscribes to natalie (ls-u-004) -- not yet subscribed
    r = s.post(f"{_base(server_url)}/api/channels/ls-u-004/subscribe")
    data = r.json()
    status1 = data.get("status", "")
    # Toggle back
    r2 = s.post(f"{_base(server_url)}/api/channels/ls-u-004/subscribe")
    data2 = r2.json()
    status2 = data2.get("status", "")
    ok = status1 == "subscribed" and status2 == "unsubscribed"
    return {"pass": ok,
            "detail": f"subscribe_by_toggle: first={status1}, second={status2}"}


def verify_macro_join_by_toggle(server_url):
    s = _login(server_url)
    r = s.post(f"{_base(server_url)}/api/streams/stream-001/join")
    data = r.json()
    status1 = data.get("status", "")
    # Toggle back
    r2 = s.post(f"{_base(server_url)}/api/streams/stream-001/join")
    data2 = r2.json()
    status2 = data2.get("status", "")
    ok = (status1 == "joined" and status2 == "left") or \
         (status1 == "left" and status2 == "joined")
    return {"pass": ok,
            "detail": f"join_by_toggle: first={status1}, second={status2}"}


def verify_macro_pay_by_dropdown(server_url):
    s = _login(server_url)
    r = s.post(f"{_base(server_url)}/api/channels/ls-u-003/gift",
               json={
                   "recipient_username": "jake_morrison",
                   "tier": "tier_1",
               })
    data = r.json()
    ok = r.status_code == 201 and data.get("status") == "gifted"
    return {"pass": ok,
            "detail": f"pay_by_dropdown: status={data.get('status')}, tier=tier_1"}


def verify_macro_redeem_by_dropdown(server_url):
    s = _login(server_url, "jake_morrison", "sync2025")
    r = s.post(f"{_base(server_url)}/api/channels/ls-u-002/redeem",
               json={"reward_id": "reward-001"})
    data = r.json()
    ok = r.status_code == 201 and data.get("status") == "redeemed"
    return {"pass": ok,
            "detail": f"redeem_by_dropdown: status={data.get('status')}"}


def verify_macro_authenticate_by_form(server_url):
    s = requests.Session()
    r = s.post(f"{_base(server_url)}/api/login",
               json={"username": "alex_rivera", "password": "stream2024"})
    data = r.json()
    ok = data.get("user_id") == "ls-u-001"
    return {"pass": ok,
            "detail": f"authenticate_by_form: user_id={data.get('user_id')}"}


def verify_macro_register_by_form(server_url):
    s = requests.Session()
    r = s.post(f"{_base(server_url)}/api/register",
               json={
                   "username": "macro_test_user",
                   "display_name": "Macro Test",
                   "password": "macrotest123",
               })
    data = r.json()
    ok = r.status_code == 201 and data.get("user_id") is not None
    return {"pass": ok,
            "detail": f"register_by_form: user_id={data.get('user_id')}, status={r.status_code}"}
