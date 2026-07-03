# MiniWeb

A web platform for benchmarking browser-agent AI systems. One Flask process serves 65 realistic websites — banking, forums, e-commerce, email, and more — each backed by real-world data (arxiv, reddit, StackExchange, Wikipedia) totaling 11M+ records in SQLite. Agents receive natural-language instructions and interact with rendered HTML; verifiers check backend state to score success.

## Quick Start (CHPC)

### 1. Clone and set up environment

```bash
cd /scratch/general/vast/$USER/projects
git clone <repo-url> MiniWeb
cd MiniWeb

# Create conda environment
module load miniforge3
conda create -n miniweb-eval python=3.11 -y
conda activate miniweb-eval
pip install -r requirements.txt
```

### 2. One-time setup (CHPC shortcut)

If you're in the `kmarino` group on CHPC, run the setup script — it creates the conda env, symlinks the shared database (~18GB), and prepares `.env`:

```bash
bash scripts/setup_chpc.sh
```

Or set up manually:

```bash
# Symlink the shared database (read-only, no download needed)
ln -s /scratch/general/vast/u1653932/data_sources/miniweb.db miniweb.db

# Or set via environment variable
export MINIWEB_DB=/scratch/general/vast/u1653932/data_sources/miniweb.db
```

### 3. Set up API keys (optional)

For AI-powered features (chatbot, translation):
```bash
echo 'OPENAI_API_KEY=sk-your-key-here' > .env
```

### 4. Run the app

```bash
conda activate miniweb-eval
python run.py
# Open http://localhost:8080
```

For running on a CHPC interactive node with port forwarding:
```bash
# On your local machine:
ssh -L 8080:localhost:8080 <username>@notchpeak.chpc.utah.edu

# On CHPC:
cd /scratch/general/vast/$USER/projects/MiniWeb
conda activate miniweb-eval
python run.py
```

### 5. Rebuilding the database (optional)

Only needed if you want to rebuild from raw data sources:
```bash
# On a compute node (large datasets need RAM + I/O):
srun --ntasks=1 --mem=32G --time=2:00:00 --account=kmarino --partition=notchpeak \
    python scripts/build_db.py --force

# Build FTS5 search indexes (can run separately):
python scripts/build_fts.py
```

## Project Structure

```
MiniWeb/
├── run.py                          # Entry point
├── CLAUDE.md                       # Development rules (read before contributing)
├── miniweb.db                      # SQLite database (all site data, ~12GB)
│
├── app/
│   ├── __init__.py                 # Flask app factory, blueprint registration, admin API
│   ├── db.py                       # Database access layer (query, get_item, save_item, search)
│   ├── events.py                   # Cross-site event bus (emit/on pattern)
│   ├── bridges.py                  # Backward-compatible event wrappers
│   ├── handlers/                   # Event handlers (banking, email, calendar, IM, cloud, passwords)
│   ├── portal/                     # Browser chrome + new tab page with search
│   └── static/                     # Shared CSS, generated tiles
│
├── sites/<site-id>/                # 65 self-contained sites
│   ├── site.json                   # Metadata (name, description, category)
│   ├── schema.py                   # SQLite table definitions
│   ├── routes.py                   # Flask blueprint (routes + SQL queries)
│   ├── templates/<site-id>/        # Jinja2 HTML templates
│   ├── tasks.json                  # 20 benchmark tasks
│   ├── verifiers.py                # Task success verification
│   ├── macro_verifiers.py          # Per-macro verification
│   └── reference_solutions.py      # Known-good solutions
│
├── scripts/
│   ├── build_db.py                 # Build miniweb.db from raw data (special ingestors)
│   ├── build_fts.py                # Build FTS5 full-text search indexes
│   ├── generate_schemas.py         # Auto-generate schema.py from data files
│   ├── extract_wiki_sample.py      # Extract Wikipedia articles from ZIM (compute node)
│   ├── extract_osm_portland.py     # Extract POIs from OpenStreetMap
│   ├── precompute_all_routes.py    # Pre-compute OSRM routes (compute node)
│   └── data_prep/                  # Per-site data preparation
│
├── annotation/                     # Human annotation + evaluation interface
├── miniweb.db -> data_sources/     # Symlink to SQLite database (~18GB)
└── docs/
    └── ARCHITECTURE.md             # Full architecture documentation
```

## How It Works

### Data Flow

```
Synthetic JSON + Raw data (CSV/JSONL/XML)
              |
         build_db.py (merged into same tables)
              |
         miniweb.db (per-site tables, NOT NULL defaults, no NULLs)
              |
         Flask routes.py — db.query() with SQL WHERE/ORDER BY/LIMIT
              |
         Jinja2 templates → HTML → Browser Agent
```

1. **Build**: `build_db.py` reads synthetic JSON + raw CSV/JSONL/XML and inserts both into the same per-site tables. All columns have NOT NULL defaults — no NULLs anywhere.
2. **Serve**: Each site's `routes.py` queries its tables through `app/db.py` — all filtering, sorting, and pagination happens in SQL. Only the ~50 rows visible on the page are fetched.
3. **Mutate**: Agent actions (transfers, posts, edits) are stored in a per-session overlay, never modifying base data.
4. **Verify**: After the agent finishes, verifiers check backend state through the admin API.

### Database

All data lives in `miniweb.db` (~18GB) with 350+ per-site tables + FTS5 indexes. Examples:

| Table | Rows | Source |
|-------|------|--------|
| `forums_posts` | 127K | reddit CSV |
| `forums_comments` | 1M | reddit CSV |
| `academic_paper_db_papers` | 1M | arxiv JSONL |
| `qa_knowledge_questions` | 1M | StackExchange XML |
| `flights_hotels_hotels` | 1M | kaggle CSV |
| `banking_transactions` | 220 | synthetic |

Sites query data through `app/db.py`:

```python
from app import db

# SQL-level filtering, sorting, pagination
txns = db.query("banking", "transactions",
                where={"user_id": 1}, sort="-date", limit=30)

# Single item
user = db.get_item("banking", "users", 1)

# Raw SQL for complex queries
rows = db.execute(
    "SELECT * FROM forums_posts WHERE subreddit=? ORDER BY score DESC LIMIT 30",
    ("science",)
)
```

### Session Isolation

Each browser session gets isolated mutations. When an agent transfers money or posts a comment, the change goes to `session_overlay`, not the base table. Multiple agents can run in parallel without interference. `POST /_reset_data` reverts to pristine state.

## Sites

65 sites across 14 categories:

| Category | Sites |
|----------|-------|
| Financial | banking, brokerage, insurance-loans, crowdfunding |
| Communication | email, instant-messaging, remote-calls, team-chat, dating |
| Social Media | forums, multimedia-posting, rating-review |
| Shopping | e-commerce, auctions, flights-hotels, ticketing-events, real-estate |
| Productivity | calendar-todo, documents, spreadsheets, project-mgmt, CRM, cloud-storage |
| Dynamic Info | news, blogs, weather, sports-esports |
| Streaming & Media | music, video, live, podcasts-audiobooks, books-comics |
| Government | agency-portals, tax-filing, petitions-voting |
| Health | health-portals, health-fitness-tracking |
| Education | course-sites, conference-review, visual-how-to-guides |
| Maps & Navigation | map-services, transit-directions |
| Utilities | password-managers, converters, translation, url-shorteners |
| Technology | ai-chatbots, code-editor, software-marketplace |
| Other | design-creative, personal-portfolio, handwritten-notes, and more |

### Cross-Site Integration

Sites are connected via a centralized event bus (`app/events.py`):
- **Purchases** → banking debit + confirmation email + 2FA verification
- **Bookings** → calendar event + email
- **Signups** → welcome email + password manager entry
- **File creation** → cloud storage sync
- **Messages** → instant messaging

All financial transactions support account selection (checking/credit) with email-based 2FA.

## Evaluation

```bash
python evaluation/run_eval.py --site banking --model gemini-flash
```

The agent receives a natural-language instruction, interacts with the site through a real browser, and verifiers check whether the task was completed correctly.

See [AGENTS.md](AGENTS.md) for supported models and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for full technical details.

## Admin API

For verification and debugging:

- `GET /_admin/data/<site>/<collection>` — query data (supports `?user_id=1&_count=1`)
- `GET /_admin/files/<site>` — list collections
- `GET /_admin/user/<site>/<user_id>` — all data for a user
- `POST /_reset_data` — reset session to pristine
- `GET /_admin/log` — request log

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and read [CLAUDE.md](CLAUDE.md) before writing code.
