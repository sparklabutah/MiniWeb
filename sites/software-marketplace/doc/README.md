# AppVault Software Marketplace (`software-marketplace`)

A Google Play-style app store. Users browse, search and filter apps, compare
two apps, install and review them, keep a wishlist, buy paid apps through a
cart and card checkout with promo codes, and manage purchases and refunds.

- URL: `/sites/software-marketplace/` (simulated domain `appvault.store`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Featured and popular apps with the "Search for apps & games" box |
| `/apps` | Browse with category, genre, min-rating and price dropdowns, a Max Price slider and a sort dropdown |
| `/category/<cat>` | Apps in one category |
| `/app/<id>` | App detail: description, reviews, Install/Uninstall, Add to Cart, wishlist toggle, review form |
| `/compare` | Two app dropdowns and a side-by-side comparison table |
| `/cart` | Cart with remove |
| `/checkout` | Card payment and promo-code field |
| `/wishlist`, `/my-apps` | Wishlisted and installed apps |
| `/purchases`, `/purchase/<id>` | Purchase history; receipt with Request Refund |
| `/settings` | Theme, language, content filter and a notification-frequency slider |
| `/login` | Sign-in form |

JSON endpoints under `/api/` cover apps (filters, semantic search, compare),
reviews, categories, genres, cart, checkout, wishlist, promo validation,
settings, purchases and export.

## Interactions and macros

- Search apps: `search`
- Filter by category, genre, rating or price: `filter_by_dropdown`; by max price: `filter_by_slider`
- Sort apps by rating, reviews, name, newest or price: `sort_by_form`
- Open an app: `navigate_by_route`
- Install or add to cart: `create_by_form`; wishlist an app: `toggle_relationship`
- Check out with a promo code: `checkout_by_form`
- Change settings, including the slider: `configure_by_form`
- Read app details and the compare table: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `software-marketplace`.

## Data

- Source: Google Play Store apps dataset (Kaggle), sampled.
- Tables (`software_marketplace_*`): `apps`, `reviews`, `app_reviews`,
  `installed`, `wishlists`, `promo_codes`, `settings`, `users`, plus `cart`
  and `purchases`, which `routes.py` creates and registers at runtime if missing.
- Login uses `session["user_id"]`, so the global auto-login signs in user 1.
- Checkout charges the card through `app/bank_charges.charge_card` (any card
  number is accepted, but a known SecureBank card needs its correct CVV) and
  emits `purchase` (banking debit and confirmation email).
- Installing an app sends an email and emits `file_created`; a refund sends an
  email; signing in emits `signup`.
