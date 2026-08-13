"""Calendar Todo — Google Calendar-style productivity app.

Reads config/config.json for simulated_today. Synthesized event data with
multiple users, categories (work/personal/health), recurring events, and
shared calendars.
"""
import json
import pathlib
from collections import Counter
from datetime import datetime, timedelta

from flask import Blueprint, Response, abort, jsonify, redirect, render_template, request, session, url_for

from app import db
from app.events import emit
from app.handlers.email_handler import _add_email
from helpers.security import safe_next

SITE = "calendar-todo"
SITE_DIR = pathlib.Path(__file__).resolve().parent
CONFIG_FILE = SITE_DIR / "config" / "config.json"

blueprint = Blueprint(
    "calendar-todo",
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


def _simulated_today():
    cfg = _load_config()
    return cfg.get("simulated_today", "2026-06-21")


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _normalize_events(events):
    """Map DB column 'end_' back to 'end' (reserved word escaping) and
    default text fields to empty strings. Must be applied to EVERY read
    path (db.query and db.search) before events reach templates."""
    for e in events:
        if "end_" in e and "end" not in e:
            e["end"] = e.pop("end_")
        for field in ("start", "end", "title", "description", "category",
                       "calendar", "location", "priority", "status", "color"):
            if e.get(field) is None:
                e[field] = ""
    return events


def _search_events(q, where=None, limit=200):
    return _normalize_events(db.search(SITE, "events", q, where=where, limit=limit))


def _load_events(user_id=None, category=None, status=None):
    where = {}
    if user_id is not None:
        where["user_id"] = user_id
    if category:
        where["category"] = category
    if status:
        where["status"] = status
    events = db.query(SITE, "events", where=where if where else None)
    return _normalize_events(events)


def _save_events(events):
    db.save_collection(SITE, "events", events)


def _load_users():
    return db.query(SITE, "users")


def _save_users(users):
    db.save_collection(SITE, "users", users)


def _get_user(user_id):
    return db.get_item(SITE, "users", user_id)


def _next_event_id():
    return db.next_id(SITE, "events")


def _next_user_id():
    return db.next_id(SITE, "users")


def _safe_next(value):
    return safe_next(value)


def _require_login():
    """Return a redirect to the login page (preserving the target as `next`)
    when no user is logged in, else None."""
    if "user_id" not in session:
        target = request.full_path
        if target.endswith("?"):
            target = target[:-1]
        return redirect(url_for("calendar-todo.login_page", next=target))
    return None


# ---------------------------------------------------------------------------
# Search / filter helpers
# ---------------------------------------------------------------------------


def _parse_date(s):
    """Parse a date string (YYYY-MM-DD) to a date object."""
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _event_date(event):
    """Extract date from event start."""
    try:
        return datetime.fromisoformat(event["start"]).date()
    except (ValueError, TypeError, KeyError):
        return None


def _filter_events(events, user_id=None, category=None, calendar=None,
                   date_from=None, date_to=None, priority=None, status=None):
    results = list(events)
    if user_id is not None:
        results = [e for e in results if e["user_id"] == user_id]
    if category:
        results = [e for e in results if e.get("category", "").lower() == category.lower()]
    if calendar:
        results = [e for e in results if e.get("calendar", "").lower() == calendar.lower()]
    if date_from:
        d = _parse_date(date_from)
        if d:
            results = [e for e in results if _event_date(e) and _event_date(e) >= d]
    if date_to:
        d = _parse_date(date_to)
        if d:
            results = [e for e in results if _event_date(e) and _event_date(e) <= d]
    if priority:
        results = [e for e in results if e.get("priority", "").lower() == priority.lower()]
    if status:
        results = [e for e in results if e.get("status", "").lower() == status.lower()]
    return results


def _sort_events(events, sort_key="date"):
    if sort_key == "date":
        events.sort(key=lambda e: e.get("start", ""))
    elif sort_key == "title":
        events.sort(key=lambda e: e.get("title", "").lower())
    elif sort_key == "priority":
        prio_order = {"high": 0, "medium": 1, "low": 2}
        events.sort(key=lambda e: prio_order.get(e.get("priority", "low"), 3))
    elif sort_key == "created":
        events.sort(key=lambda e: e.get("created_at", ""), reverse=True)
    return events


# ---------------------------------------------------------------------------
# Week / month date helpers
# ---------------------------------------------------------------------------

def _week_range(date_str):
    """Return (start, end) for the week containing date_str (Monday-based)."""
    d = _parse_date(date_str)
    if not d:
        d = _parse_date(_simulated_today())
    start = d - timedelta(days=d.weekday())  # Monday
    end = start + timedelta(days=6)  # Sunday
    return start, end


def _month_range(year, month):
    """Return (start, end) for a given month."""
    start = datetime(year, month, 1).date()
    if month == 12:
        end = datetime(year + 1, 1, 1).date() - timedelta(days=1)
    else:
        end = datetime(year, month + 1, 1).date() - timedelta(days=1)
    return start, end


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    """Main calendar view — defaults to week view of simulated today."""
    gate = _require_login()
    if gate:
        return gate
    today = _simulated_today()
    events = _load_events()
    users = _load_users()
    categories = sorted(set(e.get("category", "") for e in events))
    calendars = sorted(set(e.get("calendar", "") for e in events))

    view = request.args.get("view", "week")
    q = request.args.get("q", "").strip()
    cat = request.args.get("category", "").strip()
    cal = request.args.get("calendar", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    sort = request.args.get("sort", "date").strip()
    priority = request.args.get("priority", "").strip()
    uid = request.args.get("user_id", type=int)
    week_offset = request.args.get("week_offset", 0, type=int)

    if q:
        where = {}
        if uid:
            where["user_id"] = uid
        if cat:
            where["category"] = cat
        if cal:
            where["calendar"] = cal
        if priority:
            where["priority"] = priority
        results = _search_events(q, where=where if where else None)
    else:
        results = list(events)
        if uid:
            results = [e for e in results if e["user_id"] == uid]
        if cat:
            results = [e for e in results if e.get("category", "").lower() == cat.lower()]
        if cal:
            results = [e for e in results if e.get("calendar", "").lower() == cal.lower()]
        if priority:
            results = [e for e in results if e.get("priority", "").lower() == priority.lower()]

    # Compute week start/end based on week_offset from simulated_today
    today_d = _parse_date(today)
    offset_date = today_d + timedelta(weeks=week_offset)
    ws, we = _week_range(offset_date.isoformat())

    # Default date range based on view
    if not date_from and not date_to:
        if view == "week":
            date_from = ws.isoformat()
            date_to = we.isoformat()
        elif view == "day":
            date_from = today
            date_to = today
        # month: show all

    if date_from:
        d = _parse_date(date_from)
        if d:
            results = [e for e in results if _event_date(e) and _event_date(e) >= d]
    if date_to:
        d = _parse_date(date_to)
        if d:
            results = [e for e in results if _event_date(e) and _event_date(e) <= d]

    results = _sort_events(results, sort)

    # Build structured week days for the grid
    week_days = []
    for i in range(7):
        day = ws + timedelta(days=i)
        day_iso = day.isoformat()
        day_evts = [e for e in results if _event_date(e) == day]
        week_days.append({
            "date": day_iso,
            "weekday": day.strftime("%A"),
            "weekday_short": day.strftime("%a").upper(),
            "day_num": day.day,
            "is_today": day_iso == today,
            "events": day_evts,
        })

    # Build mini-calendar month data
    # Show the month that contains the week start
    mini_cal_year = ws.year
    mini_cal_month = ws.month
    mc_start, mc_end = _month_range(mini_cal_year, mini_cal_month)
    # Pad to start on Monday
    mc_first_weekday = mc_start.weekday()  # 0=Mon
    mc_days = []
    for i in range(-mc_first_weekday, (mc_end - mc_start).days + 1):
        d = mc_start + timedelta(days=i)
        mc_days.append({
            "date": d.isoformat(),
            "day_num": d.day,
            "in_month": d.month == mini_cal_month,
            "is_today": d.isoformat() == today,
            "in_week": ws <= d <= we,
        })
    # Pad end to complete last week row
    while len(mc_days) % 7 != 0:
        d = mc_start + timedelta(days=len(mc_days) - mc_first_weekday)
        mc_days.append({
            "date": d.isoformat(),
            "day_num": d.day,
            "in_month": False,
            "is_today": False,
            "in_week": ws <= d <= we,
        })

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template("calendar-todo/index.html",
                           events=results, categories=categories,
                           calendars=calendars, users=users,
                           q=q, cat=cat, cal=cal,
                           date_from=date_from, date_to=date_to,
                           sort=sort, priority=priority, uid=uid,
                           view=view, today=today, user=user,
                           week_offset=week_offset,
                           week_start=ws.isoformat(),
                           week_end=we.isoformat(),
                           week_days=week_days,
                           mini_cal_days=mc_days,
                           mini_cal_month=datetime(mini_cal_year, mini_cal_month, 1).strftime("%B %Y"))


@blueprint.route("/day/<date_str>")
def day_view(date_str):
    gate = _require_login()
    if gate:
        return gate
    events = _load_events()
    d = _parse_date(date_str)
    if not d:
        abort(400)
    day_events = [e for e in events if _event_date(e) == d]
    day_events = _sort_events(day_events, "date")
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("calendar-todo/day.html",
                           events=day_events, date=date_str, user=user,
                           today=_simulated_today())


@blueprint.route("/week/<date_str>")
def week_view(date_str):
    gate = _require_login()
    if gate:
        return gate
    events = _load_events()
    ws, we = _week_range(date_str)
    week_events = [e for e in events if _event_date(e) and ws <= _event_date(e) <= we]
    week_events = _sort_events(week_events, "date")
    days = []
    for i in range(7):
        day = ws + timedelta(days=i)
        day_evts = [e for e in week_events if _event_date(e) == day]
        days.append({"date": day.isoformat(), "weekday": day.strftime("%A"), "events": day_evts})
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("calendar-todo/week.html",
                           days=days, week_start=ws.isoformat(),
                           week_end=we.isoformat(), user=user,
                           today=_simulated_today())


@blueprint.route("/event/<int:event_id>")
def event_detail(event_id):
    gate = _require_login()
    if gate:
        return gate
    events = _load_events()
    event = next((e for e in events if e["id"] == event_id), None)
    if event is None:
        abort(404)
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    owner = _get_user(event["user_id"])
    return render_template("calendar-todo/event.html",
                           event=event, owner=owner, user=user,
                           today=_simulated_today())


@blueprint.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return render_template("calendar-todo/login.html", error=None, next="")
    user = _get_user(session["user_id"])
    if not user:
        return render_template("calendar-todo/login.html", error=None, next="")
    events = _load_events()
    my_events = [e for e in events if e["user_id"] == user["id"]]
    my_events = _sort_events(my_events, "date")
    today = _simulated_today()
    today_d = _parse_date(today)
    upcoming = [e for e in my_events if _event_date(e) and _event_date(e) >= today_d]
    return render_template("calendar-todo/dashboard.html", user=user,
                           events=my_events, upcoming=upcoming,
                           today=today)


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("calendar-todo/login.html", error=None,
                           next=request.args.get("next", ""))


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    nxt = request.form.get("next", "")
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return render_template("calendar-todo/login.html",
                               error="Invalid username or password", next=nxt)
    session["user_id"] = user["id"]
    return redirect(_safe_next(nxt) or url_for("calendar-todo.dashboard"))


@blueprint.route("/register", methods=["GET"])
def register_page():
    return render_template("calendar-todo/register.html", error=None,
                           next=request.args.get("next", ""))


@blueprint.route("/register", methods=["POST"])
def register_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    email = request.form.get("email", "").strip()
    name = request.form.get("name", "").strip()
    nxt = request.form.get("next", "")
    if not username or not password or not email:
        return render_template("calendar-todo/register.html",
                               error="All fields are required", next=nxt)
    # users table is small (<20 rows)
    users = _load_users()
    if any(u["username"] == username for u in users):
        return render_template("calendar-todo/register.html",
                               error="Username already taken", next=nxt)
    new_id = _next_user_id()
    new_user = {
        "id": new_id,
        "root_user_id": 0,
        "username": username,
        "password": password,
        "name": name or username,
        "email": email,
        "calendars": ["Work", "Personal", "Health"],
        "shared_calendars": [],
        "settings": {"default_view": "week", "timezone": "America/Los_Angeles",
                     "week_start": "monday"},
        "avatar": "",
    }
    db.save_item(SITE, "users", new_id, new_user)
    emit("signup", user_id=new_id, site_name=SITE,
         username=username, password=password, email=email)
    session["user_id"] = new_id
    return redirect(_safe_next(nxt) or url_for("calendar-todo.dashboard"))


# ---------------------------------------------------------------------------
# HTML form routes — create / edit / delete / toggle (non-JS fallback)
# ---------------------------------------------------------------------------

@blueprint.route("/create", methods=["POST"])
def form_create_event():
    """Create event via HTML form POST, then redirect back."""
    title = request.form.get("title", "").strip()
    if not title:
        return "Title is required", 400
    user_id = request.form.get("user_id", type=int)
    if user_id is None:
        return "User ID is required", 400

    # Parse invited attendees (comma-separated names/emails).
    attendees = [a.strip() for a in request.form.get("attendees", "").split(",")
                 if a.strip()]

    event = {
        "id": _next_event_id(),
        "user_id": user_id,
        "title": title,
        "description": request.form.get("description", ""),
        "category": request.form.get("category", "work"),
        "calendar": request.form.get("calendar", "Work"),
        "start": request.form.get("start", ""),
        "end": request.form.get("end", ""),
        "all_day": request.form.get("all_day") == "on",
        "location": request.form.get("location", ""),
        "recurring": request.form.get("recurring") or None,
        # type=int returns the default (not a crash) when the field is missing,
        # empty, or non-numeric — agents often submit an empty reminder field.
        "reminder_minutes": request.form.get("reminder_minutes", 15, type=int) or 15,
        "priority": request.form.get("priority", "medium"),
        "status": "confirmed",
        "attendees": attendees,
        "color": request.form.get("color", "#4285f4"),
        "created_at": datetime.now().isoformat(),
    }
    events = _load_events()
    events.append(event)
    _save_events(events)
    _add_email(user_id, "noreply@calendar-todo.lakeport.local",
               "New event created",
               f'Your event "{title}" has been created and added to your calendar.')
    return redirect(url_for("calendar-todo.index"))


@blueprint.route("/event/<int:event_id>/edit", methods=["GET"])
def event_edit_page(event_id):
    events = _load_events()
    event = next((e for e in events if e["id"] == event_id), None)
    if event is None:
        abort(404)
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    users = _load_users()
    categories = sorted(set(e.get("category", "") for e in events))
    calendars = sorted(set(e.get("calendar", "") for e in events))
    return render_template("calendar-todo/edit.html",
                           event=event, user=user, users=users,
                           categories=categories, calendars=calendars,
                           today=_simulated_today())


@blueprint.route("/event/<int:event_id>/edit", methods=["POST"])
def form_edit_event(event_id):
    """Edit event via HTML form POST, then redirect back."""
    events = _load_events()
    event = next((e for e in events if e["id"] == event_id), None)
    if event is None:
        abort(404)

    for field in ["title", "description", "category", "calendar", "start", "end",
                  "location", "priority", "status"]:
        val = request.form.get(field)
        if val is not None:
            event[field] = val

    _save_events(events)
    return redirect(url_for("calendar-todo.event_detail", event_id=event_id))


@blueprint.route("/event/<int:event_id>/delete", methods=["POST"])
def form_delete_event(event_id):
    """Delete event via HTML form POST, then redirect to index."""
    events = _load_events()
    event = next((e for e in events if e["id"] == event_id), None)
    if event is None:
        abort(404)
    events = [e for e in events if e["id"] != event_id]
    _save_events(events)
    return redirect(url_for("calendar-todo.index"))


@blueprint.route("/event/<int:event_id>/toggle", methods=["POST"])
def form_toggle_event(event_id):
    """Toggle event status via HTML form POST, then redirect back."""
    events = _load_events()
    event = next((e for e in events if e["id"] == event_id), None)
    if event is None:
        abort(404)
    event["status"] = "cancelled" if event["status"] == "confirmed" else "confirmed"
    _save_events(events)
    return redirect(url_for("calendar-todo.event_detail", event_id=event_id))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return render_template("calendar-todo/login.html", error=None, next="")


# ---------------------------------------------------------------------------
# API routes — read
# ---------------------------------------------------------------------------

@blueprint.route("/api/events")
def api_events():
    events = _load_events()
    q = request.args.get("q", "").strip()
    user_id = request.args.get("user_id", type=int)
    category = request.args.get("category", "").strip()
    calendar = request.args.get("calendar", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    priority = request.args.get("priority", "").strip()
    sort = request.args.get("sort", "date").strip()
    limit = request.args.get("limit", type=int)

    if q:
        where = {}
        if user_id:
            where["user_id"] = user_id
        if category:
            where["category"] = category
        if calendar:
            where["calendar"] = calendar
        if priority:
            where["priority"] = priority
        results = _search_events(q, where=where if where else None)
        # Apply date filters that FTS doesn't handle
        results = _filter_events(results, date_from=date_from, date_to=date_to)
    else:
        results = list(events)
        results = _filter_events(results, user_id=user_id, category=category,
                                 calendar=calendar, date_from=date_from,
                                 date_to=date_to, priority=priority)
    results = _sort_events(results, sort)
    if limit:
        results = results[:limit]
    return jsonify(results)


@blueprint.route("/api/events/search")
def api_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    results = _search_events(q, limit=50)
    return jsonify(results)


@blueprint.route("/api/events/<int:event_id>")
def api_event(event_id):
    events = _load_events()
    event = next((e for e in events if e["id"] == event_id), None)
    if event is None:
        abort(404)
    return jsonify(event)


@blueprint.route("/api/events/date/<date_str>")
def api_events_by_date(date_str):
    events = _load_events()
    d = _parse_date(date_str)
    if not d:
        return jsonify([])
    return jsonify([e for e in events if _event_date(e) == d])


@blueprint.route("/api/events/range")
def api_events_range():
    events = _load_events()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    user_id = request.args.get("user_id", type=int)
    results = _filter_events(events, user_id=user_id, date_from=date_from, date_to=date_to)
    results = _sort_events(results, "date")
    return jsonify(results)


@blueprint.route("/api/categories")
def api_categories():
    events = _load_events()
    counts = Counter(e.get("category", "unknown") for e in events)
    return jsonify([{"name": c, "count": n} for c, n in sorted(counts.items())])


@blueprint.route("/api/categories/<cat_name>/events")
def api_category_events(cat_name):
    events = _load_events()
    return jsonify([e for e in events if e.get("category", "").lower() == cat_name.lower()])


@blueprint.route("/api/categories/<cat_name>/stats")
def api_category_stats(cat_name):
    events = _load_events()
    filtered = [e for e in events if e.get("category", "").lower() == cat_name.lower()]
    if not filtered:
        return jsonify({"category": cat_name, "count": 0})
    dates = [_event_date(e) for e in filtered if _event_date(e)]
    users = set(e["user_id"] for e in filtered)
    return jsonify({
        "category": cat_name,
        "count": len(filtered),
        "earliest_date": min(dates).isoformat() if dates else None,
        "latest_date": max(dates).isoformat() if dates else None,
        "unique_users": len(users),
    })


@blueprint.route("/api/calendars")
def api_calendars():
    events = _load_events()
    counts = Counter(e.get("calendar", "Default") for e in events)
    return jsonify([{"name": c, "count": n} for c, n in sorted(counts.items())])


@blueprint.route("/api/stats")
def api_stats():
    events = _load_events()
    category = request.args.get("category", "").strip()
    user_id = request.args.get("user_id", type=int)
    if category:
        events = [e for e in events if e.get("category", "").lower() == category.lower()]
    if user_id:
        events = [e for e in events if e["user_id"] == user_id]
    if not events:
        return jsonify({"count": 0})
    dates = [_event_date(e) for e in events if _event_date(e)]
    recurring_count = sum(1 for e in events if e.get("recurring"))
    return jsonify({
        "count": len(events),
        "earliest_date": min(dates).isoformat() if dates else None,
        "latest_date": max(dates).isoformat() if dates else None,
        "recurring_count": recurring_count,
        "categories": dict(Counter(e.get("category", "unknown") for e in events).most_common()),
        "priorities": dict(Counter(e.get("priority", "medium") for e in events).most_common()),
        "unique_users": len(set(e["user_id"] for e in events)),
    })


@blueprint.route("/api/users")
def api_users():
    users = _load_users()
    return jsonify([{k: v for k, v in u.items() if k != "password"} for u in users])


@blueprint.route("/api/users/<int:user_id>")
def api_user(user_id):
    user = _get_user(user_id)
    if not user:
        abort(404)
    return jsonify({k: v for k, v in user.items() if k != "password"})


@blueprint.route("/api/users/<int:user_id>/events")
def api_user_events(user_id):
    events = _load_events()
    user_events = [e for e in events if e["user_id"] == user_id]
    sort = request.args.get("sort", "date")
    return jsonify(_sort_events(user_events, sort))


# ---------------------------------------------------------------------------
# API routes — authentication
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
    return jsonify({"user_id": user["id"], "username": user["username"]})


# ---------------------------------------------------------------------------
# API routes — create / edit / delete events
# ---------------------------------------------------------------------------

@blueprint.route("/api/events", methods=["POST"])
def api_create_event():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title required"}), 400
    user_id = data.get("user_id")
    if user_id is None:
        return jsonify({"error": "user_id required"}), 400

    event = {
        "id": _next_event_id(),
        "user_id": user_id,
        "title": title,
        "description": data.get("description", ""),
        "category": data.get("category", "work"),
        "calendar": data.get("calendar", "Work"),
        "start": data.get("start", ""),
        "end": data.get("end", ""),
        "all_day": data.get("all_day", False),
        "location": data.get("location", ""),
        "recurring": data.get("recurring", None),
        "reminder_minutes": data.get("reminder_minutes", 15),
        "priority": data.get("priority", "medium"),
        "status": data.get("status", "confirmed"),
        "attendees": data.get("attendees", []),
        "color": data.get("color", "#4285f4"),
        "created_at": datetime.now().isoformat(),
    }
    events = _load_events()
    events.append(event)
    _save_events(events)
    return jsonify(event), 201


@blueprint.route("/api/events/<int:event_id>", methods=["PUT"])
def api_update_event(event_id):
    data = request.get_json(silent=True) or {}
    events = _load_events()
    event = next((e for e in events if e["id"] == event_id), None)
    if event is None:
        abort(404)

    for field in ["title", "description", "category", "calendar", "start", "end",
                  "all_day", "location", "recurring", "reminder_minutes", "priority",
                  "status", "attendees", "color"]:
        if field in data:
            event[field] = data[field]

    _save_events(events)
    return jsonify(event)


@blueprint.route("/api/events/<int:event_id>", methods=["DELETE"])
def api_delete_event(event_id):
    events = _load_events()
    event = next((e for e in events if e["id"] == event_id), None)
    if event is None:
        abort(404)
    events = [e for e in events if e["id"] != event_id]
    _save_events(events)
    return jsonify({"deleted": event_id, "remaining": len(events)})


# ---------------------------------------------------------------------------
# API routes — sharing / inviting
# ---------------------------------------------------------------------------

@blueprint.route("/api/events/<int:event_id>/share", methods=["POST"])
def api_share_event(event_id):
    """Share an event to another user's shared_calendars."""
    data = request.get_json(silent=True) or {}
    target_user_id = data.get("target_user_id")
    if target_user_id is None:
        return jsonify({"error": "target_user_id required"}), 400

    events = _load_events()
    event = next((e for e in events if e["id"] == event_id), None)
    if event is None:
        abort(404)

    users = _load_users()
    target = next((u for u in users if u["id"] == target_user_id), None)
    if not target:
        abort(404)

    shared = target.setdefault("shared_calendars", [])
    entry = {"event_id": event_id, "from_user_id": event["user_id"]}
    if entry not in shared:
        shared.append(entry)
        _save_users(users)
        return jsonify({"action": "shared", "event_id": event_id, "target_user_id": target_user_id})
    return jsonify({"action": "already_shared", "event_id": event_id, "target_user_id": target_user_id})


@blueprint.route("/api/events/<int:event_id>/invite", methods=["POST"])
def api_invite_to_event(event_id):
    """Invite a user (by email) to an event."""
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip()
    if not email:
        return jsonify({"error": "email required"}), 400

    events = _load_events()
    event = next((e for e in events if e["id"] == event_id), None)
    if event is None:
        abort(404)

    attendees = event.setdefault("attendees", [])
    if email in attendees:
        return jsonify({"action": "already_invited", "event_id": event_id, "email": email})
    attendees.append(email)
    _save_events(events)
    return jsonify({"action": "invited", "event_id": event_id, "email": email,
                    "total_attendees": len(attendees)})


# ---------------------------------------------------------------------------
# API routes — toggle / status
# ---------------------------------------------------------------------------

@blueprint.route("/api/events/<int:event_id>/toggle", methods=["POST"])
def api_toggle_event(event_id):
    """Toggle event status between confirmed/cancelled."""
    events = _load_events()
    event = next((e for e in events if e["id"] == event_id), None)
    if event is None:
        abort(404)
    if event["status"] == "confirmed":
        event["status"] = "cancelled"
        action = "cancelled"
    else:
        event["status"] = "confirmed"
        action = "confirmed"
    _save_events(events)
    return jsonify({"action": action, "event_id": event_id, "status": event["status"]})


# ---------------------------------------------------------------------------
# API routes — export
# ---------------------------------------------------------------------------

@blueprint.route("/api/export")
def api_export():
    fmt = request.args.get("format", "json").lower()
    category = request.args.get("category", "").strip()
    user_id = request.args.get("user_id", type=int)
    events = _load_events()
    if category:
        events = [e for e in events if e.get("category", "").lower() == category.lower()]
    if user_id:
        events = [e for e in events if e["user_id"] == user_id]

    if fmt == "csv":
        lines = ["id,user_id,title,category,calendar,start,end,priority,status,location,recurring"]
        for e in events:
            title = e["title"].replace('"', '""')
            loc = e.get("location", "").replace('"', '""')
            lines.append(
                f'{e["id"]},{e["user_id"]},"{title}","{e.get("category","")}","{e.get("calendar","")}","{e["start"]}","{e["end"]}","{e.get("priority","")}","{e.get("status","")}","{loc}","{e.get("recurring","")}"'
            )
        return Response("\n".join(lines), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=events.csv"})
    elif fmt == "ics":
        ics_lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//CalendarTodo//EN"]
        for e in events:
            ics_lines.append("BEGIN:VEVENT")
            ics_lines.append(f"UID:{e['id']}@calendartodo")
            ics_lines.append(f"SUMMARY:{e['title']}")
            start_dt = e["start"].replace("-", "").replace(":", "").replace("T", "T")
            end_dt = e["end"].replace("-", "").replace(":", "").replace("T", "T")
            ics_lines.append(f"DTSTART:{start_dt}")
            ics_lines.append(f"DTEND:{end_dt}")
            ics_lines.append(f"LOCATION:{e.get('location', '')}")
            ics_lines.append(f"DESCRIPTION:{e.get('description', '')}")
            ics_lines.append("END:VEVENT")
        ics_lines.append("END:VCALENDAR")
        return Response("\n".join(ics_lines), mimetype="text/calendar",
                        headers={"Content-Disposition": "attachment; filename=events.ics"})
    return jsonify(events)
