# Visual How-To Guides (StepVista)

**Category**: Search & reference
**Reviewer**: Minh
**Number of macros**: 16

## Data Source

Synthetically generated how-to guides inspired by wikiHow/Instructables content patterns.
Files: `guides.json`, `categories.json`, `users.json`, `comments.json`, `bookmarks.json` (plus runtime-created `ratings.json`, `reactions.json`)

### Data Format

**guides.json** -- Array of guide objects:
- `id` -- integer guide ID
- `title` -- guide title
- `description` -- short summary
- `category` -- category name (matches categories.json name)
- `author_id` -- integer referencing users.json
- `created_at`, `updated_at` -- YYYY-MM-DD date strings
- `difficulty` -- "easy", "medium", or "hard"
- `duration_minutes` -- estimated time in minutes
- `views` -- view count integer
- `rating` -- float 0-5 average rating
- `steps` -- array of step objects: {order, title, description, image_placeholder}

**categories.json** -- Array: {id, name, description, guide_count}
**users.json** -- Array: {id, username, password, display_name, bio, avatar, joined_at}
**comments.json** -- Array: {id, guide_id, user_id, text, date, helpful_count}
**bookmarks.json** -- Array: {id, user_id, guide_id, bookmarked_at}
**ratings.json** -- Dict: {"<user_id>_<guide_id>": score} (created at runtime)
**reactions.json** -- Dict: {"<user_id>_<comment_id>": "helpful"|"unhelpful"} (created at runtime)

### Sampling

20 guides across 8 categories. All loaded by default (num_data_points=-1).

## Real-World Model

**wikiHow / Instructables** -- visual step-by-step tutorial platform. Key UI elements:
- Category navigation via header dropdown or sidebar
- Search bar for keyword and semantic search
- Guide cards with title, category, difficulty, duration, rating
- Step-by-step detail view with images, prev/next navigation (playback)
- Filter by category dropdown, difficulty slider, duration slider
- Sort by rating, popularity, date, duration
- Compare guides side-by-side in a table
- User features: bookmark guides, rate guides (1-5 stars), comment on guides, mark comments helpful, follow authors

## Target Macros

navigate_by_dropdown, navigate_by_route, search_by_query, search_by_semantic, filter_by_dropdown, filter_by_slider, sort_by_ranking, extract_from_table, extract_by_route, play_by_date_range, play_by_playback, post_from_free_text, react_by_toggle, rate_by_slider, follow_by_dropdown, save_by_toggle

## Temporal Dynamics

Not applicable -- how-to guides are static reference content. No temporal simulation needed. Data is a static snapshot.

## Domain-Specific Notes

- Difficulty maps to numeric levels for slider filtering: easy=1, medium=2, hard=3
- Duration filtering uses min/max minute ranges
- Semantic search uses keyword-overlap scoring over titles, descriptions, and step content
- Step playback provides individual step pages with prev/next navigation
- Date range filtering lets users browse guides created within a time window (play_by_date_range)
- Authors are users who have authored guides; any user can follow any author
- Ratings are per-user-per-guide; guide average is recalculated on each rating
- Reactions (helpful/unhelpful) are per-user-per-comment toggles
