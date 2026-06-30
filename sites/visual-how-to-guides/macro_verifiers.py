"""Per-macro verification functions for visual-how-to-guides.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/visual-how-to-guides"


def verify_macro_navigate_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/categories")
    cats = r.json()
    if not cats:
        return {"pass": False, "detail": "No categories returned"}
    cat_id = cats[0]["id"]
    r2 = requests.get(f"{_base(server_url)}/category/{cat_id}")
    return {"pass": r2.status_code == 200,
            "detail": f"Category page '{cats[0]['name']}': {r2.status_code}"}


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/guide/1")
    return {"pass": r.status_code == 200,
            "detail": f"Guide detail page: {r.status_code}"}


def verify_macro_search_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/search?q=bread")
    results = r.json()
    return {"pass": len(results) > 0,
            "detail": f"search_by_query 'bread': {len(results)} results"}


def verify_macro_search_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/search/semantic?q=outdoor+planting+vegetables")
    results = r.json()
    return {"pass": r.status_code == 200,
            "detail": f"search_by_semantic: {len(results)} results"}


def verify_macro_filter_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/guides?category=Cooking")
    guides = r.json()
    ok = all(g["category"] == "Cooking" for g in guides)
    return {"pass": ok and len(guides) > 0,
            "detail": f"filter_by_dropdown Cooking: {len(guides)} guides, all_cooking={ok}"}


def verify_macro_filter_by_slider(server_url):
    # Test difficulty slider
    r = requests.get(f"{_base(server_url)}/api/guides?difficulty_min=2&difficulty_max=3")
    guides = r.json()
    ok = all(g["difficulty"] in ("medium", "hard") for g in guides)
    if not ok or not guides:
        return {"pass": False,
                "detail": f"filter_by_slider difficulty 2-3: {len(guides)} guides, all_valid={ok}"}
    # Test duration slider
    r2 = requests.get(f"{_base(server_url)}/api/guides?duration_min=30&duration_max=60")
    guides2 = r2.json()
    ok2 = all(30 <= g.get("duration_minutes", 0) <= 60 for g in guides2)
    return {"pass": ok and ok2,
            "detail": f"filter_by_slider: difficulty={len(guides)}, duration 30-60={len(guides2)}, valid={ok and ok2}"}


def verify_macro_sort_by_ranking(server_url):
    r = requests.get(f"{_base(server_url)}/api/guides?sort=rating")
    guides = r.json()
    if len(guides) < 2:
        return {"pass": True, "detail": "Too few guides to verify sort"}
    ratings = [g.get("rating", 0) for g in guides]
    is_sorted = all(ratings[i] >= ratings[i + 1] for i in range(len(ratings) - 1))
    return {"pass": is_sorted,
            "detail": f"sort_by_ranking: sorted_desc={is_sorted}, top={guides[0]['title']}"}


def verify_macro_extract_from_table(server_url):
    r = requests.get(f"{_base(server_url)}/api/compare?ids=1,4")
    guides = r.json()
    return {"pass": len(guides) == 2,
            "detail": f"extract_from_table: compare returned {len(guides)} guides"}


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/guides/1")
    guide = r.json()
    return {"pass": "description" in guide and "steps" in guide,
            "detail": f"extract_by_route: guide has description={len(guide.get('description', ''))} chars, steps={len(guide.get('steps', []))}"}


def verify_macro_play_by_date_range(server_url):
    r = requests.get(f"{_base(server_url)}/api/guides?date_from=2025-06-01&date_to=2025-08-31")
    guides = r.json()
    ok = all("2025-06-01" <= g.get("created_at", "") <= "2025-08-31" for g in guides)
    return {"pass": ok,
            "detail": f"play_by_date_range 2025-06 to 2025-08: {len(guides)} guides, all_in_range={ok}"}


def verify_macro_play_by_playback(server_url):
    r = requests.get(f"{_base(server_url)}/api/guides/1/steps/1")
    data = r.json()
    step = data.get("step", {})
    has_nav = data.get("total_steps", 0) > 0 and data.get("step_num") == 1
    return {"pass": has_nav and "title" in step,
            "detail": f"play_by_playback: step 1 title='{step.get('title', '')}', total={data.get('total_steps')}"}


def verify_macro_post_from_free_text(server_url):
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "green_derek", "password": "pass423"})
    r = s.post(f"{base}/api/guides/1/comments",
               json={"text": "Macro verifier test comment"})
    data = r.json()
    ok = data.get("id") is not None
    # Clean up: no toggle needed for comments (they stay)
    return {"pass": ok,
            "detail": f"post_from_free_text: comment_id={data.get('id')}"}


def verify_macro_react_by_toggle(server_url):
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "green_derek", "password": "pass423"})
    r = s.post(f"{base}/api/comments/1/react",
               json={"reaction": "helpful"})
    data = r.json()
    ok = data.get("action") in ("helpful", "removed")
    # Toggle back to clean state
    s.post(f"{base}/api/comments/1/react", json={"reaction": "helpful"})
    return {"pass": ok,
            "detail": f"react_by_toggle: action={data.get('action')}"}


def verify_macro_rate_by_slider(server_url):
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "craft_lisa", "password": "pass523"})
    r = s.post(f"{base}/api/guides/1/rate", json={"score": 3})
    data = r.json()
    ok = data.get("action") == "rated" and data.get("new_average") is not None
    return {"pass": ok,
            "detail": f"rate_by_slider: score=3, new_avg={data.get('new_average')}"}


def verify_macro_follow_by_dropdown(server_url):
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "craft_lisa", "password": "pass523"})
    r = s.post(f"{base}/api/users/5/follow", json={"author": "TestAuthor"})
    data = r.json()
    ok = data.get("action") == "followed"
    # Toggle back
    s.post(f"{base}/api/users/5/follow", json={"author": "TestAuthor"})
    return {"pass": ok,
            "detail": f"follow_by_dropdown: action={data.get('action')}"}


def verify_macro_save_by_toggle(server_url):
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "craft_lisa", "password": "pass523"})
    r = s.post(f"{base}/api/guides/20/bookmark")
    data = r.json()
    ok = data.get("action") == "bookmarked"
    # Toggle back
    s.post(f"{base}/api/guides/20/bookmark")
    return {"pass": ok,
            "detail": f"save_by_toggle: action={data.get('action')}"}
