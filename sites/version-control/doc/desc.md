This website simulates an internal Git hosting platform (GitHub / GitLab style) for the Meridian Systems engineering organization. The interface should emulate GitLab's project-centric layout with repository browsing, commit histories, issue tracking, merge requests, code search, and developer activity feeds.

Data source: data_sources/gitlab-augment/ (users_overlay.json, repos_overlay.json, activity_overlay.json)
Synthetic data: File trees, commit histories, README content, issues, merge requests, issue comments, and file contents are generated deterministically in routes.py to provide a complete code-hosting experience.
Searching method: keyword matching for repo/user/activity search; token-overlap scoring for semantic search; substring matching for code search within file contents.
