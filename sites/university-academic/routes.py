"""Meridian State University -- university academic portal.

Serves course catalog, faculty directory, department/research-area info,
university events, and alumni network.  Data files live under
DATA_SOURCES_DIR/university-academic/.

Macro support (18):
  navigate_by_semantic, navigate_by_dropdown, navigate_by_route,
  search_by_query, search_by_semantic, search_by_route,
  filter_by_dropdown, filter_by_route,
  extract_by_query, extract_by_checkbox, extract_from_table, extract_by_route,
  extract_by_date_range, compare_from_table,
  submit_by_query, apply_by_form, export_by_dropdown, subscribe_by_toggle
"""
import csv
import io
import json
import pathlib

from flask import (
    Blueprint, Response, abort, jsonify, render_template, request, session,
    redirect, url_for,
)
from app import db

SITE = "university-academic"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "university-academic",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _courses():
    return db.query(SITE, "courses")


def _faculty():
    return db.query(SITE, "faculty")


def _departments():
    rows = db.query(SITE, "departments")
    if rows and len(rows) == 1:
        return rows[0]
    # Fallback: return first row or empty dict
    return rows[0] if rows else {}


def _events():
    return db.query(SITE, "events")


def _alumni():
    return db.query(SITE, "alumni")


def _research_areas():
    dept_data = _departments()
    return dept_data.get("research_areas", [])


def _load_users():
    return db.query(SITE, "users")


def _save_users(users):
    db.save_collection(SITE, "users", users)


def _get_user(net_id):
    results = db.query(SITE, "users", where={"net_id": net_id}, limit=1)
    return results[0] if results else None


def _keyword_score(query, text):
    """Simple keyword overlap scoring for semantic search."""
    terms = query.lower().split()
    text_lower = text.lower()
    return sum(1 for t in terms if t in text_lower)


# ---------------------------------------------------------------------------
# In-memory mutable state for subscriptions and applications
# (persisted in users.json)
# ---------------------------------------------------------------------------

def _ensure_user_field(net_id, field, default):
    """Ensure a user has a particular mutable field; return user dict."""
    users = _load_users()
    user = next((u for u in users if u["net_id"] == net_id), None)
    if not user:
        return None, users
    if field not in user:
        user[field] = default
    return user, users


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    """Homepage -- featured courses, upcoming events, department overview."""
    courses = _courses()
    events = _events()
    dept_data = _departments()
    faculty = _faculty()
    research_areas = dept_data.get("research_areas", [])
    # Feature some advanced courses
    featured_courses = [c for c in courses if c["level"] == "advanced"][:4]
    # Sort events by date, show upcoming
    sorted_events = sorted(events, key=lambda e: e["date"])
    upcoming_events = sorted_events[:3]
    return render_template(
        "university-academic/index.html",
        department=dept_data.get("department", {}),
        featured_courses=featured_courses,
        upcoming_events=upcoming_events,
        research_areas=research_areas,
        faculty_count=len(faculty),
        course_count=len(courses),
    )


@blueprint.route("/courses")
def courses_page():
    """Course catalog with filtering.
    Macros: search_by_query, filter_by_dropdown, extract_by_checkbox
    """
    courses = _courses()
    research_areas = _research_areas()

    # Filters
    dept_filter = request.args.get("dept", "")
    level_filter = request.args.get("level", "")
    search_query = request.args.get("q", "")
    # Checkbox-based filtering (extract_by_checkbox)
    checked_levels = request.args.getlist("levels")

    filtered = courses
    if dept_filter:
        filtered = [c for c in filtered if c.get("research_area") == dept_filter]
    if level_filter:
        filtered = [c for c in filtered if c["level"] == level_filter]
    if checked_levels:
        filtered = [c for c in filtered if c["level"] in checked_levels]
    if search_query:
        q = search_query.lower()
        filtered = [c for c in filtered
                     if q in c["title"].lower()
                     or q in c["code"].lower()
                     or q in c["description"].lower()]

    levels = sorted(set(c["level"] for c in courses))
    areas = sorted(set(c["research_area"] for c in courses if c.get("research_area")))

    return render_template(
        "university-academic/courses.html",
        courses=filtered,
        levels=levels,
        areas=areas,
        research_areas=research_areas,
        dept_filter=dept_filter,
        level_filter=level_filter,
        search_query=search_query,
        checked_levels=checked_levels,
    )


# --- filter_by_route: filter courses by level via URL path ---
@blueprint.route("/courses/level/<level>")
def courses_by_level(level):
    """Filter courses by level via URL path (filter_by_route)."""
    courses = _courses()
    filtered = [c for c in courses if c["level"] == level]
    levels = sorted(set(c["level"] for c in courses))
    areas = sorted(set(c["research_area"] for c in courses if c.get("research_area")))
    return render_template(
        "university-academic/courses.html",
        courses=filtered,
        levels=levels,
        areas=areas,
        research_areas=_research_areas(),
        dept_filter="",
        level_filter=level,
        search_query="",
        checked_levels=[],
    )


# --- filter_by_route: filter courses by research area via URL path ---
@blueprint.route("/courses/area/<area>")
def courses_by_area(area):
    """Filter courses by research area via URL path (filter_by_route)."""
    courses = _courses()
    filtered = [c for c in courses if c.get("research_area") == area]
    levels = sorted(set(c["level"] for c in courses))
    areas = sorted(set(c["research_area"] for c in courses if c.get("research_area")))
    return render_template(
        "university-academic/courses.html",
        courses=filtered,
        levels=levels,
        areas=areas,
        research_areas=_research_areas(),
        dept_filter=area,
        level_filter="",
        search_query="",
        checked_levels=[],
    )


# --- search_by_route: search courses via URL path ---
@blueprint.route("/courses/search/<query>")
def courses_search_by_route(query):
    """Search courses via URL path (search_by_route)."""
    courses = _courses()
    q = query.lower()
    filtered = [c for c in courses
                 if q in c["title"].lower()
                 or q in c["code"].lower()
                 or q in c["description"].lower()]
    levels = sorted(set(c["level"] for c in courses))
    areas = sorted(set(c["research_area"] for c in courses if c.get("research_area")))
    return render_template(
        "university-academic/courses.html",
        courses=filtered,
        levels=levels,
        areas=areas,
        research_areas=_research_areas(),
        dept_filter="",
        level_filter="",
        search_query=query,
        checked_levels=[],
    )


@blueprint.route("/course/<course_id>")
def course_detail(course_id):
    """Single course detail page (navigate_by_route, extract_by_route)."""
    courses = _courses()
    course = next((c for c in courses if c["id"] == course_id), None)
    if not course:
        abort(404)
    # Find the instructor's faculty profile if it exists
    faculty = _faculty()
    instructor = next(
        (f for f in faculty if f["name"] == course.get("instructor")), None
    )
    return render_template(
        "university-academic/course_detail.html",
        course=course,
        instructor=instructor,
    )


@blueprint.route("/faculty")
def faculty_page():
    """Faculty directory with filtering (filter_by_dropdown, search_by_query)."""
    faculty = _faculty()
    search_query = request.args.get("q", "")
    area_filter = request.args.get("area", "")

    filtered = faculty
    if area_filter:
        filtered = [f for f in filtered if area_filter in f.get("research_areas", [])]
    if search_query:
        q = search_query.lower()
        filtered = [f for f in filtered
                     if q in f["name"].lower()
                     or q in f.get("title", "").lower()
                     or any(q in a.lower() for a in f.get("research_areas", []))]

    all_areas = sorted(set(
        a for f in faculty for a in f.get("research_areas", [])
    ))

    return render_template(
        "university-academic/faculty.html",
        faculty=filtered,
        all_areas=all_areas,
        search_query=search_query,
        area_filter=area_filter,
    )


@blueprint.route("/faculty/<faculty_id>")
def faculty_detail(faculty_id):
    """Single faculty profile page (extract_by_route)."""
    faculty = _faculty()
    member = next((f for f in faculty if f["id"] == faculty_id), None)
    if not member:
        abort(404)
    # Find courses taught by this faculty member
    courses = _courses()
    taught = [c for c in courses if c.get("instructor") == member["name"]]
    return render_template(
        "university-academic/faculty_detail.html",
        member=member,
        taught_courses=taught,
    )


@blueprint.route("/departments")
def departments_page():
    """List of research areas / departments (navigate_by_semantic, navigate_by_dropdown)."""
    dept_data = _departments()
    department = dept_data.get("department", {})
    research_areas = dept_data.get("research_areas", [])
    return render_template(
        "university-academic/departments.html",
        department=department,
        research_areas=research_areas,
    )


@blueprint.route("/department/<dept_id>")
def department_detail(dept_id):
    """Single research area detail page (navigate_by_route)."""
    dept_data = _departments()
    research_areas = dept_data.get("research_areas", [])
    area = next((a for a in research_areas if a["id"] == dept_id), None)
    if not area:
        # Also try matching by slug
        area = next((a for a in research_areas if a["slug"] == dept_id), None)
    if not area:
        abort(404)
    # Find faculty in this area
    faculty = _faculty()
    area_faculty = [
        f for f in faculty
        if area["slug"] in f.get("research_areas", [])
        or any(area["slug"] in ra for ra in f.get("research_areas", []))
    ]
    # Find courses in this area
    courses = _courses()
    area_courses = [c for c in courses if c.get("research_area") == area["slug"]]
    return render_template(
        "university-academic/department_detail.html",
        area=area,
        faculty=area_faculty,
        courses=area_courses,
        department=dept_data.get("department", {}),
    )


@blueprint.route("/events")
def events_page():
    """Events calendar with date filtering (filter_by_dropdown, extract_by_date_range)."""
    events = _events()
    date_filter = request.args.get("date", "")
    date_to = request.args.get("date_to", "")
    type_filter = request.args.get("type", "")
    search_query = request.args.get("q", "")

    filtered = events
    if date_filter:
        filtered = [e for e in filtered if e["date"] >= date_filter]
    if date_to:
        filtered = [e for e in filtered if e["date"] <= date_to]
    if type_filter:
        filtered = [e for e in filtered if e.get("type") == type_filter]
    if search_query:
        q = search_query.lower()
        filtered = [e for e in filtered
                     if q in e["title"].lower()
                     or q in e.get("description", "").lower()]

    filtered = sorted(filtered, key=lambda e: e["date"])
    event_types = sorted(set(e.get("type", "") for e in events if e.get("type")))

    return render_template(
        "university-academic/events.html",
        events=filtered,
        event_types=event_types,
        date_filter=date_filter,
        date_to=date_to,
        type_filter=type_filter,
        search_query=search_query,
    )


@blueprint.route("/event/<event_id>")
def event_detail(event_id):
    """Single event detail page (extract_by_route)."""
    events = _events()
    event = next((e for e in events if e["id"] == event_id), None)
    if not event:
        abort(404)
    return render_template(
        "university-academic/event_detail.html",
        event=event,
    )


@blueprint.route("/alumni")
def alumni_page():
    """Alumni network directory (search_by_query, filter_by_dropdown)."""
    alumni = _alumni()
    search_query = request.args.get("q", "")
    year_filter = request.args.get("year", "")

    filtered = alumni
    if year_filter:
        try:
            filtered = [a for a in filtered if a["graduation_year"] == int(year_filter)]
        except ValueError:
            pass
    if search_query:
        q = search_query.lower()
        filtered = [a for a in filtered
                     if q in a["name"].lower()
                     or q in a.get("degree", "").lower()
                     or q in a.get("current_position", {}).get("company", "").lower()]

    years = sorted(set(a["graduation_year"] for a in alumni), reverse=True)

    return render_template(
        "university-academic/alumni.html",
        alumni=filtered,
        years=years,
        search_query=search_query,
        year_filter=year_filter,
    )


# --- compare_from_table: compare courses side-by-side ---
@blueprint.route("/compare")
def compare_page():
    """Compare courses side-by-side (compare_from_table, extract_from_table)."""
    ids_str = request.args.get("ids", "")
    courses = _courses()
    selected = []
    if ids_str:
        ids = [x.strip() for x in ids_str.split(",") if x.strip()]
        selected = [c for c in courses if c["id"] in ids]
    return render_template(
        "university-academic/compare.html",
        courses=courses,
        selected=selected,
    )


# --- apply_by_form: submit an application form ---
@blueprint.route("/apply", methods=["GET"])
def apply_page():
    """Application form page (apply_by_form)."""
    courses = _courses()
    programs = _research_areas()
    return render_template(
        "university-academic/apply.html",
        courses=courses,
        programs=programs,
        success=False,
        error=None,
    )


@blueprint.route("/apply", methods=["POST"])
def apply_submit():
    """Handle application form submission (apply_by_form)."""
    name = request.form.get("applicant_name", "").strip()
    email = request.form.get("applicant_email", "").strip()
    program = request.form.get("program", "").strip()
    statement = request.form.get("statement", "").strip()

    if not name or not email or not program:
        courses = _courses()
        programs = _research_areas()
        return render_template(
            "university-academic/apply.html",
            courses=courses,
            programs=programs,
            success=False,
            error="Please fill in all required fields (name, email, program).",
        )

    # Store application in users.json under "applications"
    users = _load_users()
    # Find or create a general applications list
    app_entry = {
        "applicant_name": name,
        "applicant_email": email,
        "program": program,
        "statement": statement,
        "status": "submitted",
    }

    # Store in a special applications key for any logged-in user
    net_id = session.get("ua_user", "")
    if net_id:
        user = next((u for u in users if u["net_id"] == net_id), None)
        if user:
            apps = user.setdefault("applications", [])
            apps.append(app_entry)
            _save_users(users)

    courses = _courses()
    programs = _research_areas()
    return render_template(
        "university-academic/apply.html",
        courses=courses,
        programs=programs,
        success=True,
        error=None,
    )


# --- subscribe_by_toggle: toggle subscriptions ---
@blueprint.route("/subscribe", methods=["GET"])
def subscribe_page():
    """Subscription management page (subscribe_by_toggle)."""
    research_areas = _research_areas()
    net_id = session.get("ua_user", "")
    subscriptions = []
    if net_id:
        user = _get_user(net_id)
        if user:
            subscriptions = user.get("subscriptions", [])
    return render_template(
        "university-academic/subscribe.html",
        research_areas=research_areas,
        subscriptions=subscriptions,
        logged_in=bool(net_id),
    )


@blueprint.route("/subscribe/<area_slug>", methods=["POST"])
def subscribe_toggle(area_slug):
    """Toggle subscription to a research area (subscribe_by_toggle)."""
    net_id = session.get("ua_user", "")
    if not net_id:
        return redirect(url_for("university-academic.login_page"))

    users = _load_users()
    user = next((u for u in users if u["net_id"] == net_id), None)
    if not user:
        return redirect(url_for("university-academic.login_page"))

    subs = user.setdefault("subscriptions", [])
    if area_slug in subs:
        subs.remove(area_slug)
        action = "unsubscribed"
    else:
        subs.append(area_slug)
        action = "subscribed"
    _save_users(users)

    # If this is an API call, return JSON
    if request.headers.get("Accept") == "application/json":
        return jsonify({"action": action, "area": area_slug,
                        "subscriptions": subs})
    return redirect(url_for("university-academic.subscribe_page"))


# --- export_by_dropdown: export course/faculty data ---
@blueprint.route("/export")
def export_page():
    """Export page with format selection (export_by_dropdown)."""
    return render_template("university-academic/export.html")


@blueprint.route("/login", methods=["GET"])
def login_page():
    """Login page for student/faculty portal."""
    return render_template("university-academic/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    """Handle login form submission."""
    username = request.form.get("username", "")
    password = request.form.get("password", "")
    if not username or not password:
        return render_template(
            "university-academic/login.html",
            error="Please enter both username and password.",
        )
    # Auth against users.json
    users = _load_users()
    user = next((u for u in users if u["net_id"] == username), None)
    if user:
        session["ua_user"] = username
        return redirect(url_for("university-academic.index"))
    # Fallback: accept any non-empty credentials for demo
    session["ua_user"] = username
    return redirect(url_for("university-academic.index"))


@blueprint.route("/logout")
def logout():
    """Logout and redirect to home."""
    session.pop("ua_user", None)
    return redirect(url_for("university-academic.index"))


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/courses", methods=["GET"])
def api_courses():
    """GET courses with optional filters: dept, level, q (search), levels (checkbox)."""
    courses = _courses()
    dept = request.args.get("dept", "")
    level = request.args.get("level", "")
    q = request.args.get("q", "")
    checked_levels = request.args.getlist("levels")

    result = courses
    if dept:
        result = [c for c in result if c.get("research_area") == dept]
    if level:
        result = [c for c in result if c["level"] == level]
    if checked_levels:
        result = [c for c in result if c["level"] in checked_levels]
    if q:
        ql = q.lower()
        result = [c for c in result
                   if ql in c["title"].lower()
                   or ql in c["code"].lower()
                   or ql in c["description"].lower()]
    return jsonify(result)


@blueprint.route("/api/courses/<course_id>", methods=["GET"])
def api_course_detail(course_id):
    """GET single course by id (extract_by_route)."""
    courses = _courses()
    course = next((c for c in courses if c["id"] == course_id), None)
    if not course:
        abort(404)
    return jsonify(course)


@blueprint.route("/api/courses/search/<query>", methods=["GET"])
def api_courses_search_by_route(query):
    """Search courses via URL route (search_by_route)."""
    courses = _courses()
    q = query.lower()
    result = [c for c in courses
               if q in c["title"].lower()
               or q in c["code"].lower()
               or q in c["description"].lower()]
    return jsonify(result)


@blueprint.route("/api/courses/level/<level>", methods=["GET"])
def api_courses_by_level(level):
    """Filter courses by level via URL (filter_by_route)."""
    courses = _courses()
    return jsonify([c for c in courses if c["level"] == level])


@blueprint.route("/api/courses/area/<area>", methods=["GET"])
def api_courses_by_area(area):
    """Filter courses by research area via URL (filter_by_route)."""
    courses = _courses()
    return jsonify([c for c in courses if c.get("research_area") == area])


@blueprint.route("/api/faculty", methods=["GET"])
def api_faculty():
    """GET faculty with optional filters: area, q (search)."""
    faculty = _faculty()
    area = request.args.get("area", "")
    q = request.args.get("q", "")

    result = faculty
    if area:
        result = [f for f in result if area in f.get("research_areas", [])]
    if q:
        ql = q.lower()
        result = [f for f in result
                   if ql in f["name"].lower()
                   or ql in f.get("title", "").lower()
                   or any(ql in a.lower() for a in f.get("research_areas", []))]
    return jsonify(result)


@blueprint.route("/api/faculty/<faculty_id>", methods=["GET"])
def api_faculty_detail(faculty_id):
    """GET single faculty by id (extract_by_route)."""
    faculty = _faculty()
    member = next((f for f in faculty if f["id"] == faculty_id), None)
    if not member:
        abort(404)
    return jsonify(member)


@blueprint.route("/api/faculty/search", methods=["GET"])
def api_faculty_search():
    """Semantic search across faculty (search_by_semantic)."""
    q = request.args.get("q", "").strip()
    faculty = _faculty()
    if not q:
        return jsonify(faculty)
    scored = []
    for f in faculty:
        text = (f["name"] + " " + f.get("title", "") + " " +
                f.get("bio", "") + " " + " ".join(f.get("research_areas", [])))
        score = _keyword_score(q, text)
        if score > 0:
            scored.append((f, score))
    scored.sort(key=lambda x: -x[1])
    return jsonify([f for f, _ in scored])


@blueprint.route("/api/departments", methods=["GET"])
def api_departments():
    """GET department info and research areas."""
    return jsonify(_departments())


@blueprint.route("/api/departments/<dept_id>", methods=["GET"])
def api_department_detail(dept_id):
    """GET single research area by id or slug."""
    research_areas = _research_areas()
    area = next((a for a in research_areas if a["id"] == dept_id), None)
    if not area:
        area = next((a for a in research_areas if a["slug"] == dept_id), None)
    if not area:
        abort(404)
    return jsonify(area)


@blueprint.route("/api/events", methods=["GET"])
def api_events():
    """GET events with optional filters: date, date_to, type, q (extract_by_date_range)."""
    events = _events()
    date = request.args.get("date", "")
    date_to = request.args.get("date_to", "")
    etype = request.args.get("type", "")
    q = request.args.get("q", "")

    result = events
    if date:
        result = [e for e in result if e["date"] >= date]
    if date_to:
        result = [e for e in result if e["date"] <= date_to]
    if etype:
        result = [e for e in result if e.get("type") == etype]
    if q:
        ql = q.lower()
        result = [e for e in result
                   if ql in e["title"].lower()
                   or ql in e.get("description", "").lower()]
    return jsonify(sorted(result, key=lambda e: e["date"]))


@blueprint.route("/api/events/<event_id>", methods=["GET"])
def api_event_detail(event_id):
    """GET single event by id."""
    events = _events()
    event = next((e for e in events if e["id"] == event_id), None)
    if not event:
        abort(404)
    return jsonify(event)


@blueprint.route("/api/alumni", methods=["GET"])
def api_alumni():
    """GET alumni with optional filters: year, q."""
    alumni = _alumni()
    year = request.args.get("year", "")
    q = request.args.get("q", "")

    result = alumni
    if year:
        try:
            result = [a for a in result if a["graduation_year"] == int(year)]
        except ValueError:
            pass
    if q:
        ql = q.lower()
        result = [a for a in result
                   if ql in a["name"].lower()
                   or ql in a.get("degree", "").lower()
                   or ql in a.get("current_position", {}).get("company", "").lower()]
    return jsonify(result)


@blueprint.route("/api/stats", methods=["GET"])
def api_stats():
    """GET aggregate statistics about the department."""
    dept_data = _departments()
    department = dept_data.get("department", {})
    courses = _courses()
    faculty = _faculty()
    events = _events()
    alumni = _alumni()
    research_areas = dept_data.get("research_areas", [])

    level_counts = {}
    for c in courses:
        lvl = c["level"]
        level_counts[lvl] = level_counts.get(lvl, 0) + 1

    return jsonify({
        "department_name": department.get("name", ""),
        "university": department.get("university", ""),
        "total_courses": len(courses),
        "courses_by_level": level_counts,
        "total_faculty": len(faculty),
        "total_events": len(events),
        "total_alumni": len(alumni),
        "research_areas_count": len(research_areas),
        "undergraduate_students": department.get("undergraduate_students", 0),
        "graduate_students": department.get("graduate_students", 0),
        "total_publications": sum(f.get("publications_count", 0) for f in faculty),
    })


# --- compare_from_table API ---
@blueprint.route("/api/compare", methods=["GET"])
def api_compare():
    """Compare courses by IDs (compare_from_table)."""
    ids_str = request.args.get("ids", "")
    ids = [x.strip() for x in ids_str.split(",") if x.strip()]
    courses = _courses()
    return jsonify([c for c in courses if c["id"] in ids])


# --- export_by_dropdown API ---
@blueprint.route("/api/export", methods=["GET"])
def api_export():
    """Export courses or faculty data as CSV or JSON (export_by_dropdown)."""
    fmt = request.args.get("format", "json").lower()
    data_type = request.args.get("type", "courses").lower()

    if data_type == "faculty":
        records = _faculty()
        if fmt == "csv":
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(["id", "name", "title", "email", "office",
                             "research_areas", "publications_count", "joined_year"])
            for f in records:
                writer.writerow([
                    f["id"], f["name"], f["title"], f["email"],
                    f["office"], "; ".join(f.get("research_areas", [])),
                    f.get("publications_count", 0), f.get("joined_year", ""),
                ])
            return Response(buf.getvalue(), mimetype="text/csv",
                            headers={"Content-Disposition": "attachment; filename=faculty.csv"})
        return jsonify(records)
    else:
        records = _courses()
        dept = request.args.get("dept", "")
        level = request.args.get("level", "")
        if dept:
            records = [c for c in records if c.get("research_area") == dept]
        if level:
            records = [c for c in records if c["level"] == level]
        if fmt == "csv":
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(["id", "code", "title", "credits", "level",
                             "instructor", "research_area", "max_enrollment"])
            for c in records:
                writer.writerow([
                    c["id"], c["code"], c["title"], c["credits"],
                    c["level"], c["instructor"],
                    c.get("research_area", ""), c.get("max_enrollment", ""),
                ])
            return Response(buf.getvalue(), mimetype="text/csv",
                            headers={"Content-Disposition": "attachment; filename=courses.csv"})
        return jsonify(records)


# --- submit_by_query: submit a question/feedback ---
@blueprint.route("/api/submit", methods=["POST"])
def api_submit():
    """Submit a question or feedback (submit_by_query)."""
    data = request.get_json(silent=True) or {}
    subject = data.get("subject", "").strip()
    message = data.get("message", "").strip()
    sender = data.get("sender", "").strip()

    if not subject or not message:
        return jsonify({"error": "subject and message required"}), 400

    return jsonify({
        "status": "submitted",
        "subject": subject,
        "sender": sender,
        "message_length": len(message),
    })


@blueprint.route("/contact", methods=["GET"])
def contact_page():
    """Contact / submit question page (submit_by_query)."""
    return render_template("university-academic/contact.html",
                           success=False, error=None)


@blueprint.route("/contact", methods=["POST"])
def contact_submit():
    """Handle contact form submission (submit_by_query)."""
    subject = request.form.get("subject", "").strip()
    message = request.form.get("message", "").strip()
    sender = request.form.get("sender_email", "").strip()

    if not subject or not message:
        return render_template("university-academic/contact.html",
                               success=False,
                               error="Please fill in subject and message.")
    return render_template("university-academic/contact.html",
                           success=True, error=None)


# --- subscribe_by_toggle API ---
@blueprint.route("/api/subscribe/<area_slug>", methods=["POST"])
def api_subscribe_toggle(area_slug):
    """Toggle subscription via API (subscribe_by_toggle)."""
    net_id = session.get("ua_user", "")
    if not net_id:
        return jsonify({"error": "Login required"}), 401

    users = _load_users()
    user = next((u for u in users if u["net_id"] == net_id), None)
    if not user:
        return jsonify({"error": "User not found"}), 404

    subs = user.setdefault("subscriptions", [])
    if area_slug in subs:
        subs.remove(area_slug)
        action = "unsubscribed"
    else:
        subs.append(area_slug)
        action = "subscribed"
    _save_users(users)
    return jsonify({"action": action, "area": area_slug, "subscriptions": subs})


# --- apply_by_form API ---
@blueprint.route("/api/apply", methods=["POST"])
def api_apply():
    """Submit application via API (apply_by_form)."""
    data = request.get_json(silent=True) or {}
    name = data.get("applicant_name", "").strip()
    email = data.get("applicant_email", "").strip()
    program = data.get("program", "").strip()
    statement = data.get("statement", "").strip()

    if not name or not email or not program:
        return jsonify({"error": "applicant_name, applicant_email, and program required"}), 400

    net_id = session.get("ua_user", "")
    if net_id:
        users = _load_users()
        user = next((u for u in users if u["net_id"] == net_id), None)
        if user:
            apps = user.setdefault("applications", [])
            apps.append({
                "applicant_name": name,
                "applicant_email": email,
                "program": program,
                "statement": statement,
                "status": "submitted",
            })
            _save_users(users)

    return jsonify({
        "status": "submitted",
        "applicant_name": name,
        "program": program,
    })


# --- API login / user endpoints ---
@blueprint.route("/api/login", methods=["POST"])
def api_login():
    """Login via API."""
    data = request.get_json(silent=True) or {}
    net_id = data.get("net_id", "").strip()
    users = _load_users()
    user = next((u for u in users if u["net_id"] == net_id), None)
    if not user:
        return jsonify({"error": "Invalid NetID"}), 401
    session["ua_user"] = net_id
    return jsonify({"net_id": net_id, "display_name": user["display_name"],
                    "role": user["role"]})


@blueprint.route("/api/users/<net_id>", methods=["GET"])
def api_user(net_id):
    """GET user by net_id."""
    user = _get_user(net_id)
    if not user:
        abort(404)
    return jsonify(user)
