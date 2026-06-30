"""Banking handler — creates debit transactions for purchases, payments, and trades."""

import uuid
from datetime import datetime

from app import db
from app.events import on


def _add_banking_transaction(user_id, description, amount, category="Shopping",
                             reference="", account_type="checking"):
    """Add a debit transaction and update account balance."""
    # Find the user's account by type
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
                    account_type="checking", **kwargs):
    ref = order_id or f"ORD-{uuid.uuid4().hex[:8].upper()}"
    desc = f"{merchant} — {item}" if item else merchant
    _add_banking_transaction(user_id, desc, amount, "Shopping", ref, account_type)


@on("payment")
def handle_payment(user_id, amount, recipient, category="Payment",
                   reference="", account_type="checking", **kwargs):
    _add_banking_transaction(user_id, recipient, amount, category, reference, account_type)


@on("trade")
def handle_trade(user_id, symbol, side, quantity, price,
                 account_type="checking", **kwargs):
    if side.lower() == "buy":
        total = round(quantity * price, 2)
        _add_banking_transaction(
            user_id, f"Buy {quantity} {symbol} @ ${price}",
            total, "Investment", f"TRADE-{symbol}", account_type)
