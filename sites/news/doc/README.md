# News (Lakeport Tribune)

**Category**: Dynamic info / feeds
**Reviewer**: Minh
**Number of macros**: 20

## Data Source

Hand-authored local news articles for the fictional city of Lakeport in Cascadia County.
Files: `data_sources/news/articles.json`, `categories.json`, `users.json`, `bookmarks.json`

Mutable state files (written at runtime): `comments.json`, `follows.json`, `shares.json`, `reports.json`

### Data Format

- **articles.json** -- JSON array. Each record: id, title, author, date (YYYY-MM-DD), category (slug), body (full text), tags (list), source, image_url, word_count, comments_count.
- **categories.json** -- JSON array. Each record: id, slug, name, description, color, article_count. Seven categories: local, business, sports, arts, weather, politics, community.
- **users.json** -- JSON array. Each record: id, root_user_id, username, display_name, email, subscription_tier (free/digital/premium), newsletter_preferences (daily_digest, breaking_news, weekly_roundup, categories), notification_settings, reading_history_count, bookmarks_count, comments_count.
- **bookmarks.json** -- JSON array. Each record: id, user_id, root_user_id, article_id, article_title, bookmarked_at, note.

### Sampling

25 articles across 7 categories, 3 authors, 4 users. All records loaded (num_data_points=-1).

## Real-World Model

**Patch.com / local newspaper websites** -- clean, category-driven local news interface. Key UI elements:
- Header with category navigation dropdown/links
- Search bar in header
- Homepage with featured articles, latest articles, category sections
- Article detail page with full text, author, date, tags, comments
- Category pages with sort options
- User features: login/register, bookmark articles, comment on articles, follow categories/authors, newsletter subscriptions, share articles, report articles
- Audio playback button for text-to-speech article reading

## Target Macros

navigate_by_dropdown, navigate_by_route, search_by_query, search_by_semantic, filter_by_dropdown, filter_by_date_range, sort_by_dropdown, extract_by_query, extract_by_semantic, extract_by_dropdown, extract_by_route, play_by_playback, post_from_free_text, follow_by_dropdown, subscribe_by_toggle, share_by_dropdown, save_by_toggle, report_by_form, authenticate_by_form, register_by_form

## Temporal Dynamics

Not applicable for this implementation. Articles are a static corpus. News freshness is simulated via date ordering but no real-time feed updates. Data is a static snapshot of 25 articles spanning 2025-2026.

## Domain-Specific Notes

- Search: keyword substring match over title, body, author, tags (search_by_query); bag-of-words overlap scoring for semantic search (search_by_semantic)
- Authentication: any valid username from users.json + password "password" (demo site)
- Comments, follows, shares, reports are persisted to data_sources/news/ JSON files at runtime
- Bookmarks (save_by_toggle) use a toggle API endpoint; re-posting the same article un-bookmarks it
- Subscriptions (subscribe_by_toggle) toggle newsletter preferences on the user record
- Share (share_by_dropdown) records the chosen platform (email, twitter, facebook, linkedin, copy_link)
- Play (play_by_playback) returns audio metadata with estimated duration based on word count
- Report (report_by_form) requires a reason category and optional details text
