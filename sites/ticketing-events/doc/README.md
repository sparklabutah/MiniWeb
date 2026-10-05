# Lakeport Events (`ticketing-events`)

An Eventbrite/Ticketmaster-style ticketing site for events in Lakeport. Users
discover events in an infinite-scroll feed, filter and sort them, compare two
events, buy tickets (with reserved seating and promo codes), save events and
cancel orders.

- URL: `/sites/ticketing-events/` (simulated domain `eventpass.live`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Discover Events: search box, Category and Status dropdowns, Date From/To, Max Price slider, Sort by, heart-save toggles, infinite-scroll feed |
| `/search` | Search results page (`q`) |
| `/event/<id>` | Event detail with ticket type and quantity, Buy Now / Reserve Now |
| `/checkout/<id>` | Checkout: buyer details, seat map for reserved events, promo code |
| `/my-tickets` | Orders and tickets with Cancel Order |
| `/cancel/<order_id>` | Cancellation form with a reason |
| `/compare` | Side-by-side comparison of two events |
| `/settings` | Location and notification preferences |
| `/login`, `/register` | Sign-in and sign-up forms |

JSON endpoints under `/api/` cover events (feed, semantic search, price and
date ranges), orders, tickets, wishlist, cart, promo validation, compare,
feedback, stats and export.

## Interactions and macros

- Search events, venues and organizers: `search`
- Filter by category or status: `filter_by_dropdown`; by date: `filter_by_date_range`; by max price: `filter_by_slider`
- Sort by date, price or name: `sort_by_form`
- Open an event or My Tickets: `navigate_by_route`
- Book tickets: `book_by_form`; pay at checkout with a promo code: `checkout_by_form`
- Cancel an order: `cancel_by_form`
- Save an event with the heart toggle: `toggle_relationship`
- Change settings: `configure_by_form`, `filter_by_options`
- Read search results and the compare table: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `ticketing-events`.

## Data

- Tables (`ticketing_events_*`): `events`, `tickets`, `orders`, `users`.
- Login uses `session["user_id"]` (via `helpers.auth`), so the global
  auto-login signs in user 1.
- A completed order calls `on_purchase` (banking debit and confirmation email)
  and `on_booking` (calendar-todo event and booking email) from `app/bridges.py`.
  Checkout takes no card; nothing goes through 2FA.
- Registering emits a `signup` event.
- Promo codes are defined in `routes.py` (`PROMO_CODES`); booking fees are 12%.
