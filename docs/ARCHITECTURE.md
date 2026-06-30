# MiniWeb Architecture

## What MiniWeb Is

MiniWeb is a benchmark platform for evaluating web-browsing AI agents. A single Flask process serves 72 realistic websites — banking, forums, e-commerce, email, and more — each backed by real-world data (arxiv, reddit, StackExchange, Wikipedia) totaling 11M+ records in SQLite. Agents receive natural-language instructions and interact with rendered HTML; verifiers check backend state to score success.

## System Overview

```
                    Browser Agent
                         |
                    HTTP requests
                         v
+----------------------------------------------------+
|  Flask App (run.py)                                |
|  +----------+  +-------------------------------+   |
|  |  Portal   |  |  72 Site Blueprints           |   |
|  |  /        |  |  /sites/banking/*             |   |
|  |           |  |  /sites/forums/*              |   |
|  |           |  |  /sites/email/*               |   |
|  +----------+  +-------------+-----------------+   |
|                               |                    |
|                        +------v------+             |
|                        |  app/db.py  |             |
|                        |  query()    |             |
|                        |  get_item() |             |
|                        +------+------+             |
+-------------------------------+--------------------+
                                |
                        +-------v--------+
                        |  miniweb.db    |
                        |  (SQLite)      |
                        |  ~350 tables   |
                        |  11M+ records  |
                        +----------------+
```

## Directory Structure

```
MiniWeb/
|-- run.py                          # Entry point: python run.py
|-- CLAUDE.md                       # Development rules (read before writing code)
|-- miniweb.db                      # SQLite database (all site data)
|
|-- app/
|   |-- __init__.py                 # create_app(), blueprint registration, admin API
|   |-- db.py                       # Database access layer (query, get_item, save_item)
|   |-- bridges.py                  # Cross-site data connections (banking<->email<->calendar)
|   |-- portal/                     # Homepage search portal
|   +-- static/                     # Shared CSS
|
|-- sites/<site-id>/                # 72 self-contained sites
|   |-- site.json                   # Metadata (name, description, category)
|   |-- schema.py                   # SQLite table definitions (columns, types, indexes, defaults)
|   |-- routes.py                   # Flask blueprint (routes + SQL queries)
|   |-- templates/<site-id>/        # Jinja2 HTML templates
|   |-- config/config.json          # Site config (random seed, etc.)
|   |-- tasks.json                  # Benchmark tasks for agents
|   |-- verifiers.py                # Task success verification
|   |-- macro_verifiers.py          # Per-macro verification
|   +-- reference_solutions.py      # Known-good solutions
|
|-- scripts/
|   |-- build_db.py                 # Build miniweb.db from data sources
|   |-- generate_schemas.py         # Auto-generate schema.py from data files
|   |-- generate_site.py            # Generate a new site from a spec
|   +-- data_prep/                  # Per-site data preparation scripts
|
|-- evaluation/                     # Browser-agent evaluation harness
|-- annotation/                     # Human annotation interface
+-- docs/                           # Documentation
```

## Database Architecture

All site data lives in a single SQLite file (`miniweb.db`) with per-site tables.

### Per-Site Tables

Each site has its own tables with real columns, indexes, and NOT NULL defaults. Table names follow the pattern `{site_name}_{collection}` (hyphens replaced with underscores).

Examples:
- `banking_users` (id, username, email, phone, ...)
- `banking_transactions` (id, user_id, date, amount, category, status, ...)
- `forums_posts` (id, subreddit, title, body, author, score, created_utc, ...)
- `forums_comments` (id, post_id, body, author, score, ...)

All columns have `NOT NULL DEFAULT` constraints — no NULLs in the database. Integer columns default to 0, text columns default to '', real columns default to 0.0.

Table schemas are defined in each site's `schema.py` and created by `scripts/build_db.py`.

### One Table, One Schema

Synthetic data and real-world raw data are merged into the SAME table at build time. The synthetic JSON files use the same field names as the raw data (e.g., `author` not `reddit_username`, `created_utc` not `created_at`). Route code has one query path — no branching on data source.

### Infrastructure Tables

- `site_registry` — maps (site, collection) to SQL table name and primary key column
- `session_overlay` — per-session mutations (upserts/deletes)
- `session_collection_replaced` — flags when a session fully replaced a collection
- `sessions` — session lifecycle tracking

### Session Isolation

Each browser session gets isolated data mutations. When an agent modifies data (e.g., transfers money), the changes are stored in `session_overlay` and merged at query time. The base tables are never modified. This means:

- Multiple agents can run in parallel without interfering
- `POST /_reset_data` reverts a session to pristine state
- Base data survives server restarts

### Data Access API (app/db.py)

Sites access data through these functions — ALL filtering, sorting, pagination happens in SQL:

```python
from app import db

# Filtered query (SQL WHERE + ORDER BY + LIMIT)
txns = db.query("banking", "transactions",
                where={"user_id": 1}, sort="-date", limit=30, offset=0)

# Single item by primary key
user = db.get_item("banking", "users", 1)

# Count without loading data
total = db.count("banking", "transactions", where={"user_id": 1})

# Raw SQL for complex queries (date ranges, LIKE, aggregation)
rows = db.execute(
    "SELECT * FROM banking_transactions WHERE user_id=? AND amount>? ORDER BY date DESC LIMIT 30",
    (uid, 100.0)
)

# Mutations (stored in session overlay)
db.save_item("banking", "transactions", tx_id, updated_tx)
db.delete_item("banking", "transactions", tx_id)
```

## Data Sources

Site data comes from two sources, merged into the same tables at build time:

### Synthetic Data
- Created by data prep scripts or hand-written
- Stored as JSON in `data_sources/<site>/*.json`
- Uses the SAME field names as the raw data
- Includes ALL raw data fields (with defaults for fields it doesn't populate)

### Real-World Data
- Sourced from public datasets
- Stored as CSV/JSONL/XML in `data_sources/<raw-source>/`
- Configured in `scripts/generate_schemas.py` `RAW_DATA_SOURCES`

| Site | Real Data Source | Records |
|------|-----------------|---------|
| academic-paper-db | arxiv metadata | 1M papers |
| forums | reddit CSV | 127K posts, 1M comments, 661K users |
| qa-knowledge | StackExchange XML | 1M questions, 1M answers |
| dictionaries | wiktionary JSONL | 1M entries |
| flights-hotels | kaggle CSV | 246K flights, 1M hotels |
| job-sites | indeed CSV | 1M jobs |
| real-estate | realtor CSV | 1M listings |
| version-control | gitlab CSV | 80K issues, 134K MRs, 303K notes |
| wikis | wikipedia JSONL | 50K articles |
| news | enwikinews XML | 20K articles |
| comparison-aggregators | gsmarena CSV | 10K phones |
| podcasts-audiobooks | kaggle CSV | 271K books, 1M ratings |
| software-marketplace | google play CSV | 10K apps, 64K reviews |

### Build Pipeline

```bash
# 1. Generate schema.py files from data
python scripts/generate_schemas.py

# 2. Build the database (run on compute node for large datasets)
salloc -n 4 --mem=32G -t 2:00:00 -p notchpeak-shared -A notchpeak-shared-short
python scripts/build_db.py --max-raw 1000000

# 3. Run the app
python run.py
```

`build_db.py` reads each site's `schema.py`, creates SQL tables with NOT NULL defaults, inserts synthetic JSON data, then streams raw CSV/JSONL/XML in batches.

## Site Architecture

Each site is a Flask Blueprint with:

### routes.py
- All HTTP routes (HTML pages + JSON API endpoints)
- Data access through `db.query()`, `db.get_item()`, `db.execute()` — SQL-level filtering only
- Mutation routes use `db.save_item()` / `db.delete_item()`
- Template rendering with Jinja2

### schema.py
- Defines SQLite table schemas (columns, types, indexes, defaults)
- Auto-generated by `scripts/generate_schemas.py`, then hand-editable
- All columns have `NOT NULL DEFAULT` — no NULLs

### tasks.json
- 20 benchmark tasks per site
- Each task has a natural-language instruction, target macros, and verification criteria
- Tasks represent realistic user interactions

### verifiers.py / macro_verifiers.py
- Check whether an agent successfully completed a task
- Query backend state through the admin API or db module

## Evaluation Flow

```
1. Agent receives task instruction (natural language)
2. Agent interacts with site through browser (clicks, types, navigates)
3. Agent's mutations go to session_overlay (isolated)
4. Verifier checks backend state via /_admin/data/<site>/<collection>
5. Score: pass/fail per task, macro coverage per site
```

## Admin API

- `GET /_admin/data/<site>/<collection>` — query a collection (supports `?user_id=1&_count=1`)
- `GET /_admin/files/<site>` — list collections for a site
- `GET /_admin/user/<site>/<user_id>` — aggregate all data for a user
- `GET /_admin/log` — request log for current session
- `POST /_reset_data` — reset session to pristine state
- `GET /_overlay_stats` — session overlay statistics

## Cross-Site Bridges

`app/bridges.py` connects 14 sites through shared data:
- Banking transfers create email notifications
- Calendar events link to remote-calls meetings
- E-commerce orders create banking debits
- IM messages cross-reference with email

## Environment

- **Platform**: CHPC (University of Utah HPC cluster)
- **Storage**: `/scratch/general/vast/u1653932/` (VAST filesystem)
- **Data sources**: `/scratch/general/vast/u1653932/data_sources/`
- **Python**: 3.11 via miniforge3
- **DB builds**: Run on compute nodes via `salloc` (large datasets need 32GB+ RAM)
