# Lakeport Government Services (`tax-filing-dmv-permits`)

A state/city services portal combining tax filing, motor-vehicle (DMV)
records, permits, payments and appointments, in the style of IRS and DMV
online services. Users file a Form 1040, sign it, register vehicles, apply
for permits, pay fees, book DMV appointments and track refunds.

- URL: `/sites/tax-filing-dmv-permits/` (simulated domain `lakeportgov.org`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Dashboard: recent filings (with per-filing notes), permits, stats, awaiting-signature alert, Export Your Data bar |
| `/tax-filings`, `/tax-filing/<id>` | Filings with year/type/status filters; filing detail |
| `/file-1040` | Form 1040 income return (filing status, income lines 1-8, line 9 total) |
| `/sign-document/<id>` | DocuSign-style signing page for a filing (draw or type) |
| `/wheres-my-refund` | Income-tax returns with refund or amount due |
| `/vehicles`, `/vehicle/<id>`, `/register-vehicle` | Vehicles with filters; vehicle detail; registration form |
| `/permits`, `/permit/<id>`, `/apply-permit` | Permits with type/status and date-range filters; detail; application with document upload |
| `/payments`, `/make-payment` | Payment history with type filter; payment form |
| `/appointments`, `/my-appointments` | DMV appointment booking; the user's booked appointments |
| `/forms` | Downloadable government forms with a category filter (`/forms/<id>/pdf`) |
| `/search`, `/verify-identity`, `/login` | Search; identity code check; sign-in |

JSON endpoints under `/api/` cover filings, vehicles, permits, payments, uploads, appointments, identity verification, signing and export.

## Interactions and macros

- Search records: `search`
- Filter filings, vehicles, permits, payments or forms: `filter_by_dropdown`, `filter_by_date_range`
- File a 1040 (line 9 is computed from lines 1-8), apply for a permit, submit a payment: `create_by_form`, `pay_by_form`
- Attach supporting documents to a permit: `upload_file`
- Sign a filing by drawing or typing: `sign_by_freeformdrawing`, `sign_by_text`
- Book a DMV appointment: `book_by_form`
- Save a note on a filing: `edit_by_form`
- Export filings, vehicles, permits or payments as CSV/JSON: `export`
- Read filings, vehicles, permits and payments: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `tax-filing-dmv-permits`.

## Data

- Tables: `tax_filing_dmv_permits_tax_filings`, `_vehicles`, `_permits`,
  `_payments`, `_users`, and `_appointments` (created at runtime on first use).
- Login goes through `helpers.auth` on `session["user_id"]`, so the global
  auto-login signs in as user 1.
- Cross-site effects: a payment emits `payment` (banking debit to "City of
  Lakeport"), a booked appointment emits `booking` (calendar event and email),
  a filed or signed return emits `file_created` (cloud-storage file and email),
  and login emits `signup`.
