"""Per-task reference solutions via Flask test client for real-estate-buy-rent."""
import json


def solve_001(client, base="/sites/real-estate-buy-rent"):
    r = client.get(f"{base}/api/listings?status=for_sale")
    return str(len(json.loads(r.data)))


def solve_002(client, base="/sites/real-estate-buy-rent"):
    r = client.get(f"{base}/api/listings/3")
    listing = json.loads(r.data)
    return f"${listing['price']:,}"


def solve_003(client, base="/sites/real-estate-buy-rent"):
    r = client.get(f"{base}/api/listings?q=lakefront")
    return str(len(json.loads(r.data)))


def solve_004(client, base="/sites/real-estate-buy-rent"):
    r1 = client.get(f"{base}/api/listings?q=pet-friendly")
    r2 = client.get(f"{base}/api/listings?q=pets+allowed")
    ids = set(l["id"] for l in json.loads(r1.data)) | set(l["id"] for l in json.loads(r2.data))
    return str(len(ids))


def solve_005(client, base="/sites/real-estate-buy-rent"):
    r = client.get(f"{base}/api/proximity?address=elm")
    return str(len(json.loads(r.data)))


def solve_006(client, base="/sites/real-estate-buy-rent"):
    r = client.get(f"{base}/api/listings?q=garage")
    return str(len(json.loads(r.data)))


def solve_007(client, base="/sites/real-estate-buy-rent"):
    r = client.get(f"{base}/api/listings?type=condo")
    return str(len(json.loads(r.data)))


def solve_008(client, base="/sites/real-estate-buy-rent"):
    r = client.get(f"{base}/api/listings?beds=3")
    return str(len(json.loads(r.data)))


def solve_009(client, base="/sites/real-estate-buy-rent"):
    r = client.get(f"{base}/api/listings?price_min=200000&price_max=400000")
    return str(len(json.loads(r.data)))


def solve_010(client, base="/sites/real-estate-buy-rent"):
    r = client.get(f"{base}/api/listings?sort=price_low")
    listings = json.loads(r.data)
    return listings[0]["title"] if listings else "No listings"


def solve_011(client, base="/sites/real-estate-buy-rent"):
    r = client.get(f"{base}/api/stats/by_type?type=house")
    stats = json.loads(r.data)
    return f"${stats['avg_price']:,}"


def solve_012(client, base="/sites/real-estate-buy-rent"):
    r = client.get(f"{base}/api/listings/1")
    return str(json.loads(r.data)["year_built"])


def solve_013(client, base="/sites/real-estate-buy-rent"):
    r = client.get(f"{base}/api/listings/2")
    listing = json.loads(r.data)
    r2 = client.get(f"{base}/api/agents/{listing['agent_id']}")
    agent = json.loads(r2.data)
    return agent["name"]


def solve_014(client, base="/sites/real-estate-buy-rent"):
    r = client.get(f"{base}/api/listings?status=for_sale&sort=price_high")
    listings = json.loads(r.data)
    return listings[1]["title"] if len(listings) >= 2 else "N/A"


def solve_015(client, base="/sites/real-estate-buy-rent"):
    r = client.get(f"{base}/api/listings?status=for_rent&sort=price_low")
    listings = json.loads(r.data)
    return listings[0]["title"] if listings else "N/A"


def solve_016(client, base="/sites/real-estate-buy-rent"):
    r = client.get(f"{base}/api/compare?ids=1,2")
    listings = json.loads(r.data)
    if len(listings) >= 2:
        return f"{listings[0]['price_per_sqft']}, {listings[1]['price_per_sqft']}"
    return "N/A"


def solve_017(client, base="/sites/real-estate-buy-rent"):
    client.post(f"{base}/api/login",
                json={"username": "alex_buyer", "password": "pass123"})
    r = client.post(f"{base}/api/inquiries",
                    json={"listing_id": 6,
                          "message": "Is this unit still available for July move-in?"})
    data = json.loads(r.data)
    return data.get("status", "failed")


def solve_018(client, base="/sites/real-estate-buy-rent"):
    client.post(f"{base}/api/login",
                json={"username": "jenny_home", "password": "pass123"})
    client.post(f"{base}/api/saved", json={"listing_id": 7})
    r = client.get(f"{base}/api/saved")
    saved = json.loads(r.data)
    has_7 = any(sv["listing_id"] == 7 for sv in saved)
    return str(has_7)


def solve_019(client, base="/sites/real-estate-buy-rent"):
    r = client.get(f"{base}/api/listings?status=for_sale&sort=price_low")
    listings = json.loads(r.data)
    return str(listings[2]["id"]) if len(listings) >= 3 else "N/A"


def solve_020(client, base="/sites/real-estate-buy-rent"):
    client.post(f"{base}/api/login",
                json={"username": "sara_renter", "password": "pass123"})
    client.post(f"{base}/api/inquiries",
                json={"listing_id": 14,
                      "message": "Can I schedule a showing this Saturday at 2pm?"})
    r = client.get(f"{base}/api/inquiries")
    inquiries = json.loads(r.data)
    has_14 = any(inq["listing_id"] == 14 for inq in inquiries)
    return str(has_14)
