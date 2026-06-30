"""Per-task HTTP verification functions for rating-review."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/rating-review"
    r = requests.get(f"{base}/api/businesses", params={"category": "Restaurants"})
    businesses = r.json()
    count = len(businesses)
    return {"pass": count > 0, "detail": f"Restaurants category: {count} businesses"}


def verify_002(server_url):
    base = f"{server_url}/sites/rating-review"
    r = requests.get(f"{base}/api/businesses/1")
    biz = r.json()
    rating = biz.get("overall_rating", 0)
    return {"pass": rating > 0, "detail": f"Cascadia Coffee overall_rating: {rating}"}


def verify_003(server_url):
    base = f"{server_url}/sites/rating-review"
    r = requests.get(f"{base}/api/search", params={"q": "sushi"})
    data = r.json()
    count = data.get("business_count", 0)
    return {"pass": count >= 0, "detail": f"Search 'sushi': {count} business results"}


def verify_004(server_url):
    base = f"{server_url}/sites/rating-review"
    r = requests.get(f"{base}/api/search/semantic", params={"q": "outdoor dining patio beer"})
    data = r.json()
    count = data.get("count", 0)
    return {"pass": count >= 0, "detail": f"Semantic search: {count} results"}


def verify_005(server_url):
    base = f"{server_url}/sites/rating-review"
    r = requests.get(f"{base}/api/search", params={"q": "broth"})
    data = r.json()
    count = data.get("review_count", 0)
    return {"pass": count >= 0, "detail": f"Reviews mentioning 'broth': {count}"}


def verify_006(server_url):
    base = f"{server_url}/sites/rating-review"
    r = requests.get(f"{base}/api/businesses", params={"category": "Coffee & Tea"})
    businesses = r.json()
    count = len(businesses)
    return {"pass": count > 0, "detail": f"Coffee & Tea: {count} businesses"}


def verify_007(server_url):
    base = f"{server_url}/sites/rating-review"
    r = requests.get(f"{base}/api/businesses", params={"price": "$"})
    businesses = r.json()
    count = len(businesses)
    ok = all(b.get("price_range") == "$" for b in businesses)
    return {"pass": ok and count > 0, "detail": f"$ price range: {count} businesses, all_match={ok}"}


def verify_008(server_url):
    base = f"{server_url}/sites/rating-review"
    r = requests.get(f"{base}/api/businesses", params={"search": "Outdoor Seating"})
    businesses = r.json()
    count = len(businesses)
    return {"pass": count > 0, "detail": f"Outdoor Seating filter: {count} businesses"}


def verify_009(server_url):
    base = f"{server_url}/sites/rating-review"
    r = requests.get(f"{base}/api/businesses", params={"min_rating": 4.5})
    businesses = r.json()
    count = len(businesses)
    ok = all(b.get("overall_rating", 0) >= 4.5 for b in businesses)
    return {"pass": ok and count > 0, "detail": f"Rating >= 4.5: {count} businesses, all_match={ok}"}


def verify_010(server_url):
    base = f"{server_url}/sites/rating-review"
    r = requests.get(f"{base}/api/businesses", params={"sort": "reviews"})
    businesses = r.json()
    if not businesses:
        return {"pass": False, "detail": "No businesses returned"}
    name = businesses[0].get("name", "")
    return {"pass": len(name) > 0, "detail": f"Most-reviewed: {name}"}


def verify_011(server_url):
    base = f"{server_url}/sites/rating-review"
    r = requests.get(f"{base}/api/businesses", params={"sort": "rating"})
    businesses = r.json()
    if not businesses:
        return {"pass": False, "detail": "No businesses returned"}
    name = businesses[0].get("name", "")
    rating = businesses[0].get("overall_rating", 0)
    return {"pass": rating > 0, "detail": f"Top rated: {name} ({rating})"}


def verify_012(server_url):
    base = f"{server_url}/sites/rating-review"
    r = requests.get(f"{base}/api/search", params={"q": "bakery"})
    data = r.json()
    businesses = data.get("businesses", [])
    if not businesses:
        return {"pass": False, "detail": "No bakery results"}
    return {"pass": True, "detail": f"First bakery result: {businesses[0].get('name', '')}"}


def verify_013(server_url):
    base = f"{server_url}/sites/rating-review"
    r = requests.get(f"{base}/api/businesses/3")
    biz = r.json()
    price = biz.get("price_range", "")
    return {"pass": len(price) > 0, "detail": f"Business 3 price_range: {price}"}


def verify_014(server_url):
    base = f"{server_url}/sites/rating-review"
    r = requests.get(f"{base}/api/businesses", params={"sort": "rating"})
    businesses = r.json()
    if len(businesses) < 3:
        return {"pass": False, "detail": f"Only {len(businesses)} businesses"}
    top3 = [(b["name"], b["overall_rating"]) for b in businesses[:3]]
    return {"pass": True, "detail": f"Top 3: {top3}"}


def verify_015(server_url):
    base = f"{server_url}/sites/rating-review"
    r = requests.get(f"{base}/api/stats")
    stats = r.json()
    avg = stats.get("average_rating", 0)
    return {"pass": avg > 0, "detail": f"Average rating: {avg}"}


def verify_016(server_url):
    base = f"{server_url}/sites/rating-review"
    r = requests.get(f"{base}/api/compare", params={"ids": "1,8"})
    businesses = r.json()
    if len(businesses) < 2:
        return {"pass": False, "detail": f"Compare returned {len(businesses)} businesses"}
    r1 = businesses[0].get("overall_rating", 0)
    r2 = businesses[1].get("overall_rating", 0)
    higher = businesses[0]["name"] if r1 >= r2 else businesses[1]["name"]
    return {"pass": True, "detail": f"Compare: {businesses[0]['name']}({r1}) vs {businesses[1]['name']}({r2}), higher={higher}"}


def verify_017(server_url):
    base = f"{server_url}/sites/rating-review"
    r = requests.get(f"{base}/api/reviews/1")
    review = r.json()
    rating = review.get("rating", 0)
    text = review.get("text", "")
    return {"pass": rating == 4 and "slowed down" in text,
            "detail": f"Review 1: rating={rating}, text_snippet='{text[:60]}'"}


def verify_018(server_url):
    base = f"{server_url}/sites/rating-review"
    r = requests.get(f"{base}/api/reviews", params={"business_id": 2})
    reviews = r.json()
    found = any(
        "craft beer" in r.get("title", "").lower() and r.get("rating", 0) == 5
        for r in reviews
    )
    return {"pass": found, "detail": f"New review for Summit Trail found: {found}"}


def verify_019(server_url):
    base = f"{server_url}/sites/rating-review"
    # Check review helpfulness
    r1 = requests.get(f"{base}/api/reviews/1")
    review = r1.json()
    useful = review.get("useful_count", 0)

    # Check saved businesses
    r2 = requests.get(f"{base}/api/users/1/saved")
    saved = r2.json()
    saved_ids = [b.get("id") for b in saved]

    # Check followed users
    r3 = requests.get(f"{base}/api/users/1")
    user = r3.json()
    followed = user.get("followed_users", [])

    all_ok = useful > 8 and 13 in saved_ids and 3 in followed
    return {"pass": all_ok,
            "detail": f"useful={useful}, saved_ids={saved_ids}, followed={followed}"}


def verify_020(server_url):
    base = f"{server_url}/sites/rating-review"
    # Check photo was uploaded
    r1 = requests.get(f"{base}/api/photos", params={"business_id": 1})
    photos = r1.json()
    photo_found = any("latte" in p.get("caption", "").lower() for p in photos)

    # Check report
    r2 = requests.get(f"{server_url}/_admin/data/rating-review/user_state")
    if r2.status_code == 200:
        state = r2.json()
        reports = state.get("reports", [])
        report_found = any(r.get("target_id") == 20 and r.get("reason") == "closed" for r in reports)
    else:
        report_found = False

    return {"pass": photo_found and report_found,
            "detail": f"photo_found={photo_found}, report_found={report_found}"}
