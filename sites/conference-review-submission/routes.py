"""Conference Review & Submission — OpenReview-style venue and paper review system.

Data lives in SQLite tables: venues, papers (PeerRead + overlay), users.
All queries go through app.db or raw SQL on the shared connection.
"""
import json
import math
import pathlib
import re
from collections import Counter
from datetime import datetime

from flask import Blueprint, Response, abort, jsonify, redirect, render_template, request, session, url_for
from app import db
from app.db import _deserialize_row
from app.events import emit
from app.handlers.email_handler import _add_email

SITE = "conference-review-submission"
SITE_DIR = pathlib.Path(__file__).resolve().parent
blueprint = Blueprint(
    "conference-review-submission",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _db_conn():
    return db.get_conn()


def _parse_json_field(obj, field):
    val = obj.get(field, "")
    if isinstance(val, str):
        if not val:
            return [] if field != "bids" and field != "venue_roles" else {}
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return [] if field != "bids" and field != "venue_roles" else {}
    return val if val is not None else ([] if field != "bids" and field != "venue_roles" else {})


# ---------------------------------------------------------------------------
# Data interpreters
# ---------------------------------------------------------------------------

def _extract_recommendation(review):
    rec = review.get("RECOMMENDATION") or review.get("recommendation")
    if rec is not None:
        try:
            return int(rec)
        except (ValueError, TypeError):
            pass
    return None


def _extract_confidence(review):
    conf = review.get("REVIEWER_CONFIDENCE") or review.get("confidence")
    if conf is not None:
        try:
            return int(conf)
        except (ValueError, TypeError):
            pass
    return None


def _interpret_review(raw_review, review_idx):
    is_meta = raw_review.get("IS_META_REVIEW") or raw_review.get("is_meta_review", False)
    rec = _extract_recommendation(raw_review)
    conf = _extract_confidence(raw_review)
    return {
        "review_idx": review_idx,
        "is_meta_review": is_meta,
        "title": raw_review.get("TITLE") or raw_review.get("title", ""),
        "comments": raw_review.get("comments", ""),
        "recommendation": rec,
        "confidence": conf,
        "date": raw_review.get("DATE") or raw_review.get("date", ""),
        "reviewer": raw_review.get("OTHER_KEYS") or raw_review.get("reviewer", "Anonymous"),
        "originality": raw_review.get("ORIGINALITY") or raw_review.get("originality"),
        "clarity": raw_review.get("CLARITY") or raw_review.get("clarity"),
        "soundness": raw_review.get("SOUNDNESS_CORRECTNESS") or raw_review.get("soundness"),
        "meaningful_comparison": raw_review.get("MEANINGFUL_COMPARISON") or raw_review.get("meaningful_comparison"),
    }


def _interpret_record(raw):
    title = re.sub(r'\s+', ' ', (raw.get("title") or "").replace("\n", " ")).strip()
    abstract = re.sub(r'\s+', ' ', (raw.get("abstract") or "").replace("\n", " ")).strip()
    authors = raw.get("authors", [])
    if isinstance(authors, str):
        try:
            authors = json.loads(authors)
        except (json.JSONDecodeError, TypeError):
            authors = [a.strip() for a in authors.split(",")]
    authors_str = ", ".join(authors[:5]) + (" et al." if len(authors) > 5 else "")
    accepted = raw.get("accepted", False)

    raw_reviews = raw.get("reviews", [])
    if isinstance(raw_reviews, str):
        try:
            raw_reviews = json.loads(raw_reviews)
        except (json.JSONDecodeError, TypeError):
            raw_reviews = []
    reviews = [_interpret_review(rr, ri) for ri, rr in enumerate(raw_reviews)]

    scored_reviews = [r for r in reviews if not r["is_meta_review"] and r["recommendation"] is not None]
    avg_score = round(sum(r["recommendation"] for r in scored_reviews) / len(scored_reviews), 2) if scored_reviews else None
    num_reviews = len([r for r in reviews if not r["is_meta_review"]])

    return {
        "id": raw.get("id", ""),
        "title": title,
        "authors": authors,
        "authors_str": authors_str,
        "abstract": abstract,
        "conference": raw.get("conference", ""),
        "venue_id": raw.get("venue_id", ""),
        "accepted": accepted,
        "decision": "Accept" if accepted else "Reject",
        "reviews": reviews,
        "num_reviews": num_reviews,
        "num_meta_reviews": len([r for r in reviews if r["is_meta_review"]]),
        "avg_score": avg_score,
        "scored_review_count": len(scored_reviews),
    }


# ---------------------------------------------------------------------------
# DB query helpers
# ---------------------------------------------------------------------------

def _db_query_papers(venue_id="", q="", status="", sort="title",
                     score_min=None, score_max=None, limit=25, offset=0):

    if q:
        # --- Text search path: use FTS5 via db.search() ---
        where_eq = {}
        if venue_id:
            where_eq["venue_id"] = venue_id
        rows = db.search(SITE, "papers", q,
                         where=where_eq if where_eq else None,
                         limit=max(limit + offset, 500))
        papers = [_interpret_record(r) for r in rows]

        # Post-filter on status
        if status == "accepted":
            papers = [p for p in papers if p["accepted"]]
        elif status == "rejected":
            papers = [p for p in papers if not p["accepted"]]
    else:
        # --- Non-search path: normal SQL filters ---
        conn = _db_conn()
        clauses = []
        params = []

        if venue_id:
            clauses.append("venue_id = ?")
            params.append(venue_id)
        if status == "accepted":
            clauses.append("accepted = 1")
        elif status == "rejected":
            clauses.append("(accepted = 0)")

        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        sql = f"SELECT * FROM conference_review_submission_papers {where} LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(sql, params).fetchall()
        papers = [_interpret_record(_deserialize_row(row)) for row in rows]

    # Post-filter on computed score fields (small result set)
    if score_min is not None:
        papers = [p for p in papers if p["avg_score"] is not None and p["avg_score"] >= score_min]
    if score_max is not None:
        papers = [p for p in papers if p["avg_score"] is not None and p["avg_score"] <= score_max]

    if sort == "score_desc":
        papers.sort(key=lambda p: -(p["avg_score"] or 0))
    elif sort == "score_asc":
        papers.sort(key=lambda p: (p["avg_score"] or 0))
    elif sort == "title":
        papers.sort(key=lambda p: p["title"].lower())
    elif sort == "reviews":
        papers.sort(key=lambda p: -p["num_reviews"])

    # Apply offset/limit for the FTS path (non-search path already did it in SQL)
    if q:
        papers = papers[offset:offset + limit]

    return papers


def _db_get_paper(paper_id):
    conn = _db_conn()
    row = conn.execute(
        "SELECT * FROM conference_review_submission_papers WHERE id = ?",
        (str(paper_id),),
    ).fetchone()
    if not row:
        return None
    return _interpret_record(_deserialize_row(row))


def _db_count_papers(venue_id="", status=""):
    conn = _db_conn()
    clauses = []
    params = []
    if venue_id:
        clauses.append("venue_id = ?")
        params.append(venue_id)
    if status == "accepted":
        clauses.append("accepted = 1")
    elif status == "rejected":
        clauses.append("accepted = 0")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    return conn.execute(
        f"SELECT COUNT(*) FROM conference_review_submission_papers {where}", params
    ).fetchone()[0]


def _db_search_papers(query, venue_id=""):
    if not query:
        return []
    where_eq = {}
    if venue_id:
        where_eq["venue_id"] = venue_id
    rows = db.search(SITE, "papers", query,
                     where=where_eq if where_eq else None,
                     limit=500)
    # db.search returns BM25-ranked results; interpret them
    return [_interpret_record(r) for r in rows]


def _db_related_papers(paper, limit=5):
    conn = _db_conn()
    accepted_val = 1 if paper["accepted"] else 0
    rows = conn.execute(
        "SELECT * FROM conference_review_submission_papers "
        "WHERE accepted = ? AND id != ? AND venue_id = ? LIMIT ?",
        (accepted_val, str(paper["id"]), paper.get("venue_id", ""), limit),
    ).fetchall()
    return [_interpret_record(_deserialize_row(r)) for r in rows]


# ---------------------------------------------------------------------------
# Venue helpers
# ---------------------------------------------------------------------------

def _get_venue(venue_id):
    return db.get_item(SITE, "venues", venue_id)


def _get_all_venues():
    return db.query(SITE, "venues", sort="-year", limit=50)


# ---------------------------------------------------------------------------
# User helpers
# ---------------------------------------------------------------------------

def _load_users():
    return db.query(SITE, "users")


def _save_users(users):
    db.save_collection(SITE, "users", users)


def _get_user(user_id):
    return db.get_item(SITE, "users", user_id)


_SESSION_KEY = "conf_review_uid"


def _get_current_user():
    uid = session.get(_SESSION_KEY)
    if uid is not None:
        return _get_user(uid)
    return None


def _is_logged_in():
    return _SESSION_KEY in session


# ---------------------------------------------------------------------------
# Review visibility
# ---------------------------------------------------------------------------

def _can_see_reviews(venue, user, paper):
    if not venue:
        return True
    vis = venue.get("review_visibility", "public")
    if vis == "public":
        return True
    if not user:
        return False
    role = user.get("role", "")
    if role in ("chair", "admin"):
        return True
    if vis == "after_decision":
        return venue.get("status") == "decisions_posted"
    if vis == "assigned_only":
        assigned = _parse_json_field(user, "assigned_papers")
        if str(paper["id"]) in [str(a) for a in assigned]:
            return True
        if user.get("name") and user["name"] in paper.get("authors", []):
            return True
        return False
    return False


# ---------------------------------------------------------------------------
# Search helpers
# ---------------------------------------------------------------------------

def _keyword_score(query, paper):
    terms = query.lower().split()
    text = (paper["title"] + " " + paper["abstract"] + " " +
            " ".join(paper["authors"])).lower()
    return sum(1 for t in terms if t in text)


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    # When logged in, go straight to console (like OpenReview)
    if _is_logged_in():
        return redirect(url_for("conference-review-submission.console"))

    venues = _get_all_venues()
    for v in venues:
        v["paper_count"] = _db_count_papers(venue_id=v["id"])
        v["accepted_count"] = _db_count_papers(venue_id=v["id"], status="accepted")

    return render_template("conference-review-submission/index.html",
                           venues=venues, user=None, pending_count=0)


@blueprint.route("/venues")
def venues_page():
    user = _get_current_user()
    venues = _get_all_venues()
    for v in venues:
        v["paper_count"] = _db_count_papers(venue_id=v["id"])
        v["accepted_count"] = _db_count_papers(venue_id=v["id"], status="accepted")

    pending_count = 0
    if user:
        assigned_ids = _parse_json_field(user, "assigned_papers")
        bids = _parse_json_field(user, "bids")
        pending_count = sum(1 for pid in assigned_ids
                           if str(pid) not in bids or not isinstance(bids.get(str(pid)), dict)
                           or not bids[str(pid)].get("recommendation"))

    return render_template("conference-review-submission/index.html",
                           venues=venues, user=user, pending_count=pending_count)


@blueprint.route("/venue/<venue_id>")
def venue_detail(venue_id):
    venue = _get_venue(venue_id)
    if not venue:
        abort(404)
    user = _get_current_user()

    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    sort = request.args.get("sort", "title").strip()
    score_min = request.args.get("score_min", "").strip()
    score_max = request.args.get("score_max", "").strip()
    page = max(1, request.args.get("page", 1, type=int))
    per_page = 25

    smin = float(score_min) if score_min else None
    smax = float(score_max) if score_max else None

    total_count = _db_count_papers(venue_id=venue_id, status=status)

    if q:
        results = _db_search_papers(q, venue_id=venue_id)
        if status == "accepted":
            results = [p for p in results if p["accepted"]]
        elif status == "rejected":
            results = [p for p in results if not p["accepted"]]
        if smin is not None:
            results = [p for p in results if p["avg_score"] is not None and p["avg_score"] >= smin]
        if smax is not None:
            results = [p for p in results if p["avg_score"] is not None and p["avg_score"] <= smax]
        if sort == "score_desc":
            results.sort(key=lambda p: -(p["avg_score"] or 0))
        elif sort == "score_asc":
            results.sort(key=lambda p: (p["avg_score"] or 0))
        elif sort == "title":
            results.sort(key=lambda p: p["title"].lower())
        elif sort == "reviews":
            results.sort(key=lambda p: -p["num_reviews"])
        total_count = len(results)
        results = results[(page - 1) * per_page : page * per_page]
    else:
        results = _db_query_papers(
            venue_id=venue_id, status=status, sort=sort,
            score_min=smin, score_max=smax,
            limit=per_page, offset=(page - 1) * per_page,
        )

    total_pages = max(1, math.ceil(total_count / per_page))

    count_all = _db_count_papers(venue_id=venue_id)
    count_accepted = _db_count_papers(venue_id=venue_id, status="accepted")
    count_rejected = count_all - count_accepted

    # Determine if scores should be shown based on review visibility
    show_scores = venue.get("review_visibility", "public") == "public" or (
        user and user.get("role") in ("chair", "admin")
    )

    return render_template("conference-review-submission/venue.html",
                           venue=venue, papers=results, q=q, status=status,
                           sort=sort, score_min=score_min, score_max=score_max,
                           user=user, page=page, per_page=per_page,
                           total_count=total_count, total_pages=total_pages,
                           count_all=count_all, count_accepted=count_accepted,
                           count_rejected=count_rejected, show_scores=show_scores)


@blueprint.route("/paper/<paper_id>")
def paper_detail(paper_id):
    paper = _db_get_paper(paper_id)
    if paper is None:
        abort(404)

    venue = _get_venue(paper.get("venue_id", ""))
    user = _get_current_user()
    related = _db_related_papers(paper)
    show_reviews = _can_see_reviews(venue, user, paper)

    return render_template("conference-review-submission/paper.html",
                           paper=paper, venue=venue, related=related,
                           user=user, show_reviews=show_reviews)


@blueprint.route("/paper/<paper_id>/review", methods=["GET", "POST"])
def review_form(paper_id):
    paper = _db_get_paper(paper_id)
    if paper is None:
        abort(404)
    user = _get_current_user()
    if not user:
        return redirect(url_for("conference-review-submission.login_page"))
    venue = _get_venue(paper.get("venue_id", ""))

    if request.method == "POST":
        recommendation = request.form.get("recommendation", "").strip()
        confidence = request.form.get("confidence", "").strip()
        comments = request.form.get("comments", "").strip()
        title = request.form.get("title", "").strip()

        # Handle optional file attachment
        attachment_name = None
        uploaded = request.files.get("file")
        if uploaded and uploaded.filename:
            attachment_name = uploaded.filename

        users = _load_users()
        u = next((u for u in users if u["id"] == user["id"]), None)
        if u:
            bids = _parse_json_field(u, "bids")
            bids[str(paper_id)] = {
                "recommendation": int(recommendation) if recommendation else None,
                "confidence": int(confidence) if confidence else None,
                "comments": comments,
                "title": title,
                "reviewer": user["name"],
                "attachment": attachment_name,
            }
            u["bids"] = bids
            _save_users(users)
        _add_email(user["id"], "noreply@conference-review.lakeport.local",
                   "Review submitted",
                   f'Your review for paper "{paper["title"]}" has been submitted successfully.')
        return redirect(url_for("conference-review-submission.paper_detail", paper_id=paper_id))

    return render_template("conference-review-submission/review.html",
                           paper=paper, venue=venue, user=user)


@blueprint.route("/venue/<venue_id>/stats")
def stats_page(venue_id):
    venue = _get_venue(venue_id)
    if not venue:
        abort(404)
    user = _get_current_user()

    papers = _db_query_papers(venue_id=venue_id, limit=50000)

    total = len(papers)
    accepted = sum(1 for p in papers if p["accepted"])
    rejected = total - accepted
    acceptance_rate = round(accepted / total * 100, 1) if total > 0 else 0

    scored = [p for p in papers if p["avg_score"] is not None]
    all_scores = [p["avg_score"] for p in scored]
    avg_overall = round(sum(all_scores) / len(all_scores), 2) if all_scores else 0
    median_score = round(sorted(all_scores)[len(all_scores) // 2], 2) if all_scores else 0

    accepted_scores = [p["avg_score"] for p in scored if p["accepted"]]
    rejected_scores = [p["avg_score"] for p in scored if not p["accepted"]]
    avg_accepted = round(sum(accepted_scores) / len(accepted_scores), 2) if accepted_scores else 0
    avg_rejected = round(sum(rejected_scores) / len(rejected_scores), 2) if rejected_scores else 0

    total_reviews = sum(p["num_reviews"] for p in papers)
    avg_reviews_per_paper = round(total_reviews / total, 1) if total > 0 else 0

    score_dist = Counter()
    for p in scored:
        bucket = min(10, max(1, round(p["avg_score"])))
        score_dist[bucket] += 1

    all_authors = set()
    for p in papers:
        all_authors.update(p["authors"])

    return render_template("conference-review-submission/stats.html",
                           venue=venue, total=total, accepted=accepted,
                           rejected=rejected, acceptance_rate=acceptance_rate,
                           avg_overall=avg_overall, median_score=median_score,
                           avg_accepted=avg_accepted, avg_rejected=avg_rejected,
                           total_reviews=total_reviews,
                           avg_reviews_per_paper=avg_reviews_per_paper,
                           score_dist=dict(score_dist),
                           unique_authors=len(all_authors), user=user)


@blueprint.route("/console")
def console():
    if not _is_logged_in():
        return redirect(url_for("conference-review-submission.login_page"))
    user = _get_current_user()
    if not user:
        return redirect(url_for("conference-review-submission.login_page"))

    assigned_ids = _parse_json_field(user, "assigned_papers")
    bids = _parse_json_field(user, "bids")
    venue_roles = _parse_json_field(user, "venue_roles")

    # Fetch assigned papers
    pending_tasks = []
    completed_tasks = []
    for pid in assigned_ids:
        p = _db_get_paper(pid)
        if not p:
            continue
        pid_str = str(pid)
        if pid_str in bids and isinstance(bids[pid_str], dict) and bids[pid_str].get("recommendation"):
            p["user_review"] = bids[pid_str]
            completed_tasks.append(p)
        else:
            pending_tasks.append(p)

    # Author submissions: papers where user is an author
    your_submissions = []
    if user.get("name"):
        conn = _db_conn()
        rows = conn.execute(
            "SELECT * FROM conference_review_submission_papers WHERE authors LIKE ? LIMIT 50",
            (f'%{user["name"]}%',),
        ).fetchall()
        for row in rows:
            p = _interpret_record(_deserialize_row(row))
            your_submissions.append(p)

    # Venue participation
    active_venues = []
    for vid, role in venue_roles.items():
        venue = _get_venue(vid)
        if venue:
            active_venues.append({"venue": venue, "role": role})

    return render_template("conference-review-submission/console.html",
                           user=user, pending_tasks=pending_tasks,
                           completed_tasks=completed_tasks,
                           your_submissions=your_submissions,
                           active_venues=active_venues, bids=bids)


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("conference-review-submission/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return render_template("conference-review-submission/login.html",
                               error="Invalid username or password")
    session[_SESSION_KEY] = user["id"]
    emit("signup", user_id=user["id"], site_name="conference-review-submission", username=username, password=password, email="")
    return redirect(url_for("conference-review-submission.console"))


@blueprint.route("/logout")
def logout():
    session.pop(_SESSION_KEY, None)
    return redirect(url_for("conference-review-submission.index"))


# ---------------------------------------------------------------------------
# Form-based mutation routes
# ---------------------------------------------------------------------------

@blueprint.route("/upload-paper", methods=["POST"])
def form_upload_paper():
    """Handle paper PDF upload from the console."""
    if not _is_logged_in():
        return redirect(url_for("conference-review-submission.login_page"))
    # Accept file but just redirect back (no persistent storage needed)
    _file = request.files.get("file")
    return redirect(url_for("conference-review-submission.console"))


@blueprint.route("/paper/<paper_id>/bid", methods=["POST"])
def form_bid(paper_id):
    if not _is_logged_in():
        return redirect(url_for("conference-review-submission.login_page"))
    users = _load_users()
    user = next((u for u in users if u["id"] == session[_SESSION_KEY]), None)
    if not user:
        return redirect(url_for("conference-review-submission.login_page"))
    bids = _parse_json_field(user, "bids")
    pk = str(paper_id)
    if pk in bids:
        del bids[pk]
    else:
        bids[pk] = {"bid": "interested"}
    user["bids"] = bids
    _save_users(users)
    return redirect(url_for("conference-review-submission.paper_detail", paper_id=paper_id))


@blueprint.route("/paper/<paper_id>/assign", methods=["POST"])
def form_assign(paper_id):
    if not _is_logged_in():
        return redirect(url_for("conference-review-submission.login_page"))
    users = _load_users()
    chair = next((u for u in users if u["id"] == session[_SESSION_KEY]), None)
    if not chair or chair.get("role") not in ("chair", "admin"):
        return redirect(url_for("conference-review-submission.login_page"))
    reviewer_id = request.form.get("reviewer_id", type=int)
    if reviewer_id is None:
        return redirect(url_for("conference-review-submission.paper_detail", paper_id=paper_id))
    reviewer = next((u for u in users if u["id"] == reviewer_id), None)
    if not reviewer:
        return redirect(url_for("conference-review-submission.paper_detail", paper_id=paper_id))
    assigned = _parse_json_field(reviewer, "assigned_papers")
    if paper_id not in assigned and str(paper_id) not in [str(a) for a in assigned]:
        assigned.append(paper_id)
    reviewer["assigned_papers"] = assigned
    _save_users(users)
    emit("booking", user_id=reviewer_id, title=f"Review deadline: Paper {paper_id}", start=datetime.now().strftime("%Y-%m-%d"), location="")
    return redirect(url_for("conference-review-submission.paper_detail", paper_id=paper_id))


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/venues")
def api_venues():
    venues = _get_all_venues()
    for v in venues:
        v["paper_count"] = _db_count_papers(venue_id=v["id"])
        v["accepted_count"] = _db_count_papers(venue_id=v["id"], status="accepted")
    return jsonify(venues)


@blueprint.route("/api/venues/<venue_id>")
def api_venue(venue_id):
    venue = _get_venue(venue_id)
    if not venue:
        abort(404)
    venue["paper_count"] = _db_count_papers(venue_id=venue_id)
    venue["accepted_count"] = _db_count_papers(venue_id=venue_id, status="accepted")
    return jsonify(venue)


@blueprint.route("/api/papers")
def api_papers():
    venue_id = request.args.get("venue_id", "").strip()
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    sort = request.args.get("sort", "title").strip()
    limit = request.args.get("limit", type=int) or 100
    score_min = request.args.get("score_min", type=float)
    score_max = request.args.get("score_max", type=float)

    if q:
        results = _db_search_papers(q, venue_id=venue_id)
        if status == "accepted":
            results = [p for p in results if p["accepted"]]
        elif status == "rejected":
            results = [p for p in results if not p["accepted"]]
        if score_min is not None:
            results = [p for p in results if p["avg_score"] is not None and p["avg_score"] >= score_min]
        if score_max is not None:
            results = [p for p in results if p["avg_score"] is not None and p["avg_score"] <= score_max]
        if sort == "score_desc":
            results.sort(key=lambda p: -(p["avg_score"] or 0))
        elif sort == "score_asc":
            results.sort(key=lambda p: (p["avg_score"] or 0))
        elif sort == "title":
            results.sort(key=lambda p: p["title"].lower())
        elif sort == "reviews":
            results.sort(key=lambda p: -p["num_reviews"])
        results = results[:limit]
    else:
        results = _db_query_papers(
            venue_id=venue_id, status=status, sort=sort,
            score_min=score_min, score_max=score_max,
            limit=limit,
        )

    out = [{k: v for k, v in p.items() if k != "reviews"} for p in results]
    return jsonify(out)


@blueprint.route("/api/papers/<paper_id>")
def api_paper(paper_id):
    paper = _db_get_paper(paper_id)
    if paper is None:
        abort(404)
    return jsonify(paper)


@blueprint.route("/api/papers/<paper_id>/reviews")
def api_paper_reviews(paper_id):
    paper = _db_get_paper(paper_id)
    if paper is None:
        abort(404)
    return jsonify(paper["reviews"])


@blueprint.route("/api/papers/search")
def api_search():
    q = request.args.get("q", "").strip()
    venue_id = request.args.get("venue_id", "").strip()
    results = _db_search_papers(q, venue_id=venue_id) if q else []
    out = [{k: v for k, v in p.items() if k != "reviews"} for p in results]
    return jsonify(out)


@blueprint.route("/api/stats")
def api_stats():
    venue_id = request.args.get("venue_id", "").strip()
    status = request.args.get("status", "").strip()

    papers = _db_query_papers(venue_id=venue_id, limit=50000)
    if status == "accepted":
        papers = [p for p in papers if p["accepted"]]
    elif status == "rejected":
        papers = [p for p in papers if not p["accepted"]]

    total = len(papers)
    accepted = sum(1 for p in papers if p["accepted"])
    rejected = total - accepted

    scored = [p for p in papers if p["avg_score"] is not None]
    all_scores = [p["avg_score"] for p in scored]
    avg_overall = round(sum(all_scores) / len(all_scores), 2) if all_scores else 0
    median_score = round(sorted(all_scores)[len(all_scores) // 2], 2) if all_scores else 0

    accepted_scores = [p["avg_score"] for p in scored if p["accepted"]]
    rejected_scores = [p["avg_score"] for p in scored if not p["accepted"]]
    avg_accepted = round(sum(accepted_scores) / len(accepted_scores), 2) if accepted_scores else 0
    avg_rejected = round(sum(rejected_scores) / len(rejected_scores), 2) if rejected_scores else 0

    total_reviews = sum(p["num_reviews"] for p in papers)
    avg_reviews_per_paper = round(total_reviews / total, 1) if total > 0 else 0

    all_authors = set()
    for p in papers:
        all_authors.update(p["authors"])

    score_dist = {}
    for p in scored:
        bucket = min(10, max(1, round(p["avg_score"])))
        score_dist[bucket] = score_dist.get(bucket, 0) + 1

    return jsonify({
        "total_papers": total,
        "accepted": accepted,
        "rejected": rejected,
        "acceptance_rate": round(accepted / total * 100, 1) if total > 0 else 0,
        "avg_score": avg_overall,
        "median_score": median_score,
        "avg_accepted_score": avg_accepted,
        "avg_rejected_score": avg_rejected,
        "total_reviews": total_reviews,
        "avg_reviews_per_paper": avg_reviews_per_paper,
        "unique_authors": len(all_authors),
        "score_distribution": score_dist,
    })


@blueprint.route("/api/papers/<paper_id>/scores")
def api_paper_scores(paper_id):
    paper = _db_get_paper(paper_id)
    if paper is None:
        abort(404)
    scores = []
    for r in paper["reviews"]:
        if not r["is_meta_review"] and r["recommendation"] is not None:
            scores.append({
                "recommendation": r["recommendation"],
                "confidence": r["confidence"],
                "reviewer": r["reviewer"],
            })
    return jsonify({
        "paper_id": paper_id,
        "title": paper["title"],
        "avg_score": paper["avg_score"],
        "scores": scores,
    })


@blueprint.route("/api/decisions")
def api_decisions():
    venue_id = request.args.get("venue_id", "").strip()
    papers = _db_query_papers(venue_id=venue_id, limit=50000)
    out = [{
        "id": p["id"],
        "title": p["title"],
        "decision": p["decision"],
        "accepted": p["accepted"],
        "avg_score": p["avg_score"],
        "num_reviews": p["num_reviews"],
    } for p in papers]
    return jsonify(out)


@blueprint.route("/api/export")
def api_export():
    fmt = request.args.get("format", "json").lower()
    venue_id = request.args.get("venue_id", "").strip()
    status = request.args.get("status", "").strip()
    papers = _db_query_papers(venue_id=venue_id, limit=50000)
    if status == "accepted":
        papers = [p for p in papers if p["accepted"]]
    elif status == "rejected":
        papers = [p for p in papers if not p["accepted"]]

    if fmt == "csv":
        lines = ["id,title,authors,decision,avg_score,num_reviews"]
        for p in papers:
            title = p["title"].replace('"', '""')
            authors = p["authors_str"].replace('"', '""')
            lines.append(f'{p["id"]},"{title}","{authors}",{p["decision"]},{p["avg_score"] or ""},"{p["num_reviews"]}"')
        return Response("\n".join(lines), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=papers.csv"})

    out = [{k: v for k, v in p.items() if k != "reviews"} for p in papers]
    return jsonify(out)


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
    session[_SESSION_KEY] = user["id"]
    return jsonify({"user_id": user["id"], "username": user["username"], "role": user["role"]})


@blueprint.route("/api/users/<int:user_id>")
def api_user(user_id):
    user = _get_user(user_id)
    if not user:
        abort(404)
    return jsonify({k: v for k, v in user.items() if k != "password"})


@blueprint.route("/api/users/<int:user_id>/bid", methods=["POST"])
def api_bid(user_id):
    data = request.get_json(silent=True) or {}
    paper_id = data.get("paper_id")
    if paper_id is None:
        return jsonify({"error": "paper_id required"}), 400
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    bids = _parse_json_field(user, "bids")
    pk = str(paper_id)
    if pk in bids:
        del bids[pk]
        action = "removed"
    else:
        bids[pk] = {"bid": "interested"}
        action = "bid"
    user["bids"] = bids
    _save_users(users)
    return jsonify({"action": action, "paper_id": paper_id, "total_bids": len(bids)})


@blueprint.route("/api/users/<int:user_id>/assign", methods=["POST"])
def api_assign(user_id):
    data = request.get_json(silent=True) or {}
    paper_id = data.get("paper_id")
    if paper_id is None:
        return jsonify({"error": "paper_id required"}), 400
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    assigned = _parse_json_field(user, "assigned_papers")
    if paper_id in assigned:
        assigned.remove(paper_id)
        action = "unassigned"
    else:
        assigned.append(paper_id)
        action = "assigned"
    user["assigned_papers"] = assigned
    _save_users(users)
    return jsonify({"action": action, "paper_id": paper_id, "total_assigned": len(assigned)})

@blueprint.route("/api/users/<int:user_id>/review", methods=["POST"])
def api_submit_review(user_id):
    data = request.get_json(silent=True) or {}
    paper_id = data.get("paper_id")
    if paper_id is None:
        return jsonify({"error": "paper_id required"}), 400
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    bids = _parse_json_field(user, "bids")
    pk = str(paper_id)
    bids[pk] = {
        "recommendation": data.get("recommendation"),
        "confidence": data.get("confidence"),
        "comments": data.get("comments", ""),
        "title": data.get("title", ""),
        "reviewer": user["name"],
    }
    user["bids"] = bids
    _save_users(users)
    return jsonify({"action": "reviewed", "paper_id": paper_id, "review": bids[pk]})
