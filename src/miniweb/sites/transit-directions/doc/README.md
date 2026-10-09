# Lakeport Transit Authority (`transit-directions`)

The public-transit website of the fictional Lakeport Transit Authority (LTA),
in the style of Google Transit / TriMet. It lists bus routes and stops with
timetables, plans trips with route preferences, explains fares and passes, and
compares routes side by side.

- URL: `/sites/transit-directions/` (simulated domain `lakeporttransit.org`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Quick trip planner, route overview, fares at a glance |
| `/routes`, `/route/<id>` | All routes (type filter, sort, export) and route detail with stops and timetable |
| `/stops`, `/stop/<id>` | "Find a Stop" search (zone filter, sort) and stop detail with upcoming arrivals |
| `/trip-planner` | Origin / destination, date, departure time, preference radios (fastest / cheapest / fewest transfers); save trip; saved trips with a sharing toggle |
| `/fares` | Zone / rider / pass-type fare calculator, fare tables, fare export |
| `/compare` | Route 1 vs Route 2 comparison table |
| `/login` | Sign-in form |

JSON endpoints under `/api/` cover routes, schedules, stops, nearby stops, trip planning, fares, compare, ranked/extremum routes, export and share.

## Interactions and macros

- Search stops by name or address: `search`
- Sort routes or stops: `sort_by_form`
- Export routes, stops or fares as CSV/JSON: `export`
- Turn sharing on or off for a saved trip: `share_by_form`
- Read timetables, fares, the fare calculator and route comparisons: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `transit-directions`.

## Data

- Tables: `transit_directions_routes_transit` (the bus routes the pages use),
  `transit_directions_stops`, `transit_directions_schedules`,
  `transit_directions_fares`, `transit_directions_trip_plans`,
  `transit_directions_users`, and `transit_directions_routes`.
- Fare zones are A (Lakeport city) and B (regional). Proximity search uses
  `helpers.geo.haversine`.
- A stop's "upcoming arrivals" are computed from the timetable and the server's
  current clock, so they change with the time of day.
- Login uses the shared `session["user_id"]`, so the global auto-login signs in
  user 1. Saved trips are stored in `trip_plans`.
