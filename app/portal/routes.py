import json

from flask import Blueprint, jsonify, render_template, request

from app import discover_sites
from app import db

portal_bp = Blueprint(
    "portal",
    __name__,
    template_folder="templates",
)


@portal_bp.route("/")
def index():
    sites = discover_sites()
    return render_template("portal/index.html", sites=sites, sites_json=json.dumps(sites))


@portal_bp.route("/api/sites")
def api_sites():
    q = request.args.get("q", "").lower().strip()
    sites = discover_sites()
    if q:
        sites = [
            s for s in sites
            if q in s["name"].lower()
            or q in s.get("description", "").lower()
            or any(q in t.lower() for t in s.get("tags", []))
        ]
    return jsonify(sites)


@portal_bp.route("/api/search")
def api_search():
    """Search across MiniWeb sites AND external web entries."""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    results = []
    ql = f"%{q.lower()}%"

    # Search the search_engines_index (both MiniWeb and external)
    try:
        rows = db.execute(
            "SELECT url, title, snippet, domain, relevance_boost FROM search_engines_index "
            "WHERE LOWER(title) LIKE ? OR LOWER(snippet) LIKE ? OR LOWER(domain) LIKE ? "
            "ORDER BY relevance_boost DESC, title ASC LIMIT 20",
            (ql, ql, ql))
        for r in rows:
            results.append({
                "url": r["url"],
                "title": r["title"],
                "snippet": r["snippet"],
                "domain": r["domain"],
                "is_miniweb": r["url"].startswith("/sites/"),
            })
    except Exception:
        pass

    # Also search MiniWeb site names/descriptions
    sites = discover_sites()
    for s in sites:
        if q.lower() in s["name"].lower() or q.lower() in s.get("description", "").lower():
            # Check if already in results
            if not any(r["url"] == s["path"] for r in results):
                results.insert(0, {
                    "url": s["path"],
                    "title": s["name"],
                    "snippet": s.get("description", ""),
                    "domain": s["id"] + ".lakeport.local",
                    "is_miniweb": True,
                })

    return jsonify(results)
