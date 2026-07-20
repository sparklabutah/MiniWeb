"""Agency Portals -- Lakeport Municipal Services Portal (.gov style).

Synthesized data: departments, services, permits, public records, users,
announcements, appointments, payments.
"""
import pathlib
import random

from flask import (Blueprint, Response, abort, jsonify, render_template,
                   request, session, redirect, url_for)
from app import db
from app.events import emit


def _send_confirmation_email(user_id, subject, body):
    """Send a confirmation email via the cross-site bridge."""
    try:
        from app.bridges import _add_email
        _add_email(user_id, from_addr="noreply@lakeport.gov", subject=subject, body=body)
    except Exception:
        pass

SITE = "agency-portals"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "agency-portals",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)


@blueprint.context_processor
def _inject_departments():
    """Make departments available in all templates (for nav dropdown)."""
    return {"departments": _load_departments()}


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def _load_departments():
    return db.query(SITE, "departments")

def _load_services(department_id=None, category=None):
    where = {}
    if department_id is not None:
        where["department_id"] = department_id
    if category:
        where["category"] = category
    return db.query(SITE, "services", where=where if where else None)

def _load_permits(department_id=None, status=None, ptype=None):
    where = {}
    if department_id is not None:
        where["department_id"] = department_id
    if status:
        where["status"] = status
    if ptype:
        where["type"] = ptype
    return db.query(SITE, "permits", where=where if where else None)

def _load_records(rtype=None):
    where = {}
    if rtype:
        where["type"] = rtype
    return db.query(SITE, "records", where=where if where else None)

def _load_users():
    return db.query(SITE, "users")

def _save_users(users):
    db.save_collection(SITE, "users", users)

def _load_announcements():
    return db.query(SITE, "announcements")

def _load_appointment_types():
    return db.query(SITE, "appointment_types")

def _load_payment_types():
    return db.query(SITE, "payment_types")

def _get_user(user_id):
    return db.get_item(SITE, "users", user_id)

# ---------------------------------------------------------------------------
# Search / filter helpers
# ---------------------------------------------------------------------------

def _keyword_score(query, text):
    terms = query.lower().split()
    text_lower = text.lower()
    return sum(1 for t in terms if t in text_lower)

def _search_services(services, query):
    if not query:
        return services
    q = query.lower().strip()
    scored = []
    for s in services:
        text = f"{s['name']} {s['description']} {s['category']} {s['code']}"
        sc = _keyword_score(q, text)
        if sc > 0:
            scored.append((s, sc))
    scored.sort(key=lambda x: -x[1])
    return [s for s, _ in scored]

def _search_permits(permits, query):
    if not query:
        return permits
    q = query.lower().strip()
    return [p for p in permits if q in p["type"].lower() or
            q in p["applicant"].lower() or
            q in p["address"].lower() or
            q in p["code"].lower() or
            q in p["status"].lower()]

def _search_records(records, query):
    if not query:
        return records
    q = query.lower().strip()
    scored = []
    for r in records:
        text = f"{r['record_id']} {r['type']} {r['owner']} {r['address']} {r['description']}"
        sc = _keyword_score(q, text)
        if sc > 0:
            scored.append((r, sc))
    scored.sort(key=lambda x: -x[1])
    return [r for r, _ in scored]

# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    departments = _load_departments()
    announcements = _load_announcements()
    services = _load_services()
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("agency-portals/index.html",
                           departments=departments,
                           announcements=announcements[:5],
                           services=services,
                           user=user)


@blueprint.route("/departments")
def departments_page():
    departments = _load_departments()
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("agency-portals/departments.html",
                           departments=departments, user=user)


@blueprint.route("/department/<int:dept_id>")
def department_detail(dept_id):
    dept = db.get_item(SITE, "departments", dept_id)
    if dept is None:
        abort(404)
    services = _load_services(department_id=dept_id)
    permits = _load_permits(department_id=dept_id)
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("agency-portals/department_detail.html",
                           dept=dept, services=services, permits=permits,
                           user=user)


@blueprint.route("/services")
def services_page():
    departments = _load_departments()
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    dept_id = request.args.get("department", "").strip()

    did = None
    if dept_id:
        try:
            did = int(dept_id)
        except ValueError:
            pass

    results = _load_services(department_id=did, category=category or None)
    if q:
        results = _search_services(results, q)

    cat_rows = db.execute(
        "SELECT DISTINCT [category] FROM [agency_portals_services] ORDER BY [category]", ())
    categories = [r["category"] for r in cat_rows]
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("agency-portals/services.html",
                           services=results, departments=departments,
                           categories=categories, q=q, category=category,
                           dept_id=dept_id, user=user)


@blueprint.route("/service/<int:service_id>")
def service_detail(service_id):
    service = db.get_item(SITE, "services", service_id)
    if service is None:
        abort(404)
    dept = db.get_item(SITE, "departments", service["department_id"])
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("agency-portals/service_detail.html",
                           service=service, dept=dept, user=user)


@blueprint.route("/permits")
def permits_page():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    ptype = request.args.get("type", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    page = max(request.args.get("page", type=int) or 1, 1)
    per_page = 50

    # SQL-level filtering + pagination (the permit archive is large)
    clauses, params = [], []
    if status:
        clauses.append("[status] = ?")
        params.append(status)
    if ptype:
        clauses.append("[type] = ?")
        params.append(ptype)
    if date_from:
        clauses.append("[date_submitted] >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("[date_submitted] <= ?")
        params.append(date_to)
    where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    if q:
        # keyword matching needs Python; run it over the SQL-filtered set
        rows = db.execute(
            f"SELECT * FROM [agency_portals_permits]{where_sql} ORDER BY [id]",
            tuple(params))
        rows = _search_permits(rows, q)
        total = len(rows)
        results = rows[(page - 1) * per_page:page * per_page]
    else:
        total = db.execute(
            f"SELECT COUNT(*) FROM [agency_portals_permits]{where_sql}",
            tuple(params), fetch="val")
        results = db.execute(
            f"SELECT * FROM [agency_portals_permits]{where_sql} "
            f"ORDER BY [id] LIMIT ? OFFSET ?",
            tuple(params) + (per_page, (page - 1) * per_page))
    pages = max((total + per_page - 1) // per_page, 1)

    stat_rows = db.execute("SELECT DISTINCT [status] FROM [agency_portals_permits] ORDER BY [status]", ())
    statuses = [r["status"] for r in stat_rows]
    type_rows = db.execute("SELECT DISTINCT [type] FROM [agency_portals_permits] ORDER BY [type]", ())
    types = [r["type"] for r in type_rows]
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("agency-portals/permits.html",
                           permits=results, statuses=statuses, types=types,
                           q=q, status=status, ptype=ptype,
                           date_from=date_from, date_to=date_to, user=user,
                           total=total, page=page, pages=pages)


@blueprint.route("/permit/<int:permit_id>")
def permit_detail(permit_id):
    permit = db.get_item(SITE, "permits", permit_id)
    if permit is None:
        abort(404)
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("agency-portals/permit_detail.html",
                           permit=permit, user=user)


@blueprint.route("/records")
def records_page():
    departments = _load_departments()
    q = request.args.get("q", "").strip()
    rtype = request.args.get("type", "").strip()
    dept_id = request.args.get("department", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    page = max(request.args.get("page", type=int) or 1, 1)
    per_page = 50

    did = None
    if dept_id:
        try:
            did = int(dept_id)
        except ValueError:
            pass

    # SQL-level filtering + pagination (the records archive is large)
    clauses, params = [], []
    if rtype:
        clauses.append("[type] = ?")
        params.append(rtype)
    if date_from:
        clauses.append("[date_filed] >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("[date_filed] <= ?")
        params.append(date_to)
    where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    if q:
        # keyword scoring needs Python; run it over the SQL-filtered set
        rows = db.execute(
            f"SELECT * FROM [agency_portals_records]{where_sql} ORDER BY [id]",
            tuple(params))
        rows = _search_records(rows, q)
        total = len(rows)
        results = rows[(page - 1) * per_page:page * per_page]
    else:
        total = db.execute(
            f"SELECT COUNT(*) FROM [agency_portals_records]{where_sql}",
            tuple(params), fetch="val")
        results = db.execute(
            f"SELECT * FROM [agency_portals_records]{where_sql} "
            f"ORDER BY [id] LIMIT ? OFFSET ?",
            tuple(params) + (per_page, (page - 1) * per_page))
    pages = max((total + per_page - 1) // per_page, 1)

    type_rows = db.execute("SELECT DISTINCT [type] FROM [agency_portals_records] ORDER BY [type]", ())
    record_types = [r["type"] for r in type_rows]
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("agency-portals/records.html",
                           records=results, departments=departments,
                           record_types=record_types, q=q, rtype=rtype,
                           dept_id=dept_id, date_from=date_from,
                           date_to=date_to, user=user,
                           total=total, page=page, pages=pages)


@blueprint.route("/announcements")
def announcements_page():
    announcements = _load_announcements()
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("agency-portals/announcements.html",
                           announcements=announcements, user=user)


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("agency-portals/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return render_template("agency-portals/login.html",
                               error="Invalid username or password")
    session["user_id"] = user["id"]
    emit("signup", user_id=user["id"], site_name="agency-portals", username=request.form.get("username", ""), password=request.form.get("password", ""), email="")
    return redirect(url_for("agency-portals.dashboard"))


@blueprint.route("/register", methods=["GET"])
def register_page():
    return render_template("agency-portals/register.html", error=None, success=False)


@blueprint.route("/register", methods=["POST"])
def register_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    address = request.form.get("address", "").strip()
    phone = request.form.get("phone", "").strip()

    if not username or not password or not name or not email:
        return render_template("agency-portals/register.html",
                               error="All required fields must be filled", success=False)
    users = _load_users()
    if any(u["username"] == username for u in users):
        return render_template("agency-portals/register.html",
                               error="Username already exists", success=False)

    rng = random.Random()
    new_id = max(u["id"] for u in users) + 1 if users else 1
    verification_code = f"VRF-{new_id + 100000}"
    new_user = {
        "id": new_id,
        "username": username,
        "password": password,
        "name": name,
        "email": email,
        "address": address,
        "phone": phone,
        "verified": False,
        "verification_code": verification_code,
        "saved_services": [],
        "permits": [],
        "payments": [],
        "appointments": [],
    }
    users.append(new_user)
    _save_users(users)
    _send_confirmation_email(
        new_id,
        "Welcome to City of Lakeport Online Services",
        f"Hello {name},\n\nYour account has been created successfully.\n"
        f"Username: {username}\nVerification Code: {verification_code}\n\n"
        f"Please verify your identity to access all services.\n\n"
        f"City of Lakeport Municipal Services")
    return render_template("agency-portals/register.html",
                           error=None, success=True, new_user=new_user)


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("agency-portals.login_page"))


@blueprint.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("agency-portals.login_page"))
    user = _get_user(session["user_id"])
    if not user:
        return redirect(url_for("agency-portals.login_page"))
    services = _load_services()
    saved = [s for s in services if s["id"] in user.get("saved_services", [])]
    return render_template("agency-portals/dashboard.html",
                           user=user, saved_services=saved)


@blueprint.route("/apply/<int:service_id>", methods=["GET"])
def apply_page(service_id):
    services = _load_services()
    service = next((s for s in services if s["id"] == service_id), None)
    if service is None:
        abort(404)
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("agency-portals/apply.html",
                           service=service, user=user, success=False)


@blueprint.route("/apply/<int:service_id>", methods=["POST"])
def apply_submit(service_id):
    services = _load_services()
    service = next((s for s in services if s["id"] == service_id), None)
    if service is None:
        abort(404)
    user = None
    applicant_name = request.form.get("applicant_name", "").strip()
    address = request.form.get("address", "").strip()
    notes = request.form.get("notes", "").strip()

    # Determine permit type from service name
    permit_type = "Building"
    sname = service.get("name", "").lower()
    if "building" in sname:
        permit_type = "Building"
    elif "business" in sname:
        permit_type = "Business"
    elif "parking" in sname:
        permit_type = "Parking"
    elif "electrical" in sname:
        permit_type = "Electrical"
    elif "plumbing" in sname:
        permit_type = "Plumbing"
    else:
        # Use first word of service name
        permit_type = service.get("name", "General").split()[0]

    permit_code = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
        if user:
            users = _load_users()
            u = next((u for u in users if u["id"] == user["id"]), None)
            if u:
                user_permits = u.setdefault("permits", [])
                permit_code = f"USR-PRM-{u['id']}-{len(user_permits)+1:03d}"
                new_permit = {
                    "code": permit_code,
                    "type": permit_type,
                    "address": address or u.get("address", ""),
                    "description": notes,
                    "status": "Submitted",
                }
                user_permits.append(new_permit)
                _save_users(users)
                _send_confirmation_email(
                    u["id"],
                    f"Permit Application Received — {permit_code}",
                    f"Hello {u['name']},\n\nYour {permit_type} permit application has been received.\n"
                    f"Permit Code: {permit_code}\nService: {service['name']}\n"
                    f"Address: {address}\nStatus: Submitted\n\n"
                    f"You will be notified when your application is reviewed.\n\n"
                    f"City of Lakeport Municipal Services")

    return render_template("agency-portals/apply.html",
                           service=service, user=user, success=True,
                           applicant_name=applicant_name,
                           permit_code=permit_code)


@blueprint.route("/book", methods=["GET"])
def book_page():
    appointment_types = _load_appointment_types()
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("agency-portals/book.html",
                           appointment_types=appointment_types, user=user,
                           success=False)


@blueprint.route("/book", methods=["POST"])
def book_submit():
    appointment_types = _load_appointment_types()
    appt_type_id = request.form.get("appointment_type", type=int)
    date = request.form.get("date", "").strip()
    time = request.form.get("time", "").strip()
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()

    appt_type = next((a for a in appointment_types if a["id"] == appt_type_id), None)

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
        if user and appt_type:
            users = _load_users()
            u = next((u for u in users if u["id"] == user["id"]), None)
            if u:
                appts = u.setdefault("appointments", [])
                conf_num = f"APT-{len(appts)+1:04d}"
                appts.append({
                    "confirmation": conf_num,
                    "type": appt_type["name"],
                    "date": date,
                    "time": time,
                })
                _save_users(users)
                _send_confirmation_email(
                    u["id"],
                    f"Appointment Confirmed — {conf_num}",
                    f"Hello {u['name']},\n\nYour appointment has been confirmed.\n"
                    f"Confirmation: {conf_num}\nType: {appt_type['name']}\n"
                    f"Date: {date}\nTime: {time}\n\n"
                    f"City of Lakeport Municipal Services")
                emit("booking", user_id=u["id"], title=f"Lakeport Appt: {appt_type['name']}", start=date, location="City of Lakeport Municipal Services")

    return render_template("agency-portals/book.html",
                           appointment_types=appointment_types, user=user,
                           success=True, booked_type=appt_type,
                           booked_date=date, booked_time=time)


@blueprint.route("/pay", methods=["GET"])
def pay_page():
    payment_types = _load_payment_types()
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("agency-portals/pay.html",
                           payment_types=payment_types, user=user,
                           success=False)


@blueprint.route("/pay", methods=["POST"])
def pay_submit():
    payment_types = _load_payment_types()
    pay_type = request.form.get("payment_type", "").strip()
    amount = request.form.get("amount", "").strip()
    account = request.form.get("account_number", "").strip()

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
        if user:
            users = _load_users()
            u = next((u for u in users if u["id"] == user["id"]), None)
            if u:
                payments = u.setdefault("payments", [])
                conf = f"PAY-{len(payments)+1:04d}"
                payments.append({
                    "confirmation": conf,
                    "type": pay_type,
                    "amount": amount,
                    "account": account,
                })
                _save_users(users)
                _send_confirmation_email(
                    u["id"],
                    f"Payment Received — {conf}",
                    f"Hello {u['name']},\n\nYour payment has been processed.\n"
                    f"Confirmation: {conf}\nType: {pay_type}\n"
                    f"Amount: ${amount}\n\n"
                    f"City of Lakeport Municipal Services")
                emit("payment", user_id=u["id"], recipient="City of Lakeport", amount=float(amount) if amount else 0, category="Government", account_number=account)

    return render_template("agency-portals/pay.html",
                           payment_types=payment_types, user=user,
                           success=True, paid_type=pay_type,
                           paid_amount=amount)


@blueprint.route("/verify-identity", methods=["GET"])
def verify_identity_page():
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("agency-portals/verify_identity.html",
                           user=user, result=None)


@blueprint.route("/verify-identity", methods=["POST"])
def verify_identity_submit():
    code = request.form.get("verification_code", "").strip()
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    users = _load_users()
    matched = next((u for u in users if u.get("verification_code") == code), None)
    if matched:
        matched["verified"] = True
        _save_users(users)
        if user and user["id"] == matched["id"]:
            user["verified"] = True
        return render_template("agency-portals/verify_identity.html",
                               user=user, result="success", verified_user=matched)
    else:
        return render_template("agency-portals/verify_identity.html",
                               user=user, result="error")


@blueprint.route("/upload", methods=["GET"])
def upload_page():
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("agency-portals/upload.html",
                           user=user, success=False)


@blueprint.route("/upload", methods=["POST"])
def upload_submit():
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    uploaded_file = request.files.get("document")
    doc_type = request.form.get("document_type", "").strip()
    description = request.form.get("description", "").strip()

    filename = uploaded_file.filename if uploaded_file else "unknown"
    return render_template("agency-portals/upload.html",
                           user=user, success=True,
                           uploaded_filename=filename,
                           doc_type=doc_type)


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/departments")
def api_departments():
    return jsonify(_load_departments())


@blueprint.route("/api/departments/<int:dept_id>")
def api_department(dept_id):
    dept = db.get_item(SITE, "departments", dept_id)
    if dept is None:
        abort(404)
    return jsonify(dept)


@blueprint.route("/api/services")
def api_services():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    dept_id = request.args.get("department", type=int)

    results = _load_services(department_id=dept_id, category=category or None)
    if q:
        results = _search_services(results, q)
    return jsonify(results)


@blueprint.route("/api/services/<int:service_id>")
def api_service(service_id):
    service = db.get_item(SITE, "services", service_id)
    if service is None:
        abort(404)
    return jsonify(service)


@blueprint.route("/api/services/search")
def api_services_search():
    q = request.args.get("q", "").strip()
    services = _load_services()
    return jsonify(_search_services(services, q))


@blueprint.route("/api/services/semantic")
def api_services_semantic():
    q = request.args.get("q", "").strip()
    services = _load_services()
    if not q:
        return jsonify(services)
    scored = []
    for s in services:
        text = f"{s['name']} {s['description']} {s['category']}"
        sc = _keyword_score(q, text)
        if sc > 0:
            scored.append((s, sc))
    scored.sort(key=lambda x: -x[1])
    return jsonify([s for s, _ in scored])


@blueprint.route("/api/permits")
def api_permits():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    ptype = request.args.get("type", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    results = _load_permits(status=status or None, ptype=ptype or None)
    if date_from:
        results = [p for p in results if p["date_submitted"] >= date_from]
    if date_to:
        results = [p for p in results if p["date_submitted"] <= date_to]
    if q:
        results = _search_permits(results, q)
    return jsonify(results)


@blueprint.route("/api/permits/<int:permit_id>")
def api_permit(permit_id):
    permit = db.get_item(SITE, "permits", permit_id)
    if permit is None:
        abort(404)
    return jsonify(permit)


@blueprint.route("/api/permits/search")
def api_permits_search():
    q = request.args.get("q", "").strip()
    code = request.args.get("code", "").strip()
    permits = _load_permits()
    if code:
        results = [p for p in permits if p["code"] == code]
        return jsonify(results)
    return jsonify(_search_permits(permits, q))


@blueprint.route("/api/records")
def api_records():
    q = request.args.get("q", "").strip()
    rtype = request.args.get("type", "").strip()
    dept_id = request.args.get("department", type=int)
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    results = _load_records(rtype=rtype or None)
    if date_from:
        results = [r for r in results if r["date_filed"] >= date_from]
    if date_to:
        results = [r for r in results if r["date_filed"] <= date_to]
    if q:
        results = _search_records(results, q)
    return jsonify(results)


@blueprint.route("/api/records/<int:record_id>")
def api_record(record_id):
    record = db.get_item(SITE, "records", record_id)
    if record is None:
        abort(404)
    return jsonify(record)


@blueprint.route("/api/announcements")
def api_announcements():
    return jsonify(_load_announcements())


@blueprint.route("/api/stats")
def api_stats():
    dept_id = request.args.get("department", type=int)

    total_departments = db.count(SITE, "departments")
    services = _load_services(department_id=dept_id)
    permits = _load_permits(department_id=dept_id)
    records = _load_records()

    permit_statuses = {}
    for p in permits:
        permit_statuses[p["status"]] = permit_statuses.get(p["status"], 0) + 1

    service_categories = {}
    for s in services:
        service_categories[s["category"]] = service_categories.get(s["category"], 0) + 1

    return jsonify({
        "total_departments": total_departments,
        "total_services": len(services),
        "total_permits": len(permits),
        "total_records": len(records),
        "permit_statuses": permit_statuses,
        "service_categories": service_categories,
    })


@blueprint.route("/api/export")
def api_export():
    fmt = request.args.get("format", "json").lower()
    data_type = request.args.get("type", "services").lower()

    if data_type == "permits":
        data = _load_permits()
    elif data_type == "records":
        data = _load_records()
    else:
        data = _load_services()

    category = request.args.get("category", "").strip()
    if category and data_type == "services":
        data = [d for d in data if d.get("category") == category]
    status = request.args.get("status", "").strip()
    if status and data_type == "permits":
        data = [d for d in data if d.get("status") == status]

    if fmt == "csv":
        if data_type == "permits":
            lines = ["id,code,type,applicant,address,status,date_submitted,fee"]
            for p in data:
                lines.append(f'{p["id"]},"{p["code"]}","{p["type"]}","{p["applicant"]}","{p["address"]}","{p["status"]}",{p["date_submitted"]},{p["fee"]}')
        elif data_type == "records":
            lines = ["id,record_id,type,owner,address,date_filed,status"]
            for r in data:
                owner = r["owner"].replace('"', '""')
                lines.append(f'{r["id"]},"{r["record_id"]}","{r["type"]}","{owner}","{r["address"]}",{r["date_filed"]},"{r["status"]}"')
        else:
            lines = ["id,code,name,category,department_id,fee_range,online"]
            for s in data:
                name = s["name"].replace('"', '""')
                lines.append(f'{s["id"]},"{s["code"]}","{name}","{s["category"]}",{s["department_id"]},"{s["fee_range"]}",{s["online"]}')
        return Response("\n".join(lines), mimetype="text/csv",
                        headers={"Content-Disposition": f"attachment; filename={data_type}.csv"})
    return jsonify(data)


# ---------------------------------------------------------------------------
# User API routes
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
    return jsonify({"user_id": user["id"], "username": user["username"],
                    "name": user["name"]})


@blueprint.route("/api/register", methods=["POST"])
def api_register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    address = data.get("address", "").strip()
    phone = data.get("phone", "").strip()

    if not username or not password or not name or not email:
        return jsonify({"error": "Missing required fields"}), 400

    users = _load_users()
    if any(u["username"] == username for u in users):
        return jsonify({"error": "Username already exists"}), 409

    new_id = max(u["id"] for u in users) + 1 if users else 1
    verification_code = f"VRF-{new_id + 100000}"
    new_user = {
        "id": new_id,
        "username": username,
        "password": password,
        "name": name,
        "email": email,
        "address": address,
        "phone": phone,
        "verified": False,
        "verification_code": verification_code,
        "saved_services": [],
        "permits": [],
        "payments": [],
        "appointments": [],
    }
    users.append(new_user)
    _save_users(users)
    return jsonify({"user_id": new_id, "username": username,
                    "verification_code": verification_code}), 201


@blueprint.route("/api/users/<int:user_id>")
def api_user(user_id):
    user = _get_user(user_id)
    if not user:
        abort(404)
    return jsonify({k: v for k, v in user.items() if k != "password"})


@blueprint.route("/api/users/<int:user_id>/save-service", methods=["POST"])
def api_save_service(user_id):
    data = request.get_json(silent=True) or {}
    service_id = data.get("service_id")
    if service_id is None:
        return jsonify({"error": "service_id required"}), 400
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    saved = user.setdefault("saved_services", [])
    if service_id in saved:
        saved.remove(service_id)
        action = "removed"
    else:
        saved.append(service_id)
        action = "saved"
    _save_users(users)
    return jsonify({"action": action, "service_id": service_id,
                    "total_saved": len(saved)})


@blueprint.route("/api/users/<int:user_id>/apply-permit", methods=["POST"])
def api_apply_permit(user_id):
    data = request.get_json(silent=True) or {}
    permit_type = data.get("permit_type", "").strip()
    address = data.get("address", "").strip()
    description = data.get("description", "").strip()

    if not permit_type:
        return jsonify({"error": "permit_type required"}), 400

    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)

    user_permits = user.setdefault("permits", [])
    permit_code = f"USR-PRM-{user_id}-{len(user_permits)+1:03d}"
    new_permit = {
        "code": permit_code,
        "type": permit_type,
        "address": address or user.get("address", ""),
        "description": description,
        "status": "Submitted",
    }
    user_permits.append(new_permit)
    _save_users(users)
    return jsonify({"action": "submitted", "permit_code": permit_code,
                    "permit": new_permit})


@blueprint.route("/api/users/<int:user_id>/pay", methods=["POST"])
def api_pay(user_id):
    data = request.get_json(silent=True) or {}
    pay_type = data.get("payment_type", "").strip()
    amount = data.get("amount", 0)
    account = data.get("account_number", "").strip()

    if not pay_type or not amount:
        return jsonify({"error": "payment_type and amount required"}), 400

    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)

    payments = user.setdefault("payments", [])
    conf = f"PAY-{user_id}-{len(payments)+1:04d}"
    payment = {
        "confirmation": conf,
        "type": pay_type,
        "amount": amount,
        "account": account,
        "status": "Completed",
    }
    payments.append(payment)
    _save_users(users)
    emit("payment", user_id=user_id, recipient="City of Lakeport", amount=float(amount), category="Government", account_number=account)
    return jsonify({"action": "paid", "confirmation": conf, "payment": payment})


@blueprint.route("/api/users/<int:user_id>/book", methods=["POST"])
def api_book(user_id):
    data = request.get_json(silent=True) or {}
    appt_type_id = data.get("appointment_type_id")
    date = data.get("date", "").strip()
    time = data.get("time", "").strip()

    if not appt_type_id or not date or not time:
        return jsonify({"error": "appointment_type_id, date, time required"}), 400

    appt_types = _load_appointment_types()
    appt_type = next((a for a in appt_types if a["id"] == appt_type_id), None)
    if not appt_type:
        return jsonify({"error": "Invalid appointment type"}), 400

    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)

    appts = user.setdefault("appointments", [])
    conf = f"APT-{user_id}-{len(appts)+1:04d}"
    appointment = {
        "confirmation": conf,
        "type": appt_type["name"],
        "type_id": appt_type_id,
        "date": date,
        "time": time,
    }
    appts.append(appointment)
    _save_users(users)
    emit("booking", user_id=user_id, title=f"Lakeport Appt: {appt_type['name']}", start=date, location="City of Lakeport Municipal Services")
    return jsonify({"action": "booked", "confirmation": conf,
                    "appointment": appointment})


@blueprint.route("/api/verify-identity", methods=["POST"])
def api_verify_identity():
    data = request.get_json(silent=True) or {}
    code = data.get("verification_code", "").strip()

    users = _load_users()
    matched = next((u for u in users if u.get("verification_code") == code), None)
    if not matched:
        return jsonify({"error": "Invalid verification code"}), 404

    matched["verified"] = True
    _save_users(users)
    return jsonify({"action": "verified", "user_id": matched["id"],
                    "name": matched["name"]})


@blueprint.route("/api/upload", methods=["POST"])
def api_upload():
    uploaded_file = request.files.get("document")
    doc_type = request.form.get("document_type", "").strip()
    description = request.form.get("description", "").strip()
    user_id = request.form.get("user_id", type=int)

    if not uploaded_file:
        return jsonify({"error": "No file uploaded"}), 400

    filename = uploaded_file.filename
    return jsonify({
        "action": "uploaded",
        "filename": filename,
        "document_type": doc_type,
        "description": description,
        "user_id": user_id,
    })
