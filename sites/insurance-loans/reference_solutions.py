"""Per-task reference solutions via Flask test client for insurance-loans."""
import json


def solve_001(client, base="/sites/insurance-loans"):
    r = client.get(f"{base}/api/policies?user_id=1&type=auto")
    policies = json.loads(r.data)
    return str(len(policies))


def solve_002(client, base="/sites/insurance-loans"):
    r = client.get(f"{base}/api/policies/1")
    policy = json.loads(r.data)
    return policy["policy_number"]


def solve_003(client, base="/sites/insurance-loans"):
    r = client.get(f"{base}/api/search?q=auto")
    result = json.loads(r.data)
    total = len(result.get("policies", [])) + len(result.get("claims", [])) + len(result.get("loans", []))
    return str(total)


def solve_004(client, base="/sites/insurance-loans"):
    r = client.get(f"{base}/api/search/semantic?q=vehicle+damage+repair")
    results = json.loads(r.data)
    return str(len(results))


def solve_005(client, base="/sites/insurance-loans"):
    r = client.get(f"{base}/api/loans")
    loans = json.loads(r.data)
    sorted_loans = sorted(loans, key=lambda l: l.get("current_balance", 0), reverse=True)
    return sorted_loans[0]["loan_number"] if sorted_loans else ""


def solve_006(client, base="/sites/insurance-loans"):
    r = client.get(f"{base}/api/stats?user_id=1")
    stats = json.loads(r.data)
    return str(stats.get("active_policies", 0))


def solve_007(client, base="/sites/insurance-loans"):
    r = client.get(f"{base}/api/payments?user_id=1")
    payments = json.loads(r.data)
    return str(len(payments))


def solve_008(client, base="/sites/insurance-loans"):
    r = client.get(f"{base}/api/loans/1")
    loan = json.loads(r.data)
    return str(loan["interest_rate"])


def solve_009(client, base="/sites/insurance-loans"):
    r = client.get(f"{base}/api/claims?user_id=1")
    claims = json.loads(r.data)
    with_payout = [c for c in claims if c.get("payout_amount") is not None and c.get("payout_amount", 0) > 0]
    if not with_payout:
        return "None"
    top = max(with_payout, key=lambda c: c["payout_amount"])
    return top["claim_number"]


def solve_010(client, base="/sites/insurance-loans"):
    r = client.get(f"{base}/api/loans?status=active")
    loans = json.loads(r.data)
    if not loans:
        return ""
    lowest = min(loans, key=lambda l: l["current_balance"])
    return f"{lowest['loan_number']} ${lowest['current_balance']}"


def solve_011(client, base="/sites/insurance-loans"):
    r = client.get(f"{base}/api/compare?type=policy&ids=1,3")
    policies = json.loads(r.data)
    premiums = {p["id"]: p["premium_monthly"] for p in policies}
    p1 = premiums.get(1, 0)
    p3 = premiums.get(3, 0)
    if p1 > p3:
        return f"Policy 1 has higher premium by ${p1 - p3}"
    else:
        return f"Policy 3 has higher premium by ${p3 - p1}"


def solve_012(client, base="/sites/insurance-loans"):
    r = client.get(f"{base}/api/users/1/settings")
    settings = json.loads(r.data)
    return f"paperless_billing={settings.get('paperless_billing')}"


def solve_013(client, base="/sites/insurance-loans"):
    r = client.post(f"{base}/api/policies/1/update",
                    json={"notes": "Updated: added roadside assistance"})
    policy = json.loads(r.data)
    return policy.get("notes", "")


def solve_014(client, base="/sites/insurance-loans"):
    r = client.get(f"{base}/api/calculator?amount=50000&rate=6.5&term=60")
    result = json.loads(r.data)
    return str(result.get("monthly_payment", ""))


def solve_015(client, base="/sites/insurance-loans"):
    r = client.get(f"{base}/api/policies?status=active")
    policies = json.loads(r.data)
    type_totals = {}
    for p in policies:
        t = p["type"]
        type_totals[t] = type_totals.get(t, 0) + p.get("premium_annual", 0)
    top_type = max(type_totals, key=type_totals.get)
    return f"{top_type}: ${type_totals[top_type]}"


def solve_016(client, base="/sites/insurance-loans"):
    client.post(f"{base}/api/login",
                json={"username": "alex.rivera"})
    r = client.post(f"{base}/api/policies/1/sign",
                    json={"signer_name": "Alex Rivera"})
    result = json.loads(r.data)
    return f"signed={result.get('signed')}"


def solve_017(client, base="/sites/insurance-loans"):
    r = client.get(f"{base}/api/policies?user_id=1&status=active")
    policies = json.loads(r.data)
    with_ded = [p for p in policies if p.get("deductible") is not None]
    lowest = min(with_ded, key=lambda p: p["deductible"])
    return f"{lowest['policy_number']} (${lowest['deductible']})"


def solve_018(client, base="/sites/insurance-loans"):
    r = client.post(f"{base}/api/users/1/settings",
                    json={"paperless_billing": True, "sms_alerts": True})
    settings = json.loads(r.data)
    return f"paperless={settings.get('paperless_billing')}, sms={settings.get('sms_alerts')}"


def solve_019(client, base="/sites/insurance-loans"):
    r = client.get(f"{base}/api/export?type=policies&format=csv&user_id=1")
    lines = r.data.decode().strip().split("\n")
    return str(len(lines) - 1)


def solve_020(client, base="/sites/insurance-loans"):
    # Login
    client.post(f"{base}/api/login", json={"username": "alex.rivera"})

    # Upload document to claim 4
    r1 = client.post(f"{base}/api/claims/4/upload",
                     data={"filename": "windshield_photos.pdf",
                           "description": "Windshield damage photos"})
    upload_result = json.loads(r1.data)

    # Make premium payment for policy 1
    r2 = client.post(f"{base}/api/policies/1/pay",
                     json={"amount": 142.00, "method": "online"})
    pay_result = json.loads(r2.data)

    # Submit loan application
    r3 = client.post(f"{base}/api/loans/apply",
                     json={"user_id": 1, "type": "personal_loan", "amount": 15000})
    loan_result = json.loads(r3.data)

    return f"upload={upload_result.get('status')}, payment={pay_result.get('status')}, loan={loan_result.get('status')}"
