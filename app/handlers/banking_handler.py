"""Banking handler — creates debit transactions for purchases, payments, and trades."""

import uuid
from datetime import datetime

from app import db
from app.events import on


def _add_banking_transaction(user_id, description, amount, category="Shopping",
                             reference="", account_type="checking",
                             account_number=""):
    """Add a debit transaction and update account balance.

    If account_number is provided, validates and uses that specific account.
    Otherwise falls back to the user's first account of account_type.
    """
    acct = None

    # Try to find by account number first
    if account_number:
        acct = db.execute(
            "SELECT * FROM banking_accounts WHERE account_number = ? AND user_id = ? LIMIT 1",
            (account_number, user_id), fetch="one",
        )
        # Also try without user_id filter (for cross-user payments)
        if not acct:
            acct = db.execute(
                "SELECT * FROM banking_accounts WHERE account_number = ? LIMIT 1",
                (account_number,), fetch="one",
            )

    # Fall back to account type
    if not acct:
        if account_type == "credit":
            type_filter = "type IN ('credit_card', 'Credit Card')"
        else:
            type_filter = "type IN ('checking', 'Checking')"
        acct = db.execute(
            f"SELECT * FROM banking_accounts WHERE user_id = ? AND {type_filter} LIMIT 1",
            (user_id,), fetch="one",
        )

    account_id = acct["id"] if acct else 1

    if acct:
        new_balance = round(acct.get("balance", 0) - abs(amount), 2)
        acct["balance"] = new_balance
        db.save_item("banking", "accounts", account_id, acct)

    new_id = db.execute(
        "SELECT MAX(id) FROM banking_transactions", fetch="val") or 0
    new_id = max(new_id + 1, 90001)

    txn = {
        "id": new_id,
        "account_id": account_id,
        "user_id": user_id,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "description": description,
        "amount": round(abs(amount), 2),
        "type": "debit",
        "category": category,
        "status": "posted",
        "reference": reference or f"BRIDGE-{uuid.uuid4().hex[:8].upper()}",
    }
    db.save_item("banking", "transactions", new_id, txn)


@on("purchase")
def handle_purchase(user_id, amount, merchant, item="", order_id="",
                    account_type="checking", account_number="", **kwargs):
    ref = order_id or f"ORD-{uuid.uuid4().hex[:8].upper()}"
    desc = f"{merchant} — {item}" if item else merchant
    _add_banking_transaction(user_id, desc, amount, "Shopping", ref, account_type, account_number)


@on("payment")
def handle_payment(user_id, amount, recipient, category="Payment",
                   reference="", account_type="checking", account_number="", **kwargs):
    _add_banking_transaction(user_id, recipient, amount, category, reference, account_type, account_number)


@on("trade")
def handle_trade(user_id, symbol, side, quantity, price,
                 account_type="checking", account_number="", **kwargs):
    if side.lower() == "buy":
        total = round(quantity * price, 2)
        _add_banking_transaction(
            user_id, f"Buy {quantity} {symbol} @ ${price}",
            total, "Investment", f"TRADE-{symbol}", account_type, account_number)


@on("account_reveal")
def handle_account_reveal(**kwargs):
    """2FA-gated reveal: mark this session identity-verified so banking pages
    show full (unmasked) account numbers. Runs when the /verify-payment code
    is accepted for a banking 'Reveal account numbers' request."""
    from flask import session
    session["identity_verified"] = True
