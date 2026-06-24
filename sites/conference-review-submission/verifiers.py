"""Per-task HTTP verification functions for conference-review-submission."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/stats")
    stats = r.json()
    total = stats.get("total_papers", 0)
    return {"pass": total > 0, "detail": f"Total submissions: {total}"}


def verify_002(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/papers?sort=title&limit=1")
    papers = r.json()
    if not papers:
        return {"pass": False, "detail": "No papers returned"}
    title = papers[0].get("title", "")
    return {"pass": len(title) > 0, "detail": f"First paper title: {title[:60]}"}


def verify_003(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/papers/search?q=generative")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Search 'generative': {count} results"}


def verify_004(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/papers?status=accepted")
    papers = r.json()
    count = len(papers)
    return {"pass": count > 0, "detail": f"Accepted papers: {count}"}


def verify_005(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/papers/1")
    paper = r.json()
    decision = paper.get("decision", "")
    return {"pass": decision in ("Accept", "Reject"), "detail": f"Paper 1 decision: {decision}"}


def verify_006(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/stats")
    stats = r.json()
    rate = stats.get("acceptance_rate", 0)
    return {"pass": rate > 0, "detail": f"Acceptance rate: {rate}%"}


def verify_007(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/papers?sort=score_desc&limit=1")
    papers = r.json()
    if not papers:
        return {"pass": False, "detail": "No papers returned"}
    title = papers[0].get("title", "")
    score = papers[0].get("avg_score")
    return {"pass": len(title) > 0, "detail": f"Highest scored: {title[:60]} (score={score})"}


def verify_008(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/papers/5/reviews")
    reviews = r.json()
    count = len(reviews)
    return {"pass": count > 0, "detail": f"Paper 5 has {count} reviews"}


def verify_009(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/papers/10/scores")
    data = r.json()
    avg = data.get("avg_score")
    return {"pass": avg is not None, "detail": f"Paper 10 avg score: {avg}"}


def verify_010(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/papers?score_min=7")
    papers = r.json()
    count = len(papers)
    ok = all(p.get("avg_score", 0) >= 7 for p in papers)
    return {"pass": ok and count >= 0, "detail": f"Papers with score >= 7: {count}, all_valid={ok}"}


def verify_011(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/stats")
    stats = r.json()
    avg_acc = stats.get("avg_accepted_score", 0)
    avg_rej = stats.get("avg_rejected_score", 0)
    return {"pass": avg_acc > 0 and avg_rej > 0,
            "detail": f"Avg accepted: {avg_acc}, avg rejected: {avg_rej}"}


def verify_012(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/papers/search?q=Yoshua+Bengio")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Yoshua Bengio papers: {count}"}


def verify_013(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/export?format=csv&status=accepted")
    lines = r.text.strip().split("\n")
    data_rows = len(lines) - 1
    return {"pass": data_rows > 0, "detail": f"CSV export accepted: {data_rows} data rows"}


def verify_014(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/stats")
    stats = r.json()
    authors = stats.get("unique_authors", 0)
    return {"pass": authors > 0, "detail": f"Unique authors: {authors}"}


def verify_015(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/stats")
    stats = r.json()
    total = stats.get("total_reviews", 0)
    return {"pass": total > 0, "detail": f"Total reviews: {total}"}


def verify_016(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/users/1")
    user = r.json()
    bids = user.get("bids", {})
    return {"pass": "3" in bids, "detail": f"User 1 bids: {list(bids.keys())}"}


def verify_017(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/users/2")
    user = r.json()
    bids = user.get("bids", {})
    review = bids.get("2", {})
    return {"pass": review.get("recommendation") == 7,
            "detail": f"User 2 review for paper 2: {review}"}


def verify_018(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/users/1")
    user = r.json()
    assigned = user.get("assigned_papers", [])
    return {"pass": 4 in assigned, "detail": f"User 1 assigned papers: {assigned}"}


def verify_019(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/users/6")
    user = r.json()
    bids = user.get("bids", {})
    expected = {"1", "5", "7"}
    actual = set(bids.keys())
    return {"pass": expected.issubset(actual) and len(bids) == 3,
            "detail": f"User 6 bids: {list(bids.keys())}"}


def verify_020(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/decisions")
    decisions = r.json()
    low_score_accepted = [d for d in decisions
                          if d["accepted"] and d.get("avg_score") is not None and d["avg_score"] < 5]
    count = len(low_score_accepted)
    return {"pass": True, "detail": f"Accepted papers with avg score < 5: {count}"}
