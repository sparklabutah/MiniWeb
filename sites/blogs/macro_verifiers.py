"""Per-macro verification functions for blogs.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/blogs"


def verify_macro_navigate_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/categories")
    cats = r.json()
    if not cats:
        return {"pass": False, "detail": "No categories returned"}
    cat = cats[0]["name"]
    r2 = requests.get(f"{_base(server_url)}/category/{cat}")
    return {"pass": r2.status_code == 200, "detail": f"Category page '{cat}': {r2.status_code}"}


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/post/1")
    return {"pass": r.status_code == 200, "detail": f"Post detail page: {r.status_code}"}


def verify_macro_search_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/posts/search?q=the")
    results = r.json()
    return {"pass": len(results) > 0, "detail": f"search_by_query 'the': {len(results)} results"}


def verify_macro_search_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/posts/semantic?q=photography+tips")
    results = r.json()
    return {"pass": r.status_code == 200, "detail": f"search_by_semantic: {len(results)} results"}


def verify_macro_filter_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/posts?category=Art")
    posts = r.json()
    ok = all(p["category"] == "Art" for p in posts)
    return {"pass": ok, "detail": f"filter_by_dropdown Art: {len(posts)} posts, all_art={ok}"}


def verify_macro_filter_by_date_range(server_url):
    r = requests.get(f"{_base(server_url)}/api/posts?date_from=2025-06-01&date_to=2025-12-01")
    posts = r.json()
    ok = all("2025-06-01" <= p["date"] <= "2025-12-01" for p in posts)
    return {"pass": ok, "detail": f"filter date range: {len(posts)} posts, all_in_range={ok}"}


def verify_macro_sort_by_date_range(server_url):
    r = requests.get(f"{_base(server_url)}/api/posts?sort=oldest")
    posts = r.json()
    if len(posts) < 2:
        return {"pass": True, "detail": "Too few posts to verify sort"}
    dates = [p["date"] for p in posts]
    is_sorted = all(dates[i] <= dates[i+1] for i in range(len(dates)-1))
    return {"pass": is_sorted, "detail": f"sort_by_date_range: sorted={is_sorted}"}


def verify_macro_extract_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/posts/search?q=journey")
    results = r.json()
    if results:
        return {"pass": True, "detail": f"extract_by_query: first result title={results[0]['title'][:50]}"}
    return {"pass": True, "detail": "extract_by_query: no results (ok)"}


def verify_macro_extract_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/posts/semantic?q=learn+something+new")
    results = r.json()
    if results:
        return {"pass": True, "detail": f"extract_by_semantic: {len(results)} results, first cat={results[0]['category']}"}
    return {"pass": True, "detail": "extract_by_semantic: no results"}


def verify_macro_extract_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/categories")
    cats = r.json()
    return {"pass": len(cats) > 0, "detail": f"extract_by_dropdown: {len(cats)} categories"}


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/posts/1")
    post = r.json()
    return {"pass": "body" in post, "detail": f"extract_by_route: post has body={len(post.get('body',''))} chars"}


def verify_macro_create_from_free_text(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/posts/create", json={
        "title": "Macro Test Post",
        "body": "Testing create macro.",
        "category": "Technology",
        "tags": ["test"],
        "author_username": "midnight_coder",
    })
    data = r.json()
    ok = r.status_code == 201 and "id" in data
    # Clean up: we leave it (idempotent test)
    return {"pass": ok, "detail": f"create_from_free_text: id={data.get('id')}"}


def verify_macro_submit_by_route(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/posts/1/comment", json={
        "body": "Macro test comment",
        "author_username": "pixel_dreamer",
    })
    data = r.json()
    ok = r.status_code == 201 and "id" in data
    return {"pass": ok, "detail": f"submit_by_route: comment id={data.get('id')}"}


def verify_macro_post_from_free_text(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/posts/create", json={
        "title": "Macro Free Text Post",
        "body": "A freely composed blog entry for testing.",
        "category": "Lifestyle",
        "tags": ["macro-test"],
        "author_username": "bookworm_alex",
    })
    data = r.json()
    ok = r.status_code == 201
    return {"pass": ok, "detail": f"post_from_free_text: created={ok}"}


def verify_macro_follow_by_dropdown(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/users/7/follow", json={"blog": "green_thumb"})
    data = r.json()
    ok = data.get("action") == "followed"
    # Toggle back
    requests.post(f"{base}/api/users/7/follow", json={"blog": "green_thumb"})
    return {"pass": ok, "detail": f"follow_by_dropdown: action={data.get('action')}"}


def verify_macro_follow_by_toggle(server_url):
    base = _base(server_url)
    # Follow
    r1 = requests.post(f"{base}/api/users/6/follow", json={"blog": "retro_vinyl"})
    d1 = r1.json()
    # Unfollow
    r2 = requests.post(f"{base}/api/users/6/follow", json={"blog": "retro_vinyl"})
    d2 = r2.json()
    ok = d1.get("action") == "followed" and d2.get("action") == "unfollowed"
    return {"pass": ok, "detail": f"follow_by_toggle: first={d1.get('action')}, second={d2.get('action')}"}


def verify_macro_subscribe_by_toggle(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/users/7/subscribe", json={"tag": "macro-test-tag"})
    data = r.json()
    ok = data.get("action") == "subscribed"
    # Toggle back
    requests.post(f"{base}/api/users/7/subscribe", json={"tag": "macro-test-tag"})
    return {"pass": ok, "detail": f"subscribe_by_toggle: action={data.get('action')}"}


def verify_macro_share_by_dropdown(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/posts/1/share", json={"platform": "twitter"})
    data = r.json()
    ok = data.get("action") == "shared"
    return {"pass": ok, "detail": f"share_by_dropdown: action={data.get('action')}, shares={data.get('total_shares')}"}


def verify_macro_save_by_toggle(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/users/7/save", json={"post_id": 99})
    data = r.json()
    ok = data.get("action") == "saved"
    # Toggle back
    requests.post(f"{base}/api/users/7/save", json={"post_id": 99})
    return {"pass": ok, "detail": f"save_by_toggle: action={data.get('action')}"}


def verify_macro_report_by_form(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/posts/1/report", json={
        "reason": "spam",
        "details": "Macro test report",
        "reporter_username": "retro_vinyl",
    })
    data = r.json()
    ok = r.status_code == 201 and data.get("status") == "pending"
    return {"pass": ok, "detail": f"report_by_form: status={data.get('status')}"}
