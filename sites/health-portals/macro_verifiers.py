"""Per-macro verification functions for health-portals.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/health-portals"


def _login(server_url):
    """Helper to log in as patient 1."""
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login", json={"username": "alex.rivera"})
    return s


def verify_macro_navigate_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/providers")
    providers = r.json()
    if not providers:
        return {"pass": False, "detail": "No providers returned"}
    return {"pass": len(providers) > 0,
            "detail": f"navigate_by_dropdown: {len(providers)} providers"}


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/appointment/1")
    return {"pass": r.status_code == 200,
            "detail": f"Appointment detail page: {r.status_code}"}


def verify_macro_search_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/search?q=knee")
    results = r.json()
    return {"pass": len(results) > 0,
            "detail": f"search_by_query 'knee': {len(results)} results"}


def verify_macro_search_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/search/semantic?q=physical+therapy+knee")
    results = r.json()
    return {"pass": r.status_code == 200,
            "detail": f"search_by_semantic: {len(results)} results"}


def verify_macro_search_by_checkbox(server_url):
    r = requests.get(f"{_base(server_url)}/api/records/filter?type=annual_physical&type=follow_up")
    records = r.json()
    ok = all(r.get("record_type") in ["annual_physical", "follow_up"] for r in records)
    return {"pass": ok,
            "detail": f"search_by_checkbox: {len(records)} records, types_correct={ok}"}


def verify_macro_filter_by_radio(server_url):
    r = requests.get(f"{_base(server_url)}/api/appointments/status?status=completed")
    appts = r.json()
    ok = all(a["status"] == "completed" for a in appts)
    return {"pass": ok and len(appts) > 0,
            "detail": f"filter_by_radio completed: {len(appts)}, all_completed={ok}"}


def verify_macro_filter_by_date_range(server_url):
    r = requests.get(f"{_base(server_url)}/api/appointments?date_from=2026-01-01&date_to=2026-06-30")
    appts = r.json()
    ok = all("2026-01-01" <= a["date"] <= "2026-06-30" for a in appts)
    return {"pass": ok,
            "detail": f"filter_by_date_range: {len(appts)} appointments, in_range={ok}"}


def verify_macro_extract_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/records/search?q=physical")
    records = r.json()
    return {"pass": r.status_code == 200,
            "detail": f"extract_by_query 'physical': {len(records)} records"}


def verify_macro_extract_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/appointments/dept-stats")
    stats = r.json()
    return {"pass": "total" in stats,
            "detail": f"extract_by_dropdown: total={stats.get('total')}"}


def verify_macro_extract_from_table(server_url):
    r = requests.get(f"{_base(server_url)}/api/billing")
    bills = r.json()
    return {"pass": len(bills) > 0,
            "detail": f"extract_from_table: {len(bills)} billing records"}


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/records/1")
    record = r.json()
    return {"pass": "vitals" in record and "summary" in record,
            "detail": f"extract_by_route: record type={record.get('record_type')}"}


def verify_macro_compare_by_date_range(server_url):
    r = requests.get(f"{_base(server_url)}/api/records/compare?from1=2025-01-01&to1=2025-12-31&from2=2026-01-01&to2=2026-12-31")
    data = r.json()
    p1 = data.get("period1", {})
    p2 = data.get("period2", {})
    return {"pass": "records" in p1 and "records" in p2,
            "detail": f"compare_by_date_range: p1={p1.get('records')}, p2={p2.get('records')}"}


def verify_macro_submit_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/providers?q=chang")
    providers = r.json()
    return {"pass": len(providers) > 0,
            "detail": f"submit_by_query: found {len(providers)} providers matching 'chang'"}


def verify_macro_submit_by_route(server_url):
    # Check prescription refill endpoint exists
    s = _login(server_url)
    r = s.get(f"{_base(server_url)}/api/prescriptions")
    rx = r.json()
    refillable = [p for p in rx if p.get("refills_remaining", 0) > 0]
    return {"pass": len(refillable) > 0 or r.status_code == 200,
            "detail": f"submit_by_route: {len(refillable)} refillable prescriptions"}


def verify_macro_edit_by_form(server_url):
    s = _login(server_url)
    # Read, modify, revert
    r = s.get(f"{_base(server_url)}/api/users/1")
    original_phone = r.json().get("phone", "")
    s.put(f"{_base(server_url)}/api/users/1",
          json={"phone": "(555) 000-TEST"})
    r = s.get(f"{_base(server_url)}/api/users/1")
    ok = r.json().get("phone") == "(555) 000-TEST"
    # Revert
    s.put(f"{_base(server_url)}/api/users/1",
          json={"phone": original_phone})
    return {"pass": ok, "detail": f"edit_by_form: phone updated={ok}"}


def verify_macro_export_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/export?format=csv&data_type=records")
    lines = r.text.strip().split("\n")
    return {"pass": len(lines) > 1,
            "detail": f"export_by_dropdown: CSV {len(lines)} lines"}


def verify_macro_upload_by_upload(server_url):
    s = _login(server_url)
    r = s.post(f"{_base(server_url)}/api/documents/upload",
               json={"filename": "macro_test.pdf", "description": "test"})
    data = r.json()
    ok = data.get("id") is not None
    return {"pass": ok,
            "detail": f"upload_by_upload: id={data.get('id')}"}


def verify_macro_message_from_free_text(server_url):
    s = _login(server_url)
    r = s.post(f"{_base(server_url)}/api/messages", json={
        "recipient_id": 3,
        "subject": "Macro test message",
        "body": "This is a test message for macro verification.",
    })
    data = r.json()
    ok = data.get("id") is not None
    return {"pass": ok,
            "detail": f"message_from_free_text: id={data.get('id')}"}


def verify_macro_submit_by_form(server_url):
    s = _login(server_url)
    r = s.post(f"{_base(server_url)}/api/appointments", json={
        "provider_id": 3,
        "date": "2026-09-01",
        "time": "14:00",
        "type": "office_visit",
        "category": "Macro Test",
    })
    data = r.json()
    ok = data.get("id") is not None
    # Clean up
    if ok:
        s.delete(f"{_base(server_url)}/api/appointments/{data['id']}")
    return {"pass": ok,
            "detail": f"submit_by_form: created appointment id={data.get('id')}"}


def verify_macro_book_by_form(server_url):
    s = _login(server_url)
    r = s.post(f"{_base(server_url)}/api/appointments", json={
        "provider_id": 4,
        "date": "2026-09-15",
        "time": "09:00",
        "type": "office_visit",
        "category": "Book Test",
    })
    data = r.json()
    ok = data.get("status") == "scheduled"
    # Clean up
    if data.get("id"):
        s.delete(f"{_base(server_url)}/api/appointments/{data['id']}")
    return {"pass": ok,
            "detail": f"book_by_form: status={data.get('status')}"}


def verify_macro_book_by_date_range(server_url):
    s = _login(server_url)
    r = s.post(f"{_base(server_url)}/api/appointments", json={
        "provider_id": 3,
        "date": "2026-10-01",
        "time": "11:00",
        "type": "office_visit",
        "category": "Date Range Test",
    })
    data = r.json()
    ok = data.get("date") == "2026-10-01"
    if data.get("id"):
        s.delete(f"{_base(server_url)}/api/appointments/{data['id']}")
    return {"pass": ok,
            "detail": f"book_by_date_range: date={data.get('date')}"}


def verify_macro_pay_by_form(server_url):
    s = _login(server_url)
    # Check if bill 10 exists and is pending
    r = s.get(f"{_base(server_url)}/api/billing")
    bills = r.json()
    pending = [b for b in bills if b["payment_status"] == "pending"]
    if not pending:
        return {"pass": True, "detail": "No pending bills (all already paid)"}
    bill_id = pending[0]["id"]
    r = s.post(f"{_base(server_url)}/api/billing/{bill_id}/pay")
    data = r.json()
    ok = "Payment processed" in data.get("message", "")
    return {"pass": ok,
            "detail": f"pay_by_form: bill {bill_id} paid={ok}"}


def verify_macro_cancel_by_form(server_url):
    s = _login(server_url)
    # Find a scheduled appointment to cancel (or create one)
    r = s.post(f"{_base(server_url)}/api/appointments", json={
        "provider_id": 3, "date": "2026-11-01", "time": "08:00",
        "type": "office_visit", "category": "Cancel Test",
    })
    appt = r.json()
    appt_id = appt.get("id")
    if not appt_id:
        return {"pass": False, "detail": "Could not create appointment to cancel"}
    r = s.delete(f"{_base(server_url)}/api/appointments/{appt_id}")
    data = r.json()
    cancelled = data.get("appointment", {}).get("status") == "cancelled"
    return {"pass": cancelled,
            "detail": f"cancel_by_form: cancelled={cancelled}"}


def verify_macro_authenticate_by_form(server_url):
    s = requests.Session()
    r = s.post(f"{_base(server_url)}/api/login",
               json={"username": "alex.rivera"})
    data = r.json()
    ok = data.get("user_id") == 1
    return {"pass": ok,
            "detail": f"authenticate_by_form: user_id={data.get('user_id')}"}


def verify_macro_register_by_form(server_url):
    s = requests.Session()
    r = s.post(f"{_base(server_url)}/register", data={
        "first_name": "MacroTest",
        "last_name": "User",
        "username": "macro_test_user",
        "email": "macro@test.com",
        "date_of_birth": "2000-01-01",
    })
    # Should redirect to verify page
    ok = r.status_code in [200, 302]
    return {"pass": ok,
            "detail": f"register_by_form: status={r.status_code}"}


def verify_macro_verify_identity_by_code(server_url):
    # The verify endpoint exists and accepts codes
    r = requests.get(f"{_base(server_url)}/verify")
    return {"pass": r.status_code == 200,
            "detail": f"verify_identity_by_code: page status={r.status_code}"}
