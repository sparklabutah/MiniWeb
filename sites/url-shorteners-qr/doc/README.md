# SnapLink URL Shortener (`url-shorteners-qr`)

A Bitly, TinyURL or Rebrandly-style link manager. Users shorten URLs with
custom codes, expiry, tags, redirect types and QR codes, manage and export their
links, and read per-link click statistics.

- URL: `/sites/url-shorteners-qr/` (simulated domain `snplnk.io`)
- Data split: held-out (test) site

## Pages

| Route | Page |
|---|---|
| `/` | "Shorten a URL" form (long URL, title, custom short code, expiry, tags, redirect type 301/302/307, Generate QR Code) and recent links |
| `/links` | My Links: search, status filter, sort, From/To dates, tag filter, CSV/JSON export |
| `/link/<id>` | Link detail: click statistics (countries, devices, referrers), Edit Link card, activate/deactivate, Delete, Sharing toggle, View QR Code |
| `/qr/<id>` | QR code for the short link |
| `/login` | Sign-in form |

`/s/<short_code>` redirects to the original URL and records a click. JSON
endpoints under `/api/` cover links, configure, expiration, stats, stats
export, share, QR, resolve and export.

## Interactions and macros

- Create a short link: `create_by_form`
- Choose the redirect type, or status and sort on My Links: `configure_by_form`
- Search links, filter by creation date: `search`, `filter_by_date_range`
- Edit a link's title, destination or tags: `edit_by_form`
- Delete a link: `delete_from_table`
- Export links as CSV or JSON: `export`
- Turn sharing on to reveal the share URL and QR link: `share_by_form`
- Read click counts and statistics tables: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `url-shorteners-qr`.

## Data

- Tables: `url_shorteners_qr_links`, `url_shorteners_qr_click_stats`,
  `url_shorteners_qr_users`.
- Login reads `session["user_id"]` (via `helpers.auth`), so the global
  auto-login signs the user in as user 1.
- QR codes are real, scannable codes rendered as SVG by the dependency-free
  encoder in `sites/url-shorteners-qr/qr_encoder.py`.
- `/s/<short_code>` returns 404 for an inactive or unknown code. Codes that
  point at a MiniWeb path redirect there. External destinations are shown on an
  "External Link" page instead, because the sandbox does not leave MiniWeb.
