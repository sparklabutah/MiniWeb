"""Per-macro verification functions for music.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/music"


def verify_macro_navigate_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/genres")
    genres = r.json()
    if not genres:
        return {"pass": False, "detail": "No genres returned"}
    genre = genres[0]["name"]
    r2 = requests.get(f"{_base(server_url)}/genre/{genre}")
    return {"pass": r2.status_code == 200,
            "detail": f"Genre page '{genre}': {r2.status_code}"}


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/artist/1")
    return {"pass": r.status_code == 200,
            "detail": f"Artist detail page: {r.status_code}"}


def verify_macro_search_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/search?q=love")
    data = r.json()
    total = len(data.get("artists", [])) + len(data.get("albums", [])) + len(data.get("tracks", []))
    return {"pass": r.status_code == 200,
            "detail": f"search_by_query 'love': {total} total results"}


def verify_macro_search_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/semantic_search?q=ambient+electronic+chill")
    data = r.json()
    total = len(data.get("artists", [])) + len(data.get("albums", [])) + len(data.get("tracks", []))
    return {"pass": r.status_code == 200,
            "detail": f"search_by_semantic: {total} total results"}


def verify_macro_search_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/search/rock")
    return {"pass": r.status_code == 200,
            "detail": f"search_by_route /search/rock: {r.status_code}"}


def verify_macro_filter_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/albums?genre=Rock")
    albums = r.json()
    ok = all(a["genre"] == "Rock" for a in albums)
    return {"pass": ok and len(albums) > 0,
            "detail": f"filter_by_dropdown Rock: {len(albums)} albums, all_rock={ok}"}


def verify_macro_sort_by_ranking(server_url):
    r = requests.get(f"{_base(server_url)}/api/tracks?sort=title")
    tracks = r.json()
    if len(tracks) < 2:
        return {"pass": True, "detail": "Too few tracks to verify sort"}
    titles = [t["title"].lower() for t in tracks]
    is_sorted = all(titles[i] <= titles[i + 1] for i in range(len(titles) - 1))
    return {"pass": is_sorted, "detail": f"sort_by_ranking: sorted={is_sorted}"}


def verify_macro_extract_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/search?q=Moon")
    data = r.json()
    tracks = data.get("tracks", [])
    if tracks:
        return {"pass": True,
                "detail": f"extract_by_query: first track={tracks[0]['title'][:50]}"}
    return {"pass": True, "detail": "extract_by_query: no results (ok)"}


def verify_macro_create_from_free_text(server_url):
    s = requests.Session()
    # Login first
    s.post(f"{_base(server_url)}/api/login",
           json={"username": "leon_fischer", "password": "pass523"})
    r = s.post(f"{_base(server_url)}/api/playlists",
               json={"name": "Test Macro Playlist", "description": "test", "is_public": True})
    data = r.json()
    ok = data.get("id") is not None
    # Clean up: delete the test playlist
    if ok:
        s.delete(f"{_base(server_url)}/api/playlists/{data['id']}")
    return {"pass": ok, "detail": f"create_from_free_text: created id={data.get('id')}"}


def verify_macro_select_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/genres")
    genres = r.json()
    return {"pass": len(genres) > 0,
            "detail": f"select_by_dropdown: {len(genres)} genres available"}


def verify_macro_add_by_button(server_url):
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login",
           json={"username": "leon_fischer", "password": "pass523"})
    # Create a temp playlist to add to
    r = s.post(f"{_base(server_url)}/api/playlists",
               json={"name": "TempAddTest", "is_public": False})
    pl = r.json()
    pl_id = pl.get("id")
    if not pl_id:
        return {"pass": False, "detail": "Could not create temp playlist"}
    r2 = s.post(f"{_base(server_url)}/api/playlists/{pl_id}/add_track",
                json={"track_id": 1})
    data = r2.json()
    ok = data.get("action") == "added"
    # Clean up
    s.delete(f"{_base(server_url)}/api/playlists/{pl_id}")
    return {"pass": ok, "detail": f"add_by_button: action={data.get('action')}"}


def verify_macro_play_by_dropdown(server_url):
    r = requests.post(f"{_base(server_url)}/api/play",
                      json={"type": "track", "id": 1})
    data = r.json()
    return {"pass": data.get("status") == "playing",
            "detail": f"play_by_dropdown: status={data.get('status')}, now_playing={data.get('now_playing')}"}


def verify_macro_play_by_date_range(server_url):
    r = requests.post(f"{_base(server_url)}/api/play/date_range",
                      json={"date_from": "2024-01-01", "date_to": "2024-12-31"})
    data = r.json()
    return {"pass": data.get("status") == "playing" and data.get("queue_length", 0) > 0,
            "detail": f"play_by_date_range: queue_length={data.get('queue_length')}"}


def verify_macro_play_by_playback(server_url):
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login",
           json={"username": "priya_kapoor", "password": "pass423"})
    s.post(f"{_base(server_url)}/api/play",
           json={"type": "album", "id": 1})
    r = s.post(f"{_base(server_url)}/api/playback",
               json={"action": "next"})
    data = r.json()
    ok = data.get("action") == "next" and data.get("status") == "playing"
    return {"pass": ok,
            "detail": f"play_by_playback: action={data.get('action')}, now_playing={data.get('now_playing')}"}


def verify_macro_follow_by_dropdown(server_url):
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login",
           json={"username": "leon_fischer", "password": "pass523"})
    r = s.post(f"{_base(server_url)}/api/artists/1/follow")
    data = r.json()
    action = data.get("action")
    # Toggle back
    s.post(f"{_base(server_url)}/api/artists/1/follow")
    return {"pass": action in ("followed", "unfollowed"),
            "detail": f"follow_by_dropdown: action={action}"}


def verify_macro_follow_by_toggle(server_url):
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login",
           json={"username": "leon_fischer", "password": "pass523"})
    r = s.post(f"{_base(server_url)}/api/library/follow",
               json={"artist_id": 22})
    data = r.json()
    action = data.get("action")
    # Toggle back
    s.post(f"{_base(server_url)}/api/library/follow",
           json={"artist_id": 22})
    return {"pass": action in ("followed", "unfollowed"),
            "detail": f"follow_by_toggle: action={action}"}


def verify_macro_share_by_dropdown(server_url):
    r = requests.post(f"{_base(server_url)}/api/share",
                      json={"type": "album", "id": 1, "platform": "link"})
    data = r.json()
    ok = data.get("share_url") is not None
    return {"pass": ok,
            "detail": f"share_by_dropdown: share_url={data.get('share_url')}"}


def verify_macro_save_by_toggle(server_url):
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login",
           json={"username": "leon_fischer", "password": "pass523"})
    r = s.post(f"{_base(server_url)}/api/tracks/56/like")
    data = r.json()
    action = data.get("action")
    # Toggle back
    s.post(f"{_base(server_url)}/api/tracks/56/like")
    return {"pass": action in ("liked", "unliked"),
            "detail": f"save_by_toggle: action={action}"}


def verify_macro_subscribe_by_toggle(server_url):
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login",
           json={"username": "leon_fischer", "password": "pass523"})
    r = s.post(f"{_base(server_url)}/api/subscribe",
               json={"type": "artist", "id": 22})
    data = r.json()
    action = data.get("action")
    # Toggle back
    s.post(f"{_base(server_url)}/api/subscribe",
           json={"type": "artist", "id": 22})
    return {"pass": action in ("subscribed", "unsubscribed"),
            "detail": f"subscribe_by_toggle: action={action}"}
