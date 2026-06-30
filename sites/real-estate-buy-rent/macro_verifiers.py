"""Per-macro verification functions for real-estate-buy-rent.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/real-estate-buy-rent"


def _login(server_url, username="alex_buyer", password="pass123"):
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login",
           json={"username": username, "password": password})
    return s


def verify_macro_navigate_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/listings?status=for_sale")
    return {"pass": r.status_code == 200,
            "detail": f"Navigate to for_sale via dropdown: {r.status_code}"}


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/listing/1")
    return {"pass": r.status_code == 200,
            "detail": f"Navigate to listing #1: {r.status_code}"}


def verify_macro_search_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings?q=craftsman")
    results = r.json()
    return {"pass": len(results) > 0,
            "detail": f"search_by_query 'craftsman': {len(results)} results"}


def verify_macro_search_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings?q=modern+open+floor+plan")
    results = r.json()
    return {"pass": r.status_code == 200,
            "detail": f"search_by_semantic: {len(results)} results"}


def verify_macro_search_by_proximity(server_url):
    r = requests.get(f"{_base(server_url)}/api/proximity?address=main+street")
    results = r.json()
    return {"pass": r.status_code == 200,
            "detail": f"search_by_proximity 'main street': {len(results)} results"}


def verify_macro_filter_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings?q=updated+kitchen")
    results = r.json()
    return {"pass": r.status_code == 200,
            "detail": f"filter_by_query 'updated kitchen': {len(results)} results"}


def verify_macro_filter_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings?type=house")
    results = r.json()
    ok = all(l["type"] == "house" for l in results)
    return {"pass": ok,
            "detail": f"filter_by_dropdown house: {len(results)} results, all_house={ok}"}


def verify_macro_filter_by_checkbox(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings?beds=2")
    results = r.json()
    ok = all(l.get("bedrooms", 0) >= 2 for l in results)
    return {"pass": ok,
            "detail": f"filter_by_checkbox beds>=2: {len(results)} results, all_valid={ok}"}


def verify_macro_filter_by_slider(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings?price_min=100000&price_max=500000")
    results = r.json()
    return {"pass": r.status_code == 200 and len(results) > 0,
            "detail": f"filter_by_slider $100k-$500k: {len(results)} results"}


def verify_macro_sort_by_ranking(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings?sort=price_low")
    results = r.json()
    if len(results) < 2:
        return {"pass": True, "detail": "Too few listings to verify sort"}
    prices = [l.get("price") or l.get("rent_monthly") or 0 for l in results]
    is_sorted = all(prices[i] <= prices[i + 1] for i in range(len(prices) - 1))
    return {"pass": is_sorted,
            "detail": f"sort_by_ranking price_low: sorted={is_sorted}"}


def verify_macro_extract_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/stats/by_type?type=condo")
    stats = r.json()
    return {"pass": "avg_price" in stats and "count" in stats,
            "detail": f"extract_by_dropdown condo: count={stats.get('count')}, avg=${stats.get('avg_price')}"}


def verify_macro_extract_from_table(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings/1")
    listing = r.json()
    return {"pass": "year_built" in listing and "sqft" in listing,
            "detail": f"extract_from_table: year_built={listing.get('year_built')}, sqft={listing.get('sqft')}"}


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings/5")
    listing = r.json()
    return {"pass": "title" in listing and "description" in listing,
            "detail": f"extract_by_route: title={listing.get('title', '')[:40]}"}


def verify_macro_extract_by_ranking(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings?sort=price_high&limit=1")
    results = r.json()
    return {"pass": len(results) == 1,
            "detail": f"extract_by_ranking: top listing={results[0]['title'][:40] if results else 'none'}"}


def verify_macro_extract_by_extremum(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings?status=for_sale&sort=price_high&limit=1")
    results = r.json()
    if not results:
        return {"pass": False, "detail": "No for-sale listings"}
    return {"pass": True,
            "detail": f"extract_by_extremum: most expensive={results[0]['title'][:40]}, ${results[0].get('price', 0):,}"}


def verify_macro_compute_by_slider(server_url):
    r = requests.get(f"{_base(server_url)}/api/compare?ids=1")
    results = r.json()
    if not results:
        return {"pass": False, "detail": "No results from compare"}
    ppsf = results[0].get("price_per_sqft", 0)
    return {"pass": ppsf > 0,
            "detail": f"compute_by_slider: price_per_sqft=${ppsf}"}


def verify_macro_compare_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/compare?ids=1,2")
    results = r.json()
    if len(results) < 2:
        return {"pass": False, "detail": "Compare needs 2 listings"}
    return {"pass": results[0]["id"] != results[1]["id"],
            "detail": f"compare_by_dropdown: listing {results[0]['id']} vs {results[1]['id']}"}


def verify_macro_submit_by_query(server_url):
    s = _login(server_url, "mike_investor", "pass123")
    r = s.post(f"{_base(server_url)}/api/inquiries",
               json={"listing_id": 1, "message": "Macro test inquiry"})
    ok = r.status_code == 201
    return {"pass": ok,
            "detail": f"submit_by_query: status={r.status_code}"}


def verify_macro_select_by_ranking(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings?sort=price_low&limit=3")
    results = r.json()
    return {"pass": len(results) == 3,
            "detail": f"select_by_ranking: got {len(results)} listings"}


def verify_macro_select_by_extremum(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings?sort=price_low&limit=1")
    results = r.json()
    return {"pass": len(results) == 1,
            "detail": f"select_by_extremum: cheapest={results[0]['title'][:40] if results else 'none'}"}


def verify_macro_follow_by_toggle(server_url):
    s = _login(server_url, "mike_investor", "pass123")
    # Save listing 99 (test)
    r = s.post(f"{_base(server_url)}/api/saved", json={"listing_id": 99})
    ok = r.status_code in (201, 409)
    # Unsave
    s.delete(f"{_base(server_url)}/api/saved", json={"listing_id": 99})
    return {"pass": ok,
            "detail": f"follow_by_toggle: save status={r.status_code}"}


def verify_macro_save_by_toggle(server_url):
    s = _login(server_url, "mike_investor", "pass123")
    r = s.post(f"{_base(server_url)}/api/saved", json={"listing_id": 98})
    ok = r.status_code in (201, 409)
    s.delete(f"{_base(server_url)}/api/saved", json={"listing_id": 98})
    return {"pass": ok,
            "detail": f"save_by_toggle: status={r.status_code}"}


def verify_macro_apply_by_form(server_url):
    s = _login(server_url, "mike_investor", "pass123")
    r = s.post(f"{_base(server_url)}/api/inquiries",
               json={"listing_id": 2, "message": "Apply form test"})
    return {"pass": r.status_code == 201,
            "detail": f"apply_by_form: status={r.status_code}"}


def verify_macro_book_by_form(server_url):
    s = _login(server_url, "mike_investor", "pass123")
    r = s.post(f"{_base(server_url)}/api/inquiries",
               json={"listing_id": 3, "message": "I would like to schedule a showing."})
    return {"pass": r.status_code == 201,
            "detail": f"book_by_form: status={r.status_code}"}


def verify_macro_route_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings?q=bungalow")
    results = r.json()
    return {"pass": len(results) > 0,
            "detail": f"route_by_query 'bungalow': {len(results)} results"}
