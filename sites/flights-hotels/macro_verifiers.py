"""Per-macro verification functions for flights-hotels.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/flights-hotels"


def verify_macro_navigate_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/flights")
    return {"pass": r.status_code == 200, "detail": f"Flights page: {r.status_code}"}


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/flight/1")
    return {"pass": r.status_code == 200, "detail": f"Flight detail: {r.status_code}"}


def verify_macro_search_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/flights/search?q=Seattle")
    results = r.json()
    return {"pass": len(results) > 0, "detail": f"search_by_query 'Seattle': {len(results)} results"}


def verify_macro_search_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/flights/1")
    flight = r.json()
    return {"pass": "flight_number" in flight,
            "detail": f"search_by_route: flight_number={flight.get('flight_number')}"}


def verify_macro_search_by_date_range(server_url):
    r = requests.get(f"{_base(server_url)}/api/flights?date=2026-07-17")
    flights = r.json()
    return {"pass": len(flights) > 0, "detail": f"search_by_date_range: {len(flights)} flights on 2026-07-17"}


def verify_macro_filter_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/flights?airline=Delta+Air+Lines")
    flights = r.json()
    ok = all(f["airline"] == "Delta Air Lines" for f in flights)
    return {"pass": ok and len(flights) > 0,
            "detail": f"filter_by_dropdown Delta: {len(flights)} flights, all_match={ok}"}


def verify_macro_filter_by_checkbox(server_url):
    r = requests.get(f"{_base(server_url)}/api/hotels?amenity=Pool")
    hotels = r.json()
    ok = all(any("pool" in a.lower() for a in h["amenities"]) for h in hotels)
    return {"pass": ok and len(hotels) > 0,
            "detail": f"filter_by_checkbox Pool: {len(hotels)} hotels"}


def verify_macro_filter_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/flights/15")
    flight = r.json()
    return {"pass": flight.get("class") == "first",
            "detail": f"filter_by_route flight 15: class={flight.get('class')}"}


def verify_macro_filter_by_slider(server_url):
    r = requests.get(f"{_base(server_url)}/api/flights?max_price=200")
    flights = r.json()
    ok = all(f["price"] <= 200 for f in flights)
    return {"pass": ok and len(flights) > 0,
            "detail": f"filter_by_slider max_price=200: {len(flights)} flights"}


def verify_macro_filter_by_date_range(server_url):
    count = 0
    for d in ["2026-07-20", "2026-07-21", "2026-07-22"]:
        r = requests.get(f"{_base(server_url)}/api/flights?date={d}")
        count += len(r.json())
    return {"pass": count > 0, "detail": f"filter_by_date_range 07-20 to 07-22: {count} flights"}


def verify_macro_sort_by_ranking(server_url):
    r = requests.get(f"{_base(server_url)}/api/flights?sort=price")
    flights = r.json()
    if len(flights) < 2:
        return {"pass": True, "detail": "Too few flights"}
    prices = [f["price"] for f in flights]
    is_sorted = all(prices[i] <= prices[i+1] for i in range(len(prices)-1))
    return {"pass": is_sorted, "detail": f"sort_by_ranking: sorted={is_sorted}"}


def verify_macro_extract_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/hotels?city=Seattle%2C+WA&sort=price")
    hotels = r.json()
    if hotels:
        return {"pass": True,
                "detail": f"extract_by_dropdown: cheapest Seattle hotel={hotels[0]['name']}"}
    return {"pass": False, "detail": "No Seattle hotels"}


def verify_macro_extract_by_ranking(server_url):
    r = requests.get(f"{_base(server_url)}/api/hotels?sort=rating")
    hotels = r.json()
    if hotels:
        return {"pass": True,
                "detail": f"extract_by_ranking: top-rated={hotels[0]['name']} ({hotels[0]['rating']})"}
    return {"pass": False, "detail": "No hotels"}


def verify_macro_extract_by_extremum(server_url):
    r = requests.get(f"{_base(server_url)}/api/flights?sort=price_desc")
    flights = r.json()
    if flights:
        return {"pass": True,
                "detail": f"extract_by_extremum: most expensive={flights[0]['flight_number']} ${flights[0]['price']}"}
    return {"pass": False, "detail": "No flights"}


def verify_macro_compare_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/compare?type=flight&ids=1,5")
    items = r.json()
    return {"pass": len(items) == 2,
            "detail": f"compare_by_dropdown: {len(items)} items returned"}


def verify_macro_compare_from_table(server_url):
    r = requests.get(f"{_base(server_url)}/api/compare?type=hotel&ids=1,5")
    items = r.json()
    if len(items) < 2:
        return {"pass": False, "detail": "compare_from_table: need 2 items"}
    return {"pass": items[0]["id"] != items[1]["id"],
            "detail": f"compare_from_table: hotel {items[0]['id']} vs {items[1]['id']}"}


def verify_macro_verify_from_free_text(server_url):
    r = requests.get(f"{_base(server_url)}/api/stats")
    stats = r.json()
    return {"pass": "hotels" in stats and "average_price_per_night" in stats["hotels"],
            "detail": f"verify_from_free_text: avg_hotel_price={stats['hotels']['average_price_per_night']}"}


def verify_macro_submit_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/hotels/search?q=Grand")
    results = r.json()
    return {"pass": len(results) > 0,
            "detail": f"submit_by_query: search 'Grand' returned {len(results)} results"}


def verify_macro_select_by_ranking(server_url):
    r = requests.get(f"{_base(server_url)}/api/hotels?sort=price")
    hotels = r.json()
    if len(hotels) >= 2:
        return {"pass": True, "detail": f"select_by_ranking: 2nd cheapest={hotels[1]['name']}"}
    return {"pass": False, "detail": "Not enough hotels"}


def verify_macro_select_by_slider(server_url):
    r = requests.get(f"{_base(server_url)}/api/hotels?max_price=100&sort=price")
    hotels = r.json()
    return {"pass": len(hotels) > 0,
            "detail": f"select_by_slider: {len(hotels)} hotels under $100"}


def verify_macro_configure_by_radio(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/users/5/preferences",
                      json={"seat_preference": "middle"})
    prefs = r.json()
    ok = prefs.get("seat_preference") == "middle"
    # Reset
    requests.post(f"{base}/api/users/5/preferences",
                  json={"seat_preference": "window"})
    return {"pass": ok, "detail": f"configure_by_radio: seat={prefs.get('seat_preference')}"}


def verify_macro_configure_by_slider(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/users/5/preferences",
                      json={"max_budget": 750})
    prefs = r.json()
    ok = prefs.get("max_budget") == 750
    # Reset
    requests.post(f"{base}/api/users/5/preferences",
                  json={"max_budget": 500})
    return {"pass": ok, "detail": f"configure_by_slider: budget={prefs.get('max_budget')}"}


def verify_macro_add_by_dropdown(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/bookings",
                      json={"user_id": 5, "type": "hotel", "reference_id": 1, "travelers": 1})
    booking = r.json()
    ok = booking.get("status") == "confirmed"
    # Clean up
    if "id" in booking:
        requests.delete(f"{base}/api/bookings/{booking['id']}")
    return {"pass": ok, "detail": f"add_by_dropdown: booking status={booking.get('status')}"}


def verify_macro_checkout_by_form(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/checkout",
                      json={"user_id": 5, "type": "flight", "reference_id": 1,
                            "travelers": 1, "card_last_four": "9999"})
    booking = r.json()
    ok = booking.get("payment_status") == "paid"
    # Clean up
    if "id" in booking:
        requests.delete(f"{base}/api/bookings/{booking['id']}")
    return {"pass": ok, "detail": f"checkout_by_form: payment_status={booking.get('payment_status')}"}


def verify_macro_book_by_form(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/bookings",
                      json={"user_id": 5, "type": "flight", "reference_id": 2, "travelers": 1})
    booking = r.json()
    ok = booking.get("status") == "confirmed" and booking.get("type") == "flight"
    if "id" in booking:
        requests.delete(f"{base}/api/bookings/{booking['id']}")
    return {"pass": ok, "detail": f"book_by_form: status={booking.get('status')}"}


def verify_macro_pay_by_form(server_url):
    base = _base(server_url)
    # Create a test booking first
    r = requests.post(f"{base}/api/bookings",
                      json={"user_id": 5, "type": "hotel", "reference_id": 2, "travelers": 1})
    booking = r.json()
    bid = booking.get("id")
    if not bid:
        return {"pass": False, "detail": "Could not create test booking"}
    # Pay it
    r2 = requests.post(f"{base}/api/bookings/{bid}/pay",
                       json={"card_last_four": "1234", "payment_method": "credit_card"})
    pay_result = r2.json()
    ok = pay_result.get("payment_status") == "paid"
    # Clean up
    requests.delete(f"{base}/api/bookings/{bid}")
    return {"pass": ok, "detail": f"pay_by_form: payment_status={pay_result.get('payment_status')}"}


def verify_macro_redeem_by_code(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/promo/validate",
                      json={"code": "SUMMER25"})
    result = r.json()
    ok = result.get("valid") is True
    return {"pass": ok, "detail": f"redeem_by_code: valid={result.get('valid')}, desc={result.get('description')}"}


def verify_macro_cancel_by_form(server_url):
    base = _base(server_url)
    # Create then cancel
    r = requests.post(f"{base}/api/bookings",
                      json={"user_id": 5, "type": "flight", "reference_id": 3, "travelers": 1})
    booking = r.json()
    bid = booking.get("id")
    if not bid:
        return {"pass": False, "detail": "Could not create test booking"}
    r2 = requests.delete(f"{base}/api/bookings/{bid}")
    result = r2.json()
    ok = result.get("status") == "cancelled"
    return {"pass": ok, "detail": f"cancel_by_form: status={result.get('status')}"}
