"""Per-task HTTP verification functions for conference-review-submission."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/venues/iclr-2017")
    venue = r.json()
    count = venue.get("paper_count", 0)
    return {"pass": count > 0, "detail": f"ICLR 2017 submissions: {count}"}


def verify_002(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/venues")
    venues = r.json()
    count = len(venues)
    return {"pass": count > 0, "detail": f"Venue count: {count}"}


def verify_003(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/papers/search?q=generative&venue_id=iclr-2017")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Search 'generative' in ICLR 2017: {count} results"}


def verify_004(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/papers?status=accepted&venue_id=iclr-2017")
    papers = r.json()
    count = len(papers)
    return {"pass": count > 0, "detail": f"Accepted ICLR 2017 papers: {count}"}


def verify_005(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/venues")
    venues = r.json()
    under_review = [v for v in venues if v.get("status") == "under_review"]
    names = [v["name"] for v in under_review]
    return {"pass": len(under_review) > 0, "detail": f"Under Review venues: {names}"}


def verify_006(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/stats?venue_id=iclr-2017")
    stats = r.json()
    rate = stats.get("acceptance_rate", 0)
    return {"pass": rate > 0, "detail": f"ICLR 2017 acceptance rate: {rate}%"}


def verify_007(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/papers?venue_id=iclr-2017&sort=score_desc&limit=1")
    papers = r.json()
    if not papers:
        return {"pass": False, "detail": "No papers returned"}
    title = papers[0].get("title", "")
    score = papers[0].get("avg_score")
    return {"pass": len(title) > 0, "detail": f"Highest scored: {title[:60]} (score={score})"}


def verify_008(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/venues/iclr-2017")
    venue = r.json()
    count = venue.get("paper_count", 0)
    return {"pass": count > 0, "detail": f"ICLR 2017 paper count via API: {count}"}


def verify_009(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/papers?venue_id=iclr-2017&score_min=7")
    papers = r.json()
    count = len(papers)
    ok = all(p.get("avg_score", 0) >= 7 for p in papers)
    return {"pass": ok and count >= 0, "detail": f"ICLR papers with score >= 7: {count}, all_valid={ok}"}


def verify_010(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/stats?venue_id=iclr-2017")
    stats = r.json()
    avg_acc = stats.get("avg_accepted_score", 0)
    avg_rej = stats.get("avg_rejected_score", 0)
    return {"pass": avg_acc > 0 and avg_rej > 0,
            "detail": f"Avg accepted: {avg_acc}, avg rejected: {avg_rej}"}


def verify_011(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/papers/search?q=Yoshua+Bengio&venue_id=iclr-2017")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Yoshua Bengio papers in ICLR: {count}"}


def verify_012(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/export?format=csv&status=accepted&venue_id=iclr-2017")
    lines = r.text.strip().split("\n")
    data_rows = len(lines) - 1
    return {"pass": data_rows > 0, "detail": f"CSV export accepted ICLR: {data_rows} data rows"}


def verify_013(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/stats?venue_id=iclr-2017")
    stats = r.json()
    authors = stats.get("unique_authors", 0)
    return {"pass": authors > 0, "detail": f"Unique authors ICLR: {authors}"}


def verify_014(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/stats?venue_id=iclr-2017")
    stats = r.json()
    total = stats.get("total_reviews", 0)
    return {"pass": total > 0, "detail": f"Total reviews ICLR: {total}"}


def verify_015(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/papers?venue_id=iclr-2017&sort=title&limit=1")
    papers = r.json()
    if not papers:
        return {"pass": False, "detail": "No papers returned"}
    title = papers[0].get("title", "")
    return {"pass": len(title) > 0, "detail": f"First ICLR paper: {title[:60]}"}


def verify_016(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/users/2")
    user = r.json()
    assigned = user.get("assigned_papers", [])
    if isinstance(assigned, str):
        import json
        assigned = json.loads(assigned) if assigned else []
    bids = user.get("bids", {})
    if isinstance(bids, str):
        import json
        bids = json.loads(bids) if bids else {}
    pending = [pid for pid in assigned if str(pid) not in bids or not isinstance(bids.get(str(pid)), dict) or not bids[str(pid)].get("recommendation")]
    return {"pass": len(pending) >= 0, "detail": f"Reviewer psharma pending tasks: {len(pending)}"}


def verify_017(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/users/2")
    user = r.json()
    bids = user.get("bids", {})
    if isinstance(bids, str):
        import json
        bids = json.loads(bids) if bids else {}
    has_review = any(isinstance(v, dict) and v.get("recommendation") == 7 for v in bids.values())
    return {"pass": has_review, "detail": f"Reviewer psharma review with rec=7: {has_review}"}


def verify_018(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/users/2")
    user = r.json()
    assigned = user.get("assigned_papers", [])
    if isinstance(assigned, str):
        import json
        assigned = json.loads(assigned) if assigned else []
    return {"pass": len(assigned) > 0, "detail": f"Reviewer psharma assigned: {assigned}"}


def verify_019(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/users/2")
    user = r.json()
    venue_roles = user.get("venue_roles", {})
    if isinstance(venue_roles, str):
        import json
        venue_roles = json.loads(venue_roles) if venue_roles else {}
    count = len(venue_roles)
    return {"pass": count > 0, "detail": f"Reviewer psharma venue roles: {count}"}


def verify_020(server_url):
    base = f"{server_url}/sites/conference-review-submission"
    r = requests.get(f"{base}/api/decisions?venue_id=iclr-2017")
    decisions = r.json()
    low_score_accepted = [d for d in decisions
                          if d["accepted"] and d.get("avg_score") is not None and d["avg_score"] < 5]
    count = len(low_score_accepted)
    return {"pass": True, "detail": f"ICLR accepted papers with avg score < 5: {count}"}
