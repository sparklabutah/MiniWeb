# Spreadsheets & Slides (SheetDeck)

**Category**: Editing
**Reviewer**: Reaz
**Number of macros**: 16

## Data Source

JSON files served from `data_sources/spreadsheets-slides/`:
- `spreadsheets.json` — 15 spreadsheets with grid data (budget reports, sprint metrics, employee directory, sales pipeline, etc.)
- `presentations.json` — 10 presentations with slides (all-hands, roadmaps, onboarding, sales strategy, etc.)
- `templates_ss.json` — 6 templates (spreadsheet and presentation)
- `users.json` — 5 users with roles at a fictional company (Meridian Systems)

### Data Format

**Spreadsheets**: Each object has `id`, `title`, `owner_id`, `created_at`, `updated_at`, `shared_with` (list of user IDs), `rows`, `cols`, and `sheets` (list of `{name, data}` where `data` is a 2D array of strings; row 0 is the header).

**Presentations**: Each object has `id`, `title`, `owner_id`, `created_at`, `updated_at`, `shared_with`, `slides_count`, and `slides` (list of `{title, content, notes}`).

**Users**: `id`, `username`, `name`, `email`, `password`, `avatar_color`, `role`.

**Templates**: `id`, `name`, `type` (spreadsheet|presentation), `category`, `description`.

## Real-World Model

**Google Sheets / Google Slides** — cloud-based productivity suite. Key UI elements:
- Dashboard file list with type icons, sort/filter controls
- Sidebar for navigation (All Files, Spreadsheets, Presentations, Shared, Templates)
- Spreadsheet editor with cell grid, sheet tabs, cell references (A1 notation)
- Presentation editor with slide panels
- Sharing and collaboration features
- Export as CSV/JSON

## Target Macros

navigate_by_semantic, navigate_from_table, navigate_by_route, extract_by_code, extract_from_table, extract_by_slider, compute_by_query, compute_by_extremum, compute_by_slider, create_from_free_text, submit_from_table, edit_by_query, edit_by_form, delete_from_table, select_from_table, export_by_dropdown

## Temporal Dynamics

Not applicable. Spreadsheets and presentations are user-created documents with no time-varying simulation needed. Data is a static snapshot of workplace documents.

## Domain-Specific Notes

- Cell references use spreadsheet notation: A1, B3, AA10, etc. Range notation: A1:C5
- Numeric computations: sum, avg, count, min, max, median on columns (skip header row)
- Threshold filtering: filter rows by numeric column with min/max bounds
- Extremum finding: find the row with min/max value in a column
- Batch cell updates: form-based (cell_<row>_<col>=value) and API-based (JSON array of updates)
- Export supports CSV (with proper escaping) and JSON (header row becomes keys)
