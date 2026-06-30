# Version Control

**Category**: Productivity
**Reviewer**: Reaz
**Number of macros**: 20

## Data Source

GitLab-augmented overlay data for Meridian Systems engineering organization.
Directory: `data_sources/gitlab-augment/`

### Data Format

Three JSON overlay files:

**users_overlay.json** -- 6 developer profiles:
- `root_user_id` -- unique user ID
- `gitlab_username` -- login username (e.g., "alex.rivera")
- `display_name` -- full name
- `email`, `role`, `groups`, `joined`

**repos_overlay.json** -- 8 repositories:
- `id` -- repo ID (1001-1008)
- `name` -- repo slug (e.g., "meridianflow-api")
- `namespace` -- GitLab namespace path
- `description`, `visibility`, `default_branch`
- `stars`, `forks`, `last_activity`, `owner_user_id`
- `tech_stack` -- list of languages/frameworks

**activity_overlay.json** -- 15 activity events:
- `id` -- activity ID
- `type` -- "push", "merge", or "merge_request_review"
- `author_root_user_id`, `gitlab_username`
- `repo`, `branch`, `commit_sha`, `commit_message`
- For merges: `merge_request_title`, `source_branch`, `target_branch`
- For reviews: `review_state`, `review_comment`

### Synthetic Augmentation

Routes.py generates additional data deterministically from the overlay data:
- File trees per repo (realistic project structures)
- Commit histories per repo (7 days of commits)
- README content per repo (Markdown documentation)
- Issues per repo (bug reports, feature requests)
- Issue comments (threaded discussion)
- Merge requests (PRs)
- File contents (source code for code search)

### Sampling

The dataset is small (8 repos, 6 users, 15 activities). `num_data_points=-1` loads all records. No sampling needed.

## Real-World Model

**GitLab / GitHub** -- project-centric code hosting interface. Key UI elements:
- Dashboard with recent activity feed
- Repository listing with search, language filter, sort
- Repository detail page with file tree, commits, README, issues
- User profile pages with owned repos and activity
- Explore/discover page for finding repos
- Issue tracker with comments
- Merge request management
- Code search across repositories
- Star/unstar repos (follow_by_toggle)
- Repository creation form
- File upload to repository
- Export repo/activity data as CSV/JSON

## Target Macros

navigate_by_dropdown, navigate_by_route, search_by_query, search_by_semantic, search_by_code, filter_by_dropdown, sort_by_ranking, extract_by_query, extract_by_semantic, extract_from_table, extract_by_route, compare_from_table, create_from_free_text, submit_by_form, edit_by_form, upload_by_upload, select_by_dropdown, export_by_route, post_from_free_text, follow_by_toggle

## Temporal Dynamics

Not applicable -- version control platforms display historical data. Activity timestamps are fixed in the overlay data. No temporal simulation needed.

## Domain-Specific Notes

- Login uses gitlab_username (any password accepted for simplicity)
- Star state is session-based (not persisted across server restarts)
- Issue creation and comments modify in-memory state (reset on restart)
- Repo creation/deletion modifies the overlay JSON file on disk
- Code search operates over synthetic file contents embedded in routes.py
- Semantic search uses token-overlap scoring (no external ML)
