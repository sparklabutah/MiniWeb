"""VaultGuard — password manager web app (1Password / LastPass style).

Reads pre-existing data from DATA_SOURCES_DIR/password-managers/ and serves
a full password vault management interface.  Data files:
  - entries.json   — password entries (logins, secure notes, credit cards)
  - vaults.json    — vaults/collections
  - audit_log.json — access & change audit trail
  - security_report.json — security analysis / score
  - users.json     — user profiles
"""

import csv
import io
import os
import pathlib
import random
import string
import uuid
from collections import Counter
from datetime import datetime
from urllib.parse import urlparse

from flask import (
    Blueprint, Response, abort, jsonify, redirect, render_template, request,
    session, url_for,
)
from app import db

SITE = "password-managers"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "password-managers",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def _load_entries():
    return db.query(SITE, "entries")


def _load_vaults():
    return db.query(SITE, "vaults")


def _load_audit_log():
    return db.query(SITE, "audit_log")


def _load_security_report():
    rows = db.query(SITE, "security_report")
    return rows[0] if rows else {}


def _load_users():
    return db.query(SITE, "users")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _current_user():
    """Return the logged-in user dict or the first user (demo mode)."""
    users = _load_users()
    uid = session.get("user_id")
    if uid:
        user = next((u for u in users if u["id"] == uid), None)
        if user:
            return user
    return users[0] if users else None


def _is_logged_in():
    return "user_id" in session


def _user_accessible_vaults(user):
    """Return vault IDs the user can access."""
    vaults = _load_vaults()
    uid = user["id"]
    return [v for v in vaults if any(m["user_id"] == uid for m in v.get("members", []))]


def _mask_password(pw):
    """Return masked version of password for display."""
    if not pw:
        return ""
    if len(pw) <= 4:
        return "*" * len(pw)
    return pw[:2] + "*" * (len(pw) - 4) + pw[-2:]


def _generate_password(length=20, uppercase=True, lowercase=True, digits=True,
                       symbols=True, exclude_ambiguous=False):
    """Generate a random password."""
    chars = ""
    required = []
    if uppercase:
        pool = string.ascii_uppercase
        if exclude_ambiguous:
            pool = pool.replace("O", "").replace("I", "")
        chars += pool
        required.append(random.choice(pool))
    if lowercase:
        pool = string.ascii_lowercase
        if exclude_ambiguous:
            pool = pool.replace("l", "").replace("o", "")
        chars += pool
        required.append(random.choice(pool))
    if digits:
        pool = string.digits
        if exclude_ambiguous:
            pool = pool.replace("0", "").replace("1", "")
        chars += pool
        required.append(random.choice(pool))
    if symbols:
        pool = "!@#$%^&*()-_=+[]{}|;:,.<>?"
        chars += pool
        required.append(random.choice(pool))

    if not chars:
        chars = string.ascii_letters + string.digits
        required = [random.choice(chars)]

    length = max(length, len(required))
    remaining = length - len(required)
    pw_chars = required + [random.choice(chars) for _ in range(remaining)]
    random.shuffle(pw_chars)
    return "".join(pw_chars)


# ---------------------------------------------------------------------------
# Security analysis — computed LIVE from the user's vault entries
# ---------------------------------------------------------------------------

# Small, deterministic seeded breach dataset. An entry is considered breached if
# its stored password appears on this known-compromised list, or its website's
# domain is one of these previously-breached services.
_BREACHED_PASSWORDS = {
    "123456", "123456789", "12345678", "password", "password1", "qwerty",
    "abc123", "letmein", "iloveyou", "admin", "welcome", "monkey", "dragon",
    "111111", "123123", "000000", "sunshine", "pass123", "login", "trustno1",
}
_BREACHED_DOMAINS = {
    "linkedin.com", "adobe.com", "dropbox.com", "myspace.com", "canva.com",
    "tumblr.com", "github.com", "netflix.com", "lastpass.com", "twitter.com",
}

# Points awarded per strength tier, and rank used for vault averages.
_STRENGTH_SCORE = {"excellent": 1.0, "strong": 0.8, "fair": 0.5, "weak": 0.15}
_STRENGTH_RANK = {"weak": 1, "fair": 2, "strong": 3, "excellent": 4}

# A password older than this many days is flagged as "aging".
_STALE_DAYS = 365


def _entry_domain(url):
    """Extract a bare domain (no www.) from a URL for breach matching."""
    if not url:
        return ""
    try:
        net = urlparse(url if "://" in url else "http://" + url).netloc.lower()
    except Exception:
        return ""
    if net.startswith("www."):
        net = net[4:]
    return net.split(":")[0]


def _classify_password(pw):
    """Derive a strength label from the actual password characters.

    Returns (label, num_character_classes, length).
    """
    pw = pw or ""
    length = len(pw)
    lower = any(c.islower() for c in pw)
    upper = any(c.isupper() for c in pw)
    digit = any(c.isdigit() for c in pw)
    symbol = any((not c.isalnum()) and (not c.isspace()) for c in pw)
    classes = sum([lower, upper, digit, symbol])
    if length < 8 or classes <= 1 or (length < 10 and classes <= 2):
        return "weak", classes, length
    if length < 12 or classes <= 2:
        return "fair", classes, length
    if length < 16 or classes == 3:
        return "strong", classes, length
    return "excellent", classes, length


def _weakness_reason(label, classes, length):
    if label == "weak":
        if length < 8:
            return f"Only {length} characters — far too short"
        if classes <= 1:
            return "Single character type — no complexity"
        return f"{length} characters with limited character variety"
    if length < 12:
        return f"{length} characters — below the recommended length"
    return "Only three character types — add symbols or mixed case"


def _password_age_days(entry, now):
    ts = entry.get("updated_at") or entry.get("created_at") or ""
    try:
        return (now - datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S")).days
    except Exception:
        return 0


def _is_breached(entry):
    """Return (breached_bool, how) where how is 'password' or 'domain'."""
    pw = entry.get("password", "")
    if pw and pw.lower() in _BREACHED_PASSWORDS:
        return True, "password"
    if _entry_domain(entry.get("url", "")) in _BREACHED_DOMAINS:
        return True, "domain"
    return False, ""


def _user_vault_entries(user):
    """Fetch the entries in every vault the user can access.

    Queried per-vault at the SQL level (each vault is a bounded, <100-row working
    set), never a full-table scan of the shared entries table.
    """
    vaults = _user_accessible_vaults(user)
    entries = []
    for v in vaults:
        entries.extend(db.query(SITE, "entries", where={"vault_id": v["id"]}))
    return entries, vaults


def _compute_security_report(user, entries=None, vaults=None):
    """Build the security report by analysing the user's live vault entries.

    The score, breach alerts, weak/reused/aging lists and per-vault health are all
    derived from the actual stored passwords, so the report changes whenever an
    entry is added, edited or removed.
    """
    if entries is None or vaults is None:
        entries, vaults = _user_vault_entries(user)

    now = datetime.utcnow()
    pw_entries = [e for e in entries if e.get("password")]
    denom = len(pw_entries) or 1

    counts = Counter(e["password"] for e in pw_entries if e.get("password"))
    reused_values = {p for p, c in counts.items() if c >= 2}

    labels = {"excellent": 0, "strong": 0, "fair": 0, "weak": 0}
    breakdown = []
    reused_entries = []
    old_entries = []
    breached_entries = []
    score_sum = 0.0

    for e in pw_entries:
        label, classes, length = _classify_password(e["password"])
        labels[label] += 1
        pts = _STRENGTH_SCORE[label]

        reused = e["password"] in reused_values
        breached, how = _is_breached(e)
        age = _password_age_days(e, now)
        old = age > _STALE_DAYS

        if reused:
            pts -= 0.3
            reused_entries.append(e)
        if breached:
            pts -= 0.4
            breached_entries.append((e, how))
        if old:
            pts -= 0.1
            old_entries.append((e, age))
        score_sum += max(0.0, pts)

        if label in ("weak", "fair"):
            breakdown.append({
                "entry_id": e["id"],
                "title": e.get("title", ""),
                "strength": label,
                "reason": _weakness_reason(label, classes, length),
            })

    overall = round(100 * score_sum / denom)
    if overall >= 80:
        rating = "Excellent"
    elif overall >= 60:
        rating = "Good"
    elif overall >= 40:
        rating = "Fair"
    else:
        rating = "Poor"

    breakdown.sort(key=lambda b: 0 if b["strength"] == "weak" else 1)

    # Reused-password groups (password values themselves are never exposed).
    grouped = {}
    for e in pw_entries:
        if e["password"] in reused_values:
            grouped.setdefault(e["password"], []).append(e)
    reused_groups = [
        {
            "count": len(es),
            "entries": [{"entry_id": x["id"], "title": x.get("title", "")} for x in es],
        }
        for es in grouped.values()
    ]
    reused_groups.sort(key=lambda g: -g["count"])

    # Breach alerts.
    breach_alerts = []
    for e, how in breached_entries:
        if how == "domain":
            src = f"{_entry_domain(e.get('url', ''))} data breach"
            exposed = ["email", "password"]
        else:
            src = "Known-compromised password list"
            exposed = ["password"]
        breach_alerts.append({
            "id": f"breach_{e['id']}",
            "severity": "high",
            "detected_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "entry_id": e["id"],
            "entry_title": e.get("title", ""),
            "email_exposed": e.get("username", ""),
            "breach_source": src,
            "breach_date": (e.get("updated_at") or e.get("created_at") or "")[:10],
            "data_exposed": exposed,
            "recommendation": f"Change the password for {e.get('title', '')} "
                              f"immediately and enable two-factor authentication.",
        })
    breach_alerts.sort(key=lambda a: a["entry_title"])

    # Aging passwords.
    old_entries.sort(key=lambda t: -t[1])
    older_than_1_year = [
        {"entry_id": e["id"], "title": e.get("title", ""), "age_days": age}
        for e, age in old_entries[:12]
    ]

    # Per-vault health.
    vault_health = []
    for v in vaults:
        ves = [e for e in entries if e["vault_id"] == v["id"]]
        pw_ves = [e for e in ves if e.get("password")]
        if pw_ves:
            avg = sum(_STRENGTH_RANK[_classify_password(e["password"])[0]]
                      for e in pw_ves) / len(pw_ves)
        else:
            avg = 0
        issues = []
        wk = sum(1 for e in pw_ves if _classify_password(e["password"])[0] == "weak")
        ru = sum(1 for e in pw_ves if e["password"] in reused_values)
        br = sum(1 for e in pw_ves if _is_breached(e)[0])
        if wk:
            issues.append(f"{wk} weak password{'s' if wk != 1 else ''}")
        if ru:
            issues.append(f"{ru} reused password{'s' if ru != 1 else ''}")
        if br:
            issues.append(f"{br} breached password{'s' if br != 1 else ''}")
        if not issues:
            issues.append("No critical issues detected")
        vault_health.append({
            "vault_name": v.get("name", ""),
            "entries": len(ves),
            "avg_strength_score": round(avg, 1),
            "issues": issues,
        })

    # Recommendations.
    recommendations = []
    if breached_entries:
        recommendations.append({
            "priority": "critical",
            "action": f"Change {len(breached_entries)} password(s) exposed in known breaches.",
            "entry_id": breached_entries[0][0]["id"],
        })
    if reused_entries:
        recommendations.append({
            "priority": "high",
            "action": f"Replace {len(reused_entries)} reused password(s) with unique ones.",
            "entry_id": reused_entries[0]["id"],
        })
    if labels["weak"]:
        recommendations.append({
            "priority": "high",
            "action": f"Strengthen {labels['weak']} weak password(s).",
            "entry_id": breakdown[0]["entry_id"] if breakdown else "",
        })
    if old_entries:
        recommendations.append({
            "priority": "medium",
            "action": f"Rotate {len(old_entries)} password(s) older than one year.",
            "entry_id": old_entries[0][0]["id"],
        })
    if not recommendations:
        recommendations.append({
            "priority": "low",
            "action": "Your vault looks healthy — keep it up!",
            "entry_id": "",
        })

    cats = Counter(e.get("category", "login") for e in entries)

    return {
        "report_generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "user_id": user["id"] if user else 0,
        "user_name": user.get("display_name", "") if user else "",
        "overall_score": overall,
        "overall_rating": rating,
        "summary": {
            "total_entries": len(entries),
            "login_entries": cats.get("login", 0),
            "secure_note_entries": cats.get("secure_note", 0),
            "credit_card_entries": cats.get("credit_card", 0),
            "total_vaults": len(vaults),
            "shared_vaults": sum(1 for v in vaults if v.get("shared")),
        },
        "password_strength": {
            "excellent": labels["excellent"],
            "strong": labels["strong"],
            "fair": labels["fair"],
            "weak": labels["weak"],
            "breakdown": breakdown[:15],
        },
        "reused_passwords": {
            "count": len(reused_entries),
            "group_count": len(reused_groups),
            "groups": reused_groups[:12],
        },
        "breach_alerts": breach_alerts[:12],
        "password_age": {
            "older_than_1_year": older_than_1_year,
            "count": len(old_entries),
            "recommendation": "Passwords unchanged for over a year should be rotated, "
                              "especially for financial and email accounts.",
        },
        "vault_health": vault_health,
        "recommendations": recommendations,
        # Convenience counters (used by the dashboard and tests).
        "weak_count": labels["weak"],
        "reused_count": len(reused_entries),
        "old_count": len(old_entries),
        "breach_count": len(breach_alerts),
    }


# ---------------------------------------------------------------------------
# Audit log — record real actions to session_overlay
# ---------------------------------------------------------------------------

def _log_audit(action, entry=None, details="", vault_id=""):
    """Append a persisted audit-log row for a user action."""
    user = _current_user()
    uid = session.get("user_id") or (user["id"] if user else 0)
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    row = {
        "id": f"audit_{uuid.uuid4().hex[:12]}",
        "timestamp": now,
        "user_id": uid,
        "action": action,
        "entry_id": entry.get("id", "") if entry else "",
        "entry_title": entry.get("title", "") if entry else "",
        "vault_id": vault_id or (entry.get("vault_id", "") if entry else ""),
        "ip_address": request.remote_addr or "198.51.100.24",
        "device": "VaultGuard Web",
        "details": details,
    }
    try:
        db.save_item(SITE, "audit_log", row["id"], row)
    except Exception:
        pass
    return row


def _compute_stats(entries, vaults, report):
    """Compute summary statistics."""
    categories = {}
    strengths = {}
    for e in entries:
        cat = e.get("category", "login")
        categories[cat] = categories.get(cat, 0) + 1
        st = e.get("strength")
        if st:
            strengths[st] = strengths.get(st, 0) + 1

    fav_count = sum(1 for e in entries if e.get("favorite"))

    return {
        "total_entries": len(entries),
        "total_vaults": len(vaults),
        "categories": categories,
        "strengths": strengths,
        "favorites": fav_count,
        "overall_score": report.get("overall_score", 0) if isinstance(report, dict) else 0,
        "overall_rating": report.get("overall_rating", "N/A") if isinstance(report, dict) else "N/A",
        "breach_count": len(report.get("breach_alerts", [])) if isinstance(report, dict) else 0,
        "weak_count": strengths.get("weak", 0),
        "fair_count": strengths.get("fair", 0),
    }


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    """Vault overview dashboard."""
    user = _current_user()
    entries, accessible = _user_vault_entries(user)
    report = _compute_security_report(user, entries, accessible)

    # Count entries per vault
    for v in accessible:
        v["_entry_count"] = sum(1 for e in entries if e["vault_id"] == v["id"])

    ps = report["password_strength"]
    stats = {
        "total_entries": report["summary"]["total_entries"],
        "total_vaults": report["summary"]["total_vaults"],
        "favorites": sum(1 for e in entries if e.get("favorite")),
        "strengths": {k: ps[k] for k in ("excellent", "strong", "fair", "weak")},
        "weak_count": ps["weak"],
        "fair_count": ps["fair"],
        "breach_count": report["breach_count"],
    }

    recent_entries = sorted(
        entries,
        key=lambda e: e.get("last_used", ""),
        reverse=True,
    )[:5]

    return render_template(
        "password-managers/index.html",
        user=user,
        vaults=accessible,
        stats=stats,
        recent_entries=recent_entries,
        report=report,
        logged_in=_is_logged_in(),
    )


@blueprint.route("/vault/<vault_id>")
def vault_detail(vault_id):
    """Show entries in a vault."""
    user = _current_user()
    vault = db.get_item(SITE, "vaults", vault_id)
    if vault is None:
        abort(404)

    vault_entries = db.query(SITE, "entries", where={"vault_id": vault_id})

    # Filters
    category = request.args.get("category", "")
    search = request.args.get("q", "").strip().lower()
    strength = request.args.get("strength", "")
    favorites_only = request.args.get("favorites") == "1"

    if category:
        vault_entries = [e for e in vault_entries if e.get("category") == category]
    if strength:
        vault_entries = [e for e in vault_entries if e.get("strength") == strength]
    if favorites_only:
        vault_entries = [e for e in vault_entries if e.get("favorite")]
    if search:
        vault_entries = [
            e for e in vault_entries
            if search in e.get("title", "").lower()
            or search in e.get("url", "").lower()
            or search in e.get("username", "").lower()
            or search in " ".join(e.get("tags", [])).lower()
        ]

    vault_entries.sort(key=lambda e: e.get("title", "").lower())

    categories = sorted({e.get("category", "login") for e in vault_entries})

    return render_template(
        "password-managers/vault.html",
        user=user,
        vault=vault,
        entries=vault_entries,
        categories=categories,
        filter_category=category,
        filter_search=search if search else "",
        filter_strength=strength,
        filter_favorites=favorites_only,
        logged_in=_is_logged_in(),
    )


@blueprint.route("/entry/<entry_id>")
def entry_detail(entry_id):
    """Show password entry detail."""
    user = _current_user()
    entry = db.get_item(SITE, "entries", entry_id)
    if entry is None:
        abort(404)

    vault = db.get_item(SITE, "vaults", entry["vault_id"])

    # Mask password for display
    masked_pw = _mask_password(entry.get("password", ""))

    entry_audit = db.query(SITE, "audit_log", where={"entry_id": entry_id},
                           sort="-timestamp", limit=10)

    return render_template(
        "password-managers/entry_detail.html",
        user=user,
        entry=entry,
        vault=vault,
        masked_password=masked_pw,
        audit_log=entry_audit,
        logged_in=_is_logged_in(),
    )


@blueprint.route("/generator")
def generator_page():
    """Password generator page."""
    user = _current_user()
    return render_template(
        "password-managers/generator.html",
        user=user,
        logged_in=_is_logged_in(),
    )


@blueprint.route("/security-report")
def security_report_page():
    """Security analysis page — computed live from the user's vault entries."""
    user = _current_user()
    entries, vaults = _user_vault_entries(user)
    report = _compute_security_report(user, entries, vaults)

    return render_template(
        "password-managers/security_report.html",
        user=user,
        report=report,
        entries=entries,
        logged_in=_is_logged_in(),
    )


@blueprint.route("/audit-log")
def audit_log_page():
    """Access history page."""
    user = _current_user()
    users = _load_users()
    user_map = {u["id"]: u["display_name"] for u in users}

    # Filters — pushed into the SQL WHERE clause; newest events first.
    action_filter = request.args.get("action", "")
    vault_filter = request.args.get("vault", "")
    where_f = {}
    if action_filter:
        where_f["action"] = action_filter
    if vault_filter:
        where_f["vault_id"] = vault_filter

    audit_log = db.query(SITE, "audit_log", where=where_f or None,
                         sort="-timestamp", limit=100)

    vaults = _load_vaults()
    # Distinct action names for the filter dropdown (bounded set of labels).
    known_actions = {"view_password", "reveal_password", "autofill",
                     "create_entry", "edit_entry", "delete_entry",
                     "login_success", "login_failed", "share_vault"}
    known_actions.update(a.get("action", "") for a in audit_log)
    actions = sorted(a for a in known_actions if a)

    return render_template(
        "password-managers/audit_log.html",
        user=user,
        audit_log=audit_log,
        user_map=user_map,
        vaults=vaults,
        actions=actions,
        filter_action=action_filter,
        filter_vault=vault_filter,
        logged_in=_is_logged_in(),
    )


@blueprint.route("/login", methods=["GET"])
def login_page():
    """Login page."""
    return render_template("password-managers/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    """Process login form."""
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["email"] == email), None)
    if not user:
        return render_template("password-managers/login.html",
                               error="Invalid email or master password")
    # In this demo, any non-empty password works for existing users
    if not password:
        return render_template("password-managers/login.html",
                               error="Please enter your master password")
    session["user_id"] = user["id"]
    return redirect(url_for("password-managers.index"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("password-managers.index"))


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/vaults")
def api_vaults():
    """List vaults accessible to the current user."""
    user = _current_user()
    vaults = _user_accessible_vaults(user)
    entries = _load_entries()
    for v in vaults:
        v["_entry_count"] = sum(1 for e in entries if e["vault_id"] == v["id"])
    return jsonify(vaults)


@blueprint.route("/api/vaults/<vault_id>")
def api_vault(vault_id):
    """Get a single vault with its entries."""
    vault = db.get_item(SITE, "vaults", vault_id)
    if not vault:
        abort(404)
    vault_entries = db.query(SITE, "entries", where={"vault_id": vault_id})
    result = dict(vault)
    result["entries"] = vault_entries
    return jsonify(result)


@blueprint.route("/api/entries", methods=["GET"])
def api_entries_list():
    """List entries with optional filters."""
    vault_id = request.args.get("vault_id")
    category = request.args.get("category")
    strength = request.args.get("strength")
    tag = request.args.get("tag")
    favorites = request.args.get("favorites")
    where_f = {}
    if vault_id:
        where_f["vault_id"] = vault_id
    if category:
        where_f["category"] = category
    if strength:
        where_f["strength"] = strength
    entries = db.query(SITE, "entries", where=where_f if where_f else None)
    if tag:
        entries = [e for e in entries if tag in e.get("tags", [])]
    if favorites == "1":
        entries = [e for e in entries if e.get("favorite")]

    return jsonify(entries)


@blueprint.route("/api/entries", methods=["POST"])
def api_entries_create():
    """Create a new entry."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body required"}), 400

    entries = _load_entries()

    # Generate ID
    max_num = 0
    for e in entries:
        try:
            num = int(e["id"].split("_")[1])
            if num > max_num:
                max_num = num
        except (IndexError, ValueError):
            pass
    new_id = f"entry_{max_num + 1:03d}"

    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    new_entry = {
        "id": new_id,
        "vault_id": data.get("vault_id", "vault_001"),
        "title": data.get("title", "Untitled"),
        "url": data.get("url", ""),
        "username": data.get("username", ""),
        "password": data.get("password", ""),
        "category": data.get("category", "login"),
        "notes": data.get("notes", ""),
        "created_at": now,
        "updated_at": now,
        "last_used": now,
        "strength": data.get("strength", "strong"),
        "favorite": data.get("favorite", False),
        "tags": data.get("tags", []),
    }

    if data.get("category") == "credit_card" and data.get("card_details"):
        new_entry["card_details"] = data["card_details"]

    entries.append(new_entry)
    db.save_collection(SITE, "entries", entries)
    _log_audit("create_entry", new_entry,
               details=f"Created {new_entry.get('category', 'login')} entry via API")

    return jsonify(new_entry), 201


@blueprint.route("/api/entries/search")
def api_entries_search():
    """Search entries by query string."""
    q = request.args.get("q", "").strip().lower()
    if not q:
        return jsonify([])

    entries = _load_entries()
    results = [
        e for e in entries
        if q in e.get("title", "").lower()
        or q in e.get("url", "").lower()
        or q in e.get("username", "").lower()
        or q in e.get("notes", "").lower()
        or q in " ".join(e.get("tags", [])).lower()
    ]
    return jsonify(results)


@blueprint.route("/api/entries/<entry_id>", methods=["GET"])
def api_entry_get(entry_id):
    """Get a single entry."""
    entry = db.get_item(SITE, "entries", entry_id)
    if not entry:
        abort(404)
    return jsonify(entry)


@blueprint.route("/api/entries/<entry_id>", methods=["PUT"])
def api_entry_update(entry_id):
    """Update an existing entry."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body required"}), 400

    entries = _load_entries()
    entry = next((e for e in entries if e["id"] == entry_id), None)
    if not entry:
        abort(404)

    updatable = ["title", "url", "username", "password", "category",
                 "notes", "strength", "favorite", "tags"]
    for field in updatable:
        if field in data:
            entry[field] = data[field]

    if "card_details" in data:
        entry["card_details"] = data["card_details"]

    entry["updated_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    db.save_collection(SITE, "entries", entries)
    _log_audit("edit_entry", entry, details="Entry updated via API")
    return jsonify(entry)


@blueprint.route("/api/entries/<entry_id>", methods=["DELETE"])
def api_entry_delete(entry_id):
    """Delete an entry."""
    entries = _load_entries()
    idx = next((i for i, e in enumerate(entries) if e["id"] == entry_id), None)
    if idx is None:
        abort(404)

    deleted = entries.pop(idx)
    db.save_collection(SITE, "entries", entries)
    _log_audit("delete_entry", deleted, details="Entry deleted via API")
    return jsonify({"deleted": deleted["id"], "title": deleted["title"]})


@blueprint.route("/api/audit-log")
def api_audit_log():
    """Return audit log with optional filters."""
    audit_log = _load_audit_log()

    action = request.args.get("action")
    vault_id = request.args.get("vault_id")
    user_id = request.args.get("user_id")
    limit = request.args.get("limit", type=int)

    if action:
        audit_log = [a for a in audit_log if a.get("action") == action]
    if vault_id:
        audit_log = [a for a in audit_log if a.get("vault_id") == vault_id]
    if user_id:
        uid = int(user_id)
        audit_log = [a for a in audit_log if a.get("user_id") == uid]
    if limit and limit > 0:
        audit_log = audit_log[:limit]

    return jsonify(audit_log)


@blueprint.route("/api/security-report")
def api_security_report():
    """Return the security report, computed live from the user's vault entries."""
    report = _compute_security_report(_current_user())
    return jsonify(report)


@blueprint.route("/api/generate-password")
def api_generate_password():
    """Generate a random password."""
    length = request.args.get("length", 20, type=int)
    length = max(8, min(128, length))
    uppercase = request.args.get("uppercase", "1") != "0"
    lowercase = request.args.get("lowercase", "1") != "0"
    digits = request.args.get("digits", "1") != "0"
    symbols = request.args.get("symbols", "1") != "0"
    exclude_ambiguous = request.args.get("exclude_ambiguous", "0") == "1"

    pw = _generate_password(
        length=length,
        uppercase=uppercase,
        lowercase=lowercase,
        digits=digits,
        symbols=symbols,
        exclude_ambiguous=exclude_ambiguous,
    )

    return jsonify({
        "password": pw,
        "length": len(pw),
        "settings": {
            "uppercase": uppercase,
            "lowercase": lowercase,
            "digits": digits,
            "symbols": symbols,
            "exclude_ambiguous": exclude_ambiguous,
        },
    })


@blueprint.route("/api/stats")
def api_stats():
    """Return summary statistics."""
    entries = _load_entries()
    vaults = _load_vaults()
    report = _load_security_report()
    vault_id = request.args.get("vault_id")
    category = request.args.get("category")
    if vault_id:
        entries = [e for e in entries if e["vault_id"] == vault_id]
    if category:
        entries = [e for e in entries if e.get("category") == category]
    stats = _compute_stats(entries, vaults, report)
    return jsonify(stats)


# ---------------------------------------------------------------------------
# Semantic search helper
# ---------------------------------------------------------------------------

def _semantic_score(query, entry):
    """Simple keyword-overlap scoring for semantic search."""
    terms = query.lower().split()
    text = " ".join([
        entry.get("title", ""),
        entry.get("url", ""),
        entry.get("username", ""),
        entry.get("notes", ""),
        " ".join(entry.get("tags", [])),
        entry.get("category", ""),
    ]).lower()
    return sum(1 for t in terms if t in text)


@blueprint.route("/api/entries/semantic")
def api_entries_semantic():
    """Semantic search — rank entries by keyword overlap relevance."""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    entries = _load_entries()
    scored = [(e, _semantic_score(q, e)) for e in entries]
    scored = [(e, s) for e, s in scored if s > 0]
    scored.sort(key=lambda x: -x[1])
    return jsonify([e for e, _ in scored])


# ---------------------------------------------------------------------------
# Reveal password with 2FA via instant messaging
# ---------------------------------------------------------------------------

@blueprint.route("/api/entries/<entry_id>/request-reveal", methods=["POST"])
def api_request_reveal(entry_id):
    """Generate a 6-digit PIN and send it to the user via instant messaging."""
    entry = db.get_item(SITE, "entries", entry_id)
    if not entry:
        abort(404)

    pin = f"{random.randint(100000, 999999)}"
    session["_pw_reveal_pin"] = {
        "pin": pin,
        "entry_id": entry_id,
        "created": datetime.utcnow().isoformat() + "Z",
    }

    # Send PIN via instant messaging bridge
    user = _current_user()
    user_root_id = user.get("root_user_id", 1) if user else 1
    try:
        _send_im_pin(user_root_id, pin, entry.get("title", ""))
    except Exception:
        pass

    return jsonify({"status": "pin_sent", "entry_id": entry_id,
                    "message": "A verification PIN has been sent to your instant messages."})


@blueprint.route("/api/entries/<entry_id>/confirm-reveal", methods=["POST"])
def api_confirm_reveal(entry_id):
    """Verify the PIN and return the full password."""
    pending = session.get("_pw_reveal_pin")
    if not pending or pending.get("entry_id") != entry_id:
        return jsonify({"error": "No pending reveal request. Click Reveal first."}), 400

    data = request.get_json(silent=True) or {}
    pin = data.get("pin", "").strip()

    if pin != pending["pin"]:
        return jsonify({"error": "Invalid PIN. Check your instant messages."}), 403

    # PIN correct — return password
    entry = db.get_item(SITE, "entries", entry_id)
    if not entry:
        abort(404)

    session.pop("_pw_reveal_pin", None)
    _log_audit("reveal_password", entry,
               details="Password revealed after PIN verification")
    return jsonify({
        "entry_id": entry_id,
        "title": entry.get("title", ""),
        "password": entry.get("password", ""),
        "username": entry.get("username", ""),
    })


@blueprint.route("/api/entries/<entry_id>/reveal", methods=["POST"])
def api_entry_reveal(entry_id):
    """Reveal the full password (legacy direct reveal, kept for API compat)."""
    entry = db.get_item(SITE, "entries", entry_id)
    if not entry:
        abort(404)
    _log_audit("reveal_password", entry, details="Password revealed")
    return jsonify({
        "entry_id": entry_id,
        "title": entry.get("title", ""),
        "password": entry.get("password", ""),
        "username": entry.get("username", ""),
    })


def _send_im_pin(root_user_id, pin, entry_title):
    """Send a 2FA PIN to the user's instant messaging account."""
    import uuid

    # Find the user's IM id from root_user_id
    im_user = db.execute(
        "SELECT id FROM instant_messaging_users WHERE root_user_id = ? LIMIT 1",
        (root_user_id,), fetch="one",
    )
    if not im_user:
        return
    to_user_id = im_user["id"] if isinstance(im_user, dict) else im_user[0]

    # Find or create a conversation with VaultGuard
    sender_id = "vaultguard-security"
    convs = db.query("instant-messaging", "conversations", limit=200)
    conv_id = None
    for c in convs:
        participants = c.get("participants", [])
        pids = [p.get("user_id") if isinstance(p, dict) else p for p in participants]
        if sender_id in pids and to_user_id in pids:
            conv_id = c["id"]
            break

    if not conv_id:
        conv_id = f"conv-vaultguard-{uuid.uuid4().hex[:6]}"
        import json
        conv = {
            "id": conv_id,
            "type": "direct",
            "participants": json.dumps([sender_id, to_user_id]),
            "participant_names": json.dumps(["VaultGuard Security", "You"]),
            "created": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "last_message": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "message_count": 0,
            "pinned_count": 0,
            "muted": 0,
            "name": "",
            "group_photo": "",
            "admin": "",
            "note": "",
        }
        db.save_item("instant-messaging", "conversations", conv_id, conv)

    msg_id = f"im-vault-{uuid.uuid4().hex[:8]}"
    msg = {
        "id": msg_id,
        "conversation_id": conv_id,
        "sender_id": sender_id,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "text": (f"Your VaultGuard verification PIN is: {pin}\n\n"
                 f"Requested for: {entry_title}\n"
                 f"This code expires in 10 minutes. "
                 f"If you did not request this, change your master password immediately."),
        "read": 0,
        "media_id": "",
    }
    db.save_item("instant-messaging", "messages", msg_id, msg)


# ---------------------------------------------------------------------------
# API login (authenticate_by_code)
# ---------------------------------------------------------------------------

@blueprint.route("/api/login", methods=["POST"])
def api_login():
    """Authenticate with email + master password (code-based auth)."""
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip()
    master_password = data.get("master_password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["email"] == email), None)
    if not user:
        return jsonify({"error": "Invalid email or master password"}), 401
    # Check master_password field
    if user.get("master_password") and user["master_password"] != master_password:
        return jsonify({"error": "Invalid email or master password"}), 401
    if not master_password:
        return jsonify({"error": "Master password required"}), 401
    session["user_id"] = user["id"]
    return jsonify({
        "user_id": user["id"],
        "email": user["email"],
        "display_name": user["display_name"],
        "requires_2fa": user.get("two_factor_enabled", False),
    })


# ---------------------------------------------------------------------------
# 2FA verification (verify_identity_by_code)
# ---------------------------------------------------------------------------

@blueprint.route("/api/verify-2fa", methods=["POST"])
def api_verify_2fa():
    """Verify two-factor authentication code."""
    data = request.get_json(silent=True) or {}
    code = data.get("code", "").strip()
    user_id = data.get("user_id") or session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        return jsonify({"error": "User not found"}), 404
    # Accept the backup code or any 6-digit code matching stored codes
    valid_codes = user.get("two_factor_codes", [])
    if code in valid_codes or code == user.get("two_factor_backup_code", ""):
        session["user_id"] = user["id"]
        session["2fa_verified"] = True
        return jsonify({
            "verified": True,
            "user_id": user["id"],
            "display_name": user["display_name"],
        })
    return jsonify({"verified": False, "error": "Invalid 2FA code"}), 403


# ---------------------------------------------------------------------------
# Share entry (share_by_dropdown)
# ---------------------------------------------------------------------------

@blueprint.route("/api/entries/<entry_id>/share", methods=["POST"])
def api_entry_share(entry_id):
    """Share a password entry with another vault or user."""
    data = request.get_json(silent=True) or {}
    target_vault_id = data.get("target_vault_id", "")
    target_user_email = data.get("target_user_email", "")
    permission = data.get("permission", "read")  # read or write

    entries = _load_entries()
    entry = next((e for e in entries if e["id"] == entry_id), None)
    if not entry:
        abort(404)

    shares = entry.setdefault("shares", [])
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    share_record = {
        "shared_at": now,
        "permission": permission,
    }
    if target_vault_id:
        share_record["target_vault_id"] = target_vault_id
    if target_user_email:
        share_record["target_user_email"] = target_user_email

    shares.append(share_record)
    db.save_collection(SITE, "entries", entries)

    return jsonify({
        "entry_id": entry_id,
        "title": entry["title"],
        "action": "shared",
        "share": share_record,
        "total_shares": len(shares),
    })


# ---------------------------------------------------------------------------
# Export (export_by_dropdown)
# ---------------------------------------------------------------------------

@blueprint.route("/api/export")
def api_export():
    """Export entries as CSV or JSON, optionally filtered by vault/category."""
    fmt = request.args.get("format", "json").lower()
    vault_id = request.args.get("vault_id", "").strip()
    category = request.args.get("category", "").strip()

    entries = _load_entries()
    if vault_id:
        entries = [e for e in entries if e["vault_id"] == vault_id]
    if category:
        entries = [e for e in entries if e.get("category") == category]

    if fmt == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "title", "url", "username", "category",
                         "vault_id", "strength", "favorite", "created_at"])
        for e in entries:
            writer.writerow([
                e.get("id"), e.get("title"), e.get("url"), e.get("username"),
                e.get("category"), e.get("vault_id"), e.get("strength"),
                e.get("favorite"), e.get("created_at"),
            ])
        csv_text = output.getvalue()
        return Response(csv_text, mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=vault_export.csv"})

    return jsonify(entries)


# ---------------------------------------------------------------------------
# Upload icon image (upload_by_image)
# ---------------------------------------------------------------------------

UPLOAD_DIR = SITE_DIR / "static" / "uploads"


@blueprint.route("/api/entries/<entry_id>/icon", methods=["POST"])
def api_entry_upload_icon(entry_id):
    """Upload an icon image for a password entry."""
    entries = _load_entries()
    entry = next((e for e in entries if e["id"] == entry_id), None)
    if not entry:
        abort(404)

    if "icon" not in request.files:
        return jsonify({"error": "No file provided (field name: icon)"}), 400

    f = request.files["icon"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400

    # Ensure upload dir exists
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"):
        return jsonify({"error": "Unsupported image format"}), 400

    filename = f"{entry_id}{ext}"
    filepath = UPLOAD_DIR / filename
    f.save(str(filepath))

    entry["icon_url"] = f"/sites/password-managers/static/uploads/{filename}"
    db.save_collection(SITE, "entries", entries)

    return jsonify({
        "entry_id": entry_id,
        "icon_url": entry["icon_url"],
        "filename": filename,
    })


# ---------------------------------------------------------------------------
# Form-based entry creation (create_by_dropdown — HTML form with vault select)
# ---------------------------------------------------------------------------

@blueprint.route("/entry/<entry_id>/delete", methods=["POST"])
def form_delete_entry(entry_id):
    """Delete a password entry via form POST."""
    entries = _load_entries()
    entry = next((e for e in entries if e["id"] == entry_id), None)
    vault_id = entry["vault_id"] if entry else "vault_001"
    if entry:
        _log_audit("delete_entry", entry, details="Entry deleted")
    entries = [e for e in entries if e["id"] != entry_id]
    db.save_collection(SITE, "entries", entries)
    return redirect(url_for("password-managers.vault_detail", vault_id=vault_id))


@blueprint.route("/import", methods=["POST"])
def form_import():
    """Import passwords from an uploaded CSV/JSON file."""
    _f = request.files.get("file")
    # Accept upload but just redirect back (placeholder)
    return redirect(url_for("password-managers.index"))


@blueprint.route("/new-entry", methods=["GET"])
def new_entry_page():
    """Page with form to create a new entry (vault selected via dropdown)."""
    user = _current_user()
    vaults = _load_vaults()
    return render_template(
        "password-managers/new_entry.html",
        user=user,
        vaults=vaults,
        logged_in=_is_logged_in(),
    )


@blueprint.route("/new-entry", methods=["POST"])
def new_entry_submit():
    """Handle form submission for creating a new entry."""
    entries = _load_entries()

    # Generate ID
    max_num = 0
    for e in entries:
        try:
            num = int(e["id"].split("_")[1])
            if num > max_num:
                max_num = num
        except (IndexError, ValueError):
            pass
    new_id = f"entry_{max_num + 1:03d}"
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    new_entry = {
        "id": new_id,
        "vault_id": request.form.get("vault_id", "vault_001"),
        "title": request.form.get("title", "Untitled"),
        "url": request.form.get("url", ""),
        "username": request.form.get("username", ""),
        "password": request.form.get("password", ""),
        "category": request.form.get("category", "login"),
        "notes": request.form.get("notes", ""),
        "created_at": now,
        "updated_at": now,
        "last_used": now,
        "strength": request.form.get("strength", "strong"),
        "favorite": request.form.get("favorite") == "on",
        "tags": [t.strip() for t in request.form.get("tags", "").split(",") if t.strip()],
    }

    # upload_by_image: optional icon image uploaded with the new entry
    icon = request.files.get("icon")
    if icon and icon.filename:
        ext = os.path.splitext(icon.filename)[1].lower()
        if ext in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"):
            UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            icon.save(str(UPLOAD_DIR / f"{new_id}{ext}"))
            new_entry["icon_url"] = f"/sites/password-managers/static/uploads/{new_id}{ext}"

    entries.append(new_entry)
    db.save_collection(SITE, "entries", entries)
    _log_audit("create_entry", new_entry,
               details=f"Created {new_entry.get('category', 'login')} entry")

    return redirect(url_for("password-managers.entry_detail", entry_id=new_id))


# ---------------------------------------------------------------------------
# Form-based entry edit (edit_by_form)
# ---------------------------------------------------------------------------

@blueprint.route("/entry/<entry_id>/edit", methods=["GET"])
def edit_entry_page(entry_id):
    """Page to edit an existing entry."""
    user = _current_user()
    entries = _load_entries()
    entry = next((e for e in entries if e["id"] == entry_id), None)
    if entry is None:
        abort(404)
    vaults = _load_vaults()
    return render_template(
        "password-managers/edit_entry.html",
        user=user,
        entry=entry,
        vaults=vaults,
        logged_in=_is_logged_in(),
    )


@blueprint.route("/entry/<entry_id>/edit", methods=["POST"])
def edit_entry_submit(entry_id):
    """Handle form submission for editing an entry."""
    entries = _load_entries()
    entry = next((e for e in entries if e["id"] == entry_id), None)
    if entry is None:
        abort(404)

    entry["title"] = request.form.get("title", entry["title"])
    entry["url"] = request.form.get("url", entry["url"])
    entry["username"] = request.form.get("username", entry["username"])
    pw = request.form.get("password", "").strip()
    if pw:
        entry["password"] = pw
    entry["category"] = request.form.get("category", entry["category"])
    entry["notes"] = request.form.get("notes", entry.get("notes", ""))
    entry["favorite"] = request.form.get("favorite") == "on"
    tags_str = request.form.get("tags", "")
    entry["tags"] = [t.strip() for t in tags_str.split(",") if t.strip()]
    entry["updated_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    db.save_collection(SITE, "entries", entries)
    _log_audit("edit_entry", entry,
               details="Entry details updated" + (", password changed" if pw else ""))
    return redirect(url_for("password-managers.entry_detail", entry_id=entry_id))


# ---------------------------------------------------------------------------
# Settings page (configure_by_dropdown)
# ---------------------------------------------------------------------------

@blueprint.route("/settings")
def settings_page():
    """User settings page."""
    user = _current_user()
    return render_template(
        "password-managers/settings.html",
        user=user,
        logged_in=_is_logged_in(),
    )


@blueprint.route("/api/settings", methods=["POST"])
def api_settings_update():
    """Update user settings (auto-lock timeout, default vault, etc.)."""
    data = request.get_json(silent=True) or {}
    users = _load_users()
    uid = session.get("user_id")
    user = next((u for u in users if u["id"] == uid), None)
    if not user:
        return jsonify({"error": "Not logged in"}), 401

    settings = user.setdefault("settings", {})
    for key in ["auto_lock_minutes", "default_vault", "clipboard_clear_seconds",
                "password_length", "theme"]:
        if key in data:
            settings[key] = data[key]

    _save_users(users)
    return jsonify({"updated": True, "settings": settings})


def _save_users(users):
    """Save users back to DB."""
    db.save_collection(SITE, "users", users)


# ---------------------------------------------------------------------------
# API user info
# ---------------------------------------------------------------------------

@blueprint.route("/api/users/<user_id>")
def api_user(user_id):
    """Get user info (no password)."""
    user = db.get_item(SITE, "users", user_id)
    if not user:
        abort(404)
    safe = {k: v for k, v in user.items() if k not in ("master_password", "two_factor_codes", "two_factor_backup_code")}
    return jsonify(safe)

