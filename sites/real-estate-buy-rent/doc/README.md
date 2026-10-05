# Lakeport Real Estate (`real-estate-buy-rent`)

A Zillow/Redfin-style home search site for Lakeport, WA. Users search and
filter homes for sale or rent, save listings, contact agents, schedule tours
and follow agents.

- URL: `/sites/real-estate-buy-rent/` (simulated domain `lakeportrealty.com`)
- Data split: held-out (test) site

## Pages

| Route | Page |
|---|---|
| `/` | Home: search hero, featured sale and rental listings, market stats |
| `/listings` | Search with type/status/beds/baths dropdowns, max-price slider, feature checkboxes (Garage, Pool, Basement), sort |
| `/listing/<id>` | Listing detail: facts, agent, Save, inquiry form, Schedule a Tour form |
| `/agents`, `/agent/<id>` | Agent directory; agent profile with listings and Follow Agent |
| `/saved` | Saved listings (login required) |
| `/inquiries` | Sent inquiries (login required) |
| `/tours` | My Tours with confirm and cancel (login required) |
| `/login`, `/register` | Sign-in and registration |

JSON endpoints under `/api/` cover listings, agents, saved items, inquiries and market stats.

## Interactions and macros

- Search by address, feature or keyword: `search`
- Filter by type, status, beds, baths, price, features: `filter_by_dropdown`, `filter_by_slider`, `filter_by_options`
- Sort by newest, price, size or bedrooms: `sort_by_form`
- Send an inquiry to the listing agent: `create_by_form`, `book_by_form`
- Save a listing, follow an agent: `toggle_relationship`
- Open listings and agents: `navigate_by_route`
- Read listing facts, agent pages and the cheapest or largest match: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `real-estate-buy-rent`.

## Data

- Tables: `real_estate_buy_rent_listings`, `_agents`, `_users`, `_saved`,
  `_inquiries`, `_listings_raw`, and `_tours` (created at runtime on first use).
  Listings were derived from public US real-estate datasets (Kaggle Zillow
  house-price data and the USA Real Estate dataset).
- Rentals carry `rent_monthly` (with `price` = 0); sorting and price filters
  use the monthly rent for them. `scripts/seed_real_estate_rentals.py` creates
  the rental listings; re-run it after a DB rebuild.
- Login reads `session["user_id"]`, so the global auto-login signs in as user 1.
- Inquiries and tour requests emit `message` (a note in instant messaging).
  Registering emits `signup`.
