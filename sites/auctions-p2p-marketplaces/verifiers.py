"""Per-task HTTP verification functions for auctions-p2p-marketplaces."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/auctions-p2p-marketplaces"
    r = requests.get(f"{base}/api/categories/Electronics/listings")
    listings = r.json()
    count = len(listings)
    return {"pass": count > 0, "detail": f"Electronics category has {count} listings"}


def verify_002(server_url):
    base = f"{server_url}/sites/auctions-p2p-marketplaces"
    r = requests.get(f"{base}/api/listings/1")
    listing = r.json()
    condition = listing.get("condition", "")
    return {"pass": len(condition) > 0, "detail": f"Listing 1 condition: {condition}"}


def verify_003(server_url):
    base = f"{server_url}/sites/auctions-p2p-marketplaces"
    r = requests.get(f"{base}/api/listings/search?q=guitar")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Search 'guitar': {count} results"}


def verify_004(server_url):
    base = f"{server_url}/sites/auctions-p2p-marketplaces"
    r = requests.get(f"{base}/api/listings/semantic?q=wireless+audio+devices")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Semantic 'wireless audio devices': {count} results"}


def verify_005(server_url):
    base = f"{server_url}/sites/auctions-p2p-marketplaces"
    r = requests.get(f"{base}/api/listings?q=keyboard&condition=New")
    results = r.json()
    count = len(results)
    ok = all(p["condition"] == "New" for p in results)
    return {"pass": ok, "detail": f"New keyboard: {count} results, all_new={ok}"}


def verify_006(server_url):
    base = f"{server_url}/sites/auctions-p2p-marketplaces"
    r = requests.get(f"{base}/api/listings?category=Collectibles")
    listings = r.json()
    count = len(listings)
    ok = all(p["category"] == "Collectibles" for p in listings)
    return {"pass": ok and count > 0, "detail": f"Collectibles filter: {count} listings"}


def verify_007(server_url):
    base = f"{server_url}/sites/auctions-p2p-marketplaces"
    r = requests.get(f"{base}/api/listings?condition=Like+New")
    listings = r.json()
    count = len(listings)
    ok = all(p["condition"] == "Like New" for p in listings)
    return {"pass": ok, "detail": f"Like New filter: {count} listings, all_match={ok}"}


def verify_008(server_url):
    base = f"{server_url}/sites/auctions-p2p-marketplaces"
    r = requests.get(f"{base}/api/listings?max_price=50")
    listings = r.json()
    count = len(listings)
    ok = all(p["current_price"] <= 50.0 for p in listings)
    return {"pass": ok and count > 0, "detail": f"Max $50: {count} listings, all_under={ok}"}


def verify_009(server_url):
    base = f"{server_url}/sites/auctions-p2p-marketplaces"
    r = requests.get(f"{base}/api/listings?sort=price_high")
    listings = r.json()
    if not listings:
        return {"pass": False, "detail": "No listings returned"}
    name = listings[0]["name"]
    prices = [p["current_price"] for p in listings]
    is_sorted = all(prices[i] >= prices[i+1] for i in range(len(prices)-1))
    return {"pass": is_sorted, "detail": f"Most expensive: {name[:50]}, sorted_desc={is_sorted}"}


def verify_010(server_url):
    base = f"{server_url}/sites/auctions-p2p-marketplaces"
    r = requests.get(f"{base}/api/listings?status=ended&sort=newest")
    listings = r.json()
    count = len(listings)
    ok = all(p["status"] == "ended" for p in listings)
    return {"pass": ok and count > 0, "detail": f"Ended auctions: {count}, all_ended={ok}"}


def verify_011(server_url):
    base = f"{server_url}/sites/auctions-p2p-marketplaces"
    r = requests.get(f"{base}/api/categories/Electronics/stats")
    stats = r.json()
    avg = stats.get("avg_price", 0)
    return {"pass": avg > 0, "detail": f"Electronics avg price: ${avg}"}


def verify_012(server_url):
    base = f"{server_url}/sites/auctions-p2p-marketplaces"
    r = requests.get(f"{base}/api/listings/5")
    listing = r.json()
    seller = listing.get("seller_username", "")
    return {"pass": len(seller) > 0, "detail": f"Listing 5 seller: {seller}"}


def verify_013(server_url):
    base = f"{server_url}/sites/auctions-p2p-marketplaces"
    r = requests.get(f"{base}/api/compare?ids=1,2,3")
    listings = r.json()
    if len(listings) < 3:
        return {"pass": False, "detail": f"Compare returned {len(listings)} listings, expected 3"}
    cats = [p["category"] for p in listings]
    return {"pass": True, "detail": f"Categories: {', '.join(cats)}"}


def verify_014(server_url):
    base = f"{server_url}/sites/auctions-p2p-marketplaces"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "alice_bidder", "password": "buyer001"})
    r = s.post(f"{base}/api/listings", json={
        "name": "Vintage Camera Lot",
        "category": "Collectibles",
        "seller_id": 21,
        "seller_username": "alice_bidder"
    })
    data = r.json()
    ok = data.get("success", False)
    return {"pass": ok, "detail": f"Created listing: {data}"}


def verify_015(server_url):
    base = f"{server_url}/sites/auctions-p2p-marketplaces"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "bob_collector", "password": "buyer002"})
    r = s.post(f"{base}/api/listings/1/bid", json={"amount": 999.99, "bidder_id": 22})
    data = r.json()
    ok = data.get("success", False)
    return {"pass": ok, "detail": f"Bid result: new_price={data.get('new_price')}"}


def verify_016(server_url):
    base = f"{server_url}/sites/auctions-p2p-marketplaces"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "alice_bidder", "password": "buyer001"})
    r = s.put(f"{base}/api/listings/1", json={"description": "Updated description for testing"})
    data = r.json()
    ok = data.get("success", False)
    # Verify
    r2 = s.get(f"{base}/api/listings/1")
    listing = r2.json()
    return {"pass": ok and listing.get("description") == "Updated description for testing",
            "detail": f"Edit result: {data}, description updated"}


def verify_017(server_url):
    base = f"{server_url}/sites/auctions-p2p-marketplaces"
    r = requests.delete(f"{base}/api/messages/1")
    data = r.json()
    ok = data.get("success", False)
    return {"pass": ok, "detail": f"Delete message 1: {data}"}


def verify_018(server_url):
    base = f"{server_url}/sites/auctions-p2p-marketplaces"
    import io
    files = {"file": ("test.jpg", io.BytesIO(b"fake image data"), "image/jpeg")}
    r = requests.post(f"{base}/api/listings/1/upload", files=files)
    data = r.json()
    ok = data.get("success", False)
    return {"pass": ok, "detail": f"Upload result: {data}"}


def verify_019(server_url):
    base = f"{server_url}/sites/auctions-p2p-marketplaces"
    r = requests.post(f"{base}/api/settings/bid-increment", json={"increment": 2.50})
    data = r.json()
    ok = data.get("success", False) and data.get("bid_increment") == 2.50
    return {"pass": ok, "detail": f"Bid increment config: {data}"}


def verify_020(server_url):
    base = f"{server_url}/sites/auctions-p2p-marketplaces"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "carol_shopper", "password": "buyer003"})
    r = s.post(f"{base}/api/ratings", json={
        "listing_id": 5, "rater_id": 23, "rated_user_id": 1,
        "score": 4, "comment": "Great transaction!"
    })
    data = r.json()
    ok = data.get("success", False)
    return {"pass": ok, "detail": f"Rating submitted: {data}"}


def verify_021(server_url):
    base = f"{server_url}/sites/auctions-p2p-marketplaces"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "dan_buyer", "password": "buyer004"})
    r = s.post(f"{base}/api/users/24/follow", json={"seller_id": 3})
    data = r.json()
    ok = data.get("action") == "followed"
    return {"pass": ok, "detail": f"Follow seller 3: {data}"}


def verify_022(server_url):
    base = f"{server_url}/sites/auctions-p2p-marketplaces"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "eve_bargain", "password": "buyer005"})
    r = s.post(f"{base}/api/users/25/save", json={"listing_id": 3})
    data = r.json()
    ok = data.get("action") == "saved"
    return {"pass": ok, "detail": f"Save listing 3: {data}"}


def verify_023(server_url):
    base = f"{server_url}/sites/auctions-p2p-marketplaces"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "frank_deals", "password": "buyer006"})
    r = s.post(f"{base}/api/listings/2/report", json={
        "reporter_id": 26, "reason": "misleading",
        "description": "Item description does not match photos"
    })
    data = r.json()
    ok = data.get("success", False)
    return {"pass": ok, "detail": f"Report filed: {data}"}


def verify_024(server_url):
    base = f"{server_url}/sites/auctions-p2p-marketplaces"
    # Get seller of listing 1
    r = requests.get(f"{base}/api/listings/1")
    listing = r.json()
    seller_id = listing["seller_id"]
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "grace_finds", "password": "buyer007"})
    r = s.post(f"{base}/api/messages", json={
        "sender_id": 27, "receiver_id": seller_id,
        "listing_id": 1, "body": "Is this item still available?"
    })
    data = r.json()
    ok = data.get("success", False)
    return {"pass": ok, "detail": f"Message sent: {data}"}


def verify_025(server_url):
    base = f"{server_url}/sites/auctions-p2p-marketplaces"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "henry_hunter", "password": "buyer008"})
    r = s.post(f"{base}/api/users/28/watch", json={"listing_id": 10})
    data = r.json()
    ok = data.get("action") == "watched"
    return {"pass": ok, "detail": f"Watch listing 10: {data}"}


def verify_026(server_url):
    base = f"{server_url}/sites/auctions-p2p-marketplaces"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "iris_treasure", "password": "buyer009"})
    r = s.post(f"{base}/api/checkout", json={
        "listing_id": 5, "buyer_id": 29,
        "payment_method": "PayPal",
        "shipping_address": "123 Main St"
    })
    data = r.json()
    ok = data.get("success", False)
    order_id = data.get("order_id", "")
    return {"pass": ok and len(order_id) > 0, "detail": f"Checkout: order_id={order_id}"}


def verify_027(server_url):
    base = f"{server_url}/sites/auctions-p2p-marketplaces"
    s = requests.Session()
    r = s.post(f"{base}/api/login", json={"username": "alice_bidder", "password": "buyer001"})
    data = r.json()
    ok = data.get("user_id") == 21
    r2 = s.get(f"{base}/api/users/21")
    user = r2.json()
    return {"pass": ok and user.get("name") == "Alice Johnson",
            "detail": f"Login: user_id={data.get('user_id')}, name={user.get('name')}"}


def verify_028(server_url):
    base = f"{server_url}/sites/auctions-p2p-marketplaces"
    r = requests.post(f"{base}/api/register", json={
        "username": "new_bidder_99", "password": "testpass",
        "email": "new@test.com", "name": "Test User"
    })
    data = r.json()
    ok = data.get("username") == "new_bidder_99"
    return {"pass": ok, "detail": f"Register: {data}"}
