# PixShare - Multimedia Posting Platform

## Domain
Social media platform for sharing photos, videos, and carousels with followers. Inspired by Instagram and Twitter's media-focused features.

## Purpose
Users create and share multimedia posts (photos, videos, carousels), follow other users, react to content (like, save, share), post comments, view stories, and manage their profiles. The platform supports content discovery through search, filters, and explore pages.

## Data Files
- `users.json` - 9 user profiles with handles, bios, follower/following counts
- `posts.json` - 40 posts (photo/video/carousel) with captions, tags, locations, likes
- `comments.json` - 50 comments linked to posts
- `stories.json` - 18 ephemeral stories with active/expired status
- `follows.json` - 50 follower/following relationships

## Real-World Model
Instagram-style social media app with feed, explore grid, stories bar, user profiles, and post detail pages.

## Temporal Dynamics
Stories have `is_active` and `expires_at` fields for ephemeral content. No continuous time simulation needed -- data is static snapshots.

## Key Features
- Feed (posts from followed users), Explore (all posts with search/filters)
- Post types: photo, video, carousel
- Reactions: like, save, share, report, block
- User interactions: follow, subscribe, block
- Content management: create posts, edit captions, delete posts
- Stories with author grouping
- Search by query, semantic, tags; filter by type (radio), sort by dropdown
- Export posts as CSV/JSON, upload media
- Notifications and settings toggles
