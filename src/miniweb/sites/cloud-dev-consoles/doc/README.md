# CloudCore Console (`cloud-dev-consoles`)

An AWS/GCP-style cloud management console. Users browse services, launch,
edit, power-cycle and terminate instances, provision functions, databases,
storage buckets and IAM users, and inspect billing, metrics, logs, alerts and
API gateway endpoints.

- URL: `/sites/cloud-dev-consoles/` (simulated domain `meridiancloud.dev`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Console Home: summary cards, live metrics, log stream, alerts, global search box, CSV export |
| `/search` | Global search results grouped by resource type |
| `/services`, `/service/<id>` | Service catalog with filters; service detail and endpoints |
| `/instances`, `/instance/<id>` | Instance table (search, status/region/sort dropdowns, environment checkboxes, launch form); detail with start/stop/reboot, Edit Configuration and delete |
| `/functions`, `/databases`, `/storage`, `/iam` | Resource tables with filters, sort and a create form each |
| `/billing` | Billing table with month and category filters |
| `/metrics` | Metrics table with an instance filter and a CPU-threshold slider |
| `/logs` | Log search with level/category dropdowns and a date range |
| `/alerts` | Alerts with status/severity/category filters, create, acknowledge, resolve, delete |
| `/api-gateway` | API endpoints table |
| `/dashboard` | User profile, preferences, recently viewed services, saved queries |
| `/login` | Sign-in form |

JSON endpoints under `/api/` mirror every resource type plus search, stats and
export (`/api/export?format=csv&resource=`).

## Interactions and macros

- Search a list page or the whole console: `search`
- Filter by status, region, engine, runtime, role, month and so on: `filter_by_dropdown`
- Filter instances by environment checkboxes: `filter_by_options`
- Filter logs by date range: `filter_by_date_range`
- Sort any resource list: `sort_by_form`
- Launch an instance, create a function, database, bucket or IAM user: `create_by_form`
- Edit an instance configuration: `edit_by_form`
- Terminate an instance: `delete_from_table`
- Set the CPU threshold slider on Metrics: `compute_by_tool`
- Read resource, billing, metrics and log tables: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `cloud-dev-consoles`.

## Data

- Tables (`cloud_dev_consoles_*`): `services`, `instances`, `functions`,
  `databases`, `storage_buckets`, `iam_users`, `billing`, `metrics`, `logs`,
  `alerts`, `api_endpoints`, `users`. Every collection is small.
- Login uses `session["user_id"]`, so the global auto-login signs in user 1.
- Signing in emits a `signup` event (password-vault entry and welcome email).
  Creating an alert sends a notification email to WebMail.
