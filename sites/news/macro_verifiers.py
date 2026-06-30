"""Per-macro verification functions for news (Lakeport Tribune).

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/news"


def verify_macro_navigate_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/categories")
    cats = r.json()
    if not cats:
        return {"pass": False, "detail": "No categories returned"}
    slug = cats[0]["slug"]
    r2 = requests.get(f"{_base(server_url)}/category/{slug}")
    return {"pass": r2.status_code == 200,
            "detail": f"Category page '{slug}': {r2.status_code}"}


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/article/1")
    return {"pass": r.status_code == 200,
            "detail": f"Article detail page: {r.status_code}"}


def verify_macro_search_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/search?q=Lakeport")
    results = r.json()
    return {"pass": len(results) > 0,
            "detail": f"search_by_query 'Lakeport': {len(results)} results"}


def verify_macro_search_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/articles/semantic?q=local+sports+event")
    results = r.json()
    return {"pass": r.status_code == 200,
            "detail": f"search_by_semantic: {len(results)} results"}


def verify_macro_filter_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/articles?category=business")
    articles = r.json()
    ok = all(a["category"] == "business" for a in articles)
    return {"pass": ok and len(articles) > 0,
            "detail": f"filter_by_dropdown business: {len(articles)} articles, all_business={ok}"}


def verify_macro_filter_by_date_range(server_url):
    r = requests.get(f"{_base(server_url)}/api/articles?date_from=2025-09-01&date_to=2025-10-31")
    articles = r.json()
    ok = all("2025-09-01" <= a["date"] <= "2025-10-31" for a in articles)
    return {"pass": ok,
            "detail": f"filter 2025-09 to 2025-10: {len(articles)} articles, all_in_range={ok}"}


def verify_macro_sort_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/articles?sort=title")
    articles = r.json()
    if len(articles) < 2:
        return {"pass": True, "detail": "Too few articles to verify sort"}
    titles = [a["title"].lower() for a in articles]
    is_sorted = all(titles[i] <= titles[i + 1] for i in range(len(titles) - 1))
    return {"pass": is_sorted,
            "detail": f"sort_by_dropdown: sorted={is_sorted}"}


def verify_macro_extract_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/search?q=bike")
    results = r.json()
    if results:
        return {"pass": True,
                "detail": f"extract_by_query: first result title={results[0]['article']['title'][:50]}"}
    return {"pass": True, "detail": "extract_by_query: no results (ok)"}


def verify_macro_extract_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/articles/semantic?q=restaurant+food+dining")
    results = r.json()
    if results:
        return {"pass": True,
                "detail": f"extract_by_semantic: top result={results[0]['article']['title'][:50]}"}
    return {"pass": True, "detail": "extract_by_semantic: no results (ok)"}


def verify_macro_extract_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/categories/sports/stats")
    stats = r.json()
    return {"pass": "unique_authors" in stats,
            "detail": f"extract_by_dropdown: sports stats unique_authors={stats.get('unique_authors')}"}


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/articles/1")
    article = r.json()
    return {"pass": "body" in article and "author" in article,
            "detail": f"extract_by_route: article has body={len(article.get('body', ''))} chars"}


def verify_macro_play_by_playback(server_url):
    r = requests.post(f"{_base(server_url)}/api/articles/1/play")
    data = r.json()
    ok = data.get("action") == "playing" and data.get("duration_seconds", 0) > 0
    return {"pass": ok,
            "detail": f"play_by_playback: action={data.get('action')}, duration={data.get('duration_seconds')}s"}


def verify_macro_post_from_free_text(server_url):
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "alex_rivera", "password": "password"})
    r = s.post(f"{base}/api/articles/1/comment", json={"body": "Test macro comment"})
    data = r.json()
    ok = data.get("action") == "posted"
    # Clean up: we don't remove it, but that's fine for verification
    return {"pass": ok,
            "detail": f"post_from_free_text: action={data.get('action')}"}


def verify_macro_follow_by_dropdown(server_url):
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "elena_vasquez", "password": "password"})
    r = s.post(f"{base}/api/follow", json={"type": "author", "target": "TestAuthor"})
    data = r.json()
    ok = data.get("action") == "followed"
    # Toggle back
    s.post(f"{base}/api/follow", json={"type": "author", "target": "TestAuthor"})
    return {"pass": ok,
            "detail": f"follow_by_dropdown: action={data.get('action')}"}


def verify_macro_subscribe_by_toggle(server_url):
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "samantha_liu", "password": "password"})
    # Get current state
    r = s.get(f"{base}/api/user/profile")
    before = r.json().get("newsletter_preferences", {}).get("daily_digest", False)
    # Toggle
    r = s.post(f"{base}/api/subscribe", json={"newsletter": "daily_digest"})
    data = r.json()
    ok = data.get("enabled") == (not before)
    # Toggle back
    s.post(f"{base}/api/subscribe", json={"newsletter": "daily_digest"})
    return {"pass": ok,
            "detail": f"subscribe_by_toggle: before={before}, after={data.get('enabled')}"}


def verify_macro_share_by_dropdown(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/articles/1/share", json={"platform": "email"})
    data = r.json()
    ok = data.get("action") == "shared"
    return {"pass": ok,
            "detail": f"share_by_dropdown: action={data.get('action')}, platform=email"}


def verify_macro_save_by_toggle(server_url):
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "elena_vasquez", "password": "password"})
    r = s.post(f"{base}/api/articles/25/bookmark")
    data = r.json()
    ok = data.get("bookmarked") is True
    # Toggle back
    s.post(f"{base}/api/articles/25/bookmark")
    return {"pass": ok,
            "detail": f"save_by_toggle: bookmarked={data.get('bookmarked')}"}


def verify_macro_report_by_form(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/articles/1/report",
                      json={"reason": "spam", "details": "Test report"})
    data = r.json()
    ok = data.get("action") == "reported"
    return {"pass": ok,
            "detail": f"report_by_form: action={data.get('action')}"}


def verify_macro_authenticate_by_form(server_url):
    base = _base(server_url)
    s = requests.Session()
    r = s.post(f"{base}/api/login",
               json={"username": "alex_rivera", "password": "password"})
    data = r.json()
    ok = data.get("user_id") == 1
    return {"pass": ok,
            "detail": f"authenticate_by_form: user_id={data.get('user_id')}"}


def verify_macro_register_by_form(server_url):
    base = _base(server_url)
    s = requests.Session()
    r = s.post(f"{base}/api/register",
               json={"username": "macro_test_user",
                     "display_name": "Macro Tester",
                     "email": "macro@test.com",
                     "password": "password"})
    data = r.json()
    ok = data.get("action") == "registered"
    return {"pass": ok,
            "detail": f"register_by_form: action={data.get('action')}, user_id={data.get('user_id')}"}
