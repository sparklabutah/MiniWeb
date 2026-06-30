"""CRM Platform — Salesforce/HubSpot-style CRM.

Data interpreter: reads JSON data files, respects config/config.json settings.
"""
import pathlib
from datetime import datetime

from flask import Blueprint, abort, jsonify, redirect, render_template, request, session, url_for

from app import db

SITE = "crm"
SITE_DIR = pathlib.Path(__file__).resolve().parent
STAGES_ORDERED = ["prospecting", "qualification", "proposal", "negotiation", "closed-won", "closed-lost"]
STAGE_PROBABILITIES = {
    "prospecting": 10,
    "qualification": 25,
    "proposal": 50,
    "negotiation": 75,
    "closed-won": 100,
    "closed-lost": 0,
}

blueprint = Blueprint(
    "crm",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _get_users():
    return db.query(SITE, "users")

def _get_contacts():
    return db.query(SITE, "contacts")

def _get_companies():
    return db.query(SITE, "companies")

def _get_deals():
    return db.query(SITE, "deals")

def _get_activities():
    return db.query(SITE, "activities")

# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

def _company_name(company_id):
    c = db.get_item(SITE, "companies", company_id)
    return c["name"] if c else "Unknown"

def _contact_name(contact_id):
    c = db.get_item(SITE, "contacts", contact_id)
    return c["name"] if c else "Unknown"

def _user_name(user_id):
    u = db.get_item(SITE, "users", user_id)
    return u["name"] if u else "Unknown"

def _current_user():
    if "user_id" in session:
        return db.get_item(SITE, "users", session["user_id"])
    return None

# ---------------------------------------------------------------------------
# Stats helpers
# ---------------------------------------------------------------------------

def _pipeline_stats():
    deals = _get_deals()
    stage_counts = {}
    stage_values = {}
    for s in STAGES_ORDERED:
        stage_deals = [d for d in deals if d["stage"] == s]
        stage_counts[s] = len(stage_deals)
        stage_values[s] = sum(d["amount"] for d in stage_deals)
    return stage_counts, stage_values

def _win_rate():
    deals = _get_deals()
    won = len([d for d in deals if d["stage"] == "closed-won"])
    lost = len([d for d in deals if d["stage"] == "closed-lost"])
    total = won + lost
    if total == 0:
        return 0.0
    return round(won / total * 100, 1)

def _total_pipeline_value():
    deals = _get_deals()
    open_stages = ["prospecting", "qualification", "proposal", "negotiation"]
    return sum(d["amount"] for d in deals if d["stage"] in open_stages)

def _total_revenue():
    deals = _get_deals()
    return sum(d["amount"] for d in deals if d["stage"] == "closed-won")

def _weighted_forecast():
    deals = _get_deals()
    open_stages = ["prospecting", "qualification", "proposal", "negotiation"]
    return sum(d["amount"] * d["probability"] / 100 for d in deals if d["stage"] in open_stages)

# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    deals = _get_deals()
    activities = _get_activities()
    stage_counts, stage_values = _pipeline_stats()
    win_rate = _win_rate()
    total_pipeline = _total_pipeline_value()
    total_revenue = _total_revenue()
    forecast = _weighted_forecast()
    recent_activities = db.query(SITE, "activities", sort="-date", limit=10)
    # Enrich recent activities
    for a in recent_activities:
        a["_contact_name"] = _contact_name(a["contact_id"])
        a["_user_name"] = _user_name(a["user_id"])
    user = _current_user()
    return render_template("crm/index.html",
                           stage_counts=stage_counts, stage_values=stage_values,
                           stages=STAGES_ORDERED, win_rate=win_rate,
                           total_pipeline=total_pipeline, total_revenue=total_revenue,
                           forecast=forecast, recent_activities=recent_activities,
                           user=user, total_deals=len(deals))


@blueprint.route("/contacts")
def contacts_page():
    contacts = _get_contacts()
    q = request.args.get("q", "").strip()
    company_filter = request.args.get("company_id", "", type=str).strip()
    results = list(contacts)
    if q:
        ql = q.lower()
        results = [c for c in results if ql in c["name"].lower() or ql in c["email"].lower()
                    or ql in c.get("title", "").lower()]
    if company_filter:
        try:
            cid = int(company_filter)
            results = [c for c in results if c["company_id"] == cid]
        except ValueError:
            pass
    # Enrich with company name
    for c in results:
        c["_company_name"] = _company_name(c["company_id"])
    companies = _get_companies()
    user = _current_user()
    return render_template("crm/contacts.html", contacts=results, q=q,
                           company_filter=company_filter, companies=companies, user=user)


@blueprint.route("/contact/<int:contact_id>")
def contact_detail(contact_id):
    contact = db.get_item(SITE, "contacts", contact_id)
    if not contact:
        abort(404)
    contact["_company_name"] = _company_name(contact["company_id"])
    deals = db.query(SITE, "deals", where={"contact_id": contact_id})
    for d in deals:
        d["_company_name"] = _company_name(d["company_id"])
        d["_owner_name"] = _user_name(d["owner_id"])
    activities = db.query(SITE, "activities", where={"contact_id": contact_id}, sort="-date")
    for a in activities:
        a["_user_name"] = _user_name(a["user_id"])
    user = _current_user()
    return render_template("crm/contact.html", contact=contact, deals=deals,
                           activities=activities, user=user)


@blueprint.route("/companies")
def companies_page():
    companies = _get_companies()
    q = request.args.get("q", "").strip()
    industry = request.args.get("industry", "").strip()
    results = list(companies)
    if q:
        ql = q.lower()
        results = [c for c in results if ql in c["name"].lower() or ql in c["industry"].lower()]
    if industry:
        results = [c for c in results if c["industry"] == industry]
    industries = sorted(set(c["industry"] for c in companies))
    user = _current_user()
    return render_template("crm/companies.html", companies=results, q=q,
                           industry=industry, industries=industries, user=user)


@blueprint.route("/company/<int:company_id>")
def company_detail(company_id):
    company = db.get_item(SITE, "companies", company_id)
    if not company:
        abort(404)
    contacts = db.query(SITE, "contacts", where={"company_id": company_id})
    deals = db.query(SITE, "deals", where={"company_id": company_id})
    for d in deals:
        d["_contact_name"] = _contact_name(d["contact_id"])
        d["_owner_name"] = _user_name(d["owner_id"])
    user = _current_user()
    return render_template("crm/company.html", company=company, contacts=contacts,
                           deals=deals, user=user)


@blueprint.route("/deals")
def deals_page():
    deals = _get_deals()
    stage_filter = request.args.get("stage", "").strip()
    owner_filter = request.args.get("owner_id", "").strip()
    results = list(deals)
    if stage_filter:
        results = [d for d in results if d["stage"] == stage_filter]
    if owner_filter:
        try:
            oid = int(owner_filter)
            results = [d for d in results if d["owner_id"] == oid]
        except ValueError:
            pass
    # Group by stage for pipeline view
    pipeline = {}
    for s in STAGES_ORDERED:
        pipeline[s] = [d for d in results if d["stage"] == s]
    # Enrich
    for s in STAGES_ORDERED:
        for d in pipeline[s]:
            d["_company_name"] = _company_name(d["company_id"])
            d["_contact_name"] = _contact_name(d["contact_id"])
            d["_owner_name"] = _user_name(d["owner_id"])
    users = _get_users()
    user = _current_user()
    return render_template("crm/deals.html", pipeline=pipeline, stages=STAGES_ORDERED,
                           stage_filter=stage_filter, owner_filter=owner_filter,
                           users=users, user=user)


@blueprint.route("/deal/<int:deal_id>")
def deal_detail(deal_id):
    deal = db.get_item(SITE, "deals", deal_id)
    if not deal:
        abort(404)
    deal["_company_name"] = _company_name(deal["company_id"])
    deal["_contact_name"] = _contact_name(deal["contact_id"])
    deal["_owner_name"] = _user_name(deal["owner_id"])
    activities = db.query(SITE, "activities", where={"deal_id": deal_id}, sort="-date")
    for a in activities:
        a["_contact_name"] = _contact_name(a["contact_id"])
        a["_user_name"] = _user_name(a["user_id"])
    user = _current_user()
    return render_template("crm/deal.html", deal=deal, activities=activities,
                           stages=STAGES_ORDERED, user=user)


@blueprint.route("/activities")
def activities_page():
    activities = _get_activities()
    type_filter = request.args.get("type", "").strip()
    contact_filter = request.args.get("contact_id", "").strip()
    deal_filter = request.args.get("deal_id", "").strip()
    results = list(activities)
    if type_filter:
        results = [a for a in results if a["type"] == type_filter]
    if contact_filter:
        try:
            cid = int(contact_filter)
            results = [a for a in results if a["contact_id"] == cid]
        except ValueError:
            pass
    if deal_filter:
        try:
            did = int(deal_filter)
            results = [a for a in results if a["deal_id"] == did]
        except ValueError:
            pass
    results.sort(key=lambda a: a["date"], reverse=True)
    for a in results:
        a["_contact_name"] = _contact_name(a["contact_id"])
        a["_user_name"] = _user_name(a["user_id"])
        a["_deal_name"] = next((d["name"] for d in _get_deals() if d["id"] == a["deal_id"]), "Unknown")
    user = _current_user()
    return render_template("crm/activities.html", activities=results,
                           type_filter=type_filter, user=user)


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("crm/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _get_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return render_template("crm/login.html", error="Invalid username or password")
    session["user_id"] = user["id"]
    return redirect(url_for("crm.index"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("crm.login_page"))


# ---------------------------------------------------------------------------
# Form mutation routes
# ---------------------------------------------------------------------------

@blueprint.route("/deal/create", methods=["POST"])
def form_create_deal():
    if "user_id" not in session:
        return redirect(url_for("crm.login_page"))
    deals = db.query(SITE, "deals")
    new_id = max((d["id"] for d in deals), default=0) + 1
    stage = request.form.get("stage", "prospecting")
    deal = {
        "id": new_id,
        "name": request.form.get("name", "").strip(),
        "company_id": int(request.form.get("company_id", 0)),
        "contact_id": int(request.form.get("contact_id", 0)),
        "owner_id": session["user_id"],
        "stage": stage,
        "amount": float(request.form.get("amount", 0)),
        "probability": STAGE_PROBABILITIES.get(stage, 0),
        "close_date": request.form.get("close_date", ""),
        "created_date": datetime.now().strftime("%Y-%m-%d"),
    }
    deals.append(deal)
    db.save_collection(SITE, "deals", deals)
    return redirect(url_for("crm.deal_detail", deal_id=new_id))


@blueprint.route("/deal/<int:deal_id>/update-stage", methods=["POST"])
def form_update_deal_stage(deal_id):
    if "user_id" not in session:
        return redirect(url_for("crm.login_page"))
    deals = db.query(SITE, "deals")
    deal = next((d for d in deals if d["id"] == deal_id), None)
    if not deal:
        abort(404)
    new_stage = request.form.get("stage", deal["stage"])
    if new_stage in STAGE_PROBABILITIES:
        deal["stage"] = new_stage
        deal["probability"] = STAGE_PROBABILITIES[new_stage]
    db.save_collection(SITE, "deals", deals)
    return redirect(url_for("crm.deal_detail", deal_id=deal_id))


@blueprint.route("/activity/create", methods=["POST"])
def form_create_activity():
    if "user_id" not in session:
        return redirect(url_for("crm.login_page"))
    activities = db.query(SITE, "activities")
    new_id = max((a["id"] for a in activities), default=0) + 1
    activity = {
        "id": new_id,
        "type": request.form.get("type", "note"),
        "contact_id": int(request.form.get("contact_id", 0)),
        "deal_id": int(request.form.get("deal_id", 0)),
        "user_id": session["user_id"],
        "date": request.form.get("date", datetime.now().strftime("%Y-%m-%d")),
        "description": request.form.get("description", "").strip(),
        "duration_minutes": int(request.form.get("duration_minutes", 0)),
    }
    activities.append(activity)
    db.save_collection(SITE, "activities", activities)
    redirect_to = request.form.get("redirect_to", "")
    if redirect_to:
        return redirect(redirect_to)
    return redirect(url_for("crm.activities_page"))


@blueprint.route("/contact/create", methods=["POST"])
def form_create_contact():
    if "user_id" not in session:
        return redirect(url_for("crm.login_page"))
    contacts = db.query(SITE, "contacts")
    new_id = max((c["id"] for c in contacts), default=0) + 1
    contact = {
        "id": new_id,
        "name": request.form.get("name", "").strip(),
        "email": request.form.get("email", "").strip(),
        "phone": request.form.get("phone", "").strip(),
        "company_id": int(request.form.get("company_id", 0)),
        "title": request.form.get("title", "").strip(),
        "created_date": datetime.now().strftime("%Y-%m-%d"),
    }
    contacts.append(contact)
    db.save_collection(SITE, "contacts", contacts)
    return redirect(url_for("crm.contact_detail", contact_id=new_id))


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/contacts")
def api_contacts():
    contacts = _get_contacts()
    q = request.args.get("q", "").strip()
    company_id = request.args.get("company_id", type=int)
    results = list(contacts)
    if q:
        ql = q.lower()
        results = [c for c in results if ql in c["name"].lower() or ql in c["email"].lower()
                    or ql in c.get("title", "").lower()]
    if company_id:
        results = [c for c in results if c["company_id"] == company_id]
    return jsonify(results)


@blueprint.route("/api/contacts/<int:contact_id>")
def api_contact(contact_id):
    contact = db.get_item(SITE, "contacts", contact_id)
    if not contact:
        abort(404)
    return jsonify(contact)


@blueprint.route("/api/contacts", methods=["POST"])
def api_create_contact():
    data = request.get_json(silent=True) or {}
    contacts = db.query(SITE, "contacts")
    new_id = max((c["id"] for c in contacts), default=0) + 1
    contact = {
        "id": new_id,
        "name": data.get("name", "").strip(),
        "email": data.get("email", "").strip(),
        "phone": data.get("phone", "").strip(),
        "company_id": int(data.get("company_id", 0)),
        "title": data.get("title", "").strip(),
        "created_date": datetime.now().strftime("%Y-%m-%d"),
    }
    contacts.append(contact)
    db.save_collection(SITE, "contacts", contacts)
    return jsonify(contact), 201


@blueprint.route("/api/companies")
def api_companies():
    companies = _get_companies()
    q = request.args.get("q", "").strip()
    industry = request.args.get("industry", "").strip()
    results = list(companies)
    if q:
        ql = q.lower()
        results = [c for c in results if ql in c["name"].lower() or ql in c["industry"].lower()]
    if industry:
        results = [c for c in results if c["industry"] == industry]
    return jsonify(results)


@blueprint.route("/api/companies/<int:company_id>")
def api_company(company_id):
    company = db.get_item(SITE, "companies", company_id)
    if not company:
        abort(404)
    return jsonify(company)


@blueprint.route("/api/deals")
def api_deals():
    deals = _get_deals()
    stage = request.args.get("stage", "").strip()
    owner_id = request.args.get("owner_id", type=int)
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    sort = request.args.get("sort", "").strip()
    results = list(deals)
    if stage:
        results = [d for d in results if d["stage"] == stage]
    if owner_id:
        results = [d for d in results if d["owner_id"] == owner_id]
    if date_from:
        results = [d for d in results if d["close_date"] >= date_from]
    if date_to:
        results = [d for d in results if d["close_date"] <= date_to]
    if sort == "amount_asc":
        results.sort(key=lambda d: d["amount"])
    elif sort == "amount_desc":
        results.sort(key=lambda d: -d["amount"])
    elif sort == "close_date":
        results.sort(key=lambda d: d["close_date"])
    elif sort == "name":
        results.sort(key=lambda d: d["name"].lower())
    return jsonify(results)


@blueprint.route("/api/deals/<int:deal_id>")
def api_deal(deal_id):
    deal = db.get_item(SITE, "deals", deal_id)
    if not deal:
        abort(404)
    return jsonify(deal)


@blueprint.route("/api/deals", methods=["POST"])
def api_create_deal():
    data = request.get_json(silent=True) or {}
    deals = db.query(SITE, "deals")

    # If an id is provided, update existing deal
    deal_id = data.get("id")
    if deal_id:
        deal = next((d for d in deals if d["id"] == deal_id), None)
        if deal:
            for key in ["name", "company_id", "contact_id", "owner_id", "stage", "amount", "close_date"]:
                if key in data:
                    deal[key] = data[key]
            if "stage" in data and data["stage"] in STAGE_PROBABILITIES:
                deal["probability"] = STAGE_PROBABILITIES[data["stage"]]
            db.save_collection(SITE, "deals", deals)
            return jsonify(deal)

    # Create new deal
    new_id = max((d["id"] for d in deals), default=0) + 1
    stage = data.get("stage", "prospecting")
    deal = {
        "id": new_id,
        "name": data.get("name", "").strip(),
        "company_id": int(data.get("company_id", 0)),
        "contact_id": int(data.get("contact_id", 0)),
        "owner_id": int(data.get("owner_id", 0)),
        "stage": stage,
        "amount": float(data.get("amount", 0)),
        "probability": STAGE_PROBABILITIES.get(stage, 0),
        "close_date": data.get("close_date", ""),
        "created_date": datetime.now().strftime("%Y-%m-%d"),
    }
    deals.append(deal)
    db.save_collection(SITE, "deals", deals)
    return jsonify(deal), 201


@blueprint.route("/api/activities")
def api_activities():
    activities = _get_activities()
    act_type = request.args.get("type", "").strip()
    contact_id = request.args.get("contact_id", type=int)
    deal_id = request.args.get("deal_id", type=int)
    results = list(activities)
    if act_type:
        results = [a for a in results if a["type"] == act_type]
    if contact_id:
        results = [a for a in results if a["contact_id"] == contact_id]
    if deal_id:
        results = [a for a in results if a["deal_id"] == deal_id]
    results.sort(key=lambda a: a["date"], reverse=True)
    return jsonify(results)


@blueprint.route("/api/activities", methods=["POST"])
def api_create_activity():
    data = request.get_json(silent=True) or {}
    activities = db.query(SITE, "activities")
    new_id = max((a["id"] for a in activities), default=0) + 1
    activity = {
        "id": new_id,
        "type": data.get("type", "note"),
        "contact_id": int(data.get("contact_id", 0)),
        "deal_id": int(data.get("deal_id", 0)),
        "user_id": int(data.get("user_id", 0)),
        "date": data.get("date", datetime.now().strftime("%Y-%m-%d")),
        "description": data.get("description", "").strip(),
        "duration_minutes": int(data.get("duration_minutes", 0)),
    }
    activities.append(activity)
    db.save_collection(SITE, "activities", activities)
    return jsonify(activity), 201


@blueprint.route("/api/pipeline")
def api_pipeline():
    stage_counts, stage_values = _pipeline_stats()
    result = []
    for s in STAGES_ORDERED:
        result.append({
            "stage": s,
            "count": stage_counts[s],
            "total_value": stage_values[s],
        })
    return jsonify(result)


@blueprint.route("/api/stats")
def api_stats():
    deals = _get_deals()
    won = [d for d in deals if d["stage"] == "closed-won"]
    lost = [d for d in deals if d["stage"] == "closed-lost"]
    open_stages = ["prospecting", "qualification", "proposal", "negotiation"]
    open_deals = [d for d in deals if d["stage"] in open_stages]
    total_closed = len(won) + len(lost)
    win_rate = round(len(won) / total_closed * 100, 1) if total_closed > 0 else 0.0
    total_pipeline = sum(d["amount"] for d in open_deals)
    total_revenue = sum(d["amount"] for d in won)
    weighted_forecast = sum(d["amount"] * d["probability"] / 100 for d in open_deals)
    avg_deal_size = round(total_revenue / len(won), 2) if won else 0
    return jsonify({
        "total_deals": len(deals),
        "open_deals": len(open_deals),
        "closed_won": len(won),
        "closed_lost": len(lost),
        "win_rate": win_rate,
        "total_pipeline": total_pipeline,
        "total_revenue": total_revenue,
        "weighted_forecast": round(weighted_forecast, 2),
        "avg_deal_size": avg_deal_size,
    })


@blueprint.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    users = _get_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return jsonify({"error": "Invalid credentials"}), 401
    session["user_id"] = user["id"]
    return jsonify({"user_id": user["id"], "username": user["username"], "name": user["name"]})
