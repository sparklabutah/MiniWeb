"""Per-macro verification functions for conference-review-submission.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/conference-review-submission"


def verify_macro_navigate_by_link(server_url):
    # Homepage -> venue list -> ICLR 2017 venue page
    r = requests.get(f"{_base(server_url)}/venue/iclr-2017")
    return {"pass": r.status_code == 200, "detail": f"ICLR 2017 venue page: {r.status_code}"}


def verify_macro_navigate_by_route(server_url):
    # Get first paper ID from ICLR
    r = requests.get(f"{_base(server_url)}/api/papers?venue_id=iclr-2017&limit=1")
    papers = r.json()
    if not papers:
        return {"pass": False, "detail": "No papers"}
    pid = papers[0]["id"]
    r2 = requests.get(f"{_base(server_url)}/paper/{pid}")
    return {"pass": r2.status_code == 200, "detail": f"Paper detail page: {r2.status_code}"}


def verify_macro_search_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/papers/search?q=learning&venue_id=iclr-2017")
    results = r.json()
    return {"pass": len(results) > 0, "detail": f"search_by_query 'learning': {len(results)} results"}


def verify_macro_filter_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/papers?status=accepted&venue_id=iclr-2017")
    papers = r.json()
    ok = all(p.get("accepted") for p in papers)
    return {"pass": ok, "detail": f"filter_by_dropdown accepted: {len(papers)} papers, all_accepted={ok}"}


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/venues/iclr-2017")
    venue = r.json()
    return {"pass": "paper_count" in venue and "name" in venue,
            "detail": f"extract_by_route: venue={venue.get('name')}, papers={venue.get('paper_count')}"}


def verify_macro_extract_from_stats(server_url):
    r = requests.get(f"{_base(server_url)}/api/stats?venue_id=iclr-2017")
    stats = r.json()
    return {"pass": "acceptance_rate" in stats and "total_papers" in stats,
            "detail": f"extract_from_stats: total={stats.get('total_papers')}, rate={stats.get('acceptance_rate')}"}


def verify_macro_extract_from_list(server_url):
    r = requests.get(f"{_base(server_url)}/api/venues")
    venues = r.json()
    return {"pass": len(venues) > 0, "detail": f"extract_from_list: {len(venues)} venues"}


def verify_macro_sort_by_ranking(server_url):
    r = requests.get(f"{_base(server_url)}/api/papers?venue_id=iclr-2017&sort=score_desc")
    papers = r.json()
    if len(papers) < 2:
        return {"pass": True, "detail": "Too few papers to verify sort"}
    scores = [(p.get("avg_score") or 0) for p in papers]
    is_sorted = all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))
    return {"pass": is_sorted, "detail": f"sort_by_ranking: sorted_desc={is_sorted}"}


def verify_macro_filter_by_score_range(server_url):
    r = requests.get(f"{_base(server_url)}/api/papers?venue_id=iclr-2017&score_min=5&score_max=8")
    papers = r.json()
    ok = all(5 <= (p.get("avg_score") or 0) <= 8 for p in papers)
    return {"pass": ok, "detail": f"filter_by_score_range 5-8: {len(papers)} papers, all_in_range={ok}"}


def verify_macro_export_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/export?format=csv&venue_id=iclr-2017")
    lines = r.text.strip().split("\n")
    return {"pass": len(lines) > 1, "detail": f"export CSV: {len(lines)} lines"}


def verify_macro_compute_from_stats(server_url):
    r = requests.get(f"{_base(server_url)}/api/stats?venue_id=iclr-2017")
    stats = r.json()
    return {"pass": "total_reviews" in stats and "avg_reviews_per_paper" in stats,
            "detail": f"compute_from_stats: reviews={stats.get('total_reviews')}, avg={stats.get('avg_reviews_per_paper')}"}


def verify_macro_compute_from_api(server_url):
    r = requests.get(f"{_base(server_url)}/api/decisions?venue_id=iclr-2017")
    data = r.json()
    return {"pass": len(data) > 0 and "accepted" in data[0],
            "detail": f"compute_from_api: {len(data)} decisions returned"}


def verify_macro_authenticate_by_form(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/login",
                      json={"username": "reviewer_psharma", "password": "pass456"})
    data = r.json()
    ok = data.get("user_id") == 2
    return {"pass": ok, "detail": f"authenticate: user_id={data.get('user_id')}"}


def verify_macro_navigate_console(server_url):
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login",
           json={"username": "reviewer_psharma", "password": "pass456"})
    r = s.get(f"{base}/console")
    return {"pass": r.status_code == 200, "detail": f"Console page: {r.status_code}"}


def verify_macro_bid_by_toggle(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/users/2/bid", json={"paper_id": "test-macro-99"})
    data = r.json()
    ok = data.get("action") == "bid"
    requests.post(f"{base}/api/users/2/bid", json={"paper_id": "test-macro-99"})
    return {"pass": ok, "detail": f"bid_by_toggle: action={data.get('action')}"}


def verify_macro_submit_review(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/users/2/review", json={
        "paper_id": "test-macro-99",
        "recommendation": 5,
        "confidence": 3,
        "comments": "Test review for macro verification.",
        "title": "Test Review",
    })
    data = r.json()
    ok = data.get("action") == "reviewed"
    return {"pass": ok, "detail": f"submit_review: action={data.get('action')}"}


def verify_macro_assign_by_form(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/users/2/assign", json={"paper_id": "test-macro-99"})
    data = r.json()
    ok = data.get("action") == "assigned"
    requests.post(f"{base}/api/users/2/assign", json={"paper_id": "test-macro-99"})
    return {"pass": ok, "detail": f"assign_by_form: action={data.get('action')}"}
