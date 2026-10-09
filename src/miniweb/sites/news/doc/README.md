# Lakeport Tribune (`news`)

A local newspaper site for the fictional city of Lakeport in Cascadia County,
modeled on Patch.com and small-city news portals. Readers browse category
pages, search articles, listen to articles, comment, bookmark, share, follow
authors or categories, and report articles.

- URL: `/sites/news/` (simulated domain `lakeporttimes.com`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Front page with Featured Stories and the latest articles by category |
| `/category/<slug>` | Category page with sort (date, popularity), topic chips, From/To date filter and pagination |
| `/article/<id>` | Article: full text, author, tags, Listen to Article, Share, Bookmark, follow author or category, comments |
| `/article/<id>/report` | Report-an-article form |
| `/search` | Keyword search with a date filter, plus a "Smart Search" natural-language box |
| `/bookmarks` | The user's bookmarked articles |
| `/login`, `/register` | Sign-in and registration (with newsletter toggles) |

JSON endpoints under `/api/` cover articles, semantic search, categories,
bookmarks, comments and upvotes, follows, subscriptions, sharing, reports and
playback.

## Interactions and macros

- Search articles, including Smart Search: `search`
- Filter search or category results by date: `filter_by_date_range`
- Open articles from the front page or a category: `navigate_by_route`
- Comment on an article, register an account: `create_by_form`
- Sign in: `authenticate_by_form`
- Bookmark or unbookmark, follow, newsletter toggles: `toggle_relationship`
- Share an article to another MiniWeb site: `share_by_form`
- Listen to an article: `play_by_playback`
- Read article text, authors, dates and comments: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `news`.

## Data

- Tables: `news_articles`, `news_categories`, `news_users`, `news_bookmarks`,
  `news_comments`. The comments table is created and registered on first use
  if it is missing (`_ensure_comments_table`).
- Login reads `session["user_id"]`, so the global auto-login signs the user in
  as user 1. The login form accepts any existing username with the password
  `password`.
- Articles are a static, dated corpus and are never date-shifted.
- Posting a comment emits a `message` event (a notification in instant
  messaging). Logging in emits `signup`.
