# Contributing to MiniWeb

## Site Status

| Site | Category | Desc | Built | Eval |
|------|----------|------|-------|------|
| academic-paper-db | Search & reference | yes | yes | yes |
| agency-portals | Government / civic | yes | yes | yes |
| ai-chatbots | Communication | yes | yes | |
| auctions-p2p-marketplaces | Shopping & transactional | yes | yes | |
| banking | Financial | yes | yes | |
| blogs | Dynamic info / feeds | yes | yes | |
| books-comics | Streaming & media | yes | yes | |
| bookstore | (template) | | | |
| brokerage | Financial | yes | yes | |
| business-company | Static / informational | yes | yes | |
| calendar-todo | Productivity | yes | yes | |
| classifieds | Social media | yes | yes | |
| cloud-dev-consoles | Productivity | yes | yes | |
| cloud-storage-file-transfer | Productivity | | | |
| code-editor-execution | Other | | | |
| comparison-aggregators | Search & reference | | | |
| conference-review-submission | Education / LMS | | | |
| converters-calculators | Utilities | | | |
| course-sites-classrooms | Education / LMS | | | |
| credit-card | Financial | | | |
| crm | Productivity | | | |
| crowdfunding-donations | Shopping & transactional | | | |
| dating | Communication | | | |
| design-creative | Productivity | | | |
| dictionaries-language-tools | Utilities | | | |
| documentation-api-docs | Static / informational | | | |
| documents | Editing | | | |
| e-commerce | Shopping & transactional | | | |
| email | Communication | | | |
| flights-hotels | Shopping & transactional | | | |
| forms-surveys | Productivity | | | |
| forums | Social media | | | |
| grocery | Shopping & transactional | | | |
| handwritten-notes-whiteboards | Editing | | | |
| health-fitness-tracking | Health | | | |
| health-portals | Health | | | |
| help-center-faq-kb | Static / informational | | | |
| instant-messaging | Communication | | | |
| insurance-loans | Shopping & transactional | | | |
| job-sites | Shopping & transactional | | | |
| live | Streaming & media | | | |
| map-services | Maps & navigation | | | |
| moocs-language-learning | Education / LMS | | | |
| multimedia-posting | Social media | | | |
| multiplayer-online | Gaming | | | |
| music | Streaming & media | | | |
| news | Dynamic info / feeds | | | |
| password-managers | Utilities | | | |
| personal-portfolio | Static / informational | | | |
| petitions-voting-info | Government / civic | | | |
| podcasts-audiobooks | Streaming & media | | | |
| project-homepages | Static / informational | | | |
| project-mgmt-issue-tracking | Productivity | | | |
| qa-knowledge | Search & reference | | | |
| rating-review | Social media | | | |
| real-estate-buy-rent | Shopping & transactional | | | |
| remote-calls | Communication | | | |
| restaurants | Static / informational | | | |
| ride-hailing-delivery | Shopping & transactional | | | |
| scheduling-e-signature | Productivity | | | |
| search-engines | Search & reference | | | |
| single-player | Gaming | | | |
| software-marketplace | Shopping & transactional | | | |
| sports-esports | Dynamic info / feeds | | | |
| spreadsheets-slides | Editing | | | |
| stock-crypto-prices | Dynamic info / feeds | | | |
| tax-filing-dmv-permits | Government / civic | | | |
| team-chat-workspace | Communication | | | |
| ticketing-events | Shopping & transactional | | | |
| transit-directions | Maps & navigation | | | |
| translation | Utilities | | | |
| university-academic | Static / informational | | | |
| url-shorteners-qr | Utilities | | | |
| version-control | Productivity | | | |
| video | Streaming & media | | | |
| visual-how-to-guides | Search & reference | | | |
| weather | Dynamic info / feeds | | | |
| wikis | Search & reference | | | |

**12/78 built** · **2/78 evaluated** · **12/78 with descriptions**

## Getting Started (CHPC Quick Start)

If you're on CHPC in the `kmarino` group, the one-time setup is:

```bash
# 1. Clone the repo
git clone git@github.com:kmarino-research/MiniWeb.git
cd MiniWeb

# 2. Run the setup script (creates conda env, symlinks shared data, prepares .env)
bash scripts/setup_chpc.sh

# 3. Add your API keys (required for evaluation only)
nano .env

# 4. Start the server
conda activate miniweb-eval
python run.py              # http://localhost:8080

# 5. View from your laptop (SSH tunnel)
ssh -L 8080:localhost:8080 <your-uid>@<chpc-node>
# Then open http://localhost:8080
```

All 12 built sites will be immediately available — no data download or generation needed.

### Manual Setup (Non-CHPC)

```bash
git clone <repo-url> && cd MiniWeb
conda env create -f environment.yml
conda activate miniweb-eval
cp .env.example .env       # Add your API keys
python run.py              # http://localhost:8080
```

You'll need to download large data files yourself (see each site's `doc/README.md` for source URLs).

### Shared Data Sources (CHPC)

Large datasets live at `/scratch/general/vast/u1653932/data_sources/` (group-readable for `kmarino`). The setup script creates symlinks automatically. **Never commit large data files to git.**

| Dataset | Shared Path | Size | Used By |
|---------|-------------|------|---------|
| arXiv metadata | `.../data_sources/arxiv/arxiv-metadata-oai-snapshot.json` | 5.0 GB | academic-paper-db |
| WebShop products | `.../data_sources/webshop/items_shuffle.json` | 5.2 GB | auctions, e-commerce, grocery |
| WebShop attributes | `.../data_sources/webshop/items_ins_v2.json` | 178 MB | auctions, e-commerce, grocery |
| Pressbooks | `.../data_sources/pressbooks/pressbooks-0000.json.gz` | 183 MB | books-comics |

**Permissions:** If you can't read these files, ask `u1653932` to run `chmod -R g+rX /scratch/general/vast/u1653932/data_sources/`.

### Evaluation Environment

Browser-based evaluation requires additional dependencies:

```bash
pip install -r evaluation/requirements.txt
playwright install chromium
```

---

## Adding a New Site — Full Pipeline

```
1. Scaffold  →  2. Add Data  →  3. Write Doc  →  4. Generate with Claude Code  →  5. Validate  →  6. Browser Eval
```

### Step 1: Scaffold

```bash
./scripts/add_site.sh my-site "My Site Name" "A short description"
```

Creates `sites/my-site/` with `data/`, `doc/`, `config/`, `templates/my-site/` directories.

If the site is already in `MiniWeb_macro_assignment.xlsx`, it was pre-scaffolded with `doc/README.md` containing the target macros.

### Step 2: Add Data

Place raw data files in `sites/my-site/data/` in their **original format**.

**Rules:**
- Never rewrite or restructure the data — `routes.py` will have an interpreter
- For large datasets (>100MB), the interpreter uses `config/config.json` to control sampling (`num_data_points: -1` = all, `1000` = sample 1000)
- For external data (e.g., shared WebShop), store the path in `config/config.json`
- For sites that synthesize data (banking, blogs, etc.), skip this step

### Step 3: Write the Description

Create `sites/my-site/doc/desc` (no file extension):

```
Creator: <your name>
1. What this website is: <domain, purpose, target audience>
2. How it uses the data files in data: <which files, how they map to the site>
3. What real world websites it should be modeled after: <e.g., Google Scholar, eBay>
4. Whether the domain has temporal/dynamic data: <static or dynamic, how to simulate>
5. Any domain-specific behavior or constraints: <special notes>
```

Don't delete the auto-generated `doc/README.md` — it has the target macros from the spreadsheet.

### Step 4: Generate with Claude Code

Open Claude Code in the MiniWeb directory and use this prompt:

```
Build the <site-id> MiniWeb site.

Read the description at sites/<site-id>/doc/desc and the macros
in sites/<site-id>/doc/README.md.
Use sites/academic-paper-db/ as the reference pattern.
Use sites/bookstore/ as the minimal example.

Generate all files:
- routes.py — Flask blueprint with data interpreter, HTML + API routes
- templates/<site-id>/*.html — UI modeled after <real-world site>
- data/*.json — synthesized data (if no external data source)
- data/.pristine/ — pristine copies of mutable JSON files
- tasks.json — 20 tasks (6 easy, 8 medium, 6 hard) covering all target macros
- verifiers.py — per-task HTTP verification functions
- macro_verifiers.py — per-macro verification functions
- reference_solutions.py — per-task solutions via Flask test client

Rules:
1. Never rewrite raw data — write an interpreter in routes.py
2. Read config/config.json for num_data_points and random_seed
3. Blueprint name must match site_id in site.json
4. Tasks must be realistic user interactions
5. Use placehold.co for placeholder images (not picsum.photos)
6. The Flask app already sets secret_key for sessions
```

This typically takes 5-15 minutes.

### Step 5: Validate

**5a. Syntax check:**
```bash
python -B -c "from app import create_app; app = create_app(); print('OK')"
```

Common fix: f-strings with backslashes — extract to a variable instead.

**5b. Task validation:**
```bash
python scripts/validate_site.py my-site
```

Target: **20/20 tasks pass**.

**5c. Macro verification:** Verify all target macros pass their verifiers in `macro_verifiers.py`.

### Step 6: Browser-Agent Evaluation

Browser eval is compute-intensive. Use an `salloc` allocation on CHPC:

```bash
# Get allocation
salloc --partition=kmarino-gpu-grn --qos=kmarino-gpu-grn --account=kmarino \
       --gres=gpu:a800:2 --time=06:00:00 --ntasks=1 --mem=60G

# Single site
conda run -n miniweb-eval python evaluation/run_eval.py \
    --site my-site --model gpt --port 8091 --max-steps 20 --workers 4

# All built sites (batch)
bash scripts/run_batch_eval.sh --model gpt --workers 4 --rounds 3 --parallel 2
```

**After each round**, check results and fix issues:
```bash
cat sites/my-site/results/gpt_*/results.json | python -m json.tool
```

Common fixes:
- **Timeouts** — paginate long lists (show first 50 items), add direct navigation
- **Login failures** — make Sign In button prominent, not a small link
- **Agent can't find elements** — add labels, make buttons bigger
- **0 tasks loaded** — port conflict or slow data loading; the server pre-warms the site now

Target: **≥70% pass rate** after 3 rounds.

### Step 7: Submit

Include in PR: `sites/<id>/` directory (with `data/.pristine/`), and validation results.

---

## PR Checklist

- [ ] `site.json` — correct id, name, description, tags
- [ ] `doc/desc` — site description written
- [ ] `config/config.json` — num_data_points, random_seed, any external paths
- [ ] `data/` — raw data in original format (never rewritten)
- [ ] `data/.pristine/` — pristine copies of all mutable JSON files
- [ ] `routes.py` — Flask blueprint with data interpreter
- [ ] `templates/<site-id>/` — all HTML templates
- [ ] `tasks.json` — 20 tasks (6 easy, 8 medium, 6 hard)
- [ ] `verifiers.py` — one verify function per task
- [ ] `macro_verifiers.py` — one verify function per target macro
- [ ] `reference_solutions.py` — one solve function per task
- [ ] Validation: 20/20 tasks pass, all macros pass
- [ ] Browser eval: ≥70% after 3 rounds
- [ ] No hardcoded `localhost` URLs
- [ ] Uses `placehold.co` for placeholder images (not picsum.photos)

## Code Style

- Python 3.11+
- Follow patterns in `sites/academic-paper-db/` (gold standard)
- JSON data: 4-space indent
- Blueprint name must match `site_id`
- HTML templates in `templates/<site-id>/`
- Base styles: `<link rel="stylesheet" href="/static/style.css">`
- Raw data in `data/` must never be rewritten

## Supported Eval Models

| Key | Model | Provider |
|-----|-------|----------|
| `gpt` | GPT-4o | OpenAI |
| `gemini-flash` | Gemini 3 Flash Preview | Google |
| `gemini-pro` | Gemini 3 Pro Preview | Google |
| `claude` | Claude Sonnet 4.6 | Anthropic |

## Project Layout

```
MiniWeb/
├── run.py                      # Flask entry point
├── app/                        # Core app (portal, static)
├── sites/                      # Benchmark sites (auto-discovered)
│   ├── _template/              # Scaffold starter
│   ├── academic-paper-db/      # Gold-standard reference (20 tasks, 21 macros)
│   ├── bookstore/              # Minimal template (no tasks)
│   └── <site-id>/              # Each site has:
│       ├── site.json, routes.py, __init__.py
│       ├── doc/                # Site description (user-written)
│       ├── config/config.json  # Site config (num_data_points, random_seed, etc.)
│       ├── data/               # Raw data (original format, never rewritten)
│       ├── data/.pristine/     # Reset baseline
│       ├── templates/<id>/*.html
│       ├── tasks.json, verifiers.py, macro_verifiers.py, reference_solutions.py
│       └── results/            # Evaluation output (gitignored)
├── specs/                      # Site generation specs
├── scripts/                    # Generation & validation tools
├── evaluation/                 # Browser-agent eval harness
├── macros/                     # Macro research pipeline
├── docs/                       # Documentation
├── AGENTS.md                   # Agent guidance & eval harness
└── CONTRIBUTING.md             # This file
```

## Quick Reference

```bash
# Scaffold
./scripts/add_site.sh my-site "My Site" "Description"

# Run the app
python run.py

# Validate a site
python scripts/validate_site.py my-site

# Reset data to pristine
python scripts/reset_site.py my-site

# Single eval
conda run -n miniweb-eval python evaluation/run_eval.py \
    --site my-site --model gpt --port 8091

# Batch eval (all built sites)
bash scripts/run_batch_eval.sh --rounds 3

# Check results
cat sites/my-site/results/gpt_*/results.json | python -m json.tool
```
