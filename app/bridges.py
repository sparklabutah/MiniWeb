"""Cross-site event bridges for MiniWeb — backward-compatible wrappers.

These functions delegate to app.events.emit(). Sites can call these
directly or use emit() for new code.

Usage:
    from app.bridges import on_purchase
    on_purchase(user_id=1, merchant="Amazon", amount=89.99)

    # Or directly:
    from app.events import emit
    emit("purchase", user_id=1, merchant="Amazon", amount=89.99)
"""

from app.events import emit


def on_purchase(user_id, merchant, amount, item_description="", order_id="",
                account_type="checking"):
    emit("purchase", user_id=user_id, merchant=merchant, amount=amount,
         item=item_description, order_id=order_id, account_type=account_type)


def on_payment(user_id, recipient, amount, category="Payment", reference="",
               account_type="checking"):
    emit("payment", user_id=user_id, recipient=recipient, amount=amount,
         category=category, reference=reference, account_type=account_type)


def on_booking(user_id, title, start, end="", location="", service_name="",
               confirmation_id=""):
    emit("booking", user_id=user_id, title=title, start=start, end=end,
         location=location, service_name=service_name,
         confirmation_id=confirmation_id)


def on_subscribe(user_id, service_name, welcome_message=""):
    emit("subscribe", user_id=user_id, service_name=service_name,
         welcome_message=welcome_message)


def on_inquiry(user_id, company_name, subject="", message=""):
    emit("inquiry", user_id=user_id, company_name=company_name,
         subject=subject, message=message)


def on_message(from_user_id, to_user_id, text, source_site=""):
    emit("message", from_user_id=from_user_id, to_user_id=to_user_id,
         text=text, source_site=source_site)


# Keep _add_email accessible for sites that call it directly (agency-portals)
def _add_email(user_id, from_addr, subject, body, labels=None):
    from app.handlers.email_handler import _add_email as _impl
    _impl(user_id, from_addr, subject, body, labels)
