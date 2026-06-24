"""SecureBank Online — digital banking portal (Chase / TD / Amex style).

Synthesises realistic banking data (users, accounts, transactions, payees,
bills, loans) and serves through Flask routes.  Data files live under data/
and are reset from data/.pristine/ between evaluation runs.
"""
import json
import pathlib
import random
import re
from datetime import datetime, timedelta
from collections import Counter

from flask import (
    Blueprint, Response, abort, jsonify, redirect, render_template, request,
    session, url_for,
)

SITE_DIR = pathlib.Path(__file__).resolve().parent
CONFIG_FILE = SITE_DIR / "config" / "config.json"
DATA_DIR = SITE_DIR / "data"
USERS_FILE = DATA_DIR / "users.json"
ACCOUNTS_FILE = DATA_DIR / "accounts.json"
TRANSACTIONS_FILE = DATA_DIR / "transactions.json"
PAYEES_FILE = DATA_DIR / "payees.json"
BILLS_FILE = DATA_DIR / "bills.json"
LOANS_FILE = DATA_DIR / "loans.json"

blueprint = Blueprint(
    "banking",
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
# Synthesised data generation (runs once, writes JSON to data/)
# ---------------------------------------------------------------------------

_FIRST_NAMES = [
    "James", "Maria", "Robert", "Linda", "Michael", "Patricia",
    "David", "Jennifer", "William", "Elizabeth", "Richard", "Susan",
    "Joseph", "Jessica", "Thomas", "Sarah", "Charles", "Karen",
    "Daniel", "Nancy",
]
_LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia",
    "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez",
    "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore",
    "Jackson", "Martin",
]
_MERCHANTS = [
    "Amazon", "Walmart", "Target", "Costco", "Whole Foods", "Shell Gas",
    "Chevron", "Starbucks", "McDonald's", "Uber", "Lyft", "Netflix",
    "Spotify", "Apple", "AT&T", "Verizon", "Home Depot", "Lowe's",
    "CVS Pharmacy", "Walgreens", "Best Buy", "Trader Joe's",
    "Safeway", "Kroger", "Publix", "Chick-fil-A", "Chipotle",
    "DoorDash", "Grubhub", "Delta Airlines",
]
_BILL_COMPANIES = [
    "City Power & Light", "Metro Water Authority", "National Gas Co",
    "Comcast Internet", "AT&T Wireless", "State Farm Insurance",
    "Blue Cross Health", "Capital One Credit", "Student Loan Corp",
    "HOA Management LLC", "City Parking Authority", "Green Energy Solar",
]
_ACCOUNT_TYPES = ["checking", "savings", "credit", "loan"]
_TX_CATEGORIES = [
    "Groceries", "Dining", "Transportation", "Entertainment", "Shopping",
    "Utilities", "Healthcare", "Education", "Travel", "Subscriptions",
    "Gas", "Insurance", "Rent", "Transfer", "Deposit", "ATM Withdrawal",
]
_LOAN_TYPES = ["mortgage", "auto", "personal", "student"]


def _synthesize_data():
    """Generate all banking data deterministically from config seed."""
    config = _load_config()
    seed = config.get("random_seed", 42)
    n = config.get("num_data_points", 200)
    rng = random.Random(seed)

    # --- Users (5 bank customers) ---
    users = []
    for i in range(1, 6):
        first = _FIRST_NAMES[(i - 1) % len(_FIRST_NAMES)]
        last = _LAST_NAMES[(i - 1) % len(_LAST_NAMES)]
        users.append({
            "id": i,
            "username": f"{first.lower()}_{last.lower()}",
            "password": f"secure{i * 111}",
            "name": f"{first} {last}",
            "email": f"{first.lower()}.{last.lower()}@email.com",
            "phone": f"({rng.randint(200,999)}) {rng.randint(200,999)}-{rng.randint(1000,9999)}",
            "address": f"{rng.randint(100,9999)} {rng.choice(['Oak','Maple','Cedar','Pine','Elm'])} {rng.choice(['St','Ave','Blvd','Dr','Ln'])}, {rng.choice(['Springfield','Portland','Austin','Denver','Seattle'])}, {rng.choice(['IL','OR','TX','CO','WA'])} {rng.randint(10000,99999)}",
            "mfa_code": f"{rng.randint(100000, 999999)}",
            "notifications": [],
        })

    # --- Accounts (2-3 per user) ---
    accounts = []
    acct_id = 1
    for user in users:
        n_accts = rng.randint(2, 3)
        types_for_user = rng.sample(_ACCOUNT_TYPES, n_accts)
        for atype in types_for_user:
            if atype == "checking":
                balance = round(rng.uniform(500, 25000), 2)
                acct_num = f"CHK-{rng.randint(100000,999999)}"
            elif atype == "savings":
                balance = round(rng.uniform(1000, 100000), 2)
                acct_num = f"SAV-{rng.randint(100000,999999)}"
            elif atype == "credit":
                balance = round(rng.uniform(-5000, 0), 2)  # negative = owed
                acct_num = f"CC-{rng.randint(1000,9999)}-{rng.randint(1000,9999)}"
            else:  # loan
                balance = round(rng.uniform(-200000, -5000), 2)
                acct_num = f"LN-{rng.randint(100000,999999)}"

            accounts.append({
                "id": acct_id,
                "user_id": user["id"],
                "account_number": acct_num,
                "type": atype,
                "balance": balance,
                "currency": "USD",
                "opened_date": f"{rng.randint(2015,2023)}-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}",
                "status": "active",
                "interest_rate": round(rng.uniform(0.01, 0.05), 4) if atype == "savings" else (round(rng.uniform(0.15, 0.25), 4) if atype == "credit" else (round(rng.uniform(0.03, 0.08), 4) if atype == "loan" else 0.0)),
            })
            acct_id += 1

    # --- Transactions (n total, spread across accounts) ---
    transactions = []
    base_date = datetime(2026, 6, 1)
    for tx_id in range(1, n + 1):
        acct = rng.choice(accounts)
        days_ago = rng.randint(0, 180)
        tx_date = base_date - timedelta(days=days_ago)
        is_credit_acct = acct["type"] == "credit"
        is_deposit = rng.random() < 0.25

        if is_deposit and not is_credit_acct:
            amount = round(rng.uniform(50, 5000), 2)
            merchant = rng.choice(["Direct Deposit", "Payroll", "Refund", "Cash Deposit", "ACH Transfer"])
            tx_type = "credit"
            category = rng.choice(["Deposit", "Transfer"])
        else:
            amount = round(rng.uniform(2, 500), 2)
            merchant = rng.choice(_MERCHANTS)
            tx_type = "debit"
            category = rng.choice(_TX_CATEGORIES[:13])

        transactions.append({
            "id": tx_id,
            "account_id": acct["id"],
            "user_id": acct["user_id"],
            "date": tx_date.strftime("%Y-%m-%d"),
            "description": merchant,
            "amount": amount,
            "type": tx_type,
            "category": category,
            "status": rng.choice(["posted", "posted", "posted", "pending"]),
            "reference": f"TXN{tx_id:06d}",
        })

    transactions.sort(key=lambda t: t["date"], reverse=True)
    for i, t in enumerate(transactions, 1):
        t["id"] = i

    # --- Payees ---
    payees = []
    payee_id = 1
    for user in users:
        n_payees = rng.randint(3, 6)
        chosen = rng.sample(_BILL_COMPANIES + _MERCHANTS[:10], n_payees)
        for name in chosen:
            payees.append({
                "id": payee_id,
                "user_id": user["id"],
                "name": name,
                "account_number": f"PAY-{rng.randint(10000,99999)}",
                "category": rng.choice(["Utility", "Insurance", "Credit Card", "Subscription", "Rent", "Other"]),
                "nickname": name.split()[0] if len(name.split()) > 1 else name[:8],
            })
            payee_id += 1

    # --- Bills ---
    bills = []
    bill_id = 1
    for user in users:
        user_payees = [p for p in payees if p["user_id"] == user["id"]]
        for payee in user_payees[:4]:
            due_day = rng.randint(1, 28)
            amount = round(rng.uniform(25, 500), 2)
            for month_offset in range(3):
                due_date = datetime(2026, 6 - month_offset, due_day)
                bills.append({
                    "id": bill_id,
                    "user_id": user["id"],
                    "payee_id": payee["id"],
                    "payee_name": payee["name"],
                    "amount": amount + round(rng.uniform(-20, 20), 2),
                    "due_date": due_date.strftime("%Y-%m-%d"),
                    "status": "paid" if month_offset > 0 else rng.choice(["due", "due", "overdue"]),
                    "category": payee["category"],
                    "auto_pay": rng.choice([True, False]),
                })
                bill_id += 1

    # --- Loans ---
    loans = []
    loan_id = 1
    for user in users:
        n_loans = rng.randint(0, 2)
        for _ in range(n_loans):
            ltype = rng.choice(_LOAN_TYPES)
            principal = round(rng.uniform(5000, 350000), 2) if ltype == "mortgage" else round(rng.uniform(2000, 50000), 2)
            rate = round(rng.uniform(0.03, 0.09), 4)
            term_months = rng.choice([36, 48, 60, 120, 180, 360])
            remaining = round(principal * rng.uniform(0.2, 0.95), 2)
            monthly = round(principal * (rate / 12) / (1 - (1 + rate / 12) ** -term_months), 2)
            loans.append({
                "id": loan_id,
                "user_id": user["id"],
                "type": ltype,
                "original_amount": principal,
                "remaining_balance": remaining,
                "interest_rate": rate,
                "term_months": term_months,
                "monthly_payment": monthly,
                "next_payment_date": f"2026-07-{rng.randint(1,28):02d}",
                "status": "active",
                "start_date": f"{rng.randint(2018,2024)}-{rng.randint(1,12):02d}-01",
            })
            loan_id += 1

    return users, accounts, transactions, payees, bills, loans


def _write_data(users, accounts, transactions, payees, bills, loans):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    pristine = DATA_DIR / ".pristine"
    pristine.mkdir(parents=True, exist_ok=True)

    for fname, data in [
        ("users.json", users),
        ("accounts.json", accounts),
        ("transactions.json", transactions),
        ("payees.json", payees),
        ("bills.json", bills),
        ("loans.json", loans),
    ]:
        content = json.dumps(data, indent=2)
        (DATA_DIR / fname).write_text(content)
        (pristine / fname).write_text(content)


def _maybe_generate():
    """Generate data if not already present."""
    if not USERS_FILE.exists():
        users, accounts, transactions, payees, bills, loans = _synthesize_data()
        _write_data(users, accounts, transactions, payees, bills, loans)


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def _load_json(path):
    _maybe_generate()
    return json.loads(path.read_text())

def _save_json(path, data):
    path.write_text(json.dumps(data, indent=2))

def _load_users():
    return _load_json(USERS_FILE)

def _save_users(users):
    _save_json(USERS_FILE, users)

def _load_accounts():
    return _load_json(ACCOUNTS_FILE)

def _save_accounts(accounts):
    _save_json(ACCOUNTS_FILE, accounts)

def _load_transactions():
    return _load_json(TRANSACTIONS_FILE)

def _save_transactions(txns):
    _save_json(TRANSACTIONS_FILE, txns)

def _load_payees():
    return _load_json(PAYEES_FILE)

def _save_payees(payees):
    _save_json(PAYEES_FILE, payees)

def _load_bills():
    return _load_json(BILLS_FILE)

def _save_bills(bills):
    _save_json(BILLS_FILE, bills)

def _load_loans():
    return _load_json(LOANS_FILE)


def _get_user(user_id):
    users = _load_users()
    return next((u for u in users if u["id"] == user_id), None)


def _get_current_user():
    if "user_id" in session:
        return _get_user(session["user_id"])
    return None


def _get_browsing_user():
    """Return the logged-in user, or fall back to user 1 for browse-only mode."""
    user = _get_current_user()
    if user:
        return user, True
    # Default to user 1 for unauthenticated browsing
    return _get_user(1), False


def _keyword_score(query, text):
    terms = query.lower().split()
    text_l = text.lower()
    return sum(1 for t in terms if t in text_l)


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    _maybe_generate()
    user, logged_in = _get_browsing_user()
    accounts = [a for a in _load_accounts() if a["user_id"] == user["id"]]
    return render_template("banking/dashboard.html", user=user, accounts=accounts,
                           logged_in=logged_in)


@blueprint.route("/login", methods=["GET"])
def login_page():
    _maybe_generate()
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
    accounts = [a for a in _load_accounts() if a["user_id"] == user["id"]]
    return render_template("banking/dashboard.html", user=user, accounts=accounts,
                           logged_in=True)


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("identity_verified", None)
    # Redirect to dashboard (browse-only mode)
    user = _get_user(1)
    accounts = [a for a in _load_accounts() if a["user_id"] == user["id"]]
    return render_template("banking/dashboard.html", user=user, accounts=accounts,
                           logged_in=False)


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


@blueprint.route("/accounts")
def accounts_page():
    user, logged_in = _get_browsing_user()
    accounts = [a for a in _load_accounts() if a["user_id"] == user["id"]]
    account_type = request.args.get("type", "").strip()
    if account_type:
        accounts = [a for a in accounts if a["type"] == account_type]
    return render_template("banking/accounts.html", user=user, accounts=accounts,
                           account_types=_ACCOUNT_TYPES, selected_type=account_type,
                           logged_in=logged_in)


@blueprint.route("/account/<int:account_id>")
def account_detail(account_id):
    user, logged_in = _get_browsing_user()
    accounts = _load_accounts()
    account = next((a for a in accounts if a["id"] == account_id and a["user_id"] == user["id"]), None)
    if not account:
        # Also try finding the account without user restriction for browse mode
        account = next((a for a in accounts if a["id"] == account_id), None)
    if not account:
        abort(404)
    transactions = [t for t in _load_transactions() if t["account_id"] == account_id]
    transactions = transactions[:30]  # Paginate: first 30
    return render_template("banking/account_detail.html", user=user,
                           account=account, transactions=transactions,
                           logged_in=logged_in)


@blueprint.route("/transactions")
def transactions_page():
    user, logged_in = _get_browsing_user()
    txns = [t for t in _load_transactions() if t["user_id"] == user["id"]]

    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    sort = request.args.get("sort", "date").strip()
    tx_type = request.args.get("type", "").strip()
    min_amount = request.args.get("min_amount", "").strip()
    max_amount = request.args.get("max_amount", "").strip()
    page = request.args.get("page", 1, type=int)

    if q:
        txns = [t for t in txns if q.lower() in t["description"].lower() or
                q.lower() in t["category"].lower() or
                q.lower() in t["reference"].lower()]
    if category:
        txns = [t for t in txns if t["category"] == category]
    if tx_type:
        txns = [t for t in txns if t["type"] == tx_type]
    if date_from:
        txns = [t for t in txns if t["date"] >= date_from]
    if date_to:
        txns = [t for t in txns if t["date"] <= date_to]
    if min_amount:
        try:
            mn = float(min_amount)
            txns = [t for t in txns if t["amount"] >= mn]
        except ValueError:
            pass
    if max_amount:
        try:
            mx = float(max_amount)
            txns = [t for t in txns if t["amount"] <= mx]
        except ValueError:
            pass

    if sort == "date":
        txns.sort(key=lambda t: t["date"], reverse=True)
    elif sort == "amount_asc":
        txns.sort(key=lambda t: t["amount"])
    elif sort == "amount_desc":
        txns.sort(key=lambda t: t["amount"], reverse=True)
    elif sort == "description":
        txns.sort(key=lambda t: t["description"].lower())

    categories = sorted(set(t["category"] for t in _load_transactions() if t["user_id"] == user["id"]))

    # Pagination: 30 per page
    total_count = len(txns)
    per_page = 30
    total_pages = max(1, (total_count + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    txns_page = txns[(page - 1) * per_page : page * per_page]

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
    accounts = [a for a in _load_accounts() if a["user_id"] == user["id"]]
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

    accounts = _load_accounts()
    from_acct = next((a for a in accounts if a["id"] == from_id and a["user_id"] == user["id"]), None)
    to_acct = next((a for a in accounts if a["id"] == to_id and a["user_id"] == user["id"]), None)

    user_accounts = [a for a in accounts if a["user_id"] == user["id"]]

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
    _save_accounts(accounts)

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
                           accounts=[a for a in _load_accounts() if a["user_id"] == user["id"]],
                           result="success", logged_in=True)


@blueprint.route("/pay-bills")
def pay_bills_page():
    user, logged_in = _get_browsing_user()
    bills = [b for b in _load_bills() if b["user_id"] == user["id"]]
    accounts = [a for a in _load_accounts() if a["user_id"] == user["id"] and a["type"] in ("checking", "savings")]
    return render_template("banking/pay_bills.html", user=user, bills=bills,
                           accounts=accounts, result=None, logged_in=logged_in)


@blueprint.route("/pay-bills", methods=["POST"])
def pay_bill_submit():
    user = _get_current_user()
    if not user:
        return render_template("banking/login.html", error="Please log in first")

    bill_id = request.form.get("bill_id", type=int)
    account_id = request.form.get("account_id", type=int)

    bills = _load_bills()
    bill = next((b for b in bills if b["id"] == bill_id), None)
    user_bills = [b for b in bills if b["user_id"] == user["id"]]
    accounts = [a for a in _load_accounts() if a["user_id"] == user["id"] and a["type"] in ("checking", "savings")]

    if not bill:
        return render_template("banking/pay_bills.html", user=user, bills=user_bills,
                               accounts=accounts, result="Bill not found.", logged_in=True)
    if bill["status"] == "paid":
        return render_template("banking/pay_bills.html", user=user, bills=user_bills,
                               accounts=accounts, result="Bill already paid.", logged_in=True)

    if account_id:
        accts = _load_accounts()
        acct = next((a for a in accts if a["id"] == account_id), None)
        if acct:
            acct["balance"] = round(acct["balance"] - bill["amount"], 2)
            _save_accounts(accts)

    bill["status"] = "paid"
    _save_bills(bills)

    txns = _load_transactions()
    new_id = max(t["id"] for t in txns) + 1 if txns else 1
    txns.insert(0, {
        "id": new_id,
        "account_id": account_id or 0,
        "user_id": bill["user_id"],
        "date": datetime.now().strftime("%Y-%m-%d"),
        "description": f"Bill payment - {bill['payee_name']}",
        "amount": bill["amount"],
        "type": "debit",
        "category": "Bills",
        "status": "posted",
        "reference": f"BILL{bill_id:06d}",
    })
    _save_transactions(txns)

    user_bills = [b for b in _load_bills() if b["user_id"] == user["id"]]
    return render_template("banking/pay_bills.html", user=user, bills=user_bills,
                           accounts=accounts,
                           result=f"Bill to {bill['payee_name']} paid successfully (${bill['amount']:.2f}).",
                           logged_in=True)


@blueprint.route("/payees")
def payees_page():
    user, logged_in = _get_browsing_user()
    payees = [p for p in _load_payees() if p["user_id"] == user["id"]]
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
        payees = [p for p in _load_payees() if p["user_id"] == user["id"]]
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
    loans = [l for l in _load_loans() if l["user_id"] == user["id"]]
    return render_template("banking/loans.html", user=user, loans=loans,
                           result=None, logged_in=logged_in)


@blueprint.route("/loans/pay", methods=["POST"])
def pay_loan_submit():
    user = _get_current_user()
    if not user:
        return render_template("banking/login.html", error="Please log in first")

    loan_id = request.form.get("loan_id", type=int)
    amount = request.form.get("amount", type=float)
    account_id = request.form.get("account_id", type=int)

    loans = _load_loans()
    loan = next((l for l in loans if l["id"] == loan_id), None)
    if not loan:
        user_loans = [l for l in loans if l["user_id"] == user["id"]]
        return render_template("banking/loans.html", user=user, loans=user_loans,
                               result="Loan not found.", logged_in=True)

    if not amount or amount <= 0:
        amount = loan["monthly_payment"]

    loan["remaining_balance"] = round(loan["remaining_balance"] - amount, 2)
    if loan["remaining_balance"] <= 0:
        loan["remaining_balance"] = 0
        loan["status"] = "paid_off"
    _save_json(LOANS_FILE, loans)

    if account_id:
        accounts = _load_accounts()
        acct = next((a for a in accounts if a["id"] == account_id), None)
        if acct:
            acct["balance"] = round(acct["balance"] - amount, 2)
            _save_accounts(accounts)

    user_loans = [l for l in _load_loans() if l["user_id"] == user["id"]]
    return render_template("banking/loans.html", user=user, loans=user_loans,
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
    user_bills = [b for b in _load_bills() if b["user_id"] == user["id"]]
    accounts = [a for a in _load_accounts() if a["user_id"] == user["id"] and a["type"] in ("checking", "savings")]
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
    _maybe_generate()
    user = _get_user(user_id)
    if not user:
        abort(404)
    safe = {k: v for k, v in user.items() if k not in ("password", "mfa_code")}
    return jsonify(safe)


@blueprint.route("/api/accounts")
def api_accounts():
    _maybe_generate()
    accounts = _load_accounts()
    user_id = request.args.get("user_id", type=int)
    atype = request.args.get("type", "").strip()
    if user_id:
        accounts = [a for a in accounts if a["user_id"] == user_id]
    if atype:
        accounts = [a for a in accounts if a["type"] == atype]
    return jsonify(accounts)


@blueprint.route("/api/accounts/<int:account_id>")
def api_account(account_id):
    _maybe_generate()
    accounts = _load_accounts()
    account = next((a for a in accounts if a["id"] == account_id), None)
    if not account:
        abort(404)
    return jsonify(account)


@blueprint.route("/api/transactions")
def api_transactions():
    _maybe_generate()
    txns = _load_transactions()
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

    if user_id:
        txns = [t for t in txns if t["user_id"] == user_id]
    if account_id:
        txns = [t for t in txns if t["account_id"] == account_id]
    if q:
        txns = [t for t in txns if q.lower() in t["description"].lower() or
                q.lower() in t["category"].lower() or
                q.lower() in t["reference"].lower()]
    if category:
        txns = [t for t in txns if t["category"] == category]
    if tx_type:
        txns = [t for t in txns if t["type"] == tx_type]
    if date_from:
        txns = [t for t in txns if t["date"] >= date_from]
    if date_to:
        txns = [t for t in txns if t["date"] <= date_to]
    if min_amount:
        try:
            mn = float(min_amount)
            txns = [t for t in txns if t["amount"] >= mn]
        except ValueError:
            pass
    if max_amount:
        try:
            mx = float(max_amount)
            txns = [t for t in txns if t["amount"] <= mx]
        except ValueError:
            pass

    if sort == "date":
        txns.sort(key=lambda t: t["date"], reverse=True)
    elif sort == "amount_asc":
        txns.sort(key=lambda t: t["amount"])
    elif sort == "amount_desc":
        txns.sort(key=lambda t: t["amount"], reverse=True)
    elif sort == "description":
        txns.sort(key=lambda t: t["description"].lower())

    if limit:
        txns = txns[:limit]
    return jsonify(txns)


@blueprint.route("/api/transactions/search")
def api_transactions_search():
    _maybe_generate()
    q = request.args.get("q", "").strip()
    txns = _load_transactions()
    if q:
        txns = [t for t in txns if q.lower() in t["description"].lower() or
                q.lower() in t["category"].lower() or
                q.lower() in t.get("reference", "").lower()]
    return jsonify(txns)


@blueprint.route("/api/transactions/semantic")
def api_transactions_semantic():
    _maybe_generate()
    q = request.args.get("q", "").strip()
    txns = _load_transactions()
    if q:
        scored = []
        for t in txns:
            text = f"{t['description']} {t['category']} {t['type']} {t['reference']}"
            s = _keyword_score(q, text)
            if s > 0:
                scored.append((t, s))
        scored.sort(key=lambda x: -x[1])
        txns = [t for t, _ in scored]
    return jsonify(txns)


@blueprint.route("/api/payees")
def api_payees():
    _maybe_generate()
    payees = _load_payees()
    user_id = request.args.get("user_id", type=int)
    if user_id:
        payees = [p for p in payees if p["user_id"] == user_id]
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
    _maybe_generate()
    bills = _load_bills()
    user_id = request.args.get("user_id", type=int)
    status = request.args.get("status", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    if user_id:
        bills = [b for b in bills if b["user_id"] == user_id]
    if status:
        bills = [b for b in bills if b["status"] == status]
    if date_from:
        bills = [b for b in bills if b["due_date"] >= date_from]
    if date_to:
        bills = [b for b in bills if b["due_date"] <= date_to]
    return jsonify(bills)


@blueprint.route("/api/bills/<int:bill_id>/pay", methods=["POST"])
def api_pay_bill(bill_id):
    data = request.get_json(silent=True) or {}
    account_id = data.get("account_id")

    bills = _load_bills()
    bill = next((b for b in bills if b["id"] == bill_id), None)
    if not bill:
        abort(404)
    if bill["status"] == "paid":
        return jsonify({"error": "Bill already paid"}), 400

    if account_id:
        accounts = _load_accounts()
        acct = next((a for a in accounts if a["id"] == account_id), None)
        if acct:
            acct["balance"] = round(acct["balance"] - bill["amount"], 2)
            _save_accounts(accounts)

    bill["status"] = "paid"
    _save_bills(bills)

    txns = _load_transactions()
    new_id = max(t["id"] for t in txns) + 1 if txns else 1
    txns.insert(0, {
        "id": new_id,
        "account_id": account_id or 0,
        "user_id": bill["user_id"],
        "date": datetime.now().strftime("%Y-%m-%d"),
        "description": f"Bill payment - {bill['payee_name']}",
        "amount": bill["amount"],
        "type": "debit",
        "category": "Bills",
        "status": "posted",
        "reference": f"BILL{bill_id:06d}",
    })
    _save_transactions(txns)
    return jsonify({"status": "paid", "bill_id": bill_id, "amount": bill["amount"]})


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
    _maybe_generate()
    loans = _load_loans()
    user_id = request.args.get("user_id", type=int)
    ltype = request.args.get("type", "").strip()
    if user_id:
        loans = [l for l in loans if l["user_id"] == user_id]
    if ltype:
        loans = [l for l in loans if l["type"] == ltype]
    return jsonify(loans)


@blueprint.route("/api/loans/<int:loan_id>/pay", methods=["POST"])
def api_pay_loan(loan_id):
    data = request.get_json(silent=True) or {}
    amount = data.get("amount")
    account_id = data.get("account_id")

    loans = _load_loans()
    loan = next((l for l in loans if l["id"] == loan_id), None)
    if not loan:
        abort(404)

    if not amount or amount <= 0:
        amount = loan["monthly_payment"]

    loan["remaining_balance"] = round(loan["remaining_balance"] - amount, 2)
    if loan["remaining_balance"] <= 0:
        loan["remaining_balance"] = 0
        loan["status"] = "paid_off"
    _save_json(LOANS_FILE, loans)

    if account_id:
        accounts = _load_accounts()
        acct = next((a for a in accounts if a["id"] == account_id), None)
        if acct:
            acct["balance"] = round(acct["balance"] - amount, 2)
            _save_accounts(accounts)

    return jsonify({"status": loan["status"], "remaining_balance": loan["remaining_balance"],
                    "payment_amount": amount})


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
    _maybe_generate()
    accounts = _load_accounts()
    txns = _load_transactions()
    user_id = request.args.get("user_id", type=int)
    if user_id:
        accounts = [a for a in accounts if a["user_id"] == user_id]
        txns = [t for t in txns if t["user_id"] == user_id]

    total_balance = sum(a["balance"] for a in accounts)
    by_type = {}
    for a in accounts:
        by_type.setdefault(a["type"], []).append(a["balance"])
    type_totals = {k: round(sum(v), 2) for k, v in by_type.items()}

    cat_spending = Counter()
    for t in txns:
        if t["type"] == "debit":
            cat_spending[t["category"]] += t["amount"]
    top_categories = dict(Counter({k: round(v, 2) for k, v in cat_spending.items()}).most_common(10))

    return jsonify({
        "total_accounts": len(accounts),
        "total_balance": round(total_balance, 2),
        "balance_by_type": type_totals,
        "total_transactions": len(txns),
        "top_spending_categories": top_categories,
    })


@blueprint.route("/api/export")
def api_export():
    _maybe_generate()
    fmt = request.args.get("format", "json").lower()
    data_type = request.args.get("type", "transactions").lower()
    user_id = request.args.get("user_id", type=int)

    if data_type == "transactions":
        data = _load_transactions()
        if user_id:
            data = [d for d in data if d["user_id"] == user_id]
        if fmt == "csv":
            lines = ["id,account_id,user_id,date,description,amount,type,category,status,reference"]
            for t in data:
                desc = t["description"].replace('"', '""')
                lines.append(f'{t["id"]},{t["account_id"]},{t["user_id"]},"{t["date"]}","{desc}",{t["amount"]},{t["type"]},{t["category"]},{t["status"]},{t["reference"]}')
            return Response("\n".join(lines), mimetype="text/csv",
                            headers={"Content-Disposition": "attachment; filename=transactions.csv"})
        return jsonify(data)

    elif data_type == "accounts":
        data = _load_accounts()
        if user_id:
            data = [d for d in data if d["user_id"] == user_id]
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
