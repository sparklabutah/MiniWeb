"""Per-task reference solutions via Flask test client for classifieds."""
import json
import io


def solve_001(client, base="/sites/classifieds"):
    r = client.get(f"{base}/api/categories/vehicles/listings")
    listings = json.loads(r.data)
    return str(len(listings))


def solve_002(client, base="/sites/classifieds"):
    r = client.get(f"{base}/api/listings/1")
    listing = json.loads(r.data)
    return str(listing["price"])


def solve_003(client, base="/sites/classifieds"):
    r = client.get(f"{base}/api/listings/search?q=Tesla")
    return str(len(json.loads(r.data)))


def solve_004(client, base="/sites/classifieds"):
    r = client.get(f"{base}/api/listings/semantic?q=outdoor+recreation+and+adventure")
    return str(len(json.loads(r.data)))


def solve_005(client, base="/sites/classifieds"):
    r = client.get(f"{base}/api/listings?category=electronics")
    return str(len(json.loads(r.data)))


def solve_006(client, base="/sites/classifieds"):
    r = client.get(f"{base}/api/listings?condition=like_new")
    return str(len(json.loads(r.data)))


def solve_007(client, base="/sites/classifieds"):
    r = client.get(f"{base}/api/listings?price_min=500&price_max=2000")
    return str(len(json.loads(r.data)))


def solve_008(client, base="/sites/classifieds"):
    r = client.get(f"{base}/api/listings/search?q=camera")
    results = json.loads(r.data)
    return results[0]["title"] if results else "No results"


def solve_009(client, base="/sites/classifieds"):
    r = client.get(f"{base}/api/listings?sort=price_low")
    listings = json.loads(r.data)
    return listings[0]["title"] if listings else ""


def solve_010(client, base="/sites/classifieds"):
    r = client.get(f"{base}/api/listings/search?q=truck")
    results = json.loads(r.data)
    return str(results[0]["price"]) if results else "No results"


def solve_011(client, base="/sites/classifieds"):
    r = client.get(f"{base}/api/categories/jobs/stats")
    stats = json.loads(r.data)
    return str(stats.get("avg_price", 0))


def solve_012(client, base="/sites/classifieds"):
    r = client.get(f"{base}/api/listings/5")
    return json.loads(r.data)["location"]


def solve_013(client, base="/sites/classifieds"):
    r = client.get(f"{base}/api/compare?ids=1,7")
    listings = json.loads(r.data)
    if len(listings) < 2:
        return "Error"
    higher = max(listings, key=lambda l: l["price"])
    return f"Listing {higher['id']} (${higher['price']})"


def solve_014(client, base="/sites/classifieds"):
    r = client.get(f"{base}/api/categories/housing/stats")
    stats = json.loads(r.data)
    subcats = stats.get("subcategories", {})
    return str(len(subcats))


def solve_015(client, base="/sites/classifieds"):
    client.post(f"{base}/api/login",
                json={"username": "mike_seller", "password": "pass123"})
    r = client.post(f"{base}/api/listings", json={
        "title": "Mountain Bike for Sale",
        "description": "Giant Trance X 29 mountain bike, excellent condition",
        "price": 1500,
        "category": "vehicles",
        "subcategory": "bicycles",
        "condition": "used",
        "location": "Salt Lake City"
    }, content_type="application/json")
    data = json.loads(r.data)
    return "created" if data.get("id") else "failed"


def solve_016(client, base="/sites/classifieds"):
    client.post(f"{base}/api/login",
                json={"username": "sarah_tech", "password": "pass456"})
    r = client.put(f"{base}/api/listings/2", json={"price": 2600},
                   content_type="application/json")
    data = json.loads(r.data)
    return "updated" if data.get("price") == 2600 else "failed"


def solve_017(client, base="/sites/classifieds"):
    client.post(f"{base}/api/login",
                json={"username": "mike_seller", "password": "pass123"})
    r = client.delete(f"{base}/api/listings/37")
    data = json.loads(r.data)
    return data.get("action", "failed")


def solve_018(client, base="/sites/classifieds"):
    client.post(f"{base}/api/login",
                json={"username": "buyer_jane", "password": "passjkl"})
    for lid in [1, 2, 3]:
        client.post(f"{base}/api/users/10/save",
                    json={"listing_id": lid},
                    content_type="application/json")
    r = client.get(f"{base}/api/users/10")
    user = json.loads(r.data)
    return str(len(user.get("saved_listings", [])))


def solve_019(client, base="/sites/classifieds"):
    client.post(f"{base}/api/login",
                json={"username": "buyer_jane", "password": "passjkl"})
    # Send message
    client.post(f"{base}/api/messages", json={
        "listing_id": 1,
        "recipient_id": 1,
        "subject": "Interested in Camry",
        "body": "Is this still available? Can I come see it tomorrow?"
    }, content_type="application/json")
    # Report listing
    client.post(f"{base}/api/reports", json={
        "listing_id": 84,
        "reason": "spam",
        "description": "Suspicious listing with unrealistic pricing"
    }, content_type="application/json")
    return "completed"


def solve_020(client, base="/sites/classifieds"):
    r = client.post(f"{base}/api/register", json={
        "username": "new_user_2026",
        "password": "newpass99",
        "name": "Alex Morgan",
        "email": "alex.morgan@example.com",
        "phone": "801-555-9999",
        "location": "Logan"
    }, content_type="application/json")
    data = json.loads(r.data)
    if "user_id" not in data:
        return "failed"
    # Upload image
    r2 = client.post(f"{base}/api/upload",
                     data={"listing_id": "1",
                           "file": (io.BytesIO(b"fake image data"), "test.jpg")},
                     content_type="multipart/form-data")
    return "registered"
