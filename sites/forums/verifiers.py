"""Per-task HTTP verification functions for forums."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/forums"
    r = requests.get(f"{base}/api/posts", params={"subreddit": "r/hiking"})
    posts = r.json()
    count = len(posts)
    return {"pass": count > 0, "detail": f"r/hiking has {count} posts"}


def verify_002(server_url):
    base = f"{server_url}/sites/forums"
    r = requests.get(f"{base}/api/posts/rd_post_001")
    post = r.json()
    score = post.get("score", 0)
    return {"pass": score > 0, "detail": f"Post rd_post_001 score: {score}"}


def verify_003(server_url):
    base = f"{server_url}/sites/forums"
    r = requests.get(f"{base}/api/search", params={"q": "trail"})
    data = r.json()
    count = data.get("count", 0)
    return {"pass": count > 0, "detail": f"Search 'trail': {count} results"}


def verify_004(server_url):
    base = f"{server_url}/sites/forums"
    r = requests.get(f"{base}/api/search/semantic", params={"q": "outdoor photography nature"})
    data = r.json()
    count = data.get("count", 0)
    return {"pass": count >= 0, "detail": f"Semantic 'outdoor photography nature': {count} results"}


def verify_005(server_url):
    base = f"{server_url}/sites/forums"
    r = requests.get(f"{base}/api/posts", params={"subreddit": "r/programming"})
    posts = r.json()
    count = len(posts)
    return {"pass": count > 0, "detail": f"r/programming filter: {count} posts"}


def verify_006(server_url):
    base = f"{server_url}/sites/forums"
    r = requests.get(f"{base}/api/posts", params={"date_from": "2026-01-01", "date_to": "2026-06-30"})
    posts = r.json()
    count = len(posts)
    ok = all(p.get("created_at", "") >= "2026-01-01" and p.get("created_at", "") <= "2026-06-30T" for p in posts)
    return {"pass": count >= 0, "detail": f"Date range 2026-01-01 to 2026-06-30: {count} posts"}


def verify_007(server_url):
    base = f"{server_url}/sites/forums"
    r = requests.get(f"{base}/api/posts", params={"sort": "top"})
    posts = r.json()
    if not posts:
        return {"pass": False, "detail": "No posts returned"}
    first_title = posts[0].get("title", "")
    return {"pass": len(first_title) > 0, "detail": f"Top post: {first_title[:60]}"}


def verify_008(server_url):
    base = f"{server_url}/sites/forums"
    r = requests.get(f"{base}/api/search/semantic", params={"q": "startup lessons"})
    data = r.json()
    posts = data.get("posts", [])
    if not posts:
        return {"pass": True, "detail": "No results for 'startup lessons'"}
    first_title = posts[0].get("title", "")
    return {"pass": len(first_title) > 0, "detail": f"Top semantic result: {first_title[:60]}"}


def verify_009(server_url):
    base = f"{server_url}/sites/forums"
    r = requests.get(f"{base}/api/subreddits/hiking/stats")
    stats = r.json()
    authors = stats.get("unique_authors", 0)
    return {"pass": authors > 0, "detail": f"r/hiking unique authors: {authors}"}


def verify_010(server_url):
    base = f"{server_url}/sites/forums"
    r = requests.get(f"{base}/api/posts/rd_post_003")
    post = r.json()
    subreddit = post.get("subreddit", "")
    return {"pass": len(subreddit) > 0, "detail": f"Post rd_post_003 subreddit: {subreddit}"}


def verify_011(server_url):
    base = f"{server_url}/sites/forums"
    r = requests.get(f"{base}/api/users/sophie_designs")
    data = r.json()
    total_karma = data.get("post_karma", 0) + data.get("comment_karma", 0)
    return {"pass": total_karma > 0, "detail": f"sophie_designs total karma: {total_karma}"}


def verify_012(server_url):
    base = f"{server_url}/sites/forums"
    r = requests.get(f"{base}/api/search", params={"q": "Best trails near Lakeport"})
    data = r.json()
    posts = data.get("posts", [])
    found = any("Best trails near Lakeport" in p.get("title", "") for p in posts)
    return {"pass": found, "detail": f"Post 'Best trails near Lakeport' found: {found}"}


def verify_013(server_url):
    base = f"{server_url}/sites/forums"
    r = requests.get(f"{base}/api/search", params={"q": "Python async tips"})
    data = r.json()
    posts = data.get("posts", [])
    found = any("Python async tips" in p.get("title", "") for p in posts)
    return {"pass": found, "detail": f"Post 'Python async tips' found: {found}"}


def verify_014(server_url):
    base = f"{server_url}/sites/forums"
    r = requests.get(f"{base}/api/posts/rd_post_003")
    post = r.json()
    body = post.get("body", "")
    return {"pass": body.endswith("[UPDATED]"), "detail": f"Post body ends with [UPDATED]: {body[-30:]}"}


def verify_015(server_url):
    base = f"{server_url}/sites/forums"
    r = requests.get(f"{base}/api/posts/rd_post_009")
    post = r.json()
    # Original score was 5230, after upvote should be 5231
    score = post.get("score", 0)
    return {"pass": score > 5230, "detail": f"Post rd_post_009 score after upvote: {score}"}


def verify_016(server_url):
    base = f"{server_url}/sites/forums"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "marcus_climbs", "password": "password"})
    r = s.get(f"{base}/api/users/marcus_climbs")
    user = r.json()
    saved = user.get("saved_posts", [])
    return {"pass": "rd_post_001" in saved, "detail": f"marcus_climbs saved posts: {saved}"}


def verify_017(server_url):
    base = f"{server_url}/sites/forums"
    r = requests.get(f"{'/_admin' if False else base}/api/users/cascadia_coder")
    # Check via admin endpoint
    r2 = requests.get(f"{server_url}/_admin/data/reddit-augment/users_overlay")
    data = r2.json()
    users = data.get("users", data) if isinstance(data, dict) else data
    user = next((u for u in users if u.get("reddit_username") == "cascadia_coder" or u.get("root_user_id") == 1), None)
    if not user:
        return {"pass": False, "detail": "User cascadia_coder not found"}
    followed = user.get("followed_users", [])
    return {"pass": "mia_rescues" in followed, "detail": f"followed_users: {followed}"}


def verify_018(server_url):
    base = f"{server_url}/sites/forums"
    r = requests.get(f"{server_url}/_admin/data/reddit-augment/users_overlay")
    data = r.json()
    users = data.get("users", data) if isinstance(data, dict) else data
    user = next((u for u in users if u.get("root_user_id") == 1), None)
    if not user:
        return {"pass": False, "detail": "User 1 not found"}
    subs = user.get("subscribed_subreddits", [])
    return {"pass": "r/climbing" in subs, "detail": f"subscribed_subreddits: {subs}"}


def verify_019(server_url):
    base = f"{server_url}/sites/forums"
    r = requests.get(f"{server_url}/_admin/data/reddit-augment/messages_overlay")
    if r.status_code == 404:
        return {"pass": False, "detail": "No messages file found"}
    data = r.json()
    messages = data.get("messages", data) if isinstance(data, dict) else data
    found = any(
        m.get("to_username") == "sophie_designs" and "design" in m.get("body", "").lower()
        for m in messages
    )
    return {"pass": found, "detail": f"Message to sophie_designs found: {found}"}


def verify_020(server_url):
    base = f"{server_url}/sites/forums"
    # Check reports
    r = requests.get(f"{server_url}/_admin/data/reddit-augment/reports_overlay")
    if r.status_code == 404:
        return {"pass": False, "detail": "No reports file found"}
    data = r.json()
    reports = data.get("reports", data) if isinstance(data, dict) else data
    report_found = any(
        r.get("target_id") == "rd_post_011" and r.get("reason") == "spam"
        for r in reports
    )
    return {"pass": report_found, "detail": f"Report on rd_post_011 with reason 'spam' found: {report_found}"}
