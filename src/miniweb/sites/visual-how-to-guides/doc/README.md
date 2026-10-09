# StepVista How-To Guides (`visual-how-to-guides`)

A wikiHow / Instructables-style site of illustrated step-by-step guides
(home, cooking, tech and more). Users browse, filter and compare guides, step
through them one step at a time, rate and comment, bookmark guides and follow
authors.

- URL: `/sites/visual-how-to-guides/` (simulated domain `stepvista.com`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Featured and most-popular guides, search bar |
| `/guides` | Browse: category and difficulty dropdowns, difficulty slider, sort (rating, views, newest, duration) |
| `/guide/<id>` | Guide detail: steps, author, rating slider (1-5), comments with helpful/unhelpful toggles, Bookmark |
| `/guide/<id>/step/<n>` | Single-step playback view with Prev/Next |
| `/category/<category_id>` | Guides in one category |
| `/compare` | Side-by-side comparison of two guides chosen from dropdowns |
| `/authors`, `/author/<name>` | Author directory; author profile with Follow button |
| `/search` | Search results |
| `/create` | New guide form |
| `/bookmarks`, `/dashboard` | Bookmarked guides; dashboard with bookmarks, followed authors and ratings |
| `/login` | Sign-in form |

JSON endpoints under `/api/` cover guides, steps, categories, authors,
comments, ratings, bookmarks, compare and search.

## Interactions and macros

- Search guides by title, description or step text: `search`
- Filter by category or difficulty: `filter_by_dropdown`, `filter_by_slider`
- Sort the browse list: `sort_by_form`
- Rate a guide with the 1-5 slider: `feedback_by_star`
- Mark a comment helpful or unhelpful: `feedback_by_react`
- Bookmark a guide: `toggle_relationship`
- Open guides from home, category or author pages: `navigate_by_route`
- Read guide steps and the comparison table: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `visual-how-to-guides`.

## Data

- Tables: `visual_how_to_guides_guides` (steps stored per guide),
  `visual_how_to_guides_categories`, `visual_how_to_guides_comments`,
  `visual_how_to_guides_ratings`, `visual_how_to_guides_reactions`,
  `visual_how_to_guides_bookmarks`, `visual_how_to_guides_users`.
- Login reads `session["user_id"]` (via `helpers.auth`), so the global
  auto-login signs in user 1.
- Ratings and comment reactions are one per user per item; a guide's average
  rating is recomputed after each rating.
- Content is synthetic and static; the site has no cross-site effects.
