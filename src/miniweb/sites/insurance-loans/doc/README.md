# Cascadia Insurance & Lending (`insurance-loans`)

An insurance and lending customer portal in the style of Progressive or
SoFi. Users review policies, claims, loans and payments, file claims, buy a
policy or apply for a loan, sign the agreement, make payments and download
policy documents.

- URL: `/sites/insurance-loans/` (simulated domain `cascadiainsure.com`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Dashboard: policies (Export CSV), loans with a sort dropdown, claims, recent payments, awaiting-signature banner |
| `/policies`, `/policy/<id>` | Policies with type/status filters; policy detail with coverage and a settings/notifications card |
| `/policy/<id>/document` | Policy document rendered as a PDF-style page (download as PDF, save to files) |
| `/policies/new` | Quote-and-enroll form for a new policy |
| `/policy/<id>/sign`, `/loan/<id>/sign` | DocuSign-style signing page (draw or type a signature) |
| `/claims`, `/claim/<id>` | Claims with filters; claim detail with timeline, settlement offer, accept or appeal |
| `/file-claim` | Claim form with policy dropdown and document upload |
| `/loans`, `/loan/<id>` | Loans with filters; loan detail with amortization schedule |
| `/loans/apply` | Loan application |
| `/payments`, `/pay` | Payment history with filters; payment form |
| `/login` | Sign-in form |

JSON endpoints under `/api/` mirror policies, claims, loans and payments.

## Interactions and macros

- Filter policies, claims, loans or payments by type/status or date range: `filter_by_dropdown`, `filter_by_date_range`
- Sort loans on the dashboard: `sort_by_form`
- File a claim with an attached document: `create_by_form`, `upload_file`
- Change policy settings (autopay, paperless, alerts): `configure_by_form`, `edit_by_form`
- Make a payment: `pay_by_form`
- Sign a new policy or loan by drawing or typing a signature: `sign_by_freeformdrawing`, `sign_by_text`
- Export policies as CSV: `export`
- Read coverage, balances, schedules and claim status: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `insurance-loans`.

## Data

- Tables: `insurance_loans_policies`, `insurance_loans_claims`,
  `insurance_loans_loans`, `insurance_loans_payments`, `insurance_loans_users`.
- Login uses the site's own `session["il_user_id"]` (via `helpers.auth`). Read
  pages fall back to user 1 in browse-only mode; claim and signing actions
  need an explicit login.
- New policies and loans are issued `awaiting_signature` and take effect only
  after signing.
- Payments and accepted claim payouts go through the shared 2FA page
  (`/verify-payment`, code sent to WebMail) and then post to banking.
- "Save to files" emits `file_created` (cloud-storage entry and email). Login
  emits `signup`. `pdf.py` renders the policy PDF with reportlab.
