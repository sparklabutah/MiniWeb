"""Per-task reference solutions via Flask test client for visual-how-to-guides."""
import json


def solve_001(client, base="/sites/visual-how-to-guides"):
    r = client.get(f"{base}/api/guides?category=Cooking")
    return str(len(json.loads(r.data)))


def solve_002(client, base="/sites/visual-how-to-guides"):
    r = client.get(f"{base}/api/guides/4")
    guide = json.loads(r.data)
    return str(len(guide.get("steps", [])))


def solve_003(client, base="/sites/visual-how-to-guides"):
    r = client.get(f"{base}/api/search?q=garden")
    return str(len(json.loads(r.data)))


def solve_004(client, base="/sites/visual-how-to-guides"):
    r = client.get(f"{base}/api/search/semantic?q=healthy+exercise+routine")
    return str(len(json.loads(r.data)))


def solve_005(client, base="/sites/visual-how-to-guides"):
    r = client.get(f"{base}/api/guides?category=Tech+Setup")
    return str(len(json.loads(r.data)))


def solve_006(client, base="/sites/visual-how-to-guides"):
    r = client.get(f"{base}/api/guides?difficulty_min=3&difficulty_max=3")
    return str(len(json.loads(r.data)))


def solve_007(client, base="/sites/visual-how-to-guides"):
    r = client.get(f"{base}/api/guides?duration_min=30&duration_max=90")
    return str(len(json.loads(r.data)))


def solve_008(client, base="/sites/visual-how-to-guides"):
    r = client.get(f"{base}/api/guides?sort=rating")
    guides = json.loads(r.data)
    return guides[0]["title"] if guides else ""


def solve_009(client, base="/sites/visual-how-to-guides"):
    r = client.get(f"{base}/api/compare?ids=1,4,7")
    guides = json.loads(r.data)
    difficulties = [g["difficulty"] for g in guides]
    return ", ".join(difficulties)


def solve_010(client, base="/sites/visual-how-to-guides"):
    r = client.get(f"{base}/api/guides/12")
    guide = json.loads(r.data)
    author_id = guide.get("author_id")
    r2 = client.get(f"{base}/api/users/{author_id}")
    author = json.loads(r2.data)
    return author.get("display_name", "")


def solve_011(client, base="/sites/visual-how-to-guides"):
    r = client.get(f"{base}/api/guides?date_from=2025-09-01&date_to=2025-10-31")
    return str(len(json.loads(r.data)))


def solve_012(client, base="/sites/visual-how-to-guides"):
    r = client.get(f"{base}/api/guides/4/steps/3")
    data = json.loads(r.data)
    return data.get("step", {}).get("title", "")


def solve_013(client, base="/sites/visual-how-to-guides"):
    client.post(f"{base}/api/login",
                json={"username": "handy_hannah", "password": "pass123"})
    r = client.post(f"{base}/api/guides/5/comments",
                    json={"text": "The wok technique here is excellent for beginners."})
    data = json.loads(r.data)
    return "posted" if data.get("id") else "failed"


def solve_014(client, base="/sites/visual-how-to-guides"):
    client.post(f"{base}/api/login",
                json={"username": "chef_marco", "password": "pass223"})
    r = client.post(f"{base}/api/comments/1/react",
                    json={"reaction": "helpful"})
    data = json.loads(r.data)
    return data.get("action", "")


def solve_015(client, base="/sites/visual-how-to-guides"):
    client.post(f"{base}/api/login",
                json={"username": "tech_priya", "password": "pass323"})
    r = client.post(f"{base}/api/guides/1/rate",
                    json={"score": 4})
    data = json.loads(r.data)
    return str(data.get("new_average", ""))


def solve_016(client, base="/sites/visual-how-to-guides"):
    client.post(f"{base}/api/login",
                json={"username": "green_derek", "password": "pass423"})
    r = client.post(f"{base}/api/users/4/follow",
                    json={"author": "Hannah Torres"})
    data = json.loads(r.data)
    return data.get("action", "")


def solve_017(client, base="/sites/visual-how-to-guides"):
    client.post(f"{base}/api/login",
                json={"username": "craft_lisa", "password": "pass523"})
    r = client.post(f"{base}/api/guides/3/bookmark")
    data = json.loads(r.data)
    return data.get("action", "")


def solve_018(client, base="/sites/visual-how-to-guides"):
    r = client.get(f"{base}/api/guides?sort=title")
    guides = json.loads(r.data)
    return guides[0]["title"] if guides else ""


def solve_019(client, base="/sites/visual-how-to-guides"):
    r = client.get(f"{base}/api/search?q=pasta")
    results = json.loads(r.data)
    if not results:
        return "No results"
    guide_id = results[0]["id"]
    r2 = client.get(f"{base}/api/guides/{guide_id}")
    guide = json.loads(r2.data)
    return str(guide.get("duration_minutes", ""))


def solve_020(client, base="/sites/visual-how-to-guides"):
    client.post(f"{base}/api/login",
                json={"username": "handy_hannah", "password": "pass123"})
    client.post(f"{base}/api/guides/9/bookmark")
    client.post(f"{base}/api/guides/10/bookmark")
    r = client.get(f"{base}/api/bookmarks")
    bookmarks = json.loads(r.data)
    return str(len(bookmarks))
