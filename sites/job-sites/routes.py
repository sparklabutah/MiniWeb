"""JobQuest -- job search and application tracker (Indeed-style).

Data is stored in per-site SQLite tables (job_sites_jobs, job_sites_users,
etc.) and queried through app.db.  Session mutations are isolated per user.

Supports all 22 assigned macros:
  navigate_by_dropdown, navigate_by_route, search_by_query, search_by_semantic,
  filter_by_query, filter_by_semantic, filter_by_dropdown, filter_by_radio,
  filter_by_slider, filter_by_date_range, sort_by_ranking, extract_by_query,
  extract_by_semantic, extract_by_dropdown, extract_by_route,
  create_from_free_text, submit_by_query, upload_by_upload,
  follow_by_toggle, subscribe_by_toggle, save_by_toggle, apply_by_form
"""
import json
import os
import pathlib
import re
from datetime import datetime

from flask import (
    Blueprint, abort, jsonify, redirect, render_template, request,
    session, url_for,
)
from app import db
from app.events import emit
from app.handlers.email_handler import _add_email
from helpers.auth import current_user, browsing_user

SITE = "job-sites"
SITE_DIR = pathlib.Path(__file__).resolve().parent
UPLOAD_DIR = SITE_DIR / "data" / "uploads"

blueprint = Blueprint(
    "job-sites",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data helpers — all data lives in SQLite via db.query() / db.save_collection()
# ---------------------------------------------------------------------------

def _get_jobs(**kwargs):
    """Return jobs from the DB with optional SQL-level filters."""
    if not kwargs:
        kwargs = {"limit": 200}
    elif "limit" not in kwargs:
        kwargs["limit"] = 200
    jobs = db.query(SITE, "jobs", limit=kwargs.pop("limit", 50), **kwargs)
    for j in jobs:
        for field in ("skills", "responsibilities", "benefits", "tags", "requirements"):
            if isinstance(j.get(field), str):
                try:
                    j[field] = json.loads(j[field])
                except (json.JSONDecodeError, TypeError):
                    j[field] = []
    return jobs


def _get_companies():
    """Return sorted list of unique company names."""
    jobs = _get_jobs()
    return sorted(set(j["company"] for j in jobs if j.get("company")))


def _get_job_by_id(job_id):
    """Lookup a single job by its integer ID."""
    job = db.get_item(SITE, "jobs", job_id)
    if job:
        for field in ("skills", "responsibilities", "benefits", "tags", "requirements"):
            if isinstance(job.get(field), str):
                try:
                    job[field] = json.loads(job[field])
                except (json.JSONDecodeError, TypeError):
                    job[field] = []
    return job


def _load_users():
    users = db.query(SITE, "users")
    for u in users:
        if isinstance(u.get("profile"), str):
            try:
                u["profile"] = json.loads(u["profile"])
            except (json.JSONDecodeError, TypeError):
                u["profile"] = {}
    return users


def _save_users(users):
    db.save_collection(SITE, "users", users)


def _load_saved_jobs():
    saved = db.query(SITE, "saved_jobs")
    for s in saved:
        for field in ("tags", "requirements"):
            if isinstance(s.get(field), str):
                try:
                    s[field] = json.loads(s[field])
                except (json.JSONDecodeError, TypeError):
                    s[field] = []
    return saved


def _load_applications():
    apps = db.query(SITE, "applications")
    for a in apps:
        if isinstance(a.get("status_history"), str):
            try:
                a["status_history"] = json.loads(a["status_history"])
            except (json.JSONDecodeError, TypeError):
                a["status_history"] = []
    return apps


def _load_alerts():
    alerts = db.query(SITE, "job_alerts")
    for a in alerts:
        if isinstance(a.get("filters"), str):
            try:
                a["filters"] = json.loads(a["filters"])
            except (json.JSONDecodeError, TypeError):
                a["filters"] = {}
    return alerts


def _load_search_history():
    history = db.query(SITE, "search_history")
    for h in history:
        if isinstance(h.get("filters_applied"), str):
            try:
                h["filters_applied"] = json.loads(h["filters_applied"])
            except (json.JSONDecodeError, TypeError):
                h["filters_applied"] = {}
    return history


# ---------------------------------------------------------------------------
# User / session helpers
# ---------------------------------------------------------------------------

def _get_user(user_id):
    return db.get_item(SITE, "users", user_id)


def _get_current_user():
    return current_user(_get_user, session_keys=("job_sites_user_id",))


def _get_browsing_user():
    """Return logged-in user or fall back to user 1 for browse-only mode."""
    return browsing_user(_get_user, session_keys=("job_sites_user_id",), fallback=1)


# ---------------------------------------------------------------------------
# Search / scoring helpers
# ---------------------------------------------------------------------------

def _keyword_score(query, text):
    """Score how well a query matches a text string (term overlap)."""
    terms = query.lower().split()
    text_l = text.lower()
    return sum(1 for t in terms if t in text_l)


def _job_search_text(job):
    """Build a full-text search target from all job fields."""
    parts = [
        job.get("job_title", ""),
        job.get("company", ""),
        job.get("description_snippet", ""),
        job.get("location", ""),
        job.get("job_type", ""),
        " ".join(job.get("tags", [])),
        " ".join(job.get("requirements", [])),
    ]
    return " ".join(parts)


def _semantic_score(query, job):
    """Semantic search: keyword overlap across all fields, weighted."""
    return _keyword_score(query, _job_search_text(job))


def _parse_salary_num(s):
    """Parse a salary string like '$59K', '$155,000', '99K', '185000' to int.

    Returns 0 for unparseable values.
    """
    try:
        if not s or not s.strip():
            return 0
        s = s.strip().replace("$", "").replace(",", "").strip()
        if not s or not s[0].isdigit():
            return 0
        if s.upper().endswith("K"):
            return int(float(s[:-1]) * 1000)
        elif s.upper().endswith("M"):
            return int(float(s[:-1]) * 1000000)
        return int(float(s))
    except (ValueError, IndexError, AttributeError):
        return 0


def _split_salary_range(salary_range):
    """Split a salary range string into (low_str, high_str).

    Handles formats: '$59K-$99K', '$155,000 - $185,000', '$100K'.
    Uses regex to split on ' - ' or '-' between dollar amounts,
    avoiding incorrect splits on negative numbers.
    """
    if not salary_range or not salary_range.strip():
        return "", ""
    # Split on ' - ' first (spaced dash), then bare '-' between amounts
    parts = re.split(r'\s*-\s*(?=\$|\d)', salary_range, maxsplit=1)
    if len(parts) >= 2:
        return parts[0].strip(), parts[1].strip()
    return parts[0].strip(), parts[0].strip()


def _parse_min_salary(salary_range):
    """Extract the minimum salary integer from a range like '$59K-$99K' or '$155,000 - $185,000'."""
    low, _ = _split_salary_range(salary_range)
    return _parse_salary_num(low)


def _parse_max_salary(salary_range):
    """Extract the maximum salary integer from a salary range string."""
    _, high = _split_salary_range(salary_range)
    return _parse_salary_num(high)


# ---------------------------------------------------------------------------
# Unified search/filter/sort — works for both DB and file mode
# ---------------------------------------------------------------------------

# UI job-type values don't always match the stored work_type verbatim
# (e.g. the "Internship" radio submits "internship" but data stores "Intern").
_JOB_TYPE_ALIASES = {"internship": "intern"}


def _normalize_job_type(job_type):
    """Map a UI job_type value to the stored work_type value (lowercased)."""
    jt = job_type.lower()
    return _JOB_TYPE_ALIASES.get(jt, jt)


def _search_and_filter_jobs(q="", location="", job_type="", company="",
                            salary_min=None, salary_max=None,
                            date_from="", date_to="", sort="date",
                            tags=""):
    """Search, filter, and sort jobs."""
    jobs = list(_get_jobs())

    # search_by_query / filter_by_query
    if q:
        jobs = [j for j in jobs if _keyword_score(q, _job_search_text(j)) > 0]
    if job_type:
        jt = _normalize_job_type(job_type)
        jobs = [j for j in jobs if j.get("work_type", j.get("job_type", "")).lower() == jt]
    if location:
        jobs = [j for j in jobs if location.lower() in j["location"].lower()]
    if company:
        jobs = [j for j in jobs if j["company"].lower() == company.lower()]
    if salary_min is not None:
        jobs = [j for j in jobs
                if _parse_min_salary(j.get("salary_range", "")) >= salary_min
                and _parse_min_salary(j.get("salary_range", "")) > 0]
    if salary_max is not None:
        jobs = [j for j in jobs
                if _parse_min_salary(j.get("salary_range", "")) <= salary_max
                and _parse_min_salary(j.get("salary_range", "")) > 0]
    if date_from:
        jobs = [j for j in jobs if j.get("job_posting_date", j.get("posted_date", "")) >= date_from]
    if date_to:
        jobs = [j for j in jobs if j.get("job_posting_date", j.get("posted_date", "")) <= date_to]
    if tags:
        tag_list = [t.strip().lower() for t in tags.split(",")]
        jobs = [
            j for j in jobs
            if any(t in [tg.lower() for tg in j.get("tags", [])] for t in tag_list)
        ]

    # sort_by_ranking
    if sort == "date":
        jobs.sort(key=lambda j: j.get("job_posting_date", j.get("posted_date", "")), reverse=True)
    elif sort == "salary_desc":
        jobs.sort(key=lambda j: _parse_min_salary(j.get("salary_range", "")), reverse=True)
    elif sort == "salary_asc":
        jobs.sort(key=lambda j: _parse_min_salary(j.get("salary_range", "")))
    elif sort == "relevance" and q:
        jobs.sort(key=lambda j: -_keyword_score(q, _job_search_text(j)))
    elif sort == "company":
        jobs.sort(key=lambda j: j.get("company", "").lower())
    elif sort == "title":
        jobs.sort(key=lambda j: j.get("job_title", "").lower())

    return jobs


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    """Job search landing page with nav dropdown for categories."""
    user, logged_in = _get_browsing_user()
    recent_searches = [
        s for s in _load_search_history() if s["user_id"] == user["id"]
    ][:5]
    # Collect distinct companies for navigate_by_dropdown
    companies = _get_companies()
    return render_template(
        "job-sites/index.html",
        user=user, logged_in=logged_in,
        recent_searches=recent_searches,
        companies=companies,
    )


@blueprint.route("/jobs")
def jobs_page():
    """Search results page with full filter/sort support.

    Macro support:
    - search_by_query: ?q=...
    - filter_by_query: ?q=... (same as search)
    - filter_by_dropdown: ?job_type=... (select)
    - filter_by_radio: ?job_type=... (radio buttons in sidebar)
    - filter_by_slider: ?salary_min=...&salary_max=...
    - filter_by_date_range: ?date_from=...&date_to=...
    - sort_by_ranking: ?sort=relevance|date|salary_asc|salary_desc
    """
    user, logged_in = _get_browsing_user()
    q = request.args.get("q", "").strip()
    location = request.args.get("location", "").strip()
    job_type = request.args.get("job_type", "").strip()
    salary_min = request.args.get("salary_min", type=int)
    salary_max = request.args.get("salary_max", type=int)
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    sort = request.args.get("sort", "date").strip()
    company = request.args.get("company", "").strip()

    jobs = _search_and_filter_jobs(
        q=q, location=location, job_type=job_type, company=company,
        salary_min=salary_min, salary_max=salary_max,
        date_from=date_from, date_to=date_to, sort=sort,
    )

    # Collect unique companies for dropdown
    companies = _get_companies()

    return render_template(
        "job-sites/jobs.html",
        user=user, logged_in=logged_in,
        jobs=jobs, query=q, location=location, job_type=job_type,
        salary_min=salary_min, salary_max=salary_max,
        date_from=date_from, date_to=date_to,
        sort=sort, company=company, companies=companies,
    )


@blueprint.route("/job/<int:job_id>")
def job_detail(job_id):
    """Single job listing detail page (navigate_by_route, extract_by_route)."""
    user, logged_in = _get_browsing_user()
    job = _get_job_by_id(job_id)
    if job is None:
        abort(404)
    # Check if this user has already applied
    applications = _load_applications()
    applied = any(
        a for a in applications
        if a["user_id"] == user["id"] and a["job_title"] == job["job_title"]
        and a["company"] == job["company"]
    )
    # Check if company is followed
    followed_companies = user.get("followed_companies", [])
    is_following = job["company"] in followed_companies
    return render_template(
        "job-sites/job_detail.html",
        user=user, logged_in=logged_in,
        job=job, applied=applied, is_following=is_following,
    )


@blueprint.route("/company/<path:company_name>")
def company_page(company_name):
    """Company page showing all jobs from a company (navigate_by_dropdown target)."""
    user, logged_in = _get_browsing_user()
    all_jobs = _get_jobs()
    company_jobs = [j for j in all_jobs if j["company"].lower() == company_name.lower()]
    if not company_jobs:
        abort(404)
    followed_companies = user.get("followed_companies", [])
    is_following = company_name in followed_companies
    return render_template(
        "job-sites/company.html",
        user=user, logged_in=logged_in,
        company_name=company_name,
        jobs=company_jobs,
        is_following=is_following,
    )


@blueprint.route("/saved")
def saved_page():
    """Saved jobs list (save_by_toggle)."""
    user, logged_in = _get_browsing_user()
    jobs = db.query(SITE, "saved_jobs", where={"user_id": user["id"]})
    return render_template(
        "job-sites/saved.html",
        user=user, logged_in=logged_in, jobs=jobs,
    )


def _saved_as_job(saved):
    """Adapt a saved_jobs snapshot row to the shape job_detail.html renders.

    Saved jobs are external-listing snapshots with no catalog row, so they
    get their own detail/apply routes keyed on the saved-row id.
    """
    job = dict(saved)
    job["job_description"] = saved.get("description_snippet", "")
    job.setdefault("requirements", [])
    job.setdefault("row_id", None)
    return job


def _get_saved_job(user, saved_id):
    rows = db.query(SITE, "saved_jobs", where={"id": saved_id}, limit=1)
    saved = rows[0] if rows else None
    if saved is None or saved.get("user_id") != user["id"]:
        return None
    return saved


@blueprint.route("/saved/<int:saved_id>")
def saved_job_detail(saved_id):
    """Detail view for a saved (external snapshot) job — same look and
    Apply flow as catalog job pages."""
    user, logged_in = _get_browsing_user()
    saved = _get_saved_job(user, saved_id)
    if saved is None:
        abort(404)
    job = _saved_as_job(saved)
    applications = _load_applications()
    applied = any(
        a for a in applications
        if a["user_id"] == user["id"] and a["job_title"] == job["job_title"]
        and a["company"] == job["company"]
    )
    is_following = job["company"] in user.get("followed_companies", [])
    return render_template(
        "job-sites/job_detail.html",
        user=user, logged_in=logged_in,
        job=job, applied=applied, is_following=is_following,
        saved_view=True,
        apply_url=url_for("job-sites.apply_saved_page", saved_id=saved_id),
    )


@blueprint.route("/applications")
def applications_page():
    """Applications list."""
    user, logged_in = _get_browsing_user()
    apps = db.query(SITE, "applications", where={"user_id": user["id"]})
    return render_template(
        "job-sites/applications.html",
        user=user, logged_in=logged_in, applications=apps,
    )


@blueprint.route("/application/<int:app_id>")
def application_detail(app_id):
    """Single application detail page."""
    user, logged_in = _get_browsing_user()
    applications = _load_applications()
    app = next((a for a in applications if a["id"] == app_id), None)
    if app is None:
        abort(404)
    return render_template(
        "job-sites/application_detail.html",
        user=user, logged_in=logged_in, application=app,
    )


@blueprint.route("/alerts")
def alerts_page():
    """Job alerts management page (subscribe_by_toggle, create_from_free_text)."""
    user, logged_in = _get_browsing_user()
    alerts = db.query(SITE, "job_alerts", where={"user_id": user["id"]})
    return render_template(
        "job-sites/alerts.html",
        user=user, logged_in=logged_in, alerts=alerts,
    )


@blueprint.route("/apply/saved/<int:saved_id>", methods=["GET", "POST"])
def apply_saved_page(saved_id):
    """Apply to a saved (external snapshot) job — same form and application
    record as catalog jobs (applications match on title + company)."""
    user, logged_in = _get_browsing_user()
    saved = _get_saved_job(user, saved_id)
    if saved is None:
        abort(404)
    return _apply_flow(user, logged_in, _saved_as_job(saved))


@blueprint.route("/apply/<int:job_id>", methods=["GET", "POST"])
def apply_form_page(job_id):
    """Apply to a job via HTML form (apply_by_form macro).

    GET: show the application form.
    POST: process the form submission.
    """
    user, logged_in = _get_browsing_user()
    job = _get_job_by_id(job_id)
    if job is None:
        abort(404)
    return _apply_flow(user, logged_in, job)


def _apply_flow(user, logged_in, job):
    """Shared GET/POST application flow for catalog and saved jobs."""
    if request.method == "GET":
        return render_template(
            "job-sites/apply.html",
            user=user, logged_in=logged_in, job=job, success=False, error=None,
        )

    # POST: process form
    applications = _load_applications()
    already = any(
        a for a in applications
        if a["user_id"] == user["id"] and a["job_title"] == job["job_title"]
        and a["company"] == job["company"]
    )
    if already:
        return render_template(
            "job-sites/apply.html",
            user=user, logged_in=logged_in, job=job, success=False,
            error="You have already applied to this position.",
        )

    cover_letter = request.form.get("cover_letter", "").strip()
    now = datetime.now().strftime("%Y-%m-%d")

    # Identifying fields posted with the application so the request body records
    # WHAT was applied to (job id / title / company) and the resume that was
    # attached.  The URL-derived `job` remains the source of truth; these only
    # need to match it.
    posted_job_id = request.form.get("job_id", "").strip()
    posted_resume_name = request.form.get("resume_filename", "").strip()

    # Handle resume upload (upload_by_upload)
    resume_filename = f"{user['username']}_resume.pdf"
    resume_file = request.files.get("resume")
    if resume_file and resume_file.filename:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r'[^\w.\-]', '_', resume_file.filename)
        resume_filename = f"{user['id']}_{safe_name}"
        resume_file.save(str(UPLOAD_DIR / resume_filename))
    elif posted_resume_name:
        # No file bytes reached the server, but the applicant named a resume in
        # the form -- record that name so the attachment is still tracked.
        resume_filename = re.sub(r'[^\w.\-]', '_', posted_resume_name)

    new_app = {
        "id": max(a["id"] for a in applications) + 1 if applications else 1,
        "user_id": user["id"],
        "root_user_id": user.get("root_user_id", user["id"]),
        "job_title": job["job_title"],
        "company": job["company"],
        "location": job["location"],
        "salary_range": job.get("salary_range", ""),
        "applied_date": now,
        "status": "applied",
        "status_history": [{"status": "applied", "date": now}],
        "cover_letter_submitted": bool(cover_letter),
        "resume_version": resume_filename,
        "recruiter_name": "",
        "recruiter_email": "",
        "notes": cover_letter,
    }
    applications.append(new_app)
    db.save_collection(SITE, "applications", applications)
    _add_email(user["id"], "noreply@job-sites.lakeport.local",
               "Application submitted",
               f'Your application to "{job["job_title"]}" at {job["company"]} has been submitted.')

    return render_template(
        "job-sites/apply.html",
        user=user, logged_in=logged_in, job=job, success=True, error=None,
        application=new_app,
    )


@blueprint.route("/upload-resume", methods=["POST"])
def form_upload_resume():
    """Upload resume via HTML form on profile page."""
    user, logged_in = _get_browsing_user()
    resume = request.files.get("resume")
    if resume and resume.filename:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r'[^\w.\-]', '_', resume.filename)
        filename = f"{user['id']}_{safe_name}"
        resume.save(str(UPLOAD_DIR / filename))
        users = _load_users()
        u = next((u for u in users if u["id"] == user["id"]), None)
        if u:
            u.setdefault("profile", {})["resume_uploaded"] = True
            u["profile"]["resume_last_updated"] = datetime.now().strftime("%Y-%m-%d")
            u["profile"]["resume_filename"] = filename
            _save_users(users)
    return redirect(url_for("job-sites.profile_page"))


@blueprint.route("/profile")
def profile_page():
    """User profile page showing followed companies and subscriptions."""
    user, logged_in = _get_browsing_user()
    followed = user.get("followed_companies", [])
    subscriptions = user.get("subscribed_alerts", [])
    return render_template(
        "job-sites/profile.html",
        user=user, logged_in=logged_in,
        followed_companies=followed,
        subscribed_alerts=subscriptions,
    )


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("job-sites/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user:
        return render_template("job-sites/login.html",
                               error="Account not found. Please check your email or username.")
    stored_pw = user.get("password", "password")
    if password and password != stored_pw:
        return render_template("job-sites/login.html", error="Invalid password")
    session["job_sites_user_id"] = user["id"]
    emit("signup", user_id=user["id"], site_name="job-sites", username=username, password=request.form.get("password", ""), email="")
    return redirect(url_for("job-sites.index"))


@blueprint.route("/logout")
def logout():
    session.pop("job_sites_user_id", None)
    return redirect(url_for("job-sites.index"))


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/jobs")
def api_jobs():
    """GET - Search/filter/sort jobs.

    Query params: q, location, job_type, salary_min, salary_max, tags,
                  date_from, date_to, sort, company.
    """
    q = request.args.get("q", "").strip()
    location = request.args.get("location", "").strip()
    job_type = request.args.get("job_type", "").strip()
    salary_min = request.args.get("salary_min", type=int)
    salary_max = request.args.get("salary_max", type=int)
    tags = request.args.get("tags", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    sort = request.args.get("sort", "date").strip()
    company = request.args.get("company", "").strip()

    jobs = _search_and_filter_jobs(
        q=q, location=location, job_type=job_type, company=company,
        salary_min=salary_min, salary_max=salary_max,
        date_from=date_from, date_to=date_to, sort=sort, tags=tags,
    )

    return jsonify(jobs)


@blueprint.route("/api/jobs/semantic")
def api_jobs_semantic():
    """GET - Semantic search over all job fields (search_by_semantic, filter_by_semantic, extract_by_semantic).

    Uses weighted keyword overlap across title, company, description, tags, requirements.
    Returns results sorted by relevance score descending.
    """
    q = request.args.get("q", "").strip()
    job_type = request.args.get("job_type", "").strip()
    location = request.args.get("location", "").strip()

    jobs = list(_get_jobs())

    if not q:
        return jsonify(jobs)

    scored = [(j, _semantic_score(q, j)) for j in jobs]
    scored = [(j, s) for j, s in scored if s > 0]
    scored.sort(key=lambda x: -x[1])
    results = [j for j, _ in scored]

    # Additional filters on semantic results
    if job_type:
        jt = _normalize_job_type(job_type)
        results = [j for j in results if j.get("work_type", j.get("job_type", "")).lower() == jt]
    if location:
        results = [j for j in results if location.lower() in j["location"].lower()]

    return jsonify(results)


@blueprint.route("/api/jobs/<int:job_id>")
def api_job(job_id):
    """GET - Single job details (extract_by_route)."""
    job = _get_job_by_id(job_id)
    if job is None:
        abort(404)
    return jsonify(job)


@blueprint.route("/api/jobs/<int:job_id>/save", methods=["POST"])
def api_toggle_save(job_id):
    """POST - Toggle save/unsave a job for current user (save_by_toggle)."""
    user, logged_in = _get_browsing_user()
    job = _get_job_by_id(job_id)
    if job is None:
        abort(404)

    saved_jobs = _load_saved_jobs()

    # Check if already saved by this user (match by job_title + company)
    already = next(
        (s for s in saved_jobs
         if s["user_id"] == user["id"]
         and s["job_title"] == job["job_title"]
         and s["company"] == job["company"]),
        None,
    )

    if already:
        # Unsave: remove from list
        saved_jobs = [s for s in saved_jobs if s["id"] != already["id"]]
        db.save_collection(SITE, "saved_jobs", saved_jobs)
        return jsonify({"status": "unsaved", "job_id": job_id})
    else:
        # Save: create a saved entry referencing this catalog job
        new_entry = dict(job)
        new_entry["id"] = max((s["id"] for s in saved_jobs), default=0) + 1
        new_entry["user_id"] = user["id"]
        new_entry["root_user_id"] = user.get("root_user_id", user["id"])
        new_entry["saved_date"] = datetime.now().strftime("%Y-%m-%d")
        new_entry["notes"] = ""
        saved_jobs.append(new_entry)
        db.save_collection(SITE, "saved_jobs", saved_jobs)
        return jsonify({"status": "saved", "job_id": new_entry["id"]})


@blueprint.route("/api/jobs/<int:job_id>/apply", methods=["POST"])
def api_apply(job_id):
    """POST - Apply to a job via API."""
    user, logged_in = _get_browsing_user()
    job = _get_job_by_id(job_id)
    if job is None:
        abort(404)

    applications = _load_applications()
    # Check if already applied
    already = any(
        a for a in applications
        if a["user_id"] == user["id"] and a["job_title"] == job["job_title"]
        and a["company"] == job["company"]
    )
    if already:
        return jsonify({"error": "Already applied to this position"}), 409

    data = request.get_json(silent=True) or {}
    now = datetime.now().strftime("%Y-%m-%d")
    new_app = {
        "id": max(a["id"] for a in applications) + 1 if applications else 1,
        "user_id": user["id"],
        "root_user_id": user.get("root_user_id", user["id"]),
        "job_title": job["job_title"],
        "company": job["company"],
        "location": job["location"],
        "salary_range": job.get("salary_range", ""),
        "applied_date": now,
        "status": "applied",
        "status_history": [{"status": "applied", "date": now}],
        "cover_letter_submitted": data.get("cover_letter_submitted", False),
        "resume_version": data.get("resume_version", f"{user['username']}_resume.pdf"),
        "recruiter_name": "",
        "recruiter_email": "",
        "notes": data.get("notes", ""),
    }
    applications.append(new_app)
    db.save_collection(SITE, "applications", applications)
    emit("booking", user_id=user["id"], title=f"Applied: {job['job_title']} at {job['company']}", start=now, location=job.get("location", ""))
    return jsonify(new_app), 201


@blueprint.route("/api/saved-jobs")
def api_saved_jobs():
    """GET - Saved jobs for current user."""
    user, _ = _get_browsing_user()
    jobs = db.query(SITE, "saved_jobs", where={"user_id": user["id"]})
    return jsonify(jobs)


@blueprint.route("/api/applications", methods=["GET", "POST"])
def api_applications():
    """GET - List applications for current user. POST - Create new application."""
    user, _ = _get_browsing_user()
    if request.method == "GET":
        status_filter = request.args.get("status", "").strip()
        apps = db.query(SITE, "applications", where={"user_id": user["id"]})
        if status_filter:
            apps = [a for a in apps if a["status"].lower() == status_filter.lower()]
        return jsonify(apps)

    # POST: create application from JSON body
    data = request.get_json(silent=True) or {}
    applications = _load_applications()
    now = datetime.now().strftime("%Y-%m-%d")
    new_app = {
        "id": max(a["id"] for a in applications) + 1 if applications else 1,
        "user_id": user["id"],
        "root_user_id": user.get("root_user_id", user["id"]),
        "job_title": data.get("job_title", ""),
        "company": data.get("company", ""),
        "location": data.get("location", ""),
        "salary_range": data.get("salary_range", ""),
        "applied_date": now,
        "status": "applied",
        "status_history": [{"status": "applied", "date": now}],
        "cover_letter_submitted": data.get("cover_letter_submitted", False),
        "resume_version": data.get("resume_version", f"{user['username']}_resume.pdf"),
        "recruiter_name": data.get("recruiter_name", ""),
        "recruiter_email": data.get("recruiter_email", ""),
        "notes": data.get("notes", ""),
    }
    applications.append(new_app)
    db.save_collection(SITE, "applications", applications)
    return jsonify(new_app), 201


@blueprint.route("/api/applications/<int:app_id>", methods=["GET", "PUT"])
def api_application(app_id):
    """GET - Single application. PUT - Update status/notes."""
    user, _ = _get_browsing_user()
    applications = _load_applications()
    app = next((a for a in applications if a["id"] == app_id), None)
    if app is None:
        abort(404)

    if request.method == "GET":
        return jsonify(app)

    # PUT: update fields
    data = request.get_json(silent=True) or {}
    if "status" in data and data["status"] != app["status"]:
        now = datetime.now().strftime("%Y-%m-%d")
        entry = {"status": data["status"], "date": now}
        if "reason" in data:
            entry["reason"] = data["reason"]
        if "note" in data:
            entry["note"] = data["note"]
        app["status_history"].append(entry)
        app["status"] = data["status"]
    if "notes" in data:
        app["notes"] = data["notes"]
    if "recruiter_name" in data:
        app["recruiter_name"] = data["recruiter_name"]
    if "recruiter_email" in data:
        app["recruiter_email"] = data["recruiter_email"]
    if "cover_letter_submitted" in data:
        app["cover_letter_submitted"] = data["cover_letter_submitted"]

    db.save_collection(SITE, "applications", applications)
    return jsonify(app)


@blueprint.route("/api/alerts", methods=["GET", "POST", "DELETE"])
def api_alerts():
    """GET - List alerts. POST - Create alert (create_from_free_text). DELETE - Remove alert."""
    user, _ = _get_browsing_user()
    alerts = _load_alerts()

    if request.method == "GET":
        user_alerts = [a for a in alerts if a["user_id"] == user["id"]]
        return jsonify(user_alerts)

    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        now = datetime.now().strftime("%Y-%m-%d")
        new_alert = {
            "id": max(a["id"] for a in alerts) + 1 if alerts else 1,
            "user_id": user["id"],
            "root_user_id": user.get("root_user_id", user["id"]),
            "alert_name": data.get("alert_name", "New Alert"),
            "search_query": data.get("search_query", ""),
            "filters": data.get("filters", {}),
            "frequency": data.get("frequency", "weekly"),
            "email_notifications": data.get("email_notifications", True),
            "push_notifications": data.get("push_notifications", False),
            "created_date": now,
            "last_triggered": None,
            "matches_last_period": 0,
            "is_active": True,
        }
        alerts.append(new_alert)
        db.save_collection(SITE, "job_alerts", alerts)
        return jsonify(new_alert), 201

    # DELETE
    data = request.get_json(silent=True) or {}
    alert_id = data.get("id")
    if alert_id is None:
        return jsonify({"error": "Missing alert id"}), 400
    alert = next((a for a in alerts if a["id"] == alert_id and a["user_id"] == user["id"]), None)
    if alert is None:
        abort(404)
    alerts = [a for a in alerts if a["id"] != alert_id]
    db.save_collection(SITE, "job_alerts", alerts)
    return jsonify({"status": "deleted", "id": alert_id})


@blueprint.route("/api/alerts/<int:alert_id>/toggle", methods=["POST"])
def api_toggle_alert(alert_id):
    """POST - Toggle alert active/paused (subscribe_by_toggle)."""
    user, _ = _get_browsing_user()
    alerts = _load_alerts()
    alert = next((a for a in alerts if a["id"] == alert_id and a["user_id"] == user["id"]), None)
    if alert is None:
        abort(404)
    alert["is_active"] = not alert["is_active"]
    db.save_collection(SITE, "job_alerts", alerts)
    action = "subscribed" if alert["is_active"] else "unsubscribed"
    return jsonify({"action": action, "alert_id": alert_id, "is_active": alert["is_active"]})


@blueprint.route("/api/companies")
def api_companies():
    """GET - List all unique companies with job counts (navigate_by_dropdown data)."""
    all_jobs = _get_jobs()
    company_counts = {}
    for j in all_jobs:
        c = j["company"]
        company_counts[c] = company_counts.get(c, 0) + 1
    result = [{"name": name, "job_count": count} for name, count in sorted(company_counts.items())]
    return jsonify(result)


@blueprint.route("/api/companies/<path:company_name>/stats")
def api_company_stats(company_name):
    """GET - Stats for a specific company (extract_by_dropdown)."""
    all_jobs = _get_jobs()
    company_jobs = [j for j in all_jobs if j["company"].lower() == company_name.lower()]
    if not company_jobs:
        return jsonify({"company": company_name, "job_count": 0})

    salaries = [_parse_min_salary(j.get("salary_range", "")) for j in company_jobs]
    salaries = [s for s in salaries if s > 0]
    job_types = list(set(j.get("job_type", "unknown") for j in company_jobs))
    all_tags = []
    for j in company_jobs:
        all_tags.extend(j.get("tags", []))
    tag_counts = {}
    for t in all_tags:
        tag_counts[t] = tag_counts.get(t, 0) + 1

    return jsonify({
        "company": company_name,
        "job_count": len(company_jobs),
        "job_types": job_types,
        "avg_min_salary": round(sum(salaries) / len(salaries)) if salaries else 0,
        "min_salary": min(salaries) if salaries else 0,
        "max_salary": max(salaries) if salaries else 0,
        "top_tags": sorted(tag_counts.items(), key=lambda x: -x[1])[:5],
        "locations": list(set(j["location"] for j in company_jobs)),
    })


@blueprint.route("/api/follow", methods=["POST"])
def api_follow_company():
    """POST - Toggle follow/unfollow a company (follow_by_toggle).

    Body: {"company": "Company Name"}
    """
    user, _ = _get_browsing_user()
    data = request.get_json(silent=True) or {}
    company = data.get("company", "").strip()
    if not company:
        return jsonify({"error": "company required"}), 400

    users = _load_users()
    u = next((u for u in users if u["id"] == user["id"]), None)
    if not u:
        abort(404)

    followed = u.setdefault("followed_companies", [])
    if company in followed:
        followed.remove(company)
        action = "unfollowed"
    else:
        followed.append(company)
        action = "followed"
    _save_users(users)
    return jsonify({"action": action, "company": company, "total_followed": len(followed)})


@blueprint.route("/api/subscribe", methods=["POST"])
def api_subscribe():
    """POST - Toggle subscribe/unsubscribe to job alerts for a search query (subscribe_by_toggle).

    Body: {"query": "search terms"} or {"alert_id": 1}
    """
    user, _ = _get_browsing_user()
    data = request.get_json(silent=True) or {}

    # If alert_id given, toggle that specific alert
    alert_id = data.get("alert_id")
    if alert_id is not None:
        alerts = _load_alerts()
        alert = next((a for a in alerts if a["id"] == alert_id and a["user_id"] == user["id"]), None)
        if alert is None:
            abort(404)
        alert["is_active"] = not alert["is_active"]
        db.save_collection(SITE, "job_alerts", alerts)
        action = "subscribed" if alert["is_active"] else "unsubscribed"
        return jsonify({"action": action, "alert_id": alert_id, "is_active": alert["is_active"]})

    # Otherwise create a new subscription from query text
    query = data.get("query", "").strip()
    if not query:
        return jsonify({"error": "query or alert_id required"}), 400

    alerts = _load_alerts()
    now = datetime.now().strftime("%Y-%m-%d")
    new_alert = {
        "id": max(a["id"] for a in alerts) + 1 if alerts else 1,
        "user_id": user["id"],
        "root_user_id": user.get("root_user_id", user["id"]),
        "alert_name": f"Alert: {query[:30]}",
        "search_query": query,
        "filters": data.get("filters", {}),
        "frequency": data.get("frequency", "weekly"),
        "email_notifications": True,
        "push_notifications": False,
        "created_date": now,
        "last_triggered": None,
        "matches_last_period": 0,
        "is_active": True,
    }
    alerts.append(new_alert)
    db.save_collection(SITE, "job_alerts", alerts)
    return jsonify({"action": "subscribed", "alert_id": new_alert["id"], "is_active": True}), 201


@blueprint.route("/api/upload-resume", methods=["POST"])
def api_upload_resume():
    """POST - Upload a resume file (upload_by_upload).

    Accepts multipart/form-data with file field 'resume'.
    """
    user, _ = _get_browsing_user()
    resume = request.files.get("resume")
    if not resume or not resume.filename:
        return jsonify({"error": "No file uploaded"}), 400

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r'[^\w.\-]', '_', resume.filename)
    filename = f"{user['id']}_{safe_name}"
    filepath = UPLOAD_DIR / filename
    resume.save(str(filepath))

    # Update user profile
    users = _load_users()
    u = next((u for u in users if u["id"] == user["id"]), None)
    if u:
        u.setdefault("profile", {})["resume_uploaded"] = True
        u["profile"]["resume_last_updated"] = datetime.now().strftime("%Y-%m-%d")
        u["profile"]["resume_filename"] = filename
        _save_users(users)

    return jsonify({
        "status": "uploaded",
        "filename": filename,
        "size": os.path.getsize(str(filepath)),
    }), 201


@blueprint.route("/api/search-history")
def api_search_history():
    """GET - Search history for current user."""
    user, _ = _get_browsing_user()
    history = [h for h in _load_search_history() if h["user_id"] == user["id"]]
    return jsonify(history)


@blueprint.route("/api/stats")
def api_stats():
    """GET - Dashboard stats for current user."""
    user, _ = _get_browsing_user()
    saved = [j for j in _load_saved_jobs() if j["user_id"] == user["id"]]
    apps = db.query(SITE, "applications", where={"user_id": user["id"]})
    alerts = db.query(SITE, "job_alerts", where={"user_id": user["id"]})
    history = [h for h in _load_search_history() if h["user_id"] == user["id"]]

    active_apps = [a for a in apps if a["status"] not in ("withdrawn", "rejected", "declined")]
    interviewing = [a for a in apps if a["status"] == "interviewing"]

    return jsonify({
        "saved_jobs_count": len(saved),
        "total_applications": len(apps),
        "active_applications": len(active_apps),
        "interviewing_count": len(interviewing),
        "active_alerts": len([a for a in alerts if a.get("is_active")]),
        "total_searches": len(history),
        "companies_applied": list(set(a["company"] for a in apps)),
        "followed_companies": user.get("followed_companies", []),
    })

@blueprint.route("/api/users/<int:user_id>")
def api_user(user_id):
    """GET - User profile data (for verifiers)."""
    user = _get_user(user_id)
    if not user:
        abort(404)
    return jsonify(user)
