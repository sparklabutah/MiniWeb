# FlowNet Project Homepage (`project-homepages`)

An academic project landing page for the FlowNet paper (ICML 2025), in the style
of nerfies.github.io and other paper homepages. It shows the paper sections,
team, downloadable resources, news updates, statistics and citation export.

- URL: `/sites/project-homepages/` (simulated domain `flownet.dev`)
- Data split: training site
- Source data: modeled on the Paper2Web benchmark
  (https://huggingface.co/datasets/FrancisChen1/Paper2Web_bench)

## Pages

| Route | Page |
|---|---|
| `/` | Hero (title, authors, venue badge, quick links) with a section-navigation dropdown |
| `/paper` | Abstract, motivation, method and results |
| `/section/<section_key>` | One paper section |
| `/team` | Team member cards |
| `/resources`, `/resource/<id>` | Resource list with a type dropdown; resource detail and download (`/resource/<id>/download`) |
| `/updates` | Project news updates |
| `/stats` | Overview, metrics, team and resources tables |
| `/search` | Search across project content, ranked by relevance |
| `/export` | Export citations or project data (BibTeX, APA, JSON, CSV) |
| `/login` | Sign-in form |

JSON endpoints under `/api/` expose the project, team, resources, updates,
citations, stats, search, semantic search, sections and export.

## Interactions and macros

- Search project content: `search`
- Move between Paper, Team, Resources, Updates and Stats, or jump to a section: `navigate_by_route`
- Export a citation or project data in a chosen format: `export`
- Read section text, resource details and stats tables: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `project-homepages`.

## Data

- Tables: `project_homepages_project`, `project_homepages_resources`,
  `project_homepages_users` (team members).
- The site is mostly read-only. Login reads `session["user_id"]`, so the global
  auto-login shows user 1 (Alex Rivera, a FlowNet author) as signed in.
- Project updates start from a built-in list in `routes.py`. Updates added
  through `POST /api/updates` are kept in the Flask session, not in the
  database.
- Dates (submission, acceptance, updates in 2025) are static.
