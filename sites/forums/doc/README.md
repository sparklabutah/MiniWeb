# ForumHub (`forums`)

A Reddit-style discussion forum. Users browse communities (subreddits), read
and write posts and threaded comments, vote, save, share and report content,
follow or block users, join communities, send direct messages and moderate
the communities they run.

- URL: `/sites/forums/` (simulated domain `lakeforum.com`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Feed with Hot/New/Top tabs, subreddit dropdown, From/To date filters |
| `/r/<name>` | One community's posts, with join/leave |
| `/post/<id>` | Post and comment thread: vote, comment, edit, delete, save, share (copy link, crosspost), report |
| `/user/<username>` | Profile with posts, karma and Follow/Block buttons |
| `/submit` | Create a post (community, title, body) |
| `/search?q=` | Search results |
| `/messages` | Direct-message inbox and compose form |
| `/mod`, `/r/<name>/mod` | Moderator dashboard and per-community report queue |
| `/login`, `/register` | Sign-in and registration |

JSON endpoints under `/api/` cover posts, comments, votes, social actions, reports, moderation, messages and export.

## Interactions and macros

- Search posts: `search`
- Filter by subreddit or date range: `filter_by_dropdown`, `filter_by_date_range`
- Sort the feed (Hot, New, Top): `sort_by_form`
- Create a post or register: `create_by_form`
- Edit or delete your post: `edit_by_form`, `delete_from_table`
- Upvote or downvote posts and comments: `feedback_by_react`
- Save a post, follow or block a user: `toggle_relationship`
- Share a post (copy link, crosspost): `share_by_form`
- Send a direct message: `message_from_free_text`
- Read post threads, profiles and search results: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `forums`.

## Data

- Tables: `forums_posts`, `forums_comments`, `forums_users`,
  `forums_reddit_users`, `forums_subreddits`, plus `forums_reports` and
  `forums_moderators`, which the site creates on first use. The moderator
  table is seeded so user 1 moderates r/hiking, r/programming and r/boardgames.
- Content comes from Reddit-derived data with fixed, past timestamps.
- Login goes through `helpers.auth` on `session["user_id"]`, which holds the
  root user id. The global auto-login signs in as user 1, whose forum username
  is `cascadia_coder`.
- Direct messages use the `messages` collection (`forums_messages`), which is
  defined in `schema.py` but missing from the current database. Until that
  table is seeded, the inbox is empty and sent messages are not kept.
- Sending a message emits `message`, which mirrors it to instant messaging.
  Registering emits `signup` (password-vault entry and welcome email).
