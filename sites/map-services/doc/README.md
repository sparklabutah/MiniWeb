# CascadiaMaps (`map-services`)

A Google Maps-style map and navigation service for Lakeport, WA. Users search
places on an interactive Leaflet map, filter by category, rating and "open
now", open place pages with hours and reviews, save places, write reviews,
get directions by travel mode and compare places.

- URL: `/sites/map-services/` (simulated domain `cascadiamaps.com`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Map with search, category, sort, min-rating slider and "Open now" filter; the result list follows the map view |
| `/place/<id>` | Place detail: address, hours, rating, reviews, "Save Place", review form |
| `/directions` | From / To inputs with Driving / Cycling / Walking / Transit modes and route cards (`?from=&to=` prefill) |
| `/route/<id>` | Saved route detail with turn-by-turn steps |
| `/saved-places` | Saved places |
| `/search-history` | Past searches |
| `/compare` | Pick places and compare them side by side |
| `/settings` | Default travel mode and distance units |
| `/login` | Sign-in form |

JSON endpoints under `/api/` cover locations, categories, nearby search, routes and route computation, saved places, reviews, sharing, compare, export and settings.

## Interactions and macros

- Search places: `search`; pan or zoom the map to change the results in view: `search_by_pan_zoom`
- Sort results: `sort_by_form`, `filter_by_dropdown`
- Min-rating slider; "Open now" toggle: `filter_by_slider`, `filter_by_options`
- Open a place from the map or the list: `navigate_by_route`
- Get directions between two places: `get_nav_route`
- Write a review, save a place: `create_by_form`
- Change the default travel mode or units: `configure_by_form`
- Read place details, directions and comparisons: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `map-services`.

## Data

- Tables: `map_services_locations`, `map_services_reviews`,
  `map_services_routes`, `map_services_route_templates`,
  `map_services_saved_places`, `map_services_search_history`,
  `map_services_users`.
- Places use real street geometry relabeled as Lakeport, WA. Directions come
  from precomputed route templates (path plus steps); distances use
  `helpers.geo.haversine`.
- Login uses the shared `session["user_id"]`, so the global auto-login signs in
  user 1. Logging in emits `signup`.
- Leaflet is served from `/static/vendor/leaflet/`. Base-map tiles load from an
  external CDN, so the map background may be blank in offline runs.
