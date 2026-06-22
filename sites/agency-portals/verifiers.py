"""Per-task HTTP verification functions for agency-portals."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/agency-portals"
    r = requests.get(f"{base}/api/departments/1")
    dept = r.json()
    phone = dept.get("phone", "")
    return {"pass": phone == "(555) 234-0100",
            "detail": f"Public Works phone: {phone}"}


def verify_002(server_url):
    base = f"{server_url}/sites/agency-portals"
    r = requests.get(f"{base}/api/services/5")
    service = r.json()
    fee = service.get("fee", 0)
    return {"pass": fee == 150.0,
            "detail": f"Building Permit Application fee: ${fee}"}


def verify_003(server_url):
    base = f"{server_url}/sites/agency-portals"
    r = requests.get(f"{base}/api/services/search?q=utility")
    results = r.json()
    count = len(results)
    return {"pass": count > 0, "detail": f"Search 'utility': {count} services"}


def verify_004(server_url):
    base = f"{server_url}/sites/agency-portals"
    r = requests.get(f"{base}/api/services/semantic?q=paying+bills+and+taxes")
    results = r.json()
    count = len(results)
    return {"pass": count > 0, "detail": f"Semantic 'paying bills and taxes': {count} services"}


def verify_005(server_url):
    base = f"{server_url}/sites/agency-portals"
    r = requests.get(f"{base}/api/permits/search?code=PRM-2023-0001")
    results = r.json()
    if not results:
        return {"pass": False, "detail": "No permit found with code PRM-2023-0001"}
    status = results[0].get("status", "")
    return {"pass": len(status) > 0,
            "detail": f"Permit PRM-2023-0001 status: {status}"}


def verify_006(server_url):
    base = f"{server_url}/sites/agency-portals"
    r = requests.get(f"{base}/api/announcements")
    announcements = r.json()
    if not announcements:
        return {"pass": False, "detail": "No announcements found"}
    title = announcements[0].get("title", "")
    return {"pass": len(title) > 0, "detail": f"First announcement: {title}"}


def verify_007(server_url):
    base = f"{server_url}/sites/agency-portals"
    r = requests.get(f"{base}/api/services?category=Permits")
    services = r.json()
    count = len(services)
    return {"pass": count > 0, "detail": f"Permits category: {count} services"}


def verify_008(server_url):
    base = f"{server_url}/sites/agency-portals"
    r = requests.get(f"{base}/api/permits/search?q=Building")
    results = r.json()
    count = len(results)
    return {"pass": count > 0, "detail": f"Search 'Building': {count} permits"}


def verify_009(server_url):
    base = f"{server_url}/sites/agency-portals"
    r = requests.get(f"{base}/api/permits?date_from=2025-01-01&date_to=2025-12-31")
    permits = r.json()
    count = len(permits)
    ok = all("2025" in p["date_submitted"] for p in permits)
    return {"pass": count >= 0 and ok,
            "detail": f"2025 permits: {count}, all_in_range={ok}"}


def verify_010(server_url):
    base = f"{server_url}/sites/agency-portals"
    r = requests.get(f"{base}/api/services/search?q=SVC-BLD")
    results = r.json()
    if not results:
        return {"pass": False, "detail": "No service found for SVC-BLD"}
    name = results[0].get("name", "")
    return {"pass": "Building Permit" in name,
            "detail": f"SVC-BLD service name: {name}"}


def verify_011(server_url):
    base = f"{server_url}/sites/agency-portals"
    r = requests.get(f"{base}/api/services?department=8")
    services = r.json()
    count = len(services)
    return {"pass": count > 0, "detail": f"Clerk & Records services: {count}"}


def verify_012(server_url):
    base = f"{server_url}/sites/agency-portals"
    r = requests.get(f"{base}/api/permits?status=Approved")
    permits = r.json()
    count = len(permits)
    return {"pass": count > 0, "detail": f"Approved permits: {count}"}


def verify_013(server_url):
    base = f"{server_url}/sites/agency-portals"
    r = requests.get(f"{base}/api/permits/1")
    permit = r.json()
    applicant = permit.get("applicant", "")
    return {"pass": len(applicant) > 0,
            "detail": f"Permit 1 applicant: {applicant}"}


def verify_014(server_url):
    base = f"{server_url}/sites/agency-portals"
    r = requests.get(f"{base}/api/export?format=csv&type=permits")
    lines = r.text.strip().split("\n")
    data_rows = len(lines) - 1
    return {"pass": data_rows > 0, "detail": f"CSV export permits: {data_rows} data rows"}


def verify_015(server_url):
    base = f"{server_url}/sites/agency-portals"
    # Login and save service
    s = requests.Session()
    s.post(f"{base}/api/login",
           json={"username": "resident_jane", "password": "cedar123"})
    s.post(f"{base}/api/users/1/save-service", json={"service_id": 5})
    r = requests.get(f"{base}/api/users/1")
    user = r.json()
    saved = user.get("saved_services", [])
    return {"pass": 5 in saved, "detail": f"User 1 saved services: {saved}"}


def verify_016(server_url):
    base = f"{server_url}/sites/agency-portals"
    r = requests.get(f"{base}/api/users/2")
    user = r.json()
    payments = user.get("payments", [])
    has_payment = any(p.get("type") == "Property Tax" and
                      float(p.get("amount", 0)) == 150.0
                      for p in payments)
    return {"pass": has_payment,
            "detail": f"User 2 payments: {len(payments)} total, property_tax_150={has_payment}"}


def verify_017(server_url):
    base = f"{server_url}/sites/agency-portals"
    r = requests.get(f"{base}/api/users/1")
    user = r.json()
    permits = user.get("permits", [])
    has_building = any(p.get("type") == "Building" for p in permits)
    if permits:
        code = permits[-1].get("code", "")
    else:
        code = ""
    return {"pass": has_building,
            "detail": f"User 1 permits: {len(permits)}, building={has_building}, last_code={code}"}


def verify_018(server_url):
    base = f"{server_url}/sites/agency-portals"
    r = requests.get(f"{base}/api/services")
    # Check if user was created via register API
    s = requests.Session()
    r = s.post(f"{base}/api/login",
               json={"username": "test_citizen", "password": "testpass"})
    if r.status_code == 200:
        data = r.json()
        user_id = data.get("user_id")
        r2 = requests.get(f"{base}/api/users/{user_id}")
        user = r2.json()
        code = user.get("verification_code", "")
        return {"pass": len(code) > 0,
                "detail": f"Registered user test_citizen, verification_code={code}"}
    return {"pass": False, "detail": "User test_citizen not found after registration"}


def verify_019(server_url):
    base = f"{server_url}/sites/agency-portals"
    r = requests.get(f"{base}/api/users/3")
    user = r.json()
    verified = user.get("verified", False)
    return {"pass": verified,
            "detail": f"User business_lisa verified: {verified}"}


def verify_020(server_url):
    base = f"{server_url}/sites/agency-portals"
    r = requests.get(f"{base}/api/users/4")
    user = r.json()
    appointments = user.get("appointments", [])
    has_appt = any(a.get("type") == "Building Permit Consultation" and
                   a.get("date") == "2026-07-15"
                   for a in appointments)
    conf = appointments[-1].get("confirmation", "") if appointments else ""
    return {"pass": has_appt,
            "detail": f"User 4 appointments: {len(appointments)}, building_consult={has_appt}, conf={conf}"}
