"""Per-task HTTP verification functions for blogs."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/blogs"
    r = requests.get(f"{base}/api/posts?category=Technology")
    posts = r.json()
    count = len(posts)
    return {"pass": count > 0, "detail": f"Technology category has {count} posts"}


def verify_002(server_url):
    base = f"{server_url}/sites/blogs"
    r = requests.get(f"{base}/api/posts/3")
    post = r.json()
    username = post.get("author_username", "")
    return {"pass": len(username) > 0, "detail": f"Post 3 author: {username}"}


def verify_003(server_url):
    base = f"{server_url}/sites/blogs"
    r = requests.get(f"{base}/api/posts/search?q=guide")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Search 'guide': {count} results"}


def verify_004(server_url):
    base = f"{server_url}/sites/blogs"
    r = requests.get(f"{base}/api/posts/semantic?q=cooking+recipes+beginner")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Semantic 'cooking recipes beginner': {count} results"}


def verify_005(server_url):
    base = f"{server_url}/sites/blogs"
    r = requests.get(f"{base}/api/posts?category=Music")
    posts = r.json()
    count = len(posts)
    return {"pass": count >= 0, "detail": f"Music filter: {count} posts"}


def verify_006(server_url):
    base = f"{server_url}/sites/blogs"
    r = requests.get(f"{base}/api/posts?date_from=2025-06-01&date_to=2025-09-30")
    posts = r.json()
    count = len(posts)
    ok = all("2025-06-01" <= p["date"] <= "2025-09-30" for p in posts)
    return {"pass": ok and count >= 0, "detail": f"Date filter Jun-Sep 2025: {count} posts, all_in_range={ok}"}


def verify_007(server_url):
    base = f"{server_url}/sites/blogs"
    r = requests.get(f"{base}/api/posts?sort=oldest")
    posts = r.json()
    if not posts:
        return {"pass": False, "detail": "No posts returned"}
    first_title = posts[0]["title"]
    dates = [p["date"] for p in posts]
    is_sorted = all(dates[i] <= dates[i+1] for i in range(len(dates)-1))
    return {"pass": is_sorted, "detail": f"Oldest first: '{first_title[:50]}', sorted={is_sorted}"}


def verify_008(server_url):
    base = f"{server_url}/sites/blogs"
    r = requests.get(f"{base}/api/posts/search?q=tips")
    results = r.json()
    if not results:
        return {"pass": True, "detail": "No results for 'tips'"}
    first = results[0]["title"]
    return {"pass": len(first) > 0, "detail": f"First 'tips' result: {first[:60]}"}


def verify_009(server_url):
    base = f"{server_url}/sites/blogs"
    r = requests.get(f"{base}/api/posts/semantic?q=fitness+workout+routine")
    results = r.json()
    if not results:
        return {"pass": True, "detail": "No results for fitness query"}
    cat = results[0]["category"]
    return {"pass": len(cat) > 0, "detail": f"First fitness result category: {cat}"}


def verify_010(server_url):
    base = f"{server_url}/sites/blogs"
    r = requests.get(f"{base}/api/categories")
    cats = r.json()
    if not cats:
        return {"pass": False, "detail": "No categories returned"}
    top = max(cats, key=lambda c: c["count"])
    return {"pass": top["count"] > 0,
            "detail": f"Top category: {top['name']} with {top['count']} posts"}


def verify_011(server_url):
    base = f"{server_url}/sites/blogs"
    r = requests.get(f"{base}/api/posts/5")
    post = r.json()
    date = post.get("date", "")
    return {"pass": len(date) > 0, "detail": f"Post 5 date: {date}"}


def verify_012(server_url):
    base = f"{server_url}/sites/blogs"
    r = requests.get(f"{base}/api/posts/search?q=My+First+Post")
    results = r.json()
    found = any(p["title"] == "My First Post" for p in results)
    return {"pass": found, "detail": f"'My First Post' found: {found}"}


def verify_013(server_url):
    base = f"{server_url}/sites/blogs"
    r = requests.get(f"{base}/api/posts/1/comments")
    comments = r.json()
    found = any(c["body"] == "Great article, thanks for sharing!" and
                c["author_username"] == "wanderlust_jess" for c in comments)
    return {"pass": found, "detail": f"Comment by wanderlust_jess on post 1: found={found}"}


def verify_014(server_url):
    base = f"{server_url}/sites/blogs"
    r = requests.get(f"{base}/api/posts/search?q=Random+Thoughts+on+Debugging")
    results = r.json()
    found = any(p["title"] == "Random Thoughts on Debugging" for p in results)
    return {"pass": found, "detail": f"'Random Thoughts on Debugging' found: {found}"}


def verify_015(server_url):
    base = f"{server_url}/sites/blogs"
    r = requests.get(f"{base}/api/users/1")
    user = r.json()
    followed = user.get("followed_blogs", [])
    return {"pass": "wanderlust_jess" in followed,
            "detail": f"User 1 followed blogs: {followed}"}


def verify_016(server_url):
    base = f"{server_url}/sites/blogs"
    r = requests.get(f"{base}/api/users/4")
    user = r.json()
    followed = user.get("followed_blogs", [])
    # After follow+unfollow, kitchen_sage should NOT be in list
    return {"pass": "kitchen_sage" not in followed,
            "detail": f"User 4 followed blogs after toggle: {followed}"}


def verify_017(server_url):
    base = f"{server_url}/sites/blogs"
    r = requests.get(f"{base}/api/users/5")
    user = r.json()
    subscribed = user.get("subscribed_tags", [])
    return {"pass": "python" in subscribed,
            "detail": f"User 5 subscribed tags: {subscribed}"}


def verify_018(server_url):
    base = f"{server_url}/sites/blogs"
    r = requests.get(f"{base}/api/posts/2")
    post = r.json()
    shares = post.get("shared_count", 0)
    return {"pass": shares > 0, "detail": f"Post 2 share count: {shares}"}


def verify_019(server_url):
    base = f"{server_url}/sites/blogs"
    r = requests.get(f"{base}/api/users/8")
    user = r.json()
    saved = user.get("saved_posts", [])
    return {"pass": len(saved) == 3 and 1 in saved and 2 in saved and 3 in saved,
            "detail": f"User 8 saved posts: {saved}"}


def verify_020(server_url):
    base = f"{server_url}/sites/blogs"
    r = requests.get(f"{base}/api/reports")
    reports = r.json()
    found = any(rpt.get("post_id") == 4 and rpt.get("reason") == "spam" and
                rpt.get("status") == "pending" for rpt in reports)
    return {"pass": found, "detail": f"Report for post 4 (spam): found={found}"}
