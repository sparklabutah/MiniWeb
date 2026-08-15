# Wikis (LakeportWiki)

**Category**: Search & reference
**Reviewer**: Minh
**Number of macros**: 13

## Data Source

Wikimedia-inspired synthetic data. A collaborative wiki encyclopedia covering a fictional city (Lakeport, WA), its people, landmarks, technology companies, and Pacific Northwest geography.

## Target Macros

navigate_by_query, navigate_by_dropdown, navigate_by_route, search_by_query, search_by_semantic, extract_by_query, extract_by_dropdown, extract_from_table, extract_by_route, compare_by_dropdown, verify_from_free_text, create_from_free_text, edit_by_dropdown

## Site Description

LakeportWiki is modeled after Wikipedia/MediaWiki. It is a multi-user collaborative encyclopedia with 30 articles across 8 categories. Users can browse, search, create, edit, and compare articles.

### Data files (in data_sources/wikis/)

- **pages.json** -- 30 wiki articles with title, slug, content (markdown-ish), category, author_id, dates, view counts, and linked_pages
- **categories.json** -- 8 categories (Lakeport City, Technology Companies, Landmarks & Places, PNW Geography, Notable People, Education, Culture & Events, Economy & Infrastructure) with page counts
- **revisions.json** -- 40 revision records tracking edit history (editor, timestamp, summary, diff stats)
- **users.json** -- 5 registered editors with credentials, roles, and edit counts

### Real-world model

Wikipedia / MediaWiki -- article pages with revision history, category navigation, search, side-by-side comparison.

### Temporal/dynamic behavior

Articles accumulate revisions over time. The data spans Feb 2024 to Jun 2026 of edits. No real-time simulation needed; the revision timeline is static but realistic.

### Key routes

| Route | Method | Purpose |
|---|---|---|
| `/` | GET | Main page with featured articles, categories, recent edits |
| `/wiki/<slug>` | GET | Article detail page |
| `/search?q=` | GET | Full-text search |
| `/category/<id>` | GET | Category listing |
| `/compare?page1=&page2=` | GET | Side-by-side comparison via dropdown |
| `/edit/<slug>` | GET/POST | Edit article (form with category dropdown) |
| `/create` | GET/POST | Create new article |
| `/recent-changes` | GET | Revision history feed |
| `/api/pages` | GET | API: list/filter/sort pages |
| `/api/pages/<slug>` | GET/PUT | API: get/update single page |
| `/api/pages` | POST | API: create page |
| `/api/search?q=` | GET | API: keyword search |
| `/api/semantic-search?q=` | GET | API: weighted relevance search |
| `/api/compare?slugs=a,b` | GET | API: compare two pages |
| `/api/verify` | POST | API: fact-check a claim against a page |
| `/api/categories` | GET | API: list categories |
| `/api/categories/<id>/pages` | GET | API: pages in a category |
| `/api/stats` | GET | API: aggregate statistics |
