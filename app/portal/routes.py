import json
import re

from flask import Blueprint, jsonify, render_template, request

from app import discover_sites
from app import db

portal_bp = Blueprint(
    "portal",
    __name__,
    template_folder="templates",
)

# Words that carry no search intent — dropped before token matching so a query
# like "file my taxes" matches on "file"/"taxes", not "my".
_STOP = {
    "a", "an", "the", "my", "to", "find", "for", "on", "in", "of", "me", "i",
    "want", "how", "do", "can", "with", "and", "or", "is", "it", "get", "go",
    "new", "some", "that", "this", "at", "by", "your", "our", "we", "you",
}


def _site_text(s):
    """All searchable text for a site: brand name + description + category +
    functionality/intent keywords."""
    return " ".join([
        s.get("name", ""), s.get("description", ""),
        s.get("category", ""), s.get("keywords", ""),
    ]).lower()


def site_search_score(s, query):
    """Realistic relevance score for a site against a free-text query.

    Matches by brand name AND by what the site does / what the user wants to do.
    0 means no match. Higher is better; name hits outweigh keyword hits.
    """
    ql = (query or "").lower().strip()
    if not ql:
        return 0
    text = _site_text(s)
    name = s.get("name", "").lower()
    score = 0
    if ql in name:
        score += 20            # whole query is (part of) the brand name
    elif ql in text:
        score += 10            # whole query appears somewhere (desc/keywords)
    toks = [t for t in re.split(r"[^a-z0-9]+", ql) if len(t) >= 3 and t not in _STOP]
    for t in toks:
        if t in name:
            score += 4
        elif t in text:
            score += 3
    return score


def _ranked_sites(query, sites=None):
    """Sites matching the query, best first."""
    sites = sites if sites is not None else discover_sites()
    scored = [(site_search_score(s, query), s) for s in sites]
    return [s for sc, s in sorted(scored, key=lambda x: -x[0]) if sc > 0]


@portal_bp.route("/")
def index():
    sites = discover_sites()
    return render_template("portal/index.html", sites=sites, sites_json=json.dumps(sites))


@portal_bp.route("/api/sites")
def api_sites():
    q = request.args.get("q", "").strip()
    sites = discover_sites()
    if q:
        sites = _ranked_sites(q, sites)
    return jsonify(sites)


@portal_bp.route("/api/search")
def api_search():
    """Search across MiniWeb sites AND external web entries.

    Sites match by brand name OR by functionality/intent keywords (realistic:
    "spreadsheet", "edit a spreadsheet", "file my taxes" all resolve), ranked by
    relevance; then the search-engine index is appended.
    """
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    results = []

    # 1) MiniWeb sites, ranked by name/functionality relevance
    for s in _ranked_sites(q):
        results.append({
            "url": s["path"],
            "title": s["name"],
            "snippet": s.get("description", "") or s.get("keywords", ""),
            "domain": s.get("domain", s["id"] + ".lakeport.local"),
            "is_miniweb": True,
        })
    seen = {r["url"] for r in results}

    # 2) Search-engine index (MiniWeb pages + external entries) for the long tail
    ql = f"%{q.lower()}%"
    try:
        rows = db.execute(
            "SELECT url, title, snippet, domain, relevance_boost FROM search_engines_index "
            "WHERE LOWER(title) LIKE ? OR LOWER(snippet) LIKE ? OR LOWER(domain) LIKE ? "
            "ORDER BY relevance_boost DESC, title ASC LIMIT 20",
            (ql, ql, ql))
        for r in rows:
            if r["url"] in seen:
                continue
            results.append({
                "url": r["url"],
                "title": r["title"],
                "snippet": r["snippet"],
                "domain": r["domain"],
                "is_miniweb": r["url"].startswith("/sites/"),
            })
    except Exception:
        pass

    return jsonify(results)
