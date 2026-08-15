"""Email handler — sends confirmation/notification emails for various events."""

import uuid
from datetime import datetime

from app import db
from app.events import on


def _add_email(user_id, from_addr, subject, body, labels=None):
    """Add an email to the user's inbox via the sent_messages overlay."""
    user = db.get_item("email", "users", user_id)
    to_addr = (user.get("email_address", "alex.rivera@meridiansystems.com")
               if user else "alex.rivera@meridiansystems.com")

    now = datetime.now()
    date_iso = now.strftime("%Y-%m-%dT%H:%M:%S") + "Z"
    body_clean = body.replace('\n', ' ').replace('\r', ' ').strip()
    body_preview = (body_clean[:120] + '...') if len(body_clean) > 120 else body_clean

    msgs = db.query("email", "sent_messages")
    new_id = 30000 + len(msgs) + 1
    msgs.append({
        "id": new_id,
        "from_": from_addr,
        "to": [to_addr],
        "cc": [],
        "subject": subject,
        "date": date_iso,
        "body": body,
        "message_id": f"<bridge-{uuid.uuid4().hex[:8]}@miniweb.local>",
        "folder": "inbox",
        "labels": labels or ["notifications"],
        "is_read": False,
        "is_starred": False,
        "has_attachment": False,
        "user_id": user_id,
        "from_addr": from_addr,
        "to_addrs": [to_addr],
        "cc_addrs": [],
        "date_display": now.strftime("%b %d, %Y %I:%M %p"),
        "date_sort": now.timestamp(),
        "body_preview": body_preview,
    })
    db.save_collection("email", "sent_messages", msgs)

    try:
        import sites.email.routes as email_mod
        email_mod._overlay_emails = None
    except (ImportError, AttributeError):
        pass


@on("purchase")
def purchase_email(user_id, merchant, amount, item="", order_id="", **kwargs):
    _add_email(
        user_id,
        from_addr=f"orders@{merchant.lower().replace(' ', '')}.com",
        subject=f"Order Confirmation — ${amount:.2f}",
        body=(f"Thank you for your purchase!\n\n"
              f"Merchant: {merchant}\n"
              f"{'Item: ' + item + chr(10) if item else ''}"
              f"Total: ${amount:.2f}\n"
              f"{'Order: ' + order_id + chr(10) if order_id else ''}\n"
              f"Your account has been charged."),
        labels=["orders", "notifications"],
    )


@on("booking")
def booking_email(user_id, title, start, service_name="", confirmation_id="", **kwargs):
    _add_email(
        user_id,
        from_addr=f"bookings@{(service_name or 'miniweb').lower().replace(' ', '')}.com",
        subject=f"Booking Confirmed — {title}",
        body=(f"Your booking has been confirmed!\n\n"
              f"What: {title}\n"
              f"When: {start}\n"
              f"{'Confirmation: ' + confirmation_id + chr(10) if confirmation_id else ''}"),
        labels=["bookings", "notifications"],
    )


@on("signup")
def signup_email(user_id, site_name, username, **kwargs):
    _add_email(
        user_id,
        from_addr=f"noreply@{site_name.lower().replace(' ', '')}.miniweb.local",
        subject=f"Welcome to {site_name.replace('-', ' ').title()}!",
        body=(f"Your account has been created.\n\n"
              f"Username: {username}\n"
              f"Site: {site_name}\n\n"
              f"You can now access all features."),
        labels=["welcome", "notifications"],
    )


@on("subscribe")
def subscribe_email(user_id, service_name, welcome_message="", **kwargs):
    _add_email(
        user_id,
        from_addr=f"newsletter@{service_name.lower().replace(' ', '')}.com",
        subject=f"Subscribed to {service_name}",
        body=(welcome_message or
              f"Thanks for subscribing to {service_name}!\n\n"
              f"You'll receive updates and news directly in your inbox."),
        labels=["newsletters", "notifications"],
    )


@on("inquiry")
def inquiry_email(user_id, company_name, subject="", message="", **kwargs):
    _add_email(
        user_id,
        from_addr=f"support@{company_name.lower().replace(' ', '')}.com",
        subject=f"Re: {subject}" if subject else f"Thank you for contacting {company_name}",
        body=(f"Thank you for reaching out to {company_name}!\n\n"
              f"We have received your inquiry"
              f"{(' regarding: ' + subject) if subject else ''}.\n\n"
              f"Our team will review your request and get back to you "
              f"within 1-2 business days."),
        labels=["support", "notifications"],
    )


@on("file_created")
def file_email(user_id, filename, file_type, source_site="", **kwargs):
    _add_email(
        user_id,
        from_addr="cloud@miniweb.local",
        subject=f"File synced: {filename}",
        body=f"Your {file_type} '{filename}' from {source_site or 'MiniWeb'} "
             f"has been synced to your cloud storage.",
        labels=["cloud", "notifications"],
    )
