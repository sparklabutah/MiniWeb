# DesignFlow (`design-creative`)

A Canva-style design tool. Users browse a template gallery, start projects from
templates, edit designs in a simplified canvas editor (positioned HTML elements,
not a real canvas), manage an asset library, invite collaborators and export
designs as SVG.

- URL: `/sites/design-creative/` (simulated domain `canvastudio.design`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Template gallery with search, category links and Sort (Most Popular, Name A-Z, Newest) |
| `/template/<id>` | Template detail with "Use This Template" and Favorite/Unfavorite |
| `/projects` | My Projects: create-project form, sort dropdown, duplicate |
| `/project/<id>` | Project detail: rename, status (draft/completed), duplicate, invite by email |
| `/editor/<id>` | Canvas editor: add text, rectangle, ellipse and image elements, drag/resize, edit properties, delete, export |
| `/project/<id>/export` | Downloads the project as an SVG |
| `/assets` | Asset library with search, upload and "use in a design" |
| `/login` | Sign-in form |

JSON endpoints under `/api/` cover templates, projects (including adding and
removing elements), assets, favorites, categories and stats.

## Interactions and macros

- Search templates or assets: `search`
- Pick a template category: `filter_by_options`
- Sort templates or projects: `sort_by_form`, `filter_by_dropdown`
- Create a project, use a template, invite a collaborator: `create_by_form`
- Rename a project or change its status: `edit_by_form`, `configure_by_form`
- Remove an element in the editor: `delete_from_table`
- Favorite a template: `toggle_relationship`, `feedback_by_react`
- Upload an asset: `upload_file`
- Open templates and projects: `navigate_by_route`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `design-creative`.

## Data

- Tables: `design_creative_templates` (read-only), `design_creative_projects`,
  `design_creative_assets`, `design_creative_users`.
- `sites/design-creative/seed_assets.py` seeds the stock asset library (inline
  SVG and `data:` URIs) into the base table; re-run it after a DB rebuild.
- Login uses `session["user_id"]` (via `helpers.auth`), so the global
  auto-login signs in user 1.
- Signing in emits a `signup` event. Creating a project or inviting a known user
  sends WebMail email. Marking a project completed or uploading an asset emits
  `file_created`, which syncs the file to cloud storage and sends an email.
