"""Per-task reference solutions via Flask test client for live."""
import json


def solve_001(client, base="/sites/live"):
    r = client.get(f"{base}/api/streams/semantic?q=coding+backend+api")
    results = json.loads(r.data)
    return str(len(results))


def solve_002(client, base="/sites/live"):
    r = client.get(f"{base}/api/streams?category=Fitness+%26+Health")
    streams = json.loads(r.data)
    return str(len(streams))


def solve_003(client, base="/sites/live"):
    r = client.get(f"{base}/api/streams/stream-001")
    stream = json.loads(r.data)
    return stream["title"]


def solve_004(client, base="/sites/live"):
    r = client.get(f"{base}/api/streams/search?q=workout")
    return str(len(json.loads(r.data)))


def solve_005(client, base="/sites/live"):
    r = client.get(f"{base}/api/streams?category=Gaming")
    return str(len(json.loads(r.data)))


def solve_006(client, base="/sites/live"):
    r = client.get(f"{base}/api/streams?sort=viewers")
    streams = json.loads(r.data)
    return streams[0]["title"] if streams else ""


def solve_007(client, base="/sites/live"):
    # Login
    client.post(f"{base}/api/login",
                json={"username": "alex_rivera", "password": "stream2024"},
                content_type="application/json")
    # Create clip
    r = client.post(f"{base}/api/clips",
                    json={
                        "stream_id": "stream-005",
                        "title": "Best HIIT moment",
                        "duration_seconds": 30,
                        "timestamp_seconds": 900,
                    },
                    content_type="application/json")
    data = json.loads(r.data)
    return "created" if data.get("id") else "failed"


def solve_008(client, base="/sites/live"):
    client.post(f"{base}/api/login",
                json={"username": "alex_rivera", "password": "stream2024"},
                content_type="application/json")
    r = client.post(f"{base}/api/streams/stream-001/playback",
                    json={"quality": "720p"},
                    content_type="application/json")
    data = json.loads(r.data)
    return data.get("playback", {}).get("quality", "")


def solve_009(client, base="/sites/live"):
    client.post(f"{base}/api/login",
                json={"username": "alex_rivera", "password": "stream2024"},
                content_type="application/json")
    r = client.post(f"{base}/api/streams/stream-003/playback",
                    json={"timestamp_seconds": 3600},
                    content_type="application/json")
    data = json.loads(r.data)
    return str(data.get("playback", {}).get("current_timestamp", 0))


def solve_010(client, base="/sites/live"):
    client.post(f"{base}/api/login",
                json={"username": "alex_rivera", "password": "stream2024"},
                content_type="application/json")
    r = client.post(f"{base}/api/streams/stream-001/playback",
                    json={"playback_speed": 1.5},
                    content_type="application/json")
    data = json.loads(r.data)
    return str(data.get("playback", {}).get("playback_speed", 1.0))


def solve_011(client, base="/sites/live"):
    client.post(f"{base}/api/login",
                json={"username": "alex_rivera", "password": "stream2024"},
                content_type="application/json")
    r = client.post(f"{base}/api/streams/stream-003/chat",
                    json={"message": "Great stream tonight!"},
                    content_type="application/json")
    data = json.loads(r.data)
    return "posted" if data.get("id") else "failed"


def solve_012(client, base="/sites/live"):
    client.post(f"{base}/api/login",
                json={"username": "natalie_kim", "password": "leetcode42"},
                content_type="application/json")
    r = client.post(f"{base}/api/channels/ls-u-001/follow",
                    content_type="application/json")
    data = json.loads(r.data)
    return data.get("status", "")


def solve_013(client, base="/sites/live"):
    client.post(f"{base}/api/login",
                json={"username": "alex_rivera", "password": "stream2024"},
                content_type="application/json")
    r = client.post(f"{base}/api/streams/stream-001/share",
                    json={"platform": "twitter"},
                    content_type="application/json")
    data = json.loads(r.data)
    return data.get("status", "")


def solve_014(client, base="/sites/live"):
    client.post(f"{base}/api/login",
                json={"username": "alex_rivera", "password": "stream2024"},
                content_type="application/json")
    r = client.post(f"{base}/api/report",
                    json={
                        "target_type": "stream",
                        "target_id": "stream-003",
                        "reason": "spam",
                        "description": "Misleading title",
                    },
                    content_type="application/json")
    data = json.loads(r.data)
    return data.get("status", "")


def solve_015(client, base="/sites/live"):
    client.post(f"{base}/api/login",
                json={"username": "natalie_kim", "password": "leetcode42"},
                content_type="application/json")
    # Toggle off
    client.post(f"{base}/api/channels/ls-u-005/subscribe",
                content_type="application/json")
    # Toggle back on
    r = client.post(f"{base}/api/channels/ls-u-005/subscribe",
                    content_type="application/json")
    data = json.loads(r.data)
    return data.get("status", "")


def solve_016(client, base="/sites/live"):
    client.post(f"{base}/api/login",
                json={"username": "alex_rivera", "password": "stream2024"},
                content_type="application/json")
    r = client.post(f"{base}/api/streams/stream-005/join",
                    content_type="application/json")
    data = json.loads(r.data)
    return data.get("status", "")


def solve_017(client, base="/sites/live"):
    client.post(f"{base}/api/login",
                json={"username": "alex_rivera", "password": "stream2024"},
                content_type="application/json")
    r = client.post(f"{base}/api/channels/ls-u-002/gift",
                    json={
                        "recipient_username": "natalie_kim",
                        "tier": "tier_2",
                    },
                    content_type="application/json")
    data = json.loads(r.data)
    return data.get("status", "")


def solve_018(client, base="/sites/live"):
    client.post(f"{base}/api/login",
                json={"username": "alex_rivera", "password": "stream2024"},
                content_type="application/json")
    r = client.post(f"{base}/api/channels/ls-u-002/redeem",
                    json={"reward_id": "reward-001"},
                    content_type="application/json")
    data = json.loads(r.data)
    return data.get("status", "")


def solve_019(client, base="/sites/live"):
    r = client.post(f"{base}/api/login",
                    json={"username": "marcus_chen", "password": "code4life"},
                    content_type="application/json")
    data = json.loads(r.data)
    return data.get("username", "")


def solve_020(client, base="/sites/live"):
    r = client.post(f"{base}/api/register",
                    json={
                        "username": "test_streamer",
                        "display_name": "Test Streamer",
                        "password": "test123",
                    },
                    content_type="application/json")
    data = json.loads(r.data)
    return "registered" if data.get("user_id") else "failed"
