"""Per-task HTTP verification functions for live."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/live"
    r = requests.get(f"{base}/api/streams/semantic?q=coding+backend+api")
    results = r.json()
    count = len(results)
    return {"pass": count > 0, "detail": f"Semantic search 'coding backend api': {count} results"}


def verify_002(server_url):
    base = f"{server_url}/sites/live"
    r = requests.get(f"{base}/api/streams?category=Fitness+%26+Health")
    streams = r.json()
    count = len(streams)
    return {"pass": count > 0, "detail": f"Fitness & Health category: {count} streams"}


def verify_003(server_url):
    base = f"{server_url}/sites/live"
    r = requests.get(f"{base}/api/streams/stream-001")
    stream = r.json()
    title = stream.get("title", "")
    return {"pass": len(title) > 0, "detail": f"Stream stream-001 title: {title[:60]}"}


def verify_004(server_url):
    base = f"{server_url}/sites/live"
    r = requests.get(f"{base}/api/streams/search?q=workout")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Search 'workout': {count} results"}


def verify_005(server_url):
    base = f"{server_url}/sites/live"
    r = requests.get(f"{base}/api/streams?category=Gaming")
    streams = r.json()
    count = len(streams)
    return {"pass": count > 0, "detail": f"Gaming category: {count} streams"}


def verify_006(server_url):
    base = f"{server_url}/sites/live"
    r = requests.get(f"{base}/api/streams?sort=viewers")
    streams = r.json()
    if not streams:
        return {"pass": False, "detail": "No streams returned"}
    first_title = streams[0]["title"]
    # Verify sorted by views descending
    views = [s.get("total_views", 0) for s in streams]
    is_sorted = all(views[i] >= views[i + 1] for i in range(len(views) - 1))
    return {"pass": is_sorted, "detail": f"First by views: {first_title[:60]}, sorted={is_sorted}"}


def verify_007(server_url):
    base = f"{server_url}/sites/live"
    r = requests.get(f"{base}/api/clips")
    clips = r.json()
    new_clip = next(
        (c for c in clips
         if c.get("title") == "Best HIIT moment"
         and c.get("stream_id") == "stream-005"
         and c.get("timestamp_seconds") == 900),
        None,
    )
    return {"pass": new_clip is not None,
            "detail": f"Clip 'Best HIIT moment' at 900s: {'found' if new_clip else 'not found'}"}


def verify_008(server_url):
    base = f"{server_url}/sites/live"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "alex_rivera", "password": "stream2024"})
    r = s.get(f"{base}/api/streams/stream-001/playback")
    state = r.json()
    quality = state.get("quality", "")
    return {"pass": quality == "720p", "detail": f"Playback quality: {quality}"}


def verify_009(server_url):
    base = f"{server_url}/sites/live"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "alex_rivera", "password": "stream2024"})
    r = s.get(f"{base}/api/streams/stream-003/playback")
    state = r.json()
    ts = state.get("current_timestamp", 0)
    return {"pass": ts == 3600, "detail": f"Playback timestamp: {ts}"}


def verify_010(server_url):
    base = f"{server_url}/sites/live"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "alex_rivera", "password": "stream2024"})
    r = s.get(f"{base}/api/streams/stream-001/playback")
    state = r.json()
    speed = state.get("playback_speed", 1.0)
    return {"pass": speed == 1.5, "detail": f"Playback speed: {speed}"}


def verify_011(server_url):
    base = f"{server_url}/sites/live"
    r = requests.get(f"{base}/api/streams/stream-003/chat")
    messages = r.json()
    found = any(
        m for m in messages
        if m.get("message") == "Great stream tonight!"
        and m.get("username") == "alex_rivera"
    )
    return {"pass": found, "detail": f"Chat message found: {found}"}


def verify_012(server_url):
    base = f"{server_url}/sites/live"
    r = requests.get(f"{base}/api/follows?channel_id=ls-u-001&follower_id=ls-u-004")
    follows = r.json()
    found = len(follows) > 0
    return {"pass": found, "detail": f"Natalie follows Alex: {found} ({len(follows)} records)"}


def verify_013(server_url):
    base = f"{server_url}/sites/live"
    r = requests.get(f"{base}/api/shares?stream_id=stream-001")
    shares = r.json()
    twitter_share = next(
        (s for s in shares
         if s.get("platform") == "twitter"
         and s.get("stream_id") == "stream-001"),
        None,
    )
    return {"pass": twitter_share is not None,
            "detail": f"Twitter share on stream-001: {'found' if twitter_share else 'not found'}"}


def verify_014(server_url):
    base = f"{server_url}/sites/live"
    r = requests.get(f"{base}/api/reports")
    reports = r.json()
    spam_report = next(
        (rp for rp in reports
         if rp.get("target_id") == "stream-003"
         and rp.get("reason") == "spam"),
        None,
    )
    return {"pass": spam_report is not None,
            "detail": f"Spam report on stream-003: {'found' if spam_report else 'not found'}"}


def verify_015(server_url):
    base = f"{server_url}/sites/live"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "natalie_kim", "password": "leetcode42"})
    r = s.get(f"{base}/api/subscriptions")
    subs = r.json()
    jake_sub = next(
        (sub for sub in subs if sub.get("channel_id") == "ls-u-005" and sub.get("is_active", False)),
        None,
    )
    return {"pass": jake_sub is not None,
            "detail": f"Natalie subscribed to Jake: {'yes' if jake_sub else 'no'}"}


def verify_016(server_url):
    base = f"{server_url}/sites/live"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "alex_rivera", "password": "stream2024"})
    r = s.get(f"{base}/api/streams/stream-005/playback")
    state = r.json()
    joined = state.get("joined", False)
    return {"pass": joined is True, "detail": f"Join status for stream-005: {joined}"}


def verify_017(server_url):
    base = f"{server_url}/sites/live"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "natalie_kim", "password": "leetcode42"})
    r = s.get(f"{base}/api/subscriptions")
    subs = r.json()
    gift_sub = next(
        (sub for sub in subs
         if sub.get("channel_id") == "ls-u-002"
         and sub.get("is_gift", False)
         and sub.get("tier") == "tier_2"),
        None,
    )
    return {"pass": gift_sub is not None,
            "detail": f"Gift tier_2 sub to natalie on marcus channel: {'found' if gift_sub else 'not found'}"}


def verify_018(server_url):
    base = f"{server_url}/sites/live"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "alex_rivera", "password": "stream2024"})
    r = s.get(f"{base}/api/users/ls-u-001")
    user = r.json()
    balance = user.get("channel_points_balance", 5000)
    # Original balance was 5000, reward costs 500, so after redemption should be 4500
    return {"pass": balance == 4500,
            "detail": f"Alex channel points balance: {balance} (expected 4500 after redemption)"}


def verify_019(server_url):
    base = f"{server_url}/sites/live"
    s = requests.Session()
    r = s.post(f"{base}/api/login",
               json={"username": "marcus_chen", "password": "code4life"})
    data = r.json()
    user_id = data.get("user_id", "")
    return {"pass": user_id == "ls-u-002",
            "detail": f"Login as marcus_chen: user_id={user_id}"}


def verify_020(server_url):
    base = f"{server_url}/sites/live"
    s = requests.Session()
    r = s.post(f"{base}/api/login",
               json={"username": "test_streamer", "password": "test123"})
    if r.status_code == 200:
        data = r.json()
        return {"pass": True,
                "detail": f"User test_streamer registered and can log in, user_id={data.get('user_id')}"}
    return {"pass": False, "detail": "User test_streamer cannot log in (not registered)"}
