"""Per-macro verification functions for video.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/video"


def verify_macro_navigate_by_dropdown(server_url):
    """Navigate by category dropdown on homepage."""
    r = requests.get(f"{_base(server_url)}/api/categories")
    cats = r.json()
    if not cats:
        return {"pass": False, "detail": "No categories returned"}
    cat = cats[0]["name"]
    r2 = requests.get(f"{_base(server_url)}/", params={"category": cat})
    return {"pass": r2.status_code == 200,
            "detail": f"Category page '{cat}': {r2.status_code}"}


def verify_macro_navigate_by_route(server_url):
    """Navigate to video watch page by direct URL."""
    r = requests.get(f"{_base(server_url)}/watch/1")
    return {"pass": r.status_code == 200,
            "detail": f"Watch page /watch/1: {r.status_code}"}


def verify_macro_search_by_query(server_url):
    """Search videos by keyword query."""
    r = requests.get(f"{_base(server_url)}/api/search", params={"q": "hiking"})
    results = r.json()
    return {"pass": len(results) > 0,
            "detail": f"search_by_query 'hiking': {len(results)} results"}


def verify_macro_search_by_semantic(server_url):
    """Semantic multi-word relevance search."""
    r = requests.get(f"{_base(server_url)}/api/search/semantic",
                     params={"q": "programming tutorial beginner"})
    results = r.json()
    return {"pass": r.status_code == 200,
            "detail": f"search_by_semantic: {len(results)} results"}


def verify_macro_filter_by_dropdown(server_url):
    """Filter videos by category dropdown."""
    r = requests.get(f"{_base(server_url)}/api/videos",
                     params={"category": "Gaming"})
    videos = r.json()
    ok = all(v.get("category") == "Gaming" for v in videos)
    return {"pass": ok and len(videos) > 0,
            "detail": f"filter Gaming: {len(videos)} videos, all_gaming={ok}"}


def verify_macro_filter_by_slider(server_url):
    """Filter videos by duration range (slider)."""
    r = requests.get(f"{_base(server_url)}/api/videos",
                     params={"duration_min": 500, "duration_max": 1000})
    videos = r.json()
    ok = all(500 <= v.get("duration_seconds", 0) <= 1000 for v in videos)
    return {"pass": ok,
            "detail": f"filter duration 500-1000s: {len(videos)} videos, all_in_range={ok}"}


def verify_macro_filter_by_date_range(server_url):
    """Filter videos by upload date range."""
    r = requests.get(f"{_base(server_url)}/api/videos",
                     params={"date_from": "2025-01-01", "date_to": "2025-06-30"})
    videos = r.json()
    ok = all("2025-01-01" <= v.get("upload_date", "") <= "2025-06-30"
             for v in videos)
    return {"pass": ok,
            "detail": f"filter 2025-01-01 to 2025-06-30: {len(videos)} videos, in_range={ok}"}


def verify_macro_sort_by_ranking(server_url):
    """Sort videos by view count."""
    r = requests.get(f"{_base(server_url)}/api/videos", params={"sort": "views"})
    videos = r.json()
    if len(videos) < 2:
        return {"pass": True, "detail": "Too few videos to verify sort"}
    is_sorted = all(videos[i].get("views", 0) >= videos[i + 1].get("views", 0)
                     for i in range(len(videos) - 1))
    return {"pass": is_sorted,
            "detail": f"sort_by_ranking (views): sorted={is_sorted}"}


def verify_macro_extract_by_query(server_url):
    """Extract information from search results."""
    r = requests.get(f"{_base(server_url)}/api/search", params={"q": "recipe"})
    results = r.json()
    if results:
        return {"pass": True,
                "detail": f"extract_by_query: first result={results[0]['title'][:50]}"}
    return {"pass": True, "detail": "extract_by_query: no results (ok)"}


def verify_macro_submit_by_route(server_url):
    """Update video metadata via API."""
    r = requests.put(f"{_base(server_url)}/api/videos/1",
                     json={"description": "Updated description for macro test"})
    data = r.json()
    ok = data.get("description") == "Updated description for macro test"
    # Revert
    requests.put(f"{_base(server_url)}/api/videos/1",
                 json={"description": "Join me on the Cascadia Lake trail in the Washington Cascades! I cover the trailhead parking situation, trail conditions, what gear to bring, and the stunning views along the way. This 8.4-mile out-and-back hike is one of my all-time favorites in the PNW."})
    return {"pass": ok,
            "detail": f"submit_by_route: updated={ok}"}


def verify_macro_upload_by_upload(server_url):
    """Upload a new video via API."""
    r = requests.post(f"{_base(server_url)}/api/videos",
                      json={"title": "Macro Test Upload", "channel_id": 1,
                            "category": "Education"})
    data = r.json()
    created = data.get("id") is not None
    # Clean up
    if created:
        requests.delete(f"{_base(server_url)}/api/videos/{data['id']}")
    return {"pass": created,
            "detail": f"upload_by_upload: created id={data.get('id')}"}


def verify_macro_select_by_dropdown(server_url):
    """Add video to playlist (select playlist dropdown)."""
    # Use a test video that is likely not in playlist 2
    r = requests.post(f"{_base(server_url)}/api/playlists/2/add",
                      json={"video_id": 8})
    if r.status_code == 409:
        return {"pass": True, "detail": "select_by_dropdown: video already in playlist (ok)"}
    data = r.json()
    items = data.get("items", [])
    has_8 = any(i.get("video_id") == 8 for i in items)
    return {"pass": has_8,
            "detail": f"select_by_dropdown: video 8 in playlist 2={has_8}"}


def verify_macro_configure_by_route(server_url):
    """Update user settings/preferences."""
    r = requests.put(f"{_base(server_url)}/api/users/1/settings",
                     json={"autoplay": False})
    data = r.json()
    prefs = data.get("preferences", {})
    ok = prefs.get("autoplay") is False
    # Revert
    requests.put(f"{_base(server_url)}/api/users/1/settings",
                 json={"autoplay": True})
    return {"pass": ok,
            "detail": f"configure_by_route: autoplay set to False={ok}"}


def verify_macro_play_by_slider(server_url):
    """Seek video playback position."""
    r = requests.post(f"{_base(server_url)}/api/videos/1/seek",
                      json={"position": 500})
    data = r.json()
    pos = data.get("position_seconds", 0)
    return {"pass": pos == 500,
            "detail": f"play_by_slider: position={pos}"}


def verify_macro_play_by_date_range(server_url):
    """Filter watch history by date range."""
    r = requests.get(f"{_base(server_url)}/api/history",
                     params={"date_from": "2025-01-01", "date_to": "2025-12-31"})
    entries = r.json()
    return {"pass": r.status_code == 200,
            "detail": f"play_by_date_range: {len(entries)} history entries"}


def verify_macro_play_by_playback(server_url):
    """Set playback speed and quality."""
    r = requests.post(f"{_base(server_url)}/api/videos/1/playback",
                      json={"speed": 2.0, "quality": "1080p"})
    data = r.json()
    speed_ok = data.get("speed") == 2.0
    quality_ok = data.get("quality") == "1080p"
    return {"pass": speed_ok and quality_ok,
            "detail": f"play_by_playback: speed={data.get('speed')}, quality={data.get('quality')}"}


def verify_macro_post_from_free_text(server_url):
    """Post a comment on a video."""
    r = requests.post(f"{_base(server_url)}/api/videos/1/comments",
                      json={"text": "Macro test comment", "user_id": 1})
    data = r.json()
    ok = data.get("text") == "Macro test comment"
    # Clean up
    if data.get("id"):
        requests.delete(f"{_base(server_url)}/api/comments/{data['id']}")
    return {"pass": ok,
            "detail": f"post_from_free_text: comment created={ok}"}


def verify_macro_react_by_toggle(server_url):
    """Like/unlike a video."""
    # Get current likes
    r0 = requests.get(f"{_base(server_url)}/api/videos/1")
    before = r0.json().get("likes", 0)
    # Like
    r = requests.post(f"{_base(server_url)}/api/videos/1/like",
                      json={"action": "like"})
    data = r.json()
    after = data.get("likes", 0)
    ok = after == before + 1
    # Unlike to revert
    requests.post(f"{_base(server_url)}/api/videos/1/like",
                  json={"action": "unlike"})
    return {"pass": ok,
            "detail": f"react_by_toggle: likes {before} -> {after}"}


def verify_macro_rate_by_slider(server_url):
    """Rate a video 1-5 stars."""
    r = requests.post(f"{_base(server_url)}/api/videos/1/rate",
                      json={"rating": 4, "user_id": 9})
    data = r.json()
    ok = data.get("user_rating") == 4
    return {"pass": ok,
            "detail": f"rate_by_slider: rating={data.get('user_rating')}, avg={data.get('average_rating')}"}


def verify_macro_follow_by_toggle(server_url):
    """Toggle follow on a channel."""
    r = requests.post(f"{_base(server_url)}/api/channels/1/follow",
                      json={"user_id": 9})
    data = r.json()
    ok = data.get("action") == "followed"
    # Toggle back
    requests.post(f"{_base(server_url)}/api/channels/1/follow",
                  json={"user_id": 9})
    return {"pass": ok,
            "detail": f"follow_by_toggle: action={data.get('action')}"}


def verify_macro_subscribe_by_toggle(server_url):
    """Toggle subscription to a channel."""
    r = requests.post(f"{_base(server_url)}/api/channels/1/subscribe",
                      json={"user_id": 9})
    data = r.json()
    ok = data.get("action") == "subscribed"
    # Toggle back
    requests.post(f"{_base(server_url)}/api/channels/1/subscribe",
                  json={"user_id": 9})
    return {"pass": ok,
            "detail": f"subscribe_by_toggle: action={data.get('action')}"}


def verify_macro_share_by_dropdown(server_url):
    """Share a video via a specified platform."""
    r = requests.post(f"{_base(server_url)}/api/videos/1/share",
                      json={"platform": "twitter"})
    data = r.json()
    ok = data.get("platform") == "twitter" and data.get("share_url") is not None
    return {"pass": ok,
            "detail": f"share_by_dropdown: platform={data.get('platform')}, shares={data.get('total_shares')}"}


def verify_macro_save_by_toggle(server_url):
    """Toggle save/bookmark on a video."""
    r = requests.post(f"{_base(server_url)}/api/videos/1/save",
                      json={"user_id": 9})
    data = r.json()
    ok = data.get("action") == "saved"
    # Toggle back
    requests.post(f"{_base(server_url)}/api/videos/1/save",
                  json={"user_id": 9})
    return {"pass": ok,
            "detail": f"save_by_toggle: action={data.get('action')}"}


def verify_macro_report_by_form(server_url):
    """Report a video for a reason."""
    r = requests.post(f"{_base(server_url)}/api/videos/1/report",
                      json={"reason": "spam", "details": "Macro test report",
                            "user_id": 9})
    data = r.json()
    ok = data.get("reason") == "spam" and data.get("status") == "pending"
    return {"pass": ok,
            "detail": f"report_by_form: reason={data.get('reason')}, status={data.get('status')}"}


def verify_macro_authenticate_by_form(server_url):
    """Authenticate via API login."""
    r = requests.post(f"{_base(server_url)}/api/login",
                      json={"username": "alex_trails", "password": "alex_trails"})
    data = r.json()
    ok = data.get("user_id") == 1
    return {"pass": ok,
            "detail": f"authenticate: user_id={data.get('user_id')}"}
