# Contributing to MiniWeb

## Site Status

| Site | Category | Desc | Built | Validated | Eval |
|------|----------|------|-------|-----------|------|
| academic-paper-db | Search & reference | yes | yes | 20/20 | yes |
| agency-portals | Government / civic | yes | yes | 20/20 | yes |
| ai-chatbots | Communication | yes | yes | 20/20 | |
| auctions-p2p-marketplaces | Shopping & transactional | yes | yes | 28/28 | |
| banking | Financial | yes | yes | 20/20 | |
| blogs | Dynamic info / feeds | yes | yes | 20/20 | |
| books-comics | Streaming & media | yes | yes | 20/20 | |
| brokerage | Financial | yes | yes | 20/20 | |
| business-company | Static / informational | yes | yes | 20/20 | |
| calendar-todo | Productivity | yes | yes | 20/20 | |
| cloud-dev-consoles | Productivity | yes | yes | 20/20 | |
| cloud-storage-file-transfer | Productivity | | yes | | |
| code-editor-execution | Editing | | yes | 19/20 | |
| comparison-aggregators | Search & reference | | yes | 14/20 | |
| conference-review-submission | Education / LMS | | yes | 20/20 | |
| converters-calculators | Utilities | | yes | 20/20 | |
| course-sites-classrooms | Education / LMS | | yes | 20/20 | |
| crm | Productivity | | yes | 19/20 | |
| crowdfunding-donations | Shopping & transactional | | yes | 18/20 | |
| dating | Communication | | yes | 13/20 | |
| design-creative | Productivity | | yes | 18/20 | |
| dictionaries-language-tools | Utilities | | yes | 20/20 | |
| documentation-api-docs | Static / informational | | yes | 20/20 | |
| documents | Editing | | yes | 20/20 | |
| e-commerce | Shopping & transactional | | yes | 17/20 | |
| email | Communication | | yes | 15/20 | |
| flights-hotels | Shopping & transactional | | yes | | |
| forms-surveys | Productivity | | yes | | |
| forums | Social media | | yes | | |
| handwritten-notes-whiteboards | Editing | | yes | | |
| health-fitness-tracking | Health | | yes | | |
| health-portals | Health | | yes | | |
| instant-messaging | Communication | | yes | | |
| insurance-loans | Financial | | yes | | |
| job-sites | Shopping & transactional | | yes | | |
| live | Streaming & media | | yes | | |
| map-services | Maps & navigation | | yes | | |
| multimedia-posting | Social media | | yes | | |
| music | Streaming & media | | yes | | |
| news | Dynamic info / feeds | | yes | | |
| password-managers | Utilities | | yes | | |
| personal-portfolio | Static / informational | | yes | | |
| petitions-voting-info | Government / civic | | yes | | |
| podcasts-audiobooks | Streaming & media | | yes | | |
| project-homepages | Static / informational | | yes | | |
| project-mgmt-issue-tracking | Productivity | | yes | | |
| qa-knowledge | Search & reference | | yes | | |
| rating-review | Social media | | yes | | |
| real-estate-buy-rent | Shopping & transactional | | yes | | |
| remote-calls | Communication | | yes | | |
| software-marketplace | Shopping & transactional | | yes | | |
| sports-esports | Dynamic info / feeds | | yes | | |
| spreadsheets-slides | Editing | | yes | | |
| tax-filing-dmv-permits | Government / civic | | yes | | |
| team-chat-workspace | Communication | | yes | | |
| ticketing-events | Shopping & transactional | | yes | | |
| transit-directions | Maps & navigation | | yes | | |
| translation | Utilities | | yes | | |
| university-academic | Static / informational | | yes | | |
| url-shorteners-qr | Utilities | | yes | | |
| version-control | Productivity | | yes | | |
| video | Streaming & media | | yes | | |
| visual-how-to-guides | Search & reference | | yes | | |
| weather | Dynamic info / feeds | | yes | | |
| wikis | Search & reference | | yes | | |

**72/72 desc** · **72/72 built** · **72/72 tasks+verifiers** · **2/72 browser-evaluated**


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

All 72 built sites will be immediately available — no data download or generation needed.

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

All site data lives at `/scratch/general/vast/u1653932/data_sources/` (group-readable for `kmarino`). Each site's data is in `data_sources/<site-name>/` alongside external datasets. **Never commit data files to git** — the `data_sources/` directory is gitignored.

| Dataset | Shared Path | Size | Used By |
|---------|-------------|------|---------|
| arXiv metadata | `.../data_sources/arxiv/arxiv-metadata-oai-snapshot.json` | 5.0 GB | academic-paper-db |
| Pressbooks | `.../data_sources/pressbooks/pressbooks-0000.json.gz` | 183 MB | books-comics |
| PeerRead | `.../data_sources/PeerRead/data/` | ~50 MB | conference-review-submission |
| Enron emails | `.../data_sources/enron/enron_mail_20150507.tar.gz` | 1.7 GB | email |
| Wiktionary | `.../data_sources/wikidictionary/raw-wiktextract-data.jsonl` | 22 GB | dictionaries-language-tools |

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

Generate all files:
- routes.py — Flask blueprint with data interpreter, HTML + API routes
- templates/<site-id>/*.html — UI modeled after <real-world site>
- data_sources/<site-id>/*.json — synthesized data (written to shared data_sources path)
- data_sources/<site-id>/.pristine/ — pristine copies of mutable JSON files
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
