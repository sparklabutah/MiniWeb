# MiniWeb

MiniWeb is a set of **65 synthetic websites** (banking, email, forums, shopping, maps, code
editors, and more) served by one Flask app, built to diagnose and train web agents by skill.

- **Skill-level grading.** Every human-annotated task is tagged with **primitives** (called macros in the code):
  reusable interaction skills such as `filter_by_slider`, `create_by_form` or `report_information`. Each task has a
  deterministic verifier with one check tree per primitive, so a run reports which skills an agent has, not just a
  single pass rate.
- **MiniWebGen** (`datagen/`): verifiable single-primitive training trajectories, generated on the training sites. A
  trajectory is kept only if the backend shows the intended change.
- **MiniWebAgent** (`webmix/`): an untrained Qwen3.5-4B planner that hands each primitive-level step to one LoRA
  executor trained on MiniWebGen's trajectories (see [Results](#results)).

| | |
|---|---|
| Sites | 65 (`sites/<site>/`): 52 training sites, 13 held-out sites (`data/datagen/site_split.json`) |
| Human tasks | 376 (`data/annotations/<annotator>/<site>_<hash>/`): 63 on held-out sites (the test set), 310 on training sites only (development). The other 3 start on a training site but also use a held-out site, so neither split uses them. |
| Primitives | 37 well-covered primitives in 7 skill families (`data/final_set.yaml`), from 46 base macros + 7 reasoning operations (`data/macros.yaml`) |
| Grading | per-task verifiers (`evaluation/verifiers.py`) and a VLM primitive judge (`evaluation/macro_judge.py`) |
| Training data | 3,128 generated trajectories replayed into 27.6K training steps (`experiments/pools/`) |

## Results

One Qwen3.5-4B in the same browser-use harness, as a single agent or as MiniWebAgent's planner, with the executor
untrained or trained on the 27.6K generated steps. Task success in %:

| Benchmark | Tasks | Runs | Single, untrained | Single, trained | Planner, untrained | **MiniWebAgent** |
|---|---|---|---|---|---|---|
| MiniWeb single primitives (held-out sites) | 103 | 3 | 55.3 | 80.3 | 54.0 | 71.5 |
| MiniWeb held-out tasks | 63 | 3 | 37.0 | 37.0 | 42.3 | **54.5** |
| WebArena-Lite | 154 | 3 | 27.1 | 20.3 | 30.7 | **36.4** |
| WebVoyager | 536, normalized | 1 | 45.5 | 32.8 | 59.9 | **65.5** |
| Online-Mind2Web | 280, normalized | 1 | 17.9 | 8.6 | 21.8 | **33.9** |

Practice raises single primitives, but alone it does not raise task success: the trained single agent learns to stop
after one primitive. With the planner, the trained executor adds to what planning alone achieves. "Normalized" leaves
out impossible and outdated tasks and sites that block our network. Every number, figure and table of the paper
regenerates with [`python reproduce.py`](experiments/README.md); [docs/RESEARCH.md](docs/RESEARCH.md) gives the
protocols and research questions.

## Quickstart

### 1. Install

```bash
conda create -n miniweb python=3.11 -y && conda activate miniweb
pip install -r requirements.txt
python -m playwright install chromium     # browser for the agent harnesses
```

All commands below run from the repo root in this env. On the lab machines the env already
exists: `~/.conda/envs/miniweb/bin/python`. Training and serving WebMix use a second env; see
step 6.

### 2. Get the dataset and configure `.env`

Site data lives in one SQLite file (about 38 GB). Git tracks neither this file nor the
annotations under `data/` (see [data/README.md](data/README.md)). Put the file at
`data/trimmed_miniweb.db` and create `.env` at the repo root (`cp .env.example .env`).
`app/__init__.py` loads that file at startup. Its parser takes `KEY=VALUE` lines and
whole-line comments only, with no comments after a value:

```bash
# without MINIWEB_DB the app looks for ./miniweb.db
MINIWEB_DB="data/trimmed_miniweb.db"
MINIWEB_ANNOTATIONS_DIR="data/annotations"
# annotation-tool logins
MINIWEB_ANNOTATORS="alice:secret,bob:secret"
# LLM providers, only the ones you use (routing: helpers/llm.py).
# Gemini via Vertex + a service account:
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=...
GOOGLE_CREDENTIALS_JSON={...}
# or Gemini by API key:
GEMINI_API_KEY=...
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
```

Never run `build_db.py`. The database was changed after it was built, and some content comes
from runtime seed scripts in `scripts/seed_*.py`.

### 3. Run the server and open a site

```bash
python run.py                              # http://localhost:8080  (FLASK_RUN_PORT / PORT to change)
MINIWEB_SITES=banking,email python run.py  # load only some sites (faster startup)
```

| URL | What |
|---|---|
| `/` | Portal listing every site |
| `/sites/<site>/` | A site, e.g. `/sites/banking/`. Visitors are logged in as user 1 automatically; evaluation turns this off for login tasks. |
| `/annotate/login` | Annotation tool (accounts from `MINIWEB_ANNOTATORS`) |
| `/_admin/...` | Grading endpoints: request log, recorder stream, data changes ([app/README.md](app/README.md)) |

Production uses `gunicorn run:app` (see `Procfile` and `Dockerfile`). To keep the macro
registry on a persistent volume, set `MINIWEB_MACRO_DIR`.

### 4. Annotation tool

Log in at `/annotate/login`. The main pages:

| Page | Use |
|---|---|
| `/annotate/` | Dashboard: tasks per macro, least covered first |
| `/annotate/task` | Record a task: the tool samples a site and macros, you perform the task and tag each macro's span. Saved to `data/annotations/` |
| `/annotate/verify` | Verifier Builder: pin each macro's checks and re-run the verifier on the recording |
| `/annotate/task-review` | Task Review: queues of tasks whose tags, answer or instruction changed |
| `/annotate/macro-browser` | Macro Browser: every tagged macro instance with its gold span and screenshots |

Details: [annotation/README.md](annotation/README.md), [docs/macro_system.md](docs/macro_system.md).

### 5. Evaluate an agent on MiniWeb

```bash
# one task (starts its own server; --model mock is a pipeline smoke test)
python evaluation/run_agent_verify.py --task-id Minh/crm_bf9346 --model mock
python evaluation/run_agent_verify.py --task-id Minh/crm_bf9346 --model gemini-3.5-flash --obs visual

# a study: N models x M tasks x repeats, parallel workers (YAML or JSON config)
python evaluation/run_study.py --config evaluation/configs/qwen35_4b_all_x3.json --dry-run
python evaluation/run_study.py --config evaluation/configs/qwen35_4b_all_x3.json --workers 8

# per-macro LLM judge over a finished study
python evaluation/macro_judge.py --results evaluation/results/qwen35_4b_all_x3
```

By default `run_agent_verify.py` grades with the macro judge (gemini-3.5-flash) and reports the
deterministic verifier next to it. `--grader verifier` makes no LLM calls for grading. The agent
browser can reach localhost only, and each task starts in a fresh session. See
[evaluation/README.md](evaluation/README.md) and
[docs/VERIFIER_DESIGN.md](docs/VERIFIER_DESIGN.md).

### 6. Reproduce the paper (MiniWebGen, MiniWebAgent, figures)

```bash
python reproduce.py status                  # every run, RQ1 run and adapter the paper reads: present and complete?
python reproduce.py show planner_pooled     # MiniWebAgent: model server, run and grading commands per benchmark
python reproduce.py show rq1                # the ten untrained agents of Table 2
python reproduce.py train pooled_v4         # the executor: training folder from its id list + the torchrun line
python reproduce.py figures                 # regenerate every figure and table into the paper source
```

[experiments/README.md](experiments/README.md) explains the registry (`experiments/paper.yaml`), the training-set id
lists, the cluster and WebArena scripts, the exact environments (`experiments/envs/`) and the grading. Each module
documents its flags in its docstring and `--help`; see [datagen/README.md](datagen/README.md) and
[webmix/README.md](webmix/README.md).

### 7. Tests

```bash
PYTHONPATH=. python -m pytest tests/ -q
```

## Repository map

| Path | Contents |
|---|---|
| `run.py` | Entry point: `create_app()` from `app/` |
| `app/` | Flask app: site mounting, per-site SQLite access with session overlays (`db.py`), cross-site events, simulated file system (`vfs.py`), `/_admin` grading endpoints, injected page scripts (`static/recorder.js`, ...) |
| `sites/<site>/` | One mock website each: `routes.py`, `schema.py`, `templates/`, `site.json`, `doc/` |
| `annotation/` | `/annotate` tool: recording, macro tagging, Verifier Builder, Task Review, Macro Browser; macro registry loader (`macros.py`) |
| `evaluation/` | Agent harness and grading: `run_agent_verify.py`, `run_study.py`, `verifiers.py`, `macro_judge.py`, `xray.py` (results viewer) |
| `datagen/` | Macro data pipeline: site split, site maps, task sampling, scripted executor, backend gate, exports |
| `webmix/` | WebMix: replay to training rows, augmentation, LoRA training, vLLM serving, planner agent, MiniWeb / WebArena-Lite / live-web evaluation |
| `helpers/` | Generic utilities: LLM routing and token accounting (`llm.py`), geo, auth, security |
| `data/` | `macros.yaml`, `macro_locations.yaml` (tracked); the DB, annotations, datagen and webmix outputs (not tracked) |
| `tests/` | pytest suite |
| `scripts/` | Runtime seed scripts, task-review exports, Railway sync |
| `filesystem/` | Base home directory for the simulated file explorer |
| `browsergym_miniweb/` | Optional BrowserGym / AgentLab harness (`requirements-browsergym.txt`, separate env; [doc](docs/BROWSERGYM_AGENTLAB_MIGRATION.md)) |
| `method/hyperWeb/` | Separate sub-project with its own README |
| `docs/` | Design and research docs ([index](docs/README.md)) |

## Documentation

- [docs/README.md](docs/README.md): index of all docs
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): how the pieces fit together
- [docs/RESEARCH.md](docs/RESEARCH.md): claims, research questions, results, evaluation protocols
- [docs/macro_system.md](docs/macro_system.md): macros, reasoning operations, the registry
- [docs/VERIFIER_DESIGN.md](docs/VERIFIER_DESIGN.md): verifiers and the macro judge
- [docs/BROWSERGYM_AGENTLAB_MIGRATION.md](docs/BROWSERGYM_AGENTLAB_MIGRATION.md): the optional BrowserGym + AgentLab harness
- [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md): known site and data bugs
- [docs/CHANGELOG.md](docs/CHANGELOG.md): what changed and when
- [AGENTS.md](AGENTS.md) and [CLAUDE.md](CLAUDE.md): rules for coding agents
- [CONTRIBUTING.md](CONTRIBUTING.md): how to change sites, tasks, macros and code
