# Scholar Search (`academic-paper-db`)

An academic paper search engine over arXiv metadata, modeled on Google Scholar,
Semantic Scholar and arXiv.org. Users search and browse papers, open paper and
author pages, compare two papers side by side, and keep a library of saved
papers and followed authors.

- URL: `/sites/academic-paper-db/` (simulated domain `scholarbase.edu`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Search results (`q`), with Sort and "Since <year>" dropdowns and category filters |
| `/paper/<id>` | Paper detail: abstract, metadata, authors, Save and Follow Author buttons |
| `/author/<name>` | Author profile with publications and stats, Follow/Unfollow |
| `/category/<name>` | Papers in an arXiv category, with a "Compute paper count" dropdown |
| `/compare` | Two paper dropdowns and a side-by-side comparison table (`?ids=a,b`) |
| `/dashboard` | My Library: saved papers and followed authors (login required) |
| `/login` | Sign-in form |

JSON endpoints under `/api/` cover papers, keyword and semantic search,
categories, stats, compare and export (`/api/export?format=`).

## Interactions and macros

- Search papers by keyword: `search`
- Sort results by date, title or relevance: `sort_by_form`
- Filter results by year: `filter_by_dropdown`
- Open a paper, an author or a category: `navigate_by_route`
- Save/unsave a paper, follow/unfollow an author: `toggle_relationship`
- Sign in: `authenticate_by_form`
- Read paper metadata, author publications, compare table, category counts: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `academic-paper-db`.

## Data

- Source: arXiv bulk metadata snapshot (public Kaggle/arXiv dataset), sampled.
- Tables: `academic_paper_db_papers`, `academic_paper_db_users`.
- Login uses `session["user_id"]`, so the global auto-login signs in user 1.
- Signing in emits a `signup` event (password-vault entry and welcome email).
  Saving a paper sends a "Paper saved" email to the WebMail inbox.
- Citation counts shown on papers are synthetic and deterministic per paper.
