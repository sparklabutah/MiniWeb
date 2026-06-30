"""Per-task reference solutions via Flask test client for forums."""
import json


def solve_001(client, base="/sites/forums"):
    r = client.get(f"{base}/api/posts?subreddit=r/hiking")
    posts = json.loads(r.data)
    return str(len(posts))


def solve_002(client, base="/sites/forums"):
    r = client.get(f"{base}/api/posts/rd_post_001")
    post = json.loads(r.data)
    return str(post["score"])


def solve_003(client, base="/sites/forums"):
    r = client.get(f"{base}/api/search?q=trail")
    data = json.loads(r.data)
    return str(data.get("count", 0))


def solve_004(client, base="/sites/forums"):
    r = client.get(f"{base}/api/search/semantic?q=outdoor+photography+nature")
    data = json.loads(r.data)
    return str(data.get("count", 0))


def solve_005(client, base="/sites/forums"):
    r = client.get(f"{base}/api/posts?subreddit=r/programming")
    posts = json.loads(r.data)
    return str(len(posts))


def solve_006(client, base="/sites/forums"):
    r = client.get(f"{base}/api/posts?date_from=2026-01-01&date_to=2026-06-30")
    posts = json.loads(r.data)
    return str(len(posts))


def solve_007(client, base="/sites/forums"):
    r = client.get(f"{base}/api/posts?sort=top")
    posts = json.loads(r.data)
    return posts[0]["title"] if posts else ""


def solve_008(client, base="/sites/forums"):
    r = client.get(f"{base}/api/search/semantic?q=startup+lessons")
    data = json.loads(r.data)
    posts = data.get("posts", [])
    return posts[0]["title"] if posts else "No results"


def solve_009(client, base="/sites/forums"):
    r = client.get(f"{base}/api/subreddits/hiking/stats")
    stats = json.loads(r.data)
    return str(stats.get("unique_authors", 0))


def solve_010(client, base="/sites/forums"):
    r = client.get(f"{base}/api/posts/rd_post_003")
    post = json.loads(r.data)
    return post["subreddit"]


def solve_011(client, base="/sites/forums"):
    r = client.get(f"{base}/api/users/sophie_designs")
    data = json.loads(r.data)
    total = data.get("post_karma", 0) + data.get("comment_karma", 0)
    return str(total)


def solve_012(client, base="/sites/forums"):
    # Login first
    client.post(f"{base}/api/login",
                json={"username": "cascadia_coder", "password": "password"})
    r = client.post(f"{base}/api/posts",
                    json={"title": "Best trails near Lakeport",
                          "body": "Looking for recommendations for day hikes under 10 miles",
                          "subreddit": "r/hiking"})
    data = json.loads(r.data)
    return "created" if data.get("id") else "failed"


def solve_013(client, base="/sites/forums"):
    client.post(f"{base}/api/login",
                json={"username": "cascadia_coder", "password": "password"})
    r = client.post(f"{base}/api/posts",
                    json={"title": "Python async tips",
                          "body": "Share your best asyncio patterns",
                          "subreddit": "r/programming"})
    data = json.loads(r.data)
    return "created" if data.get("id") else "failed"


def solve_014(client, base="/sites/forums"):
    client.post(f"{base}/api/login",
                json={"username": "cascadia_coder", "password": "password"})
    # Get current body
    r = client.get(f"{base}/api/posts/rd_post_003")
    post = json.loads(r.data)
    new_body = post["body"] + " [UPDATED]"
    r = client.put(f"{base}/api/posts/rd_post_003",
                   json={"body": new_body})
    data = json.loads(r.data)
    return "edited" if data.get("body", "").endswith("[UPDATED]") else "failed"


def solve_015(client, base="/sites/forums"):
    client.post(f"{base}/api/login",
                json={"username": "cascadia_coder", "password": "password"})
    r = client.post(f"{base}/api/posts/rd_post_009/vote",
                    json={"direction": "up"})
    data = json.loads(r.data)
    return str(data.get("score", 0))


def solve_016(client, base="/sites/forums"):
    client.post(f"{base}/api/login",
                json={"username": "marcus_climbs", "password": "password"})
    r = client.post(f"{base}/api/posts/rd_post_001/save")
    data = json.loads(r.data)
    return data.get("action", "failed")


def solve_017(client, base="/sites/forums"):
    client.post(f"{base}/api/login",
                json={"username": "cascadia_coder", "password": "password"})
    r = client.post(f"{base}/api/users/mia_rescues/follow")
    data = json.loads(r.data)
    return data.get("action", "failed")


def solve_018(client, base="/sites/forums"):
    client.post(f"{base}/api/login",
                json={"username": "cascadia_coder", "password": "password"})
    r = client.post(f"{base}/api/subreddits/climbing/join")
    data = json.loads(r.data)
    return data.get("action", "failed")


def solve_019(client, base="/sites/forums"):
    client.post(f"{base}/api/login",
                json={"username": "cascadia_coder", "password": "password"})
    r = client.post(f"{base}/api/messages",
                    json={"to": "sophie_designs",
                          "subject": "Hello",
                          "body": "Great design work on the coffee shop logo!"})
    data = json.loads(r.data)
    return "sent" if data.get("id") else "failed"


def solve_020(client, base="/sites/forums"):
    client.post(f"{base}/api/login",
                json={"username": "cascadia_coder", "password": "password"})
    # Share post
    r1 = client.post(f"{base}/api/posts/rd_post_007/share",
                     json={"method": "copy_link"})
    # Report post
    r2 = client.post(f"{base}/api/report",
                     json={"target_type": "post",
                           "target_id": "rd_post_011",
                           "reason": "spam",
                           "description": "Unrelated gaming content"})
    data1 = json.loads(r1.data)
    data2 = json.loads(r2.data)
    if data1.get("share_url") and data2.get("id"):
        return "shared_and_reported"
    return "failed"
