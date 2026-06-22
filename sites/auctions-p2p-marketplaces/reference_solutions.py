"""Per-task reference solutions via Flask test client for auctions-p2p-marketplaces."""
import json


def solve_001(client, base="/sites/auctions-p2p-marketplaces"):
    r = client.get(f"{base}/api/categories/Electronics/listings")
    listings = json.loads(r.data)
    return str(len(listings))


def solve_002(client, base="/sites/auctions-p2p-marketplaces"):
    r = client.get(f"{base}/api/listings/1")
    listing = json.loads(r.data)
    return listing["condition"]


def solve_003(client, base="/sites/auctions-p2p-marketplaces"):
    r = client.get(f"{base}/api/listings/search?q=guitar")
    return str(len(json.loads(r.data)))


def solve_004(client, base="/sites/auctions-p2p-marketplaces"):
    r = client.get(f"{base}/api/listings/semantic?q=wireless+audio+devices")
    return str(len(json.loads(r.data)))


def solve_005(client, base="/sites/auctions-p2p-marketplaces"):
    r = client.get(f"{base}/api/listings?q=keyboard&condition=New")
    return str(len(json.loads(r.data)))


def solve_006(client, base="/sites/auctions-p2p-marketplaces"):
    r = client.get(f"{base}/api/listings?category=Collectibles")
    return str(len(json.loads(r.data)))


def solve_007(client, base="/sites/auctions-p2p-marketplaces"):
    r = client.get(f"{base}/api/listings?condition=Like+New")
    return str(len(json.loads(r.data)))


def solve_008(client, base="/sites/auctions-p2p-marketplaces"):
    r = client.get(f"{base}/api/listings?max_price=50")
    return str(len(json.loads(r.data)))


def solve_009(client, base="/sites/auctions-p2p-marketplaces"):
    r = client.get(f"{base}/api/listings?sort=price_high")
    listings = json.loads(r.data)
    return listings[0]["name"] if listings else ""


def solve_010(client, base="/sites/auctions-p2p-marketplaces"):
    r = client.get(f"{base}/api/listings?status=ended&sort=newest")
    return str(len(json.loads(r.data)))


def solve_011(client, base="/sites/auctions-p2p-marketplaces"):
    r = client.get(f"{base}/api/categories/Electronics/stats")
    stats = json.loads(r.data)
    return str(stats.get("avg_price", 0))


def solve_012(client, base="/sites/auctions-p2p-marketplaces"):
    r = client.get(f"{base}/api/listings/5")
    listing = json.loads(r.data)
    return listing["seller_username"]


def solve_013(client, base="/sites/auctions-p2p-marketplaces"):
    r = client.get(f"{base}/api/compare?ids=1,2,3")
    listings = json.loads(r.data)
    cats = [p["category"] for p in listings]
    return ", ".join(cats)


def solve_014(client, base="/sites/auctions-p2p-marketplaces"):
    client.post(f"{base}/api/login",
                json={"username": "alice_bidder", "password": "buyer001"},
                content_type="application/json")
    r = client.post(f"{base}/api/listings",
                    json={"name": "Vintage Camera Lot", "category": "Collectibles",
                          "seller_id": 21, "seller_username": "alice_bidder"},
                    content_type="application/json")
    data = json.loads(r.data)
    return str(data.get("listing_id", ""))


def solve_015(client, base="/sites/auctions-p2p-marketplaces"):
    client.post(f"{base}/api/login",
                json={"username": "bob_collector", "password": "buyer002"},
                content_type="application/json")
    r = client.post(f"{base}/api/listings/1/bid",
                    json={"amount": 999.99, "bidder_id": 22},
                    content_type="application/json")
    data = json.loads(r.data)
    return str(data.get("new_price", ""))


def solve_016(client, base="/sites/auctions-p2p-marketplaces"):
    client.post(f"{base}/api/login",
                json={"username": "alice_bidder", "password": "buyer001"},
                content_type="application/json")
    r = client.put(f"{base}/api/listings/1",
                   json={"description": "Updated description for testing"},
                   content_type="application/json")
    data = json.loads(r.data)
    return "success" if data.get("success") else "failed"


def solve_017(client, base="/sites/auctions-p2p-marketplaces"):
    r = client.delete(f"{base}/api/messages/1")
    data = json.loads(r.data)
    return str(data.get("deleted_id", ""))


def solve_018(client, base="/sites/auctions-p2p-marketplaces"):
    import io
    data = {"file": (io.BytesIO(b"fake image data"), "test.jpg")}
    r = client.post(f"{base}/api/listings/1/upload",
                    data=data, content_type="multipart/form-data")
    result = json.loads(r.data)
    return result.get("filename", "")


def solve_019(client, base="/sites/auctions-p2p-marketplaces"):
    r = client.post(f"{base}/api/settings/bid-increment",
                    json={"increment": 2.50},
                    content_type="application/json")
    data = json.loads(r.data)
    return str(data.get("bid_increment", ""))


def solve_020(client, base="/sites/auctions-p2p-marketplaces"):
    client.post(f"{base}/api/login",
                json={"username": "carol_shopper", "password": "buyer003"},
                content_type="application/json")
    r = client.post(f"{base}/api/ratings",
                    json={"listing_id": 5, "rater_id": 23, "rated_user_id": 1,
                          "score": 4, "comment": "Great transaction!"},
                    content_type="application/json")
    data = json.loads(r.data)
    return str(data.get("rating_id", ""))


def solve_021(client, base="/sites/auctions-p2p-marketplaces"):
    client.post(f"{base}/api/login",
                json={"username": "dan_buyer", "password": "buyer004"},
                content_type="application/json")
    r = client.post(f"{base}/api/users/24/follow",
                    json={"seller_id": 3},
                    content_type="application/json")
    data = json.loads(r.data)
    return data.get("action", "")


def solve_022(client, base="/sites/auctions-p2p-marketplaces"):
    client.post(f"{base}/api/login",
                json={"username": "eve_bargain", "password": "buyer005"},
                content_type="application/json")
    r = client.post(f"{base}/api/users/25/save",
                    json={"listing_id": 3},
                    content_type="application/json")
    data = json.loads(r.data)
    return data.get("action", "")


def solve_023(client, base="/sites/auctions-p2p-marketplaces"):
    client.post(f"{base}/api/login",
                json={"username": "frank_deals", "password": "buyer006"},
                content_type="application/json")
    r = client.post(f"{base}/api/listings/2/report",
                    json={"reporter_id": 26, "reason": "misleading",
                          "description": "Item description does not match photos"},
                    content_type="application/json")
    data = json.loads(r.data)
    return str(data.get("report_id", ""))


def solve_024(client, base="/sites/auctions-p2p-marketplaces"):
    r = client.get(f"{base}/api/listings/1")
    listing = json.loads(r.data)
    seller_id = listing["seller_id"]
    client.post(f"{base}/api/login",
                json={"username": "grace_finds", "password": "buyer007"},
                content_type="application/json")
    r = client.post(f"{base}/api/messages",
                    json={"sender_id": 27, "receiver_id": seller_id,
                          "listing_id": 1, "body": "Is this item still available?"},
                    content_type="application/json")
    data = json.loads(r.data)
    return str(data.get("message_id", ""))


def solve_025(client, base="/sites/auctions-p2p-marketplaces"):
    client.post(f"{base}/api/login",
                json={"username": "henry_hunter", "password": "buyer008"},
                content_type="application/json")
    r = client.post(f"{base}/api/users/28/watch",
                    json={"listing_id": 10},
                    content_type="application/json")
    data = json.loads(r.data)
    return data.get("action", "")


def solve_026(client, base="/sites/auctions-p2p-marketplaces"):
    client.post(f"{base}/api/login",
                json={"username": "iris_treasure", "password": "buyer009"},
                content_type="application/json")
    r = client.post(f"{base}/api/checkout",
                    json={"listing_id": 5, "buyer_id": 29,
                          "payment_method": "PayPal",
                          "shipping_address": "123 Main St"},
                    content_type="application/json")
    data = json.loads(r.data)
    return data.get("order_id", "")


def solve_027(client, base="/sites/auctions-p2p-marketplaces"):
    client.post(f"{base}/api/login",
                json={"username": "alice_bidder", "password": "buyer001"},
                content_type="application/json")
    r = client.get(f"{base}/api/users/21")
    user = json.loads(r.data)
    return user.get("name", "")


def solve_028(client, base="/sites/auctions-p2p-marketplaces"):
    r = client.post(f"{base}/api/register",
                    json={"username": "new_bidder_99", "password": "testpass",
                          "email": "new@test.com", "name": "Test User"},
                    content_type="application/json")
    data = json.loads(r.data)
    return data.get("username", "")
