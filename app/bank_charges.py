"""Shared 'secure bank charge' backend.

Any site that collects card details (e.g. Lakeport Medical Center billing) can
call ``charge_card`` to validate the card against the banking site's card
fixture (``banking_cc_users``) and record the charge on the cardholder's credit
card (``banking_cc_transactions``).

Charges are written to the SESSION OVERLAY via ``db.save_item`` — so parallel
agents stay isolated and the pristine base ledger is never mutated (see
CLAUDE.md "Session isolation").
"""
import re
import uuid
from datetime import datetime

from app import db

BANK = "banking"


def _digits(s):
    return re.sub(r"\D", "", s or "")


def _norm_exp(e):
    d = _digits(e)
    return d[-4:] if len(d) >= 4 else d   # normalise MM/YY or MMYY -> MMYY


def find_card(card_number):
    """Look up a banking card by full number (preferred) or last-4 fallback.
    cc_users is a small table (<100 rows), so a full scan is fine here."""
    d = _digits(card_number)
    if not d:
        return None
    cards = db.query(BANK, "cc_users")
    for u in cards:
        if u.get("card_number") and _digits(u["card_number"]) == d:
            return u
    if len(d) >= 4:
        for u in cards:
            if u.get("card_number_last4") == d[-4:]:
                return u
    return None


def charge_card(card_number, cvv, expiry, amount, merchant,
                category="general", description="", require_expiry=True, strict=True):
    """Validate a card and post a charge. Returns a dict with ok/error.

    strict=True (default): declines an unrecognised card, wrong CVV/expiry, a
    frozen card, a bad amount, or insufficient available credit.

    strict=False (loose): accepts ANY card number so checkout is never blocked
    for an external card — EXCEPT that a recognised SecureBank number must carry
    the correct CVV (wrong CVV on a known card => declined). An unrecognised
    number is accepted with no bank charge; a recognised number + correct CVV
    records the charge (expiry/limit not enforced). Returns ok with a
    ``charged`` flag, or ok=False + error on a declined known card.
    """
    card = find_card(card_number)

    if not strict:
        if not card:
            # any other card number is accepted; nothing to charge to the bank
            return {"ok": True, "charged": False, "external": True,
                    "note": "external card accepted — no bank charge recorded"}
        if card.get("card_frozen"):
            return {"ok": False, "error": "Card declined — card is frozen"}
        # recognised card => the CVV must match
        if str(cvv or "").strip() != str(card.get("cvv") or "").strip():
            return {"ok": False, "error": "Card declined — invalid security code (CVV)"}
        # recognised + correct CVV: fall through to record the charge
    else:
        if not card:
            return {"ok": False, "error": "Card declined — number not recognized"}
        if card.get("card_frozen"):
            return {"ok": False, "error": "Card declined — card is frozen"}
        if str(cvv or "").strip() != str(card.get("cvv") or "").strip():
            return {"ok": False, "error": "Card declined — invalid security code (CVV)"}
        if require_expiry and card.get("card_expiry"):
            if _norm_exp(expiry) != _norm_exp(card.get("card_expiry")):
                return {"ok": False, "error": "Card declined — invalid or expired card"}

    try:
        amt = round(float(amount), 2)
    except (TypeError, ValueError):
        return {"ok": False, "error": "Invalid amount"}
    if amt <= 0:
        return {"ok": False, "error": "Invalid amount"}
    avail = float(card.get("available_credit") or 0)
    if strict and amt > avail:
        return {"ok": False, "error": "Card declined — insufficient available credit"}

    txid = 700000 + (uuid.uuid4().int % 100000)
    db.save_item(BANK, "cc_transactions", txid, {
        "id": txid,
        "user_id": card.get("root_user_id"),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "merchant": merchant,
        "amount": amt,
        "category": category,
        "status": "posted",
        "description": description or f"Card charge — {merchant}",
    })
    updated = dict(card)
    updated["current_balance"] = round(float(card.get("current_balance") or 0) + amt, 2)
    updated["available_credit"] = round(avail - amt, 2)
    db.save_item(BANK, "cc_users", card["id"], updated)

    return {"ok": True, "charged": True, "transaction_id": txid,
            "card_last4": card.get("card_number_last4"),
            "cardholder": card.get("name"), "merchant": merchant, "amount": amt,
            "available_credit": updated["available_credit"]}
