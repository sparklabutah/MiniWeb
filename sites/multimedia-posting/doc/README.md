# Multimedia posting

**Category**: Social media
**Reviewer**: Reaz
**Number of macros**: 29

## Data Source

Synthesize with AI agents

## Target Macros

navigate_by_dropdown, navigate_by_route, search_by_query, search_by_semantic, search_by_checkbox, filter_by_radio, sort_by_dropdown, extract_by_semantic, extract_by_dropdown, extract_by_route, create_from_free_text, edit_by_form, delete_from_table, post_by_query, post_from_free_text, select_by_dropdown, configure_by_toggle, play_by_dropdown, play_by_playback, export_by_dropdown, upload_by_upload, react_by_toggle, follow_by_dropdown, follow_by_toggle, subscribe_by_toggle, share_by_dropdown, save_by_toggle, report_by_form, block_by_toggle

## Site Description

PixShare is an Instagram/Twitter-inspired multimedia social media platform. Users create and share photo, video, and carousel posts with captions, tags, and locations. The platform supports a feed of posts from followed users, an explore page with search/filter/sort, stories, user profiles, and extensive social interactions.

### Data Files
- `users.json` -- 9 user profiles with usernames, bios, follower counts
- `posts.json` -- 40 multimedia posts (photo/video/carousel) with captions, tags, locations
- `comments.json` -- 50 comments linked to posts
- `stories.json` -- 18 ephemeral stories with active/expired status
- `follows.json` -- 50 follower/following relationships

### Key Features
- Feed (posts from followed users), Explore (all posts with search/filter/sort)
- Post types: photo, video, carousel
- Reactions: like (react_by_toggle), save (save_by_toggle)
- Sharing via dropdown (link, DM, email, embed)
- User interactions: follow toggle, follow by dropdown, subscribe, block
- Content management: create posts, edit captions, delete posts
- Comment system: post comments, delete comments
- Stories with play/view tracking
- Search by keyword and semantic multi-word matching
- Filter by type (radio chips), checkbox multi-type, sort by dropdown
- Export posts as CSV/JSON, upload media files
- User settings with toggle controls (dark mode, notifications, privacy)
- Report posts via form, block users via toggle

### Real-World Model
Modeled after Instagram with elements of Twitter -- photo grid explore, story ring, post detail with side panel, profile with follower stats.

### No Temporal Dynamics
Stories have `is_active`/`expires_at` fields but no continuous time simulation. Data is static snapshot-based.
