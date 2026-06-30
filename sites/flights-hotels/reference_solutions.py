"""Per-task reference solutions via Flask test client for flights-hotels."""
import json


def solve_001(client, base="/sites/flights-hotels"):
    r = client.get(f"{base}/api/flights?airline=Alaska+Airlines")
    flights = json.loads(r.data)
    return str(len(flights))


def solve_002(client, base="/sites/flights-hotels"):
    r = client.get(f"{base}/api/flights/5")
    flight = json.loads(r.data)
    return flight["flight_number"]


def solve_003(client, base="/sites/flights-hotels"):
    r = client.get(f"{base}/api/flights/search?q=Seattle")
    results = json.loads(r.data)
    return str(len(results))


def solve_004(client, base="/sites/flights-hotels"):
    r = client.get(f"{base}/api/hotels/5")
    hotel = json.loads(r.data)
    return hotel["name"]


def solve_005(client, base="/sites/flights-hotels"):
    r = client.get(f"{base}/api/flights?date=2026-07-17")
    flights = json.loads(r.data)
    return str(len(flights))


def solve_006(client, base="/sites/flights-hotels"):
    r = client.get(f"{base}/api/hotels?amenity=Pool")
    hotels = json.loads(r.data)
    return str(len(hotels))


def solve_007(client, base="/sites/flights-hotels"):
    r = client.get(f"{base}/api/flights/15")
    flight = json.loads(r.data)
    return flight["class"]


def solve_008(client, base="/sites/flights-hotels"):
    r = client.get(f"{base}/api/flights?max_price=200")
    flights = json.loads(r.data)
    return str(len(flights))


def solve_009(client, base="/sites/flights-hotels"):
    count = 0
    for date in ["2026-07-20", "2026-07-21", "2026-07-22"]:
        r = client.get(f"{base}/api/flights?date={date}")
        count += len(json.loads(r.data))
    return str(count)


def solve_010(client, base="/sites/flights-hotels"):
    r = client.get(f"{base}/api/flights?sort=duration")
    flights = json.loads(r.data)
    return flights[0]["flight_number"] if flights else ""


def solve_011(client, base="/sites/flights-hotels"):
    r = client.get(f"{base}/api/hotels?city=Seattle%2C+WA&sort=price")
    hotels = json.loads(r.data)
    return hotels[0]["name"] if hotels else ""


def solve_012(client, base="/sites/flights-hotels"):
    r = client.get(f"{base}/api/hotels?sort=rating")
    hotels = json.loads(r.data)
    return hotels[0]["name"] if hotels else ""


def solve_013(client, base="/sites/flights-hotels"):
    r = client.get(f"{base}/api/flights?sort=price_desc")
    flights = json.loads(r.data)
    if flights:
        f = flights[0]
        return f"{f['flight_number']} ${f['price']}"
    return ""


def solve_014(client, base="/sites/flights-hotels"):
    r = client.get(f"{base}/api/compare?type=flight&ids=1,5")
    flights = json.loads(r.data)
    prices = {f["id"]: f["price"] for f in flights}
    p1 = prices.get(1, 0)
    p5 = prices.get(5, 0)
    if p1 < p5:
        return f"Flight 1 is cheaper by ${p5 - p1}"
    else:
        return f"Flight 5 is cheaper by ${p1 - p5}"


def solve_015(client, base="/sites/flights-hotels"):
    r = client.get(f"{base}/api/stats")
    stats = json.loads(r.data)
    return str(stats["hotels"]["average_price_per_night"])


def solve_016(client, base="/sites/flights-hotels"):
    # Login as alex_morgan
    client.post(f"{base}/api/login",
                json={"username": "alex_morgan", "password": "travel123"})
    # Search for 'Grand' hotels
    r = client.get(f"{base}/api/hotels/search?q=Grand")
    hotels = json.loads(r.data)
    if len(hotels) < 2:
        return "Not enough results"
    target = hotels[1]
    # Book the hotel
    r = client.post(f"{base}/api/bookings",
                    json={"user_id": 1, "type": "hotel",
                          "reference_id": target["id"], "nights": 2, "travelers": 1})
    booking = json.loads(r.data)
    return f"Booked hotel {target['name']}, booking_id={booking.get('id')}"


def solve_017(client, base="/sites/flights-hotels"):
    client.post(f"{base}/api/login",
                json={"username": "jamie_chen", "password": "travel234"})
    r = client.post(f"{base}/api/users/2/preferences",
                    json={"seat_preference": "aisle", "max_budget": 300})
    prefs = json.loads(r.data)
    return f"seat={prefs.get('seat_preference')}, budget={prefs.get('max_budget')}"


def solve_018(client, base="/sites/flights-hotels"):
    client.post(f"{base}/api/login",
                json={"username": "alex_morgan", "password": "travel123"})
    # Get cheapest hotel
    r = client.get(f"{base}/api/hotels?sort=price&limit=1")
    hotels = json.loads(r.data)
    if not hotels:
        return "No hotels"
    cheapest = hotels[0]
    # Checkout with payment
    r = client.post(f"{base}/api/checkout",
                    json={"user_id": 1, "type": "hotel",
                          "reference_id": cheapest["id"], "nights": 1,
                          "travelers": 1, "card_last_four": "4242"})
    booking = json.loads(r.data)
    return f"Booked {cheapest['name']}, paid ${booking.get('total_price')}"


def solve_019(client, base="/sites/flights-hotels"):
    client.post(f"{base}/api/login",
                json={"username": "taylor_brooks", "password": "travel345"})
    r = client.post(f"{base}/api/promo/validate",
                    json={"code": "SAVE10", "booking_id": 5})
    result = json.loads(r.data)
    return str(result.get("new_price", ""))


def solve_020(client, base="/sites/flights-hotels"):
    client.post(f"{base}/api/login",
                json={"username": "alex_morgan", "password": "travel123"})
    r = client.delete(f"{base}/api/bookings/1")
    result = json.loads(r.data)
    return result.get("status", "")
