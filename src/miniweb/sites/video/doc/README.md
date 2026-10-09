# StreamHub (`video`)

A YouTube-style video sharing platform. Users browse trending and latest
videos, search, filter by upload date, watch videos in the shared mini-player,
like, comment, save, share and report videos, subscribe to or follow channels,
manage playlists and upload new videos.

- URL: `/sites/video/` (simulated domain `streamtube.tv`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Video grid with sort chips (Trending, Latest, Popular, Most Liked), category chips, "Uploaded from/to" dates and "Play Newest in Range" |
| `/search` | Search results |
| `/watch/<id>` | Player (play reveals exact duration, quality and chapters), like / dislike, save, share, report, comments |
| `/channel/<id>` | Channel videos with Subscribe and Follow |
| `/playlists`, `/playlist/<id>` | Playlists and playlist detail |
| `/history` | Watch history |
| `/upload` | Upload form: file, title, description, category, visibility |
| `/settings` | Default quality, playback speed, autoplay and notifications |
| `/login` | Sign-in form |

JSON endpoints under `/api/` cover videos, likes, ratings, play/seek/playback, comments, channels, playlists, history, search and settings.

## Interactions and macros

- Search videos: `search`
- Sort the home grid; filter by upload date: `sort_by_form`, `filter_by_date_range`
- Open videos, channels and playlists: `navigate_by_route`
- Play a video: `play_by_playback`
- Like a video: `feedback_by_react`
- Comment on a video: `create_by_form`
- Upload a video, choosing category and visibility: `upload_file`, `create_by_form`, `filter_by_dropdown`
- Subscribe to or follow a channel, save a video: `toggle_relationship`
- Share a video to a platform: `share_by_form`
- Change playback settings: `configure_by_form`
- Read search results; sign in: `report_information`, `authenticate_by_form`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `video`.

## Data

- Tables: `video_videos`, `video_comments`, `video_playlists`,
  `video_watch_history`, `video_users`.
- Login uses the shared `session["user_id"]`, so the global auto-login signs in
  user 1. Logging in emits `signup` (password-vault entry + email).
- Ratings and reports are saved to `ratings` and `reports` collections that have
  no base table, so `db.query` cannot read them back. Graders see those writes
  only in the request log. Clicking "Report" also posts a placeholder report
  (reason `other`) as it opens the report form.
