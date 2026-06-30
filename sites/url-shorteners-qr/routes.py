"""SnapLink URL Shortener -- shorten URLs, generate QR codes, track clicks.

Inspired by Bitly / TinyURL / Rebrandly.  Data lives under data_sources/
and is reset from .pristine/ between evaluation runs.

Supported macros:
  navigate_by_query, navigate_by_route, search_by_query,
  filter_by_date_range, extract_by_query, extract_from_table,
  edit_by_query, edit_by_date_range, delete_from_table,
  configure_by_dropdown, export_by_dropdown, share_by_dropdown,
  create_by_query, create_from_free_text, create_by_toggle
"""
import csv
import io
import json
import pathlib
import re
import string
import random
from collections import Counter
from datetime import datetime

from flask import (
    Blueprint, Response, abort, jsonify, redirect, render_template, request,
    session, url_for,
)
from app import db

SITE = "url-shorteners-qr"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "url-shorteners-qr",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _load_users():
    return db.query(SITE, "users")

def _load_links():
    return db.query(SITE, "links")

def _save_links(links):
    db.save_collection(SITE, "links", links)

def _load_clicks():
    return db.query(SITE, "click_stats")

def _save_clicks(clicks):
    db.save_collection(SITE, "click_stats", clicks)

def _get_user(user_id):
    return db.get_item(SITE, "users", user_id)

def _get_current_user():
    if "user_id" in session:
        return _get_user(session["user_id"])
    return None

def _get_browsing_user():
    user = _get_current_user()
    if user:
        return user, True
    return _get_user(1), False

def _generate_short_code(length=6):
    chars = string.ascii_lowercase + string.digits
    return "".join(random.choice(chars) for _ in range(length))


def _filter_links(links, args):
    """Shared filtering logic used by HTML and API routes."""
    q = args.get("q", "").strip().lower()
    status = args.get("status", "").strip()
    tag = args.get("tag", "").strip().lower()
    date_from = args.get("date_from", "").strip()
    date_to = args.get("date_to", "").strip()

    if q:
        links = [l for l in links if q in l.get("title", "").lower()
                 or q in l.get("original_url", "").lower()
                 or q in l.get("short_code", "").lower()
                 or any(q in t.lower() for t in l.get("tags", []))]
    if status == "active":
        links = [l for l in links if l["is_active"]]
    elif status == "inactive":
        links = [l for l in links if not l["is_active"]]
    if tag:
        links = [l for l in links if tag in [t.lower() for t in l.get("tags", [])]]
    if date_from:
        links = [l for l in links if l["created_at"][:10] >= date_from]
    if date_to:
        links = [l for l in links if l["created_at"][:10] <= date_to]

    sort = args.get("sort", "newest").strip()
    if sort == "clicks":
        links.sort(key=lambda l: l["clicks"], reverse=True)
    elif sort == "oldest":
        links.sort(key=lambda l: l["created_at"])
    else:
        links.sort(key=lambda l: l["created_at"], reverse=True)
    return links


def _build_link(links, original_url, title, custom_code, owner_id,
                expires_at=None, redirect_type="301", tags=None,
                qr_enabled=True, utm_source="", utm_medium="", utm_campaign=""):
    """Build and append a new link record."""
    short_code = custom_code if custom_code else _generate_short_code()
    existing_codes = {l["short_code"] for l in links}
    if custom_code and custom_code in existing_codes:
        return None, "Short code already in use"
    while short_code in existing_codes:
        short_code = _generate_short_code()

    new_id = max((l["id"] for l in links), default=0) + 1
    link = {
        "id": new_id,
        "short_code": short_code,
        "original_url": original_url,
        "title": title or original_url[:50],
        "owner_id": owner_id,
        "created_at": datetime.now().isoformat(),
        "clicks": 0,
        "is_active": True,
        "expires_at": expires_at,
        "redirect_type": redirect_type,
        "tags": tags or [],
        "qr_enabled": qr_enabled,
        "utm_source": utm_source or "",
        "utm_medium": utm_medium or "",
        "utm_campaign": utm_campaign or "",
    }
    links.append(link)
    return link, None


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    user, logged_in = _get_browsing_user()
    links = [l for l in _load_links() if l["owner_id"] == user["id"]]
    links.sort(key=lambda l: l["created_at"], reverse=True)
    return render_template("url-shorteners-qr/index.html", user=user,
                           links=links[:5], logged_in=logged_in)


@blueprint.route("/links")
def links_page():
    """My Links page -- supports navigate_by_query, search_by_query,
    filter_by_date_range via query params q, status, date_from, date_to, tag."""
    user, logged_in = _get_browsing_user()
    links = [l for l in _load_links() if l["owner_id"] == user["id"]]
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    tag = request.args.get("tag", "").strip()
    sort = request.args.get("sort", "newest").strip()
    links = _filter_links(links, request.args)
    return render_template("url-shorteners-qr/links.html", user=user,
                           links=links, logged_in=logged_in,
                           q=q, status=status, sort=sort,
                           date_from=date_from, date_to=date_to, tag=tag)


@blueprint.route("/link/<int:link_id>")
def link_detail(link_id):
    """Link detail page -- supports navigate_by_route, extract_from_table."""
    user, logged_in = _get_browsing_user()
    links = _load_links()
    link = next((l for l in links if l["id"] == link_id), None)
    if not link:
        abort(404)
    clicks = [c for c in _load_clicks() if c["link_id"] == link_id]
    clicks.sort(key=lambda c: c["timestamp"], reverse=True)
    # Aggregate stats
    countries = Counter(c["country"] for c in clicks)
    devices = Counter(c["device"] for c in clicks)
    referrers = Counter(c["referrer"] for c in clicks)
    return render_template("url-shorteners-qr/link_detail.html", user=user,
                           link=link, clicks=clicks[:20],
                           countries=dict(countries.most_common(10)),
                           devices=dict(devices),
                           referrers=dict(referrers.most_common(10)),
                           logged_in=logged_in)


@blueprint.route("/qr/<int:link_id>")
def qr_page(link_id):
    user, logged_in = _get_browsing_user()
    links = _load_links()
    link = next((l for l in links if l["id"] == link_id), None)
    if not link:
        abort(404)
    return render_template("url-shorteners-qr/qr.html", user=user,
                           link=link, logged_in=logged_in)


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("url-shorteners-qr/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return render_template("url-shorteners-qr/login.html",
                               error="Invalid username or password")
    session["user_id"] = user["id"]
    return redirect(url_for("url-shorteners-qr.index"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("url-shorteners-qr.index"))


@blueprint.route("/create", methods=["POST"])
def create_link_form():
    """Form-based link creation -- supports create_by_toggle (qr_enabled checkbox)."""
    user = _get_current_user()
    if not user:
        return render_template("url-shorteners-qr/login.html",
                               error="Please log in first")
    original_url = request.form.get("original_url", "").strip()
    title = request.form.get("title", "").strip() or original_url[:50]
    custom_code = request.form.get("short_code", "").strip()
    expires_at = request.form.get("expires_at", "").strip() or None
    redirect_type = request.form.get("redirect_type", "301").strip()
    qr_enabled = request.form.get("qr_enabled") == "on"
    tags_raw = request.form.get("tags", "").strip()
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []

    if not original_url:
        links = [l for l in _load_links() if l["owner_id"] == user["id"]]
        return render_template("url-shorteners-qr/index.html", user=user,
                               links=links[:5], logged_in=True,
                               error="URL is required")

    links = _load_links()
    link, err = _build_link(links, original_url, title, custom_code,
                            user["id"], expires_at=expires_at,
                            redirect_type=redirect_type, tags=tags,
                            qr_enabled=qr_enabled)
    if err:
        user_links = [l for l in links if l["owner_id"] == user["id"]]
        return render_template("url-shorteners-qr/index.html", user=user,
                               links=user_links[:5], logged_in=True,
                               error=err)
    _save_links(links)
    return redirect(url_for("url-shorteners-qr.link_detail", link_id=link["id"]))


@blueprint.route("/link/<int:link_id>/edit", methods=["POST"])
def edit_link_form(link_id):
    """Form-based link edit -- supports edit_by_query (title, url)."""
    user = _get_current_user()
    if not user:
        return redirect(url_for("url-shorteners-qr.login_page"))
    links = _load_links()
    link = next((l for l in links if l["id"] == link_id), None)
    if not link:
        abort(404)
    for field in ("title", "original_url", "expires_at", "redirect_type",
                  "utm_source", "utm_medium", "utm_campaign"):
        val = request.form.get(field, "").strip()
        if val:
            link[field] = val
    tags_raw = request.form.get("tags", "").strip()
    if tags_raw:
        link["tags"] = [t.strip() for t in tags_raw.split(",") if t.strip()]
    _save_links(links)
    return redirect(url_for("url-shorteners-qr.link_detail", link_id=link_id))


@blueprint.route("/link/<int:link_id>/toggle", methods=["POST"])
def toggle_link(link_id):
    user = _get_current_user()
    if not user:
        return redirect(url_for("url-shorteners-qr.login_page"))
    links = _load_links()
    link = next((l for l in links if l["id"] == link_id), None)
    if link:
        link["is_active"] = not link["is_active"]
        _save_links(links)
    return redirect(url_for("url-shorteners-qr.link_detail", link_id=link_id))


@blueprint.route("/link/<int:link_id>/delete", methods=["POST"])
def delete_link_form(link_id):
    """Form-based delete -- supports delete_from_table."""
    user = _get_current_user()
    if not user:
        return redirect(url_for("url-shorteners-qr.login_page"))
    links = _load_links()
    links = [l for l in links if l["id"] != link_id]
    _save_links(links)
    # Also remove associated clicks
    clicks = _load_clicks()
    clicks = [c for c in clicks if c["link_id"] != link_id]
    _save_clicks(clicks)
    return redirect(url_for("url-shorteners-qr.links_page"))


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/login", methods=["POST"])
def api_login():
    """API login endpoint."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return jsonify({"error": "Invalid credentials"}), 401
    session["user_id"] = user["id"]
    return jsonify({"user_id": user["id"], "username": user["username"],
                    "name": user["name"]})


@blueprint.route("/api/users/<int:user_id>")
def api_user(user_id):
    """Get user info (without password)."""
    user = _get_user(user_id)
    if not user:
        abort(404)
    return jsonify({k: v for k, v in user.items() if k != "password"})


@blueprint.route("/api/links", methods=["GET"])
def api_links_list():
    """List/search/filter links -- supports search_by_query, filter_by_date_range,
    navigate_by_query."""
    links = _load_links()
    owner_id = request.args.get("owner_id", type=int)
    if owner_id:
        links = [l for l in links if l["owner_id"] == owner_id]
    links = _filter_links(links, request.args)
    return jsonify(links)


@blueprint.route("/api/links", methods=["POST"])
def api_links_create():
    """Create link via JSON body -- supports create_by_query, create_by_toggle,
    create_from_free_text."""
    data = request.get_json(silent=True) or {}
    original_url = data.get("original_url", "").strip()

    # create_from_free_text: parse a natural-language description
    free_text = data.get("free_text", "").strip()
    if free_text and not original_url:
        # Extract URL from free text
        url_match = re.search(r'https?://\S+', free_text)
        if url_match:
            original_url = url_match.group(0).rstrip(".,;)")
        # Extract title: anything before the URL or the whole text
        title_candidate = free_text
        if url_match:
            title_candidate = free_text[:url_match.start()].strip()
            if not title_candidate:
                title_candidate = free_text[url_match.end():].strip()
        # Strip common prefixes
        for prefix in ("shorten ", "create ", "make ", "link "):
            if title_candidate.lower().startswith(prefix):
                title_candidate = title_candidate[len(prefix):]
        data.setdefault("title", title_candidate.strip(" -:,") or original_url[:50] if original_url else "")

    if not original_url:
        return jsonify({"error": "original_url is required"}), 400

    title = data.get("title", "").strip() or original_url[:50]
    custom_code = data.get("short_code", "").strip()
    owner_id = data.get("owner_id")
    expires_at = data.get("expires_at")
    redirect_type = data.get("redirect_type", "301")
    tags = data.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    qr_enabled = data.get("qr_enabled", True)  # create_by_toggle
    utm_source = data.get("utm_source", "")
    utm_medium = data.get("utm_medium", "")
    utm_campaign = data.get("utm_campaign", "")

    if not owner_id:
        user = _get_current_user()
        owner_id = user["id"] if user else 1

    links = _load_links()
    link, err = _build_link(links, original_url, title, custom_code,
                            owner_id, expires_at=expires_at,
                            redirect_type=redirect_type, tags=tags,
                            qr_enabled=qr_enabled,
                            utm_source=utm_source, utm_medium=utm_medium,
                            utm_campaign=utm_campaign)
    if err:
        return jsonify({"error": err}), 409
    _save_links(links)
    return jsonify(link), 201


@blueprint.route("/api/links/create")
def api_links_create_get():
    """Create link via GET query params -- supports create_by_query.
    e.g. /api/links/create?url=https://...&title=My+Link&qr=true"""
    original_url = request.args.get("url", "").strip()
    if not original_url:
        return jsonify({"error": "url query parameter is required"}), 400

    title = request.args.get("title", "").strip() or original_url[:50]
    custom_code = request.args.get("code", "").strip()
    owner_id = request.args.get("owner_id", type=int)
    expires_at = request.args.get("expires_at", "").strip() or None
    redirect_type = request.args.get("redirect_type", "301").strip()
    qr_str = request.args.get("qr", "true").strip().lower()
    qr_enabled = qr_str not in ("false", "0", "no", "off")
    tags_raw = request.args.get("tags", "").strip()
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []

    if not owner_id:
        user = _get_current_user()
        owner_id = user["id"] if user else 1

    links = _load_links()
    link, err = _build_link(links, original_url, title, custom_code,
                            owner_id, expires_at=expires_at,
                            redirect_type=redirect_type, tags=tags,
                            qr_enabled=qr_enabled)
    if err:
        return jsonify({"error": err}), 409
    _save_links(links)
    return jsonify(link), 201


@blueprint.route("/api/links/<int:link_id>", methods=["GET"])
def api_link_get(link_id):
    links = _load_links()
    link = next((l for l in links if l["id"] == link_id), None)
    if not link:
        abort(404)
    return jsonify(link)


@blueprint.route("/api/links/<int:link_id>", methods=["PUT"])
def api_link_update(link_id):
    """Update link -- supports edit_by_query, edit_by_date_range (expires_at),
    configure_by_dropdown (redirect_type, tags, utm_*)."""
    data = request.get_json(silent=True) or {}
    links = _load_links()
    link = next((l for l in links if l["id"] == link_id), None)
    if not link:
        abort(404)
    for field in ("title", "original_url", "is_active", "expires_at",
                  "redirect_type", "qr_enabled",
                  "utm_source", "utm_medium", "utm_campaign"):
        if field in data:
            link[field] = data[field]
    if "tags" in data:
        tags = data["tags"]
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        link["tags"] = tags
    if "short_code" in data:
        new_code = data["short_code"].strip()
        existing = {l["short_code"] for l in links if l["id"] != link_id}
        if new_code in existing:
            return jsonify({"error": "Short code already in use"}), 409
        link["short_code"] = new_code
    _save_links(links)
    return jsonify(link)


@blueprint.route("/api/links/<int:link_id>/configure", methods=["PUT"])
def api_link_configure(link_id):
    """Configure link settings -- supports configure_by_dropdown.
    Accepts: redirect_type (301/302/307), qr_enabled, utm_source/medium/campaign."""
    data = request.get_json(silent=True) or {}
    links = _load_links()
    link = next((l for l in links if l["id"] == link_id), None)
    if not link:
        abort(404)
    for field in ("redirect_type", "qr_enabled", "utm_source", "utm_medium",
                  "utm_campaign"):
        if field in data:
            link[field] = data[field]
    if "tags" in data:
        tags = data["tags"]
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        link["tags"] = tags
    _save_links(links)
    return jsonify(link)


@blueprint.route("/api/links/<int:link_id>/expiration", methods=["PUT"])
def api_link_set_expiration(link_id):
    """Set link expiration -- supports edit_by_date_range.
    Accepts JSON: {"expires_at": "2026-12-31T23:59:59"}"""
    data = request.get_json(silent=True) or {}
    links = _load_links()
    link = next((l for l in links if l["id"] == link_id), None)
    if not link:
        abort(404)
    if "expires_at" in data:
        link["expires_at"] = data["expires_at"]
    _save_links(links)
    return jsonify(link)


@blueprint.route("/api/links/<int:link_id>", methods=["DELETE"])
def api_link_delete(link_id):
    """Delete link -- supports delete_from_table."""
    links = _load_links()
    link = next((l for l in links if l["id"] == link_id), None)
    if not link:
        abort(404)
    links = [l for l in links if l["id"] != link_id]
    _save_links(links)
    # Also remove associated clicks
    clicks = _load_clicks()
    clicks = [c for c in clicks if c["link_id"] != link_id]
    _save_clicks(clicks)
    return jsonify({"deleted": link_id})


@blueprint.route("/api/links/<int:link_id>/stats")
def api_link_stats(link_id):
    """Link click statistics -- supports extract_from_table."""
    links = _load_links()
    link = next((l for l in links if l["id"] == link_id), None)
    if not link:
        abort(404)
    clicks = [c for c in _load_clicks() if c["link_id"] == link_id]
    countries = Counter(c["country"] for c in clicks)
    devices = Counter(c["device"] for c in clicks)
    referrers = Counter(c["referrer"] for c in clicks)
    return jsonify({
        "link_id": link_id,
        "total_clicks": link["clicks"],
        "tracked_clicks": len(clicks),
        "countries": dict(countries.most_common(20)),
        "devices": dict(devices),
        "referrers": dict(referrers.most_common(20)),
    })


@blueprint.route("/api/links/<int:link_id>/stats/export")
def api_link_stats_export(link_id):
    """Export link stats -- supports export_by_dropdown.
    ?format=csv or ?format=json (default json)."""
    links = _load_links()
    link = next((l for l in links if l["id"] == link_id), None)
    if not link:
        abort(404)
    clicks = [c for c in _load_clicks() if c["link_id"] == link_id]
    fmt = request.args.get("format", "json").lower()

    if fmt == "csv":
        si = io.StringIO()
        writer = csv.writer(si)
        writer.writerow(["id", "link_id", "timestamp", "country", "device", "referrer"])
        for c in clicks:
            writer.writerow([c["id"], c["link_id"], c["timestamp"],
                             c["country"], c["device"], c["referrer"]])
        return Response(si.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition":
                                 f"attachment; filename=link_{link_id}_stats.csv"})
    return jsonify(clicks)


@blueprint.route("/api/links/<int:link_id>/share")
def api_link_share(link_id):
    """Generate share URLs -- supports share_by_dropdown.
    ?method=email|twitter|linkedin|copy|qr"""
    links = _load_links()
    link = next((l for l in links if l["id"] == link_id), None)
    if not link:
        abort(404)
    short_url = f"https://snplnk.io/{link['short_code']}"
    method = request.args.get("method", "copy").lower()
    title = link.get("title", "")

    share_data = {
        "link_id": link_id,
        "short_url": short_url,
        "method": method,
    }

    if method == "email":
        share_data["share_url"] = (
            f"mailto:?subject={title}&body=Check%20this%20out:%20{short_url}"
        )
    elif method == "twitter":
        share_data["share_url"] = (
            f"https://twitter.com/intent/tweet?text={title}&url={short_url}"
        )
    elif method == "linkedin":
        share_data["share_url"] = (
            f"https://www.linkedin.com/sharing/share-offsite/?url={short_url}"
        )
    elif method == "qr":
        share_data["qr_url"] = url_for("url-shorteners-qr.api_link_qr",
                                        link_id=link_id, _external=False)
    else:  # copy
        share_data["copy_text"] = short_url

    return jsonify(share_data)


@blueprint.route("/api/links/<int:link_id>/qr")
def api_link_qr(link_id):
    links = _load_links()
    link = next((l for l in links if l["id"] == link_id), None)
    if not link:
        abort(404)
    short_url = f"https://snplnk.io/{link['short_code']}"
    qr_placeholder = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" viewBox="0 0 200 200">'
        f'<rect width="200" height="200" fill="white" stroke="#ccc"/>'
        f'<rect x="20" y="20" width="40" height="40" fill="black"/>'
        f'<rect x="140" y="20" width="40" height="40" fill="black"/>'
        f'<rect x="20" y="140" width="40" height="40" fill="black"/>'
        f'<rect x="70" y="70" width="60" height="60" fill="black"/>'
        f'<text x="100" y="195" text-anchor="middle" font-size="8" fill="#666">{link["short_code"]}</text>'
        f'</svg>'
    )
    return jsonify({
        "link_id": link_id,
        "short_code": link["short_code"],
        "short_url": short_url,
        "original_url": link["original_url"],
        "qr_enabled": link.get("qr_enabled", True),
        "qr_svg": qr_placeholder,
    })


@blueprint.route("/api/resolve/<short_code>")
def api_resolve(short_code):
    links = _load_links()
    link = next((l for l in links if l["short_code"] == short_code), None)
    if not link:
        return jsonify({"error": "Short code not found"}), 404
    if not link["is_active"]:
        return jsonify({"error": "Link is deactivated", "link_id": link["id"]}), 410
    # Check expiration
    if link.get("expires_at"):
        try:
            expires = datetime.fromisoformat(link["expires_at"])
            if datetime.now() > expires:
                return jsonify({"error": "Link has expired", "link_id": link["id"]}), 410
        except (ValueError, TypeError):
            pass
    # Record click
    link["clicks"] = link.get("clicks", 0) + 1
    _save_links(links)
    clicks = _load_clicks()
    new_id = max((c["id"] for c in clicks), default=0) + 1
    clicks.append({
        "id": new_id,
        "link_id": link["id"],
        "timestamp": datetime.now().isoformat(),
        "referrer": request.headers.get("Referer", "direct"),
        "country": "US",
        "device": "desktop",
    })
    _save_clicks(clicks)
    return jsonify({
        "original_url": link["original_url"],
        "title": link["title"],
        "link_id": link["id"],
    })


@blueprint.route("/api/export")
def api_export():
    """Export all links -- supports export_by_dropdown.
    ?format=csv or ?format=json.  ?owner_id=N to filter by owner."""
    links = _load_links()
    owner_id = request.args.get("owner_id", type=int)
    if owner_id:
        links = [l for l in links if l["owner_id"] == owner_id]
    fmt = request.args.get("format", "json").lower()

    if fmt == "csv":
        si = io.StringIO()
        writer = csv.writer(si)
        writer.writerow(["id", "short_code", "original_url", "title", "owner_id",
                         "created_at", "clicks", "is_active", "expires_at",
                         "redirect_type", "tags", "qr_enabled"])
        for l in links:
            writer.writerow([
                l["id"], l["short_code"], l["original_url"], l["title"],
                l["owner_id"], l["created_at"], l["clicks"], l["is_active"],
                l.get("expires_at", ""), l.get("redirect_type", "301"),
                ";".join(l.get("tags", [])), l.get("qr_enabled", True),
            ])
        return Response(si.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=links.csv"})
    return jsonify(links)


@blueprint.route("/api/stats")
def api_stats():
    links = _load_links()
    clicks = _load_clicks()
    owner_id = request.args.get("owner_id", type=int)
    if owner_id:
        links = [l for l in links if l["owner_id"] == owner_id]
        link_ids = {l["id"] for l in links}
        clicks = [c for c in clicks if c["link_id"] in link_ids]
    total_links = len(links)
    active_links = sum(1 for l in links if l["is_active"])
    total_clicks = sum(l["clicks"] for l in links)
    top_links = sorted(links, key=lambda l: l["clicks"], reverse=True)[:5]
    countries = Counter(c["country"] for c in clicks)
    devices = Counter(c["device"] for c in clicks)
    # Collect all tags
    all_tags = Counter()
    for l in links:
        for t in l.get("tags", []):
            all_tags[t] += 1
    return jsonify({
        "total_links": total_links,
        "active_links": active_links,
        "inactive_links": total_links - active_links,
        "total_clicks": total_clicks,
        "top_links": [{"id": l["id"], "short_code": l["short_code"],
                       "title": l["title"], "clicks": l["clicks"]}
                      for l in top_links],
        "countries": dict(countries.most_common(10)),
        "devices": dict(devices),
        "tags": dict(all_tags.most_common(20)),
    })
