"""Crowdfunding & Donations platform (Kickstarter / GoFundMe style).

Data interpreter: reads synthesized JSON files, respects config/config.json,
and serves through Flask routes.  Raw data files are never modified except for
mutable user/pledge state.
"""
import pathlib
from collections import Counter
from datetime import datetime

from flask import (Blueprint, Response, abort, jsonify, redirect,
                   render_template, request, session, url_for)
from app import db
from app.events import emit
from app.handlers.email_handler import _add_email

SITE = "crowdfunding-donations"
SITE_DIR = pathlib.Path(__file__).resolve().parent
blueprint = Blueprint(
    "crowdfunding-donations",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

_categories_list = ["technology", "art", "games", "film", "music", "community", "design", "food"]


def _get_campaigns():
    return db.query(SITE, "campaigns")


def _get_campaign(campaign_id):
    return db.get_item(SITE, "campaigns", campaign_id)


def _save_campaigns(campaigns):
    db.save_collection(SITE, "campaigns", campaigns)


def _load_users():
    return db.query(SITE, "users")


def _save_users(users):
    db.save_collection(SITE, "users", users)


def _get_user(user_id):
    return db.get_item(SITE, "users", user_id)


def _load_pledges():
    return db.query(SITE, "pledges")


def _save_pledges(pledges):
    db.save_collection(SITE, "pledges", pledges)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _funding_pct(campaign):
    if campaign["goal_amount"] <= 0:
        return 0
    return round(campaign["raised_amount"] / campaign["goal_amount"] * 100, 1)


def _build_reward_tiers(raw_tiers):
    """Normalise a list of loosely-typed tier dicts into stored reward tiers.

    Each raw tier may supply: name/title, amount, description, limit (or
    quantity_available), fulfillment. Tiers missing a name or a positive
    amount are dropped. IDs are assigned 1..N in author order.
    """
    tiers = []
    next_id = 1
    for raw in raw_tiers or []:
        name = str(raw.get("name") or raw.get("title") or "").strip()
        try:
            amount = float(raw.get("amount") or 0)
        except (TypeError, ValueError):
            amount = 0
        if not name or amount <= 0:
            continue
        limit = raw.get("quantity_available", raw.get("limit"))
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 0
        if limit <= 0:
            limit = 100  # default cap when the author leaves the limit blank
        fulfillment = str(raw.get("fulfillment") or "physical").strip().lower()
        if fulfillment not in ("physical", "digital"):
            fulfillment = "physical"
        tiers.append({
            "id": next_id,
            "name": name,
            "amount": amount,
            "description": str(raw.get("description") or "").strip(),
            "quantity_available": limit,
            "quantity_claimed": 0,
            "fulfillment": fulfillment,
        })
        next_id += 1
    return tiers


def _reward_tiers_from_form(form):
    """Read the parallel-array reward-tier fields from a submitted form."""
    names = form.getlist("tier_name")
    amounts = form.getlist("tier_amount")
    descriptions = form.getlist("tier_description")
    limits = form.getlist("tier_limit")
    fulfillments = form.getlist("tier_fulfillment")
    raw = []
    for i in range(len(names)):
        raw.append({
            "name": names[i],
            "amount": amounts[i] if i < len(amounts) else "",
            "description": descriptions[i] if i < len(descriptions) else "",
            "limit": limits[i] if i < len(limits) else "",
            "fulfillment": fulfillments[i] if i < len(fulfillments) else "physical",
        })
    return _build_reward_tiers(raw)


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
    saved_ids = []
    if "user_id" in session:
        user = _get_user(session["user_id"])
        if user:
            saved_ids = user.get("saved_campaigns", [])

    for c in results:
        c["funding_pct"] = _funding_pct(c)

    return render_template("crowdfunding-donations/index.html",
                           campaigns=results, categories=_categories_list,
                           q=q, cat=cat, status_filter=status, sort=sort,
                           user=user, saved_ids=saved_ids)


@blueprint.route("/campaign/<int:campaign_id>")
def campaign_detail(campaign_id):
    campaign = _get_campaign(campaign_id)
    if campaign is None:
        abort(404)
    campaign["funding_pct"] = _funding_pct(campaign)
    creator = _get_user(campaign["creator_id"])
    user = None
    is_saved = False
    is_following = False
    is_subscribed = False
    if "user_id" in session:
        user = _get_user(session["user_id"])
        if user:
            is_saved = campaign_id in user.get("saved_campaigns", [])
            is_following = campaign["creator_id"] in user.get("followed_creators", [])
            is_subscribed = campaign_id in user.get("subscribed_campaigns", [])
    related = [c for c in _get_campaigns()
               if c["category"] == campaign["category"] and c["id"] != campaign_id][:4]
    for r in related:
        r["funding_pct"] = _funding_pct(r)
    return render_template("crowdfunding-donations/campaign.html",
                           campaign=campaign, creator=creator,
                           related=related, user=user,
                           is_saved=is_saved, is_following=is_following,
                           is_subscribed=is_subscribed)


@blueprint.route("/category/<cat_name>")
def category_page(cat_name):
    campaigns = _get_campaigns()
    filtered = [c for c in campaigns if c["category"] == cat_name]
    for c in filtered:
        c["funding_pct"] = _funding_pct(c)
    user = None
    saved_ids = []
    if "user_id" in session:
        user = _get_user(session["user_id"])
        if user:
            saved_ids = user.get("saved_campaigns", [])
    return render_template("crowdfunding-donations/category.html",
                           campaigns=filtered, category=cat_name,
                           categories=_categories_list, user=user,
                           saved_ids=saved_ids)


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
    saved = []
    for sid in user.get("saved_campaigns", []):
        c = next((c for c in campaigns if c["id"] == sid), None)
        if c:
            c["funding_pct"] = _funding_pct(c)
            saved.append(c)
    return render_template("crowdfunding-donations/dashboard.html",
                           user=user, created_campaigns=created,
                           backed_campaigns=backed_details,
                           saved_campaigns=saved)


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("crowdfunding-donations/login.html", error=None,
                           next_url=request.args.get("next", ""), tab="login")


@blueprint.route("/login", methods=["POST"])
def login_submit():
    if request.is_json:
        data = request.get_json(silent=True) or {}
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()
    else:
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
    users = _load_users()  # small table
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        if request.is_json:
            return jsonify({"error": "Invalid credentials"}), 401
        return render_template("crowdfunding-donations/login.html",
                               error="Invalid username or password", tab="login")
    session["user_id"] = user["id"]
    emit("signup", user_id=user["id"], site_name="crowdfunding-donations", username=request.form.get("username", ""), password=request.form.get("password", ""), email="")
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

def _record_pledge(campaigns, campaign, tier, tier_id, amount, user_id, extra=None):
    """Apply a pledge: campaign totals, pledge row, user history, email.
    Returns the new pledge id. `extra` fields are stored on the pledge row."""
    campaign["raised_amount"] += amount
    campaign["backer_count"] += 1
    if tier:
        tier["quantity_claimed"] += 1
    if campaign["raised_amount"] >= campaign["goal_amount"] and campaign["status"] == "active":
        campaign["status"] = "funded"
    _save_campaigns(campaigns)

    pledges = _load_pledges()
    new_id = max((p["id"] for p in pledges), default=0) + 1
    row = {
        "id": new_id,
        "user_id": user_id,
        "campaign_id": campaign["id"],
        "amount": amount,
        "tier_id": tier_id,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "status": "completed"
    }
    row.update(extra or {})
    pledges.append(row)
    _save_pledges(pledges)

    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if user:
        user.setdefault("backed_campaigns", []).append({
            "campaign_id": campaign["id"],
            "amount": amount,
            "tier_id": tier_id
        })
        _save_users(users)

    _add_email(user_id, "noreply@crowdfunding.lakeport.local",
               "Pledge confirmed",
               f'Your pledge of ${amount:.2f} to "{campaign["title"]}" has been confirmed. Thank you for your support!')
    return new_id


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
        account_type = data.get("account_type", "checking")
        if tier_id is not None:
            tier_id = int(tier_id)
        if amount is not None:
            amount = float(amount)
    else:
        tier_id = request.form.get("tier_id", type=int)
        amount = request.form.get("amount", type=float)
        account_type = request.form.get("account_type", "checking")

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

    new_id = _record_pledge(campaigns, campaign, tier, tier_id, amount, user_id)

    if is_json:
        # API path: direct payment bridge call (no 2FA)
        try:
            from app.bridges import on_payment
            on_payment(user_id=user_id, recipient=campaign["title"],
                       amount=amount, category="Donations",
                       account_type=account_type)
        except Exception:
            pass  # bridge failure should never block the main flow
        return jsonify({"pledge_id": new_id, "new_raised": campaign["raised_amount"],
                        "backer_count": campaign["backer_count"],
                        "new_status": campaign["status"]})

    # Form path: 2FA verification before completing the payment
    from app.events import request_2fa
    verify_url = request_2fa("payment",
                             return_url=url_for("crowdfunding-donations.campaign_detail",
                                                campaign_id=campaign_id),
                             user_id=user_id,
                             recipient=campaign["title"],
                             amount=amount,
                             category="Donations",
                             account_type=account_type)
    return redirect(verify_url)


@blueprint.route("/campaign/<int:campaign_id>/checkout", methods=["GET", "POST"])
def checkout(campaign_id):
    """Pledge checkout: backer info, conditional shipping, payment method,
    funding-model consent — then hands off to the shared 2FA flow."""
    if "user_id" not in session:
        return redirect(url_for("crowdfunding-donations.login_page"))
    user_id = session["user_id"]

    campaigns = _get_campaigns()
    campaign = next((c for c in campaigns if c["id"] == campaign_id), None)
    if not campaign or campaign["status"] not in ("active", "funded"):
        abort(404)

    tier_id = (request.form.get("tier_id", type=int) if request.method == "POST"
               else request.args.get("tier_id", type=int))
    tier = None
    if tier_id:
        tier = next((t for t in campaign["reward_tiers"] if t["id"] == tier_id), None)
        if not tier:
            abort(404)
        if tier["quantity_claimed"] >= tier["quantity_available"]:
            abort(400)
    needs_shipping = bool(tier and tier.get("fulfillment", "physical") == "physical")
    min_amount = tier["amount"] if tier else 1

    users = _load_users()
    me = next((u for u in users if u["id"] == user_id), None)

    if request.method == "GET":
        form = {"backer_name": (me or {}).get("name", ""),
                "email": (me or {}).get("email", ""),
                "amount": tier["amount"] if tier else ""}
        return render_template("crowdfunding-donations/checkout.html",
                               campaign=campaign, tier=tier,
                               needs_shipping=needs_shipping,
                               min_amount=min_amount, form=form, errors={})

    # POST — validate
    f = {k: (request.form.get(k) or "").strip() for k in
         ("backer_name", "email", "amount", "account_type",
          "street", "city", "state", "zip_code")}
    f["anonymous"] = bool(request.form.get("anonymous"))
    f["consent"] = bool(request.form.get("consent"))

    errors = {}
    if not f["backer_name"]:
        errors["backer_name"] = "Name is required"
    if not f["email"] or "@" not in f["email"]:
        errors["email"] = "A valid email is required"
    try:
        amount = float(f["amount"])
    except (TypeError, ValueError):
        amount = 0
    if amount < min_amount:
        errors["amount"] = f"Minimum pledge is ${min_amount:.2f}"
    if f["account_type"] not in ("checking", "credit"):
        errors["account_type"] = "Choose a payment method"
    if needs_shipping:
        for k, label in (("street", "Street address"), ("city", "City"),
                         ("state", "State"), ("zip_code", "ZIP code")):
            if not f[k]:
                errors[k] = f"{label} is required"
    if not f["consent"]:
        errors["consent"] = "Please confirm you understand how you will be charged"

    if errors:
        return render_template("crowdfunding-donations/checkout.html",
                               campaign=campaign, tier=tier,
                               needs_shipping=needs_shipping,
                               min_amount=min_amount, form=f, errors=errors), 400

    extra = {
        "backer_name": f["backer_name"],
        "email": f["email"],
        "anonymous": f["anonymous"],
        "shipping": ({"street": f["street"], "city": f["city"],
                      "state": f["state"], "zip_code": f["zip_code"]}
                     if needs_shipping else None),
    }
    _record_pledge(campaigns, campaign, tier, tier_id, amount, user_id, extra=extra)

    from app.events import request_2fa
    verify_url = request_2fa("payment",
                             return_url=url_for("crowdfunding-donations.campaign_detail",
                                                campaign_id=campaign_id),
                             user_id=user_id,
                             recipient=campaign["title"],
                             amount=amount,
                             category="Donations",
                             account_type=f["account_type"])
    return redirect(verify_url)


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
        story = data.get("story", "").strip()
        reward_tiers = _build_reward_tiers(data.get("reward_tiers"))
    else:
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "").strip()
        goal_amount = request.form.get("goal_amount", type=float)
        funding_model = request.form.get("funding_model", "all-or-nothing").strip()
        end_date = request.form.get("end_date", "").strip()
        story = request.form.get("story", "").strip()
        reward_tiers = _reward_tiers_from_form(request.form)

    if not title or not description or not category or not goal_amount or not end_date:
        if is_json:
            return jsonify({"error": "Missing required fields"}), 400
        abort(400)

    # An optional richer story is folded into the description, which the
    # campaign page renders (with pre-line whitespace) as "About this project".
    if story:
        description = f"{description}\n\n{story}"

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
        "reward_tiers": reward_tiers,
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
    account_type = data.get("account_type", "checking")

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

    # Bridge: notify banking of donation payment
    try:
        from app.bridges import on_payment
        on_payment(user_id=user_id, recipient=campaign["title"],
                   amount=amount, category="Donations",
                   account_type=account_type)
    except Exception:
        pass  # bridge failure should never block the main flow

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
    story = data.get("story", "").strip()
    reward_tiers = _build_reward_tiers(data.get("reward_tiers"))

    if not user_id:
        return jsonify({"error": "Authentication required"}), 401
    if not title or not description or not category or not goal_amount or not end_date:
        return jsonify({"error": "Missing required fields"}), 400

    if story:
        description = f"{description}\n\n{story}"

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
        "reward_tiers": reward_tiers,
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


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

@blueprint.route("/register", methods=["GET"])
def register_page():
    return render_template("crowdfunding-donations/login.html", error=None,
                           next_url=request.args.get("next", ""), tab="register")


@blueprint.route("/register", methods=["POST"])
def register_submit():
    if request.is_json:
        data = request.get_json(silent=True) or {}
        name = data.get("name", "").strip()
        email = data.get("email", "").strip()
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()
    else:
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

    if not name or not username or not password:
        err = "Name, username, and password are required"
        if request.is_json:
            return jsonify({"error": err}), 400
        return render_template("crowdfunding-donations/login.html",
                               error=err, tab="register")

    users = _load_users()
    if any(u["username"] == username for u in users):
        err = "Username already taken"
        if request.is_json:
            return jsonify({"error": err}), 409
        return render_template("crowdfunding-donations/login.html",
                               error=err, tab="register")

    new_id = max((u["id"] for u in users), default=0) + 1
    new_user = {
        "id": new_id, "root_user_id": new_id,
        "username": username, "password": password,
        "name": name, "email": email or f"{username}@fundspark.com",
        "backed_campaigns": [], "created_campaigns": [],
        "saved_campaigns": [], "followed_creators": [],
        "subscribed_campaigns": [],
    }
    users.append(new_user)
    _save_users(users)
    session["user_id"] = new_id
    emit("signup", user_id=new_id, site_name="crowdfunding-donations",
         username=username, password=password, email=new_user["email"])

    if request.is_json:
        return jsonify({"user_id": new_id, "username": username}), 201
    next_url = request.form.get("next", "") or request.args.get("next", "")
    return redirect(next_url or url_for("crowdfunding-donations.dashboard"))


# ---------------------------------------------------------------------------
# Save / bookmark campaigns
# ---------------------------------------------------------------------------

@blueprint.route("/campaign/<int:campaign_id>/save", methods=["POST"])
def form_save_campaign(campaign_id):
    if "user_id" not in session:
        if request.is_json:
            return jsonify({"error": "Authentication required"}), 401
        return redirect(url_for("crowdfunding-donations.login_page"))
    users = _load_users()
    user = next((u for u in users if u["id"] == session["user_id"]), None)
    if not user:
        if request.is_json:
            return jsonify({"error": "User not found"}), 404
        return redirect(url_for("crowdfunding-donations.login_page"))
    saved = user.setdefault("saved_campaigns", [])
    if campaign_id in saved:
        saved.remove(campaign_id)
        action = "unsaved"
    else:
        saved.append(campaign_id)
        action = "saved"
    _save_users(users)
    if request.is_json:
        return jsonify({"action": action, "campaign_id": campaign_id})
    return redirect(request.referrer or url_for("crowdfunding-donations.index"))


# ---------------------------------------------------------------------------
# Follow / unfollow creators
# ---------------------------------------------------------------------------

@blueprint.route("/creator/<int:creator_id>/follow", methods=["POST"])
def form_follow_creator(creator_id):
    if "user_id" not in session:
        if request.is_json:
            return jsonify({"error": "Authentication required"}), 401
        return redirect(url_for("crowdfunding-donations.login_page"))
    users = _load_users()
    user = next((u for u in users if u["id"] == session["user_id"]), None)
    if not user:
        if request.is_json:
            return jsonify({"error": "User not found"}), 404
        return redirect(url_for("crowdfunding-donations.login_page"))
    followed = user.setdefault("followed_creators", [])
    if creator_id in followed:
        followed.remove(creator_id)
        action = "unfollowed"
    else:
        followed.append(creator_id)
        action = "followed"
    _save_users(users)
    if request.is_json:
        return jsonify({"action": action, "creator_id": creator_id})
    return redirect(request.referrer or url_for("crowdfunding-donations.index"))


# ---------------------------------------------------------------------------
# Subscribe / unsubscribe to campaign updates
# ---------------------------------------------------------------------------

@blueprint.route("/campaign/<int:campaign_id>/subscribe", methods=["POST"])
def form_subscribe_campaign(campaign_id):
    if "user_id" not in session:
        if request.is_json:
            return jsonify({"error": "Authentication required"}), 401
        return redirect(url_for("crowdfunding-donations.login_page"))
    users = _load_users()
    user = next((u for u in users if u["id"] == session["user_id"]), None)
    if not user:
        if request.is_json:
            return jsonify({"error": "User not found"}), 404
        return redirect(url_for("crowdfunding-donations.login_page"))
    subs = user.setdefault("subscribed_campaigns", [])
    if campaign_id in subs:
        subs.remove(campaign_id)
        action = "unsubscribed"
    else:
        subs.append(campaign_id)
        action = "subscribed"
    _save_users(users)
    if request.is_json:
        return jsonify({"action": action, "campaign_id": campaign_id})
    return redirect(request.referrer or url_for("crowdfunding-donations.campaign_detail",
                                                 campaign_id=campaign_id))
