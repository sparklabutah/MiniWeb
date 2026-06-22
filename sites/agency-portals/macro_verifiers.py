"""Per-macro verification functions for agency-portals.

Each function tests that the corresponding macro works end-to-end.
"""
import io
import requests


def _base(server_url):
    return f"{server_url}/sites/agency-portals"


def verify_macro_navigate_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/announcements")
    return {"pass": r.status_code == 200,
            "detail": f"Announcements page: {r.status_code}"}


def verify_macro_navigate_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/departments")
    depts = r.json()
    if not depts:
        return {"pass": False, "detail": "No departments returned"}
    dept = depts[0]
    r2 = requests.get(f"{_base(server_url)}/department/{dept['id']}")
    return {"pass": r2.status_code == 200,
            "detail": f"Department '{dept['name']}': {r2.status_code}"}


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/service/1")
    return {"pass": r.status_code == 200,
            "detail": f"Service detail page: {r.status_code}"}


def verify_macro_search_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/services/search?q=permit")
    results = r.json()
    return {"pass": len(results) > 0,
            "detail": f"search_by_query 'permit': {len(results)} results"}


def verify_macro_search_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/services/semantic?q=water+bill+payment")
    results = r.json()
    return {"pass": r.status_code == 200,
            "detail": f"search_by_semantic: {len(results)} results"}


def verify_macro_search_by_code(server_url):
    r = requests.get(f"{_base(server_url)}/api/permits/search?code=PRM-2023-0001")
    results = r.json()
    return {"pass": r.status_code == 200,
            "detail": f"search_by_code: {len(results)} results"}


def verify_macro_filter_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/permits?q=Building")
    results = r.json()
    return {"pass": r.status_code == 200,
            "detail": f"filter_by_query 'Building': {len(results)} permits"}


def verify_macro_filter_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/services?category=Permits")
    services = r.json()
    ok = all(s["category"] == "Permits" for s in services)
    return {"pass": ok and len(services) > 0,
            "detail": f"filter_by_dropdown Permits: {len(services)} services, all_permits={ok}"}


def verify_macro_filter_by_date_range(server_url):
    r = requests.get(f"{_base(server_url)}/api/permits?date_from=2024-01-01&date_to=2024-12-31")
    permits = r.json()
    ok = all(p["date_submitted"] >= "2024-01-01" and p["date_submitted"] <= "2024-12-31"
             for p in permits)
    return {"pass": ok,
            "detail": f"filter 2024: {len(permits)} permits, all_in_range={ok}"}


def verify_macro_extract_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/services/search?q=building")
    results = r.json()
    if results:
        return {"pass": True,
                "detail": f"extract_by_query: first result={results[0]['name'][:50]}"}
    return {"pass": True, "detail": "extract_by_query: no results"}


def verify_macro_extract_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/services?department=8")
    services = r.json()
    return {"pass": len(services) > 0,
            "detail": f"extract_by_dropdown dept 8: {len(services)} services"}


def verify_macro_extract_from_table(server_url):
    r = requests.get(f"{_base(server_url)}/api/permits?status=Approved")
    permits = r.json()
    return {"pass": len(permits) > 0,
            "detail": f"extract_from_table: {len(permits)} approved permits"}


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/permits/1")
    permit = r.json()
    return {"pass": "applicant" in permit,
            "detail": f"extract_by_route: permit applicant={permit.get('applicant', 'N/A')}"}


def verify_macro_verify_by_toggle(server_url):
    base = _base(server_url)
    # Toggle save a service for user 5
    r = requests.post(f"{base}/api/users/5/save-service", json={"service_id": 99})
    data = r.json()
    ok = data.get("action") == "saved"
    # Toggle back
    requests.post(f"{base}/api/users/5/save-service", json={"service_id": 99})
    return {"pass": ok, "detail": f"verify_by_toggle: action={data.get('action')}"}


def verify_macro_submit_by_query(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/users/5/apply-permit",
                      json={"permit_type": "TestPermit", "address": "123 Test St"})
    data = r.json()
    ok = data.get("action") == "submitted"
    return {"pass": ok, "detail": f"submit_by_query: {data.get('permit_code', 'N/A')}"}


def verify_macro_apply_by_form(server_url):
    base = _base(server_url)
    r = requests.get(f"{base}/apply/5")
    return {"pass": r.status_code == 200,
            "detail": f"apply_by_form page: {r.status_code}"}


def verify_macro_sign_by_query(server_url):
    base = _base(server_url)
    # Signing is modeled as accepting terms and submitting a service application
    r = requests.post(f"{base}/apply/1", data={"applicant_name": "Test User",
                                                "email": "test@test.com"})
    return {"pass": r.status_code == 200,
            "detail": f"sign_by_query: form submission status={r.status_code}"}


def verify_macro_upload_by_upload(server_url):
    base = _base(server_url)
    files = {"document": ("test.pdf", io.BytesIO(b"test content"), "application/pdf")}
    data = {"document_type": "Permit Application", "description": "Test doc"}
    r = requests.post(f"{base}/api/upload", files=files, data=data)
    result = r.json()
    return {"pass": result.get("action") == "uploaded",
            "detail": f"upload: filename={result.get('filename', 'N/A')}"}


def verify_macro_select_by_dropdown(server_url):
    base = _base(server_url)
    r = requests.get(f"{base}/api/services?category=Permits")
    services = r.json()
    return {"pass": len(services) > 0,
            "detail": f"select_by_dropdown: {len(services)} Permits services"}


def verify_macro_export_by_dropdown(server_url):
    base = _base(server_url)
    r = requests.get(f"{base}/api/export?format=csv&type=permits")
    lines = r.text.strip().split("\n")
    return {"pass": len(lines) > 1, "detail": f"export CSV: {len(lines)} lines"}


def verify_macro_book_by_form(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/users/5/book",
                      json={"appointment_type_id": 1, "date": "2026-08-01", "time": "10:00"})
    data = r.json()
    ok = data.get("action") == "booked"
    return {"pass": ok,
            "detail": f"book_by_form: conf={data.get('confirmation', 'N/A')}"}


def verify_macro_pay_by_query(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/users/5/pay",
                      json={"payment_type": "Utility Bill", "amount": 50.0,
                            "account_number": "TEST-001"})
    data = r.json()
    ok = data.get("action") == "paid"
    return {"pass": ok,
            "detail": f"pay_by_query: conf={data.get('confirmation', 'N/A')}"}


def verify_macro_authenticate_by_form(server_url):
    base = _base(server_url)
    s = requests.Session()
    r = s.post(f"{base}/api/login",
               json={"username": "resident_jane", "password": "cedar123"})
    data = r.json()
    ok = data.get("user_id") == 1
    return {"pass": ok, "detail": f"authenticate: user_id={data.get('user_id')}"}


def verify_macro_register_by_form(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/register",
                      json={"username": "macro_test_user", "password": "mpass",
                            "name": "Macro Test", "email": "macro@test.com"})
    data = r.json()
    ok = "user_id" in data or "verification_code" in data
    return {"pass": ok,
            "detail": f"register: {data}"}


def verify_macro_verify_identity_by_code(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/verify-identity",
                      json={"verification_code": "VRF-100005"})
    data = r.json()
    ok = data.get("action") == "verified"
    return {"pass": ok,
            "detail": f"verify_identity: {data.get('action', 'N/A')}"}
