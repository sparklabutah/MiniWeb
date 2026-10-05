# FormFlow (`forms-surveys`)

A Google Forms / SurveyMonkey-style form builder. Users create forms from
scratch or from templates, fill them in, review results and analytics, edit
responses in a grid, attach files and share links.

- URL: `/sites/forms-surveys/` (simulated domain `formstack.io`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Form cards with search, status tabs (All, Active, Drafts, Closed), Share and Delete per card |
| `/form/<id>` | Form detail: fields, response count, status buttons (draft/active/closed), attachments upload, link to the grid |
| `/form/<id>/respond` | Fill in a form (text, radio, checkbox, dropdown, slider, ranking fields) |
| `/form/<id>/success` | Confirmation shown after a response is submitted |
| `/form/<id>/results` | Per-field statistics with Summary and Individual tabs |
| `/form/<id>/grid` | Spreadsheet-style response grid: edit cells, add rows, save |
| `/create`, `/form/<id>/edit` | Form builder (title, description, field rows, options) |
| `/templates` | Template gallery for quick starts |
| `/login` | Sign-in form |

JSON endpoints under `/api/` cover forms, responses, search, stats, share,
attachments and CSV/JSON export.

## Interactions and macros

- Build a form, or fill in and submit a response: `create_by_form`
- Change a form in the builder: `edit_by_form`
- Edit response cells in the grid: `edit_by_cell`
- Delete a form from its card: `delete_from_table`
- Copy a form's share link: `share_by_form`
- Attach a file to a form: `upload_file`
- Open forms and quick-start cards: `navigate_by_route`
- Read form lists, response counts and results statistics: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `forms-surveys`.

## Data

- Tables: `forms_surveys_forms`, `forms_surveys_responses`,
  `forms_surveys_templates_forms`, `forms_surveys_users`.
- Login uses `session["user_id"]`, so the global auto-login signs in user 1.
- If a Pew Research Center survey ZIP exists at
  `$MINIWEB_DATA_SOURCES/pew-research-survey`, its surveys are merged in
  read-only as forms with ids 100 and up. Without it, only the database forms appear.
- Submitting a response sends a WebMail confirmation. Logging in emits `signup`
  (password-vault entry and welcome email). The `form_*` and `grid_edit` events
  are recorded in the event log only.
