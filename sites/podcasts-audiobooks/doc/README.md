# Podcasts & Audiobooks

**Category**: Streaming & media
**Reviewer**: Reaz
**Number of macros**: 21

## Data Source

Synthetic data generated to resemble Spotify Podcasts / Audible catalog structure.
Files: `data_sources/podcasts-audiobooks/` (podcasts.json, episodes.json, audiobooks.json, users.json, library.json, reviews.json)

### Data Format

- `podcasts.json` — Array of podcast objects with id, title, host, description, category, rating, subscribers, episodes_count, language, cover_color, created_date
- `episodes.json` — Array of episode objects with id, podcast_id, episode_number, title, description, duration_minutes, publish_date, listens, liked_by
- `audiobooks.json` — Array of audiobook objects with id, title, author, narrator, description, genre, rating, price, duration_hours, chapters, publish_date, liked_by
- `users.json` — Array of user objects with id, username, password, display_name, bio, joined
- `library.json` — Array of per-user library objects with subscribed_podcasts, followed_podcasts, purchased_audiobooks, saved_episodes, listen_history, playback_speed, playlists
- `reviews.json` — Array of review objects with id, user_id, item_type (podcast/audiobook), item_id, rating, text, date

### Sampling

All data is loaded by default (num_data_points=-1). 12 podcasts, 82 episodes, 15 audiobooks, 5 users.

## Real-World Model

**Spotify Podcasts / Audible / Apple Podcasts** — dark-themed streaming platform. Key UI elements:
- Discover page with trending podcasts, top audiobooks, recent episodes
- Browse podcasts with category filter dropdown
- Browse audiobooks with genre filter, rating slider, and sort options
- Podcast detail page with episodes list, subscribe toggle, reviews
- Audiobook detail page with purchase button, reviews, related items
- Episode player page with play/pause controls and progress bar
- User library with subscriptions, purchases, listen history
- Search bar for cross-content search
- Review submission with rating and free text

## Target Macros

navigate_by_dropdown, navigate_by_route, search_by_query, search_by_semantic, filter_by_dropdown, filter_by_slider, sort_by_ranking, extract_by_query, submit_by_query, select_by_dropdown, play_by_dropdown, play_by_date_range, play_by_playback, export_by_dropdown, post_from_free_text, react_by_toggle, rate_by_slider, follow_by_dropdown, follow_by_toggle, subscribe_by_toggle, save_by_toggle

## Temporal Dynamics

Not applicable — podcast/audiobook catalogs are append-only. No temporal simulation needed. Data is a static snapshot.

## Domain-Specific Notes

- Semantic search: keyword-overlap scoring across titles, descriptions, hosts/authors (lightweight, no ML)
- Podcast categories: News, Technology, True Crime, Comedy, Science, History, Business, Health & Wellness, Music, Food, Family
- Audiobook genres: Fiction, Self-Help, Science Fiction, History, Business, Memoir, Science
- Subscribe/follow/save are toggle operations (idempotent on/off)
- Playback speed is adjustable (0.5x to 3.0x)
- Episodes have liked_by arrays for react_by_toggle
- Reviews require login; rating 1-5 with free text
- Export supports CSV format for podcast/audiobook catalogs
- Filter by slider for rating (min_rating) and duration range
