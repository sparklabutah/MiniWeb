# Q&A / Knowledge

**Category**: Search & reference
**Reviewer**: Minh
**Number of macros**: 21

## Data Source

Stack Exchange data dump + augment overlay.
Directory: `data_sources/stackexchange-augment/`

### Data Format

Three overlay JSON files, each with `_overlay_meta` header plus a data array:

**questions_overlay.json** — `questions` array:
- `id` — integer question ID (e.g., 90001)
- `title` — question title string
- `body_excerpt` — body text / excerpt
- `author_root_user_id` — integer FK to users
- `tags` — list of tag strings (e.g., ["python", "asyncio"])
- `score` — integer vote score
- `answer_count` — integer count of answers
- `created_at` — ISO datetime string
- `site` — source site (e.g., "stackoverflow")

**answers_overlay.json** — `answers` array:
- `id` — integer answer ID (e.g., 80001)
- `question_id` — integer FK to questions
- `author_root_user_id` — integer FK to users
- `body_excerpt` — answer body text
- `score` — integer vote score
- `is_accepted` — boolean
- `created_at` — ISO datetime string

**users_overlay.json** — `users` array:
- `root_user_id` — integer user ID
- `se_username` — login username
- `se_display_name` — display name
- `reputation` — integer reputation score
- `tags` — list of expertise tag strings
- `top_answers_count` — integer
- `member_since` — date string (YYYY-MM-DD)
- `about_me` — bio text

### Sampling

All records are loaded by default (`num_data_points: -1`). The dataset is small (10 questions, 8 answers, 5 users) so no sampling is needed.

## Real-World Model

**Stack Overflow / Stack Exchange** — the canonical Q&A platform for programming. Key UI elements:
- Question list with vote counts, answer counts, and tag badges
- Tag-based navigation and filtering (sidebar, dropdown, checkbox multi-select)
- Sort options (votes, newest, active, unanswered)
- Question detail page with answer thread, voting arrows, accept checkmark
- User profiles with reputation, activity, and expertise tags
- Search bar with keyword and semantic search
- Ask Question form with tag input
- Save/bookmark questions, follow tags
- Share via platform dropdown, report content

## Target Macros

navigate_by_dropdown, navigate_by_route, search_by_query, search_by_semantic, filter_by_dropdown, sort_by_ranking, extract_by_query, extract_by_route, create_from_free_text, submit_by_query, edit_by_form, post_from_free_text, post_by_route, react_by_toggle, follow_by_dropdown, follow_by_toggle, share_by_dropdown, save_by_toggle, report_by_form, authenticate_by_form, register_by_form

## Temporal Dynamics

Not applicable. Q&A knowledge bases are append-only archives. New questions and answers are added but existing content does not change over time. No temporal simulation needed.

## Domain-Specific Notes

- Voting is a toggle: upvote increments score by 1, downvote decrements by 1
- Tags are the primary organizational axis (like Stack Overflow)
- Users can save/bookmark questions and follow tags
- Answer acceptance is per-question (only one accepted answer at a time)
- Reports are stored on the question/answer object for verification
- Authentication uses simple username/password matching against user records
- Registration creates new users with default reputation of 1
