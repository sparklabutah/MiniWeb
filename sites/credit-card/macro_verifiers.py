"""Per-macro verification functions for credit-card.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/credit-card"


def verify_macro_authenticate_by_form(server_url):
    s = requests.Session()
    r = s.post(f"{_base(server_url)}/api/login",
               json={"username": "sarah_miller", "password": "cardpass1"})
    data = r.json()
    ok = data.get("user_id") == 1
    return {"pass": ok, "detail": f"authenticate: user_id={data.get('user_id')}"}


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/transactions?user_id=1")
    return {"pass": r.status_code == 200, "detail": f"Transactions API: {r.status_code}"}


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/accounts/1")
    data = r.json()
    return {"pass": "current_balance" in data and "credit_limit" in data,
            "detail": f"Account data keys: {list(data.keys())[:6]}"}


def verify_macro_filter_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/transactions?user_id=1&category=Groceries")
    txns = r.json()
    ok = all(t["category"] == "Groceries" for t in txns)
    return {"pass": ok and len(txns) > 0,
            "detail": f"Grocery filter: {len(txns)} txns, all_groceries={ok}"}


def verify_macro_filter_by_date_range(server_url):
    r = requests.get(f"{_base(server_url)}/api/transactions?user_id=1&date_from=2025-01-01&date_to=2025-01-15")
    txns = r.json()
    ok = all("2025-01-01" <= t["date"] <= "2025-01-15" for t in txns)
    return {"pass": ok, "detail": f"Date filter Jan 1-15: {len(txns)} txns, in_range={ok}"}


def verify_macro_sort_by_ranking(server_url):
    r = requests.get(f"{_base(server_url)}/api/transactions?sort=amount_desc")
    txns = r.json()
    if len(txns) < 2:
        return {"pass": True, "detail": "Too few transactions to verify sort"}
    is_sorted = all(txns[i]["amount"] >= txns[i+1]["amount"] for i in range(len(txns)-1))
    return {"pass": is_sorted, "detail": f"Sort amount desc: sorted={is_sorted}"}


def verify_macro_compute_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/spending?user_id=1")
    data = r.json()
    return {"pass": "total" in data and "by_category" in data,
            "detail": f"Spending: total=${data.get('total')}, categories={len(data.get('by_category', {}))}"}


def verify_macro_submit_form(server_url):
    # Test making a payment via API
    r = requests.post(f"{_base(server_url)}/api/payments",
                      json={"user_id": 4, "amount": 10.00, "method": "bank_transfer"})
    data = r.json()
    ok = data.get("status") == "completed"
    # Verify it was created
    if ok:
        # Clean up by checking it exists
        r2 = requests.get(f"{_base(server_url)}/api/payments?user_id=4")
        payments = r2.json()
        found = any(p["amount"] == 10.0 for p in payments)
        return {"pass": found, "detail": f"Payment submitted and found: {found}"}
    return {"pass": ok, "detail": f"submit_form: status={data.get('status')}"}


def verify_macro_toggle_by_api(server_url):
    base = _base(server_url)
    # Toggle dispute on transaction 1
    r = requests.post(f"{base}/api/transactions/1/dispute")
    data = r.json()
    action = data.get("action")
    # Toggle back
    requests.post(f"{base}/api/transactions/1/dispute")
    return {"pass": action in ("disputed", "undisputed"),
            "detail": f"toggle_by_api: action={action}"}
