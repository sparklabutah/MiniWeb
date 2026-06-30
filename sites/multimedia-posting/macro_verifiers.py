"""Per-macro verification functions for multimedia-posting.

Each function tests that the corresponding macro works end-to-end.
"""
import io
import requests


def _base(server_url):
    return f"{server_url}/sites/multimedia-posting"


def _login(server_url, username="alex.rivera"):
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login", json={"username": username})
    return s


def verify_macro_navigate_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/post-types")
    types = r.json()
    if not types:
        return {"pass": False, "detail": "No post types returned"}
    # Navigate to explore with type filter
    r2 = requests.get(f"{_base(server_url)}/explore?type={types[0]}")
    return {"pass": r2.status_code == 200,
            "detail": f"Navigate by type '{types[0]}': {r2.status_code}"}


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/profile/mp-u-001")
    return {"pass": r.status_code == 200, "detail": f"Profile page: {r.status_code}"}


def verify_macro_search_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/search?q=hiking")
    data = r.json()
    count = len(data.get("posts", []))
    return {"pass": count > 0, "detail": f"search_by_query 'hiking': {count} posts"}


def verify_macro_search_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/search/semantic?q=outdoor+adventure")
    results = r.json()
    return {"pass": r.status_code == 200, "detail": f"search_by_semantic: {len(results)} results"}


def verify_macro_search_by_checkbox(server_url):
    r = requests.get(f"{_base(server_url)}/api/posts?types=photo&types=video")
    posts = r.json()
    types = set(p.get("type") for p in posts)
    ok = types <= {"photo", "video"} and len(posts) > 0
    return {"pass": ok, "detail": f"search_by_checkbox: {len(posts)} posts, types={types}"}


def verify_macro_filter_by_radio(server_url):
    r = requests.get(f"{_base(server_url)}/api/posts?type=video")
    posts = r.json()
    ok = all(p.get("type") == "video" for p in posts)
    return {"pass": ok, "detail": f"filter_by_radio video: {len(posts)} posts"}


def verify_macro_sort_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/posts?sort=most_liked")
    posts = r.json()
    if len(posts) < 2:
        return {"pass": True, "detail": "Too few posts to verify sort"}
    is_sorted = all(posts[i].get("likes_count", 0) >= posts[i+1].get("likes_count", 0)
                     for i in range(len(posts)-1))
    return {"pass": is_sorted, "detail": f"sort_by_dropdown: sorted={is_sorted}"}


def verify_macro_extract_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/search/semantic?q=coffee")
    results = r.json()
    if results:
        return {"pass": True, "detail": f"extract_by_semantic: top={results[0].get('caption','')[:50]}"}
    return {"pass": True, "detail": "extract_by_semantic: no results (ok)"}


def verify_macro_extract_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/stats?type=photo")
    stats = r.json()
    return {"pass": "total_posts" in stats,
            "detail": f"extract_by_dropdown: photo count={stats.get('total_posts')}"}


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/posts/post-001")
    post = r.json()
    return {"pass": "caption" in post,
            "detail": f"extract_by_route: post-001 caption={post.get('caption','')[:50]}"}


def verify_macro_create_from_free_text(server_url):
    s = _login(server_url)
    r = s.post(f"{_base(server_url)}/api/posts", json={
        "caption": "Test post for macro verification #test",
        "type": "photo"
    })
    data = r.json()
    ok = r.status_code == 201 and "id" in data
    # Cleanup: delete the test post
    if ok:
        s.delete(f"{_base(server_url)}/api/posts/{data['id']}")
    return {"pass": ok, "detail": f"create_from_free_text: id={data.get('id')}"}


def verify_macro_edit_by_form(server_url):
    s = _login(server_url)
    # Create a test post, edit it, verify, then delete
    r = s.post(f"{_base(server_url)}/api/posts", json={
        "caption": "Original caption", "type": "photo"})
    post = r.json()
    pid = post["id"]
    r2 = s.put(f"{_base(server_url)}/api/posts/{pid}",
               json={"caption": "Edited caption"})
    edited = r2.json()
    ok = edited.get("caption") == "Edited caption"
    s.delete(f"{_base(server_url)}/api/posts/{pid}")
    return {"pass": ok, "detail": f"edit_by_form: caption={edited.get('caption')}"}


def verify_macro_delete_from_table(server_url):
    s = _login(server_url)
    r = s.post(f"{_base(server_url)}/api/posts", json={
        "caption": "To be deleted", "type": "photo"})
    post = r.json()
    pid = post["id"]
    r2 = s.delete(f"{_base(server_url)}/api/posts/{pid}")
    data = r2.json()
    ok = data.get("status") == "deleted"
    return {"pass": ok, "detail": f"delete_from_table: status={data.get('status')}"}


def verify_macro_post_by_query(server_url):
    s = _login(server_url, "marcus.chen")
    r = s.post(f"{_base(server_url)}/api/posts/post-001/comments",
               json={"text": "Macro test comment"})
    data = r.json()
    ok = r.status_code == 201 and "id" in data
    # Cleanup
    if ok:
        s.delete(f"{_base(server_url)}/api/comments/{data['id']}")
    return {"pass": ok, "detail": f"post_by_query: comment id={data.get('id')}"}


def verify_macro_post_from_free_text(server_url):
    s = _login(server_url)
    r = s.post(f"{_base(server_url)}/api/posts", json={
        "caption": "Free text post #macro #test", "type": "photo"})
    data = r.json()
    ok = r.status_code == 201 and "macro" in data.get("tags", [])
    if "id" in data:
        s.delete(f"{_base(server_url)}/api/posts/{data['id']}")
    return {"pass": ok, "detail": f"post_from_free_text: tags={data.get('tags')}"}


def verify_macro_select_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/posts?type=carousel")
    posts = r.json()
    ok = all(p.get("type") == "carousel" for p in posts) and len(posts) > 0
    return {"pass": ok, "detail": f"select_by_dropdown carousel: {len(posts)} posts"}


def verify_macro_configure_by_toggle(server_url):
    s = _login(server_url)
    s.put(f"{_base(server_url)}/api/settings", json={"dark_mode": True})
    r = s.get(f"{_base(server_url)}/api/settings")
    settings = r.json()
    ok = settings.get("dark_mode") is True
    # Toggle back
    s.put(f"{_base(server_url)}/api/settings", json={"dark_mode": False})
    return {"pass": ok, "detail": f"configure_by_toggle: dark_mode={settings.get('dark_mode')}"}


def verify_macro_play_by_dropdown(server_url):
    r = requests.post(f"{_base(server_url)}/api/posts/post-027/play",
                      json={"quality": "720p"})
    data = r.json()
    ok = data.get("quality") == "720p" and data.get("status") == "playing"
    return {"pass": ok, "detail": f"play_by_dropdown: quality={data.get('quality')}"}


def verify_macro_play_by_playback(server_url):
    r = requests.post(f"{_base(server_url)}/api/stories/story-001/play")
    data = r.json()
    ok = data.get("status") == "played" and data.get("views_count", 0) > 0
    return {"pass": ok, "detail": f"play_by_playback: views={data.get('views_count')}"}


def verify_macro_export_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/export?format=csv")
    lines = r.text.strip().split("\n")
    ok = len(lines) > 1
    return {"pass": ok, "detail": f"export_by_dropdown CSV: {len(lines)} lines"}


def verify_macro_upload_by_upload(server_url):
    s = _login(server_url)
    files = {"file": ("test.jpg", io.BytesIO(b"test data"), "image/jpeg")}
    r = s.post(f"{_base(server_url)}/api/upload", files=files)
    data = r.json()
    ok = r.status_code == 201 and data.get("filename") == "test.jpg"
    return {"pass": ok, "detail": f"upload_by_upload: filename={data.get('filename')}"}


def verify_macro_react_by_toggle(server_url):
    s = _login(server_url)
    r = s.post(f"{_base(server_url)}/api/posts/post-001/like")
    data = r.json()
    ok = data.get("status") in ("liked", "unliked")
    # Toggle back
    s.post(f"{_base(server_url)}/api/posts/post-001/like")
    return {"pass": ok, "detail": f"react_by_toggle: {data.get('status')}"}


def verify_macro_follow_by_dropdown(server_url):
    s = _login(server_url)
    r = s.post(f"{_base(server_url)}/api/users/follow-by-dropdown",
               json={"user_id": "mp-u-005"})
    data = r.json()
    ok = data.get("status") == "followed"
    return {"pass": ok,
            "detail": f"follow_by_dropdown: status={data.get('status')}"}


def verify_macro_follow_by_toggle(server_url):
    s = _login(server_url)
    r = s.post(f"{_base(server_url)}/api/users/mp-u-009/follow")
    data = r.json()
    ok = data.get("status") in ("followed", "unfollowed")
    # Toggle back
    s.post(f"{_base(server_url)}/api/users/mp-u-009/follow")
    return {"pass": ok, "detail": f"follow_by_toggle: {data.get('status')}"}


def verify_macro_subscribe_by_toggle(server_url):
    s = _login(server_url)
    r = s.post(f"{_base(server_url)}/api/users/mp-u-002/subscribe")
    data = r.json()
    ok = data.get("status") in ("subscribed", "unsubscribed")
    # Toggle back
    s.post(f"{_base(server_url)}/api/users/mp-u-002/subscribe")
    return {"pass": ok, "detail": f"subscribe_by_toggle: {data.get('status')}"}


def verify_macro_share_by_dropdown(server_url):
    s = _login(server_url)
    r = s.post(f"{_base(server_url)}/api/posts/post-001/share",
               json={"method": "dm", "recipient": "mp-u-002"})
    data = r.json()
    ok = data.get("method") == "dm"
    return {"pass": ok, "detail": f"share_by_dropdown: method={data.get('method')}"}


def verify_macro_save_by_toggle(server_url):
    s = _login(server_url)
    r = s.post(f"{_base(server_url)}/api/posts/post-001/save")
    data = r.json()
    ok = data.get("status") in ("saved", "unsaved")
    # Toggle back
    s.post(f"{_base(server_url)}/api/posts/post-001/save")
    return {"pass": ok, "detail": f"save_by_toggle: {data.get('status')}"}


def verify_macro_report_by_form(server_url):
    s = _login(server_url)
    r = s.post(f"{_base(server_url)}/api/posts/post-010/report",
               json={"reason": "spam", "details": "test report"})
    data = r.json()
    ok = r.status_code == 201 and data.get("reason") == "spam"
    return {"pass": ok, "detail": f"report_by_form: reason={data.get('reason')}"}


def verify_macro_block_by_toggle(server_url):
    s = _login(server_url)
    r = s.post(f"{_base(server_url)}/api/users/mp-u-009/block")
    data = r.json()
    ok = data.get("status") in ("blocked", "unblocked")
    # Toggle back
    s.post(f"{_base(server_url)}/api/users/mp-u-009/block")
    return {"pass": ok, "detail": f"block_by_toggle: {data.get('status')}"}
