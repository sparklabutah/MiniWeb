"""Per-task HTTP verification functions for tax-filing-dmv-permits."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/tax-filing-dmv-permits"
    r = requests.get(f"{base}/api/tax-filings?user_id=1")
    filings = r.json()
    count = len(filings)
    return {"pass": count > 0, "detail": f"Alex Rivera has {count} tax filings"}


def verify_002(server_url):
    base = f"{server_url}/sites/tax-filing-dmv-permits"
    r = requests.get(f"{base}/api/tax-filings/1")
    filing = r.json()
    name = filing.get("taxpayer_name", "")
    return {"pass": name == "Alex Rivera", "detail": f"Filing 1 taxpayer: {name}"}


def verify_003(server_url):
    base = f"{server_url}/sites/tax-filing-dmv-permits"
    r = requests.get(f"{base}/api/search?q=property")
    data = r.json()
    total = data.get("total", 0)
    return {"pass": total > 0, "detail": f"Search 'property': {total} results"}


def verify_004(server_url):
    base = f"{server_url}/sites/tax-filing-dmv-permits"
    r = requests.get(f"{base}/api/search/semantic?q=rental+apartment+building")
    data = r.json()
    count = data.get("count", 0)
    return {"pass": count > 0, "detail": f"Semantic search: {count} results"}


def verify_005(server_url):
    base = f"{server_url}/sites/tax-filing-dmv-permits"
    r = requests.get(f"{base}/api/vehicles?body_type=pickup+truck")
    vehicles = r.json()
    count = len(vehicles)
    return {"pass": count > 0, "detail": f"Pickup trucks: {count}"}


def verify_006(server_url):
    base = f"{server_url}/sites/tax-filing-dmv-permits"
    r = requests.get(f"{base}/api/payments?user_id=1&date_from=2025-01-01&date_to=2025-06-30")
    payments = r.json()
    count = len(payments)
    return {"pass": count > 0, "detail": f"Payments 2025 H1 for user 1: {count}"}


def verify_007(server_url):
    base = f"{server_url}/sites/tax-filing-dmv-permits"
    r = requests.get(f"{base}/api/search?q=Honda&category=vehicles")
    data = r.json()
    vehicles = data.get("results", {}).get("vehicles", [])
    if vehicles:
        reg_id = vehicles[0].get("registration_id", "")
        return {"pass": len(reg_id) > 0, "detail": f"Honda vehicle reg_id: {reg_id}"}
    return {"pass": False, "detail": "No Honda vehicle found"}


def verify_008(server_url):
    base = f"{server_url}/sites/tax-filing-dmv-permits"
    r = requests.get(f"{base}/api/search/semantic?q=overdue+late+penalty")
    data = r.json()
    results = data.get("results", [])
    overdue = [item for item in results if item.get("type") == "filing" and item["data"].get("status") == "overdue"]
    if overdue:
        fid = overdue[0]["data"]["filing_id"]
        return {"pass": True, "detail": f"Overdue filing: {fid}"}
    return {"pass": len(results) > 0, "detail": f"Semantic search returned {len(results)} results"}


def verify_009(server_url):
    base = f"{server_url}/sites/tax-filing-dmv-permits"
    r = requests.get(f"{base}/api/tax-filings?user_id=3&type=property_tax")
    filings = r.json()
    count = len(filings)
    return {"pass": count > 0, "detail": f"Carlos property tax filings: {count}"}


def verify_010(server_url):
    base = f"{server_url}/sites/tax-filing-dmv-permits"
    r = requests.get(f"{base}/api/payments")
    payments = r.json()
    total = sum(p.get("amount", 0) for p in payments)
    return {"pass": total > 0, "detail": f"Total payments: ${total:.2f}"}


def verify_011(server_url):
    base = f"{server_url}/sites/tax-filing-dmv-permits"
    r = requests.get(f"{base}/api/vehicles/1")
    vehicle = r.json()
    plate = vehicle.get("plate_number", "")
    return {"pass": plate == "BKT-4921", "detail": f"Vehicle 1 plate: {plate}"}


def verify_012(server_url):
    base = f"{server_url}/sites/tax-filing-dmv-permits"
    r = requests.get(f"{base}/api/tax-filings/compute")
    data = r.json()
    outstanding = data.get("outstanding", 0)
    return {"pass": outstanding > 0, "detail": f"Outstanding tax: ${outstanding:.2f}"}


def verify_013(server_url):
    base = f"{server_url}/sites/tax-filing-dmv-permits"
    r = requests.get(f"{base}/api/stats")
    stats = r.json()
    highest = stats.get("highest_tax_owed_filing")
    if highest:
        amount = highest.get("tax_owed", 0)
        return {"pass": amount > 0, "detail": f"Highest tax owed: ${amount:.2f}"}
    return {"pass": False, "detail": "No highest filing found"}


def verify_014(server_url):
    base = f"{server_url}/sites/tax-filing-dmv-permits"
    r = requests.get(f"{base}/api/tax-filings/compute?min_amount=5000&max_amount=10000")
    data = r.json()
    count = data.get("count", 0)
    return {"pass": count > 0, "detail": f"Filings $5k-$10k: {count}"}


def verify_015(server_url):
    base = f"{server_url}/sites/tax-filing-dmv-permits"
    # Toggle insurance: first read current state
    r = requests.get(f"{base}/api/vehicles/1")
    original = r.json().get("insurance_verified")
    # Toggle
    requests.put(f"{base}/api/vehicles/1", json={"insurance_verified": not original})
    r2 = requests.get(f"{base}/api/vehicles/1")
    new_val = r2.json().get("insurance_verified")
    ok = new_val != original
    # Toggle back
    requests.put(f"{base}/api/vehicles/1", json={"insurance_verified": original})
    return {"pass": ok, "detail": f"Toggle insurance: {original} -> {new_val}"}


def verify_016(server_url):
    base = f"{server_url}/sites/tax-filing-dmv-permits"
    # Login
    s = requests.Session()
    s.post(f"{base}/login", data={"username": "alex.rivera", "password": "pass"})
    # Submit permit
    r = s.post(f"{base}/api/permits", json={
        "type": "Building",
        "applicant_name": "Alex Rivera",
        "address": "500 Pine St, Lakeport, WA 98401",
        "description": "New garage construction",
        "user_id": 1,
    })
    data = r.json()
    ok = r.status_code == 201 and data.get("status") == "pending"
    return {"pass": ok, "detail": f"Permit created: {data.get('permit_id', 'N/A')}"}


def verify_017(server_url):
    base = f"{server_url}/sites/tax-filing-dmv-permits"
    r = requests.put(f"{base}/api/tax-filings/4", json={"notes": "Payment plan requested"})
    data = r.json()
    ok = data.get("notes") == "Payment plan requested"
    return {"pass": ok, "detail": f"Filing 4 notes: {data.get('notes')}"}


def verify_018(server_url):
    base = f"{server_url}/sites/tax-filing-dmv-permits"
    r = requests.post(f"{base}/api/sign", json={"filing_id": 1, "signature": "Alex Rivera"})
    data = r.json()
    ok = data.get("status") == "signed"
    # Verify the filing is now signed
    r2 = requests.get(f"{base}/api/tax-filings/1")
    signed = r2.json().get("signed", False)
    return {"pass": ok and signed, "detail": f"Filing 1 signed: {signed}"}


def verify_019(server_url):
    base = f"{server_url}/sites/tax-filing-dmv-permits"
    r = requests.get(f"{base}/api/export?format=csv&category=filings")
    lines = r.text.strip().split("\n")
    data_rows = len(lines) - 1
    return {"pass": data_rows > 0, "detail": f"CSV export: {data_rows} data rows"}


def verify_020(server_url):
    base = f"{server_url}/sites/tax-filing-dmv-permits"
    r = requests.post(f"{base}/api/appointments", json={
        "service": "Vehicle Registration",
        "date": "2026-07-15",
        "time_slot": "10:00 AM",
        "location": "Lakeport DMV Office",
    })
    data = r.json()
    ok = data.get("status") == "booked" and "appointment_id" in data
    return {"pass": ok, "detail": f"Appointment: {data.get('appointment_id', 'N/A')}"}
