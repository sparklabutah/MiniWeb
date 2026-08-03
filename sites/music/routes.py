"""SoundWave Music — Spotify-style music streaming platform.

Browse artists, albums, and tracks. Create and manage playlists.
Build a personal library of liked songs and followed artists.
Data is stored in SQLite: raw MusicBrainz data in the raw_data table,
overlay and mutable data in per-site typed tables.  Queried through app.db.
"""
import hashlib
import json
import logging
import pathlib
from collections import Counter
from datetime import datetime

from flask import Blueprint, abort, jsonify, redirect, render_template, request, session, url_for

from app import db

# Simple TF-IDF-like scoring for semantic search
import math
import re
from app.events import emit

logger = logging.getLogger(__name__)

SITE = "music"
SITE_DIR = pathlib.Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Raw data loading — now uses per-site tables (music_artists, etc.)
# ---------------------------------------------------------------------------


def _load_raw_artists_db() -> list:
    return db.query(SITE, "artists")


def _load_raw_albums_db() -> list:
    return db.query(SITE, "albums")


def _load_raw_tracks_db() -> list:
    return db.query(SITE, "tracks")

# Overlay IDs start at this offset to avoid collisions with raw data IDs
OVERLAY_ID_OFFSET = 9_000_000

blueprint = Blueprint(
    "music",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Module-level cache — loaded once at import time
# ---------------------------------------------------------------------------
_RAW_ARTISTS: list = []
_RAW_ALBUMS: list = []
_RAW_TRACKS: list = []
_RAW_DATA_LOADED: bool = False


def _color_from_title(title: str) -> str:
    """Generate a deterministic hex color from a string (album title)."""
    h = hashlib.md5(title.encode("utf-8")).hexdigest()
    return "#" + h[:6]


def _best_genre(genres: list, tags: list) -> str:
    """Pick the most-voted genre name from MusicBrainz genres/tags lists."""
    candidates = []
    for g in (genres or []):
        candidates.append((g.get("count", 0), g.get("name", "")))
    if not candidates:
        for t in (tags or []):
            candidates.append((t.get("count", 0), t.get("name", "")))
    if not candidates:
        return "Other"
    candidates.sort(key=lambda x: -x[0])
    name = candidates[0][1]
    # Title-case for display
    return name.title() if name else "Other"


def _make_bio(raw_artist: dict) -> str:
    """Compose a short bio from MusicBrainz artist metadata."""
    parts = []
    atype = raw_artist.get("type") or "Artist"
    country = raw_artist.get("country") or ""
    area_name = ""
    area = raw_artist.get("area")
    if area:
        area_name = area.get("name", "")

    # Opening
    if atype == "Person":
        if area_name and country:
            parts.append(f"Solo artist from {area_name} ({country}).")
        elif country:
            parts.append(f"Solo artist from {country}.")
        else:
            parts.append("Solo artist.")
    elif atype == "Group":
        if area_name and country:
            parts.append(f"Musical group from {area_name} ({country}).")
        elif country:
            parts.append(f"Musical group from {country}.")
        else:
            parts.append("Musical group.")
    else:
        parts.append(f"{atype}." if atype else "Artist.")

    # Genre summary
    genres = raw_artist.get("genres", [])
    top_genres = sorted(genres, key=lambda g: -g.get("count", 0))[:3]
    genre_names = [g["name"].title() for g in top_genres if g.get("name")]
    if genre_names:
        parts.append("Known for " + ", ".join(genre_names) + ".")

    # Life span
    lifespan = raw_artist.get("life-span", {})
    begin = lifespan.get("begin", "")
    if begin:
        parts.append(f"Active since {begin[:4]}.")
        if lifespan.get("ended") and lifespan.get("end"):
            parts[-1] = f"Active {begin[:4]}–{lifespan['end'][:4]}."

    disambiguation = raw_artist.get("disambiguation", "")
    if disambiguation:
        parts.append(disambiguation.capitalize() + ".")

    return " ".join(parts)


def _parse_release_date(date_str: str) -> str:
    """Normalize a MusicBrainz date (YYYY, YYYY-MM, YYYY-MM-DD, '') to YYYY-MM-DD."""
    if not date_str:
        return "2000-01-01"
    date_str = date_str.strip()
    if len(date_str) == 4:
        return f"{date_str}-01-01"
    if len(date_str) == 7:
        return f"{date_str}-01"
    if len(date_str) >= 10:
        return date_str[:10]
    return "2000-01-01"


def _init_raw_data():
    """Load raw MusicBrainz data from SQLite raw_data table into module-level caches."""
    global _RAW_ARTISTS, _RAW_ALBUMS, _RAW_TRACKS, _RAW_DATA_LOADED
    if _RAW_DATA_LOADED:
        return

    logger.info("Loading MusicBrainz data from SQLite raw_data table...")
    try:
        _RAW_ARTISTS = _load_raw_artists_db()
        _RAW_ALBUMS = _load_raw_albums_db()
        _RAW_TRACKS = _load_raw_tracks_db()
    except Exception:
        logger.exception("Failed to load raw MusicBrainz data from DB")
        _RAW_ARTISTS = []
        _RAW_ALBUMS = []
        _RAW_TRACKS = []

    _RAW_DATA_LOADED = True
    logger.info("Loaded %d artists, %d albums, %d tracks from DB",
                len(_RAW_ARTISTS), len(_RAW_ALBUMS), len(_RAW_TRACKS))


# ---------------------------------------------------------------------------
# Data access helpers
# ---------------------------------------------------------------------------

def _load(name):
    return db.query(SITE, name)


def _save(name, data):
    db.save_collection(SITE, name, data)


def _merge_overlay(raw_list: list, overlay_list: list) -> list:
    """Merge overlay entries onto raw data.

    Overlay entries get IDs shifted by OVERLAY_ID_OFFSET. If there's an ID
    collision (unlikely given the offset), overlay wins.
    """
    # Shift overlay IDs
    shifted = []
    for entry in overlay_list:
        e = dict(entry)
        e["id"] = e["id"] + OVERLAY_ID_OFFSET
        # Shift foreign-key references too
        if "artist_id" in e:
            e["artist_id"] = e["artist_id"] + OVERLAY_ID_OFFSET
        if "album_id" in e:
            e["album_id"] = e["album_id"] + OVERLAY_ID_OFFSET
        shifted.append(e)

    # Combine: raw first, then overlay
    raw_ids = {item["id"] for item in raw_list}
    combined = list(raw_list)
    for entry in shifted:
        if entry["id"] not in raw_ids:
            combined.append(entry)
        else:
            # Overlay wins on collision
            combined = [item for item in combined if item["id"] != entry["id"]]
            combined.append(entry)
    return combined


def _load_artists():
    _init_raw_data()
    overlay = _load("artists")
    return _merge_overlay(_RAW_ARTISTS, overlay)

def _load_albums():
    _init_raw_data()
    overlay = _load("albums")
    return _merge_overlay(_RAW_ALBUMS, overlay)

def _load_tracks():
    _init_raw_data()
    overlay = _load("tracks")
    return _merge_overlay(_RAW_TRACKS, overlay)


def _save_tracks(tracks):
    """Save only overlay-originated tracks back to the overlay file.

    Raw MusicBrainz tracks (IDs < OVERLAY_ID_OFFSET) are never persisted.
    Overlay tracks have IDs >= OVERLAY_ID_OFFSET; un-shift them for storage.
    """
    overlay_tracks = []
    for t in tracks:
        if t["id"] >= OVERLAY_ID_OFFSET:
            tc = dict(t)
            tc["id"] = tc["id"] - OVERLAY_ID_OFFSET
            if tc.get("artist_id", 0) >= OVERLAY_ID_OFFSET:
                tc["artist_id"] = tc["artist_id"] - OVERLAY_ID_OFFSET
            if tc.get("album_id", 0) >= OVERLAY_ID_OFFSET:
                tc["album_id"] = tc["album_id"] - OVERLAY_ID_OFFSET
            overlay_tracks.append(tc)
    _save("tracks", overlay_tracks)

def _shift_id(entity_id: int) -> int:
    """Shift an overlay-era ID to the offset range. Already-shifted IDs pass through."""
    if entity_id >= OVERLAY_ID_OFFSET:
        return entity_id  # already shifted
    if _RAW_DATA_LOADED and _RAW_ARTISTS:
        return entity_id + OVERLAY_ID_OFFSET
    return entity_id  # no raw data loaded, IDs stay as-is


def _unshift_id(entity_id: int) -> int:
    """Reverse a shifted ID back to its original overlay value for storage."""
    if entity_id >= OVERLAY_ID_OFFSET:
        return entity_id - OVERLAY_ID_OFFSET
    return entity_id


def _load_playlists():
    playlists = _load("playlists")
    if _RAW_DATA_LOADED and _RAW_ARTISTS:
        # Shift track_ids so they reference overlay-shifted track IDs
        for p in playlists:
            p["track_ids"] = [_shift_id(tid) for tid in p.get("track_ids", [])]
    return playlists


def _save_playlists(playlists):
    """Save playlists, un-shifting overlay IDs back to original values."""
    to_save = []
    for p in playlists:
        pc = dict(p)
        pc["track_ids"] = [_unshift_id(tid) for tid in pc.get("track_ids", [])]
        to_save.append(pc)
    _save("playlists", to_save)


def _load_library():
    libs = _load("library")
    if _RAW_DATA_LOADED and _RAW_ARTISTS:
        # Shift ID references so they point to overlay-shifted entities
        for lib in libs:
            lib["liked_tracks"] = [_shift_id(tid)
                                   for tid in lib.get("liked_tracks", [])]
            lib["liked_albums"] = [_shift_id(aid)
                                   for aid in lib.get("liked_albums", [])]
            lib["followed_artists"] = [_shift_id(aid)
                                       for aid in lib.get("followed_artists", [])]
    return libs


def _save_library(libs):
    """Save library, un-shifting overlay IDs back to original values."""
    to_save = []
    for lib in libs:
        lc = dict(lib)
        lc["liked_tracks"] = [_unshift_id(tid)
                              for tid in lc.get("liked_tracks", [])]
        lc["liked_albums"] = [_unshift_id(aid)
                              for aid in lc.get("liked_albums", [])]
        lc["followed_artists"] = [_unshift_id(aid)
                                  for aid in lc.get("followed_artists", [])]
        to_save.append(lc)
    _save("library", to_save)


def _load_users():
    return db.query(SITE, "users")


def _get_user(user_id):
    return db.get_item(SITE, "users", user_id)


def _get_library(user_id):
    libs = _load_library()
    lib = next((l for l in libs if l["user_id"] == user_id), None)
    if lib is None:
        lib = {"id": len(libs) + 1, "user_id": user_id, "liked_tracks": [], "liked_albums": [], "followed_artists": []}
        libs.append(lib)
        _save_library(libs)
    return lib


def _format_duration(seconds):
    m, s = divmod(seconds, 60)
    return f"{m}:{s:02d}"


def _format_plays(plays):
    if plays >= 1_000_000:
        return f"{plays / 1_000_000:.1f}M"
    if plays >= 1_000:
        return f"{plays / 1_000:.0f}K"
    return str(plays)


def _enrich_track(track, artists, albums):
    """Add artist name, album title, formatted duration to a track dict."""
    t = dict(track)
    artist = next((a for a in artists if a["id"] == t["artist_id"]), None)
    album = next((a for a in albums if a["id"] == t["album_id"]), None)
    t["artist_name"] = artist["name"] if artist else "Unknown"
    t["album_title"] = album["title"] if album else "Unknown"
    t["album_cover_color"] = album["cover_color"] if album else "#666"
    t["duration_formatted"] = _format_duration(t["duration_seconds"])
    t["plays_formatted"] = _format_plays(t["plays"])
    return t


def _enrich_album(album, artists, tracks):
    """Add artist name and track list to an album dict."""
    a = dict(album)
    artist = next((ar for ar in artists if ar["id"] == a["artist_id"]), None)
    a["artist_name"] = artist["name"] if artist else "Unknown"
    a["track_list"] = [t for t in tracks if t["album_id"] == a["id"]]
    a["track_list"].sort(key=lambda t: t["track_number"])
    return a


# ---------------------------------------------------------------------------
# Subscription / playback / share helpers
# ---------------------------------------------------------------------------

def _load_subscriptions():
    return _load("subscriptions")

def _load_shares():
    return _load("shares")

def _load_playback():
    return _load("playback")


# ---------------------------------------------------------------------------
# Search helper
# ---------------------------------------------------------------------------

def _search_all(query, artists, albums, tracks):
    q = query.lower().strip()
    if not q:
        return {"artists": [], "albums": [], "tracks": []}
    matched_artists = [a for a in artists if q in a["name"].lower() or q in a["genre"].lower()]
    matched_albums = [a for a in albums if q in a["title"].lower() or q in a["genre"].lower()]
    matched_tracks = [t for t in tracks if q in t["title"].lower()]
    return {"artists": matched_artists, "albums": matched_albums, "tracks": matched_tracks}


# ---------------------------------------------------------------------------
# Semantic search helper (lightweight keyword overlap scoring)
# ---------------------------------------------------------------------------

def _tokenize(text):
    return re.findall(r'[a-z0-9]+', text.lower())


def _semantic_search(query, artists, albums, tracks, limit=20):
    """Score items by keyword overlap with query across all text fields."""
    q_tokens = set(_tokenize(query))
    if not q_tokens:
        return {"artists": [], "albums": [], "tracks": []}

    def _score(text):
        tokens = set(_tokenize(text))
        if not tokens:
            return 0.0
        overlap = len(q_tokens & tokens)
        return overlap / math.sqrt(len(q_tokens)) / math.sqrt(len(tokens))

    scored_artists = []
    for a in artists:
        s = _score(f"{a['name']} {a['genre']} {a['bio']}")
        if s > 0:
            scored_artists.append((s, a))
    scored_artists.sort(key=lambda x: -x[0])

    scored_albums = []
    for a in albums:
        s = _score(f"{a['title']} {a['genre']}")
        if s > 0:
            scored_albums.append((s, a))
    scored_albums.sort(key=lambda x: -x[0])

    scored_tracks = []
    for t in tracks:
        s = _score(t["title"])
        if s > 0:
            scored_tracks.append((s, t))
    scored_tracks.sort(key=lambda x: -x[0])

    return {
        "artists": [x[1] for x in scored_artists[:limit]],
        "albums": [x[1] for x in scored_albums[:limit]],
        "tracks": [x[1] for x in scored_tracks[:limit]],
    }


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.context_processor
def _inject_shell():
    """Sidebar playlists + current user for the shared Spotify-style shell."""
    try:
        if "/api/" in request.path:
            return {}
        uid = session.get("user_id")
        user = _get_user(uid) if uid else None
        pls = [p for p in _load_playlists() if p.get("user_id") == uid] if uid else []
        return {"music_user": user, "sidebar_playlists": pls[:40]}
    except Exception:
        return {"music_user": None, "sidebar_playlists": []}


@blueprint.route("/")
def index():
    artists = _load_artists()
    albums = _load_albums()
    tracks = _load_tracks()

    # Featured: top artists by listeners
    featured_artists = sorted(artists, key=lambda a: -a["monthly_listeners"])[:6]
    # New releases: most recent albums
    new_releases = sorted(albums, key=lambda a: a["release_date"], reverse=True)[:6]
    # Popular tracks
    enriched = [_enrich_track(t, artists, albums) for t in tracks]
    popular_tracks = sorted(enriched, key=lambda t: -t["plays"])[:10]

    # All genres for quick links
    genres = sorted(set(a["genre"] for a in artists))

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template("music/index.html",
                           featured_artists=featured_artists,
                           new_releases=new_releases,
                           popular_tracks=popular_tracks,
                           genres=genres,
                           user=user)


@blueprint.route("/browse")
def browse():
    artists = _load_artists()
    albums = _load_albums()
    genre = request.args.get("genre", "").strip()
    sort = request.args.get("sort", "release_date").strip()

    genres = sorted(set(a["genre"] for a in artists))

    filtered_albums = albums
    filtered_artists = artists
    if genre:
        filtered_albums = [a for a in albums if a["genre"] == genre]
        filtered_artists = [a for a in artists if a["genre"] == genre]

    # Sort albums
    if sort == "title":
        filtered_albums = sorted(filtered_albums, key=lambda a: a["title"].lower())
    elif sort == "listeners":
        # Sort by artist monthly listeners
        artist_map = {a["id"]: a["monthly_listeners"] for a in artists}
        filtered_albums = sorted(filtered_albums,
                                 key=lambda a: -artist_map.get(a["artist_id"], 0))
    else:
        filtered_albums = sorted(filtered_albums, key=lambda a: a["release_date"], reverse=True)

    # Sort artists
    if sort == "listeners":
        filtered_artists = sorted(filtered_artists, key=lambda a: -a["monthly_listeners"])
    elif sort == "title":
        filtered_artists = sorted(filtered_artists, key=lambda a: a["name"].lower())

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template("music/browse.html",
                           albums=filtered_albums,
                           artists=filtered_artists,
                           genres=genres,
                           selected_genre=genre,
                           user=user)


@blueprint.route("/artist/<int:artist_id>")
def artist_detail(artist_id):
    artists = _load_artists()
    artist = next((a for a in artists if a["id"] == artist_id), None)
    if not artist:
        abort(404)
    albums = _load_albums()
    tracks = _load_tracks()
    artist_albums = sorted(
        [_enrich_album(a, artists, tracks) for a in albums if a["artist_id"] == artist_id],
        key=lambda a: a["release_date"], reverse=True
    )
    artist_tracks = sorted(
        [_enrich_track(t, artists, albums) for t in tracks if t["artist_id"] == artist_id],
        key=lambda t: -t["plays"]
    )

    user = None
    is_following = False
    is_subscribed = False
    if "user_id" in session:
        user = _get_user(session["user_id"])
        lib = _get_library(session["user_id"])
        is_following = artist_id in lib.get("followed_artists", [])
        subs = _load_subscriptions()
        is_subscribed = any(s["user_id"] == session["user_id"] and s["type"] == "artist"
                           and s["item_id"] == artist_id for s in subs)

    return render_template("music/artist.html",
                           artist=artist,
                           albums=artist_albums,
                           tracks=artist_tracks,
                           is_following=is_following,
                           is_subscribed=is_subscribed,
                           user=user)


@blueprint.route("/album/<int:album_id>")
def album_detail(album_id):
    albums = _load_albums()
    album = next((a for a in albums if a["id"] == album_id), None)
    if not album:
        abort(404)
    artists = _load_artists()
    tracks = _load_tracks()

    enriched = _enrich_album(album, artists, tracks)
    enriched_tracks = [_enrich_track(t, artists, albums) for t in enriched["track_list"]]
    total_duration = sum(t["duration_seconds"] for t in enriched["track_list"])

    artist = next((a for a in artists if a["id"] == album["artist_id"]), None)

    user = None
    is_liked = False
    if "user_id" in session:
        user = _get_user(session["user_id"])
        lib = _get_library(session["user_id"])
        is_liked = album_id in lib.get("liked_albums", [])

    return render_template("music/album.html",
                           album=enriched,
                           artist=artist,
                           tracks=enriched_tracks,
                           total_duration=_format_duration(total_duration),
                           is_liked=is_liked,
                           user=user)


@blueprint.route("/track/<int:track_id>")
def track_detail(track_id):
    tracks = _load_tracks()
    track = next((t for t in tracks if t["id"] == track_id), None)
    if not track:
        abort(404)
    artists = _load_artists()
    albums = _load_albums()

    enriched = _enrich_track(track, artists, albums)
    artist = next((a for a in artists if a["id"] == track["artist_id"]), None)
    album = next((a for a in albums if a["id"] == track["album_id"]), None)

    # Other tracks from same album
    album_tracks = [_enrich_track(t, artists, albums) for t in tracks
                    if t["album_id"] == track["album_id"] and t["id"] != track_id]
    album_tracks.sort(key=lambda t: t["track_number"])

    user = None
    is_liked = False
    if "user_id" in session:
        user = _get_user(session["user_id"])
        lib = _get_library(session["user_id"])
        is_liked = track_id in lib.get("liked_tracks", [])

    # User's own playlists for "Add to Playlist" dropdown
    user_playlists = []
    uid = session.get("user_id")
    if uid:
        all_playlists = _load_playlists()
        user_playlists = [p for p in all_playlists if p["user_id"] == uid]

    return render_template("music/track.html",
                           track=enriched,
                           artist=artist,
                           album=album,
                           album_tracks=album_tracks,
                           is_liked=is_liked,
                           user=user,
                           playlists=user_playlists)


@blueprint.route("/playlists")
def playlists_page():
    playlists = _load_playlists()
    users = _load_users()
    tracks = _load_tracks()

    user = None
    user_id = session.get("user_id")
    if user_id:
        user = _get_user(user_id)

    # Show public playlists + user's own playlists
    visible = [p for p in playlists if p["is_public"] or (user_id and p["user_id"] == user_id)]

    # Enrich with owner name and track count
    for p in visible:
        owner = next((u for u in users if u["id"] == p["user_id"]), None)
        p["owner_name"] = owner["display_name"] if owner else "Unknown"
        p["total_tracks"] = len(p.get("track_ids", []))

    return render_template("music/playlists.html", playlists=visible, user=user)


@blueprint.route("/playlist/<int:playlist_id>")
def playlist_detail(playlist_id):
    playlists = _load_playlists()
    playlist = next((p for p in playlists if p["id"] == playlist_id), None)
    if not playlist:
        abort(404)

    user_id = session.get("user_id")
    if not playlist["is_public"] and (not user_id or playlist["user_id"] != user_id):
        abort(404)

    artists = _load_artists()
    albums = _load_albums()
    tracks = _load_tracks()
    users = _load_users()

    owner = next((u for u in users if u["id"] == playlist["user_id"]), None)
    playlist_tracks = []
    for tid in playlist.get("track_ids", []):
        t = next((t for t in tracks if t["id"] == tid), None)
        if t:
            playlist_tracks.append(_enrich_track(t, artists, albums))

    total_duration = sum(t["duration_seconds"] for t in playlist_tracks)
    is_owner = user_id and playlist["user_id"] == user_id

    user = None
    if user_id:
        user = _get_user(user_id)

    return render_template("music/playlist.html",
                           playlist=playlist,
                           owner=owner,
                           tracks=playlist_tracks,
                           total_duration=_format_duration(total_duration),
                           is_owner=is_owner,
                           user=user)


@blueprint.route("/library")
def library_page():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("music.login_page"))

    user = _get_user(user_id)
    lib = _get_library(user_id)
    artists = _load_artists()
    albums = _load_albums()
    tracks = _load_tracks()

    liked_tracks = [_enrich_track(t, artists, albums) for t in tracks if t["id"] in lib.get("liked_tracks", [])]
    liked_albums_list = [_enrich_album(a, artists, tracks) for a in albums if a["id"] in lib.get("liked_albums", [])]
    followed_artists = [a for a in artists if a["id"] in lib.get("followed_artists", [])]

    tab = request.args.get("tab", "tracks")

    return render_template("music/library.html",
                           user=user,
                           liked_tracks=liked_tracks,
                           liked_albums=liked_albums_list,
                           followed_artists=followed_artists,
                           tab=tab)


@blueprint.route("/search")
def search_page():
    q = request.args.get("q", "").strip()
    artists = _load_artists()
    albums = _load_albums()
    tracks = _load_tracks()

    results = _search_all(q, artists, albums, tracks)
    enriched_tracks = [_enrich_track(t, artists, albums) for t in results["tracks"]]
    enriched_albums = [_enrich_album(a, artists, tracks) for a in results["albums"]]

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template("music/search.html",
                           q=q,
                           artists=results["artists"],
                           albums=enriched_albums,
                           tracks=enriched_tracks,
                           user=user)


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("music/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return render_template("music/login.html", error="Invalid username or password")
    session["user_id"] = user["id"]
    emit("signup", user_id=user["id"], site_name="music", username=request.form.get("username", ""), password=request.form.get("password", ""), email="")
    return redirect(url_for("music.index"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("music.index"))


# ---------------------------------------------------------------------------
# API routes — READ
# ---------------------------------------------------------------------------

@blueprint.route("/api/artists")
def api_artists():
    artists = _load_artists()
    q = request.args.get("q", "").strip().lower()
    genre = request.args.get("genre", "").strip()
    verified = request.args.get("verified", "").strip()
    sort = request.args.get("sort", "name").strip()

    results = list(artists)
    if q:
        results = [a for a in results if q in a["name"].lower() or q in a["genre"].lower() or q in a["bio"].lower()]
    if genre:
        results = [a for a in results if a["genre"] == genre]
    if verified:
        v = verified.lower() == "true"
        results = [a for a in results if a["verified"] == v]
    if sort == "listeners":
        results.sort(key=lambda a: -a["monthly_listeners"])
    elif sort == "name":
        results.sort(key=lambda a: a["name"].lower())

    return jsonify(results)


@blueprint.route("/api/artists/<int:artist_id>")
def api_artist(artist_id):
    artists = _load_artists()
    artist = next((a for a in artists if a["id"] == artist_id), None)
    if not artist:
        abort(404)
    return jsonify(artist)


@blueprint.route("/api/albums")
def api_albums():
    albums = _load_albums()
    genre = request.args.get("genre", "").strip()
    artist_id = request.args.get("artist_id", type=int)
    sort = request.args.get("sort", "release_date").strip()

    results = list(albums)
    if genre:
        results = [a for a in results if a["genre"] == genre]
    if artist_id:
        results = [a for a in results if a["artist_id"] == artist_id]
    if sort == "release_date":
        results.sort(key=lambda a: a["release_date"], reverse=True)
    elif sort == "title":
        results.sort(key=lambda a: a["title"].lower())

    return jsonify(results)


@blueprint.route("/api/albums/<int:album_id>")
def api_album(album_id):
    albums = _load_albums()
    album = next((a for a in albums if a["id"] == album_id), None)
    if not album:
        abort(404)
    artists = _load_artists()
    tracks = _load_tracks()
    return jsonify(_enrich_album(album, artists, tracks))


@blueprint.route("/api/tracks")
def api_tracks():
    tracks = _load_tracks()
    album_id = request.args.get("album_id", type=int)
    artist_id = request.args.get("artist_id", type=int)
    sort = request.args.get("sort", "plays").strip()

    results = list(tracks)
    if album_id:
        results = [t for t in results if t["album_id"] == album_id]
    if artist_id:
        results = [t for t in results if t["artist_id"] == artist_id]
    if sort == "plays":
        results.sort(key=lambda t: -t["plays"])
    elif sort == "title":
        results.sort(key=lambda t: t["title"].lower())
    elif sort == "track_number":
        results.sort(key=lambda t: (t["album_id"], t["track_number"]))

    artists = _load_artists()
    albums = _load_albums()
    return jsonify([_enrich_track(t, artists, albums) for t in results])


@blueprint.route("/api/tracks/<int:track_id>/like", methods=["POST"])
def api_like_track(track_id):
    tracks = _load_tracks()
    track = next((t for t in tracks if t["id"] == track_id), None)
    if not track:
        abort(404)

    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Login required"}), 401

    # Update track liked_by
    liked_by = track.setdefault("liked_by", [])
    if user_id in liked_by:
        liked_by.remove(user_id)
        action = "unliked"
    else:
        liked_by.append(user_id)
        action = "liked"
    _save_tracks(tracks)

    # Update library
    libs = _load_library()
    lib = next((l for l in libs if l["user_id"] == user_id), None)
    if lib is None:
        lib = {"id": len(libs) + 1, "user_id": user_id, "liked_tracks": [], "liked_albums": [], "followed_artists": []}
        libs.append(lib)
    lt = lib.setdefault("liked_tracks", [])
    if action == "liked" and track_id not in lt:
        lt.append(track_id)
    elif action == "unliked" and track_id in lt:
        lt.remove(track_id)
    _save_library(libs)

    return jsonify({"action": action, "track_id": track_id, "total_likes": len(liked_by)})


@blueprint.route("/api/playlists", methods=["GET"])
def api_playlists_list():
    playlists = _load_playlists()
    user_id = session.get("user_id")
    # Show public + own
    visible = [p for p in playlists if p["is_public"] or (user_id and p["user_id"] == user_id)]
    owner_filter = request.args.get("user_id", type=int)
    if owner_filter:
        visible = [p for p in visible if p["user_id"] == owner_filter]
    return jsonify(visible)


@blueprint.route("/api/playlists", methods=["POST"])
def api_create_playlist():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Login required"}), 401

    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    description = data.get("description", "").strip()
    is_public = data.get("is_public", True)

    if not name:
        return jsonify({"error": "name required"}), 400

    playlists = _load_playlists()
    new_id = max((p["id"] for p in playlists), default=0) + 1
    new_playlist = {
        "id": new_id,
        "user_id": user_id,
        "name": name,
        "description": description,
        "track_ids": data.get("track_ids", []),
        "created_at": datetime.now().strftime("%Y-%m-%d"),
        "is_public": bool(is_public),
    }
    playlists.append(new_playlist)
    _save_playlists(playlists)
    return jsonify(new_playlist), 201


@blueprint.route("/api/playlists/<int:playlist_id>", methods=["GET"])
def api_playlist_detail(playlist_id):
    playlists = _load_playlists()
    playlist = next((p for p in playlists if p["id"] == playlist_id), None)
    if not playlist:
        abort(404)
    user_id = session.get("user_id")
    if not playlist["is_public"] and (not user_id or playlist["user_id"] != user_id):
        abort(404)

    artists = _load_artists()
    albums = _load_albums()
    tracks = _load_tracks()
    enriched_tracks = []
    for tid in playlist.get("track_ids", []):
        t = next((t for t in tracks if t["id"] == tid), None)
        if t:
            enriched_tracks.append(_enrich_track(t, artists, albums))

    result = dict(playlist)
    result["tracks"] = enriched_tracks
    return jsonify(result)


@blueprint.route("/api/playlists/<int:playlist_id>", methods=["PUT"])
def api_update_playlist(playlist_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Login required"}), 401

    playlists = _load_playlists()
    playlist = next((p for p in playlists if p["id"] == playlist_id), None)
    if not playlist:
        abort(404)
    if playlist["user_id"] != user_id:
        return jsonify({"error": "Not your playlist"}), 403

    data = request.get_json(silent=True) or {}
    if "name" in data:
        playlist["name"] = data["name"].strip()
    if "description" in data:
        playlist["description"] = data["description"].strip()
    if "is_public" in data:
        playlist["is_public"] = bool(data["is_public"])
    if "track_ids" in data:
        playlist["track_ids"] = data["track_ids"]

    _save_playlists(playlists)
    return jsonify(playlist)


@blueprint.route("/api/playlists/<int:playlist_id>", methods=["DELETE"])
def api_delete_playlist(playlist_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Login required"}), 401

    playlists = _load_playlists()
    playlist = next((p for p in playlists if p["id"] == playlist_id), None)
    if not playlist:
        abort(404)
    if playlist["user_id"] != user_id:
        return jsonify({"error": "Not your playlist"}), 403

    playlists.remove(playlist)
    _save_playlists(playlists)
    return jsonify({"status": "deleted", "id": playlist_id})


@blueprint.route("/api/playlists/<int:playlist_id>/add", methods=["POST"])
def api_add_to_playlist(playlist_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Login required"}), 401

    playlists = _load_playlists()
    playlist = next((p for p in playlists if p["id"] == playlist_id), None)
    if not playlist:
        abort(404)
    if playlist["user_id"] != user_id:
        return jsonify({"error": "Not your playlist"}), 403

    data = request.get_json(silent=True) or {}
    track_id = data.get("track_id")
    if track_id is None:
        return jsonify({"error": "track_id required"}), 400

    # Verify track exists
    tracks = _load_tracks()
    if not any(t["id"] == track_id for t in tracks):
        return jsonify({"error": "Track not found"}), 404

    track_ids = playlist.setdefault("track_ids", [])
    if track_id in track_ids:
        return jsonify({"error": "Track already in playlist"}), 409
    track_ids.append(track_id)
    _save_playlists(playlists)
    return jsonify({"action": "added", "track_id": track_id, "playlist_id": playlist_id, "total_tracks": len(track_ids)})


@blueprint.route("/api/library")
def api_library():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Login required"}), 401
    lib = _get_library(user_id)
    return jsonify(lib)


@blueprint.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    artists = _load_artists()
    albums = _load_albums()
    tracks = _load_tracks()
    results = _search_all(q, artists, albums, tracks)
    enriched_tracks = [_enrich_track(t, artists, albums) for t in results["tracks"]]
    enriched_albums = [_enrich_album(a, artists, tracks) for a in results["albums"]]
    return jsonify({
        "query": q,
        "artists": results["artists"],
        "albums": enriched_albums,
        "tracks": enriched_tracks,
    })


@blueprint.route("/api/stats")
def api_stats():
    artists = _load_artists()
    albums = _load_albums()
    tracks = _load_tracks()
    playlists = _load_playlists()
    users = _load_users()

    genre_counts = Counter(a["genre"] for a in artists)
    total_plays = sum(t["plays"] for t in tracks)
    total_duration = sum(t["duration_seconds"] for t in tracks)

    return jsonify({
        "total_artists": len(artists),
        "total_albums": len(albums),
        "total_tracks": len(tracks),
        "total_playlists": len(playlists),
        "total_users": len(users),
        "total_plays": total_plays,
        "total_duration_hours": round(total_duration / 3600, 1),
        "genres": dict(genre_counts),
        "top_track": max(tracks, key=lambda t: t["plays"])["title"] if tracks else None,
    })


# ---------------------------------------------------------------------------
# API routes — WRITE (additional mutations)
# ---------------------------------------------------------------------------

@blueprint.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return jsonify({"error": "Invalid credentials"}), 401
    session["user_id"] = user["id"]
    return jsonify({"user_id": user["id"], "username": user["username"]})


@blueprint.route("/api/library/follow", methods=["POST"])
def api_follow_artist():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Login required"}), 401

    data = request.get_json(silent=True) or {}
    artist_id = data.get("artist_id")
    if artist_id is None:
        return jsonify({"error": "artist_id required"}), 400

    artists = _load_artists()
    if not any(a["id"] == artist_id for a in artists):
        return jsonify({"error": "Artist not found"}), 404

    libs = _load_library()
    lib = next((l for l in libs if l["user_id"] == user_id), None)
    if lib is None:
        lib = {"id": len(libs) + 1, "user_id": user_id, "liked_tracks": [], "liked_albums": [], "followed_artists": []}
        libs.append(lib)

    fa = lib.setdefault("followed_artists", [])
    if artist_id in fa:
        fa.remove(artist_id)
        action = "unfollowed"
    else:
        fa.append(artist_id)
        action = "followed"
    _save_library(libs)
    return jsonify({"action": action, "artist_id": artist_id})


@blueprint.route("/api/library/like_album", methods=["POST"])
def api_like_album():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Login required"}), 401

    data = request.get_json(silent=True) or {}
    album_id = data.get("album_id")
    if album_id is None:
        return jsonify({"error": "album_id required"}), 400

    albums = _load_albums()
    if not any(a["id"] == album_id for a in albums):
        return jsonify({"error": "Album not found"}), 404

    libs = _load_library()
    lib = next((l for l in libs if l["user_id"] == user_id), None)
    if lib is None:
        lib = {"id": len(libs) + 1, "user_id": user_id, "liked_tracks": [], "liked_albums": [], "followed_artists": []}
        libs.append(lib)

    la = lib.setdefault("liked_albums", [])
    if album_id in la:
        la.remove(album_id)
        action = "unliked"
    else:
        la.append(album_id)
        action = "liked"
    _save_library(libs)
    return jsonify({"action": action, "album_id": album_id})


# ---------------------------------------------------------------------------
# API routes — Semantic search (search_by_semantic)
# ---------------------------------------------------------------------------

@blueprint.route("/api/semantic_search")
def api_semantic_search():
    q = request.args.get("q", "").strip()
    artists = _load_artists()
    albums = _load_albums()
    tracks = _load_tracks()
    results = _semantic_search(q, artists, albums, tracks)
    enriched_tracks = [_enrich_track(t, artists, albums) for t in results["tracks"]]
    enriched_albums = [_enrich_album(a, artists, tracks) for a in results["albums"]]
    return jsonify({
        "query": q,
        "artists": results["artists"],
        "albums": enriched_albums,
        "tracks": enriched_tracks,
    })


# ---------------------------------------------------------------------------
# API routes — Play (play_by_dropdown, play_by_date_range, play_by_playback)
# ---------------------------------------------------------------------------

@blueprint.route("/api/play", methods=["POST"])
def api_play():
    """Start playing a track, album, or playlist (play_by_dropdown).

    Expects JSON: {type: "track"|"album"|"playlist", id: <int>}
    """
    data = request.get_json(silent=True) or {}
    play_type = data.get("type", "track")
    item_id = data.get("id")
    if item_id is None:
        return jsonify({"error": "id required"}), 400

    artists = _load_artists()
    albums = _load_albums()
    tracks = _load_tracks()

    queue = []
    if play_type == "track":
        t = next((t for t in tracks if t["id"] == item_id), None)
        if not t:
            return jsonify({"error": "Track not found"}), 404
        queue = [_enrich_track(t, artists, albums)]
    elif play_type == "album":
        a = next((a for a in albums if a["id"] == item_id), None)
        if not a:
            return jsonify({"error": "Album not found"}), 404
        album_tracks = sorted([t for t in tracks if t["album_id"] == item_id],
                              key=lambda t: t["track_number"])
        queue = [_enrich_track(t, artists, albums) for t in album_tracks]
    elif play_type == "playlist":
        playlists = _load_playlists()
        pl = next((p for p in playlists if p["id"] == item_id), None)
        if not pl:
            return jsonify({"error": "Playlist not found"}), 404
        for tid in pl.get("track_ids", []):
            t = next((t for t in tracks if t["id"] == tid), None)
            if t:
                queue.append(_enrich_track(t, artists, albums))
    else:
        return jsonify({"error": "Invalid type"}), 400

    # Save playback state
    user_id = session.get("user_id")
    state = {
        "user_id": user_id,
        "type": play_type,
        "item_id": item_id,
        "queue": [{"id": t["id"], "title": t["title"]} for t in queue],
        "current_index": 0,
        "status": "playing",
        "started_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    }

    playback_states = _load_playback()
    if user_id:
        playback_states = [p for p in playback_states if p.get("user_id") != user_id]
    playback_states.append(state)
    _save("playback", playback_states)

    np = queue[0] if queue else None
    return jsonify({"status": "playing", "queue_length": len(queue),
                    "now_playing": np["title"] if np else None,
                    "track": {
                        "id": np.get("id"),
                        "title": np.get("title", ""),
                        "artist": np.get("artist_name", ""),
                        "cover": np.get("album_cover_color", "#333"),
                        "duration": np.get("duration_formatted", ""),
                    } if np else None})


@blueprint.route("/api/play/date_range", methods=["POST"])
def api_play_date_range():
    """Play tracks released within a date range (play_by_date_range)."""
    data = request.get_json(silent=True) or {}
    date_from = data.get("date_from", "")
    date_to = data.get("date_to", "")

    if not date_from or not date_to:
        return jsonify({"error": "date_from and date_to required"}), 400

    albums = _load_albums()
    tracks = _load_tracks()
    artists = _load_artists()

    # Find albums in date range
    matching_album_ids = [a["id"] for a in albums
                          if date_from <= a["release_date"] <= date_to]

    # Get tracks from those albums
    matching_tracks = [t for t in tracks if t["album_id"] in matching_album_ids]
    matching_tracks.sort(key=lambda t: -t["plays"])

    enriched = [_enrich_track(t, artists, albums) for t in matching_tracks]

    user_id = session.get("user_id")
    state = {
        "user_id": user_id,
        "type": "date_range",
        "date_from": date_from,
        "date_to": date_to,
        "queue": [{"id": t["id"], "title": t["title"]} for t in enriched],
        "current_index": 0,
        "status": "playing",
        "started_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    }
    playback_states = _load_playback()
    if user_id:
        playback_states = [p for p in playback_states if p.get("user_id") != user_id]
    playback_states.append(state)
    _save("playback", playback_states)

    return jsonify({
        "status": "playing",
        "date_from": date_from,
        "date_to": date_to,
        "queue_length": len(enriched),
        "now_playing": enriched[0]["title"] if enriched else None,
        "tracks": [{"id": t["id"], "title": t["title"], "artist_name": t["artist_name"]}
                   for t in enriched],
    })


@blueprint.route("/api/playback", methods=["GET"])
def api_playback_state():
    """Get current playback state."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"status": "stopped", "queue": []})
    playback_states = _load_playback()
    state = next((p for p in playback_states if p.get("user_id") == user_id), None)
    if not state:
        return jsonify({"status": "stopped", "queue": []})
    return jsonify(state)


@blueprint.route("/api/playback", methods=["POST"])
def api_playback_control():
    """Control playback: play, pause, next, previous (play_by_playback)."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Login required"}), 401

    data = request.get_json(silent=True) or {}
    action = data.get("action", "")  # "play", "pause", "next", "previous"

    playback_states = _load_playback()
    state = next((p for p in playback_states if p.get("user_id") == user_id), None)
    if not state:
        return jsonify({"error": "Nothing is playing"}), 404

    queue = state.get("queue", [])
    idx = state.get("current_index", 0)

    if action == "pause":
        state["status"] = "paused"
    elif action == "play":
        state["status"] = "playing"
    elif action == "next":
        if idx + 1 < len(queue):
            state["current_index"] = idx + 1
            state["status"] = "playing"
        else:
            state["status"] = "stopped"
    elif action == "previous":
        if idx > 0:
            state["current_index"] = idx - 1
            state["status"] = "playing"
    else:
        return jsonify({"error": "Invalid action. Use play/pause/next/previous."}), 400

    _save("playback", playback_states)

    now_playing = None
    if state["status"] == "playing" and queue:
        now_playing = queue[state["current_index"]]["title"]

    return jsonify({
        "action": action,
        "status": state["status"],
        "current_index": state["current_index"],
        "now_playing": now_playing,
    })


# ---------------------------------------------------------------------------
# API routes — Follow (follow_by_dropdown)
# ---------------------------------------------------------------------------

@blueprint.route("/api/artists/<int:artist_id>/follow", methods=["POST"])
def api_follow_artist_by_id(artist_id):
    """Follow/unfollow artist by ID (follow_by_dropdown / follow_by_toggle).

    This provides a per-artist endpoint in addition to the library/follow endpoint.
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Login required"}), 401

    artists = _load_artists()
    if not any(a["id"] == artist_id for a in artists):
        return jsonify({"error": "Artist not found"}), 404

    libs = _load_library()
    lib = next((l for l in libs if l["user_id"] == user_id), None)
    if lib is None:
        lib = {"id": len(libs) + 1, "user_id": user_id, "liked_tracks": [],
               "liked_albums": [], "followed_artists": []}
        libs.append(lib)

    fa = lib.setdefault("followed_artists", [])
    if artist_id in fa:
        fa.remove(artist_id)
        action = "unfollowed"
    else:
        fa.append(artist_id)
        action = "followed"
    _save_library(libs)

    artist = next(a for a in artists if a["id"] == artist_id)
    return jsonify({"action": action, "artist_id": artist_id, "artist_name": artist["name"]})


# ---------------------------------------------------------------------------
# API routes — Share (share_by_dropdown)
# ---------------------------------------------------------------------------

@blueprint.route("/api/share", methods=["POST"])
def api_share():
    """Share a track, album, or playlist via a shareable link (share_by_dropdown)."""
    data = request.get_json(silent=True) or {}
    share_type = data.get("type", "track")  # track, album, playlist
    item_id = data.get("id")
    platform = data.get("platform", "link")  # link, twitter, facebook, email

    if item_id is None:
        return jsonify({"error": "id required"}), 400

    # Validate the item exists
    if share_type == "track":
        items = _load_tracks()
        item = next((i for i in items if i["id"] == item_id), None)
        title = item["title"] if item else None
    elif share_type == "album":
        items = _load_albums()
        item = next((i for i in items if i["id"] == item_id), None)
        title = item["title"] if item else None
    elif share_type == "playlist":
        items = _load_playlists()
        item = next((i for i in items if i["id"] == item_id), None)
        title = item["name"] if item else None
    else:
        return jsonify({"error": "Invalid type"}), 400

    if not item:
        return jsonify({"error": f"{share_type.capitalize()} not found"}), 404

    share_url = f"/sites/music/{share_type}/{item_id}"

    # Log the share
    shares = _load_shares()
    new_share = {
        "id": max((s["id"] for s in shares), default=0) + 1,
        "type": share_type,
        "item_id": item_id,
        "title": title,
        "platform": platform,
        "share_url": share_url,
        "user_id": session.get("user_id"),
        "shared_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    }
    shares.append(new_share)
    _save("shares", shares)

    return jsonify({"share_url": share_url, "title": title, "platform": platform,
                    "share_id": new_share["id"]})


# ---------------------------------------------------------------------------
# API routes — Subscribe (subscribe_by_toggle)
# ---------------------------------------------------------------------------

@blueprint.route("/api/subscribe", methods=["POST"])
def api_subscribe():
    """Subscribe/unsubscribe to an artist or playlist for updates (subscribe_by_toggle)."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Login required"}), 401

    data = request.get_json(silent=True) or {}
    sub_type = data.get("type", "artist")  # artist or playlist
    item_id = data.get("id")

    if item_id is None:
        return jsonify({"error": "id required"}), 400

    # Validate item
    if sub_type == "artist":
        items = _load_artists()
        item = next((i for i in items if i["id"] == item_id), None)
        item_name = item["name"] if item else None
    elif sub_type == "playlist":
        items = _load_playlists()
        item = next((i for i in items if i["id"] == item_id), None)
        item_name = item["name"] if item else None
    else:
        return jsonify({"error": "Invalid type. Use artist or playlist."}), 400

    if not item:
        return jsonify({"error": f"{sub_type.capitalize()} not found"}), 404

    subs = _load_subscriptions()
    existing = next((s for s in subs
                     if s["user_id"] == user_id and s["type"] == sub_type and s["item_id"] == item_id), None)

    if existing:
        subs.remove(existing)
        action = "unsubscribed"
    else:
        new_sub = {
            "id": max((s["id"] for s in subs), default=0) + 1,
            "user_id": user_id,
            "type": sub_type,
            "item_id": item_id,
            "item_name": item_name,
            "subscribed_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        }
        subs.append(new_sub)
        action = "subscribed"

    _save("subscriptions", subs)
    return jsonify({"action": action, "type": sub_type, "item_id": item_id, "item_name": item_name})


@blueprint.route("/api/subscriptions")
def api_subscriptions():
    """List subscriptions for the current user."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Login required"}), 401
    subs = _load_subscriptions()
    user_subs = [s for s in subs if s["user_id"] == user_id]
    return jsonify(user_subs)


# ---------------------------------------------------------------------------
# API routes — Add track to playlist (add_by_button, form-based)
# ---------------------------------------------------------------------------

@blueprint.route("/api/playlists/<int:playlist_id>/add_track", methods=["POST"])
def api_add_track_to_playlist(playlist_id):
    """Add a track to a playlist via form or JSON (add_by_button).

    Accepts form data (track_id) or JSON {track_id: <int>}.
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Login required"}), 401

    playlists = _load_playlists()
    playlist = next((p for p in playlists if p["id"] == playlist_id), None)
    if not playlist:
        return jsonify({"error": "Playlist not found"}), 404
    if playlist["user_id"] != user_id:
        return jsonify({"error": "Not your playlist"}), 403

    # Accept both form and JSON
    if request.is_json:
        data = request.get_json(silent=True) or {}
        track_id = data.get("track_id")
    else:
        track_id = request.form.get("track_id", type=int)

    if track_id is None:
        return jsonify({"error": "track_id required"}), 400

    tracks = _load_tracks()
    if not any(t["id"] == track_id for t in tracks):
        return jsonify({"error": "Track not found"}), 404

    track_ids = playlist.setdefault("track_ids", [])
    if track_id in track_ids:
        return jsonify({"error": "Track already in playlist"}), 409
    track_ids.append(track_id)
    _save_playlists(playlists)

    track = next(t for t in tracks if t["id"] == track_id)
    return jsonify({"action": "added", "track_id": track_id, "track_title": track["title"],
                    "playlist_id": playlist_id, "total_tracks": len(track_ids)})


# ---------------------------------------------------------------------------
# API routes — User data retrieval (for verifiers)
# ---------------------------------------------------------------------------

@blueprint.route("/api/users/<int:uid>")
def api_user(uid):
    users = _load_users()
    user = next((u for u in users if u["id"] == uid), None)
    if not user:
        abort(404)
    safe = {k: v for k, v in user.items() if k != "password"}
    # Include library data
    lib = _get_library(uid)
    safe["liked_tracks"] = lib.get("liked_tracks", [])
    safe["liked_albums"] = lib.get("liked_albums", [])
    safe["followed_artists"] = lib.get("followed_artists", [])
    # Include subscriptions
    subs = _load_subscriptions()
    safe["subscriptions"] = [s for s in subs if s["user_id"] == uid]
    return jsonify(safe)


# ---------------------------------------------------------------------------
# API routes — Tracks sorted & filtered (sort_by_ranking, filter queries)
# ---------------------------------------------------------------------------

@blueprint.route("/api/tracks/by_date_range")
def api_tracks_by_date_range():
    """Get tracks from albums released in a date range."""
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")

    albums = _load_albums()
    tracks = _load_tracks()
    artists = _load_artists()

    matching_album_ids = set()
    for a in albums:
        if date_from and a["release_date"] < date_from:
            continue
        if date_to and a["release_date"] > date_to:
            continue
        matching_album_ids.add(a["id"])

    matching = [t for t in tracks if t["album_id"] in matching_album_ids]
    matching.sort(key=lambda t: -t["plays"])

    return jsonify([_enrich_track(t, artists, albums) for t in matching])


# ---------------------------------------------------------------------------
# HTML route — genre browse via dropdown (navigate_by_dropdown supplement)
# ---------------------------------------------------------------------------

@blueprint.route("/genre/<genre_name>")
def genre_page(genre_name):
    """Navigate to a genre page (navigate_by_dropdown)."""
    artists = _load_artists()
    albums = _load_albums()

    genre_artists = [a for a in artists if a["genre"].lower() == genre_name.lower()]
    genre_albums = [a for a in albums if a["genre"].lower() == genre_name.lower()]
    genre_albums.sort(key=lambda a: a["release_date"], reverse=True)

    genres = sorted(set(a["genre"] for a in artists))

    # Find actual genre name (case-correct)
    actual_genre = genre_name
    for g in genres:
        if g.lower() == genre_name.lower():
            actual_genre = g
            break

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template("music/browse.html",
                           albums=genre_albums,
                           artists=genre_artists,
                           genres=genres,
                           selected_genre=actual_genre,
                           user=user)


# ---------------------------------------------------------------------------
# HTML route — search results via route (search_by_route)
# ---------------------------------------------------------------------------

@blueprint.route("/search/<query>")
def search_by_route(query):
    """Navigate to search results via URL path (search_by_route)."""
    artists = _load_artists()
    albums = _load_albums()
    tracks = _load_tracks()

    results = _search_all(query, artists, albums, tracks)
    enriched_tracks = [_enrich_track(t, artists, albums) for t in results["tracks"]]
    enriched_albums = [_enrich_album(a, artists, tracks) for a in results["albums"]]

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template("music/search.html",
                           q=query,
                           artists=results["artists"],
                           albums=enriched_albums,
                           tracks=enriched_tracks,
                           user=user)


# ---------------------------------------------------------------------------
# Form-based mutation routes (for browser automation compatibility)
# ---------------------------------------------------------------------------

@blueprint.route("/track/<int:track_id>/like", methods=["POST"])
def form_like_track(track_id):
    """Toggle like on a track via form POST (save_by_toggle)."""
    if "user_id" not in session:
        return redirect(url_for("music.login_page"))
    user_id = session["user_id"]

    tracks = _load_tracks()
    track = next((t for t in tracks if t["id"] == track_id), None)
    if not track:
        abort(404)

    liked_by = track.setdefault("liked_by", [])
    if user_id in liked_by:
        liked_by.remove(user_id)
    else:
        liked_by.append(user_id)
    _save_tracks(tracks)

    libs = _load_library()
    lib = next((l for l in libs if l["user_id"] == user_id), None)
    if lib is None:
        lib = {"id": len(libs) + 1, "user_id": user_id, "liked_tracks": [],
               "liked_albums": [], "followed_artists": []}
        libs.append(lib)
    lt = lib.setdefault("liked_tracks", [])
    if track_id in lt:
        lt.remove(track_id)
    else:
        lt.append(track_id)
    _save_library(libs)

    return redirect(url_for("music.track_detail", track_id=track_id))


@blueprint.route("/artist/<int:artist_id>/follow", methods=["POST"])
def form_follow_artist(artist_id):
    """Toggle follow on an artist via form POST (follow_by_toggle)."""
    if "user_id" not in session:
        return redirect(url_for("music.login_page"))
    user_id = session["user_id"]

    artists = _load_artists()
    if not any(a["id"] == artist_id for a in artists):
        abort(404)

    libs = _load_library()
    lib = next((l for l in libs if l["user_id"] == user_id), None)
    if lib is None:
        lib = {"id": len(libs) + 1, "user_id": user_id, "liked_tracks": [],
               "liked_albums": [], "followed_artists": []}
        libs.append(lib)

    fa = lib.setdefault("followed_artists", [])
    if artist_id in fa:
        fa.remove(artist_id)
    else:
        fa.append(artist_id)
    _save_library(libs)

    return redirect(url_for("music.artist_detail", artist_id=artist_id))


@blueprint.route("/album/<int:album_id>/save", methods=["POST"])
def form_save_album(album_id):
    """Toggle save/like on an album via form POST (save_by_toggle)."""
    if "user_id" not in session:
        return redirect(url_for("music.login_page"))
    user_id = session["user_id"]

    albums = _load_albums()
    if not any(a["id"] == album_id for a in albums):
        abort(404)

    libs = _load_library()
    lib = next((l for l in libs if l["user_id"] == user_id), None)
    if lib is None:
        lib = {"id": len(libs) + 1, "user_id": user_id, "liked_tracks": [],
               "liked_albums": [], "followed_artists": []}
        libs.append(lib)

    la = lib.setdefault("liked_albums", [])
    if album_id in la:
        la.remove(album_id)
    else:
        la.append(album_id)
    _save_library(libs)

    return redirect(url_for("music.album_detail", album_id=album_id))


@blueprint.route("/playlist/<int:playlist_id>/add", methods=["POST"])
def form_add_to_playlist(playlist_id):
    """Add track to playlist via form POST (add_by_button)."""
    if "user_id" not in session:
        return redirect(url_for("music.login_page"))
    user_id = session["user_id"]

    playlists = _load_playlists()
    playlist = next((p for p in playlists if p["id"] == playlist_id), None)
    if not playlist:
        abort(404)
    if playlist["user_id"] != user_id:
        abort(403)

    track_id = request.form.get("track_id", type=int)
    if track_id is None:
        abort(400)

    tracks = _load_tracks()
    if not any(t["id"] == track_id for t in tracks):
        abort(404)

    track_ids = playlist.setdefault("track_ids", [])
    if track_id not in track_ids:
        track_ids.append(track_id)
    _save_playlists(playlists)

    redirect_to = request.form.get("redirect_to", "")
    if redirect_to:
        return redirect(redirect_to)
    return redirect(url_for("music.playlist_detail", playlist_id=playlist_id))


@blueprint.route("/playlists/create", methods=["GET"])
def create_playlist_page():
    """Show the create playlist form (create_from_free_text)."""
    if "user_id" not in session:
        return redirect(url_for("music.login_page"))
    user = _get_user(session["user_id"])
    return render_template("music/create_playlist.html", user=user, error=None)


@blueprint.route("/playlists/create", methods=["POST"])
def create_playlist_submit():
    """Create a new playlist from form input (create_from_free_text)."""
    if "user_id" not in session:
        return redirect(url_for("music.login_page"))
    user_id = session["user_id"]

    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    is_public = request.form.get("is_public", "on") == "on"

    if not name:
        user = _get_user(user_id)
        return render_template("music/create_playlist.html", user=user,
                               error="Playlist name is required")

    playlists = _load_playlists()
    new_id = max((p["id"] for p in playlists), default=0) + 1
    new_playlist = {
        "id": new_id,
        "user_id": user_id,
        "name": name,
        "description": description,
        "track_ids": [],
        "created_at": datetime.now().strftime("%Y-%m-%d"),
        "is_public": bool(is_public),
    }
    playlists.append(new_playlist)
    _save_playlists(playlists)
    return redirect(url_for("music.playlist_detail", playlist_id=new_id))


@blueprint.route("/artist/<int:artist_id>/subscribe", methods=["POST"])
def form_subscribe_artist(artist_id):
    """Toggle subscription on an artist via form POST (subscribe_by_toggle)."""
    if "user_id" not in session:
        return redirect(url_for("music.login_page"))
    user_id = session["user_id"]

    artists = _load_artists()
    artist = next((a for a in artists if a["id"] == artist_id), None)
    if not artist:
        abort(404)

    subs = _load_subscriptions()
    existing = next((s for s in subs
                     if s["user_id"] == user_id and s["type"] == "artist"
                     and s["item_id"] == artist_id), None)

    if existing:
        subs.remove(existing)
    else:
        new_sub = {
            "id": max((s["id"] for s in subs), default=0) + 1,
            "user_id": user_id,
            "type": "artist",
            "item_id": artist_id,
            "item_name": artist["name"],
            "subscribed_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        }
        subs.append(new_sub)
    _save("subscriptions", subs)

    return redirect(url_for("music.artist_detail", artist_id=artist_id))


# ---------------------------------------------------------------------------
# API — Genres list (for select_by_dropdown)
# ---------------------------------------------------------------------------

@blueprint.route("/api/genres")
def api_genres():
    """List all genres with artist/album counts (select_by_dropdown)."""
    artists = _load_artists()
    albums = _load_albums()
    genre_counts = Counter(a["genre"] for a in artists)
    album_genre_counts = Counter(a["genre"] for a in albums)
    genres = sorted(genre_counts.keys())
    return jsonify([{"name": g, "artist_count": genre_counts[g],
                     "album_count": album_genre_counts.get(g, 0)} for g in genres])


# ---------------------------------------------------------------------------
# API — Shares list (for verifiers)
# ---------------------------------------------------------------------------

@blueprint.route("/api/shares")
def api_shares():
    """List all share log entries."""
    return jsonify(_load_shares())
