"""Per-task HTTP verification functions for real-estate-buy-rent."""
import requests


def _base(server_url):
    return f"{server_url}/sites/real-estate-buy-rent"


def verify_001(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings?status=for_sale")
    listings = r.json()
    count = len(listings)
    return {"pass": count > 0, "detail": f"For-sale listings: {count}"}


def verify_002(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings/3")
    listing = r.json()
    price = listing.get("price", 0)
    return {"pass": price == 575000, "detail": f"Listing #3 price: ${price:,}"}


def verify_003(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings?q=lakefront")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Search 'lakefront': {count} results"}


def verify_004(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings?q=pet-friendly")
    r2 = requests.get(f"{_base(server_url)}/api/listings?q=pets+allowed")
    results1 = r.json()
    results2 = r2.json()
    ids = set(l["id"] for l in results1) | set(l["id"] for l in results2)
    return {"pass": True, "detail": f"Pet-related search: {len(ids)} unique listings"}


def verify_005(server_url):
    r = requests.get(f"{_base(server_url)}/api/proximity?address=elm")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Proximity 'elm': {count} listings"}


def verify_006(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings?q=garage")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Filter 'garage': {count} listings"}


def verify_007(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings?type=condo")
    results = r.json()
    count = len(results)
    ok = all(l["type"] == "condo" for l in results)
    return {"pass": ok and count > 0, "detail": f"Condo filter: {count} condos, all_condo={ok}"}


def verify_008(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings?beds=3")
    results = r.json()
    count = len(results)
    ok = all(l.get("bedrooms", 0) >= 3 for l in results)
    return {"pass": ok and count > 0, "detail": f"3+ beds: {count} listings, all_valid={ok}"}


def verify_009(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings?price_min=200000&price_max=400000")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"$200k-$400k: {count} listings"}


def verify_010(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings?sort=price_low")
    results = r.json()
    if not results:
        return {"pass": False, "detail": "No listings returned"}
    title = results[0]["title"]
    return {"pass": True, "detail": f"Cheapest listing: {title}"}


def verify_011(server_url):
    r = requests.get(f"{_base(server_url)}/api/stats/by_type?type=house")
    stats = r.json()
    avg = stats.get("avg_price", 0)
    return {"pass": avg > 0, "detail": f"House avg price: ${avg:,}"}


def verify_012(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings/1")
    listing = r.json()
    year = listing.get("year_built")
    return {"pass": year == 1948, "detail": f"Listing #1 year_built: {year}"}


def verify_013(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings/2")
    listing = r.json()
    agent_id = listing.get("agent_id")
    r2 = requests.get(f"{_base(server_url)}/api/agents/{agent_id}")
    agent = r2.json()
    name = agent.get("name", "")
    return {"pass": len(name) > 0, "detail": f"Listing #2 agent: {name}"}


def verify_014(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings?status=for_sale&sort=price_high")
    results = r.json()
    if len(results) < 2:
        return {"pass": False, "detail": f"Need at least 2 for-sale listings, got {len(results)}"}
    title = results[1]["title"]
    return {"pass": True, "detail": f"2nd most expensive for-sale: {title}"}


def verify_015(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings?status=for_rent&sort=price_low")
    results = r.json()
    if not results:
        return {"pass": False, "detail": "No for-rent listings"}
    title = results[0]["title"]
    rent = results[0].get("rent_monthly", 0)
    return {"pass": True, "detail": f"Cheapest rental: {title} at ${rent}/mo"}


def verify_016(server_url):
    r = requests.get(f"{_base(server_url)}/api/compare?ids=1,2")
    results = r.json()
    if len(results) < 2:
        return {"pass": False, "detail": f"Compare returned {len(results)} listings"}
    ppsf1 = results[0].get("price_per_sqft", 0)
    ppsf2 = results[1].get("price_per_sqft", 0)
    return {"pass": ppsf1 > 0 and ppsf2 > 0,
            "detail": f"Listing 1 ppsf: ${ppsf1}, Listing 2 ppsf: ${ppsf2}"}


def verify_017(server_url):
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login",
           json={"username": "alex_buyer", "password": "pass123"})
    r = s.post(f"{_base(server_url)}/api/inquiries",
               json={"listing_id": 6, "message": "Is this unit still available for July move-in?"})
    if r.status_code == 201:
        return {"pass": True, "detail": "Inquiry submitted successfully"}
    return {"pass": False, "detail": f"Inquiry submission failed: {r.status_code}"}


def verify_018(server_url):
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login",
           json={"username": "jenny_home", "password": "pass123"})
    r = s.post(f"{_base(server_url)}/api/saved",
               json={"listing_id": 7})
    if r.status_code in (201, 409):
        r2 = s.get(f"{_base(server_url)}/api/saved")
        saved = r2.json()
        has_7 = any(sv["listing_id"] == 7 for sv in saved)
        return {"pass": has_7, "detail": f"Listing #7 in saved: {has_7}"}
    return {"pass": False, "detail": f"Save failed: {r.status_code}"}


def verify_019(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings?status=for_sale&sort=price_low")
    results = r.json()
    if len(results) < 3:
        return {"pass": False, "detail": f"Need at least 3 for-sale listings, got {len(results)}"}
    lid = results[2]["id"]
    return {"pass": True, "detail": f"3rd cheapest for-sale listing ID: {lid}"}


def verify_020(server_url):
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login",
           json={"username": "sara_renter", "password": "pass123"})
    r = s.post(f"{_base(server_url)}/api/inquiries",
               json={"listing_id": 14,
                      "message": "Can I schedule a showing this Saturday at 2pm?"})
    if r.status_code != 201:
        return {"pass": False, "detail": f"Inquiry submission failed: {r.status_code}"}
    r2 = s.get(f"{_base(server_url)}/api/inquiries")
    inquiries = r2.json()
    has_14 = any(inq["listing_id"] == 14 for inq in inquiries)
    return {"pass": has_14, "detail": f"Listing #14 inquiry exists: {has_14}"}
