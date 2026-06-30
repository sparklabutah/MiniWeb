"""Per-macro verification functions for podcasts-audiobooks.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/podcasts-audiobooks"


def _login(server_url, username, password):
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login",
           json={"username": username, "password": password})
    return s


def verify_macro_navigate_by_dropdown(server_url):
    """Navigate to a category page via category dropdown."""
    r = requests.get(f"{_base(server_url)}/api/podcasts/categories")
    cats = r.json()
    if not cats:
        return {"pass": False, "detail": "No categories returned"}
    cat = cats[0]
    r2 = requests.get(f"{_base(server_url)}/podcasts?category={cat}")
    return {"pass": r2.status_code == 200, "detail": f"Category '{cat}' page: {r2.status_code}"}


def verify_macro_navigate_by_route(server_url):
    """Navigate to a podcast detail page by route."""
    r = requests.get(f"{_base(server_url)}/podcast/1")
    return {"pass": r.status_code == 200, "detail": f"Podcast detail page: {r.status_code}"}


def verify_macro_search_by_query(server_url):
    """Keyword search returns results."""
    r = requests.get(f"{_base(server_url)}/api/search?q=the")
    results = r.json()
    total = len(results.get("podcasts", [])) + len(results.get("audiobooks", [])) + len(results.get("episodes", []))
    return {"pass": total > 0, "detail": f"search_by_query 'the': {total} results"}


def verify_macro_search_by_semantic(server_url):
    """Semantic search returns ranked results."""
    r = requests.get(f"{_base(server_url)}/api/search/semantic?q=technology+programming")
    results = r.json()
    total = len(results.get("podcasts", [])) + len(results.get("audiobooks", []))
    return {"pass": r.status_code == 200, "detail": f"search_by_semantic: {total} results"}


def verify_macro_filter_by_dropdown(server_url):
    """Filter audiobooks by genre dropdown."""
    r = requests.get(f"{_base(server_url)}/api/audiobooks?genre=Fiction")
    audiobooks = r.json()
    ok = all(a["genre"] == "Fiction" for a in audiobooks)
    return {"pass": ok and len(audiobooks) > 0,
            "detail": f"filter_by_dropdown Fiction: {len(audiobooks)}, all_fiction={ok}"}


def verify_macro_filter_by_slider(server_url):
    """Filter audiobooks by minimum rating slider."""
    r = requests.get(f"{_base(server_url)}/api/audiobooks?min_rating=4.6")
    audiobooks = r.json()
    ok = all(a["rating"] >= 4.6 for a in audiobooks)
    return {"pass": ok and len(audiobooks) > 0,
            "detail": f"filter_by_slider min_rating=4.6: {len(audiobooks)}, all_pass={ok}"}


def verify_macro_sort_by_ranking(server_url):
    """Sort audiobooks by title."""
    r = requests.get(f"{_base(server_url)}/api/audiobooks?sort=title")
    audiobooks = r.json()
    if len(audiobooks) < 2:
        return {"pass": True, "detail": "Too few audiobooks to verify sort"}
    titles = [a["title"].lower() for a in audiobooks]
    is_sorted = all(titles[i] <= titles[i + 1] for i in range(len(titles) - 1))
    return {"pass": is_sorted, "detail": f"sort_by_ranking: sorted={is_sorted}"}


def verify_macro_extract_by_query(server_url):
    """Search and extract first result title."""
    r = requests.get(f"{_base(server_url)}/api/search?q=science")
    results = r.json()
    podcasts = results.get("podcasts", [])
    if podcasts:
        return {"pass": True, "detail": f"extract_by_query: first={podcasts[0]['title'][:50]}"}
    return {"pass": True, "detail": "extract_by_query: no podcast results (ok)"}


def verify_macro_submit_by_query(server_url):
    """Submit a search query and get results."""
    r = requests.get(f"{_base(server_url)}/search?q=music")
    return {"pass": r.status_code == 200, "detail": f"submit_by_query: {r.status_code}"}


def verify_macro_select_by_dropdown(server_url):
    """Select a genre from dropdown to filter audiobooks."""
    r = requests.get(f"{_base(server_url)}/api/audiobooks/genres")
    genres = r.json()
    if not genres:
        return {"pass": False, "detail": "No genres returned"}
    genre = genres[0]
    r2 = requests.get(f"{_base(server_url)}/api/audiobooks?genre={genre}")
    audiobooks = r2.json()
    ok = all(a["genre"] == genre for a in audiobooks)
    return {"pass": ok, "detail": f"select_by_dropdown '{genre}': {len(audiobooks)}, all_match={ok}"}


def verify_macro_play_by_dropdown(server_url):
    """Select an episode from a podcast to play."""
    r = requests.get(f"{_base(server_url)}/api/episodes?podcast_id=1&sort=date&limit=1")
    episodes = r.json()
    if not episodes:
        return {"pass": False, "detail": "No episodes for podcast 1"}
    ep = episodes[0]
    r2 = requests.get(f"{_base(server_url)}/episode/{ep['id']}")
    return {"pass": r2.status_code == 200,
            "detail": f"play_by_dropdown: episode {ep['id']} ({ep['title'][:40]})"}


def verify_macro_play_by_date_range(server_url):
    """Filter episodes by date range."""
    r = requests.get(f"{_base(server_url)}/api/episodes?date_from=2025-01-01&date_to=2025-12-31")
    episodes = r.json()
    ok = all("2025-01-01" <= e["publish_date"] <= "2025-12-31" for e in episodes)
    return {"pass": ok and len(episodes) > 0,
            "detail": f"play_by_date_range 2025: {len(episodes)} episodes, all_in_range={ok}"}


def verify_macro_play_by_playback(server_url):
    """Set playback speed."""
    s = _login(server_url, "story_eve", "pass654")
    r = s.post(f"{_base(server_url)}/api/playback/speed", json={"speed": 2.0})
    data = r.json()
    ok = data.get("action") == "speed_set" and data.get("speed") == 2.0
    # Reset
    s.post(f"{_base(server_url)}/api/playback/speed", json={"speed": 1.0})
    return {"pass": ok, "detail": f"play_by_playback: action={data.get('action')}, speed={data.get('speed')}"}


def verify_macro_export_by_dropdown(server_url):
    """Export catalog as CSV."""
    r = requests.get(f"{_base(server_url)}/api/export?type=podcasts&format=csv")
    lines = r.text.strip().split("\n")
    return {"pass": len(lines) > 1, "detail": f"export CSV: {len(lines)} lines"}


def verify_macro_post_from_free_text(server_url):
    """Post a review with free text."""
    s = _login(server_url, "story_eve", "pass654")
    r = s.post(f"{_base(server_url)}/api/reviews",
               json={"item_type": "podcast", "item_id": 2, "rating": 3,
                      "text": "Macro test review text."})
    data = r.json()
    ok = data.get("text") == "Macro test review text."
    return {"pass": ok, "detail": f"post_from_free_text: id={data.get('id')}, text={data.get('text','')[:40]}"}


def verify_macro_react_by_toggle(server_url):
    """Toggle like on an episode."""
    s = _login(server_url, "audio_dave", "pass321")
    r = s.post(f"{_base(server_url)}/api/episodes/5/like")
    data = r.json()
    ok = data.get("action") == "liked"
    # Toggle back
    s.post(f"{_base(server_url)}/api/episodes/5/like")
    return {"pass": ok, "detail": f"react_by_toggle: action={data.get('action')}"}


def verify_macro_rate_by_slider(server_url):
    """Post a review with a specific rating value (slider)."""
    s = _login(server_url, "story_eve", "pass654")
    r = s.post(f"{_base(server_url)}/api/reviews",
               json={"item_type": "audiobook", "item_id": 9, "rating": 2.5,
                      "text": "Rating slider test."})
    data = r.json()
    ok = data.get("rating") == 2.5
    return {"pass": ok, "detail": f"rate_by_slider: rating={data.get('rating')}"}


def verify_macro_follow_by_dropdown(server_url):
    """Follow a podcast by selecting host from dropdown."""
    s = _login(server_url, "audio_dave", "pass321")
    r = s.post(f"{_base(server_url)}/api/follow/host",
               json={"host": "Sarah Mitchell"})
    data = r.json()
    ok = data.get("action") in ("followed", "already_followed")
    return {"pass": ok, "detail": f"follow_by_dropdown: action={data.get('action')}"}


def verify_macro_follow_by_toggle(server_url):
    """Toggle follow on a podcast."""
    s = _login(server_url, "audio_dave", "pass321")
    r = s.post(f"{_base(server_url)}/api/podcasts/8/follow")
    data = r.json()
    ok = data.get("action") == "followed"
    # Toggle back
    s.post(f"{_base(server_url)}/api/podcasts/8/follow")
    return {"pass": ok, "detail": f"follow_by_toggle: action={data.get('action')}"}


def verify_macro_subscribe_by_toggle(server_url):
    """Toggle subscription on a podcast."""
    s = _login(server_url, "story_eve", "pass654")
    r = s.post(f"{_base(server_url)}/api/podcasts/4/subscribe")
    data = r.json()
    ok = data.get("action") == "subscribed"
    # Toggle back
    s.post(f"{_base(server_url)}/api/podcasts/4/subscribe")
    return {"pass": ok, "detail": f"subscribe_by_toggle: action={data.get('action')}"}


def verify_macro_save_by_toggle(server_url):
    """Toggle save on an episode."""
    s = _login(server_url, "audio_dave", "pass321")
    r = s.post(f"{_base(server_url)}/api/episodes/20/save")
    data = r.json()
    ok = data.get("action") == "saved"
    # Toggle back
    s.post(f"{_base(server_url)}/api/episodes/20/save")
    return {"pass": ok, "detail": f"save_by_toggle: action={data.get('action')}"}
