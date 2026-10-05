# SheetDeck (`spreadsheets-slides`)

A Google Sheets / Google Slides-style workspace for a fictional company
(Meridian Systems). Users browse files, edit spreadsheet cells in a grid, add
and reorder slides, share files and export them.

- URL: `/sites/spreadsheets-slides/` (simulated domain `sheetdeck.app`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | File dashboard: search, type and owner filters, sort, Delete per file card |
| `/spreadsheet/<sid>` | Spreadsheet editor: sheet tabs, editable cell grid (A1 references), Add row, Save Changes, Share, export (XLSX/CSV/JSON) |
| `/presentation/<pid>` | Presentation editor: slide list, edit slide, add, Move Up/Down, delete, export (PPTX/TXT/JSON) |
| `/create` | New spreadsheet or presentation form |
| `/shared` | Files shared with the current user |
| `/templates` | Template gallery |
| `/login` | Sign-in form |

JSON endpoints under `/api/` cover files, cells, ranges, rows, batch edits,
compute, extremum, filter, slides, export and templates.

## Interactions and macros

- Create a spreadsheet or presentation: `create_by_form`
- Edit cells in the grid and save: `edit_by_cell`, `edit_by_form`
- Reorder slides with Move Up/Move Down: `edit_by_ranking`
- Delete a file from the dashboard: `delete_from_table`
- Share a file (copy link or share with a user): `share_by_form`
- Export a spreadsheet or deck: `export`
- Open files from the dashboard or sidebar: `navigate_by_route`
- Read cell values and tables: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `spreadsheets-slides`.

## Data

- Tables: `spreadsheets_slides_spreadsheets` (sheets stored as 2D arrays, row 0
  is the header), `spreadsheets_slides_presentations`,
  `spreadsheets_slides_templates_ss`, `spreadsheets_slides_users`.
- Login uses `session["user_id"]`, so the global auto-login signs in user 1.
- XLSX export produces a real workbook with every sheet.
- Creating a file emits `file_created` (a copy appears in cloud storage and a
  notification email is sent). Logging in emits `signup` (password-vault entry
  and welcome email).
