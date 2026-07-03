"""Lakeport Medical Center Patient Portal — MyChart-style health portal.

Reads real medical data (users, appointments, medical records, messages,
prescriptions, billing) from the shared data-sources directory and serves
through Flask routes.

Supported macros (26):
  navigate_by_dropdown, navigate_by_route, search_by_query,
  search_by_semantic, search_by_checkbox, filter_by_radio,
  filter_by_date_range, extract_by_query, extract_by_dropdown,
  extract_from_table, extract_by_route, compare_by_date_range,
  submit_by_query, submit_by_route, edit_by_form, export_by_dropdown,
  upload_by_upload, message_from_free_text, submit_by_form,
  book_by_form, book_by_date_range, pay_by_form, cancel_by_form,
  authenticate_by_form, register_by_form, verify_identity_by_code
"""
import csv
import io
import json
import os
import pathlib
import random
import re
import string
from datetime import datetime

from flask import (
    Blueprint, Response, abort, jsonify, redirect, render_template, request,
    session, url_for,
)
from app import db
from app.events import emit

SITE = "health-portals"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "health-portals",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static") if (SITE_DIR / "static").exists() else None,
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _load_users():
    return db.query(SITE, "users")

def _load_appointments():
    return db.query(SITE, "appointments")

def _save_appointments(data):
    db.save_collection(SITE, "appointments", data)

def _load_records():
    return db.query(SITE, "medical_records")

def _load_messages():
    return db.query(SITE, "messages")

def _save_messages(data):
    db.save_collection(SITE, "messages", data)

def _load_prescriptions():
    return db.query(SITE, "prescriptions")

def _save_prescriptions(data):
    db.save_collection(SITE, "prescriptions", data)

def _load_billing():
    return db.query(SITE, "billing")

def _save_billing(data):
    db.save_collection(SITE, "billing", data)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _get_user(user_id):
    return db.get_item(SITE, "users", user_id)


def _get_current_user():
    if "health_user_id" in session:
        return _get_user(session["health_user_id"])
    return None


def _get_browsing_user():
    """Return logged-in user, or fall back to patient 1 for browse-only mode."""
    user = _get_current_user()
    if user:
        return user, True
    return _get_user(1), False


def _get_providers():
    """Return list of provider users."""
    return [u for u in _load_users() if u.get("role") == "provider"]


def _get_provider_name(provider_id):
    p = _get_user(provider_id)
    return p["full_name"] if p else "Unknown Provider"


def _get_patient_name(patient_id):
    p = _get_user(patient_id)
    return p["full_name"] if p else "Unknown Patient"


def _save_users(data):
    db.save_collection(SITE, "users", data)


def _save_records(data):
    db.save_collection(SITE, "medical_records", data)


def _text_match(text, query):
    """Case-insensitive substring match."""
    return query.lower() in (text or "").lower()


def _semantic_match(record, query):
    """Lightweight keyword-overlap scoring for semantic search."""
    words = query.lower().split()
    blob = " ".join(filter(None, [
        record.get("summary"),
        record.get("diagnosis"),
        record.get("record_type"),
        record.get("follow_up"),
    ])).lower()
    return sum(1 for w in words if w in blob)


# In-memory verification code store: {user_id: code_string}
_verification_codes = {}


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    user, logged_in = _get_browsing_user()
    patient_id = user["id"]

    appointments = _load_appointments()
    today = datetime.now().strftime("%Y-%m-%d")
    upcoming = sorted(
        [a for a in appointments if a["patient_id"] == patient_id and a["date"] >= today],
        key=lambda a: (a["date"], a["time"]),
    )[:5]

    messages = _load_messages()
    recent_msgs = sorted(
        [m for m in messages if m.get("recipient_id") == patient_id],
        key=lambda m: m["date"],
        reverse=True,
    )[:5]

    unread_count = sum(1 for m in messages if m.get("recipient_id") == patient_id and not m.get("read", True))

    prescriptions = [p for p in _load_prescriptions() if p["patient_id"] == patient_id and p["status"] == "active"]

    billing = _load_billing()
    pending_bills = [b for b in billing if b["patient_id"] == patient_id and b["payment_status"] == "pending"]
    total_due = sum(b.get("patient_responsibility") or b.get("patient_copay", 0) for b in pending_bills)

    for a in upcoming:
        a["provider_name"] = _get_provider_name(a["provider_id"])

    for m in recent_msgs:
        if m.get("sender_id"):
            m["sender_name"] = _get_provider_name(m["sender_id"]) if m["sender_id"] != patient_id else user["full_name"]
        else:
            m["sender_name"] = "System"

    return render_template(
        "health-portals/index.html",
        user=user, logged_in=logged_in,
        upcoming=upcoming, recent_msgs=recent_msgs,
        unread_count=unread_count,
        active_prescriptions=len(prescriptions),
        pending_bills=pending_bills, total_due=total_due,
    )


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("health-portals/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user:
        return render_template("health-portals/login.html",
                               error="Invalid username or password")
    stored_pw = user.get("password", "password")
    if password and password != stored_pw:
        return render_template("health-portals/login.html", error="Invalid password")
    session["health_user_id"] = user["id"]
    return redirect(url_for("health-portals.index"))


@blueprint.route("/logout")
def logout():
    session.pop("health_user_id", None)
    return redirect(url_for("health-portals.index"))


@blueprint.route("/appointments")
def appointments_page():
    user, logged_in = _get_browsing_user()
    appointments = _load_appointments()
    patient_appts = [a for a in appointments if a["patient_id"] == user["id"]]

    # Filters
    status = request.args.get("status")
    provider = request.args.get("provider")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    dept = request.args.get("department")

    if status:
        patient_appts = [a for a in patient_appts if a["status"] == status]
    if provider:
        patient_appts = [a for a in patient_appts if str(a["provider_id"]) == provider]
    if date_from:
        patient_appts = [a for a in patient_appts if a["date"] >= date_from]
    if date_to:
        patient_appts = [a for a in patient_appts if a["date"] <= date_to]
    if dept:
        providers_in_dept = [u["id"] for u in _load_users() if u.get("department", "").lower() == dept.lower()]
        patient_appts = [a for a in patient_appts if a["provider_id"] in providers_in_dept]

    patient_appts.sort(key=lambda a: (a["date"], a["time"]), reverse=True)

    for a in patient_appts:
        a["provider_name"] = _get_provider_name(a["provider_id"])

    providers = _get_providers()
    return render_template(
        "health-portals/appointments.html",
        user=user, logged_in=logged_in,
        appointments=patient_appts, providers=providers,
        filters={"status": status, "provider": provider, "date_from": date_from,
                 "date_to": date_to, "department": dept},
    )


@blueprint.route("/appointment/<int:appt_id>")
def appointment_detail(appt_id):
    user, logged_in = _get_browsing_user()
    appointments = _load_appointments()
    appt = next((a for a in appointments if a["id"] == appt_id), None)
    if not appt:
        abort(404)
    appt["provider_name"] = _get_provider_name(appt["provider_id"])
    appt["patient_name"] = _get_patient_name(appt["patient_id"])
    return render_template(
        "health-portals/appointment_detail.html",
        user=user, logged_in=logged_in, appointment=appt,
    )


@blueprint.route("/schedule")
def schedule_page():
    user, logged_in = _get_browsing_user()
    providers = _get_providers()
    return render_template(
        "health-portals/schedule.html",
        user=user, logged_in=logged_in, providers=providers,
    )


@blueprint.route("/records")
def records_page():
    user, logged_in = _get_browsing_user()
    records = _load_records()
    patient_records = [r for r in records if r["patient_id"] == user["id"]]
    patient_records.sort(key=lambda r: r["date"], reverse=True)

    for r in patient_records:
        r["provider_name"] = _get_provider_name(r["provider_id"])

    return render_template(
        "health-portals/records.html",
        user=user, logged_in=logged_in, records=patient_records,
    )


@blueprint.route("/record/<int:record_id>")
def record_detail(record_id):
    user, logged_in = _get_browsing_user()
    records = _load_records()
    record = next((r for r in records if r["id"] == record_id), None)
    if not record:
        abort(404)
    record["provider_name"] = _get_provider_name(record["provider_id"])
    record["patient_name"] = _get_patient_name(record["patient_id"])
    return render_template(
        "health-portals/record_detail.html",
        user=user, logged_in=logged_in, record=record,
    )


@blueprint.route("/messages")
def messages_page():
    user, logged_in = _get_browsing_user()
    messages = _load_messages()
    user_msgs = [m for m in messages if m.get("recipient_id") == user["id"] or m.get("sender_id") == user["id"]]

    # Filter by read status
    read_status = request.args.get("read")
    if read_status == "unread":
        user_msgs = [m for m in user_msgs if not m.get("read", True) and m.get("recipient_id") == user["id"]]
    elif read_status == "read":
        user_msgs = [m for m in user_msgs if m.get("read", True)]

    user_msgs.sort(key=lambda m: m["date"], reverse=True)

    for m in user_msgs:
        if m.get("sender_id"):
            m["sender_name"] = _get_provider_name(m["sender_id"]) if m["sender_id"] != user["id"] else user["full_name"]
        else:
            m["sender_name"] = "System"
        if m.get("recipient_id"):
            m["recipient_name"] = _get_provider_name(m["recipient_id"]) if m["recipient_id"] != user["id"] else user["full_name"]
        else:
            m["recipient_name"] = "Unknown"

    return render_template(
        "health-portals/messages.html",
        user=user, logged_in=logged_in, messages=user_msgs,
        filters={"read": read_status},
    )


@blueprint.route("/message/<int:msg_id>")
def message_detail(msg_id):
    user, logged_in = _get_browsing_user()
    messages = _load_messages()
    msg = next((m for m in messages if m["id"] == msg_id), None)
    if not msg:
        abort(404)

    # Mark as read if recipient is current user
    if msg.get("recipient_id") == user["id"] and not msg.get("read", True):
        msg["read"] = True
        _save_messages(messages)

    # Get all messages in the same thread
    thread_msgs = sorted(
        [m for m in messages if m.get("thread_id") == msg.get("thread_id")],
        key=lambda m: m["date"],
    )

    for m in thread_msgs:
        if m.get("sender_id"):
            m["sender_name"] = _get_provider_name(m["sender_id"]) if m["sender_id"] != user["id"] else user["full_name"]
        else:
            m["sender_name"] = "System"

    return render_template(
        "health-portals/message_detail.html",
        user=user, logged_in=logged_in, message=msg, thread=thread_msgs,
    )


@blueprint.route("/compose")
def compose_page():
    user, logged_in = _get_browsing_user()
    providers = _get_providers()
    reply_to = request.args.get("reply_to")
    thread_id = request.args.get("thread_id")
    subject = request.args.get("subject", "")
    return render_template(
        "health-portals/compose.html",
        user=user, logged_in=logged_in, providers=providers,
        reply_to=reply_to, thread_id=thread_id, subject=subject,
    )


@blueprint.route("/prescriptions")
def prescriptions_page():
    user, logged_in = _get_browsing_user()
    prescriptions = _load_prescriptions()
    patient_rx = [p for p in prescriptions if p["patient_id"] == user["id"]]
    patient_rx.sort(key=lambda p: p["date_prescribed"], reverse=True)

    for p in patient_rx:
        p["prescriber_name"] = _get_provider_name(p["prescriber_id"])

    return render_template(
        "health-portals/prescriptions.html",
        user=user, logged_in=logged_in, prescriptions=patient_rx,
    )


@blueprint.route("/billing")
def billing_page():
    user, logged_in = _get_browsing_user()
    billing = _load_billing()
    patient_bills = [b for b in billing if b["patient_id"] == user["id"]]
    patient_bills.sort(key=lambda b: b["date_of_service"], reverse=True)

    for b in patient_bills:
        b["provider_name"] = _get_provider_name(b["provider_id"])

    total_due = sum(
        (b.get("patient_responsibility") or b.get("patient_copay", 0))
        for b in patient_bills if b["payment_status"] == "pending"
    )

    return render_template(
        "health-portals/billing.html",
        user=user, logged_in=logged_in, bills=patient_bills, total_due=total_due,
    )


@blueprint.route("/register", methods=["GET"])
def register_page():
    return render_template("health-portals/register.html", error=None)


@blueprint.route("/register", methods=["POST"])
def register_submit():
    """register_by_form — create a new patient account."""
    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip()
    dob = request.form.get("date_of_birth", "").strip()
    phone = request.form.get("phone", "").strip()

    if not all([first_name, last_name, username, email, dob]):
        return render_template("health-portals/register.html",
                               error="All fields are required")

    users = _load_users()
    if any(u["username"] == username for u in users):
        return render_template("health-portals/register.html",
                               error="Username already taken")

    new_id = max(u["id"] for u in users) + 1
    new_user = {
        "id": new_id,
        "root_user_id": new_id + 100,
        "username": username,
        "first_name": first_name,
        "last_name": last_name,
        "full_name": f"{first_name} {last_name}",
        "date_of_birth": dob,
        "gender": request.form.get("gender", ""),
        "email": email,
        "phone": phone,
        "address": request.form.get("address", ""),
        "role": "patient",
        "insurance_id": None,
        "insurance_provider": None,
        "insurance_group": None,
        "primary_physician_id": None,
        "emergency_contact": None,
        "allergies": [],
        "blood_type": None,
        "registered_date": datetime.now().strftime("%Y-%m-%d"),
        "last_login": None,
        "verified": False,
    }
    users.append(new_user)
    _save_users(users)
    emit("signup", user_id=new_id, site_name="health-portals",
         username=username, password="", email=email)
    # Generate verification code
    code = "".join(random.choices(string.digits, k=6))
    _verification_codes[new_id] = code
    session["health_pending_verify_id"] = new_id
    return redirect(url_for("health-portals.verify_page"))


@blueprint.route("/verify", methods=["GET"])
def verify_page():
    pending_id = session.get("health_pending_verify_id")
    code = _verification_codes.get(pending_id, "------")
    return render_template("health-portals/verify.html",
                           error=None, code_hint=code)


@blueprint.route("/verify", methods=["POST"])
def verify_submit():
    """verify_identity_by_code — verify account with a 6-digit code."""
    pending_id = session.get("health_pending_verify_id")
    code = request.form.get("code", "").strip()
    expected = _verification_codes.get(pending_id)
    if not expected or code != expected:
        return render_template("health-portals/verify.html",
                               error="Invalid verification code",
                               code_hint=expected or "------")
    users = _load_users()
    user = next((u for u in users if u["id"] == pending_id), None)
    if user:
        user["verified"] = True
        _save_users(users)
    _verification_codes.pop(pending_id, None)
    session.pop("health_pending_verify_id", None)
    session["health_user_id"] = pending_id
    return redirect(url_for("health-portals.index"))


@blueprint.route("/billing/<int:bill_id>/pay", methods=["GET"])
def pay_bill_page(bill_id):
    """pay_by_form — show payment form for a bill."""
    user, logged_in = _get_browsing_user()
    billing = _load_billing()
    bill = next((b for b in billing if b["id"] == bill_id), None)
    if not bill:
        abort(404)
    bill["provider_name"] = _get_provider_name(bill["provider_id"])
    amount = bill.get("patient_responsibility") or bill.get("patient_copay", 0)
    return render_template("health-portals/pay.html",
                           user=user, logged_in=logged_in,
                           bill=bill, amount=amount, error=None, success=False)


@blueprint.route("/billing/<int:bill_id>/pay", methods=["POST"])
def pay_bill_submit(bill_id):
    """pay_by_form — process payment for a bill."""
    user, logged_in = _get_browsing_user()
    if not logged_in:
        return redirect(url_for("health-portals.login_page"))

    billing = _load_billing()
    bill = next((b for b in billing if b["id"] == bill_id), None)
    if not bill:
        abort(404)

    card_number = request.form.get("card_number", "").strip()
    card_name = request.form.get("card_name", "").strip()
    if not card_number or not card_name:
        bill["provider_name"] = _get_provider_name(bill["provider_id"])
        amount = bill.get("patient_responsibility") or bill.get("patient_copay", 0)
        return render_template("health-portals/pay.html",
                               user=user, logged_in=logged_in,
                               bill=bill, amount=amount,
                               error="All payment fields are required", success=False)

    bill["payment_status"] = "paid_in_full"
    bill["date_patient_paid"] = datetime.now().strftime("%Y-%m-%d")
    bill["payment_method"] = f"card ending {card_number[-4:]}"
    _save_billing(billing)
    amount = bill.get("patient_responsibility") or bill.get("patient_copay", 0)
    emit("payment", user_id=user["id"], recipient="Lakeport Medical Center", amount=float(amount), category="Medical")
    bill["provider_name"] = _get_provider_name(bill["provider_id"])
    return render_template("health-portals/pay.html",
                           user=user, logged_in=logged_in,
                           bill=bill, amount=amount, error=None, success=True)


@blueprint.route("/appointment/<int:appt_id>/cancel", methods=["GET"])
def cancel_appointment_page(appt_id):
    """cancel_by_form — show cancellation form."""
    user, logged_in = _get_browsing_user()
    appointments = _load_appointments()
    appt = next((a for a in appointments if a["id"] == appt_id), None)
    if not appt:
        abort(404)
    appt["provider_name"] = _get_provider_name(appt["provider_id"])
    return render_template("health-portals/cancel.html",
                           user=user, logged_in=logged_in,
                           appointment=appt, error=None, success=False)


@blueprint.route("/appointment/<int:appt_id>/cancel", methods=["POST"])
def cancel_appointment_submit(appt_id):
    """cancel_by_form — process appointment cancellation."""
    user, logged_in = _get_browsing_user()
    if not logged_in:
        return redirect(url_for("health-portals.login_page"))

    reason = request.form.get("reason", "").strip()
    appointments = _load_appointments()
    appt = next((a for a in appointments if a["id"] == appt_id), None)
    if not appt:
        abort(404)
    if appt["status"] == "cancelled":
        appt["provider_name"] = _get_provider_name(appt["provider_id"])
        return render_template("health-portals/cancel.html",
                               user=user, logged_in=logged_in,
                               appointment=appt,
                               error="Appointment is already cancelled",
                               success=False)

    appt["status"] = "cancelled"
    appt["cancellation_reason"] = reason
    _save_appointments(appointments)
    appt["provider_name"] = _get_provider_name(appt["provider_id"])
    return render_template("health-portals/cancel.html",
                           user=user, logged_in=logged_in,
                           appointment=appt, error=None, success=True)


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/appointments", methods=["GET"])
def api_appointments_list():
    user, _ = _get_browsing_user()
    appointments = _load_appointments()
    patient_appts = [a for a in appointments if a["patient_id"] == user["id"]]

    status = request.args.get("status")
    provider = request.args.get("provider")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    dept = request.args.get("department")

    if status:
        patient_appts = [a for a in patient_appts if a["status"] == status]
    if provider:
        patient_appts = [a for a in patient_appts if str(a["provider_id"]) == provider]
    if date_from:
        patient_appts = [a for a in patient_appts if a["date"] >= date_from]
    if date_to:
        patient_appts = [a for a in patient_appts if a["date"] <= date_to]
    if dept:
        providers_in_dept = [u["id"] for u in _load_users() if u.get("department", "").lower() == dept.lower()]
        patient_appts = [a for a in patient_appts if a["provider_id"] in providers_in_dept]

    patient_appts.sort(key=lambda a: (a["date"], a["time"]))
    return jsonify(patient_appts)


@blueprint.route("/api/appointments", methods=["POST"])
def api_appointments_create():
    user, logged_in = _get_browsing_user()
    if not logged_in:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json(force=True)
    appointments = _load_appointments()
    new_id = max(a["id"] for a in appointments) + 1 if appointments else 1

    new_appt = {
        "id": new_id,
        "patient_id": user["id"],
        "provider_id": data.get("provider_id"),
        "date": data.get("date"),
        "time": data.get("time"),
        "duration_minutes": data.get("duration_minutes", 30),
        "type": data.get("type", "office_visit"),
        "category": data.get("category", "General Visit"),
        "status": "scheduled",
        "location": data.get("location", "Lakeport Medical Center, 800 Health Plaza, Lakeport, WA 98401"),
        "room": None,
        "notes": data.get("notes", ""),
        "check_in_time": None,
        "check_out_time": None,
    }
    appointments.append(new_appt)
    _save_appointments(appointments)

    try:
        from app.bridges import on_booking
        doctor_name = _get_provider_name(new_appt["provider_id"])
        on_booking(
            user_id=user["id"],
            title=f"Dr. Appointment - {doctor_name}",
            start=f"{new_appt['date']}T{new_appt['time']}",
            location="Lakeport Medical Center",
            service_name="Health Portal",
        )
    except Exception:
        pass

    return jsonify(new_appt), 201


@blueprint.route("/api/appointments/<int:appt_id>", methods=["GET"])
def api_appointment_detail(appt_id):
    appointments = _load_appointments()
    appt = next((a for a in appointments if a["id"] == appt_id), None)
    if not appt:
        return jsonify({"error": "Appointment not found"}), 404
    return jsonify(appt)


@blueprint.route("/api/appointments/<int:appt_id>", methods=["PUT"])
def api_appointment_update(appt_id):
    user, logged_in = _get_browsing_user()
    if not logged_in:
        return jsonify({"error": "Authentication required"}), 401

    appointments = _load_appointments()
    appt = next((a for a in appointments if a["id"] == appt_id), None)
    if not appt:
        return jsonify({"error": "Appointment not found"}), 404

    data = request.get_json(force=True)
    for field in ["date", "time", "provider_id", "notes", "status", "type", "category", "duration_minutes"]:
        if field in data:
            appt[field] = data[field]

    _save_appointments(appointments)
    return jsonify(appt)


@blueprint.route("/api/appointments/<int:appt_id>", methods=["DELETE"])
def api_appointment_delete(appt_id):
    user, logged_in = _get_browsing_user()
    if not logged_in:
        return jsonify({"error": "Authentication required"}), 401

    appointments = _load_appointments()
    appt = next((a for a in appointments if a["id"] == appt_id), None)
    if not appt:
        return jsonify({"error": "Appointment not found"}), 404

    appt["status"] = "cancelled"
    _save_appointments(appointments)
    return jsonify({"message": "Appointment cancelled", "appointment": appt})


@blueprint.route("/api/records", methods=["GET"])
def api_records_list():
    user, _ = _get_browsing_user()
    records = _load_records()
    patient_records = [r for r in records if r["patient_id"] == user["id"]]

    # Filter by record_type if provided
    record_type = request.args.get("record_type")
    if record_type:
        patient_records = [r for r in patient_records if r.get("record_type") == record_type]

    patient_records.sort(key=lambda r: r["date"], reverse=True)
    return jsonify(patient_records)


@blueprint.route("/api/records/<int:record_id>", methods=["GET"])
def api_record_detail(record_id):
    records = _load_records()
    record = next((r for r in records if r["id"] == record_id), None)
    if not record:
        return jsonify({"error": "Record not found"}), 404
    return jsonify(record)


@blueprint.route("/api/messages", methods=["GET"])
def api_messages_list():
    user, _ = _get_browsing_user()
    messages = _load_messages()
    user_msgs = [m for m in messages if m.get("recipient_id") == user["id"] or m.get("sender_id") == user["id"]]

    read_status = request.args.get("read")
    if read_status == "unread":
        user_msgs = [m for m in user_msgs if not m.get("read", True) and m.get("recipient_id") == user["id"]]
    elif read_status == "read":
        user_msgs = [m for m in user_msgs if m.get("read", True)]

    user_msgs.sort(key=lambda m: m["date"], reverse=True)
    return jsonify(user_msgs)


@blueprint.route("/api/messages", methods=["POST"])
def api_messages_create():
    user, logged_in = _get_browsing_user()
    if not logged_in:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json(force=True)
    messages = _load_messages()
    new_id = max(m["id"] for m in messages) + 1 if messages else 1

    new_msg = {
        "id": new_id,
        "thread_id": data.get("thread_id", f"THR-{datetime.now().strftime('%Y')}-{new_id:03d}"),
        "sender_id": user["id"],
        "recipient_id": data.get("recipient_id"),
        "date": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "subject": data.get("subject", ""),
        "body": data.get("body", ""),
        "read": False,
        "category": data.get("category", "general"),
        "priority": data.get("priority", "normal"),
    }
    messages.append(new_msg)
    _save_messages(messages)
    return jsonify(new_msg), 201


@blueprint.route("/api/messages/<int:msg_id>", methods=["GET"])
def api_message_detail(msg_id):
    messages = _load_messages()
    msg = next((m for m in messages if m["id"] == msg_id), None)
    if not msg:
        return jsonify({"error": "Message not found"}), 404
    return jsonify(msg)


@blueprint.route("/api/messages/<int:msg_id>/reply", methods=["POST"])
def api_message_reply(msg_id):
    user, logged_in = _get_browsing_user()
    if not logged_in:
        return jsonify({"error": "Authentication required"}), 401

    messages = _load_messages()
    original = next((m for m in messages if m["id"] == msg_id), None)
    if not original:
        return jsonify({"error": "Message not found"}), 404

    data = request.get_json(force=True)
    new_id = max(m["id"] for m in messages) + 1

    # Reply goes to the original sender
    recipient_id = original["sender_id"] if original["sender_id"] != user["id"] else original["recipient_id"]

    reply = {
        "id": new_id,
        "thread_id": original.get("thread_id"),
        "sender_id": user["id"],
        "recipient_id": recipient_id,
        "date": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "subject": f"RE: {original['subject'].replace('RE: ', '')}",
        "body": data.get("body", ""),
        "read": False,
        "category": data.get("category", "general"),
        "priority": data.get("priority", "normal"),
    }
    messages.append(reply)
    _save_messages(messages)
    return jsonify(reply), 201


@blueprint.route("/api/prescriptions", methods=["GET"])
def api_prescriptions_list():
    user, _ = _get_browsing_user()
    prescriptions = _load_prescriptions()
    patient_rx = [p for p in prescriptions if p["patient_id"] == user["id"]]
    patient_rx.sort(key=lambda p: p["date_prescribed"], reverse=True)
    return jsonify(patient_rx)


@blueprint.route("/api/prescriptions/<int:rx_id>/refill", methods=["POST"])
def api_prescription_refill(rx_id):
    user, logged_in = _get_browsing_user()
    if not logged_in:
        return jsonify({"error": "Authentication required"}), 401

    prescriptions = _load_prescriptions()
    rx = next((p for p in prescriptions if p["id"] == rx_id), None)
    if not rx:
        return jsonify({"error": "Prescription not found"}), 404
    if rx["refills_remaining"] <= 0:
        return jsonify({"error": "No refills remaining. Contact your provider."}), 400

    rx["refills_remaining"] -= 1
    rx["date_filled"] = datetime.now().strftime("%Y-%m-%d")
    _save_prescriptions(prescriptions)
    return jsonify({"message": "Refill requested successfully", "prescription": rx})


@blueprint.route("/api/billing", methods=["GET"])
def api_billing_list():
    user, _ = _get_browsing_user()
    billing = _load_billing()
    patient_bills = [b for b in billing if b["patient_id"] == user["id"]]
    patient_bills.sort(key=lambda b: b["date_of_service"], reverse=True)
    return jsonify(patient_bills)


@blueprint.route("/api/billing/<int:bill_id>/pay", methods=["POST"])
def api_billing_pay(bill_id):
    user, logged_in = _get_browsing_user()
    if not logged_in:
        return jsonify({"error": "Authentication required"}), 401

    billing = _load_billing()
    bill = next((b for b in billing if b["id"] == bill_id), None)
    if not bill:
        return jsonify({"error": "Bill not found"}), 404
    if bill["payment_status"] == "paid_in_full":
        return jsonify({"error": "Bill already paid"}), 400

    bill["payment_status"] = "paid_in_full"
    bill["date_patient_paid"] = datetime.now().strftime("%Y-%m-%d")
    _save_billing(billing)
    pay_amount = bill.get("patient_responsibility") or bill.get("patient_copay", 0)
    emit("payment", user_id=user["id"], recipient="Lakeport Medical Center", amount=float(pay_amount), category="Medical")
    return jsonify({"message": "Payment processed successfully", "bill": bill})


@blueprint.route("/api/stats", methods=["GET"])
def api_stats():
    user, _ = _get_browsing_user()
    patient_id = user["id"]

    appointments = _load_appointments()
    records = _load_records()
    messages = _load_messages()
    prescriptions = _load_prescriptions()
    billing = _load_billing()

    today = datetime.now().strftime("%Y-%m-%d")
    patient_appts = [a for a in appointments if a["patient_id"] == patient_id]
    patient_records = [r for r in records if r["patient_id"] == patient_id]
    patient_msgs = [m for m in messages if m.get("recipient_id") == patient_id]
    patient_rx = [p for p in prescriptions if p["patient_id"] == patient_id]
    patient_bills = [b for b in billing if b["patient_id"] == patient_id]

    return jsonify({
        "total_appointments": len(patient_appts),
        "upcoming_appointments": len([a for a in patient_appts if a["date"] >= today and a["status"] == "scheduled"]),
        "completed_appointments": len([a for a in patient_appts if a["status"] == "completed"]),
        "total_records": len(patient_records),
        "unread_messages": len([m for m in patient_msgs if not m.get("read", True)]),
        "total_messages": len(patient_msgs),
        "active_prescriptions": len([p for p in patient_rx if p["status"] == "active"]),
        "total_prescriptions": len(patient_rx),
        "pending_bills": len([b for b in patient_bills if b["payment_status"] == "pending"]),
        "total_billed": sum(b.get("billed_amount", 0) or 0 for b in patient_bills),
        "total_patient_responsibility": sum(
            (b.get("patient_responsibility") or b.get("patient_copay", 0))
            for b in patient_bills
        ),
        "total_outstanding": sum(
            (b.get("patient_responsibility") or b.get("patient_copay", 0))
            for b in patient_bills if b["payment_status"] == "pending"
        ),
    })


# ---------------------------------------------------------------------------
# Macro: search_by_query -- text search across records and messages
# ---------------------------------------------------------------------------

@blueprint.route("/api/search", methods=["GET"])
def api_search():
    """Full-text search across medical records and messages.

    Macro: search_by_query
    """
    q = request.args.get("q", "").strip().lower()
    if not q:
        return jsonify([])

    results = []
    user, _ = _get_browsing_user()
    patient_id = user["id"]

    for r in _load_records():
        if r["patient_id"] != patient_id:
            continue
        searchable = " ".join(filter(None, [
            r.get("summary"),
            r.get("diagnosis"),
            r.get("record_type"),
            r.get("follow_up"),
        ])).lower()
        if q in searchable:
            results.append({"type": "record", "item": r})

    for m in _load_messages():
        if m.get("recipient_id") != patient_id and m.get("sender_id") != patient_id:
            continue
        searchable = " ".join(filter(None, [
            m.get("subject"),
            m.get("body"),
        ])).lower()
        if q in searchable:
            results.append({"type": "message", "item": m})

    return jsonify(results)


# ---------------------------------------------------------------------------
# Macro: search_by_semantic -- keyword-overlap relevance on records
# ---------------------------------------------------------------------------

@blueprint.route("/api/search/semantic", methods=["GET"])
def api_search_semantic():
    """Semantic search over medical records using keyword overlap.

    Macro: search_by_semantic
    """
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    user, _ = _get_browsing_user()
    patient_id = user["id"]
    records = [r for r in _load_records() if r["patient_id"] == patient_id]

    scored = []
    for r in records:
        score = _semantic_match(r, q)
        if score > 0:
            scored.append((score, r))

    scored.sort(key=lambda x: x[0], reverse=True)
    return jsonify([item for _, item in scored])


# ---------------------------------------------------------------------------
# Macro: search_by_checkbox -- filter records by type checkboxes
# ---------------------------------------------------------------------------

@blueprint.route("/api/records/filter", methods=["GET"])
def api_records_filter():
    """Filter medical records by type checkboxes.

    Macro: search_by_checkbox
    Params: type (can be repeated, e.g. ?type=annual_physical&type=lab_work)
    """
    user, _ = _get_browsing_user()
    records = _load_records()
    patient_records = [r for r in records if r["patient_id"] == user["id"]]

    types = request.args.getlist("type")
    if types:
        patient_records = [r for r in patient_records if r.get("record_type") in types]

    patient_records.sort(key=lambda r: r["date"], reverse=True)
    return jsonify(patient_records)


# ---------------------------------------------------------------------------
# Macro: filter_by_radio -- filter appointments by status
# ---------------------------------------------------------------------------

@blueprint.route("/api/appointments/status", methods=["GET"])
def api_appointments_by_status():
    """Filter appointments by status radio button.

    Macro: filter_by_radio
    Params: status (scheduled, completed, cancelled)
    """
    user, _ = _get_browsing_user()
    appointments = _load_appointments()
    patient_appts = [a for a in appointments if a["patient_id"] == user["id"]]

    status = request.args.get("status")
    if status:
        patient_appts = [a for a in patient_appts if a["status"] == status]

    patient_appts.sort(key=lambda a: (a["date"], a["time"]))
    return jsonify(patient_appts)


# ---------------------------------------------------------------------------
# Macro: extract_by_query -- search records and extract info
# ---------------------------------------------------------------------------

@blueprint.route("/api/records/search", methods=["GET"])
def api_records_search():
    """Search medical records by query and return matches.

    Macro: extract_by_query
    """
    q = request.args.get("q", "").strip().lower()
    user, _ = _get_browsing_user()
    records = _load_records()
    patient_records = [r for r in records if r["patient_id"] == user["id"]]

    if q:
        patient_records = [r for r in patient_records if _text_match(
            " ".join(filter(None, [r.get("summary"), r.get("diagnosis"),
                                   r.get("record_type"), r.get("follow_up")])), q)]

    patient_records.sort(key=lambda r: r["date"], reverse=True)
    return jsonify(patient_records)


# ---------------------------------------------------------------------------
# Macro: extract_by_dropdown -- department appointment stats
# ---------------------------------------------------------------------------

@blueprint.route("/api/appointments/dept-stats", methods=["GET"])
def api_appointments_dept_stats():
    """Get appointment statistics grouped by department.

    Macro: extract_by_dropdown
    Params: department (optional)
    """
    appointments = _load_appointments()
    users = _load_users()
    dept = request.args.get("department", "")

    provider_dept = {}
    for u in users:
        if u.get("role") == "provider":
            provider_dept[u["id"]] = u.get("department", "General")

    if dept:
        dept_providers = [pid for pid, d in provider_dept.items()
                          if d.lower() == dept.lower()]
        appts = [a for a in appointments if a["provider_id"] in dept_providers]
    else:
        appts = appointments

    stats = {
        "department": dept or "all",
        "total": len(appts),
        "scheduled": len([a for a in appts if a["status"] == "scheduled"]),
        "completed": len([a for a in appts if a["status"] == "completed"]),
        "cancelled": len([a for a in appts if a["status"] == "cancelled"]),
    }
    return jsonify(stats)


# ---------------------------------------------------------------------------
# Macro: compare_by_date_range -- compare vitals across periods
# ---------------------------------------------------------------------------

@blueprint.route("/api/records/compare", methods=["GET"])
def api_records_compare():
    """Compare medical data between two date ranges.

    Macro: compare_by_date_range
    Params: from1, to1, from2, to2
    """
    user, _ = _get_browsing_user()
    from1 = request.args.get("from1", "")
    to1 = request.args.get("to1", "")
    from2 = request.args.get("from2", "")
    to2 = request.args.get("to2", "")

    if not (from1 and to1 and from2 and to2):
        return jsonify({"error": "Provide from1, to1, from2, to2"}), 400

    records = [r for r in _load_records() if r["patient_id"] == user["id"]]
    w1 = [r for r in records if from1 <= r["date"] <= to1]
    w2 = [r for r in records if from2 <= r["date"] <= to2]

    def _vitals_avg(recs):
        vitals_list = [r["vitals"] for r in recs if r.get("vitals")]
        if not vitals_list:
            return None
        return {
            "avg_weight_lbs": round(sum(v.get("weight_lbs", 0) for v in vitals_list) / len(vitals_list), 1),
            "avg_bp_systolic": round(sum(v.get("blood_pressure_systolic", 0) for v in vitals_list) / len(vitals_list)),
            "avg_bp_diastolic": round(sum(v.get("blood_pressure_diastolic", 0) for v in vitals_list) / len(vitals_list)),
            "avg_heart_rate": round(sum(v.get("heart_rate_bpm", 0) for v in vitals_list) / len(vitals_list)),
            "records_count": len(vitals_list),
        }

    return jsonify({
        "period1": {"from": from1, "to": to1, "vitals": _vitals_avg(w1), "records": len(w1)},
        "period2": {"from": from2, "to": to2, "vitals": _vitals_avg(w2), "records": len(w2)},
    })


# ---------------------------------------------------------------------------
# Macro: submit_by_query -- search for provider and submit appointment
# ---------------------------------------------------------------------------

@blueprint.route("/api/providers", methods=["GET"])
def api_providers_list():
    """Search providers by name or department.

    Macro: submit_by_query (search step)
    """
    q = request.args.get("q", "").strip().lower()
    providers = _get_providers()

    if q:
        providers = [p for p in providers
                     if q in p.get("full_name", "").lower()
                     or q in p.get("department", "").lower()
                     or q in p.get("specialty", "").lower()]

    return jsonify([{
        "id": p["id"],
        "full_name": p["full_name"],
        "department": p.get("department", "General"),
        "specialty": p.get("specialty", ""),
    } for p in providers])


# ---------------------------------------------------------------------------
# Macro: submit_by_route -- submit prescription refill (already exists)
# Macro: edit_by_form -- edit appointment (already exists via PUT)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Macro: export_by_dropdown -- export data as CSV or JSON
# ---------------------------------------------------------------------------

@blueprint.route("/api/export", methods=["GET"])
def api_export():
    """Export records, appointments, or billing as CSV or JSON.

    Macro: export_by_dropdown
    Params: format (csv|json), data_type (records|appointments|billing|prescriptions)
    """
    fmt = request.args.get("format", "json")
    data_type = request.args.get("data_type", "records")
    user, _ = _get_browsing_user()
    patient_id = user["id"]

    if data_type == "records":
        data = [r for r in _load_records() if r["patient_id"] == patient_id]
        columns = ["id", "patient_id", "date", "record_type", "summary",
                    "diagnosis", "follow_up"]
    elif data_type == "appointments":
        data = [a for a in _load_appointments() if a["patient_id"] == patient_id]
        columns = ["id", "patient_id", "provider_id", "date", "time",
                    "type", "category", "status", "location"]
    elif data_type == "billing":
        data = [b for b in _load_billing() if b["patient_id"] == patient_id]
        columns = ["id", "patient_id", "date_of_service", "description",
                    "billed_amount", "patient_responsibility", "payment_status"]
    elif data_type == "prescriptions":
        data = [p for p in _load_prescriptions() if p["patient_id"] == patient_id]
        columns = ["id", "patient_id", "medication", "dosage", "frequency",
                    "date_prescribed", "status", "refills_remaining"]
    else:
        return jsonify({"error": "data_type must be records, appointments, billing, or prescriptions"}), 400

    if fmt == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in data:
            writer.writerow(row)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={data_type}.csv"},
        )
    else:
        return jsonify(data)


# ---------------------------------------------------------------------------
# Macro: upload_by_upload -- upload medical documents
# ---------------------------------------------------------------------------

# In-memory uploaded document store
_uploaded_documents = []

@blueprint.route("/api/documents/upload", methods=["POST"])
def api_document_upload():
    """Upload a medical document.

    Macro: upload_by_upload
    """
    user, logged_in = _get_browsing_user()
    if not logged_in:
        return jsonify({"error": "Authentication required"}), 401

    f = request.files.get("file")
    if not f:
        # Also accept JSON body with filename/content for testing
        data = request.get_json(silent=True) or {}
        filename = data.get("filename", "unknown.pdf")
        description = data.get("description", "")
    else:
        filename = f.filename
        description = request.form.get("description", "")
        # Don't actually save to disk in test mode

    doc = {
        "id": len(_uploaded_documents) + 1,
        "patient_id": user["id"],
        "filename": filename,
        "description": description,
        "upload_date": datetime.now().strftime("%Y-%m-%d"),
        "status": "received",
    }
    _uploaded_documents.append(doc)
    return jsonify(doc), 201


@blueprint.route("/api/documents", methods=["GET"])
def api_documents_list():
    """List uploaded documents for current patient."""
    user, _ = _get_browsing_user()
    docs = [d for d in _uploaded_documents if d["patient_id"] == user["id"]]
    return jsonify(docs)


# ---------------------------------------------------------------------------
# Macro: message_from_free_text -- already exists (api_messages_create)
# Macro: submit_by_form / book_by_form / book_by_date_range -- already exists
#   (api_appointments_create)
# Macro: pay_by_form -- already exists (api_billing_pay, pay_bill_submit)
# Macro: cancel_by_form -- already exists (cancel_appointment_submit)
# Macro: authenticate_by_form -- already exists (login_submit)
# Macro: register_by_form -- already exists (register_submit)
# Macro: verify_identity_by_code -- already exists (verify_submit)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# API: User profile endpoints
# ---------------------------------------------------------------------------

@blueprint.route("/api/users", methods=["GET"])
def api_users_list():
    """List all users.

    Macro: navigate_by_dropdown (provider selector)
    """
    users = _load_users()
    return jsonify([{
        "id": u["id"],
        "username": u["username"],
        "full_name": u["full_name"],
        "role": u.get("role", "patient"),
        "department": u.get("department", ""),
    } for u in users])


@blueprint.route("/api/users/<int:user_id>", methods=["GET"])
def api_user_detail(user_id):
    """Get user profile details.

    Macro: navigate_by_route, extract_by_route
    """
    user = _get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user)


@blueprint.route("/api/users/<int:user_id>", methods=["PUT"])
def api_user_update(user_id):
    """Update user profile (edit_by_form).

    Macro: edit_by_form
    """
    current_user, logged_in = _get_browsing_user()
    if not logged_in:
        return jsonify({"error": "Authentication required"}), 401

    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json(force=True)
    updatable = ["phone", "email", "address"]
    for key in updatable:
        if key in data:
            user[key] = data[key]

    _save_users(users)
    return jsonify(user)


# ---------------------------------------------------------------------------
# API login for verifier use
# ---------------------------------------------------------------------------

@blueprint.route("/api/login", methods=["POST"])
def api_login():
    """API login endpoint for programmatic access."""
    data = request.get_json(force=True)
    username = data.get("username", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user:
        return jsonify({"error": "Invalid credentials"}), 401
    session["health_user_id"] = user["id"]
    return jsonify({"user_id": user["id"], "username": user["username"],
                    "full_name": user["full_name"]})


# ---------------------------------------------------------------------------
# Record types list (for checkbox filtering)
# ---------------------------------------------------------------------------

@blueprint.route("/api/record-types", methods=["GET"])
def api_record_types():
    """Return all known record types."""
    records = _load_records()
    types = sorted(set(r.get("record_type", "") for r in records if r.get("record_type")))
    return jsonify(types)
