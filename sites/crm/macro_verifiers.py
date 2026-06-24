"""Per-macro verification functions for crm.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/crm"


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/companies/1")
    data = r.json()
    return {"pass": "name" in data and "industry" in data,
            "detail": f"Company data keys: {list(data.keys())[:6]}"}


def verify_macro_authenticate_by_form(server_url):
    s = requests.Session()
    r = s.post(f"{_base(server_url)}/api/login",
               json={"username": "jmartinez", "password": "sales123"})
    data = r.json()
    ok = data.get("user_id") == 1
    return {"pass": ok, "detail": f"authenticate: user_id={data.get('user_id')}"}


def verify_macro_filter_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/deals?stage=closed-won")
    deals = r.json()
    ok = all(d["stage"] == "closed-won" for d in deals)
    return {"pass": ok,
            "detail": f"Closed-won filter: {len(deals)} deals, all_closed_won={ok}"}


def verify_macro_sort_by_ranking(server_url):
    r = requests.get(f"{_base(server_url)}/api/deals?sort=amount_desc")
    deals = r.json()
    if len(deals) < 2:
        return {"pass": True, "detail": "Too few deals to verify sort"}
    is_sorted = all(deals[i]["amount"] >= deals[i+1]["amount"] for i in range(len(deals)-1))
    return {"pass": is_sorted, "detail": f"Sort amount desc: sorted={is_sorted}"}


def verify_macro_compute_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/stats")
    data = r.json()
    return {"pass": "total_revenue" in data and "total_pipeline" in data,
            "detail": f"Stats: revenue=${data.get('total_revenue')}, pipeline=${data.get('total_pipeline')}"}


def verify_macro_submit_form(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/contacts", json={
        "name": "Macro Test Contact",
        "email": "macrotest@example.com",
        "company_id": 1,
        "title": "Test"
    })
    data = r.json()
    ok = data.get("id") is not None and data.get("name") == "Macro Test Contact"
    return {"pass": ok, "detail": f"submit_form: created contact id={data.get('id')}"}
