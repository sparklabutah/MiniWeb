"""Per-task reference solutions via Flask test client for health-portals."""
import json


def solve_001(client, base="/sites/health-portals"):
    r = client.get(f"{base}/api/appointments")
    appointments = json.loads(r.data)
    return str(len(appointments))


def solve_002(client, base="/sites/health-portals"):
    r = client.get(f"{base}/api/appointments/1")
    appt = json.loads(r.data)
    return f"{appt['category']}, {appt['status']}"


def solve_003(client, base="/sites/health-portals"):
    r = client.get(f"{base}/api/search?q=knee")
    return str(len(json.loads(r.data)))


def solve_004(client, base="/sites/health-portals"):
    r = client.get(f"{base}/api/search/semantic?q=knee+pain+physical+therapy")
    return str(len(json.loads(r.data)))


def solve_005(client, base="/sites/health-portals"):
    r = client.get(f"{base}/api/records/filter?type=annual_physical")
    return str(len(json.loads(r.data)))


def solve_006(client, base="/sites/health-portals"):
    r = client.get(f"{base}/api/appointments/status?status=completed")
    return str(len(json.loads(r.data)))


def solve_007(client, base="/sites/health-portals"):
    r = client.get(f"{base}/api/appointments?date_from=2026-01-01&date_to=2026-06-30")
    return str(len(json.loads(r.data)))


def solve_008(client, base="/sites/health-portals"):
    r = client.get(f"{base}/api/records/search?q=cholesterol")
    records = json.loads(r.data)
    if not records:
        r = client.get(f"{base}/api/records/search?q=lipid")
        records = json.loads(r.data)
    return records[0]["record_type"] if records else "not found"


def solve_009(client, base="/sites/health-portals"):
    r = client.get(f"{base}/api/stats")
    stats = json.loads(r.data)
    return f"${stats['total_outstanding']:.2f}"


def solve_010(client, base="/sites/health-portals"):
    r = client.get(f"{base}/api/records/compare?from1=2025-01-01&to1=2025-12-31&from2=2026-01-01&to2=2026-12-31")
    data = json.loads(r.data)
    p1 = data["period1"]["records"]
    p2 = data["period2"]["records"]
    return "2025" if p1 > p2 else "2026"


def solve_011(client, base="/sites/health-portals"):
    r = client.get(f"{base}/api/providers")
    providers = json.loads(r.data)
    names = [p["full_name"] for p in providers]
    return f"{len(providers)} providers: {', '.join(names)}"


def solve_012(client, base="/sites/health-portals"):
    r = client.get(f"{base}/api/records/1")
    record = json.loads(r.data)
    vitals = record.get("vitals", {})
    return f"{vitals['blood_pressure_systolic']}/{vitals['blood_pressure_diastolic']}"


def solve_013(client, base="/sites/health-portals"):
    r = client.get(f"{base}/api/export?format=json&data_type=billing")
    return str(len(json.loads(r.data)))


def solve_014(client, base="/sites/health-portals"):
    # Login
    client.post(f"{base}/api/login", json={"username": "alex.rivera"})
    # Send message
    r = client.post(f"{base}/api/messages", json={
        "recipient_id": 3,
        "subject": "Question about medication",
        "body": "Hi Dr. Chang, I had a question about my ibuprofen dosage. Can I take it with food only?",
    })
    msg = json.loads(r.data)
    return f"sent: id={msg.get('id')}"


def solve_015(client, base="/sites/health-portals"):
    client.post(f"{base}/api/login", json={"username": "alex.rivera"})
    # Book appointment
    r = client.post(f"{base}/api/appointments", json={
        "provider_id": 3,
        "date": "2026-08-15",
        "time": "10:00",
        "type": "office_visit",
        "category": "Follow-up",
    })
    appt = json.loads(r.data)
    # Cancel appointment 11
    r = client.delete(f"{base}/api/appointments/11")
    cancel_data = json.loads(r.data)
    return f"booked: id={appt.get('id')}, cancelled: {cancel_data.get('appointment', {}).get('status')}"


def solve_016(client, base="/sites/health-portals"):
    client.post(f"{base}/api/login", json={"username": "alex.rivera"})
    r = client.post(f"{base}/api/prescriptions/2/refill")
    data = json.loads(r.data)
    return data.get("message", data.get("error", ""))


def solve_017(client, base="/sites/health-portals"):
    client.post(f"{base}/api/login", json={"username": "alex.rivera"})
    client.put(f"{base}/api/users/1", json={"phone": "(555) 999-8888"})
    r = client.get(f"{base}/api/users/1")
    user = json.loads(r.data)
    return user.get("phone", "")


def solve_018(client, base="/sites/health-portals"):
    client.post(f"{base}/api/login", json={"username": "alex.rivera"})
    r = client.post(f"{base}/api/documents/upload", json={
        "filename": "lab_results_2026.pdf",
        "description": "Annual blood work results",
    })
    doc = json.loads(r.data)
    return f"uploaded: {doc.get('filename')}"


def solve_019(client, base="/sites/health-portals"):
    client.post(f"{base}/api/login", json={"username": "alex.rivera"})
    r = client.post(f"{base}/api/billing/10/pay")
    data = json.loads(r.data)
    return data.get("message", data.get("error", ""))


def solve_020(client, base="/sites/health-portals"):
    # Register
    r = client.post(f"{base}/register", data={
        "first_name": "Test",
        "last_name": "Patient",
        "username": "test.patient",
        "email": "test@example.com",
        "date_of_birth": "1990-05-15",
        "gender": "other",
        "phone": "(555) 000-0000",
    }, follow_redirects=True)
    # The verification page shows the code
    # Get the code from the session/page
    r = client.get(f"{base}/verify")
    html = r.data.decode()
    # Extract code from the page (it's displayed as code_hint)
    import re
    code_match = re.search(r'class="code-display">\s*(\d{6})', html)
    if code_match:
        code = code_match.group(1)
        r = client.post(f"{base}/verify", data={"code": code}, follow_redirects=True)
        return f"verified with code {code}"
    return "could not extract code"
