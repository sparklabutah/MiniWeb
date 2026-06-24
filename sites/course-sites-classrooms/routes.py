"""Course Sites & Classrooms -- Canvas/Moodle-style LMS.

Serves courses, assignments, submissions, gradebook, and discussion
boards with role-based access (admin / instructor / student).
Data is loaded from JSON files in data/.
"""
import json
import pathlib
from datetime import datetime

from flask import (
    Blueprint, Response, abort, jsonify, redirect,
    render_template, request, session, url_for,
)

SITE_DIR = pathlib.Path(__file__).resolve().parent
DATA_DIR = SITE_DIR / "data"
CONFIG_FILE = SITE_DIR / "config" / "config.json"

blueprint = Blueprint(
    "course-sites-classrooms",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

BP = "course-sites-classrooms"

# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def _load_json(filename):
    path = DATA_DIR / filename
    if path.exists():
        return json.loads(path.read_text())
    return []


def _save_json(filename, data):
    path = DATA_DIR / filename
    path.write_text(json.dumps(data, indent=2))


def _load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)


# Cached data (immutable reference data loaded once)
_users = None
_courses = None
_assignments = None
_submissions = None
_discussions = None


def _ensure_loaded():
    global _users, _courses, _assignments, _submissions, _discussions
    if _users is None:
        _users = _load_json("users.json")
        _courses = _load_json("courses.json")
        _assignments = _load_json("assignments.json")
        _submissions = _load_json("submissions.json")
        _discussions = _load_json("discussions.json")


def _get_users():
    _ensure_loaded()
    return _users


def _get_courses():
    _ensure_loaded()
    return _courses


def _get_assignments():
    _ensure_loaded()
    return _assignments


def _get_submissions():
    return _load_json("submissions.json")


def _get_discussions():
    return _load_json("discussions.json")


def _save_submissions(subs):
    _save_json("submissions.json", subs)


def _save_discussions(discs):
    _save_json("discussions.json", discs)


def _save_users(users):
    global _users
    _save_json("users.json", users)
    _users = users


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

def _find(collection, **kwargs):
    """Return first item matching all kwargs."""
    for item in collection:
        if all(item.get(k) == v for k, v in kwargs.items()):
            return item
    return None


def _filter(collection, **kwargs):
    """Return all items matching all kwargs."""
    return [item for item in collection
            if all(item.get(k) == v for k, v in kwargs.items())]


def _current_user():
    """Return current logged-in user or None."""
    uid = session.get("user_id")
    if uid is None:
        return None
    return _find(_get_users(), id=uid)


def _user_courses(user):
    """Return courses a user can see based on role."""
    courses = _get_courses()
    if user["role"] == "admin":
        return courses
    if user["role"] == "instructor":
        return [c for c in courses if c["instructor_id"] == user["id"]]
    # student
    return [c for c in courses if user["id"] in c.get("enrolled_students", [])]


def _is_enrolled(user, course):
    """Check if user is enrolled in or teaches a course."""
    if user["role"] == "admin":
        return True
    if user["role"] == "instructor" and course["instructor_id"] == user["id"]:
        return True
    return user["id"] in course.get("enrolled_students", [])


def _weighted_average(student_id, course_id):
    """Compute the weighted average grade for a student in a course.

    Grade weights: homework 30%, exams 40%, projects 20%, quizzes 10%.
    Each category average is the mean of (score/points) for graded submissions.
    """
    course = _find(_get_courses(), id=course_id)
    if not course:
        return None
    weights = course.get("grade_weights", {
        "homework": 0.30, "exams": 0.40, "projects": 0.20, "quizzes": 0.10
    })

    assignments = _filter(_get_assignments(), course_id=course_id)
    submissions = _get_submissions()

    category_scores = {}  # type -> list of (score, max_points)
    for a in assignments:
        sub = None
        for s in submissions:
            if s["assignment_id"] == a["id"] and s["student_id"] == student_id:
                sub = s
                break
        if sub and sub["status"] == "graded":
            cat = a["type"]
            # Map singular types to weight keys
            weight_key = cat
            if cat == "exam":
                weight_key = "exams"
            elif cat == "quiz":
                weight_key = "quizzes"
            elif cat == "project":
                weight_key = "projects"
            elif cat == "homework":
                weight_key = "homework"
            category_scores.setdefault(weight_key, []).append(
                (sub["score"], a["points"])
            )

    if not category_scores:
        return None

    total = 0.0
    total_weight = 0.0
    for cat, pairs in category_scores.items():
        cat_pct = sum(s / m for s, m in pairs) / len(pairs) * 100
        w = weights.get(cat, 0)
        total += cat_pct * w
        total_weight += w

    if total_weight == 0:
        return None
    return round(total / total_weight, 2)


def _letter_grade(pct):
    """Convert percentage to letter grade."""
    if pct is None:
        return "N/A"
    if pct >= 93:
        return "A"
    if pct >= 90:
        return "A-"
    if pct >= 87:
        return "B+"
    if pct >= 83:
        return "B"
    if pct >= 80:
        return "B-"
    if pct >= 77:
        return "C+"
    if pct >= 73:
        return "C"
    if pct >= 70:
        return "C-"
    if pct >= 67:
        return "D+"
    if pct >= 60:
        return "D"
    return "F"


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    user = _current_user()
    courses = _get_courses()
    # Build instructor name map
    users = _get_users()
    instructor_map = {u["id"]: u["name"] for u in users if u["role"] == "instructor"}
    return render_template(f"{BP}/index.html",
                           courses=courses, user=user,
                           instructor_map=instructor_map)


@blueprint.route("/course/<int:course_id>")
def course_detail(course_id):
    user = _current_user()
    course = _find(_get_courses(), id=course_id)
    if not course:
        abort(404)
    assignments = _filter(_get_assignments(), course_id=course_id)
    discussions = [d for d in _get_discussions() if d["course_id"] == course_id]
    instructor = _find(_get_users(), id=course["instructor_id"])
    students = [_find(_get_users(), id=sid) for sid in course.get("enrolled_students", [])]
    students = [s for s in students if s is not None]
    return render_template(f"{BP}/course.html",
                           course=course, assignments=assignments,
                           discussions=discussions, instructor=instructor,
                           students=students, user=user)


@blueprint.route("/course/<int:course_id>/assignment/<int:assignment_id>")
def assignment_detail(course_id, assignment_id):
    user = _current_user()
    course = _find(_get_courses(), id=course_id)
    if not course:
        abort(404)
    assignment = _find(_get_assignments(), id=assignment_id, course_id=course_id)
    if not assignment:
        abort(404)
    submissions = _get_submissions()
    # For instructors/admins, show all submissions; for students, show own
    if user and user["role"] in ("instructor", "admin"):
        related_subs = [s for s in submissions if s["assignment_id"] == assignment_id]
        # Attach student names
        for s in related_subs:
            student = _find(_get_users(), id=s["student_id"])
            s["student_name"] = student["name"] if student else "Unknown"
    elif user and user["role"] == "student":
        related_subs = [s for s in submissions
                        if s["assignment_id"] == assignment_id and s["student_id"] == user["id"]]
    else:
        related_subs = []
    return render_template(f"{BP}/assignment.html",
                           course=course, assignment=assignment,
                           submissions=related_subs, user=user)


@blueprint.route("/course/<int:course_id>/gradebook")
def gradebook(course_id):
    user = _current_user()
    course = _find(_get_courses(), id=course_id)
    if not course:
        abort(404)
    assignments = _filter(_get_assignments(), course_id=course_id)
    submissions = _get_submissions()
    students = [_find(_get_users(), id=sid) for sid in course.get("enrolled_students", [])]
    students = [s for s in students if s is not None]

    gradebook_data = []
    for student in students:
        row = {"student": student, "scores": {}, "weighted_avg": None, "letter": "N/A"}
        for a in assignments:
            sub = next((s for s in submissions
                        if s["assignment_id"] == a["id"] and s["student_id"] == student["id"]), None)
            row["scores"][a["id"]] = sub
        row["weighted_avg"] = _weighted_average(student["id"], course_id)
        row["letter"] = _letter_grade(row["weighted_avg"])
        gradebook_data.append(row)

    return render_template(f"{BP}/gradebook.html",
                           course=course, assignments=assignments,
                           gradebook=gradebook_data, user=user)


@blueprint.route("/course/<int:course_id>/discussions")
def discussions_page(course_id):
    user = _current_user()
    course = _find(_get_courses(), id=course_id)
    if not course:
        abort(404)
    discussions = [d for d in _get_discussions() if d["course_id"] == course_id]
    # Attach author names
    users = _get_users()
    user_map = {u["id"]: u["name"] for u in users}
    for d in discussions:
        d["author_name"] = user_map.get(d["author_id"], "Unknown")
        for r in d.get("replies", []):
            r["author_name"] = user_map.get(r["author_id"], "Unknown")
    # Sort: pinned first, then by date descending
    discussions.sort(key=lambda d: (not d.get("pinned", False), d["created_at"]), reverse=False)
    pinned = [d for d in discussions if d.get("pinned")]
    unpinned = sorted([d for d in discussions if not d.get("pinned")],
                      key=lambda d: d["created_at"], reverse=True)
    discussions = pinned + unpinned
    return render_template(f"{BP}/discussions.html",
                           course=course, discussions=discussions,
                           user=user, user_map=user_map)


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template(f"{BP}/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    user = _find(_get_users(), username=username)
    if not user or user.get("password") != password:
        return render_template(f"{BP}/login.html",
                               error="Invalid username or password")
    session["user_id"] = user["id"]
    return redirect(url_for(f"{BP}.index"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for(f"{BP}.login_page"))


# ---------------------------------------------------------------------------
# Form-based mutation routes (browser automation compatible)
# ---------------------------------------------------------------------------

@blueprint.route("/course/<int:course_id>/assignment/<int:assignment_id>/submit", methods=["POST"])
def form_submit_assignment(course_id, assignment_id):
    user = _current_user()
    if not user or user["role"] != "student":
        return redirect(url_for(f"{BP}.login_page"))
    course = _find(_get_courses(), id=course_id)
    if not course or user["id"] not in course.get("enrolled_students", []):
        abort(403)
    submissions = _get_submissions()
    new_id = max((s["id"] for s in submissions), default=0) + 1
    submissions.append({
        "id": new_id,
        "assignment_id": assignment_id,
        "student_id": user["id"],
        "course_id": course_id,
        "submitted_at": datetime.now().isoformat(),
        "score": None,
        "status": "submitted",
        "feedback": ""
    })
    _save_submissions(submissions)
    return redirect(url_for(f"{BP}.assignment_detail",
                            course_id=course_id, assignment_id=assignment_id))


@blueprint.route("/course/<int:course_id>/assignment/<int:assignment_id>/grade", methods=["POST"])
def form_grade_submission(course_id, assignment_id):
    user = _current_user()
    if not user or user["role"] not in ("instructor", "admin"):
        return redirect(url_for(f"{BP}.login_page"))
    student_id = request.form.get("student_id", type=int)
    score = request.form.get("score", type=float)
    feedback = request.form.get("feedback", "").strip()
    if student_id is None or score is None:
        abort(400)
    submissions = _get_submissions()
    sub = next((s for s in submissions
                if s["assignment_id"] == assignment_id and s["student_id"] == student_id), None)
    if sub:
        sub["score"] = score
        sub["status"] = "graded"
        sub["feedback"] = feedback
    _save_submissions(submissions)
    return redirect(url_for(f"{BP}.assignment_detail",
                            course_id=course_id, assignment_id=assignment_id))


@blueprint.route("/course/<int:course_id>/discussions/new", methods=["POST"])
def form_new_discussion(course_id):
    user = _current_user()
    if not user:
        return redirect(url_for(f"{BP}.login_page"))
    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()
    if not title or not content:
        return redirect(url_for(f"{BP}.discussions_page", course_id=course_id))
    discussions = _get_discussions()
    new_id = max((d["id"] for d in discussions), default=0) + 1
    discussions.append({
        "id": new_id,
        "course_id": course_id,
        "title": title,
        "author_id": user["id"],
        "created_at": datetime.now().isoformat(),
        "content": content,
        "pinned": False,
        "replies": []
    })
    _save_discussions(discussions)
    return redirect(url_for(f"{BP}.discussions_page", course_id=course_id))


@blueprint.route("/course/<int:course_id>/discussion/<int:disc_id>/reply", methods=["POST"])
def form_reply_discussion(course_id, disc_id):
    user = _current_user()
    if not user:
        return redirect(url_for(f"{BP}.login_page"))
    content = request.form.get("content", "").strip()
    if not content:
        return redirect(url_for(f"{BP}.discussions_page", course_id=course_id))
    discussions = _get_discussions()
    disc = _find(discussions, id=disc_id)
    if not disc:
        abort(404)
    replies = disc.setdefault("replies", [])
    new_reply_id = max((r["id"] for r in replies), default=0) + 1
    replies.append({
        "id": new_reply_id,
        "author_id": user["id"],
        "content": content,
        "created_at": datetime.now().isoformat()
    })
    _save_discussions(discussions)
    return redirect(url_for(f"{BP}.discussions_page", course_id=course_id))


@blueprint.route("/course/<int:course_id>/enroll", methods=["POST"])
def form_enroll(course_id):
    """Admin or self-enroll a student into a course."""
    user = _current_user()
    if not user:
        return redirect(url_for(f"{BP}.login_page"))
    student_id = request.form.get("student_id", type=int)
    if student_id is None:
        student_id = user["id"]
    courses = _get_courses()
    course = _find(courses, id=course_id)
    if not course:
        abort(404)
    enrolled = course.setdefault("enrolled_students", [])
    if student_id not in enrolled:
        enrolled.append(student_id)
        _save_json("courses.json", courses)
    return redirect(url_for(f"{BP}.course_detail", course_id=course_id))


@blueprint.route("/course/<int:course_id>/unenroll", methods=["POST"])
def form_unenroll(course_id):
    """Remove a student from a course."""
    user = _current_user()
    if not user:
        return redirect(url_for(f"{BP}.login_page"))
    student_id = request.form.get("student_id", type=int)
    if student_id is None:
        student_id = user["id"]
    courses = _get_courses()
    course = _find(courses, id=course_id)
    if not course:
        abort(404)
    enrolled = course.get("enrolled_students", [])
    if student_id in enrolled:
        enrolled.remove(student_id)
        _save_json("courses.json", courses)
    return redirect(url_for(f"{BP}.course_detail", course_id=course_id))


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/courses")
def api_courses():
    courses = _get_courses()
    dept = request.args.get("department", "").strip()
    instructor_id = request.args.get("instructor_id", type=int)
    semester = request.args.get("semester", "").strip()
    if dept:
        courses = [c for c in courses if c.get("department", "").lower() == dept.lower()]
    if instructor_id:
        courses = [c for c in courses if c["instructor_id"] == instructor_id]
    if semester:
        courses = [c for c in courses if c.get("semester", "").lower() == semester.lower()]
    return jsonify(courses)


@blueprint.route("/api/courses/<int:course_id>")
def api_course(course_id):
    course = _find(_get_courses(), id=course_id)
    if not course:
        abort(404)
    return jsonify(course)


@blueprint.route("/api/courses/<int:course_id>/assignments")
def api_course_assignments(course_id):
    assignments = _filter(_get_assignments(), course_id=course_id)
    atype = request.args.get("type", "").strip()
    if atype:
        assignments = [a for a in assignments if a["type"] == atype]
    return jsonify(assignments)


@blueprint.route("/api/assignments/<int:assignment_id>")
def api_assignment(assignment_id):
    a = _find(_get_assignments(), id=assignment_id)
    if not a:
        abort(404)
    return jsonify(a)


@blueprint.route("/api/courses/<int:course_id>/submissions")
def api_course_submissions(course_id):
    subs = [s for s in _get_submissions() if s.get("course_id") == course_id]
    student_id = request.args.get("student_id", type=int)
    if student_id:
        subs = [s for s in subs if s["student_id"] == student_id]
    return jsonify(subs)


@blueprint.route("/api/assignments/<int:assignment_id>/submissions")
def api_assignment_submissions(assignment_id):
    subs = [s for s in _get_submissions() if s["assignment_id"] == assignment_id]
    return jsonify(subs)


@blueprint.route("/api/courses/<int:course_id>/gradebook")
def api_gradebook(course_id):
    course = _find(_get_courses(), id=course_id)
    if not course:
        abort(404)
    assignments = _filter(_get_assignments(), course_id=course_id)
    submissions = _get_submissions()
    students = [_find(_get_users(), id=sid) for sid in course.get("enrolled_students", [])]
    students = [s for s in students if s is not None]

    rows = []
    for student in students:
        row = {
            "student_id": student["id"],
            "student_name": student["name"],
            "scores": {},
            "weighted_avg": _weighted_average(student["id"], course_id),
        }
        row["letter_grade"] = _letter_grade(row["weighted_avg"])
        for a in assignments:
            sub = next((s for s in submissions
                        if s["assignment_id"] == a["id"] and s["student_id"] == student["id"]), None)
            if sub:
                row["scores"][str(a["id"])] = {
                    "score": sub["score"],
                    "max_points": a["points"],
                    "pct": round(sub["score"] / a["points"] * 100, 1) if sub["score"] is not None else None
                }
        rows.append(row)
    return jsonify({
        "course_id": course_id,
        "course_title": course["title"],
        "grade_weights": course.get("grade_weights", {}),
        "assignments": [{"id": a["id"], "title": a["title"], "type": a["type"], "points": a["points"]}
                        for a in assignments],
        "students": rows
    })


@blueprint.route("/api/courses/<int:course_id>/grades/<int:student_id>")
def api_student_grade(course_id, student_id):
    course = _find(_get_courses(), id=course_id)
    if not course:
        abort(404)
    avg = _weighted_average(student_id, course_id)
    return jsonify({
        "student_id": student_id,
        "course_id": course_id,
        "weighted_average": avg,
        "letter_grade": _letter_grade(avg)
    })


@blueprint.route("/api/courses/<int:course_id>/discussions")
def api_course_discussions(course_id):
    discussions = [d for d in _get_discussions() if d["course_id"] == course_id]
    return jsonify(discussions)


@blueprint.route("/api/discussions/<int:disc_id>")
def api_discussion(disc_id):
    disc = _find(_get_discussions(), id=disc_id)
    if not disc:
        abort(404)
    return jsonify(disc)


@blueprint.route("/api/users")
def api_users():
    users = _get_users()
    role = request.args.get("role", "").strip()
    if role:
        users = [u for u in users if u["role"] == role]
    # Exclude passwords
    return jsonify([{k: v for k, v in u.items() if k != "password"} for u in users])


@blueprint.route("/api/users/<int:user_id>")
def api_user(user_id):
    user = _find(_get_users(), id=user_id)
    if not user:
        abort(404)
    return jsonify({k: v for k, v in user.items() if k != "password"})


@blueprint.route("/api/users/<int:user_id>/courses")
def api_user_courses(user_id):
    user = _find(_get_users(), id=user_id)
    if not user:
        abort(404)
    courses = _user_courses(user)
    return jsonify(courses)


@blueprint.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    user = _find(_get_users(), username=username)
    if not user or user.get("password") != password:
        return jsonify({"error": "Invalid credentials"}), 401
    session["user_id"] = user["id"]
    return jsonify({"user_id": user["id"], "username": user["username"], "role": user["role"]})


@blueprint.route("/api/courses/<int:course_id>/enroll", methods=["POST"])
def api_enroll(course_id):
    data = request.get_json(silent=True) or {}
    student_id = data.get("student_id")
    if student_id is None:
        return jsonify({"error": "student_id required"}), 400
    courses = _get_courses()
    course = _find(courses, id=course_id)
    if not course:
        abort(404)
    enrolled = course.setdefault("enrolled_students", [])
    if student_id in enrolled:
        return jsonify({"action": "already_enrolled", "student_id": student_id})
    enrolled.append(student_id)
    _save_json("courses.json", courses)
    return jsonify({"action": "enrolled", "student_id": student_id,
                    "total_enrolled": len(enrolled)})


@blueprint.route("/api/courses/<int:course_id>/unenroll", methods=["POST"])
def api_unenroll(course_id):
    data = request.get_json(silent=True) or {}
    student_id = data.get("student_id")
    if student_id is None:
        return jsonify({"error": "student_id required"}), 400
    courses = _get_courses()
    course = _find(courses, id=course_id)
    if not course:
        abort(404)
    enrolled = course.get("enrolled_students", [])
    if student_id not in enrolled:
        return jsonify({"action": "not_enrolled", "student_id": student_id})
    enrolled.remove(student_id)
    _save_json("courses.json", courses)
    return jsonify({"action": "unenrolled", "student_id": student_id,
                    "total_enrolled": len(enrolled)})


@blueprint.route("/api/courses/<int:course_id>/assignment/<int:assignment_id>/submit", methods=["POST"])
def api_submit_assignment(course_id, assignment_id):
    data = request.get_json(silent=True) or {}
    student_id = data.get("student_id")
    if student_id is None:
        return jsonify({"error": "student_id required"}), 400
    submissions = _get_submissions()
    new_id = max((s["id"] for s in submissions), default=0) + 1
    new_sub = {
        "id": new_id,
        "assignment_id": assignment_id,
        "student_id": student_id,
        "course_id": course_id,
        "submitted_at": datetime.now().isoformat(),
        "score": None,
        "status": "submitted",
        "feedback": ""
    }
    submissions.append(new_sub)
    _save_submissions(submissions)
    return jsonify({"action": "submitted", "submission_id": new_id})


@blueprint.route("/api/courses/<int:course_id>/assignment/<int:assignment_id>/grade", methods=["POST"])
def api_grade_submission(course_id, assignment_id):
    data = request.get_json(silent=True) or {}
    student_id = data.get("student_id")
    score = data.get("score")
    feedback = data.get("feedback", "")
    if student_id is None or score is None:
        return jsonify({"error": "student_id and score required"}), 400
    submissions = _get_submissions()
    sub = next((s for s in submissions
                if s["assignment_id"] == assignment_id and s["student_id"] == student_id), None)
    if not sub:
        return jsonify({"error": "No submission found"}), 404
    sub["score"] = score
    sub["status"] = "graded"
    sub["feedback"] = feedback
    _save_submissions(submissions)
    return jsonify({"action": "graded", "submission_id": sub["id"],
                    "score": score, "feedback": feedback})


@blueprint.route("/api/courses/<int:course_id>/discussions/new", methods=["POST"])
def api_new_discussion(course_id):
    data = request.get_json(silent=True) or {}
    author_id = data.get("author_id")
    title = data.get("title", "").strip()
    content = data.get("content", "").strip()
    if not author_id or not title or not content:
        return jsonify({"error": "author_id, title, and content required"}), 400
    discussions = _get_discussions()
    new_id = max((d["id"] for d in discussions), default=0) + 1
    new_disc = {
        "id": new_id,
        "course_id": course_id,
        "title": title,
        "author_id": author_id,
        "created_at": datetime.now().isoformat(),
        "content": content,
        "pinned": False,
        "replies": []
    }
    discussions.append(new_disc)
    _save_discussions(discussions)
    return jsonify({"action": "created", "discussion_id": new_id})


@blueprint.route("/api/discussions/<int:disc_id>/reply", methods=["POST"])
def api_reply_discussion(disc_id):
    data = request.get_json(silent=True) or {}
    author_id = data.get("author_id")
    content = data.get("content", "").strip()
    if not author_id or not content:
        return jsonify({"error": "author_id and content required"}), 400
    discussions = _get_discussions()
    disc = _find(discussions, id=disc_id)
    if not disc:
        abort(404)
    replies = disc.setdefault("replies", [])
    new_reply_id = max((r["id"] for r in replies), default=0) + 1
    replies.append({
        "id": new_reply_id,
        "author_id": author_id,
        "content": content,
        "created_at": datetime.now().isoformat()
    })
    _save_discussions(discussions)
    return jsonify({"action": "replied", "discussion_id": disc_id, "reply_id": new_reply_id})


@blueprint.route("/api/stats")
def api_stats():
    courses = _get_courses()
    users = _get_users()
    assignments = _get_assignments()
    submissions = _get_submissions()
    discussions = _get_discussions()
    return jsonify({
        "total_courses": len(courses),
        "total_users": len(users),
        "total_assignments": len(assignments),
        "total_submissions": len(submissions),
        "total_discussions": len(discussions),
        "instructors": len([u for u in users if u["role"] == "instructor"]),
        "students": len([u for u in users if u["role"] == "student"]),
        "departments": list(set(c.get("department", "") for c in courses)),
    })


@blueprint.route("/api/courses/<int:course_id>/stats")
def api_course_stats(course_id):
    course = _find(_get_courses(), id=course_id)
    if not course:
        abort(404)
    assignments = _filter(_get_assignments(), course_id=course_id)
    submissions = [s for s in _get_submissions() if s.get("course_id") == course_id]
    graded = [s for s in submissions if s["status"] == "graded" and s["score"] is not None]
    enrolled = len(course.get("enrolled_students", []))
    discussions = [d for d in _get_discussions() if d["course_id"] == course_id]
    total_replies = sum(len(d.get("replies", [])) for d in discussions)

    avg_score = None
    if graded:
        avg_score = round(sum(s["score"] for s in graded) / len(graded), 2)

    return jsonify({
        "course_id": course_id,
        "course_title": course["title"],
        "enrolled_count": enrolled,
        "assignment_count": len(assignments),
        "submission_count": len(submissions),
        "graded_count": len(graded),
        "average_score": avg_score,
        "discussion_count": len(discussions),
        "total_replies": total_replies,
    })


@blueprint.route("/api/export/gradebook/<int:course_id>")
def api_export_gradebook(course_id):
    """Export gradebook as CSV."""
    course = _find(_get_courses(), id=course_id)
    if not course:
        abort(404)
    assignments = _filter(_get_assignments(), course_id=course_id)
    submissions = _get_submissions()
    students = [_find(_get_users(), id=sid) for sid in course.get("enrolled_students", [])]
    students = [s for s in students if s is not None]

    headers = ["Student ID", "Student Name"] + [a["title"] for a in assignments] + ["Weighted Avg", "Letter Grade"]
    lines = [",".join(f'"{h}"' for h in headers)]

    for student in students:
        row = [str(student["id"]), f'"{student["name"]}"']
        for a in assignments:
            sub = next((s for s in submissions
                        if s["assignment_id"] == a["id"] and s["student_id"] == student["id"]), None)
            if sub and sub["score"] is not None:
                row.append(str(sub["score"]))
            else:
                row.append("")
        avg = _weighted_average(student["id"], course_id)
        row.append(str(avg) if avg is not None else "")
        row.append(_letter_grade(avg))
        lines.append(",".join(row))

    return Response("\n".join(lines), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=gradebook_{course['code']}.csv"})
