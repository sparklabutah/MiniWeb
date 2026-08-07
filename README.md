# MiniWeb

A web benchmark for evaluating browser-agent AI systems. One Flask process serves 65 realistic websites — banking, forums, e-commerce, email, and more — each backed by real-world data totaling 14M+ records in SQLite. Agents receive natural-language instructions and interact with rendered HTML; an LLM judge scores success against annotator-defined expected outcomes.

## Quick Start

```bash
pip install -r requirements.txt
python run.py
# Open http://localhost:8080
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `MINIWEB_DB` | Yes | Path to SQLite database file |
| `SECRET_KEY` | Production | Session cookie encryption key |
| `MINIWEB_ANNOTATIONS_DIR` | No | Path to annotations (default: `./data/annotations`) |
| `MINIWEB_ANNOTATORS` | No | Login credentials: `user1:pass1,user2:pass2` |
| `MINIWEB_NO_AUTOLOGIN` | No | Set `1` to disable auto-login (for eval) |

### Docker

```bash
docker build -t miniweb .
docker run -v /path/to/miniweb.db:/app/miniweb.db -p 8080:8080 miniweb
```

### Railway Deployment

The app is configured for Railway with `Procfile` and `Dockerfile`. Mount the DB as a persistent volume and set env vars in the Railway dashboard.

## Architecture

```
65 sites (Flask blueprints) ─── SQLite (14M rows) ─── Jinja2 templates ─── Browser
      │                              │
      ├── Session overlay ───── Per-session mutations (isolated)
      ├── Admin API ─────────── /_admin/data/<site>/<collection>
      ├── Event bus ─────────── Cross-site actions (payments, emails, bookings)
      └── 2FA ───────────────── /verify-payment (email-based codes)
```

### Sites (65)

Each site is a self-contained Flask blueprint under `sites/<id>/`:

| Category | Count | Examples |
|----------|-------|---------|
| Productivity | 8 | calendar-todo, documents, spreadsheets, CRM, cloud-storage |
| Shopping & Transactional | 8 | e-commerce, auctions, flights-hotels, ticketing-events |
| Communication | 6 | email, instant-messaging, remote-calls, team-chat |
| Search & Reference | 5 | qa-knowledge, wikis, dictionaries, comparison-aggregators |
| Streaming & Media | 5 | music, video, live, podcasts-audiobooks, books-comics |
| Static & Informational | 5 | news, blogs, business-company, personal-portfolio |
| Utilities | 5 | password-managers, converters, translation, url-shorteners |
| Financial | 2 | banking, brokerage |
| + 8 more categories | 21 | ... |

### Macro System (121 canonical macros)

Macros are primitive UI skills that agents must perform, defined in the canonical registry `data/macros.yaml` (see `docs/macro_system.md` for the two-axis model). Each macro is tagged with a difficulty category:

| Category | Macros | Weight | Description |
|----------|--------|--------|-------------|
| Spatial control | 28 | 5.0x | Sliders, date pickers, drag, pan/zoom |
| Reasoning | 8 | 8.0x | Extract, compute, compare values |
| State change | 16 | 4.0x | Create, edit, delete via forms |
| Media | 7 | 4.0x | Upload, playback controls |
| Text input | 50 | 1.5x | Search, type, query-based |
| Simple select | 48 | 1.0x | Dropdowns, toggles, radio buttons |
| Trivial | 12 | 0.5x | Navigation, auth |

### Database

SQLite with 362 tables, 14.4M rows, ~17GB. Key tables:

| Table | Rows | Source |
|-------|------|--------|
| `classifieds_listings` | 2M | Craigslist |
| `health_fitness_tracking_foods` | 1.8M | USDA |
| `qa_knowledge_questions` | 1M | StackExchange |
| `forums_comments` | 1M | Reddit |
| `academic_paper_db_papers` | 1M | arXiv |
| `job_sites_jobs` | 1M | Indeed |

### Annotation System

Access at `/annotate/` (requires login). Features:
- Task design with macro sampling weighted by difficulty
- Trajectory recording with HTML snapshots and accessibility trees
- QA answer fields for extract/compute macros
- Ambiguous instruction generation via LLM
- Trajectory playback in verify dashboard
- 2FA disable toggle for transaction tasks

### Evaluation

```bash
# Run annotated tasks with Claude CLI agent
python evaluation/run_annotated.py --model claude-cli --timeout 300

# With ambiguous instructions
python evaluation/run_annotated.py --model claude-cli --ambiguous

# With Groq Llama
python evaluation/run_annotated.py --model groq --timeout 300

# Specific task
python evaluation/run_annotated.py --model claude-cli --task-id crm_bf9346
```

Supported models: `claude-cli` (Claude Opus), `groq` (Llama 4 Scout), `groq-70b` (Llama 3.3 70B), `mock` (pipeline testing).

## Admin API

| Endpoint | Description |
|----------|-------------|
| `GET /_admin/data/<site>/<collection>` | Query data with filters |
| `GET /_admin/files/<site>` | List collections |
| `GET /_admin/user/<site>/<user_id>` | All data for a user |
| `POST /_reset_data` | Reset session to pristine |
| `GET /_admin/log` | Request log |
| `GET /_admin/session` | Current session state |

## Project Structure

```
MiniWeb/
├── run.py                    # Entry point
├── app/
│   ├── __init__.py           # App factory, admin API, script injection
│   ├── db.py                 # Database layer (query, search, overlay)
│   ├── events.py             # Cross-site event bus + 2FA
│   ├── bridges.py            # Event wrappers (payments, bookings)
│   ├── handlers/             # Event handlers (banking, email, calendar, IM)
│   ├── portal/               # Browser chrome UI with tabs
│   └── static/               # recorder.js, file-picker.js, export-feedback.js
├── sites/<site-id>/          # 65 self-contained sites
│   ├── site.json             # Metadata
│   ├── schema.py             # SQLite table definitions
│   ├── routes.py             # Flask blueprint
│   ├── templates/<site-id>/  # Jinja2 templates
│   └── tasks.json            # Legacy benchmark tasks
├── annotation/               # Annotation interface
│   ├── app.py                # Blueprint, macro sampling, auth, APIs
│   ├── storage.py            # File-based task storage
│   ├── macro_locations.py    # Per-site macro-to-UI mapping (source of truth)
│   └── macro_difficulty.py   # Difficulty categories and sampling weights
├── evaluation/               # Agent evaluation
│   ├── run_annotated.py      # Run annotated tasks with LLM judge
│   ├── agents.py             # BrowserUseAgent, MockAgent, ChatClaude
│   ├── judge.py              # LLM-as-judge evaluator
│   └── tasks.py              # Task loading and verification
├── scripts/
│   ├── trim_db.py            # Trim DB for deployment (~18GB → ~4GB)
│   ├── build_db.py           # Build DB from raw data (DO NOT re-run)
│   └── build_fts.py          # Build FTS5 search indexes
└── data/annotations/         # Saved annotation tasks and trajectories
```
