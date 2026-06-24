"""Conference Review & Submission — OpenReview-style conference management system.

Data interpreter: reads the original PeerRead JSONL snapshot (ICLR 2017),
samples based on config/config.json, and serves through Flask routes.
The raw data file is never modified.
"""
import json
import math
import pathlib
import random
import re
from collections import Counter

from flask import Blueprint, Response, abort, jsonify, redirect, render_template, request, session, url_for

SITE_DIR = pathlib.Path(__file__).resolve().parent
DATA_FILE = SITE_DIR / "data" / "peerread_reviews.jsonl"
USERS_FILE = SITE_DIR / "data" / "users.json"
CONFIG_FILE = SITE_DIR / "config" / "config.json"

blueprint = Blueprint(
    "conference-review-submission",
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

# ---------------------------------------------------------------------------
# Data interpreter — reads raw JSONL, samples, cleans
# ---------------------------------------------------------------------------

def _extract_recommendation(review):
    """Extract a numeric recommendation score from a review dict."""
    rec = review.get("RECOMMENDATION")
    if rec is not None:
        try:
            return int(rec)
        except (ValueError, TypeError):
            pass
    return None


def _extract_confidence(review):
    """Extract reviewer confidence."""
    conf = review.get("REVIEWER_CONFIDENCE")
    if conf is not None:
        try:
            return int(conf)
        except (ValueError, TypeError):
            pass
    return None


def _interpret_review(raw_review, review_idx):
    """Interpret a single raw review into a normalized dict."""
    is_meta = raw_review.get("IS_META_REVIEW", False)
    rec = _extract_recommendation(raw_review)
    conf = _extract_confidence(raw_review)
    return {
        "review_idx": review_idx,
        "is_meta_review": is_meta,
        "title": raw_review.get("TITLE", ""),
        "comments": raw_review.get("comments", ""),
        "recommendation": rec,
        "confidence": conf,
        "date": raw_review.get("DATE", ""),
        "reviewer": raw_review.get("OTHER_KEYS", "Anonymous"),
        "originality": raw_review.get("ORIGINALITY"),
        "clarity": raw_review.get("CLARITY"),
        "soundness": raw_review.get("SOUNDNESS_CORRECTNESS"),
        "meaningful_comparison": raw_review.get("MEANINGFUL_COMPARISON"),
    }


def _interpret_record(raw, idx):
    """Interpret a raw JSONL record into a normalized paper dict."""
    title = re.sub(r'\s+', ' ', raw.get("title", "").replace("\n", " ")).strip()
    abstract = re.sub(r'\s+', ' ', raw.get("abstract", "").replace("\n", " ")).strip()
    authors = raw.get("authors", [])
    if isinstance(authors, str):
        authors = [a.strip() for a in authors.split(",")]
    authors_str = ", ".join(authors[:5]) + (" et al." if len(authors) > 5 else "")
    accepted = raw.get("accepted", False)

    raw_reviews = raw.get("reviews", [])
    reviews = []
    for ri, rr in enumerate(raw_reviews):
        reviews.append(_interpret_review(rr, ri))

    # Compute aggregate scores from non-meta reviews that have recommendations
    scored_reviews = [r for r in reviews if not r["is_meta_review"] and r["recommendation"] is not None]
    avg_score = round(sum(r["recommendation"] for r in scored_reviews) / len(scored_reviews), 2) if scored_reviews else None
    num_reviews = len([r for r in reviews if not r["is_meta_review"]])
    meta_reviews = [r for r in reviews if r["is_meta_review"]]

    return {
        "id": idx,
        "original_id": raw.get("id", ""),
        "title": title,
        "authors": authors,
        "authors_str": authors_str,
        "abstract": abstract,
        "conference": raw.get("conference", "ICLR 2017"),
        "accepted": accepted,
        "decision": "Accept" if accepted else "Reject",
        "reviews": reviews,
        "num_reviews": num_reviews,
        "num_meta_reviews": len(meta_reviews),
        "avg_score": avg_score,
        "scored_review_count": len(scored_reviews),
    }


def _load_papers():
    """Read JSONL dataset. num_data_points=-1 loads all records; positive N
    uses reservoir sampling to pick N records."""
    config = _load_config()
    n = config.get("num_data_points", -1)
    seed = config.get("random_seed", 42)
    rng = random.Random(seed)

    if n > 0:
        reservoir = []
        with open(DATA_FILE) as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if len(reservoir) < n:
                    reservoir.append(raw)
                else:
                    j = rng.randint(0, i)
                    if j < n:
                        reservoir[j] = raw
        selected = reservoir
    else:
        selected = []
        with open(DATA_FILE) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    selected.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    papers = []
    for idx, raw in enumerate(selected, 1):
        papers.append(_interpret_record(raw, idx))

    papers.sort(key=lambda p: p["title"])
    for i, p in enumerate(papers, 1):
        p["id"] = i

    return papers


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------

_papers = None


def _ensure_loaded():
    global _papers
    if _papers is None:
        _papers = _load_papers()


def _get_papers():
    _ensure_loaded()
    return _papers


# ---------------------------------------------------------------------------
# Users (mutable state)
# ---------------------------------------------------------------------------

def _load_users():
    if USERS_FILE.exists():
        return json.loads(USERS_FILE.read_text())
    return []


def _save_users(users):
    USERS_FILE.write_text(json.dumps(users, indent=2))


def _get_user(user_id):
    users = _load_users()
    return next((u for u in users if u["id"] == user_id), None)


# ---------------------------------------------------------------------------
# Search helpers
# ---------------------------------------------------------------------------

def _keyword_score(query, paper):
    terms = query.lower().split()
    text = (paper["title"] + " " + paper["abstract"] + " " +
            " ".join(paper["authors"])).lower()
    return sum(1 for t in terms if t in text)


def _search_papers(papers, query):
    if not query:
        return papers
    q = query.lower().strip()
    scored = [(p, _keyword_score(q, p)) for p in papers]
    scored = [(p, s) for p, s in scored if s > 0]
    scored.sort(key=lambda x: -x[1])
    return [p for p, _ in scored]


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    papers = _get_papers()
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()  # "accepted", "rejected", "all"
    sort = request.args.get("sort", "title").strip()
    score_min = request.args.get("score_min", "").strip()
    score_max = request.args.get("score_max", "").strip()

    results = list(papers)

    if q:
        results = _search_papers(results, q)
    if status == "accepted":
        results = [p for p in results if p["accepted"]]
    elif status == "rejected":
        results = [p for p in results if not p["accepted"]]
    if score_min:
        try:
            smin = float(score_min)
            results = [p for p in results if p["avg_score"] is not None and p["avg_score"] >= smin]
        except ValueError:
            pass
    if score_max:
        try:
            smax = float(score_max)
            results = [p for p in results if p["avg_score"] is not None and p["avg_score"] <= smax]
        except ValueError:
            pass

    if sort == "score_desc":
        results.sort(key=lambda p: -(p["avg_score"] or 0))
    elif sort == "score_asc":
        results.sort(key=lambda p: (p["avg_score"] or 0))
    elif sort == "title":
        results.sort(key=lambda p: p["title"].lower())
    elif sort == "reviews":
        results.sort(key=lambda p: -p["num_reviews"])

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template("conference-review-submission/index.html",
                           papers=results, q=q, status=status, sort=sort,
                           score_min=score_min, score_max=score_max, user=user)


@blueprint.route("/paper/<int:paper_id>")
def paper_detail(paper_id):
    papers = _get_papers()
    paper = next((p for p in papers if p["id"] == paper_id), None)
    if paper is None:
        abort(404)
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    related = [p for p in papers if p["accepted"] == paper["accepted"] and p["id"] != paper_id][:5]
    return render_template("conference-review-submission/paper.html",
                           paper=paper, related=related, user=user)


@blueprint.route("/paper/<int:paper_id>/review", methods=["GET", "POST"])
def review_form(paper_id):
    papers = _get_papers()
    paper = next((p for p in papers if p["id"] == paper_id), None)
    if paper is None:
        abort(404)
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    if not user:
        return redirect(url_for("conference-review-submission.login_page"))

    if request.method == "POST":
        # Add a new review (stored in user's bids for this paper)
        recommendation = request.form.get("recommendation", "").strip()
        confidence = request.form.get("confidence", "").strip()
        comments = request.form.get("comments", "").strip()
        title = request.form.get("title", "").strip()

        users = _load_users()
        u = next((u for u in users if u["id"] == user["id"]), None)
        if u:
            bids = u.setdefault("bids", {})
            paper_key = str(paper_id)
            bids[paper_key] = {
                "recommendation": int(recommendation) if recommendation else None,
                "confidence": int(confidence) if confidence else None,
                "comments": comments,
                "title": title,
                "reviewer": user["name"],
            }
            _save_users(users)
        return redirect(url_for("conference-review-submission.paper_detail", paper_id=paper_id))

    return render_template("conference-review-submission/review.html",
                           paper=paper, user=user)


@blueprint.route("/stats")
def stats_page():
    papers = _get_papers()
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

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

    # Score distribution (histogram buckets 1-10)
    score_dist = Counter()
    for p in scored:
        bucket = min(10, max(1, round(p["avg_score"])))
        score_dist[bucket] += 1

    # Author stats
    all_authors = set()
    for p in papers:
        all_authors.update(p["authors"])

    return render_template("conference-review-submission/stats.html",
                           total=total, accepted=accepted, rejected=rejected,
                           acceptance_rate=acceptance_rate,
                           avg_overall=avg_overall, median_score=median_score,
                           avg_accepted=avg_accepted, avg_rejected=avg_rejected,
                           total_reviews=total_reviews,
                           avg_reviews_per_paper=avg_reviews_per_paper,
                           score_dist=dict(score_dist),
                           unique_authors=len(all_authors), user=user)


@blueprint.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("conference-review-submission.login_page"))
    user = _get_user(session["user_id"])
    if not user:
        return redirect(url_for("conference-review-submission.login_page"))
    papers = _get_papers()
    assigned = [p for p in papers if p["id"] in user.get("assigned_papers", [])]
    bids = user.get("bids", {})
    reviewed_ids = [int(k) for k in bids.keys()]
    reviewed_papers = [p for p in papers if p["id"] in reviewed_ids]
    return render_template("conference-review-submission/dashboard.html",
                           user=user, assigned_papers=assigned,
                           reviewed_papers=reviewed_papers, bids=bids)


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
    session["user_id"] = user["id"]
    return redirect(url_for("conference-review-submission.dashboard"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("conference-review-submission.index"))


# ---------------------------------------------------------------------------
# Form-based mutation routes (for browser automation compatibility)
# ---------------------------------------------------------------------------

@blueprint.route("/paper/<int:paper_id>/bid", methods=["POST"])
def form_bid(paper_id):
    if "user_id" not in session:
        return redirect(url_for("conference-review-submission.login_page"))
    users = _load_users()
    user = next((u for u in users if u["id"] == session["user_id"]), None)
    if not user:
        return redirect(url_for("conference-review-submission.login_page"))
    bids = user.setdefault("bids", {})
    pk = str(paper_id)
    if pk in bids:
        del bids[pk]
    else:
        bids[pk] = {"bid": "interested"}
    _save_users(users)
    return redirect(url_for("conference-review-submission.paper_detail", paper_id=paper_id))


@blueprint.route("/paper/<int:paper_id>/assign", methods=["POST"])
def form_assign(paper_id):
    """Chair assigns a paper to a reviewer."""
    if "user_id" not in session:
        return redirect(url_for("conference-review-submission.login_page"))
    users = _load_users()
    chair = next((u for u in users if u["id"] == session["user_id"]), None)
    if not chair or chair.get("role") not in ("chair", "admin"):
        return redirect(url_for("conference-review-submission.login_page"))
    reviewer_id = request.form.get("reviewer_id", type=int)
    if reviewer_id is None:
        return redirect(url_for("conference-review-submission.paper_detail", paper_id=paper_id))
    reviewer = next((u for u in users if u["id"] == reviewer_id), None)
    if not reviewer:
        return redirect(url_for("conference-review-submission.paper_detail", paper_id=paper_id))
    assigned = reviewer.setdefault("assigned_papers", [])
    if paper_id not in assigned:
        assigned.append(paper_id)
    _save_users(users)
    return redirect(url_for("conference-review-submission.paper_detail", paper_id=paper_id))


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/papers")
def api_papers():
    papers = _get_papers()
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    sort = request.args.get("sort", "title").strip()
    limit = request.args.get("limit", type=int)
    score_min = request.args.get("score_min", type=float)
    score_max = request.args.get("score_max", type=float)

    results = list(papers)
    if q:
        results = _search_papers(results, q)
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

    if limit:
        results = results[:limit]

    # Strip full reviews for list view (lighter payload)
    out = []
    for p in results:
        d = {k: v for k, v in p.items() if k != "reviews"}
        out.append(d)
    return jsonify(out)


@blueprint.route("/api/papers/<int:paper_id>")
def api_paper(paper_id):
    papers = _get_papers()
    paper = next((p for p in papers if p["id"] == paper_id), None)
    if paper is None:
        abort(404)
    return jsonify(paper)


@blueprint.route("/api/papers/<int:paper_id>/reviews")
def api_paper_reviews(paper_id):
    papers = _get_papers()
    paper = next((p for p in papers if p["id"] == paper_id), None)
    if paper is None:
        abort(404)
    return jsonify(paper["reviews"])


@blueprint.route("/api/papers/search")
def api_search():
    q = request.args.get("q", "").strip()
    papers = _get_papers()
    results = _search_papers(papers, q)
    out = []
    for p in results:
        d = {k: v for k, v in p.items() if k != "reviews"}
        out.append(d)
    return jsonify(out)


@blueprint.route("/api/stats")
def api_stats():
    papers = _get_papers()
    status = request.args.get("status", "").strip()
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

    # Score distribution
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


@blueprint.route("/api/papers/<int:paper_id>/scores")
def api_paper_scores(paper_id):
    """Return just the scores/ratings for a specific paper."""
    papers = _get_papers()
    paper = next((p for p in papers if p["id"] == paper_id), None)
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
    """Return accept/reject decisions for all papers."""
    papers = _get_papers()
    out = []
    for p in papers:
        out.append({
            "id": p["id"],
            "title": p["title"],
            "decision": p["decision"],
            "accepted": p["accepted"],
            "avg_score": p["avg_score"],
            "num_reviews": p["num_reviews"],
        })
    return jsonify(out)


@blueprint.route("/api/export")
def api_export():
    fmt = request.args.get("format", "json").lower()
    status = request.args.get("status", "").strip()
    papers = list(_get_papers())
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

    # JSON: strip full reviews for lighter export
    out = []
    for p in papers:
        d = {k: v for k, v in p.items() if k != "reviews"}
        out.append(d)
    return jsonify(out)


# ---------------------------------------------------------------------------
# User API routes (mutable state)
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
    bids = user.setdefault("bids", {})
    pk = str(paper_id)
    if pk in bids:
        del bids[pk]
        action = "removed"
    else:
        bids[pk] = {"bid": "interested"}
        action = "bid"
    _save_users(users)
    return jsonify({"action": action, "paper_id": paper_id, "total_bids": len(bids)})


@blueprint.route("/api/users/<int:user_id>/assign", methods=["POST"])
def api_assign(user_id):
    """Assign a paper to a reviewer."""
    data = request.get_json(silent=True) or {}
    paper_id = data.get("paper_id")
    if paper_id is None:
        return jsonify({"error": "paper_id required"}), 400
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    assigned = user.setdefault("assigned_papers", [])
    if paper_id in assigned:
        assigned.remove(paper_id)
        action = "unassigned"
    else:
        assigned.append(paper_id)
        action = "assigned"
    _save_users(users)
    return jsonify({"action": action, "paper_id": paper_id, "total_assigned": len(assigned)})


@blueprint.route("/api/users/<int:user_id>/review", methods=["POST"])
def api_submit_review(user_id):
    """Submit a review for a paper."""
    data = request.get_json(silent=True) or {}
    paper_id = data.get("paper_id")
    if paper_id is None:
        return jsonify({"error": "paper_id required"}), 400
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    bids = user.setdefault("bids", {})
    pk = str(paper_id)
    bids[pk] = {
        "recommendation": data.get("recommendation"),
        "confidence": data.get("confidence"),
        "comments": data.get("comments", ""),
        "title": data.get("title", ""),
        "reviewer": user["name"],
    }
    _save_users(users)
    return jsonify({"action": "reviewed", "paper_id": paper_id, "review": bids[pk]})
