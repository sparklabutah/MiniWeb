# Project mgmt / issue tracking

**Category**: Productivity
**Reviewer**: Reaz
**Number of macros**: 21

## Data Source

Jira social repository -- https://github.com/marcoortu/jira-social-repository

Files (in data_sources/project-mgmt-issue-tracking/):
- `projects.json` -- 5 projects (MeridianFlow, MeridianVault, MeridianLens, Internal Tools, Website Redesign)
- `issues.json` -- 40 issues across all projects with keys like MF-101, MV-201, etc.
- `comments.json` -- 30 comments attached to issues
- `sprints.json` -- 6 sprints across projects
- `users.json` -- 5 team members (alex.chen, priya.sharma, marcus.johnson, david.kim, natalie.brooks)

### Data Format

**projects.json**: `id`, `name`, `key`, `description`, `owner_id`, `status`, `created_at`
**issues.json**: `id`, `project_id`, `key`, `title`, `description`, `type` (bug/feature/task/story), `status` (open/in_progress/review/done/closed), `priority` (critical/high/medium/low), `assignee_id`, `reporter_id`, `created_at`, `updated_at`, `labels`, `story_points`, `sprint`
**comments.json**: `id`, `issue_id`, `user_id`, `text`, `created_at`
**sprints.json**: `id`, `project_id`, `name`, `start_date`, `end_date`, `status`, `goal`
**users.json**: `id`, `username`, `name`, `email`, `password`, `role`, `avatar_color`

### Sampling

All data is loaded by default (num_data_points=-1). The dataset is small (40 issues, 30 comments) and fully usable without sampling.

## Real-World Model

**Jira / Linear / Asana** -- professional project management tool. Key UI elements:
- Dashboard with project cards showing issue counts and critical items
- Kanban board per project with columns: Open, In Progress, Review, Done, Closed
- Issue detail page with description, sidebar metadata, comments, edit form, status transitions
- Sprint overview with progress bars and story point tracking
- Backlog view for unassigned issues
- Create issue form with project, type, priority, assignee, story points, sprint, labels
- Search across issues by keyword
- Filter by project, status, type, priority, assignee, sprint, date range, label
- Sort by priority, date, status, key, story points
- Export issues as CSV or JSON
- Watch/follow toggle on issues

## Target Macros

navigate_by_semantic, navigate_by_dropdown, navigate_by_route, search_by_query, filter_by_dropdown, filter_by_date_range, sort_by_ranking, extract_by_query, extract_by_semantic, extract_by_dropdown, extract_from_table, extract_by_route, create_from_free_text, submit_by_query, edit_by_query, edit_by_dropdown, edit_by_form, delete_from_table, post_from_free_text, export_by_dropdown, follow_by_toggle

## Temporal Dynamics

Not applicable -- issue trackers represent a live snapshot of project state. The data is a static snapshot at a point in time. Mutations (create, edit, delete, transition) happen through user actions, not temporal simulation.

## Domain-Specific Notes

- Issue keys follow Jira convention: PROJECT_KEY-NUMBER (e.g., MF-101, MV-201)
- Status workflow: open -> in_progress -> review -> done -> closed
- Priority ordering: critical > high > medium > low
- Story points are optional numeric values per issue
- Sprints have status: planned, active, closed
- Watch/follow is a per-issue toggle that tracks which users are watching an issue
- Comments are append-only per issue; adding a comment updates the issue's updated_at timestamp
