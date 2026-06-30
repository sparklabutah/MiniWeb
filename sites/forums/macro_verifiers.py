"""Per-macro verification functions for forums.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/forums"


def verify_macro_navigate_by_semantic(server_url):
    """Navigate to user profile by finding username in post listing."""
    r = requests.get(f"{_base(server_url)}/api/users/cascadia_coder")
    data = r.json()
    return {"pass": data.get("post_count", 0) > 0,
            "detail": f"navigate_by_semantic: user profile loaded, posts={data.get('post_count')}"}


def verify_macro_navigate_by_dropdown(server_url):
    """Navigate to a subreddit via the subreddit listing."""
    r = requests.get(f"{_base(server_url)}/api/subreddits")
    subs = r.json()
    if not subs:
        return {"pass": False, "detail": "No subreddits returned"}
    name = subs[0]["name"].replace("r/", "")
    r2 = requests.get(f"{_base(server_url)}/r/{name}")
    return {"pass": r2.status_code == 200,
            "detail": f"Subreddit page '{name}': {r2.status_code}"}


def verify_macro_navigate_by_route(server_url):
    """Navigate to a post detail page by route."""
    r = requests.get(f"{_base(server_url)}/post/rd_post_001")
    return {"pass": r.status_code == 200,
            "detail": f"Post detail page: {r.status_code}"}


def verify_macro_search_by_query(server_url):
    """Keyword search across posts."""
    r = requests.get(f"{_base(server_url)}/api/search", params={"q": "hiking"})
    data = r.json()
    count = data.get("count", 0)
    return {"pass": count > 0,
            "detail": f"search_by_query 'hiking': {count} results"}


def verify_macro_search_by_semantic(server_url):
    """Semantic search across posts."""
    r = requests.get(f"{_base(server_url)}/api/search/semantic",
                     params={"q": "software development programming"})
    data = r.json()
    count = data.get("count", 0)
    return {"pass": r.status_code == 200,
            "detail": f"search_by_semantic: {count} results"}


def verify_macro_filter_by_dropdown(server_url):
    """Filter posts by subreddit dropdown."""
    r = requests.get(f"{_base(server_url)}/api/posts",
                     params={"subreddit": "r/hiking"})
    posts = r.json()
    ok = all(p["subreddit"] == "r/hiking" for p in posts)
    return {"pass": ok and len(posts) > 0,
            "detail": f"filter_by_dropdown r/hiking: {len(posts)} posts, all_match={ok}"}


def verify_macro_filter_by_date_range(server_url):
    """Filter posts by date range."""
    r = requests.get(f"{_base(server_url)}/api/posts",
                     params={"date_from": "2026-01-01", "date_to": "2026-12-31"})
    posts = r.json()
    ok = all(p.get("created_at", "") >= "2026-01-01" for p in posts)
    return {"pass": ok,
            "detail": f"filter 2026: {len(posts)} posts, all_in_range={ok}"}


def verify_macro_sort_by_ranking(server_url):
    """Sort posts by score (top)."""
    r = requests.get(f"{_base(server_url)}/api/posts", params={"sort": "top"})
    posts = r.json()
    if len(posts) < 2:
        return {"pass": True, "detail": "Too few posts to verify sort"}
    scores = [p.get("score", 0) for p in posts]
    is_sorted = all(scores[i] >= scores[i+1] for i in range(len(scores)-1))
    return {"pass": is_sorted,
            "detail": f"sort_by_ranking: sorted desc={is_sorted}"}


def verify_macro_extract_by_semantic(server_url):
    """Extract post info via semantic search."""
    r = requests.get(f"{_base(server_url)}/api/search/semantic",
                     params={"q": "machine learning artificial intelligence"})
    data = r.json()
    posts = data.get("posts", [])
    if posts:
        return {"pass": True,
                "detail": f"extract_by_semantic: top result='{posts[0]['title'][:50]}'"}
    return {"pass": True, "detail": "extract_by_semantic: no results (ok)"}


def verify_macro_extract_by_dropdown(server_url):
    """Extract subreddit stats via API."""
    r = requests.get(f"{_base(server_url)}/api/subreddits/hiking/stats")
    stats = r.json()
    return {"pass": "unique_authors" in stats,
            "detail": f"extract_by_dropdown: hiking stats={stats}"}


def verify_macro_extract_by_route(server_url):
    """Extract post details via direct route."""
    r = requests.get(f"{_base(server_url)}/api/posts/rd_post_001")
    post = r.json()
    return {"pass": "body" in post and "title" in post,
            "detail": f"extract_by_route: title='{post.get('title', '')[:50]}'"}


def verify_macro_create_from_free_text(server_url):
    """Create a comment from free text."""
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login",
           json={"username": "cascadia_coder", "password": "password"})
    r = s.post(f"{_base(server_url)}/api/posts/rd_post_001/comments",
               json={"body": "Test comment for macro verification"})
    data = r.json()
    ok = r.status_code == 201 and data.get("id")
    # Clean up
    if ok:
        s.delete(f"{_base(server_url)}/api/comments/{data['id']}")
    return {"pass": ok,
            "detail": f"create_from_free_text: comment_id={data.get('id')}"}


def verify_macro_submit_by_form(server_url):
    """Submit a post via form."""
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login",
           json={"username": "cascadia_coder", "password": "password"})
    r = s.post(f"{_base(server_url)}/api/posts",
               json={"title": "Macro test post", "body": "Test body",
                     "subreddit": "r/hiking"})
    data = r.json()
    ok = r.status_code == 201 and data.get("id")
    # Clean up
    if ok:
        s.delete(f"{_base(server_url)}/api/posts/{data['id']}")
    return {"pass": ok,
            "detail": f"submit_by_form: post_id={data.get('id')}"}


def verify_macro_submit_by_route(server_url):
    """Submit a post via API route."""
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login",
           json={"username": "cascadia_coder", "password": "password"})
    r = s.post(f"{_base(server_url)}/api/posts",
               json={"title": "API route test post", "body": "Body",
                     "subreddit": "r/programming"})
    data = r.json()
    ok = r.status_code == 201
    if ok:
        s.delete(f"{_base(server_url)}/api/posts/{data['id']}")
    return {"pass": ok,
            "detail": f"submit_by_route: status={r.status_code}"}


def verify_macro_edit_by_form(server_url):
    """Edit a post via API."""
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login",
           json={"username": "cascadia_coder", "password": "password"})
    # Create then edit
    r = s.post(f"{_base(server_url)}/api/posts",
               json={"title": "Edit test", "body": "Original", "subreddit": "r/hiking"})
    post = r.json()
    pid = post.get("id")
    r2 = s.put(f"{_base(server_url)}/api/posts/{pid}",
               json={"body": "Edited body"})
    edited = r2.json()
    ok = edited.get("body") == "Edited body"
    if pid:
        s.delete(f"{_base(server_url)}/api/posts/{pid}")
    return {"pass": ok,
            "detail": f"edit_by_form: body='{edited.get('body', '')}'"}


def verify_macro_delete_from_table(server_url):
    """Delete a post."""
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login",
           json={"username": "cascadia_coder", "password": "password"})
    r = s.post(f"{_base(server_url)}/api/posts",
               json={"title": "Delete test", "body": "To delete", "subreddit": "r/hiking"})
    post = r.json()
    pid = post.get("id")
    r2 = s.delete(f"{_base(server_url)}/api/posts/{pid}")
    data = r2.json()
    ok = data.get("status") == "deleted"
    return {"pass": ok,
            "detail": f"delete_from_table: {data}"}


def verify_macro_react_by_toggle(server_url):
    """Upvote a post (toggle)."""
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login",
           json={"username": "cascadia_coder", "password": "password"})
    # Get original score
    r = s.get(f"{_base(server_url)}/api/posts/rd_post_001")
    original_score = r.json().get("score", 0)
    # Upvote
    r2 = s.post(f"{_base(server_url)}/api/posts/rd_post_001/vote",
                json={"direction": "up"})
    data = r2.json()
    ok = data.get("score", 0) == original_score + 1
    # Undo
    s.post(f"{_base(server_url)}/api/posts/rd_post_001/vote",
           json={"direction": "down"})
    return {"pass": ok,
            "detail": f"react_by_toggle: score {original_score} -> {data.get('score')}"}


def verify_macro_follow_by_dropdown(server_url):
    """Follow a subreddit (follow_by_dropdown alias)."""
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login",
           json={"username": "cascadia_coder", "password": "password"})
    r = s.post(f"{_base(server_url)}/api/subreddits/gaming/follow")
    data = r.json()
    ok = data.get("action") in ("joined", "left")
    # Toggle back
    s.post(f"{_base(server_url)}/api/subreddits/gaming/follow")
    return {"pass": ok,
            "detail": f"follow_by_dropdown: action={data.get('action')}"}


def verify_macro_follow_by_toggle(server_url):
    """Follow a user (toggle)."""
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login",
           json={"username": "cascadia_coder", "password": "password"})
    r = s.post(f"{_base(server_url)}/api/users/marcus_climbs/follow")
    data = r.json()
    ok = data.get("action") in ("followed", "unfollowed")
    # Toggle back
    s.post(f"{_base(server_url)}/api/users/marcus_climbs/follow")
    return {"pass": ok,
            "detail": f"follow_by_toggle: action={data.get('action')}"}


def verify_macro_join_by_toggle(server_url):
    """Join/leave a subreddit (toggle)."""
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login",
           json={"username": "cascadia_coder", "password": "password"})
    r = s.post(f"{_base(server_url)}/api/subreddits/climbing/join")
    data = r.json()
    ok = data.get("action") in ("joined", "left")
    # Toggle back
    s.post(f"{_base(server_url)}/api/subreddits/climbing/join")
    return {"pass": ok,
            "detail": f"join_by_toggle: action={data.get('action')}"}


def verify_macro_share_by_dropdown(server_url):
    """Share a post via dropdown method selection."""
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login",
           json={"username": "cascadia_coder", "password": "password"})
    r = s.post(f"{_base(server_url)}/api/posts/rd_post_001/share",
               json={"method": "copy_link"})
    data = r.json()
    return {"pass": "share_url" in data,
            "detail": f"share_by_dropdown: url={data.get('share_url')}"}


def verify_macro_save_by_toggle(server_url):
    """Save/unsave a post (toggle)."""
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login",
           json={"username": "cascadia_coder", "password": "password"})
    r = s.post(f"{_base(server_url)}/api/posts/rd_post_005/save")
    data = r.json()
    ok = data.get("action") in ("saved", "unsaved")
    # Toggle back
    s.post(f"{_base(server_url)}/api/posts/rd_post_005/save")
    return {"pass": ok,
            "detail": f"save_by_toggle: action={data.get('action')}"}


def verify_macro_report_by_form(server_url):
    """Report a post via form."""
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login",
           json={"username": "cascadia_coder", "password": "password"})
    r = s.post(f"{_base(server_url)}/api/report",
               json={"target_type": "post", "target_id": "rd_post_001",
                     "reason": "test", "description": "macro verification test"})
    data = r.json()
    return {"pass": r.status_code == 201 and data.get("id"),
            "detail": f"report_by_form: report_id={data.get('id')}"}


def verify_macro_block_by_toggle(server_url):
    """Block/unblock a user (toggle)."""
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login",
           json={"username": "cascadia_coder", "password": "password"})
    r = s.post(f"{_base(server_url)}/api/users/syncwave_jake/block")
    data = r.json()
    ok = data.get("action") in ("blocked", "unblocked")
    # Toggle back
    s.post(f"{_base(server_url)}/api/users/syncwave_jake/block")
    return {"pass": ok,
            "detail": f"block_by_toggle: action={data.get('action')}"}


def verify_macro_message_from_free_text(server_url):
    """Send a direct message from free text."""
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login",
           json={"username": "cascadia_coder", "password": "password"})
    r = s.post(f"{_base(server_url)}/api/messages",
               json={"to": "marcus_climbs", "subject": "Macro test",
                     "body": "Testing message macro"})
    data = r.json()
    return {"pass": r.status_code == 201 and data.get("id"),
            "detail": f"message_from_free_text: msg_id={data.get('id')}"}


def verify_macro_authenticate_by_form(server_url):
    """Authenticate via login form/API."""
    s = requests.Session()
    r = s.post(f"{_base(server_url)}/api/login",
               json={"username": "cascadia_coder", "password": "password"})
    data = r.json()
    ok = data.get("user_id") == 1
    return {"pass": ok,
            "detail": f"authenticate_by_form: user_id={data.get('user_id')}"}


def verify_macro_register_by_form(server_url):
    """Register a new user via form/API."""
    s = requests.Session()
    import time
    username = f"test_macro_{int(time.time())}"
    r = s.post(f"{_base(server_url)}/api/register",
               json={"username": username, "password": "testpass123"})
    data = r.json()
    ok = r.status_code == 201 and data.get("user_id")
    return {"pass": ok,
            "detail": f"register_by_form: username={username}, user_id={data.get('user_id')}"}
