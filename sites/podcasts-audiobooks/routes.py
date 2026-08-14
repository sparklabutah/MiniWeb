"""SoundShelf -- Podcasts & Audiobooks streaming platform.

Data: podcasts, episodes, audiobooks, library, reviews, and users loaded from
per-site SQLite tables via db.query().

Browse podcasts, listen to episodes, purchase audiobooks, manage your library,
and leave reviews.
"""

import csv
import io
import pathlib
from collections import Counter
from datetime import datetime

from flask import (
    Blueprint,
    Response,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from app import db
from app.events import emit

SITE = "podcasts-audiobooks"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "podcasts-audiobooks",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)



# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _load_podcasts():
    return db.query(SITE, "podcasts")


def _load_episodes():
    return db.query(SITE, "episodes")


# ---------------------------------------------------------------------------
# Audiobook loading
# ---------------------------------------------------------------------------

def _load_audiobooks():
    """Load audiobooks from the per-site DB table."""
    return db.query(SITE, "audiobooks")


# ---------------------------------------------------------------------------
# Overlay-only data (mutable state)
# ---------------------------------------------------------------------------

def _load_library():
    return db.query(SITE, "library")


def _load_reviews():
    return db.query(SITE, "reviews")


def _load_users():
    return db.query(SITE, "users")


def _get_user(user_id):
    return db.get_item(SITE, "users", user_id)


def _get_user_library(user_id):
    libs = db.query(SITE, "library", where={"user_id": user_id}, limit=1)
    return libs[0] if libs else None


def _search_items(query, podcasts, audiobooks, episodes):
    """Search across podcasts, audiobooks, and episodes by keyword."""
    q = query.lower().strip()
    if not q:
        return {"podcasts": podcasts, "audiobooks": audiobooks, "episodes": episodes}

    matched_podcasts = [
        p for p in podcasts
        if q in p["title"].lower()
        or q in p["host"].lower()
        or q in p["description"].lower()
        or q in p["category"].lower()
    ]
    matched_audiobooks = [
        a for a in audiobooks
        if q in a["title"].lower()
        or q in a["author"].lower()
        or q in a["narrator"].lower()
        or q in a["description"].lower()
        or q in a["genre"].lower()
    ]
    matched_episodes = [
        e for e in episodes
        if q in e["title"].lower()
        or q in e["description"].lower()
    ]
    return {
        "podcasts": matched_podcasts,
        "audiobooks": matched_audiobooks,
        "episodes": matched_episodes,
    }


def _semantic_score(query, text_fields):
    """Simple keyword-overlap score for semantic-style search."""
    terms = query.lower().split()
    combined = " ".join(text_fields).lower()
    return sum(1 for t in terms if t in combined)


def _semantic_search_podcasts(podcasts, query):
    """Rank podcasts by semantic relevance to query."""
    if not query:
        return podcasts
    scored = []
    for p in podcasts:
        s = _semantic_score(query, [p["title"], p["host"], p["description"], p["category"]])
        if s > 0:
            scored.append((p, s))
    scored.sort(key=lambda x: -x[1])
    return [p for p, _ in scored]


def _semantic_search_audiobooks(audiobooks, query):
    """Rank audiobooks by semantic relevance to query."""
    if not query:
        return audiobooks
    scored = []
    for a in audiobooks:
        s = _semantic_score(query, [a["title"], a["author"], a["narrator"], a["description"], a["genre"]])
        if s > 0:
            scored.append((a, s))
    scored.sort(key=lambda x: -x[1])
    return [a for a, _ in scored]


def _get_resume(lib, item_type, item_id):
    """Return the saved (position_seconds, progress_percent) for an item, or (0, 0)."""
    if not lib:
        return 0, 0
    for h in lib.get("listen_history", []):
        if h.get("item_type") == item_type and h.get("item_id") == item_id:
            return h.get("position", 0) or 0, h.get("progress_percent", 0) or 0
    return 0, 0


def _ensure_lib(libraries, user_id):
    """Get or create a library entry for user_id."""
    lib = next((l for l in libraries if l["user_id"] == user_id), None)
    if not lib:
        lib = {
            "id": max((l["id"] for l in libraries), default=0) + 1,
            "user_id": user_id,
            "subscribed_podcasts": [],
            "followed_podcasts": [],
            "purchased_audiobooks": [],
            "saved_episodes": [],
            "listen_history": [],
            "playback_speed": 1.0,
            "playlists": [],
        }
        libraries.append(lib)
    return lib


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    """Discover page: trending podcasts, new audiobooks, recent episodes."""
    podcasts = _load_podcasts()
    audiobooks = _load_audiobooks()
    episodes = _load_episodes()

    trending_podcasts = sorted(podcasts, key=lambda p: -p["subscribers"])[:6]
    new_audiobooks = sorted(audiobooks, key=lambda a: -a["rating"])[:6]
    recent_episodes = sorted(episodes, key=lambda e: e["publish_date"], reverse=True)[:8]

    # Attach podcast titles to episodes for display
    podcast_map = {p["id"]: p for p in podcasts}
    for ep in recent_episodes:
        ep["_podcast"] = podcast_map.get(ep["podcast_id"], {})

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template(
        "podcasts-audiobooks/index.html",
        trending_podcasts=trending_podcasts,
        new_audiobooks=new_audiobooks,
        recent_episodes=recent_episodes,
        user=user,
    )


@blueprint.route("/podcasts")
def podcasts_list():
    """Browse all podcasts with optional category filter."""
    podcasts = _load_podcasts()
    categories = sorted(set(p["category"] for p in podcasts))
    cat = request.args.get("category", "").strip()
    if cat:
        podcasts = [p for p in podcasts if p["category"] == cat]
    podcasts.sort(key=lambda p: -p["subscribers"])

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template(
        "podcasts-audiobooks/podcasts.html",
        podcasts=podcasts,
        categories=categories,
        selected_category=cat,
        user=user,
    )


@blueprint.route("/podcast/<int:podcast_id>")
def podcast_detail(podcast_id):
    """Single podcast page with episodes list."""
    podcasts = _load_podcasts()
    podcast = next((p for p in podcasts if p["id"] == podcast_id), None)
    if podcast is None:
        abort(404)

    episodes = db.query(SITE, "episodes", where={"podcast_id": podcast_id}, sort="-publish_date")

    reviews = db.query(SITE, "reviews", where={"item_type": "podcast", "item_id": podcast_id})

    subscribed = False
    followed = False
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
        lib = _get_user_library(session["user_id"])
        if lib:
            if podcast_id in lib.get("subscribed_podcasts", []):
                subscribed = True
            if podcast_id in lib.get("followed_podcasts", []):
                followed = True

    return render_template(
        "podcasts-audiobooks/podcast_detail.html",
        podcast=podcast,
        episodes=episodes,
        reviews=reviews,
        subscribed=subscribed,
        followed=followed,
        user=user,
    )


@blueprint.route("/episode/<int:episode_id>")
def episode_detail(episode_id):
    """Single episode player page."""
    episodes = _load_episodes()
    episode = next((e for e in episodes if e["id"] == episode_id), None)
    if episode is None:
        abort(404)

    podcasts = _load_podcasts()
    podcast = next((p for p in podcasts if p["id"] == episode["podcast_id"]), None)

    liked = False
    saved = False
    user = None
    resume_position = 0
    resume_percent = 0
    if "user_id" in session:
        user = _get_user(session["user_id"])
        if user and user["id"] in episode.get("liked_by", []):
            liked = True
        lib = _get_user_library(session["user_id"])
        if lib and episode_id in lib.get("saved_episodes", []):
            saved = True
        # Resume where the listener left off (persisted playback position).
        resume_position, resume_percent = _get_resume(lib, "episode", episode_id)

    return render_template(
        "podcasts-audiobooks/episode_detail.html",
        episode=episode,
        podcast=podcast,
        liked=liked,
        saved=saved,
        user=user,
        resume_position=resume_position,
        resume_percent=resume_percent,
    )


@blueprint.route("/audiobooks")
def audiobooks_list():
    """Browse all audiobooks with optional genre filter and slider filters."""
    audiobooks = _load_audiobooks()
    genres = sorted(set(a["genre"] for a in audiobooks))
    genre = request.args.get("genre", "").strip()
    sort = request.args.get("sort", "rating").strip()
    min_rating = request.args.get("min_rating", type=float)
    max_duration = request.args.get("max_duration", type=float)

    if genre:
        audiobooks = [a for a in audiobooks if a["genre"] == genre]

    # filter_by_slider: rating and duration
    if min_rating is not None:
        audiobooks = [a for a in audiobooks if a["rating"] >= min_rating]
    if max_duration is not None:
        audiobooks = [a for a in audiobooks if a["duration_hours"] <= max_duration]

    if sort == "price_low":
        audiobooks.sort(key=lambda a: a["price"])
    elif sort == "price_high":
        audiobooks.sort(key=lambda a: -a["price"])
    elif sort == "duration":
        audiobooks.sort(key=lambda a: -a["duration_hours"])
    elif sort == "title":
        audiobooks.sort(key=lambda a: a["title"].lower())
    else:
        audiobooks.sort(key=lambda a: -a["rating"])

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template(
        "podcasts-audiobooks/audiobooks.html",
        audiobooks=audiobooks,
        genres=genres,
        selected_genre=genre,
        selected_sort=sort,
        min_rating=min_rating,
        max_duration=max_duration,
        user=user,
    )


@blueprint.route("/audiobook/<int:audiobook_id>")
def audiobook_detail(audiobook_id):
    """Single audiobook detail page."""
    audiobooks = _load_audiobooks()
    audiobook = next((a for a in audiobooks if a["id"] == audiobook_id), None)
    if audiobook is None:
        abort(404)

    reviews = db.query(SITE, "reviews", where={"item_type": "audiobook", "item_id": audiobook_id})

    purchased = False
    liked = False
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
        lib = _get_user_library(session["user_id"])
        if lib and audiobook_id in lib.get("purchased_audiobooks", []):
            purchased = True
        if user and user["id"] in audiobook.get("liked_by", []):
            liked = True

    # Related audiobooks in same genre
    related = [a for a in audiobooks if a["genre"] == audiobook["genre"] and a["id"] != audiobook_id][:4]

    return render_template(
        "podcasts-audiobooks/audiobook_detail.html",
        audiobook=audiobook,
        reviews=reviews,
        purchased=purchased,
        liked=liked,
        related=related,
        user=user,
    )


@blueprint.route("/library")
def library_page():
    """User's personal library with subscriptions and purchases."""
    if "user_id" not in session:
        return redirect(url_for("podcasts-audiobooks.login_page"))

    user = _get_user(session["user_id"])
    if not user:
        return redirect(url_for("podcasts-audiobooks.login_page"))

    lib = _get_user_library(session["user_id"])
    if not lib:
        lib = {
            "subscribed_podcasts": [], "followed_podcasts": [],
            "purchased_audiobooks": [], "saved_episodes": [],
            "listen_history": [], "playback_speed": 1.0,
        }

    podcasts = _load_podcasts()
    audiobooks = _load_audiobooks()
    episodes = _load_episodes()

    subscribed = [p for p in podcasts if p["id"] in lib.get("subscribed_podcasts", [])]
    followed = [p for p in podcasts if p["id"] in lib.get("followed_podcasts", [])]
    purchased = [a for a in audiobooks if a["id"] in lib.get("purchased_audiobooks", [])]
    saved_eps = [e for e in episodes if e["id"] in lib.get("saved_episodes", [])]

    # Attach podcast info to saved episodes
    podcast_map = {p["id"]: p for p in podcasts}
    for ep in saved_eps:
        ep["_podcast"] = podcast_map.get(ep["podcast_id"], {})

    # Build listen history with titles
    audiobook_map = {a["id"]: a for a in audiobooks}
    episode_map = {e["id"]: e for e in episodes}
    history = []
    for entry in lib.get("listen_history", []):
        item = dict(entry)
        if entry["item_type"] == "episode":
            ep = episode_map.get(entry["item_id"])
            if ep:
                item["_title"] = ep["title"]
                item["_podcast"] = podcast_map.get(ep["podcast_id"], {}).get("title", "")
        elif entry["item_type"] == "audiobook":
            ab = audiobook_map.get(entry["item_id"])
            if ab:
                item["_title"] = ab["title"]
                item["_author"] = ab["author"]
        history.append(item)

    history.sort(key=lambda h: h.get("last_played", ""), reverse=True)

    return render_template(
        "podcasts-audiobooks/library.html",
        user=user,
        subscribed_podcasts=subscribed,
        followed_podcasts=followed,
        purchased_audiobooks=purchased,
        saved_episodes=saved_eps,
        listen_history=history,
        playback_speed=lib.get("playback_speed", 1.0),
    )


@blueprint.route("/search")
def search_page():
    """Search results page."""
    q = request.args.get("q", "").strip()
    podcasts = _load_podcasts()
    audiobooks = _load_audiobooks()
    episodes = _load_episodes()

    results = _search_items(q, podcasts, audiobooks, episodes)

    # Attach podcast info to episode results
    podcast_map = {p["id"]: p for p in podcasts}
    for ep in results["episodes"]:
        ep["_podcast"] = podcast_map.get(ep["podcast_id"], {})

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template(
        "podcasts-audiobooks/search.html",
        q=q,
        results=results,
        user=user,
    )


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("podcasts-audiobooks/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return render_template("podcasts-audiobooks/login.html", error="Invalid username or password")
    session["user_id"] = user["id"]
    emit("signup", user_id=user["id"], site_name="podcasts-audiobooks", username=request.form.get("username", ""), password=request.form.get("password", ""), email="")
    return redirect(url_for("podcasts-audiobooks.library_page"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("podcasts-audiobooks.index"))


# ---------------------------------------------------------------------------
# API routes -- read
# ---------------------------------------------------------------------------

@blueprint.route("/api/podcasts")
def api_podcasts():
    """List podcasts with optional category filter and sort."""
    podcasts = _load_podcasts()
    cat = request.args.get("category", "").strip()
    sort = request.args.get("sort", "subscribers").strip()
    limit = request.args.get("limit", type=int)

    if cat:
        podcasts = [p for p in podcasts if p["category"] == cat]

    if sort == "rating":
        podcasts.sort(key=lambda p: -p["rating"])
    elif sort == "title":
        podcasts.sort(key=lambda p: p["title"].lower())
    else:
        podcasts.sort(key=lambda p: -p["subscribers"])

    if limit:
        podcasts = podcasts[:limit]

    return jsonify(podcasts)


@blueprint.route("/api/podcasts/<int:podcast_id>")
def api_podcast(podcast_id):
    podcasts = _load_podcasts()
    podcast = next((p for p in podcasts if p["id"] == podcast_id), None)
    if podcast is None:
        abort(404)
    return jsonify(podcast)


@blueprint.route("/api/podcasts/categories")
def api_podcast_categories():
    """List all podcast categories (for navigate_by_dropdown)."""
    podcasts = _load_podcasts()
    categories = sorted(set(p["category"] for p in podcasts))
    return jsonify(categories)


@blueprint.route("/api/episodes")
def api_episodes():
    """List episodes with optional podcast_id filter, date range, and sort."""
    podcast_id = request.args.get("podcast_id", type=int)
    sort = request.args.get("sort", "date").strip()
    limit = request.args.get("limit", type=int)
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    where_f = {}
    if podcast_id:
        where_f["podcast_id"] = podcast_id
    episodes = db.query(SITE, "episodes", where=where_f if where_f else None)

    # play_by_date_range: filter episodes by date range
    if date_from:
        episodes = [e for e in episodes if e["publish_date"] >= date_from]
    if date_to:
        episodes = [e for e in episodes if e["publish_date"] <= date_to]

    if sort == "listens":
        episodes.sort(key=lambda e: -e["listens"])
    elif sort == "duration":
        episodes.sort(key=lambda e: -e["duration_minutes"])
    else:
        episodes.sort(key=lambda e: e["publish_date"], reverse=True)

    if limit:
        episodes = episodes[:limit]

    return jsonify(episodes)


@blueprint.route("/api/episodes/<int:episode_id>")
def api_episode(episode_id):
    """Get a single episode by ID."""
    episodes = _load_episodes()
    episode = next((e for e in episodes if e["id"] == episode_id), None)
    if episode is None:
        abort(404)
    return jsonify(episode)


@blueprint.route("/api/audiobooks")
def api_audiobooks():
    """List audiobooks with optional genre filter, slider filters, and sort."""
    audiobooks = _load_audiobooks()
    genre = request.args.get("genre", "").strip()
    sort = request.args.get("sort", "rating").strip()
    limit = request.args.get("limit", type=int)
    min_rating = request.args.get("min_rating", type=float)
    max_duration = request.args.get("max_duration", type=float)

    if genre:
        audiobooks = [a for a in audiobooks if a["genre"] == genre]

    # filter_by_slider
    if min_rating is not None:
        audiobooks = [a for a in audiobooks if a["rating"] >= min_rating]
    if max_duration is not None:
        audiobooks = [a for a in audiobooks if a["duration_hours"] <= max_duration]

    if sort == "price_low":
        audiobooks.sort(key=lambda a: a["price"])
    elif sort == "price_high":
        audiobooks.sort(key=lambda a: -a["price"])
    elif sort == "duration":
        audiobooks.sort(key=lambda a: -a["duration_hours"])
    elif sort == "title":
        audiobooks.sort(key=lambda a: a["title"].lower())
    else:
        audiobooks.sort(key=lambda a: -a["rating"])

    if limit:
        audiobooks = audiobooks[:limit]

    return jsonify(audiobooks)


@blueprint.route("/api/audiobooks/<int:audiobook_id>")
def api_audiobook(audiobook_id):
    audiobooks = _load_audiobooks()
    audiobook = next((a for a in audiobooks if a["id"] == audiobook_id), None)
    if audiobook is None:
        abort(404)
    return jsonify(audiobook)


@blueprint.route("/api/audiobooks/genres")
def api_audiobook_genres():
    """List all audiobook genres (for select_by_dropdown)."""
    audiobooks = _load_audiobooks()
    genres = sorted(set(a["genre"] for a in audiobooks))
    return jsonify(genres)


@blueprint.route("/api/library")
def api_library():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401
    lib = _get_user_library(session["user_id"])
    if not lib:
        return jsonify({
            "subscribed_podcasts": [], "followed_podcasts": [],
            "purchased_audiobooks": [], "saved_episodes": [],
            "listen_history": [], "playback_speed": 1.0,
        })
    return jsonify(lib)


@blueprint.route("/api/library/<int:user_id>")
def api_library_user(user_id):
    """Get library for a specific user (for verifiers)."""
    lib = next((l for l in _load_library() if l["user_id"] == user_id), None)
    if not lib:
        return jsonify({
            "user_id": user_id,
            "subscribed_podcasts": [], "followed_podcasts": [],
            "purchased_audiobooks": [], "saved_episodes": [],
            "listen_history": [], "playback_speed": 1.0,
        })
    return jsonify(lib)


@blueprint.route("/api/reviews")
def api_reviews_get():
    item_type = request.args.get("item_type", "").strip()
    item_id = request.args.get("item_id", type=int)
    user_id = request.args.get("user_id", type=int)
    where_f = {}
    if item_type:
        where_f["item_type"] = item_type
    if item_id is not None:
        where_f["item_id"] = item_id
    if user_id is not None:
        where_f["user_id"] = user_id
    reviews = db.query(SITE, "reviews", where=where_f if where_f else None)

    return jsonify(reviews)


@blueprint.route("/api/search")
def api_search():
    """Keyword search across all content types (search_by_query)."""
    q = request.args.get("q", "").strip()
    podcasts = _load_podcasts()
    audiobooks = _load_audiobooks()
    episodes = _load_episodes()
    results = _search_items(q, podcasts, audiobooks, episodes)
    return jsonify(results)


@blueprint.route("/api/search/semantic")
def api_search_semantic():
    """Semantic search with keyword-overlap scoring (search_by_semantic)."""
    q = request.args.get("q", "").strip()
    content_type = request.args.get("type", "all").strip()

    result = {}
    if content_type in ("all", "podcasts"):
        result["podcasts"] = _semantic_search_podcasts(_load_podcasts(), q)
    if content_type in ("all", "audiobooks"):
        result["audiobooks"] = _semantic_search_audiobooks(_load_audiobooks(), q)
    if content_type in ("all", "episodes"):
        episodes = _load_episodes()
        if q:
            scored = []
            for e in episodes:
                s = _semantic_score(q, [e["title"], e["description"]])
                if s > 0:
                    scored.append((e, s))
            scored.sort(key=lambda x: -x[1])
            result["episodes"] = [e for e, _ in scored]
        else:
            result["episodes"] = episodes

    return jsonify(result)


@blueprint.route("/api/stats")
def api_stats():
    podcasts = _load_podcasts()
    audiobooks = _load_audiobooks()
    episodes = _load_episodes()
    reviews = _load_reviews()
    libraries = _load_library()

    total_listen_minutes = sum(e["duration_minutes"] for e in episodes)
    total_audiobook_hours = sum(a["duration_hours"] for a in audiobooks)
    podcast_categories = Counter(p["category"] for p in podcasts)
    audiobook_genres = Counter(a["genre"] for a in audiobooks)
    avg_podcast_rating = round(sum(p["rating"] for p in podcasts) / len(podcasts), 2) if podcasts else 0
    avg_audiobook_rating = round(sum(a["rating"] for a in audiobooks) / len(audiobooks), 2) if audiobooks else 0

    return jsonify({
        "total_podcasts": len(podcasts),
        "total_audiobooks": len(audiobooks),
        "total_episodes": len(episodes),
        "total_reviews": len(reviews),
        "total_users": len(libraries),
        "total_episode_minutes": total_listen_minutes,
        "total_audiobook_hours": total_audiobook_hours,
        "avg_podcast_rating": avg_podcast_rating,
        "avg_audiobook_rating": avg_audiobook_rating,
        "podcast_categories": dict(podcast_categories),
        "audiobook_genres": dict(audiobook_genres),
    })


@blueprint.route("/api/export")
def api_export():
    """Export podcast or audiobook catalog as CSV (export_by_dropdown)."""
    content_type = request.args.get("type", "podcasts").strip()
    fmt = request.args.get("format", "csv").strip()

    if content_type == "audiobooks":
        items = _load_audiobooks()
        if fmt == "json":
            return jsonify(items)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "title", "author", "narrator", "genre", "rating", "price", "duration_hours", "chapters", "publish_date"])
        for a in items:
            writer.writerow([a["id"], a["title"], a["author"], a["narrator"], a["genre"],
                             a["rating"], a["price"], a["duration_hours"], a["chapters"], a["publish_date"]])
        return Response(output.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=audiobooks.csv"})
    else:
        items = _load_podcasts()
        if fmt == "json":
            return jsonify(items)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "title", "host", "category", "rating", "subscribers", "episodes_count", "language", "created_date"])
        for p in items:
            writer.writerow([p["id"], p["title"], p["host"], p["category"],
                             p["rating"], p["subscribers"], p["episodes_count"], p["language"], p["created_date"]])
        return Response(output.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=podcasts.csv"})


# ---------------------------------------------------------------------------
# API routes -- write (mutable state)
# ---------------------------------------------------------------------------

@blueprint.route("/api/podcasts/<int:podcast_id>/subscribe", methods=["POST"])
def api_subscribe_podcast(podcast_id):
    """Toggle podcast subscription (subscribe_by_toggle)."""
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    podcasts = _load_podcasts()
    podcast = next((p for p in podcasts if p["id"] == podcast_id), None)
    if not podcast:
        abort(404)

    libraries = _load_library()
    lib = _ensure_lib(libraries, session["user_id"])

    subs = lib.setdefault("subscribed_podcasts", [])
    if podcast_id in subs:
        subs.remove(podcast_id)
        action = "unsubscribed"
        podcast["subscribers"] = max(0, podcast["subscribers"] - 1)
    else:
        subs.append(podcast_id)
        action = "subscribed"
        podcast["subscribers"] += 1

    db.save_collection(SITE, "library", libraries)
    db.save_collection(SITE, "podcasts", podcasts)

    return jsonify({
        "action": action,
        "podcast_id": podcast_id,
        "podcast_title": podcast["title"],
        "subscribers": podcast["subscribers"],
    })


@blueprint.route("/api/podcasts/<int:podcast_id>/follow", methods=["POST"])
def api_follow_podcast(podcast_id):
    """Toggle follow on a podcast (follow_by_toggle)."""
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    podcasts = _load_podcasts()
    podcast = next((p for p in podcasts if p["id"] == podcast_id), None)
    if not podcast:
        abort(404)

    libraries = _load_library()
    lib = _ensure_lib(libraries, session["user_id"])

    followed = lib.setdefault("followed_podcasts", [])
    if podcast_id in followed:
        followed.remove(podcast_id)
        action = "unfollowed"
    else:
        followed.append(podcast_id)
        action = "followed"

    db.save_collection(SITE, "library", libraries)

    return jsonify({
        "action": action,
        "podcast_id": podcast_id,
        "podcast_title": podcast["title"],
    })


@blueprint.route("/api/follow/host", methods=["POST"])
def api_follow_host():
    """Follow a podcast by selecting a host from dropdown (follow_by_dropdown).

    Expects JSON: {"host": "Sarah Mitchell"}
    Finds the podcast with that host and follows it.
    """
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    data = request.get_json(silent=True) or {}
    host = data.get("host", "").strip()
    if not host:
        return jsonify({"error": "host required"}), 400

    podcasts = _load_podcasts()
    podcast = next((p for p in podcasts if p["host"].lower() == host.lower()), None)
    if not podcast:
        return jsonify({"error": f"No podcast by host '{host}'"}), 404

    libraries = _load_library()
    lib = _ensure_lib(libraries, session["user_id"])

    followed = lib.setdefault("followed_podcasts", [])
    if podcast["id"] not in followed:
        followed.append(podcast["id"])
        action = "followed"
    else:
        action = "already_followed"

    db.save_collection(SITE, "library", libraries)

    return jsonify({
        "action": action,
        "podcast_id": podcast["id"],
        "podcast_title": podcast["title"],
        "host": podcast["host"],
    })


@blueprint.route("/api/episodes/<int:episode_id>/like", methods=["POST"])
def api_like_episode(episode_id):
    """Toggle like on an episode (react_by_toggle)."""
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    episodes = _load_episodes()
    episode = next((e for e in episodes if e["id"] == episode_id), None)
    if not episode:
        abort(404)

    user_id = session["user_id"]
    liked_by = episode.setdefault("liked_by", [])

    if user_id in liked_by:
        liked_by.remove(user_id)
        action = "unliked"
    else:
        liked_by.append(user_id)
        action = "liked"

    db.save_collection(SITE, "episodes", episodes)

    return jsonify({
        "action": action,
        "episode_id": episode_id,
        "likes": len(liked_by),
    })


@blueprint.route("/api/audiobooks/<int:audiobook_id>/like", methods=["POST"])
def api_like_audiobook(audiobook_id):
    """Toggle like on an audiobook (react_by_toggle)."""
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    audiobooks = _load_audiobooks()
    audiobook = next((a for a in audiobooks if a["id"] == audiobook_id), None)
    if not audiobook:
        abort(404)

    user_id = session["user_id"]
    liked_by = audiobook.setdefault("liked_by", [])

    if user_id in liked_by:
        liked_by.remove(user_id)
        action = "unliked"
    else:
        liked_by.append(user_id)
        action = "liked"

    # Persist the updated liked_by list
    all_audiobooks = db.query(SITE, "audiobooks")
    for ab in all_audiobooks:
        if ab["id"] == audiobook_id:
            ab["liked_by"] = liked_by
            break
    db.save_collection(SITE, "audiobooks", all_audiobooks)

    return jsonify({
        "action": action,
        "audiobook_id": audiobook_id,
        "likes": len(liked_by),
    })


@blueprint.route("/api/episodes/<int:episode_id>/save", methods=["POST"])
def api_save_episode(episode_id):
    """Toggle save on an episode (save_by_toggle)."""
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    episodes = _load_episodes()
    episode = next((e for e in episodes if e["id"] == episode_id), None)
    if not episode:
        abort(404)

    libraries = _load_library()
    lib = _ensure_lib(libraries, session["user_id"])

    saved = lib.setdefault("saved_episodes", [])
    if episode_id in saved:
        saved.remove(episode_id)
        action = "unsaved"
    else:
        saved.append(episode_id)
        action = "saved"

    db.save_collection(SITE, "library", libraries)

    return jsonify({
        "action": action,
        "episode_id": episode_id,
    })


@blueprint.route("/api/audiobooks/<int:audiobook_id>/purchase", methods=["POST"])
def api_purchase_audiobook(audiobook_id):
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    audiobooks = _load_audiobooks()
    audiobook = next((a for a in audiobooks if a["id"] == audiobook_id), None)
    if not audiobook:
        abort(404)

    libraries = _load_library()
    lib = _ensure_lib(libraries, session["user_id"])

    purchased = lib.setdefault("purchased_audiobooks", [])
    if audiobook_id in purchased:
        return jsonify({"error": "Already purchased"}), 400

    purchased.append(audiobook_id)
    db.save_collection(SITE, "library", libraries)

    return jsonify({
        "action": "purchased",
        "audiobook_id": audiobook_id,
        "audiobook_title": audiobook["title"],
        "price": audiobook["price"],
    })


@blueprint.route("/api/playback/speed", methods=["POST"])
def api_playback_speed():
    """Set playback speed (play_by_playback)."""
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    data = request.get_json(silent=True) or {}
    speed = data.get("speed")
    if speed is None or not isinstance(speed, (int, float)):
        return jsonify({"error": "speed required (number)"}), 400
    if speed < 0.5 or speed > 3.0:
        return jsonify({"error": "speed must be between 0.5 and 3.0"}), 400

    libraries = _load_library()
    lib = _ensure_lib(libraries, session["user_id"])
    lib["playback_speed"] = speed
    db.save_item(SITE, "library", lib["id"], lib)

    return jsonify({
        "action": "speed_set",
        "speed": speed,
    })


def _item_duration_seconds(item_type, item):
    """Total playable length of an episode/audiobook in seconds."""
    if item_type == "episode":
        return int(item.get("duration_minutes", 0)) * 60
    return int(round(float(item.get("duration_hours", 0)) * 3600))


@blueprint.route("/api/playback/progress", methods=["POST"])
def api_playback_progress():
    """Persist real playback position/progress for an episode or audiobook.

    This is what makes "Continue Listening" / resume real: the player POSTs the
    listener's current position as they listen, seek, or pause, and we upsert the
    matching listen_history entry (keyed by user + item) with the new position,
    progress_percent, and last_played date.

    Body JSON:
      item_type: "episode" | "audiobook"   (required)
      item_id:   int                        (required)
      position:  number (seconds, >= 0)     (required)
      duration:  number (seconds, optional) -- overrides catalog length
      progress_percent: number (optional)   -- else derived from position/duration
    """
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    data = request.get_json(silent=True) or {}
    item_type = str(data.get("item_type", "")).strip()
    item_id = data.get("item_id")
    position = data.get("position")

    if item_type not in ("episode", "audiobook"):
        return jsonify({"error": "item_type must be 'episode' or 'audiobook'"}), 400
    if not isinstance(item_id, int):
        return jsonify({"error": "item_id required (int)"}), 400
    if not isinstance(position, (int, float)) or isinstance(position, bool) or position < 0:
        return jsonify({"error": "position required (number >= 0 seconds)"}), 400

    if item_type == "episode":
        item = next((e for e in _load_episodes() if e["id"] == item_id), None)
    else:
        item = next((a for a in _load_audiobooks() if a["id"] == item_id), None)
    if not item:
        return jsonify({"error": f"{item_type} not found"}), 404

    total_sec = _item_duration_seconds(item_type, item)
    duration_override = data.get("duration")
    if isinstance(duration_override, (int, float)) and not isinstance(duration_override, bool) and duration_override > 0:
        total_sec = duration_override

    # Clamp position to the item's length so a resume can never overshoot.
    if total_sec:
        position = min(position, total_sec)

    progress_percent = data.get("progress_percent")
    if not isinstance(progress_percent, (int, float)) or isinstance(progress_percent, bool):
        progress_percent = (position / total_sec * 100) if total_sec else 0
    progress_percent = int(max(0, min(100, round(progress_percent))))
    position = round(float(position), 2)

    libraries = _load_library()
    lib = _ensure_lib(libraries, session["user_id"])
    history = lib.setdefault("listen_history", [])

    entry = next(
        (h for h in history
         if h.get("item_type") == item_type and h.get("item_id") == item_id),
        None,
    )
    if entry is None:
        entry = {"item_type": item_type, "item_id": item_id}
        history.append(entry)
    entry["position"] = position
    entry["progress_percent"] = progress_percent
    entry["last_played"] = datetime.now().strftime("%Y-%m-%d")

    db.save_item(SITE, "library", lib["id"], lib)

    return jsonify({
        "action": "progress_saved",
        "item_type": item_type,
        "item_id": item_id,
        "position": position,
        "progress_percent": progress_percent,
        "last_played": entry["last_played"],
    })


@blueprint.route("/api/reviews", methods=["POST"])
def api_reviews_post():
    """Post a review with rating and free text (post_from_free_text, rate_by_slider)."""
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    data = request.get_json(silent=True) or {}
    item_type = data.get("item_type", "").strip()
    item_id = data.get("item_id")
    rating = data.get("rating")
    text = data.get("text", "").strip()

    if item_type not in ("podcast", "audiobook"):
        return jsonify({"error": "item_type must be 'podcast' or 'audiobook'"}), 400
    if item_id is None or rating is None:
        return jsonify({"error": "item_id and rating required"}), 400
    if not isinstance(rating, (int, float)) or rating < 1 or rating > 5:
        return jsonify({"error": "rating must be between 1 and 5"}), 400

    # Validate item exists
    if item_type == "podcast":
        items = _load_podcasts()
    else:
        items = _load_audiobooks()
    item = next((i for i in items if i["id"] == item_id), None)
    if not item:
        return jsonify({"error": f"{item_type} not found"}), 404

    reviews = _load_reviews()
    new_id = max((r["id"] for r in reviews), default=0) + 1
    new_review = {
        "id": new_id,
        "user_id": session["user_id"],
        "item_type": item_type,
        "item_id": item_id,
        "rating": rating,
        "text": text,
        "date": datetime.now().strftime("%Y-%m-%d"),
    }
    reviews.append(new_review)
    db.save_collection(SITE, "reviews", reviews)

    return jsonify(new_review), 201


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


@blueprint.route("/api/users/<int:user_id>")
def api_user(user_id):
    """Get user profile (for verifiers)."""
    user = _get_user(user_id)
    if not user:
        abort(404)
    safe = {k: v for k, v in user.items() if k != "password"}
    return jsonify(safe)
