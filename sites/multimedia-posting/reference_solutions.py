"""Per-task reference solutions via Flask test client for multimedia-posting."""
import io
import json


def solve_001(client, base="/sites/multimedia-posting"):
    r = client.get(f"{base}/api/posts")
    return str(len(json.loads(r.data)))


def solve_002(client, base="/sites/multimedia-posting"):
    r = client.get(f"{base}/api/users/mp-u-003")
    return json.loads(r.data)["display_name"]


def solve_003(client, base="/sites/multimedia-posting"):
    r = client.get(f"{base}/api/search?q=sunset")
    data = json.loads(r.data)
    return str(len(data.get("posts", [])))


def solve_004(client, base="/sites/multimedia-posting"):
    r = client.get(f"{base}/api/search/semantic?q=hiking+mountain+trail")
    results = json.loads(r.data)
    return results[0]["caption"] if results else "No results"


def solve_005(client, base="/sites/multimedia-posting"):
    r = client.get(f"{base}/api/posts?types=photo&types=video")
    return str(len(json.loads(r.data)))


def solve_006(client, base="/sites/multimedia-posting"):
    r = client.get(f"{base}/api/posts?type=video")
    return str(len(json.loads(r.data)))


def solve_007(client, base="/sites/multimedia-posting"):
    r = client.get(f"{base}/api/posts?sort=most_liked")
    posts = json.loads(r.data)
    return posts[0]["id"] if posts else ""


def solve_008(client, base="/sites/multimedia-posting"):
    r = client.get(f"{base}/api/search/semantic?q=coffee+morning")
    results = json.loads(r.data)
    return results[0]["author"]["username"] if results else "No results"


def solve_009(client, base="/sites/multimedia-posting"):
    r = client.get(f"{base}/api/stats?type=photo")
    return str(json.loads(r.data).get("total_posts", 0))


def solve_010(client, base="/sites/multimedia-posting"):
    r = client.get(f"{base}/api/posts/post-001")
    post = json.loads(r.data)
    return str(len(post.get("comments_list", [])))


def solve_011(client, base="/sites/multimedia-posting"):
    client.post(f"{base}/api/login", json={"username": "alex.rivera"})
    r = client.post(f"{base}/api/posts", json={
        "caption": "Beautiful day at the park #sunshine #nature",
        "location": "Lakeport Park, WA",
        "type": "photo"
    })
    return json.loads(r.data)["id"]


def solve_012(client, base="/sites/multimedia-posting"):
    client.post(f"{base}/api/login", json={"username": "alex.rivera"})
    client.put(f"{base}/api/posts/post-001",
               json={"caption": "Updated sunset shot at Cascadia Lake"})
    r = client.get(f"{base}/api/posts/post-001")
    return json.loads(r.data)["caption"]


def solve_013(client, base="/sites/multimedia-posting"):
    client.post(f"{base}/api/login", json={"username": "alex.rivera"})
    client.delete(f"{base}/api/posts/post-002")
    r = client.get(f"{base}/api/posts?user=mp-u-001")
    return str(len(json.loads(r.data)))


def solve_014(client, base="/sites/multimedia-posting"):
    client.post(f"{base}/api/login", json={"username": "marcus.chen"})
    r = client.post(f"{base}/api/posts/post-001/comments",
                    json={"text": "Amazing colors in this photo!"})
    return json.loads(r.data)["id"]


def solve_015(client, base="/sites/multimedia-posting"):
    client.post(f"{base}/api/login", json={"username": "alex.rivera"})
    r = client.post(f"{base}/api/posts", json={
        "caption": "Weekend brunch at the market. Best coffee ever! #brunch #weekend",
        "type": "photo"
    })
    data = json.loads(r.data)
    return ", ".join(data.get("tags", []))


def solve_016(client, base="/sites/multimedia-posting"):
    r = client.get(f"{base}/api/posts?type=carousel")
    return str(len(json.loads(r.data)))


def solve_017(client, base="/sites/multimedia-posting"):
    client.post(f"{base}/api/login", json={"username": "alex.rivera"})
    client.put(f"{base}/api/settings", json={"dark_mode": True})
    r = client.get(f"{base}/api/settings")
    return str(json.loads(r.data).get("dark_mode", False)).lower()


def solve_018(client, base="/sites/multimedia-posting"):
    r = client.post(f"{base}/api/posts/post-027/play",
                    json={"quality": "1080p"})
    return json.loads(r.data).get("quality", "")


def solve_019(client, base="/sites/multimedia-posting"):
    r = client.post(f"{base}/api/stories/story-001/play")
    return str(json.loads(r.data).get("views_count", 0))


def solve_020(client, base="/sites/multimedia-posting"):
    r = client.get(f"{base}/api/export?format=csv")
    lines = r.data.decode().strip().split("\n")
    return str(len(lines) - 1)


def solve_021(client, base="/sites/multimedia-posting"):
    client.post(f"{base}/api/login", json={"username": "alex.rivera"})
    data = {"file": (io.BytesIO(b"fake image data"), "photo.jpg")}
    r = client.post(f"{base}/api/upload", data=data,
                    content_type="multipart/form-data")
    return json.loads(r.data).get("filename", "")


def solve_022(client, base="/sites/multimedia-posting"):
    client.post(f"{base}/api/login", json={"username": "alex.rivera"})
    r = client.post(f"{base}/api/posts/post-003/like")
    data = json.loads(r.data)
    return str(data.get("likes_count", 0))


def solve_023(client, base="/sites/multimedia-posting"):
    client.post(f"{base}/api/login", json={"username": "alex.rivera"})
    r = client.post(f"{base}/api/users/follow-by-dropdown",
                    json={"user_id": "mp-u-005"})
    data = json.loads(r.data)
    return str(data.get("follower_count", 0))


def solve_024(client, base="/sites/multimedia-posting"):
    client.post(f"{base}/api/login", json={"username": "alex.rivera"})
    r = client.post(f"{base}/api/users/mp-u-006/follow")
    return json.loads(r.data).get("status", "")


def solve_025(client, base="/sites/multimedia-posting"):
    client.post(f"{base}/api/login", json={"username": "alex.rivera"})
    r = client.post(f"{base}/api/users/mp-u-002/subscribe")
    return json.loads(r.data).get("status", "")


def solve_026(client, base="/sites/multimedia-posting"):
    client.post(f"{base}/api/login", json={"username": "alex.rivera"})
    r = client.post(f"{base}/api/posts/post-001/share",
                    json={"method": "email"})
    return json.loads(r.data).get("method", "")


def solve_027(client, base="/sites/multimedia-posting"):
    client.post(f"{base}/api/login", json={"username": "alex.rivera"})
    client.post(f"{base}/api/posts/post-003/save")
    r = client.get(f"{base}/api/saved")
    saved = json.loads(r.data)
    in_list = any(p.get("id") == "post-003" for p in saved)
    return str(in_list).lower()


def solve_028(client, base="/sites/multimedia-posting"):
    client.post(f"{base}/api/login", json={"username": "alex.rivera"})
    r = client.post(f"{base}/api/posts/post-010/report",
                    json={"reason": "spam", "details": "Looks like bot-generated content"})
    data = json.loads(r.data)
    return data.get("status", "")


def solve_029(client, base="/sites/multimedia-posting"):
    client.post(f"{base}/api/login", json={"username": "alex.rivera"})
    client.post(f"{base}/api/users/mp-u-009/block")
    r = client.get(f"{base}/api/blocked")
    blocked = json.loads(r.data)
    return str("mp-u-009" in blocked).lower()


def solve_030(client, base="/sites/multimedia-posting"):
    client.post(f"{base}/api/login", json={"username": "alex.rivera"})
    # Create post
    r = client.post(f"{base}/api/posts", json={
        "caption": "Surfing at Westport today! Epic waves #surfing #PNW",
        "location": "Westport, WA",
        "type": "video"
    })
    post = json.loads(r.data)
    pid = post["id"]
    # Like it
    r2 = client.post(f"{base}/api/posts/{pid}/like")
    likes = json.loads(r2.data).get("likes_count", 0)
    # Comment
    client.post(f"{base}/api/posts/{pid}/comments",
                json={"text": "Stoked!"})
    return f"{pid}, {likes}"
