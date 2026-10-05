# City of Lakeport (`agency-portals`)

A `.gov`-style municipal services portal for the fictional city of Lakeport, WA.
Residents browse departments, services, permits, public records and
announcements, and (signed in) apply for services, book appointments, pay city
bills and upload documents.

- URL: `/sites/agency-portals/` (simulated domain `lakeport.gov`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Home: service search, quick access, announcements |
| `/departments`, `/department/<id>` | Department directory and detail |
| `/services`, `/service/<id>` | Service catalog (category/department filters) and detail |
| `/permits`, `/permit/<id>` | Permit list (status, type, date filters) and detail |
| `/records` | Public records table (type and date-range filters) |
| `/announcements` | City announcements |
| `/dashboard` | My Account: saved services, applications, permits with review-stage buttons |
| `/apply/<service_id>` | Service / permit application form |
| `/book` | Schedule an appointment |
| `/pay` | Pay a city bill online |
| `/upload` | Upload a supporting document |
| `/verify-identity` | Enter the verification code sent at registration |
| `/login`, `/register` | Sign-in and registration |

JSON endpoints under `/api/` mirror the pages (services and permit search, records, stats, export, user actions).

## Interactions and macros

- Search services from the home page: `search`
- Filter services, permits and records by dropdowns: `filter_by_dropdown`
- Filter records or permits by date: `filter_by_date_range`
- Register, apply for a service or permit: `create_by_form`
- Book an appointment: `book_by_form`
- Pay a city bill: `pay_by_form`
- Upload a document: `upload_file`
- Sign in: `authenticate_by_form`
- Open departments, services and permits; read tables and details: `navigate_by_route`, `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `agency-portals`.

## Data

- Tables: `agency_portals_departments`, `agency_portals_services`,
  `agency_portals_permits`, `agency_portals_records`,
  `agency_portals_announcements`, `agency_portals_appointment_types`,
  `agency_portals_payment_types`, `agency_portals_users`.
- Login uses the shared `session["user_id"]`, so the global auto-login signs in user 1.
- Registration emails a `VRF-…` verification code to WebMail and emits
  `signup` (password-vault entry). Booking emits `booking` (calendar event +
  email); paying emits `payment` (banking debit). Applications send a
  confirmation email.
- A resident permit moves Submitted → Under Review → Approved/Denied one step
  at a time from the dashboard.
- `generate_data.py` holds the synthetic-data generator for the site's tables.
