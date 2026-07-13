"""CallHub -- remote video/audio calling platform (Zoom / Teams style).

Serves meetings, recordings, call logs, and user profiles from JSON data
files in the data_sources directory.
"""
import csv
import io
import json
import pathlib
import random
import uuid
from datetime import datetime, timedelta

from flask import (
    Blueprint, Response, abort, jsonify, redirect, render_template, request,
    session, url_for,
)
from app import db
from app.db import _deserialize_row

SITE = "remote-calls"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "remote-calls",
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


def _load_meetings():
    return db.query(SITE, "meetings")


def _load_recordings():
    return db.query(SITE, "recordings")


def _load_call_log():
    return db.query(SITE, "call_log")


def _get_user(root_user_id):
    """Find user by root_user_id (the session user_id from auto-login)."""
    results = db.query(SITE, "users", where={"root_user_id": root_user_id}, limit=1)
    return results[0] if results else None


def _get_user_by_id(user_id):
    """Find user by their rc-u-XXX id."""
    return db.get_item(SITE, "users", user_id)


def _build_user_map():
    """Return {user_id: display_name} for quick lookups."""
    return {u["id"]: u["display_name"] for u in _load_users()}


def _current_user():
    """Get the currently logged-in user, or None."""
    uid = session.get("user_id")
    if uid is None:
        return None
    return _get_user(uid)


def _require_login():
    user = _current_user()
    if not user:
        return None, redirect(url_for("remote-calls.login_page"))
    return user, None


def _parse_dt(dt_str):
    """Parse ISO datetime string, handling timezone offsets."""
    try:
        # Handle timezone offset format like 2026-06-23T09:00:00-07:00
        if "+" in dt_str[10:] or dt_str.count("-") > 2:
            # Strip timezone for naive comparison
            base = dt_str[:19]
            return datetime.fromisoformat(base)
        return datetime.fromisoformat(dt_str)
    except (ValueError, TypeError):
        return None


def _format_duration(seconds):
    """Format duration in seconds to human-readable string."""
    if seconds == 0:
        return "0s"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs and not hours:
        parts.append(f"{secs}s")
    return " ".join(parts)


def _format_duration_minutes(minutes):
    """Format duration in minutes to human-readable string."""
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    mins = minutes % 60
    if mins:
        return f"{hours}h {mins}m"
    return f"{hours}h"


def _load_messages():
    rows = db.query(SITE, "messages")
    if rows:
        # messages collection stores a single dict keyed by meeting_id
        # If stored as list of items, reconstruct the dict
        if isinstance(rows, list) and rows and isinstance(rows[0], dict):
            result = {}
            for item in rows:
                mid = item.get("meeting_id", "")
                msgs = item.get("msgs", [])
                if mid:
                    result[mid] = msgs
            return result if result else {}
    return {}


def _save_messages(data):
    # Convert dict keyed by meeting_id to a list for save_collection
    items = []
    for meeting_id, msgs in data.items():
        items.append({"meeting_id": meeting_id, "msgs": msgs})
    db.save_collection(SITE, "messages", items)


def _load_settings():
    rows = db.query(SITE, "settings")
    if rows:
        # settings collection stores a single dict keyed by user_id
        if isinstance(rows, list) and rows and isinstance(rows[0], dict):
            result = {}
            for item in rows:
                uid = item.get("user_id", "")
                settings = item.get("settings", {})
                if uid:
                    result[uid] = settings
            return result if result else {}
    return {}


def _save_settings(data):
    # Convert dict keyed by user_id to a list for save_collection
    items = []
    for user_id, settings in data.items():
        items.append({"user_id": user_id, "settings": settings})
    db.save_collection(SITE, "settings", items)


def _semantic_search_meetings(query, meetings, user_map):
    """Simple keyword-overlap semantic search over meetings."""
    query_words = set(query.lower().split())
    scored = []
    for m in meetings:
        text = (
            m["title"].lower() + " " +
            m["type"].lower() + " " +
            m["status"].lower() + " " +
            " ".join(user_map.get(p, "").lower() for p in m.get("participants", []))
        )
        text_words = set(text.split())
        overlap = len(query_words & text_words)
        # Also partial matching
        partial = sum(1 for qw in query_words if any(qw in tw for tw in text_words))
        score = overlap * 2 + partial
        if score > 0:
            scored.append((score, m))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [m for _, m in scored]


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    user, redir = _require_login()
    if redir:
        return redir

    user_map = _build_user_map()
    meetings = _load_meetings()
    calls = _load_call_log()
    recordings = _load_recordings()

    now = datetime.now()

    # Upcoming meetings: scheduled, involving current user
    upcoming = [
        m for m in meetings
        if m["status"] == "scheduled" and user["id"] in m.get("participants", [])
    ]
    upcoming.sort(key=lambda m: m["date"])

    # Recent meetings: completed, involving current user, last 7 days
    week_ago = now - timedelta(days=7)
    recent_meetings = [
        m for m in meetings
        if m["status"] == "completed"
        and user["id"] in m.get("participants", [])
        and _parse_dt(m["date"]) and _parse_dt(m["date"]) >= week_ago
    ]
    recent_meetings.sort(key=lambda m: m["date"], reverse=True)

    # Recent calls: involving current user
    recent_calls = [
        c for c in calls
        if c["caller_id"] == user["id"] or c["callee_id"] == user["id"]
    ]
    recent_calls.sort(key=lambda c: c["date"], reverse=True)
    recent_calls = recent_calls[:5]

    return render_template(
        "remote-calls/index.html",
        user=user,
        user_map=user_map,
        upcoming=upcoming,
        recent_meetings=recent_meetings[:5],
        recent_calls=recent_calls,
        total_recordings=len(recordings),
        format_duration=_format_duration,
        format_duration_minutes=_format_duration_minutes,
        parse_dt=_parse_dt,
    )


@blueprint.route("/meetings")
def meetings_page():
    user, redir = _require_login()
    if redir:
        return redir

    user_map = _build_user_map()
    meetings = _load_meetings()

    # Filters
    status = request.args.get("status", "")
    meeting_type = request.args.get("type", "")
    participant = request.args.get("participant", "")
    search = request.args.get("q", "")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")

    filtered = list(meetings)

    if status:
        filtered = [m for m in filtered if m["status"] == status]
    if meeting_type:
        filtered = [m for m in filtered if m["type"] == meeting_type]
    if participant:
        filtered = [m for m in filtered if participant in m.get("participants", [])]
    if search:
        q = search.lower()
        filtered = [m for m in filtered if q in m["title"].lower()]
    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
            filtered = [m for m in filtered if _parse_dt(m["date"]) and _parse_dt(m["date"]) >= dt_from]
        except ValueError:
            pass
    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to)
            filtered = [m for m in filtered if _parse_dt(m["date"]) and _parse_dt(m["date"]) <= dt_to]
        except ValueError:
            pass

    filtered.sort(key=lambda m: m["date"], reverse=True)

    users = _load_users()

    return render_template(
        "remote-calls/meetings.html",
        user=user,
        user_map=user_map,
        meetings=filtered,
        users=users,
        status=status,
        meeting_type=meeting_type,
        participant=participant,
        search=search,
        date_from=date_from,
        date_to=date_to,
        format_duration_minutes=_format_duration_minutes,
        parse_dt=_parse_dt,
    )


@blueprint.route("/meeting/<meeting_id>")
def meeting_detail(meeting_id):
    user, redir = _require_login()
    if redir:
        return redir

    meetings = _load_meetings()
    meeting = next((m for m in meetings if m["id"] == meeting_id), None)
    if not meeting:
        abort(404)

    user_map = _build_user_map()
    recordings = _load_recordings()
    recording = next((r for r in recordings if r["meeting_id"] == meeting_id), None)

    host = _get_user_by_id(meeting["host_id"])
    participants = [_get_user_by_id(pid) for pid in meeting.get("participants", [])]
    participants = [p for p in participants if p]

    return render_template(
        "remote-calls/meeting_detail.html",
        user=user,
        user_map=user_map,
        meeting=meeting,
        host=host,
        participants=participants,
        recording=recording,
        format_duration_minutes=_format_duration_minutes,
        parse_dt=_parse_dt,
    )


@blueprint.route("/recordings")
def recordings_page():
    user, redir = _require_login()
    if redir:
        return redir

    user_map = _build_user_map()
    recordings = _load_recordings()
    search = request.args.get("q", "")

    if search:
        q = search.lower()
        recordings = [r for r in recordings if q in r["title"].lower()]

    recordings.sort(key=lambda r: r["date"], reverse=True)

    return render_template(
        "remote-calls/recordings.html",
        user=user,
        user_map=user_map,
        recordings=recordings,
        search=search,
        format_duration_minutes=_format_duration_minutes,
        parse_dt=_parse_dt,
    )


@blueprint.route("/recording/<recording_id>")
def recording_detail(recording_id):
    user, redir = _require_login()
    if redir:
        return redir

    recordings = _load_recordings()
    recording = next((r for r in recordings if r["id"] == recording_id), None)
    if not recording:
        abort(404)

    user_map = _build_user_map()
    meetings = _load_meetings()
    meeting = next((m for m in meetings if m["id"] == recording["meeting_id"]), None)

    recorded_by = _get_user_by_id(recording["recorded_by"])

    return render_template(
        "remote-calls/recording_detail.html",
        user=user,
        user_map=user_map,
        recording=recording,
        meeting=meeting,
        recorded_by=recorded_by,
        format_duration_minutes=_format_duration_minutes,
        parse_dt=_parse_dt,
    )


@blueprint.route("/call-log")
def call_log_page():
    user, redir = _require_login()
    if redir:
        return redir

    user_map = _build_user_map()
    calls = _load_call_log()

    # Filters
    call_type = request.args.get("type", "")
    call_status = request.args.get("status", "")
    search = request.args.get("q", "")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    contact = request.args.get("contact", "")

    # Only show calls involving the current user
    filtered = [
        c for c in calls
        if c["caller_id"] == user["id"] or c["callee_id"] == user["id"]
    ]

    if call_type:
        filtered = [c for c in filtered if c["type"] == call_type]
    if call_status:
        filtered = [c for c in filtered if c["status"] == call_status]
    if contact:
        filtered = [
            c for c in filtered
            if (c["caller_id"] == contact or c["callee_id"] == contact)
        ]
    if search:
        q = search.lower()
        filtered = [
            c for c in filtered
            if (c.get("note") and q in c["note"].lower())
            or q in user_map.get(c["caller_id"], "").lower()
            or q in user_map.get(c["callee_id"], "").lower()
        ]
    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
            filtered = [c for c in filtered if _parse_dt(c["date"]) and _parse_dt(c["date"]) >= dt_from]
        except ValueError:
            pass
    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to)
            filtered = [c for c in filtered if _parse_dt(c["date"]) and _parse_dt(c["date"]) <= dt_to]
        except ValueError:
            pass

    filtered.sort(key=lambda c: c["date"], reverse=True)

    users = _load_users()

    return render_template(
        "remote-calls/call_log.html",
        user=user,
        user_map=user_map,
        calls=filtered,
        users=users,
        call_type=call_type,
        call_status=call_status,
        search=search,
        date_from=date_from,
        date_to=date_to,
        contact=contact,
        format_duration=_format_duration,
        parse_dt=_parse_dt,
    )


@blueprint.route("/schedule")
def schedule_page():
    user, redir = _require_login()
    if redir:
        return redir

    users = _load_users()
    other_users = [u for u in users if u["id"] != user["id"]]

    return render_template(
        "remote-calls/schedule.html",
        user=user,
        other_users=other_users,
    )


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("remote-calls/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user:
        return render_template("remote-calls/login.html", error="Invalid username or password.")
    if not password:
        return render_template("remote-calls/login.html", error="Password is required.")
    # Users with a stored password require an exact match (alex.rivera);
    # users without one still accept any non-empty password.
    if user.get("password") and password != user["password"]:
        return render_template("remote-calls/login.html", error="Invalid username or password.")
    session["user_id"] = user["root_user_id"]
    return redirect(url_for("remote-calls.index"))


@blueprint.route("/recording/<recording_id>/play", methods=["POST"])
def recording_play(recording_id):
    """Start playback of a recording.

    Increments the view count and returns playback metadata that is only
    revealed once the media is actually played (chapters, exact runtime,
    resolution) — playing is a verifiable precondition for follow-up macros.
    """
    user, redir = _require_login()
    if redir:
        return jsonify({"error": "login required"}), 401
    recordings = _load_recordings()
    recording = next((r for r in recordings if r["id"] == recording_id), None)
    if not recording:
        return jsonify({"error": "Recording not found"}), 404

    recording["views"] = (recording.get("views") or 0) + 1
    db.save_item(SITE, "recordings", recording_id, recording)

    # Deterministic playback details derived from the recording itself
    dur = recording.get("duration_minutes") or 30
    rnd = random.Random(recording_id)
    titles = ["Opening & attendance", "Main discussion", "Deep dive",
              "Q&A", "Action items & wrap-up"]
    n_chapters = max(2, min(5, dur // 12 + 1))
    bounds = sorted(rnd.sample(range(2, max(3, dur - 1)), n_chapters - 1)) if dur > 4 else []
    starts = [0] + bounds
    chapters = [{"start_min": s, "title": titles[i % len(titles)]}
                for i, s in enumerate(starts)]
    exact_seconds = dur * 60 + rnd.randint(0, 59)
    return jsonify({
        "playing": True,
        "recording_id": recording_id,
        "views": recording["views"],
        "exact_duration": f"{exact_seconds // 60}:{exact_seconds % 60:02d}",
        "resolution": rnd.choice(["1280x720", "1920x1080"]),
        "audio_channels": rnd.choice(["mono", "stereo"]),
        "chapters": chapters,
    })


@blueprint.route("/join")
def join_page():
    return render_template("remote-calls/join.html")


@blueprint.route("/settings")
def settings_page():
    user, redir = _require_login()
    if redir:
        return redir
    settings = _load_settings()
    user_settings = settings.get(user["id"], {})
    return render_template(
        "remote-calls/settings.html",
        user=user,
        user_settings=user_settings,
    )


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("remote-calls.index"))

@blueprint.route("/api/meetings", methods=["GET"])
def api_meetings_list():
    meetings = _load_meetings()
    user_map = _build_user_map()

    # Filters
    status = request.args.get("status", "")
    meeting_type = request.args.get("type", "")
    participant = request.args.get("participant", "")
    search = request.args.get("q", "")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")

    filtered = list(meetings)

    if status:
        filtered = [m for m in filtered if m["status"] == status]
    if meeting_type:
        filtered = [m for m in filtered if m["type"] == meeting_type]
    if participant:
        filtered = [m for m in filtered if participant in m.get("participants", [])]
    if search:
        q = search.lower()
        filtered = [m for m in filtered if q in m["title"].lower()]
    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
            filtered = [m for m in filtered if _parse_dt(m["date"]) and _parse_dt(m["date"]) >= dt_from]
        except ValueError:
            pass
    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to)
            filtered = [m for m in filtered if _parse_dt(m["date"]) and _parse_dt(m["date"]) <= dt_to]
        except ValueError:
            pass

    filtered.sort(key=lambda m: m["date"], reverse=True)

    # Enrich with host name
    results = []
    for m in filtered:
        entry = dict(m)
        entry["host_name"] = user_map.get(m["host_id"], "Unknown")
        entry["participant_names"] = [user_map.get(pid, "Unknown") for pid in m.get("participants", [])]
        results.append(entry)

    return jsonify({"meetings": results, "count": len(results)})


@blueprint.route("/api/meetings", methods=["POST"])
def api_meetings_create():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "Title is required"}), 400

    date_str = data.get("date", "")
    if not date_str:
        return jsonify({"error": "Date is required"}), 400

    duration = data.get("duration_minutes", 30)
    meeting_type = data.get("type", "work")
    participant_ids = data.get("participants", [])

    user = _current_user()
    if not user:
        return jsonify({"error": "Login required"}), 401

    # Ensure host is in participants
    if user["id"] not in participant_ids:
        participant_ids.insert(0, user["id"])

    meetings = _load_meetings()
    new_id = f"mtg-{len(meetings) + 1:03d}"

    new_meeting = {
        "id": new_id,
        "title": title,
        "host_id": user["id"],
        "participants": participant_ids,
        "date": date_str,
        "duration_minutes": int(duration),
        "type": meeting_type,
        "recording_available": False,
        "status": "scheduled",
    }

    meetings.append(new_meeting)
    db.save_collection(SITE, "meetings", meetings)

    try:
        from app.bridges import on_booking
        on_booking(
            user_id=session.get("user_id", 1),
            title=title,
            start=date_str,
            location="Virtual",
            service_name="Video Call",
        )
    except Exception:
        pass

    return jsonify(new_meeting), 201


@blueprint.route("/api/meetings/<meeting_id>", methods=["GET"])
def api_meeting_detail(meeting_id):
    meetings = _load_meetings()
    meeting = next((m for m in meetings if m["id"] == meeting_id), None)
    if not meeting:
        return jsonify({"error": "Meeting not found"}), 404

    user_map = _build_user_map()
    result = dict(meeting)
    result["host_name"] = user_map.get(meeting["host_id"], "Unknown")
    result["participant_names"] = [user_map.get(pid, "Unknown") for pid in meeting.get("participants", [])]

    recordings = _load_recordings()
    recording = next((r for r in recordings if r["meeting_id"] == meeting_id), None)
    if recording:
        result["recording"] = recording

    return jsonify(result)


@blueprint.route("/api/meetings/<meeting_id>", methods=["PUT"])
def api_meeting_update(meeting_id):
    meetings = _load_meetings()
    meeting = next((m for m in meetings if m["id"] == meeting_id), None)
    if not meeting:
        return jsonify({"error": "Meeting not found"}), 404

    data = request.get_json(silent=True) or {}

    if "title" in data:
        meeting["title"] = data["title"].strip()
    if "date" in data:
        meeting["date"] = data["date"]
    if "duration_minutes" in data:
        meeting["duration_minutes"] = int(data["duration_minutes"])
    if "type" in data:
        meeting["type"] = data["type"]
    if "participants" in data:
        meeting["participants"] = data["participants"]
    if "status" in data:
        meeting["status"] = data["status"]

    db.save_collection(SITE, "meetings", meetings)
    return jsonify(meeting)


@blueprint.route("/api/meetings/<meeting_id>", methods=["DELETE"])
def api_meeting_delete(meeting_id):
    meetings = _load_meetings()
    meeting = next((m for m in meetings if m["id"] == meeting_id), None)
    if not meeting:
        return jsonify({"error": "Meeting not found"}), 404

    if meeting["status"] == "completed":
        return jsonify({"error": "Cannot cancel a completed meeting"}), 400

    meeting["status"] = "cancelled"
    db.save_collection(SITE, "meetings", meetings)
    return jsonify({"message": f"Meeting '{meeting['title']}' has been cancelled", "meeting": meeting})


@blueprint.route("/api/recordings", methods=["GET"])
def api_recordings_list():
    recordings = _load_recordings()
    user_map = _build_user_map()
    search = request.args.get("q", "")

    if search:
        q = search.lower()
        recordings = [r for r in recordings if q in r["title"].lower()]

    recordings.sort(key=lambda r: r["date"], reverse=True)

    results = []
    for r in recordings:
        entry = _deserialize_row(r)
        entry["recorded_by_name"] = user_map.get(r["recorded_by"], "Unknown")
        results.append(entry)

    return jsonify({"recordings": results, "count": len(results)})


@blueprint.route("/api/recordings/<recording_id>", methods=["GET"])
def api_recording_detail(recording_id):
    recordings = _load_recordings()
    recording = next((r for r in recordings if r["id"] == recording_id), None)
    if not recording:
        return jsonify({"error": "Recording not found"}), 404

    user_map = _build_user_map()
    result = dict(recording)
    result["recorded_by_name"] = user_map.get(recording["recorded_by"], "Unknown")

    meetings = _load_meetings()
    meeting = next((m for m in meetings if m["id"] == recording["meeting_id"]), None)
    if meeting:
        result["meeting"] = meeting

    return jsonify(result)


@blueprint.route("/api/call-log", methods=["GET"])
def api_call_log():
    calls = _load_call_log()
    user_map = _build_user_map()

    # Filters
    call_type = request.args.get("type", "")
    call_status = request.args.get("status", "")
    caller = request.args.get("caller", "")
    callee = request.args.get("callee", "")
    search = request.args.get("q", "")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")

    filtered = list(calls)

    if call_type:
        filtered = [c for c in filtered if c["type"] == call_type]
    if call_status:
        filtered = [c for c in filtered if c["status"] == call_status]
    if caller:
        filtered = [c for c in filtered if c["caller_id"] == caller]
    if callee:
        filtered = [c for c in filtered if c["callee_id"] == callee]
    if search:
        q = search.lower()
        filtered = [
            c for c in filtered
            if (c.get("note") and q in c["note"].lower())
            or q in user_map.get(c["caller_id"], "").lower()
            or q in user_map.get(c["callee_id"], "").lower()
        ]
    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
            filtered = [c for c in filtered if _parse_dt(c["date"]) and _parse_dt(c["date"]) >= dt_from]
        except ValueError:
            pass
    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to)
            filtered = [c for c in filtered if _parse_dt(c["date"]) and _parse_dt(c["date"]) <= dt_to]
        except ValueError:
            pass

    filtered.sort(key=lambda c: c["date"], reverse=True)

    results = []
    for c in filtered:
        entry = dict(c)
        entry["caller_name"] = user_map.get(c["caller_id"], "Unknown")
        entry["callee_name"] = user_map.get(c["callee_id"], "Unknown")
        entry["duration_formatted"] = _format_duration(c["duration_seconds"])
        results.append(entry)

    return jsonify({"calls": results, "count": len(results)})


@blueprint.route("/api/stats", methods=["GET"])
def api_stats():
    user = _current_user()
    meetings = _load_meetings()
    calls = _load_call_log()
    recordings = _load_recordings()

    # Global stats
    total_meetings = len(meetings)
    scheduled_meetings = len([m for m in meetings if m["status"] == "scheduled"])
    completed_meetings = len([m for m in meetings if m["status"] == "completed"])
    total_calls = len(calls)
    completed_calls = len([c for c in calls if c["status"] == "completed"])
    missed_calls = len([c for c in calls if c["status"] == "missed"])
    total_recordings = len(recordings)
    total_recording_minutes = sum(r["duration_minutes"] for r in recordings)
    total_recording_size_mb = round(sum(r["file_size_mb"] for r in recordings), 1)

    stats = {
        "total_meetings": total_meetings,
        "scheduled_meetings": scheduled_meetings,
        "completed_meetings": completed_meetings,
        "total_calls": total_calls,
        "completed_calls": completed_calls,
        "missed_calls": missed_calls,
        "total_recordings": total_recordings,
        "total_recording_minutes": total_recording_minutes,
        "total_recording_size_mb": total_recording_size_mb,
    }

    # Per-user stats if logged in
    if user:
        uid = user["id"]
        user_meetings = [m for m in meetings if uid in m.get("participants", [])]
        user_calls = [c for c in calls if c["caller_id"] == uid or c["callee_id"] == uid]
        user_missed = [c for c in user_calls if c["status"] == "missed"]

        total_call_seconds = sum(c["duration_seconds"] for c in user_calls if c["status"] == "completed")
        total_meeting_minutes = sum(m["duration_minutes"] for m in user_meetings if m["status"] == "completed")

        stats["user"] = {
            "id": uid,
            "display_name": user["display_name"],
            "meetings_count": len(user_meetings),
            "calls_count": len(user_calls),
            "missed_calls": len(user_missed),
            "total_call_seconds": total_call_seconds,
            "total_call_time_formatted": _format_duration(total_call_seconds),
            "total_meeting_minutes": total_meeting_minutes,
            "total_meeting_time_formatted": _format_duration_minutes(total_meeting_minutes),
        }

    return jsonify(stats)


# ---------------------------------------------------------------------------
# Semantic search API
# ---------------------------------------------------------------------------

@blueprint.route("/api/meetings/search", methods=["GET"])
def api_meetings_search():
    """Keyword-overlap semantic search over meetings."""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"meetings": [], "count": 0})
    meetings = _load_meetings()
    user_map = _build_user_map()
    results = _semantic_search_meetings(query, meetings, user_map)
    enriched = []
    for m in results:
        entry = dict(m)
        entry["host_name"] = user_map.get(m["host_id"], "Unknown")
        entry["participant_names"] = [user_map.get(pid, "Unknown") for pid in m.get("participants", [])]
        enriched.append(entry)
    return jsonify({"meetings": enriched, "count": len(enriched)})


# ---------------------------------------------------------------------------
# Recording playback API  (play_by_playback)
# ---------------------------------------------------------------------------

@blueprint.route("/api/recordings/<recording_id>/play", methods=["POST"])
def api_recording_play(recording_id):
    """Mark a recording as played (increment views)."""
    recordings = _load_recordings()
    recording = next((r for r in recordings if r["id"] == recording_id), None)
    if not recording:
        return jsonify({"error": "Recording not found"}), 404
    recording["views"] = recording.get("views", 0) + 1
    db.save_collection(SITE, "recordings", recordings)
    return jsonify({"status": "playing", "recording_id": recording_id,
                    "title": recording["title"], "views": recording["views"]})


# ---------------------------------------------------------------------------
# Share toggle API  (share_by_toggle)
# ---------------------------------------------------------------------------

@blueprint.route("/api/meetings/<meeting_id>/share", methods=["POST"])
def api_meeting_share_toggle(meeting_id):
    """Toggle share link for a meeting."""
    meetings = _load_meetings()
    meeting = next((m for m in meetings if m["id"] == meeting_id), None)
    if not meeting:
        return jsonify({"error": "Meeting not found"}), 404
    currently_shared = meeting.get("share_link_active", False)
    if currently_shared:
        meeting["share_link_active"] = False
        meeting.pop("share_link", None)
        action = "unshared"
    else:
        meeting["share_link_active"] = True
        meeting["share_link"] = f"https://callhub.io/join/{meeting_id}"
        action = "shared"
    db.save_collection(SITE, "meetings", meetings)
    return jsonify({"action": action, "meeting_id": meeting_id,
                    "share_link": meeting.get("share_link", ""),
                    "share_link_active": meeting.get("share_link_active", False)})


# ---------------------------------------------------------------------------
# Invite participant API  (invite_by_form)
# ---------------------------------------------------------------------------

@blueprint.route("/meeting/<meeting_id>/invite", methods=["POST"])
def form_invite_to_meeting(meeting_id):
    """Invite a participant via form POST and redirect back."""
    email = request.form.get("email", "").strip()
    if email:
        meetings = _load_meetings()
        meeting = next((m for m in meetings if m["id"] == meeting_id), None)
        if meeting:
            users = _load_users()
            found = next((u for u in users if u.get("email") == email), None)
            if found and found["id"] not in meeting.get("participants", []):
                meeting.setdefault("participants", []).append(found["id"])
                db.save_collection(SITE, "meetings", meetings)
    return redirect(url_for("remote-calls.meeting_detail", meeting_id=meeting_id))


@blueprint.route("/api/meetings/<meeting_id>/invite", methods=["POST"])
def api_meeting_invite(meeting_id):
    """Invite a participant to a meeting."""
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id", "").strip()
    email = data.get("email", "").strip()
    if not user_id and not email:
        return jsonify({"error": "user_id or email is required"}), 400

    meetings = _load_meetings()
    meeting = next((m for m in meetings if m["id"] == meeting_id), None)
    if not meeting:
        return jsonify({"error": "Meeting not found"}), 404

    # Resolve by email if user_id not given
    if not user_id and email:
        users = _load_users()
        found = next((u for u in users if u["email"] == email), None)
        if found:
            user_id = found["id"]
        else:
            return jsonify({"error": f"No user found with email {email}"}), 404

    if user_id in meeting.get("participants", []):
        return jsonify({"message": "Already a participant", "meeting_id": meeting_id,
                        "user_id": user_id}), 200

    meeting.setdefault("participants", []).append(user_id)
    db.save_collection(SITE, "meetings", meetings)

    user_map = _build_user_map()
    return jsonify({"message": "Invited successfully", "meeting_id": meeting_id,
                    "user_id": user_id,
                    "user_name": user_map.get(user_id, "Unknown"),
                    "participant_count": len(meeting["participants"])}), 201


# ---------------------------------------------------------------------------
# Meeting chat / messages API  (message_from_free_text)
# ---------------------------------------------------------------------------

@blueprint.route("/api/meetings/<meeting_id>/messages", methods=["GET"])
def api_meeting_messages(meeting_id):
    """Get chat messages for a meeting."""
    meetings = _load_meetings()
    meeting = next((m for m in meetings if m["id"] == meeting_id), None)
    if not meeting:
        return jsonify({"error": "Meeting not found"}), 404
    all_msgs = _load_messages()
    msgs = all_msgs.get(meeting_id, [])
    return jsonify({"messages": msgs, "count": len(msgs), "meeting_id": meeting_id})


@blueprint.route("/api/meetings/<meeting_id>/messages", methods=["POST"])
def api_meeting_send_message(meeting_id):
    """Send a chat message in a meeting."""
    meetings = _load_meetings()
    meeting = next((m for m in meetings if m["id"] == meeting_id), None)
    if not meeting:
        return jsonify({"error": "Meeting not found"}), 404

    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    sender_id = data.get("sender_id", "")
    if not text:
        return jsonify({"error": "Message text is required"}), 400
    if not sender_id:
        user = _current_user()
        if user:
            sender_id = user["id"]
        else:
            return jsonify({"error": "sender_id is required"}), 400

    user_map = _build_user_map()
    all_msgs = _load_messages()
    msgs = all_msgs.setdefault(meeting_id, [])
    new_msg = {
        "id": f"msg-{len(msgs)+1:03d}",
        "meeting_id": meeting_id,
        "sender_id": sender_id,
        "sender_name": user_map.get(sender_id, "Unknown"),
        "text": text,
        "timestamp": datetime.now().isoformat(),
    }
    msgs.append(new_msg)
    _save_messages(all_msgs)
    return jsonify(new_msg), 201


# ---------------------------------------------------------------------------
# Join meeting by code API  (join_by_code)
# ---------------------------------------------------------------------------

@blueprint.route("/api/join", methods=["POST"])
def api_join_meeting():
    """Join a meeting using a meeting code/ID."""
    data = request.get_json(silent=True) or {}
    code = data.get("code", "").strip()
    if not code:
        return jsonify({"error": "Meeting code is required"}), 400

    meetings = _load_meetings()
    meeting = next((m for m in meetings if m["id"] == code), None)
    if not meeting:
        return jsonify({"error": f"No meeting found with code '{code}'"}), 404

    if meeting["status"] == "cancelled":
        return jsonify({"error": "This meeting has been cancelled"}), 400

    user = _current_user()
    if user and user["id"] not in meeting.get("participants", []):
        meeting.setdefault("participants", []).append(user["id"])
        db.save_collection(SITE, "meetings", meetings)

    user_map = _build_user_map()
    return jsonify({
        "message": "Joined meeting successfully",
        "meeting": {
            "id": meeting["id"],
            "title": meeting["title"],
            "status": meeting["status"],
            "host_name": user_map.get(meeting["host_id"], "Unknown"),
            "participant_count": len(meeting.get("participants", [])),
        },
    })


# ---------------------------------------------------------------------------
# Configure meeting settings API  (configure_by_dropdown)
# ---------------------------------------------------------------------------

@blueprint.route("/api/settings", methods=["GET"])
def api_settings_get():
    """Get user settings."""
    user = _current_user()
    if not user:
        return jsonify({"error": "Login required"}), 401
    settings = _load_settings()
    user_settings = settings.get(user["id"], {
        "default_duration": 30,
        "camera_on_join": True,
        "mic_on_join": True,
        "recording_auto": False,
        "notification_sound": "default",
        "background": "none",
        "language": "en",
    })
    return jsonify({"user_id": user["id"], "settings": user_settings})


@blueprint.route("/api/settings", methods=["PUT"])
def api_settings_update():
    """Update user settings."""
    user = _current_user()
    if not user:
        return jsonify({"error": "Login required"}), 401
    data = request.get_json(silent=True) or {}
    settings = _load_settings()
    user_settings = settings.get(user["id"], {})
    for key in ("default_duration", "camera_on_join", "mic_on_join",
                "recording_auto", "notification_sound", "background", "language"):
        if key in data:
            user_settings[key] = data[key]
    settings[user["id"]] = user_settings
    _save_settings(settings)
    return jsonify({"user_id": user["id"], "settings": user_settings})


@blueprint.route("/api/meetings/<meeting_id>/settings", methods=["PUT"])
def api_meeting_settings(meeting_id):
    """Configure per-meeting settings (configure_by_dropdown)."""
    meetings = _load_meetings()
    meeting = next((m for m in meetings if m["id"] == meeting_id), None)
    if not meeting:
        return jsonify({"error": "Meeting not found"}), 404
    data = request.get_json(silent=True) or {}
    meeting_settings = meeting.setdefault("settings", {})
    for key in ("recording_mode", "waiting_room", "mute_on_entry",
                "allow_screen_share", "chat_enabled"):
        if key in data:
            meeting_settings[key] = data[key]
    meeting["settings"] = meeting_settings
    db.save_collection(SITE, "meetings", meetings)
    return jsonify({"meeting_id": meeting_id, "settings": meeting_settings})


# ---------------------------------------------------------------------------
# Export API  (export_by_dropdown)
# ---------------------------------------------------------------------------

@blueprint.route("/api/export", methods=["GET"])
def api_export():
    """Export meetings or call log as CSV or JSON."""
    fmt = request.args.get("format", "json")
    data_type = request.args.get("type", "meetings")
    status_filter = request.args.get("status", "")
    meeting_type_filter = request.args.get("meeting_type", "")

    if data_type == "meetings":
        records = _load_meetings()
        if status_filter:
            records = [r for r in records if r["status"] == status_filter]
        if meeting_type_filter:
            records = [r for r in records if r["type"] == meeting_type_filter]
        if fmt == "csv":
            si = io.StringIO()
            writer = csv.writer(si)
            writer.writerow(["id", "title", "host_id", "date", "duration_minutes",
                             "type", "status", "participants_count", "recording_available"])
            for r in records:
                writer.writerow([r["id"], r["title"], r["host_id"], r["date"],
                                 r["duration_minutes"], r["type"], r["status"],
                                 len(r.get("participants", [])), r["recording_available"]])
            return Response(si.getvalue(), mimetype="text/csv",
                            headers={"Content-Disposition": "attachment; filename=meetings.csv"})
        return jsonify(records)

    elif data_type == "calls":
        records = _load_call_log()
        if status_filter:
            records = [r for r in records if r["status"] == status_filter]
        if fmt == "csv":
            si = io.StringIO()
            writer = csv.writer(si)
            writer.writerow(["id", "caller_id", "callee_id", "type", "date",
                             "duration_seconds", "status", "note"])
            for r in records:
                writer.writerow([r["id"], r["caller_id"], r["callee_id"],
                                 r["type"], r["date"], r["duration_seconds"],
                                 r["status"], r.get("note", "")])
            return Response(si.getvalue(), mimetype="text/csv",
                            headers={"Content-Disposition": "attachment; filename=calls.csv"})
        return jsonify(records)

    elif data_type == "recordings":
        records = _load_recordings()
        if fmt == "csv":
            si = io.StringIO()
            writer = csv.writer(si)
            writer.writerow(["id", "meeting_id", "title", "recorded_by", "date",
                             "duration_minutes", "file_size_mb", "format",
                             "transcript_available", "access", "views"])
            for r in records:
                writer.writerow([r["id"], r["meeting_id"], r["title"],
                                 r["recorded_by"], r["date"], r["duration_minutes"],
                                 r["file_size_mb"], r["format"],
                                 r["transcript_available"], r["access"], r["views"]])
            return Response(si.getvalue(), mimetype="text/csv",
                            headers={"Content-Disposition": "attachment; filename=recordings.csv"})
        return jsonify(records)

    return jsonify({"error": f"Unknown type: {data_type}"}), 400


# ---------------------------------------------------------------------------
# Login API (for programmatic auth)
# ---------------------------------------------------------------------------

@blueprint.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user:
        return jsonify({"error": "Invalid credentials"}), 401
    if not password:
        return jsonify({"error": "Password required"}), 400
    session["user_id"] = user["root_user_id"]
    return jsonify({"user_id": user["id"], "display_name": user["display_name"],
                    "root_user_id": user["root_user_id"]})


# ---------------------------------------------------------------------------
# Users API
# ---------------------------------------------------------------------------

@blueprint.route("/api/users", methods=["GET"])
def api_users_list():
    users = _load_users()
    return jsonify({"users": users, "count": len(users)})

