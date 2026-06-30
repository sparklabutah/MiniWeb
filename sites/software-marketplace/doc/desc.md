This website simulates a software marketplace / app store (Google Play Store style). Users can browse, search, filter, and sort applications across 25 categories. The interface emulates the Google Play Store with featured apps, category browsing, app detail pages with user reviews, wishlists, shopping cart, checkout with promo codes, and user settings.

Data source: data_sources/software-marketplace/apps.json (50 apps derived from Google Play Store CSV)
Additional data: users.json, reviews.json, installed.json, wishlists.json, cart.json, purchases.json, promo_codes.json, settings.json
Searching method: keyword match + semantic overlap scoring over app names, descriptions, and categories
