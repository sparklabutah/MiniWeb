"""Project Management / Issue Tracking — Jira-style project management app.

Meridian Systems internal project tracker. Supports multiple projects,
Kanban board views, sprints, backlog management, and issue CRUD with
filtering by project, status, assignee, type, and priority.
"""
import csv
import io
import pathlib
from collections import Counter
from datetime import datetime

from flask import (
    Blueprint, Response, abort, jsonify, redirect, render_template,
    request, session, url_for,
)

from app import db
from app.events import emit
from app.handlers.email_handler import _add_email

SITE = "project-mgmt-issue-tracking"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "project-mgmt-issue-tracking",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _load_projects():
    return [_ensure_project_key(_remap_key(p)) for p in db.query(SITE, "projects")]


_PROJECT_PREFIXES = {1: "MF", 2: "MV", 3: "ML", 4: "IT", 5: "WR",
                     6: "MC", 7: "MP", 8: "MG", 9: "MD"}


def _remap_key(item):
    """Remap 'key_' -> 'key' since 'key' is a SQL reserved word."""
    if "key_" in item:
        item["key"] = item.pop("key_")
    return item


def _ensure_project_key(project):
    """Ensure project has its prefix key (MF, MV, etc.)."""
    if not project.get("key"):
        project["key"] = _PROJECT_PREFIXES.get(project["id"], "UNK")
    return project


def _ensure_issue_key(issue):
    """Ensure issue has a key like MF-101."""
    if not issue.get("key"):
        prefix = _PROJECT_PREFIXES.get(issue.get("project_id", 0), "UNK")
        issue["key"] = f"{prefix}-{100 + issue['id']}"
    return issue


def _load_issues():
    return [_ensure_issue_key(_remap_key(i)) for i in db.query(SITE, "issues")]


def _save_issues(issues):
    db.save_collection(SITE, "issues", issues)


def _lbl(v):
    """Human label for a status/priority/type value."""
    return str(v or "None").replace("_", " ").title()


def _log_activity(issue, actor_id, text):
    """Append a change event to the issue's activity timeline."""
    activity = issue.setdefault("activity", [])
    activity.append({
        "id": len(activity) + 1,
        "actor_id": actor_id,
        "text": text,
        "at": datetime.now().isoformat(),
    })


def _load_comments():
    return db.query(SITE, "comments")


def _save_comments(comments):
    db.save_collection(SITE, "comments", comments)


def _load_sprints():
    return db.query(SITE, "sprints")


def _load_users():
    return db.query(SITE, "users")


def _get_user(user_id):
    return db.get_item(SITE, "users", user_id)


def _get_project(project_id):
    p = db.get_item(SITE, "projects", project_id)
    return _ensure_project_key(_remap_key(p)) if p else None


def _next_issue_id():
    issues = _load_issues()
    return max((i["id"] for i in issues), default=0) + 1


def _next_comment_id():
    comments = _load_comments()
    return max((c["id"] for c in comments), default=0) + 1


def _next_issue_key(project_id):
    """Generate the next issue key like MF-113 for a project."""
    project = _get_project(project_id)
    if not project:
        return "UNK-1"
    prefix = project["key"]
    issues = _load_issues()
    project_issues = [i for i in issues if i["project_id"] == project_id]
    if not project_issues:
        return f"{prefix}-1"
    # Extract numeric part from keys
    max_num = 0
    for issue in project_issues:
        parts = issue["key"].split("-")
        if len(parts) == 2:
            try:
                num = int(parts[1])
                if num > max_num:
                    max_num = num
            except ValueError:
                pass
    return f"{prefix}-{max_num + 1}"


def _user_map():
    """Return {user_id: user_dict} for quick lookups."""
    return {u["id"]: u for u in _load_users()}


def _project_map():
    """Return {project_id: project_dict} for quick lookups."""
    return {p["id"]: p for p in _load_projects()}


# ---------------------------------------------------------------------------
# Filter / search helpers
# ---------------------------------------------------------------------------

STATUS_ORDER = ["open", "in_progress", "review", "done", "closed"]
PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _filter_issues(issues, project_id=None, status=None, assignee_id=None,
                   type_=None, priority=None, sprint=None, label=None, q=None,
                   date_from=None, date_to=None):
    results = list(issues)
    if project_id is not None:
        results = [i for i in results if i["project_id"] == project_id]
    if status:
        results = [i for i in results if i["status"] == status]
    if assignee_id is not None:
        results = [i for i in results if i.get("assignee_id") == assignee_id]
    if type_:
        results = [i for i in results if i["type"] == type_]
    if priority:
        results = [i for i in results if i["priority"] == priority]
    if sprint is not None:
        results = [i for i in results if i.get("sprint") == sprint]
    if label:
        results = [i for i in results if label in i.get("labels", [])]
    if date_from:
        results = [i for i in results if i.get("created_at", "") >= date_from]
    if date_to:
        # date_to is inclusive: compare against date_to + end-of-day
        to_end = date_to if "T" in date_to else date_to + "T23:59:59"
        results = [i for i in results if i.get("created_at", "") <= to_end]
    if q:
        ql = q.lower()
        results = [i for i in results
                   if ql in i["title"].lower()
                   or ql in i.get("description", "").lower()
                   or ql in i["key"].lower()]
    return results


def _semantic_search_issues(issues, query):
    """Simple keyword-overlap semantic search over issues."""
    if not query:
        return issues
    terms = query.lower().split()
    scored = []
    for issue in issues:
        text = " ".join([
            issue.get("title", ""),
            issue.get("description", ""),
            " ".join(issue.get("labels", [])),
            issue.get("key", ""),
        ]).lower()
        score = sum(1 for t in terms if t in text)
        if score > 0:
            scored.append((score, issue))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [s[1] for s in scored]


def _sort_issues(issues, sort_key="priority"):
    if sort_key == "priority":
        issues.sort(key=lambda i: PRIORITY_ORDER.get(i.get("priority", "medium"), 2))
    elif sort_key == "created":
        issues.sort(key=lambda i: i.get("created_at", ""), reverse=True)
    elif sort_key == "updated":
        issues.sort(key=lambda i: i.get("updated_at", ""), reverse=True)
    elif sort_key == "status":
        issues.sort(key=lambda i: STATUS_ORDER.index(i["status"])
                    if i["status"] in STATUS_ORDER else 99)
    elif sort_key == "key":
        issues.sort(key=lambda i: i.get("key", ""))
    elif sort_key == "story_points":
        issues.sort(key=lambda i: i.get("story_points") or 0, reverse=True)
    return issues


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.context_processor
def _inject_chrome():
    """Sidebar project list + current user for the shared tracker shell."""
    try:
        if "/api/" in request.path:
            return {}
        uid = session.get("user_id")
        user = _get_user(uid) if uid else None
        return {"chrome_user": user, "sidebar_projects": _load_projects()[:12]}
    except Exception:
        return {"chrome_user": None, "sidebar_projects": []}


@blueprint.route("/")
def index():
    """Dashboard — overview of all projects with issue counts and recent activity."""
    projects = _load_projects()
    issues = _load_issues()
    users = _load_users()
    user_lookup = _user_map()

    project_stats = []
    for p in projects:
        p_issues = [i for i in issues if i["project_id"] == p["id"]]
        open_count = sum(1 for i in p_issues if i["status"] in ("open", "in_progress", "review"))
        done_count = sum(1 for i in p_issues if i["status"] in ("done", "closed"))
        critical_count = sum(1 for i in p_issues if i["priority"] == "critical" and i["status"] not in ("done", "closed"))
        owner = user_lookup.get(p["owner_id"])
        project_stats.append({
            "project": p,
            "total": len(p_issues),
            "open": open_count,
            "done": done_count,
            "critical": critical_count,
            "owner": owner,
        })

    # Recent issues (last 10 updated)
    recent = sorted(issues, key=lambda i: i.get("updated_at", ""), reverse=True)[:10]

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    # My issues (assigned to current user)
    my_issues = []
    if user:
        my_issues = [i for i in issues if i.get("assignee_id") == user["id"]
                     and i["status"] not in ("done", "closed")]
        my_issues = _sort_issues(my_issues, "priority")

    def _cnt(pred):
        return sum(1 for i in issues if pred(i))
    kpis = {
        "total": len(issues),
        "open": _cnt(lambda i: i["status"] == "open"),
        "in_progress": _cnt(lambda i: i["status"] == "in_progress"),
        "review": _cnt(lambda i: i["status"] == "review"),
        "done": _cnt(lambda i: i["status"] in ("done", "closed")),
        "critical": _cnt(lambda i: i["priority"] == "critical" and i["status"] not in ("done", "closed")),
        "my_open": len(my_issues),
    }

    return render_template("project-mgmt-issue-tracking/index.html",
                           project_stats=project_stats,
                           recent_issues=recent,
                           my_issues=my_issues,
                           kpis=kpis,
                           user=user,
                           user_lookup=user_lookup,
                           project_lookup=_project_map())


@blueprint.route("/project/<int:project_id>")
def project_board(project_id):
    """Kanban board view for a single project."""
    project = _get_project(project_id)
    if not project:
        abort(404)
    issues = _load_issues()
    p_issues = [i for i in issues if i["project_id"] == project_id]
    user_lookup = _user_map()

    # Filter by sprint if specified
    sprint_id = request.args.get("sprint", type=int)
    q = request.args.get("q", "").strip()
    assignee = request.args.get("assignee", type=int)
    type_filter = request.args.get("type", "").strip()
    priority_filter = request.args.get("priority", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    filtered = list(p_issues)
    if sprint_id:
        filtered = [i for i in filtered if i.get("sprint") == sprint_id]
    if q:
        ql = q.lower()
        filtered = [i for i in filtered
                    if ql in i["title"].lower() or ql in i["key"].lower()]
    if assignee:
        filtered = [i for i in filtered if i.get("assignee_id") == assignee]
    if type_filter:
        filtered = [i for i in filtered if i["type"] == type_filter]
    if priority_filter:
        filtered = [i for i in filtered if i["priority"] == priority_filter]
    if date_from or date_to:
        filtered = _filter_issues(filtered, date_from=date_from or None,
                                  date_to=date_to or None)

    # Group by status for board columns
    columns = {}
    for status in STATUS_ORDER:
        col_issues = [i for i in filtered if i["status"] == status]
        col_issues = _sort_issues(col_issues, "priority")
        columns[status] = col_issues

    # Sprints for this project
    sprints = [s for s in _load_sprints() if s["project_id"] == project_id]

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    users = _load_users()

    return render_template("project-mgmt-issue-tracking/project.html",
                           project=project,
                           columns=columns,
                           status_order=STATUS_ORDER,
                           sprints=sprints,
                           user=user,
                           users=users,
                           user_lookup=user_lookup,
                           sprint_id=sprint_id,
                           q=q,
                           assignee=assignee,
                           type_filter=type_filter,
                           priority_filter=priority_filter,
                           date_from=date_from,
                           date_to=date_to)


@blueprint.route("/issue/<int:issue_id>")
def issue_detail(issue_id):
    """Single issue detail page with comments."""
    issue = db.get_item(SITE, "issues", issue_id)
    if issue:
        _ensure_issue_key(_remap_key(issue))
    if not issue:
        abort(404)
    issue_comments = db.query(SITE, "comments", where={"issue_id": issue_id}, sort="created_at")
    user_lookup = _user_map()
    project = _get_project(issue["project_id"])
    assignee = user_lookup.get(issue.get("assignee_id"))
    reporter = user_lookup.get(issue.get("reporter_id"))
    users = _load_users()

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    # Sprint info
    sprint = None
    if issue.get("sprint"):
        sprints = _load_sprints()
        sprint = next((s for s in sprints if s["id"] == issue["sprint"]), None)

    return render_template("project-mgmt-issue-tracking/issue.html",
                           issue=issue,
                           comments=issue_comments,
                           project=project,
                           assignee=assignee,
                           reporter=reporter,
                           sprint=sprint,
                           user=user,
                           users=users,
                           user_lookup=user_lookup)


@blueprint.route("/create-issue")
def create_issue_page():
    """Form to create a new issue."""
    projects = _load_projects()
    users = _load_users()
    sprints = _load_sprints()
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    project_id = request.args.get("project", type=int)
    return render_template("project-mgmt-issue-tracking/create_issue.html",
                           projects=projects,
                           users=users,
                           sprints=sprints,
                           user=user,
                           selected_project=project_id)


@blueprint.route("/sprints")
def sprints_page():
    """All sprints overview."""
    sprints = _load_sprints()
    issues = _load_issues()
    user_lookup = _user_map()
    project_lookup = _project_map()

    sprint_data = []
    for s in sprints:
        s_issues = [i for i in issues if i.get("sprint") == s["id"]]
        done_count = sum(1 for i in s_issues if i["status"] in ("done", "closed"))
        total_points = sum(i.get("story_points", 0) or 0 for i in s_issues)
        done_points = sum((i.get("story_points", 0) or 0) for i in s_issues
                         if i["status"] in ("done", "closed"))
        sprint_data.append({
            "sprint": s,
            "project": project_lookup.get(s["project_id"]),
            "total_issues": len(s_issues),
            "done_issues": done_count,
            "total_points": total_points,
            "done_points": done_points,
        })

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template("project-mgmt-issue-tracking/sprints.html",
                           sprint_data=sprint_data,
                           user=user)


@blueprint.route("/sprint/<int:sprint_id>")
def sprint_detail(sprint_id):
    """Sprint detail — issues in this sprint with board view."""
    sprints = _load_sprints()
    sprint = next((s for s in sprints if s["id"] == sprint_id), None)
    if not sprint:
        abort(404)
    issues = _load_issues()
    sprint_issues = [i for i in issues if i.get("sprint") == sprint_id]
    user_lookup = _user_map()
    project = _get_project(sprint["project_id"])

    columns = {}
    for status in STATUS_ORDER:
        col_issues = [i for i in sprint_issues if i["status"] == status]
        col_issues = _sort_issues(col_issues, "priority")
        columns[status] = col_issues

    total_points = sum(i.get("story_points", 0) or 0 for i in sprint_issues)
    done_points = sum((i.get("story_points", 0) or 0) for i in sprint_issues
                     if i["status"] in ("done", "closed"))

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template("project-mgmt-issue-tracking/sprint_detail.html",
                           sprint=sprint,
                           project=project,
                           columns=columns,
                           status_order=STATUS_ORDER,
                           total_points=total_points,
                           done_points=done_points,
                           user=user,
                           user_lookup=user_lookup)


@blueprint.route("/backlog")
def backlog():
    """Backlog — issues not assigned to any sprint."""
    issues = _load_issues()
    backlog_issues = [i for i in issues if not i.get("sprint")
                      and i["status"] not in ("done", "closed")]

    # Apply filters
    project_id = request.args.get("project", type=int)
    priority = request.args.get("priority", "").strip()
    type_filter = request.args.get("type", "").strip()
    q = request.args.get("q", "").strip()

    if project_id:
        backlog_issues = [i for i in backlog_issues if i["project_id"] == project_id]
    if priority:
        backlog_issues = [i for i in backlog_issues if i["priority"] == priority]
    if type_filter:
        backlog_issues = [i for i in backlog_issues if i["type"] == type_filter]
    if q:
        ql = q.lower()
        backlog_issues = [i for i in backlog_issues
                          if ql in i["title"].lower() or ql in i["key"].lower()]

    backlog_issues = _sort_issues(backlog_issues, "priority")
    user_lookup = _user_map()
    project_lookup = _project_map()
    projects = _load_projects()
    users = _load_users()

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template("project-mgmt-issue-tracking/backlog.html",
                           issues=backlog_issues,
                           projects=projects,
                           users=users,
                           user=user,
                           user_lookup=user_lookup,
                           project_lookup=project_lookup,
                           project_id=project_id,
                           priority=priority,
                           type_filter=type_filter,
                           q=q)


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("project-mgmt-issue-tracking/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return render_template("project-mgmt-issue-tracking/login.html",
                               error="Invalid username or password")
    session["user_id"] = user["id"]
    emit("signup", user_id=user["id"], site_name="project-mgmt-issue-tracking", username=request.form.get("username", ""), password=request.form.get("password", ""), email="")
    return redirect(url_for("project-mgmt-issue-tracking.index"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("project-mgmt-issue-tracking.login_page"))


# ---------------------------------------------------------------------------
# HTML form actions (non-JS fallback)
# ---------------------------------------------------------------------------

@blueprint.route("/create-issue", methods=["POST"])
def form_create_issue():
    """Create issue via HTML form POST."""
    title = request.form.get("title", "").strip()
    if not title:
        return "Title is required", 400
    project_id = request.form.get("project_id", type=int)
    if not project_id:
        return "Project is required", 400

    assignee_id = request.form.get("assignee_id", type=int)
    sprint_val = request.form.get("sprint", type=int)

    issue = {
        "id": _next_issue_id(),
        "project_id": project_id,
        "key": _next_issue_key(project_id),
        "title": title,
        "description": request.form.get("description", ""),
        "type": request.form.get("type", "task"),
        "status": "open",
        "priority": request.form.get("priority", "medium"),
        "assignee_id": assignee_id if assignee_id else None,
        "reporter_id": session.get("user_id", 1),
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "labels": [l.strip() for l in request.form.get("labels", "").split(",") if l.strip()],
        "story_points": request.form.get("story_points", type=int),
        "sprint": sprint_val if sprint_val else None,
    }
    issues = _load_issues()
    issues.append(issue)
    _save_issues(issues)
    if issue.get("assignee_id"):
        emit("booking", user_id=issue["assignee_id"], title=f"Issue assigned: {issue['title'][:40]}", start=datetime.now().strftime("%Y-%m-%d"), location="")
        emit("message", from_user_id=issue["reporter_id"], to_user_id=issue["assignee_id"], text=f"You've been assigned: {issue['key']} - {issue['title']}", source_site="project-mgmt")
    return redirect(url_for("project-mgmt-issue-tracking.issue_detail",
                            issue_id=issue["id"]))


@blueprint.route("/issue/<int:issue_id>/edit", methods=["POST"])
def form_edit_issue(issue_id):
    """Edit issue fields via HTML form POST."""
    issues = _load_issues()
    issue = next((i for i in issues if i["id"] == issue_id), None)
    if not issue:
        abort(404)

    # Snapshot the fields we track for the activity log.
    um = _user_map()
    old = {
        "status": issue.get("status"), "priority": issue.get("priority"),
        "type": issue.get("type"), "assignee_id": issue.get("assignee_id"),
        "reporter_id": issue.get("reporter_id"),
    }

    for field in ["title", "description", "type", "status", "priority"]:
        val = request.form.get(field)
        if val is not None and val.strip():
            issue[field] = val.strip()

    assignee_id = request.form.get("assignee_id")
    if assignee_id is not None:
        issue["assignee_id"] = int(assignee_id) if assignee_id else None

    reporter_id = request.form.get("reporter_id")
    if reporter_id is not None:
        issue["reporter_id"] = int(reporter_id) if reporter_id else None

    # Record change events for the notable fields.
    actor = session.get("user_id")
    def _uname(uid):
        u = um.get(uid)
        return u["name"] if u else "Unassigned"
    if issue.get("assignee_id") != old["assignee_id"]:
        if issue.get("assignee_id"):
            _log_activity(issue, actor, "assigned this to %s" % _uname(issue["assignee_id"]))
        else:
            _log_activity(issue, actor, "removed the assignee")
    if issue.get("reporter_id") != old["reporter_id"]:
        _log_activity(issue, actor, "changed reporter to %s" % _uname(issue.get("reporter_id")))
    if issue.get("status") != old["status"]:
        _log_activity(issue, actor, "changed status from %s to %s" % (_lbl(old["status"]), _lbl(issue.get("status"))))
    if issue.get("priority") != old["priority"]:
        _log_activity(issue, actor, "changed priority from %s to %s" % (_lbl(old["priority"]), _lbl(issue.get("priority"))))
    if issue.get("type") != old["type"]:
        _log_activity(issue, actor, "changed type from %s to %s" % (_lbl(old["type"]), _lbl(issue.get("type"))))

    sprint_val = request.form.get("sprint")
    if sprint_val is not None:
        issue["sprint"] = int(sprint_val) if sprint_val else None

    sp = request.form.get("story_points")
    if sp is not None:
        issue["story_points"] = int(sp) if sp else None

    labels = request.form.get("labels")
    if labels is not None:
        issue["labels"] = [l.strip() for l in labels.split(",") if l.strip()]

    issue["updated_at"] = datetime.now().isoformat()
    _save_issues(issues)
    if issue.get("assignee_id"):
        _add_email(issue["assignee_id"], "noreply@project-mgmt.lakeport.local",
                   "Issue assigned to you",
                   f'Issue "{issue["title"]}" ({issue["key"]}) has been assigned to you.')
    return redirect(url_for("project-mgmt-issue-tracking.issue_detail",
                            issue_id=issue_id))


@blueprint.route("/backlog/save", methods=["POST"])
def form_backlog_save():
    """Persist inline cell edits (and an optional new issue) from the backlog grid.

    Editable cells are POSTed as ``cell_<issue_id>_<field>`` and an optional new
    issue via the ``new_*`` fields. Everything travels in the request body so the
    mutation is captured by /_admin/log and is gradeable. Supports the
    edit_by_cell (data-grid cell editing) + create_by_form macros.
    """
    issues = _load_issues()
    by_id = {i["id"]: i for i in issues}
    editable = {"title", "type", "status", "priority", "assignee_id", "story_points"}
    int_fields = {"assignee_id", "story_points"}
    changed = False

    for key, value in request.form.items():
        if not key.startswith("cell_"):
            continue
        parts = key.split("_", 2)  # ["cell", "<id>", "<field>"]
        if len(parts) != 3:
            continue
        _, sid_str, field = parts
        if field not in editable:
            continue
        try:
            iid = int(sid_str)
        except ValueError:
            continue
        issue = by_id.get(iid)
        if not issue:
            continue
        val = value.strip()
        new_val = (int(val) if val else None) if field in int_fields else val
        if issue.get(field) != new_val:
            issue[field] = new_val
            issue["updated_at"] = datetime.now().isoformat()
            changed = True

    # Optional new issue added via the "+ Add row" button.
    new_title = request.form.get("new_title", "").strip()
    new_project_id = request.form.get("new_project_id", type=int)
    if new_title and new_project_id:
        assignee_id = request.form.get("new_assignee_id", type=int)
        sp = request.form.get("new_story_points", type=int)
        issue = {
            "id": db.next_id(SITE, "issues"),
            "project_id": new_project_id,
            "key": _next_issue_key(new_project_id),
            "title": new_title,
            "description": "",
            "type": request.form.get("new_type", "task"),
            "status": request.form.get("new_status", "open"),
            "priority": request.form.get("new_priority", "medium"),
            "assignee_id": assignee_id if assignee_id else None,
            "reporter_id": session.get("user_id", 1),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "labels": [],
            "story_points": sp if sp else None,
            "sprint": None,
        }
        issues.append(issue)
        changed = True

    if changed:
        _save_issues(issues)
    return redirect(url_for("project-mgmt-issue-tracking.backlog"))


@blueprint.route("/issue/<int:issue_id>/comment", methods=["POST"])
def form_add_comment(issue_id):
    """Add comment via HTML form POST."""
    issues = _load_issues()
    issue = next((i for i in issues if i["id"] == issue_id), None)
    if not issue:
        abort(404)
    text = request.form.get("text", "").strip()
    if not text:
        return redirect(url_for("project-mgmt-issue-tracking.issue_detail",
                                issue_id=issue_id))
    comment = {
        "id": _next_comment_id(),
        "issue_id": issue_id,
        "user_id": session.get("user_id", 1),
        "text": text,
        "created_at": datetime.now().isoformat(),
    }
    comments = _load_comments()
    comments.append(comment)
    _save_comments(comments)

    # Update issue timestamp
    issue["updated_at"] = datetime.now().isoformat()
    _save_issues(issues)

    return redirect(url_for("project-mgmt-issue-tracking.issue_detail",
                            issue_id=issue_id))


@blueprint.route("/issue/<int:issue_id>/delete", methods=["POST"])
def form_delete_issue(issue_id):
    """Delete issue via HTML form POST."""
    issues = _load_issues()
    issue = next((i for i in issues if i["id"] == issue_id), None)
    if not issue:
        abort(404)
    project_id = issue["project_id"]
    issues = [i for i in issues if i["id"] != issue_id]
    _save_issues(issues)
    # Also delete associated comments
    comments = _load_comments()
    comments = [c for c in comments if c["issue_id"] != issue_id]
    _save_comments(comments)
    return redirect(url_for("project-mgmt-issue-tracking.project_board",
                            project_id=project_id))


@blueprint.route("/issue/<int:issue_id>/transition", methods=["POST"])
def form_transition_issue(issue_id):
    """Transition issue status via HTML form POST."""
    issues = _load_issues()
    issue = next((i for i in issues if i["id"] == issue_id), None)
    if not issue:
        abort(404)
    new_status = request.form.get("status", "").strip()
    old_status = issue.get("status")
    if new_status and new_status in STATUS_ORDER and new_status != old_status:
        issue["status"] = new_status
        issue["updated_at"] = datetime.now().isoformat()
        _log_activity(issue, session.get("user_id"),
                      "changed status from %s to %s" % (_lbl(old_status), _lbl(new_status)))
        _save_issues(issues)
    return redirect(url_for("project-mgmt-issue-tracking.issue_detail",
                            issue_id=issue_id))


# ---------------------------------------------------------------------------
# API routes — read
# ---------------------------------------------------------------------------

@blueprint.route("/api/projects")
def api_projects():
    projects = _load_projects()
    return jsonify(projects)


@blueprint.route("/api/projects/<int:project_id>")
def api_project(project_id):
    project = _get_project(project_id)
    if not project:
        abort(404)
    return jsonify(project)


@blueprint.route("/api/issues", methods=["GET"])
def api_issues():
    issues = _load_issues()
    project_id = request.args.get("project_id", type=int)
    status = request.args.get("status", "").strip() or None
    assignee_id = request.args.get("assignee_id", type=int)
    type_ = request.args.get("type", "").strip() or None
    priority = request.args.get("priority", "").strip() or None
    sprint = request.args.get("sprint", type=int)
    label = request.args.get("label", "").strip() or None
    q = request.args.get("q", "").strip() or None
    date_from = request.args.get("date_from", "").strip() or None
    date_to = request.args.get("date_to", "").strip() or None
    sort = request.args.get("sort", "priority").strip()
    limit = request.args.get("limit", type=int)

    results = _filter_issues(issues, project_id=project_id, status=status,
                             assignee_id=assignee_id, type_=type_,
                             priority=priority, sprint=sprint, label=label, q=q,
                             date_from=date_from, date_to=date_to)
    results = _sort_issues(results, sort)
    if limit:
        results = results[:limit]
    return jsonify(results)


@blueprint.route("/api/issues/<int:issue_id>", methods=["GET"])
def api_issue(issue_id):
    issue = db.get_item(SITE, "issues", issue_id)
    if issue:
        _ensure_issue_key(_remap_key(issue))
    if not issue:
        abort(404)
    return jsonify(issue)


@blueprint.route("/api/issues/<int:issue_id>/comments", methods=["GET"])
def api_issue_comments(issue_id):
    issue_comments = db.query(SITE, "comments", where={"issue_id": issue_id}, sort="created_at")
    return jsonify(issue_comments)


@blueprint.route("/api/sprints")
def api_sprints():
    project_id = request.args.get("project_id", type=int)
    where_f = {}
    if project_id:
        where_f["project_id"] = project_id
    sprints = db.query(SITE, "sprints", where=where_f if where_f else None)
    return jsonify(sprints)


@blueprint.route("/api/sprints/<int:sprint_id>")
def api_sprint(sprint_id):
    sprint = db.get_item(SITE, "sprints", sprint_id)
    if not sprint:
        abort(404)
    return jsonify(sprint)


@blueprint.route("/api/stats")
def api_stats():
    issues = _load_issues()
    projects = _load_projects()

    # Optional filters
    project_id = request.args.get("project_id", type=int)
    if project_id:
        issues = [i for i in issues if i["project_id"] == project_id]

    status_counts = dict(Counter(i["status"] for i in issues))
    type_counts = dict(Counter(i["type"] for i in issues))
    priority_counts = dict(Counter(i["priority"] for i in issues))
    assignee_counts = dict(Counter(i.get("assignee_id") for i in issues if i.get("assignee_id")))

    total_points = sum(i.get("story_points", 0) or 0 for i in issues)
    done_points = sum((i.get("story_points", 0) or 0) for i in issues
                     if i["status"] in ("done", "closed"))

    return jsonify({
        "total_issues": len(issues),
        "total_projects": len(projects),
        "status_counts": status_counts,
        "type_counts": type_counts,
        "priority_counts": priority_counts,
        "assignee_counts": assignee_counts,
        "total_story_points": total_points,
        "completed_story_points": done_points,
    })


# ---------------------------------------------------------------------------
# API routes — write
# ---------------------------------------------------------------------------

@blueprint.route("/api/issues", methods=["POST"])
def api_create_issue():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title required"}), 400
    project_id = data.get("project_id")
    if not project_id:
        return jsonify({"error": "project_id required"}), 400

    assignee_id = data.get("assignee_id")
    sprint_val = data.get("sprint")

    issue = {
        "id": _next_issue_id(),
        "project_id": project_id,
        "key": _next_issue_key(project_id),
        "title": title,
        "description": data.get("description", ""),
        "type": data.get("type", "task"),
        "status": data.get("status", "open"),
        "priority": data.get("priority", "medium"),
        "assignee_id": assignee_id,
        "reporter_id": data.get("reporter_id", session.get("user_id", 1)),
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "labels": data.get("labels", []),
        "story_points": data.get("story_points"),
        "sprint": sprint_val,
    }
    issues = _load_issues()
    issues.append(issue)
    _save_issues(issues)
    return jsonify(issue), 201


@blueprint.route("/api/issues/<int:issue_id>", methods=["PUT"])
def api_update_issue(issue_id):
    data = request.get_json(silent=True) or {}
    issues = _load_issues()
    issue = next((i for i in issues if i["id"] == issue_id), None)
    if not issue:
        abort(404)

    for field in ["title", "description", "type", "status", "priority",
                  "assignee_id", "labels", "story_points", "sprint"]:
        if field in data:
            issue[field] = data[field]

    issue["updated_at"] = datetime.now().isoformat()
    _save_issues(issues)
    return jsonify(issue)


@blueprint.route("/api/issues/<int:issue_id>", methods=["DELETE"])
def api_delete_issue(issue_id):
    issues = _load_issues()
    issue = next((i for i in issues if i["id"] == issue_id), None)
    if not issue:
        abort(404)
    issues = [i for i in issues if i["id"] != issue_id]
    _save_issues(issues)
    # Also delete associated comments
    comments = _load_comments()
    comments = [c for c in comments if c["issue_id"] != issue_id]
    _save_comments(comments)
    return jsonify({"deleted": issue_id, "remaining": len(issues)})


@blueprint.route("/api/issues/<int:issue_id>/comments", methods=["POST"])
def api_create_comment(issue_id):
    issues = _load_issues()
    issue = next((i for i in issues if i["id"] == issue_id), None)
    if not issue:
        abort(404)
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "text required"}), 400

    comment = {
        "id": _next_comment_id(),
        "issue_id": issue_id,
        "user_id": data.get("user_id", session.get("user_id", 1)),
        "text": text,
        "created_at": datetime.now().isoformat(),
    }
    comments = _load_comments()
    comments.append(comment)
    _save_comments(comments)

    # Update issue timestamp
    issue["updated_at"] = datetime.now().isoformat()
    _save_issues(issues)

    return jsonify(comment), 201


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


@blueprint.route("/api/users")
def api_users():
    users = _load_users()
    return jsonify([{k: v for k, v in u.items() if k != "password"} for u in users])


@blueprint.route("/api/users/<int:user_id>")
def api_user(user_id):
    user = db.get_item(SITE, "users", user_id)
    if not user:
        abort(404)
    return jsonify({k: v for k, v in user.items() if k != "password"})


# ---------------------------------------------------------------------------
# API routes — semantic search
# ---------------------------------------------------------------------------

@blueprint.route("/api/issues/search")
def api_search_issues():
    """Keyword search across issue title, description, labels, key."""
    issues = _load_issues()
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify(issues)
    results = _semantic_search_issues(issues, q)
    limit = request.args.get("limit", type=int)
    if limit:
        results = results[:limit]
    return jsonify(results)


@blueprint.route("/api/issues/by-key/<key>")
def api_issue_by_key(key):
    """Lookup an issue by its project key (e.g., MF-101)."""
    key = key.upper()
    # First try stored key_ column
    results = db.query(SITE, "issues", where={"key_": key}, limit=1)
    if results:
        issue = _ensure_issue_key(_remap_key(results[0]))
        return jsonify(issue)
    # Fallback: parse computed key PREFIX-NNN where NNN = 100 + id
    parts = key.split("-")
    if len(parts) == 2:
        prefix_to_project = {v: k for k, v in _PROJECT_PREFIXES.items()}
        project_id = prefix_to_project.get(parts[0])
        try:
            issue_id = int(parts[1]) - 100
        except ValueError:
            issue_id = None
        if project_id and issue_id:
            issue = db.get_item(SITE, "issues", issue_id)
            if issue and issue.get("project_id") == project_id:
                _ensure_issue_key(_remap_key(issue))
                return jsonify(issue)
    abort(404)


# ---------------------------------------------------------------------------
# API routes — export
# ---------------------------------------------------------------------------

@blueprint.route("/api/export")
def api_export():
    """Export issues as CSV or JSON.

    Query params:
        format: csv|json (default json)
        project_id: filter by project
        status: filter by status
        sprint: filter by sprint
    """
    issues = _load_issues()
    project_id = request.args.get("project_id", type=int)
    status = request.args.get("status", "").strip() or None
    sprint = request.args.get("sprint", type=int)
    fmt = request.args.get("format", "json").strip().lower()

    results = _filter_issues(issues, project_id=project_id, status=status,
                             sprint=sprint)

    if fmt == "csv":
        output = io.StringIO()
        fields = ["id", "key", "project_id", "title", "type", "status",
                  "priority", "assignee_id", "reporter_id", "story_points",
                  "sprint", "created_at", "updated_at"]
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for issue in results:
            writer.writerow(issue)
        return Response(output.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=issues.csv"})

    return jsonify(results)


# ---------------------------------------------------------------------------
# API routes — watch / follow toggle
# ---------------------------------------------------------------------------

def _load_watchers():
    rows = db.query(SITE, "watchers")
    return rows[0] if rows else {}


def _save_watchers(watchers):
    db.save_collection(SITE, "watchers", [watchers])


@blueprint.route("/api/issues/<int:issue_id>/watch", methods=["POST"])
def api_toggle_watch(issue_id):
    """Toggle watch/follow on an issue for the current or specified user."""
    issues = _load_issues()
    issue = next((i for i in issues if i["id"] == issue_id), None)
    if not issue:
        abort(404)
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id", session.get("user_id", 1))
    watchers = _load_watchers()
    key = str(issue_id)
    if key not in watchers:
        watchers[key] = []
    if user_id in watchers[key]:
        watchers[key].remove(user_id)
        action = "unwatched"
    else:
        watchers[key].append(user_id)
        action = "watched"
    _save_watchers(watchers)
    return jsonify({"issue_id": issue_id, "user_id": user_id,
                    "action": action, "watchers": watchers[key]})


@blueprint.route("/api/issues/<int:issue_id>/watchers")
def api_issue_watchers(issue_id):
    """Get list of user IDs watching an issue."""
    watchers = _load_watchers()
    key = str(issue_id)
    return jsonify({"issue_id": issue_id, "watchers": watchers.get(key, [])})


# ---------------------------------------------------------------------------
# API routes — batch / bulk operations
# ---------------------------------------------------------------------------

@blueprint.route("/api/issues/bulk-update", methods=["POST"])
def api_bulk_update():
    """Update multiple issues at once (select_from_table support).

    Expects JSON: {"issue_ids": [1,2,3], "updates": {"status": "done"}}
    """
    data = request.get_json(silent=True) or {}
    issue_ids = data.get("issue_ids", [])
    updates = data.get("updates", {})
    if not issue_ids or not updates:
        return jsonify({"error": "issue_ids and updates required"}), 400

    issues = _load_issues()
    updated = []
    for issue in issues:
        if issue["id"] in issue_ids:
            for field in ["title", "description", "type", "status", "priority",
                          "assignee_id", "labels", "story_points", "sprint"]:
                if field in updates:
                    issue[field] = updates[field]
            issue["updated_at"] = datetime.now().isoformat()
            updated.append(issue["id"])
    _save_issues(issues)
    return jsonify({"updated": updated, "count": len(updated)})


# ---------------------------------------------------------------------------
# API routes — project stats (for extract_by_dropdown)
# ---------------------------------------------------------------------------

@blueprint.route("/api/projects/<int:project_id>/stats")
def api_project_stats(project_id):
    """Per-project statistics for extraction tasks."""
    project = _get_project(project_id)
    if not project:
        abort(404)
    issues = _load_issues()
    p_issues = [i for i in issues if i["project_id"] == project_id]

    status_counts = dict(Counter(i["status"] for i in p_issues))
    type_counts = dict(Counter(i["type"] for i in p_issues))
    priority_counts = dict(Counter(i["priority"] for i in p_issues))
    total_points = sum(i.get("story_points", 0) or 0 for i in p_issues)
    done_points = sum((i.get("story_points", 0) or 0) for i in p_issues
                     if i["status"] in ("done", "closed"))
    unique_assignees = len(set(i.get("assignee_id") for i in p_issues
                               if i.get("assignee_id")))

    return jsonify({
        "project_id": project_id,
        "project_name": project["name"],
        "total_issues": len(p_issues),
        "status_counts": status_counts,
        "type_counts": type_counts,
        "priority_counts": priority_counts,
        "total_story_points": total_points,
        "completed_story_points": done_points,
        "unique_assignees": unique_assignees,
    })
