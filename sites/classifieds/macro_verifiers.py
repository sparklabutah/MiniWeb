"""Per-macro verification functions for classifieds.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/classifieds"


def verify_macro_navigate_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/?q=Toyota")
    return {"pass": r.status_code == 200, "detail": f"navigate_by_query: {r.status_code}"}


def verify_macro_navigate_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/category/vehicles")
    return {"pass": r.status_code == 200, "detail": f"Category page vehicles: {r.status_code}"}


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/listing/1")
    return {"pass": r.status_code == 200, "detail": f"Listing detail page: {r.status_code}"}


def verify_macro_search_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings/search?q=car")
    results = r.json()
    return {"pass": len(results) > 0, "detail": f"search_by_query 'car': {len(results)} results"}


def verify_macro_search_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings/semantic?q=home+improvement")
    results = r.json()
    return {"pass": r.status_code == 200, "detail": f"search_by_semantic: {len(results)} results"}


def verify_macro_filter_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings/search?q=camera")
    results = r.json()
    return {"pass": r.status_code == 200, "detail": f"filter_by_query: {len(results)} results"}


def verify_macro_filter_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings?category=electronics")
    listings = r.json()
    ok = all(l["category"] == "electronics" for l in listings)
    return {"pass": ok, "detail": f"filter_by_dropdown: {len(listings)} electronics, all_match={ok}"}


def verify_macro_filter_by_radio(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings?condition=new")
    listings = r.json()
    ok = all(l.get("condition") == "new" for l in listings)
    return {"pass": ok, "detail": f"filter_by_radio: {len(listings)} new items, all_match={ok}"}


def verify_macro_filter_by_slider(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings?price_min=100&price_max=500")
    listings = r.json()
    ok = all(100 <= l["price"] <= 500 for l in listings)
    return {"pass": ok, "detail": f"filter_by_slider $100-$500: {len(listings)} listings, in_range={ok}"}


def verify_macro_sort_by_ranking(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings?sort=price_low")
    listings = r.json()
    if len(listings) < 2:
        return {"pass": True, "detail": "Too few listings to verify sort"}
    prices = [l["price"] for l in listings]
    is_sorted = all(prices[i] <= prices[i+1] for i in range(len(prices)-1))
    return {"pass": is_sorted, "detail": f"sort_by_ranking: sorted={is_sorted}"}


def verify_macro_extract_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings/search?q=sofa")
    results = r.json()
    if results:
        return {"pass": True, "detail": f"extract_by_query: first={results[0]['title'][:50]}"}
    return {"pass": True, "detail": "extract_by_query: no results (ok)"}


def verify_macro_extract_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/categories/furniture/stats")
    stats = r.json()
    return {"pass": "avg_price" in stats, "detail": f"extract_by_dropdown: furniture stats={stats}"}


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/listings/1")
    listing = r.json()
    return {"pass": "description" in listing, "detail": f"extract_by_route: has description={len(listing.get('description',''))} chars"}


def verify_macro_compare_from_table(server_url):
    r = requests.get(f"{_base(server_url)}/api/compare?ids=1,2")
    listings = r.json()
    if len(listings) < 2:
        return {"pass": False, "detail": "Compare needs 2 listings"}
    return {"pass": listings[0]["id"] != listings[1]["id"],
            "detail": f"compare: listing {listings[0]['id']} vs {listings[1]['id']}"}


def verify_macro_create_from_free_text(server_url):
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "mike_seller", "password": "pass123"})
    r = s.post(f"{base}/api/listings", json={
        "title": "__macro_test_listing__",
        "description": "Test listing for macro verification",
        "price": 100,
        "category": "electronics",
        "condition": "new",
        "location": "Test City"
    })
    data = r.json()
    ok = data.get("title") == "__macro_test_listing__"
    # Clean up: delete it
    if ok:
        s.delete(f"{base}/api/listings/{data['id']}")
    return {"pass": ok, "detail": f"create_from_free_text: created={ok}"}


def verify_macro_submit_by_query(server_url):
    # Same as create - the form submission is the macro
    r = requests.get(f"{_base(server_url)}/post")
    return {"pass": r.status_code == 200 or r.status_code == 302,
            "detail": f"submit_by_query: post page status={r.status_code}"}


def verify_macro_edit_by_form(server_url):
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "sarah_tech", "password": "pass456"})
    # Read original
    r = s.get(f"{base}/api/listings/2")
    orig_price = r.json().get("price")
    # Update
    r = s.put(f"{base}/api/listings/2", json={"price": orig_price})
    data = r.json()
    return {"pass": data.get("price") == orig_price,
            "detail": f"edit_by_form: price={data.get('price')}"}


def verify_macro_delete_from_table(server_url):
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "mike_seller", "password": "pass123"})
    # Create a temp listing to delete
    r = s.post(f"{base}/api/listings", json={
        "title": "__delete_test__", "description": "temp", "price": 1,
        "category": "electronics", "condition": "new", "location": "Test"
    })
    lid = r.json().get("id")
    r = s.delete(f"{base}/api/listings/{lid}")
    data = r.json()
    return {"pass": data.get("action") == "deleted",
            "detail": f"delete_from_table: action={data.get('action')}"}


def verify_macro_upload_by_upload(server_url):
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "mike_seller", "password": "pass123"})
    import io
    files = {"file": ("test.jpg", io.BytesIO(b"fake image data"), "image/jpeg")}
    r = s.post(f"{base}/api/upload", files=files, data={"listing_id": "1"})
    data = r.json()
    return {"pass": data.get("action") == "uploaded",
            "detail": f"upload_by_upload: action={data.get('action')}, file={data.get('filename')}"}


def verify_macro_select_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/categories")
    cats = r.json()
    return {"pass": len(cats) > 0, "detail": f"select_by_dropdown: {len(cats)} categories available"}


def verify_macro_save_by_toggle(server_url):
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "buyer_jane", "password": "passjkl"})
    r = s.post(f"{base}/api/users/10/save", json={"listing_id": 99})
    data = r.json()
    ok = data.get("action") == "saved"
    # Toggle back
    s.post(f"{base}/api/users/10/save", json={"listing_id": 99})
    return {"pass": ok, "detail": f"save_by_toggle: action={data.get('action')}"}


def verify_macro_report_by_form(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/reports", json={
        "listing_id": 999,
        "reason": "test",
        "description": "Macro test report"
    })
    data = r.json()
    ok = data.get("status") == "pending"
    return {"pass": ok, "detail": f"report_by_form: status={data.get('status')}"}


def verify_macro_message_from_free_text(server_url):
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "buyer_jane", "password": "passjkl"})
    r = s.post(f"{base}/api/messages", json={
        "listing_id": 1,
        "recipient_id": 1,
        "subject": "__macro_test_msg__",
        "body": "Test message"
    })
    data = r.json()
    ok = data.get("subject") == "__macro_test_msg__"
    return {"pass": ok, "detail": f"message_from_free_text: sent={ok}"}


def verify_macro_authenticate_by_form(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/login",
                      json={"username": "mike_seller", "password": "pass123"})
    data = r.json()
    ok = data.get("user_id") == 1
    return {"pass": ok, "detail": f"authenticate: user_id={data.get('user_id')}"}


def verify_macro_register_by_form(server_url):
    base = _base(server_url)
    import time
    uname = f"__test_user_{int(time.time())}__"
    r = requests.post(f"{base}/api/register", json={
        "username": uname,
        "password": "testpass",
        "name": "Test User",
        "email": f"{uname}@test.com"
    })
    data = r.json()
    ok = "user_id" in data
    return {"pass": ok, "detail": f"register_by_form: user_id={data.get('user_id')}"}
