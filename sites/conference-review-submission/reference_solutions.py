"""Per-task reference solutions via Flask test client for conference-review-submission."""
import json


def solve_001(client, base="/sites/conference-review-submission"):
    r = client.get(f"{base}/api/stats")
    stats = json.loads(r.data)
    return str(stats["total_papers"])


def solve_002(client, base="/sites/conference-review-submission"):
    r = client.get(f"{base}/api/papers?sort=title&limit=1")
    papers = json.loads(r.data)
    return papers[0]["title"] if papers else ""


def solve_003(client, base="/sites/conference-review-submission"):
    r = client.get(f"{base}/api/papers/search?q=generative")
    return str(len(json.loads(r.data)))


def solve_004(client, base="/sites/conference-review-submission"):
    r = client.get(f"{base}/api/papers?status=accepted")
    return str(len(json.loads(r.data)))


def solve_005(client, base="/sites/conference-review-submission"):
    r = client.get(f"{base}/api/papers/1")
    paper = json.loads(r.data)
    return paper["decision"]


def solve_006(client, base="/sites/conference-review-submission"):
    r = client.get(f"{base}/api/stats")
    stats = json.loads(r.data)
    return str(stats["acceptance_rate"])


def solve_007(client, base="/sites/conference-review-submission"):
    r = client.get(f"{base}/api/papers?sort=score_desc&limit=1")
    papers = json.loads(r.data)
    return papers[0]["title"] if papers else ""


def solve_008(client, base="/sites/conference-review-submission"):
    r = client.get(f"{base}/api/papers/5/reviews")
    reviews = json.loads(r.data)
    return str(len(reviews))


def solve_009(client, base="/sites/conference-review-submission"):
    r = client.get(f"{base}/api/papers/10/scores")
    data = json.loads(r.data)
    return str(data["avg_score"])


def solve_010(client, base="/sites/conference-review-submission"):
    r = client.get(f"{base}/api/papers?score_min=7")
    return str(len(json.loads(r.data)))


def solve_011(client, base="/sites/conference-review-submission"):
    r = client.get(f"{base}/api/stats")
    stats = json.loads(r.data)
    return f"Accepted: {stats['avg_accepted_score']}, Rejected: {stats['avg_rejected_score']}"


def solve_012(client, base="/sites/conference-review-submission"):
    r = client.get(f"{base}/api/papers/search?q=Yoshua+Bengio")
    return str(len(json.loads(r.data)))


def solve_013(client, base="/sites/conference-review-submission"):
    r = client.get(f"{base}/api/export?format=csv&status=accepted")
    lines = r.data.decode().strip().split("\n")
    return str(len(lines) - 1)


def solve_014(client, base="/sites/conference-review-submission"):
    r = client.get(f"{base}/api/stats")
    return str(json.loads(r.data)["unique_authors"])


def solve_015(client, base="/sites/conference-review-submission"):
    r = client.get(f"{base}/api/stats")
    return str(json.loads(r.data)["total_reviews"])


def solve_016(client, base="/sites/conference-review-submission"):
    client.post(f"{base}/api/login",
                json={"username": "reviewer_alice", "password": "pass123"})
    r = client.post(f"{base}/api/users/1/bid", json={"paper_id": 3})
    return json.loads(r.data).get("action", "")


def solve_017(client, base="/sites/conference-review-submission"):
    client.post(f"{base}/api/login",
                json={"username": "reviewer_bob", "password": "pass456"})
    r = client.post(f"{base}/api/users/2/review", json={
        "paper_id": 2,
        "recommendation": 7,
        "confidence": 4,
        "comments": "Good paper with solid contributions.",
        "title": "Solid work",
    })
    return json.loads(r.data).get("action", "")


def solve_018(client, base="/sites/conference-review-submission"):
    client.post(f"{base}/api/login",
                json={"username": "chair_eve", "password": "pass654"})
    r = client.post(f"{base}/api/users/1/assign", json={"paper_id": 4})
    return json.loads(r.data).get("action", "")


def solve_019(client, base="/sites/conference-review-submission"):
    client.post(f"{base}/api/login",
                json={"username": "reviewer_frank", "password": "pass987"})
    for pid in [1, 5, 7]:
        client.post(f"{base}/api/users/6/bid", json={"paper_id": pid})
    r = client.get(f"{base}/api/users/6")
    user = json.loads(r.data)
    return str(len(user.get("bids", {})))


def solve_020(client, base="/sites/conference-review-submission"):
    r = client.get(f"{base}/api/decisions")
    decisions = json.loads(r.data)
    count = sum(1 for d in decisions
                if d["accepted"] and d.get("avg_score") is not None and d["avg_score"] < 5)
    return str(count)
