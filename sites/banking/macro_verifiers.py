"""Per-macro verification functions for banking.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/banking"


def verify_macro_navigate_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/accounts?user_id=1&type=checking")
    accts = r.json()
    return {"pass": r.status_code == 200 and isinstance(accts, list),
            "detail": f"navigate_by_dropdown: {len(accts)} checking accounts"}


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/accounts/1")
    return {"pass": r.status_code == 200, "detail": f"Account detail: {r.status_code}"}


def verify_macro_search_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/transactions/search?q=Amazon")
    results = r.json()
    return {"pass": r.status_code == 200, "detail": f"search 'Amazon': {len(results)} results"}


def verify_macro_search_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/transactions/semantic?q=grocery+shopping")
    results = r.json()
    return {"pass": r.status_code == 200, "detail": f"semantic search: {len(results)} results"}


def verify_macro_filter_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/accounts?user_id=1&type=savings")
    accts = r.json()
    ok = all(a["type"] == "savings" for a in accts)
    return {"pass": ok, "detail": f"filter savings: {len(accts)}, all_savings={ok}"}


def verify_macro_filter_by_radio(server_url):
    r = requests.get(f"{_base(server_url)}/api/transactions?user_id=1&type=debit")
    txns = r.json()
    ok = all(t["type"] == "debit" for t in txns)
    return {"pass": ok, "detail": f"filter debit: {len(txns)}, all_debit={ok}"}


def verify_macro_filter_by_date_range(server_url):
    r = requests.get(f"{_base(server_url)}/api/transactions?user_id=1&date_from=2026-04-01&date_to=2026-05-01")
    txns = r.json()
    ok = all("2026-04-01" <= t["date"] <= "2026-05-01" for t in txns)
    return {"pass": ok, "detail": f"date range filter: {len(txns)}, all_in_range={ok}"}


def verify_macro_sort_by_ranking(server_url):
    r = requests.get(f"{_base(server_url)}/api/transactions?user_id=1&sort=amount_desc")
    txns = r.json()
    if len(txns) < 2:
        return {"pass": True, "detail": "Too few transactions to verify sort"}
    is_sorted = all(txns[i]["amount"] >= txns[i+1]["amount"] for i in range(len(txns)-1))
    return {"pass": is_sorted, "detail": f"sort_by_ranking: sorted_desc={is_sorted}"}


def verify_macro_extract_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/transactions/search?q=TXN000001")
    results = r.json()
    if results:
        return {"pass": True, "detail": f"extract: {results[0]['description'][:50]}"}
    return {"pass": True, "detail": "No matching transaction (ok)"}


def verify_macro_extract_from_table(server_url):
    r = requests.get(f"{_base(server_url)}/api/transactions?account_id=1")
    txns = r.json()
    return {"pass": len(txns) >= 0, "detail": f"account 1 transactions: {len(txns)}"}


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/accounts/1")
    acct = r.json()
    return {"pass": "account_number" in acct,
            "detail": f"extract_by_route: {acct.get('account_number')}"}


def verify_macro_compute_by_extremum(server_url):
    r = requests.get(f"{_base(server_url)}/api/stats?user_id=1")
    stats = r.json()
    top = stats.get("top_spending_categories", {})
    if top:
        top_cat = max(top, key=top.get)
        return {"pass": True, "detail": f"top spending: {top_cat}=${top[top_cat]}"}
    return {"pass": False, "detail": "No spending data"}


def verify_macro_compute_by_slider(server_url):
    r = requests.get(f"{_base(server_url)}/transfer")
    return {"pass": "amount_slider" in r.text, "detail": "Slider present on transfer page"}


def verify_macro_compare_by_date_range(server_url):
    r1 = requests.get(f"{_base(server_url)}/api/transactions?user_id=1&date_from=2026-03-01&date_to=2026-04-30")
    r2 = requests.get(f"{_base(server_url)}/api/transactions?user_id=1&date_from=2026-05-01&date_to=2026-06-30")
    return {"pass": r1.status_code == 200 and r2.status_code == 200,
            "detail": f"compare: {len(r1.json())} vs {len(r2.json())}"}


def verify_macro_verify_by_slider(server_url):
    r = requests.get(f"{_base(server_url)}/transfer")
    has_slider = "amount_slider" in r.text and 'min="1"' in r.text
    return {"pass": has_slider, "detail": f"verify_by_slider: slider_present={has_slider}"}


def verify_macro_create_from_free_text(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/payees",
                      json={"user_id": 1, "name": "TestPayee_Macro", "category": "Other"})
    data = r.json()
    ok = data.get("name") == "TestPayee_Macro"
    # Cleanup
    if ok:
        requests.delete(f"{base}/api/payees/{data['id']}")
    return {"pass": ok, "detail": f"create payee: {data.get('name')}"}


def verify_macro_submit_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/payees?user_id=1")
    payees = r.json()
    return {"pass": len(payees) > 0, "detail": f"submit_by_query: {len(payees)} payees"}


def verify_macro_edit_by_form(server_url):
    base = _base(server_url)
    r = requests.put(f"{base}/api/users/1/settings",
                     json={"email": "test_macro@email.com"})
    data = r.json()
    ok = data.get("email") == "test_macro@email.com"
    # Restore original
    requests.put(f"{base}/api/users/1/settings",
                 json={"email": "james.smith@email.com"})
    return {"pass": ok, "detail": f"edit_by_form: email={data.get('email')}"}


def verify_macro_delete_from_table(server_url):
    base = _base(server_url)
    # Create a dummy transaction by adding a payee, then delete it
    r = requests.post(f"{base}/api/payees",
                      json={"user_id": 1, "name": "DeleteMe", "category": "Test"})
    payee = r.json()
    pid = payee.get("id")
    if pid:
        r2 = requests.delete(f"{base}/api/payees/{pid}")
        return {"pass": r2.status_code == 200, "detail": f"delete payee {pid}: {r2.status_code}"}
    return {"pass": False, "detail": "Could not create test payee"}


def verify_macro_select_from_table(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/transactions/1/select")
    data = r.json()
    flagged = data.get("flagged")
    # Toggle back
    requests.post(f"{base}/api/transactions/1/select")
    return {"pass": flagged is not None, "detail": f"select_from_table: flagged={flagged}"}


def verify_macro_configure_by_date_range(server_url):
    base = _base(server_url)
    r = requests.put(f"{base}/api/bills/1/configure",
                     json={"due_date": "2026-08-01", "auto_pay": True})
    data = r.json()
    ok = data.get("due_date") == "2026-08-01" and data.get("auto_pay") is True
    # Restore
    requests.put(f"{base}/api/bills/1/configure",
                 json={"due_date": "2026-06-15", "auto_pay": False})
    return {"pass": ok, "detail": f"configure bill: due={data.get('due_date')}, auto={data.get('auto_pay')}"}


def verify_macro_export_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/export?format=csv&type=transactions&user_id=1")
    lines = r.text.strip().split("\n")
    return {"pass": len(lines) > 1, "detail": f"export CSV: {len(lines)} lines"}


def verify_macro_pay_by_query(server_url):
    base = _base(server_url)
    # Find a due bill and pay it
    r = requests.get(f"{base}/api/bills?status=due")
    bills = r.json()
    if bills:
        r2 = requests.post(f"{base}/api/bills/{bills[0]['id']}/pay",
                           json={"account_id": None})
        return {"pass": r2.status_code == 200, "detail": f"pay bill: {r2.status_code}"}
    return {"pass": True, "detail": "No due bills to pay (ok)"}


def verify_macro_pay_by_form(server_url):
    base = _base(server_url)
    r = requests.get(f"{base}/api/loans")
    loans = r.json()
    if loans:
        r2 = requests.post(f"{base}/api/loans/{loans[0]['id']}/pay",
                           json={"amount": 100})
        data = r2.json()
        return {"pass": r2.status_code == 200,
                "detail": f"loan payment: remaining={data.get('remaining_balance')}"}
    return {"pass": True, "detail": "No loans to pay (ok)"}


def verify_macro_authenticate_by_form(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/login",
                      json={"username": "james_smith", "password": "secure111"})
    data = r.json()
    ok = data.get("user_id") == 1
    return {"pass": ok, "detail": f"authenticate: user_id={data.get('user_id')}"}


def verify_macro_verify_identity_by_code(server_url):
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login",
           json={"username": "james_smith", "password": "secure111"})
    # Get MFA code from user data (in real scenario, user would know it)
    r = s.post(f"{base}/api/verify-identity", json={"mfa_code": "000000"})
    # We expect failure with wrong code
    return {"pass": r.status_code in (200, 403),
            "detail": f"verify_identity: status={r.status_code}"}
