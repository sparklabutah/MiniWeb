"""Email -- Webmail client modeled after Gmail/Outlook.

Data is stored in SQLite: enron emails in the email_emails table, users and
sent messages in per-site typed tables.  Queried through app.db.
"""
import pathlib
import re
from datetime import datetime
from email.utils import parsedate_to_datetime

from flask import Blueprint, Response, abort, jsonify, redirect, render_template, request, session, url_for
from app import db
from app.db import _deserialize_row
from app.events import emit

SITE = "email"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "email",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

EMAILS_PER_PAGE = 25

# ---------------------------------------------------------------------------
# Data interpreter -- reads raw JSONL, maps to users
# ---------------------------------------------------------------------------

# Map known sender addresses to user IDs (must match email_users table).
# Includes both Enron legacy addresses (for routing raw data) and
# Meridian addresses (for compose delivery between app users).
_USER_EMAIL_MAP = {
    # Enron legacy
    "lynn.blair@enron.com": 1,
    "michael.bodnar@enron.com": 2,
    "john.buchanan@enron.com": 3,
    "britt.davis@enron.com": 4,
    "shelley.corman@enron.com": 7,
    # Meridian app users
    "alex.rivera@meridiansystems.com": 1,
    "priya.sharma@meridiansystems.com": 2,
    "marcus.chen@meridiansystems.com": 3,
    "jessica.okafor@meridiansystems.com": 4,
    "david.petrov@meridiansystems.com": 7,
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
    from_addr = (raw.get("from") or raw.get("from_") or "").strip()
    to_addrs = _parse_addr_list(raw.get("to") or "")
    cc_addrs = _parse_addr_list(raw.get("cc") or "")
    subject = (raw.get("subject") or "(no subject)").strip()
    date_obj = _parse_email_date(raw.get("date") or "")
    body = raw.get("body") or ""
    message_id = raw.get("message_id") or ""

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


def _assign_emails_to_users(raw_records):
    """Interpret raw records and assign them to users."""
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
# DB-backed data access  (email_emails table)
# ---------------------------------------------------------------------------


def _db_conn():
    return db.get_conn()


def _db_load_all_raw():
    """Load all raw email records from DB."""
    conn = _db_conn()
    rows = conn.execute(
        "SELECT * FROM email_emails ORDER BY date"
    ).fetchall()
    results = []
    for row in rows:
        raw = _deserialize_row(row)
        # The per-site table uses 'from_' to avoid SQL keyword;
        # _interpret_record expects 'from'
        if "from_" in raw and "from" not in raw:
            raw["from"] = raw.pop("from_")
        results.append(raw)
    return results


# DB emails cache -- loaded and assigned once
_db_emails = None
_db_contacts = None


def _db_ensure_loaded():
    global _db_emails, _db_contacts
    if _db_emails is None:
        raw_records = _db_load_all_raw()
        _db_emails = _assign_emails_to_users(raw_records)
        # Extract contacts
        addr_set = set()
        for e in _db_emails:
            if e["from_addr"]:
                addr_set.add(e["from_addr"])
            for a in e["to_addrs"]:
                addr_set.add(a)
            for a in e["cc_addrs"]:
                addr_set.add(a)
        _db_contacts = sorted(addr_set)


def _db_get_emails():
    _db_ensure_loaded()
    return _db_emails


def _db_get_contacts():
    _db_ensure_loaded()
    return _db_contacts


# ---------------------------------------------------------------------------
# Unified accessors -- always use DB
# ---------------------------------------------------------------------------

def _get_emails():
    return _db_get_emails()


def _get_contacts():
    return _db_get_contacts()


# ---------------------------------------------------------------------------
# Users (mutable state -- stored in per-site SQLite table)
# ---------------------------------------------------------------------------

def _load_users():
    return db.query(SITE, "users")


def _save_users(users):
    db.save_collection(SITE, "users", users)


def _get_user(user_id):
    return db.get_item(SITE, "users", user_id)


def _current_user():
    if "user_id" in session:
        return _get_user(session["user_id"])
    return None


def _session_user_id():
    """Return the user_id from session, or None."""
    return session.get("user_id")


# ---------------------------------------------------------------------------
# Sent messages (mutable state -- stored in per-site SQLite table)
# ---------------------------------------------------------------------------

def _load_sent():
    return db.query(SITE, "sent_messages")


def _save_sent(messages):
    db.save_collection(SITE, "sent_messages", messages)


# ---------------------------------------------------------------------------
# Synthetic overlay emails -- Alex Rivera's Meridian emails
# ---------------------------------------------------------------------------
# The sent_messages.json file contains pre-authored Alex Rivera emails in
# raw format (from/to fields).  We interpret them once into the normalized
# email format and assign user_ids based on @meridiansystems.com addresses.
# These take priority over Enron background data.

_overlay_emails = None


def _build_user_addr_map():
    """Build email_address -> user_id mapping from users.json."""
    users = _load_users()
    return {u["email_address"]: u["id"] for u in users if u.get("email_address")}


def _load_overlay_emails():
    """Interpret sent_messages.json into normalized email objects."""
    global _overlay_emails
    if _overlay_emails is not None:
        return _overlay_emails

    raw_msgs = _load_sent()
    if not raw_msgs:
        _overlay_emails = []
        return _overlay_emails

    addr_map = _build_user_addr_map()
    emails = []

    for idx, raw in enumerate(raw_msgs):
        from_addr = (raw.get("from") or raw.get("from_") or "").strip()
        to_addrs = raw.get("to") or []
        if isinstance(to_addrs, str):
            to_addrs = _parse_addr_list(to_addrs)
        cc_addrs = raw.get("cc") or []
        if isinstance(cc_addrs, str):
            cc_addrs = _parse_addr_list(cc_addrs)

        subject = (raw.get("subject") or "(no subject)").strip()
        date_str = raw.get("date", "")
        try:
            date_obj = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            date_obj = _parse_email_date(date_str)

        body = raw.get("body", "")
        folder = raw.get("folder", "inbox")
        is_read = raw.get("is_read", False)
        is_starred = raw.get("is_starred", False)
        labels = raw.get("labels", [])

        # Determine which user this belongs to
        user_id = None
        # If sender is a known user, assign to them (sent folder)
        sender_uid = addr_map.get(from_addr)
        # If any recipient is a known user, assign to them (inbox)
        recipient_uids = [addr_map[a] for a in to_addrs if a in addr_map]

        if folder == "sent" and sender_uid:
            user_id = sender_uid
        elif recipient_uids:
            user_id = recipient_uids[0]
        elif sender_uid:
            user_id = sender_uid
        else:
            # Default to user 1 (Alex Rivera)
            user_id = 1

        # Use IDs starting at 20000 to avoid collision with Enron (1-N)
        # and composed messages (10000+)
        email_id = 20000 + idx + 1

        email = {
            "id": email_id,
            "from_addr": from_addr,
            "to_addrs": to_addrs,
            "cc_addrs": cc_addrs,
            "subject": subject,
            "date": date_obj.isoformat(),
            "date_display": date_obj.strftime("%b %d, %Y %I:%M %p"),
            "date_sort": date_obj.timestamp(),
            "body": body,
            "body_preview": (body[:120].replace('\n', ' ').replace('\r', ' ').strip() + '...') if len(body) > 120 else body.replace('\n', ' ').replace('\r', ' ').strip(),
            "message_id": raw.get("message_id", f"<overlay-{email_id}@meridiansystems.com>"),
            "folder": folder,
            "is_read": is_read,
            "is_starred": is_starred,
            "labels": labels,
            "user_id": user_id,
        }
        emails.append(email)

        # If this message is TO a known user (inbox), also create a copy
        # in the sender's sent folder (if sender is a known user)
        if folder == "inbox" and sender_uid and sender_uid != user_id:
            sent_copy = dict(email)
            sent_copy["id"] = 20000 + len(raw_msgs) + len(emails) + 1
            sent_copy["folder"] = "sent"
            sent_copy["is_read"] = True
            sent_copy["user_id"] = sender_uid
            emails.append(sent_copy)

    emails.sort(key=lambda e: e.get("date_sort", 0), reverse=True)
    _overlay_emails = emails
    return _overlay_emails


# ---------------------------------------------------------------------------
# Helper: filter emails for current user
# ---------------------------------------------------------------------------

def _user_emails(user_id, folder=None):
    """Get emails for a user, optionally filtered by folder.

    Priority order:
    1. Overlay emails (synthetic Alex Rivera / Meridian emails from sent_messages.json)
    2. Composed emails (runtime-composed messages stored back to sent_messages.json
       with id >= 10000, which are NOT in the overlay set)
    3. Enron background emails (supplementary)
    """
    # Start with overlay (Alex Rivera) emails
    overlay = _load_overlay_emails()
    overlay_ids = {e["id"] for e in overlay}
    emails = [e for e in overlay if e["user_id"] == user_id]

    # Add runtime-composed messages (id >= 10000 and < 20000, not in overlay)
    sent_msgs = _load_sent()
    for sm in sent_msgs:
        sm_id = sm.get("id")
        if sm_id is not None and sm_id not in overlay_ids and sm.get("user_id") == user_id:
            emails.append(sm)

    # Add Enron background emails
    for e in _get_emails():
        if e["user_id"] == user_id:
            emails.append(e)

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
    """Find an email by ID across overlay, static, and sent stores."""
    # Check overlay emails first
    for e in _load_overlay_emails():
        if e["id"] == email_id:
            if user_id is None or e["user_id"] == user_id:
                return e, "overlay"
    # Check static (Enron) emails
    for e in _get_emails():
        if e["id"] == email_id:
            if user_id is None or e["user_id"] == user_id:
                return e, "static"
    # Check runtime-composed sent messages
    sent_msgs = _load_sent()
    overlay_ids = {e["id"] for e in _load_overlay_emails()}
    for e in sent_msgs:
        if e["id"] == email_id and e["id"] not in overlay_ids:
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
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    sort = request.args.get("sort", "date").strip()
    all_emails = _user_emails(user["id"], folder=folder)

    # Date-range filter (date inputs are YYYY-MM-DD; email `date` is an ISO
    # string that starts YYYY-MM-DD, so a lexicographic compare on the first 10
    # chars is a correct inclusive range test).
    if date_from or date_to:
        def _in_range(e):
            d = (e.get("date") or "")[:10]
            if not d:
                return False
            if date_from and d < date_from:
                return False
            if date_to and d > date_to:
                return False
            return True
        all_emails = [e for e in all_emails if _in_range(e)]

    # Sort (toolbar dropdown). Default is most-recent-first by date.
    if sort == "subject":
        all_emails.sort(key=lambda e: (e.get("subject") or "").lower())
    elif sort == "from":
        all_emails.sort(key=lambda e: (e.get("from_addr") or "").lower())
    else:
        all_emails.sort(key=lambda e: e.get("date_sort", 0), reverse=True)

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
    folder = request.args.get("folder", "").strip()
    emails = _user_emails(user["id"], folder=folder or None)
    results = _search_emails(emails, q) if q else []
    counts = _folder_counts(user["id"])
    return render_template("email/search.html", user=user, results=results,
                           q=q, folder=folder, counts=counts)


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
    emit("signup", user_id=user["id"], site_name="email", username=request.form.get("username", ""), password=request.form.get("password", ""), email="")
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


@blueprint.route("/bulk", methods=["POST"])
def form_bulk_action():
    """Handle bulk actions on selected emails (delete, mark read/unread)."""
    user = _current_user()
    if not user:
        return redirect(url_for("email.login_page"))
    action = request.form.get("action", "")
    selected_ids = request.form.getlist("selected")
    folder = request.form.get("folder", "inbox")
    for eid_str in selected_ids:
        try:
            eid = int(eid_str)
        except (ValueError, TypeError):
            continue
        email, source = _find_email(eid, user["id"])
        if not email:
            continue
        if action == "delete":
            email["folder"] = "trash"
            if source == "sent":
                sent = _load_sent()
                for s in sent:
                    if s["id"] == eid:
                        s["folder"] = "trash"
                _save_sent(sent)
        elif action == "mark_read":
            email["is_read"] = True
            if source == "sent":
                sent = _load_sent()
                for s in sent:
                    if s["id"] == eid:
                        s["is_read"] = True
                _save_sent(sent)
        elif action == "mark_unread":
            email["is_read"] = False
            if source == "sent":
                sent = _load_sent()
                for s in sent:
                    if s["id"] == eid:
                        s["is_read"] = False
                _save_sent(sent)
    return redirect(url_for("email.index", folder=folder))


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


@blueprint.route("/message/<int:email_id>/block", methods=["POST"])
def form_block_sender(email_id):
    """Block the sender of a message and move the message to spam."""
    user = _current_user()
    if not user:
        return redirect(url_for("email.login_page"))
    email, source = _find_email(email_id, user["id"])
    if email:
        sender = (email.get("from_addr") or "").strip().lower()
        if sender:
            users = _load_users()
            for u in users:
                if u["id"] == user["id"]:
                    blocked = u.setdefault("blocked_senders", [])
                    if sender not in blocked:
                        blocked.append(sender)
            _save_users(users)
        email["folder"] = "spam"
        if source == "sent":
            sent = _load_sent()
            for s in sent:
                if s["id"] == email_id:
                    s["folder"] = "spam"
            _save_sent(sent)
    return redirect(request.form.get("redirect_to", url_for("email.index")))


@blueprint.route("/message/<int:email_id>/report", methods=["POST"])
def form_report(email_id):
    """Report a message (spam/phishing/other) via form; moves it to spam."""
    user = _current_user()
    if not user:
        return redirect(url_for("email.login_page"))
    reason = request.form.get("reason", "spam").strip()
    details = request.form.get("details", "").strip()
    email, source = _find_email(email_id, user["id"])
    if email:
        users = _load_users()
        for u in users:
            if u["id"] == user["id"]:
                reports = u.setdefault("reported_messages", [])
                reports.append({
                    "email_id": email_id,
                    "from_addr": email.get("from_addr", ""),
                    "subject": email.get("subject", ""),
                    "reason": reason,
                    "details": details,
                })
        _save_users(users)
        email["folder"] = "spam"
        if source == "sent":
            sent = _load_sent()
            for s in sent:
                if s["id"] == email_id:
                    s["folder"] = "spam"
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
        # No user_id: return all emails (overlay + Enron + composed)
        overlay = _load_overlay_emails()
        overlay_ids = {e["id"] for e in overlay}
        emails = list(overlay)
        emails.extend(_get_emails())
        # Add runtime-composed messages not already in overlay
        for sm in _load_sent():
            if sm.get("id") not in overlay_ids:
                emails.append(sm)
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
        overlay = _load_overlay_emails()
        overlay_ids = {e["id"] for e in overlay}
        all_emails = list(overlay) + list(_get_emails())
        all_emails.extend(sm for sm in _load_sent() if sm.get("id") not in overlay_ids)
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
        overlay = _load_overlay_emails()
        overlay_ids = {e["id"] for e in overlay}
        emails = list(overlay) + list(_get_emails())
        emails.extend(sm for sm in _load_sent() if sm.get("id") not in overlay_ids)
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
    overlay = _load_overlay_emails()
    overlay_ids = {e["id"] for e in overlay}
    emails = list(overlay) + list(_get_emails())
    emails.extend(sm for sm in _load_sent() if sm.get("id") not in overlay_ids)
    user_id = _resolve_user_id(request.args.get("user_id", type=int))
    if user_id:
        emails = [e for e in emails if e.get("user_id") == user_id]
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


@blueprint.route("/api/export")
def api_export():
    """Export emails as JSON or CSV."""
    fmt = request.args.get("format", "json").lower()
    folder = request.args.get("folder", "").strip()
    user_id = _resolve_user_id(request.args.get("user_id", type=int))

    overlay = _load_overlay_emails()
    overlay_ids = {e["id"] for e in overlay}
    emails = list(overlay) + list(_get_emails())
    emails.extend(sm for sm in _load_sent() if sm.get("id") not in overlay_ids)

    if user_id:
        emails = [e for e in emails if e.get("user_id") == user_id]
    if folder:
        emails = [e for e in emails if e.get("folder") == folder]

    emails.sort(key=lambda e: e.get("date_sort", 0), reverse=True)
    emails = emails[:500]  # cap export size

    if fmt == "csv":
        lines = ["id,from_addr,to_addr,subject,date,folder,is_read,is_starred"]
        for e in emails:
            subj = str(e.get("subject", "")).replace('"', '""')
            lines.append(f'{e.get("id", "")},"{e.get("from_addr", "")}","{e.get("to_addr", "")}","{subj}","{e.get("date", "")}","{e.get("folder", "")}",{e.get("is_read", False)},{e.get("is_starred", False)}')
        return Response("\n".join(lines), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=emails.csv"})
    return jsonify(emails)
