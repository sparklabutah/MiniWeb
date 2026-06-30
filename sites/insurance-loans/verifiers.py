"""Per-task HTTP verification functions for insurance-loans."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/insurance-loans"
    r = requests.get(f"{base}/api/policies?user_id=1&type=auto")
    policies = r.json()
    count = len(policies)
    return {"pass": count > 0, "detail": f"User 1 auto policies: {count}"}


def verify_002(server_url):
    base = f"{server_url}/sites/insurance-loans"
    r = requests.get(f"{base}/api/policies/1")
    policy = r.json()
    pn = policy.get("policy_number", "")
    return {"pass": pn == "POL-AUTO-2020-11847",
            "detail": f"Policy 1 number: {pn}"}


def verify_003(server_url):
    base = f"{server_url}/sites/insurance-loans"
    r = requests.get(f"{base}/api/search?q=auto")
    result = r.json()
    total = len(result.get("policies", [])) + len(result.get("claims", [])) + len(result.get("loans", []))
    return {"pass": total > 0, "detail": f"Search 'auto': {total} total results"}


def verify_004(server_url):
    base = f"{server_url}/sites/insurance-loans"
    r = requests.get(f"{base}/api/search/semantic?q=vehicle+damage+repair")
    results = r.json()
    count = len(results)
    return {"pass": count > 0, "detail": f"Semantic search 'vehicle damage repair': {count} results"}


def verify_005(server_url):
    base = f"{server_url}/sites/insurance-loans"
    r = requests.get(f"{base}/api/loans")
    loans = r.json()
    if not loans:
        return {"pass": False, "detail": "No loans found"}
    sorted_loans = sorted(loans, key=lambda l: l.get("current_balance", 0), reverse=True)
    top = sorted_loans[0]
    return {"pass": top["current_balance"] > 0,
            "detail": f"Highest balance: {top['loan_number']} (${top['current_balance']})"}


def verify_006(server_url):
    base = f"{server_url}/sites/insurance-loans"
    r = requests.get(f"{base}/api/stats?user_id=1")
    stats = r.json()
    active = stats.get("active_policies", 0)
    return {"pass": active > 0, "detail": f"User 1 active policies: {active}"}


def verify_007(server_url):
    base = f"{server_url}/sites/insurance-loans"
    r = requests.get(f"{base}/api/payments?user_id=1")
    payments = r.json()
    count = len(payments)
    return {"pass": count > 0, "detail": f"User 1 total payments: {count}"}


def verify_008(server_url):
    base = f"{server_url}/sites/insurance-loans"
    r = requests.get(f"{base}/api/loans/1")
    loan = r.json()
    rate = loan.get("interest_rate")
    return {"pass": rate == 4.53, "detail": f"Loan 1 interest rate: {rate}%"}


def verify_009(server_url):
    base = f"{server_url}/sites/insurance-loans"
    r = requests.get(f"{base}/api/claims?user_id=1")
    claims = r.json()
    # Filter to claims with payout
    with_payout = [c for c in claims if c.get("payout_amount") is not None and c.get("payout_amount", 0) > 0]
    if not with_payout:
        return {"pass": False, "detail": "No claims with payouts for user 1"}
    top = max(with_payout, key=lambda c: c["payout_amount"])
    return {"pass": True, "detail": f"Highest payout claim: {top['claim_number']} (${top['payout_amount']})"}


def verify_010(server_url):
    base = f"{server_url}/sites/insurance-loans"
    r = requests.get(f"{base}/api/loans?status=active")
    loans = r.json()
    if not loans:
        return {"pass": False, "detail": "No active loans"}
    lowest = min(loans, key=lambda l: l["current_balance"])
    return {"pass": True,
            "detail": f"Lowest balance active loan: {lowest['loan_number']} (${lowest['current_balance']})"}


def verify_011(server_url):
    base = f"{server_url}/sites/insurance-loans"
    r = requests.get(f"{base}/api/compare?type=policy&ids=1,3")
    policies = r.json()
    if len(policies) < 2:
        return {"pass": False, "detail": f"Compare returned {len(policies)} policies"}
    premiums = {p["id"]: p["premium_monthly"] for p in policies}
    p1 = premiums.get(1, 0)
    p3 = premiums.get(3, 0)
    diff = abs(p1 - p3)
    return {"pass": True,
            "detail": f"Policy 1: ${p1}/mo, Policy 3: ${p3}/mo, diff: ${diff}"}


def verify_012(server_url):
    base = f"{server_url}/sites/insurance-loans"
    r = requests.get(f"{base}/api/users/1/settings")
    settings = r.json()
    paperless = settings.get("paperless_billing")
    return {"pass": paperless is not None,
            "detail": f"Paperless billing: {paperless}"}


def verify_013(server_url):
    base = f"{server_url}/sites/insurance-loans"
    r = requests.get(f"{base}/api/policies/1")
    policy = r.json()
    notes = policy.get("notes", "")
    ok = "Updated: added roadside assistance" in notes
    return {"pass": ok, "detail": f"Policy 1 notes: {notes[:80]}"}


def verify_014(server_url):
    base = f"{server_url}/sites/insurance-loans"
    r = requests.get(f"{base}/api/calculator?amount=50000&rate=6.5&term=60")
    result = r.json()
    mp = result.get("monthly_payment")
    # Expected ~ $978.31
    ok = mp is not None and 975 < mp < 985
    return {"pass": ok, "detail": f"Monthly payment for $50k at 6.5% for 60mo: ${mp}"}


def verify_015(server_url):
    base = f"{server_url}/sites/insurance-loans"
    r = requests.get(f"{base}/api/policies?status=active")
    policies = r.json()
    if not policies:
        return {"pass": False, "detail": "No active policies"}
    # Sum annual premiums by type
    type_totals = {}
    for p in policies:
        t = p["type"]
        type_totals[t] = type_totals.get(t, 0) + p.get("premium_annual", 0)
    top_type = max(type_totals, key=type_totals.get)
    return {"pass": True,
            "detail": f"Highest annual premium type: {top_type} (${type_totals[top_type]})"}


def verify_016(server_url):
    base = f"{server_url}/sites/insurance-loans"
    r = requests.get(f"{base}/api/policies/1")
    policy = r.json()
    ok = policy.get("signed") is True and policy.get("signed_by") == "Alex Rivera"
    return {"pass": ok,
            "detail": f"Policy 1 signed={policy.get('signed')}, by={policy.get('signed_by')}"}


def verify_017(server_url):
    base = f"{server_url}/sites/insurance-loans"
    r = requests.get(f"{base}/api/policies?user_id=1&status=active")
    policies = r.json()
    # Filter to ones with numeric deductible
    with_ded = [p for p in policies if p.get("deductible") is not None]
    if not with_ded:
        return {"pass": False, "detail": "No policies with deductible"}
    lowest = min(with_ded, key=lambda p: p["deductible"])
    return {"pass": True,
            "detail": f"Lowest deductible: {lowest['policy_number']} (${lowest['deductible']})"}


def verify_018(server_url):
    base = f"{server_url}/sites/insurance-loans"
    r = requests.get(f"{base}/api/users/1/settings")
    settings = r.json()
    ok = settings.get("paperless_billing") is True and settings.get("sms_alerts") is True
    return {"pass": ok,
            "detail": f"paperless={settings.get('paperless_billing')}, sms={settings.get('sms_alerts')}"}


def verify_019(server_url):
    base = f"{server_url}/sites/insurance-loans"
    r = requests.get(f"{base}/api/export?type=policies&format=csv&user_id=1")
    lines = r.text.strip().split("\n")
    data_rows = len(lines) - 1
    return {"pass": data_rows > 0, "detail": f"CSV export user 1 policies: {data_rows} data rows"}


def verify_020(server_url):
    base = f"{server_url}/sites/insurance-loans"
    # Check claim 4 has a document
    r1 = requests.get(f"{base}/api/claims/4")
    claim = r1.json()
    has_doc = len(claim.get("documents", [])) > 0

    # Check there's a new premium payment for policy 1
    r2 = requests.get(f"{base}/api/payments?user_id=1&type=insurance_premium")
    payments = r2.json()
    pol1_payments = [p for p in payments if p.get("related_policy") == "POL-AUTO-2020-11847"]
    has_payment = len(pol1_payments) > 0

    # Check there's a new loan application
    r3 = requests.get(f"{base}/api/loans?user_id=1")
    loans = r3.json()
    pending = [l for l in loans if l.get("status") == "pending_approval"]
    has_app = len(pending) > 0

    ok = has_doc and has_payment and has_app
    return {"pass": ok,
            "detail": f"doc={has_doc}, payment={has_payment}, loan_app={has_app}"}
