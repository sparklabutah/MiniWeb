# Project Homepages

**Category**: Static / informational
**Reviewer**: Minh
**Number of macros**: 10

## Data Source

https://huggingface.co/datasets/FrancisChen1/Paper2Web_bench

### Data Format

Three JSON files in `data_sources/project-homepages/`:

- **project.json** — Single JSON object with project metadata. Fields: `id`, `title`, `short_title`, `venue`, `year`, `status`, `doi`, `arxiv_id`, `authors` (array of {name, affiliation, email, corresponding, orcid}), `sections` (keyed by: abstract, motivation, method, results, citation, code_link, demo_link — each with title and content/content_summary), `keywords` (array of strings), `date_submitted`, `date_accepted`, `date_published`, `last_updated`.

- **resources.json** — JSON array of downloadable resources. Each: `id`, `type` (paper_pdf, slides, poster, code_repository, dataset, video, supplementary, blog_post), `title`, `url`, `format`, `size_mb`, `description`, `date_added`, optional `license` and `duration_minutes`.

- **users.json** — JSON array of team members. Each: `id`, `root_user_id`, `username`, `full_name`, `email`, `role`, `affiliation`, `department`.

## Real-World Model

**Academic project homepages** (e.g., projectpage.github.io, nerfies.github.io, institutional paper landing pages). Key UI elements:
- Hero section with paper title, authors, venue badge, and quick-access links
- Paper sections (abstract, motivation, method, results) with in-page or routed navigation
- Team member cards with profiles
- Resources/downloads list with type badges
- Citation display (BibTeX, APA) with copy functionality
- Search bar for project content
- Section navigation dropdown in the nav bar
- Export functionality for citations and project data
- Statistics page with data in HTML tables

## Target Macros

navigate_by_query, navigate_by_semantic, navigate_by_dropdown, navigate_by_route, search_by_query, extract_by_semantic, extract_by_dropdown, extract_from_table, extract_by_route, export_by_dropdown

### Macro Details

- **navigate_by_query**: Navigate to a page/section via query parameter (e.g., `/?section=team`)
- **navigate_by_semantic**: Find and navigate to content using semantic/keyword-overlap search (`/api/semantic?q=...`)
- **navigate_by_dropdown**: Use the section dropdown in the nav bar to jump to a paper section
- **navigate_by_route**: Click direct links (Paper, Team, Resources, Updates, Stats, section pages)
- **search_by_query**: Use the search bar to find content across all project data (`/search?q=...`, `/api/search?q=...`)
- **extract_by_semantic**: Extract information from semantic search results (`/api/semantic?q=...`)
- **extract_by_dropdown**: Extract resource statistics filtered by type dropdown (`/api/resources/stats?type=...`)
- **extract_from_table**: Read data from HTML tables on the stats page (overview, metrics, team, resources tables)
- **extract_by_route**: Get section content via direct API route (`/api/sections/<key>`)
- **export_by_dropdown**: Export project data by selecting a format from the export dropdown (bibtex, apa, json, csv via `/api/export?format=...`)

## Temporal Dynamics

Not applicable. Project homepages are static publications. No temporal simulation needed.

## Domain-Specific Notes

- This is a single-project homepage, not a multi-paper database
- All content revolves around one paper (FlowNet: Adaptive Workflow Optimization via RL)
- Navigation is between sections of the project rather than between papers
- The site has 7 navigable paper sections: abstract, motivation, method, results, citation, code_link, demo_link
- Resources span 8 types: paper_pdf, slides, poster, code_repository, dataset, video, supplementary, blog_post
- Updates are stored in session (mutable) with 4 default entries
- Team has 2 members (Alex Rivera and Aisha Patel)
