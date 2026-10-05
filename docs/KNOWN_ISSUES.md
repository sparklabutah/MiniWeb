# Known issues

Problems found during the 2026-10-02 documentation audit. The dataset (sites + training data) is frozen, so these are recorded, not fixed. None of them affects a reported result: no affected feature is on a held-out (test) site.

## Site and data bugs

| Issue | Where | Effect |
|---|---|---|
| Writes go to collections that have no base table, so reads and `/_admin/data` return nothing for them | personal-portfolio `contact_messages`; sports-esports `comments`, `subscriptions`; video `ratings`, `reports` | One task uses one of them: `sports-esports_c6d65b` (subscribe, a training-site dev task). Its verifier grades the backend request and the page state, not a table read. |
| `forums_messages` table is missing from the local DB | forums direct messages | Runtime seed step; re-seed after a DB rebuild (the seed script is in `../MiniWeb-archive`). |
| `wikis` emits an `edit` event that no handler consumes | `sites/wikis/routes.py` (two `emit("edit", ...)` calls) | None; the event is dropped. |
| `data/macro_locations.yaml` lists UI controls that do not exist | health-fitness-tracking, design-creative, dictionaries-language-tools, personal-portfolio, cloud-storage-file-transfer, map-services, music, handwritten-notes-whiteboards, remote-calls | Coverage statistics only. Tasks and training data do not use it. The per-site docs describe the real UI. |

## Code

| Issue | Where | Effect |
|---|---|---|
| Whole collections are loaded into Python, against the DB rules in `CLAUDE.md` | `/_admin/data`, `/_admin/user` in `app/__init__.py` | Slower grading on large tables; results are correct. |

## Repo hygiene

| Issue | Where |
|---|---|
| Stale config in the old `--config` format | `evaluation/configs/example.yaml` |
| Docstring cites `evaluation/configs/study.yaml`, which does not exist | `evaluation/run_study.py` (lines 5-6) |
| Untracked and unused by any code | `data/macro_templates.yaml` |
| Hand-written but gitignored by the `data/datagen/*` rule | `data/datagen/retired.json` |
| Un-ignore rule for a directory that does not exist | `.gitignore` line 67 (`!data/reviews/`) |
| `build_db.py` exists only in `../MiniWeb-archive`, and `sites/*/tasks.json` were removed (commit 16310a1); the benchmark tasks are `data/annotations/*/*/task.json` | — |
