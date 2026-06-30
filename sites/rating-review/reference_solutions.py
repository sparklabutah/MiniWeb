"""Per-task reference solutions via Flask test client for rating-review."""
import json


def solve_001(client, base="/sites/rating-review"):
    r = client.get(f"{base}/api/businesses?category=Restaurants")
    businesses = json.loads(r.data)
    return str(len(businesses))


def solve_002(client, base="/sites/rating-review"):
    r = client.get(f"{base}/api/businesses/1")
    biz = json.loads(r.data)
    return str(biz["overall_rating"])


def solve_003(client, base="/sites/rating-review"):
    r = client.get(f"{base}/api/search?q=sushi")
    data = json.loads(r.data)
    return str(data.get("business_count", 0))


def solve_004(client, base="/sites/rating-review"):
    r = client.get(f"{base}/api/search/semantic?q=outdoor+dining+patio+beer")
    data = json.loads(r.data)
    return str(data.get("count", 0))


def solve_005(client, base="/sites/rating-review"):
    r = client.get(f"{base}/api/search?q=broth")
    data = json.loads(r.data)
    return str(data.get("review_count", 0))


def solve_006(client, base="/sites/rating-review"):
    r = client.get(f"{base}/api/businesses?category=Coffee+%26+Tea")
    businesses = json.loads(r.data)
    return str(len(businesses))


def solve_007(client, base="/sites/rating-review"):
    r = client.get(f"{base}/api/businesses?price=$")
    businesses = json.loads(r.data)
    return str(len(businesses))


def solve_008(client, base="/sites/rating-review"):
    r = client.get(f"{base}/api/businesses?search=Outdoor+Seating")
    businesses = json.loads(r.data)
    return str(len(businesses))


def solve_009(client, base="/sites/rating-review"):
    r = client.get(f"{base}/api/businesses?min_rating=4.5")
    businesses = json.loads(r.data)
    return str(len(businesses))


def solve_010(client, base="/sites/rating-review"):
    r = client.get(f"{base}/api/businesses?sort=reviews")
    businesses = json.loads(r.data)
    return businesses[0]["name"] if businesses else ""


def solve_011(client, base="/sites/rating-review"):
    r = client.get(f"{base}/api/businesses?sort=rating")
    businesses = json.loads(r.data)
    if businesses:
        return f"{businesses[0]['name']} ({businesses[0]['overall_rating']})"
    return ""


def solve_012(client, base="/sites/rating-review"):
    r = client.get(f"{base}/api/search?q=bakery")
    data = json.loads(r.data)
    businesses = data.get("businesses", [])
    return businesses[0]["name"] if businesses else "No results"


def solve_013(client, base="/sites/rating-review"):
    r = client.get(f"{base}/api/businesses/3")
    biz = json.loads(r.data)
    return biz.get("price_range", "")


def solve_014(client, base="/sites/rating-review"):
    r = client.get(f"{base}/api/businesses?sort=rating")
    businesses = json.loads(r.data)
    top3 = [(b["name"], b["overall_rating"]) for b in businesses[:3]]
    return str(top3)


def solve_015(client, base="/sites/rating-review"):
    r = client.get(f"{base}/api/stats")
    stats = json.loads(r.data)
    return str(stats.get("average_rating", 0))


def solve_016(client, base="/sites/rating-review"):
    r = client.get(f"{base}/api/compare?ids=1,8")
    businesses = json.loads(r.data)
    if len(businesses) < 2:
        return "compare failed"
    higher = businesses[0] if businesses[0]["overall_rating"] >= businesses[1]["overall_rating"] else businesses[1]
    return higher["name"]


def solve_017(client, base="/sites/rating-review"):
    # Login
    client.post(f"{base}/api/login", json={"username": "alex_r"})
    r = client.put(f"{base}/api/reviews/1",
                   json={"rating": 4,
                         "text": "Still my favorite coffee spot, but service has slowed down recently."})
    data = json.loads(r.data)
    return "edited" if data.get("rating") == 4 else "failed"


def solve_018(client, base="/sites/rating-review"):
    client.post(f"{base}/api/login", json={"username": "alex_r"})
    r = client.post(f"{base}/api/reviews",
                    json={"business_id": 2, "rating": 5,
                          "title": "Amazing craft beer selection",
                          "text": "The rotating taps are always interesting. Great atmosphere and friendly staff."})
    data = json.loads(r.data)
    return "posted" if data.get("id") else "failed"


def solve_019(client, base="/sites/rating-review"):
    client.post(f"{base}/api/login", json={"username": "alex_r"})
    # Vote useful
    r1 = client.post(f"{base}/api/reviews/1/helpful",
                     json={"type": "useful"})
    # Save business
    r2 = client.post(f"{base}/api/users/1/save",
                     json={"business_id": 13})
    # Follow user
    r3 = client.post(f"{base}/api/users/1/follow",
                     json={"target_user_id": 3})
    d1 = json.loads(r1.data)
    d2 = json.loads(r2.data)
    d3 = json.loads(r3.data)
    if d1.get("success") and d2.get("action") == "saved" and d3.get("action") == "followed":
        return "all_done"
    return "failed"


def solve_020(client, base="/sites/rating-review"):
    client.post(f"{base}/api/login", json={"username": "alex_r"})
    # Upload photo
    r1 = client.post(f"{base}/api/photos",
                     json={"business_id": 1,
                           "caption": "Latte art at Cascadia",
                           "url": "/photos/latte-art.jpg"})
    # Report business
    r2 = client.post(f"{base}/api/report",
                     json={"target_type": "business",
                           "target_id": 20,
                           "reason": "closed",
                           "description": "This business appears to be permanently closed."})
    d1 = json.loads(r1.data)
    d2 = json.loads(r2.data)
    if d1.get("id") and d2.get("id"):
        return "uploaded_and_reported"
    return "failed"
