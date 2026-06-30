"""Centralized cross-site event bus for MiniWeb.

Sites emit events (purchases, bookings, signups, etc.) and registered
handlers create corresponding records on target sites (banking debits,
confirmation emails, calendar events, etc.).

Usage in a site's routes.py:
    from app.events import emit
    emit("purchase", user_id=1, amount=50, merchant="Store", item="Book")

Handler registration (in app/handlers/*.py):
    from app.events import on

    @on("purchase")
    def create_banking_debit(user_id, amount, merchant, **kwargs):
        ...
"""

import json
import logging
import random
import time

from app import db

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Handler registry
# ---------------------------------------------------------------------------

_handlers: dict[str, list] = {}


def on(event_type: str):
    """Decorator to register a handler for an event type."""
    def decorator(fn):
        _handlers.setdefault(event_type, []).append(fn)
        return fn
    return decorator


def emit(event_type: str, **kwargs):
    """Emit an event. All registered handlers are called synchronously.

    Errors in individual handlers are caught and logged — they never
    propagate to the emitting site.
    """
    handlers = _handlers.get(event_type, [])
    errors = []

    for handler in handlers:
        try:
            handler(**kwargs)
        except Exception as e:
            err = f"{handler.__module__}.{handler.__name__}: {e}"
            errors.append(err)
            log.warning("Event handler error [%s] %s", event_type, err)

    _log_event(event_type, kwargs, len(handlers), errors)


# ---------------------------------------------------------------------------
# Event log — written directly to DB for auditing
# ---------------------------------------------------------------------------

def _log_event(event_type, payload, handlers_called, errors):
    """Write to the event_log table."""
    try:
        sid = db._get_session_id()
        source = payload.pop("_source_site", "")
        conn = db._get_conn()
        conn.execute(
            "INSERT INTO event_log (timestamp, session_id, event_type, source_site, "
            "payload, handlers_called, errors) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                time.strftime("%Y-%m-%dT%H:%M:%S"),
                sid,
                event_type,
                source,
                json.dumps(payload, default=str)[:2000],
                handlers_called,
                "; ".join(errors) if errors else "",
            ),
        )
        conn.commit()
    except Exception:
        pass  # logging should never break the app


# ---------------------------------------------------------------------------
# 2FA for financial transactions
# ---------------------------------------------------------------------------

_2FA_EVENT_TYPES = {"purchase", "payment", "trade"}


def request_2fa(event_type, return_url, **event_kwargs):
    """Initiate 2FA for a financial transaction.

    Generates a 6-digit code, emails it to the user, stores the pending
    transaction in the Flask session, and returns the verification page URL.

    The calling site should redirect to the returned URL.
    """
    from flask import session, url_for

    code = f"{random.randint(100000, 999999)}"
    user_id = event_kwargs.get("user_id", 1)

    # Store pending transaction in session
    session["_pending_2fa"] = {
        "code": code,
        "event_type": event_type,
        "kwargs": {k: v for k, v in event_kwargs.items()},
        "return_url": return_url,
        "created": time.time(),
    }

    # Send code via email
    try:
        from app.handlers.email_handler import _add_email
        amount = event_kwargs.get("amount", "")
        merchant = event_kwargs.get("merchant", event_kwargs.get("recipient", ""))
        _add_email(
            user_id,
            from_addr="security@miniweb.local",
            subject=f"Verification Code: {code}",
            body=(f"Your verification code is: {code}\n\n"
                  f"Transaction: {event_type}\n"
                  f"{'Amount: $' + str(amount) if amount else ''}\n"
                  f"{'To: ' + str(merchant) if merchant else ''}\n\n"
                  f"If you did not initiate this transaction, ignore this email."),
            labels=["security", "2fa"],
        )
    except Exception:
        pass

    return url_for("_verify_payment")


def verify_2fa(code):
    """Verify a 2FA code and execute the pending transaction.

    Returns (success: bool, return_url: str, error: str).
    """
    from flask import session

    pending = session.get("_pending_2fa")
    if not pending:
        return False, "/", "No pending transaction"

    # Expire after 10 minutes
    if time.time() - pending.get("created", 0) > 600:
        session.pop("_pending_2fa", None)
        return False, pending.get("return_url", "/"), "Verification code expired"

    if code != pending["code"]:
        return False, "", "Invalid verification code"

    # Code correct — execute the transaction
    emit(pending["event_type"], **pending["kwargs"])
    return_url = pending.get("return_url", "/")
    session.pop("_pending_2fa", None)
    return True, return_url, ""


def get_event_log(session_id=None, limit=100):
    """Retrieve recent events for a session (or all if no session)."""
    if session_id:
        return db.execute(
            "SELECT * FROM event_log WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit))
    return db.execute(
        "SELECT * FROM event_log ORDER BY id DESC LIMIT ?", (limit,))
