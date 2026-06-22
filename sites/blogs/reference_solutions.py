"""Per-task reference solutions via Flask test client for blogs."""
import json


def solve_001(client, base="/sites/blogs"):
    r = client.get(f"{base}/api/posts?category=Technology")
    posts = json.loads(r.data)
    return str(len(posts))


def solve_002(client, base="/sites/blogs"):
    r = client.get(f"{base}/api/posts/3")
    post = json.loads(r.data)
    return post["author_username"]


def solve_003(client, base="/sites/blogs"):
    r = client.get(f"{base}/api/posts/search?q=guide")
    return str(len(json.loads(r.data)))


def solve_004(client, base="/sites/blogs"):
    r = client.get(f"{base}/api/posts/semantic?q=cooking+recipes+beginner")
    return str(len(json.loads(r.data)))


def solve_005(client, base="/sites/blogs"):
    r = client.get(f"{base}/api/posts?category=Music")
    return str(len(json.loads(r.data)))


def solve_006(client, base="/sites/blogs"):
    r = client.get(f"{base}/api/posts?date_from=2025-06-01&date_to=2025-09-30")
    return str(len(json.loads(r.data)))


def solve_007(client, base="/sites/blogs"):
    r = client.get(f"{base}/api/posts?sort=oldest")
    posts = json.loads(r.data)
    return posts[0]["title"] if posts else ""


def solve_008(client, base="/sites/blogs"):
    r = client.get(f"{base}/api/posts/search?q=tips")
    results = json.loads(r.data)
    return results[0]["title"] if results else "No results"


def solve_009(client, base="/sites/blogs"):
    r = client.get(f"{base}/api/posts/semantic?q=fitness+workout+routine")
    results = json.loads(r.data)
    return results[0]["category"] if results else "No results"


def solve_010(client, base="/sites/blogs"):
    r = client.get(f"{base}/api/categories")
    cats = json.loads(r.data)
    top = max(cats, key=lambda c: c["count"])
    return f"{top['name']} ({top['count']})"


def solve_011(client, base="/sites/blogs"):
    r = client.get(f"{base}/api/posts/5")
    return json.loads(r.data)["date"]


def solve_012(client, base="/sites/blogs"):
    r = client.post(f"{base}/api/posts/create",
                    json={
                        "title": "My First Post",
                        "body": "Hello world, this is my first blog post on TumblrVibe!",
                        "category": "Lifestyle",
                        "tags": ["intro", "hello"],
                        "author_username": "midnight_coder",
                    },
                    content_type="application/json")
    data = json.loads(r.data)
    return str(data.get("id", ""))


def solve_013(client, base="/sites/blogs"):
    r = client.post(f"{base}/api/posts/1/comment",
                    json={
                        "body": "Great article, thanks for sharing!",
                        "author_username": "wanderlust_jess",
                    },
                    content_type="application/json")
    data = json.loads(r.data)
    return str(data.get("id", ""))


def solve_014(client, base="/sites/blogs"):
    r = client.post(f"{base}/api/posts/create",
                    json={
                        "title": "Random Thoughts on Debugging",
                        "body": "Debugging is like being the detective in a crime movie where you are also the murderer. Here are my top strategies for finding bugs faster.",
                        "category": "Technology",
                        "tags": ["debugging", "coding"],
                        "author_username": "pixel_dreamer",
                    },
                    content_type="application/json")
    data = json.loads(r.data)
    return str(data.get("id", ""))


def solve_015(client, base="/sites/blogs"):
    client.post(f"{base}/api/login",
                json={"username": "midnight_coder", "password": "pass123"},
                content_type="application/json")
    r = client.post(f"{base}/api/users/1/follow",
                    json={"blog": "wanderlust_jess"},
                    content_type="application/json")
    return json.loads(r.data).get("action", "")


def solve_016(client, base="/sites/blogs"):
    client.post(f"{base}/api/login",
                json={"username": "pixel_dreamer", "password": "pass423"},
                content_type="application/json")
    # Follow
    client.post(f"{base}/api/users/4/follow",
                json={"blog": "kitchen_sage"},
                content_type="application/json")
    # Unfollow
    r = client.post(f"{base}/api/users/4/follow",
                    json={"blog": "kitchen_sage"},
                    content_type="application/json")
    return json.loads(r.data).get("action", "")


def solve_017(client, base="/sites/blogs"):
    client.post(f"{base}/api/login",
                json={"username": "bookworm_alex", "password": "pass523"},
                content_type="application/json")
    r = client.post(f"{base}/api/users/5/subscribe",
                    json={"tag": "python"},
                    content_type="application/json")
    return json.loads(r.data).get("action", "")


def solve_018(client, base="/sites/blogs"):
    r = client.post(f"{base}/api/posts/2/share",
                    json={"platform": "twitter"},
                    content_type="application/json")
    data = json.loads(r.data)
    return str(data.get("total_shares", ""))


def solve_019(client, base="/sites/blogs"):
    client.post(f"{base}/api/login",
                json={"username": "green_thumb", "password": "pass823"},
                content_type="application/json")
    for pid in [1, 2, 3]:
        client.post(f"{base}/api/users/8/save",
                    json={"post_id": pid},
                    content_type="application/json")
    r = client.get(f"{base}/api/users/8")
    user = json.loads(r.data)
    return str(len(user.get("saved_posts", [])))


def solve_020(client, base="/sites/blogs"):
    r = client.post(f"{base}/api/posts/4/report",
                    json={
                        "reason": "spam",
                        "details": "This post appears to be automated spam content",
                        "reporter_username": "fitness_nova",
                    },
                    content_type="application/json")
    data = json.loads(r.data)
    return data.get("status", "")
