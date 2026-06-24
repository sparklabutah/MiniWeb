"""Per-macro verification functions for crowdfunding-donations.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/crowdfunding-donations"


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/campaigns/1")
    data = r.json()
    return {"pass": "title" in data and "raised_amount" in data,
            "detail": f"Campaign data keys: {list(data.keys())[:6]}"}


def verify_macro_filter_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/campaigns?category=technology")
    campaigns = r.json()
    ok = all(c["category"] == "technology" for c in campaigns)
    return {"pass": ok and len(campaigns) > 0,
            "detail": f"Technology filter: {len(campaigns)} campaigns, all_tech={ok}"}


def verify_macro_sort_by_ranking(server_url):
    r = requests.get(f"{_base(server_url)}/api/campaigns?sort=most_funded")
    campaigns = r.json()
    if len(campaigns) < 2:
        return {"pass": True, "detail": "Too few campaigns to verify sort"}
    is_sorted = all(campaigns[i]["raised_amount"] >= campaigns[i+1]["raised_amount"]
                    for i in range(len(campaigns)-1))
    return {"pass": is_sorted, "detail": f"Sort most_funded: sorted={is_sorted}"}


def verify_macro_authenticate_by_form(server_url):
    s = requests.Session()
    r = s.post(f"{_base(server_url)}/api/login",
               json={"username": "techvoyager", "password": "solar123"})
    data = r.json()
    ok = data.get("user_id") == 1
    return {"pass": ok, "detail": f"authenticate: user_id={data.get('user_id')}"}


def verify_macro_submit_form(server_url):
    base = _base(server_url)
    # Make a small pledge to an active campaign
    r = requests.get(f"{base}/api/campaigns?status=active&limit=1")
    campaigns = r.json()
    if not campaigns:
        return {"pass": False, "detail": "No active campaigns to test"}
    cid = campaigns[0]["id"]
    before = campaigns[0]["raised_amount"]
    r2 = requests.post(f"{base}/api/campaigns/{cid}/pledge", json={
        "user_id": 4,
        "amount": 5
    })
    data = r2.json()
    new_raised = data.get("new_raised", 0)
    return {"pass": new_raised > before,
            "detail": f"submit_form: pledged $5 to campaign {cid}, raised ${before} -> ${new_raised}"}


def verify_macro_compute_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/stats")
    data = r.json()
    return {"pass": "total_raised" in data and "total_backers" in data,
            "detail": f"Stats: raised=${data.get('total_raised')}, backers={data.get('total_backers')}"}
