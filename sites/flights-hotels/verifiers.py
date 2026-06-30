"""Per-task HTTP verification functions for flights-hotels."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/flights-hotels"
    r = requests.get(f"{base}/api/flights?airline=Alaska+Airlines")
    flights = r.json()
    count = len(flights)
    return {"pass": count > 0, "detail": f"Alaska Airlines flights: {count}"}


def verify_002(server_url):
    base = f"{server_url}/sites/flights-hotels"
    r = requests.get(f"{base}/api/flights/5")
    flight = r.json()
    flight_num = flight.get("flight_number", "")
    return {"pass": flight_num == "AA-1090", "detail": f"Flight 5 number: {flight_num}"}


def verify_003(server_url):
    base = f"{server_url}/sites/flights-hotels"
    r = requests.get(f"{base}/api/flights/search?q=Seattle")
    results = r.json()
    count = len(results)
    return {"pass": count > 0, "detail": f"Search 'Seattle': {count} results"}


def verify_004(server_url):
    base = f"{server_url}/sites/flights-hotels"
    r = requests.get(f"{base}/api/hotels/5")
    hotel = r.json()
    name = hotel.get("name", "")
    return {"pass": name == "Bayshore Luxury Resort",
            "detail": f"Hotel 5 name: {name}"}


def verify_005(server_url):
    base = f"{server_url}/sites/flights-hotels"
    r = requests.get(f"{base}/api/flights?date=2026-07-17")
    flights = r.json()
    count = len(flights)
    ok = all(f["date"] == "2026-07-17" for f in flights)
    return {"pass": count > 0 and ok, "detail": f"Flights on 2026-07-17: {count}"}


def verify_006(server_url):
    base = f"{server_url}/sites/flights-hotels"
    r = requests.get(f"{base}/api/hotels?amenity=Pool")
    hotels = r.json()
    count = len(hotels)
    ok = all(any("pool" in a.lower() for a in h["amenities"]) for h in hotels)
    return {"pass": count > 0 and ok, "detail": f"Hotels with Pool: {count}"}


def verify_007(server_url):
    base = f"{server_url}/sites/flights-hotels"
    r = requests.get(f"{base}/api/flights/15")
    flight = r.json()
    cls = flight.get("class", "")
    return {"pass": cls == "first", "detail": f"Flight 15 class: {cls}"}


def verify_008(server_url):
    base = f"{server_url}/sites/flights-hotels"
    r = requests.get(f"{base}/api/flights?max_price=200")
    flights = r.json()
    count = len(flights)
    ok = all(f["price"] <= 200 for f in flights)
    return {"pass": count > 0 and ok, "detail": f"Flights <= $200: {count}"}


def verify_009(server_url):
    base = f"{server_url}/sites/flights-hotels"
    # Get flights for each date in range
    all_in_range = []
    for date in ["2026-07-20", "2026-07-21", "2026-07-22"]:
        r = requests.get(f"{base}/api/flights?date={date}")
        all_in_range.extend(r.json())
    count = len(all_in_range)
    return {"pass": count > 0, "detail": f"Flights 2026-07-20 to 2026-07-22: {count}"}


def verify_010(server_url):
    base = f"{server_url}/sites/flights-hotels"
    r = requests.get(f"{base}/api/flights?sort=duration")
    flights = r.json()
    if not flights:
        return {"pass": False, "detail": "No flights returned"}
    shortest = flights[0]
    durations = [f["duration_minutes"] for f in flights]
    is_sorted = all(durations[i] <= durations[i+1] for i in range(len(durations)-1))
    return {"pass": is_sorted,
            "detail": f"Shortest flight: {shortest['flight_number']} ({shortest['duration_minutes']}min)"}


def verify_011(server_url):
    base = f"{server_url}/sites/flights-hotels"
    r = requests.get(f"{base}/api/hotels?city=Seattle%2C+WA&sort=price")
    hotels = r.json()
    if not hotels:
        return {"pass": False, "detail": "No Seattle hotels"}
    cheapest = hotels[0]["name"]
    return {"pass": len(cheapest) > 0, "detail": f"Cheapest Seattle hotel: {cheapest}"}


def verify_012(server_url):
    base = f"{server_url}/sites/flights-hotels"
    r = requests.get(f"{base}/api/hotels?sort=rating")
    hotels = r.json()
    if not hotels:
        return {"pass": False, "detail": "No hotels returned"}
    top = hotels[0]
    return {"pass": top["rating"] >= 4.5,
            "detail": f"Top-rated: {top['name']} ({top['rating']})"}


def verify_013(server_url):
    base = f"{server_url}/sites/flights-hotels"
    r = requests.get(f"{base}/api/flights?sort=price_desc")
    flights = r.json()
    if not flights:
        return {"pass": False, "detail": "No flights returned"}
    most_expensive = flights[0]
    return {"pass": most_expensive["price"] > 0,
            "detail": f"Most expensive: {most_expensive['flight_number']} ${most_expensive['price']}"}


def verify_014(server_url):
    base = f"{server_url}/sites/flights-hotels"
    r = requests.get(f"{base}/api/compare?type=flight&ids=1,5")
    flights = r.json()
    if len(flights) < 2:
        return {"pass": False, "detail": f"Compare returned {len(flights)} flights"}
    prices = {f["id"]: f["price"] for f in flights}
    diff = abs(prices.get(1, 0) - prices.get(5, 0))
    return {"pass": True, "detail": f"Flight 1: ${prices.get(1)}, Flight 5: ${prices.get(5)}, diff: ${diff}"}


def verify_015(server_url):
    base = f"{server_url}/sites/flights-hotels"
    r = requests.get(f"{base}/api/stats")
    stats = r.json()
    avg = stats["hotels"]["average_price_per_night"]
    return {"pass": avg > 0, "detail": f"Average hotel price: ${avg}"}


def verify_016(server_url):
    base = f"{server_url}/sites/flights-hotels"
    # Check that a new booking was created by user 1 for a hotel with 'Grand' in name
    r = requests.get(f"{base}/api/bookings?user_id=1&type=hotel")
    bookings = r.json()
    hotels = requests.get(f"{base}/api/hotels/search?q=Grand").json()
    if len(hotels) < 2:
        return {"pass": False, "detail": "Not enough 'Grand' hotels found"}
    target_hotel_id = hotels[1]["id"]
    new_booking = [b for b in bookings if b["reference_id"] == target_hotel_id and b["status"] == "confirmed"]
    return {"pass": len(new_booking) > 0,
            "detail": f"Booking for hotel {target_hotel_id}: {'found' if new_booking else 'not found'}"}


def verify_017(server_url):
    base = f"{server_url}/sites/flights-hotels"
    r = requests.get(f"{base}/api/users/2/preferences")
    prefs = r.json()
    ok = prefs.get("seat_preference") == "aisle" and prefs.get("max_budget") == 300
    return {"pass": ok,
            "detail": f"seat={prefs.get('seat_preference')}, budget={prefs.get('max_budget')}"}


def verify_018(server_url):
    base = f"{server_url}/sites/flights-hotels"
    # Cheapest hotel is id 17 (Wicker Park at $79). Check new booking exists with payment.
    r = requests.get(f"{base}/api/bookings?user_id=1&type=hotel")
    bookings = r.json()
    # Find booking for cheapest hotel with payment status
    paid_bookings = [b for b in bookings if b.get("payment_status") == "paid"]
    return {"pass": len(paid_bookings) > 0,
            "detail": f"Paid hotel bookings for user 1: {len(paid_bookings)}"}


def verify_019(server_url):
    base = f"{server_url}/sites/flights-hotels"
    r = requests.get(f"{base}/api/bookings/5")
    booking = r.json()
    has_promo = booking.get("promo_code") == "SAVE10"
    # Original was 789.00, 10% off = 710.10
    return {"pass": has_promo,
            "detail": f"Booking 5 promo={booking.get('promo_code')}, price={booking.get('total_price')}"}


def verify_020(server_url):
    base = f"{server_url}/sites/flights-hotels"
    r = requests.get(f"{base}/api/bookings/1")
    booking = r.json()
    ok = booking.get("status") == "cancelled"
    return {"pass": ok, "detail": f"Booking 1 status: {booking.get('status')}"}
