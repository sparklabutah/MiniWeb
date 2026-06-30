"""Per-task reference solutions via Flask test client for conference-review-submission."""
import json


def solve_001(client, base="/sites/conference-review-submission"):
    r = client.get(f"{base}/api/venues/iclr-2017")
    venue = json.loads(r.data)
    return str(venue["paper_count"])


def solve_002(client, base="/sites/conference-review-submission"):
    r = client.get(f"{base}/api/venues")
    venues = json.loads(r.data)
    return str(len(venues))


def solve_003(client, base="/sites/conference-review-submission"):
    r = client.get(f"{base}/api/papers/search?q=generative&venue_id=iclr-2017")
    return str(len(json.loads(r.data)))


def solve_004(client, base="/sites/conference-review-submission"):
    r = client.get(f"{base}/api/papers?status=accepted&venue_id=iclr-2017")
    return str(len(json.loads(r.data)))


def solve_005(client, base="/sites/conference-review-submission"):
    r = client.get(f"{base}/api/venues")
    venues = json.loads(r.data)
    under_review = [v for v in venues if v.get("status") == "under_review"]
    return under_review[0]["name"] if under_review else ""


def solve_006(client, base="/sites/conference-review-submission"):
    r = client.get(f"{base}/api/stats?venue_id=iclr-2017")
    stats = json.loads(r.data)
    return str(stats["acceptance_rate"])


def solve_007(client, base="/sites/conference-review-submission"):
    r = client.get(f"{base}/api/papers?venue_id=iclr-2017&sort=score_desc&limit=1")
    papers = json.loads(r.data)
    return papers[0]["title"] if papers else ""


def solve_008(client, base="/sites/conference-review-submission"):
    r = client.get(f"{base}/api/venues/iclr-2017")
    venue = json.loads(r.data)
    return str(venue["paper_count"])


def solve_009(client, base="/sites/conference-review-submission"):
    r = client.get(f"{base}/api/papers?venue_id=iclr-2017&score_min=7")
    return str(len(json.loads(r.data)))


def solve_010(client, base="/sites/conference-review-submission"):
    r = client.get(f"{base}/api/stats?venue_id=iclr-2017")
    stats = json.loads(r.data)
    return f"Accepted: {stats['avg_accepted_score']}, Rejected: {stats['avg_rejected_score']}"


def solve_011(client, base="/sites/conference-review-submission"):
    r = client.get(f"{base}/api/papers/search?q=Yoshua+Bengio&venue_id=iclr-2017")
    return str(len(json.loads(r.data)))


def solve_012(client, base="/sites/conference-review-submission"):
    r = client.get(f"{base}/api/export?format=csv&status=accepted&venue_id=iclr-2017")
    lines = r.data.decode().strip().split("\n")
    return str(len(lines) - 1)


def solve_013(client, base="/sites/conference-review-submission"):
    r = client.get(f"{base}/api/stats?venue_id=iclr-2017")
    return str(json.loads(r.data)["unique_authors"])


def solve_014(client, base="/sites/conference-review-submission"):
    r = client.get(f"{base}/api/stats?venue_id=iclr-2017")
    return str(json.loads(r.data)["total_reviews"])


def solve_015(client, base="/sites/conference-review-submission"):
    r = client.get(f"{base}/api/papers?venue_id=iclr-2017&sort=title&limit=1")
    papers = json.loads(r.data)
    return papers[0]["title"] if papers else ""


def solve_016(client, base="/sites/conference-review-submission"):
    client.post(f"{base}/api/login",
                json={"username": "reviewer_psharma", "password": "pass456"})
    r = client.get(f"{base}/api/users/2")
    user = json.loads(r.data)
    assigned = user.get("assigned_papers", [])
    if isinstance(assigned, str):
        assigned = json.loads(assigned) if assigned else []
    bids = user.get("bids", {})
    if isinstance(bids, str):
        bids = json.loads(bids) if bids else {}
    pending = [pid for pid in assigned
               if str(pid) not in bids or not isinstance(bids.get(str(pid)), dict)
               or not bids[str(pid)].get("recommendation")]
    return str(len(pending))


def solve_017(client, base="/sites/conference-review-submission"):
    client.post(f"{base}/api/login",
                json={"username": "reviewer_psharma", "password": "pass456"})
    # Get first assigned paper
    r = client.get(f"{base}/api/users/2")
    user = json.loads(r.data)
    assigned = user.get("assigned_papers", [])
    if isinstance(assigned, str):
        assigned = json.loads(assigned) if assigned else []
    if not assigned:
        return "no_papers"
    paper_id = assigned[0]
    r = client.post(f"{base}/api/users/2/review", json={
        "paper_id": paper_id,
        "recommendation": 7,
        "confidence": 4,
        "comments": "Good paper with solid contributions.",
        "title": "Solid work",
    })
    return json.loads(r.data).get("action", "")


def solve_018(client, base="/sites/conference-review-submission"):
    client.post(f"{base}/api/login",
                json={"username": "chair_knguyen", "password": "pass321"})
    # Get a paper from ICLR to assign
    r = client.get(f"{base}/api/papers?venue_id=iclr-2017&limit=1")
    papers = json.loads(r.data)
    if not papers:
        return "no_papers"
    paper_id = papers[0]["id"]
    r = client.post(f"{base}/api/users/2/assign", json={"paper_id": paper_id})
    return json.loads(r.data).get("action", "")


def solve_019(client, base="/sites/conference-review-submission"):
    client.post(f"{base}/api/login",
                json={"username": "reviewer_psharma", "password": "pass456"})
    r = client.get(f"{base}/api/users/2")
    user = json.loads(r.data)
    venue_roles = user.get("venue_roles", {})
    if isinstance(venue_roles, str):
        venue_roles = json.loads(venue_roles) if venue_roles else {}
    return str(len(venue_roles))


def solve_020(client, base="/sites/conference-review-submission"):
    r = client.get(f"{base}/api/decisions?venue_id=iclr-2017")
    decisions = json.loads(r.data)
    count = sum(1 for d in decisions
                if d["accepted"] and d.get("avg_score") is not None and d["avg_score"] < 5)
    return str(count)
