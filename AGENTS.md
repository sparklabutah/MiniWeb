# AGENTS.md

Rules for coding agents (Claude Code, Codex, ...) working in this repo. `CLAUDE.md` holds the
same core rules and is always loaded. This file adds the working conventions. What the
project is and how to run it: [README.md](README.md). How it fits together:
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Environment

- Python: `~/.conda/envs/miniweb/bin/python`. Plain `python3` lacks Flask and browser-use.
  WebMix training and vLLM serving use `~/.conda/envs/webmix`.
- Run everything from the repo root, because `.env` uses relative paths such as
  `MINIWEB_DB="data/trimmed_miniweb.db"`.
- Server: `python run.py` (port 8080). Harnesses start their own servers on their own ports:
  datagen uses 8300-8320, and studies take a port from their config.
- Tests: `PYTHONPATH=. ~/.conda/envs/miniweb/bin/python -m pytest tests/ -q`.
- Read-only commands (grep, `--help`, `--dry-run`, reading results) need no permission. Ask
  before anything that writes data, deletes files, or uses shared GPUs.

## Data access (MANDATORY)

All site data is in per-site SQLite tables (`banking_transactions`, `forums_posts`, ...). Code
reaches them only through `app.db`. Tables reach millions of rows.

1. Filter in SQL `WHERE`, sort in SQL `ORDER BY`, paginate with SQL `LIMIT`/`OFFSET`. Pages
   show fewer than 50 items, so fetch only what is visible.
2. Python-side filtering is allowed only on result sets already limited to under 100 rows.
3. `db.query()` without `limit` is allowed only for tables guaranteed to stay under 100 rows
   (users, config).
4. For text search on large tables use `db.search()` (FTS5/BM25), never `LIKE`.
5. For counts use `db.count()` or `SELECT COUNT(*)`, never `len(db.query(...))`.
6. For new integer ids use `db.next_id(site, collection)`. It sees both the base table and this
   session's overlay. Taking `MAX(id)+1` from the base table alone makes the second create in a
   session collide.

```python
posts = db.query(SITE, "posts", where={"user_id": uid}, sort="-created_at", limit=30, offset=0)
rows = db.execute(
    "SELECT * FROM forums_posts WHERE subreddit=? AND score>? ORDER BY created_at DESC LIMIT ? OFFSET ?",
    (subreddit, min_score, per_page, offset))
```

`app.db` API: `query`, `get_item`, `count`, `search`, `save_item`, `delete_item`,
`save_collection` (small tables only), `next_id`, `execute(sql, params, fetch="all"|"one"|"val")`.
Writes go to the session overlay, never to base tables (see ARCHITECTURE.md).

## Sites (`sites/<site>/`)

- Each site is a Flask blueprint: `routes.py`, `schema.py`, `templates/<site>/`, `site.json`,
  `doc/README.md`, and sometimes `static/`. The app mounts it at `/sites/<site>/`.
- Every collection read with `db.query` or written with `save_collection` must have a real base
  table in `schema.py`. Otherwise reads never see overlay writes.
- Use the shared helpers: `helpers.auth` for the current user, `helpers.geo`,
  `helpers.security.safe_next`. `live` and `multimedia-posting` keep their own auth on purpose.
- Logout pops the site's own session keys. Never call `session.clear()` in site code: it drops
  the overlay session id, the annotator login and the 2FA toggle.
- Seed dates are deliberately static and in the past. Fix date filters in each site's UI. Never
  shift dates in the data.
- Seed data is generated offline and deterministically. Sites never fetch from external APIs at
  runtime.

## Macros, tasks, grading

- **Macro registry:** `data/macros.yaml` is the single source of truth: 46 base macros, 7
  reasoning operations, and aliases. It is loaded by `annotation/macros.py`. Edit the YAML, not
  derived code (`_MACRO_DESCRIPTIONS` and `_canon` in `annotation/app.py` derive from it).
  `tests/test_macro_registry.py` catches drift. Per-site UI locations live in
  `data/macro_locations.yaml`. See [docs/macro_system.md](docs/macro_system.md).
- **Tasks:** the real tasks are `data/annotations/<annotator>/<task_id>/task.json`, each with a
  `verifier.json`, `trajectory.json` and `screenshots/`. Macro tags follow the original human
  annotations.
- **Grading:** `evaluation/verifiers.py::verify_task` is the deterministic per-macro verifier.
  `evaluation/macro_judge.py` is the LLM judge (gemini-3.5-flash, best of 3 votes per macro).
  When grading, trust the backend request: a macro passes when the right server call carries
  the task's values. See [docs/VERIFIER_DESIGN.md](docs/VERIFIER_DESIGN.md).
- **Splits:** `data/datagen/site_split.json` (52 training sites, 13 held-out sites) is fixed.
  Training data comes only from training sites. Held-out tasks are only for measuring.

## The dataset is frozen

The sites, the database, the macro registry, the annotations and the WebMix training rows
(`data/webmix/replay_v4/`) are the paper's fixed artifact. Do not change them, and do not
generate new training data, without the maintainer's explicit sign-off. Agent improvements go
in the harness (`webmix/`, `evaluation/`).

## Never

- Run `build_db.py`. The DB was changed after it was built.
- Delete data, annotations, results or adapters without asking.
- Load whole tables into Python to filter them.
- Kill or restart the user's own runs (servers, studies, training, vLLM). Report the problem
  and let them decide.
- Commit `.env`, credentials, the DB or anything else under the gitignored `data/` paths.
- Commit unless the user asks.

## Removing files

Never `rm` project files. Move them to
`~/Documents/MiniWeb-archive/cleanup-<YYYYMMDD>/<repo-relative path>` and add a line to that
folder's `README.md` saying what each file was.

## Docs

- Each top-level package has a `README.md`. Update it in the same change as the code.
- Reference docs describe the current state only. History goes in
  [docs/CHANGELOG.md](docs/CHANGELOG.md), and research status in
  [docs/RESEARCH.md](docs/RESEARCH.md).
- Long-running modules (`datagen/`, `webmix/`, `evaluation/`) document their CLI in the module
  docstring and `--help`. Keep those in sync.
