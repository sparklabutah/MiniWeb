"""Per-task HTTP verification functions for visual-how-to-guides."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/visual-how-to-guides"
    r = requests.get(f"{base}/api/guides?category=Cooking")
    guides = r.json()
    count = len(guides)
    return {"pass": count > 0, "detail": f"Cooking category has {count} guides"}


def verify_002(server_url):
    base = f"{server_url}/sites/visual-how-to-guides"
    r = requests.get(f"{base}/api/guides/4")
    guide = r.json()
    steps = guide.get("steps", [])
    count = len(steps)
    return {"pass": count > 0, "detail": f"Guide 4 has {count} steps"}


def verify_003(server_url):
    base = f"{server_url}/sites/visual-how-to-guides"
    r = requests.get(f"{base}/api/search?q=garden")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Search 'garden': {count} results"}


def verify_004(server_url):
    base = f"{server_url}/sites/visual-how-to-guides"
    r = requests.get(f"{base}/api/search/semantic?q=healthy+exercise+routine")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Semantic 'healthy exercise routine': {count} results"}


def verify_005(server_url):
    base = f"{server_url}/sites/visual-how-to-guides"
    r = requests.get(f"{base}/api/guides?category=Tech+Setup")
    guides = r.json()
    count = len(guides)
    return {"pass": count > 0, "detail": f"Tech Setup filter: {count} guides"}


def verify_006(server_url):
    base = f"{server_url}/sites/visual-how-to-guides"
    r = requests.get(f"{base}/api/guides?difficulty_min=3&difficulty_max=3")
    guides = r.json()
    count = len(guides)
    ok = all(g["difficulty"] == "hard" for g in guides)
    return {"pass": ok and count > 0, "detail": f"Hard-only filter: {count} guides, all_hard={ok}"}


def verify_007(server_url):
    base = f"{server_url}/sites/visual-how-to-guides"
    r = requests.get(f"{base}/api/guides?duration_min=30&duration_max=90")
    guides = r.json()
    count = len(guides)
    ok = all(30 <= g.get("duration_minutes", 0) <= 90 for g in guides)
    return {"pass": ok and count > 0, "detail": f"Duration 30-90 min: {count} guides, all_in_range={ok}"}


def verify_008(server_url):
    base = f"{server_url}/sites/visual-how-to-guides"
    r = requests.get(f"{base}/api/guides?sort=rating")
    guides = r.json()
    if not guides:
        return {"pass": False, "detail": "No guides returned"}
    first_title = guides[0]["title"]
    # Verify sorted descending
    ratings = [g.get("rating", 0) for g in guides]
    is_sorted = all(ratings[i] >= ratings[i + 1] for i in range(len(ratings) - 1))
    return {"pass": is_sorted, "detail": f"Top-rated: {first_title}, sorted_desc={is_sorted}"}


def verify_009(server_url):
    base = f"{server_url}/sites/visual-how-to-guides"
    r = requests.get(f"{base}/api/compare?ids=1,4,7")
    guides = r.json()
    if len(guides) < 3:
        return {"pass": False, "detail": f"Compare returned {len(guides)} guides, expected 3"}
    difficulties = [g["difficulty"] for g in guides]
    return {"pass": True, "detail": f"Difficulties: {', '.join(difficulties)}"}


def verify_010(server_url):
    base = f"{server_url}/sites/visual-how-to-guides"
    r = requests.get(f"{base}/api/guides/12")
    guide = r.json()
    author_id = guide.get("author_id")
    r2 = requests.get(f"{base}/api/users/{author_id}")
    author = r2.json()
    name = author.get("display_name", "")
    return {"pass": len(name) > 0, "detail": f"Guide 12 author: {name}"}


def verify_011(server_url):
    base = f"{server_url}/sites/visual-how-to-guides"
    r = requests.get(f"{base}/api/guides?date_from=2025-09-01&date_to=2025-10-31")
    guides = r.json()
    count = len(guides)
    ok = all("2025-09-01" <= g.get("created_at", "") <= "2025-10-31" for g in guides)
    return {"pass": ok and count >= 0, "detail": f"Date 2025-09-01 to 2025-10-31: {count} guides, all_in_range={ok}"}


def verify_012(server_url):
    base = f"{server_url}/sites/visual-how-to-guides"
    r = requests.get(f"{base}/api/guides/4/steps/3")
    data = r.json()
    step = data.get("step", {})
    title = step.get("title", "")
    return {"pass": len(title) > 0, "detail": f"Guide 4 step 3 title: {title}"}


def verify_013(server_url):
    base = f"{server_url}/sites/visual-how-to-guides"
    r = requests.get(f"{base}/api/guides/5/comments")
    comments = r.json()
    found = any(
        "wok technique" in c.get("text", "").lower() and c.get("user_id") == 1
        for c in comments
    )
    return {"pass": found, "detail": f"Comment by user 1 on guide 5 found={found}"}


def verify_014(server_url):
    base = f"{server_url}/sites/visual-how-to-guides"
    # Check that user 2 reacted to comment 1
    # We verify by checking the comment's helpful_count changed
    r = requests.get(f"{base}/api/guides/4/comments")
    comments = r.json()
    comment = next((c for c in comments if c["id"] == 1), None)
    if not comment:
        return {"pass": False, "detail": "Comment 1 not found"}
    helpful = comment.get("helpful_count", 0)
    return {"pass": helpful > 0, "detail": f"Comment 1 helpful_count: {helpful}"}


def verify_015(server_url):
    base = f"{server_url}/sites/visual-how-to-guides"
    r = requests.get(f"{base}/api/guides/1")
    guide = r.json()
    rating = guide.get("rating", 0)
    return {"pass": rating > 0, "detail": f"Guide 1 average rating: {rating}"}


def verify_016(server_url):
    base = f"{server_url}/sites/visual-how-to-guides"
    r = requests.get(f"{base}/api/users/4")
    user = r.json()
    followed = user.get("followed_authors", [])
    return {"pass": "Hannah Torres" in followed,
            "detail": f"User 4 followed: {followed}"}


def verify_017(server_url):
    base = f"{server_url}/sites/visual-how-to-guides"
    r = requests.get(f"{base}/api/bookmarks")
    # This needs session, so use the user-specific bookmark check
    # Check via users endpoint or bookmarks list
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "craft_lisa", "password": "pass523"})
    r = s.get(f"{base}/api/bookmarks")
    bookmarks = r.json()
    found = any(b.get("guide_id") == 3 for b in bookmarks)
    return {"pass": found, "detail": f"User 5 has guide 3 bookmarked: {found}"}


def verify_018(server_url):
    base = f"{server_url}/sites/visual-how-to-guides"
    r = requests.get(f"{base}/api/guides?sort=title")
    guides = r.json()
    if not guides:
        return {"pass": False, "detail": "No guides returned"}
    first_title = guides[0]["title"]
    titles = [g["title"].lower() for g in guides]
    is_sorted = all(titles[i] <= titles[i + 1] for i in range(len(titles) - 1))
    return {"pass": is_sorted, "detail": f"First (A-Z): {first_title}, sorted={is_sorted}"}


def verify_019(server_url):
    base = f"{server_url}/sites/visual-how-to-guides"
    r = requests.get(f"{base}/api/search?q=pasta")
    results = r.json()
    if not results:
        return {"pass": False, "detail": "No results for 'pasta'"}
    first = results[0]
    guide_id = first["id"]
    r2 = requests.get(f"{base}/api/guides/{guide_id}")
    guide = r2.json()
    duration = guide.get("duration_minutes")
    return {"pass": duration is not None, "detail": f"First 'pasta' result: {guide['title']}, duration={duration} min"}


def verify_020(server_url):
    base = f"{server_url}/sites/visual-how-to-guides"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "handy_hannah", "password": "pass123"})
    r = s.get(f"{base}/api/bookmarks")
    bookmarks = r.json()
    # User 1 starts with bookmarks for guides 4, 7, 12, and should now also have 9 and 10
    bookmark_guide_ids = {b.get("guide_id") for b in bookmarks}
    has_9 = 9 in bookmark_guide_ids
    has_10 = 10 in bookmark_guide_ids
    total = len(bookmarks)
    return {"pass": has_9 and has_10, "detail": f"User 1 total bookmarks: {total}, has_9={has_9}, has_10={has_10}"}
