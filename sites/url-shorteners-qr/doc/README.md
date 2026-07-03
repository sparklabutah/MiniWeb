# URL Shorteners / QR

**Category**: Utilities
**Reviewer**: Kenny
**Number of macros**: 13

## Data Source

Synthetic seed data modeled after Bitly/TinyURL link management.
Files: `data_sources/url-shorteners-qr/links.json`, `click_stats.json`, `users.json`

### Data Format

**users.json** -- JSON array. Each user has: `id`, `username`, `password`, `name`, `email`, `plan` (free/pro/enterprise).

**links.json** -- JSON array. Each link has: `id`, `short_code`, `original_url`, `title`, `owner_id`, `created_at`, `clicks`, `is_active`, `expires_at`, `redirect_type` (301/302/307), `tags` (array), `qr_enabled` (bool), `utm_source`, `utm_medium`, `utm_campaign`.

**click_stats.json** -- JSON array. Each click event: `id`, `link_id`, `timestamp`, `referrer`, `country`, `device`.

### Sampling

All records loaded by default (`num_data_points: -1`). 4 users, 12 links, 30 click events in seed data.

## Real-World Model

**Bitly / TinyURL / Rebrandly** -- URL shortener with analytics dashboard. Key UI elements:
- URL creation form with custom short code, expiration, redirect type dropdown, QR toggle
- My Links list with search, status filter, date range filter, tag filter, sort options
- Link detail page with click statistics table (countries, devices, referrers)
- Export (CSV/JSON), share (email/twitter/linkedin/copy/qr), configure (redirect type, UTM params)

## Target Macros

navigate_by_query, navigate_by_route, search_by_query, filter_by_date_range, extract_by_query, extract_from_table, edit_by_query, delete_from_table, configure_by_dropdown, export_by_dropdown, share_by_dropdown, create_by_query, create_from_free_text

## Temporal Dynamics

Not applicable -- URL shortener data is user-generated and static between interactions. No temporal simulation needed.

## Domain-Specific Notes

- Short codes are alphanumeric, 6 chars generated or user-specified custom codes
- Links can be active/inactive (toggled) and have optional expiration dates
- Click tracking records country, device, and referrer per click event
- QR code generation is a per-link toggle (create_by_toggle)
- Export supports CSV and JSON formats (export_by_dropdown)
- Share generates platform-specific URLs for email, Twitter, LinkedIn, or copy-to-clipboard (share_by_dropdown)
- Configure allows changing redirect type (301/302/307) and UTM parameters (configure_by_dropdown)
