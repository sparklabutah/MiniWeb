# SkyLodge Travel (`flights-hotels`)

A flight and hotel booking site in the style of Expedia / Kayak, covering major
US cities. Users search and filter flights and hotels, book a flight through a
multi-step flow (travelers, seat map, review, payment), book hotel stays, and
view or cancel their bookings.

- URL: `/sites/flights-hotels/` (simulated domain `skylodge.travel`)
- Data split: held-out (test) site
- Data sources: US airline routes and fares
  (https://www.kaggle.com/datasets/bhavikjikadara/us-airline-flight-routes-and-fares-1993-2024)
  and TBO hotels (https://www.kaggle.com/datasets/raj713335/tbo-hotels-dataset)

## Pages

| Route | Page |
|---|---|
| `/` | Search home with Flights and Hotels tabs: origin/destination, dates, airline, cabin class, max-price slider, stops checkboxes, hotel city/stars/rating/sort |
| `/flights`, `/flight/<id>` | Flight results (date, max price, sort) and flight detail with the booking form |
| `/book/flight/seats`, `/book/flight/review` | Seat map, then itinerary, fare breakdown and payment review |
| `/hotels`, `/hotel/<id>` | Hotel results (city, stars, rating, amenity) and hotel detail with the booking form |
| `/book/hotel/review` | Stay review: room, nightly rate, nights, total, payment |
| `/bookings`, `/booking/<id>` | My bookings and booking detail with "Cancel Booking" |
| `/login` | Sign-in form |

JSON endpoints under `/api/` cover flights, hotels, search, compare, bookings, promo-code validation and user preferences.

## Interactions and macros

- Search flights by origin and destination: `search`
- Filter by airline, cabin class, city, stars, rating or amenity: `filter_by_dropdown`
- Set departure or check-in/check-out dates: `filter_by_date_range`
- Max-price slider; stops checkboxes: `filter_by_slider`, `filter_by_options`
- Sort flights or hotels: `sort_by_form`
- Open a flight, hotel or booking: `navigate_by_route`
- Book a flight or hotel and pay: `book_by_form`, `checkout_by_form`, `pay_by_form`
- Cancel a booking: `cancel_by_form`
- Compare and read listings: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `flights-hotels`.

## Data

- Tables: `flights_hotels_flights`, `flights_hotels_hotels`,
  `flights_hotels_bookings`, `flights_hotels_users`.
- Login uses the shared `session["user_id"]` (via `helpers.auth`), so the
  global auto-login signs in user 1.
- Confirming a booking goes through 2FA (`request_2fa("payment")` →
  `/verify-payment`, code emailed to WebMail), which posts the banking debit.
  The booking is written only after 2FA, on `/book/<flight|hotel>/complete`.
  That step also adds a calendar event and email (`on_booking`) and sends an
  instant message (`emit("message")`).
- Cancelling refunds the full total of a confirmed booking. Logging in emits
  `signup` (password-vault entry + email).
