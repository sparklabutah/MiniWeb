# MeridianGit (`version-control`)

A GitHub/GitLab-style code-hosting site for the fictional Meridian Systems
engineering team, mixed with real GitLab projects, issues and merge requests.
Users browse repositories (code, commits, issues, merge requests), search code,
create repositories, issues and merge requests, comment, star repos, upload
files and merge or close merge requests.

- URL: `/sites/version-control/` (simulated domain `codehost.dev`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Dashboard: recent activity, "Search or jump to..." box, repo sort |
| `/repos` | Repository list with search and a sort dropdown |
| `/repo/<id>` | Repo detail tabs: Code (file tree, README, upload form), Commits (compare two commits, open a merge request), Issues (new issue, edit, comment), Star |
| `/explore` | Discover repositories |
| `/projects`, `/project/<name>` | GitLab projects; project detail with its issues and merge requests |
| `/issues`, `/issue/<id>` | All issues with state and project dropdowns; issue detail with comments |
| `/merge-requests`, `/mr/<id>` | All merge requests with state and project dropdowns; MR detail with comments, Merge and Close |
| `/members`, `/user/<id>`, `/group/<name>` | Member list, user profile with repos and activity, namespace page |
| `/activity` | Full activity feed |
| `/new-repo` | New-repository form (name, description, owner, default branch) |
| `/login` | Sign-in form |

JSON endpoints under `/api/` cover repos (files, star, fork, settings,
upload, compare), issues, merge requests, comments, activity, users,
keyword/semantic/code search, stats and export.

## Interactions and macros

- Search repos or code: `search`
- Filter issues and merge requests by state or project: `filter_by_dropdown`
- Sort repositories (Updated, Stars, Name): `sort_by_form`
- Open repos, issues, merge requests and nav pages: `navigate_by_route`
- Create a repo, issue, merge request or comment: `create_by_form`
- Edit an issue's title or state: `edit_by_form`
- Star a repo: `toggle_relationship`
- Upload a file to a repository: `upload_file`
- Read file trees, commit history, commit comparisons and issue threads: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `version-control`.

## Data

- Source: real GitLab data (`*_raw` tables: projects, issues, merge requests,
  notes, labels, users) plus synthetic Meridian repositories with generated
  file trees, commits and READMEs.
- Tables (`version_control_*`): `repositories`, `activities`, `users`,
  `projects_raw`, `issues_raw`, `merge_requests_raw`, `notes_raw`,
  `labels_raw`, `users_raw`.
- Login sets the site's own `session["vc_user_id"]` and accepts a blank
  password. Content created without a login is attributed to
  `session["user_id"]`, which the global auto-login sets to user 1.
- Signing in emits `signup`. Opening a merge request sends an email and emits
  `message` (an instant message).
