"""Lakeport Civic Hub -- community petitions, elections & voter info portal.

Reads real civic data (petitions, signatures, elections, voter info, users)
from DATA_SOURCES_DIR / "petitions-voting" and serves a full-featured civic
engagement site with HTML pages and JSON API endpoints.

Supported macros (20):
  navigate_by_dropdown, navigate_by_route, search_by_query, search_by_semantic,
  filter_by_query, filter_by_dropdown, sort_by_toggle, extract_by_query,
  extract_by_dropdown, extract_by_route, extract_by_date_range,
  verify_by_dropdown, create_from_free_text, submit_by_query,
  sign_by_signature, subscribe_by_toggle, share_by_dropdown, save_by_toggle,
  authenticate_by_form, register_by_form
"""
import pathlib
from datetime import datetime

from flask import (
    Blueprint, abort, jsonify, redirect, render_template, request,
    session, url_for,
)
from app import db

SITE = "petitions-voting-info"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "petitions-voting-info",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _load_petitions():
    return db.query(SITE, "petitions")

def _load_signatures():
    return db.query(SITE, "signatures")

def _load_elections():
    return db.query(SITE, "elections")

def _load_voter_info():
    rows = db.query(SITE, "voter_info")
    return rows[0] if rows else {}

def _load_users():
    return db.query(SITE, "users")

def _save_users(users):
    db.save_collection(SITE, "users", users)

def _get_current_user():
    if "user_id" in session:
        return db.get_item(SITE, "users", session["user_id"])
    return None

def _now_iso():
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Search helpers (search_by_query, search_by_semantic)
# ---------------------------------------------------------------------------

def _keyword_score(query, petition):
    """Score a petition against a query by keyword overlap."""
    terms = query.lower().split()
    text = (petition["title"] + " " + petition["description"] + " " +
            petition["category"].replace("_", " ") + " " +
            " ".join(petition.get("tags", []))).lower()
    return sum(1 for t in terms if t in text)


def _search_petitions(petitions, query, semantic=False):
    """Filter petitions by text query; semantic mode ranks by keyword score."""
    if not query:
        return petitions
    q = query.lower().strip()
    if semantic:
        scored = [(p, _keyword_score(q, p)) for p in petitions]
        scored = [(p, s) for p, s in scored if s > 0]
        scored.sort(key=lambda x: -x[1])
        return [p for p, _ in scored]
    else:
        return [p for p in petitions if q in p["title"].lower() or
                q in p["description"].lower() or
                q in p["category"].replace("_", " ").lower() or
                any(q in t.lower() for t in p.get("tags", []))]


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    """Dashboard -- active petitions + upcoming elections."""
    petitions = _load_petitions()
    elections = _load_elections()
    user = _get_current_user()

    active_petitions = [p for p in petitions if p["status"] == "active"]
    active_petitions.sort(key=lambda p: p["signatures_current"], reverse=True)

    upcoming_elections = [e for e in elections if e["status"] == "upcoming"]
    completed_elections = [e for e in elections if e["status"] == "completed"]
    completed_elections.sort(key=lambda e: e["date"], reverse=True)

    return render_template(
        "petitions-voting-info/index.html",
        active_petitions=active_petitions[:5],
        upcoming_elections=upcoming_elections,
        recent_elections=completed_elections[:2],
        user=user,
        logged_in=user is not None,
    )


@blueprint.route("/petitions")
def petitions_list():
    """List petitions with filter, search, and sort."""
    petitions = _load_petitions()
    user = _get_current_user()

    # Search (search_by_query)
    q = request.args.get("q", "").strip()
    # Filters
    status = request.args.get("status", "")
    category = request.args.get("category", "")
    sort_by = request.args.get("sort", "date")
    order = request.args.get("order", "desc")  # sort_by_toggle: asc/desc

    if q:
        petitions = _search_petitions(petitions, q)
    if status:
        petitions = [p for p in petitions if p["status"] == status]
    if category:
        petitions = [p for p in petitions if p["category"] == category]

    reverse = (order == "desc")
    if sort_by == "signatures":
        petitions.sort(key=lambda p: p["signatures_current"], reverse=reverse)
    elif sort_by == "title":
        petitions.sort(key=lambda p: p["title"].lower(), reverse=reverse)
    else:  # date
        petitions.sort(key=lambda p: p["created_at"], reverse=reverse)

    # Collect unique categories for filter dropdown
    all_petitions = _load_petitions()
    categories = sorted(set(p["category"] for p in all_petitions))
    statuses = sorted(set(p["status"] for p in all_petitions))

    return render_template(
        "petitions-voting-info/petitions.html",
        petitions=petitions,
        categories=categories,
        statuses=statuses,
        current_status=status,
        current_category=category,
        current_sort=sort_by,
        current_order=order,
        q=q,
        user=user,
        logged_in=user is not None,
    )


@blueprint.route("/petition/<int:petition_id>")
def petition_detail(petition_id):
    """Petition detail page with signatures."""
    petitions = _load_petitions()
    petition = next((p for p in petitions if p["id"] == petition_id), None)
    if not petition:
        abort(404)

    pet_sigs = db.query(SITE, "signatures", where={"petition_id": petition_id}, sort="-signed_at")

    user = _get_current_user()
    already_signed = False
    is_subscribed = False
    is_saved = False
    if user:
        already_signed = any(s["user_id"] == user["id"] for s in pet_sigs)
        is_subscribed = petition_id in user.get("subscribed_petitions", [])
        is_saved = petition_id in user.get("saved_petitions", [])

    progress_pct = min(100, round(petition["signatures_current"] / petition["signatures_required"] * 100, 1))

    return render_template(
        "petitions-voting-info/petition_detail.html",
        petition=petition,
        signatures=pet_sigs,
        already_signed=already_signed,
        is_subscribed=is_subscribed,
        is_saved=is_saved,
        progress_pct=progress_pct,
        user=user,
        logged_in=user is not None,
    )


@blueprint.route("/create-petition")
def create_petition_page():
    """Form to create a new petition."""
    user = _get_current_user()
    all_petitions = _load_petitions()
    categories = sorted(set(p["category"] for p in all_petitions))
    return render_template(
        "petitions-voting-info/create_petition.html",
        categories=categories,
        user=user,
        logged_in=user is not None,
    )


@blueprint.route("/elections")
def elections_list():
    """List all elections."""
    elections = _load_elections()
    user = _get_current_user()

    upcoming = [e for e in elections if e["status"] == "upcoming"]
    completed = [e for e in elections if e["status"] == "completed"]
    completed.sort(key=lambda e: e["date"], reverse=True)

    return render_template(
        "petitions-voting-info/elections.html",
        upcoming_elections=upcoming,
        completed_elections=completed,
        user=user,
        logged_in=user is not None,
    )


@blueprint.route("/election/<int:election_id>")
def election_detail(election_id):
    """Election detail page."""
    elections = _load_elections()
    election = next((e for e in elections if e["id"] == election_id), None)
    if not election:
        abort(404)

    voter_info = _load_voter_info()
    user = _get_current_user()

    return render_template(
        "petitions-voting-info/election_detail.html",
        election=election,
        voter_info=voter_info,
        user=user,
        logged_in=user is not None,
    )


@blueprint.route("/voter-info")
def voter_info_page():
    """Voter registration and polling information."""
    voter_info = _load_voter_info()
    elections = _load_elections()
    user = _get_current_user()

    upcoming = [e for e in elections if e["status"] == "upcoming"]

    return render_template(
        "petitions-voting-info/voter_info.html",
        voter_info=voter_info,
        upcoming_elections=upcoming,
        user=user,
        logged_in=user is not None,
    )


@blueprint.route("/dashboard")
def dashboard():
    """User dashboard with saved petitions and subscriptions."""
    if "user_id" not in session:
        return redirect(url_for("petitions-voting-info.login_page"))
    user = _get_current_user()
    if not user:
        return redirect(url_for("petitions-voting-info.login_page"))
    petitions = _load_petitions()
    saved = [p for p in petitions if p["id"] in user.get("saved_petitions", [])]
    subscribed = [p for p in petitions if p["id"] in user.get("subscribed_petitions", [])]
    return render_template(
        "petitions-voting-info/dashboard.html",
        user=user,
        saved_petitions=saved,
        subscribed_petitions=subscribed,
        logged_in=True,
    )


@blueprint.route("/register-voter")
def register_voter_page():
    """Voter registration form page (register_by_form)."""
    user = _get_current_user()
    voter_info = _load_voter_info()
    return render_template(
        "petitions-voting-info/register_voter.html",
        voter_info=voter_info,
        user=user,
        logged_in=user is not None,
    )


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template(
        "petitions-voting-info/login.html",
        error=None,
        logged_in=False,
    )


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user:
        return render_template("petitions-voting-info/login.html",
                               error="Invalid username or password",
                               logged_in=False)
    # For this civic portal, any non-empty password is accepted (demo)
    if not password:
        return render_template("petitions-voting-info/login.html",
                               error="Password is required",
                               logged_in=False)
    session["user_id"] = user["id"]
    return redirect(url_for("petitions-voting-info.index"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("petitions-voting-info.index"))


# ---------------------------------------------------------------------------
# API routes -- core CRUD
# ---------------------------------------------------------------------------

@blueprint.route("/api/petitions", methods=["GET"])
def api_petitions_list():
    """GET petitions with optional filters: status, category, q, sort, order,
    date_from, date_to.

    Supports macros: filter_by_query, filter_by_dropdown, search_by_query,
    sort_by_toggle, extract_by_date_range.
    """
    petitions = _load_petitions()

    # search_by_query / filter_by_query
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    category = request.args.get("category", "")
    sort_by = request.args.get("sort", "date")
    order = request.args.get("order", "desc")  # sort_by_toggle
    date_from = request.args.get("date_from", "").strip()  # extract_by_date_range
    date_to = request.args.get("date_to", "").strip()

    if q:
        petitions = _search_petitions(petitions, q)
    if status:
        petitions = [p for p in petitions if p["status"] == status]
    if category:
        petitions = [p for p in petitions if p["category"] == category]
    if date_from:
        petitions = [p for p in petitions if p["created_at"][:10] >= date_from]
    if date_to:
        petitions = [p for p in petitions if p["created_at"][:10] <= date_to]

    reverse = (order == "desc")
    if sort_by == "signatures":
        petitions.sort(key=lambda p: p["signatures_current"], reverse=reverse)
    elif sort_by == "title":
        petitions.sort(key=lambda p: p["title"].lower(), reverse=reverse)
    else:  # date
        petitions.sort(key=lambda p: p["created_at"], reverse=reverse)

    return jsonify(petitions)


@blueprint.route("/api/petitions/search", methods=["GET"])
def api_petitions_search():
    """Text search across petition titles and descriptions (search_by_query)."""
    petitions = _load_petitions()
    q = request.args.get("q", "").strip()
    return jsonify(_search_petitions(petitions, q))


@blueprint.route("/api/petitions/semantic", methods=["GET"])
def api_petitions_semantic():
    """Semantic search -- ranks petitions by keyword relevance (search_by_semantic)."""
    petitions = _load_petitions()
    q = request.args.get("q", "").strip()
    return jsonify(_search_petitions(petitions, q, semantic=True))


@blueprint.route("/api/petitions", methods=["POST"])
def api_petitions_create():
    """Create a new petition (create_from_free_text). Requires login."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Login required"}), 401

    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    description = data.get("description", "").strip()
    category = data.get("category", "community").strip()
    signatures_required = data.get("signatures_required", 300)
    deadline = data.get("deadline", "")
    tags = data.get("tags", [])

    if not title:
        return jsonify({"error": "Title is required"}), 400
    if not description:
        return jsonify({"error": "Description is required"}), 400

    petitions = _load_petitions()
    new_id = max((p["id"] for p in petitions), default=0) + 1

    new_petition = {
        "id": new_id,
        "title": title,
        "creator_id": user["id"],
        "creator_name": user["display_name"],
        "description": description,
        "category": category,
        "signatures_required": int(signatures_required),
        "signatures_current": 0,
        "status": "active",
        "created_at": _now_iso(),
        "deadline": deadline or None,
        "tags": tags if isinstance(tags, list) else [],
        "related_links": {},
    }
    petitions.append(new_petition)
    db.save_collection(SITE, "petitions", petitions)
    return jsonify(new_petition), 201


@blueprint.route("/api/petitions/<int:petition_id>", methods=["GET"])
def api_petition_get(petition_id):
    """Get a single petition by id (extract_by_route)."""
    petitions = _load_petitions()
    petition = next((p for p in petitions if p["id"] == petition_id), None)
    if not petition:
        return jsonify({"error": "Petition not found"}), 404
    return jsonify(petition)


@blueprint.route("/api/petitions/<int:petition_id>", methods=["PUT"])
def api_petition_update(petition_id):
    """Update a petition (creator or any logged-in user for status changes)."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Login required"}), 401

    petitions = _load_petitions()
    petition = next((p for p in petitions if p["id"] == petition_id), None)
    if not petition:
        return jsonify({"error": "Petition not found"}), 404

    data = request.get_json(silent=True) or {}

    for field in ("title", "description", "category", "status", "deadline", "signatures_required"):
        if field in data:
            petition[field] = data[field]

    if "tags" in data and isinstance(data["tags"], list):
        petition["tags"] = data["tags"]

    db.save_collection(SITE, "petitions", petitions)
    return jsonify(petition)


# ---------------------------------------------------------------------------
# API routes -- sign_by_signature
# ---------------------------------------------------------------------------

@blueprint.route("/api/petitions/<int:petition_id>/sign", methods=["POST"])
def api_petition_sign(petition_id):
    """Sign a petition with typed signature text (sign_by_signature).

    Requires login. Body: {"signature": "Full Name", "comment": "optional"}.
    The signature field is the user's typed legal name confirming their support.
    """
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Login required"}), 401

    petitions = _load_petitions()
    petition = next((p for p in petitions if p["id"] == petition_id), None)
    if not petition:
        return jsonify({"error": "Petition not found"}), 404

    if petition["status"] != "active":
        return jsonify({"error": "Petition is not active"}), 400

    signatures = _load_signatures()
    already = any(s["petition_id"] == petition_id and s["user_id"] == user["id"]
                  for s in signatures)
    if already:
        return jsonify({"error": "Already signed this petition"}), 409

    data = request.get_json(silent=True) or {}
    signature_text = data.get("signature", "").strip()
    comment = data.get("comment", "").strip()

    if not signature_text:
        return jsonify({"error": "Signature (typed name) is required"}), 400

    new_sig_id = max((s["id"] for s in signatures), default=0) + 1
    new_sig = {
        "id": new_sig_id,
        "petition_id": petition_id,
        "user_id": user["id"],
        "user_name": user["display_name"],
        "signature": signature_text,
        "signed_at": _now_iso(),
        "comment": comment,
    }
    signatures.append(new_sig)
    db.save_collection(SITE, "signatures", signatures)

    # Update petition signature count
    petition["signatures_current"] += 1
    if petition["signatures_current"] >= petition["signatures_required"]:
        petition["status"] = "won"
    db.save_collection(SITE, "petitions", petitions)

    return jsonify(new_sig), 201


@blueprint.route("/api/petitions/<int:petition_id>/signatures", methods=["GET"])
def api_petition_signatures(petition_id):
    """Get all signatures for a petition."""
    petitions = _load_petitions()
    petition = next((p for p in petitions if p["id"] == petition_id), None)
    if not petition:
        return jsonify({"error": "Petition not found"}), 404

    pet_sigs = db.query(SITE, "signatures", where={"petition_id": petition_id}, sort="-signed_at")
    return jsonify(pet_sigs)


# ---------------------------------------------------------------------------
# API routes -- submit_by_query (submit a comment/feedback on a petition)
# ---------------------------------------------------------------------------

@blueprint.route("/api/petitions/<int:petition_id>/comments", methods=["GET"])
def api_petition_comments(petition_id):
    """Get comments for a petition."""
    petitions = _load_petitions()
    petition = next((p for p in petitions if p["id"] == petition_id), None)
    if not petition:
        return jsonify({"error": "Petition not found"}), 404

    signatures = _load_signatures()
    pet_sigs = [s for s in signatures if s["petition_id"] == petition_id and s.get("comment")]
    pet_sigs.sort(key=lambda s: s["signed_at"], reverse=True)
    return jsonify(pet_sigs)


@blueprint.route("/api/petitions/<int:petition_id>/comments", methods=["POST"])
def api_petition_submit_comment(petition_id):
    """Submit a comment on a petition (submit_by_query). Requires login."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Login required"}), 401

    petitions = _load_petitions()
    petition = next((p for p in petitions if p["id"] == petition_id), None)
    if not petition:
        return jsonify({"error": "Petition not found"}), 404

    data = request.get_json(silent=True) or {}
    comment = data.get("comment", "").strip()
    if not comment:
        return jsonify({"error": "Comment text is required"}), 400

    signatures = _load_signatures()
    new_id = max((s["id"] for s in signatures), default=0) + 1
    new_entry = {
        "id": new_id,
        "petition_id": petition_id,
        "user_id": user["id"],
        "user_name": user["display_name"],
        "signed_at": _now_iso(),
        "comment": comment,
        "type": "comment",
    }
    signatures.append(new_entry)
    db.save_collection(SITE, "signatures", signatures)
    return jsonify(new_entry), 201


# ---------------------------------------------------------------------------
# API routes -- subscribe_by_toggle
# ---------------------------------------------------------------------------

@blueprint.route("/api/petitions/<int:petition_id>/subscribe", methods=["POST"])
def api_petition_subscribe(petition_id):
    """Toggle subscription to petition updates (subscribe_by_toggle).

    Returns {"action": "subscribed"} or {"action": "unsubscribed"}.
    """
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Login required"}), 401

    petitions = _load_petitions()
    petition = next((p for p in petitions if p["id"] == petition_id), None)
    if not petition:
        return jsonify({"error": "Petition not found"}), 404

    users = _load_users()
    db_user = next((u for u in users if u["id"] == user["id"]), None)
    if not db_user:
        return jsonify({"error": "User not found"}), 404

    subs = db_user.setdefault("subscribed_petitions", [])
    if petition_id in subs:
        subs.remove(petition_id)
        action = "unsubscribed"
    else:
        subs.append(petition_id)
        action = "subscribed"

    _save_users(users)
    return jsonify({"action": action, "petition_id": petition_id,
                    "total_subscribed": len(subs)})


# ---------------------------------------------------------------------------
# API routes -- save_by_toggle
# ---------------------------------------------------------------------------

@blueprint.route("/api/petitions/<int:petition_id>/save", methods=["POST"])
def api_petition_save(petition_id):
    """Toggle saving a petition to the user's favorites (save_by_toggle).

    Returns {"action": "saved"} or {"action": "unsaved"}.
    """
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Login required"}), 401

    petitions = _load_petitions()
    petition = next((p for p in petitions if p["id"] == petition_id), None)
    if not petition:
        return jsonify({"error": "Petition not found"}), 404

    users = _load_users()
    db_user = next((u for u in users if u["id"] == user["id"]), None)
    if not db_user:
        return jsonify({"error": "User not found"}), 404

    saved = db_user.setdefault("saved_petitions", [])
    if petition_id in saved:
        saved.remove(petition_id)
        action = "unsaved"
    else:
        saved.append(petition_id)
        action = "saved"

    _save_users(users)
    return jsonify({"action": action, "petition_id": petition_id,
                    "total_saved": len(saved)})


# ---------------------------------------------------------------------------
# API routes -- share_by_dropdown
# ---------------------------------------------------------------------------

@blueprint.route("/api/petitions/<int:petition_id>/share", methods=["POST"])
def api_petition_share(petition_id):
    """Share a petition via a selected method (share_by_dropdown).

    Body: {"method": "email"|"twitter"|"facebook"|"link"}.
    Returns a share payload (URL or confirmation).
    """
    petitions = _load_petitions()
    petition = next((p for p in petitions if p["id"] == petition_id), None)
    if not petition:
        return jsonify({"error": "Petition not found"}), 404

    data = request.get_json(silent=True) or {}
    method = data.get("method", "").strip().lower()

    valid_methods = ["email", "twitter", "facebook", "link"]
    if method not in valid_methods:
        return jsonify({"error": f"Invalid share method. Choose from: {', '.join(valid_methods)}"}), 400

    petition_url = f"/sites/petitions-voting-info/petition/{petition_id}"
    title_encoded = petition["title"].replace(" ", "+")

    share_urls = {
        "email": f"mailto:?subject={title_encoded}&body=Check+out+this+petition:+{petition_url}",
        "twitter": f"https://twitter.com/intent/tweet?text={title_encoded}&url={petition_url}",
        "facebook": f"https://www.facebook.com/sharer/sharer.php?u={petition_url}",
        "link": petition_url,
    }

    return jsonify({
        "method": method,
        "petition_id": petition_id,
        "petition_title": petition["title"],
        "share_url": share_urls[method],
        "status": "shared",
    })


# ---------------------------------------------------------------------------
# API routes -- elections
# ---------------------------------------------------------------------------

@blueprint.route("/api/elections", methods=["GET"])
def api_elections_list():
    """Get all elections with optional status filter and date_range (extract_by_date_range)."""
    elections = _load_elections()
    status = request.args.get("status", "")
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    if status:
        elections = [e for e in elections if e["status"] == status]
    if date_from:
        elections = [e for e in elections if e["date"] >= date_from]
    if date_to:
        elections = [e for e in elections if e["date"] <= date_to]

    elections.sort(key=lambda e: e["date"], reverse=True)
    return jsonify(elections)


@blueprint.route("/api/elections/<int:election_id>", methods=["GET"])
def api_election_get(election_id):
    """Get a single election by id (extract_by_route)."""
    elections = _load_elections()
    election = next((e for e in elections if e["id"] == election_id), None)
    if not election:
        return jsonify({"error": "Election not found"}), 404
    return jsonify(election)


# ---------------------------------------------------------------------------
# API routes -- voter info & verify_by_dropdown
# ---------------------------------------------------------------------------

@blueprint.route("/api/voter-info", methods=["GET"])
def api_voter_info_get():
    """Get voter registration and polling info."""
    voter_info = _load_voter_info()
    return jsonify(voter_info)


@blueprint.route("/api/voter-info/verify", methods=["GET"])
def api_voter_verify():
    """Verify voter registration status via precinct dropdown (verify_by_dropdown).

    Query params: precinct (e.g., "Precinct 1"), username.
    Returns registration status and polling location.
    """
    precinct = request.args.get("precinct", "").strip()
    username = request.args.get("username", "").strip()

    if not precinct:
        return jsonify({"error": "Precinct is required"}), 400

    voter_info = _load_voter_info()
    users = _load_users()

    # Find polling location for precinct
    matching_locations = []
    for loc in voter_info.get("polling_locations", []):
        if precinct in loc.get("precincts_served", []):
            matching_locations.append(loc)

    result = {
        "precinct": precinct,
        "polling_locations": matching_locations,
        "has_polling_location": len(matching_locations) > 0,
    }

    # If username given, look up that user's registration
    if username:
        user = next((u for u in users if u["username"] == username), None)
        if user:
            user_precinct = user.get("precinct", "")
            result["user_found"] = True
            result["registration_status"] = user.get("voter_registration_status", "unknown")
            result["registered_precinct"] = user_precinct
            result["registered_address"] = user.get("registered_address", "")
            result["party_affiliation"] = user.get("party_affiliation", "")
            result["precinct_match"] = (precinct in user_precinct)
        else:
            result["user_found"] = False
            result["registration_status"] = "not_found"

    return jsonify(result)


@blueprint.route("/api/voter-info", methods=["PUT"])
def api_voter_info_update():
    """Update voter registration info for the logged-in user."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Login required"}), 401

    data = request.get_json(silent=True) or {}
    users = _load_users()
    db_user = next((u for u in users if u["id"] == user["id"]), None)
    if not db_user:
        return jsonify({"error": "User not found"}), 404

    for field in ("registered_address", "precinct", "party_affiliation"):
        if field in data:
            db_user[field] = data[field]

    if "profile" in data and isinstance(data["profile"], dict):
        db_user["profile"].update(data["profile"])

    _save_users(users)
    return jsonify(db_user)


# ---------------------------------------------------------------------------
# API routes -- register_by_form (voter registration)
# ---------------------------------------------------------------------------

@blueprint.route("/api/register-voter", methods=["POST"])
def api_register_voter():
    """Register a new voter (register_by_form).

    Body: {"full_name": "...", "address": "...", "precinct": "...",
           "date_of_birth": "...", "party_affiliation": "...",
           "email": "...", "username": "...", "password": "..."}.
    Creates a new user with voter_registration_status = "active".
    """
    data = request.get_json(silent=True) or {}
    full_name = data.get("full_name", "").strip()
    address = data.get("address", "").strip()
    precinct = data.get("precinct", "").strip()
    dob = data.get("date_of_birth", "").strip()
    party = data.get("party_affiliation", "independent").strip()
    email = data.get("email", "").strip()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not full_name:
        return jsonify({"error": "Full name is required"}), 400
    if not address:
        return jsonify({"error": "Address is required"}), 400
    if not precinct:
        return jsonify({"error": "Precinct is required"}), 400
    if not dob:
        return jsonify({"error": "Date of birth is required"}), 400
    if not username:
        return jsonify({"error": "Username is required"}), 400
    if not password:
        return jsonify({"error": "Password is required"}), 400

    users = _load_users()

    # Check for duplicate username
    if any(u["username"] == username for u in users):
        return jsonify({"error": "Username already exists"}), 409

    new_id = max((u["id"] for u in users), default=0) + 1

    new_user = {
        "id": new_id,
        "root_user_id": None,
        "username": username,
        "display_name": full_name,
        "email": email,
        "voter_registration_status": "active",
        "registered_address": address,
        "precinct": precinct,
        "party_affiliation": party,
        "registration_date": _now_iso()[:10],
        "date_of_birth": dob,
        "profile": {
            "bio": "",
            "interests": [],
        },
        "saved_petitions": [],
        "subscribed_petitions": [],
    }
    users.append(new_user)
    _save_users(users)

    session["user_id"] = new_user["id"]

    return jsonify({
        "user_id": new_user["id"],
        "username": new_user["username"],
        "display_name": new_user["display_name"],
        "voter_registration_status": "active",
        "precinct": precinct,
    }), 201


# ---------------------------------------------------------------------------
# API routes -- categories & stats (extract_by_dropdown)
# ---------------------------------------------------------------------------

@blueprint.route("/api/categories", methods=["GET"])
def api_categories():
    """List all petition categories with counts (navigate_by_dropdown support)."""
    petitions = _load_petitions()
    category_counts = {}
    for p in petitions:
        cat = p["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1
    return jsonify([{"name": cat, "count": n}
                    for cat, n in sorted(category_counts.items())])


@blueprint.route("/api/categories/<path:cat_name>/stats", methods=["GET"])
def api_category_stats(cat_name):
    """Stats for a specific petition category (extract_by_dropdown)."""
    petitions = _load_petitions()
    signatures = _load_signatures()
    filtered = [p for p in petitions if p["category"] == cat_name]
    if not filtered:
        return jsonify({"category": cat_name, "count": 0})

    sig_count = sum(1 for s in signatures if s["petition_id"] in {p["id"] for p in filtered})
    statuses = {}
    for p in filtered:
        statuses[p["status"]] = statuses.get(p["status"], 0) + 1

    return jsonify({
        "category": cat_name,
        "count": len(filtered),
        "total_signatures": sig_count,
        "statuses": statuses,
        "avg_signatures": round(sum(p["signatures_current"] for p in filtered) / len(filtered), 1),
    })


@blueprint.route("/api/stats", methods=["GET"])
def api_stats():
    """Aggregate stats for the civic hub."""
    petitions = _load_petitions()
    signatures = _load_signatures()
    elections = _load_elections()
    users = _load_users()

    total_petitions = len(petitions)
    active_petitions = sum(1 for p in petitions if p["status"] == "active")
    won_petitions = sum(1 for p in petitions if p["status"] == "won")
    total_signatures = len(signatures)
    total_elections = len(elections)
    upcoming_elections = sum(1 for e in elections if e["status"] == "upcoming")
    total_users = len(users)

    # Category breakdown
    category_counts = {}
    for p in petitions:
        cat = p["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1

    return jsonify({
        "total_petitions": total_petitions,
        "active_petitions": active_petitions,
        "won_petitions": won_petitions,
        "total_signatures": total_signatures,
        "total_elections": total_elections,
        "upcoming_elections": upcoming_elections,
        "total_users": total_users,
        "petitions_by_category": category_counts,
    })


# ---------------------------------------------------------------------------
# API routes -- user endpoints
# ---------------------------------------------------------------------------

@blueprint.route("/api/users/<int:user_id>", methods=["GET"])
def api_user_get(user_id):
    """Get a user's public profile."""
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        return jsonify({"error": "User not found"}), 404
    # Exclude sensitive fields
    safe = {k: v for k, v in user.items() if k not in ("password",)}
    return jsonify(safe)


@blueprint.route("/api/login", methods=["POST"])
def api_login():
    """API login (authenticate_by_form)."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user:
        return jsonify({"error": "Invalid credentials"}), 401
    if not password:
        return jsonify({"error": "Password required"}), 401
    session["user_id"] = user["id"]
    return jsonify({
        "user_id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
    })
