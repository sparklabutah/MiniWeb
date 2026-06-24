"""Academic Paper DB — arXiv paper search engine (Google Scholar / Semantic Scholar style).

Data interpreter: reads the original arxiv JSONL snapshot, samples based on
config/config.json, and serves through Flask routes. The raw data file is
never modified.
"""
import json
import pathlib
import random
import re
from collections import Counter

from flask import Blueprint, Response, abort, jsonify, redirect, render_template, request, session, url_for

SITE_DIR = pathlib.Path(__file__).resolve().parent
DATA_FILE = SITE_DIR / "data" / "291" / "arxiv-metadata-oai-snapshot.json"
USERS_FILE = SITE_DIR / "data" / "users.json"
CONFIG_FILE = SITE_DIR / "config" / "config.json"

blueprint = Blueprint(
    "academic-paper-db",
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

_LATEX_MAP = {
    "\\'a": "á", "\\'e": "é", "\\'i": "í", "\\'o": "ó", "\\'u": "ú",
    '\\"a': "ä", '\\"o': "ö", '\\"u': "ü", "\\~n": "ñ", "\\v{c}": "č",
    "\\c{c}": "ç", "\\ss": "ß",
}


def _clean_latex(text):
    for pat, repl in _LATEX_MAP.items():
        text = text.replace(pat, repl)
    text = re.sub(r'\\[a-zA-Z]+\{([^}]*)\}', r'\1', text)
    text = text.replace('\\', '').replace('{', '').replace('}', '')
    return text.strip()


def _parse_authors(raw):
    names = []
    for parts in raw:
        last = _clean_latex(parts[0]) if parts[0] else ""
        first = _clean_latex(parts[1]) if parts[1] else ""
        name = f"{first} {last}".strip()
        if name:
            names.append(name)
    return names


def _extract_year(record):
    if record.get("versions"):
        created = record["versions"][0].get("created", "")
        m = re.search(r'\b(19|20)\d{2}\b', created)
        if m:
            return int(m.group())
    if record.get("update_date"):
        return int(record["update_date"][:4])
    return 2000


def _interpret_record(raw, idx):
    authors = _parse_authors(raw.get("authors_parsed", []))
    categories = raw.get("categories", "").split()
    primary_cat = categories[0] if categories else "unknown"
    top_cat = primary_cat.split(".")[0]
    title = re.sub(r'\s+', ' ', raw.get("title", "").replace("\n", " ")).strip()
    abstract = re.sub(r'\s+', ' ', raw.get("abstract", "")).strip()
    year = _extract_year(raw)

    return {
        "id": idx,
        "arxiv_id": raw.get("id", ""),
        "title": title,
        "authors": authors,
        "authors_str": ", ".join(authors[:5]) + (" et al." if len(authors) > 5 else ""),
        "abstract": abstract,
        "categories": categories,
        "primary_category": primary_cat,
        "top_category": top_cat,
        "year": year,
        "doi": raw.get("doi"),
        "journal_ref": raw.get("journal-ref"),
        "comments": raw.get("comments"),
        "update_date": raw.get("update_date", ""),
    }


def _load_papers():
    """Read JSONL dataset. Uses reservoir sampling to avoid loading the entire
    5GB file into memory. num_data_points=-1 streams all records; positive N
    uses reservoir sampling to pick N records uniformly at random."""
    config = _load_config()
    n = config.get("num_data_points", -1)
    seed = config.get("random_seed", 42)
    rng = random.Random(seed)

    if n > 0:
        # Reservoir sampling: O(n) memory regardless of file size
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
        # Load all
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

    papers.sort(key=lambda p: (-p["year"], p["title"]))
    for i, p in enumerate(papers, 1):
        p["id"] = i

    return papers


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------

_papers = None
_top_categories = None
_all_categories = None


def _ensure_loaded():
    global _papers, _top_categories, _all_categories
    if _papers is None:
        _papers = _load_papers()
        _top_categories = sorted(set(p["top_category"] for p in _papers))
        cat_counts = Counter()
        for p in _papers:
            for c in p["categories"]:
                cat_counts[c] += 1
        _all_categories = sorted(cat_counts.keys())


def _get_papers():
    _ensure_loaded()
    return _papers


def _get_top_categories():
    _ensure_loaded()
    return _top_categories


def _get_all_categories():
    _ensure_loaded()
    return _all_categories


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
            " ".join(paper["authors"]) + " " + " ".join(paper["categories"])).lower()
    return sum(1 for t in terms if t in text)


def _search_papers(papers, query, semantic=False):
    if not query:
        return papers
    q = query.lower().strip()
    if semantic:
        scored = [(p, _keyword_score(q, p)) for p in papers]
        scored = [(p, s) for p, s in scored if s > 0]
        scored.sort(key=lambda x: -x[1])
        return [p for p, _ in scored]
    else:
        return [p for p in papers if q in p["title"].lower() or
                q in p["authors_str"].lower() or
                any(q in c.lower() for c in p["categories"])]


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    papers = _get_papers()
    categories = _get_top_categories()
    q = request.args.get("q", "").strip()
    cat = request.args.get("category", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    sort = request.args.get("sort", "date").strip()
    checked_cats = request.args.getlist("cats")

    results = list(papers)

    if q:
        results = _search_papers(results, q)
    if cat:
        results = [p for p in results if p["top_category"] == cat or cat in p["categories"]]
    if checked_cats:
        results = [p for p in results if p["top_category"] in checked_cats or
                   any(c in checked_cats for c in p["categories"])]
    if date_from:
        try:
            results = [p for p in results if p["year"] >= int(date_from)]
        except ValueError:
            pass
    if date_to:
        try:
            results = [p for p in results if p["year"] <= int(date_to)]
        except ValueError:
            pass

    if sort == "date":
        results.sort(key=lambda p: (-p["year"], p["title"]))
    elif sort == "title":
        results.sort(key=lambda p: p["title"].lower())
    elif sort == "relevance" and q:
        results.sort(key=lambda p: -_keyword_score(q, p))

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template("academic-paper-db/index.html",
                           papers=results, categories=categories,
                           all_categories=_get_all_categories(),
                           q=q, cat=cat, date_from=date_from, date_to=date_to,
                           sort=sort, checked_cats=checked_cats, user=user)


@blueprint.route("/paper/<int:paper_id>")
def paper_detail(paper_id):
    papers = _get_papers()
    paper = next((p for p in papers if p["id"] == paper_id), None)
    if paper is None:
        abort(404)
    related = [p for p in papers if p["primary_category"] == paper["primary_category"]
               and p["id"] != paper_id][:5]
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("academic-paper-db/paper.html", paper=paper,
                           related=related, user=user)


@blueprint.route("/category/<path:cat_name>")
def category_page(cat_name):
    papers = _get_papers()
    filtered = [p for p in papers if cat_name in p["categories"] or
                p["top_category"] == cat_name]
    return render_template("academic-paper-db/category.html",
                           papers=filtered, category=cat_name,
                           categories=_get_top_categories())


@blueprint.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return render_template("academic-paper-db/login.html", error=None)
    user = _get_user(session["user_id"])
    if not user:
        return render_template("academic-paper-db/login.html", error=None)
    papers = _get_papers()
    saved = [p for p in papers if p["id"] in user.get("saved_papers", [])]
    return render_template("academic-paper-db/dashboard.html", user=user,
                           saved_papers=saved,
                           followed_authors=user.get("followed_authors", []))


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("academic-paper-db/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return render_template("academic-paper-db/login.html",
                               error="Invalid username or password")
    session["user_id"] = user["id"]
    return redirect(url_for("academic-paper-db.dashboard"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return render_template("academic-paper-db/login.html", error=None)


@blueprint.route("/compare")
def compare_page():
    ids_str = request.args.get("ids", "")
    papers = _get_papers()
    selected = []
    if ids_str:
        ids = [int(x) for x in ids_str.split(",") if x.strip().isdigit()]
        selected = [p for p in papers if p["id"] in ids]
    return render_template("academic-paper-db/compare.html", papers=papers,
                           selected=selected)


# ---------------------------------------------------------------------------
# Form-based mutation routes (for browser automation compatibility)
# ---------------------------------------------------------------------------

@blueprint.route("/paper/<int:paper_id>/save", methods=["POST"])
def form_save_paper(paper_id):
    if "user_id" not in session:
        return redirect(url_for("academic-paper-db.login_page"))
    users = _load_users()
    user = next((u for u in users if u["id"] == session["user_id"]), None)
    if not user:
        return redirect(url_for("academic-paper-db.login_page"))
    saved = user.setdefault("saved_papers", [])
    if paper_id in saved:
        saved.remove(paper_id)
    else:
        saved.append(paper_id)
    _save_users(users)
    return redirect(url_for("academic-paper-db.paper_detail", paper_id=paper_id))


@blueprint.route("/author/<path:author_name>/follow", methods=["POST"])
def form_follow_author(author_name):
    if "user_id" not in session:
        return redirect(url_for("academic-paper-db.login_page"))
    users = _load_users()
    user = next((u for u in users if u["id"] == session["user_id"]), None)
    if not user:
        return redirect(url_for("academic-paper-db.login_page"))
    followed = user.setdefault("followed_authors", [])
    if author_name in followed:
        followed.remove(author_name)
    else:
        followed.append(author_name)
    _save_users(users)
    referrer = request.form.get("redirect_to", "")
    if referrer:
        return redirect(referrer)
    return redirect(url_for("academic-paper-db.dashboard"))


@blueprint.route("/paper/<int:paper_id>/unsave", methods=["POST"])
def form_unsave_paper(paper_id):
    if "user_id" not in session:
        return redirect(url_for("academic-paper-db.login_page"))
    users = _load_users()
    user = next((u for u in users if u["id"] == session["user_id"]), None)
    if not user:
        return redirect(url_for("academic-paper-db.login_page"))
    saved = user.setdefault("saved_papers", [])
    if paper_id in saved:
        saved.remove(paper_id)
    _save_users(users)
    return redirect(url_for("academic-paper-db.dashboard"))


@blueprint.route("/author/<path:author_name>/unfollow", methods=["POST"])
def form_unfollow_author(author_name):
    if "user_id" not in session:
        return redirect(url_for("academic-paper-db.login_page"))
    users = _load_users()
    user = next((u for u in users if u["id"] == session["user_id"]), None)
    if not user:
        return redirect(url_for("academic-paper-db.login_page"))
    followed = user.setdefault("followed_authors", [])
    if author_name in followed:
        followed.remove(author_name)
    _save_users(users)
    return redirect(url_for("academic-paper-db.dashboard"))


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/papers")
def api_papers():
    papers = _get_papers()
    q = request.args.get("q", "").strip()
    cat = request.args.get("category", "").strip()
    date_from = request.args.get("date_from", type=int)
    date_to = request.args.get("date_to", type=int)
    sort = request.args.get("sort", "date")
    limit = request.args.get("limit", type=int)

    results = list(papers)
    if q:
        results = _search_papers(results, q)
    if cat:
        results = [p for p in results if p["top_category"] == cat or cat in p["categories"]]
    if date_from:
        results = [p for p in results if p["year"] >= date_from]
    if date_to:
        results = [p for p in results if p["year"] <= date_to]
    if sort == "date":
        results.sort(key=lambda p: (-p["year"], p["title"]))
    elif sort == "title":
        results.sort(key=lambda p: p["title"].lower())
    elif sort == "relevance" and q:
        results.sort(key=lambda p: -_keyword_score(q, p))
    if limit:
        results = results[:limit]
    return jsonify(results)


@blueprint.route("/api/papers/<int:paper_id>")
def api_paper(paper_id):
    papers = _get_papers()
    paper = next((p for p in papers if p["id"] == paper_id), None)
    if paper is None:
        abort(404)
    return jsonify(paper)


@blueprint.route("/api/papers/search")
def api_search():
    q = request.args.get("q", "").strip()
    papers = _get_papers()
    return jsonify(_search_papers(papers, q))


@blueprint.route("/api/papers/semantic")
def api_semantic_search():
    q = request.args.get("q", "").strip()
    papers = _get_papers()
    return jsonify(_search_papers(papers, q, semantic=True))


@blueprint.route("/api/categories")
def api_categories():
    papers = _get_papers()
    counts = Counter(p["top_category"] for p in papers)
    return jsonify([{"name": c, "count": n} for c, n in sorted(counts.items())])


@blueprint.route("/api/categories/<path:cat_name>/papers")
def api_category_papers(cat_name):
    papers = _get_papers()
    return jsonify([p for p in papers if cat_name in p["categories"] or
                    p["top_category"] == cat_name])


@blueprint.route("/api/categories/<path:cat_name>/stats")
def api_category_stats(cat_name):
    papers = _get_papers()
    filtered = [p for p in papers if cat_name in p["categories"] or
                p["top_category"] == cat_name]
    if not filtered:
        return jsonify({"category": cat_name, "count": 0})
    years = [p["year"] for p in filtered]
    authors = set()
    for p in filtered:
        authors.update(p["authors"])
    return jsonify({
        "category": cat_name,
        "count": len(filtered),
        "earliest_year": min(years),
        "latest_year": max(years),
        "unique_authors": len(authors),
        "avg_year": round(sum(years) / len(years), 1),
    })


@blueprint.route("/api/stats")
def api_stats():
    papers = _get_papers()
    cat = request.args.get("category", "").strip()
    if cat:
        papers = [p for p in papers if p["top_category"] == cat or cat in p["categories"]]
    if not papers:
        return jsonify({"count": 0})
    years = [p["year"] for p in papers]
    authors = set()
    for p in papers:
        authors.update(p["authors"])
    return jsonify({
        "count": len(papers),
        "earliest_year": min(years),
        "latest_year": max(years),
        "unique_authors": len(authors),
        "top_categories": dict(Counter(p["top_category"] for p in papers).most_common(10)),
    })


@blueprint.route("/api/compare")
def api_compare():
    ids_str = request.args.get("ids", "")
    ids = [int(x) for x in ids_str.split(",") if x.strip().isdigit()]
    papers = _get_papers()
    return jsonify([p for p in papers if p["id"] in ids])


@blueprint.route("/api/export")
def api_export():
    fmt = request.args.get("format", "json").lower()
    cat = request.args.get("category", "").strip()
    papers = list(_get_papers())
    if cat:
        papers = [p for p in papers if p["top_category"] == cat or cat in p["categories"]]

    if fmt == "csv":
        lines = ["id,arxiv_id,title,authors,primary_category,year,doi"]
        for p in papers:
            title = p["title"].replace('"', '""')
            authors = p["authors_str"].replace('"', '""')
            doi = (p["doi"] or "").replace('"', '""')
            lines.append(f'{p["id"]},"{p["arxiv_id"]}","{title}","{authors}","{p["primary_category"]}",{p["year"]},"{doi}"')
        return Response("\n".join(lines), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=papers.csv"})
    return jsonify(papers)


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
    return jsonify({"user_id": user["id"], "username": user["username"]})


@blueprint.route("/api/users/<int:user_id>")
def api_user(user_id):
    user = _get_user(user_id)
    if not user:
        abort(404)
    return jsonify({k: v for k, v in user.items() if k != "password"})


@blueprint.route("/api/users/<int:user_id>/save", methods=["POST"])
def api_save_paper(user_id):
    data = request.get_json(silent=True) or {}
    paper_id = data.get("paper_id")
    if paper_id is None:
        return jsonify({"error": "paper_id required"}), 400
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    saved = user.setdefault("saved_papers", [])
    if paper_id in saved:
        saved.remove(paper_id)
        action = "unsaved"
    else:
        saved.append(paper_id)
        action = "saved"
    _save_users(users)
    return jsonify({"action": action, "paper_id": paper_id, "total_saved": len(saved)})


@blueprint.route("/api/users/<int:user_id>/follow", methods=["POST"])
def api_follow_author(user_id):
    data = request.get_json(silent=True) or {}
    author = data.get("author", "").strip()
    if not author:
        return jsonify({"error": "author required"}), 400
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    followed = user.setdefault("followed_authors", [])
    if author in followed:
        followed.remove(author)
        action = "unfollowed"
    else:
        followed.append(author)
        action = "followed"
    _save_users(users)
    return jsonify({"action": action, "author": author, "total_followed": len(followed)})
