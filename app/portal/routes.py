from flask import Blueprint, jsonify, render_template, request

from app import discover_sites

portal_bp = Blueprint(
    "portal",
    __name__,
    template_folder="templates",
)


@portal_bp.route("/")
def index():
    return render_template("portal/index.html", sites=discover_sites())


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
