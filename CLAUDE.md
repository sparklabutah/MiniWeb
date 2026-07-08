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

Macros are primitive UI skills (e.g., `filter_by_slider`, `create_by_form`). The authoritative source for which macros each site supports is `annotation/macro_locations.py` — NOT the README files.

- 170 unique macros across 7 difficulty categories (see `annotation/macro_difficulty.py`)
- Each macro maps to specific UI locations per site
- Navigation macros (`navigate_by_route`) are NOT sampled for tasks — agents start on the target page
- Macro descriptions live in `_MACRO_DESCRIPTIONS` in `annotation/app.py`

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
