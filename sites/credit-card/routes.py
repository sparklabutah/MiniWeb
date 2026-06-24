"""Credit Card Portal -- Chase/Capital One-style credit card management.

Data interpreter: reads JSON data files, respects config/config.json settings.
"""
import json
import pathlib
from datetime import datetime

from flask import Blueprint, abort, jsonify, redirect, render_template, request, session, url_for

SITE_DIR = pathlib.Path(__file__).resolve().parent
CONFIG_FILE = SITE_DIR / "config" / "config.json"
USERS_FILE = SITE_DIR / "data" / "users.json"
TRANSACTIONS_FILE = SITE_DIR / "data" / "transactions.json"
STATEMENTS_FILE = SITE_DIR / "data" / "statements.json"
PAYMENTS_FILE = SITE_DIR / "data" / "payments.json"

REWARDS_RATES = {
    "Dining": 3,
    "Travel": 5,
    "Gas": 2,
    "Groceries": 3,
    "Entertainment": 2,
    "Shopping": 1,
    "Electronics": 1,
    "Healthcare": 1,
    "Transportation": 1,
    "Home": 1,
    "Utilities": 1,
    "Auto": 1,
}

blueprint = Blueprint(
    "credit-card",
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
# Data loading
# ---------------------------------------------------------------------------

def _load_json(filepath):
    if filepath.exists():
        return json.loads(filepath.read_text())
    return []

def _save_json(filepath, data):
    filepath.write_text(json.dumps(data, indent=2))

# Cached data
_users = None
_transactions = None
_statements = None
_payments = None

def _ensure_loaded():
    global _users, _transactions, _statements, _payments
    if _users is None:
        _users = _load_json(USERS_FILE)
        _transactions = _load_json(TRANSACTIONS_FILE)
        _statements = _load_json(STATEMENTS_FILE)
        _payments = _load_json(PAYMENTS_FILE)

def _get_users():
    _ensure_loaded()
    return _users

def _get_transactions():
    _ensure_loaded()
    return _transactions

def _get_statements():
    _ensure_loaded()
    return _statements

def _get_payments():
    _ensure_loaded()
    return _payments

def _reload_users():
    global _users
    _users = _load_json(USERS_FILE)
    return _users

def _reload_transactions():
    global _transactions
    _transactions = _load_json(TRANSACTIONS_FILE)
    return _transactions

def _reload_payments():
    global _payments
    _payments = _load_json(PAYMENTS_FILE)
    return _payments

# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

def _current_user():
    if "user_id" in session:
        users = _get_users()
        return next((u for u in users if u["id"] == session["user_id"]), None)
    return None

def _get_user(user_id):
    users = _get_users()
    return next((u for u in users if u["id"] == user_id), None)

# ---------------------------------------------------------------------------
# Rewards helpers
# ---------------------------------------------------------------------------

def _calculate_rewards_earned(transactions, user_id):
    """Calculate total rewards points earned from transactions for a user."""
    user_txns = [t for t in transactions if t["user_id"] == user_id and t["status"] == "posted"]
    total = 0
    by_category = {}
    for t in user_txns:
        rate = REWARDS_RATES.get(t["category"], 1)
        pts = int(t["amount"] * rate)
        total += pts
        by_category[t["category"]] = by_category.get(t["category"], 0) + pts
    return total, by_category

def _spending_by_category(transactions, user_id):
    """Aggregate spending by category for a user."""
    user_txns = [t for t in transactions if t["user_id"] == user_id]
    cats = {}
    for t in user_txns:
        cats[t["category"]] = cats.get(t["category"], 0) + t["amount"]
    return dict(sorted(cats.items(), key=lambda x: -x[1]))

# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    user = _current_user()
    if not user:
        return render_template("credit-card/login.html", error=None, show_login_prompt=True,
                               users=_load_users(), show_api_links=True)
    transactions = _get_transactions()
    user_txns = sorted(
        [t for t in transactions if t["user_id"] == user["id"]],
        key=lambda t: t["date"], reverse=True
    )[:5]
    statements = _get_statements()
    latest_stmt = next(
        (s for s in sorted(
            [s for s in statements if s["user_id"] == user["id"]],
            key=lambda s: s["period"], reverse=True
        )),
        None
    )
    payments = _get_payments()
    recent_payments = sorted(
        [p for p in payments if p["user_id"] == user["id"]],
        key=lambda p: p["date"], reverse=True
    )[:3]
    spending = _spending_by_category(transactions, user["id"])
    return render_template("credit-card/index.html", user=user,
                           recent_transactions=user_txns,
                           latest_statement=latest_stmt,
                           recent_payments=recent_payments,
                           spending=spending)


@blueprint.route("/transactions")
def transactions_page():
    user = _current_user()
    if not user:
        return render_template("credit-card/login.html", error=None, show_login_prompt=True)
    transactions = _get_transactions()
    user_txns = [t for t in transactions if t["user_id"] == user["id"]]
    # Filters
    category = request.args.get("category", "").strip()
    status = request.args.get("status", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    search = request.args.get("q", "").strip()
    if category:
        user_txns = [t for t in user_txns if t["category"] == category]
    if status:
        user_txns = [t for t in user_txns if t["status"] == status]
    if date_from:
        user_txns = [t for t in user_txns if t["date"] >= date_from]
    if date_to:
        user_txns = [t for t in user_txns if t["date"] <= date_to]
    if search:
        sl = search.lower()
        user_txns = [t for t in user_txns if sl in t["merchant"].lower() or sl in t["category"].lower()]
    user_txns.sort(key=lambda t: t["date"], reverse=True)
    total_count = len(user_txns)
    total_amount = sum(t["amount"] for t in user_txns)

    # Pagination: 20 per page
    page = request.args.get("page", 1, type=int)
    per_page = 20
    total_pages = max(1, (total_count + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    end = start + per_page
    page_txns = user_txns[start:end]

    categories = sorted(set(t["category"] for t in _get_transactions() if t["user_id"] == user["id"]))
    return render_template("credit-card/transactions.html", user=user,
                           transactions=page_txns, categories=categories,
                           category=category, status=status,
                           date_from=date_from, date_to=date_to, q=search,
                           page=page, total_pages=total_pages,
                           total_count=total_count, total_amount=total_amount)


@blueprint.route("/statements")
def statements_page():
    user = _current_user()
    if not user:
        return render_template("credit-card/login.html", error=None, show_login_prompt=True)
    statements = _get_statements()
    user_stmts = sorted(
        [s for s in statements if s["user_id"] == user["id"]],
        key=lambda s: s["period"], reverse=True
    )
    return render_template("credit-card/statements.html", user=user,
                           statements=user_stmts)


@blueprint.route("/payments")
def payments_page():
    user = _current_user()
    if not user:
        return render_template("credit-card/login.html", error=None, show_login_prompt=True)
    payments = _get_payments()
    user_payments = sorted(
        [p for p in payments if p["user_id"] == user["id"]],
        key=lambda p: p["date"], reverse=True
    )
    return render_template("credit-card/payments.html", user=user,
                           payments=user_payments)


@blueprint.route("/rewards")
def rewards_page():
    user = _current_user()
    if not user:
        return render_template("credit-card/login.html", error=None, show_login_prompt=True)
    transactions = _get_transactions()
    total_earned, by_category = _calculate_rewards_earned(transactions, user["id"])
    return render_template("credit-card/rewards.html", user=user,
                           total_earned=total_earned, by_category=by_category,
                           rewards_rates=REWARDS_RATES)


@blueprint.route("/settings")
def settings_page():
    user = _current_user()
    if not user:
        return render_template("credit-card/login.html", error=None, show_login_prompt=True)
    return render_template("credit-card/settings.html", user=user)


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("credit-card/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _get_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return render_template("credit-card/login.html", error="Invalid username or password")
    session["user_id"] = user["id"]
    return redirect(url_for("credit-card.index"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("credit-card.login_page"))


# ---------------------------------------------------------------------------
# Form mutation routes
# ---------------------------------------------------------------------------

@blueprint.route("/payment/make", methods=["POST"])
def form_make_payment():
    if "user_id" not in session:
        return render_template("credit-card/login.html", error=None, show_login_prompt=True)
    payments = _load_json(PAYMENTS_FILE)
    new_id = max((p["id"] for p in payments), default=0) + 1
    amount = float(request.form.get("amount", 0))
    payment = {
        "id": new_id,
        "user_id": session["user_id"],
        "date": request.form.get("date", datetime.now().strftime("%Y-%m-%d")),
        "amount": amount,
        "method": request.form.get("method", "bank_transfer"),
        "bank_name": request.form.get("bank_name", ""),
        "status": "completed",
        "confirmation": f"PMT-{datetime.now().strftime('%Y%m%d')}-{new_id:03d}",
    }
    payments.append(payment)
    _save_json(PAYMENTS_FILE, payments)
    _reload_payments()
    # Update user balance
    users = _load_json(USERS_FILE)
    user = next((u for u in users if u["id"] == session["user_id"]), None)
    if user:
        user["current_balance"] = round(user["current_balance"] - amount, 2)
        user["available_credit"] = round(user["credit_limit"] - user["current_balance"], 2)
        _save_json(USERS_FILE, users)
        _reload_users()
    return redirect(url_for("credit-card.payments_page"))


@blueprint.route("/transaction/<int:txn_id>/dispute", methods=["POST"])
def form_dispute_transaction(txn_id):
    if "user_id" not in session:
        return render_template("credit-card/login.html", error=None, show_login_prompt=True)
    transactions = _load_json(TRANSACTIONS_FILE)
    txn = next((t for t in transactions if t["id"] == txn_id), None)
    if not txn or txn["user_id"] != session["user_id"]:
        abort(404)
    txn["disputed"] = not txn["disputed"]
    _save_json(TRANSACTIONS_FILE, transactions)
    _reload_transactions()
    return redirect(url_for("credit-card.transactions_page"))


@blueprint.route("/settings/update", methods=["POST"])
def form_update_settings():
    if "user_id" not in session:
        return render_template("credit-card/login.html", error=None, show_login_prompt=True)
    users = _load_json(USERS_FILE)
    user = next((u for u in users if u["id"] == session["user_id"]), None)
    if not user:
        abort(404)
    if "email" in request.form:
        user["email"] = request.form["email"].strip()
    if "autopay_enabled" in request.form:
        user["autopay_enabled"] = request.form["autopay_enabled"] == "true"
    if "card_frozen" in request.form:
        user["card_frozen"] = request.form["card_frozen"] == "true"
    _save_json(USERS_FILE, users)
    _reload_users()
    return redirect(url_for("credit-card.settings_page"))


# ---------------------------------------------------------------------------
# API routes  (no session required -- return 401 JSON when user_id missing)
# ---------------------------------------------------------------------------

@blueprint.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    users = _get_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return jsonify({"error": "Invalid credentials"}), 401
    session["user_id"] = user["id"]
    return jsonify({"user_id": user["id"], "username": user["username"], "name": user["name"]})


@blueprint.route("/api/accounts/<int:uid>")
def api_account(uid):
    user = _get_user(uid)
    if not user:
        return jsonify({"error": "User not found"}), 404
    safe = {k: v for k, v in user.items() if k != "password"}
    return jsonify(safe)


@blueprint.route("/api/transactions")
def api_transactions():
    transactions = _get_transactions()
    uid = request.args.get("user_id", type=int)
    category = request.args.get("category", "").strip()
    status = request.args.get("status", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    merchant = request.args.get("merchant", "").strip()
    disputed = request.args.get("disputed", "").strip()
    sort = request.args.get("sort", "date_desc").strip()
    results = list(transactions)
    if uid:
        results = [t for t in results if t["user_id"] == uid]
    if category:
        results = [t for t in results if t["category"] == category]
    if status:
        results = [t for t in results if t["status"] == status]
    if date_from:
        results = [t for t in results if t["date"] >= date_from]
    if date_to:
        results = [t for t in results if t["date"] <= date_to]
    if merchant:
        ml = merchant.lower()
        results = [t for t in results if ml in t["merchant"].lower()]
    if disputed == "true":
        results = [t for t in results if t["disputed"]]
    elif disputed == "false":
        results = [t for t in results if not t["disputed"]]
    if sort == "date_asc":
        results.sort(key=lambda t: t["date"])
    elif sort == "date_desc":
        results.sort(key=lambda t: t["date"], reverse=True)
    elif sort == "amount_asc":
        results.sort(key=lambda t: t["amount"])
    elif sort == "amount_desc":
        results.sort(key=lambda t: t["amount"], reverse=True)
    elif sort == "merchant":
        results.sort(key=lambda t: t["merchant"].lower())
    return jsonify(results)


@blueprint.route("/api/transactions/<int:txn_id>")
def api_transaction(txn_id):
    transactions = _get_transactions()
    txn = next((t for t in transactions if t["id"] == txn_id), None)
    if not txn:
        return jsonify({"error": "Transaction not found"}), 404
    return jsonify(txn)


@blueprint.route("/api/transactions/<int:txn_id>/dispute", methods=["POST"])
def api_dispute_transaction(txn_id):
    transactions = _load_json(TRANSACTIONS_FILE)
    txn = next((t for t in transactions if t["id"] == txn_id), None)
    if not txn:
        return jsonify({"error": "Transaction not found"}), 404
    txn["disputed"] = not txn["disputed"]
    _save_json(TRANSACTIONS_FILE, transactions)
    _reload_transactions()
    action = "disputed" if txn["disputed"] else "undisputed"
    return jsonify({"action": action, "transaction_id": txn_id, "disputed": txn["disputed"]})


@blueprint.route("/api/statements")
def api_statements():
    statements = _get_statements()
    uid = request.args.get("user_id", type=int)
    period = request.args.get("period", "").strip()
    results = list(statements)
    if uid:
        results = [s for s in results if s["user_id"] == uid]
    if period:
        results = [s for s in results if s["period"] == period]
    results.sort(key=lambda s: s["period"], reverse=True)
    return jsonify(results)


@blueprint.route("/api/statements/<int:stmt_id>")
def api_statement(stmt_id):
    statements = _get_statements()
    stmt = next((s for s in statements if s["id"] == stmt_id), None)
    if not stmt:
        return jsonify({"error": "Statement not found"}), 404
    return jsonify(stmt)


@blueprint.route("/api/payments", methods=["GET"])
def api_payments_list():
    payments = _get_payments()
    uid = request.args.get("user_id", type=int)
    status = request.args.get("status", "").strip()
    results = list(payments)
    if uid:
        results = [p for p in results if p["user_id"] == uid]
    if status:
        results = [p for p in results if p["status"] == status]
    results.sort(key=lambda p: p["date"], reverse=True)
    return jsonify(results)


@blueprint.route("/api/payments", methods=["POST"])
def api_make_payment():
    data = request.get_json(silent=True) or {}
    uid = data.get("user_id")
    amount = data.get("amount")
    if not uid or not amount:
        return jsonify({"error": "user_id and amount required"}), 400
    amount = float(amount)
    payments = _load_json(PAYMENTS_FILE)
    new_id = max((p["id"] for p in payments), default=0) + 1
    payment = {
        "id": new_id,
        "user_id": uid,
        "date": data.get("date", datetime.now().strftime("%Y-%m-%d")),
        "amount": amount,
        "method": data.get("method", "bank_transfer"),
        "bank_name": data.get("bank_name", ""),
        "status": "completed",
        "confirmation": f"PMT-{datetime.now().strftime('%Y%m%d')}-{new_id:03d}",
    }
    payments.append(payment)
    _save_json(PAYMENTS_FILE, payments)
    _reload_payments()
    # Update user balance
    users = _load_json(USERS_FILE)
    user = next((u for u in users if u["id"] == uid), None)
    if user:
        user["current_balance"] = round(user["current_balance"] - amount, 2)
        user["available_credit"] = round(user["credit_limit"] - user["current_balance"], 2)
        _save_json(USERS_FILE, users)
        _reload_users()
    return jsonify(payment), 201


@blueprint.route("/api/rewards")
def api_rewards():
    uid = request.args.get("user_id", type=int)
    if not uid:
        return jsonify({"error": "user_id required"}), 400
    user = _get_user(uid)
    if not user:
        return jsonify({"error": "User not found"}), 404
    transactions = _get_transactions()
    total_earned, by_category = _calculate_rewards_earned(transactions, uid)
    return jsonify({
        "user_id": uid,
        "current_points": user["rewards_points"],
        "total_earned_from_transactions": total_earned,
        "by_category": by_category,
        "rates": REWARDS_RATES,
    })


@blueprint.route("/api/rewards/redeem", methods=["POST"])
def api_redeem_rewards():
    data = request.get_json(silent=True) or {}
    uid = data.get("user_id")
    points = data.get("points")
    if not uid or not points:
        return jsonify({"error": "user_id and points required"}), 400
    points = int(points)
    users = _load_json(USERS_FILE)
    user = next((u for u in users if u["id"] == uid), None)
    if not user:
        return jsonify({"error": "User not found"}), 404
    if points > user["rewards_points"]:
        return jsonify({"error": "Insufficient points"}), 400
    user["rewards_points"] -= points
    credit_amount = round(points / 100, 2)  # 100 points = $1
    user["current_balance"] = round(user["current_balance"] - credit_amount, 2)
    user["available_credit"] = round(user["credit_limit"] - user["current_balance"], 2)
    _save_json(USERS_FILE, users)
    _reload_users()
    return jsonify({
        "action": "redeemed",
        "points_redeemed": points,
        "credit_amount": credit_amount,
        "remaining_points": user["rewards_points"],
    })


@blueprint.route("/api/settings", methods=["GET"])
def api_get_settings():
    """GET settings for a user by user_id query param."""
    uid = request.args.get("user_id", type=int)
    if not uid:
        return jsonify({"error": "user_id required"}), 400
    user = _get_user(uid)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({
        "user_id": uid,
        "email": user["email"],
        "autopay_enabled": user["autopay_enabled"],
        "card_frozen": user["card_frozen"],
    })


@blueprint.route("/api/settings", methods=["POST"])
def api_update_settings():
    data = request.get_json(silent=True) or {}
    uid = data.get("user_id")
    if not uid:
        return jsonify({"error": "user_id required"}), 400
    users = _load_json(USERS_FILE)
    user = next((u for u in users if u["id"] == uid), None)
    if not user:
        return jsonify({"error": "User not found"}), 404
    changed = []
    if "email" in data:
        user["email"] = data["email"].strip()
        changed.append("email")
    if "autopay_enabled" in data:
        user["autopay_enabled"] = bool(data["autopay_enabled"])
        changed.append("autopay_enabled")
    if "card_frozen" in data:
        user["card_frozen"] = bool(data["card_frozen"])
        changed.append("card_frozen")
    _save_json(USERS_FILE, users)
    _reload_users()
    return jsonify({"action": "updated", "fields": changed, "user_id": uid})


@blueprint.route("/api/spending")
def api_spending():
    uid = request.args.get("user_id", type=int)
    if not uid:
        return jsonify({"error": "user_id required"}), 400
    transactions = _get_transactions()
    spending = _spending_by_category(transactions, uid)
    total = sum(spending.values())
    return jsonify({
        "user_id": uid,
        "total": round(total, 2),
        "by_category": spending,
    })


@blueprint.route("/api/stats")
def api_stats():
    transactions = _get_transactions()
    users = _get_users()
    total_txns = len(transactions)
    total_spend = sum(t["amount"] for t in transactions)
    disputed_count = sum(1 for t in transactions if t["disputed"])
    categories = {}
    for t in transactions:
        categories[t["category"]] = categories.get(t["category"], 0) + t["amount"]
    return jsonify({
        "total_transactions": total_txns,
        "total_spend": round(total_spend, 2),
        "total_users": len(users),
        "disputed_transactions": disputed_count,
        "spending_by_category": dict(sorted(categories.items(), key=lambda x: -x[1])),
    })
