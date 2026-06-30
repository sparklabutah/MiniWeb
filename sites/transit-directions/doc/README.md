# Transit / Directions

**Category**: Maps & navigation
**Reviewer**: Kenny
**Number of macros**: 20

## Data Source

Synthetic transit data for the fictional Lakeport Transit Authority (LTA) serving Lakeport, WA and the surrounding region. Six JSON files in `data_sources/transit-directions/`:

- `routes_transit.json` -- 6 bus routes (local, express, circulator) with route numbers, colors, frequencies, travel times, fare zones
- `stops.json` -- 25 stops with lat/lng coordinates, stop codes, zones (A/B), amenities, routes served
- `schedules.json` -- Full timetables for routes 1, 2, and 6X with per-stop departure times
- `fares.json` -- Fare structure: 2 zones (A/B), 5 rider types, 4 pass types (single/day/monthly/annual), transfer policy, employer programs
- `trip_plans.json` -- 8 pre-saved trip plans across 3 users with detailed leg-by-leg itineraries
- `users.json` -- 3 demo users with home/work addresses and transit pass info

### Data Format

All files are JSON. Routes have numeric IDs and string route_numbers (e.g., "1", "6X"). Stops have lat/lng for proximity search. Schedules contain timetable arrays with per-stop time strings ("HH:MM" 24h format). Fares are nested by pass_type > zone > rider_type.

## Real-World Model

**Google Transit / TriMet / Metro Transit** -- clean, information-dense transit portal. Key UI elements:
- Homepage with quick trip planner and route overview cards
- Routes list with type filter (local/express/circulator) and sort options
- Route detail page with stops timeline, schedule timetable, and service info
- Stops search with name/zone/route filters and real-time arrival display
- Trip planner with origin/destination inputs, departure time, and route preference radio buttons (fastest/cheapest/fewest transfers)
- Fares page with zone/rider/pass dropdowns and fare comparison tables
- Route comparison page (side-by-side table)
- Stop detail page with upcoming arrivals and served routes
- Export and share functionality

## Target Macros

navigate_by_dropdown, search_by_query, search_by_proximity, route_by_query, route_by_radio, route_by_route, route_by_date_range, filter_by_radio, sort_by_dropdown, extract_by_query, extract_by_dropdown, extract_from_table, compute_by_dropdown, compute_by_extremum, compare_from_table, select_by_dropdown, select_by_ranking, select_by_extremum, export_by_dropdown, share_by_dropdown

## Temporal Dynamics

Semi-dynamic -- the stop detail page shows simulated "upcoming arrivals" based on the current time and schedule timetables. This provides time-varying data without requiring a full temporal simulation layer. The schedule data itself is static (like a published transit schedule).

## Domain-Specific Notes

- Trip planner builds route options algorithmically by finding common routes between origin/destination stops, plus transfer options via the Transit Center
- Routes have types: "local" (city routes), "express" (regional/inter-city), "circulator" (neighborhood loops)
- Fare zones: A (Lakeport city) and B (regional/Seattle express)
- Haversine distance calculation used for proximity-based stop search
- Route comparison allows side-by-side comparison of travel time, frequency, fare, and accessibility features
