"""Crowdfunding & Donations platform (Kickstarter / GoFundMe style).

Data interpreter: reads synthesized JSON files, respects config/config.json,
and serves through Flask routes.  Raw data files are never modified except for
mutable user/pledge state.
"""
import json
import pathlib
from collections import Counter
from datetime import datetime

from flask import (Blueprint, Response, abort, jsonify, redirect,
                   render_template, request, session, url_for)

SITE_DIR = pathlib.Path(__file__).resolve().parent
CAMPAIGNS_FILE = SITE_DIR / "data" / "campaigns.json"
USERS_FILE = SITE_DIR / "data" / "users.json"
PLEDGES_FILE = SITE_DIR / "data" / "pledges.json"
CONFIG_FILE = SITE_DIR / "config" / "config.json"

blueprint = Blueprint(
    "crowdfunding-donations",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

_categories_list = ["technology", "art", "games", "film", "music", "community", "design", "food"]


def _load_campaigns():
    with open(CAMPAIGNS_FILE) as f:
        return json.load(f)


def _get_campaigns():
    return _load_campaigns()


def _get_campaign(campaign_id):
    campaigns = _get_campaigns()
    return next((c for c in campaigns if c["id"] == campaign_id), None)


def _save_campaigns(campaigns):
    CAMPAIGNS_FILE.write_text(json.dumps(campaigns, indent=2))


def _load_users():
    if USERS_FILE.exists():
        return json.loads(USERS_FILE.read_text())
    return []


def _save_users(users):
    USERS_FILE.write_text(json.dumps(users, indent=2))


def _get_user(user_id):
    users = _load_users()
    return next((u for u in users if u["id"] == user_id), None)


def _load_pledges():
    if PLEDGES_FILE.exists():
        return json.loads(PLEDGES_FILE.read_text())
    return []


def _save_pledges(pledges):
    PLEDGES_FILE.write_text(json.dumps(pledges, indent=2))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _funding_pct(campaign):
    if campaign["goal_amount"] <= 0:
        return 0
    return round(campaign["raised_amount"] / campaign["goal_amount"] * 100, 1)


def _search_campaigns(campaigns, query):
    if not query:
        return campaigns
    q = query.lower().strip()
    return [c for c in campaigns if q in c["title"].lower()
            or q in c["description"].lower()
            or q in c["category"].lower()]


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    campaigns = _get_campaigns()
    q = request.args.get("q", "").strip()
    cat = request.args.get("category", "").strip()
    status = request.args.get("status", "").strip()
    sort = request.args.get("sort", "trending").strip()

    results = list(campaigns)

    if q:
        results = _search_campaigns(results, q)
    if cat:
        results = [c for c in results if c["category"] == cat]
    if status:
        results = [c for c in results if c["status"] == status]

    if sort == "newest":
        results.sort(key=lambda c: c["start_date"], reverse=True)
    elif sort == "most_funded":
        results.sort(key=lambda c: c["raised_amount"], reverse=True)
    elif sort == "ending_soon":
        results.sort(key=lambda c: c["end_date"])
    elif sort == "most_backed":
        results.sort(key=lambda c: c["backer_count"], reverse=True)
    else:  # trending — active first, then by backer_count
        results.sort(key=lambda c: (0 if c["status"] == "active" else 1, -c["backer_count"]))

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    for c in results:
        c["funding_pct"] = _funding_pct(c)

    return render_template("crowdfunding-donations/index.html",
                           campaigns=results, categories=_categories_list,
                           q=q, cat=cat, status_filter=status, sort=sort, user=user)


@blueprint.route("/campaign/<int:campaign_id>")
def campaign_detail(campaign_id):
    campaign = _get_campaign(campaign_id)
    if campaign is None:
        abort(404)
    campaign["funding_pct"] = _funding_pct(campaign)
    creator = _get_user(campaign["creator_id"])
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    related = [c for c in _get_campaigns()
               if c["category"] == campaign["category"] and c["id"] != campaign_id][:4]
    for r in related:
        r["funding_pct"] = _funding_pct(r)
    return render_template("crowdfunding-donations/campaign.html",
                           campaign=campaign, creator=creator,
                           related=related, user=user)


@blueprint.route("/category/<cat_name>")
def category_page(cat_name):
    campaigns = _get_campaigns()
    filtered = [c for c in campaigns if c["category"] == cat_name]
    for c in filtered:
        c["funding_pct"] = _funding_pct(c)
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("crowdfunding-donations/category.html",
                           campaigns=filtered, category=cat_name,
                           categories=_categories_list, user=user)


@blueprint.route("/create", methods=["GET"])
def create_page():
    if "user_id" not in session:
        return redirect(url_for("crowdfunding-donations.login_page",
                                next=url_for("crowdfunding-donations.create_page")))
    user = _get_user(session["user_id"])
    return render_template("crowdfunding-donations/create.html",
                           categories=_categories_list, user=user)


@blueprint.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("crowdfunding-donations.login_page",
                                next=url_for("crowdfunding-donations.dashboard")))
    user = _get_user(session["user_id"])
    if not user:
        return redirect(url_for("crowdfunding-donations.login_page"))
    campaigns = _get_campaigns()
    created = [c for c in campaigns if c["id"] in user.get("created_campaigns", [])]
    for c in created:
        c["funding_pct"] = _funding_pct(c)
    backed_details = []
    for b in user.get("backed_campaigns", []):
        camp = next((c for c in campaigns if c["id"] == b["campaign_id"]), None)
        if camp:
            backed_details.append({
                "campaign": camp,
                "amount": b["amount"],
                "tier_id": b["tier_id"],
                "funding_pct": _funding_pct(camp),
            })
    return render_template("crowdfunding-donations/dashboard.html",
                           user=user, created_campaigns=created,
                           backed_campaigns=backed_details)


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("crowdfunding-donations/login.html", error=None,
                           next_url=request.args.get("next", ""))


@blueprint.route("/login", methods=["POST"])
def login_submit():
    if request.is_json:
        data = request.get_json(silent=True) or {}
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()
    else:
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        if request.is_json:
            return jsonify({"error": "Invalid credentials"}), 401
        return render_template("crowdfunding-donations/login.html",
                               error="Invalid username or password")
    session["user_id"] = user["id"]
    if request.is_json:
        return jsonify({"user_id": user["id"], "username": user["username"]})
    next_url = request.form.get("next", "") or request.args.get("next", "")
    if next_url:
        return redirect(next_url)
    return redirect(url_for("crowdfunding-donations.dashboard"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("crowdfunding-donations.index"))


# ---------------------------------------------------------------------------
# Form-based mutation routes
# ---------------------------------------------------------------------------

@blueprint.route("/campaign/<int:campaign_id>/pledge", methods=["POST"])
def form_pledge(campaign_id):
    is_json = request.is_json
    if "user_id" not in session:
        if is_json:
            return jsonify({"error": "Authentication required"}), 401
        return redirect(url_for("crowdfunding-donations.login_page"))
    user_id = session["user_id"]

    if is_json:
        data = request.get_json(silent=True) or {}
        tier_id = data.get("tier_id")
        amount = data.get("amount")
        if tier_id is not None:
            tier_id = int(tier_id)
        if amount is not None:
            amount = float(amount)
    else:
        tier_id = request.form.get("tier_id", type=int)
        amount = request.form.get("amount", type=float)

    campaigns = _get_campaigns()
    campaign = next((c for c in campaigns if c["id"] == campaign_id), None)
    if not campaign or campaign["status"] not in ("active", "funded"):
        if is_json:
            return jsonify({"error": "Campaign not accepting pledges"}), 400
        abort(400)

    # Find the tier
    tier = None
    if tier_id:
        tier = next((t for t in campaign["reward_tiers"] if t["id"] == tier_id), None)
        if tier:
            amount = amount or tier["amount"]
            if tier["quantity_claimed"] >= tier["quantity_available"]:
                if is_json:
                    return jsonify({"error": "Tier sold out"}), 400
                abort(400)

    if not amount or amount <= 0:
        if is_json:
            return jsonify({"error": "Invalid amount"}), 400
        abort(400)

    # Update campaign
    campaign["raised_amount"] += amount
    campaign["backer_count"] += 1
    if tier:
        tier["quantity_claimed"] += 1
    # Check if now funded
    if campaign["raised_amount"] >= campaign["goal_amount"] and campaign["status"] == "active":
        campaign["status"] = "funded"
    _save_campaigns(campaigns)

    # Update pledges
    pledges = _load_pledges()
    new_id = max((p["id"] for p in pledges), default=0) + 1
    pledges.append({
        "id": new_id,
        "user_id": user_id,
        "campaign_id": campaign_id,
        "amount": amount,
        "tier_id": tier_id,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "status": "completed"
    })
    _save_pledges(pledges)

    # Update user backed_campaigns
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if user:
        user.setdefault("backed_campaigns", []).append({
            "campaign_id": campaign_id,
            "amount": amount,
            "tier_id": tier_id
        })
        _save_users(users)

    if is_json:
        return jsonify({"pledge_id": new_id, "new_raised": campaign["raised_amount"],
                        "backer_count": campaign["backer_count"],
                        "new_status": campaign["status"]})
    return redirect(url_for("crowdfunding-donations.campaign_detail", campaign_id=campaign_id))


@blueprint.route("/campaign/create", methods=["POST"])
def form_create_campaign():
    is_json = request.is_json
    if "user_id" not in session:
        if is_json:
            return jsonify({"error": "Authentication required"}), 401
        return redirect(url_for("crowdfunding-donations.login_page"))
    user_id = session["user_id"]

    if is_json:
        data = request.get_json(silent=True) or {}
        title = data.get("title", "").strip()
        description = data.get("description", "").strip()
        category = data.get("category", "").strip()
        goal_amount = data.get("goal_amount")
        if goal_amount is not None:
            goal_amount = float(goal_amount)
        funding_model = data.get("funding_model", "all-or-nothing").strip()
        end_date = data.get("end_date", "").strip()
    else:
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "").strip()
        goal_amount = request.form.get("goal_amount", type=float)
        funding_model = request.form.get("funding_model", "all-or-nothing").strip()
        end_date = request.form.get("end_date", "").strip()

    if not title or not description or not category or not goal_amount or not end_date:
        if is_json:
            return jsonify({"error": "Missing required fields"}), 400
        abort(400)

    campaigns = _get_campaigns()
    new_id = max((c["id"] for c in campaigns), default=0) + 1
    new_campaign = {
        "id": new_id,
        "title": title,
        "creator_id": user_id,
        "description": description,
        "category": category,
        "goal_amount": goal_amount,
        "raised_amount": 0,
        "backer_count": 0,
        "funding_model": funding_model,
        "status": "active",
        "start_date": datetime.now().strftime("%Y-%m-%d"),
        "end_date": end_date,
        "reward_tiers": [],
        "updates": []
    }
    campaigns.append(new_campaign)
    _save_campaigns(campaigns)

    # Update user created_campaigns
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if user:
        user.setdefault("created_campaigns", []).append(new_id)
        _save_users(users)

    if is_json:
        return jsonify({"campaign_id": new_id, "campaign": new_campaign}), 201
    return redirect(url_for("crowdfunding-donations.campaign_detail", campaign_id=new_id))


@blueprint.route("/campaign/<int:campaign_id>/update", methods=["POST"])
def form_post_update(campaign_id):
    if "user_id" not in session:
        if request.is_json:
            return jsonify({"error": "Authentication required"}), 401
        return redirect(url_for("crowdfunding-donations.login_page"))
    user_id = session["user_id"]
    campaigns = _get_campaigns()
    campaign = next((c for c in campaigns if c["id"] == campaign_id), None)
    if not campaign or campaign["creator_id"] != user_id:
        if request.is_json:
            return jsonify({"error": "Forbidden"}), 403
        abort(403)
    # Accept both form data and JSON
    if request.is_json:
        data = request.get_json(silent=True) or {}
        title = data.get("title", "").strip()
        content = data.get("content", "").strip()
    else:
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
    if not title or not content:
        if request.is_json:
            return jsonify({"error": "title and content required"}), 400
        abort(400)
    campaign["updates"].append({
        "date": datetime.now().strftime("%Y-%m-%d"),
        "title": title,
        "content": content
    })
    _save_campaigns(campaigns)
    if request.is_json:
        return jsonify({"status": "ok", "update": campaign["updates"][-1]})
    return redirect(url_for("crowdfunding-donations.campaign_detail", campaign_id=campaign_id))


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/campaigns")
def api_campaigns():
    campaigns = _get_campaigns()
    q = request.args.get("q", "").strip()
    cat = request.args.get("category", "").strip()
    status = request.args.get("status", "").strip()
    sort = request.args.get("sort", "").strip()
    limit = request.args.get("limit", type=int)

    results = list(campaigns)
    if q:
        results = _search_campaigns(results, q)
    if cat:
        results = [c for c in results if c["category"] == cat]
    if status:
        results = [c for c in results if c["status"] == status]
    if sort == "most_funded":
        results.sort(key=lambda c: c["raised_amount"], reverse=True)
    elif sort == "most_backed":
        results.sort(key=lambda c: c["backer_count"], reverse=True)
    elif sort == "newest":
        results.sort(key=lambda c: c["start_date"], reverse=True)
    elif sort == "ending_soon":
        results.sort(key=lambda c: c["end_date"])
    elif sort == "goal_asc":
        results.sort(key=lambda c: c["goal_amount"])
    elif sort == "goal_desc":
        results.sort(key=lambda c: c["goal_amount"], reverse=True)

    for c in results:
        c["funding_pct"] = _funding_pct(c)

    if limit:
        results = results[:limit]
    return jsonify(results)


@blueprint.route("/api/campaigns/<int:campaign_id>")
def api_campaign(campaign_id):
    campaign = _get_campaign(campaign_id)
    if campaign is None:
        abort(404)
    campaign["funding_pct"] = _funding_pct(campaign)
    return jsonify(campaign)


@blueprint.route("/api/campaigns/<int:campaign_id>/pledge", methods=["POST"])
def api_pledge(campaign_id):
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id") or session.get("user_id")
    tier_id = data.get("tier_id")
    amount = data.get("amount")

    if not user_id:
        return jsonify({"error": "Authentication required"}), 401

    campaigns = _get_campaigns()
    campaign = next((c for c in campaigns if c["id"] == campaign_id), None)
    if not campaign:
        abort(404)
    if campaign["status"] not in ("active", "funded"):
        return jsonify({"error": "Campaign is not accepting pledges"}), 400

    tier = None
    if tier_id:
        tier = next((t for t in campaign["reward_tiers"] if t["id"] == tier_id), None)
        if tier:
            amount = amount or tier["amount"]
            if tier["quantity_claimed"] >= tier["quantity_available"]:
                return jsonify({"error": "Tier sold out"}), 400

    if not amount or amount <= 0:
        return jsonify({"error": "Invalid amount"}), 400

    campaign["raised_amount"] += amount
    campaign["backer_count"] += 1
    if tier:
        tier["quantity_claimed"] += 1
    if campaign["raised_amount"] >= campaign["goal_amount"] and campaign["status"] == "active":
        campaign["status"] = "funded"
    _save_campaigns(campaigns)

    pledges = _load_pledges()
    new_id = max((p["id"] for p in pledges), default=0) + 1
    pledge = {
        "id": new_id,
        "user_id": user_id,
        "campaign_id": campaign_id,
        "amount": amount,
        "tier_id": tier_id,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "status": "completed"
    }
    pledges.append(pledge)
    _save_pledges(pledges)

    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if user:
        user.setdefault("backed_campaigns", []).append({
            "campaign_id": campaign_id,
            "amount": amount,
            "tier_id": tier_id
        })
        _save_users(users)

    return jsonify({"pledge_id": new_id, "new_raised": campaign["raised_amount"],
                    "new_status": campaign["status"],
                    "funding_pct": _funding_pct(campaign)})


@blueprint.route("/api/campaigns/<int:campaign_id>/update", methods=["POST"])
def api_post_update(campaign_id):
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id") or session.get("user_id")
    title = data.get("title", "").strip()
    content = data.get("content", "").strip()

    if not user_id:
        return jsonify({"error": "Authentication required"}), 401
    if not title or not content:
        return jsonify({"error": "title and content required"}), 400

    campaigns = _get_campaigns()
    campaign = next((c for c in campaigns if c["id"] == campaign_id), None)
    if not campaign:
        abort(404)
    if campaign["creator_id"] != user_id:
        return jsonify({"error": "Only the creator can post updates"}), 403

    update_entry = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "title": title,
        "content": content
    }
    campaign["updates"].append(update_entry)
    _save_campaigns(campaigns)
    return jsonify({"status": "ok", "update": update_entry,
                    "total_updates": len(campaign["updates"])})


@blueprint.route("/api/campaigns", methods=["POST"])
def api_create_campaign():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id") or session.get("user_id")
    title = data.get("title", "").strip()
    description = data.get("description", "").strip()
    category = data.get("category", "").strip()
    goal_amount = data.get("goal_amount")
    funding_model = data.get("funding_model", "all-or-nothing").strip()
    end_date = data.get("end_date", "").strip()

    if not user_id:
        return jsonify({"error": "Authentication required"}), 401
    if not title or not description or not category or not goal_amount or not end_date:
        return jsonify({"error": "Missing required fields"}), 400

    campaigns = _get_campaigns()
    new_id = max((c["id"] for c in campaigns), default=0) + 1
    new_campaign = {
        "id": new_id,
        "title": title,
        "creator_id": user_id,
        "description": description,
        "category": category,
        "goal_amount": goal_amount,
        "raised_amount": 0,
        "backer_count": 0,
        "funding_model": funding_model,
        "status": "active",
        "start_date": datetime.now().strftime("%Y-%m-%d"),
        "end_date": end_date,
        "reward_tiers": [],
        "updates": []
    }
    campaigns.append(new_campaign)
    _save_campaigns(campaigns)

    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if user:
        user.setdefault("created_campaigns", []).append(new_id)
        _save_users(users)

    return jsonify({"campaign_id": new_id, "campaign": new_campaign}), 201


@blueprint.route("/api/categories")
def api_categories():
    campaigns = _get_campaigns()
    counts = Counter(c["category"] for c in campaigns)
    return jsonify([{"name": cat, "count": counts.get(cat, 0)} for cat in _categories_list])


@blueprint.route("/api/stats")
def api_stats():
    campaigns = _get_campaigns()
    cat = request.args.get("category", "").strip()
    if cat:
        campaigns = [c for c in campaigns if c["category"] == cat]
    if not campaigns:
        return jsonify({"count": 0})
    total_raised = sum(c["raised_amount"] for c in campaigns)
    total_backers = sum(c["backer_count"] for c in campaigns)
    total_goal = sum(c["goal_amount"] for c in campaigns)
    funded_count = sum(1 for c in campaigns if c["status"] == "funded")
    active_count = sum(1 for c in campaigns if c["status"] == "active")
    expired_count = sum(1 for c in campaigns if c["status"] == "expired")
    cancelled_count = sum(1 for c in campaigns if c["status"] == "cancelled")
    avg_funding_pct = round(sum(_funding_pct(c) for c in campaigns) / len(campaigns), 1)
    return jsonify({
        "count": len(campaigns),
        "total_raised": total_raised,
        "total_goal": total_goal,
        "total_backers": total_backers,
        "funded_count": funded_count,
        "active_count": active_count,
        "expired_count": expired_count,
        "cancelled_count": cancelled_count,
        "avg_funding_pct": avg_funding_pct,
        "categories": dict(Counter(c["category"] for c in campaigns)),
    })


@blueprint.route("/api/users/<int:user_id>")
def api_user(user_id):
    user = _get_user(user_id)
    if not user:
        abort(404)
    return jsonify({k: v for k, v in user.items() if k != "password"})


@blueprint.route("/api/users/<int:user_id>/pledges")
def api_user_pledges(user_id):
    pledges = _load_pledges()
    user_pledges = [p for p in pledges if p["user_id"] == user_id]
    return jsonify(user_pledges)


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
