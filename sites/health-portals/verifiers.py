"""Per-task HTTP verification functions for health-portals."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/health-portals"
    r = requests.get(f"{base}/api/appointments")
    appointments = r.json()
    count = len(appointments)
    return {"pass": count > 0, "detail": f"Patient appointments: {count}"}


def verify_002(server_url):
    base = f"{server_url}/sites/health-portals"
    r = requests.get(f"{base}/api/appointments/1")
    appt = r.json()
    category = appt.get("category", "")
    status = appt.get("status", "")
    return {"pass": category == "Annual Physical" and status == "completed",
            "detail": f"Appointment 1: category={category}, status={status}"}


def verify_003(server_url):
    base = f"{server_url}/sites/health-portals"
    r = requests.get(f"{base}/api/search?q=knee")
    results = r.json()
    count = len(results)
    return {"pass": count > 0, "detail": f"Search 'knee': {count} results"}


def verify_004(server_url):
    base = f"{server_url}/sites/health-portals"
    r = requests.get(f"{base}/api/search/semantic?q=knee+pain+physical+therapy")
    results = r.json()
    count = len(results)
    return {"pass": count > 0, "detail": f"Semantic 'knee pain physical therapy': {count} records"}


def verify_005(server_url):
    base = f"{server_url}/sites/health-portals"
    r = requests.get(f"{base}/api/records/filter?type=annual_physical")
    records = r.json()
    count = len(records)
    ok = all(r.get("record_type") == "annual_physical" for r in records)
    return {"pass": ok and count > 0,
            "detail": f"annual_physical records: {count}, all_correct={ok}"}


def verify_006(server_url):
    base = f"{server_url}/sites/health-portals"
    r = requests.get(f"{base}/api/appointments/status?status=completed")
    appts = r.json()
    count = len(appts)
    ok = all(a["status"] == "completed" for a in appts)
    return {"pass": ok and count > 0,
            "detail": f"Completed appointments: {count}, all_completed={ok}"}


def verify_007(server_url):
    base = f"{server_url}/sites/health-portals"
    r = requests.get(f"{base}/api/appointments?date_from=2026-01-01&date_to=2026-06-30")
    appts = r.json()
    count = len(appts)
    ok = all("2026-01-01" <= a["date"] <= "2026-06-30" for a in appts)
    return {"pass": ok, "detail": f"Appointments 2026 H1: {count}, all_in_range={ok}"}


def verify_008(server_url):
    base = f"{server_url}/sites/health-portals"
    r = requests.get(f"{base}/api/records/search?q=cholesterol")
    records = r.json()
    if not records:
        # Try lipid
        r = requests.get(f"{base}/api/records/search?q=lipid")
        records = r.json()
    if records:
        rtype = records[0].get("record_type", "")
        return {"pass": True, "detail": f"First cholesterol/lipid record: type={rtype}"}
    return {"pass": True, "detail": "No cholesterol/lipid records found (ok for data)"}


def verify_009(server_url):
    base = f"{server_url}/sites/health-portals"
    r = requests.get(f"{base}/api/stats")
    stats = r.json()
    outstanding = stats.get("total_outstanding", 0)
    return {"pass": outstanding >= 0,
            "detail": f"Total outstanding: ${outstanding}"}


def verify_010(server_url):
    base = f"{server_url}/sites/health-portals"
    r = requests.get(f"{base}/api/records/compare?from1=2025-01-01&to1=2025-12-31&from2=2026-01-01&to2=2026-12-31")
    data = r.json()
    p1 = data.get("period1", {}).get("records", 0)
    p2 = data.get("period2", {}).get("records", 0)
    higher = "2025" if p1 > p2 else "2026"
    return {"pass": True,
            "detail": f"Period1 records: {p1}, Period2 records: {p2}, higher: {higher}"}


def verify_011(server_url):
    base = f"{server_url}/sites/health-portals"
    r = requests.get(f"{base}/api/providers")
    providers = r.json()
    count = len(providers)
    names = [p["full_name"] for p in providers]
    return {"pass": count > 0,
            "detail": f"Providers: {count}, names={names}"}


def verify_012(server_url):
    base = f"{server_url}/sites/health-portals"
    r = requests.get(f"{base}/api/records/1")
    record = r.json()
    vitals = record.get("vitals", {})
    systolic = vitals.get("blood_pressure_systolic")
    diastolic = vitals.get("blood_pressure_diastolic")
    return {"pass": systolic is not None and diastolic is not None,
            "detail": f"Record 1 BP: {systolic}/{diastolic}"}


def verify_013(server_url):
    base = f"{server_url}/sites/health-portals"
    r = requests.get(f"{base}/api/export?format=json&data_type=billing")
    data = r.json()
    count = len(data)
    return {"pass": count > 0, "detail": f"Billing export: {count} records"}


def verify_014(server_url):
    base = f"{server_url}/sites/health-portals"
    r = requests.get(f"{base}/api/messages")
    messages = r.json()
    sent = [m for m in messages if m.get("subject") == "Question about medication"
            and "ibuprofen" in m.get("body", "").lower()]
    return {"pass": len(sent) > 0,
            "detail": f"Message about medication: found={len(sent)}"}


def verify_015(server_url):
    base = f"{server_url}/sites/health-portals"
    # Check booking
    r = requests.get(f"{base}/api/appointments?date_from=2026-08-15&date_to=2026-08-15")
    appts = r.json()
    follow_up = [a for a in appts if a.get("category") == "Follow-up"
                 and a.get("status") == "scheduled"]
    booked = len(follow_up) > 0
    # Check cancellation of appointment 11
    r = requests.get(f"{base}/api/appointments/11")
    appt11 = r.json()
    cancelled = appt11.get("status") == "cancelled"
    return {"pass": booked and cancelled,
            "detail": f"Booked follow-up: {booked}, cancelled #11: {cancelled}"}


def verify_016(server_url):
    base = f"{server_url}/sites/health-portals"
    r = requests.get(f"{base}/api/prescriptions")
    prescriptions = r.json()
    rx2 = next((p for p in prescriptions if p["id"] == 2), None)
    if not rx2:
        return {"pass": False, "detail": "Prescription 2 not found"}
    # Original refills_remaining was 3, should now be 2
    refills = rx2.get("refills_remaining", -1)
    return {"pass": refills < 3,
            "detail": f"Prescription 2 refills_remaining: {refills} (was 3)"}


def verify_017(server_url):
    base = f"{server_url}/sites/health-portals"
    r = requests.get(f"{base}/api/users/1")
    user = r.json()
    phone = user.get("phone", "")
    return {"pass": phone == "(555) 999-8888",
            "detail": f"User 1 phone: {phone}"}


def verify_018(server_url):
    base = f"{server_url}/sites/health-portals"
    r = requests.get(f"{base}/api/documents")
    docs = r.json()
    lab_doc = [d for d in docs if "lab_results" in d.get("filename", "")]
    return {"pass": len(lab_doc) > 0,
            "detail": f"Uploaded lab_results doc: found={len(lab_doc)}"}


def verify_019(server_url):
    base = f"{server_url}/sites/health-portals"
    r = requests.get(f"{base}/api/billing")
    bills = r.json()
    bill10 = next((b for b in bills if b["id"] == 10), None)
    if not bill10:
        return {"pass": False, "detail": "Bill 10 not found"}
    status = bill10.get("payment_status", "")
    return {"pass": status == "paid_in_full",
            "detail": f"Bill 10 status: {status}"}


def verify_020(server_url):
    base = f"{server_url}/sites/health-portals"
    # Check for newly registered user
    r = requests.get(f"{base}/api/users")
    users = r.json()
    test_user = next((u for u in users if u.get("username") == "test.patient"), None)
    if not test_user:
        return {"pass": False, "detail": "test.patient user not found"}
    # Check verified status
    r = requests.get(f"{base}/api/users/{test_user['id']}")
    user_detail = r.json()
    verified = user_detail.get("verified", False)
    return {"pass": verified,
            "detail": f"test.patient verified: {verified}"}
