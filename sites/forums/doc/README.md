# Forums

**Category**: Social media
**Reviewer**: Reaz
**Number of macros**: 27

## Data Source

data_sources/reddit-augment/ (overlay format: users_overlay.json, posts_overlay.json, comments_overlay.json)

## Target Macros

navigate_by_semantic, navigate_by_dropdown, navigate_by_route, search_by_query, search_by_semantic, filter_by_dropdown, filter_by_date_range, sort_by_ranking, extract_by_semantic, extract_by_dropdown, extract_by_route, create_from_free_text, submit_by_form, submit_by_route, edit_by_form, delete_from_table, react_by_toggle, follow_by_dropdown, follow_by_toggle, join_by_toggle, share_by_dropdown, save_by_toggle, report_by_form, block_by_toggle, message_from_free_text, authenticate_by_form, register_by_form

## Site Description

A Reddit-style community discussion forum. Users browse subreddits, read and create posts, comment in threaded discussions, vote on content, and interact socially (follow users, join communities, save posts, send direct messages, report/block). Modeled after reddit.com.

- **Domain**: Social media / forums
- **Data**: 6 users, 12 posts across 10 subreddits, 15 threaded comments, plus runtime-created messages and reports
- **Real-world model**: Reddit
- **Temporal**: No temporal simulation needed; content is static user-generated
- **Auth**: Users log in by reddit_username; default user is cascadia_coder (root_user_id=1)
