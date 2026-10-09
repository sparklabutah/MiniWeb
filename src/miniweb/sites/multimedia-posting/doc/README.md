# PixShare (`multimedia-posting`)

An Instagram/Twitter-style social network for photo, video and carousel posts.
It has a feed of followed accounts, an explore page, stories, profiles, direct
messages and the usual social actions (like, save, follow, block, share).

- URL: `/sites/multimedia-posting/` (simulated domain `pixshare.social`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Feed of posts from followed users |
| `/explore` | All posts with search, type chips (Photos, Videos, Carousels), tag filter and sort |
| `/post/<post_id>` | Post detail: media (videos use the shared mini-player), comments, like, save, share, more-actions menu (delete, block, report) |
| `/profile/<user_id>` | Profile with posts and a Follow/Unfollow button |
| `/stories` | Stories carousel with playback and prev/next |
| `/create` | New post: type, caption, tags, location, file upload |
| `/messages`, `/messages/<other_id>` | DM inbox and conversation thread with reply box |
| `/settings` | Dark mode, notification and privacy toggles; data export (JSON/CSV) |
| `/login` | Sign-in form |

JSON endpoints under `/api/` cover posts, comments, likes, saves, shares,
follows, blocks, subscriptions, stories, messages, uploads, search and export.

## Interactions and macros

- Create a post or comment: `create_by_form` (with `upload_file` for media)
- Edit a post's caption, tags or location: `edit_by_form`
- Delete your own post: `delete_from_table`
- Like a post: `feedback_by_react`
- Follow, save, block or toggle notifications: `toggle_relationship`
- Search, filter by type and sort the explore page: `search`, `filter_by_options`, `sort_by_form`
- Share a post (copy link or send as DM): `share_by_form`
- Play stories: `play_by_playback`
- Change settings, export your data: `configure_by_form`, `export`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `multimedia-posting`.

## Data

- Tables: `multimedia_posting_users`, `multimedia_posting_posts`,
  `multimedia_posting_comments`, `multimedia_posting_stories`,
  `multimedia_posting_follows`, `multimedia_posting_dm_messages`
  (`dm_messages` is created on first use if missing).
- Login reads `session["user_id"]`. User ids are strings (`mp-u-001`), so the
  global auto-login value `1` falls back to `mp-u-001`. This auth is bespoke on
  purpose; do not switch it to `helpers.auth`.
- Blocks, subscriptions and settings are kept in the Flask session
  (`blocked_users`, `subscribed_users`, `user_settings`), not in tables.
- The shared Share dialog (`miniweb-share.js`) can post a page from any site
  here. Logging in emits `signup` (password-vault entry and welcome email).
