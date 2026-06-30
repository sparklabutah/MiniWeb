"""Apex Dynamics Corp — corporate website.

Synthesises realistic corporate data (team, products, services, blog posts,
testimonials, job openings, contact info) from config/config.json seeds.
All JSON data is written to data/ on first load and pristine copies kept in
data/.pristine/.
"""
import json
import pathlib
from collections import Counter

from flask import (
    Blueprint, Response, abort, jsonify, redirect, render_template, request, session, url_for,
)
from app import db

SITE = "business-company"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "business-company",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def _load(name, where=None, sort=None, limit=None):
    return db.query(SITE, name, where=where, sort=sort, limit=limit)


def _save(name, data):
    db.save_collection(SITE, name, data)


def _get(name, where=None, sort=None, limit=None):
    return db.query(SITE, name, where=where, sort=sort, limit=limit)

def _get_item(name, item_id):
    return db.get_item(SITE, name, item_id)


# ---------------------------------------------------------------------------
# Search helpers
# ---------------------------------------------------------------------------

def _keyword_score(query, text_fields):
    terms = query.lower().split()
    combined = " ".join(str(f) for f in text_fields).lower()
    return sum(1 for t in terms if t in combined)


def _search_items(items, query, fields, semantic=False):
    if not query:
        return items
    q = query.lower().strip()
    if semantic:
        scored = []
        for item in items:
            s = _keyword_score(q, [item.get(f, "") for f in fields])
            if s > 0:
                scored.append((item, s))
        scored.sort(key=lambda x: -x[1])
        return [item for item, _ in scored]
    else:
        results = []
        for item in items:
            combined = " ".join(str(item.get(f, "")) for f in fields).lower()
            if q in combined:
                results.append(item)
        return results


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    team = _get("team")[:6]
    products = [p for p in _get("products") if p.get("is_featured")][:3]
    posts = _get("posts")[:3]
    testimonials = _get("testimonials")[:3]
    services = _get("services")[:6]
    return render_template("business-company/index.html",
                           team=team, products=products, posts=posts,
                           testimonials=testimonials, services=services)


@blueprint.route("/search")
def search_page():
    q = request.args.get("q", "").strip()
    results = {"products": [], "posts": [], "team": [], "services": [], "jobs": []}
    if q:
        results["products"] = _search_items(_get("products"), q, ["name", "description", "category"])
        results["posts"] = _search_items(_get("posts"), q, ["title", "body", "tags", "author"])
        results["team"] = _search_items(_get("team"), q, ["name", "title", "department", "bio"])
        results["services"] = _search_items(_get("services"), q, ["name", "description", "category"])
        results["jobs"] = _search_items(_get("jobs"), q, ["title", "department", "location", "description"])
    total = sum(len(v) for v in results.values())
    return render_template("business-company/search.html", q=q, results=results, total=total)


@blueprint.route("/newsletter")
def newsletter_page():
    return render_template("business-company/newsletter.html")


@blueprint.route("/about")
def about():
    team = _get("team")
    departments = sorted(set(m["department"] for m in team))
    dept = request.args.get("department", "").strip()
    filtered = list(team)
    if dept:
        filtered = [m for m in filtered if m["department"] == dept]
    page = request.args.get("page", "1")
    page = int(page) if page.isdigit() else 1
    per_page = 30
    total = len(filtered)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    paginated = filtered[(page - 1) * per_page: page * per_page]
    return render_template("business-company/about.html",
                           team=paginated, departments=departments, dept=dept,
                           page=page, total_pages=total_pages, total=total)


@blueprint.route("/team/<int:member_id>")
def team_member(member_id):
    team = _get("team")
    member = next((m for m in team if m["id"] == member_id), None)
    if member is None:
        abort(404)
    colleagues = [m for m in team if m["department"] == member["department"]
                  and m["id"] != member_id][:4]
    return render_template("business-company/team_member.html",
                           member=member, colleagues=colleagues)


@blueprint.route("/products")
def products_page():
    products = _get("products")
    categories = sorted(set(p["category"] for p in products))
    cat = request.args.get("category", "").strip()
    q = request.args.get("q", "").strip()
    filtered = list(products)
    if cat:
        filtered = [p for p in filtered if p["category"] == cat]
    if q:
        filtered = _search_items(filtered, q, ["name", "description", "category"])
    page = request.args.get("page", "1")
    page = int(page) if page.isdigit() else 1
    per_page = 30
    total = len(filtered)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    paginated = filtered[(page - 1) * per_page: page * per_page]
    return render_template("business-company/products.html",
                           products=paginated, categories=categories, cat=cat, q=q,
                           page=page, total_pages=total_pages, total=total)


@blueprint.route("/product/<int:product_id>")
def product_detail(product_id):
    products = _get("products")
    product = next((p for p in products if p["id"] == product_id), None)
    if product is None:
        abort(404)
    related = [p for p in products if p["category"] == product["category"]
               and p["id"] != product_id][:3]
    return render_template("business-company/product_detail.html",
                           product=product, related=related)


@blueprint.route("/services")
def services_page():
    services = _get("services")
    categories = sorted(set(s["category"] for s in services))
    cat = request.args.get("category", "").strip()
    filtered = list(services)
    if cat:
        filtered = [s for s in filtered if s["category"] == cat]
    page = request.args.get("page", "1")
    page = int(page) if page.isdigit() else 1
    per_page = 30
    total = len(filtered)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    paginated = filtered[(page - 1) * per_page: page * per_page]
    return render_template("business-company/services.html",
                           services=paginated, categories=categories, cat=cat,
                           page=page, total_pages=total_pages, total=total)


@blueprint.route("/blog")
def blog_page():
    posts = _get("posts")
    categories = sorted(set(p["category"] for p in posts))
    cat = request.args.get("category", "").strip()
    q = request.args.get("q", "").strip()
    filtered = list(posts)
    if cat:
        filtered = [p for p in filtered if p["category"] == cat]
    if q:
        filtered = _search_items(filtered, q, ["title", "body", "tags", "author"])
    page = request.args.get("page", "1")
    page = int(page) if page.isdigit() else 1
    per_page = 30
    total = len(filtered)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    paginated = filtered[(page - 1) * per_page: page * per_page]
    return render_template("business-company/blog.html",
                           posts=paginated, categories=categories, cat=cat, q=q,
                           page=page, total_pages=total_pages, total=total)


@blueprint.route("/blog/<int:post_id>")
def blog_post(post_id):
    posts = _get("posts")
    post = next((p for p in posts if p["id"] == post_id), None)
    if post is None:
        abort(404)
    related = [p for p in posts if p["category"] == post["category"]
               and p["id"] != post_id][:3]
    return render_template("business-company/blog_post.html",
                           post=post, related=related)


@blueprint.route("/careers")
def careers_page():
    jobs = _get("jobs")
    departments = sorted(set(j["department"] for j in jobs))
    locations = sorted(set(j["location"] for j in jobs))
    dept = request.args.get("department", "").strip()
    loc = request.args.get("location", "").strip()
    filtered = list(jobs)
    if dept:
        filtered = [j for j in filtered if j["department"] == dept]
    if loc:
        filtered = [j for j in filtered if j["location"] == loc]
    page = request.args.get("page", "1")
    page = int(page) if page.isdigit() else 1
    per_page = 30
    total_count = len(filtered)
    total_pages = max(1, (total_count + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    paginated = filtered[(page - 1) * per_page: page * per_page]
    return render_template("business-company/careers.html",
                           jobs=paginated, departments=departments,
                           locations=locations, dept=dept, loc=loc,
                           page=page, total_pages=total_pages, total=total_count)


@blueprint.route("/careers/<int:job_id>")
def job_detail(job_id):
    jobs = _get("jobs")
    job = next((j for j in jobs if j["id"] == job_id), None)
    if job is None:
        abort(404)
    return render_template("business-company/job_detail.html", job=job)


@blueprint.route("/contact", methods=["GET"])
def contact_page():
    return render_template("business-company/contact.html", success=False, error=None)


@blueprint.route("/contact", methods=["POST"])
def contact_submit():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    subject = request.form.get("subject", "").strip()
    message = request.form.get("message", "").strip()
    if not name or not email or not message:
        return render_template("business-company/contact.html",
                               success=False, error="Please fill in all required fields.")
    contacts = _load("contacts")
    contacts.append({
        "id": len(contacts) + 1,
        "name": name,
        "email": email,
        "subject": subject,
        "message": message,
    })
    _save("contacts", contacts)

    # Bridge: send confirmation email to user's inbox
    try:
        from app.bridges import on_inquiry
        on_inquiry(
            user_id=session.get("user_id", 1),
            company_name="Meridian Systems",
            subject=subject or "Contact Inquiry",
            message=message,
        )
    except Exception:
        pass

    return render_template("business-company/contact.html", success=True, error=None)


@blueprint.route("/newsletter/subscribe", methods=["POST"])
def newsletter_subscribe():
    """Form-based newsletter subscription (browser-automation friendly)."""
    email = request.form.get("email", "").strip()
    name = request.form.get("name", "").strip()
    topics = request.form.getlist("topics")
    if not email:
        return render_template("business-company/newsletter.html")

    subscribers = _load("subscribers")
    existing = next((s for s in subscribers if s["email"] == email), None)
    if existing:
        # Always (re)subscribe — unsubscribe is a separate action
        existing["active"] = True
        action = "subscribed"
        if topics:
            existing["subscribed_topics"] = topics
    else:
        existing = {
            "id": len(subscribers) + 1,
            "email": email,
            "name": name,
            "subscribed_topics": topics if topics else ["blog"],
            "active": True,
        }
        subscribers.append(existing)
        action = "subscribed"
    _save("subscribers", subscribers)

    if action == "subscribed":
        try:
            from app.bridges import on_subscribe
            on_subscribe(user_id=session.get("user_id", 1), service_name="Meridian Systems")
        except Exception:
            pass

    return render_template("business-company/newsletter.html",
                           subscribe_success=True, subscribe_action=action,
                           subscribe_email=email)


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/team")
def api_team():
    team = _get("team")
    dept = request.args.get("department", "").strip()
    q = request.args.get("q", "").strip()
    results = list(team)
    if dept:
        results = [m for m in results if m["department"] == dept]
    if q:
        results = _search_items(results, q, ["name", "title", "department", "bio"])
    return jsonify(results)


@blueprint.route("/api/team/<int:member_id>")
def api_team_member(member_id):
    member = _get_item("team", member_id)
    if member is None:
        abort(404)
    return jsonify(member)


@blueprint.route("/api/products")
def api_products():
    products = _get("products")
    cat = request.args.get("category", "").strip()
    q = request.args.get("q", "").strip()
    sort = request.args.get("sort", "").strip()
    results = list(products)
    if cat:
        results = [p for p in results if p["category"] == cat]
    if q:
        results = _search_items(results, q, ["name", "description", "category"])
    if sort == "price":
        results.sort(key=lambda p: p.get("price_monthly") or 0)
    elif sort == "name":
        results.sort(key=lambda p: p["name"].lower())
    return jsonify(results)


@blueprint.route("/api/products/<int:product_id>")
def api_product(product_id):
    product = _get_item("products", product_id)
    if product is None:
        abort(404)
    return jsonify(product)


@blueprint.route("/api/products/search")
def api_products_search():
    q = request.args.get("q", "").strip()
    products = _get("products")
    return jsonify(_search_items(products, q, ["name", "description", "category"]))


@blueprint.route("/api/products/semantic")
def api_products_semantic():
    q = request.args.get("q", "").strip()
    products = _get("products")
    return jsonify(_search_items(products, q, ["name", "description", "category", "features"], semantic=True))


@blueprint.route("/api/services")
def api_services():
    services = _get("services")
    cat = request.args.get("category", "").strip()
    results = list(services)
    if cat:
        results = [s for s in results if s["category"] == cat]
    return jsonify(results)


@blueprint.route("/api/services/<int:service_id>")
def api_service(service_id):
    service = _get_item("services", service_id)
    if service is None:
        abort(404)
    return jsonify(service)


@blueprint.route("/api/posts")
def api_posts():
    posts = _get("posts")
    cat = request.args.get("category", "").strip()
    q = request.args.get("q", "").strip()
    sort = request.args.get("sort", "date").strip()
    results = list(posts)
    if cat:
        results = [p for p in results if p["category"] == cat]
    if q:
        results = _search_items(results, q, ["title", "body", "tags", "author"])
    if sort == "date":
        results.sort(key=lambda p: p["date"], reverse=True)
    elif sort == "title":
        results.sort(key=lambda p: p["title"].lower())
    return jsonify(results)


@blueprint.route("/api/posts/<int:post_id>")
def api_post(post_id):
    post = _get_item("posts", post_id)
    if post is None:
        abort(404)
    return jsonify(post)


@blueprint.route("/api/posts/search")
def api_posts_search():
    q = request.args.get("q", "").strip()
    posts = _get("posts")
    return jsonify(_search_items(posts, q, ["title", "body", "tags", "author"]))


@blueprint.route("/api/posts/semantic")
def api_posts_semantic():
    q = request.args.get("q", "").strip()
    posts = _get("posts")
    return jsonify(_search_items(posts, q, ["title", "body", "tags", "author", "category"], semantic=True))


@blueprint.route("/api/testimonials")
def api_testimonials():
    testimonials = _get("testimonials")
    company = request.args.get("company", "").strip()
    results = list(testimonials)
    if company:
        results = [t for t in results if company.lower() in t["company"].lower()]
    return jsonify(results)


@blueprint.route("/api/jobs")
def api_jobs():
    jobs = _get("jobs")
    dept = request.args.get("department", "").strip()
    loc = request.args.get("location", "").strip()
    jtype = request.args.get("type", "").strip()
    results = list(jobs)
    if dept:
        results = [j for j in results if j["department"] == dept]
    if loc:
        results = [j for j in results if j["location"] == loc]
    if jtype:
        results = [j for j in results if j["type"] == jtype]
    return jsonify(results)


@blueprint.route("/api/jobs/<int:job_id>")
def api_job(job_id):
    job = _get_item("jobs", job_id)
    if job is None:
        abort(404)
    return jsonify(job)


@blueprint.route("/api/stats")
def api_stats():
    team = _get("team")
    products = _get("products")
    services = _get("services")
    posts = _get("posts")
    jobs = _get("jobs")
    testimonials = _get("testimonials")
    # Note: these are small tables (<20 rows each), aggregation done in Python
    dept_counts = Counter(m["department"] for m in team)
    product_cats = Counter(p["category"] for p in products)
    return jsonify({
        "team_count": len(team),
        "product_count": len(products),
        "service_count": len(services),
        "post_count": len(posts),
        "job_count": len(jobs),
        "testimonial_count": len(testimonials),
        "departments": dict(dept_counts),
        "product_categories": dict(product_cats),
    })


@blueprint.route("/api/stats/department/<dept_name>")
def api_dept_stats(dept_name):
    team = _get("team")
    jobs = _get("jobs")
    members = [m for m in team if m["department"] == dept_name]
    openings = [j for j in jobs if j["department"] == dept_name]
    if not members and not openings:
        return jsonify({"department": dept_name, "member_count": 0, "opening_count": 0})
    return jsonify({
        "department": dept_name,
        "member_count": len(members),
        "opening_count": len(openings),
        "members": [m["name"] for m in members],
    })


@blueprint.route("/api/export")
def api_export():
    fmt = request.args.get("format", "json").lower()
    resource = request.args.get("resource", "products").strip()
    cat = request.args.get("category", "").strip()

    data = list(_get(resource) if resource in ("team", "products", "services", "posts", "jobs", "testimonials") else [])
    if cat and data:
        data = [d for d in data if cat.lower() in str(d.get("category", "")).lower()
                or cat.lower() in str(d.get("department", "")).lower()]

    if fmt == "csv":
        if not data:
            return Response("", mimetype="text/csv")
        headers = list(data[0].keys())
        lines = [",".join(headers)]
        for row in data:
            vals = []
            for h in headers:
                v = row.get(h, "")
                if isinstance(v, list):
                    v = "; ".join(str(x) for x in v)
                v = str(v).replace('"', '""')
                vals.append(f'"{v}"')
            lines.append(",".join(vals))
        return Response("\n".join(lines), mimetype="text/csv",
                        headers={"Content-Disposition": f"attachment; filename={resource}.csv"})
    return jsonify(data)


@blueprint.route("/api/compare")
def api_compare():
    resource = request.args.get("resource", "products").strip()
    ids_str = request.args.get("ids", "")
    ids = [int(x) for x in ids_str.split(",") if x.strip().isdigit()]
    data = _get(resource) if resource in ("products", "services", "jobs", "team") else []
    return jsonify([d for d in data if d["id"] in ids])


# ---------------------------------------------------------------------------
# Contact form API
# ---------------------------------------------------------------------------

@blueprint.route("/api/contact", methods=["POST"])
def api_contact():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    subject = data.get("subject", "").strip()
    message = data.get("message", "").strip()
    if not name or not email or not message:
        return jsonify({"error": "name, email, and message are required"}), 400
    contacts = _load("contacts")
    entry = {
        "id": len(contacts) + 1,
        "name": name,
        "email": email,
        "subject": subject,
        "message": message,
    }
    contacts.append(entry)
    _save("contacts", contacts)

    # Bridge: send confirmation email to user's inbox
    try:
        from app.bridges import on_inquiry
        on_inquiry(
            user_id=session.get("user_id", 1),
            company_name="Meridian Systems",
            subject=subject or "Contact Inquiry",
            message=message,
        )
    except Exception:
        pass

    return jsonify({"status": "submitted", "contact_id": entry["id"]})


# ---------------------------------------------------------------------------
# Newsletter subscription API (toggle)
# ---------------------------------------------------------------------------

@blueprint.route("/api/subscribers")
def api_subscribers():
    return jsonify(_get("subscribers"))


@blueprint.route("/api/subscribe", methods=["POST"])
def api_subscribe():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip()
    topics = data.get("topics", [])
    if not email:
        return jsonify({"error": "email required"}), 400
    subscribers = _load("subscribers")
    existing = next((s for s in subscribers if s["email"] == email), None)
    if existing:
        if existing["active"]:
            # Already subscribed – unsubscribe (toggle off)
            existing["active"] = False
            action = "unsubscribed"
        else:
            # Was unsubscribed – resubscribe
            existing["active"] = True
            action = "subscribed"
        if topics:
            existing["subscribed_topics"] = topics
    else:
        existing = {
            "id": len(subscribers) + 1,
            "email": email,
            "name": data.get("name", ""),
            "subscribed_topics": topics if topics else ["blog"],
            "active": True,
        }
        subscribers.append(existing)
        action = "subscribed"
    _save("subscribers", subscribers)

    if action == "subscribed":
        try:
            from app.bridges import on_subscribe
            on_subscribe(user_id=session.get("user_id", 1), service_name="Meridian Systems")
        except Exception:
            pass

    return jsonify({"action": action, "email": email, "subscriber": existing})


@blueprint.route("/api/subscriber/<int:sub_id>/toggle", methods=["POST"])
def api_toggle_subscription(sub_id):
    """Toggle a single topic subscription for a subscriber."""
    data = request.get_json(silent=True) or {}
    topic = data.get("topic", "").strip()
    if not topic:
        return jsonify({"error": "topic required"}), 400
    subscribers = _load("subscribers")
    sub = next((s for s in subscribers if s["id"] == sub_id), None)
    if not sub:
        abort(404)
    topics = sub.setdefault("subscribed_topics", [])
    if topic in topics:
        topics.remove(topic)
        action = "unsubscribed"
    else:
        topics.append(topic)
        action = "subscribed"
    _save("subscribers", subscribers)
    return jsonify({"action": action, "topic": topic, "subscribed_topics": topics})
