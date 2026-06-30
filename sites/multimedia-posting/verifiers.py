"""Per-task HTTP verification functions for multimedia-posting."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/multimedia-posting"
    r = requests.get(f"{base}/api/posts")
    posts = r.json()
    count = len(posts)
    return {"pass": count > 0, "detail": f"Explore shows {count} total posts"}


def verify_002(server_url):
    base = f"{server_url}/sites/multimedia-posting"
    r = requests.get(f"{base}/api/users/mp-u-003")
    user = r.json()
    name = user.get("display_name", "")
    return {"pass": name == "Samantha Liu", "detail": f"mp-u-003 display_name: {name}"}


def verify_003(server_url):
    base = f"{server_url}/sites/multimedia-posting"
    r = requests.get(f"{base}/api/search?q=sunset")
    data = r.json()
    count = len(data.get("posts", []))
    return {"pass": count >= 0, "detail": f"Search 'sunset': {count} posts"}


def verify_004(server_url):
    base = f"{server_url}/sites/multimedia-posting"
    r = requests.get(f"{base}/api/search/semantic?q=hiking+mountain+trail")
    results = r.json()
    ok = len(results) > 0
    caption = results[0].get("caption", "")[:60] if results else ""
    return {"pass": ok, "detail": f"Semantic search: {len(results)} results, top: {caption}"}


def verify_005(server_url):
    base = f"{server_url}/sites/multimedia-posting"
    r = requests.get(f"{base}/api/posts?types=photo&types=video")
    posts = r.json()
    types = set(p.get("type") for p in posts)
    ok = types <= {"photo", "video"}
    return {"pass": ok and len(posts) > 0,
            "detail": f"Checkbox photo+video: {len(posts)} posts, types={types}"}


def verify_006(server_url):
    base = f"{server_url}/sites/multimedia-posting"
    r = requests.get(f"{base}/api/posts?type=video")
    posts = r.json()
    ok = all(p.get("type") == "video" for p in posts)
    return {"pass": ok, "detail": f"Video filter: {len(posts)} posts"}


def verify_007(server_url):
    base = f"{server_url}/sites/multimedia-posting"
    r = requests.get(f"{base}/api/posts?sort=most_liked")
    posts = r.json()
    if len(posts) < 2:
        return {"pass": False, "detail": "Too few posts"}
    is_sorted = all(posts[i].get("likes_count", 0) >= posts[i+1].get("likes_count", 0)
                     for i in range(len(posts)-1))
    top_id = posts[0]["id"]
    return {"pass": is_sorted, "detail": f"Most liked: {top_id}, sorted={is_sorted}"}


def verify_008(server_url):
    base = f"{server_url}/sites/multimedia-posting"
    r = requests.get(f"{base}/api/search/semantic?q=coffee+morning")
    results = r.json()
    ok = len(results) > 0
    username = results[0].get("author", {}).get("username", "") if results else ""
    return {"pass": ok, "detail": f"Coffee morning search: {len(results)} results, top author: {username}"}


def verify_009(server_url):
    base = f"{server_url}/sites/multimedia-posting"
    r = requests.get(f"{base}/api/stats?type=photo")
    stats = r.json()
    count = stats.get("total_posts", 0)
    return {"pass": count > 0, "detail": f"Photo stats: {count} posts"}


def verify_010(server_url):
    base = f"{server_url}/sites/multimedia-posting"
    r = requests.get(f"{base}/api/posts/post-001")
    post = r.json()
    comments = post.get("comments_list", [])
    return {"pass": len(comments) >= 0, "detail": f"post-001 has {len(comments)} comments"}


def verify_011(server_url):
    base = f"{server_url}/sites/multimedia-posting"
    # Check that a new post was created with matching caption
    r = requests.get(f"{base}/api/posts?user=mp-u-001")
    posts = r.json()
    new_posts = [p for p in posts if "Beautiful day at the park" in p.get("caption", "")]
    ok = len(new_posts) > 0
    post_id = new_posts[0]["id"] if new_posts else ""
    return {"pass": ok, "detail": f"New post created: id={post_id}"}


def verify_012(server_url):
    base = f"{server_url}/sites/multimedia-posting"
    r = requests.get(f"{base}/api/posts/post-001")
    post = r.json()
    caption = post.get("caption", "")
    ok = caption == "Updated sunset shot at Cascadia Lake"
    return {"pass": ok, "detail": f"post-001 caption: {caption}"}


def verify_013(server_url):
    base = f"{server_url}/sites/multimedia-posting"
    # post-002 should be deleted
    r = requests.get(f"{base}/api/posts/post-002")
    deleted = r.status_code == 404 or "error" in r.json()
    # Count remaining posts by mp-u-001
    r2 = requests.get(f"{base}/api/posts?user=mp-u-001")
    remaining = len(r2.json())
    return {"pass": deleted, "detail": f"post-002 deleted={deleted}, mp-u-001 remaining={remaining}"}


def verify_014(server_url):
    base = f"{server_url}/sites/multimedia-posting"
    r = requests.get(f"{base}/api/posts/post-001/comments")
    comments = r.json()
    new_comments = [c for c in comments if "Amazing colors" in c.get("text", "")]
    ok = len(new_comments) > 0
    cid = new_comments[0]["id"] if new_comments else ""
    return {"pass": ok, "detail": f"New comment found: id={cid}"}


def verify_015(server_url):
    base = f"{server_url}/sites/multimedia-posting"
    r = requests.get(f"{base}/api/posts?user=mp-u-001")
    posts = r.json()
    new_posts = [p for p in posts if "Weekend brunch" in p.get("caption", "")]
    ok = len(new_posts) > 0
    tags = new_posts[0].get("tags", []) if new_posts else []
    return {"pass": ok and "brunch" in tags and "weekend" in tags,
            "detail": f"Free-text post tags: {tags}"}


def verify_016(server_url):
    base = f"{server_url}/sites/multimedia-posting"
    r = requests.get(f"{base}/api/posts?type=carousel")
    posts = r.json()
    ok = all(p.get("type") == "carousel" for p in posts)
    return {"pass": ok and len(posts) > 0, "detail": f"Carousel select: {len(posts)} posts"}


def verify_017(server_url):
    base = f"{server_url}/sites/multimedia-posting"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "alex.rivera"})
    s.put(f"{base}/api/settings", json={"dark_mode": True})
    r = s.get(f"{base}/api/settings")
    settings = r.json()
    ok = settings.get("dark_mode") is True
    return {"pass": ok, "detail": f"dark_mode={settings.get('dark_mode')}"}


def verify_018(server_url):
    base = f"{server_url}/sites/multimedia-posting"
    r = requests.post(f"{base}/api/posts/post-027/play",
                      json={"quality": "1080p"})
    data = r.json()
    ok = data.get("quality") == "1080p"
    return {"pass": ok, "detail": f"Play quality: {data.get('quality')}"}


def verify_019(server_url):
    base = f"{server_url}/sites/multimedia-posting"
    r = requests.post(f"{base}/api/stories/story-001/play")
    data = r.json()
    views = data.get("views_count", 0)
    ok = views > 0
    return {"pass": ok, "detail": f"story-001 views: {views}"}


def verify_020(server_url):
    base = f"{server_url}/sites/multimedia-posting"
    r = requests.get(f"{base}/api/export?format=csv")
    lines = r.text.strip().split("\n")
    data_rows = len(lines) - 1
    return {"pass": data_rows > 0, "detail": f"CSV export: {data_rows} data rows"}


def verify_021(server_url):
    base = f"{server_url}/sites/multimedia-posting"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "alex.rivera"})
    import io
    files = {"file": ("photo.jpg", io.BytesIO(b"fake image data"), "image/jpeg")}
    r = s.post(f"{base}/api/upload", files=files)
    data = r.json()
    ok = data.get("filename") == "photo.jpg"
    return {"pass": ok, "detail": f"Upload filename: {data.get('filename')}"}


def verify_022(server_url):
    base = f"{server_url}/sites/multimedia-posting"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "alex.rivera"})
    r = s.post(f"{base}/api/posts/post-003/like")
    data = r.json()
    ok = data.get("status") == "liked"
    return {"pass": ok, "detail": f"Like status: {data.get('status')}, count: {data.get('likes_count')}"}


def verify_023(server_url):
    base = f"{server_url}/sites/multimedia-posting"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "alex.rivera"})
    r = s.post(f"{base}/api/users/follow-by-dropdown", json={"user_id": "mp-u-005"})
    data = r.json()
    ok = data.get("status") == "followed"
    return {"pass": ok,
            "detail": f"Follow-by-dropdown: status={data.get('status')}, followers={data.get('follower_count')}"}


def verify_024(server_url):
    base = f"{server_url}/sites/multimedia-posting"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "alex.rivera"})
    r = s.post(f"{base}/api/users/mp-u-006/follow")
    data = r.json()
    ok = data.get("status") in ("followed", "unfollowed")
    return {"pass": ok, "detail": f"Follow toggle: {data.get('status')}"}


def verify_025(server_url):
    base = f"{server_url}/sites/multimedia-posting"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "alex.rivera"})
    r = s.post(f"{base}/api/users/mp-u-002/subscribe")
    data = r.json()
    ok = data.get("status") == "subscribed"
    return {"pass": ok, "detail": f"Subscribe: {data.get('status')}"}


def verify_026(server_url):
    base = f"{server_url}/sites/multimedia-posting"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "alex.rivera"})
    r = s.post(f"{base}/api/posts/post-001/share",
               json={"method": "email", "recipient": ""})
    data = r.json()
    ok = data.get("method") == "email"
    return {"pass": ok, "detail": f"Share method: {data.get('method')}"}


def verify_027(server_url):
    base = f"{server_url}/sites/multimedia-posting"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "alex.rivera"})
    r = s.post(f"{base}/api/posts/post-003/save")
    data = r.json()
    ok = data.get("status") == "saved"
    r2 = s.get(f"{base}/api/saved")
    saved = r2.json()
    in_saved = any(p.get("id") == "post-003" for p in saved)
    return {"pass": ok and in_saved,
            "detail": f"Save: {data.get('status')}, in_list={in_saved}"}


def verify_028(server_url):
    base = f"{server_url}/sites/multimedia-posting"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "alex.rivera"})
    r = s.post(f"{base}/api/posts/post-010/report",
               json={"reason": "spam", "details": "Looks like bot-generated content"})
    data = r.json()
    ok = data.get("reason") == "spam" and data.get("status") == "pending"
    return {"pass": ok, "detail": f"Report: reason={data.get('reason')}, status={data.get('status')}"}


def verify_029(server_url):
    base = f"{server_url}/sites/multimedia-posting"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "alex.rivera"})
    r = s.post(f"{base}/api/users/mp-u-009/block")
    data = r.json()
    ok = data.get("status") == "blocked"
    r2 = s.get(f"{base}/api/blocked")
    blocked = r2.json()
    in_list = "mp-u-009" in blocked
    return {"pass": ok and in_list,
            "detail": f"Block: {data.get('status')}, in_list={in_list}"}


def verify_030(server_url):
    base = f"{server_url}/sites/multimedia-posting"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "alex.rivera"})
    r = s.get(f"{base}/api/posts?user=mp-u-001&sort=newest")
    posts = r.json()
    surf_posts = [p for p in posts if "Surfing at Westport" in p.get("caption", "")]
    if not surf_posts:
        return {"pass": False, "detail": "Surfing post not found"}
    post = surf_posts[0]
    pid = post["id"]
    likes = post.get("likes_count", 0)
    # Check comment
    r2 = s.get(f"{base}/api/posts/{pid}/comments")
    comments = r2.json()
    has_stoked = any("Stoked" in c.get("text", "") for c in comments)
    return {"pass": likes >= 1 and has_stoked,
            "detail": f"Post {pid}: likes={likes}, has_stoked_comment={has_stoked}"}
