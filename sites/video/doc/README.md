# Video

**Category**: Streaming & media
**Reviewer**: Reaz
**Number of macros**: 25

## Data Source

Synthesized dataset of 30 videos across 9 channels/users with 50 comments, 10 playlists, and 18 watch history entries.

Files in `data_sources/video/`:
- `videos.json` -- 30 video records
- `comments.json` -- 50 comment records (threaded via parent_comment_id)
- `users.json` -- 9 user/channel records
- `playlists.json` -- 10 playlists with video items
- `watch_history.json` -- 18 watch history entries

Additionally, `ratings.json` and `reports.json` are created dynamically when users rate or report videos.

### Data Format

**videos.json**: Array of objects with fields: id, title, channel_id, user_id, description, duration_seconds, views, likes, dislikes, upload_date, category, tags, thumbnail_url, video_url, status.

**comments.json**: Array of objects: id, video_id, user_id, username, display_name, text, timestamp, likes, parent_comment_id.

**users.json**: Array of objects: id, root_user_id, username, display_name, channel_name, email, avatar_url, subscriber_count, videos_count, joined_date, about, links, is_verified.

**playlists.json**: Array of objects: id, user_id, username, title, description, visibility, created_date, updated_date, items (array of {video_id, added_date, position}).

**watch_history.json**: Array of objects: id, user_id, video_id, video_title, channel_name, watched_at, progress_percent, duration_seconds.

## Real-World Model

**YouTube** -- the dominant video sharing platform. Key UI elements:
- Homepage with trending/recent video grid
- Video player page with comments, like/dislike, share, save, report
- Channel pages with subscriber counts and video listings
- Search with filters (category, duration, date, sort)
- Playlists (public and private)
- Watch history
- User settings/preferences (autoplay, quality, playback speed)
- Login/authentication

## Target Macros

navigate_by_dropdown, navigate_by_route, search_by_query, search_by_semantic, filter_by_dropdown, filter_by_slider, filter_by_date_range, sort_by_ranking, extract_by_query, submit_by_route, upload_by_upload, select_by_dropdown, configure_by_route, play_by_slider, play_by_date_range, play_by_playback, post_from_free_text, react_by_toggle, rate_by_slider, follow_by_toggle, subscribe_by_toggle, share_by_dropdown, save_by_toggle, report_by_form, authenticate_by_form

## Temporal Dynamics

Not applicable -- video platform data is event-driven (uploads, comments, views) rather than time-varying. No temporal simulation needed. Data is a static snapshot of video metadata and user interactions.

## Domain-Specific Notes

- Semantic search: multi-word keyword overlap scoring over titles, descriptions, tags, and channel names
- Categories: Travel & Outdoors, Education, Gaming, Food & Cooking, Sports, Science & Technology, Entertainment, Pets & Animals
- Video durations range from ~600s to ~2500s
- Authentication uses username/password matching against user records (password defaults to username if not set)
- Ratings are 1-5 stars, stored in a separate ratings.json
- Reports use predefined reason categories: spam, harassment, misinformation, copyright, inappropriate, violence, other
- Share supports platforms: link, twitter, facebook, reddit, email, embed
- Playback settings: speed (0.25x-2.0x), quality (144p-2160p)
