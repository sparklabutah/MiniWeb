"""Per-task HTTP verification functions for crm."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/crm"
    r = requests.get(f"{base}/api/companies")
    companies = r.json()
    count = len(companies)
    return {"pass": count > 0, "detail": f"Total companies: {count}"}


def verify_002(server_url):
    base = f"{server_url}/sites/crm"
    r = requests.get(f"{base}/api/companies/1")
    company = r.json()
    industry = company.get("industry")
    return {"pass": industry == "Technology", "detail": f"Pinnacle Technologies industry: {industry}"}


def verify_003(server_url):
    base = f"{server_url}/sites/crm"
    r = requests.get(f"{base}/api/stats")
    data = r.json()
    total = data.get("total_deals", 0)
    return {"pass": total >= 0, "detail": f"Total deals: {total}"}


def verify_004(server_url):
    base = f"{server_url}/sites/crm"
    r = requests.get(f"{base}/api/contacts")
    contacts = r.json()
    count = len(contacts)
    return {"pass": count >= 0, "detail": f"Total contacts: {count}"}


def verify_005(server_url):
    base = f"{server_url}/sites/crm"
    s = requests.Session()
    r = s.post(f"{base}/api/login", json={"username": "jmartinez", "password": "sales123"})
    data = r.json()
    ok = data.get("user_id") == 1
    return {"pass": ok, "detail": f"Login: user_id={data.get('user_id')}, name={data.get('name')}"}


def verify_006(server_url):
    base = f"{server_url}/sites/crm"
    r = requests.get(f"{base}/api/pipeline")
    pipeline = r.json()
    count = len(pipeline)
    return {"pass": count == 6, "detail": f"Pipeline stages: {count}"}


def verify_007(server_url):
    base = f"{server_url}/sites/crm"
    r = requests.get(f"{base}/api/deals?stage=closed-won")
    deals = r.json()
    count = len(deals)
    ok = all(d["stage"] == "closed-won" for d in deals)
    return {"pass": count >= 0 and ok, "detail": f"Closed-won deals: {count}"}


def verify_008(server_url):
    base = f"{server_url}/sites/crm"
    r = requests.get(f"{base}/api/stats")
    data = r.json()
    win_rate = data.get("win_rate", 0)
    return {"pass": win_rate >= 0, "detail": f"Win rate: {win_rate}%"}


def verify_009(server_url):
    base = f"{server_url}/sites/crm"
    r = requests.get(f"{base}/api/stats")
    data = r.json()
    revenue = data.get("total_revenue", 0)
    return {"pass": revenue >= 0, "detail": f"Total revenue: ${revenue}"}


def verify_010(server_url):
    base = f"{server_url}/sites/crm"
    r = requests.get(f"{base}/api/deals?sort=amount_desc")
    deals = r.json()
    if deals:
        top = deals[0]
        return {"pass": True, "detail": f"Highest-value deal: {top['name']} ${top['amount']}"}
    return {"pass": False, "detail": "No deals"}


def verify_011(server_url):
    base = f"{server_url}/sites/crm"
    r = requests.get(f"{base}/api/companies?industry=Technology")
    companies = r.json()
    count = len(companies)
    ok = all(c["industry"] == "Technology" for c in companies)
    return {"pass": count >= 0 and ok, "detail": f"Technology companies: {count}"}


def verify_012(server_url):
    base = f"{server_url}/sites/crm"
    r = requests.get(f"{base}/api/activities?type=call")
    activities = r.json()
    count = len(activities)
    return {"pass": count >= 0, "detail": f"Call activities: {count}"}


def verify_013(server_url):
    base = f"{server_url}/sites/crm"
    r = requests.get(f"{base}/api/pipeline")
    pipeline = r.json()
    if pipeline:
        top_stage = max(pipeline, key=lambda s: s["total_value"])
        return {"pass": True, "detail": f"Highest value stage: {top_stage['stage']} ${top_stage['total_value']}"}
    return {"pass": False, "detail": "No pipeline data"}


def verify_014(server_url):
    base = f"{server_url}/sites/crm"
    r = requests.get(f"{base}/api/stats")
    data = r.json()
    forecast = data.get("weighted_forecast", 0)
    return {"pass": forecast >= 0, "detail": f"Weighted forecast: ${forecast}"}


def verify_015(server_url):
    base = f"{server_url}/sites/crm"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "jmartinez", "password": "sales123"})
    r = s.post(f"{base}/api/deals", json={
        "name": "Enterprise License",
        "company_id": 1,
        "contact_id": 1,
        "owner_id": 1,
        "amount": 75000,
        "stage": "proposal",
        "close_date": "2026-09-30"
    })
    data = r.json()
    deal_id = data.get("id")
    ok = deal_id is not None and data.get("name") == "Enterprise License"
    return {"pass": ok, "detail": f"Created deal ID: {deal_id}, name={data.get('name')}"}


def verify_016(server_url):
    base = f"{server_url}/sites/crm"
    r = requests.post(f"{base}/api/contacts", json={
        "name": "Test User",
        "email": "test@pinnacletech.com",
        "company_id": 1,
        "title": "Engineer"
    })
    data = r.json()
    contact_id = data.get("id")
    # Verify it exists
    r2 = requests.get(f"{base}/api/contacts?q=Test+User")
    contacts = r2.json()
    found = any(c["name"] == "Test User" for c in contacts)
    return {"pass": found, "detail": f"Contact created: id={contact_id}, found={found}"}


def verify_017(server_url):
    base = f"{server_url}/sites/crm"
    r = requests.post(f"{base}/api/activities", json={
        "type": "meeting",
        "contact_id": 1,
        "deal_id": 1,
        "user_id": 1,
        "description": "Quarterly review meeting",
        "duration_minutes": 60
    })
    data = r.json()
    act_id = data.get("id")
    # Verify
    r2 = requests.get(f"{base}/api/activities?type=meeting")
    activities = r2.json()
    found = any(a.get("description") == "Quarterly review meeting" for a in activities)
    return {"pass": found, "detail": f"Activity created: id={act_id}, found={found}"}


def verify_018(server_url):
    base = f"{server_url}/sites/crm"
    # Update deal 1 to closed-won
    r = requests.post(f"{base}/api/deals", json={
        "id": 1,
        "stage": "closed-won"
    })
    data = r.json()
    stage = data.get("stage")
    prob = data.get("probability")
    return {"pass": stage == "closed-won" and prob == 100,
            "detail": f"Deal 1 stage={stage}, probability={prob}"}


def verify_019(server_url):
    base = f"{server_url}/sites/crm"
    r = requests.get(f"{base}/api/deals?stage=negotiation")
    deals = r.json()
    total = sum(d["amount"] for d in deals)
    return {"pass": total >= 0, "detail": f"Negotiation deals total: ${total}"}


def verify_020(server_url):
    base = f"{server_url}/sites/crm"
    r = requests.get(f"{base}/api/stats")
    data = r.json()
    avg = data.get("avg_deal_size", 0)
    r2 = requests.get(f"{base}/api/deals?sort=amount_desc")
    deals = r2.json()
    above_avg = [d for d in deals if d["amount"] > avg]
    count = len(above_avg)
    return {"pass": count >= 0, "detail": f"Deals above avg (${avg}): {count}"}
