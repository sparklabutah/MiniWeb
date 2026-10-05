# ShopHub (`e-commerce`)

An Amazon or eBay-style online store. Users search and filter a large product
catalog, read and write reviews, keep a cart and a wishlist, check out, and
cancel or return orders. The UI brand is ShopHub; `site.json` names the site
"E-commerce".

- URL: `/sites/e-commerce/` (simulated domain `shopwave.com`)
- Data split: training site
- Source data: product catalog and reviews derived from WebShop

## Pages

| Route | Page |
|---|---|
| `/` | Catalog with search, sidebar category/brand/rating dropdowns, category checkboxes, price range (Min $ input, Max Price slider) and sort |
| `/category/<name>` | Products in one category |
| `/product/<id>` | Product detail: specs, reviews and review form, Add to Cart, Add to Wishlist |
| `/cart` | Cart with quantity updates, remove and promo-code entry |
| `/checkout` | Shipping address, shipping method, "Pay with" account and Place Your Order |
| `/orders`, `/order/<order_id>` | Order history with Cancel Order and Request Return; order detail |
| `/wishlist` | Saved products |
| `/login` | Sign-in form |

JSON endpoints under `/api/` cover products, categories, brands, cart,
wishlist, orders, returns and reviews.

## Interactions and macros

- Search products: `search`
- Filter by dropdowns, category checkboxes or the price slider: `filter_by_dropdown`, `filter_by_options`, `filter_by_slider`
- Set a min/max price range: `configure_by_form`
- Sort by price, rating or review count: `sort_by_form`
- Add to cart: `create_by_form`
- Apply a promo code and check out: `checkout_by_form`, `pay_by_form`
- Cancel an order: `cancel_by_form`
- Add to or remove from the wishlist: `toggle_relationship`
- Compare products and read specs and reviews: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `e-commerce`.

## Data

- Tables: `e_commerce_products`, `e_commerce_reviews`, `e_commerce_users`.
  Cart, wishlist and orders are stored on the user record.
- Login reads `session["user_id"]`, so the global auto-login signs the user in
  as user 1.
- Placing an order goes through the shared 2FA flow: a code is emailed to
  WebMail and entered at `/verify-payment` (skipped when
  `session["_disable_2fa"]` is set). On success a `purchase` event debits the
  chosen bank account and sends an order email.
- Promo codes are the static `SAVE10`, `WELCOME5` and `SHOP20`, plus
  checksum-signed codes that appear briefly inside videos on other sites
  (`app/playback.validate_promo`).
- Product cards are reused as in-network ads on other sites (`app/ads.py`).
- Logging in emits a `signup` event (password-manager entry and welcome email).
