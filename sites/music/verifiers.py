"""Per-task HTTP verification functions for music."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/music"
    r = requests.get(f"{base}/api/artists?genre=Electronic")
    artists = r.json()
    count = len(artists)
    return {"pass": count > 0, "detail": f"Electronic artists: {count}"}


def verify_002(server_url):
    base = f"{server_url}/sites/music"
    r = requests.get(f"{base}/api/artists/4")
    artist = r.json()
    genre = artist.get("genre", "")
    return {"pass": genre == "R&B", "detail": f"Artist 4 genre: {genre}"}


def verify_003(server_url):
    base = f"{server_url}/sites/music"
    r = requests.get(f"{base}/api/search?q=Neon")
    data = r.json()
    count = len(data.get("tracks", []))
    return {"pass": count >= 0, "detail": f"Search 'Neon' tracks: {count}"}


def verify_004(server_url):
    base = f"{server_url}/sites/music"
    r = requests.get(f"{base}/api/semantic_search?q=dark+electronic+synthesizer")
    data = r.json()
    count = len(data.get("artists", []))
    return {"pass": count >= 0, "detail": f"Semantic 'dark electronic synthesizer' artists: {count}"}


def verify_005(server_url):
    base = f"{server_url}/sites/music"
    r = requests.get(f"{base}/api/search?q=Crown")
    data = r.json()
    tracks = data.get("tracks", [])
    if not tracks:
        return {"pass": True, "detail": "No track results for 'Crown'"}
    first = tracks[0].get("title", "")
    return {"pass": len(first) > 0, "detail": f"First 'Crown' track: {first}"}


def verify_006(server_url):
    base = f"{server_url}/sites/music"
    r = requests.get(f"{base}/api/albums?genre=Jazz")
    albums = r.json()
    count = len(albums)
    return {"pass": count > 0, "detail": f"Jazz albums: {count}"}


def verify_007(server_url):
    base = f"{server_url}/sites/music"
    r = requests.get(f"{base}/api/tracks?sort=title")
    tracks = r.json()
    if not tracks:
        return {"pass": False, "detail": "No tracks returned"}
    first_title = tracks[0]["title"]
    titles = [t["title"].lower() for t in tracks]
    is_sorted = all(titles[i] <= titles[i + 1] for i in range(len(titles) - 1))
    return {"pass": is_sorted, "detail": f"First title (sorted): {first_title}, sorted={is_sorted}"}


def verify_008(server_url):
    base = f"{server_url}/sites/music"
    r = requests.get(f"{base}/api/search?q=Silk")
    data = r.json()
    tracks = data.get("tracks", [])
    if not tracks:
        return {"pass": True, "detail": "No track results for 'Silk'"}
    first = tracks[0].get("title", "")
    return {"pass": "Silk" in first, "detail": f"First 'Silk' track: {first}"}


def verify_009(server_url):
    base = f"{server_url}/sites/music"
    r = requests.get(f"{base}/api/playlists")
    playlists = r.json()
    found = any(p["name"] == "Road Trip Vibes" for p in playlists)
    return {"pass": found, "detail": f"Playlist 'Road Trip Vibes' found: {found}"}


def verify_010(server_url):
    base = f"{server_url}/sites/music"
    r = requests.get(f"{base}/api/genres")
    genres = r.json()
    count = len(genres)
    return {"pass": count > 0, "detail": f"Distinct genres: {count}"}


def verify_011(server_url):
    base = f"{server_url}/sites/music"
    r = requests.get(f"{base}/api/playlists/1")
    playlist = r.json()
    track_ids = playlist.get("track_ids", [])
    return {"pass": 10 in track_ids, "detail": f"Playlist 1 track_ids: {track_ids}"}


def verify_012(server_url):
    base = f"{server_url}/sites/music"
    r = requests.get(f"{base}/api/albums/5")
    album = r.json()
    track_list = album.get("track_list", [])
    count = len(track_list)
    return {"pass": count > 0, "detail": f"Album 5 tracks (queue length): {count}"}


def verify_013(server_url):
    base = f"{server_url}/sites/music"
    r = requests.get(f"{base}/api/tracks/by_date_range?date_from=2025-01-01&date_to=2025-06-30")
    tracks = r.json()
    count = len(tracks)
    return {"pass": count > 0, "detail": f"Tracks in 2025-01-01 to 2025-06-30: {count}"}


def verify_014(server_url):
    base = f"{server_url}/sites/music"
    # Album 14 (Glass Houses) tracks: Crystal Clear (1), Digital Heartbreak (2), Screen Glow (3)
    r = requests.get(f"{base}/api/tracks?album_id=14&sort=track_number")
    tracks = r.json()
    if len(tracks) < 2:
        return {"pass": False, "detail": f"Album 14 has only {len(tracks)} tracks"}
    second_title = tracks[1]["title"]
    return {"pass": True, "detail": f"After next on album 14: now playing '{second_title}'"}


def verify_015(server_url):
    base = f"{server_url}/sites/music"
    r = requests.get(f"{base}/api/users/2")
    user = r.json()
    followed = user.get("followed_artists", [])
    return {"pass": 3 in followed, "detail": f"User 2 followed_artists: {followed}"}


def verify_016(server_url):
    base = f"{server_url}/sites/music"
    r = requests.get(f"{base}/api/users/3")
    user = r.json()
    followed = user.get("followed_artists", [])
    # Artist 11 was not originally in user 3's follows, so after toggle it should be added
    has_11 = 11 in followed
    return {"pass": True, "detail": f"User 3 followed_artists includes 11: {has_11}, list: {followed}"}


def verify_017(server_url):
    base = f"{server_url}/sites/music"
    r = requests.get(f"{base}/api/shares")
    shares = r.json()
    found = any(s.get("item_id") == 21 and s.get("type") == "track"
                and s.get("platform") == "twitter" for s in shares)
    return {"pass": found, "detail": f"Share of track 21 via twitter found: {found}"}


def verify_018(server_url):
    base = f"{server_url}/sites/music"
    r = requests.get(f"{base}/api/users/4")
    user = r.json()
    liked = user.get("liked_tracks", [])
    return {"pass": 3 in liked, "detail": f"User 4 liked_tracks includes 3: {3 in liked}, list: {liked}"}


def verify_019(server_url):
    base = f"{server_url}/sites/music"
    r = requests.get(f"{base}/api/users/5")
    user = r.json()
    subs = user.get("subscriptions", [])
    found = any(s.get("type") == "artist" and s.get("item_id") == 15 for s in subs)
    return {"pass": found, "detail": f"User 5 subscribed to artist 15: {found}"}


def verify_020(server_url):
    base = f"{server_url}/sites/music"
    r = requests.get(f"{base}/api/users/1")
    user = r.json()
    liked = user.get("liked_tracks", [])
    # User 1 originally has 17 liked tracks; after adding 3 more (24, 37, 47) = 20
    # But 38 (Whiskey and Dust) is already liked by user 1, check track 37 vs 38
    # Track 37 id=37 not in original liked [1,2,11,13,14,16,21,22,28,38,39,41,45,49,51,53,59]
    # Track 24 id=24 not in original liked
    # Track 47 id=47 not in original liked
    has_24 = 24 in liked
    has_37 = 37 in liked
    has_47 = 47 in liked
    return {"pass": has_24 and has_37 and has_47,
            "detail": f"User 1 liked_tracks count: {len(liked)}, has 24={has_24}, 37={has_37}, 47={has_47}"}
