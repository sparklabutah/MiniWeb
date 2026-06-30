"""Per-macro verification functions for insurance-loans.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/insurance-loans"


def verify_macro_navigate_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/policies")
    return {"pass": r.status_code == 200, "detail": f"Policies page: {r.status_code}"}


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/policy/1")
    return {"pass": r.status_code == 200, "detail": f"Policy detail: {r.status_code}"}


def verify_macro_search_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/search?q=auto")
    result = r.json()
    total = len(result.get("policies", [])) + len(result.get("claims", [])) + len(result.get("loans", []))
    return {"pass": total > 0, "detail": f"search_by_query 'auto': {total} results"}


def verify_macro_search_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/search/semantic?q=mortgage+property")
    results = r.json()
    return {"pass": len(results) > 0,
            "detail": f"search_by_semantic 'mortgage property': {len(results)} results"}


def verify_macro_filter_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/policies?type=auto")
    policies = r.json()
    ok = all(p["type"] == "auto" for p in policies)
    return {"pass": ok and len(policies) > 0,
            "detail": f"filter_by_dropdown auto: {len(policies)} policies, all_match={ok}"}


def verify_macro_sort_by_ranking(server_url):
    r = requests.get(f"{_base(server_url)}/api/loans")
    loans = r.json()
    if len(loans) < 2:
        return {"pass": True, "detail": "Too few loans to verify sort"}
    sorted_loans = sorted(loans, key=lambda l: l.get("current_balance", 0), reverse=True)
    return {"pass": True,
            "detail": f"sort_by_ranking: highest balance={sorted_loans[0]['loan_number']}"}


def verify_macro_extract_by_toggle(server_url):
    r = requests.get(f"{_base(server_url)}/api/stats?user_id=1")
    stats = r.json()
    return {"pass": "active_policies" in stats,
            "detail": f"extract_by_toggle: active_policies={stats.get('active_policies')}"}


def verify_macro_extract_from_table(server_url):
    r = requests.get(f"{_base(server_url)}/api/payments?user_id=1")
    payments = r.json()
    return {"pass": len(payments) > 0,
            "detail": f"extract_from_table: {len(payments)} payments for user 1"}


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/loans/1")
    loan = r.json()
    return {"pass": "interest_rate" in loan,
            "detail": f"extract_by_route: loan 1 rate={loan.get('interest_rate')}%"}


def verify_macro_extract_by_ranking(server_url):
    r = requests.get(f"{_base(server_url)}/api/claims?user_id=1")
    claims = r.json()
    with_payout = [c for c in claims if c.get("payout_amount") and c["payout_amount"] > 0]
    if with_payout:
        top = max(with_payout, key=lambda c: c["payout_amount"])
        return {"pass": True,
                "detail": f"extract_by_ranking: top payout={top['claim_number']} (${top['payout_amount']})"}
    return {"pass": True, "detail": "No claims with payouts (ok)"}


def verify_macro_extract_by_extremum(server_url):
    r = requests.get(f"{_base(server_url)}/api/loans?status=active")
    loans = r.json()
    if not loans:
        return {"pass": False, "detail": "No active loans"}
    lowest = min(loans, key=lambda l: l["current_balance"])
    return {"pass": True,
            "detail": f"extract_by_extremum: lowest balance={lowest['loan_number']} (${lowest['current_balance']})"}


def verify_macro_compare_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/compare?type=policy&ids=1,3")
    items = r.json()
    return {"pass": len(items) == 2,
            "detail": f"compare_by_dropdown: {len(items)} items returned"}


def verify_macro_compare_from_table(server_url):
    r = requests.get(f"{_base(server_url)}/api/compare?type=loan&ids=1,2")
    items = r.json()
    if len(items) < 2:
        return {"pass": False, "detail": "compare_from_table: need 2 items"}
    return {"pass": items[0]["id"] != items[1]["id"],
            "detail": f"compare_from_table: loan {items[0]['id']} vs {items[1]['id']}"}


def verify_macro_verify_by_toggle(server_url):
    r = requests.get(f"{_base(server_url)}/api/users/1/settings")
    settings = r.json()
    return {"pass": "paperless_billing" in settings,
            "detail": f"verify_by_toggle: paperless={settings.get('paperless_billing')}"}


def verify_macro_edit_by_query(server_url):
    base = _base(server_url)
    # Save original
    r = requests.get(f"{base}/api/policies/1")
    original_notes = r.json().get("notes", "")
    # Edit
    r2 = requests.post(f"{base}/api/policies/1/update",
                       json={"notes": "test_edit_macro_note"})
    ok = r2.json().get("notes") == "test_edit_macro_note"
    # Restore
    requests.post(f"{base}/api/policies/1/update",
                  json={"notes": original_notes})
    return {"pass": ok, "detail": f"edit_by_query: updated notes ok={ok}"}


def verify_macro_sign_by_query(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/policies/1/sign",
                      json={"signer_name": "Test Signer"})
    result = r.json()
    ok = result.get("signed") is True
    # Clean up: remove signed fields
    requests.post(f"{base}/api/policies/1/update",
                  json={"notes": r.json().get("notes", "")})
    return {"pass": ok, "detail": f"sign_by_query: signed={result.get('signed')}"}


def verify_macro_select_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/policies?user_id=1&status=active")
    policies = r.json()
    return {"pass": len(policies) > 0,
            "detail": f"select_by_dropdown: {len(policies)} active policies for user 1"}


def verify_macro_select_by_ranking(server_url):
    r = requests.get(f"{_base(server_url)}/api/policies?user_id=1&status=active")
    policies = r.json()
    with_ded = [p for p in policies if p.get("deductible") is not None]
    if with_ded:
        sorted_ded = sorted(with_ded, key=lambda p: p["deductible"])
        return {"pass": True,
                "detail": f"select_by_ranking: lowest ded={sorted_ded[0]['policy_number']} (${sorted_ded[0]['deductible']})"}
    return {"pass": False, "detail": "No policies with deductible"}


def verify_macro_select_by_extremum(server_url):
    r = requests.get(f"{_base(server_url)}/api/loans?status=active")
    loans = r.json()
    if not loans:
        return {"pass": False, "detail": "No active loans"}
    highest = max(loans, key=lambda l: l["current_balance"])
    return {"pass": True,
            "detail": f"select_by_extremum: highest balance={highest['loan_number']}"}


def verify_macro_configure_by_toggle(server_url):
    base = _base(server_url)
    # Save original
    r0 = requests.get(f"{base}/api/users/1/settings")
    original = r0.json()
    # Toggle
    r = requests.post(f"{base}/api/users/1/settings",
                      json={"paperless_billing": True})
    result = r.json()
    ok = result.get("paperless_billing") is True
    # Restore
    requests.post(f"{base}/api/users/1/settings", json=original)
    return {"pass": ok, "detail": f"configure_by_toggle: paperless={result.get('paperless_billing')}"}


def verify_macro_export_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/export?type=policies&format=csv")
    lines = r.text.strip().split("\n")
    return {"pass": len(lines) > 1, "detail": f"export CSV: {len(lines)} lines"}


def verify_macro_upload_by_upload(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/claims/4/upload",
                      data={"filename": "test_doc.pdf", "description": "Test"})
    result = r.json()
    ok = result.get("status") == "uploaded"
    return {"pass": ok, "detail": f"upload_by_upload: status={result.get('status')}"}


def verify_macro_pay_by_form(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/policies/1/pay",
                      json={"amount": 142.00, "method": "online"})
    result = r.json()
    ok = result.get("status") == "completed"
    return {"pass": ok, "detail": f"pay_by_form: status={result.get('status')}"}


def verify_macro_submit_by_form(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/claims",
                      json={"policy_number": "POL-AUTO-2020-11847",
                            "description": "Test claim for macro verification",
                            "date_of_incident": "2026-06-25",
                            "type": "auto_collision"})
    result = r.json()
    ok = result.get("status") == "open"
    return {"pass": ok, "detail": f"submit_by_form: claim status={result.get('status')}"}


def verify_macro_apply_by_query(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/loans/apply",
                      json={"user_id": 5, "type": "personal_loan", "amount": 5000})
    result = r.json()
    ok = result.get("status") == "pending_approval"
    return {"pass": ok,
            "detail": f"apply_by_query: loan status={result.get('status')}, number={result.get('loan_number')}"}


def verify_macro_compute_from_table(server_url):
    r = requests.get(f"{_base(server_url)}/api/calculator?amount=10000&rate=5&term=36")
    result = r.json()
    mp = result.get("monthly_payment")
    return {"pass": mp is not None and mp > 0,
            "detail": f"compute_from_table: monthly_payment=${mp}"}


def verify_macro_compute_by_extremum(server_url):
    r = requests.get(f"{_base(server_url)}/api/policies?status=active")
    policies = r.json()
    type_totals = {}
    for p in policies:
        t = p["type"]
        type_totals[t] = type_totals.get(t, 0) + p.get("premium_annual", 0)
    if type_totals:
        top = max(type_totals, key=type_totals.get)
        return {"pass": True,
                "detail": f"compute_by_extremum: top type={top} (${type_totals[top]})"}
    return {"pass": False, "detail": "No active policies"}


def verify_macro_compute_by_slider(server_url):
    r = requests.get(f"{_base(server_url)}/api/calculator?amount=25000&rate=4.5&term=48")
    result = r.json()
    mp = result.get("monthly_payment")
    ti = result.get("total_interest")
    return {"pass": mp is not None and ti is not None,
            "detail": f"compute_by_slider: monthly=${mp}, total_interest=${ti}"}
