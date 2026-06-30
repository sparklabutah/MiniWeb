# Lakeport Real Estate - Site Description

## Domain & Purpose
A Zillow/Redfin-style residential real estate platform for the fictional city of Lakeport, WA. Users can browse, search, and filter property listings for sale or rent. Registered users can save listings, send inquiries to agents, and view market statistics.

## Target Audience
- Homebuyers searching for properties to purchase
- Renters looking for apartments, condos, or houses to rent
- Landlords and investors browsing comparable properties
- Real estate agents managing listings

## Data Model
- **listings.json**: 30 properties (houses, condos, apartments, townhouses) with status (for_sale, for_rent, sold, rented), pricing, bed/bath counts, sqft, features, and agent assignments
- **agents.json**: 8 real estate agents across 3 agencies with contact info and ratings
- **users.json**: 5 registered users (buyers, renters, landlord, investor) with credentials (all password: pass123)
- **saved.json**: 10 saved listings across users with notes
- **inquiries.json**: 10 user inquiries to agents about specific listings

## Real-World Model
Modeled after Zillow.com with simplified UI: search bar with filters on the listings page, property detail pages with agent info, save/inquiry functionality, and an agents directory.

## Temporal/Dynamic Data
No temporal simulation required. Listings are static snapshots. User-generated data (saved, inquiries) is mutable.

## Key Routes
- `/` - Homepage with featured listings and market stats
- `/listings` - Search & filter listings (query, type dropdown, status dropdown, price slider range, beds/baths, sqft, sort)
- `/listing/<id>` - Property detail with save toggle, inquiry form, related listings
- `/agents` - Agents directory
- `/agent/<id>` - Agent profile with their listings
- `/saved` - User's saved listings (requires login)
- `/inquiries` - User's sent inquiries (requires login)
- `/api/listings` - JSON API with full filter/sort support
- `/api/stats` - Market statistics

## UI Affordances for Macros
- **navigate_by_dropdown**: Property type dropdown in nav bar links to filtered views
- **navigate_by_route**: Direct URL navigation to listing/agent detail pages
- **search_by_query**: Text search bar on listings page
- **search_by_semantic**: Keyword search matching against title, description, features
- **search_by_proximity**: Filter by city/zip (all Lakeport, but address-based proximity via API)
- **filter_by_query**: Text-based filtering combined with search
- **filter_by_dropdown**: Property type and status dropdowns
- **filter_by_checkbox**: Feature checkboxes (pet-friendly, parking, etc.)
- **filter_by_slider**: Price range min/max inputs
- **sort_by_ranking**: Sort dropdown (price low/high, date, sqft, beds)
- **extract_by_dropdown**: Stats by property type via API
- **extract_from_table**: Property details table on detail page
- **extract_by_route**: Direct API access to listing/agent data
- **extract_by_ranking**: First/last items from sorted results
- **extract_by_extremum**: Most/least expensive listing
- **compute_by_slider**: Price per sqft calculation
- **compare_by_dropdown**: Compare listings by type/status categories
- **submit_by_query**: Submit inquiry message about a listing
- **select_by_ranking**: Select Nth listing from sorted results
- **select_by_extremum**: Select cheapest/most expensive listing
- **follow_by_toggle**: Save/unsave listing toggle
- **save_by_toggle**: Save/unsave listing toggle (alias)
- **apply_by_form**: Submit inquiry form with message
- **book_by_form**: Schedule viewing via inquiry form
- **route_by_query**: Navigate to specific listing via search
