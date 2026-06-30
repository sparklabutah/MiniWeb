"""Per-task reference solutions via Flask test client for news (Lakeport Tribune)."""
import json


def solve_001(client, base="/sites/news"):
    r = client.get(f"{base}/api/articles?category=sports")
    return str(len(json.loads(r.data)))


def solve_002(client, base="/sites/news"):
    r = client.get(f"{base}/api/articles/3")
    return json.loads(r.data)["author"]


def solve_003(client, base="/sites/news"):
    r = client.get(f"{base}/api/search?q=Meridian")
    return str(len(json.loads(r.data)))


def solve_004(client, base="/sites/news"):
    r = client.get(f"{base}/api/articles/semantic?q=community+volunteer+environment")
    return str(len(json.loads(r.data)))


def solve_005(client, base="/sites/news"):
    r = client.get(f"{base}/api/articles?category=business")
    return str(len(json.loads(r.data)))


def solve_006(client, base="/sites/news"):
    r = client.get(f"{base}/api/articles?date_from=2025-10-01&date_to=2025-12-31")
    return str(len(json.loads(r.data)))


def solve_007(client, base="/sites/news"):
    r = client.get(f"{base}/api/articles?sort=title")
    articles = json.loads(r.data)
    return articles[0]["title"] if articles else ""


def solve_008(client, base="/sites/news"):
    r = client.get(f"{base}/api/search?q=Lakeport+High")
    results = json.loads(r.data)
    return results[0]["article"]["title"] if results else "No results"


def solve_009(client, base="/sites/news"):
    r = client.get(f"{base}/api/articles/semantic?q=technology+startup+funding")
    results = json.loads(r.data)
    return results[0]["article"]["title"] if results else "No results"


def solve_010(client, base="/sites/news"):
    r = client.get(f"{base}/api/categories/local/stats")
    return str(json.loads(r.data).get("unique_authors", 0))


def solve_011(client, base="/sites/news"):
    r = client.get(f"{base}/api/articles/4")
    return json.loads(r.data)["title"]


def solve_012(client, base="/sites/news"):
    r = client.post(f"{base}/api/articles/1/play")
    return str(json.loads(r.data).get("duration_seconds", 0))


def solve_013(client, base="/sites/news"):
    client.post(f"{base}/api/login",
                json={"username": "alex_rivera", "password": "password"},
                content_type="application/json")
    r = client.post(f"{base}/api/articles/2/comment",
                    json={"body": "Great news for the community!"},
                    content_type="application/json")
    return json.loads(r.data).get("action", "")


def solve_014(client, base="/sites/news"):
    client.post(f"{base}/api/login",
                json={"username": "rachel_kim", "password": "password"},
                content_type="application/json")
    r = client.post(f"{base}/api/follow",
                    json={"type": "category", "target": "sports"},
                    content_type="application/json")
    return json.loads(r.data).get("action", "")


def solve_015(client, base="/sites/news"):
    client.post(f"{base}/api/login",
                json={"username": "alex_rivera", "password": "password"},
                content_type="application/json")
    r = client.post(f"{base}/api/subscribe",
                    json={"newsletter": "breaking_news"},
                    content_type="application/json")
    data = json.loads(r.data)
    return str(data.get("enabled", ""))


def solve_016(client, base="/sites/news"):
    r = client.post(f"{base}/api/articles/7/share",
                    json={"platform": "twitter"},
                    content_type="application/json")
    return json.loads(r.data).get("action", "")


def solve_017(client, base="/sites/news"):
    client.post(f"{base}/api/login",
                json={"username": "samantha_liu", "password": "password"},
                content_type="application/json")
    r = client.post(f"{base}/api/articles/5/bookmark",
                    content_type="application/json")
    data = json.loads(r.data)
    return str(data.get("bookmarked", ""))


def solve_018(client, base="/sites/news"):
    r = client.post(f"{base}/api/articles/11/report",
                    json={"reason": "inaccurate",
                          "details": "The rainfall amounts seem incorrect."},
                    content_type="application/json")
    return json.loads(r.data).get("action", "")


def solve_019(client, base="/sites/news"):
    r = client.post(f"{base}/api/login",
                    json={"username": "elena_vasquez", "password": "password"},
                    content_type="application/json")
    return json.loads(r.data).get("display_name", "")


def solve_020(client, base="/sites/news"):
    client.post(f"{base}/api/register",
                json={"username": "test_reporter",
                      "display_name": "Test Reporter",
                      "email": "test@lakeport.news",
                      "password": "password"},
                content_type="application/json")
    client.post(f"{base}/api/articles/3/bookmark",
                content_type="application/json")
    client.post(f"{base}/api/articles/9/bookmark",
                content_type="application/json")
    r = client.get(f"{base}/api/bookmarks")
    bookmarks = json.loads(r.data)
    return str(len(bookmarks))
