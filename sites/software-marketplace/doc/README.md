# Software Marketplace

**Category**: Shopping & transactional
**Reviewer**: Farhan
**Number of macros**: 17

## Data Source

Google Play Store dataset (Kaggle) -- 50 apps sampled from the full CSV.
File: `data_sources/software-marketplace/apps.json`

### Data Format

`apps.json` contains 50 app records with fields:
- `id` -- integer app ID (1-50)
- `name` -- app name (e.g., "Uber Driver")
- `category` -- Play Store category (e.g., "BUSINESS", "GAME")
- `rating` -- store rating (4.0-4.8)
- `reviews_count` -- total review count from the store listing
- `size` -- app size string (e.g., "Varies with device", "25M")
- `installs` -- install count string (e.g., "10,000,000+")
- `price` -- price in USD (0.0 for free, 0.99-7.99 for paid)
- `content_rating` -- age rating (Everyone, Teen, Mature 17+)
- `genre` -- genre label (e.g., "Business", "Arcade")
- `developer` -- developer name
- `description` -- short description text
- `last_updated` -- date string (YYYY-MM-DD)

Additional mutable data files:
- `users.json` -- 5 user accounts (username, password, display_name)
- `reviews.json` -- 40 user-submitted reviews with ratings 1-5
- `installed.json` -- user-app install records
- `wishlists.json` -- user wishlist items
- `cart.json` -- shopping cart items
- `purchases.json` -- completed purchase records
- `promo_codes.json` -- 5 promo codes (WELCOME20, SUMMER50, FREEAPP, EXPIRED10, VIP30)
- `settings.json` -- per-user settings (theme, language, notification_frequency, etc.)

### Sampling

All 50 apps are loaded by default (num_data_points=-1). The dataset covers 25 categories and 26 genres with 38 free and 12 paid apps.

## Real-World Model

**Google Play Store** -- mobile app marketplace with card-based browsing. Key UI elements:
- Home page with featured and popular app carousels
- Category browsing with dropdown navigation
- Search bar with keyword and semantic matching
- Filter sidebar (category, genre, rating slider, price slider)
- Sort options (rating, reviews, name, newest, price)
- App detail page with reviews, install/uninstall, add to cart, wishlist toggle
- Compare page for side-by-side app comparison
- Shopping cart with checkout flow and promo code redemption
- User settings page with dropdown and slider configuration
- Export apps as CSV or JSON

## Target Macros

navigate_by_dropdown, navigate_by_route, search_by_query, search_by_semantic, filter_by_dropdown, filter_by_slider, sort_by_ranking, sort_by_extremum, extract_from_table, extract_by_route, compare_from_table, select_by_dropdown, configure_by_dropdown, export_by_dropdown, save_by_toggle, add_by_button, redeem_by_code

## Temporal Dynamics

Not applicable -- app store listings are static catalog data. No temporal simulation needed. Mutable state (reviews, installs, cart, purchases) changes only through user actions.

## Domain-Specific Notes

- 25 categories span typical Play Store verticals (BUSINESS, GAME, EDUCATION, etc.)
- Paid apps range from $0.99 to $7.99; 38 of 50 apps are free
- Promo codes: WELCOME20 (20% off), SUMMER50 (50% off), FREEAPP (100% off), EXPIRED10 (inactive), VIP30 (30% off)
- 5 test users all share password "pass123" for easy automation
- Semantic search uses keyword overlap scoring over name + description fields
- Compare feature supports side-by-side comparison of 2+ apps with enriched review stats
- Settings support dropdown configs (theme, language, content_filter) and slider config (notification_frequency 0-10)
