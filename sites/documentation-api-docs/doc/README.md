# MeridianFlow Docs (`documentation-api-docs`)

A developer documentation site modeled after Stripe Docs, for the fictional
MeridianFlow workflow API. It has guides, an API reference with method badges,
a changelog, full-text search, and bookmarks for signed-in users.

- URL: `/sites/documentation-api-docs/` (simulated domain `devdocs.io`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Home: sidebar navigation by section, section cards, page list |
| `/page/<slug>` | Documentation page with code blocks (copy buttons) and a Bookmark button |
| `/api-reference` | API endpoint reference |
| `/search` | Search results (`?q=`) |
| `/changelog` | Version history |
| `/dashboard` | Bookmarked pages (login required) |
| `/login` | Sign-in form |

JSON endpoints under `/api/` cover docs, sections, endpoints, changelog,
search and bookmarks.

## Interactions and macros

- Search the docs from the header or the search page: `search`
- Open a page from the sidebar, the page list or the top nav: `navigate_by_route`
- Copy a code example with its copy button: `copy_content`
- Read parameters, endpoint docs and changelog entries: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `documentation-api-docs`.

## Data

- Tables: `documentation_api_docs_docs` (pages grouped by `section`: Getting
  Started, Guides, API Reference, Webhooks, SDKs, Changelog, ...),
  `documentation_api_docs_search_index`, `documentation_api_docs_users`.
- Login uses `session["user_id"]`, so the global auto-login signs in user 1.
- Content is static; the site has no cross-site effects.
