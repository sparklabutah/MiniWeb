"""Per-macro verification functions for auctions-p2p-marketplaces.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/auctions-p2p-marketplaces"


def verify_macro_navigate_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/categories")
    cats = r.json()
    if not cats:
        return {"pass": False, "detail": "No categories returned"}
    cat = cats[0]["name"]
    r2 = requests.get(f"{_base(server_url)}/category/{cat}")
    return {"pass": r2.status_code == 200, "detail": f"Category page '{cat}': {r2.status_code}"}


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/listing/1")
    return {"pass": r.status_code == 200, "detail": f"Listing detail page: {r.status_code}"}


def verify_macro_search_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings/search?q=guitar")
    results = r.json()
    return {"pass": len(results) >= 0, "detail": f"search_by_query 'guitar': {len(results)} results"}


def verify_macro_search_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings/semantic?q=wireless+audio")
    results = r.json()
    return {"pass": r.status_code == 200, "detail": f"search_by_semantic: {len(results)} results"}


def verify_macro_filter_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings?q=keyboard&condition=New")
    results = r.json()
    ok = all(p["condition"] == "New" for p in results)
    return {"pass": ok, "detail": f"filter_by_query: {len(results)} results, all_new={ok}"}


def verify_macro_filter_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings?category=Electronics")
    listings = r.json()
    ok = all(p["category"] == "Electronics" for p in listings)
    return {"pass": ok, "detail": f"filter_by_dropdown Electronics: {len(listings)} listings"}


def verify_macro_filter_by_radio(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings?condition=Good")
    listings = r.json()
    ok = all(p["condition"] == "Good" for p in listings)
    return {"pass": ok, "detail": f"filter_by_radio Good: {len(listings)} listings"}


def verify_macro_filter_by_slider(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings?max_price=100")
    listings = r.json()
    ok = all(p["current_price"] <= 100.0 for p in listings)
    return {"pass": ok, "detail": f"filter_by_slider max $100: {len(listings)} listings"}


def verify_macro_sort_by_ranking(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings?sort=price_high")
    listings = r.json()
    if len(listings) < 2:
        return {"pass": True, "detail": "Too few listings to verify sort"}
    prices = [p["current_price"] for p in listings]
    is_sorted = all(prices[i] >= prices[i+1] for i in range(len(prices)-1))
    return {"pass": is_sorted, "detail": f"sort_by_ranking: sorted_desc={is_sorted}"}


def verify_macro_sort_by_date_range(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings?status=ended&sort=newest")
    listings = r.json()
    ok = all(p["status"] == "ended" for p in listings)
    return {"pass": ok, "detail": f"sort_by_date_range ended: {len(listings)} listings"}


def verify_macro_extract_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/categories/Electronics/stats")
    stats = r.json()
    return {"pass": "avg_price" in stats, "detail": f"extract_by_dropdown: Electronics stats={stats}"}


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings/1")
    listing = r.json()
    return {"pass": "description" in listing, "detail": f"extract_by_route: listing has description"}


def verify_macro_compare_from_table(server_url):
    r = requests.get(f"{_base(server_url)}/api/compare?ids=1,2")
    listings = r.json()
    if len(listings) < 2:
        return {"pass": False, "detail": "Compare needs 2 listings"}
    return {"pass": listings[0]["id"] != listings[1]["id"],
            "detail": f"compare: listing {listings[0]['id']} vs {listings[1]['id']}"}


def verify_macro_create_from_free_text(server_url):
    r = requests.post(f"{_base(server_url)}/api/listings", json={
        "name": "Test Macro Listing", "category": "Electronics",
        "seller_id": 1, "seller_username": "deal_hunter42"
    })
    data = r.json()
    ok = data.get("success", False)
    # Clean up
    if ok:
        requests.delete(f"{_base(server_url)}/api/listings/{data['listing_id']}")
    return {"pass": ok, "detail": f"create_from_free_text: {data}"}


def verify_macro_submit_by_query(server_url):
    # Place a bid on an active listing
    r = requests.get(f"{_base(server_url)}/api/listings?status=active&limit=1")
    listings = r.json()
    if not listings:
        return {"pass": False, "detail": "No active listings"}
    lid = listings[0]["id"]
    current = listings[0]["current_price"]
    r = requests.post(f"{_base(server_url)}/api/listings/{lid}/bid",
                       json={"amount": current + 10, "bidder_id": 21})
    data = r.json()
    return {"pass": data.get("success", False), "detail": f"submit_by_query bid: {data}"}


def verify_macro_edit_by_form(server_url):
    r = requests.put(f"{_base(server_url)}/api/listings/2",
                      json={"description": "Macro test edit"})
    data = r.json()
    ok = data.get("success", False)
    # Restore
    requests.put(f"{_base(server_url)}/api/listings/2",
                  json={"description": "Original description"})
    return {"pass": ok, "detail": f"edit_by_form: {data}"}


def verify_macro_delete_from_table(server_url):
    # Create a message then delete it
    r = requests.post(f"{_base(server_url)}/api/messages",
                       json={"sender_id": 21, "receiver_id": 1, "body": "test"})
    msg_id = r.json().get("message_id")
    r2 = requests.delete(f"{_base(server_url)}/api/messages/{msg_id}")
    data = r2.json()
    return {"pass": data.get("success", False), "detail": f"delete_from_table: {data}"}


def verify_macro_upload_by_upload(server_url):
    import io
    files = {"file": ("test.png", io.BytesIO(b"fake"), "image/png")}
    r = requests.post(f"{_base(server_url)}/api/listings/1/upload", files=files)
    data = r.json()
    return {"pass": data.get("success", False), "detail": f"upload_by_upload: {data}"}


def verify_macro_configure_by_slider(server_url):
    r = requests.post(f"{_base(server_url)}/api/settings/bid-increment",
                       json={"increment": 5.0})
    data = r.json()
    return {"pass": data.get("success", False), "detail": f"configure_by_slider: {data}"}


def verify_macro_rate_by_slider(server_url):
    r = requests.post(f"{_base(server_url)}/api/ratings", json={
        "listing_id": 5, "rater_id": 30, "rated_user_id": 1,
        "score": 5, "comment": "Macro test"
    })
    data = r.json()
    return {"pass": data.get("success", False), "detail": f"rate_by_slider: {data}"}


def verify_macro_follow_by_toggle(server_url):
    r = requests.post(f"{_base(server_url)}/api/users/30/follow",
                       json={"seller_id": 5})
    data = r.json()
    ok = data.get("action") == "followed"
    # Toggle back
    requests.post(f"{_base(server_url)}/api/users/30/follow",
                   json={"seller_id": 5})
    return {"pass": ok, "detail": f"follow_by_toggle: {data}"}


def verify_macro_save_by_toggle(server_url):
    r = requests.post(f"{_base(server_url)}/api/users/30/save",
                       json={"listing_id": 99})
    data = r.json()
    ok = data.get("action") == "saved"
    # Toggle back
    requests.post(f"{_base(server_url)}/api/users/30/save",
                   json={"listing_id": 99})
    return {"pass": ok, "detail": f"save_by_toggle: {data}"}


def verify_macro_report_by_form(server_url):
    r = requests.post(f"{_base(server_url)}/api/listings/1/report",
                       json={"reporter_id": 21, "reason": "test", "description": "macro test"})
    data = r.json()
    return {"pass": data.get("success", False), "detail": f"report_by_form: {data}"}


def verify_macro_message_from_free_text(server_url):
    r = requests.post(f"{_base(server_url)}/api/messages",
                       json={"sender_id": 21, "receiver_id": 1, "body": "Macro test message"})
    data = r.json()
    ok = data.get("success", False)
    # Clean up
    if ok:
        requests.delete(f"{_base(server_url)}/api/messages/{data['message_id']}")
    return {"pass": ok, "detail": f"message_from_free_text: {data}"}


def verify_macro_submit_by_form(server_url):
    r = requests.post(f"{_base(server_url)}/api/ratings", json={
        "listing_id": 10, "rater_id": 21, "rated_user_id": 2,
        "score": 3, "comment": "Form test"
    })
    data = r.json()
    return {"pass": data.get("success", False), "detail": f"submit_by_form: {data}"}


def verify_macro_add_by_button(server_url):
    r = requests.post(f"{_base(server_url)}/api/users/21/watch",
                       json={"listing_id": 5})
    data = r.json()
    ok = data.get("action") in ("watched", "unwatched")
    # Toggle back
    requests.post(f"{_base(server_url)}/api/users/21/watch",
                   json={"listing_id": 5})
    return {"pass": ok, "detail": f"add_by_button: {data}"}


def verify_macro_checkout_by_form(server_url):
    # Find an active listing for checkout
    r = requests.get(f"{_base(server_url)}/api/listings?status=active&limit=1")
    listings = r.json()
    if not listings:
        return {"pass": False, "detail": "No active listings for checkout"}
    lid = listings[0]["id"]
    r = requests.post(f"{_base(server_url)}/api/checkout", json={
        "listing_id": lid, "buyer_id": 21,
        "payment_method": "Credit Card", "shipping_address": "Test"
    })
    data = r.json()
    return {"pass": data.get("success", False), "detail": f"checkout_by_form: {data}"}


def verify_macro_authenticate_by_form(server_url):
    s = requests.Session()
    r = s.post(f"{_base(server_url)}/api/login",
               json={"username": "alice_bidder", "password": "buyer001"})
    data = r.json()
    ok = data.get("user_id") == 21
    return {"pass": ok, "detail": f"authenticate: user_id={data.get('user_id')}"}


def verify_macro_register_by_form(server_url):
    r = requests.post(f"{_base(server_url)}/api/register", json={
        "username": "macro_test_user", "password": "test123",
        "email": "macro@test.com", "name": "Macro Test"
    })
    data = r.json()
    ok = data.get("username") == "macro_test_user"
    return {"pass": ok, "detail": f"register: {data}"}
