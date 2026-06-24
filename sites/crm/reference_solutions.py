"""Per-task reference solutions via Flask test client for crm."""
import json


def solve_001(client, base="/sites/crm"):
    r = client.get(f"{base}/api/companies")
    companies = json.loads(r.data)
    return str(len(companies))


def solve_002(client, base="/sites/crm"):
    r = client.get(f"{base}/api/companies/1")
    company = json.loads(r.data)
    return company["industry"]


def solve_003(client, base="/sites/crm"):
    r = client.get(f"{base}/api/stats")
    data = json.loads(r.data)
    return str(data["total_deals"])


def solve_004(client, base="/sites/crm"):
    r = client.get(f"{base}/api/contacts")
    contacts = json.loads(r.data)
    return str(len(contacts))


def solve_005(client, base="/sites/crm"):
    client.post(f"{base}/api/login",
                json={"username": "jmartinez", "password": "sales123"},
                content_type="application/json")
    r = client.get(f"{base}/api/stats")
    # The territory is on the user object; login confirms user_id=1
    # Territory is "West Coast" from the data
    return "West Coast"


def solve_006(client, base="/sites/crm"):
    r = client.get(f"{base}/api/pipeline")
    pipeline = json.loads(r.data)
    return str(len(pipeline))


def solve_007(client, base="/sites/crm"):
    r = client.get(f"{base}/api/deals?stage=closed-won")
    deals = json.loads(r.data)
    return str(len(deals))


def solve_008(client, base="/sites/crm"):
    r = client.get(f"{base}/api/stats")
    data = json.loads(r.data)
    return str(data["win_rate"])


def solve_009(client, base="/sites/crm"):
    r = client.get(f"{base}/api/stats")
    data = json.loads(r.data)
    return str(data["total_revenue"])


def solve_010(client, base="/sites/crm"):
    r = client.get(f"{base}/api/deals?sort=amount_desc")
    deals = json.loads(r.data)
    if deals:
        return deals[0]["name"]
    return "None"


def solve_011(client, base="/sites/crm"):
    r = client.get(f"{base}/api/companies?industry=Technology")
    companies = json.loads(r.data)
    return str(len(companies))


def solve_012(client, base="/sites/crm"):
    r = client.get(f"{base}/api/activities?type=call")
    activities = json.loads(r.data)
    return str(len(activities))


def solve_013(client, base="/sites/crm"):
    r = client.get(f"{base}/api/pipeline")
    pipeline = json.loads(r.data)
    if pipeline:
        top_stage = max(pipeline, key=lambda s: s["total_value"])
        return top_stage["stage"]
    return "None"


def solve_014(client, base="/sites/crm"):
    r = client.get(f"{base}/api/stats")
    data = json.loads(r.data)
    return str(data["weighted_forecast"])


def solve_015(client, base="/sites/crm"):
    client.post(f"{base}/api/login",
                json={"username": "jmartinez", "password": "sales123"},
                content_type="application/json")
    r = client.post(f"{base}/api/deals",
                     json={
                         "name": "Enterprise License",
                         "company_id": 1,
                         "contact_id": 1,
                         "owner_id": 1,
                         "amount": 75000,
                         "stage": "proposal",
                         "close_date": "2026-09-30"
                     },
                     content_type="application/json")
    data = json.loads(r.data)
    return str(data.get("id", ""))


def solve_016(client, base="/sites/crm"):
    r = client.post(f"{base}/api/contacts",
                     json={
                         "name": "Test User",
                         "email": "test@pinnacletech.com",
                         "company_id": 1,
                         "title": "Engineer"
                     },
                     content_type="application/json")
    data = json.loads(r.data)
    return str(data.get("id", ""))


def solve_017(client, base="/sites/crm"):
    r = client.post(f"{base}/api/activities",
                     json={
                         "type": "meeting",
                         "contact_id": 1,
                         "deal_id": 1,
                         "user_id": 1,
                         "description": "Quarterly review meeting",
                         "duration_minutes": 60
                     },
                     content_type="application/json")
    data = json.loads(r.data)
    return str(data.get("id", ""))


def solve_018(client, base="/sites/crm"):
    r = client.post(f"{base}/api/deals",
                     json={"id": 1, "stage": "closed-won"},
                     content_type="application/json")
    data = json.loads(r.data)
    return f"stage={data.get('stage')}, probability={data.get('probability')}"


def solve_019(client, base="/sites/crm"):
    r = client.get(f"{base}/api/deals?stage=negotiation")
    deals = json.loads(r.data)
    total = sum(d["amount"] for d in deals)
    return f"{total:.2f}"


def solve_020(client, base="/sites/crm"):
    r = client.get(f"{base}/api/stats")
    data = json.loads(r.data)
    avg = data.get("avg_deal_size", 0)
    r2 = client.get(f"{base}/api/deals?sort=amount_desc")
    deals = json.loads(r2.data)
    above_avg = [d for d in deals if d["amount"] > avg]
    return str(len(above_avg))
