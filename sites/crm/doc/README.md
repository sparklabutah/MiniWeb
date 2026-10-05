# SalesPro CRM (`crm`)

A Salesforce/HubSpot-style CRM for a sales team: contacts, companies, a deal
pipeline, logged activities and a follow-up task queue.

- URL: `/sites/crm/` (simulated domain `salesflow.io`)
- Data split: held-out (test) site

## Pages

| Route | Page |
|---|---|
| `/` | Pipeline Overview dashboard: section cards, Sort Deals dropdown, Export CSV |
| `/contacts`, `/contact/<id>` | Contacts as an inline-editable grid (search, company filter, add row, delete); contact detail with deals and activities |
| `/companies`, `/company/<id>` | Companies table (search, industry filter, create form); company detail with contacts and deals |
| `/deals`, `/deal/<id>` | Deals list (search, stage and owner filters); deal detail with stage update, tasks and activity log |
| `/activities` | Activities table with type and From/To date filters, create-activity form |
| `/tasks` | Open follow-up tasks: create, complete, reopen |
| `/login` | Sign-in form |

JSON endpoints under `/api/` cover contacts, companies, deals, activities,
pipeline, stats and export.

## Interactions and macros

- Search contacts, companies or deals: `search`
- Filter by company, industry, stage, owner or activity type: `filter_by_dropdown`
- Filter activities by date: `filter_by_date_range`
- Sort deals on the dashboard: `sort_by_form`
- Log an activity: `create_by_form`
- Update a deal's stage or log activity on a deal: `edit_by_form`
- Edit contact cells inline and save: `edit_by_cell`
- Delete a contact: `delete_from_table`
- Export deals as CSV: `export`
- Read pipeline, contact, company and deal details: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `crm`.

## Data

- Tables: `crm_contacts`, `crm_companies`, `crm_deals`, `crm_activities`,
  `crm_tasks`, `crm_users`. `crm_tasks` is created on first use if missing.
- Login uses `session["user_id"]`, so the global auto-login signs in user 1.
- Cross-site effects: creating a deal sends a WebMail notice; moving a deal's
  stage sends an instant message; logging a meeting or call emits `booking`
  (a calendar event plus a confirmation email); logging in emits `signup`
  (password-vault entry and welcome email).
