"""Per-macro verification functions for tax-filing-dmv-permits.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/tax-filing-dmv-permits"


def verify_macro_navigate_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/tax-filings")
    return {"pass": r.status_code == 200, "detail": f"Tax filings page: {r.status_code}"}


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/tax-filing/1")
    return {"pass": r.status_code == 200, "detail": f"Filing detail page: {r.status_code}"}


def verify_macro_search_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/search?q=Rivera")
    data = r.json()
    return {"pass": data["total"] > 0, "detail": f"search 'Rivera': {data['total']} results"}


def verify_macro_search_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/search/semantic?q=property+tax+building")
    data = r.json()
    return {"pass": data["count"] > 0, "detail": f"semantic search: {data['count']} results"}


def verify_macro_filter_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/tax-filings?type=income_tax")
    filings = r.json()
    ok = all(f["type"] == "income_tax" for f in filings)
    return {"pass": ok and len(filings) > 0, "detail": f"filter income_tax: {len(filings)} filings, all_match={ok}"}


def verify_macro_filter_by_date_range(server_url):
    r = requests.get(f"{_base(server_url)}/api/payments?date_from=2025-01-01&date_to=2025-12-31")
    payments = r.json()
    ok = all("2025" in p["payment_date"] for p in payments if p.get("payment_date"))
    return {"pass": ok and len(payments) > 0, "detail": f"filter 2025: {len(payments)} payments"}


def verify_macro_extract_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/search?q=Honda")
    data = r.json()
    return {"pass": data["total"] > 0, "detail": f"extract 'Honda': {data['total']} results"}


def verify_macro_extract_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/search/semantic?q=overdue+penalty")
    data = r.json()
    return {"pass": data["count"] > 0, "detail": f"semantic 'overdue penalty': {data['count']} results"}


def verify_macro_extract_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/tax-filings?type=property_tax")
    filings = r.json()
    return {"pass": len(filings) > 0, "detail": f"extract property_tax: {len(filings)} filings"}


def verify_macro_extract_from_table(server_url):
    r = requests.get(f"{_base(server_url)}/api/payments")
    payments = r.json()
    total = sum(p["amount"] for p in payments)
    return {"pass": total > 0, "detail": f"extract from payments table: total=${total:.2f}"}


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/vehicles/1")
    vehicle = r.json()
    return {"pass": "plate_number" in vehicle, "detail": f"extract vehicle 1: plate={vehicle.get('plate_number')}"}


def verify_macro_compute_from_table(server_url):
    r = requests.get(f"{_base(server_url)}/api/tax-filings/compute")
    data = r.json()
    return {"pass": "outstanding" in data, "detail": f"compute: outstanding=${data.get('outstanding', 0):.2f}"}


def verify_macro_compute_by_extremum(server_url):
    r = requests.get(f"{_base(server_url)}/api/stats")
    stats = r.json()
    highest = stats.get("highest_tax_owed_filing")
    return {"pass": highest is not None, "detail": f"extremum: highest=${highest.get('tax_owed', 0) if highest else 0:.2f}"}


def verify_macro_compute_by_slider(server_url):
    r = requests.get(f"{_base(server_url)}/api/tax-filings/compute?min_amount=1000&max_amount=5000")
    data = r.json()
    return {"pass": "count" in data, "detail": f"slider $1k-$5k: {data.get('count')} filings"}


def verify_macro_verify_by_toggle(server_url):
    base = _base(server_url)
    r = requests.get(f"{base}/api/vehicles/1")
    original = r.json()["insurance_verified"]
    requests.put(f"{base}/api/vehicles/1", json={"insurance_verified": not original})
    r2 = requests.get(f"{base}/api/vehicles/1")
    toggled = r2.json()["insurance_verified"]
    # Toggle back
    requests.put(f"{base}/api/vehicles/1", json={"insurance_verified": original})
    return {"pass": toggled != original, "detail": f"toggle insurance: {original} -> {toggled}"}


def verify_macro_submit_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/tax-filings/search?q=Rivera")
    results = r.json()
    return {"pass": len(results) > 0, "detail": f"submit search query: {len(results)} results"}


def verify_macro_submit_by_form(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/permits", json={
        "type": "Building", "applicant_name": "Test User",
        "address": "Test Address", "description": "Test permit",
        "user_id": 1,
    })
    ok = r.status_code == 201
    return {"pass": ok, "detail": f"submit form: {r.status_code}"}


def verify_macro_edit_by_query(server_url):
    base = _base(server_url)
    r = requests.put(f"{base}/api/tax-filings/1", json={"notes": "Test note"})
    data = r.json()
    ok = data.get("notes") == "Test note"
    # Clean up
    requests.put(f"{base}/api/tax-filings/1", json={"notes": None})
    return {"pass": ok, "detail": f"edit by query: notes={data.get('notes')}"}


def verify_macro_apply_by_form(server_url):
    r = requests.get(f"{_base(server_url)}/apply-permit")
    return {"pass": r.status_code == 200, "detail": f"apply permit page: {r.status_code}"}


def verify_macro_sign_by_signature(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/sign", json={"filing_id": 2, "signature": "Test User"})
    data = r.json()
    ok = data.get("status") == "signed"
    return {"pass": ok, "detail": f"sign: status={data.get('status')}"}


def verify_macro_select_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/vehicles?body_type=sedan")
    vehicles = r.json()
    return {"pass": len(vehicles) > 0, "detail": f"select sedan: {len(vehicles)} vehicles"}


def verify_macro_select_by_date_range(server_url):
    r = requests.get(f"{_base(server_url)}/api/permits?date_from=2025-01-01&date_to=2026-12-31")
    permits = r.json()
    return {"pass": len(permits) > 0, "detail": f"select date range: {len(permits)} permits"}


def verify_macro_export_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/export?format=csv&category=filings")
    lines = r.text.strip().split("\n")
    return {"pass": len(lines) > 1, "detail": f"export CSV: {len(lines)} lines"}


def verify_macro_upload_by_upload(server_url):
    base = _base(server_url)
    files = {"file": ("test.txt", b"test content", "text/plain")}
    r = requests.post(f"{base}/api/upload", files=files)
    data = r.json()
    return {"pass": data.get("status") == "uploaded", "detail": f"upload: {data.get('filename')}"}


def verify_macro_book_by_date_range(server_url):
    r = requests.post(f"{_base(server_url)}/api/appointments", json={
        "date": "2026-08-01", "time_slot": "9:00 AM",
        "service": "License Renewal",
    })
    data = r.json()
    return {"pass": data.get("status") == "booked", "detail": f"book: {data.get('appointment_id')}"}


def verify_macro_pay_by_form(server_url):
    r = requests.post(f"{_base(server_url)}/api/payments", json={
        "type": "income_tax", "amount": 100.00,
        "method": "credit_card", "card_last_four": "9999",
        "user_id": 1, "payer_name": "Test",
    })
    data = r.json()
    ok = data.get("status") == "completed"
    return {"pass": ok, "detail": f"pay: confirmation={data.get('confirmation_number')}"}


def verify_macro_authenticate_by_form(server_url):
    base = _base(server_url)
    s = requests.Session()
    r = s.post(f"{base}/login", data={"username": "alex.rivera", "password": "pass"})
    ok = r.status_code in (200, 302)
    return {"pass": ok, "detail": f"login: status={r.status_code}"}


def verify_macro_verify_identity_by_code(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/verify-identity", json={"code": "000000", "user_id": 1})
    # This should fail with wrong code
    fail = r.status_code == 400
    # Now test with correct code: we need to compute it
    import hashlib
    seed = "lakeport-verify-1-2026"
    h = hashlib.sha256(seed.encode()).hexdigest()
    correct_code = str(int(h[:8], 16) % 900000 + 100000)
    r2 = requests.post(f"{base}/api/verify-identity", json={"code": correct_code, "user_id": 1})
    data = r2.json()
    ok = data.get("status") == "verified"
    return {"pass": fail and ok, "detail": f"verify identity: wrong=rejected, correct=verified"}
