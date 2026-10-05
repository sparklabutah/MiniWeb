# LakeportWiki (`wikis`)

A Wikipedia/MediaWiki-style encyclopedia about the fictional city of
Lakeport, WA and the Pacific Northwest, mixed with real Wikipedia articles.
Users read, search, compare, create and edit articles and browse revision
history, diffs and recent changes.

- URL: `/sites/wikis/` (simulated domain `lakeportwiki.org`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Main page: featured articles, categories, recent edits, search |
| `/wiki/<slug>` | Article with infobox, categories and revision history |
| `/wiki/<slug>/revision/<rev>`, `/wiki/<slug>/diff/<rev>` | One past revision; what that edit changed (with revert) |
| `/edit/<slug>` | Edit form: content, category dropdown, edit summary |
| `/create` | New article form (title, content, category) |
| `/category/<id>` | Articles in one category |
| `/recent-changes` | Revision feed (editor, timestamp, summary) |
| `/compare?page1=&page2=` | Two page dropdowns and a side-by-side comparison |
| `/search?q=` | Search results with snippets |
| `/login` | Sign-in form |

JSON endpoints under `/api/` cover pages, search, semantic search, compare, fact verification (`/api/verify`), categories and stats.

## Interactions and macros

- Search the wiki: `search`
- Open articles from the main page, categories and recent changes: `navigate_by_route`
- Create a new article: `create_by_form`
- Edit an article and its category: `edit_by_form`
- Read facts from articles and infoboxes, compare two pages, read revision history: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `wikis`.

## Data

- Tables: `wikis_articles` (real Wikipedia articles), `wikis_pages`
  (Lakeport pages layered on top), `wikis_categories`, `wikis_revisions`, `wikis_users`.
- Seeded revision timestamps are fixed past dates.
- Login reads `session["user_id"]`, so the global auto-login signs in as user 1.
- Edits and reverts emit `edit` (recorded in the event log only; no handler).
  Creating an article emits `file_created` (cloud-storage file and email).
  Login emits `signup`.
