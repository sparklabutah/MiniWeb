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

# WRONG — still loads everything then slices
all_txns = db.query(SITE, "transactions")
page = all_txns[offset:offset+30]

# RIGHT — SQL does the filtering, sorting, pagination
posts = db.query(SITE, "posts", where={"user_id": uid}, sort="-created_at", limit=30, offset=0)

# RIGHT — for complex filters, use db.execute() with raw SQL
rows = db.execute(
    "SELECT * FROM forums_posts WHERE subreddit=? AND score>? ORDER BY created_at DESC LIMIT ? OFFSET ?",
    (subreddit, min_score, per_page, offset)
)
```

### Rules

1. ALL filtering (user_id, category, status, date range, text search) happens in SQL WHERE clauses
2. ALL sorting happens in SQL ORDER BY
3. ALL pagination happens in SQL LIMIT/OFFSET
4. Python-side filtering is ONLY acceptable on result sets already limited to <100 rows
5. `db.query()` without `limit` is ONLY acceptable for tables guaranteed <100 rows (e.g., users, config)
6. For text search on large tables, use `WHERE column LIKE ?` in SQL, not Python string matching
7. For date range filters, use `WHERE date >= ? AND date <= ?` in SQL
8. For count queries, use `SELECT COUNT(*)` — never `len(db.query(...))`

### Available db functions

- `db.query(site, collection, where=dict, sort=str, limit=int, offset=int)` — filtered query
- `db.get_item(site, collection, item_id)` — single item by PK
- `db.count(site, collection, where=dict)` — count without loading data
- `db.save_item(site, collection, item_id, data)` — upsert one item
- `db.delete_item(site, collection, item_id)` — delete one item
- `db.save_collection(site, collection, items)` — replace entire collection (small tables only)
- `db.execute(sql, params, fetch="all"|"one"|"val")` — raw SQL for complex queries

## Raw Data + Synthetic Data = ONE Table

Synthetic and raw data are merged into the SAME per-site table at build time.
Route code has ONE query path. No if/else branching on data source. No separate load functions for "overlay" vs "raw."

- Raw data sources (CSV, JSONL, XML) are configured in `scripts/generate_schemas.py` `RAW_DATA_SOURCES`
- Always use the FULL raw data files, never samples
- Synthetic data MUST use the same field names as the raw data (e.g., `author` not `reddit_username`)
- Synthetic data MUST include ALL fields from the raw schema (with sensible defaults for fields it doesn't populate)
- All columns have `NOT NULL DEFAULT` — no NULLs anywhere in the database
- Route code should NEVER check whether a record is synthetic or raw

## Build Pipeline

```bash
# Generate schema.py files from data
python scripts/generate_schemas.py

# Build the database (on compute node for large datasets)
python scripts/build_db.py --max-raw 1000000

# Run the app
python run.py
```
