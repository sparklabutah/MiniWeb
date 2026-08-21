"""SecureBank Online — digital banking portal (Chase / TD / Amex style).

Data is stored in per-site SQLite tables (banking_users, banking_transactions,
etc.) and queried through app.db.  Session mutations are isolated per user.
"""
import pathlib
import random
from datetime import datetime, timedelta

from flask import (
    Blueprint, Response, abort, jsonify, redirect, render_template, request,
    session, url_for,
)
from app import db
from app.events import emit
from helpers.auth import browsing_user, current_user

SITE = "banking"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "banking",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

_ACCOUNT_TYPES = ["checking", "savings", "credit", "loan"]

# ---------------------------------------------------------------------------
# Data loading helpers — thin wrappers around db.query / db.get_item
# ---------------------------------------------------------------------------

def _load_users():
    return db.query(SITE, "users")

def _save_users(users):
    db.save_collection(SITE, "users", users)

def _load_accounts(user_id=None, account_type=None):
    where = {}
    if user_id is not None:
        where["user_id"] = user_id
    if account_type:
        where["type"] = account_type
    return db.query(SITE, "accounts", where=where if where else None)

def _save_accounts(accounts):
    db.save_collection(SITE, "accounts", accounts)

def _load_transactions(user_id=None, account_id=None, limit=None, offset=0):
    where = {}
    if user_id is not None:
        where["user_id"] = user_id
    if account_id is not None:
        where["account_id"] = account_id
    return db.query(SITE, "transactions", where=where if where else None,
                    sort="-date", limit=limit, offset=offset)


def _save_transactions(txns):
    db.save_collection(SITE, "transactions", txns)

def _load_payees(user_id=None):
    where = {"user_id": user_id} if user_id is not None else None
    return db.query(SITE, "payees", where=where)

def _save_payees(payees):
    db.save_collection(SITE, "payees", payees)

def _load_bills(user_id=None):
    where = {"user_id": user_id} if user_id is not None else None
    return db.query(SITE, "bills", where=where)

def _save_bills(bills):
    db.save_collection(SITE, "bills", bills)

def _load_loans(user_id=None):
    where = {"user_id": user_id} if user_id is not None else None
    return db.query(SITE, "loans", where=where)


def _get_user(user_id):
    return db.get_item(SITE, "users", user_id)


def _get_current_user():
    return current_user(_get_user)


def _get_browsing_user():
    return browsing_user(_get_user, fallback=1)




def _dashboard_context(user):
    """Rich summary data for the dashboard. Aggregates are anchored to the
    latest transaction month in the data (site dates are intentionally static)."""
    uid = user["id"]
    accounts = _load_accounts(user_id=uid)
    cc_user = _cc_get_user_for_banking(user)

    deposits = sum(a["balance"] for a in accounts if a.get("type") in ("checking", "savings"))
    loan_debt = sum(abs(a["balance"]) for a in accounts if a.get("type") == "loan")
    cc_bal = (cc_user or {}).get("current_balance", 0) or 0
    total_debt = loan_debt + cc_bal
    net_worth = deposits - total_debt

    latest = db.execute(
        "SELECT MAX(date) FROM banking_transactions WHERE user_id=?", (uid,), fetch="val") or ""
    month = latest[:7]
    like = month + "%"
    month_income = db.execute(
        "SELECT COALESCE(SUM(amount),0) FROM banking_transactions "
        "WHERE user_id=? AND type='credit' AND date LIKE ?", (uid, like), fetch="val") or 0
    month_spending = db.execute(
        "SELECT COALESCE(SUM(amount),0) FROM banking_transactions "
        "WHERE user_id=? AND type='debit' AND category!='Transfer' AND date LIKE ?",
        (uid, like), fetch="val") or 0
    spend_rows = db.execute(
        "SELECT category, SUM(amount) AS tot FROM banking_transactions "
        "WHERE user_id=? AND type='debit' AND category!='Transfer' AND date LIKE ? "
        "GROUP BY category ORDER BY tot DESC LIMIT 6", (uid, like))
    top = max((r["tot"] for r in spend_rows), default=0) or 1
    spending = [{"category": r["category"], "amount": r["tot"],
                 "pct": round(r["tot"] / top * 100)} for r in spend_rows]

    recent = _load_transactions(user_id=uid, limit=8)
    bills = _load_bills(user_id=uid)
    upcoming_bills = sorted(
        [b for b in bills if b.get("status") == "due"],
        key=lambda b: b.get("due_date", ""))[:4]

    try:
        month_label = datetime.strptime(month, "%Y-%m").strftime("%B %Y")
    except (ValueError, TypeError):
        month_label = month

    return dict(
        accounts=accounts, cc_user=cc_user, net_worth=net_worth,
        total_deposits=deposits, total_debt=total_debt,
        month_label=month_label, month_income=month_income,
        month_spending=month_spending, spending=spending,
        recent=recent, upcoming_bills=upcoming_bills)


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():

    user, logged_in = _get_browsing_user()
    return render_template("banking/dashboard.html", user=user,
                           logged_in=logged_in, **_dashboard_context(user))


@blueprint.route("/login", methods=["GET"])
def login_page():

    return render_template("banking/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return render_template("banking/login.html",
                               error="Invalid username or password")
    session["user_id"] = user["id"]
    emit("signup", user_id=user["id"], site_name="banking", username=request.form.get("username", ""), password=request.form.get("password", ""), email="")
    return render_template("banking/dashboard.html", user=user,
                           logged_in=True, **_dashboard_context(user))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("identity_verified", None)
    # Redirect to dashboard (browse-only mode)
    user = _get_user(1)
    return render_template("banking/dashboard.html", user=user,
                           logged_in=False, **_dashboard_context(user))


@blueprint.route("/verify-identity", methods=["GET"])
def verify_identity_page():
    user, logged_in = _get_browsing_user()
    return render_template("banking/verify_identity.html", user=user, result=None,
                           logged_in=logged_in)


@blueprint.route("/verify-identity", methods=["POST"])
def verify_identity_submit():
    user = _get_current_user()
    if not user:
        return render_template("banking/login.html", error="Please log in first")
    code = request.form.get("mfa_code", "").strip()
    if code == user.get("mfa_code"):
        session["identity_verified"] = True
        return render_template("banking/verify_identity.html", user=user,
                               result="success", logged_in=True)
    return render_template("banking/verify_identity.html", user=user,
                           result="failure", logged_in=True)


@blueprint.app_template_filter("mask_account")
def _mask_account_filter(num):
    """Mask an account number (CHK-847291 -> CHK-••••91) unless this session
    completed the 2FA reveal (session["identity_verified"])."""
    s = str(num or "")
    if session.get("identity_verified"):
        return s
    prefix, sep, digits = s.rpartition("-")
    if sep and len(digits) > 2:
        return f"{prefix}-{'•' * (len(digits) - 2)}{digits[-2:]}"
    return ("•" * max(len(s) - 2, 0)) + s[-2:]


@blueprint.route("/accounts/reveal", methods=["POST"])
def accounts_reveal():
    """Reveal full account numbers, gated behind the shared 2FA flow.

    Sends a code to the user's WebMail inbox and redirects to /verify-payment;
    on success the account_reveal event handler sets session["identity_verified"]
    and the user returns to the page they came from, unmasked.
    """
    user = _get_current_user()
    if not user:
        return render_template("banking/login.html", error="Please log in first")
    next_url = request.form.get("next") or url_for("banking.accounts_page")
    if session.get("_disable_2fa"):
        # Annotation mode: request_2fa's disabled path routes to the payment
        # bridge, which is wrong for a reveal — set the flag directly instead.
        session["identity_verified"] = True
        return redirect(next_url)
    from app.events import request_2fa
    verify_url = request_2fa(
        "account_reveal",
        return_url=next_url,
        user_id=user["id"],
        category="Reveal full account numbers",
    )
    return redirect(verify_url)


@blueprint.route("/accounts")
def accounts_page():
    user, logged_in = _get_browsing_user()
    account_type = request.args.get("type", "").strip()
    accounts = _load_accounts(user_id=user["id"], account_type=account_type or None)
    return render_template("banking/accounts.html", user=user, accounts=accounts,
                           account_types=_ACCOUNT_TYPES, selected_type=account_type,
                           logged_in=logged_in)


@blueprint.route("/account/<int:account_id>")
def account_detail(account_id):
    user, logged_in = _get_browsing_user()
    account = db.get_item(SITE, "accounts", account_id)
    if not account:
        abort(404)
    transactions = _load_transactions(account_id=account_id, limit=30)
    return render_template("banking/account_detail.html", user=user,
                           account=account, transactions=transactions,
                           logged_in=logged_in)


@blueprint.route("/transactions")
def transactions_page():
    user, logged_in = _get_browsing_user()
    uid = user["id"]

    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    sort = request.args.get("sort", "date").strip()
    tx_type = request.args.get("type", "").strip()
    min_amount = request.args.get("min_amount", "").strip()
    max_amount = request.args.get("max_amount", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = 30

    # Sort
    sort_map = {
        "date": "[date] DESC",
        "amount_asc": "[amount] ASC",
        "amount_desc": "[amount] DESC",
        "description": "[description] ASC",
    }
    order_sql = sort_map.get(sort, "[date] DESC")

    # Predicate mirroring the filters — merges session-overlay transactions
    # (transfers/payments made this session) into raw SQL/FTS results.
    def _overlay_match(t):
        if t.get("user_id") != uid:
            return False
        if category and t.get("category") != category:
            return False
        if tx_type and t.get("type") != tx_type:
            return False
        if date_from and (t.get("date") or "") < date_from:
            return False
        if date_to and (t.get("date") or "") > date_to:
            return False
        for bound, op in ((min_amount, "ge"), (max_amount, "le")):
            if bound:
                try:
                    b = float(bound)
                    amt = t.get("amount") or 0
                    if (op == "ge" and amt < b) or (op == "le" and amt > b):
                        return False
                except ValueError:
                    pass
        if q:
            text = " ".join(str(t.get(f, ""))
                            for f in ("description", "merchant", "category")).lower()
            if not all(term in text for term in q.lower().split()):
                return False
        return True

    if q:
        # Use FTS for text search, then post-filter
        results = db.search(SITE, "transactions", q,
                            where={"user_id": uid}, limit=500)
        results = db.merge_overlay(SITE, "transactions", results, match=_overlay_match)
        # Apply remaining filters on the small result set
        if category:
            results = [t for t in results if t.get("category") == category]
        if tx_type:
            results = [t for t in results if t.get("type") == tx_type]
        if date_from:
            results = [t for t in results if t.get("date", "") >= date_from]
        if date_to:
            results = [t for t in results if t.get("date", "") <= date_to]
        if min_amount:
            try:
                mn = float(min_amount)
                results = [t for t in results if (t.get("amount") or 0) >= mn]
            except ValueError:
                pass
        if max_amount:
            try:
                mx = float(max_amount)
                results = [t for t in results if (t.get("amount") or 0) <= mx]
            except ValueError:
                pass

        # Sort (FTS returns by relevance; re-sort if needed)
        sort_key_map = {
            "date": (lambda t: t.get("date", ""), True),
            "amount_asc": (lambda t: t.get("amount", 0), False),
            "amount_desc": (lambda t: t.get("amount", 0), True),
            "description": (lambda t: t.get("description", "").lower(), False),
        }
        if sort in sort_key_map:
            key_fn, rev = sort_key_map[sort]
            results.sort(key=key_fn, reverse=rev)

        total_count = len(results)
        total_pages = max(1, (total_count + per_page - 1) // per_page)
        page = max(1, min(page, total_pages))
        offset = (page - 1) * per_page
        txns_page = results[offset:offset + per_page]
    else:
        # Build SQL query with non-search filters
        clauses = ["[user_id] = ?"]
        params = [uid]

        if category:
            clauses.append("[category] = ?")
            params.append(category)
        if tx_type:
            clauses.append("[type] = ?")
            params.append(tx_type)
        if date_from:
            clauses.append("[date] >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("[date] <= ?")
            params.append(date_to)
        if min_amount:
            try:
                mn = float(min_amount)
                clauses.append("[amount] >= ?")
                params.append(mn)
            except ValueError:
                pass
        if max_amount:
            try:
                mx = float(max_amount)
                clauses.append("[amount] <= ?")
                params.append(mx)
            except ValueError:
                pass

        where_sql = " AND ".join(clauses)

        # Count
        total_count = db.execute(
            f"SELECT COUNT(*) FROM [banking_transactions] WHERE {where_sql}",
            tuple(params), fetch="val") or 0
        total_pages = max(1, (total_count + per_page - 1) // per_page)
        page = max(1, min(page, total_pages))
        offset = (page - 1) * per_page

        # Fetch page
        txns_page = db.execute(
            f"SELECT * FROM [banking_transactions] WHERE {where_sql} ORDER BY {order_sql} LIMIT ? OFFSET ?",
            tuple(params) + (per_page, offset))

        # Raw SQL reads the base table only — merge in this session's
        # transactions (transfers/payments) from the overlay.
        overlay_sort = {
            "date": "-date",
            "amount_asc": "amount",
            "amount_desc": "-amount",
            "description": "description",
        }.get(sort, "-date")
        txns_page = db.merge_overlay(SITE, "transactions", txns_page,
                                     match=_overlay_match, sort=overlay_sort,
                                     limit=per_page)

    # Categories for filter dropdown (small query)
    cat_rows = db.execute(
        "SELECT DISTINCT [category] FROM [banking_transactions] WHERE [user_id] = ? ORDER BY [category]",
        (uid,))
    categories = [r["category"] for r in cat_rows]

    return render_template("banking/transactions.html", user=user,
                           transactions=txns_page, categories=categories,
                           q=q, category=category, date_from=date_from,
                           date_to=date_to, sort=sort, tx_type=tx_type,
                           min_amount=min_amount, max_amount=max_amount,
                           logged_in=logged_in, page=page,
                           total_pages=total_pages, total_count=total_count)


@blueprint.route("/transfer", methods=["GET"])
def transfer_page():
    user, logged_in = _get_browsing_user()
    accounts = _load_accounts(user_id=user["id"])
    return render_template("banking/transfer.html", user=user, accounts=accounts,
                           result=None, logged_in=logged_in)


@blueprint.route("/transfer", methods=["POST"])
def transfer_submit():
    user = _get_current_user()
    if not user:
        return render_template("banking/login.html", error="Please log in first")

    from_id = request.form.get("from_account", type=int)
    to_id = request.form.get("to_account", type=int)
    amount = request.form.get("amount", type=float)
    memo = request.form.get("memo", "").strip()

    user_accounts = _load_accounts(user_id=user["id"])
    from_acct = next((a for a in user_accounts if a["id"] == from_id), None)
    to_acct = next((a for a in user_accounts if a["id"] == to_id), None)

    if not from_acct or not to_acct or from_id == to_id:
        return render_template("banking/transfer.html", user=user,
                               accounts=user_accounts, result="error_invalid", logged_in=True)
    if not amount or amount <= 0:
        return render_template("banking/transfer.html", user=user,
                               accounts=user_accounts, result="error_amount", logged_in=True)
    if from_acct["balance"] < amount:
        return render_template("banking/transfer.html", user=user,
                               accounts=user_accounts, result="error_funds", logged_in=True)

    from_acct["balance"] = round(from_acct["balance"] - amount, 2)
    to_acct["balance"] = round(to_acct["balance"] + amount, 2)
    _save_accounts(user_accounts)

    txns = _load_transactions()
    new_id = max(t["id"] for t in txns) + 1 if txns else 1
    today = datetime.now().strftime("%Y-%m-%d")
    txns.insert(0, {
        "id": new_id,
        "account_id": from_id,
        "user_id": user["id"],
        "date": today,
        "description": f"Transfer to {to_acct['account_number']}" + (f" - {memo}" if memo else ""),
        "amount": amount,
        "type": "debit",
        "category": "Transfer",
        "status": "posted",
        "reference": f"TXN{new_id:06d}",
    })
    txns.insert(0, {
        "id": new_id + 1,
        "account_id": to_id,
        "user_id": user["id"],
        "date": today,
        "description": f"Transfer from {from_acct['account_number']}" + (f" - {memo}" if memo else ""),
        "amount": amount,
        "type": "credit",
        "category": "Transfer",
        "status": "posted",
        "reference": f"TXN{new_id + 1:06d}",
    })
    _save_transactions(txns)

    return render_template("banking/transfer.html", user=user,
                           accounts=_load_accounts(user_id=user["id"]),
                           result="success", logged_in=True)


@blueprint.route("/pay-bills")
def pay_bills_page():
    user, logged_in = _get_browsing_user()
    bills = _load_bills(user_id=user["id"])
    all_accounts = _load_accounts(user_id=user["id"])
    accounts = [a for a in all_accounts if a["type"] in ("checking", "savings")]
    return render_template("banking/pay_bills.html", user=user, bills=bills,
                           accounts=accounts, result=None, logged_in=logged_in)


@blueprint.route("/pay-bills", methods=["POST"])
def pay_bill_submit():
    user = _get_current_user()
    if not user:
        return render_template("banking/login.html", error="Please log in first")

    bill_id = request.form.get("bill_id", type=int)
    account_id = request.form.get("account_id", type=int)

    bill = db.get_item(SITE, "bills", bill_id)
    user_bills = _load_bills(user_id=user["id"])
    all_accounts = _load_accounts(user_id=user["id"])
    accounts = [a for a in all_accounts if a["type"] in ("checking", "savings")]

    if not bill:
        return render_template("banking/pay_bills.html", user=user, bills=user_bills,
                               accounts=accounts, result="Bill not found.", logged_in=True)
    if bill["status"] == "paid":
        return render_template("banking/pay_bills.html", user=user, bills=user_bills,
                               accounts=accounts, result="Bill already paid.", logged_in=True)

    # If no account_id provided, find the user's primary checking account
    if not account_id:
        checking_accounts = [a for a in accounts if a["type"] == "checking"]
        if checking_accounts:
            account_id = checking_accounts[0]["id"]

    # Debit the paying account
    if account_id:
        acct = db.get_item(SITE, "accounts", account_id)
        if acct:
            if acct["balance"] < bill["amount"]:
                return render_template("banking/pay_bills.html", user=user, bills=user_bills,
                                       accounts=accounts,
                                       result="Insufficient funds in account.", logged_in=True)
            acct["balance"] = round(acct["balance"] - bill["amount"], 2)
            db.save_item(SITE, "accounts", account_id, acct)

    # Mark bill as paid
    bill["status"] = "paid"
    db.save_item(SITE, "bills", bill_id, bill)

    # Create a transaction record for the debit
    today = datetime.now().strftime("%Y-%m-%d")
    max_id = db.execute(
        "SELECT COALESCE(MAX([id]), 0) FROM [banking_transactions]", (), fetch="val")
    new_id = max_id + 1
    db.save_item(SITE, "transactions", new_id, {
        "id": new_id,
        "account_id": account_id or 0,
        "user_id": bill["user_id"],
        "date": today,
        "description": f"Bill payment - {bill['payee_name']}",
        "amount": bill["amount"],
        "type": "debit",
        "category": "Bills",
        "status": "posted",
        "reference": f"BILL{bill_id:06d}",
    })

    user_bills = _load_bills(user_id=user["id"])
    return render_template("banking/pay_bills.html", user=user, bills=user_bills,
                           accounts=accounts,
                           result=f"Bill to {bill['payee_name']} paid successfully (${bill['amount']:.2f}).",
                           logged_in=True)


@blueprint.route("/payees")
def payees_page():
    user, logged_in = _get_browsing_user()
    payees = _load_payees(user_id=user["id"])
    return render_template("banking/payees.html", user=user, payees=payees,
                           result=None, logged_in=logged_in)


@blueprint.route("/payees/add", methods=["POST"])
def add_payee_submit():
    user = _get_current_user()
    if not user:
        return render_template("banking/login.html", error="Please log in first")

    name = request.form.get("name", "").strip()
    account_number = request.form.get("account_number", "").strip()
    category = request.form.get("category", "").strip() or "Other"
    nickname = request.form.get("nickname", "").strip()

    if not name:
        payees = _load_payees(user_id=user["id"])
        return render_template("banking/payees.html", user=user, payees=payees,
                               result="error", logged_in=True)

    payees = _load_payees()
    new_id = max(p["id"] for p in payees) + 1 if payees else 1
    payee = {
        "id": new_id,
        "user_id": user["id"],
        "name": name,
        "account_number": account_number or f"PAY-{random.randint(10000,99999)}",
        "category": category,
        "nickname": nickname or (name.split()[0] if len(name.split()) > 1 else name[:8]),
    }
    payees.append(payee)
    _save_payees(payees)

    user_payees = [p for p in payees if p["user_id"] == user["id"]]
    return render_template("banking/payees.html", user=user, payees=user_payees,
                           result="added", logged_in=True)


@blueprint.route("/payees/delete", methods=["POST"])
def delete_payee_submit():
    user = _get_current_user()
    if not user:
        return render_template("banking/login.html", error="Please log in first")

    payee_id = request.form.get("payee_id", type=int)
    payees = _load_payees()
    payee = next((p for p in payees if p["id"] == payee_id), None)
    if payee:
        payees = [p for p in payees if p["id"] != payee_id]
        _save_payees(payees)

    user_payees = [p for p in payees if p["user_id"] == user["id"]]
    return render_template("banking/payees.html", user=user, payees=user_payees,
                           result="deleted", logged_in=True)


@blueprint.route("/loans")
def loans_page():
    user, logged_in = _get_browsing_user()
    loans = _load_loans(user_id=user["id"])
    accounts = _load_accounts(user_id=user["id"])
    return render_template("banking/loans.html", user=user, loans=loans,
                           accounts=accounts, result=None, logged_in=logged_in)


@blueprint.route("/loans/pay", methods=["POST"])
def pay_loan_submit():
    user = _get_current_user()
    if not user:
        return render_template("banking/login.html", error="Please log in first")

    loan_id = request.form.get("loan_id", type=int)
    amount = request.form.get("amount", type=float)
    account_id = request.form.get("account_id", type=int)

    loan = db.get_item(SITE, "loans", loan_id)
    if not loan:
        user_loans = _load_loans(user_id=user["id"])
        return render_template("banking/loans.html", user=user, loans=user_loans,
                               result="Loan not found.", logged_in=True)

    if not amount or amount <= 0:
        amount = loan["monthly_payment"]
    # Never debit more than what's left on the loan.
    amount = round(min(amount, loan["remaining_balance"]), 2)

    # If no account_id provided, find the user's primary checking account
    if not account_id:
        checking_accounts = _load_accounts(user_id=user["id"], account_type="checking")
        if checking_accounts:
            account_id = checking_accounts[0]["id"]

    # Debit the paying account
    if account_id:
        acct = db.get_item(SITE, "accounts", account_id)
        if acct:
            if acct["balance"] < amount:
                user_loans = _load_loans(user_id=user["id"])
                accounts = _load_accounts(user_id=user["id"])
                return render_template("banking/loans.html", user=user, loans=user_loans,
                                       accounts=accounts,
                                       result="Insufficient funds in account.", logged_in=True)
            acct["balance"] = round(acct["balance"] - amount, 2)
            db.save_item(SITE, "accounts", account_id, acct)

    # Reduce loan balance
    loan["remaining_balance"] = round(loan["remaining_balance"] - amount, 2)
    if loan["remaining_balance"] <= 0:
        loan["remaining_balance"] = 0
        loan["status"] = "paid_off"
    db.save_item(SITE, "loans", loan_id, loan)

    # Create a transaction record for the debit
    today = datetime.now().strftime("%Y-%m-%d")
    max_id = db.execute(
        "SELECT COALESCE(MAX([id]), 0) FROM [banking_transactions]", (), fetch="val")
    new_id = max_id + 1
    db.save_item(SITE, "transactions", new_id, {
        "id": new_id,
        "account_id": account_id or 0,
        "user_id": user["id"],
        "date": today,
        "description": f"Loan payment - {loan.get('type', 'Loan')} loan #{loan_id}",
        "amount": amount,
        "type": "debit",
        "category": "Loan Payment",
        "status": "posted",
        "reference": f"LOAN{loan_id:06d}",
    })

    user_loans = _load_loans(user_id=user["id"])
    accounts = _load_accounts(user_id=user["id"])
    return render_template("banking/loans.html", user=user, loans=user_loans,
                           accounts=accounts,
                           result=f"Payment of ${amount:.2f} applied. Remaining balance: ${loan['remaining_balance']:.2f}.",
                           logged_in=True)


@blueprint.route("/settings")
def settings_page():
    user, logged_in = _get_browsing_user()
    return render_template("banking/settings.html", user=user, result=None,
                           logged_in=logged_in)


@blueprint.route("/settings", methods=["POST"])
def settings_submit():
    user = _get_current_user()
    if not user:
        return render_template("banking/login.html", error="Please log in first")
    users = _load_users()
    u = next((u for u in users if u["id"] == user["id"]), None)
    if u:
        for field in ("name", "email", "phone", "address"):
            val = request.form.get(field, "").strip()
            if val:
                u[field] = val
        _save_users(users)
    user = _get_user(user["id"])
    return render_template("banking/settings.html", user=user, result="success",
                           logged_in=True)


@blueprint.route("/transactions/delete", methods=["POST"])
def delete_transaction_submit():
    user = _get_current_user()
    if not user:
        return render_template("banking/login.html", error="Please log in first")
    tx_id = request.form.get("tx_id", type=int)
    txns = _load_transactions()
    tx = next((t for t in txns if t["id"] == tx_id), None)
    ref = tx["reference"] if tx else "unknown"
    if tx:
        txns = [t for t in txns if t["id"] != tx_id]
        _save_transactions(txns)
    # Redirect back to transactions page
    return redirect(url_for("banking.transactions_page"))


@blueprint.route("/transactions/flag", methods=["POST"])
def flag_transaction_submit():
    user = _get_current_user()
    if not user:
        return render_template("banking/login.html", error="Please log in first")
    tx_id = request.form.get("tx_id", type=int)
    txns = _load_transactions()
    tx = next((t for t in txns if t["id"] == tx_id), None)
    if tx:
        tx["flagged"] = not tx.get("flagged", False)
        _save_transactions(txns)
    return redirect(url_for("banking.transactions_page"))


@blueprint.route("/bills/configure", methods=["POST"])
def configure_bill_submit():
    user = _get_current_user()
    if not user:
        return render_template("banking/login.html", error="Please log in first")
    bill_id = request.form.get("bill_id", type=int)
    bills = _load_bills()
    bill = next((b for b in bills if b["id"] == bill_id), None)
    if bill:
        due_date = request.form.get("due_date", "").strip()
        auto_pay = request.form.get("auto_pay", "").strip()
        if due_date:
            bill["due_date"] = due_date
        if auto_pay:
            bill["auto_pay"] = auto_pay.lower() in ("true", "yes", "on", "1")
        _save_bills(bills)
    user_bills = _load_bills(user_id=user["id"])
    all_accounts = _load_accounts(user_id=user["id"])
    accounts = [a for a in all_accounts if a["type"] in ("checking", "savings")]
    return render_template("banking/pay_bills.html", user=user, bills=user_bills,
                           accounts=accounts,
                           result=f"Bill #{bill_id} configured successfully." if bill else "Bill not found.",
                           logged_in=True)


# ---------------------------------------------------------------------------
# API routes
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
    return jsonify({"user_id": user["id"], "username": user["username"],
                    "name": user["name"]})


@blueprint.route("/api/verify-identity", methods=["POST"])
def api_verify_identity():
    data = request.get_json(silent=True) or {}
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    code = data.get("mfa_code", "").strip()
    if code == user.get("mfa_code"):
        session["identity_verified"] = True
        return jsonify({"status": "verified", "user_id": user["id"]})
    return jsonify({"status": "failed", "error": "Invalid code"}), 403


@blueprint.route("/api/users/<int:user_id>")
def api_user(user_id):

    user = _get_user(user_id)
    if not user:
        abort(404)
    safe = {k: v for k, v in user.items() if k not in ("password", "mfa_code")}
    return jsonify(safe)


@blueprint.route("/api/accounts")
def api_accounts():
    user_id = request.args.get("user_id", type=int)
    atype = request.args.get("type", "").strip()
    accounts = _load_accounts(user_id=user_id, account_type=atype or None)
    return jsonify(accounts)


@blueprint.route("/api/accounts/<int:account_id>")
def api_account(account_id):
    account = db.get_item(SITE, "accounts", account_id)
    if not account:
        abort(404)
    return jsonify(account)


@blueprint.route("/api/transactions")
def api_transactions():
    user_id = request.args.get("user_id", type=int)
    account_id = request.args.get("account_id", type=int)
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    tx_type = request.args.get("type", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    sort = request.args.get("sort", "date").strip()
    min_amount = request.args.get("min_amount", "").strip()
    max_amount = request.args.get("max_amount", "").strip()
    limit = request.args.get("limit", type=int)

    sort_map = {
        "date": "[date] DESC",
        "amount_asc": "[amount] ASC",
        "amount_desc": "[amount] DESC",
        "description": "[description] ASC",
    }
    order_sql = sort_map.get(sort, "[date] DESC")

    if q:
        # Use FTS for text search, then post-filter
        where_eq = {}
        if user_id:
            where_eq["user_id"] = user_id
        if account_id:
            where_eq["account_id"] = account_id
        if category:
            where_eq["category"] = category
        if tx_type:
            where_eq["type"] = tx_type
        results = db.search(SITE, "transactions", q,
                            where=where_eq if where_eq else None,
                            limit=limit or 500)
        if date_from:
            results = [t for t in results if t.get("date", "") >= date_from]
        if date_to:
            results = [t for t in results if t.get("date", "") <= date_to]
        if min_amount:
            try:
                mn = float(min_amount)
                results = [t for t in results if (t.get("amount") or 0) >= mn]
            except ValueError:
                pass
        if max_amount:
            try:
                mx = float(max_amount)
                results = [t for t in results if (t.get("amount") or 0) <= mx]
            except ValueError:
                pass
        # Re-sort if user asked for non-relevance ordering
        sort_key_map = {
            "date": (lambda t: t.get("date", ""), True),
            "amount_asc": (lambda t: t.get("amount", 0), False),
            "amount_desc": (lambda t: t.get("amount", 0), True),
            "description": (lambda t: t.get("description", "").lower(), False),
        }
        if sort in sort_key_map:
            key_fn, rev = sort_key_map[sort]
            results.sort(key=key_fn, reverse=rev)
        txns = results
    else:
        clauses = []
        params = []
        if user_id:
            clauses.append("[user_id] = ?")
            params.append(user_id)
        if account_id:
            clauses.append("[account_id] = ?")
            params.append(account_id)
        if category:
            clauses.append("[category] = ?")
            params.append(category)
        if tx_type:
            clauses.append("[type] = ?")
            params.append(tx_type)
        if date_from:
            clauses.append("[date] >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("[date] <= ?")
            params.append(date_to)
        if min_amount:
            try:
                mn = float(min_amount)
                clauses.append("[amount] >= ?")
                params.append(mn)
            except ValueError:
                pass
        if max_amount:
            try:
                mx = float(max_amount)
                clauses.append("[amount] <= ?")
                params.append(mx)
            except ValueError:
                pass

        where_sql = " WHERE " + " AND ".join(clauses) if clauses else ""
        limit_sql = f" LIMIT {limit}" if limit else ""
        txns = db.execute(
            f"SELECT * FROM [banking_transactions]{where_sql} ORDER BY {order_sql}{limit_sql}",
            tuple(params))
    return jsonify(txns)


@blueprint.route("/api/transactions/search")
def api_transactions_search():
    q = request.args.get("q", "").strip()
    if q:
        txns = db.search(SITE, "transactions", q, limit=50)
    else:
        txns = _load_transactions(limit=50)
    return jsonify(txns)


@blueprint.route("/api/transactions/semantic")
def api_transactions_semantic():
    q = request.args.get("q", "").strip()
    if q:
        txns = db.search(SITE, "transactions", q, limit=50)
    else:
        txns = _load_transactions(limit=50)
    return jsonify(txns)


@blueprint.route("/api/payees")
def api_payees():
    user_id = request.args.get("user_id", type=int)
    payees = _load_payees(user_id=user_id)
    return jsonify(payees)


@blueprint.route("/api/payees", methods=["POST"])
def api_add_payee():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    name = data.get("name", "").strip()
    if not user_id or not name:
        return jsonify({"error": "user_id and name required"}), 400
    payees = _load_payees()
    new_id = max(p["id"] for p in payees) + 1 if payees else 1
    payee = {
        "id": new_id,
        "user_id": user_id,
        "name": name,
        "account_number": data.get("account_number", f"PAY-{random.randint(10000,99999)}"),
        "category": data.get("category", "Other"),
        "nickname": data.get("nickname", name.split()[0] if name else ""),
    }
    payees.append(payee)
    _save_payees(payees)
    return jsonify(payee), 201


@blueprint.route("/api/payees/<int:payee_id>", methods=["DELETE"])
def api_delete_payee(payee_id):
    payees = _load_payees()
    payee = next((p for p in payees if p["id"] == payee_id), None)
    if not payee:
        abort(404)
    payees = [p for p in payees if p["id"] != payee_id]
    _save_payees(payees)
    return jsonify({"deleted": payee_id})


@blueprint.route("/api/bills")
def api_bills():
    user_id = request.args.get("user_id", type=int)
    status = request.args.get("status", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    clauses = []
    params = []
    if user_id:
        clauses.append("[user_id] = ?")
        params.append(user_id)
    if status:
        clauses.append("[status] = ?")
        params.append(status)
    if date_from:
        clauses.append("[due_date] >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("[due_date] <= ?")
        params.append(date_to)

    where_sql = " WHERE " + " AND ".join(clauses) if clauses else ""
    bills = db.execute(f"SELECT * FROM [banking_bills]{where_sql}", tuple(params))
    return jsonify(bills)


@blueprint.route("/api/bills/<int:bill_id>/pay", methods=["POST"])
def api_pay_bill(bill_id):
    data = request.get_json(silent=True) or {}
    account_id = data.get("account_id")

    bill = db.get_item(SITE, "bills", bill_id)
    if not bill:
        abort(404)
    if bill["status"] == "paid":
        return jsonify({"error": "Bill already paid"}), 400

    # If no account_id provided, find the bill owner's primary checking account
    if not account_id:
        checking_accounts = _load_accounts(user_id=bill["user_id"], account_type="checking")
        if checking_accounts:
            account_id = checking_accounts[0]["id"]

    # Debit the paying account
    if account_id:
        acct = db.get_item(SITE, "accounts", account_id)
        if acct:
            if acct["balance"] < bill["amount"]:
                return jsonify({"error": "Insufficient funds"}), 400
            acct["balance"] = round(acct["balance"] - bill["amount"], 2)
            db.save_item(SITE, "accounts", account_id, acct)

    # Mark bill as paid
    bill["status"] = "paid"
    db.save_item(SITE, "bills", bill_id, bill)

    # Create a transaction record for the debit
    today = datetime.now().strftime("%Y-%m-%d")
    max_id = db.execute(
        "SELECT COALESCE(MAX([id]), 0) FROM [banking_transactions]", (), fetch="val")
    new_id = max_id + 1
    db.save_item(SITE, "transactions", new_id, {
        "id": new_id,
        "account_id": account_id or 0,
        "user_id": bill["user_id"],
        "date": today,
        "description": f"Bill payment - {bill['payee_name']}",
        "amount": bill["amount"],
        "type": "debit",
        "category": "Bills",
        "status": "posted",
        "reference": f"BILL{bill_id:06d}",
    })
    return jsonify({"status": "paid", "bill_id": bill_id, "amount": bill["amount"],
                    "account_id": account_id})


@blueprint.route("/api/transfer", methods=["POST"])
def api_transfer():
    data = request.get_json(silent=True) or {}
    from_id = data.get("from_account_id")
    to_id = data.get("to_account_id")
    amount = data.get("amount")
    memo = data.get("memo", "")

    if not from_id or not to_id or not amount or amount <= 0:
        return jsonify({"error": "Invalid transfer details"}), 400

    accounts = _load_accounts()
    from_acct = next((a for a in accounts if a["id"] == from_id), None)
    to_acct = next((a for a in accounts if a["id"] == to_id), None)
    if not from_acct or not to_acct:
        return jsonify({"error": "Account not found"}), 404
    if from_acct["balance"] < amount:
        return jsonify({"error": "Insufficient funds"}), 400

    from_acct["balance"] = round(from_acct["balance"] - amount, 2)
    to_acct["balance"] = round(to_acct["balance"] + amount, 2)
    _save_accounts(accounts)

    txns = _load_transactions()
    new_id = max(t["id"] for t in txns) + 1 if txns else 1
    today = datetime.now().strftime("%Y-%m-%d")
    txns.insert(0, {
        "id": new_id,
        "account_id": from_id,
        "user_id": from_acct["user_id"],
        "date": today,
        "description": f"Transfer to {to_acct['account_number']}" + (f" - {memo}" if memo else ""),
        "amount": amount,
        "type": "debit",
        "category": "Transfer",
        "status": "posted",
        "reference": f"TXN{new_id:06d}",
    })
    txns.insert(0, {
        "id": new_id + 1,
        "account_id": to_id,
        "user_id": to_acct["user_id"],
        "date": today,
        "description": f"Transfer from {from_acct['account_number']}" + (f" - {memo}" if memo else ""),
        "amount": amount,
        "type": "credit",
        "category": "Transfer",
        "status": "posted",
        "reference": f"TXN{new_id + 1:06d}",
    })
    _save_transactions(txns)

    return jsonify({
        "status": "success",
        "from_balance": from_acct["balance"],
        "to_balance": to_acct["balance"],
        "amount": amount,
    })


@blueprint.route("/api/loans")
def api_loans():
    user_id = request.args.get("user_id", type=int)
    ltype = request.args.get("type", "").strip()
    where = {}
    if user_id:
        where["user_id"] = user_id
    if ltype:
        where["type"] = ltype
    loans = db.query(SITE, "loans", where=where if where else None)
    return jsonify(loans)


@blueprint.route("/api/loans/<int:loan_id>/pay", methods=["POST"])
def api_pay_loan(loan_id):
    data = request.get_json(silent=True) or {}
    amount = data.get("amount")
    account_id = data.get("account_id")

    loan = db.get_item(SITE, "loans", loan_id)
    if not loan:
        abort(404)

    if not amount or amount <= 0:
        amount = loan["monthly_payment"]
    # Never debit more than what's left on the loan.
    amount = round(min(amount, loan["remaining_balance"]), 2)

    # If no account_id provided, find the loan owner's primary checking account
    if not account_id:
        checking_accounts = _load_accounts(user_id=loan["user_id"], account_type="checking")
        if checking_accounts:
            account_id = checking_accounts[0]["id"]

    # Debit the paying account
    if account_id:
        acct = db.get_item(SITE, "accounts", account_id)
        if acct:
            if acct["balance"] < amount:
                return jsonify({"error": "Insufficient funds"}), 400
            acct["balance"] = round(acct["balance"] - amount, 2)
            db.save_item(SITE, "accounts", account_id, acct)

    # Reduce loan balance
    loan["remaining_balance"] = round(loan["remaining_balance"] - amount, 2)
    if loan["remaining_balance"] <= 0:
        loan["remaining_balance"] = 0
        loan["status"] = "paid_off"
    db.save_item(SITE, "loans", loan_id, loan)

    # Create a transaction record for the debit
    today = datetime.now().strftime("%Y-%m-%d")
    max_id = db.execute(
        "SELECT COALESCE(MAX([id]), 0) FROM [banking_transactions]", (), fetch="val")
    new_id = max_id + 1
    db.save_item(SITE, "transactions", new_id, {
        "id": new_id,
        "account_id": account_id or 0,
        "user_id": loan["user_id"],
        "date": today,
        "description": f"Loan payment - {loan.get('type', 'Loan')} loan #{loan_id}",
        "amount": amount,
        "type": "debit",
        "category": "Loan Payment",
        "status": "posted",
        "reference": f"LOAN{loan_id:06d}",
    })

    return jsonify({"status": loan["status"], "remaining_balance": loan["remaining_balance"],
                    "payment_amount": amount, "account_id": account_id})


@blueprint.route("/api/users/<int:user_id>/settings", methods=["PUT"])
def api_update_settings(user_id):
    data = request.get_json(silent=True) or {}
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    for field in ("email", "phone", "address", "name"):
        if field in data:
            user[field] = data[field]
    _save_users(users)
    return jsonify({k: v for k, v in user.items() if k not in ("password", "mfa_code")})


@blueprint.route("/api/users/<int:user_id>/notifications", methods=["POST"])
def api_add_notification(user_id):
    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "message required"}), 400
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    notifs = user.setdefault("notifications", [])
    notifs.append({"message": message, "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                   "read": False})
    _save_users(users)
    return jsonify({"total_notifications": len(notifs)})


@blueprint.route("/api/stats")
def api_stats():
    user_id = request.args.get("user_id", type=int)
    accounts = _load_accounts(user_id=user_id)

    total_balance = sum(a["balance"] for a in accounts)
    by_type = {}
    for a in accounts:
        by_type.setdefault(a["type"], []).append(a["balance"])
    type_totals = {k: round(sum(v), 2) for k, v in by_type.items()}

    # Use SQL aggregation for spending categories
    uid_clause = " AND [user_id] = ?" if user_id else ""
    uid_params = (user_id,) if user_id else ()
    cat_rows = db.execute(
        f"SELECT [category], SUM([amount]) as total FROM [banking_transactions] WHERE [type] = 'debit'{uid_clause} GROUP BY [category] ORDER BY total DESC LIMIT 10",
        ("debit" and uid_params) if not user_id else uid_params)
    # Requery correctly
    if user_id:
        cat_rows = db.execute(
            "SELECT [category], SUM([amount]) as total FROM [banking_transactions] WHERE [type] = 'debit' AND [user_id] = ? GROUP BY [category] ORDER BY total DESC LIMIT 10",
            (user_id,))
    else:
        cat_rows = db.execute(
            "SELECT [category], SUM([amount]) as total FROM [banking_transactions] WHERE [type] = 'debit' GROUP BY [category] ORDER BY total DESC LIMIT 10",
            ())
    top_categories = {r["category"]: round(r["total"], 2) for r in cat_rows}

    total_txns = db.count(SITE, "transactions", where={"user_id": user_id} if user_id else None)

    return jsonify({
        "total_accounts": len(accounts),
        "total_balance": round(total_balance, 2),
        "balance_by_type": type_totals,
        "total_transactions": total_txns,
        "top_spending_categories": top_categories,
    })


@blueprint.route("/api/export")
def api_export():
    fmt = request.args.get("format", "json").lower()
    data_type = request.args.get("type", "transactions").lower()
    user_id = request.args.get("user_id", type=int)

    if data_type == "transactions":
        data = _load_transactions(user_id=user_id)
        if fmt == "csv":
            lines = ["id,account_id,user_id,date,description,amount,type,category,status,reference"]
            for t in data:
                desc = t["description"].replace('"', '""')
                lines.append(f'{t["id"]},{t["account_id"]},{t["user_id"]},"{t["date"]}","{desc}",{t["amount"]},{t["type"]},{t["category"]},{t["status"]},{t["reference"]}')
            return Response("\n".join(lines), mimetype="text/csv",
                            headers={"Content-Disposition": "attachment; filename=transactions.csv"})
        return jsonify(data)

    elif data_type == "accounts":
        data = _load_accounts(user_id=user_id)
        if fmt == "csv":
            lines = ["id,user_id,account_number,type,balance,currency,opened_date,status,interest_rate"]
            for a in data:
                lines.append(f'{a["id"]},{a["user_id"]},"{a["account_number"]}",{a["type"]},{a["balance"]},{a["currency"]},"{a["opened_date"]}",{a["status"]},{a["interest_rate"]}')
            return Response("\n".join(lines), mimetype="text/csv",
                            headers={"Content-Disposition": "attachment; filename=accounts.csv"})
        return jsonify(data)

    return jsonify({"error": "Unknown data type"}), 400


@blueprint.route("/api/bills/<int:bill_id>/configure", methods=["PUT"])
def api_configure_bill(bill_id):
    """Configure auto-pay or schedule for a bill."""
    data = request.get_json(silent=True) or {}
    bills = _load_bills()
    bill = next((b for b in bills if b["id"] == bill_id), None)
    if not bill:
        abort(404)
    if "auto_pay" in data:
        bill["auto_pay"] = data["auto_pay"]
    if "due_date" in data:
        bill["due_date"] = data["due_date"]
    _save_bills(bills)
    return jsonify(bill)


@blueprint.route("/api/transactions/<int:tx_id>", methods=["DELETE"])
def api_delete_transaction(tx_id):
    txns = _load_transactions()
    tx = next((t for t in txns if t["id"] == tx_id), None)
    if not tx:
        abort(404)
    txns = [t for t in txns if t["id"] != tx_id]
    _save_transactions(txns)
    return jsonify({"deleted": tx_id})


@blueprint.route("/api/transactions/<int:tx_id>/select", methods=["POST"])
def api_select_transaction(tx_id):
    """Mark a transaction as selected/flagged for review."""
    txns = _load_transactions()
    tx = next((t for t in txns if t["id"] == tx_id), None)
    if not tx:
        abort(404)
    tx["flagged"] = not tx.get("flagged", False)
    _save_transactions(txns)
    return jsonify({"id": tx_id, "flagged": tx["flagged"]})


# ===========================================================================
# Credit Card section — merged from credit-card site
# ===========================================================================

CC_REWARDS_RATES = {
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

# ---------------------------------------------------------------------------
# Credit card data helpers
# ---------------------------------------------------------------------------

def _cc_load_users():
    return db.query(SITE, "cc_users")

def _cc_load_transactions(user_id=None, limit=None, sort="-date"):
    where = {"user_id": user_id} if user_id is not None else None
    return db.query(SITE, "cc_transactions", where=where, sort=sort, limit=limit)

def _cc_load_statements(user_id=None):
    where = {"user_id": user_id} if user_id is not None else None
    return db.query(SITE, "cc_statements", where=where)

def _cc_load_payments(user_id=None):
    where = {"user_id": user_id} if user_id is not None else None
    return db.query(SITE, "cc_payments", where=where)

def _cc_get_user_for_banking(banking_user):
    """Find a credit card user that corresponds to the banking user."""
    cc_user = db.get_item(SITE, "cc_users", banking_user["id"])
    if cc_user:
        return cc_user
    cc_users = db.query(SITE, "cc_users", limit=1)
    return cc_users[0] if cc_users else None

def _cc_calculate_rewards_earned(transactions, user_id):
    """Calculate total rewards points earned from CC transactions for a user."""
    user_txns = [t for t in transactions if t["user_id"] == user_id and t["status"] == "posted"]
    total = 0
    by_category = {}
    for t in user_txns:
        rate = CC_REWARDS_RATES.get(t["category"], 1)
        pts = int(t["amount"] * rate)
        total += pts
        by_category[t["category"]] = by_category.get(t["category"], 0) + pts
    return total, by_category

def _cc_spending_by_category(transactions, user_id):
    """Aggregate spending by category for a CC user."""
    user_txns = [t for t in transactions if t["user_id"] == user_id]
    cats = {}
    for t in user_txns:
        cats[t["category"]] = cats.get(t["category"], 0) + t["amount"]
    return dict(sorted(cats.items(), key=lambda x: -x[1]))


# ---------------------------------------------------------------------------
# Credit card HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/credit-card")
def cc_index():
    user, logged_in = _get_browsing_user()
    cc_user = _cc_get_user_for_banking(user)
    if not cc_user:
        abort(404)
    user_txns = _cc_load_transactions(user_id=cc_user["id"], limit=5, sort="-date")
    statements = _cc_load_statements(user_id=cc_user["id"])
    statements.sort(key=lambda s: s.get("period", ""), reverse=True)
    latest_stmt = statements[0] if statements else None
    recent_payments = _cc_load_payments(user_id=cc_user["id"])
    recent_payments.sort(key=lambda p: p.get("date", ""), reverse=True)
    recent_payments = recent_payments[:3]
    cc_txns_for_spending = _cc_load_transactions(user_id=cc_user["id"])
    spending = _cc_spending_by_category(cc_txns_for_spending, cc_user["id"])
    return render_template("banking/cc_index.html", user=user, cc_user=cc_user,
                           recent_transactions=user_txns,
                           latest_statement=latest_stmt,
                           recent_payments=recent_payments,
                           spending=spending, logged_in=logged_in)


@blueprint.route("/credit-card/transactions")
def cc_transactions():
    user, logged_in = _get_browsing_user()
    cc_user = _cc_get_user_for_banking(user)
    if not cc_user:
        abort(404)
    uid = cc_user["id"]

    category = request.args.get("category", "").strip()
    status = request.args.get("status", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    search = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = 20

    if search:
        # Use FTS for text search, then post-filter
        where_eq = {"user_id": uid}
        if category:
            where_eq["category"] = category
        if status:
            where_eq["status"] = status
        results = db.search(SITE, "cc_transactions", search,
                            where=where_eq, limit=500)
        if date_from:
            results = [t for t in results if t.get("date", "") >= date_from]
        if date_to:
            results = [t for t in results if t.get("date", "") <= date_to]
        # Sort by date desc
        results.sort(key=lambda t: t.get("date", ""), reverse=True)

        total_count = len(results)
        total_amount = sum(t.get("amount", 0) for t in results)
        total_pages = max(1, (total_count + per_page - 1) // per_page)
        page = max(1, min(page, total_pages))
        offset = (page - 1) * per_page
        page_txns = results[offset:offset + per_page]
    else:
        clauses = ["[user_id] = ?"]
        params = [uid]
        if category:
            clauses.append("[category] = ?")
            params.append(category)
        if status:
            clauses.append("[status] = ?")
            params.append(status)
        if date_from:
            clauses.append("[date] >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("[date] <= ?")
            params.append(date_to)

        where_sql = " AND ".join(clauses)
        total_count = db.execute(
            f"SELECT COUNT(*) FROM [banking_cc_transactions] WHERE {where_sql}",
            tuple(params), fetch="val") or 0
        total_amount_val = db.execute(
            f"SELECT COALESCE(SUM([amount]), 0) FROM [banking_cc_transactions] WHERE {where_sql}",
            tuple(params), fetch="val") or 0
        total_amount = total_amount_val

        total_pages = max(1, (total_count + per_page - 1) // per_page)
        page = max(1, min(page, total_pages))
        offset = (page - 1) * per_page
        page_txns = db.execute(
            f"SELECT * FROM [banking_cc_transactions] WHERE {where_sql} ORDER BY [date] DESC LIMIT ? OFFSET ?",
            tuple(params) + (per_page, offset))

    cat_rows = db.execute(
        "SELECT DISTINCT [category] FROM [banking_cc_transactions] WHERE [user_id] = ? ORDER BY [category]",
        (uid,))
    categories = [r["category"] for r in cat_rows]
    return render_template("banking/cc_transactions.html", user=user, cc_user=cc_user,
                           transactions=page_txns, categories=categories,
                           category=category, status=status,
                           date_from=date_from, date_to=date_to, q=search,
                           page=page, total_pages=total_pages,
                           total_count=total_count, total_amount=total_amount,
                           logged_in=logged_in)


@blueprint.route("/credit-card/statements")
def cc_statements():
    user, logged_in = _get_browsing_user()
    cc_user = _cc_get_user_for_banking(user)
    if not cc_user:
        abort(404)
    user_stmts = _cc_load_statements(user_id=cc_user["id"])
    user_stmts.sort(key=lambda s: s.get("period", ""), reverse=True)
    return render_template("banking/cc_statements.html", user=user, cc_user=cc_user,
                           statements=user_stmts, logged_in=logged_in)


@blueprint.route("/credit-card/payments")
def cc_payments():
    user, logged_in = _get_browsing_user()
    cc_user = _cc_get_user_for_banking(user)
    if not cc_user:
        abort(404)
    user_payments = _cc_load_payments(user_id=cc_user["id"])
    user_payments.sort(key=lambda p: p.get("date", ""), reverse=True)
    return render_template("banking/cc_payments.html", user=user, cc_user=cc_user,
                           payments=user_payments, logged_in=logged_in)


@blueprint.route("/credit-card/rewards")
def cc_rewards():
    user, logged_in = _get_browsing_user()
    cc_user = _cc_get_user_for_banking(user)
    if not cc_user:
        abort(404)
    user_cc_txns = _cc_load_transactions(user_id=cc_user["id"])
    total_earned, by_category = _cc_calculate_rewards_earned(user_cc_txns, cc_user["id"])
    return render_template("banking/cc_rewards.html", user=user, cc_user=cc_user,
                           total_earned=total_earned, by_category=by_category,
                           rewards_rates=CC_REWARDS_RATES, logged_in=logged_in)


@blueprint.route("/credit-card/settings")
def cc_settings():
    user, logged_in = _get_browsing_user()
    cc_user = _cc_get_user_for_banking(user)
    if not cc_user:
        abort(404)
    return render_template("banking/cc_settings.html", user=user, cc_user=cc_user,
                           logged_in=logged_in)


# ---------------------------------------------------------------------------
# Credit card form mutation routes
# ---------------------------------------------------------------------------

@blueprint.route("/credit-card/payment/make", methods=["POST"])
def cc_form_make_payment():
    user = _get_current_user()
    if not user:
        return render_template("banking/login.html", error="Please log in first")
    cc_user = _cc_get_user_for_banking(user)
    if not cc_user:
        abort(404)

    payments = _cc_load_payments()
    new_id = max((p["id"] for p in payments), default=0) + 1
    amount = float(request.form.get("amount", 0))
    payment = {
        "id": new_id,
        "user_id": cc_user["id"],
        "date": request.form.get("date", datetime.now().strftime("%Y-%m-%d")),
        "amount": amount,
        "method": request.form.get("method", "bank_transfer"),
        "bank_name": request.form.get("bank_name", ""),
        "status": "completed",
        "confirmation": f"PMT-{datetime.now().strftime('%Y%m%d')}-{new_id:03d}",
    }
    payments.append(payment)
    db.save_collection(SITE, "cc_payments", payments)

    # Update CC user balance
    cc_users = _cc_load_users()
    u = next((u for u in cc_users if u["id"] == cc_user["id"]), None)
    if u:
        u["current_balance"] = round(u["current_balance"] - amount, 2)
        u["available_credit"] = round(u["credit_limit"] - u["current_balance"], 2)
        db.save_collection(SITE, "cc_users", cc_users)

    return redirect(url_for("banking.cc_payments"))


@blueprint.route("/credit-card/transaction/<int:txn_id>/dispute", methods=["POST"])
def cc_form_dispute_transaction(txn_id):
    user = _get_current_user()
    if not user:
        return render_template("banking/login.html", error="Please log in first")

    transactions = _cc_load_transactions()
    txn = next((t for t in transactions if t["id"] == txn_id), None)
    if not txn:
        abort(404)
    txn["disputed"] = not txn.get("disputed", False)
    db.save_collection(SITE, "cc_transactions", transactions)
    return redirect(url_for("banking.cc_transactions"))


@blueprint.route("/credit-card/settings/update", methods=["POST"])
def cc_form_update_settings():
    user = _get_current_user()
    if not user:
        return render_template("banking/login.html", error="Please log in first")
    cc_user = _cc_get_user_for_banking(user)
    if not cc_user:
        abort(404)

    cc_users = _cc_load_users()
    u = next((u for u in cc_users if u["id"] == cc_user["id"]), None)
    if not u:
        abort(404)
    if "email" in request.form:
        u["email"] = request.form["email"].strip()
    if "autopay_enabled" in request.form:
        u["autopay_enabled"] = request.form["autopay_enabled"] == "true"
    if "card_frozen" in request.form:
        u["card_frozen"] = request.form["card_frozen"] == "true"
    db.save_collection(SITE, "cc_users", cc_users)
    return redirect(url_for("banking.cc_settings"))


# ---------------------------------------------------------------------------
# Credit card API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/credit-card/transactions")
def api_cc_transactions():
    uid = request.args.get("user_id", type=int)
    category = request.args.get("category", "").strip()
    status = request.args.get("status", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    merchant = request.args.get("merchant", "").strip()
    disputed = request.args.get("disputed", "").strip()
    sort = request.args.get("sort", "date_desc").strip()

    sort_map = {
        "date_asc": "[date] ASC",
        "date_desc": "[date] DESC",
        "amount_asc": "[amount] ASC",
        "amount_desc": "[amount] DESC",
        "merchant": "[merchant] ASC",
    }
    order_sql = sort_map.get(sort, "[date] DESC")

    if merchant:
        # Use FTS for merchant text search, then post-filter
        where_eq = {}
        if uid:
            where_eq["user_id"] = uid
        if category:
            where_eq["category"] = category
        if status:
            where_eq["status"] = status
        results = db.search(SITE, "cc_transactions", merchant,
                            where=where_eq if where_eq else None,
                            limit=500)
        if date_from:
            results = [t for t in results if t.get("date", "") >= date_from]
        if date_to:
            results = [t for t in results if t.get("date", "") <= date_to]
        # Re-sort
        sort_key_map = {
            "date_asc": (lambda t: t.get("date", ""), False),
            "date_desc": (lambda t: t.get("date", ""), True),
            "amount_asc": (lambda t: t.get("amount", 0), False),
            "amount_desc": (lambda t: t.get("amount", 0), True),
            "merchant": (lambda t: t.get("merchant", "").lower(), False),
        }
        if sort in sort_key_map:
            key_fn, rev = sort_key_map[sort]
            results.sort(key=key_fn, reverse=rev)
    else:
        clauses = []
        params = []
        if uid:
            clauses.append("[user_id] = ?")
            params.append(uid)
        if category:
            clauses.append("[category] = ?")
            params.append(category)
        if status:
            clauses.append("[status] = ?")
            params.append(status)
        if date_from:
            clauses.append("[date] >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("[date] <= ?")
            params.append(date_to)

        where_sql = " WHERE " + " AND ".join(clauses) if clauses else ""
        results = db.execute(
            f"SELECT * FROM [banking_cc_transactions]{where_sql} ORDER BY {order_sql}",
            tuple(params))
    return jsonify(results)


@blueprint.route("/api/credit-card/transactions/<int:txn_id>/dispute", methods=["POST"])
def api_cc_dispute_transaction(txn_id):
    transactions = _cc_load_transactions()
    txn = next((t for t in transactions if t["id"] == txn_id), None)
    if not txn:
        return jsonify({"error": "Transaction not found"}), 404
    txn["disputed"] = not txn.get("disputed", False)
    db.save_collection(SITE, "cc_transactions", transactions)
    action = "disputed" if txn["disputed"] else "undisputed"
    return jsonify({"action": action, "transaction_id": txn_id, "disputed": txn["disputed"]})


@blueprint.route("/api/credit-card/statements")
def api_cc_statements():
    uid = request.args.get("user_id", type=int)
    period = request.args.get("period", "").strip()
    where = {}
    if uid:
        where["user_id"] = uid
    if period:
        where["period"] = period
    results = db.query(SITE, "cc_statements", where=where if where else None, sort="-period")
    return jsonify(results)


@blueprint.route("/api/credit-card/payments", methods=["GET"])
def api_cc_payments_list():
    uid = request.args.get("user_id", type=int)
    status = request.args.get("status", "").strip()
    where = {}
    if uid:
        where["user_id"] = uid
    if status:
        where["status"] = status
    results = db.query(SITE, "cc_payments", where=where if where else None, sort="-date")
    return jsonify(results)


@blueprint.route("/api/credit-card/payments", methods=["POST"])
def api_cc_make_payment():
    data = request.get_json(silent=True) or {}
    uid = data.get("user_id")
    amount = data.get("amount")
    if not uid or not amount:
        return jsonify({"error": "user_id and amount required"}), 400
    amount = float(amount)
    payments = _cc_load_payments()
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
    db.save_collection(SITE, "cc_payments", payments)

    # Update user balance
    cc_users = _cc_load_users()
    user = next((u for u in cc_users if u["id"] == uid), None)
    if user:
        user["current_balance"] = round(user["current_balance"] - amount, 2)
        user["available_credit"] = round(user["credit_limit"] - user["current_balance"], 2)
        db.save_collection(SITE, "cc_users", cc_users)
    return jsonify(payment), 201


@blueprint.route("/api/credit-card/rewards")
def api_cc_rewards():
    uid = request.args.get("user_id", type=int)
    if not uid:
        return jsonify({"error": "user_id required"}), 400
    cc_user = db.get_item(SITE, "cc_users", uid)
    if not cc_user:
        return jsonify({"error": "User not found"}), 404
    user_txns = _cc_load_transactions(user_id=uid)
    total_earned, by_category = _cc_calculate_rewards_earned(user_txns, uid)
    return jsonify({
        "user_id": uid,
        "current_points": cc_user.get("rewards_points", 0),
        "total_earned_from_transactions": total_earned,
        "by_category": by_category,
        "rates": CC_REWARDS_RATES,
    })


@blueprint.route("/api/credit-card/rewards/redeem", methods=["POST"])
def api_cc_redeem_rewards():
    data = request.get_json(silent=True) or {}
    uid = data.get("user_id")
    points = data.get("points")
    if not uid or not points:
        return jsonify({"error": "user_id and points required"}), 400
    points = int(points)
    cc_users = _cc_load_users()
    cc_user = next((u for u in cc_users if u["id"] == uid), None)
    if not cc_user:
        return jsonify({"error": "User not found"}), 404
    if points > cc_user.get("rewards_points", 0):
        return jsonify({"error": "Insufficient points"}), 400
    cc_user["rewards_points"] -= points
    credit_amount = round(points / 100, 2)  # 100 points = $1
    cc_user["current_balance"] = round(cc_user["current_balance"] - credit_amount, 2)
    cc_user["available_credit"] = round(cc_user["credit_limit"] - cc_user["current_balance"], 2)
    db.save_collection(SITE, "cc_users", cc_users)
    return jsonify({
        "action": "redeemed",
        "points_redeemed": points,
        "credit_amount": credit_amount,
        "remaining_points": cc_user["rewards_points"],
    })


@blueprint.route("/api/credit-card/spending")
def api_cc_spending():
    uid = request.args.get("user_id", type=int)
    if not uid:
        return jsonify({"error": "user_id required"}), 400
    user_txns = _cc_load_transactions(user_id=uid)
    spending = _cc_spending_by_category(user_txns, uid)
    total = sum(spending.values())
    return jsonify({
        "user_id": uid,
        "total": round(total, 2),
        "by_category": spending,
    })


@blueprint.route("/api/credit-card/stats")
def api_cc_stats():
    total_txns = db.count(SITE, "cc_transactions")
    total_spend = db.execute(
        "SELECT COALESCE(SUM([amount]), 0) FROM [banking_cc_transactions]", (), fetch="val") or 0
    total_users = db.count(SITE, "cc_users")
    cat_rows = db.execute(
        "SELECT [category], SUM([amount]) as total FROM [banking_cc_transactions] GROUP BY [category] ORDER BY total DESC",
        ())
    categories = {r["category"]: round(r["total"], 2) for r in cat_rows}
    return jsonify({
        "total_transactions": total_txns,
        "total_spend": round(total_spend, 2),
        "total_users": total_users,
        "disputed_transactions": 0,
        "spending_by_category": categories,
    })


@blueprint.route("/api/credit-card/settings", methods=["GET"])
def api_cc_get_settings():
    uid = request.args.get("user_id", type=int)
    if not uid:
        return jsonify({"error": "user_id required"}), 400
    cc_user = db.get_item(SITE, "cc_users", uid)
    if not cc_user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({
        "user_id": uid,
        "email": cc_user.get("email", ""),
        "autopay_enabled": cc_user.get("autopay_enabled", False),
        "card_frozen": cc_user.get("card_frozen", False),
    })


@blueprint.route("/api/credit-card/settings", methods=["POST"])
def api_cc_update_settings():
    data = request.get_json(silent=True) or {}
    uid = data.get("user_id")
    if not uid:
        return jsonify({"error": "user_id required"}), 400
    cc_users = _cc_load_users()
    cc_user = next((u for u in cc_users if u["id"] == uid), None)
    if not cc_user:
        return jsonify({"error": "User not found"}), 404
    changed = []
    if "email" in data:
        cc_user["email"] = data["email"].strip()
        changed.append("email")
    if "autopay_enabled" in data:
        cc_user["autopay_enabled"] = bool(data["autopay_enabled"])
        changed.append("autopay_enabled")
    if "card_frozen" in data:
        cc_user["card_frozen"] = bool(data["card_frozen"])
        changed.append("card_frozen")
    db.save_collection(SITE, "cc_users", cc_users)
    return jsonify({"action": "updated", "fields": changed, "user_id": uid})
