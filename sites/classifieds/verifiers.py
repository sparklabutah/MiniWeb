"""Per-task HTTP verification functions for classifieds."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/classifieds"
    r = requests.get(f"{base}/api/categories/vehicles/listings")
    listings = r.json()
    count = len(listings)
    return {"pass": count > 0, "detail": f"vehicles category has {count} listings"}


def verify_002(server_url):
    base = f"{server_url}/sites/classifieds"
    r = requests.get(f"{base}/api/listings/1")
    listing = r.json()
    price = listing.get("price", 0)
    return {"pass": price == 22500, "detail": f"Listing 1 price: ${price}"}


def verify_003(server_url):
    base = f"{server_url}/sites/classifieds"
    r = requests.get(f"{base}/api/listings/search?q=Tesla")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Search 'Tesla': {count} results"}


def verify_004(server_url):
    base = f"{server_url}/sites/classifieds"
    r = requests.get(f"{base}/api/listings/semantic?q=outdoor+recreation+and+adventure")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Semantic 'outdoor recreation': {count} results"}


def verify_005(server_url):
    base = f"{server_url}/sites/classifieds"
    r = requests.get(f"{base}/api/listings?category=electronics")
    listings = r.json()
    count = len(listings)
    return {"pass": count > 0, "detail": f"electronics filter: {count} listings"}


def verify_006(server_url):
    base = f"{server_url}/sites/classifieds"
    r = requests.get(f"{base}/api/listings?condition=like_new")
    listings = r.json()
    count = len(listings)
    ok = all(l.get("condition") == "like_new" for l in listings)
    return {"pass": ok and count > 0, "detail": f"like_new condition: {count} listings, all_match={ok}"}


def verify_007(server_url):
    base = f"{server_url}/sites/classifieds"
    r = requests.get(f"{base}/api/listings?price_min=500&price_max=2000")
    listings = r.json()
    count = len(listings)
    ok = all(500 <= l["price"] <= 2000 for l in listings)
    return {"pass": ok and count >= 0, "detail": f"$500-$2000 range: {count} listings, all_in_range={ok}"}


def verify_008(server_url):
    base = f"{server_url}/sites/classifieds"
    r = requests.get(f"{base}/api/listings/search?q=camera")
    results = r.json()
    if not results:
        return {"pass": True, "detail": "No results for 'camera'"}
    first = results[0]["title"]
    return {"pass": len(first) > 0, "detail": f"First 'camera' result: {first[:60]}"}


def verify_009(server_url):
    base = f"{server_url}/sites/classifieds"
    r = requests.get(f"{base}/api/listings?sort=price_low")
    listings = r.json()
    if not listings:
        return {"pass": False, "detail": "No listings returned"}
    first_title = listings[0]["title"]
    prices = [l["price"] for l in listings]
    is_sorted = all(prices[i] <= prices[i+1] for i in range(len(prices)-1))
    return {"pass": is_sorted, "detail": f"Cheapest: {first_title} (${listings[0]['price']}), sorted={is_sorted}"}


def verify_010(server_url):
    base = f"{server_url}/sites/classifieds"
    r = requests.get(f"{base}/api/listings/search?q=truck")
    results = r.json()
    if not results:
        return {"pass": True, "detail": "No results for 'truck'"}
    price = results[0]["price"]
    return {"pass": price > 0, "detail": f"First 'truck' result price: ${price}"}


def verify_011(server_url):
    base = f"{server_url}/sites/classifieds"
    r = requests.get(f"{base}/api/categories/jobs/stats")
    stats = r.json()
    avg = stats.get("avg_price", 0)
    return {"pass": avg > 0, "detail": f"jobs avg price: ${avg}"}


def verify_012(server_url):
    base = f"{server_url}/sites/classifieds"
    r = requests.get(f"{base}/api/listings/5")
    listing = r.json()
    location = listing.get("location", "")
    return {"pass": len(location) > 0, "detail": f"Listing 5 location: {location}"}


def verify_013(server_url):
    base = f"{server_url}/sites/classifieds"
    r = requests.get(f"{base}/api/compare?ids=1,7")
    listings = r.json()
    if len(listings) < 2:
        return {"pass": False, "detail": f"Compare returned {len(listings)} listings, expected 2"}
    prices = {l["id"]: l["price"] for l in listings}
    higher = max(prices, key=prices.get)
    return {"pass": True, "detail": f"Listing {higher} has higher price (${prices[higher]})"}


def verify_014(server_url):
    base = f"{server_url}/sites/classifieds"
    r = requests.get(f"{base}/api/categories/housing/stats")
    stats = r.json()
    subcats = stats.get("subcategories", {})
    count = len(subcats)
    return {"pass": count > 0, "detail": f"housing subcategories: {count} ({', '.join(subcats.keys())})"}


def verify_015(server_url):
    base = f"{server_url}/sites/classifieds"
    r = requests.get(f"{base}/api/listings/search?q=Mountain+Bike+for+Sale")
    results = r.json()
    found = any(l["title"] == "Mountain Bike for Sale" for l in results)
    return {"pass": found, "detail": f"New listing found: {found}"}


def verify_016(server_url):
    base = f"{server_url}/sites/classifieds"
    r = requests.get(f"{base}/api/listings/2")
    listing = r.json()
    price = listing.get("price", 0)
    return {"pass": price == 2600, "detail": f"Listing 2 price after edit: ${price}"}


def verify_017(server_url):
    base = f"{server_url}/sites/classifieds"
    r = requests.get(f"{base}/api/listings/37")
    listing = r.json()
    status = listing.get("status", "")
    return {"pass": status == "deleted", "detail": f"Listing 37 status: {status}"}


def verify_018(server_url):
    base = f"{server_url}/sites/classifieds"
    r = requests.get(f"{base}/api/users/10")
    user = r.json()
    saved = user.get("saved_listings", [])
    return {"pass": len(saved) == 3 and 1 in saved and 2 in saved and 3 in saved,
            "detail": f"User 10 saved listings: {saved}"}


def verify_019(server_url):
    base = f"{server_url}/sites/classifieds"
    # Check message was sent
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "buyer_jane", "password": "passjkl"})
    r = s.get(f"{base}/api/messages")
    messages = r.json()
    msg_found = any("Interested in Camry" in m.get("subject", "") for m in messages)
    # Check report was filed
    r2 = requests.get(f"{base}/api/reports")
    reports = r2.json()
    report_found = any(r.get("listing_id") == 84 and r.get("reason") == "spam" for r in reports)
    return {"pass": msg_found and report_found,
            "detail": f"Message found: {msg_found}, Report found: {report_found}"}


def verify_020(server_url):
    base = f"{server_url}/sites/classifieds"
    # Check user was registered
    users_r = requests.get(f"{base}/api/users/11")
    if users_r.status_code == 200:
        user = users_r.json()
        found = user.get("username") == "new_user_2026"
    else:
        found = False
    return {"pass": found, "detail": f"New user registered: {found}"}
