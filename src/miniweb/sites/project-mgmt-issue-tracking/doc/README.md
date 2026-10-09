# Meridian Tracker (`project-mgmt-issue-tracking`)

A Jira-style project tracker for the fictional Meridian Systems. It has
per-project Kanban boards, issue detail pages with comments and status
transitions, sprints, a backlog grid and issue export. Issue keys follow Jira
style (`MF-101`).

- URL: `/sites/project-mgmt-issue-tracking/` (simulated domain `taskflow.pm`)
- Data split: held-out (test) site

## Pages

| Route | Page |
|---|---|
| `/` | Dashboard: project cards with issue counts and recent activity |
| `/project/<id>` | Kanban board with search, Sprint/Assignee/Type/Priority dropdowns, "Created from/to" dates, export (CSV/JSON) |
| `/issue/<id>` | Issue detail: description, metadata, comments, edit form, status transition, Watch, Delete |
| `/create-issue` | New-issue form (project, title, description, type, priority, assignee, sprint, story points, labels) |
| `/backlog` | Backlog: search, project/type/priority filters, inline-editable issue grid with add row and Save Changes |
| `/sprints`, `/sprint/<id>` | Sprint list with create form; sprint board with add/remove issue, Start Sprint, Complete Sprint |
| `/login` | Sign-in form |

JSON endpoints under `/api/` cover projects, issues (search, lookup by key,
bulk update, watch), comments, sprints, users, stats and export.

## Interactions and macros

- Search issues on a board or the backlog: `search`
- Filter by assignee, type, priority, project or sprint: `filter_by_dropdown`
- Filter a board by creation date: `filter_by_date_range`
- Open a project, an issue or a nav page: `navigate_by_route`
- Create an issue or add a comment: `create_by_form`
- Edit an issue or transition its status: `edit_by_form`
- Edit issues inline in the backlog grid: `edit_by_cell`
- Delete an issue: `delete_from_table`; watch an issue: `toggle_relationship`
- Export a project's issues: `export`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `project-mgmt-issue-tracking`.

## Data

- Source: Jira social repository (github.com/marcoortu/jira-social-repository),
  adapted to Meridian projects.
- Tables (`project_mgmt_issue_tracking_*`): `projects`, `issues`, `comments`,
  `sprints`, `users`.
- Login uses `session["user_id"]`, so the global auto-login signs in user 1.
  Signing in emits a `signup` event.
- Creating an issue with an assignee emits `booking` (calendar event) and
  `message` (instant message to the assignee). Editing an assigned issue emails
  the assignee.
