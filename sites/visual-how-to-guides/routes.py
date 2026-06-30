"""StepVista How-To Guides — Visual step-by-step tutorial platform.

Data is stored in per-site SQLite tables and queried through app.db.

Macros supported:
  navigate_by_dropdown, navigate_by_route, search_by_query, search_by_semantic,
  filter_by_dropdown, filter_by_slider, sort_by_ranking, extract_from_table,
  extract_by_route, play_by_date_range, play_by_playback, post_from_free_text,
  react_by_toggle, rate_by_slider, follow_by_dropdown, save_by_toggle
"""
import json
import pathlib
from collections import Counter
from datetime import datetime

from flask import (
    Blueprint, abort, jsonify, redirect, render_template, request, session, url_for,
)
from app import DATA_SOURCES_DIR, db

SITE = "visual-how-to-guides"
SITE_DIR = pathlib.Path(__file__).resolve().parent
DATA_DIR = DATA_SOURCES_DIR / "visual-how-to-guides"   # kept for ratings/reactions (dict-shaped, not in schema)

blueprint = Blueprint(
    "visual-how-to-guides",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Difficulty numeric mapping (for filter_by_slider)
# ---------------------------------------------------------------------------
DIFFICULTY_LEVEL = {"easy": 1, "medium": 2, "hard": 3}
LEVEL_DIFFICULTY = {v: k for k, v in DIFFICULTY_LEVEL.items()}

# ---------------------------------------------------------------------------
# Data access helpers
# ---------------------------------------------------------------------------

def _load_guides():
    """Load all guides from the database."""
    return db.query(SITE, "guides")


def _save_guides(guides):
    """Save guides back to the guides collection."""
    db.save_collection(SITE, "guides", guides)


def _load_categories():
    return db.query(SITE, "categories")


def _load_users():
    return db.query(SITE, "users")


def _save_users(users):
    db.save_collection(SITE, "users", users)


def _load_bookmarks():
    return db.query(SITE, "bookmarks")


def _load_comments():
    return db.query(SITE, "comments")


def _load_ratings():
    """Ratings stored as { "<user_id>_<guide_id>": <score> }."""
    path = DATA_DIR / "ratings.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _save_ratings(ratings):
    (DATA_DIR / "ratings.json").write_text(json.dumps(ratings, indent=2))


def _load_reactions():
    """Reactions stored as { "<user_id>_<comment_id>": "helpful"|"unhelpful" }."""
    path = DATA_DIR / "reactions.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _save_reactions(reactions):
    (DATA_DIR / "reactions.json").write_text(json.dumps(reactions, indent=2))


def _get_user(user_id):
    users = _load_users()
    return next((u for u in users if u["id"] == user_id), None)


def _get_current_user():
    if "user_id" in session:
        return _get_user(session["user_id"])
    return None


def _recalc_category_counts():
    """Recalculate guide_count for each category based on actual guides."""
    guides = _load_guides()
    categories = _load_categories()
    counts = Counter(g["category"] for g in guides)
    for cat in categories:
        cat["guide_count"] = counts.get(cat["name"], 0)
    db.save_collection(SITE, "categories", categories)
    return categories


# ---------------------------------------------------------------------------
# Search helpers
# ---------------------------------------------------------------------------

def _keyword_score(query, guide):
    """Score a guide against query terms — used for semantic search ranking."""
    terms = query.lower().split()
    text = " ".join([
        guide.get("title", ""),
        guide.get("description", ""),
        guide.get("category", ""),
        guide.get("difficulty", ""),
    ]).lower()
    for step in guide.get("steps", []):
        text += " " + step.get("title", "").lower()
        text += " " + step.get("description", "").lower()
    return sum(1 for t in terms if t in text)


def _search_guides(guides, query, semantic=False):
    if not query:
        return guides
    q = query.lower().strip()
    if semantic:
        scored = [(g, _keyword_score(q, g)) for g in guides]
        scored = [(g, s) for g, s in scored if s > 0]
        scored.sort(key=lambda x: -x[1])
        return [g for g, _ in scored]
    else:
        results = []
        for g in guides:
            text = " ".join([
                g.get("title", ""),
                g.get("description", ""),
                g.get("category", ""),
                g.get("difficulty", ""),
            ]).lower()
            for step in g.get("steps", []):
                text += " " + step.get("title", "").lower()
            if q in text:
                results.append(g)
        return results


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    """Featured guides page -- shows top-rated and most-viewed guides."""
    guides = _load_guides()
    categories = _load_categories()
    user = _get_current_user()

    # Featured = top rated guides
    featured = sorted(guides, key=lambda g: g.get("rating", 0), reverse=True)[:6]
    # Most popular
    popular = sorted(guides, key=lambda g: g.get("views", 0), reverse=True)[:6]
    # Recently updated
    recent = sorted(guides, key=lambda g: g.get("updated_at", ""), reverse=True)[:6]

    return render_template(
        "visual-how-to-guides/index.html",
        featured=featured, popular=popular, recent=recent,
        categories=categories, user=user,
    )


@blueprint.route("/guides")
def guides_list():
    """Browse and filter all guides.

    Supports: category dropdown, difficulty dropdown, duration slider range,
    difficulty slider range, sort order, search query.
    """
    guides = _load_guides()
    categories = _load_categories()
    user = _get_current_user()

    # Filters
    q = request.args.get("q", "").strip()
    cat = request.args.get("category", "").strip()
    diff = request.args.get("difficulty", "").strip()
    sort = request.args.get("sort", "newest").strip()
    # filter_by_slider: duration range
    dur_min = request.args.get("duration_min", type=int)
    dur_max = request.args.get("duration_max", type=int)
    # filter_by_slider: difficulty level range (1=easy, 2=medium, 3=hard)
    diff_min = request.args.get("difficulty_min", type=int)
    diff_max = request.args.get("difficulty_max", type=int)

    results = list(guides)
    if q:
        results = _search_guides(results, q)
    if cat:
        results = [g for g in results if g["category"] == cat]
    if diff:
        results = [g for g in results if g["difficulty"] == diff]
    if dur_min is not None:
        results = [g for g in results if g.get("duration_minutes", 0) >= dur_min]
    if dur_max is not None:
        results = [g for g in results if g.get("duration_minutes", 0) <= dur_max]
    if diff_min is not None:
        results = [g for g in results if DIFFICULTY_LEVEL.get(g["difficulty"], 0) >= diff_min]
    if diff_max is not None:
        results = [g for g in results if DIFFICULTY_LEVEL.get(g["difficulty"], 0) <= diff_max]

    if sort == "newest":
        results.sort(key=lambda g: g.get("created_at", ""), reverse=True)
    elif sort == "oldest":
        results.sort(key=lambda g: g.get("created_at", ""))
    elif sort == "rating":
        results.sort(key=lambda g: g.get("rating", 0), reverse=True)
    elif sort == "popular":
        results.sort(key=lambda g: g.get("views", 0), reverse=True)
    elif sort == "duration_asc":
        results.sort(key=lambda g: g.get("duration_minutes", 0))
    elif sort == "duration_desc":
        results.sort(key=lambda g: g.get("duration_minutes", 0), reverse=True)

    return render_template(
        "visual-how-to-guides/guides.html",
        guides=results, categories=categories, user=user,
        q=q, cat=cat, diff=diff, sort=sort,
    )


@blueprint.route("/guide/<int:guide_id>")
def guide_detail(guide_id):
    """Step-by-step guide view with comments, rating, reactions."""
    guide = db.get_item(SITE, "guides", guide_id)
    if guide is None:
        abort(404)

    comments = db.query(SITE, "comments", where={"guide_id": guide_id}, sort="-date", limit=50)

    author = db.get_item(SITE, "users", guide.get("author_id"))

    user = _get_current_user()
    bookmarks = _load_bookmarks()
    is_bookmarked = any(
        b["user_id"] == session.get("user_id") and b["guide_id"] == guide_id
        for b in bookmarks
    )

    # User's current rating for this guide
    ratings = _load_ratings()
    user_rating = None
    if user:
        key = f"{user['id']}_{guide_id}"
        user_rating = ratings.get(key)

    # Related guides in the same category
    related = db.query(SITE, "guides", where={"category": guide["category"]}, sort="-rating", limit=5)
    related = [g for g in related if g["id"] != guide_id][:4]

    users = _load_users()

    return render_template(
        "visual-how-to-guides/guide_detail.html",
        guide=guide, comments=comments, author=author, user=user,
        is_bookmarked=is_bookmarked, related=related, users=users,
        user_rating=user_rating,
    )


@blueprint.route("/guide/<int:guide_id>/step/<int:step_num>")
def guide_step(guide_id, step_num):
    """Playback view: show a single step of a guide (play_by_playback).

    step_num is 1-based. Provides prev/next navigation.
    """
    guide = db.get_item(SITE, "guides", guide_id)
    if guide is None:
        abort(404)

    steps = guide.get("steps", [])
    if step_num < 1 or step_num > len(steps):
        abort(404)

    step = steps[step_num - 1]
    user = _get_current_user()

    return render_template(
        "visual-how-to-guides/step_playback.html",
        guide=guide, step=step, step_num=step_num,
        total_steps=len(steps), user=user,
    )


@blueprint.route("/category/<int:category_id>")
def category_page(category_id):
    """View guides in a specific category."""
    categories = _load_categories()
    category = next((c for c in categories if c["id"] == category_id), None)
    if category is None:
        abort(404)

    guides = _load_guides()
    filtered = [g for g in guides if g["category"] == category["name"]]
    filtered.sort(key=lambda g: g.get("rating", 0), reverse=True)

    user = _get_current_user()
    return render_template(
        "visual-how-to-guides/category.html",
        category=category, guides=filtered, categories=categories, user=user,
    )


@blueprint.route("/compare")
def compare_page():
    """Compare multiple guides side by side (extract_from_table)."""
    ids_str = request.args.get("ids", "")
    guides = _load_guides()
    selected = []
    if ids_str:
        ids = [int(x) for x in ids_str.split(",") if x.strip().isdigit()]
        selected = [g for g in guides if g["id"] in ids]
    user = _get_current_user()
    return render_template(
        "visual-how-to-guides/compare.html",
        guides=guides, selected=selected, user=user,
    )


@blueprint.route("/author/<int:author_id>")
def author_page(author_id):
    """Author profile page with follow button (follow_by_dropdown)."""
    users = _load_users()
    author = next((u for u in users if u["id"] == author_id), None)
    if not author:
        abort(404)

    guides = _load_guides()
    author_guides = [g for g in guides if g.get("author_id") == author_id]
    author_guides.sort(key=lambda g: g.get("created_at", ""), reverse=True)

    user = _get_current_user()
    is_following = False
    if user:
        is_following = author["display_name"] in user.get("followed_authors", [])

    return render_template(
        "visual-how-to-guides/author.html",
        author=author, guides=author_guides, user=user,
        is_following=is_following,
    )


@blueprint.route("/create", methods=["GET"])
def create_page():
    """Form to create a new guide."""
    categories = _load_categories()
    user = _get_current_user()
    return render_template(
        "visual-how-to-guides/create.html",
        categories=categories, user=user,
    )


@blueprint.route("/create", methods=["POST"])
def create_submit():
    """Handle guide creation from HTML form."""
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    category = request.form.get("category", "").strip()
    difficulty = request.form.get("difficulty", "easy").strip()
    duration = request.form.get("duration_minutes", "30")

    if not title or not description:
        categories = _load_categories()
        user = _get_current_user()
        return render_template(
            "visual-how-to-guides/create.html",
            categories=categories, user=user,
            error="Title and description are required.",
        )

    user = _get_current_user()
    author_id = user["id"] if user else 1

    # Parse steps from form
    steps = []
    step_idx = 1
    while True:
        step_title = request.form.get(f"step_{step_idx}_title", "").strip()
        step_desc = request.form.get(f"step_{step_idx}_description", "").strip()
        if not step_title:
            break
        steps.append({
            "order": step_idx,
            "title": step_title,
            "description": step_desc,
        })
        step_idx += 1

    guides = _load_guides()
    new_id = max((g["id"] for g in guides), default=0) + 1
    now = datetime.now().strftime("%Y-%m-%d")

    new_guide = {
        "id": new_id,
        "title": title,
        "description": description,
        "category": category,
        "author_id": author_id,
        "created_at": now,
        "updated_at": now,
        "difficulty": difficulty,
        "duration_minutes": int(duration) if duration.isdigit() else 30,
        "views": 0,
        "rating": 0.0,
        "steps": steps,
    }

    guides.append(new_guide)
    _save_guides(guides)
    _recalc_category_counts()

    return redirect(url_for("visual-how-to-guides.guide_detail", guide_id=new_id))


@blueprint.route("/bookmarks")
def bookmarks_page():
    """Show bookmarked guides for the current user."""
    user = _get_current_user()
    if not user:
        return redirect(url_for("visual-how-to-guides.login_page"))

    bookmarks = _load_bookmarks()
    user_bookmarks = [b for b in bookmarks if b["user_id"] == user["id"]]
    guides = _load_guides()
    guide_map = {g["id"]: g for g in guides}
    bookmarked_guides = []
    for bm in user_bookmarks:
        guide = guide_map.get(bm["guide_id"])
        if guide:
            bookmarked_guides.append({"guide": guide, "bookmarked_at": bm["bookmarked_at"]})

    categories = _load_categories()
    return render_template(
        "visual-how-to-guides/bookmarks.html",
        bookmarked_guides=bookmarked_guides, user=user, categories=categories,
    )


@blueprint.route("/search")
def search_page():
    """Search results page."""
    q = request.args.get("q", "").strip()
    guides = _load_guides()
    results = _search_guides(guides, q) if q else []
    categories = _load_categories()
    user = _get_current_user()
    return render_template(
        "visual-how-to-guides/search.html",
        results=results, q=q, categories=categories, user=user,
    )


@blueprint.route("/dashboard")
def dashboard():
    """User dashboard with bookmarks, followed authors, ratings."""
    user = _get_current_user()
    if not user:
        return redirect(url_for("visual-how-to-guides.login_page"))

    bookmarks = _load_bookmarks()
    user_bookmarks = [b for b in bookmarks if b["user_id"] == user["id"]]
    guides = _load_guides()
    guide_map = {g["id"]: g for g in guides}
    bookmarked_guides = [guide_map[b["guide_id"]] for b in user_bookmarks if b["guide_id"] in guide_map]

    followed = user.get("followed_authors", [])
    categories = _load_categories()

    return render_template(
        "visual-how-to-guides/dashboard.html",
        user=user, bookmarked_guides=bookmarked_guides,
        followed_authors=followed, categories=categories,
    )


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("visual-how-to-guides/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return render_template("visual-how-to-guides/login.html", error="Invalid username or password")
    session["user_id"] = user["id"]
    return redirect(url_for("visual-how-to-guides.index"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("visual-how-to-guides.index"))


# ---------------------------------------------------------------------------
# Form-based mutation routes (for browser automation compatibility)
# ---------------------------------------------------------------------------

@blueprint.route("/guide/<int:guide_id>/bookmark", methods=["POST"])
def form_bookmark(guide_id):
    """Toggle bookmark via HTML form (save_by_toggle)."""
    user = _get_current_user()
    if not user:
        return redirect(url_for("visual-how-to-guides.login_page"))

    bookmarks = _load_bookmarks()
    existing = next(
        (b for b in bookmarks if b["user_id"] == user["id"] and b["guide_id"] == guide_id),
        None,
    )
    if existing:
        bookmarks = [b for b in bookmarks if b["id"] != existing["id"]]
    else:
        new_id = max((b["id"] for b in bookmarks), default=0) + 1
        bookmarks.append({
            "id": new_id,
            "user_id": user["id"],
            "guide_id": guide_id,
            "bookmarked_at": datetime.now().strftime("%Y-%m-%d"),
        })
    db.save_collection(SITE, "bookmarks", bookmarks)
    return redirect(url_for("visual-how-to-guides.guide_detail", guide_id=guide_id))


@blueprint.route("/guide/<int:guide_id>/comment", methods=["POST"])
def form_comment(guide_id):
    """Add comment via HTML form (post_from_free_text)."""
    user = _get_current_user()
    if not user:
        return redirect(url_for("visual-how-to-guides.login_page"))

    text = request.form.get("text", "").strip()
    if not text:
        return redirect(url_for("visual-how-to-guides.guide_detail", guide_id=guide_id))

    guides = _load_guides()
    guide = next((g for g in guides if g["id"] == guide_id), None)
    if not guide:
        abort(404)

    comments = _load_comments()
    new_id = max((c["id"] for c in comments), default=0) + 1
    comments.append({
        "id": new_id,
        "guide_id": guide_id,
        "user_id": user["id"],
        "text": text,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "helpful_count": 0,
    })
    db.save_collection(SITE, "comments", comments)
    return redirect(url_for("visual-how-to-guides.guide_detail", guide_id=guide_id))


@blueprint.route("/guide/<int:guide_id>/rate", methods=["POST"])
def form_rate(guide_id):
    """Rate a guide via HTML form (rate_by_slider)."""
    user = _get_current_user()
    if not user:
        return redirect(url_for("visual-how-to-guides.login_page"))

    score_str = request.form.get("score", "").strip()
    try:
        score = float(score_str)
    except (ValueError, TypeError):
        return redirect(url_for("visual-how-to-guides.guide_detail", guide_id=guide_id))

    if score < 1 or score > 5:
        return redirect(url_for("visual-how-to-guides.guide_detail", guide_id=guide_id))

    ratings = _load_ratings()
    key = f"{user['id']}_{guide_id}"
    ratings[key] = score
    _save_ratings(ratings)

    # Recalculate guide average rating
    guide_ratings = [v for k, v in ratings.items() if k.endswith(f"_{guide_id}")]
    new_avg = round(sum(guide_ratings) / len(guide_ratings), 2) if guide_ratings else 0.0

    guides = _load_guides()
    guide = next((g for g in guides if g["id"] == guide_id), None)
    if guide:
        guide["rating"] = new_avg
        _save_guides(guides)

    return redirect(url_for("visual-how-to-guides.guide_detail", guide_id=guide_id))


@blueprint.route("/comment/<int:comment_id>/react", methods=["POST"])
def form_react(comment_id):
    """Toggle helpful/unhelpful on a comment (react_by_toggle)."""
    user = _get_current_user()
    if not user:
        return redirect(url_for("visual-how-to-guides.login_page"))

    reaction = request.form.get("reaction", "helpful").strip()
    if reaction not in ("helpful", "unhelpful"):
        reaction = "helpful"

    reactions = _load_reactions()
    key = f"{user['id']}_{comment_id}"

    if reactions.get(key) == reaction:
        # Toggle off
        del reactions[key]
        action = "removed"
    else:
        reactions[key] = reaction
        action = reaction

    _save_reactions(reactions)

    # Update helpful_count on the comment
    comments = _load_comments()
    comment = next((c for c in comments if c["id"] == comment_id), None)
    if comment:
        helpful = sum(1 for k, v in reactions.items() if k.endswith(f"_{comment_id}") and v == "helpful")
        comment["helpful_count"] = helpful
        db.save_collection(SITE, "comments", comments)
        guide_id = comment["guide_id"]
        return redirect(url_for("visual-how-to-guides.guide_detail", guide_id=guide_id))

    return redirect(url_for("visual-how-to-guides.index"))


@blueprint.route("/author/<int:author_id>/follow", methods=["POST"])
def form_follow_author(author_id):
    """Toggle follow on an author (follow_by_dropdown)."""
    user = _get_current_user()
    if not user:
        return redirect(url_for("visual-how-to-guides.login_page"))

    target = _get_user(author_id)
    if not target:
        abort(404)

    users = _load_users()
    current = next((u for u in users if u["id"] == user["id"]), None)
    if not current:
        return redirect(url_for("visual-how-to-guides.login_page"))

    followed = current.setdefault("followed_authors", [])
    author_name = target["display_name"]
    if author_name in followed:
        followed.remove(author_name)
    else:
        followed.append(author_name)
    _save_users(users)

    referrer = request.form.get("redirect_to", "")
    if referrer:
        return redirect(referrer)
    return redirect(url_for("visual-how-to-guides.author_page", author_id=author_id))


# ---------------------------------------------------------------------------
# API routes -- read
# ---------------------------------------------------------------------------

@blueprint.route("/api/guides", methods=["GET"])
def api_guides_list():
    """GET: list/filter guides.

    Supports: category, difficulty, search query, duration slider range,
    difficulty slider range, date range, sort.
    """
    guides = _load_guides()
    q = request.args.get("q", "").strip()
    cat = request.args.get("category", "").strip()
    diff = request.args.get("difficulty", "").strip()
    sort = request.args.get("sort", "newest").strip()
    limit = request.args.get("limit", type=int)
    # filter_by_slider
    dur_min = request.args.get("duration_min", type=int)
    dur_max = request.args.get("duration_max", type=int)
    diff_min = request.args.get("difficulty_min", type=int)
    diff_max = request.args.get("difficulty_max", type=int)
    # play_by_date_range
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    results = list(guides)
    if q:
        results = _search_guides(results, q)
    if cat:
        results = [g for g in results if g["category"] == cat]
    if diff:
        results = [g for g in results if g["difficulty"] == diff]
    if dur_min is not None:
        results = [g for g in results if g.get("duration_minutes", 0) >= dur_min]
    if dur_max is not None:
        results = [g for g in results if g.get("duration_minutes", 0) <= dur_max]
    if diff_min is not None:
        results = [g for g in results if DIFFICULTY_LEVEL.get(g["difficulty"], 0) >= diff_min]
    if diff_max is not None:
        results = [g for g in results if DIFFICULTY_LEVEL.get(g["difficulty"], 0) <= diff_max]
    if date_from:
        results = [g for g in results if g.get("created_at", "") >= date_from]
    if date_to:
        results = [g for g in results if g.get("created_at", "") <= date_to]

    if sort == "newest":
        results.sort(key=lambda g: g.get("created_at", ""), reverse=True)
    elif sort == "oldest":
        results.sort(key=lambda g: g.get("created_at", ""))
    elif sort == "rating":
        results.sort(key=lambda g: g.get("rating", 0), reverse=True)
    elif sort == "popular":
        results.sort(key=lambda g: g.get("views", 0), reverse=True)
    elif sort == "duration_asc":
        results.sort(key=lambda g: g.get("duration_minutes", 0))
    elif sort == "duration_desc":
        results.sort(key=lambda g: g.get("duration_minutes", 0), reverse=True)
    elif sort == "title":
        results.sort(key=lambda g: g.get("title", "").lower())

    if limit:
        results = results[:limit]
    return jsonify(results)


@blueprint.route("/api/guides/<int:guide_id>")
def api_guide_detail(guide_id):
    guides = _load_guides()
    guide = next((g for g in guides if g["id"] == guide_id), None)
    if guide is None:
        abort(404)
    return jsonify(guide)


@blueprint.route("/api/guides/<int:guide_id>/steps")
def api_guide_steps(guide_id):
    """List all steps for a guide (play_by_playback support)."""
    guides = _load_guides()
    guide = next((g for g in guides if g["id"] == guide_id), None)
    if guide is None:
        abort(404)
    return jsonify(guide.get("steps", []))


@blueprint.route("/api/guides/<int:guide_id>/steps/<int:step_num>")
def api_guide_step(guide_id, step_num):
    """Get a single step by number (1-based) for playback."""
    guides = _load_guides()
    guide = next((g for g in guides if g["id"] == guide_id), None)
    if guide is None:
        abort(404)
    steps = guide.get("steps", [])
    if step_num < 1 or step_num > len(steps):
        abort(404)
    step = steps[step_num - 1]
    return jsonify({
        "guide_id": guide_id,
        "step_num": step_num,
        "total_steps": len(steps),
        "step": step,
    })


@blueprint.route("/api/guides/<int:guide_id>/comments", methods=["GET"])
def api_guide_comments_get(guide_id):
    comments = _load_comments()
    guide_comments = [c for c in comments if c["guide_id"] == guide_id]
    guide_comments.sort(key=lambda c: c.get("date", ""), reverse=True)
    return jsonify(guide_comments)


@blueprint.route("/api/categories")
def api_categories():
    return jsonify(_recalc_category_counts())


@blueprint.route("/api/categories/<int:cat_id>/guides")
def api_category_guides(cat_id):
    """Get guides in a specific category by category ID."""
    categories = _load_categories()
    category = next((c for c in categories if c["id"] == cat_id), None)
    if category is None:
        abort(404)
    guides = _load_guides()
    filtered = [g for g in guides if g["category"] == category["name"]]
    filtered.sort(key=lambda g: g.get("rating", 0), reverse=True)
    return jsonify(filtered)


@blueprint.route("/api/bookmarks")
def api_bookmarks():
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    bookmarks = _load_bookmarks()
    return jsonify([b for b in bookmarks if b["user_id"] == user["id"]])


@blueprint.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    guides = _load_guides()
    results = _search_guides(guides, q) if q else []
    return jsonify(results)


@blueprint.route("/api/search/semantic")
def api_semantic_search():
    """Semantic search — ranks results by keyword overlap score."""
    q = request.args.get("q", "").strip()
    guides = _load_guides()
    results = _search_guides(guides, q, semantic=True) if q else []
    return jsonify(results)


@blueprint.route("/api/stats")
def api_stats():
    guides = _load_guides()
    categories = _load_categories()
    comments = _load_comments()
    users = _load_users()
    bookmarks = _load_bookmarks()

    total_views = sum(g.get("views", 0) for g in guides)
    avg_rating = (
        sum(g.get("rating", 0) for g in guides) / len(guides) if guides else 0
    )
    difficulty_counts = {}
    for g in guides:
        d = g.get("difficulty", "unknown")
        difficulty_counts[d] = difficulty_counts.get(d, 0) + 1

    return jsonify({
        "total_guides": len(guides),
        "total_categories": len(categories),
        "total_comments": len(comments),
        "total_users": len(users),
        "total_bookmarks": len(bookmarks),
        "total_views": total_views,
        "average_rating": round(avg_rating, 2),
        "difficulty_distribution": difficulty_counts,
    })


@blueprint.route("/api/compare")
def api_compare():
    """Compare guides side by side (extract_from_table)."""
    ids_str = request.args.get("ids", "")
    ids = [int(x) for x in ids_str.split(",") if x.strip().isdigit()]
    guides = _load_guides()
    return jsonify([g for g in guides if g["id"] in ids])


@blueprint.route("/api/authors")
def api_authors():
    """List all authors (users who have authored guides)."""
    users = _load_users()
    guides = _load_guides()
    author_ids = set(g.get("author_id") for g in guides)
    authors = [u for u in users if u["id"] in author_ids]
    return jsonify([{k: v for k, v in a.items() if k != "password"} for a in authors])


@blueprint.route("/api/authors/<int:author_id>")
def api_author(author_id):
    """Get author details and their guides."""
    user = _get_user(author_id)
    if not user:
        abort(404)
    guides = _load_guides()
    author_guides = [g for g in guides if g.get("author_id") == author_id]
    return jsonify({
        "author": {k: v for k, v in user.items() if k != "password"},
        "guides": author_guides,
    })


@blueprint.route("/api/users/<int:user_id>")
def api_user(user_id):
    """Get user details (excluding password)."""
    user = _get_user(user_id)
    if not user:
        abort(404)
    return jsonify({k: v for k, v in user.items() if k != "password"})


# ---------------------------------------------------------------------------
# API routes -- write
# ---------------------------------------------------------------------------

@blueprint.route("/api/guides", methods=["POST"])
def api_create_guide():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    description = data.get("description", "").strip()
    category = data.get("category", "").strip()
    difficulty = data.get("difficulty", "easy").strip()
    duration = data.get("duration_minutes", 30)
    steps = data.get("steps", [])

    if not title or not description:
        return jsonify({"error": "title and description required"}), 400

    user = _get_current_user()
    author_id = data.get("author_id", user["id"] if user else 1)

    guides = _load_guides()
    new_id = max((g["id"] for g in guides), default=0) + 1
    now = datetime.now().strftime("%Y-%m-%d")

    # Normalize steps
    normalized_steps = []
    for i, s in enumerate(steps, 1):
        normalized_steps.append({
            "order": i,
            "title": s.get("title", f"Step {i}"),
            "description": s.get("description", ""),
        })

    new_guide = {
        "id": new_id,
        "title": title,
        "description": description,
        "category": category,
        "author_id": author_id,
        "created_at": now,
        "updated_at": now,
        "difficulty": difficulty,
        "duration_minutes": int(duration) if isinstance(duration, str) and duration.isdigit() else duration,
        "views": 0,
        "rating": 0.0,
        "steps": normalized_steps,
    }

    guides.append(new_guide)
    _save_guides(guides)
    _recalc_category_counts()
    return jsonify(new_guide), 201


@blueprint.route("/api/guides/<int:guide_id>/bookmark", methods=["POST"])
def api_bookmark(guide_id):
    """Toggle bookmark (save_by_toggle)."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401

    guides = _load_guides()
    guide = next((g for g in guides if g["id"] == guide_id), None)
    if not guide:
        abort(404)

    bookmarks = _load_bookmarks()
    existing = next(
        (b for b in bookmarks if b["user_id"] == user["id"] and b["guide_id"] == guide_id),
        None,
    )
    if existing:
        bookmarks = [b for b in bookmarks if b["id"] != existing["id"]]
        action = "unbookmarked"
    else:
        new_id = max((b["id"] for b in bookmarks), default=0) + 1
        bookmarks.append({
            "id": new_id,
            "user_id": user["id"],
            "guide_id": guide_id,
            "bookmarked_at": datetime.now().strftime("%Y-%m-%d"),
        })
        action = "bookmarked"
    db.save_collection(SITE, "bookmarks", bookmarks)
    return jsonify({"action": action, "guide_id": guide_id})


@blueprint.route("/api/guides/<int:guide_id>/comments", methods=["POST"])
def api_guide_comments_post(guide_id):
    """Post a comment (post_from_free_text)."""
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "text required"}), 400

    user = _get_current_user()
    user_id = data.get("user_id", user["id"] if user else None)
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    guides = _load_guides()
    guide = next((g for g in guides if g["id"] == guide_id), None)
    if not guide:
        abort(404)

    comments = _load_comments()
    new_id = max((c["id"] for c in comments), default=0) + 1
    new_comment = {
        "id": new_id,
        "guide_id": guide_id,
        "user_id": user_id,
        "text": text,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "helpful_count": 0,
    }
    comments.append(new_comment)
    db.save_collection(SITE, "comments", comments)
    return jsonify(new_comment), 201


@blueprint.route("/api/guides/<int:guide_id>/rate", methods=["POST"])
def api_rate_guide(guide_id):
    """Rate a guide 1-5 (rate_by_slider). Recalculates average."""
    data = request.get_json(silent=True) or {}
    user = _get_current_user()
    user_id = data.get("user_id", user["id"] if user else None)
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    score = data.get("score")
    try:
        score = float(score)
    except (ValueError, TypeError):
        return jsonify({"error": "score required (1-5)"}), 400
    if score < 1 or score > 5:
        return jsonify({"error": "score must be between 1 and 5"}), 400

    guides = _load_guides()
    guide = next((g for g in guides if g["id"] == guide_id), None)
    if not guide:
        abort(404)

    ratings = _load_ratings()
    key = f"{user_id}_{guide_id}"
    ratings[key] = score
    _save_ratings(ratings)

    # Recalculate guide average
    guide_ratings = [v for k, v in ratings.items() if k.endswith(f"_{guide_id}")]
    new_avg = round(sum(guide_ratings) / len(guide_ratings), 2) if guide_ratings else 0.0

    guide["rating"] = new_avg
    _save_guides(guides)

    return jsonify({"action": "rated", "guide_id": guide_id, "score": score, "new_average": new_avg})


@blueprint.route("/api/comments/<int:comment_id>/react", methods=["POST"])
def api_react_comment(comment_id):
    """Toggle helpful/unhelpful reaction on a comment (react_by_toggle)."""
    data = request.get_json(silent=True) or {}
    user = _get_current_user()
    user_id = data.get("user_id", user["id"] if user else None)
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    reaction = data.get("reaction", "helpful").strip()
    if reaction not in ("helpful", "unhelpful"):
        return jsonify({"error": "reaction must be 'helpful' or 'unhelpful'"}), 400

    reactions = _load_reactions()
    key = f"{user_id}_{comment_id}"

    if reactions.get(key) == reaction:
        del reactions[key]
        action = "removed"
    else:
        reactions[key] = reaction
        action = reaction

    _save_reactions(reactions)

    # Update helpful_count
    comments = _load_comments()
    comment = next((c for c in comments if c["id"] == comment_id), None)
    if comment:
        helpful = sum(1 for k, v in reactions.items() if k.endswith(f"_{comment_id}") and v == "helpful")
        comment["helpful_count"] = helpful
        db.save_collection(SITE, "comments", comments)

    return jsonify({"action": action, "comment_id": comment_id, "reaction": reaction})


@blueprint.route("/api/users/<int:user_id>/follow", methods=["POST"])
def api_follow_author(user_id):
    """Toggle follow on an author by name (follow_by_dropdown)."""
    data = request.get_json(silent=True) or {}
    author = data.get("author", "").strip()
    if not author:
        return jsonify({"error": "author name required"}), 400

    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)

    followed = user.setdefault("followed_authors", [])
    if author in followed:
        followed.remove(author)
        action = "unfollowed"
    else:
        followed.append(author)
        action = "followed"
    _save_users(users)
    return jsonify({"action": action, "author": author, "total_followed": len(followed)})


@blueprint.route("/api/users/<int:user_id>/bookmark", methods=["POST"])
def api_user_bookmark(user_id):
    """Bookmark/unbookmark a guide for a specific user (save_by_toggle)."""
    data = request.get_json(silent=True) or {}
    guide_id = data.get("guide_id")
    if guide_id is None:
        return jsonify({"error": "guide_id required"}), 400

    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)

    bookmarks = _load_bookmarks()
    existing = next(
        (b for b in bookmarks if b["user_id"] == user_id and b["guide_id"] == guide_id),
        None,
    )
    if existing:
        bookmarks = [b for b in bookmarks if b["id"] != existing["id"]]
        action = "unbookmarked"
    else:
        new_id = max((b["id"] for b in bookmarks), default=0) + 1
        bookmarks.append({
            "id": new_id,
            "user_id": user_id,
            "guide_id": guide_id,
            "bookmarked_at": datetime.now().strftime("%Y-%m-%d"),
        })
        action = "bookmarked"
    db.save_collection(SITE, "bookmarks", bookmarks)
    return jsonify({"action": action, "guide_id": guide_id})


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
