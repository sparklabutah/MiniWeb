"""Per-task reference solutions via Flask test client for video."""
import json


def solve_001(client, base="/sites/video"):
    r = client.get(f"{base}/api/videos?category=Gaming")
    videos = json.loads(r.data)
    return str(len(videos))


def solve_002(client, base="/sites/video"):
    r = client.get(f"{base}/api/videos/7")
    video = json.loads(r.data)
    channel_id = video["channel_id"]
    r2 = client.get(f"{base}/api/channels/{channel_id}")
    channel = json.loads(r2.data)
    return channel["channel_name"]


def solve_003(client, base="/sites/video"):
    r = client.get(f"{base}/api/search?q=Rust")
    return str(len(json.loads(r.data)))


def solve_004(client, base="/sites/video"):
    r = client.get(f"{base}/api/search/semantic?q=outdoor+hiking+adventure")
    return str(len(json.loads(r.data)))


def solve_005(client, base="/sites/video"):
    r = client.get(f"{base}/api/videos?category=Education")
    return str(len(json.loads(r.data)))


def solve_006(client, base="/sites/video"):
    r = client.get(f"{base}/api/videos?duration_min=1000&duration_max=1500")
    return str(len(json.loads(r.data)))


def solve_007(client, base="/sites/video"):
    r = client.get(f"{base}/api/videos?date_from=2025-06-01&date_to=2025-12-31")
    return str(len(json.loads(r.data)))


def solve_008(client, base="/sites/video"):
    r = client.get(f"{base}/api/videos?sort=views")
    videos = json.loads(r.data)
    return videos[0]["title"] if videos else ""


def solve_009(client, base="/sites/video"):
    r = client.get(f"{base}/api/search?q=design")
    results = json.loads(r.data)
    return results[0]["title"] if results else "No results"


def solve_010(client, base="/sites/video"):
    r = client.put(f"{base}/api/videos/3",
                   json={"title": "Easy Homemade Pasta | Quick Weeknight Recipe"})
    video = json.loads(r.data)
    return video["title"]


def solve_011(client, base="/sites/video"):
    r = client.post(f"{base}/api/videos",
                    json={"title": "Test Upload Video",
                          "channel_id": 2,
                          "category": "Education"})
    video = json.loads(r.data)
    return str(video["id"])


def solve_012(client, base="/sites/video"):
    r = client.post(f"{base}/api/playlists/2/add",
                    json={"video_id": 5})
    playlist = json.loads(r.data)
    items = playlist.get("items", [])
    has_5 = any(item.get("video_id") == 5 for item in items)
    return "added" if has_5 else "failed"


def solve_013(client, base="/sites/video"):
    # Login as alex_trails
    client.post(f"{base}/api/login",
                json={"username": "alex_trails", "password": "alex_trails"})
    # Enable dark mode
    r = client.put(f"{base}/api/users/1/settings",
                   json={"dark_mode": True})
    prefs = json.loads(r.data).get("preferences", {})
    return "enabled" if prefs.get("dark_mode") else "failed"


def solve_014(client, base="/sites/video"):
    r = client.post(f"{base}/api/videos/14/seek",
                    json={"position": 900},
                    content_type="application/json")
    data = json.loads(r.data)
    return str(data.get("progress_percent", 0))


def solve_015(client, base="/sites/video"):
    r = client.get(f"{base}/api/history?date_from=2025-09-01&date_to=2025-12-31")
    return str(len(json.loads(r.data)))


def solve_016(client, base="/sites/video"):
    r = client.post(f"{base}/api/videos/6/playback",
                    json={"speed": 1.5, "quality": "720p"})
    data = json.loads(r.data)
    return f"speed={data.get('speed')}, quality={data.get('quality')}"


def solve_017(client, base="/sites/video"):
    r = client.post(f"{base}/api/videos/1/comments",
                    json={
                        "text": "Amazing trail footage! Adding this to my hiking bucket list.",
                        "user_id": 2
                    })
    comment = json.loads(r.data)
    return str(comment.get("id", ""))


def solve_018(client, base="/sites/video"):
    # Login as marcuscodes
    client.post(f"{base}/api/login",
                json={"username": "marcuscodes", "password": "marcuscodes"})
    # Like video 28
    client.post(f"{base}/api/videos/28/like",
                json={"action": "like"})
    # Save video 28
    r = client.post(f"{base}/api/videos/28/save",
                    json={"user_id": 2})
    data = json.loads(r.data)
    return data.get("action", "")


def solve_019(client, base="/sites/video"):
    # Rate video 7 as user 1
    client.post(f"{base}/api/videos/7/rate",
                json={"rating": 5, "user_id": 1})
    # Share via twitter
    r = client.post(f"{base}/api/videos/7/share",
                    json={"platform": "twitter"})
    data = json.loads(r.data)
    return str(data.get("total_shares", 0))


def solve_020(client, base="/sites/video"):
    # Login as nate_fitness
    client.post(f"{base}/api/login",
                json={"username": "nate_fitness", "password": "nate_fitness"})
    # Subscribe to channel 9
    client.post(f"{base}/api/channels/9/subscribe",
                json={"user_id": 4})
    # Follow channel 1
    client.post(f"{base}/api/channels/1/follow",
                json={"user_id": 4})
    # Report video 8
    client.post(f"{base}/api/videos/8/report",
                json={
                    "reason": "inappropriate",
                    "details": "Contains misleading gameplay edits",
                    "user_id": 4
                })
    return "completed"
