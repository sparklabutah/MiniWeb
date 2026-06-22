# MiniWeb

A lightweight, self-contained web platform for agentic benchmarking. One Flask process serves a search portal and any number of mini-sites, each with its own pages, JSON data, and verifiable tasks.

**163 macros** from 4 web-agent datasets

## Quick Start

### Option A: Python (no Docker)

```bash
pip install -r requirements.txt
python run.py
```

Open [http://localhost:8080](http://localhost:8080).

### Option B: Docker

```bash
docker build -t miniweb .
docker run -p 8080:8080 miniweb
```

## Project Structure

```
MiniWeb/
├── run.py                      # Entry point
├── requirements.txt            # Flask
├── Dockerfile                  # Optional container
├── app/
│   ├── __init__.py             # Auto-discovers sites and mounts blueprints
│   ├── portal/                 # Search homepage
│   └── static/                 # Shared CSS
├── sites/
│   ├── _template/              # Copy to create a new site
│   ├── academic-paper-db/      # Full reference site (20 tasks, 21 macros)
│   ├── bookstore/              # Minimal template (no tasks)
│   └── <site-id>/              # Each site contains:
│       ├── site.json           #   Metadata
│       ├── doc/                #   User-written site description
│       ├── config/config.json  #   Site config (num_data_points, etc.)
│       ├── routes.py           #   Flask blueprint (with data interpreter)
│       ├── data/               #   Raw data (original format, never rewritten)
│       ├── data/.pristine/     #   Immutable reset baseline
│       ├── templates/<id>/     #   Jinja2 templates
│       ├── tasks.json          #   20 benchmark tasks
│       ├── verifiers.py        #   Per-task verification
│       ├── macro_verifiers.py  #   Per-macro verification
│       └── reference_solutions.py  # Per-task solutions
├── specs/                      # Site generation specs (JSON)
├── scripts/                    # Generation & validation tools
├── evaluation/                 # Browser-agent evaluation harness
├── macros/                     # Macro research pipeline
└── docs/                       # Documentation
```

## How It Works

At startup, `app/__init__.py` scans `sites/*/site.json` and auto-registers each site as a Flask Blueprint mounted at `/sites/<id>/`. The portal at `/` reads all `site.json` files to build a searchable index.

No config files to edit. No routing to update. Just drop a folder and restart.

## Adding a New Site

### 1. Scaffold + prepare data and docs

```bash
./scripts/add_site.sh my-site "My Site Name" "A short description"
```

Then:
- Place raw data files in `sites/my-site/data/` (keep original format — never rewrite)
- Write site description in `sites/my-site/doc/` (what the site is, how it uses the data, what real-world site to model after, temporal dynamics if any)

### 2. Generate and validate

```bash
python scripts/generate_site.py specs/my-site.json
python scripts/validate_site.py my-site
```

### 3. Browser-eval loop (×N)

```bash
python evaluation/run_eval.py --site my-site --model gemini-flash
```

Run N times (currently 3), fixing issues between rounds.

See [docs/miniweb_webgen_pipeline.md](docs/miniweb_webgen_pipeline.md) for the full pipeline.

## Key Design Principles

- **Original data format preserved**: Raw data in `data/` is never rewritten. `routes.py` contains a data interpreter that reads the raw format at runtime.
- **Temporal simulation**: Sites with time-varying domains (stocks, weather, news) must simulate data changes over time.
- **Macro-driven**: Every site implements a set of target macros, each with a dedicated verifier.
- **Realistic tasks**: Tasks represent things a real user would actually do on the site.
- **Self-contained sites**: Each site directory is fully isolated with all code, data, and templates.

## Evaluation

Run browser agents against benchmark tasks:

```bash
pip install -r evaluation/requirements.txt
python evaluation/run_eval.py --site my-site --model gemini-flash
```

The agent receives only the natural-language instruction and interacts with the rendered UI through a real browser. Verifiers check backend state after each task.

See [AGENTS.md](AGENTS.md) for supported models, CLI flags, and how to add new agents.

## API

### Portal

- `GET /` — search homepage
- `GET /api/sites` — list all sites (optional `?q=` filter)

### Per-site

Each site defines its own routes under `/sites/<id>/`. See the site's `routes.py` for available endpoints.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on adding sites, submitting PRs, and code style.
