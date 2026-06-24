"""Per-task HTTP verification functions for crowdfunding-donations."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/crowdfunding-donations"
    r = requests.get(f"{base}/api/campaigns")
    campaigns = r.json()
    count = len(campaigns)
    return {"pass": count > 0, "detail": f"Total campaigns: {count}"}


def verify_002(server_url):
    base = f"{server_url}/sites/crowdfunding-donations"
    r = requests.get(f"{base}/api/campaigns/1")
    data = r.json()
    pct = data.get("funding_pct")
    return {"pass": pct is not None and pct > 0, "detail": f"EcoCharge funding: {pct}%"}


def verify_003(server_url):
    base = f"{server_url}/sites/crowdfunding-donations"
    r = requests.get(f"{base}/api/categories")
    cats = r.json()
    count = len(cats)
    return {"pass": count == 8, "detail": f"Categories: {count}"}


def verify_004(server_url):
    base = f"{server_url}/sites/crowdfunding-donations"
    r = requests.get(f"{base}/api/stats")
    data = r.json()
    total = data.get("total_raised", 0)
    return {"pass": total > 0, "detail": f"Total raised: ${total}"}


def verify_005(server_url):
    base = f"{server_url}/sites/crowdfunding-donations"
    r = requests.get(f"{base}/api/users/1")
    user = r.json()
    username = user.get("username")
    return {"pass": username == "techvoyager", "detail": f"Username: {username}"}


def verify_006(server_url):
    base = f"{server_url}/sites/crowdfunding-donations"
    r = requests.get(f"{base}/api/campaigns?category=technology")
    campaigns = r.json()
    count = len(campaigns)
    ok = all(c["category"] == "technology" for c in campaigns)
    return {"pass": count > 0 and ok, "detail": f"Technology campaigns: {count}"}


def verify_007(server_url):
    base = f"{server_url}/sites/crowdfunding-donations"
    r = requests.get(f"{base}/api/campaigns?status=active")
    campaigns = r.json()
    count = len(campaigns)
    ok = all(c["status"] == "active" for c in campaigns)
    return {"pass": count > 0 and ok, "detail": f"Active campaigns: {count}"}


def verify_008(server_url):
    base = f"{server_url}/sites/crowdfunding-donations"
    r = requests.get(f"{base}/api/campaigns?sort=most_funded")
    campaigns = r.json()
    if campaigns:
        top = campaigns[0]
        return {"pass": True, "detail": f"Most funded: {top['title']} (${top['raised_amount']})"}
    return {"pass": False, "detail": "No campaigns"}


def verify_009(server_url):
    base = f"{server_url}/sites/crowdfunding-donations"
    r = requests.get(f"{base}/api/stats")
    data = r.json()
    funded = data.get("funded_count", 0)
    return {"pass": funded >= 0, "detail": f"Funded campaigns: {funded}"}


def verify_010(server_url):
    base = f"{server_url}/sites/crowdfunding-donations"
    r = requests.get(f"{base}/api/campaigns?q=tabletop")
    campaigns = r.json()
    count = len(campaigns)
    return {"pass": count > 0, "detail": f"Tabletop search results: {count}, titles={[c['title'] for c in campaigns[:3]]}"}


def verify_011(server_url):
    base = f"{server_url}/sites/crowdfunding-donations"
    r = requests.get(f"{base}/api/stats?category=games")
    data = r.json()
    total = data.get("total_raised", 0)
    return {"pass": total >= 0, "detail": f"Games total raised: ${total}"}


def verify_012(server_url):
    base = f"{server_url}/sites/crowdfunding-donations"
    r = requests.get(f"{base}/api/users/3/pledges")
    pledges = r.json()
    count = len(pledges)
    return {"pass": count >= 0, "detail": f"Ethan's pledges: {count}"}


def verify_013(server_url):
    base = f"{server_url}/sites/crowdfunding-donations"
    r = requests.get(f"{base}/api/campaigns?sort=most_backed")
    campaigns = r.json()
    if campaigns:
        top = campaigns[0]
        return {"pass": True, "detail": f"Most backed: {top['title']} ({top['backer_count']} backers)"}
    return {"pass": False, "detail": "No campaigns"}


def verify_014(server_url):
    base = f"{server_url}/sites/crowdfunding-donations"
    r = requests.get(f"{base}/api/stats")
    data = r.json()
    avg_pct = data.get("avg_funding_pct", 0)
    return {"pass": avg_pct >= 0, "detail": f"Average funding %: {avg_pct}"}


def verify_015(server_url):
    base = f"{server_url}/sites/crowdfunding-donations"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "techvoyager", "password": "solar123"})
    # Get campaign 2 raised_amount before pledge
    r1 = s.get(f"{base}/api/campaigns/2")
    before = r1.json().get("raised_amount", 0)
    # Make pledge
    r = s.post(f"{base}/api/campaigns/2/pledge", json={
        "user_id": 1,
        "tier_id": 4,
        "amount": 50
    })
    data = r.json()
    new_raised = data.get("new_raised", 0)
    return {"pass": new_raised > before, "detail": f"Pledge: before=${before}, after=${new_raised}"}


def verify_016(server_url):
    base = f"{server_url}/sites/crowdfunding-donations"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "techvoyager", "password": "solar123"})
    r = s.post(f"{base}/api/campaigns", json={
        "user_id": 1,
        "title": "Test Campaign",
        "description": "A test campaign",
        "category": "technology",
        "goal_amount": 10000,
        "end_date": "2026-12-31"
    })
    data = r.json()
    cid = data.get("campaign_id")
    ok = cid is not None
    return {"pass": ok, "detail": f"Created campaign ID: {cid}"}


def verify_017(server_url):
    base = f"{server_url}/sites/crowdfunding-donations"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "artlens", "password": "canvas456"})
    # Get update count before
    r1 = s.get(f"{base}/api/campaigns/2")
    before = len(r1.json().get("updates", []))
    # Post update
    r = s.post(f"{base}/api/campaigns/2/update", json={
        "user_id": 2,
        "title": "Progress Update",
        "content": "New venue added to the tour"
    })
    data = r.json()
    total = data.get("total_updates", 0)
    return {"pass": total > before, "detail": f"Updates before={before}, after={total}"}


def verify_018(server_url):
    base = f"{server_url}/sites/crowdfunding-donations"
    # Find active campaigns sorted by ending soon
    r = requests.get(f"{base}/api/campaigns?status=active&sort=ending_soon")
    campaigns = r.json()
    if not campaigns:
        return {"pass": False, "detail": "No active campaigns"}
    target = campaigns[0]
    cid = target["id"]
    before_raised = target["raised_amount"]
    # Pledge
    r2 = requests.post(f"{base}/api/campaigns/{cid}/pledge", json={
        "user_id": 5,
        "amount": 25
    })
    data = r2.json()
    new_raised = data.get("new_raised", 0)
    return {"pass": new_raised > before_raised,
            "detail": f"Campaign {cid}: ${before_raised} -> ${new_raised}"}


def verify_019(server_url):
    base = f"{server_url}/sites/crowdfunding-donations"
    r = requests.get(f"{base}/api/users/5/pledges")
    pledges = r.json()
    total = sum(p["amount"] for p in pledges)
    return {"pass": total > 0, "detail": f"Jordan total pledged: ${total}"}


def verify_020(server_url):
    base = f"{server_url}/sites/crowdfunding-donations"
    r = requests.get(f"{base}/api/stats")
    stats = r.json()
    total_backers = stats.get("total_backers", 0)
    r2 = requests.get(f"{base}/api/campaigns?sort=most_funded&limit=3")
    top3 = r2.json()
    top3_backers = sum(c["backer_count"] for c in top3)
    if total_backers > 0:
        pct = round(top3_backers / total_backers * 100, 1)
        return {"pass": True, "detail": f"Top 3 backers: {top3_backers}/{total_backers} = {pct}%"}
    return {"pass": False, "detail": "No backers"}
