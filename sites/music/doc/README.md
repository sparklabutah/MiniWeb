# Music

**Category**: Streaming & media
**Reviewer**: Reaz
**Number of macros**: 19

## Data Source

Synthetic dataset inspired by MusicBrainz entity structures.
Files: `data_sources/music/` directory containing:
- `artists.json` -- 25 artists across 15 genres with bios, monthly listeners, verified status
- `albums.json` -- 30 albums linked to artists with release dates, genres, cover colors
- `tracks.json` -- 60 tracks linked to albums and artists with play counts, durations, liked_by lists
- `playlists.json` -- 10 user-created playlists (public and private) with track ID lists
- `library.json` -- Per-user library state: liked tracks, liked albums, followed artists
- `users.json` -- 5 user accounts with credentials and display profiles
- `playback.json` -- Playback queue/state per user (mutable)
- `shares.json` -- Share log entries (mutable)
- `subscriptions.json` -- Artist/playlist subscription toggles (mutable)

### Data Format

All files are JSON arrays. Each record uses integer `id` as primary key with foreign keys (`artist_id`, `album_id`, `user_id`) linking entities. Tracks include `liked_by` (list of user IDs), `plays` (integer play count), and `duration_seconds`.

### Sampling

All records are loaded by default (`num_data_points: -1`). The dataset is small enough (60 tracks, 25 artists, 30 albums) to load entirely without sampling.

## Real-World Model

**Spotify** -- dark-themed music streaming interface. Key UI elements:
- Home page with featured artists, new releases, popular tracks
- Browse/explore page with genre dropdown filters and sort options
- Artist detail pages with discography, top tracks, follow/subscribe buttons
- Album detail pages with track listing, save/like toggle
- Track detail pages with "Add to Playlist" dropdown, like toggle, share button
- Playlist pages (create, view, add/remove tracks)
- Library page with tabs for liked tracks, liked albums, followed artists
- Search page with query input and results split by type (artists, albums, tracks)
- Playback controls (play, pause, next, previous) with queue state

## Target Macros

navigate_by_dropdown, navigate_by_route, search_by_query, search_by_semantic, search_by_route, filter_by_dropdown, sort_by_ranking, extract_by_query, create_from_free_text, select_by_dropdown, add_by_button, play_by_dropdown, play_by_date_range, play_by_playback, follow_by_dropdown, follow_by_toggle, share_by_dropdown, save_by_toggle, subscribe_by_toggle

## Temporal Dynamics

Not applicable -- the music catalog is a static snapshot. Playback state, shares, and subscriptions are user-driven mutations, not time-varying data. No temporal simulation needed.

## Domain-Specific Notes

- Genres span 15 categories: Electronic, Folk, Rock, R&B, Indie, Hip-Hop, Jazz, Funk, Metal, Pop, Classical, Country, Latin, Afrobeats, Post-Rock, Blues
- Playback is simulated state (queue + current index + status) -- no actual audio streaming
- Share creates a log entry with a shareable URL path, not a real external share
- Subscriptions are distinct from follows: follow adds artist to library, subscribe opts in to release notifications
- Semantic search uses lightweight keyword-overlap scoring across all text fields
