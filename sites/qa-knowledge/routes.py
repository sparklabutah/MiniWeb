"""KnowledgeHub Q&A -- Stack Overflow-style Q&A site.

Data is stored in per-site SQLite tables (qa_knowledge_questions,
qa_knowledge_answers, qa_knowledge_users) and queried through app.db.
Session mutations are isolated per user.

Macros supported (23):
  navigate_by_dropdown, navigate_by_route, search_by_query, search_by_semantic,
  search_by_route, filter_by_dropdown, filter_by_checkbox, sort_by_ranking,
  extract_by_query, extract_by_route, create_from_free_text, submit_by_query,
  edit_by_form, post_from_free_text, post_by_route, react_by_toggle,
  follow_by_dropdown, follow_by_toggle, share_by_dropdown, save_by_toggle,
  report_by_form, authenticate_by_form, register_by_form
"""
import json
import pathlib
from collections import Counter
from datetime import datetime

from flask import (
    Blueprint, Response, abort, jsonify, redirect, render_template, request,
    session, url_for,
)
from app import db
from app.events import emit

SITE = "qa-knowledge"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "qa-knowledge",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data helpers — all data lives in SQLite via db.query() / db.save_item()
# ---------------------------------------------------------------------------

def _load_users():
    users = db.query(SITE, "users")
    for u in users:
        for field in ("tags", "saved_questions", "followed_tags", "reports"):
            if isinstance(u.get(field), str):
                try:
                    u[field] = json.loads(u[field])
                except (json.JSONDecodeError, TypeError):
                    u[field] = []
    return users


def _load_questions(**kwargs):
    """Load questions with optional SQL-level filtering.

    Accepts all db.query kwargs: where, sort, limit, offset.
    """
    questions = db.query(SITE, "questions", limit=kwargs.pop("limit", 50), **kwargs)
    for q in questions:
        if isinstance(q.get("tags"), str):
            try:
                q["tags"] = json.loads(q["tags"])
            except (json.JSONDecodeError, TypeError):
                q["tags"] = []
        if isinstance(q.get("reports"), str):
            try:
                q["reports"] = json.loads(q["reports"])
            except (json.JSONDecodeError, TypeError):
                q["reports"] = []
    return questions


def _get_question(qid):
    """Fetch a single question by ID."""
    q = db.get_item(SITE, "questions", qid)
    if q:
        if isinstance(q.get("tags"), str):
            try:
                q["tags"] = json.loads(q["tags"])
            except (json.JSONDecodeError, TypeError):
                q["tags"] = []
        if isinstance(q.get("reports"), str):
            try:
                q["reports"] = json.loads(q["reports"])
            except (json.JSONDecodeError, TypeError):
                q["reports"] = []
    return q


def _load_answers(**kwargs):
    """Load answers with optional SQL-level filtering.

    Accepts all db.query kwargs: where, sort, limit, offset.
    """
    answers = db.query(SITE, "answers", limit=kwargs.pop("limit", 50), **kwargs)
    for a in answers:
        if isinstance(a.get("reports"), str):
            try:
                a["reports"] = json.loads(a["reports"])
            except (json.JSONDecodeError, TypeError):
                a["reports"] = []
    return answers


def _get_answer(aid):
    """Fetch a single answer by ID."""
    a = db.get_item(SITE, "answers", aid)
    if a:
        if isinstance(a.get("reports"), str):
            try:
                a["reports"] = json.loads(a["reports"])
            except (json.JSONDecodeError, TypeError):
                a["reports"] = []
    return a


def _save_users(users):
    db.save_collection(SITE, "users", users)


# --- Single-item writes (replaces _save_questions/_save_answers for mutations) ---
# These avoid the load-all/save-all pattern that truncated large tables down to
# the default query limit. PK is `id` for both collections (see _get_*).

def _save_question(q):
    db.save_item(SITE, "questions", q["id"], q)


def _save_answer(a):
    db.save_item(SITE, "answers", a["id"], a)


def _user_by_id(user_id):
    users = db.query(SITE, "users", where={"root_user_id": user_id}, limit=1)
    if users:
        u = users[0]
        for field in ("tags", "saved_questions", "followed_tags", "reports"):
            if isinstance(u.get(field), str):
                try:
                    u[field] = json.loads(u[field])
                except (json.JSONDecodeError, TypeError):
                    u[field] = []
        return u
    return None


def _build_user_map():
    return {u["root_user_id"]: u for u in _load_users()}


def _parse_dt(dt_str):
    """Parse an ISO datetime string."""
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except Exception:
        return datetime.min


def _enrich_question(q, user_map, answers=None, fetch_answers=False):
    """Add author info and computed fields to a question dict.

    If fetch_answers=True, fetches answers from DB for this question (SQL-level).
    If answers list is provided, filters from it (legacy path for small sets).
    """
    author = user_map.get(q.get("author_root_user_id", -1))
    q_copy = dict(q)
    q_copy["author"] = author
    if fetch_answers:
        q_answers = _load_answers(where={"question_id": q["id"]})
        q_copy["answers"] = q_answers
        q_copy["answer_count"] = len(q_answers)
        q_copy["has_accepted"] = any(a.get("is_accepted") for a in q_answers)
    elif answers is not None:
        q_answers = [a for a in answers if a["question_id"] == q["id"]]
        q_copy["answers"] = q_answers
        q_copy["answer_count"] = len(q_answers)
        q_copy["has_accepted"] = any(a.get("is_accepted") for a in q_answers)
    return q_copy


def _next_question_id():
    """Next question ID via SQL MAX (not bounded by query limit)."""
    table = db.get_table_name(SITE, "questions")
    m = db.execute(f"SELECT MAX([id]) FROM [{table}]", fetch="val")
    return (m + 1) if m else 90001


def _next_answer_id():
    """Next answer ID via SQL MAX (not bounded by query limit)."""
    table = db.get_table_name(SITE, "answers")
    m = db.execute(f"SELECT MAX([id]) FROM [{table}]", fetch="val")
    return (m + 1) if m else 80001


def _next_user_id(users):
    if not users:
        return 1
    return max(u["root_user_id"] for u in users) + 1


def _get_logged_in_user():
    """Return the currently logged-in user or None."""
    uid = session.get("qa_user_id")
    if uid is not None:
        return _user_by_id(uid)
    return None


def _keyword_score(query, question):
    """Simple keyword-overlap relevance score for semantic search."""
    terms = query.lower().split()
    text = (question.get("title", "") + " " +
            question.get("body_excerpt", "") + " " +
            " ".join(question.get("tags", []))).lower()
    return sum(1 for t in terms if t in text)


def _serialize_user(u):
    """Return a safe JSON-serializable user dict."""
    if not u:
        return None
    return {
        "root_user_id": u["root_user_id"],
        "se_display_name": u["se_display_name"],
        "se_username": u["se_username"],
        "reputation": u["reputation"],
    }


# ---------------------------------------------------------------------------
# Tag aggregation (cached, with invalidation on question/tag mutations)
# ---------------------------------------------------------------------------

_top_tags_cache = None
_stats_cache = None


def _invalidate_tag_caches():
    global _top_tags_cache, _stats_cache
    _top_tags_cache = None
    _stats_cache = None


def _cached_stats(num_users=0):
    """Return lightweight stats without expensive COUNT(*) on million-row tables."""
    global _stats_cache
    if _stats_cache is not None:
        _stats_cache["total_users"] = num_users
        return _stats_cache
    _stats_cache = {"total_users": num_users}
    return _stats_cache


def _cached_top_tags(limit=15):
    """Return top tags with counts from pre-built tags_meta table."""
    global _top_tags_cache
    if _top_tags_cache is not None:
        return _top_tags_cache[:limit]
    rows = db.query(SITE, "tags_meta", sort="-count", limit=50)
    _top_tags_cache = [(r["tag"], r["count"]) for r in rows]
    return _top_tags_cache[:limit]


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

# macro: navigate_by_dropdown -- tag dropdown in header, also navigate_by_route
@blueprint.route("/")
def index():
    user_map = _build_user_map()
    sort = request.args.get("sort", "newest")
    page = max(1, request.args.get("page", 1, type=int))
    per_page = 30
    # filter_by_checkbox: multiple tags via checkboxes
    checked_tags = request.args.getlist("tags")
    # filter_by_dropdown: single tag dropdown
    filter_tag = request.args.get("filter_tag", "").strip()

    # Build SQL-level sort
    sort_map = {"votes": "-score", "newest": "-creation_date", "active": "-creation_date"}
    sql_sort = sort_map.get(sort, "-creation_date")

    # Tag filtering requires text search since tags is a JSON string column
    table = db.get_table_name(SITE, "questions")
    if checked_tags or filter_tag or sort == "unanswered":
        # Need text-based tag filter or answer_count filter -- use db.execute
        clauses = []
        params = []
        if sort == "unanswered":
            clauses.append("[answer_count] = 0")
        if filter_tag:
            clauses.append("[tags] LIKE ?")
            params.append(f'%"{filter_tag}"%')
        if checked_tags:
            tag_clauses = []
            for t in checked_tags:
                tag_clauses.append("[tags] LIKE ?")
                params.append(f'%"{t}"%')
            clauses.append("(" + " OR ".join(tag_clauses) + ")")
        where_sql = " AND ".join(clauses) if clauses else "1=1"
        desc = sql_sort.startswith("-")
        col = sql_sort.lstrip("-")
        direction = "DESC" if desc else "ASC"
        sql = f"SELECT * FROM [{table}] WHERE {where_sql} ORDER BY [{col}] {direction} LIMIT ? OFFSET ?"
        params.extend([per_page, (page - 1) * per_page])
        questions = db.execute(sql, tuple(params), fetch="all")

        # Raw SQL reads the base table only — merge in this session's questions
        def _overlay_match(item):
            tags = item.get("tags") or []
            if isinstance(tags, str):
                try:
                    tags = json.loads(tags)
                except (json.JSONDecodeError, TypeError):
                    tags = []
            if sort == "unanswered" and (item.get("answer_count") or 0) != 0:
                return False
            if filter_tag and filter_tag not in tags:
                return False
            if checked_tags and not any(t in tags for t in checked_tags):
                return False
            return True

        questions = db.merge_overlay(SITE, "questions", questions,
                                     match=_overlay_match, sort=sql_sort,
                                     limit=per_page)
        # Deserialize tags
        for q in questions:
            if isinstance(q.get("tags"), str):
                try:
                    q["tags"] = json.loads(q["tags"])
                except (json.JSONDecodeError, TypeError):
                    q["tags"] = []
    else:
        questions = _load_questions(sort=sql_sort, limit=per_page, offset=(page - 1) * per_page)

    enriched = [_enrich_question(q, user_map) for q in questions]
    # answer_count is already a column -- use it directly, no need to re-count from answers

    top_tags = _cached_top_tags()
    stats = _cached_stats(len(user_map))
    current_user = _get_logged_in_user()
    return render_template(
        "qa-knowledge/index.html",
        questions=enriched, sort=sort, top_tags=top_tags,
        checked_tags=checked_tags, filter_tag=filter_tag,
        stats=stats, current_user=current_user,
    )


# macro: navigate_by_route
@blueprint.route("/question/<int:qid>")
def question_detail(qid):
    user_map = _build_user_map()
    q = _get_question(qid)
    if q is None:
        abort(404)
    question = _enrich_question(q, user_map, fetch_answers=True)
    # Enrich answers with author info
    for a in question.get("answers", []):
        a["author"] = user_map.get(a.get("author_root_user_id", -1))
    # Sort: accepted first, then by score
    question["answers"] = sorted(
        question.get("answers", []),
        key=lambda a: (not a.get("is_accepted", False), -a.get("score", 0)),
    )
    current_user = _get_logged_in_user()
    # Check if user has saved or followed
    saved_ids = []
    followed_tags = []
    if current_user:
        saved_ids = current_user.get("saved_questions", [])
        followed_tags = current_user.get("followed_tags", [])
    return render_template(
        "qa-knowledge/question_detail.html",
        question=question, current_user=current_user,
        saved_ids=saved_ids, followed_tags=followed_tags,
    )


# macro: create_from_free_text, submit_by_query
@blueprint.route("/ask")
def ask_page():
    current_user = _get_logged_in_user()
    return render_template("qa-knowledge/ask.html",
                           current_user=current_user, top_tags=_cached_top_tags(50))


# macro: submit_by_query -- form-based question submission
@blueprint.route("/ask", methods=["POST"])
def ask_submit():
    current_user = _get_logged_in_user()
    title = request.form.get("title", "").strip()
    body = request.form.get("body", "").strip()
    tags_str = request.form.get("tags", "").strip()
    tags = [t.strip() for t in tags_str.split(",") if t.strip()]

    if not title:
        return render_template("qa-knowledge/ask.html",
                               current_user=current_user, top_tags=_cached_top_tags(50),
                               error="Title is required.")

    new_q = {
        "id": _next_question_id(),
        "title": title,
        "body_excerpt": body,
        "author_root_user_id": session.get("qa_user_id", 1),
        "tags": tags,
        "score": 0,
        "answer_count": 0,
        "creation_date": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "site": "stackoverflow",
    }
    _save_question(new_q)
    _invalidate_tag_caches()
    return redirect(url_for("qa-knowledge.question_detail", qid=new_q["id"]))


@blueprint.route("/tags")
def tags_page():
    # Use pre-built tags_meta table instead of scanning all questions
    tag_rows = db.query(SITE, "tags_meta", sort="-count", limit=500)
    tags_sorted = [(r["tag"], r["count"]) for r in tag_rows]
    current_user = _get_logged_in_user()
    return render_template(
        "qa-knowledge/tags.html",
        tags=tags_sorted, current_user=current_user,
    )


# macro: navigate_by_dropdown (tag link), filter_by_dropdown
@blueprint.route("/tag/<tag>")
def tag_questions(tag):
    user_map = _build_user_map()
    sort = request.args.get("sort", "newest")
    sort_map = {"votes": "-score", "newest": "-creation_date", "active": "-creation_date"}
    sql_sort = sort_map.get(sort, "-creation_date")
    # Use SQL LIKE for tag filtering since tags is a JSON string column
    table = db.get_table_name(SITE, "questions")
    desc = sql_sort.startswith("-")
    col = sql_sort.lstrip("-")
    direction = "DESC" if desc else "ASC"
    rows = db.execute(
        f"SELECT * FROM [{table}] WHERE [tags] LIKE ? ORDER BY [{col}] {direction} LIMIT 50",
        (f'%"{tag}"%',), fetch="all"
    )
    for q in rows:
        if isinstance(q.get("tags"), str):
            try:
                q["tags"] = json.loads(q["tags"])
            except (json.JSONDecodeError, TypeError):
                q["tags"] = []
    enriched = [_enrich_question(q, user_map) for q in rows]
    if sort == "unanswered":
        enriched = [q for q in enriched if q.get("answer_count", 0) == 0]
    current_user = _get_logged_in_user()
    return render_template(
        "qa-knowledge/tag_questions.html",
        questions=enriched, tag=tag, sort=sort, current_user=current_user,
    )


@blueprint.route("/users")
def users_page():
    users = _load_users()
    current_user = _get_logged_in_user()
    return render_template(
        "qa-knowledge/users.html",
        users=users, current_user=current_user,
    )


@blueprint.route("/user/<int:uid>")
def user_profile(uid):
    user = _user_by_id(uid)
    if user is None:
        abort(404)
    user_map = _build_user_map()
    user_questions = _load_questions(where={"author_root_user_id": uid}, sort="-creation_date", limit=50)
    user_questions = [_enrich_question(q, user_map) for q in user_questions]
    user_answers = _load_answers(where={"author_root_user_id": uid}, sort="-creation_date", limit=50)
    # Enrich answers with question title via single lookups
    for a in user_answers:
        qobj = _get_question(a["question_id"])
        a["question_title"] = qobj["title"] if qobj else "Unknown"
    current_user = _get_logged_in_user()
    return render_template(
        "qa-knowledge/user_profile.html",
        profile_user=user, user_questions=user_questions,
        user_answers=user_answers, current_user=current_user,
    )


@blueprint.route("/search")
def search_page():
    q = request.args.get("q", "").strip()
    user_map = _build_user_map()
    results = []
    if q:
        rows = db.search(SITE, "questions", q, limit=50)
        for quest in rows:
            if isinstance(quest.get("tags"), str):
                try:
                    quest["tags"] = json.loads(quest["tags"])
                except (json.JSONDecodeError, TypeError):
                    quest["tags"] = []
            results.append(_enrich_question(quest, user_map))
    current_user = _get_logged_in_user()
    return render_template(
        "qa-knowledge/search.html",
        query=q, results=results, current_user=current_user,
    )


# macro: authenticate_by_form
@blueprint.route("/login", methods=["GET"])
def login_page():
    current_user = _get_logged_in_user()
    return render_template("qa-knowledge/login.html",
                           current_user=current_user, error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    for u in users:
        if u["se_username"] == username:
            # Accept any password for existing users (simple auth)
            if not u.get("password") or u.get("password") == password:
                session["qa_user_id"] = u["root_user_id"]
                return redirect(url_for("qa-knowledge.index"))
            else:
                return render_template(
                    "qa-knowledge/login.html",
                    error="Invalid password.",
                    current_user=None,
                )
    return render_template(
        "qa-knowledge/login.html",
        error="Invalid username. Try one of the registered usernames.",
        current_user=None,
    )


@blueprint.route("/logout")
def logout():
    session.pop("qa_user_id", None)
    return redirect(url_for("qa-knowledge.index"))


# macro: register_by_form
@blueprint.route("/register", methods=["GET"])
def register_page():
    return render_template("qa-knowledge/register.html",
                           current_user=None, error=None)


@blueprint.route("/register", methods=["POST"])
def register_submit():
    username = request.form.get("username", "").strip()
    display_name = request.form.get("display_name", "").strip()
    password = request.form.get("password", "").strip()

    if not username or not display_name:
        return render_template("qa-knowledge/register.html",
                               current_user=None,
                               error="Username and display name are required.")

    users = _load_users()
    # Check duplicate
    if any(u["se_username"] == username for u in users):
        return render_template("qa-knowledge/register.html",
                               current_user=None,
                               error="Username already taken.")

    new_user = {
        "root_user_id": _next_user_id(users),
        "se_username": username,
        "se_display_name": display_name,
        "password": password,
        "reputation": 1,
        "tags": [],
        "top_answers_count": 0,
        "member_since": datetime.utcnow().strftime("%Y-%m-%d"),
        "about_me": "",
        "saved_questions": [],
        "followed_tags": [],
        "reports": [],
    }
    users.append(new_user)
    _save_users(users)
    emit("signup", user_id=new_user["root_user_id"], site_name="qa-knowledge",
         username=username, password=password, email="")
    session["qa_user_id"] = new_user["root_user_id"]
    return redirect(url_for("qa-knowledge.index"))


# macro: edit_by_form -- HTML form to edit a question
@blueprint.route("/question/<int:qid>/edit", methods=["GET"])
def edit_question_page(qid):
    question = _get_question(qid)
    if question is None:
        abort(404)
    current_user = _get_logged_in_user()
    return render_template("qa-knowledge/edit_question.html",
                           question=question, current_user=current_user)


@blueprint.route("/question/<int:qid>/edit", methods=["POST"])
def edit_question_submit(qid):
    title = request.form.get("title", "").strip()
    body = request.form.get("body", "").strip()
    tags_str = request.form.get("tags", "").strip()
    tags = [t.strip() for t in tags_str.split(",") if t.strip()]

    q = _get_question(qid)
    if q is None:
        abort(404)
    if title:
        q["title"] = title
    if body:
        q["body_excerpt"] = body
    if tags:
        q["tags"] = tags
    _save_question(q)
    _invalidate_tag_caches()
    return redirect(url_for("qa-knowledge.question_detail", qid=qid))


# macro: post_from_free_text -- form-based answer submission
@blueprint.route("/question/<int:qid>/answer", methods=["POST"])
def form_answer_submit(qid):
    body = request.form.get("body", "").strip()
    if not body:
        return redirect(url_for("qa-knowledge.question_detail", qid=qid))

    q_obj = _get_question(qid)
    if not q_obj:
        abort(404)

    new_a = {
        "id": _next_answer_id(),
        "question_id": qid,
        "author_root_user_id": session.get("qa_user_id", 1),
        "body_excerpt": body,
        "score": 0,
        "is_accepted": False,
        "creation_date": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    _save_answer(new_a)

    # Update question answer count
    q_obj["answer_count"] = q_obj.get("answer_count", 0) + 1
    _save_question(q_obj)
    return redirect(url_for("qa-knowledge.question_detail", qid=qid))


# macro: react_by_toggle -- form-based voting (upvote/downvote toggle)
@blueprint.route("/question/<int:qid>/vote", methods=["POST"])
def form_question_vote(qid):
    direction = request.form.get("direction", "up")
    q = _get_question(qid)
    if q is not None:
        q["score"] = q.get("score", 0) + (1 if direction == "up" else -1)
        _save_question(q)
    return redirect(url_for("qa-knowledge.question_detail", qid=qid))


@blueprint.route("/answer/<int:aid>/vote", methods=["POST"])
def form_answer_vote(aid):
    direction = request.form.get("direction", "up")
    a = _get_answer(aid)
    if a is None:
        abort(404)
    a["score"] = a.get("score", 0) + (1 if direction == "up" else -1)
    _save_answer(a)
    return redirect(url_for("qa-knowledge.question_detail", qid=a["question_id"]))


# macro: save_by_toggle -- bookmark/save a question
@blueprint.route("/question/<int:qid>/save", methods=["POST"])
def form_save_question(qid):
    if "qa_user_id" not in session:
        return redirect(url_for("qa-knowledge.login_page"))
    users = _load_users()
    user = None
    for u in users:
        if u["root_user_id"] == session["qa_user_id"]:
            user = u
            break
    if not user:
        return redirect(url_for("qa-knowledge.login_page"))
    saved = user.setdefault("saved_questions", [])
    if qid in saved:
        saved.remove(qid)
    else:
        saved.append(qid)
    _save_users(users)
    return redirect(url_for("qa-knowledge.question_detail", qid=qid))


# macro: follow_by_toggle -- follow/unfollow a tag via toggle button
@blueprint.route("/tag/<tag>/follow", methods=["POST"])
def form_follow_tag(tag):
    if "qa_user_id" not in session:
        return redirect(url_for("qa-knowledge.login_page"))
    users = _load_users()
    user = None
    for u in users:
        if u["root_user_id"] == session["qa_user_id"]:
            user = u
            break
    if not user:
        return redirect(url_for("qa-knowledge.login_page"))
    followed = user.setdefault("followed_tags", [])
    if tag in followed:
        followed.remove(tag)
        action = "unfollowed"
    else:
        followed.append(tag)
        action = "followed"
    _save_users(users)
    redirect_to = request.form.get("redirect_to", "")
    if redirect_to:
        return redirect(redirect_to)
    return redirect(url_for("qa-knowledge.tag_questions", tag=tag))


# macro: follow_by_dropdown -- follow a tag chosen from a dropdown
@blueprint.route("/follow-tag", methods=["POST"])
def form_follow_tag_dropdown():
    if "qa_user_id" not in session:
        return redirect(url_for("qa-knowledge.login_page"))
    tag = request.form.get("tag", "").strip()
    if not tag:
        return redirect(url_for("qa-knowledge.tags_page"))
    users = _load_users()
    user = None
    for u in users:
        if u["root_user_id"] == session["qa_user_id"]:
            user = u
            break
    if not user:
        return redirect(url_for("qa-knowledge.login_page"))
    followed = user.setdefault("followed_tags", [])
    if tag not in followed:
        followed.append(tag)
    _save_users(users)
    return redirect(url_for("qa-knowledge.tag_questions", tag=tag))


# macro: share_by_dropdown -- share a question via a chosen platform
@blueprint.route("/question/<int:qid>/share", methods=["POST"])
def form_share_question(qid):
    platform = request.form.get("platform", "link").strip()
    question = _get_question(qid)
    if question is None:
        abort(404)
    # Record the share action (simulated)
    share_url = url_for("qa-knowledge.question_detail", qid=qid, _external=False)
    return jsonify({
        "shared": True,
        "platform": platform,
        "question_id": qid,
        "title": question["title"],
        "url": share_url,
    })


# macro: report_by_form -- report a question or answer
@blueprint.route("/question/<int:qid>/report", methods=["GET"])
def report_question_page(qid):
    question = _get_question(qid)
    if question is None:
        abort(404)
    current_user = _get_logged_in_user()
    return render_template("qa-knowledge/report.html",
                           item_type="question", item_id=qid,
                           item_title=question["title"],
                           current_user=current_user)


@blueprint.route("/question/<int:qid>/report", methods=["POST"])
def report_question_submit(qid):
    reason = request.form.get("reason", "").strip()
    details = request.form.get("details", "").strip()
    question = _get_question(qid)
    if question is None:
        abort(404)
    if not reason:
        current_user = _get_logged_in_user()
        return render_template("qa-knowledge/report.html",
                               item_type="question", item_id=qid,
                               item_title=question["title"],
                               current_user=current_user,
                               error="Please select a reason.")

    report_entry = {
        "item_type": "question",
        "item_id": qid,
        "reason": reason,
        "details": details,
        "reported_by": session.get("qa_user_id"),
        "reported_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    question.setdefault("reports", []).append(report_entry)
    _save_question(question)
    return redirect(url_for("qa-knowledge.question_detail", qid=qid))


@blueprint.route("/answer/<int:aid>/report", methods=["POST"])
def report_answer_submit(aid):
    reason = request.form.get("reason", "").strip()
    details = request.form.get("details", "").strip()
    a = _get_answer(aid)
    if a is None:
        abort(404)
    report_entry = {
        "item_type": "answer",
        "item_id": aid,
        "reason": reason,
        "details": details,
        "reported_by": session.get("qa_user_id"),
        "reported_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    a.setdefault("reports", []).append(report_entry)
    _save_answer(a)
    return redirect(url_for("qa-knowledge.question_detail", qid=a["question_id"]))


# macro: dashboard -- shows saved questions and followed tags
@blueprint.route("/dashboard")
def dashboard():
    if "qa_user_id" not in session:
        return redirect(url_for("qa-knowledge.login_page"))
    user = _get_logged_in_user()
    if not user:
        return redirect(url_for("qa-knowledge.login_page"))
    saved_ids = user.get("saved_questions", [])
    saved_questions = []
    for sid in saved_ids:
        sq = _get_question(sid)
        if sq:
            saved_questions.append(sq)
    followed_tags = user.get("followed_tags", [])
    return render_template("qa-knowledge/dashboard.html",
                           current_user=user,
                           saved_questions=saved_questions,
                           followed_tags=followed_tags)


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/questions", methods=["GET"])
def api_questions_list():
    user_map = _build_user_map()

    # Filters
    tag = request.args.get("tag")
    tags_list = request.args.getlist("tags")  # filter_by_checkbox
    user_id = request.args.get("user_id", type=int)
    sort = request.args.get("sort", "newest")
    answered = request.args.get("answered")
    page = max(1, request.args.get("page", 1, type=int))
    per_page = 30

    sort_map = {"votes": "-score", "newest": "-creation_date", "active": "-creation_date"}
    sql_sort = sort_map.get(sort, "-creation_date")
    desc = sql_sort.startswith("-")
    col = sql_sort.lstrip("-")
    direction = "DESC" if desc else "ASC"

    table = db.get_table_name(SITE, "questions")
    clauses = []
    params = []

    if user_id is not None:
        clauses.append("[author_root_user_id] = ?")
        params.append(user_id)
    if answered == "true":
        clauses.append("[answer_count] > 0")
    elif answered == "false":
        clauses.append("[answer_count] = 0")
    if tag:
        clauses.append("[tags] LIKE ?")
        params.append(f'%"{tag}"%')
    if tags_list:
        tag_clauses = []
        for t in tags_list:
            tag_clauses.append("[tags] LIKE ?")
            params.append(f'%"{t}"%')
        clauses.append("(" + " OR ".join(tag_clauses) + ")")

    where_sql = " AND ".join(clauses) if clauses else "1=1"
    sql = f"SELECT * FROM [{table}] WHERE {where_sql} ORDER BY [{col}] {direction} LIMIT ? OFFSET ?"
    params.extend([per_page, (page - 1) * per_page])
    questions = db.execute(sql, tuple(params), fetch="all")

    for q in questions:
        if isinstance(q.get("tags"), str):
            try:
                q["tags"] = json.loads(q["tags"])
            except (json.JSONDecodeError, TypeError):
                q["tags"] = []

    # Strip non-serializable bits
    result = []
    for q in questions:
        qc = _enrich_question(q, user_map)
        qc["author"] = _serialize_user(qc.get("author"))
        result.append(qc)
    return jsonify(result)


@blueprint.route("/api/questions", methods=["POST"])
def api_questions_create():
    data = request.get_json(force=True)
    new_q = {
        "id": _next_question_id(),
        "title": data.get("title", ""),
        "body_excerpt": data.get("body", data.get("body_excerpt", "")),
        "author_root_user_id": data.get("author_root_user_id",
                                        session.get("qa_user_id", 1)),
        "tags": data.get("tags", []),
        "score": 0,
        "answer_count": 0,
        "creation_date": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "site": "stackoverflow",
    }
    _save_question(new_q)
    _invalidate_tag_caches()
    return jsonify(new_q), 201


@blueprint.route("/api/questions/<int:qid>", methods=["GET"])
def api_question_detail(qid):
    user_map = _build_user_map()
    q = _get_question(qid)
    if not q:
        abort(404)
    enriched = _enrich_question(q, user_map, fetch_answers=True)
    for a in enriched.get("answers", []):
        a["author"] = _serialize_user(
            user_map.get(a.get("author_root_user_id", -1)))
    enriched["author"] = _serialize_user(enriched.get("author"))
    return jsonify(enriched)


@blueprint.route("/api/questions/<int:qid>", methods=["PUT"])
def api_question_update(qid):
    data = request.get_json(force=True)
    q = _get_question(qid)
    if q is None:
        abort(404)
    if "title" in data:
        q["title"] = data["title"]
    if "body" in data or "body_excerpt" in data:
        q["body_excerpt"] = data.get("body", data.get("body_excerpt", q["body_excerpt"]))
    if "tags" in data:
        q["tags"] = data["tags"]
        _invalidate_tag_caches()
    _save_question(q)
    return jsonify(q)


@blueprint.route("/api/questions/<int:qid>", methods=["DELETE"])
def api_question_delete(qid):
    q = _get_question(qid)
    if q is None:
        abort(404)
    db.delete_item(SITE, "questions", qid)
    # Also delete associated answers (high limit so none are missed)
    for a in _load_answers(where={"question_id": qid}, limit=100000):
        db.delete_item(SITE, "answers", a["id"])
    _invalidate_tag_caches()
    return jsonify({"deleted": True, "id": qid})


# macro: react_by_toggle (API)
@blueprint.route("/api/questions/<int:qid>/vote", methods=["POST"])
def api_question_vote(qid):
    data = request.get_json(force=True)
    direction = data.get("direction", "up")
    q = _get_question(qid)
    if q is None:
        abort(404)
    q["score"] = q.get("score", 0) + (1 if direction == "up" else -1)
    _save_question(q)
    return jsonify({"id": qid, "score": q["score"]})


@blueprint.route("/api/questions/<int:qid>/answers", methods=["GET"])
def api_question_answers(qid):
    user_map = _build_user_map()
    q_answers = _load_answers(where={"question_id": qid})
    for a in q_answers:
        a["author"] = _serialize_user(
            user_map.get(a.get("author_root_user_id", -1)))
    return jsonify(q_answers)


# macro: post_by_route (API answer creation)
@blueprint.route("/api/questions/<int:qid>/answers", methods=["POST"])
def api_answer_create(qid):
    data = request.get_json(force=True)
    # Verify question exists
    q_obj = _get_question(qid)
    if not q_obj:
        abort(404)
    new_a = {
        "id": _next_answer_id(),
        "question_id": qid,
        "author_root_user_id": data.get("author_root_user_id",
                                        session.get("qa_user_id", 1)),
        "body_excerpt": data.get("body", data.get("body_excerpt", "")),
        "score": 0,
        "is_accepted": False,
        "creation_date": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    _save_answer(new_a)
    # Update question answer count
    q_obj["answer_count"] = q_obj.get("answer_count", 0) + 1
    _save_question(q_obj)
    return jsonify(new_a), 201


@blueprint.route("/api/answers/<int:aid>", methods=["GET"])
def api_answer_detail(aid):
    a = _get_answer(aid)
    if not a:
        abort(404)
    user_map = _build_user_map()
    a_copy = dict(a)
    a_copy["author"] = _serialize_user(
        user_map.get(a.get("author_root_user_id", -1)))
    return jsonify(a_copy)


@blueprint.route("/api/answers/<int:aid>", methods=["PUT"])
def api_answer_update(aid):
    data = request.get_json(force=True)
    a = _get_answer(aid)
    if a is None:
        abort(404)
    if "body" in data or "body_excerpt" in data:
        a["body_excerpt"] = data.get("body", data.get("body_excerpt", a["body_excerpt"]))
    _save_answer(a)
    return jsonify(a)


@blueprint.route("/api/answers/<int:aid>", methods=["DELETE"])
def api_answer_delete(aid):
    a = _get_answer(aid)
    if a is None:
        abort(404)
    qid = a["question_id"]
    db.delete_item(SITE, "answers", aid)
    # Decrement question answer count
    q = _get_question(qid)
    if q is not None:
        q["answer_count"] = max(0, q.get("answer_count", 1) - 1)
        _save_question(q)
    return jsonify({"deleted": True, "id": aid})


@blueprint.route("/api/answers/<int:aid>/accept", methods=["POST"])
def api_answer_accept(aid):
    target = _get_answer(aid)
    if target is None:
        abort(404)
    # Unaccept any other accepted answer for the same question.
    # Only write the answers whose accepted-state actually changes.
    siblings = _load_answers(where={"question_id": target["question_id"]}, limit=100000)
    for a in siblings:
        desired = (a["id"] == aid)
        if bool(a.get("is_accepted", False)) != desired:
            a["is_accepted"] = desired
            _save_answer(a)
    return jsonify({"id": aid, "is_accepted": True})


@blueprint.route("/api/answers/<int:aid>/vote", methods=["POST"])
def api_answer_vote(aid):
    data = request.get_json(force=True)
    direction = data.get("direction", "up")
    a = _get_answer(aid)
    if a is None:
        abort(404)
    a["score"] = a.get("score", 0) + (1 if direction == "up" else -1)
    _save_answer(a)
    return jsonify({"id": aid, "score": a["score"]})


@blueprint.route("/api/tags")
def api_tags():
    # Use pre-built tags_meta table instead of scanning all questions
    tag_rows = db.query(SITE, "tags_meta", sort="-count", limit=500)
    result = [{"name": r["tag"], "count": r["count"]} for r in tag_rows]
    return jsonify(result)


@blueprint.route("/api/users")
def api_users():
    users = _load_users()
    result = []
    for u in users:
        result.append({
            "root_user_id": u["root_user_id"],
            "se_username": u["se_username"],
            "se_display_name": u["se_display_name"],
            "reputation": u["reputation"],
            "tags": u.get("tags", []),
            "top_answers_count": u.get("top_answers_count", 0),
            "member_since": u.get("member_since", ""),
        })
    return jsonify(result)


@blueprint.route("/api/users/<int:uid>")
def api_user_detail(uid):
    user = _user_by_id(uid)
    if not user:
        abort(404)
    safe = dict(user)
    safe.pop("password", None)
    return jsonify(safe)


# macro: search_by_query, search_by_semantic
@blueprint.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    user_map = _build_user_map()
    results = []
    if q:
        rows = db.search(SITE, "questions", q, limit=50)
        for quest in rows:
            if isinstance(quest.get("tags"), str):
                try:
                    quest["tags"] = json.loads(quest["tags"])
                except (json.JSONDecodeError, TypeError):
                    quest["tags"] = []
            enriched = _enrich_question(quest, user_map)
            enriched["author"] = _serialize_user(enriched.get("author"))
            results.append(enriched)
    return jsonify(results)


# macro: search_by_semantic -- keyword-overlap semantic search
@blueprint.route("/api/search/semantic")
def api_semantic_search():
    q = request.args.get("q", "").strip()
    user_map = _build_user_map()
    if not q:
        return jsonify([])
    # FTS5 handles both search and BM25 ranking
    rows = db.search(SITE, "questions", q, limit=50)
    results = []
    for quest in rows:
        if isinstance(quest.get("tags"), str):
            try:
                quest["tags"] = json.loads(quest["tags"])
            except (json.JSONDecodeError, TypeError):
                quest["tags"] = []
        enriched = _enrich_question(quest, user_map)
        enriched["author"] = _serialize_user(enriched.get("author"))
        results.append(enriched)
    return jsonify(results)


# macro: save_by_toggle (API)
@blueprint.route("/api/users/<int:uid>/save", methods=["POST"])
def api_save_question(uid):
    data = request.get_json(silent=True) or {}
    question_id = data.get("question_id")
    if question_id is None:
        return jsonify({"error": "question_id required"}), 400
    users = _load_users()
    user = None
    for u in users:
        if u["root_user_id"] == uid:
            user = u
            break
    if not user:
        abort(404)
    saved = user.setdefault("saved_questions", [])
    if question_id in saved:
        saved.remove(question_id)
        action = "unsaved"
    else:
        saved.append(question_id)
        action = "saved"
    _save_users(users)
    return jsonify({"action": action, "question_id": question_id,
                    "total_saved": len(saved)})


# macro: follow_by_toggle, follow_by_dropdown (API)
@blueprint.route("/api/users/<int:uid>/follow-tag", methods=["POST"])
def api_follow_tag(uid):
    data = request.get_json(silent=True) or {}
    tag = data.get("tag", "").strip()
    if not tag:
        return jsonify({"error": "tag required"}), 400
    users = _load_users()
    user = None
    for u in users:
        if u["root_user_id"] == uid:
            user = u
            break
    if not user:
        abort(404)
    followed = user.setdefault("followed_tags", [])
    if tag in followed:
        followed.remove(tag)
        action = "unfollowed"
    else:
        followed.append(tag)
        action = "followed"
    _save_users(users)
    return jsonify({"action": action, "tag": tag,
                    "total_followed": len(followed)})


# macro: share_by_dropdown (API)
@blueprint.route("/api/questions/<int:qid>/share", methods=["POST"])
def api_share_question(qid):
    data = request.get_json(silent=True) or {}
    platform = data.get("platform", "link")
    question = _get_question(qid)
    if question is None:
        abort(404)
    return jsonify({
        "shared": True,
        "platform": platform,
        "question_id": qid,
        "title": question["title"],
    })


# macro: report_by_form (API)
@blueprint.route("/api/questions/<int:qid>/report", methods=["POST"])
def api_report_question(qid):
    data = request.get_json(silent=True) or {}
    reason = data.get("reason", "").strip()
    details = data.get("details", "").strip()
    if not reason:
        return jsonify({"error": "reason required"}), 400
    q = _get_question(qid)
    if q is None:
        abort(404)
    report_entry = {
        "item_type": "question",
        "item_id": qid,
        "reason": reason,
        "details": details,
        "reported_by": session.get("qa_user_id"),
        "reported_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    q.setdefault("reports", []).append(report_entry)
    _save_question(q)
    return jsonify({"reported": True, "question_id": qid, "reason": reason})


@blueprint.route("/api/answers/<int:aid>/report", methods=["POST"])
def api_report_answer(aid):
    data = request.get_json(silent=True) or {}
    reason = data.get("reason", "").strip()
    details = data.get("details", "").strip()
    if not reason:
        return jsonify({"error": "reason required"}), 400
    a = _get_answer(aid)
    if a is None:
        abort(404)
    report_entry = {
        "item_type": "answer",
        "item_id": aid,
        "reason": reason,
        "details": details,
        "reported_by": session.get("qa_user_id"),
        "reported_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    a.setdefault("reports", []).append(report_entry)
    _save_answer(a)
    return jsonify({"reported": True, "answer_id": aid, "reason": reason})


# macro: authenticate_by_form (API)
@blueprint.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    users = _load_users()
    user = None
    for u in users:
        if u["se_username"] == username:
            user = u
            break
    if not user:
        return jsonify({"error": "Invalid credentials"}), 401
    # Accept any password for users without a stored password
    if user.get("password") and user["password"] != password:
        return jsonify({"error": "Invalid credentials"}), 401
    session["qa_user_id"] = user["root_user_id"]
    return jsonify({"user_id": user["root_user_id"],
                    "username": user["se_username"]})


# macro: register_by_form (API)
@blueprint.route("/api/register", methods=["POST"])
def api_register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    display_name = data.get("display_name", "").strip()
    password = data.get("password", "").strip()

    if not username or not display_name:
        return jsonify({"error": "username and display_name required"}), 400

    users = _load_users()
    if any(u["se_username"] == username for u in users):
        return jsonify({"error": "Username already taken"}), 409

    new_uid = _next_user_id(users)
    new_user = {
        "row_id": max((u.get("row_id", 0) for u in users), default=0) + 1,
        "root_user_id": new_uid,
        "se_username": username,
        "se_display_name": display_name,
        "password": password,
        "reputation": 1,
        "tags": [],
        "top_answers_count": 0,
        "member_since": datetime.utcnow().strftime("%Y-%m-%d"),
        "about_me": "",
        "saved_questions": [],
        "followed_tags": [],
        "reports": [],
    }
    # Use save_item to avoid session_overlay conflicts
    db.save_item(SITE, "users", new_user["row_id"], new_user)
    emit("signup", user_id=new_uid, site_name="qa-knowledge",
         username=username, password=password, email="")
    session["qa_user_id"] = new_uid
    return jsonify({"user_id": new_uid,
                    "username": new_user["se_username"]}), 201


@blueprint.route("/api/stats")
def api_stats():
    total_questions = db.count(SITE, "questions")
    total_answers = db.count(SITE, "answers")
    total_users = db.count(SITE, "users")
    q_table = db.get_table_name(SITE, "questions")
    a_table = db.get_table_name(SITE, "answers")
    unanswered = db.execute(
        f"SELECT COUNT(*) FROM [{q_table}] WHERE [answer_count] = 0", fetch="val"
    ) or 0
    accepted = db.execute(
        f"SELECT COUNT(*) FROM [{a_table}] WHERE [is_accepted] = 1", fetch="val"
    ) or 0
    tags_count = db.count(SITE, "tags_meta")
    return jsonify({
        "total_questions": total_questions,
        "total_answers": total_answers,
        "total_users": total_users,
        "total_tags": tags_count,
        "unanswered_questions": unanswered,
        "accepted_answers": accepted,
    })