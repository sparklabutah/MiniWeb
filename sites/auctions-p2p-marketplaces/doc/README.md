# BidMarket (`auctions-p2p-marketplaces`)

An eBay-style auction and peer-to-peer marketplace. Users browse and filter
listings, bid or buy now, watch and save items, follow sellers, message
sellers, and sell their own items.

- URL: `/sites/auctions-p2p-marketplaces/` (simulated domain `bidmarket.com`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Listing grid with search, category/status dropdowns, condition radios, max-price slider, sort |
| `/listing/<id>` | Listing detail: bid form, Buy It Now, watch/save, follow seller, contact seller, report, bid history, seller reviews |
| `/listing/<id>/checkout` | Buy It Now checkout (shipping and card form) |
| `/category/<name>` | Listings in one category |
| `/seller/<id>` | Seller profile, listings and reviews |
| `/compare?ids=` | Side-by-side comparison of selected listings |
| `/dashboard` | My listings, bids, watchlist, won and purchased items, messages (login required) |
| `/create-listing` | Sell form with image upload |
| `/edit-listing/<id>` | Edit one of the user's listings |
| `/login`, `/register` | Sign-in and registration |

JSON endpoints under `/api/` cover listings, search, categories, compare, export, bids, messages and ratings.

## Interactions and macros

- Search listings by keyword: `search`
- Filter by category/status, condition, max price: `filter_by_dropdown`, `filter_by_options`, `filter_by_slider`
- Sort results (Ending Soon, Newest, Price, Most Bids): `sort_by_form`
- Create a listing (with image upload), place a bid, register: `create_by_form`, `upload_file`
- Edit or delete a listing, delete a message: `edit_by_form`, `delete_from_table`
- Buy It Now checkout: `checkout_by_form`
- Watch or save a listing, follow a seller: `toggle_relationship`
- Message a seller: `message_from_free_text`
- Read listing details, bid history and the compare table: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `auctions-p2p-marketplaces`.

## Data

- Tables: `auctions_p2p_marketplaces_products`, `_bids`, `_users`, `_watchlist`,
  `_messages`, `_ratings`, `_reports`, `_orders` (created at runtime on first use),
  `_webshop_products_samplel`. Listings were built from WebShop product data.
- Login reads `session["user_id"]`, so the global auto-login signs in as user 1.
- Auction dates are static. Active listings stay biddable regardless of the
  wall clock; only listings already marked `ended` get a winner (top bid above reserve).
- Checkout charges the card through `app.bank_charges.charge_card` (a known
  SecureBank card must have the right CVC) and emits `purchase`, which posts a
  banking debit and a confirmation email. Registering emits `signup`; messages
  to sellers are mirrored to instant messaging (`on_message`).
