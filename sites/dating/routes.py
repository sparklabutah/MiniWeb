"""Dating -- Tinder/Bumble/Hinge-style dating platform (HeartLink / Spark).

Data interpreter: loads JSON data files, respects config, provides matching
and messaging logic through Flask routes.
"""
import pathlib
from datetime import datetime

from flask import (Blueprint, Response, abort, jsonify, redirect, render_template,
                   request, session, url_for)
from app import db
from app.events import emit
from app.handlers.email_handler import _add_email

SITE = "dating"
SITE_DIR = pathlib.Path(__file__).resolve().parent
blueprint = Blueprint(
    "dating",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def _load_users():
    return db.query(SITE, "users")


def _load_matches():
    return db.query(SITE, "matches")


def _load_messages():
    # Full-table load — only for the public stats/export endpoints.
    return db.query(SITE, "messages")


def _load_likes():
    return db.query(SITE, "likes")


def _get_user(user_id):
    return db.get_item(SITE, "users", user_id)


def _get_current_user():
    if "user_id" not in session:
        return None
    return _get_user(session["user_id"])


def _safe_user(u):
    """Return user dict without password."""
    return {k: v for k, v in u.items() if k != "password"}


# ---------------------------------------------------------------------------
# Matching logic helpers
# ---------------------------------------------------------------------------

def _get_prefs(user):
    """Effective matching preferences for a user.

    Seeded profiles store preferences nested in the `preferences` dict
    (keys: min_age, max_age, gender_pref, max_distance_miles); profile edits
    write top-level *_pref keys. Top-level keys win when both exist.
    """
    nested = user.get("preferences")
    if not isinstance(nested, dict):
        nested = {}
    return {
        "gender_pref": user.get("gender_pref") or nested.get("gender_pref") or "any",
        "min_age": user.get("min_age_pref") or nested.get("min_age") or 18,
        "max_age": user.get("max_age_pref") or nested.get("max_age") or 99,
        "max_distance_miles": user.get("max_distance_pref") or nested.get("max_distance_miles"),
    }


def _distance_miles(a, b):
    """Great-circle distance between two users, or None if either lacks coords."""
    try:
        lat1, lng1, lat2, lng2 = float(a["lat"]), float(a["lng"]), float(b["lat"]), float(b["lng"])
    except (KeyError, TypeError, ValueError):
        return None
    from math import asin, cos, radians, sin, sqrt
    lat1, lng1, lat2, lng2 = map(radians, (lat1, lng1, lat2, lng2))
    h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lng2 - lng1) / 2) ** 2
    return 2 * 3958.8 * asin(sqrt(h))


def _next_id(collection):
    """Next free integer id for a collection (overlay-aware)."""
    newest = db.query(SITE, collection, sort="-id", limit=1)
    return (newest[0].get("id", 0) if newest else 0) + 1


def _matches_preferences(viewer, candidate):
    """Check if candidate fits viewer's preferences (age range, gender)."""
    prefs = _get_prefs(viewer)
    if prefs["gender_pref"] != "any" and candidate["gender"] != prefs["gender_pref"]:
        return False
    age = candidate["age"]
    if age < prefs["min_age"] or age > prefs["max_age"]:
        return False
    max_dist = prefs["max_distance_miles"]
    if max_dist:
        dist = _distance_miles(viewer, candidate)
        if dist is not None and dist > max_dist:
            return False
    return True


def _get_user_matches(user_id):
    """Get all active matches for a user."""
    matches = _load_matches()
    return [m for m in matches if m["status"] == "active" and
            (m["user1_id"] == user_id or m["user2_id"] == user_id)]


def _get_match_between(user1_id, user2_id):
    """Find a match between two users."""
    matches = _load_matches()
    for m in matches:
        if m["status"] == "active":
            if (m["user1_id"] == user1_id and m["user2_id"] == user2_id) or \
               (m["user1_id"] == user2_id and m["user2_id"] == user1_id):
                return m
    return None


def _get_discover_profiles(user_id):
    """Get profiles the user can discover (not already liked/matched, matching prefs)."""
    users = _load_users()
    my_likes = db.query(SITE, "likes", where={"from_user_id": user_id})
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        return []

    # IDs the user has already liked or passed on
    already_acted = {l["to_user_id"] for l in my_likes}
    already_acted.add(user_id)  # exclude self

    candidates = []
    for u in users:
        if u["id"] in already_acted:
            continue
        if _matches_preferences(user, u):
            candidates.append(u)

    return candidates


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    user = _get_current_user()
    if not user:
        return redirect(url_for("dating.login_page"))
    profiles = _get_discover_profiles(user["id"])

    min_age = request.args.get("min_age", type=int)
    max_age = request.args.get("max_age", type=int)
    if min_age is not None:
        profiles = [p for p in profiles if p.get("age", 0) >= min_age]
    if max_age is not None:
        profiles = [p for p in profiles if p.get("age", 0) <= max_age]

    looking_for = request.args.get("looking_for", "").strip()
    if looking_for:
        profiles = [p for p in profiles if p.get("looking_for") == looking_for]

    interest = request.args.get("interest", "").strip().lower()
    if interest:
        profiles = [p for p in profiles
                    if any(interest in i.lower() for i in p.get("interests", []))]

    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    if date_from:
        profiles = [p for p in profiles if (p.get("joined_date") or "")[:10] >= date_from]
    if date_to:
        profiles = [p for p in profiles if (p.get("joined_date") or "")[:10] <= date_to]

    sort = request.args.get("sort", "")
    if sort == "age_asc":
        profiles.sort(key=lambda p: p.get("age", 0))
    elif sort == "age_desc":
        profiles.sort(key=lambda p: p.get("age", 0), reverse=True)
    elif sort == "name":
        profiles.sort(key=lambda p: p.get("name", "").lower())
    elif sort == "newest":
        profiles.sort(key=lambda p: p.get("joined_date") or "", reverse=True)

    return render_template("dating/index.html", user=user, profiles=profiles,
                           current_profile=profiles[0] if profiles else None)


@blueprint.route("/profiles")
def profiles_list():
    """Paginated text-based list of all profiles. Supports filtering."""
    user = _get_current_user()

    # Build SQL filter
    where = {}
    gender = request.args.get("gender")
    if gender:
        where["gender"] = gender

    looking_for = request.args.get("looking_for")
    if looking_for:
        where["looking_for"] = looking_for

    interest = request.args.get("interest")
    min_age = request.args.get("min_age", type=int)
    max_age = request.args.get("max_age", type=int)

    q = request.args.get("q", "").strip().lower()
    interests_checked = [i.lower() for i in request.args.getlist("interests")]
    within = request.args.get("within", type=int)
    sort = request.args.get("sort", "")

    # For simple exact-match filters, use db.query; for range/list filters, load filtered set
    # (users table is small — <100 rows — so Python-side refinement is acceptable)
    users = db.query(SITE, "users", where=where if where else None)

    # Apply Python-side filters for complex conditions (interest in list, age range)
    if interest:
        users = [u for u in users if interest.lower() in [i.lower() for i in u.get("interests", [])]]
    if interests_checked:
        users = [u for u in users
                 if any(i.lower() in interests_checked for i in u.get("interests", []))]
    if min_age is not None:
        users = [u for u in users if u.get("age", 0) >= min_age]
    if max_age is not None:
        users = [u for u in users if u.get("age", 0) <= max_age]
    if q:
        def _haystack(u):
            return " ".join([u.get("name", ""), u.get("username", ""), u.get("bio", ""),
                             u.get("location", ""), " ".join(u.get("interests", []))]).lower()
        users = [u for u in users if all(term in _haystack(u) for term in q.split())]

    # Distance from the logged-in user (needs coordinates on both sides)
    distances = {}
    if user:
        for u in users:
            distances[u["id"]] = _distance_miles(user, u) if u["id"] != user["id"] else 0.0
    if within is not None and user:
        users = [u for u in users
                 if distances.get(u["id"]) is not None and distances[u["id"]] <= within]

    if sort == "nearest" and user:
        users.sort(key=lambda u: (distances.get(u["id"]) is None, distances.get(u["id"]) or 0))
    elif sort == "age":
        users.sort(key=lambda u: u.get("age", 0))
    elif sort == "newest":
        users.sort(key=lambda u: u.get("joined_date") or "", reverse=True)
    elif sort == "name":
        users.sort(key=lambda u: u.get("name", "").lower())

    # Pagination
    page = request.args.get("page", 1, type=int)
    per_page = 20
    total = len(users)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    end = start + per_page
    page_users = users[start:end]

    # Query args to preserve in pagination links (everything except page)
    filter_args = {k: v for k, v in request.args.to_dict(flat=False).items() if k != "page"}

    return render_template("dating/profiles.html", user=user,
                           profiles=page_users, total=total,
                           page=page, total_pages=total_pages,
                           distances=distances, filter_args=filter_args,
                           gender=gender or "", looking_for=looking_for or "",
                           interest=interest or "", q=q, within=within or "",
                           sort=sort,
                           min_age=min_age or "", max_age=max_age or "")


@blueprint.route("/profile/<int:profile_id>")
def profile_detail(profile_id):
    user = _get_current_user()
    profile = _get_user(profile_id)
    if not profile:
        abort(404)
    # Check if they are matched
    is_matched = False
    if user:
        match = _get_match_between(user["id"], profile_id)
        is_matched = match is not None
    # Count shared interests
    shared_interests = []
    if user:
        shared_interests = [i for i in profile.get("interests", [])
                            if i in user.get("interests", [])]
    return render_template("dating/profile.html", user=user, profile=profile,
                           is_matched=is_matched, shared_interests=shared_interests)


@blueprint.route("/matches")
def matches_page():
    user = _get_current_user()
    if not user:
        return redirect(url_for("dating.login_page"))
    user_matches = _get_user_matches(user["id"])
    users = _load_users()
    user_map = {u["id"]: u for u in users}

    match_data = []
    for m in user_matches:
        other_id = m["user2_id"] if m["user1_id"] == user["id"] else m["user1_id"]
        other = user_map.get(other_id)
        if not other:
            continue
        match_msgs = db.query(SITE, "messages", where={"match_id": m["id"]},
                              sort="timestamp")
        last_msg = match_msgs[-1] if match_msgs else None
        unread = sum(1 for msg in match_msgs
                     if msg["sender_id"] != user["id"] and not msg.get("read", True))
        match_data.append({
            "match": m,
            "other": other,
            "last_message": last_msg,
            "unread_count": unread,
        })
    # Sort by last message timestamp (most recent first)
    match_data.sort(key=lambda x: x["last_message"]["timestamp"] if x["last_message"] else x["match"]["matched_date"], reverse=True)
    return render_template("dating/matches.html", user=user, match_data=match_data)


@blueprint.route("/conversation/<int:match_id>")
def conversation(match_id):
    user = _get_current_user()
    if not user:
        return redirect(url_for("dating.login_page"))
    matches = _load_matches()
    match = next((m for m in matches if m["id"] == match_id), None)
    if not match or match["status"] != "active":
        abort(404)
    if user["id"] not in (match["user1_id"], match["user2_id"]):
        abort(403)
    other_id = match["user2_id"] if match["user1_id"] == user["id"] else match["user1_id"]
    other = _get_user(other_id)
    match_msgs = db.query(SITE, "messages", where={"match_id": match_id},
                          sort="timestamp")
    # Mark messages as read
    for msg in match_msgs:
        if msg["sender_id"] != user["id"] and not msg.get("read"):
            msg["read"] = True
            db.save_item(SITE, "messages", msg["id"], msg)
    return render_template("dating/conversation.html", user=user, other=other,
                           match=match, messages=match_msgs)


@blueprint.route("/edit-profile")
def edit_profile():
    user = _get_current_user()
    if not user:
        return redirect(url_for("dating.login_page"))
    return render_template("dating/edit_profile.html", user=user,
                           prefs=_get_prefs(user))


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("dating/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return render_template("dating/login.html",
                               error="Invalid username or password")
    session["user_id"] = user["id"]
    emit("signup", user_id=user["id"], site_name="dating", username=request.form.get("username", ""), password=request.form.get("password", ""), email="")
    return redirect(url_for("dating.index"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("dating.login_page"))


@blueprint.route("/register", methods=["GET"])
def register_page():
    return render_template("dating/register.html", error=None, form={})


@blueprint.route("/register", methods=["POST"])
def register_submit():
    form = {k: request.form.get(k, "").strip() for k in
            ("username", "password", "name", "age", "gender", "location",
             "bio", "interests", "looking_for", "gender_pref")}
    error = None
    if not form["username"] or not form["password"] or not form["name"]:
        error = "Username, password and name are required"
    elif not form["age"].isdigit() or not 18 <= int(form["age"]) <= 99:
        error = "Age must be a number between 18 and 99"
    elif any(u["username"] == form["username"] for u in _load_users()):
        error = "That username is already taken"
    if error:
        return render_template("dating/register.html", error=error, form=form)

    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    new_id = _next_id("users")
    user = {
        "id": new_id,
        "root_user_id": 0,
        "username": form["username"],
        "password": form["password"],
        "name": form["name"],
        "age": int(form["age"]),
        "gender": form["gender"] or "other",
        "bio": form["bio"],
        "location": form["location"],
        "interests": [i.strip() for i in form["interests"].split(",") if i.strip()],
        "looking_for": form["looking_for"] or "relationship",
        "preferences": {"gender_pref": form["gender_pref"] or "any",
                        "min_age": 18, "max_age": 99},
        "photos": [],
        "verified": 0,
        "joined_date": now,
        "last_active": now,
    }
    db.save_item(SITE, "users", new_id, user)
    session["user_id"] = new_id
    emit("signup", user_id=new_id, site_name="dating",
         username=form["username"], password=form["password"], email="")
    return redirect(url_for("dating.index"))


@blueprint.route("/likes")
def likes_page():
    """Pending likes received by the current user ('Likes You')."""
    user = _get_current_user()
    if not user:
        return redirect(url_for("dating.login_page"))
    pending = db.query(SITE, "likes", where={"to_user_id": user["id"],
                                             "status": "pending"},
                       sort="-date")
    user_map = {u["id"]: u for u in _load_users()}
    likers = []
    for like in pending:
        liker = user_map.get(like["from_user_id"])
        if liker:
            likers.append({"like": like, "profile": liker})
    return render_template("dating/likes.html", user=user, likers=likers)


# ---------------------------------------------------------------------------
# Form mutation routes
# ---------------------------------------------------------------------------

def _do_like(user_id, profile_id):
    """Record a like; create a match if it's mutual.

    Returns ("already", None), ("liked", None) or ("matched", match_id).
    """
    my_likes = db.query(SITE, "likes", where={"from_user_id": user_id})
    if any(l["to_user_id"] == profile_id for l in my_likes):
        return "already", None

    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    their_likes = db.query(SITE, "likes", where={"from_user_id": profile_id})
    reverse = next((l for l in their_likes
                    if l["to_user_id"] == user_id and l["status"] == "pending"), None)

    new_id = _next_id("likes")
    if reverse:
        reverse["status"] = "matched"
        db.save_item(SITE, "likes", reverse["id"], reverse)
        db.save_item(SITE, "likes", new_id,
                     {"id": new_id, "from_user_id": user_id,
                      "to_user_id": profile_id, "date": now, "status": "matched"})
        match_id = _next_id("matches")
        db.save_item(SITE, "matches", match_id,
                     {"id": match_id, "user1_id": user_id, "user2_id": profile_id,
                      "matched_date": now, "status": "active"})
        return "matched", match_id

    db.save_item(SITE, "likes", new_id,
                 {"id": new_id, "from_user_id": user_id,
                  "to_user_id": profile_id, "date": now, "status": "pending"})
    return "liked", None


def _do_pass(user_id, profile_id):
    """Record a pass unless the user already acted on this profile."""
    my_likes = db.query(SITE, "likes", where={"from_user_id": user_id})
    if any(l["to_user_id"] == profile_id for l in my_likes):
        return
    new_id = _next_id("likes")
    db.save_item(SITE, "likes", new_id,
                 {"id": new_id, "from_user_id": user_id, "to_user_id": profile_id,
                  "date": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                  "status": "passed"})


@blueprint.route("/like/<int:profile_id>", methods=["POST"])
def form_like(profile_id):
    user = _get_current_user()
    if not user:
        return redirect(url_for("dating.login_page"))
    _do_like(user["id"], profile_id)
    return redirect(request.form.get("next") or url_for("dating.index"))


@blueprint.route("/pass/<int:profile_id>", methods=["POST"])
def form_pass(profile_id):
    user = _get_current_user()
    if not user:
        return redirect(url_for("dating.login_page"))
    _do_pass(user["id"], profile_id)
    return redirect(request.form.get("next") or url_for("dating.index"))


@blueprint.route("/unmatch/<int:match_id>", methods=["POST"])
def form_unmatch(match_id):
    user = _get_current_user()
    if not user:
        return redirect(url_for("dating.login_page"))
    match = db.get_item(SITE, "matches", match_id)
    if not match or match["status"] != "active":
        abort(404)
    if user["id"] not in (match["user1_id"], match["user2_id"]):
        abort(403)
    match["status"] = "unmatched"
    db.save_item(SITE, "matches", match_id, match)
    return redirect(url_for("dating.matches_page"))


@blueprint.route("/report/<int:profile_id>", methods=["POST"])
def form_report_profile(profile_id):
    user = _get_current_user()
    if not user:
        return redirect(url_for("dating.login_page"))
    target = _get_user(profile_id)
    if not target:
        abort(404)
    target["reported"] = True
    target["report_reason"] = request.form.get("reason", "").strip()
    db.save_item(SITE, "users", profile_id, target)
    return redirect(url_for("dating.profile_detail", profile_id=profile_id))


@blueprint.route("/block/<int:profile_id>", methods=["POST"])
def form_block_profile(profile_id):
    user = _get_current_user()
    if not user:
        return redirect(url_for("dating.login_page"))
    target = _get_user(profile_id)
    if not target:
        abort(404)
    target["blocked"] = not target.get("blocked", False)
    db.save_item(SITE, "users", profile_id, target)
    return redirect(url_for("dating.profile_detail", profile_id=profile_id))


@blueprint.route("/send-message/<int:match_id>", methods=["POST"])
def form_send_message(match_id):
    user = _get_current_user()
    if not user:
        return redirect(url_for("dating.login_page"))

    matches = _load_matches()
    match = next((m for m in matches if m["id"] == match_id), None)
    if not match or match["status"] != "active":
        abort(404)
    if user["id"] not in (match["user1_id"], match["user2_id"]):
        abort(403)

    content = request.form.get("content", "").strip()
    attachment = request.files.get("file")
    attachment_name = attachment.filename if attachment and attachment.filename else ""
    if not content and not attachment_name:
        return redirect(url_for("dating.conversation", match_id=match_id))

    other_id = match["user2_id"] if match["user1_id"] == user["id"] else match["user1_id"]

    new_id = _next_id("messages")
    msg = {
        "id": new_id, "match_id": match_id, "sender_id": user["id"],
        "content": content,
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "read": False
    }
    if attachment_name:
        msg["attachment"] = attachment_name
    db.save_item(SITE, "messages", new_id, msg)
    _add_email(other_id, "noreply@dating.lakeport.local",
               "You have a new message",
               f"You have received a new message from your match. Log in to read it.")

    try:
        from app.bridges import on_message
        on_message(from_user_id=user["id"], to_user_id=other_id, text=content, source_site="Dating")
    except Exception:
        pass

    if any(kw in content.lower() for kw in ("meet", "date", "dinner", "coffee", "drinks", "tonight", "tomorrow")):
        emit("booking", user_id=user["id"], title="Date planned", start=datetime.now().strftime("%Y-%m-%d"), location="")

    return redirect(url_for("dating.conversation", match_id=match_id))


@blueprint.route("/update-profile", methods=["POST"])
def form_update_profile():
    user = _get_current_user()
    if not user:
        return redirect(url_for("dating.login_page"))

    u = _get_user(user["id"])
    if not u:
        return redirect(url_for("dating.login_page"))

    if request.form.get("bio"):
        u["bio"] = request.form["bio"].strip()
    if request.form.get("location"):
        u["location"] = request.form["location"].strip()
    if request.form.get("looking_for"):
        u["looking_for"] = request.form["looking_for"].strip()
    if request.form.get("interests"):
        u["interests"] = [i.strip() for i in request.form["interests"].split(",") if i.strip()]

    # Preferences live in the nested `preferences` dict AND top-level *_pref
    # keys (the form's representation) — keep both in sync.
    prefs = u.get("preferences") if isinstance(u.get("preferences"), dict) else {}
    if request.form.get("min_age_pref"):
        try:
            u["min_age_pref"] = prefs["min_age"] = int(request.form["min_age_pref"])
        except ValueError:
            pass
    if request.form.get("max_age_pref"):
        try:
            u["max_age_pref"] = prefs["max_age"] = int(request.form["max_age_pref"])
        except ValueError:
            pass
    if request.form.get("max_distance_pref"):
        try:
            u["max_distance_pref"] = prefs["max_distance_miles"] = int(request.form["max_distance_pref"])
        except ValueError:
            pass
    if request.form.get("gender_pref"):
        u["gender_pref"] = prefs["gender_pref"] = request.form["gender_pref"].strip()
    u["preferences"] = prefs

    db.save_item(SITE, "users", u["id"], u)
    return redirect(url_for("dating.edit_profile"))


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/profiles")
def api_profiles():
    """List all profiles with optional filtering. Public endpoint (no auth required)."""
    users = _load_users()

    # Filtering
    gender = request.args.get("gender")
    if gender:
        users = [u for u in users if u.get("gender", "").lower() == gender.lower()]

    looking_for = request.args.get("looking_for")
    if looking_for:
        users = [u for u in users if u.get("looking_for", "").lower() == looking_for.lower()]

    interest = request.args.get("interest")
    if interest:
        users = [u for u in users if interest.lower() in [i.lower() for i in u.get("interests", [])]]

    min_age = request.args.get("min_age", type=int)
    max_age = request.args.get("max_age", type=int)
    if min_age is not None:
        users = [u for u in users if u.get("age", 0) >= min_age]
    if max_age is not None:
        users = [u for u in users if u.get("age", 0) <= max_age]

    safe = [_safe_user(u) for u in users]
    return jsonify(safe)


@blueprint.route("/api/discover")
def api_discover():
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    profiles = _get_discover_profiles(user["id"])
    safe = [_safe_user(p) for p in profiles]
    return jsonify(safe)


@blueprint.route("/api/profiles/<int:profile_id>")
def api_profile(profile_id):
    profile = _get_user(profile_id)
    if not profile:
        return jsonify({"error": "Profile not found"}), 404
    return jsonify(_safe_user(profile))


@blueprint.route("/api/like", methods=["POST"])
def api_like():
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json(silent=True) or {}
    # Accept both "profile_id" and "to_user_id" for compatibility
    profile_id = data.get("profile_id") or data.get("to_user_id")
    if not profile_id:
        return jsonify({"error": "profile_id required"}), 400

    action, match_id = _do_like(user["id"], profile_id)
    if action == "already":
        return jsonify({"error": "Already acted on this profile"}), 400
    if action == "matched":
        return jsonify({"action": "matched", "match_id": match_id})
    return jsonify({"action": "liked"})


@blueprint.route("/api/pass", methods=["POST"])
def api_pass():
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json(silent=True) or {}
    profile_id = data.get("profile_id") or data.get("to_user_id")
    if not profile_id:
        return jsonify({"error": "profile_id required"}), 400

    _do_pass(user["id"], profile_id)
    return jsonify({"action": "passed"})


@blueprint.route("/api/matches")
def api_matches():
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    user_matches = _get_user_matches(user["id"])
    users = _load_users()
    user_map = {u["id"]: u for u in users}
    result = []
    for m in user_matches:
        other_id = m["user2_id"] if m["user1_id"] == user["id"] else m["user1_id"]
        other = user_map.get(other_id)
        if not other:
            continue
        match_msgs = db.query(SITE, "messages", where={"match_id": m["id"]},
                              sort="timestamp")
        last_msg = match_msgs[-1] if match_msgs else None
        unread = sum(1 for msg in match_msgs
                     if msg["sender_id"] != user["id"] and not msg.get("read", True))
        result.append({
            "match_id": m["id"],
            "matched_date": m["matched_date"],
            "other_user": _safe_user(other),
            "last_message": last_msg,
            "unread_count": unread,
        })
    return jsonify(result)


@blueprint.route("/api/messages/all")
def api_all_messages():
    """Get all messages on the platform (public, for stats tasks)."""
    messages = _load_messages()
    return jsonify(messages)


@blueprint.route("/api/messages/<int:match_id>")
def api_messages(match_id):
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    matches = _load_matches()
    match = next((m for m in matches if m["id"] == match_id), None)
    if not match or match["status"] != "active":
        return jsonify({"error": "Match not found"}), 404
    if user["id"] not in (match["user1_id"], match["user2_id"]):
        return jsonify({"error": "Forbidden"}), 403
    match_msgs = db.query(SITE, "messages", where={"match_id": match_id},
                          sort="timestamp")
    return jsonify(match_msgs)


@blueprint.route("/api/messages", methods=["GET"])
def api_messages_list():
    """Get messages for the logged-in user (or by user_id query param)."""
    user = _get_current_user()
    user_id = request.args.get("user_id", type=int)
    if user_id is None:
        if not user:
            return jsonify({"error": "Not authenticated"}), 401
        user_id = user["id"]

    # Return messages from every match the user belongs to
    matches = _load_matches()
    user_match_ids = {m["id"] for m in matches
                      if m["user1_id"] == user_id or m["user2_id"] == user_id}
    user_msgs = []
    for mid in user_match_ids:
        user_msgs.extend(db.query(SITE, "messages", where={"match_id": mid}))
    user_msgs.sort(key=lambda x: x["timestamp"], reverse=True)
    return jsonify(user_msgs)


@blueprint.route("/api/messages", methods=["POST"])
def api_send_message():
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json(silent=True) or {}
    match_id = data.get("match_id")
    content = data.get("content", "").strip()
    if not match_id or not content:
        return jsonify({"error": "match_id and content required"}), 400

    matches = _load_matches()
    match = next((m for m in matches if m["id"] == match_id), None)
    if not match or match["status"] != "active":
        return jsonify({"error": "Match not found"}), 404
    if user["id"] not in (match["user1_id"], match["user2_id"]):
        return jsonify({"error": "Forbidden"}), 403

    other_id = match["user2_id"] if match["user1_id"] == user["id"] else match["user1_id"]

    new_id = _next_id("messages")
    new_msg = {
        "id": new_id, "match_id": match_id, "sender_id": user["id"],
        "content": content,
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "read": False
    }
    db.save_item(SITE, "messages", new_id, new_msg)

    try:
        from app.bridges import on_message
        on_message(from_user_id=user["id"], to_user_id=other_id, text=content, source_site="Dating")
    except Exception:
        pass

    return jsonify(new_msg)


@blueprint.route("/api/profile", methods=["PUT"])
def api_update_profile():
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json(silent=True) or {}
    u = _get_user(user["id"])
    if not u:
        return jsonify({"error": "User not found"}), 404

    prefs = u.get("preferences") if isinstance(u.get("preferences"), dict) else {}
    for field in ["bio", "location", "looking_for"]:
        if field in data:
            u[field] = data[field]
    if "gender_pref" in data:
        u["gender_pref"] = prefs["gender_pref"] = data["gender_pref"]
    if "interests" in data:
        u["interests"] = data["interests"] if isinstance(data["interests"], list) else \
            [i.strip() for i in data["interests"].split(",") if i.strip()]
    if "min_age_pref" in data:
        u["min_age_pref"] = prefs["min_age"] = int(data["min_age_pref"])
    if "max_age_pref" in data:
        u["max_age_pref"] = prefs["max_age"] = int(data["max_age_pref"])
    u["preferences"] = prefs

    db.save_item(SITE, "users", u["id"], u)
    return jsonify(_safe_user(u))


@blueprint.route("/api/users/<int:user_id>")
def api_user(user_id):
    user = _get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(_safe_user(user))


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


@blueprint.route("/api/likes")
def api_likes():
    """Get likes. If logged in, returns current user's sent likes.
    If not logged in, returns all likes (for stats tasks)."""
    user = _get_current_user()
    likes = _load_likes()
    if user:
        user_likes = [l for l in likes if l["from_user_id"] == user["id"]]
        return jsonify(user_likes)
    # Public access: return all likes for platform stats
    return jsonify(likes)


@blueprint.route("/api/pending-likes")
def api_pending_likes():
    """Get pending likes received by current user."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    likes = _load_likes()
    pending = [l for l in likes if l["to_user_id"] == user["id"] and l["status"] == "pending"]
    return jsonify(pending)


@blueprint.route("/api/stats")
def api_stats():
    """Get platform stats or user stats."""
    users = _load_users()
    matches = _load_matches()
    messages = _load_messages()
    likes = _load_likes()

    user_id = request.args.get("user_id", type=int)
    if user_id:
        user_matches = [m for m in matches if m["status"] == "active" and
                        (m["user1_id"] == user_id or m["user2_id"] == user_id)]
        user_msgs = [msg for msg in messages
                     if msg["sender_id"] == user_id]
        user_likes_sent = [l for l in likes if l["from_user_id"] == user_id]
        user_likes_received = [l for l in likes if l["to_user_id"] == user_id]
        return jsonify({
            "user_id": user_id,
            "active_matches": len(user_matches),
            "messages_sent": len(user_msgs),
            "likes_sent": len(user_likes_sent),
            "likes_received": len(user_likes_received),
        })

    active_matches = [m for m in matches if m["status"] == "active"]
    locations = {}
    for u in users:
        loc = u.get("location", "Unknown")
        locations[loc] = locations.get(loc, 0) + 1
    looking_for = {}
    for u in users:
        lf = u.get("looking_for", "unknown")
        looking_for[lf] = looking_for.get(lf, 0) + 1
    interests_count = {}
    for u in users:
        for interest in u.get("interests", []):
            interests_count[interest] = interests_count.get(interest, 0) + 1

    return jsonify({
        "total_users": len(users),
        "active_matches": len(active_matches),
        "total_messages": len(messages),
        "total_likes": len(likes),
        "locations": locations,
        "looking_for": looking_for,
        "top_interests": dict(sorted(interests_count.items(), key=lambda x: -x[1])[:10]),
        "verified_users": sum(1 for u in users if u.get("verified")),
        "avg_age": round(sum(u["age"] for u in users) / len(users), 1) if users else 0,
    })


@blueprint.route("/api/export")
def api_export():
    """Export profiles or matches as JSON or CSV."""
    fmt = request.args.get("format", "json").lower()
    data_type = request.args.get("type", "profiles").lower()

    if data_type == "matches":
        data = _load_matches()
    elif data_type == "messages":
        data = _load_messages()
    else:
        data = [_safe_user(u) for u in _load_users()]

    if fmt == "csv":
        if not data:
            return Response("", mimetype="text/csv")
        keys = list(data[0].keys())
        lines = [",".join(keys)]
        for row in data:
            vals = []
            for k in keys:
                v = str(row.get(k, "")).replace('"', '""')
                vals.append(f'"{v}"')
            lines.append(",".join(vals))
        return Response("\n".join(lines), mimetype="text/csv",
                        headers={"Content-Disposition": f"attachment; filename={data_type}.csv"})
    return jsonify(data)
