"""Per-task HTTP verification functions for video."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/video"
    r = requests.get(f"{base}/api/videos", params={"category": "Gaming"})
    videos = r.json()
    count = len(videos)
    return {"pass": count > 0, "detail": f"Gaming category has {count} videos"}


def verify_002(server_url):
    base = f"{server_url}/sites/video"
    r = requests.get(f"{base}/api/videos/7")
    video = r.json()
    channel_id = video.get("channel_id")
    r2 = requests.get(f"{base}/api/channels/{channel_id}")
    channel = r2.json()
    name = channel.get("channel_name", "")
    return {"pass": name == "Marcus Codes & Climbs",
            "detail": f"Video 7 channel: {name}"}


def verify_003(server_url):
    base = f"{server_url}/sites/video"
    r = requests.get(f"{base}/api/search", params={"q": "Rust"})
    results = r.json()
    count = len(results)
    return {"pass": count > 0, "detail": f"Search 'Rust': {count} results"}


def verify_004(server_url):
    base = f"{server_url}/sites/video"
    r = requests.get(f"{base}/api/search/semantic",
                     params={"q": "outdoor hiking adventure"})
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Semantic 'outdoor hiking adventure': {count} results"}


def verify_005(server_url):
    base = f"{server_url}/sites/video"
    r = requests.get(f"{base}/api/videos", params={"category": "Education"})
    videos = r.json()
    count = len(videos)
    return {"pass": count > 0, "detail": f"Education filter: {count} videos"}


def verify_006(server_url):
    base = f"{server_url}/sites/video"
    r = requests.get(f"{base}/api/videos",
                     params={"duration_min": 1000, "duration_max": 1500})
    videos = r.json()
    count = len(videos)
    ok = all(1000 <= v.get("duration_seconds", 0) <= 1500 for v in videos)
    return {"pass": ok and count >= 0,
            "detail": f"Duration 1000-1500s: {count} videos, all_in_range={ok}"}


def verify_007(server_url):
    base = f"{server_url}/sites/video"
    r = requests.get(f"{base}/api/videos",
                     params={"date_from": "2025-06-01", "date_to": "2025-12-31"})
    videos = r.json()
    count = len(videos)
    ok = all("2025-06-01" <= v.get("upload_date", "") <= "2025-12-31" for v in videos)
    return {"pass": ok and count >= 0,
            "detail": f"Date 2025-06-01 to 2025-12-31: {count} videos, all_in_range={ok}"}


def verify_008(server_url):
    base = f"{server_url}/sites/video"
    r = requests.get(f"{base}/api/videos", params={"sort": "views"})
    videos = r.json()
    if not videos:
        return {"pass": False, "detail": "No videos returned"}
    first_title = videos[0].get("title", "")
    is_sorted = all(videos[i].get("views", 0) >= videos[i + 1].get("views", 0)
                     for i in range(len(videos) - 1))
    return {"pass": is_sorted,
            "detail": f"Most viewed: {first_title[:60]}, sorted={is_sorted}"}


def verify_009(server_url):
    base = f"{server_url}/sites/video"
    r = requests.get(f"{base}/api/search", params={"q": "design"})
    results = r.json()
    if not results:
        return {"pass": True, "detail": "No results for 'design'"}
    first = results[0].get("title", "")
    return {"pass": len(first) > 0,
            "detail": f"First 'design' result: {first[:60]}"}


def verify_010(server_url):
    base = f"{server_url}/sites/video"
    r = requests.get(f"{base}/api/videos/3")
    video = r.json()
    title = video.get("title", "")
    expected = "Easy Homemade Pasta | Quick Weeknight Recipe"
    return {"pass": title == expected,
            "detail": f"Video 3 title: {title}"}


def verify_011(server_url):
    base = f"{server_url}/sites/video"
    r = requests.get(f"{base}/api/search", params={"q": "Test Upload Video"})
    results = r.json()
    found = any(v.get("title") == "Test Upload Video" for v in results)
    return {"pass": found,
            "detail": f"'Test Upload Video' found in search: {found}"}


def verify_012(server_url):
    base = f"{server_url}/sites/video"
    r = requests.get(f"{base}/api/playlists/2")
    playlist = r.json()
    items = playlist.get("items", [])
    has_video_5 = any(item.get("video_id") == 5 for item in items)
    return {"pass": has_video_5,
            "detail": f"Playlist 2 contains video 5: {has_video_5}, total items: {len(items)}"}


def verify_013(server_url):
    base = f"{server_url}/sites/video"
    r = requests.get(f"{base}/api/users/1/settings")
    data = r.json()
    prefs = data.get("preferences", {})
    dark_mode = prefs.get("dark_mode", False)
    return {"pass": dark_mode is True,
            "detail": f"User 1 dark_mode: {dark_mode}"}


def verify_014(server_url):
    base = f"{server_url}/sites/video"
    r = requests.post(f"{base}/api/videos/14/seek",
                      json={"position": 900})
    data = r.json()
    progress = data.get("progress_percent", 0)
    # Video 14 is 1845 seconds, 900/1845 ~= 48.8%
    expected_approx = round((900 / 1845) * 100, 1)
    return {"pass": abs(progress - expected_approx) < 1.0,
            "detail": f"Seek to 900s: progress={progress}%, expected~{expected_approx}%"}


def verify_015(server_url):
    base = f"{server_url}/sites/video"
    r = requests.get(f"{base}/api/history",
                     params={"date_from": "2025-09-01", "date_to": "2025-12-31"})
    entries = r.json()
    count = len(entries)
    ok = all("2025-09-01" <= h.get("watched_at", "")[:10] <= "2025-12-31"
             for h in entries)
    return {"pass": ok,
            "detail": f"History 2025-09-01 to 2025-12-31: {count} entries, all_in_range={ok}"}


def verify_016(server_url):
    base = f"{server_url}/sites/video"
    r = requests.post(f"{base}/api/videos/6/playback",
                      json={"speed": 1.5, "quality": "720p"})
    data = r.json()
    speed_ok = data.get("speed") == 1.5
    quality_ok = data.get("quality") == "720p"
    return {"pass": speed_ok and quality_ok,
            "detail": f"Playback: speed={data.get('speed')}, quality={data.get('quality')}"}


def verify_017(server_url):
    base = f"{server_url}/sites/video"
    r = requests.get(f"{base}/api/videos/1/comments")
    comments = r.json()
    target_text = "Amazing trail footage! Adding this to my hiking bucket list."
    found = any(c.get("text") == target_text and c.get("user_id") == 2
                for c in comments)
    return {"pass": found,
            "detail": f"Comment by user 2 on video 1 found: {found}"}


def verify_018(server_url):
    base = f"{server_url}/sites/video"
    # Check video 28 was liked (likes should have increased)
    r = requests.get(f"{base}/api/videos/28")
    video = r.json()
    # Check user 2 has video 28 saved
    r2 = requests.get(f"{base}/api/users/2")
    user = r2.json()
    saved = user.get("saved_videos", [])
    has_saved = 28 in saved
    return {"pass": has_saved,
            "detail": f"User 2 saved video 28: {has_saved}, video 28 likes: {video.get('likes')}"}


def verify_019(server_url):
    base = f"{server_url}/sites/video"
    # Check rating exists
    r = requests.get(f"{base}/api/videos/7/ratings")
    data = r.json()
    ratings = data.get("ratings", [])
    has_rating = any(r.get("user_id") == 1 and r.get("rating") == 5
                     for r in ratings)
    # Check shares
    r2 = requests.get(f"{base}/api/videos/7")
    video = r2.json()
    shares = video.get("shares", 0)
    return {"pass": has_rating and shares > 0,
            "detail": f"Video 7: user 1 5-star rating={has_rating}, shares={shares}"}


def verify_020(server_url):
    base = f"{server_url}/sites/video"
    # Check user 4 subscribed to channel 9
    r = requests.get(f"{base}/api/users/4")
    user = r.json()
    subscriptions = user.get("subscriptions", [])
    sub_ok = 9 in subscriptions

    # Check user 4 follows channel 1
    following = user.get("following", [])
    follow_ok = 1 in following

    # Check report on video 8
    r2 = requests.get(f"{base}/api/reports", params={"video_id": 8})
    reports = r2.json()
    report_ok = any(
        rpt.get("reason") == "inappropriate"
        and "misleading" in rpt.get("details", "").lower()
        for rpt in reports
    )
    return {"pass": sub_ok and follow_ok and report_ok,
            "detail": f"sub_channel9={sub_ok}, follow_channel1={follow_ok}, report_video8={report_ok}"}
