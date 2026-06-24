"""Per-macro verification functions for conference-review-submission.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/conference-review-submission"


def verify_macro_navigate_by_link(server_url):
    r = requests.get(f"{_base(server_url)}/stats")
    return {"pass": r.status_code == 200, "detail": f"Stats page: {r.status_code}"}


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/paper/1")
    return {"pass": r.status_code == 200, "detail": f"Paper detail page: {r.status_code}"}


def verify_macro_search_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/papers/search?q=learning")
    results = r.json()
    return {"pass": len(results) > 0, "detail": f"search_by_query 'learning': {len(results)} results"}


def verify_macro_filter_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/papers?status=accepted")
    papers = r.json()
    ok = all(p.get("accepted") for p in papers)
    return {"pass": ok, "detail": f"filter_by_dropdown accepted: {len(papers)} papers, all_accepted={ok}"}


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/papers/1")
    paper = r.json()
    return {"pass": "decision" in paper and "abstract" in paper,
            "detail": f"extract_by_route: paper 1 decision={paper.get('decision')}"}


def verify_macro_extract_from_stats(server_url):
    r = requests.get(f"{_base(server_url)}/api/stats")
    stats = r.json()
    return {"pass": "acceptance_rate" in stats and "total_papers" in stats,
            "detail": f"extract_from_stats: total={stats.get('total_papers')}, rate={stats.get('acceptance_rate')}"}


def verify_macro_sort_by_ranking(server_url):
    r = requests.get(f"{_base(server_url)}/api/papers?sort=score_desc")
    papers = r.json()
    if len(papers) < 2:
        return {"pass": True, "detail": "Too few papers to verify sort"}
    scores = [(p.get("avg_score") or 0) for p in papers]
    is_sorted = all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))
    return {"pass": is_sorted, "detail": f"sort_by_ranking: sorted_desc={is_sorted}"}


def verify_macro_filter_by_score_range(server_url):
    r = requests.get(f"{_base(server_url)}/api/papers?score_min=5&score_max=8")
    papers = r.json()
    ok = all(5 <= (p.get("avg_score") or 0) <= 8 for p in papers)
    return {"pass": ok, "detail": f"filter_by_score_range 5-8: {len(papers)} papers, all_in_range={ok}"}


def verify_macro_export_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/export?format=csv")
    lines = r.text.strip().split("\n")
    return {"pass": len(lines) > 1, "detail": f"export CSV: {len(lines)} lines"}


def verify_macro_compute_from_stats(server_url):
    r = requests.get(f"{_base(server_url)}/api/stats")
    stats = r.json()
    return {"pass": "total_reviews" in stats and "avg_reviews_per_paper" in stats,
            "detail": f"compute_from_stats: reviews={stats.get('total_reviews')}, avg={stats.get('avg_reviews_per_paper')}"}


def verify_macro_compute_from_api(server_url):
    r = requests.get(f"{_base(server_url)}/api/decisions")
    data = r.json()
    return {"pass": len(data) > 0 and "accepted" in data[0],
            "detail": f"compute_from_api: {len(data)} decisions returned"}


def verify_macro_authenticate_by_form(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/login",
                      json={"username": "reviewer_alice", "password": "pass123"})
    data = r.json()
    ok = data.get("user_id") == 1
    return {"pass": ok, "detail": f"authenticate: user_id={data.get('user_id')}"}


def verify_macro_bid_by_toggle(server_url):
    base = _base(server_url)
    # Use a throwaway paper ID for testing
    r = requests.post(f"{base}/api/users/8/bid", json={"paper_id": 99})
    data = r.json()
    ok = data.get("action") == "bid"
    # Toggle back
    requests.post(f"{base}/api/users/8/bid", json={"paper_id": 99})
    return {"pass": ok, "detail": f"bid_by_toggle: action={data.get('action')}"}


def verify_macro_submit_review(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/users/8/review", json={
        "paper_id": 99,
        "recommendation": 5,
        "confidence": 3,
        "comments": "Test review for macro verification.",
        "title": "Test Review",
    })
    data = r.json()
    ok = data.get("action") == "reviewed"
    # Clean up: remove the test review by bidding (toggle removes it)
    return {"pass": ok, "detail": f"submit_review: action={data.get('action')}"}


def verify_macro_assign_by_form(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/users/8/assign", json={"paper_id": 99})
    data = r.json()
    ok = data.get("action") == "assigned"
    # Toggle back
    requests.post(f"{base}/api/users/8/assign", json={"paper_id": 99})
    return {"pass": ok, "detail": f"assign_by_form: action={data.get('action')}"}
