# MiniWeb — Changes for Annotators

_Last updated: 2026-08-12_

This note summarizes recent changes that affect how you **design and tag tasks**. New
macros, new site features you can build tasks around, annotation-UI changes, and
grading fixes. Read the top three sections; the rest is reference.

---

## 1. New macros you can tag

| Macro | Group | What it is | Aliases |
|---|---|---|---|
| **`edit_by_cell`** | content | Enter or change data directly in a grid/table **cell** (incl. adding a row to extend the table). Span: focus a cell → value committed (save/autosave). | `extend_table`, `edit_by_grid`, `add_by_row` |
| **`sign_by_text`** | content | Sign a document by **typing** your full legal name (adopt a typed signature). | `sign_by_typed_name` |

**`sign_by_freeformdrawing` changed** — it is now a realistic DocuSign-style single
**"Sign here"** field where you *draw* your signature and click **Adopt and Sign**.
The old "hidden detector zones" mechanic is gone; there are no zones to hit anymore.
Use `sign_by_freeformdrawing` when the intended path is **drawing**, `sign_by_text`
when it's **typing**.

## 2. New reasoning operation: `spatial`

A 7th reasoning op (alongside read / extremum / count / compute / compare / verify):

- **`spatial`** — reason about **WHERE** something is: locate/position by region,
  proximity, or coordinates (pan/zoom to reveal off-screen info, pick the item
  closest to a point, sign/draw in the correct field, scrub to a timestamp).
  Graded on the agent acting at the correct location/region, not just the right value.

## 3. New site features to build tasks around

### Inline-editable grids (`edit_by_cell`) — now on 8 sites
Each has a table where you click a cell, type a value, and Save (and a "+ Add row"):

| Site (brand) | Where |
|---|---|
| SheetDeck (spreadsheets-slides) | the spreadsheet cell grid |
| EduPortal LMS (course-sites-classrooms) | course **gradebook** (students × assignments) |
| Meridian State University (university-academic) | course **gradebook** |
| Meridian Tracker (project-mgmt-issue-tracking) | the **Backlog** issues table |
| SalesPro CRM (crm) | the **Contacts** table |
| DocEdit (documents) | an in-document **data table** |
| FitTrack (health-fitness-tracking) | the **Daily Log** editor |
| FormFlow (forms-surveys) | the **response** grid |

### File a tax return (`create_by_form` + `compute` op)
**Lakeport Government Services** (tax-filing) → **Tax Filings → "File a Form 1040"**:
fill the income lines and enter **Line 9 = Total income** (the sum of lines 1–8). Good
for `create_by_form.compute` (recompute the total) or `.verify` (transcribe a W-2 value).

### Document signing (`sign_by_freeformdrawing` / `sign_by_text`)
Signing is now realistic and gradeable on **three sites**. Documents that need signing
are **surfaced up front** (a banner, or notifications), and the signer offers **both
"Draw" and "Type"** tabs:

- **Lakeport Government Services** (tax-filing): **every newly-filed form requires a
  signature** — filing a 1040 takes you straight to the Sign page; a front-page alert
  lists documents awaiting signature.
- **Cascadia Insurance & Lending** (insurance-loans): **every new policy and new loan**
  is created "awaiting signature"; front-page banner + "Sign now" on the detail page.
- **Lakeport Medical Center** (health-portals): the patient has **2 pending consent
  forms shown as notifications**; signing one clears its notification (2 → 1 → 0).

## 4. Annotation interface changes

- **Site labels show the site TYPE.** Sampled-site chips and the single-site dropdown
  now read **"Brand Name (Site Type)"** — e.g. `Lakeport Government Services (Tax Filing,
  DMV & Permits)`, `EduPortal LMS (Course Sites & Classrooms)`. The single-site dropdown
  also shows coverage as `— covered/total`.
- **Reasoning-op reference.** Next to each macro's reasoning-op dropdown there's an
  **"ⓘ ops guide"** button (and a "what do these mean?" link in the help panel) that
  opens a reference listing every op, its meaning, and how it's graded.
- **More design-warning popups.** When you add a macro that has a known gotcha, a
  **"Design notes"** popup appears. Newly covered: `authenticate_by_form` (start
  **logged out** — turn off auto-login), `toggle_relationship` (act on the **right**
  target), `navigate_by_route`, `feedback_by_star` (specify the **exact** rating),
  `report_information` (place **last**; report a specific, gradeable value), and both
  sign macros (make it **obvious** the document needs signing). Plus the existing
  spatial macros.
- **Macro CSV has a `warning` column.** The Macro Template Builder download (and
  `docs/refined_macro_set.csv`) now includes each macro's design warning; reasoning-op
  rows carry their grading `check`.

## 5. MiniWeb portal search is realistic

On the MiniWeb home page you can now search by **brand name** *or* by **what a site
does / what you want to do** — e.g. `spreadsheet`, `edit a spreadsheet`, `file my
taxes`, `book a flight`, `send an email`, `find a job` all resolve to the right site.

## Action needed (re-record)

- **`spreadsheets-slides_facc7a`** ("add a new row") — its gold recording used the old
  add-row form. Please **re-record on the new grid UI and re-tag `create_by_form` →
  `edit_by_cell`**. (The old form still works, so gold isn't broken, but the tag and
  recording should move to the realistic flow.)

## Quick tagging reminders

- **Signing:** draw → `sign_by_freeformdrawing`, type → `sign_by_text`. Design so the
  document clearly **needs** signing.
- **Grid edits:** cell edit / add-row → `edit_by_cell` on the sites in §3.
- **Location tasks** (pan/zoom, proximity, sign-in-the-right-field, scrub-to-timestamp):
  set the reasoning op to **`spatial`**.
