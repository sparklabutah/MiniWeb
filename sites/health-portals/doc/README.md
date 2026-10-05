# Lakeport Medical Center Patient Portal (`health-portals`)

A MyChart-style patient portal for Lakeport Medical Center. Patients manage
appointments, read medical records (vitals, labs, diagnoses), message their
care team, request prescription refills, pay bills and e-sign consent forms.

- URL: `/sites/health-portals/` (simulated domain `lakeportmedical.org`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Dashboard, including "forms awaiting signature" notices |
| `/appointments`, `/appointment/<id>` | Appointments (status, provider, department, From/To filters) and detail |
| `/schedule` | Schedule an appointment (provider, type, date, time) |
| `/appointment/<id>/cancel` | Cancellation form with reason |
| `/records`, `/record/<id>` | Medical records with keyword and "Smart Search"; record detail with vitals and labs |
| `/messages`, `/message/<id>`, `/compose` | Inbox, thread view, and "Send Message" with a document upload |
| `/prescriptions` | Prescriptions with "Request Refill" |
| `/billing`, `/billing/<id>/pay` | Billing table with CSV/JSON export; card payment form |
| `/forms/<form_id>/sign` | Consent form with Draw / Type signature tabs |
| `/register`, `/verify`, `/login` | Registration, 6-digit code verification, sign-in |

JSON endpoints under `/api/` mirror these (appointments, records, messages, prescriptions, billing, search, export, documents, users).

## Interactions and macros

- Search records by keyword or natural language: `search`
- Filter appointments by date: `filter_by_date_range`
- Open appointments, records and messages: `navigate_by_route`
- Schedule an appointment: `book_by_form`, `create_by_form`
- Register or request a refill: `create_by_form`
- Cancel an appointment: `cancel_by_form`
- Message the care team and attach a document: `message_from_free_text`, `upload_file`
- Pay a bill; export billing: `pay_by_form`, `export`
- Sign a consent form by drawing or typing: `sign_by_freeformdrawing`, `sign_by_text`
- Sign in: `authenticate_by_form`
- Read appointments, records, lab results and bills: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `health-portals`.

## Data

- Tables: `health_portals_users`, `health_portals_appointments`,
  `health_portals_medical_records`, `health_portals_messages`,
  `health_portals_prescriptions`, `health_portals_billing`.
- Auth (`helpers.auth`) checks `session["health_user_id"]` first, then the
  shared `user_id`, so the global auto-login signs in user 1. Logged-out
  visitors browse as user 1.
- Bill payment validates the card with `app/bank_charges.charge_card` and emits
  `payment` (banking debit). Scheduling adds a calendar event and email
  (`on_booking`). Registration emits `signup`.
- The registration code is generated in memory and shown on `/verify`; it is
  not emailed.
