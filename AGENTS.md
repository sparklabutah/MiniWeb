# AGENTS.md

Guidance for Coding agents (Claude Code, Codex, ...) when working in this repository.

## Quick Start

```bash
pip install -r requirements.txt
python run.py
# Runs on http://localhost:8080
```

Docker alternative: `docker build -t miniweb . && docker run -p 8080:8080 miniweb`

No test suite or linter configured.

## Architecture

MiniWeb is a Flask app that auto-discovers and hosts isolated "mini-sites" under a shared search portal, designed for agentic web benchmarking.

**Entry point**: `run.py` → `create_app()` in `app/__init__.py`:
1. Registers the portal blueprint (`app/portal/routes.py`) at `/`
2. `discover_sites()` scans `sites/*/site.json` (skips `_` prefixes) for metadata
3. `register_site_blueprints()` dynamically imports each site's `routes.py` and mounts at `/sites/<id>/`

**Portal**: `GET /` (homepage), `GET /api/sites?q=` (JSON search)

**Key rule**: Sites auto-discover at startup. Drop a directory with `site.json` + `routes.py` — no manual registration needed.

## Site Structure

Each site under `sites/<id>/` is a self-contained Flask blueprint:

| File/Dir | Purpose |
|----------|---------|
| `site.json` | Metadata: id, name, description, tags |
| `doc/` | User-written description of the site and how it uses the data |
| `data/` | Raw data files in their **original format** (user-provided, never rewritten) |
| `data/.pristine/` | Immutable baseline snapshot (for reset) |
| `config/config.json` | Site configuration (num_data_points, random_seed, etc.) |
| `routes.py` | Blueprint with HTML + JSON API routes, including **data interpreter** |
| `templates/<id>/` | Jinja2 templates (site-scoped) |
| `tasks.json` | 20 construction-time validation tasks (easy/medium/hard) |
| `verifiers.py` | Per-task HTTP verification functions |
| `macro_verifiers.py` | Per-macro verification functions (one per target macro) |
| `reference_solutions.py` | Per-task solutions via Flask test client |

**Note on tasks**: The `tasks.json` generated during site construction exists to validate that the site works correctly during the build process. These are **not** the final benchmark tasks. The actual evaluation tasks will be generated via a separate macro-driven task generation pipeline (not yet defined).

**Reference sites**: `academic-paper-db/` is the full reference pattern (20 tasks, 21 macros verified, browser-eval complete). `bookstore/` is the minimal template example (no tasks). `_template/` is the scaffold starter.

## Data Handling: Original Format + Interpreter

**Critical rule**: Raw data files placed in `data/` by the user must **never be rewritten or reformatted**. They stay in whatever format they arrive in (CSV, nested JSON, API response format, XML, etc.).

Instead, `routes.py` must contain a **data interpreter layer** that:
1. Reads raw data files in their original format
2. Transforms/adapts data at runtime for Flask routes and templates
3. Handles any format-specific parsing (date formats, nested structures, etc.)

This keeps the data provenance clean and allows the same raw data to be reused or inspected independently.

## Site Configuration

Each site has a `config/config.json` that controls runtime parameters:

```json
{
    "num_data_points": -1,
    "random_seed": 42
}
```

- **`num_data_points`**: How many records to load from the raw data. `-1` means load all records (default). A positive number means sample that many records deterministically. The data interpreter in `routes.py` reads this value and uses reservoir sampling when a limit is set, allowing the same raw data to be used at different scales without modifying the source files.
- **`random_seed`**: Seed for deterministic sampling, ensuring reproducibility.

Sites may add additional config keys as needed for domain-specific settings. The interpreter must read `config/config.json` at startup and respect its values.

## Temporal Simulation

Sites whose domain involves **time-varying data** (stock prices, weather forecasts, news feeds, sports scores, etc.) must implement a **temporal simulation layer**. Static JSON snapshots are not acceptable for dynamic-domain sites.

The simulation mechanism should:
- Allow data to change as simulated time progresses
- Be appropriate to the site's domain (e.g., price ticker for stocks, forecast updates for weather)
- Be deterministic and reproducible (same seed/time → same data)
- Support reset to baseline state

The exact implementation (simulated clock, time-step ticker, etc.) is domain-specific and should be described in the site's `doc/` folder.

## Adding a New Site

### Workflow

1. **Scaffold**: `./scripts/add_site.sh <site-id> ["Site Name"] ["Description"]` — creates `sites/<id>/` from `_template/` with `data/` and `doc/` folders
2. **Populate data**: User places raw data files in `data/` (original format, not rewritten)
3. **Write description**: User writes `doc/` files describing the site, its domain, how it uses the data, and any temporal dynamics. This is **on top of** the base conventions (simple Flask app, macros)
4. **Generate**: Pipeline builds a prompt from `doc/` + spec + reference sites (`academic-paper-db/` as gold standard, `bookstore/` as minimal example), then Claude Code produces all site files (routes with data interpreter, templates, tasks, verifiers, macro verifiers)
5. **Snapshot**: `reset_site.py --snapshot` saves `data/*.json` → `data/.pristine/`
6. **Validate**: `validate_site.py` runs each task in isolation: reset → solve → verify → reset
7. **Verify macros**: Each target macro must pass its dedicated verifier in `macro_verifiers.py`
8. **Browser-eval loop** (N iterations, currently 3): Run browser-use agent, identify failures, fix site, re-validate. Repeat N times.

```bash
# Full pipeline
python scripts/generate_site.py specs/<site-id>.json

# Individual steps
python scripts/generate_site.py specs/<site-id>.json --step validate
python scripts/validate_site.py <site-id>
python scripts/reset_site.py <site-id>  # or --all
```

See `docs/miniweb_webgen_pipeline.md` for the pipeline spec and `CONTRIBUTING.md` for the step-by-step walkthrough.

### Pipeline Requirements

- **Data interpreter**: `routes.py` must read raw data in its original format — never rewrite the source files
- **Temporal simulation**: If the site domain has dynamic data, implement a simulation layer
- **Macro verifiers**: Every macro in `target_macros` must have a verifier in `macro_verifiers.py`
- **Realistic tasks**: Tasks must represent things a real user would actually do on that type of website
- **Browser-use iterations**: Site must be refined through N browser-agent evaluation rounds (currently N=3)
- **Site design**: UI/UX should be modeled after a well-known real-world website in the same domain

## Evaluation Harness

Browser-agent evaluation using real browsers against site tasks.

The evaluation harness in `evaluation/` runs an LLM-backed browser agent against a site's tasks, then verifies results using the site's `verifiers.py`. The agent receives **only the natural-language instruction** — no expected answers, no verifier code, no reference solutions. It interacts with the rendered UI through a real browser.

### Eval Quick Start

```bash
# Install evaluation dependencies
pip install -r evaluation/requirements.txt

# Set API keys in .env
echo "GOOGLE_API_KEY=..." >> .env
echo "OPENAI_API_KEY=..." >> .env
echo "ANTHROPIC_API_KEY=..." >> .env

# Run evaluation
python evaluation/run_eval.py --site <site-id> --model gemini-flash
```

### Supported Models

| Key | Model | Provider |
|-----|-------|----------|
| `gemini-flash` | Gemini 3 Flash Preview | Google |
| `gemini-pro` | Gemini 3 Pro Preview | Google |
| `gpt` | GPT-4o | OpenAI |
| `gpt-5.4` | GPT-5.4 | OpenAI |
| `claude` | Claude Sonnet 4.6 | Anthropic |

Models are defined in `AGENT_FACTORIES` in `evaluation/run_eval.py`.

### CLI Reference

```bash
python evaluation/run_eval.py \
    --site <site-id>         # Required. Site to evaluate
    --model <key>            # LLM backend (default: gemini-flash)
    --task-id <ids>          # Comma-separated task IDs to run (default: all)
    --difficulty <level>     # Filter: easy, medium, or hard
    --workers <n>            # Parallel browser instances (default: 1)
    --repetitions <n>        # Attempts per task (default: 1)
    --max-steps <n>          # Agent step limit (default: 50)
    --use-vision             # Enable screenshot-based reasoning
    --no-headless            # Show browser window (for debugging)
    --port <n>               # MiniWeb server port (default: 8080)
```

### How a Task Runs

1. MiniWeb server starts on the specified port
2. Browser agent navigates to `/sites/<site-id>/`
3. Agent receives **only** the task instruction (natural language)
4. Agent interacts with the rendered UI (clicks, types, navigates)
5. After the agent finishes (or times out at 600s), the verifier checks backend state via HTTP
6. Result: PASS, FAIL, TIME (timeout), or ERR (crash)

**Key difference from `validate_site.py`**: Evaluation uses a real browser (unprivileged UI access). Validation uses the Flask test client (privileged API access). Evaluation does NOT reset data between tasks.

### Output Format

Results are saved to `sites/<site-id>/results/<model>_<timestamp>/`:

```
results/gemini-flash_20260618_143000/
├── results.json          # Aggregate: pass rates by difficulty
├── <site-id>_-001/
│   └── result.json       # Per-task: passed, elapsed, steps, errors
└── ...
```

### Eval Architecture

| File | Purpose |
|------|---------|
| `run_eval.py` | Orchestrator: starts server, dispatches tasks to async workers, aggregates results |
| `agents.py` | `AgentRunner` protocol + `BrowserUseAgent` implementation |
| `tasks.py` | Task loading, filtering, verifier execution |
| `server.py` | Flask server lifecycle (start/stop/wait) |

### Adding a New Agent

Implement the `AgentRunner` protocol from `evaluation/agents.py`:

```python
@runtime_checkable
class AgentRunner(Protocol):
    async def setup(self, server_url: str) -> None:
        """One-time setup (e.g. start browser)."""
        ...

    async def run(self, task: str, server_url: str, task_dir: Path) -> AgentResult:
        """Execute a single task. Save artifacts to task_dir."""
        ...

    async def teardown(self) -> None:
        """Release resources (e.g. close browser)."""
        ...
```

`AgentResult` is a dataclass with: `elapsed`, `steps`, `is_done`, `final_result`, `errors`.

## Macros

### What is a Macro?

A **macro** is the smallest unit of web interaction that carries a distinct, recurring **intent**. It sits between a mechanical action (click a button) and a full task (log in, then buy an item). Every macro is named `verb_modifier` in snake_case — e.g., `search_by_query`, `filter_by_dropdown`, `extract_by_route`.

| Level | Example | Description |
|-------|---------|-------------|
| Atomic Action | Click "Submit" | Too small — just UI mechanics |
| **Macro** | `search_by_query` | The sweet spot — one clear intent |
| Task | Search, filter, then extract a price | Too big — a chain of macros |

A valid macro must pass three tests:
1. **Single intent** — one goal, phrased as verb + target + modifier
2. **One terminal state** — a single, verifiable outcome
3. **Indivisible intent** — splitting it yields only bare atomic actions

The **verb** names the goal (navigate, search, filter, extract, submit, etc.). The **modifier** names how the target is defined (by_query, by_dropdown, by_route, by_semantic, by_toggle, etc.). Macros live on the **intent axis** — never UI mechanics. See `docs/macros_def.md` for the authoritative definition.

### Macros as an Evaluation Axis

Macros are the core evaluation axis for MiniWeb. Traditional web-agent benchmarks report a single aggregate pass rate, but this tells you nothing about *which capabilities* an agent has or lacks. Macros decompose evaluation along the intent dimension: instead of "the agent passed 14/20 tasks," you can say "the agent succeeds at `search_by_query` and `filter_by_dropdown` but fails at `extract_by_semantic` and `post_from_free_text`."

This is why MiniWeb sites are built to support a defined set of macros:

- Each site spec declares a `target_macros` list — the macros the site must exercise
- Sites are constructed with UI affordances that make each target macro possible
- Evaluation results can be sliced by macro to produce per-macro pass rates across agents

The macro bank provides a **closed, unified vocabulary** induced from 4 existing benchmarks (WebArena, Mind2Web, WebShop, WebVoyager). By building sites against this vocabulary, MiniWeb ensures its tasks are grounded in real-world interaction patterns, and results are comparable across sites and agents.

### Macros in Site Generation

The `target_macros` field in a site spec drives site design:

1. **Site design**: the site must implement UI affordances that make each target macro possible (e.g., a search bar for `search_by_query`, a category dropdown for `filter_by_dropdown`, a toggle for `save_by_toggle`)
2. **Macro verification**: every target macro must have a dedicated verifier in `macro_verifiers.py` that tests the macro works end-to-end
3. **Construction-time tasks**: during generation, 20 tasks are created to validate the site works — these cover the target macros but are scaffolding, not final benchmark tasks
4. **Task verification**: verifiers check the outcome of the macro's intent (e.g., after `save_by_toggle`, the item appears in the user's saved list)

Macro assignments per site subcategory are human-refined in `MiniWeb_macro_assignment.xlsx`, then encoded as `target_macros` in each spec.

### Macro-Driven Task Generation (Planned)

The final benchmark tasks will be generated via a separate macro-involved pipeline (not yet defined). This pipeline will use the macro vocabulary to systematically produce tasks with controlled macro coverage, replacing the construction-time tasks for evaluation purposes.

### Macro Research Pipeline

The macro vocabulary is derived from the macro research pipeline, independent of the Flask app. Lives in `macros/pipeline/`. Current artifact: **163 macros** (18 verbs × 42 modifiers) over **15,728 tasks** from 4 benchmarks. Significant human refinement and addition is performed after the auto generation process.

- `docs/macros_def.md` — authoritative, frozen definition of what a "macro" is
- `docs/macros_pipeline.md` — master directive for the extraction pipeline
Verb/modifier vocabularies are closed registries with status tiers: `seed` → `proposed` → `established`.

## Conventions

- **Conda env `miniweb-eval`** has `openpyxl`, `pandas`, `numpy`, `matplotlib`. Use `conda run -n miniweb-eval python ...` for those deps.
- `academic-paper-db` is the full reference site (20 tasks, 21 macros, browser-eval 80%). `bookstore` is the minimal template (no tasks). `_template` is excluded from discovery.
- `data/.pristine/` directories are committed — they are the reset baselines for evaluation.
- `macros/legacy/` is superseded by `macros/pipeline/`. Source datasets in `macros/datasets/`.
- `MiniWeb_macro_assignment.xlsx` has per-subcategory macro assignments (human-refined).
