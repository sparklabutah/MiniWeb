"""Email -- Webmail client modeled after Gmail/Outlook.

Data interpreter: reads enron_sample.jsonl line by line. Maps emails to users
based on from/to fields. The raw data file is never modified.
"""
import json
import pathlib
import random
import re
from datetime import datetime
from email.utils import parsedate_to_datetime

from flask import Blueprint, Response, abort, jsonify, redirect, render_template, request, session, url_for

SITE_DIR = pathlib.Path(__file__).resolve().parent
DATA_FILE = SITE_DIR / "data" / "enron_sample.jsonl"
USERS_FILE = SITE_DIR / "data" / "users.json"
SENT_FILE = SITE_DIR / "data" / "sent_messages.json"
CONFIG_FILE = SITE_DIR / "config" / "config.json"

blueprint = Blueprint(
    "email",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

EMAILS_PER_PAGE = 25

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)

# ---------------------------------------------------------------------------
# Data interpreter -- reads raw JSONL, maps to users
# ---------------------------------------------------------------------------

# Map 5 known sender addresses to user IDs
_USER_EMAIL_MAP = {
    "lynn.blair@enron.com": 1,
    "michael.bodnar@enron.com": 2,
    "john.buchanan@enron.com": 3,
    "britt.davis@enron.com": 4,
    "shelley.corman@enron.com": 5,
}

_USER_EMAILS_SET = set(_USER_EMAIL_MAP.keys())


def _parse_email_date(date_str):
    """Parse Enron email date strings, handling various formats."""
    if not date_str:
        return datetime(2001, 1, 1)
    try:
        # Strip trailing timezone name like (PDT), (PST)
        cleaned = re.sub(r'\s*\([A-Z]{2,4}\)\s*$', '', date_str.strip())
        return parsedate_to_datetime(cleaned)
    except Exception:
        try:
            return parsedate_to_datetime(date_str.strip())
        except Exception:
            return datetime(2001, 1, 1)


def _parse_addr_list(raw):
    """Split comma-separated email addresses, stripping whitespace/newlines."""
    if not raw or not raw.strip():
        return []
    # Normalize whitespace (Enron data has \r\n\t in multi-line to fields)
    raw = re.sub(r'[\r\n\t]+', ' ', raw)
    addrs = [a.strip() for a in raw.split(',')]
    return [a for a in addrs if a and '@' in a]


def _match_user_id(to_addrs, from_addr):
    """Determine which user this email belongs to.
    If from_addr is a known user, put it in their sent folder.
    If any to_addr is a known user, put it in their inbox.
    Otherwise, distribute round-robin among users.
    """
    # Check to addresses first (inbox)
    for addr in to_addrs:
        uid = _USER_EMAIL_MAP.get(addr)
        if uid is not None:
            return uid, "inbox"
    # Check from address (sent)
    uid = _USER_EMAIL_MAP.get(from_addr)
    if uid is not None:
        return uid, "inbox"  # Default to inbox for sent items from user
    return None, "inbox"


def _interpret_record(raw, idx):
    """Convert a raw JSONL record into a normalized email object."""
    from_addr = raw.get("from", "").strip()
    to_addrs = _parse_addr_list(raw.get("to", ""))
    cc_addrs = _parse_addr_list(raw.get("cc", ""))
    subject = raw.get("subject", "(no subject)").strip()
    date_obj = _parse_email_date(raw.get("date", ""))
    body = raw.get("body", "")
    message_id = raw.get("message_id", "")

    return {
        "id": idx,
        "from_addr": from_addr,
        "to_addrs": to_addrs,
        "cc_addrs": cc_addrs,
        "subject": subject,
        "date": date_obj.isoformat(),
        "date_display": date_obj.strftime("%b %d, %Y %I:%M %p"),
        "date_sort": date_obj.timestamp(),
        "body": body,
        "body_preview": (body[:120].replace('\n', ' ').replace('\r', ' ').strip() + '...') if len(body) > 120 else body.replace('\n', ' ').replace('\r', ' ').strip(),
        "message_id": message_id,
        "folder": "inbox",
        "is_read": False,
        "is_starred": False,
        "labels": [],
        "user_id": None,
    }


def _load_emails():
    """Read JSONL dataset and map emails to users."""
    config = _load_config()
    n = config.get("num_data_points", -1)
    seed = config.get("random_seed", 42)
    rng = random.Random(seed)

    raw_records = []
    with open(DATA_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                raw_records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if n > 0 and n < len(raw_records):
        raw_records = rng.sample(raw_records, n)

    emails = []
    robin_counter = 0
    for idx, raw in enumerate(raw_records, 1):
        email = _interpret_record(raw, idx)
        from_addr = email["from_addr"]
        to_addrs = email["to_addrs"]

        # Assign to user
        uid, folder = _match_user_id(to_addrs, from_addr)
        if uid is None:
            # Round-robin among 5 users
            robin_counter += 1
            uid = (robin_counter % 5) + 1
            folder = "inbox"

        # If sender is the user, put in sent
        user_email = None
        for addr, u_id in _USER_EMAIL_MAP.items():
            if u_id == uid:
                user_email = addr
                break
        if from_addr == user_email:
            folder = "sent"

        email["user_id"] = uid
        email["folder"] = folder
        emails.append(email)

    # Sort by date descending
    emails.sort(key=lambda e: e["date_sort"], reverse=True)
    # Re-assign IDs after sort
    for i, e in enumerate(emails, 1):
        e["id"] = i

    return emails


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------

_emails = None
_contacts = None


def _ensure_loaded():
    global _emails, _contacts
    if _emails is None:
        _emails = _load_emails()
        # Extract contacts from all emails
        addr_set = set()
        for e in _emails:
            if e["from_addr"]:
                addr_set.add(e["from_addr"])
            for a in e["to_addrs"]:
                addr_set.add(a)
            for a in e["cc_addrs"]:
                addr_set.add(a)
        _contacts = sorted(addr_set)


def _get_emails():
    _ensure_loaded()
    return _emails


def _get_contacts():
    _ensure_loaded()
    return _contacts


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


def _current_user():
    if "user_id" in session:
        return _get_user(session["user_id"])
    return None


def _session_user_id():
    """Return the user_id from session, or None."""
    return session.get("user_id")


# ---------------------------------------------------------------------------
# Sent messages (mutable state for composed emails)
# ---------------------------------------------------------------------------

def _load_sent():
    if SENT_FILE.exists():
        try:
            return json.loads(SENT_FILE.read_text())
        except (json.JSONDecodeError, ValueError):
            return []
    return []


def _save_sent(messages):
    SENT_FILE.write_text(json.dumps(messages, indent=2))


# ---------------------------------------------------------------------------
# Helper: filter emails for current user
# ---------------------------------------------------------------------------

def _user_emails(user_id, folder=None):
    """Get emails for a user, optionally filtered by folder. Includes composed messages."""
    emails = [e for e in _get_emails() if e["user_id"] == user_id]
    # Add composed/sent messages from mutable storage
    sent_msgs = _load_sent()
    for sm in sent_msgs:
        if sm.get("user_id") == user_id:
            emails.append(sm)
    if folder:
        emails = [e for e in emails if e.get("folder") == folder]
    emails.sort(key=lambda e: e.get("date_sort", 0), reverse=True)
    return emails


def _folder_counts(user_id):
    """Get unread count per folder for a user."""
    all_emails = _user_emails(user_id)
    counts = {}
    for e in all_emails:
        f = e.get("folder", "inbox")
        if f not in counts:
            counts[f] = {"total": 0, "unread": 0}
        counts[f]["total"] += 1
        if not e.get("is_read", False):
            counts[f]["unread"] += 1
    return counts


def _find_email(email_id, user_id=None):
    """Find an email by ID across both static and sent stores."""
    # Check static emails
    for e in _get_emails():
        if e["id"] == email_id:
            if user_id is None or e["user_id"] == user_id:
                return e, "static"
    # Check sent messages
    sent_msgs = _load_sent()
    for e in sent_msgs:
        if e["id"] == email_id:
            if user_id is None or e["user_id"] == user_id:
                return e, "sent"
    return None, None


# ---------------------------------------------------------------------------
# Search helpers
# ---------------------------------------------------------------------------

def _search_emails(emails, query):
    if not query:
        return emails
    q = query.lower().strip()
    results = []
    for e in emails:
        text = (e.get("subject", "") + " " + e.get("from_addr", "") + " " +
                e.get("body", "") + " " + " ".join(e.get("to_addrs", []))).lower()
        if q in text:
            results.append(e)
    return results


# ---------------------------------------------------------------------------
# Resolve user_id: prefer explicit param, fall back to session
# ---------------------------------------------------------------------------

def _resolve_user_id(explicit=None):
    """Return user_id from explicit param or session. Returns int or None."""
    if explicit is not None:
        return int(explicit)
    return _session_user_id()


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    user = _current_user()
    if not user:
        return redirect(url_for("email.login_page"))
    folder = request.args.get("folder", "inbox")
    page = request.args.get("page", 1, type=int)
    all_emails = _user_emails(user["id"], folder=folder)
    total = len(all_emails)
    total_pages = max(1, (total + EMAILS_PER_PAGE - 1) // EMAILS_PER_PAGE)
    page = max(1, min(page, total_pages))
    start = (page - 1) * EMAILS_PER_PAGE
    end = start + EMAILS_PER_PAGE
    emails = all_emails[start:end]
    counts = _folder_counts(user["id"])
    return render_template("email/index.html", user=user, emails=emails,
                           folder=folder, counts=counts,
                           page=page, total_pages=total_pages, total=total)


@blueprint.route("/message/<int:email_id>")
def message_detail(email_id):
    user = _current_user()
    if not user:
        return redirect(url_for("email.login_page"))
    email, source = _find_email(email_id, user["id"])
    if email is None:
        abort(404)
    # Mark as read
    if not email.get("is_read"):
        email["is_read"] = True
        if source == "sent":
            sent = _load_sent()
            for s in sent:
                if s["id"] == email_id:
                    s["is_read"] = True
            _save_sent(sent)
    counts = _folder_counts(user["id"])
    return render_template("email/message.html", user=user, email=email, counts=counts)


@blueprint.route("/compose")
def compose_page():
    user = _current_user()
    if not user:
        return redirect(url_for("email.login_page"))
    reply_to = request.args.get("reply_to", "")
    forward_id = request.args.get("forward", "")
    prefill = {"to": "", "cc": "", "subject": "", "body": ""}
    if reply_to:
        try:
            orig, _ = _find_email(int(reply_to), user["id"])
            if orig:
                prefill["to"] = orig["from_addr"]
                prefill["subject"] = "Re: " + orig["subject"] if not orig["subject"].startswith("Re:") else orig["subject"]
                prefill["body"] = "\n\n--- Original Message ---\nFrom: " + orig["from_addr"] + "\nDate: " + orig.get("date_display", "") + "\n\n" + orig.get("body", "")
        except (ValueError, TypeError):
            pass
    if forward_id:
        try:
            orig, _ = _find_email(int(forward_id), user["id"])
            if orig:
                prefill["subject"] = "Fwd: " + orig["subject"] if not orig["subject"].startswith("Fwd:") else orig["subject"]
                prefill["body"] = "\n\n--- Forwarded Message ---\nFrom: " + orig["from_addr"] + "\nTo: " + ", ".join(orig.get("to_addrs", [])) + "\nDate: " + orig.get("date_display", "") + "\nSubject: " + orig["subject"] + "\n\n" + orig.get("body", "")
        except (ValueError, TypeError):
            pass
    counts = _folder_counts(user["id"])
    return render_template("email/compose.html", user=user, prefill=prefill, counts=counts)


@blueprint.route("/search")
def search_page():
    user = _current_user()
    if not user:
        return redirect(url_for("email.login_page"))
    q = request.args.get("q", "").strip()
    emails = _user_emails(user["id"])
    results = _search_emails(emails, q) if q else []
    counts = _folder_counts(user["id"])
    return render_template("email/search.html", user=user, results=results,
                           q=q, counts=counts)


@blueprint.route("/contacts")
def contacts_page():
    user = _current_user()
    if not user:
        return redirect(url_for("email.login_page"))
    contacts = _get_contacts()
    counts = _folder_counts(user["id"])
    return render_template("email/contacts.html", user=user, contacts=contacts, counts=counts)


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("email/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return render_template("email/login.html", error="Invalid username or password")
    session["user_id"] = user["id"]
    return redirect(url_for("email.index"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("email.login_page"))


# ---------------------------------------------------------------------------
# Form-based mutation routes
# ---------------------------------------------------------------------------

@blueprint.route("/compose", methods=["POST"])
def compose_submit():
    user = _current_user()
    if not user:
        return redirect(url_for("email.login_page"))
    to_raw = request.form.get("to", "").strip()
    cc_raw = request.form.get("cc", "").strip()
    subject = request.form.get("subject", "").strip() or "(no subject)"
    body = request.form.get("body", "")

    to_addrs = _parse_addr_list(to_raw)
    cc_addrs = _parse_addr_list(cc_raw)

    now = datetime.utcnow()
    sent_msgs = _load_sent()
    # Generate new ID: start from 10000 to avoid conflicts
    new_id = 10000 + len(sent_msgs) + 1

    new_email = {
        "id": new_id,
        "from_addr": user["email_address"],
        "to_addrs": to_addrs,
        "cc_addrs": cc_addrs,
        "subject": subject,
        "date": now.isoformat(),
        "date_display": now.strftime("%b %d, %Y %I:%M %p"),
        "date_sort": now.timestamp(),
        "body": body,
        "body_preview": (body[:120].replace('\n', ' ').strip() + '...') if len(body) > 120 else body.replace('\n', ' ').strip(),
        "message_id": f"<compose-{new_id}@webmail>",
        "folder": "sent",
        "is_read": True,
        "is_starred": False,
        "labels": [],
        "user_id": user["id"],
    }
    sent_msgs.append(new_email)

    # Also deliver to recipient if they are a known user
    for addr in to_addrs:
        uid = _USER_EMAIL_MAP.get(addr)
        if uid is not None and uid != user["id"]:
            inbox_copy = dict(new_email)
            inbox_copy["id"] = 10000 + len(sent_msgs) + 1
            inbox_copy["folder"] = "inbox"
            inbox_copy["is_read"] = False
            inbox_copy["user_id"] = uid
            sent_msgs.append(inbox_copy)

    _save_sent(sent_msgs)
    return redirect(url_for("email.index", folder="sent"))


@blueprint.route("/message/<int:email_id>/star", methods=["POST"])
def form_star(email_id):
    user = _current_user()
    if not user:
        return redirect(url_for("email.login_page"))
    email, source = _find_email(email_id, user["id"])
    if email:
        new_val = not email.get("is_starred", False)
        email["is_starred"] = new_val
        if source == "sent":
            sent = _load_sent()
            for s in sent:
                if s["id"] == email_id:
                    s["is_starred"] = new_val
            _save_sent(sent)
    return redirect(request.form.get("redirect_to", url_for("email.index")))


@blueprint.route("/message/<int:email_id>/move", methods=["POST"])
def form_move(email_id):
    user = _current_user()
    if not user:
        return redirect(url_for("email.login_page"))
    target_folder = request.form.get("folder", "inbox").strip()
    email, source = _find_email(email_id, user["id"])
    if email:
        email["folder"] = target_folder
        if source == "sent":
            sent = _load_sent()
            for s in sent:
                if s["id"] == email_id:
                    s["folder"] = target_folder
            _save_sent(sent)
    return redirect(request.form.get("redirect_to", url_for("email.index")))


@blueprint.route("/message/<int:email_id>/delete", methods=["POST"])
def form_delete(email_id):
    user = _current_user()
    if not user:
        return redirect(url_for("email.login_page"))
    email, source = _find_email(email_id, user["id"])
    if email:
        email["folder"] = "trash"
        if source == "sent":
            sent = _load_sent()
            for s in sent:
                if s["id"] == email_id:
                    s["folder"] = "trash"
            _save_sent(sent)
    return redirect(request.form.get("redirect_to", url_for("email.index")))


@blueprint.route("/message/<int:email_id>/read", methods=["POST"])
def form_mark_read(email_id):
    user = _current_user()
    if not user:
        return redirect(url_for("email.login_page"))
    email, source = _find_email(email_id, user["id"])
    if email:
        mark = request.form.get("mark", "read")
        email["is_read"] = (mark == "read")
        if source == "sent":
            sent = _load_sent()
            for s in sent:
                if s["id"] == email_id:
                    s["is_read"] = (mark == "read")
            _save_sent(sent)
    return redirect(request.form.get("redirect_to", url_for("email.index")))


@blueprint.route("/message/<int:email_id>/label", methods=["POST"])
def form_label(email_id):
    user = _current_user()
    if not user:
        return redirect(url_for("email.login_page"))
    label = request.form.get("label", "").strip()
    action = request.form.get("action", "add")
    email, source = _find_email(email_id, user["id"])
    if email and label:
        labels = email.get("labels", [])
        if action == "add" and label not in labels:
            labels.append(label)
        elif action == "remove" and label in labels:
            labels.remove(label)
        email["labels"] = labels
        if source == "sent":
            sent = _load_sent()
            for s in sent:
                if s["id"] == email_id:
                    s["labels"] = labels
            _save_sent(sent)
    return redirect(request.form.get("redirect_to", url_for("email.index")))


# ---------------------------------------------------------------------------
# API routes  (all accept explicit user_id OR fall back to session)
# ---------------------------------------------------------------------------

@blueprint.route("/api/messages")
def api_messages():
    user_id = _resolve_user_id(request.args.get("user_id", type=int))
    folder = request.args.get("folder", "").strip()
    q = request.args.get("q", "").strip()
    sort = request.args.get("sort", "date").strip()
    starred = request.args.get("starred", "").strip()
    page = request.args.get("page", 0, type=int)  # 0 = no pagination

    if user_id:
        emails = _user_emails(user_id, folder=folder if folder else None)
    else:
        emails = list(_get_emails())
        sent = _load_sent()
        emails.extend(sent)
        if folder:
            emails = [e for e in emails if e.get("folder") == folder]

    if q:
        emails = _search_emails(emails, q)
    if starred == "true":
        emails = [e for e in emails if e.get("is_starred")]

    if sort == "date":
        emails.sort(key=lambda e: e.get("date_sort", 0), reverse=True)
    elif sort == "subject":
        emails.sort(key=lambda e: e.get("subject", "").lower())
    elif sort == "from":
        emails.sort(key=lambda e: e.get("from_addr", "").lower())

    total = len(emails)

    # Optional API-level pagination
    if page > 0:
        start = (page - 1) * EMAILS_PER_PAGE
        end = start + EMAILS_PER_PAGE
        emails = emails[start:end]

    return jsonify({"messages": emails, "total": total, "page": page,
                    "per_page": EMAILS_PER_PAGE})


@blueprint.route("/api/messages/<int:email_id>")
def api_message(email_id):
    user_id = _resolve_user_id(request.args.get("user_id", type=int))
    email, _ = _find_email(email_id, user_id)
    if email is None:
        abort(404)
    return jsonify(email)


@blueprint.route("/api/messages/compose", methods=["POST"])
def api_compose():
    data = request.get_json(silent=True) or {}
    user_id = _resolve_user_id(data.get("user_id"))
    if not user_id:
        return jsonify({"error": "user_id required (pass in body or log in via session)"}), 400
    user = _get_user(user_id)
    if not user:
        return jsonify({"error": "user not found"}), 404

    to_addrs = _parse_addr_list(data.get("to", ""))
    cc_addrs = _parse_addr_list(data.get("cc", ""))
    subject = data.get("subject", "").strip() or "(no subject)"
    body = data.get("body", "")

    now = datetime.utcnow()
    sent_msgs = _load_sent()
    new_id = 10000 + len(sent_msgs) + 1

    new_email = {
        "id": new_id,
        "from_addr": user["email_address"],
        "to_addrs": to_addrs,
        "cc_addrs": cc_addrs,
        "subject": subject,
        "date": now.isoformat(),
        "date_display": now.strftime("%b %d, %Y %I:%M %p"),
        "date_sort": now.timestamp(),
        "body": body,
        "body_preview": (body[:120].replace('\n', ' ').strip() + '...') if len(body) > 120 else body.replace('\n', ' ').strip(),
        "message_id": f"<compose-{new_id}@webmail>",
        "folder": "sent",
        "is_read": True,
        "is_starred": False,
        "labels": [],
        "user_id": user_id,
    }
    sent_msgs.append(new_email)

    for addr in to_addrs:
        uid = _USER_EMAIL_MAP.get(addr)
        if uid is not None and uid != user_id:
            inbox_copy = dict(new_email)
            inbox_copy["id"] = 10000 + len(sent_msgs) + 1
            inbox_copy["folder"] = "inbox"
            inbox_copy["is_read"] = False
            inbox_copy["user_id"] = uid
            sent_msgs.append(inbox_copy)

    _save_sent(sent_msgs)
    counts = _folder_counts(user_id)
    sent_count = counts.get("sent", {}).get("total", 0)
    return jsonify({"status": "sent", "id": new_id, "message": new_email,
                    "sent_count": sent_count})


@blueprint.route("/api/messages/<int:email_id>/read", methods=["POST"])
def api_mark_read(email_id):
    data = request.get_json(silent=True) or {}
    mark = data.get("mark", "read")
    user_id = _resolve_user_id(data.get("user_id"))
    email, source = _find_email(email_id, user_id)
    if email is None:
        abort(404)
    email["is_read"] = (mark == "read")
    if source == "sent":
        sent = _load_sent()
        for s in sent:
            if s["id"] == email_id:
                s["is_read"] = (mark == "read")
        _save_sent(sent)
    return jsonify({"id": email_id, "is_read": email["is_read"]})


@blueprint.route("/api/messages/<int:email_id>/star", methods=["POST"])
def api_star(email_id):
    data = request.get_json(silent=True) or {}
    user_id = _resolve_user_id(data.get("user_id"))
    email, source = _find_email(email_id, user_id)
    if email is None:
        abort(404)
    new_val = not email.get("is_starred", False)
    email["is_starred"] = new_val
    if source == "sent":
        sent = _load_sent()
        for s in sent:
            if s["id"] == email_id:
                s["is_starred"] = new_val
        _save_sent(sent)
    return jsonify({"id": email_id, "is_starred": email["is_starred"]})


@blueprint.route("/api/messages/<int:email_id>/move", methods=["POST"])
def api_move(email_id):
    data = request.get_json(silent=True) or {}
    target = data.get("folder", "inbox")
    user_id = _resolve_user_id(data.get("user_id"))
    email, source = _find_email(email_id, user_id)
    if email is None:
        abort(404)
    old_folder = email.get("folder")
    email["folder"] = target
    if source == "sent":
        sent = _load_sent()
        for s in sent:
            if s["id"] == email_id:
                s["folder"] = target
        _save_sent(sent)
    # Return folder counts so the caller can verify the move
    if user_id:
        counts = _folder_counts(user_id)
    else:
        counts = {}
    return jsonify({"id": email_id, "old_folder": old_folder,
                    "new_folder": target, "folder_counts": counts})


@blueprint.route("/api/messages/<int:email_id>/label", methods=["POST"])
def api_label(email_id):
    data = request.get_json(silent=True) or {}
    label = data.get("label", "").strip()
    action = data.get("action", "add")
    user_id = _resolve_user_id(data.get("user_id"))
    email, source = _find_email(email_id, user_id)
    if email is None:
        abort(404)
    labels = list(email.get("labels", []))
    if action == "add" and label and label not in labels:
        labels.append(label)
        result = "added"
    elif action == "remove" and label in labels:
        labels.remove(label)
        result = "removed"
    else:
        result = "no_change"
    email["labels"] = labels
    if source == "sent":
        sent = _load_sent()
        for s in sent:
            if s["id"] == email_id:
                s["labels"] = labels
        _save_sent(sent)
    return jsonify({"id": email_id, "action": result, "labels": labels})


@blueprint.route("/api/messages/<int:email_id>/delete", methods=["POST"])
def api_delete(email_id):
    data = request.get_json(silent=True) or {}
    user_id = _resolve_user_id(data.get("user_id"))
    email, source = _find_email(email_id, user_id)
    if email is None:
        abort(404)
    old_folder = email.get("folder")
    email["folder"] = "trash"
    if source == "sent":
        sent = _load_sent()
        for s in sent:
            if s["id"] == email_id:
                s["folder"] = "trash"
        _save_sent(sent)
    # Return folder counts so the caller can verify the delete
    if user_id:
        counts = _folder_counts(user_id)
    else:
        counts = {}
    return jsonify({"id": email_id, "old_folder": old_folder,
                    "new_folder": "trash", "folder_counts": counts})


@blueprint.route("/api/folders")
def api_folders():
    user_id = _resolve_user_id(request.args.get("user_id", type=int))
    if not user_id:
        return jsonify(["inbox", "sent", "drafts", "trash", "spam"])
    user = _get_user(user_id)
    if not user:
        abort(404)
    return jsonify(user.get("folders", ["inbox", "sent", "drafts", "trash", "spam"]))


@blueprint.route("/api/folders/<name>/count")
def api_folder_count(name):
    user_id = _resolve_user_id(request.args.get("user_id", type=int))
    if not user_id:
        # Count across all users
        all_emails = list(_get_emails()) + _load_sent()
        emails_in_folder = [e for e in all_emails if e.get("folder") == name]
        return jsonify({"folder": name, "total": len(emails_in_folder),
                        "unread": sum(1 for e in emails_in_folder if not e.get("is_read"))})
    emails = _user_emails(user_id, folder=name)
    return jsonify({
        "folder": name,
        "total": len(emails),
        "unread": sum(1 for e in emails if not e.get("is_read"))
    })


@blueprint.route("/api/contacts")
def api_contacts():
    contacts = _get_contacts()
    q = request.args.get("q", "").strip().lower()
    if q:
        contacts = [c for c in contacts if q in c.lower()]
    return jsonify(contacts)


@blueprint.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    user_id = _resolve_user_id(request.args.get("user_id", type=int))
    if user_id:
        emails = _user_emails(user_id)
    else:
        emails = list(_get_emails()) + _load_sent()
    results = _search_emails(emails, q)
    return jsonify(results)


@blueprint.route("/api/users/<int:user_id>")
def api_user(user_id):
    user = _get_user(user_id)
    if not user:
        abort(404)
    return jsonify({k: v for k, v in user.items() if k != "password"})


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


@blueprint.route("/api/stats")
def api_stats():
    emails = list(_get_emails()) + _load_sent()
    user_id = _resolve_user_id(request.args.get("user_id", type=int))
    if user_id:
        emails = [e for e in emails if e["user_id"] == user_id]
    total = len(emails)
    unread = sum(1 for e in emails if not e.get("is_read"))
    starred = sum(1 for e in emails if e.get("is_starred"))
    folders = {}
    for e in emails:
        f = e.get("folder", "inbox")
        folders[f] = folders.get(f, 0) + 1
    senders = set(e.get("from_addr", "") for e in emails if e.get("from_addr"))
    return jsonify({
        "total": total,
        "unread": unread,
        "starred": starred,
        "folders": folders,
        "unique_senders": len(senders),
    })
