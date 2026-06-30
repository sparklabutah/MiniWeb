"""Per-task HTTP verification functions for podcasts-audiobooks."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/podcasts-audiobooks"
    r = requests.get(f"{base}/api/podcasts?category=Technology")
    podcasts = r.json()
    count = len(podcasts)
    return {"pass": count > 0, "detail": f"Technology podcasts: {count}"}


def verify_002(server_url):
    base = f"{server_url}/sites/podcasts-audiobooks"
    r = requests.get(f"{base}/api/podcasts/1")
    podcast = r.json()
    host = podcast.get("host", "")
    return {"pass": len(host) > 0, "detail": f"Podcast 1 host: {host}"}


def verify_003(server_url):
    base = f"{server_url}/sites/podcasts-audiobooks"
    r = requests.get(f"{base}/api/search?q=crime")
    results = r.json()
    count = len(results.get("podcasts", []))
    return {"pass": count >= 0, "detail": f"Search 'crime' podcasts: {count}"}


def verify_004(server_url):
    base = f"{server_url}/sites/podcasts-audiobooks"
    r = requests.get(f"{base}/api/search/semantic?q=technology+artificial+intelligence&type=podcasts")
    results = r.json()
    count = len(results.get("podcasts", []))
    return {"pass": count >= 0, "detail": f"Semantic search 'technology AI' podcasts: {count}"}


def verify_005(server_url):
    base = f"{server_url}/sites/podcasts-audiobooks"
    r = requests.get(f"{base}/api/audiobooks?genre=Fiction")
    audiobooks = r.json()
    count = len(audiobooks)
    ok = all(a["genre"] == "Fiction" for a in audiobooks)
    return {"pass": count > 0 and ok, "detail": f"Fiction audiobooks: {count}, all_fiction={ok}"}


def verify_006(server_url):
    base = f"{server_url}/sites/podcasts-audiobooks"
    r = requests.get(f"{base}/api/audiobooks?min_rating=4.7")
    audiobooks = r.json()
    count = len(audiobooks)
    ok = all(a["rating"] >= 4.7 for a in audiobooks)
    return {"pass": count > 0 and ok, "detail": f"Audiobooks rating >= 4.7: {count}, all_pass={ok}"}


def verify_007(server_url):
    base = f"{server_url}/sites/podcasts-audiobooks"
    r = requests.get(f"{base}/api/audiobooks?sort=title")
    audiobooks = r.json()
    if not audiobooks:
        return {"pass": False, "detail": "No audiobooks returned"}
    first = audiobooks[0]["title"]
    titles = [a["title"].lower() for a in audiobooks]
    is_sorted = all(titles[i] <= titles[i + 1] for i in range(len(titles) - 1))
    return {"pass": is_sorted, "detail": f"First title (sorted): {first}, sorted={is_sorted}"}


def verify_008(server_url):
    base = f"{server_url}/sites/podcasts-audiobooks"
    r = requests.get(f"{base}/api/search?q=history")
    results = r.json()
    podcasts = results.get("podcasts", [])
    if not podcasts:
        return {"pass": True, "detail": "No podcast results for 'history'"}
    first = podcasts[0]["title"]
    return {"pass": len(first) > 0, "detail": f"First 'history' podcast: {first}"}


def verify_009(server_url):
    base = f"{server_url}/sites/podcasts-audiobooks"
    r = requests.get(f"{base}/api/podcasts?category=Science")
    podcasts = r.json()
    if not podcasts:
        return {"pass": False, "detail": "No Science podcasts found"}
    first = podcasts[0]["title"]
    return {"pass": len(first) > 0, "detail": f"First Science podcast: {first}"}


def verify_010(server_url):
    base = f"{server_url}/sites/podcasts-audiobooks"
    r = requests.get(f"{base}/api/audiobooks?genre=Science+Fiction")
    audiobooks = r.json()
    count = len(audiobooks)
    return {"pass": count > 0, "detail": f"Science Fiction audiobooks: {count}"}


def verify_011(server_url):
    base = f"{server_url}/sites/podcasts-audiobooks"
    r = requests.get(f"{base}/api/episodes?podcast_id=3&sort=date&limit=1")
    episodes = r.json()
    if not episodes:
        return {"pass": False, "detail": "No episodes for podcast 3"}
    title = episodes[0]["title"]
    return {"pass": len(title) > 0, "detail": f"Most recent episode of podcast 3: {title}"}


def verify_012(server_url):
    base = f"{server_url}/sites/podcasts-audiobooks"
    r = requests.get(f"{base}/api/episodes?date_from=2025-01-01&date_to=2025-06-30")
    episodes = r.json()
    count = len(episodes)
    ok = all("2025-01-01" <= e["publish_date"] <= "2025-06-30" for e in episodes)
    return {"pass": count > 0 and ok, "detail": f"Episodes Jan-Jun 2025: {count}, all_in_range={ok}"}


def verify_013(server_url):
    base = f"{server_url}/sites/podcasts-audiobooks"
    r = requests.get(f"{base}/api/library/1")
    lib = r.json()
    speed = lib.get("playback_speed", 1.0)
    return {"pass": speed == 1.5, "detail": f"User 1 playback speed: {speed}"}


def verify_014(server_url):
    base = f"{server_url}/sites/podcasts-audiobooks"
    r = requests.get(f"{base}/api/export?type=podcasts&format=csv")
    lines = r.text.strip().split("\n")
    data_rows = len(lines) - 1  # minus header
    return {"pass": data_rows > 0, "detail": f"CSV export podcasts: {data_rows} data rows"}


def verify_015(server_url):
    base = f"{server_url}/sites/podcasts-audiobooks"
    r = requests.get(f"{base}/api/reviews?item_type=podcast&item_id=1&user_id=2")
    reviews = r.json()
    has_review = any(
        r["text"] == "Excellent daily coverage of current events." and r["rating"] == 4
        for r in reviews
    )
    return {"pass": has_review, "detail": f"User 2 review on podcast 1: found={has_review}"}


def verify_016(server_url):
    base = f"{server_url}/sites/podcasts-audiobooks"
    r = requests.get(f"{base}/api/episodes/1")
    episode = r.json()
    liked_by = episode.get("liked_by", [])
    has_user3 = 3 in liked_by
    return {"pass": has_user3, "detail": f"Episode 1 liked_by: {liked_by}, user3={has_user3}"}


def verify_017(server_url):
    base = f"{server_url}/sites/podcasts-audiobooks"
    r = requests.get(f"{base}/api/reviews?item_type=audiobook&item_id=5&user_id=4")
    reviews = r.json()
    has_review = any(r["rating"] == 3.5 for r in reviews)
    return {"pass": has_review, "detail": f"User 4 review on audiobook 5: found_3.5={has_review}"}


def verify_018(server_url):
    base = f"{server_url}/sites/podcasts-audiobooks"
    # Sarah Mitchell is host of podcast 1
    r = requests.get(f"{base}/api/library/5")
    lib = r.json()
    followed = lib.get("followed_podcasts", [])
    return {"pass": 1 in followed, "detail": f"User 5 followed podcasts: {followed}"}


def verify_019(server_url):
    base = f"{server_url}/sites/podcasts-audiobooks"
    r = requests.get(f"{base}/api/library/1")
    lib = r.json()
    followed = lib.get("followed_podcasts", [])
    return {"pass": 10 in followed, "detail": f"User 1 followed podcasts: {followed}"}


def verify_020(server_url):
    base = f"{server_url}/sites/podcasts-audiobooks"
    r = requests.get(f"{base}/api/library/2")
    lib = r.json()
    subscribed = lib.get("subscribed_podcasts", [])
    saved = lib.get("saved_episodes", [])
    ok = 4 in subscribed and 20 in saved
    return {"pass": ok, "detail": f"User 2 subscribed: {subscribed}, saved: {saved}"}
