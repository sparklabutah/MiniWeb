"""Academic Paper DB — arXiv paper search engine (Google Scholar / Semantic Scholar style).

Data is stored in SQLite: arxiv papers in the raw_data table, users in a
per-site typed table.  Queried through app.db.
"""
import pathlib
import re
from collections import Counter

from flask import Blueprint, Response, abort, jsonify, redirect, render_template, request, session, url_for
from app import db
from app.db import _deserialize_row
from app.events import emit
from app.handlers.email_handler import _add_email

SITE = "academic-paper-db"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "academic-paper-db",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data interpreter — cleans raw arxiv JSON into display-ready dicts
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


# ---------------------------------------------------------------------------
# DB-backed data access — queries academic_paper_db_papers directly
# ---------------------------------------------------------------------------

_TABLE = "academic_paper_db_papers"


def _query_papers(q="", cat="", checked_cats=None, date_from=None, date_to=None,
                  sort="date", limit=50, offset=0):
    """Query papers with filters pushed to SQL on real columns."""

    conn = db.get_conn()
    clauses = []
    params = []

    if q:
        clauses.append("(title LIKE ? OR abstract LIKE ? OR authors_parsed LIKE ?)")
        params.extend([f"%{q}%"] * 3)
    if cat:
        clauses.append("categories LIKE ?")
        params.append(f"%{cat}%")
    if checked_cats:
        cat_clauses = ["categories LIKE ?" for _ in checked_cats]
        clauses.append(f"({' OR '.join(cat_clauses)})")
        params.extend(f"%{c}%" for c in checked_cats)
    # Publication year lives in the arXiv id prefix (YYMM.xxxxx — every row
    # in this dataset is new-style), which matches the year shown to users
    # (_extract_year from versions[0].created). update_date is arXiv's
    # last-modified date and is ~always recent, so filtering on it is a no-op.
    _year_expr = "(2000 + CAST(substr(id, 1, 2) AS INTEGER))"
    if date_from:
        clauses.append(f"{_year_expr} >= ?")
        params.append(int(date_from))
    if date_to:
        clauses.append(f"{_year_expr} <= ?")
        params.append(int(date_to))

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    # Relevance: keyword-overlap ranking over a bounded candidate window
    # (only meaningful with a query; without one it falls back to date).
    if sort == "relevance" and q:
        window = max((offset + limit) * 5, 250)
        sql = f"SELECT rowid, * FROM [{_TABLE}]{where} ORDER BY update_date DESC LIMIT ?"
        rows = conn.execute(sql, params + [window]).fetchall()
        papers = [_interpret_record(_deserialize_row(r), r["rowid"]) for r in rows]
        papers.sort(key=lambda p: -_keyword_score(q, p))
        return papers[offset:offset + limit]

    # Normal path: ORDER BY in SQL
    if sort == "title":
        order = " ORDER BY title ASC"
    else:
        order = " ORDER BY update_date DESC"

    sql = f"SELECT rowid, * FROM [{_TABLE}]{where}{order} LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    rows = conn.execute(sql, params).fetchall()
    return [_interpret_record(_deserialize_row(r), r["rowid"]) for r in rows]




def _get_paper_by_row(paper_id):
    """Look up a paper by numeric row offset."""
    conn = db.get_conn()
    row = conn.execute(f"SELECT rowid, * FROM [{_TABLE}] LIMIT 1 OFFSET ?", (paper_id - 1,)).fetchone()
    if not row:
        return None
    return _interpret_record(_deserialize_row(row), paper_id)


_total_papers_cache = None

def _count_papers_db(q="", cat=""):
    global _total_papers_cache
    conn = db.get_conn()
    if not q and not cat:
        if _total_papers_cache is None:
            _total_papers_cache = conn.execute(f"SELECT COUNT(*) FROM [{_TABLE}]").fetchone()[0]
        return _total_papers_cache
    if q:
        clauses = ["(title LIKE ? OR abstract LIKE ? OR authors_parsed LIKE ?)"]
        params = [f"%{q}%"] * 3
        if cat:
            clauses.append("categories LIKE ?")
            params.append(f"%{cat}%")
        where = " WHERE " + " AND ".join(clauses)
        cap = 500
        return conn.execute(
            f"SELECT COUNT(*) FROM (SELECT 1 FROM [{_TABLE}]{where} LIMIT ?)",
            params + [cap],
        ).fetchone()[0]
    # Category-only count
    clauses = []
    params = []
    if cat:
        clauses.append("categories LIKE ?")
        params.append(f"%{cat}%")
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    cap = 500
    return conn.execute(
        f"SELECT COUNT(*) FROM (SELECT 1 FROM [{_TABLE}]{where} LIMIT ?)",
        params + [cap],
    ).fetchone()[0]


_categories_cache = None

def _get_categories_db():
    global _categories_cache
    if _categories_cache is not None:
        return _categories_cache
    conn = db.get_conn()
    rows = conn.execute(f"SELECT categories FROM [{_TABLE}] LIMIT 5000").fetchall()
    top_cats = set()
    all_cats = Counter()
    for row in rows:
        cats_str = row[0] or ""
        for c in cats_str.split():
            all_cats[c] += 1
            top_cats.add(c.split(".")[0])
    _categories_cache = (sorted(top_cats), sorted(all_cats.keys()))
    return _categories_cache


def _related_papers(paper, limit=5):
    """Find papers with the same primary category."""
    conn = db.get_conn()
    rows = conn.execute(
        f"SELECT rowid, * FROM [{_TABLE}] WHERE categories LIKE ? AND id != ? LIMIT ?",
        (f"%{paper['primary_category']}%", paper["arxiv_id"], limit),
    ).fetchall()
    return [_interpret_record(_deserialize_row(r), r["rowid"]) for r in rows]


# ---------------------------------------------------------------------------
# Unified accessors
# ---------------------------------------------------------------------------

def _get_papers(q="", cat="", checked_cats=None, date_from=None, date_to=None,
                sort="date", limit=50, offset=0):
    return _query_papers(q, cat, checked_cats, date_from, date_to, sort, limit, offset)


def _get_paper(paper_id):
    return _get_paper_by_row(paper_id)


def _get_categories():
    return _get_categories_db()


def _count_papers(q="", cat=""):
    return _count_papers_db(q, cat)


# ---------------------------------------------------------------------------
# Users (mutable state — stored in per-site SQLite table)
# ---------------------------------------------------------------------------

def _load_users():
    return db.query(SITE, "users")


def _save_users(users):
    db.save_collection(SITE, "users", users)


def _get_user(user_id):
    return db.get_item(SITE, "users", user_id)


# ---------------------------------------------------------------------------
# Search helpers
# ---------------------------------------------------------------------------

def _keyword_score(query, paper):
    """Occurrence-weighted relevance: title hits count 3x, author/category 2x."""
    terms = query.lower().split()
    title = paper["title"].lower()
    abstract = paper["abstract"].lower()
    other = (" ".join(paper["authors"]) + " " + " ".join(paper["categories"])).lower()
    return sum(3 * title.count(t) + abstract.count(t) + 2 * other.count(t)
               for t in terms)


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
    top_cats, all_cats = _get_categories()
    q = request.args.get("q", "").strip()
    cat = request.args.get("category", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    sort = request.args.get("sort", "date").strip()
    checked_cats = request.args.getlist("cats")

    df = int(date_from) if date_from.isdigit() else None
    dt = int(date_to) if date_to.isdigit() else None

    results = _get_papers(q=q, cat=cat, checked_cats=checked_cats or None,
                          date_from=df, date_to=dt, sort=sort, limit=50)
    total = _count_papers(q=q, cat=cat)

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template("academic-paper-db/index.html",
                           papers=results, categories=top_cats,
                           all_categories=all_cats,
                           q=q, cat=cat, date_from=date_from, date_to=date_to,
                           sort=sort, checked_cats=checked_cats, user=user,
                           total=total)


def _bibtex(paper):
    """Build a BibTeX entry for a paper."""
    authors = paper.get("authors", []) or []
    author_field = " and ".join(authors) if authors else "Unknown"
    year = paper.get("year") or "n.d."
    title = (paper.get("title") or "").strip()
    first_last = (authors[0].split()[-1] if authors and authors[0].split() else "unknown").lower()
    first_word = re.sub(r"[^a-z0-9]", "", (title.split()[0].lower() if title else "paper"))
    key = f"{first_last}{year}{first_word}"
    lines = ["@article{%s," % key,
             "  title        = {%s}," % title,
             "  author       = {%s}," % author_field,
             "  year         = {%s}," % year]
    if paper.get("arxiv_id"):
        lines.append("  eprint       = {%s}," % paper["arxiv_id"])
        lines.append("  archivePrefix= {arXiv},")
    if paper.get("primary_category"):
        lines.append("  primaryClass = {%s}," % paper["primary_category"])
    if paper.get("journal_ref"):
        lines.append("  journal      = {%s}," % paper["journal_ref"])
    if paper.get("doi"):
        lines.append("  doi          = {%s}," % paper["doi"])
    lines.append("}")
    return "\n".join(lines)


@blueprint.route("/paper/<int:paper_id>")
def paper_detail(paper_id):
    paper = _get_paper(paper_id)
    if paper is None:
        abort(404)
    related = _related_papers(paper)
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("academic-paper-db/paper.html", paper=paper,
                           related=related, user=user, bibtex=_bibtex(paper))


@blueprint.route("/category/<path:cat_name>")
def category_page(cat_name):
    top_cats, _ = _get_categories()
    papers = _get_papers(cat=cat_name, limit=50)
    return render_template("academic-paper-db/category.html",
                           papers=papers, category=cat_name,
                           categories=top_cats)


@blueprint.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return render_template("academic-paper-db/login.html", error=None)
    user = _get_user(session["user_id"])
    if not user:
        return render_template("academic-paper-db/login.html", error=None)
    saved_ids = user.get("saved_papers", [])
    saved = []
    for pid in saved_ids:
        p = _get_paper(pid)
        if p:
            saved.append(p)
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
    emit("signup", user_id=user["id"], site_name="academic-paper-db", username=request.form.get("username", ""), password=request.form.get("password", ""), email="")
    return redirect(url_for("academic-paper-db.dashboard"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return render_template("academic-paper-db/login.html", error=None)


@blueprint.route("/compare")
def compare_page():
    ids_str = request.args.get("ids", "")
    selected = []
    if ids_str:
        ids = [int(x) for x in ids_str.split(",") if x.strip().isdigit()]
        selected = [p for pid in ids if (p := _get_paper(pid))]
    all_papers = _get_papers(limit=50)
    return render_template("academic-paper-db/compare.html", papers=all_papers,
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
        _add_email(session["user_id"], "noreply@academic-paper-db.lakeport.local",
                   "Paper saved to your library",
                   f"Paper #{paper_id} has been saved to your library. You can view your saved papers from the dashboard.")
    _save_users(users)
    return redirect(url_for("academic-paper-db.paper_detail", paper_id=paper_id))


def _paper_citations(paper):
    """Deterministic synthetic citation count (arXiv metadata has none)."""
    import zlib
    key = str(paper.get("arxiv_id") or paper.get("id") or paper.get("title", ""))
    base = zlib.crc32(key.encode()) % 240
    try:
        age = max(0, 2026 - int(paper.get("year") or 2020))
    except (TypeError, ValueError):
        age = 3
    return int(base * (1 + age * 0.45))


@blueprint.route("/author/<path:author_name>")
def author_profile(author_name):
    """Author profile page (Google Scholar style) with publications + stats."""
    # authors_parsed stores [["Last", "First", ""], ...] while author_name is
    # "First Last" — match the JSON layout directly in SQL.
    parts = author_name.strip().rsplit(" ", 1)
    if len(parts) == 2:
        pattern = f'%"{parts[1]}", "{parts[0]}%'
    else:
        pattern = f'%"{parts[0]}"%'
    conn = db.get_conn()
    rows = conn.execute(
        f"SELECT rowid, * FROM [{_TABLE}] WHERE authors_parsed LIKE ? "
        "ORDER BY update_date DESC LIMIT 100",
        (pattern,)).fetchall()
    author_papers = [_interpret_record(_deserialize_row(r), r["rowid"]) for r in rows]

    # Citation-based stats (Google Scholar style).
    for p in author_papers:
        p["citations"] = _paper_citations(p)
    cites = sorted((p["citations"] for p in author_papers), reverse=True)
    h_index = 0
    for n, c in enumerate(cites, 1):
        if c >= n:
            h_index = n
        else:
            break
    stats = {
        "papers": len(author_papers),
        "citations": sum(cites),
        "h_index": h_index,
        "i10": sum(1 for c in cites if c >= 10),
    }

    # Collaborators (co-authors across the author's papers).
    from collections import Counter
    collab = Counter()
    for p in author_papers:
        for a in p.get("authors", []):
            if a and a.strip() and a.strip() != author_name:
                collab[a.strip()] += 1
    collaborators = [{"name": n, "count": c} for n, c in collab.most_common(12)]

    user = None
    is_followed = False
    if "user_id" in session:
        user = _get_user(session["user_id"])
        if user:
            is_followed = author_name in user.get("followed_authors", [])

    return render_template("academic-paper-db/author.html",
                           author_name=author_name,
                           papers=author_papers[:20],
                           stats=stats, collaborators=collaborators,
                           user=user, is_followed=is_followed)


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
    q = request.args.get("q", "").strip()
    cat = request.args.get("category", "").strip()
    date_from = request.args.get("date_from", type=int)
    date_to = request.args.get("date_to", type=int)
    sort = request.args.get("sort", "date")
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)

    results = _get_papers(q=q, cat=cat, date_from=date_from, date_to=date_to,
                          sort=sort, limit=limit, offset=offset)
    return jsonify(results)


@blueprint.route("/api/papers/<int:paper_id>")
def api_paper(paper_id):
    paper = _get_paper(paper_id)
    if paper is None:
        abort(404)
    return jsonify(paper)


@blueprint.route("/api/papers/search")
def api_search():
    q = request.args.get("q", "").strip()
    limit = request.args.get("limit", 50, type=int)
    results = _get_papers(q=q, sort="relevance", limit=limit)
    return jsonify(results)


@blueprint.route("/api/papers/semantic")
def api_semantic_search():
    q = request.args.get("q", "").strip()
    limit = request.args.get("limit", 50, type=int)
    results = _get_papers(q=q, sort="relevance", limit=limit)
    return jsonify(results)


@blueprint.route("/api/categories")
def api_categories():
    top_cats, _ = _get_categories()
    counts = []
    for c in top_cats:
        n = _count_papers(cat=c)
        counts.append({"name": c, "count": n})
    return jsonify(sorted(counts, key=lambda x: x["name"]))


@blueprint.route("/api/categories/<path:cat_name>/papers")
def api_category_papers(cat_name):
    limit = request.args.get("limit", 50, type=int)
    return jsonify(_get_papers(cat=cat_name, limit=limit))


@blueprint.route("/api/categories/<path:cat_name>/stats")
def api_category_stats(cat_name):
    papers = _get_papers(cat=cat_name, limit=1000)
    if not papers:
        return jsonify({"category": cat_name, "count": 0})
    years = [p["year"] for p in papers]
    authors = set()
    for p in papers:
        authors.update(p["authors"])
    return jsonify({
        "category": cat_name,
        "count": _count_papers(cat=cat_name),
        "earliest_year": min(years),
        "latest_year": max(years),
        "unique_authors": len(authors),
        "avg_year": round(sum(years) / len(years), 1),
    })


@blueprint.route("/api/stats")
def api_stats():
    cat = request.args.get("category", "").strip()
    total = _count_papers(cat=cat)
    if total == 0:
        return jsonify({"count": 0})
    papers = _get_papers(cat=cat, limit=1000)
    years = [p["year"] for p in papers]
    authors = set()
    for p in papers:
        authors.update(p["authors"])
    return jsonify({
        "count": total,
        "earliest_year": min(years) if years else 0,
        "latest_year": max(years) if years else 0,
        "unique_authors": len(authors),
        "top_categories": dict(Counter(p["top_category"] for p in papers).most_common(10)),
    })


@blueprint.route("/api/compare")
def api_compare():
    ids_str = request.args.get("ids", "")
    ids = [int(x) for x in ids_str.split(",") if x.strip().isdigit()]
    return jsonify([p for pid in ids if (p := _get_paper(pid))])


@blueprint.route("/api/export")
def api_export():
    fmt = request.args.get("format", "json").lower()
    cat = request.args.get("category", "").strip()
    limit = request.args.get("limit", 1000, type=int)
    papers = _get_papers(cat=cat, limit=limit)

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
