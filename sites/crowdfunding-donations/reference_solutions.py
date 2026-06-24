"""Per-task reference solutions via Flask test client for crowdfunding-donations."""
import json


def solve_001(client, base="/sites/crowdfunding-donations"):
    r = client.get(f"{base}/api/campaigns")
    campaigns = json.loads(r.data)
    return str(len(campaigns))


def solve_002(client, base="/sites/crowdfunding-donations"):
    r = client.get(f"{base}/api/campaigns/1")
    data = json.loads(r.data)
    return str(data["funding_pct"])


def solve_003(client, base="/sites/crowdfunding-donations"):
    r = client.get(f"{base}/api/categories")
    cats = json.loads(r.data)
    return str(len(cats))


def solve_004(client, base="/sites/crowdfunding-donations"):
    r = client.get(f"{base}/api/stats")
    data = json.loads(r.data)
    return str(data["total_raised"])


def solve_005(client, base="/sites/crowdfunding-donations"):
    r = client.get(f"{base}/api/users/1")
    user = json.loads(r.data)
    return user["username"]


def solve_006(client, base="/sites/crowdfunding-donations"):
    r = client.get(f"{base}/api/campaigns?category=technology")
    campaigns = json.loads(r.data)
    return str(len(campaigns))


def solve_007(client, base="/sites/crowdfunding-donations"):
    r = client.get(f"{base}/api/campaigns?status=active")
    campaigns = json.loads(r.data)
    return str(len(campaigns))


def solve_008(client, base="/sites/crowdfunding-donations"):
    r = client.get(f"{base}/api/campaigns?sort=most_funded")
    campaigns = json.loads(r.data)
    if campaigns:
        return campaigns[0]["title"]
    return "None"


def solve_009(client, base="/sites/crowdfunding-donations"):
    r = client.get(f"{base}/api/stats")
    data = json.loads(r.data)
    return str(data["funded_count"])


def solve_010(client, base="/sites/crowdfunding-donations"):
    r = client.get(f"{base}/api/campaigns?q=tabletop")
    campaigns = json.loads(r.data)
    if campaigns:
        return campaigns[0]["title"]
    return "None"


def solve_011(client, base="/sites/crowdfunding-donations"):
    r = client.get(f"{base}/api/stats?category=games")
    data = json.loads(r.data)
    return str(data["total_raised"])


def solve_012(client, base="/sites/crowdfunding-donations"):
    r = client.get(f"{base}/api/users/3/pledges")
    pledges = json.loads(r.data)
    return str(len(pledges))


def solve_013(client, base="/sites/crowdfunding-donations"):
    r = client.get(f"{base}/api/campaigns?sort=most_backed")
    campaigns = json.loads(r.data)
    if campaigns:
        top = campaigns[0]
        return f"{top['title']} ({top['backer_count']} backers)"
    return "None"


def solve_014(client, base="/sites/crowdfunding-donations"):
    r = client.get(f"{base}/api/stats")
    data = json.loads(r.data)
    return str(data["avg_funding_pct"])


def solve_015(client, base="/sites/crowdfunding-donations"):
    client.post(f"{base}/api/login",
                json={"username": "techvoyager", "password": "solar123"},
                content_type="application/json")
    r = client.post(f"{base}/api/campaigns/2/pledge",
                     json={"user_id": 1, "tier_id": 4, "amount": 50},
                     content_type="application/json")
    data = json.loads(r.data)
    return str(data.get("new_raised", ""))


def solve_016(client, base="/sites/crowdfunding-donations"):
    client.post(f"{base}/api/login",
                json={"username": "techvoyager", "password": "solar123"},
                content_type="application/json")
    r = client.post(f"{base}/api/campaigns",
                     json={
                         "user_id": 1,
                         "title": "Test Campaign",
                         "description": "A test campaign",
                         "category": "technology",
                         "goal_amount": 10000,
                         "end_date": "2026-12-31"
                     },
                     content_type="application/json")
    data = json.loads(r.data)
    return str(data.get("campaign_id", ""))


def solve_017(client, base="/sites/crowdfunding-donations"):
    client.post(f"{base}/api/login",
                json={"username": "artlens", "password": "canvas456"},
                content_type="application/json")
    r = client.post(f"{base}/api/campaigns/2/update",
                     json={
                         "user_id": 2,
                         "title": "Progress Update",
                         "content": "New venue added to the tour"
                     },
                     content_type="application/json")
    data = json.loads(r.data)
    return str(data.get("total_updates", ""))


def solve_018(client, base="/sites/crowdfunding-donations"):
    r = client.get(f"{base}/api/campaigns?status=active&sort=ending_soon")
    campaigns = json.loads(r.data)
    if not campaigns:
        return "No active campaigns"
    target = campaigns[0]
    cid = target["id"]
    r2 = client.post(f"{base}/api/campaigns/{cid}/pledge",
                      json={"user_id": 5, "amount": 25},
                      content_type="application/json")
    data = json.loads(r2.data)
    return str(data.get("new_raised", ""))


def solve_019(client, base="/sites/crowdfunding-donations"):
    r = client.get(f"{base}/api/users/5/pledges")
    pledges = json.loads(r.data)
    total = sum(p["amount"] for p in pledges)
    return f"{total:.2f}"


def solve_020(client, base="/sites/crowdfunding-donations"):
    r = client.get(f"{base}/api/stats")
    stats = json.loads(r.data)
    total_backers = stats.get("total_backers", 0)
    r2 = client.get(f"{base}/api/campaigns?sort=most_funded&limit=3")
    top3 = json.loads(r2.data)
    top3_backers = sum(c["backer_count"] for c in top3)
    if total_backers > 0:
        pct = round(top3_backers / total_backers * 100, 1)
        return f"{pct}%"
    return "0%"
