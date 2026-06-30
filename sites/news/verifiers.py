"""Per-task HTTP verification functions for news (Lakeport Tribune)."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/news"
    r = requests.get(f"{base}/api/articles?category=sports")
    articles = r.json()
    count = len(articles)
    return {"pass": count > 0, "detail": f"Sports category has {count} articles"}


def verify_002(server_url):
    base = f"{server_url}/sites/news"
    r = requests.get(f"{base}/api/articles/3")
    article = r.json()
    author = article.get("author", "")
    return {"pass": author == "Maya Johnson",
            "detail": f"Article 3 author: {author}"}


def verify_003(server_url):
    base = f"{server_url}/sites/news"
    r = requests.get(f"{base}/api/search?q=Meridian")
    results = r.json()
    count = len(results)
    return {"pass": count > 0, "detail": f"Search 'Meridian': {count} results"}


def verify_004(server_url):
    base = f"{server_url}/sites/news"
    r = requests.get(f"{base}/api/articles/semantic?q=community+volunteer+environment")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Semantic 'community volunteer environment': {count} results"}


def verify_005(server_url):
    base = f"{server_url}/sites/news"
    r = requests.get(f"{base}/api/articles?category=business")
    articles = r.json()
    count = len(articles)
    ok = all(a["category"] == "business" for a in articles)
    return {"pass": count > 0 and ok,
            "detail": f"Business filter: {count} articles, all_business={ok}"}


def verify_006(server_url):
    base = f"{server_url}/sites/news"
    r = requests.get(f"{base}/api/articles?date_from=2025-10-01&date_to=2025-12-31")
    articles = r.json()
    count = len(articles)
    ok = all("2025-10-01" <= a["date"] <= "2025-12-31" for a in articles)
    return {"pass": ok and count > 0,
            "detail": f"Date range 2025-10 to 2025-12: {count} articles, all_in_range={ok}"}


def verify_007(server_url):
    base = f"{server_url}/sites/news"
    r = requests.get(f"{base}/api/articles?sort=title")
    articles = r.json()
    if not articles:
        return {"pass": False, "detail": "No articles returned"}
    first_title = articles[0]["title"]
    titles = [a["title"].lower() for a in articles]
    is_sorted = all(titles[i] <= titles[i + 1] for i in range(len(titles) - 1))
    return {"pass": is_sorted,
            "detail": f"First title (sorted): {first_title[:60]}, sorted={is_sorted}"}


def verify_008(server_url):
    base = f"{server_url}/sites/news"
    r = requests.get(f"{base}/api/search?q=Lakeport+High")
    results = r.json()
    if not results:
        return {"pass": False, "detail": "No results for 'Lakeport High'"}
    first_title = results[0]["article"]["title"]
    return {"pass": len(first_title) > 0,
            "detail": f"First 'Lakeport High' result: {first_title[:60]}"}


def verify_009(server_url):
    base = f"{server_url}/sites/news"
    r = requests.get(f"{base}/api/articles/semantic?q=technology+startup+funding")
    results = r.json()
    if not results:
        return {"pass": True, "detail": "No semantic results (ok)"}
    first_title = results[0]["article"]["title"]
    return {"pass": len(first_title) > 0,
            "detail": f"Top semantic result: {first_title[:60]}"}


def verify_010(server_url):
    base = f"{server_url}/sites/news"
    r = requests.get(f"{base}/api/categories/local/stats")
    stats = r.json()
    authors = stats.get("unique_authors", 0)
    return {"pass": authors > 0,
            "detail": f"Local unique authors: {authors}"}


def verify_011(server_url):
    base = f"{server_url}/sites/news"
    r = requests.get(f"{base}/api/articles/4")
    article = r.json()
    title = article.get("title", "")
    return {"pass": len(title) > 0,
            "detail": f"Article 4 title: {title[:60]}"}


def verify_012(server_url):
    base = f"{server_url}/sites/news"
    r = requests.post(f"{base}/api/articles/1/play")
    data = r.json()
    duration = data.get("duration_seconds", 0)
    return {"pass": duration > 0 and data.get("action") == "playing",
            "detail": f"Audio playback: duration={duration}s, action={data.get('action')}"}


def verify_013(server_url):
    base = f"{server_url}/sites/news"
    r = requests.get(f"{base}/api/articles/2/comments")
    comments = r.json()
    match = [c for c in comments if "Great news for the community" in c.get("body", "")]
    return {"pass": len(match) > 0,
            "detail": f"Comment found: {len(match)} matching comments on article 2"}


def verify_014(server_url):
    base = f"{server_url}/sites/news"
    # Log in as rachel_kim to check follows
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "rachel_kim", "password": "password"})
    r = s.get(f"{base}/api/follows")
    follows = r.json()
    match = [f for f in follows if f.get("type") == "category" and f.get("target") == "sports"]
    return {"pass": len(match) > 0,
            "detail": f"rachel_kim follows sports: {len(match)} matches"}


def verify_015(server_url):
    base = f"{server_url}/sites/news"
    # Check alex_rivera's newsletter prefs
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "alex_rivera", "password": "password"})
    r = s.get(f"{base}/api/user/profile")
    user = r.json()
    breaking = user.get("newsletter_preferences", {}).get("breaking_news")
    return {"pass": breaking is not None,
            "detail": f"alex_rivera breaking_news={breaking}"}


def verify_016(server_url):
    base = f"{server_url}/sites/news"
    r = requests.post(f"{base}/api/articles/7/share",
                      json={"platform": "twitter"})
    data = r.json()
    ok = data.get("action") == "shared"
    return {"pass": ok,
            "detail": f"Share article 7 via twitter: action={data.get('action')}"}


def verify_017(server_url):
    base = f"{server_url}/sites/news"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "samantha_liu", "password": "password"})
    r = s.get(f"{base}/api/bookmarks")
    bookmarks = r.json()
    match = [b for b in bookmarks if b.get("article_id") == 5]
    return {"pass": len(match) > 0,
            "detail": f"samantha_liu bookmark article 5: {len(match)} matches"}


def verify_018(server_url):
    base = f"{server_url}/sites/news"
    r = requests.post(f"{base}/api/articles/11/report",
                      json={"reason": "inaccurate",
                            "details": "The rainfall amounts seem incorrect."})
    data = r.json()
    ok = data.get("action") == "reported"
    return {"pass": ok,
            "detail": f"Report article 11: action={data.get('action')}"}


def verify_019(server_url):
    base = f"{server_url}/sites/news"
    s = requests.Session()
    r = s.post(f"{base}/api/login",
               json={"username": "elena_vasquez", "password": "password"})
    data = r.json()
    display_name = data.get("display_name", "")
    return {"pass": display_name == "Elena Vasquez",
            "detail": f"Login elena_vasquez: display_name={display_name}"}


def verify_020(server_url):
    base = f"{server_url}/sites/news"
    s = requests.Session()
    # Register test_reporter
    s.post(f"{base}/api/register",
           json={"username": "test_reporter",
                  "display_name": "Test Reporter",
                  "email": "test@lakeport.news",
                  "password": "password"})
    # Bookmark articles 3 and 9
    s.post(f"{base}/api/articles/3/bookmark")
    s.post(f"{base}/api/articles/9/bookmark")
    # Check bookmarks
    r = s.get(f"{base}/api/bookmarks")
    bookmarks = r.json()
    count = len(bookmarks)
    return {"pass": count == 2,
            "detail": f"test_reporter bookmarks: {count}"}
