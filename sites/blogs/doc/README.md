# TumblrVibe Blogging Platform (`blogs`)

A Tumblr-style blogging platform with posts (articles, tips, stories,
tutorials), comments, tags, likes and reblogs. Users browse and filter the feed,
write posts, comment, follow authors, save posts and subscribe to tags.

- URL: `/sites/blogs/` (simulated domain `tumblevibe.com`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Post feed with search (`q`), From/To dates, Sort (Newest, Oldest, Popular) and pagination |
| `/category/<name>`, `/tag/<name>` | Feed narrowed to a category or tag |
| `/post/<id>` | Post with comments; Like, Reblog, Save, Follow Author, Subscribe to Tag, Share and Report |
| `/compose` | New-post form (title, body, category, tags) |
| `/report/<id>` | Report-a-post form |
| `/dashboard` | Saved posts, my posts, followed blogs and subscribed tags (login required) |
| `/login`, `/register` | Sign-in and sign-up forms |

JSON endpoints under `/api/` cover posts, search, categories, tags, comments,
authors and reports.

## Interactions and macros

- Search posts: `search`
- Filter by date range or category: `filter_by_date_range`, `filter_by_dropdown`
- Sort the feed: `sort_by_form`
- Write a post or a comment: `create_by_form`
- Follow an author, save a post, subscribe to a tag: `toggle_relationship`
- Share a post to another MiniWeb site: `share_by_form`
- Open posts and nav pages: `navigate_by_route`
- Read post content, authors and comments: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `blogs`.

## Data

- Tables: `blogs_posts`, `blogs_comments`, `blogs_users`, `blogs_reports`.
- Login uses `session["user_id"]`, so the global auto-login signs in user 1.
- Registering emits a `signup` event (password-vault entry and welcome email).
  Publishing a post sends a "Your post has been published" email to WebMail.
- Share uses the shared cross-site share dialog (`app/static/miniweb-share.js`).
