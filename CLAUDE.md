# MiniWeb Development Rules

## Database Access — MANDATORY

All data lives in per-site SQLite tables (e.g., `banking_transactions`, `forums_posts`).
Sites query data through `app.db` functions.

### NEVER load entire collections. NEVER.

Every query MUST include `WHERE`, `LIMIT`, and `ORDER BY` at the SQL level.
The frontend displays <50 items per page. Only fetch what's visible.

```python
# WRONG — loads 1M+ rows into Python
posts = db.query(SITE, "posts")
user_posts = [p for p in posts if p["user_id"] == uid]

# RIGHT — SQL does the filtering, sorting, pagination
posts = db.query(SITE, "posts", where={"user_id": uid}, sort="-created_at", limit=30, offset=0)

# RIGHT — for complex filters, use db.execute() with raw SQL
rows = db.execute(
    "SELECT * FROM forums_posts WHERE subreddit=? AND score>? ORDER BY created_at DESC LIMIT ? OFFSET ?",
    (subreddit, min_score, per_page, offset)
)
```

### Rules

1. ALL filtering happens in SQL WHERE clauses
2. ALL sorting happens in SQL ORDER BY
3. ALL pagination happens in SQL LIMIT/OFFSET
4. Python-side filtering is ONLY acceptable on result sets already limited to <100 rows
5. `db.query()` without `limit` is ONLY acceptable for tables guaranteed <100 rows (e.g., users, config)
6. For text search on large tables, use `db.search()` (FTS5/BM25), never LIKE queries
7. For count queries, use `SELECT COUNT(*)` — never `len(db.query(...))`

### Available db functions

- `db.query(site, collection, where=dict, sort=str, limit=int, offset=int)` — filtered query
- `db.get_item(site, collection, item_id)` — single item by PK
- `db.count(site, collection, where=dict)` — count without loading data
- `db.search(site, collection, query, limit, offset)` — FTS5/BM25 full-text search
- `db.save_item(site, collection, item_id, data)` — upsert one item
- `db.delete_item(site, collection, item_id)` — delete one item
- `db.save_collection(site, collection, items)` — replace entire collection (small tables only)
- `db.execute(sql, params, fetch="all"|"one"|"val")` — raw SQL for complex queries

## Macro System

Two-axis macro tags (see `docs/macro_system.md`): a **base macro** (physical interaction, e.g. `create_by_form`, `filter_by_slider`, `toggle_relationship`) + an optional **reasoning operation** (`read/extremum/count/compute/compare/verify`). Reasoning that the agent must **output to the human** uses the op-only base `report_information` (this REPLACED `reasoning_on_page`, which is now an alias). Intermediate reasoning is NOT its own tag — its op folds onto the base macro it is part of. The canonical registry is `data/macros.yaml` (loaded via `annotation/macros.py`) — the single source of truth; do not duplicate macro facts elsewhere, edit the registry.

- **39 base macros + 6 operations** in `data/macros.yaml` (`groups:` / `operations:` / `macros:`). Retired flat `verb_by_modality` names fold in as `aliases:` so `canon()` migrates them. `compare_by_form` and `report_information` were added during review; `reasoning_on_page` retired into `report_information`'s aliases. Annotators can register new macros from the annotate UI (persisted to `data/macros.yaml` under the `unassigned` group). Download the current set as CSV from the Macro Template Builder.
- **Op definitions:** `read`=info is on the page · `extremum`=get max/min · `count`=count · `compute`=compute a NEW value from on-page values · `compare`=compare 2 on-page values · `verify`=compare an on-page value against a value in the instruction.
- `_MACRO_DESCRIPTIONS`/`_canon` in `annotation/app.py` derive from `annotation/macros.py` — edit the registry, not those.
- Navigation macros (`navigate_by_route`) are NOT sampled for tasks — agents start on the target page
- `tests/test_macro_registry.py` guards registry drift.
- Per-site macro→UI-location data lives in **`data/macro_locations.yaml`** (canonical-macro-keyed; drives coverage/sampling). `annotation/macro_locations.py` is now just a loader — edit the YAML, not the module.
- **Persistence (deploy):** annotators register macros by *writing* to `macros.yaml`, so in production point the YAMLs at a persistent volume via **`MINIWEB_MACRO_DIR`** (dir holding both `macros.yaml` + `macro_locations.yaml`). Per-file overrides: **`MINIWEB_MACROS`**, **`MINIWEB_MACRO_LOCATIONS`**. A fresh volume is auto-seeded from the repo's bundled copies (both are committed). Defaults to the repo `data/` dir when unset.

## Key Architecture

- **Session isolation**: Mutations go to `session_overlay`, not base tables. Multiple agents can run in parallel.
- **Auto-login**: `before_request` handler sets `session["user_id"] = 1` on `/sites/*` requests unless `_no_autologin` flag is set.
- **2FA**: Financial transactions go through `/verify-payment`. Can be disabled via `session["_disable_2fa"]`.
- **Script injection**: `@app.after_request` injects `recorder.js`, `file-picker.js`, and `export-feedback.js` into all `/sites/*` pages.
- **Annotation auth**: `/annotate/*` routes require `session["annotator_authenticated"]`. Login at `/annotate/login`.

## NEVER do these

- NEVER run `build_db.py` — the DB has been modified post-build
- NEVER delete data without asking the user first
- NEVER load entire tables into Python for filtering
- NEVER add `navigate_by_route` as a macro to tasks
