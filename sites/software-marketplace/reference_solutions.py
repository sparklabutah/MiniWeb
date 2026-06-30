"""Per-task reference solutions via Flask test client for software-marketplace."""
import json


def solve_001(client, base="/sites/software-marketplace"):
    r = client.get(f"{base}/api/categories/GAME/apps")
    apps = json.loads(r.data)
    return str(len(apps))


def solve_002(client, base="/sites/software-marketplace"):
    # Featured = top rated apps, first one
    r = client.get(f"{base}/api/apps?sort=rating&limit=1")
    apps = json.loads(r.data)
    return apps[0]["developer"] if apps else ""


def solve_003(client, base="/sites/software-marketplace"):
    r = client.get(f"{base}/api/apps?q=messenger")
    return str(len(json.loads(r.data)))


def solve_004(client, base="/sites/software-marketplace"):
    r = client.get(f"{base}/api/apps/semantic?q=social+media+chat+messaging")
    return str(len(json.loads(r.data)))


def solve_005(client, base="/sites/software-marketplace"):
    r = client.get(f"{base}/api/categories/EDUCATION/apps")
    return str(len(json.loads(r.data)))


def solve_006(client, base="/sites/software-marketplace"):
    r = client.get(f"{base}/api/apps?max_price=2.0")
    return str(len(json.loads(r.data)))


def solve_007(client, base="/sites/software-marketplace"):
    r = client.get(f"{base}/api/apps?sort=rating&limit=1")
    apps = json.loads(r.data)
    return apps[0]["name"] if apps else ""


def solve_008(client, base="/sites/software-marketplace"):
    r = client.get(f"{base}/api/apps?sort=price_desc&limit=1")
    apps = json.loads(r.data)
    if apps:
        return f"{apps[0]['name']}, ${apps[0]['price']}"
    return ""


def solve_009(client, base="/sites/software-marketplace"):
    r = client.get(f"{base}/api/compare?ids=1,2")
    apps = json.loads(r.data)
    ratings = [str(a["rating"]) for a in apps]
    return ", ".join(ratings)


def solve_010(client, base="/sites/software-marketplace"):
    r = client.get(f"{base}/api/apps/5")
    app = json.loads(r.data)
    return app["content_rating"]


def solve_011(client, base="/sites/software-marketplace"):
    r = client.get(f"{base}/api/categories/GAME/apps")
    apps = json.loads(r.data)
    arcade = [a for a in apps if a["genre"] == "Arcade"]
    return arcade[0]["name"] if arcade else "No Arcade apps"


def solve_012(client, base="/sites/software-marketplace"):
    client.post(f"{base}/api/login",
                json={"username": "alex_dev", "password": "pass123"})
    client.post(f"{base}/api/settings",
                json={"user_id": 1, "theme": "dark"})
    r = client.get(f"{base}/api/settings?user_id=1")
    settings = json.loads(r.data)
    return settings["theme"]


def solve_013(client, base="/sites/software-marketplace"):
    client.post(f"{base}/api/login",
                json={"username": "samantha_k", "password": "pass123"})
    client.post(f"{base}/api/settings",
                json={"user_id": 2, "notification_frequency": 8})
    r = client.get(f"{base}/api/settings?user_id=2")
    settings = json.loads(r.data)
    return str(settings["notification_frequency"])


def solve_014(client, base="/sites/software-marketplace"):
    r = client.get(f"{base}/api/export?format=csv&category=GAME")
    lines = r.data.decode().strip().split("\n")
    return str(len(lines) - 1)


def solve_015(client, base="/sites/software-marketplace"):
    client.post(f"{base}/api/login",
                json={"username": "marcus_j", "password": "pass123"})
    r = client.post(f"{base}/api/apps/2/reviews",
                    json={"user_id": 3, "rating": 4,
                          "text": "Very useful app for tracking daily nutrition"})
    data = json.loads(r.data)
    return data.get("action", "")


def solve_016(client, base="/sites/software-marketplace"):
    client.post(f"{base}/api/login",
                json={"username": "priya_s", "password": "pass123"})
    r = client.post(f"{base}/api/wishlist/toggle",
                    json={"user_id": 4, "app_id": 9})
    data = json.loads(r.data)
    return data.get("action", "")


def solve_017(client, base="/sites/software-marketplace"):
    client.post(f"{base}/api/login",
                json={"username": "jordan_w", "password": "pass123"})
    r = client.post(f"{base}/api/cart/add",
                    json={"user_id": 5, "app_id": 44})
    data = json.loads(r.data)
    return data.get("action", "")


def solve_018(client, base="/sites/software-marketplace"):
    client.post(f"{base}/api/login",
                json={"username": "alex_dev", "password": "pass123"})
    client.post(f"{base}/api/cart/add",
                json={"user_id": 1, "app_id": 7})
    r = client.post(f"{base}/api/checkout",
                    json={"user_id": 1,
                          "card_name": "Alex Chen",
                          "card_number": "4111111111111111",
                          "card_expiry": "12/28"})
    data = json.loads(r.data)
    return data.get("action", "")


def solve_019(client, base="/sites/software-marketplace"):
    client.post(f"{base}/api/login",
                json={"username": "samantha_k", "password": "pass123"})
    client.post(f"{base}/api/cart/add",
                json={"user_id": 2, "app_id": 30})
    r = client.post(f"{base}/api/checkout",
                    json={"user_id": 2,
                          "card_name": "Samantha Kim",
                          "card_number": "4222222222222222",
                          "card_expiry": "06/27",
                          "promo_code": "WELCOME20"})
    data = json.loads(r.data)
    return f"${data.get('total', 0)}"


def solve_020(client, base="/sites/software-marketplace"):
    r = client.post(f"{base}/api/promo/validate",
                    json={"code": "EXPIRED10"})
    data = json.loads(r.data)
    return f"rejected: {data.get('error', '')}"
