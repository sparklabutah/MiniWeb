"""Cascadia Insurance & Lending -- insurance/lending portal.

Reads realistic pre-authored data from DATA_SOURCES_DIR/insurance-loans/
(policies, claims, loans, payments, users).
"""
import json
import pathlib
from datetime import datetime

from flask import (
    Blueprint, abort, jsonify, redirect, render_template, request,
    session, url_for,
)
from app import db
from app.events import emit
from helpers.auth import current_user, browsing_user

SITE = "insurance-loans"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "insurance-loans",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _load_users():
    return db.query(SITE, "users")

def _load_policies():
    return db.query(SITE, "policies")

def _save_policies(data):
    db.save_collection(SITE, "policies", data)

def _load_claims():
    return db.query(SITE, "claims")

def _save_claims(data):
    db.save_collection(SITE, "claims", data)

def _load_loans():
    return db.query(SITE, "loans")

def _save_loans(data):
    db.save_collection(SITE, "loans", data)

def _load_payments():
    return db.query(SITE, "payments")

def _save_payments(data):
    db.save_collection(SITE, "payments", data)

def _get_user(user_id):
    return db.get_item(SITE, "users", user_id)

def _get_current_user():
    return current_user(_get_user, session_keys=("il_user_id",))

def _get_browsing_user():
    return browsing_user(_get_user, session_keys=("il_user_id",), fallback=1)


# ---------------------------------------------------------------------------
# Signature helpers (sign_by_freeformdrawing)
# ---------------------------------------------------------------------------

def _to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _valid_signature_drawing(drawing, points):
    """A drawn signature counts when it's a PNG data URL of plausible size backed
    by enough stroke points that a stray dot doesn't pass as a signature."""
    if not (isinstance(drawing, str) and drawing.startswith("data:image/png;base64,")):
        return False
    if len(points or []) < 8:
        return False
    import base64
    try:
        return len(base64.b64decode(drawing.split(",", 1)[1])) > 500
    except Exception:
        return False


def _needs_signature(rec):
    """A newly-created agreement that requires the user's signature and hasn't
    been signed yet. Pre-existing seed records (no requires_signature flag) are
    left untouched."""
    return bool(rec.get("requires_signature")) and not rec.get("signed")


def _awaiting_signature_docs(user_id):
    """Policies and loans belonging to the user that still need a signature,
    surfaced as small dicts for the dashboard alert bar."""
    docs = []
    for p in db.query(SITE, "policies", where={"user_id": user_id}):
        if _needs_signature(p):
            docs.append({
                "kind": "policy",
                "number": p["policy_number"],
                "sign_url": url_for("insurance-loans.policy_sign_page", policy_id=p["id"]),
            })
    for l in db.query(SITE, "loans", where={"user_id": user_id}):
        if _needs_signature(l):
            docs.append({
                "kind": "loan",
                "number": l["loan_number"],
                "sign_url": url_for("insurance-loans.loan_sign_page", loan_id=l["id"]),
            })
    return docs


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    user, logged_in = _get_browsing_user()
    policies = db.query(SITE, "policies", where={"user_id": user["id"]})
    loans = db.query(SITE, "loans", where={"user_id": user["id"]})
    claims = db.query(SITE, "claims", where={"user_id": user["id"]})
    payments = db.query(SITE, "payments", where={"user_id": user["id"]}, sort="-payment_date", limit=5)

    # Sort loans if requested
    sort = request.args.get("sort", "").strip()
    if sort == "balance_desc":
        loans.sort(key=lambda l: l.get("current_balance", 0), reverse=True)
    elif sort == "balance_asc":
        loans.sort(key=lambda l: l.get("current_balance", 0))
    elif sort == "rate":
        loans.sort(key=lambda l: l.get("interest_rate", 0), reverse=True)

    active_policies = [p for p in policies if p["status"] == "active"]
    active_loans = [l for l in loans if l["status"] == "active"]
    open_claims = [c for c in claims if c["status"] in ("open", "in_review")]
    total_monthly_premiums = sum(p.get("premium_monthly", 0) for p in active_policies)
    total_monthly_loan = sum(l.get("monthly_payment", 0) for l in active_loans)
    total_loan_balance = sum(l.get("current_balance", 0) for l in active_loans)

    # Agreements awaiting the user's signature — surfaced up front (DocuSign-style)
    awaiting_signature = _awaiting_signature_docs(user["id"])

    return render_template(
        "insurance-loans/index.html",
        user=user, logged_in=logged_in,
        policies=policies, loans=loans, claims=claims,
        recent_payments=payments,
        active_policies=active_policies, active_loans=active_loans,
        open_claims=open_claims,
        total_monthly_premiums=total_monthly_premiums,
        total_monthly_loan=total_monthly_loan,
        total_loan_balance=total_loan_balance,
        awaiting_signature=awaiting_signature,
    )


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("insurance-loans/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user:
        return render_template("insurance-loans/login.html",
                               error="Invalid username or password")
    stored_pw = user.get("password", "password")
    if password and password != stored_pw:
        return render_template("insurance-loans/login.html", error="Invalid password")
    session["il_user_id"] = user["id"]
    emit("signup", user_id=user["id"], site_name="insurance-loans", username=username, password=request.form.get("password", ""), email="")
    return redirect(url_for("insurance-loans.index"))


@blueprint.route("/logout")
def logout():
    session.pop("il_user_id", None)
    return redirect(url_for("insurance-loans.index"))


@blueprint.route("/policies")
def policies_page():
    user, logged_in = _get_browsing_user()
    where_filters = {"user_id": user["id"]}
    policy_type = request.args.get("type", "").strip()
    status = request.args.get("status", "").strip()
    if policy_type:
        where_filters["type"] = policy_type
    if status:
        where_filters["status"] = status
    policies = db.query(SITE, "policies", where=where_filters)

    all_policies = db.query(SITE, "policies", where={"user_id": user["id"]})
    types = sorted(set(p["type"] for p in all_policies))
    statuses = sorted(set(p["status"] for p in all_policies))

    return render_template(
        "insurance-loans/policies.html",
        user=user, logged_in=logged_in, policies=policies,
        types=types, statuses=statuses,
        selected_type=policy_type, selected_status=status,
    )


@blueprint.route("/policy/<int:policy_id>")
def policy_detail(policy_id):
    user, logged_in = _get_browsing_user()
    policy = db.get_item(SITE, "policies", policy_id)
    if not policy:
        abort(404)
    claims = db.query(SITE, "claims", where={"policy_number": policy["policy_number"]})
    payments = db.query(SITE, "payments", where={"related_policy": policy["policy_number"]}, sort="-payment_date")
    return render_template(
        "insurance-loans/policy_detail.html",
        user=user, logged_in=logged_in, policy=policy,
        claims=claims, payments=payments,
    )


@blueprint.route("/policy/<int:policy_id>/document")
def policy_document(policy_id):
    """Render a dense insurance policy document styled as a PDF."""
    user, logged_in = _get_browsing_user()
    policy = db.get_item(SITE, "policies", policy_id)
    if not policy:
        abort(404)
    import json as _json
    coverage = policy.get("coverage", {})
    if isinstance(coverage, str):
        try:
            coverage = _json.loads(coverage)
        except (ValueError, TypeError):
            coverage = {}
    vehicle = policy.get("vehicle", {})
    if isinstance(vehicle, str):
        try:
            vehicle = _json.loads(vehicle)
        except (ValueError, TypeError):
            vehicle = {}
    # Note: saving the document to the user's files is an explicit action via the
    # "Save to my files" button (POST /policy/<id>/save-to-files), not a side
    # effect of viewing — so merely opening the document no longer creates a file.
    return render_template(
        "insurance-loans/policy_document.html",
        policy=policy, coverage=coverage, vehicle=vehicle,
        user=user, logged_in=logged_in,
    )


@blueprint.route("/policy/<int:policy_id>/save-to-files", methods=["POST"])
def policy_save_to_files(policy_id):
    """Save the policy document as a real file into the user's files.

    Persists the policy document through the shared ``file_created`` event, so
    the cloud-storage handler creates a file entry that surfaces in the file
    picker / Cloud Storage files list. This is a normal /sites/... route so the
    action is captured by /_admin/log.
    """
    policy = db.get_item(SITE, "policies", policy_id)
    if not policy:
        abort(404)

    owner_id = policy.get("user_id", 1)
    filename = f"Policy {policy['policy_number']}"
    emit("file_created", user_id=owner_id, filename=filename,
         file_type="document", source_site="insurance-loans",
         source_id=str(policy_id))

    return jsonify({
        "status": "saved",
        "policy_id": policy_id,
        "filename": f"{filename}.doc",
        "message": f"Saved “{filename}” to your files.",
    })


@blueprint.route("/policies/new", methods=["GET"])
def buy_policy_page():
    """Quote-and-enroll form for a brand new policy."""
    user, logged_in = _get_browsing_user()
    return render_template(
        "insurance-loans/buy_policy.html",
        user=user, logged_in=logged_in,
        today=datetime.now().strftime("%Y-%m-%d"),
    )


@blueprint.route("/policies/new", methods=["POST"])
def buy_policy_submit():
    """Create a new policy. Every new policy is issued 'awaiting_signature' and
    requires the policyholder's drawn signature before it takes effect."""
    user, logged_in = _get_browsing_user()

    policy_type = (request.form.get("type", "") or "auto").strip()
    holder = (request.form.get("policyholder_name", "") or user["display_name"]).strip()
    premium_monthly = _to_float(request.form.get("premium_monthly"), 120.0)
    deductible = int(_to_float(request.form.get("deductible"), 500))
    coverage_amount = _to_float(request.form.get("coverage_amount"), 100000)
    effective = (request.form.get("effective_date", "") or datetime.now().strftime("%Y-%m-%d")).strip()

    new_id = db.next_id(SITE, "policies")
    today = datetime.now().strftime("%Y-%m-%d")
    policy_number = f"POL-{datetime.now().year}-{new_id:05d}"

    new_policy = {
        "id": new_id,
        "policy_number": policy_number,
        "user_id": user["id"],
        "root_user_id": user.get("root_user_id", user["id"]),
        "policyholder_name": holder,
        "type": policy_type,
        "subtype": "standard",
        # not in force until signed
        "status": "awaiting_signature",
        "requires_signature": True,
        "signed": False,
        "effective_date": effective,
        "renewal_date": "",
        "expiration_date": "",
        "premium_monthly": round(premium_monthly, 2),
        "premium_annual": round(premium_monthly * 12, 2),
        "deductible": deductible,
        "coverage": {"liability": coverage_amount},
        "vehicle": {},
        "agent": "Cascadia Direct",
        "agent_phone": "1-800-555-0199",
        "underwriter": "Cascadia Mutual Insurance Company",
        "notes": "Policy purchased online. Awaiting signature.",
        "property_address": "",
        "landlord_name": "",
        "autopay_enabled": False,
        "paperless_billing": False,
        "email_notifications": True,
        "sms_alerts": False,
    }
    db.save_item(SITE, "policies", new_id, new_policy)
    # policy isn't in force until it's signed — take the user straight to signing
    return redirect(url_for("insurance-loans.policy_sign_page", policy_id=new_id))


@blueprint.route("/policy/<int:policy_id>/sign", methods=["GET"])
def policy_sign_page(policy_id):
    """DocuSign-style signing surface for a policy (sign_by_freeformdrawing)."""
    user, logged_in = _get_browsing_user()
    policy = db.get_item(SITE, "policies", policy_id)
    if not policy:
        abort(404)
    summary = [
        ("Policy Number", policy["policy_number"]),
        ("Policyholder", policy.get("policyholder_name", "")),
        ("Policy Type", (policy.get("type", "") or "").replace("_", " ").title()),
        ("Monthly Premium", "${:,.2f}".format(policy.get("premium_monthly", 0) or 0)),
        ("Deductible", "${:,.0f}".format(policy.get("deductible", 0) or 0)),
        ("Effective Date", policy.get("effective_date", "") or "--"),
        ("Status", (policy.get("status", "") or "").replace("_", " ").title()),
    ]
    return render_template(
        "insurance-loans/sign_document.html",
        user=user, logged_in=logged_in,
        kind="policy",
        title="Insurance Policy Agreement",
        number=policy["policy_number"],
        signer_name=policy.get("policyholder_name", user["display_name"]),
        signed=bool(policy.get("signed")),
        signed_date=policy.get("signed_date", ""),
        summary=summary,
        cert_text=(
            "By signing below, I accept the terms and conditions of this insurance "
            "policy and authorize Cascadia Mutual Insurance Company to place it in "
            "force. I certify that the information provided is true and complete."
        ),
        sign_url=url_for("insurance-loans.api_policy_sign", policy_id=policy_id),
        detail_url=url_for("insurance-loans.policy_detail", policy_id=policy_id),
    )


@blueprint.route("/claims")
def claims_page():
    user, logged_in = _get_browsing_user()
    status = request.args.get("status", "").strip()
    claim_type = request.args.get("type", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    where_c = {"user_id": user["id"]}
    if status:
        where_c["status"] = status
    if claim_type:
        where_c["type"] = claim_type
    claims = db.query(SITE, "claims", where=where_c, sort="-date_filed")
    if date_from:
        claims = [c for c in claims if c["date_filed"] >= date_from]
    if date_to:
        claims = [c for c in claims if c["date_filed"] <= date_to]

    all_claims = db.query(SITE, "claims", where={"user_id": user["id"]})
    statuses = sorted(set(c["status"] for c in all_claims))
    types = sorted(set(c["type"] for c in all_claims))

    return render_template(
        "insurance-loans/claims.html",
        user=user, logged_in=logged_in, claims=claims,
        statuses=statuses, types=types,
        selected_status=status, selected_type=claim_type,
        date_from=date_from, date_to=date_to,
    )


@blueprint.route("/claim/<int:claim_id>")
def claim_detail(claim_id):
    user, logged_in = _get_browsing_user()
    claim = db.get_item(SITE, "claims", claim_id)
    if not claim:
        abort(404)
    policies_match = db.query(SITE, "policies", where={"policy_number": claim["policy_number"]}, limit=1)
    policy = policies_match[0] if policies_match else None
    return render_template(
        "insurance-loans/claim_detail.html",
        user=user, logged_in=logged_in, claim=claim, policy=policy,
    )


@blueprint.route("/file-claim", methods=["GET"])
def file_claim_page():
    user, logged_in = _get_browsing_user()
    policies = db.query(SITE, "policies", where={"user_id": user["id"], "status": "active"})
    return render_template(
        "insurance-loans/file_claim.html",
        user=user, logged_in=logged_in, policies=policies, result=None,
    )


@blueprint.route("/file-claim", methods=["POST"])
def file_claim_submit():
    user = _get_current_user()
    if not user:
        return render_template("insurance-loans/login.html",
                               error="Please log in first")
    policies = db.query(SITE, "policies", where={"user_id": user["id"], "status": "active"})

    policy_number = request.form.get("policy_number", "").strip()
    claim_type = request.form.get("type", "").strip()
    incident_date = request.form.get("date_of_incident", "").strip()
    incident_location = request.form.get("incident_location", "").strip()
    description = request.form.get("description", "").strip()

    if not policy_number or not description or not incident_date:
        return render_template(
            "insurance-loans/file_claim.html",
            user=user, logged_in=True, policies=policies,
            result="error_missing",
        )

    policy_matches = db.query(SITE, "policies", where={"policy_number": policy_number}, limit=1)
    policy = policy_matches[0] if policy_matches else None
    if not policy:
        return render_template(
            "insurance-loans/file_claim.html",
            user=user, logged_in=True, policies=policies,
            result="error_policy",
        )

    claims = _load_claims()
    new_id = max(c["id"] for c in claims) + 1 if claims else 1
    today = datetime.now().strftime("%Y-%m-%d")
    claim_number = f"CLM-{datetime.now().year}-{new_id:05d}"

    new_claim = {
        "id": new_id,
        "claim_number": claim_number,
        "policy_number": policy_number,
        "user_id": user["id"],
        "root_user_id": user["root_user_id"],
        "claimant_name": user["display_name"],
        "type": claim_type or "general",
        "status": "open",
        "date_of_incident": incident_date,
        "date_filed": today,
        "date_resolved": None,
        "incident_location": incident_location,
        "description": description,
        "damage_estimate": None,
        "deductible_applied": None,
        "payout_amount": None,
        "payout_date": None,
        "at_fault": None,
        "adjuster": None,
        "adjuster_phone": None,
        "police_report_number": request.form.get("police_report_number", "").strip() or None,
        "repair_shop": None,
        "repair_shop_address": None,
        "notes": "Claim filed online.",
    }
    claims.append(new_claim)
    _save_claims(claims)

    return render_template(
        "insurance-loans/file_claim.html",
        user=user, logged_in=True, policies=policies,
        result="success", claim_number=claim_number,
    )


@blueprint.route("/loans")
def loans_page():
    user, logged_in = _get_browsing_user()
    loan_type = request.args.get("type", "").strip()
    status = request.args.get("status", "").strip()
    where_l = {"user_id": user["id"]}
    if loan_type:
        where_l["type"] = loan_type
    if status:
        where_l["status"] = status
    loans = db.query(SITE, "loans", where=where_l)

    all_loans = db.query(SITE, "loans", where={"user_id": user["id"]})
    types = sorted(set(l["type"] for l in all_loans))
    statuses = sorted(set(l["status"] for l in all_loans))

    return render_template(
        "insurance-loans/loans.html",
        user=user, logged_in=logged_in, loans=loans,
        types=types, statuses=statuses,
        selected_type=loan_type, selected_status=status,
    )


@blueprint.route("/loan/<int:loan_id>")
def loan_detail(loan_id):
    user, logged_in = _get_browsing_user()
    loan = db.get_item(SITE, "loans", loan_id)
    if not loan:
        abort(404)
    payments = db.query(SITE, "payments", where={"related_loan": loan["loan_number"]}, sort="-payment_date")
    return render_template(
        "insurance-loans/loan_detail.html",
        user=user, logged_in=logged_in, loan=loan, payments=payments,
    )


@blueprint.route("/payments")
def payments_page():
    user, logged_in = _get_browsing_user()
    pay_type = request.args.get("type", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    status = request.args.get("status", "").strip()
    where_p = {"user_id": user["id"]}
    if pay_type:
        where_p["type"] = pay_type
    if status:
        where_p["status"] = status
    payments = db.query(SITE, "payments", where=where_p, sort="-payment_date")
    if date_from:
        payments = [p for p in payments if p["payment_date"] >= date_from]
    if date_to:
        payments = [p for p in payments if p["payment_date"] <= date_to]

    all_payments = db.query(SITE, "payments", where={"user_id": user["id"]})
    types = sorted(set(p["type"] for p in all_payments))

    return render_template(
        "insurance-loans/payments.html",
        user=user, logged_in=logged_in, payments=payments,
        types=types, selected_type=pay_type,
        date_from=date_from, date_to=date_to, selected_status=status,
    )


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/policies")
def api_policies():
    user_id = request.args.get("user_id", type=int)
    policy_type = request.args.get("type", "").strip()
    status = request.args.get("status", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    where_f = {}
    if user_id:
        where_f["user_id"] = user_id
    if policy_type:
        where_f["type"] = policy_type
    if status:
        where_f["status"] = status
    policies = db.query(SITE, "policies", where=where_f if where_f else None)
    if date_from:
        policies = [p for p in policies if p.get("effective_date", "") >= date_from]
    if date_to:
        policies = [p for p in policies if p.get("effective_date", "") <= date_to]
    return jsonify(policies)


@blueprint.route("/api/policies/<int:policy_id>")
def api_policy(policy_id):
    policy = db.get_item(SITE, "policies", policy_id)
    if not policy:
        abort(404)
    return jsonify(policy)


@blueprint.route("/api/claims", methods=["GET"])
def api_claims_list():
    user_id = request.args.get("user_id", type=int)
    status = request.args.get("status", "").strip()
    claim_type = request.args.get("type", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    where_f = {}
    if user_id:
        where_f["user_id"] = user_id
    if status:
        where_f["status"] = status
    if claim_type:
        where_f["type"] = claim_type
    claims = db.query(SITE, "claims", where=where_f if where_f else None, sort="-date_filed")
    if date_from:
        claims = [c for c in claims if c["date_filed"] >= date_from]
    if date_to:
        claims = [c for c in claims if c["date_filed"] <= date_to]
    return jsonify(claims)


@blueprint.route("/api/claims", methods=["POST"])
def api_claims_create():
    data = request.get_json(silent=True) or {}
    policy_number = data.get("policy_number", "").strip()
    description = data.get("description", "").strip()
    incident_date = data.get("date_of_incident", "").strip()

    if not policy_number or not description or not incident_date:
        return jsonify({"error": "policy_number, description, and date_of_incident required"}), 400

    policy = next(
        (p for p in _load_policies() if p["policy_number"] == policy_number), None,
    )
    if not policy:
        return jsonify({"error": "Policy not found"}), 404

    claims = _load_claims()
    new_id = max(c["id"] for c in claims) + 1 if claims else 1
    today = datetime.now().strftime("%Y-%m-%d")
    claim_number = f"CLM-{datetime.now().year}-{new_id:05d}"

    new_claim = {
        "id": new_id,
        "claim_number": claim_number,
        "policy_number": policy_number,
        "user_id": policy["user_id"],
        "root_user_id": policy["root_user_id"],
        "claimant_name": policy["policyholder_name"],
        "type": data.get("type", "general"),
        "status": "open",
        "date_of_incident": incident_date,
        "date_filed": today,
        "date_resolved": None,
        "incident_location": data.get("incident_location", ""),
        "description": description,
        "damage_estimate": data.get("damage_estimate"),
        "deductible_applied": None,
        "payout_amount": None,
        "payout_date": None,
        "at_fault": None,
        "adjuster": None,
        "adjuster_phone": None,
        "police_report_number": data.get("police_report_number"),
        "repair_shop": None,
        "repair_shop_address": None,
        "notes": "Claim filed via API.",
    }
    claims.append(new_claim)
    _save_claims(claims)
    return jsonify(new_claim), 201


@blueprint.route("/api/claims/<int:claim_id>")
def api_claim(claim_id):
    claim = db.get_item(SITE, "claims", claim_id)
    if not claim:
        abort(404)
    return jsonify(claim)


@blueprint.route("/api/claims/<int:claim_id>/update", methods=["POST"])
def api_claim_update(claim_id):
    data = request.get_json(silent=True) or {}
    claims = _load_claims()
    claim = next((c for c in claims if c["id"] == claim_id), None)
    if not claim:
        abort(404)

    updatable = [
        "status", "damage_estimate", "deductible_applied", "payout_amount",
        "payout_date", "at_fault", "adjuster", "adjuster_phone",
        "repair_shop", "repair_shop_address", "notes", "date_resolved",
    ]
    for field in updatable:
        if field in data:
            claim[field] = data[field]

    _save_claims(claims)
    return jsonify(claim)


@blueprint.route("/api/loans", methods=["GET"])
def api_loans_list():
    user_id = request.args.get("user_id", type=int)
    loan_type = request.args.get("type", "").strip()
    status = request.args.get("status", "").strip()
    where_f = {}
    if user_id:
        where_f["user_id"] = user_id
    if loan_type:
        where_f["type"] = loan_type
    if status:
        where_f["status"] = status
    loans = db.query(SITE, "loans", where=where_f if where_f else None)
    return jsonify(loans)


@blueprint.route("/api/loans/<int:loan_id>")
def api_loan(loan_id):
    loan = db.get_item(SITE, "loans", loan_id)
    if not loan:
        abort(404)
    return jsonify(loan)


@blueprint.route("/api/loans/<int:loan_id>/pay", methods=["POST"])
def api_loan_pay(loan_id):
    data = request.get_json(silent=True) or {}
    loans = _load_loans()
    loan = next((l for l in loans if l["id"] == loan_id), None)
    if not loan:
        abort(404)
    if loan["status"] == "paid_off":
        return jsonify({"error": "Loan already paid off"}), 400

    amount = data.get("amount")
    if not amount or amount <= 0:
        amount = loan["monthly_payment"]

    loan["current_balance"] = round(max(0, loan["current_balance"] - amount), 2)
    if loan["current_balance"] == 0:
        loan["status"] = "paid_off"
        loan["payments_remaining"] = 0
    else:
        loan["payments_made"] = loan.get("payments_made", 0) + 1
        loan["payments_remaining"] = max(0, loan.get("payments_remaining", 0) - 1)
    _save_loans(loans)

    # Record the payment
    payments = _load_payments()
    new_id = max(p["id"] for p in payments) + 1 if payments else 1
    today = datetime.now().strftime("%Y-%m-%d")
    new_payment = {
        "id": new_id,
        "payment_id": f"ILPAY-{datetime.now().year}-{new_id:04d}",
        "user_id": loan["user_id"],
        "root_user_id": loan["root_user_id"],
        "payer_name": loan["borrower_name"],
        "type": "loan_payment",
        "related_loan": loan["loan_number"],
        "amount": amount,
        "method": data.get("method", "online"),
        "payment_date": today,
        "due_date": loan.get("next_payment_due", today),
        "status": "completed",
        "confirmation_number": f"ILP-{today.replace('-', '')}-{new_id:05d}",
        "notes": f"Loan payment via API",
    }
    payments.append(new_payment)
    _save_payments(payments)

    # Bridge: notify banking of loan payment
    try:
        from app.bridges import on_payment
        account_type = data.get("account_type", "checking")
        on_payment(user_id=loan["user_id"],
                   recipient=f"Cascadia Federal - Loan {loan['loan_number']}",
                   amount=amount, category="Insurance",
                   reference=new_payment["confirmation_number"],
                   account_type=account_type)
    except Exception:
        pass  # bridge failure should never block the main flow

    if loan.get("next_payment_due"):
        emit("booking", user_id=loan["user_id"], title=f"Loan payment due: {loan['loan_number']}", start=loan["next_payment_due"], location="")

    return jsonify({
        "status": loan["status"],
        "current_balance": loan["current_balance"],
        "payment_amount": amount,
        "confirmation_number": new_payment["confirmation_number"],
    })


@blueprint.route("/api/payments")
def api_payments():
    user_id = request.args.get("user_id", type=int)
    pay_type = request.args.get("type", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    status = request.args.get("status", "").strip()
    where_f = {}
    if user_id:
        where_f["user_id"] = user_id
    if pay_type:
        where_f["type"] = pay_type
    if status:
        where_f["status"] = status
    payments = db.query(SITE, "payments", where=where_f if where_f else None, sort="-payment_date")
    if date_from:
        payments = [p for p in payments if p["payment_date"] >= date_from]
    if date_to:
        payments = [p for p in payments if p["payment_date"] <= date_to]
    return jsonify(payments)


@blueprint.route("/api/stats")
def api_stats():
    user_id = request.args.get("user_id", type=int)
    policies = _load_policies()
    claims = _load_claims()
    loans = _load_loans()
    payments = _load_payments()

    if user_id:
        policies = [p for p in policies if p["user_id"] == user_id]
        claims = [c for c in claims if c["user_id"] == user_id]
        loans = [l for l in loans if l["user_id"] == user_id]
        payments = [p for p in payments if p["user_id"] == user_id]

    active_policies = [p for p in policies if p["status"] == "active"]
    active_loans = [l for l in loans if l["status"] == "active"]
    open_claims = [c for c in claims if c["status"] in ("open", "in_review")]

    stats = {
        "total_policies": len(policies),
        "active_policies": len(active_policies),
        "total_claims": len(claims),
        "open_claims": len(open_claims),
        "closed_claims": len([c for c in claims if c["status"] == "closed"]),
        "total_loans": len(loans),
        "active_loans": len(active_loans),
        "total_loan_balance": sum(l.get("current_balance", 0) for l in active_loans),
        "monthly_premiums": sum(p.get("premium_monthly", 0) for p in active_policies),
        "monthly_loan_payments": sum(l.get("monthly_payment", 0) for l in active_loans),
        "total_payments": len(payments),
        "total_paid_amount": sum(p.get("amount", 0) for p in payments),
        "policy_types": dict(
            sorted(
                {t: len([p for p in active_policies if p["type"] == t])
                 for t in set(p["type"] for p in active_policies)}.items()
            )
        ),
        "loan_types": dict(
            sorted(
                {t: len([l for l in active_loans if l["type"] == t])
                 for t in set(l["type"] for l in active_loans)}.items()
            )
        ),
    }
    return jsonify(stats)


# ---------------------------------------------------------------------------
# API: Search (search_by_query, search_by_semantic)
# ---------------------------------------------------------------------------

@blueprint.route("/api/search")
def api_search():
    """Full-text search across policies, claims, and loans."""
    q = request.args.get("q", "").strip().lower()
    if not q:
        return jsonify({"policies": [], "claims": [], "loans": []})

    policies = _load_policies()
    claims = _load_claims()
    loans = _load_loans()

    matched_policies = [
        p for p in policies
        if q in p["policy_number"].lower()
        or q in p["policyholder_name"].lower()
        or q in p["type"].lower()
        or q in p.get("notes", "").lower()
    ]
    matched_claims = [
        c for c in claims
        if q in c["claim_number"].lower()
        or q in c["claimant_name"].lower()
        or q in c["description"].lower()
        or q in c["type"].lower()
    ]
    matched_loans = [
        ln for ln in loans
        if q in ln["loan_number"].lower()
        or q in ln["borrower_name"].lower()
        or q in ln["type"].lower()
        or q in ln.get("notes", "").lower()
    ]

    return jsonify({
        "policies": matched_policies,
        "claims": matched_claims,
        "loans": matched_loans,
    })


@blueprint.route("/api/search/semantic")
def api_search_semantic():
    """Keyword-based semantic search (simple keyword expansion)."""
    q = request.args.get("q", "").strip().lower()
    if not q:
        return jsonify([])

    keywords = q.split()
    policies = _load_policies()
    claims = _load_claims()
    loans = _load_loans()

    results = []
    for p in policies:
        text = f"{p['type']} {p['policyholder_name']} {p.get('notes', '')} {p['policy_number']}".lower()
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            results.append({"type": "policy", "id": p["id"], "score": score, "data": p})
    for c in claims:
        text = f"{c['type']} {c['claimant_name']} {c['description']} {c.get('notes', '')}".lower()
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            results.append({"type": "claim", "id": c["id"], "score": score, "data": c})
    for ln in loans:
        text = f"{ln['type']} {ln['borrower_name']} {ln.get('notes', '')} {ln['loan_number']}".lower()
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            results.append({"type": "loan", "id": ln["id"], "score": score, "data": ln})

    results.sort(key=lambda r: r["score"], reverse=True)
    return jsonify(results)


# ---------------------------------------------------------------------------
# API: Compare policies
# ---------------------------------------------------------------------------

@blueprint.route("/api/compare")
def api_compare():
    """Compare policies, claims, or loans by IDs. ?type=policy&ids=1,2"""
    compare_type = request.args.get("type", "policy").strip()
    ids_raw = request.args.get("ids", "")
    try:
        ids = [int(x.strip()) for x in ids_raw.split(",") if x.strip()]
    except ValueError:
        return jsonify({"error": "ids must be comma-separated integers"}), 400
    if not ids:
        return jsonify({"error": "ids required"}), 400

    if compare_type == "policy":
        items = _load_policies()
    elif compare_type == "claim":
        items = _load_claims()
    elif compare_type == "loan":
        items = _load_loans()
    else:
        return jsonify({"error": "type must be policy, claim, or loan"}), 400

    results = [item for item in items if item["id"] in ids]
    return jsonify(results)


# ---------------------------------------------------------------------------
# API: Edit policy notes (edit_by_query)
# ---------------------------------------------------------------------------

@blueprint.route("/api/policies/<int:policy_id>/update", methods=["POST"])
def api_policy_update(policy_id):
    data = request.get_json(silent=True) or {}
    policies = _load_policies()
    policy = next((p for p in policies if p["id"] == policy_id), None)
    if not policy:
        abort(404)

    if "notes" in data:
        policy["notes"] = data["notes"]
    if "deductible" in data:
        policy["deductible"] = data["deductible"]
    if "agent" in data:
        policy["agent"] = data["agent"]
    # configure_by_toggle: policy settings and notification preferences
    for key in ("autopay_enabled", "paperless_billing", "email_notifications", "sms_alerts"):
        if key in data:
            policy[key] = bool(data[key])

    _save_policies(policies)
    return jsonify(policy)


# ---------------------------------------------------------------------------
# API: Sign document (sign_by_query) — e-signature for policy/claim
# ---------------------------------------------------------------------------

@blueprint.route("/api/policies/<int:policy_id>/sign", methods=["POST"])
def api_policy_sign(policy_id):
    """Electronically sign a policy (sign_by_freeformdrawing).

    DocuSign-style single "Sign here" field: the policyholder DRAWS their
    signature on a canvas. A valid drawn signature (PNG data URL + stroke points)
    places the policy in force. The saved record + response carry the signed flag
    so the trajectory network log makes the action gradeable.
    """
    data = request.get_json(silent=True) or {}
    policy = db.get_item(SITE, "policies", policy_id)
    if not policy:
        abort(404)

    drawing = data.get("signature_drawing") or ""
    points = data.get("signature_points") or []
    typed_name = (data.get("typed_name") or "").strip()
    valid_drawing = _valid_signature_drawing(drawing, points)
    # sign by DRAWING (sign_by_freeformdrawing) or by TYPING your name (sign_by_text)
    if not valid_drawing and not typed_name:
        return jsonify({"error": "Draw your signature, or type your full legal name, to continue."}), 400
    method = "drawn" if valid_drawing else "typed"

    signer = typed_name or (data.get("signature") or data.get("signer_name") or "").strip() \
        or policy.get("policyholder_name", "")
    policy["signed"] = True
    policy["signed_by"] = signer
    policy["signature"] = signer
    policy["signed_date"] = datetime.now().strftime("%Y-%m-%d")
    policy["signed_method"] = method
    policy["signed_with_drawing"] = valid_drawing
    policy["signature_drawing"] = drawing if valid_drawing else ""
    # signing places an awaiting-signature policy in force
    if policy.get("requires_signature") or policy.get("status") == "awaiting_signature":
        policy["status"] = "active"
    db.save_item(SITE, "policies", policy_id, policy)
    return jsonify({
        "status": "signed",
        "policy_id": policy_id,
        "signed": True,
        "signed_by": signer,
        "signed_date": policy["signed_date"],
        "signed_method": method,
        "signed_with_drawing": valid_drawing,
    })


# ---------------------------------------------------------------------------
# API: Export data (export_by_dropdown)
# ---------------------------------------------------------------------------

@blueprint.route("/api/export")
def api_export():
    """Export data as JSON or CSV. ?type=policies&format=json"""
    export_type = request.args.get("type", "policies").strip()
    fmt = request.args.get("format", "json").strip()
    user_id = request.args.get("user_id", type=int)

    if export_type == "policies":
        data = _load_policies()
    elif export_type == "claims":
        data = _load_claims()
    elif export_type == "loans":
        data = _load_loans()
    elif export_type == "payments":
        data = _load_payments()
    else:
        return jsonify({"error": "type must be policies, claims, loans, or payments"}), 400

    if user_id:
        data = [d for d in data if d.get("user_id") == user_id]

    if fmt == "csv":
        if not data:
            return "No data", 200
        import csv
        import io
        # Collect all keys across all records
        all_keys = []
        seen = set()
        for row in data:
            for k in row.keys():
                if k not in seen:
                    all_keys.append(k)
                    seen.add(k)
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=all_keys, extrasaction="ignore")
        writer.writeheader()
        for row in data:
            flat = {}
            for k in all_keys:
                v = row.get(k, "")
                flat[k] = json.dumps(v) if isinstance(v, (dict, list)) else v
            writer.writerow(flat)
        resp = output.getvalue()
        from flask import Response
        return Response(resp, mimetype="text/csv",
                       headers={"Content-Disposition": f"attachment; filename={export_type}.csv"})

    return jsonify(data)


# ---------------------------------------------------------------------------
# API: Upload document (upload_by_upload)
# ---------------------------------------------------------------------------

@blueprint.route("/api/claims/<int:claim_id>/upload", methods=["POST"])
def api_claim_upload(claim_id):
    """Upload supporting document for a claim."""
    claims = _load_claims()
    claim = next((c for c in claims if c["id"] == claim_id), None)
    if not claim:
        abort(404)

    filename = request.form.get("filename", "document.pdf")
    description = request.form.get("description", "Supporting document")

    if "documents" not in claim:
        claim["documents"] = []
    doc_id = len(claim["documents"]) + 1
    claim["documents"].append({
        "doc_id": doc_id,
        "filename": filename,
        "description": description,
        "uploaded_date": datetime.now().strftime("%Y-%m-%d"),
    })
    _save_claims(claims)
    return jsonify({
        "claim_id": claim_id,
        "doc_id": doc_id,
        "filename": filename,
        "status": "uploaded",
    }), 201


# ---------------------------------------------------------------------------
# API: Loan application (apply_by_query)
# ---------------------------------------------------------------------------

@blueprint.route("/api/loans/apply", methods=["POST"])
def api_loan_apply():
    """Submit a loan application."""
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    loan_type = data.get("type", "personal_loan")
    amount = data.get("amount")

    if not user_id or not amount:
        return jsonify({"error": "user_id and amount required"}), 400

    user = _get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    new_id = db.next_id(SITE, "loans")
    today = datetime.now().strftime("%Y-%m-%d")
    loan_number = f"LN-APP-{datetime.now().year}-{new_id:05d}"

    new_loan = {
        "id": new_id,
        "loan_number": loan_number,
        "user_id": user_id,
        "root_user_id": user["root_user_id"],
        "borrower_name": user["display_name"],
        "type": loan_type,
        "subtype": data.get("subtype", "standard"),
        # a new loan agreement isn't complete until the borrower signs it
        "status": "awaiting_signature",
        "requires_signature": True,
        "signed": False,
        "lender": "Cascadia Federal Credit Union",
        "servicer": "Cascadia Federal Credit Union",
        "original_amount": amount,
        "current_balance": amount,
        "interest_rate": data.get("interest_rate", 5.99),
        "rate_type": data.get("rate_type", "fixed"),
        "term_months": data.get("term_months", 60),
        "monthly_payment": round(amount / data.get("term_months", 60), 2),
        "origination_date": today,
        "first_payment_date": None,
        "maturity_date": None,
        "payments_made": 0,
        "payments_remaining": data.get("term_months", 60),
        "next_payment_due": None,
        "autopay_enabled": False,
        "autopay_account_last_four": None,
        "collateral": data.get("collateral"),
        "notes": "Application submitted online. Awaiting signature.",
    }
    db.save_item(SITE, "loans", new_id, new_loan)
    result = dict(new_loan)
    result["sign_url"] = url_for("insurance-loans.loan_sign_page", loan_id=new_id)
    return jsonify(result), 201


@blueprint.route("/loan/<int:loan_id>/sign", methods=["GET"])
def loan_sign_page(loan_id):
    """DocuSign-style signing surface for a loan agreement (sign_by_freeformdrawing)."""
    user, logged_in = _get_browsing_user()
    loan = db.get_item(SITE, "loans", loan_id)
    if not loan:
        abort(404)
    summary = [
        ("Loan Number", loan["loan_number"]),
        ("Borrower", loan.get("borrower_name", "")),
        ("Loan Type", (loan.get("type", "") or "").replace("_", " ").title()),
        ("Amount", "${:,.2f}".format(loan.get("original_amount", 0) or 0)),
        ("Interest Rate", "{}%".format(loan.get("interest_rate", 0))),
        ("Term", "{} months".format(loan.get("term_months", 0))),
        ("Monthly Payment", "${:,.2f}".format(loan.get("monthly_payment", 0) or 0)),
    ]
    return render_template(
        "insurance-loans/sign_document.html",
        user=user, logged_in=logged_in,
        kind="loan",
        title="Loan Agreement & Promissory Note",
        number=loan["loan_number"],
        signer_name=loan.get("borrower_name", user["display_name"]),
        signed=bool(loan.get("signed")),
        signed_date=loan.get("signed_date", ""),
        summary=summary,
        cert_text=(
            "By signing below, I agree to the terms of this loan agreement and "
            "promissory note, including the interest rate, repayment schedule, and "
            "monthly payment shown above. I promise to repay the amounts owed to "
            "Cascadia Federal Credit Union."
        ),
        sign_url=url_for("insurance-loans.api_loan_sign", loan_id=loan_id),
        detail_url=url_for("insurance-loans.loan_detail", loan_id=loan_id),
    )


@blueprint.route("/api/loans/<int:loan_id>/sign", methods=["POST"])
def api_loan_sign(loan_id):
    """Electronically sign a loan agreement (sign_by_freeformdrawing)."""
    data = request.get_json(silent=True) or {}
    loan = db.get_item(SITE, "loans", loan_id)
    if not loan:
        abort(404)

    drawing = data.get("signature_drawing") or ""
    points = data.get("signature_points") or []
    typed_name = (data.get("typed_name") or "").strip()
    valid_drawing = _valid_signature_drawing(drawing, points)
    # sign by DRAWING (sign_by_freeformdrawing) or by TYPING your name (sign_by_text)
    if not valid_drawing and not typed_name:
        return jsonify({"error": "Draw your signature, or type your full legal name, to continue."}), 400
    method = "drawn" if valid_drawing else "typed"

    signer = typed_name or (data.get("signature") or data.get("signer_name") or "").strip() \
        or loan.get("borrower_name", "")
    loan["signed"] = True
    loan["signed_by"] = signer
    loan["signature"] = signer
    loan["signed_date"] = datetime.now().strftime("%Y-%m-%d")
    loan["signed_method"] = method
    loan["signed_with_drawing"] = valid_drawing
    loan["signature_drawing"] = drawing if valid_drawing else ""
    # signing completes an awaiting-signature loan; it proceeds to underwriting
    if loan.get("requires_signature") or loan.get("status") == "awaiting_signature":
        loan["status"] = "pending_approval"
    db.save_item(SITE, "loans", loan_id, loan)
    return jsonify({
        "status": "signed",
        "loan_id": loan_id,
        "signed": True,
        "signed_by": signer,
        "signed_date": loan["signed_date"],
        "signed_method": method,
        "signed_with_drawing": valid_drawing,
    })


# ---------------------------------------------------------------------------
# API: Premium payment (pay_by_form)
# ---------------------------------------------------------------------------

@blueprint.route("/api/policies/<int:policy_id>/pay", methods=["POST"])
def api_policy_pay(policy_id):
    """Record a premium payment for a policy."""
    data = request.get_json(silent=True) or {}
    policies = _load_policies()
    policy = next((p for p in policies if p["id"] == policy_id), None)
    if not policy:
        abort(404)

    amount = data.get("amount", policy.get("premium_monthly", 0))
    method = data.get("method", "online")

    payments = _load_payments()
    new_id = max(p["id"] for p in payments) + 1 if payments else 1
    today = datetime.now().strftime("%Y-%m-%d")

    new_payment = {
        "id": new_id,
        "payment_id": f"ILPAY-{datetime.now().year}-{new_id:04d}",
        "user_id": policy["user_id"],
        "root_user_id": policy["root_user_id"],
        "payer_name": policy["policyholder_name"],
        "type": "insurance_premium",
        "related_policy": policy["policy_number"],
        "amount": amount,
        "method": method,
        "payment_date": today,
        "due_date": today,
        "status": "completed",
        "confirmation_number": f"ILP-{today.replace('-', '')}-{new_id:05d}",
        "notes": f"Premium payment via {method}",
    }
    payments.append(new_payment)
    _save_payments(payments)

    # Bridge: notify banking of insurance premium payment
    try:
        from app.bridges import on_payment as bridge_payment
        account_type = data.get("account_type", "checking")
        bridge_payment(user_id=policy["user_id"],
                       recipient=f"Cascadia Insurance - Policy {policy['policy_number']}",
                       amount=amount, category="Insurance",
                       reference=new_payment["confirmation_number"],
                       account_type=account_type)
    except Exception:
        pass  # bridge failure should never block the main flow

    return jsonify(new_payment), 201


# ---------------------------------------------------------------------------
# API: Loan calculator (compute_by_slider)
# ---------------------------------------------------------------------------

@blueprint.route("/api/calculator")
def api_calculator():
    """Loan calculator: compute monthly payment from amount, rate, term."""
    amount = request.args.get("amount", type=float)
    rate = request.args.get("rate", type=float)
    term = request.args.get("term", type=int)

    if not amount or not rate or not term:
        return jsonify({"error": "amount, rate, and term required"}), 400

    monthly_rate = rate / 100 / 12
    if monthly_rate == 0:
        monthly_payment = round(amount / term, 2)
    else:
        monthly_payment = round(
            amount * (monthly_rate * (1 + monthly_rate) ** term) /
            ((1 + monthly_rate) ** term - 1), 2
        )
    total_payment = round(monthly_payment * term, 2)
    total_interest = round(total_payment - amount, 2)

    return jsonify({
        "amount": amount,
        "rate": rate,
        "term": term,
        "monthly_payment": monthly_payment,
        "total_payment": total_payment,
        "total_interest": total_interest,
    })


# ---------------------------------------------------------------------------
# API: User settings (configure_by_toggle)
# ---------------------------------------------------------------------------

@blueprint.route("/api/users/<int:user_id>/settings", methods=["GET"])
def api_user_settings(user_id):
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    settings = user.get("settings", {
        "paperless_billing": False,
        "email_notifications": True,
        "sms_alerts": False,
        "autopay_default": True,
    })
    return jsonify(settings)


@blueprint.route("/api/users/<int:user_id>/settings", methods=["POST"])
def api_user_settings_update(user_id):
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    data = request.get_json(silent=True) or {}
    settings = user.get("settings", {
        "paperless_billing": False,
        "email_notifications": True,
        "sms_alerts": False,
        "autopay_default": True,
    })
    for k in ["paperless_billing", "email_notifications", "sms_alerts", "autopay_default"]:
        if k in data:
            settings[k] = data[k]
    user["settings"] = settings
    db.save_collection(SITE, "users", users)
    return jsonify(settings)


# ---------------------------------------------------------------------------
# API: Users
# ---------------------------------------------------------------------------

@blueprint.route("/api/users/<int:user_id>")
def api_user(user_id):
    user = _get_user(user_id)
    if not user:
        abort(404)
    return jsonify(user)


@blueprint.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user:
        return jsonify({"error": "Invalid credentials"}), 401
    session["il_user_id"] = user["id"]
    return jsonify({"user_id": user["id"], "username": user["username"],
                    "display_name": user["display_name"]})
