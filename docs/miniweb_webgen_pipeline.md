# MiniWeb Site Generation Pipeline

How MiniWeb generates benchmark websites with verifiable tasks.

## Design Principle: Minimal but Real

Each site is **simple in fidelity, not simple in mechanics**. A thin Flask app — a handful of pages, small seed data, no production polish — but with a *genuine backend that holds real state*, because the state is what verifiers check. We deliberately drop infrastructure fidelity (real payment rails, WebRTC, live map tiles); we do **not** drop state. A "bank" is a few tables and a transfer form that updates balances; a "map" is a small fixed grid of POIs. The macro still fires, the verifier still has real state to read.

## Pipeline Overview

This pipeline follows the **WA-inf web generation** approach, which closes the loop between website generation and browser-agent evaluation. After initial generation and validation (via Flask test client), sites are evaluated by a real browser-use agent. Agent failures surface usability issues — broken navigation, unclear UI, missing affordances — that pure API-level validation misses. These findings feed back into iterative site refinement.

```
data/ + doc/  →  scaffold  →  generate  →  snapshot  →  validate  →  verify macros  →  browser-eval (×N)
                 (add_site.sh) (Claude Code) (pristine)   (ref solutions)  (macro_verifiers)  (browser-use agent)
                                                               ↑                                     │
                                                               └──────────── fix ←───────────────────┘
```

**Input**: User-provided raw data files in `data/` + site description in `doc/` + spec JSON.
**Output**: A complete `sites/<id>/` directory with routes (including data interpreter), templates, 20 tasks, verifiers, macro verifiers, and reference solutions — auto-discovered by Flask at startup.

## Site Setup (Before Pipeline)

Before running the generation pipeline, the user prepares the site:

### 1. Scaffold
```bash
./scripts/add_site.sh <site-id> "Site Name" "Description"
```
Creates `sites/<id>/` from `_template/` with `data/`, `doc/`, and `templates/<id>/` directories.

### 2. Populate `data/`
User places raw data files in `data/` in their **original format**. These files are never rewritten or reformatted by the pipeline. Examples:
- CSV files downloaded from an API
- JSON responses from a web service
- XML exports from a database

### 3. Write `doc/`
User writes description files in `doc/` explaining:
- What the website is (domain, purpose, target audience)
- How it uses the data files in `data/`
- What real-world website it should be modeled after
- Whether the domain has temporal/dynamic data (and how it should simulate)
- Any domain-specific behavior

The `doc/` description is **on top of** the base conventions (simple Flask app, macro-driven design). It does not need to repeat those.

## Spec Format

Specs live in `specs/*.json`. Structure:

```json
{
    "site_id": "news",
    "site_name": "DailyPulse News",
    "description": "A news portal with articles, categories, and social features",
    "domain": "dynamic/news",
    "tags": ["news", "articles", "media"],
    "num_tasks": 20,
    "entities": [...],
    "features": [...],
    "task_guidance": "Mix read-only lookups with write operations...",
    "target_macros": ["search_by_query", "filter_by_dropdown", "save_by_toggle", ...]
}
```

Key fields:
- **entities**: data models with fields and target record counts
- **features**: API endpoints the site must implement
- **target_macros**: macros from `MiniWeb_macro_assignment.xlsx` that tasks must exercise
- **task_guidance**: prose directing task design (difficulty mix, operation types)

## Pipeline Steps

### Step 1: Generate

Builds a generation prompt from:
- The site's `doc/` description (domain intent, data usage)
- The spec JSON (entities, features, macros)
- `academic-paper-db/` as the gold-standard reference (full pipeline complete)
- `bookstore/` as the minimal reference site

The prompt instructs Claude Code to produce:

1. **`routes.py`** — Flask blueprint with HTML + JSON API routes, including a **data interpreter** that reads raw data in its original format
2. **`templates/<id>/*.html`** — Jinja2 templates with UI modeled after a well-known real-world website in the domain
3. **`tasks.json`** — 20 realistic tasks (~6 easy, ~8 medium, ~6 hard) covering all target macros
4. **`verifiers.py`** — one `verify_*` function per task
5. **`macro_verifiers.py`** — one verifier per target macro (tests the macro works end-to-end)
6. **`reference_solutions.py`** — one `solve_*` function per task
7. **Temporal simulation** (if applicable) — simulation layer for time-varying data

**Critical**: The generator must NOT rewrite or reformat files in `data/`. It must write an interpreter in `routes.py` that reads the raw format.

### Step 2: Snapshot

```bash
python scripts/reset_site.py --snapshot <site-id>
```

Copies `data/*.json` → `data/.pristine/`, establishing the reset baseline.

### Step 3: Validate

```bash
python scripts/validate_site.py <site-id>
```

Per-task isolated validation:
1. **Reset** data to pristine state
2. **Solve**: run the reference solution via Flask test client → returns an answer
3. **Verify**: run the verifier via HTTP against the running server → `{"pass": bool, "detail": str}`
4. **Reset** data again (so write-tasks don't pollute the next task)

### Step 4: Verify Macros

Each target macro in the site's spec must pass its dedicated verifier in `macro_verifiers.py`. This ensures that every macro the site claims to support actually works end-to-end through the UI/API.

### Step 5: Browser-Eval Loop (×N, currently N=3)

```bash
python evaluation/run_eval.py --site <site-id> --model gemini-flash
```

Runs a browser-use agent against the site's tasks through a real browser. Agent failures reveal usability issues:
- **Navigation gaps**: pages that exist at API level but aren't linked from the UI
- **Missing affordances**: actions that require API calls but have no corresponding buttons or forms
- **Ambiguous UI**: instructions that are clear to a human reading the API but unclear when facing the rendered page
- **Broken workflows**: multi-step tasks where intermediate state isn't visible in the browser

When the agent fails tasks that validation passes, the site is refined and re-validated. This loop runs N times (currently 3).

## Data Interpreter Pattern

The data interpreter in `routes.py` bridges raw data files and Flask routes. Example:

```python
# Raw data is CSV with columns: Symbol,Price,Change,Volume
import csv

def _load_assets():
    """Interpreter: reads raw CSV, returns list of dicts for routes."""
    with open(DATA_DIR / "prices.csv") as f:
        reader = csv.DictReader(f)
        return [
            {
                "id": i,
                "symbol": row["Symbol"],
                "price": float(row["Price"]),
                "change": float(row["Change"]),
                "volume": int(row["Volume"]),
            }
            for i, row in enumerate(reader, 1)
        ]
```

The raw `prices.csv` is never modified. The interpreter handles format translation at runtime.

### Respecting `config/config.json`

The interpreter must read `config/config.json` to determine how many data points to load:

```python
import json

def _load_config():
    config_path = SITE_DIR / "config" / "config.json"
    with open(config_path) as f:
        return json.load(f)

def _load_assets():
    config = _load_config()
    n = config.get("num_data_points", -1)  # -1 = load all
    seed = config.get("random_seed", 42)
    # ... sample n records deterministically using seed ...
```

This allows adjusting dataset size without modifying code or data files.

## Temporal Simulation

Sites with time-varying domains (stocks, weather, news, sports) must implement a simulation layer. The simulation should be:

- **Deterministic**: same seed + same simulated time = same data
- **Reproducible**: resets cleanly to baseline
- **Domain-appropriate**: stock tickers vs. weather forecasts vs. news feeds

The simulation mechanism is described in the site's `doc/` folder and implemented in `routes.py`.

## Task Format

Each entry in `tasks.json`:

```json
{
    "task_id": "news_-003",
    "difficulty": "easy",
    "instruction": "Search for articles about 'climate'. How many results are there?",
    "expected_answer": "5",
    "verifier": "verify_news_003",
    "reference_solution": "solve_news_003",
    "macros": ["search_by_query"]
}
```

- **Easy**: single API call, read-only (lookup, count, filter)
- **Medium**: multi-step reads, computation, cross-entity joins
- **Hard**: write operations (create, update, delete) + verify mutation persisted
- **Realistic**: tasks must represent things a real user would actually do on the site

## Verifier Format

Verifiers check backend state via HTTP — never browser content:

```python
def verify_news_003(server_url):
    """Count climate articles."""
    r = requests.get(f"{server_url}/sites/news/api/articles/search?q=climate")
    articles = r.json()
    count = len(articles)
    return {"pass": count == 5, "detail": f"Expected 5, got {count}"}
```

Two categories:
- **Extraction verifiers**: deterministic answer from seed data (compare against expected)
- **Mutation verifiers**: check a state change via GET after a POST/PUT/DELETE

## Macro Verifier Format

Each target macro gets its own verifier in `macro_verifiers.py`:

```python
def verify_macro_search_by_query(server_url):
    """Verify search_by_query macro works end-to-end."""
    r = requests.get(f"{server_url}/sites/news/api/articles/search?q=climate")
    assert r.status_code == 200
    results = r.json()
    return {"pass": len(results) > 0, "detail": f"search_by_query returned {len(results)} results"}
```

## Running the Full Pipeline

```bash
# All steps in sequence
python scripts/generate_site.py specs/<site-id>.json

# Single step only
python scripts/generate_site.py specs/<site-id>.json --step validate

# Auto-invoke Claude Code for generation
python scripts/generate_site.py specs/<site-id>.json --auto

# Validate only (no spec needed)
python scripts/validate_site.py <site-id>

# Reset all sites to pristine
python scripts/reset_site.py --all
```
