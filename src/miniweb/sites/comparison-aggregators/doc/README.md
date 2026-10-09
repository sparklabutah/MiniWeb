# PhoneCompare (`comparison-aggregators`)

A GSMArena-style phone catalog and comparison site. Users filter and sort
phones by specs, open spec sheets, compare two phones side by side, and keep a
favorites list and a compare list.

- URL: `/sites/comparison-aggregators/` (simulated domain `comparewise.com`)
- Data split: held-out (test) site

## Pages

| Route | Page |
|---|---|
| `/` | Phone list: search, brand/OS/sort dropdowns, max-price and min-battery sliders, feature checkboxes (NFC, GPS, Dual SIM, Fingerprint) |
| `/phone/<id>` | Spec sheet with Favorite and Add to Compare buttons |
| `/brand/<name>` | One brand's phones |
| `/compare` | Two phone dropdowns and a side-by-side spec table |
| `/favorites` | The user's favorite phones |
| `/dashboard` | Favorites and compare list with remove buttons (login required) |
| `/login` | Sign-in form |

JSON endpoints under `/api/` expose phones, brands, compare and stats.

## Interactions and macros

- Search phones by name: `search`
- Filter by brand/OS, price/battery, features: `filter_by_dropdown`, `filter_by_slider`, `filter_by_options`
- Sort by newest, name, price or battery: `sort_by_form`
- Open a phone or a brand page: `navigate_by_route`
- Favorite/unfavorite a phone, remove from favorites: `toggle_relationship`
- Read specs, find the cheapest or longest-lasting phone, compare two phones: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `comparison-aggregators`.

## Data

- Tables: `comparison_aggregators_phones`, `comparison_aggregators_users`.
  Favorites and the compare list are stored on the user row.
- Login reads `session["user_id"]`, so the global auto-login signs in as user 1.
- No cross-site effects.
