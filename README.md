# MiniWeb

A **web-agent benchmark with a skill profile.** One Flask process serves **65 realistic
mock websites** (banking, forums, e-commerce, email, maps, dev consoles, …), each backed by
seeded SQLite data. Agents get a natural-language instruction and drive a real browser;
instead of a single pass/fail, every task is graded against a **per-macro verifier** so you
get a **vector of per-skill pass rates** — *what* the agent can and can't do (fill a form,
operate a slider, compose a multi-step workflow, report an answer), not just one number.

- **65 sites**, one server, **no Docker**, per-session state isolation (many agents in parallel).
- **253 annotated tasks** (`data/annotations/*/*/task.json` + `verifier.json`).
- **Deterministic grading** (`evaluation/verifiers.py::verify_task`) with a per-macro breakdown; optional LLM judge.
- Two agent harnesses: **browser-use / computer-use** (built in) and **BrowserGym + AgentLab** (standardized, leaderboard-comparable).
- **Offline** and **session-reset** by construction during eval.

---

## 1. Setup

Use the project's conda env (plain `python3` lacks the deps):

```bash
# create/activate an env, then:
pip install -r requirements.txt
python -m playwright install chromium      # browser for the eval harness
```

Put provider keys in a `.env` at the repo root (only what you'll use):

```bash
# Gemini via Vertex (service account)
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=your-project
GOOGLE_CREDENTIALS_JSON={...service-account json...}
# or direct keys
GEMINI_API_KEY=...        OPENAI_API_KEY=...        ANTHROPIC_API_KEY=...
GROQ_API_KEY=...          OLLAMA_HOST=http://localhost:11434
```

---

## 2. Run & host MiniWeb

**Local:**

```bash
python run.py                      # serves on http://localhost:8080
FLASK_RUN_PORT=8099 python run.py  # pick a port
```

Open **http://localhost:8080** — a browser-style landing page lists every site; tiles show
the site's **brand name** (category on hover). Direct URLs:

| Path | What |
|---|---|
| `/` | Portal / site directory |
| `/sites/<id>/` | A specific site (e.g. `/sites/forums/`, `/sites/banking/`) |
| `/annotate/` | Annotation + verifier tooling (login required) |

**Production / hosting** (Procfile-based — Railway, Render, Heroku-style):

```bash
gunicorn run:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
```

Useful env vars:

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Session cookie key (set in production) |
| `MINIWEB_SITES=forums,banking` | Load only some sites (faster dev startup) |
| `MINIWEB_NO_AUTOLOGIN=1` | Start logged out (eval sets this per-task for `authenticate_by_form`) |
| `MINIWEB_MACRO_DIR=/data` | Persist the macro registry (`macros.yaml` + `macro_locations.yaml`) on a volume |
| `MINIWEB_ANNOTATORS=user:pass,...` | Annotator logins (default `minh:miniweb`) |

> The DB (`miniweb.db`) is modified post-build — **never run `build_db.py`.** Some content is
> a runtime seed (see `docs/` / the forums seed notes); re-run those + push the DB after any
> rebuild.

---

## 3. Run agents (built-in harness)

`evaluation/run_agent_verify.py` boots a fresh server, runs an agent on a task, assembles the
trajectory from the server's admin logs, and grades it with `verify_task`.

**One task:**

```bash
python evaluation/run_agent_verify.py \
  --task-id Minh/e-commerce_224c4c \
  --model gemini-3.5-flash \
  --harness browser-use --obs axtree
```

- `--harness browser-use` (DOM/text loop, any provider) · `computer-use` (native Anthropic/OpenAI/Gemini computer-use) · `auto`
- `--obs axtree | html | visual` (visual = screenshots)
- `--model` any id in `helpers/llm.py` (`gemini-3.5-flash`, `gpt-5.6`, `claude-opus-4-8`, `ollama/qwen2.5`, …) or `mock`
- `--grade verifier | judge | both` · `--no-headless` to watch · `--max-steps`, `--timeout`, `--port`

**A matrix of agents × tasks (config mode):**

```bash
python evaluation/run_agent_verify.py --config evaluation/configs/my_run.json
```

```jsonc
{
  "agents": [{ "model": "gemini-3.5-flash", "label": "flash", "obs": "axtree" }],
  "tasks":  "all",                 // "all" | "site:banking" | ["Minh/e-commerce_224c4c", ...]
  "harness": "browser-use",
  "grade": "verifier",
  "max_steps": 50, "timeout": 300, "headless": true,
  "out": "evaluation/results/my_run"
}
```

Each run writes `result.json` (with `by_macro`), `verify_report.json`, `trajectory.json`, and
screenshots per task under `out/`.

**Multiple local models, one GPU each** (one ollama server + one runner per GPU):

```bash
```

During eval the agent is **network-isolated to localhost** (a Chromium DNS-block flag) and each
task gets a **fresh session** — no cross-task state leakage.

### How grading works
Each task's `verifier.json` maps macros → check trees. A macro's **backend request is the
gate** (did the right server call fire with the task's values); the **frontend affordance is
advisory** (was the right control used). `verify_task` returns `passed` plus `by_macro` — the
skill profile. See `docs/macro_system.md`.

### Models
`helpers/llm.py` is the one place model names route to providers (anthropic / openai / gemini /
ollama / groq) and tokens are tracked. Local models via ollama (`ollama/<model>`), Gemini via
Vertex or `GEMINI_API_KEY`.

---

## 4. Annotation & verifiers

`/annotate/` (login with an entry from `MINIWEB_ANNOTATORS`) is where tasks are recorded,
macros are tagged, and verifiers are built/reviewed (`/annotate/verifiers`). The canonical
macro registry is `data/macros.yaml` (loaded via `annotation/macros.py`) — edit the YAML, not
derived code.

---

## 5. BrowserGym + AgentLab (standardized eval)

Run MiniWeb under the **same harness as WebArena / WorkArena / MiniWoB** so numbers are
directly comparable, with reproducible studies and a visual trace debugger. Lives on the
**`browser-gym` branch**, in a **separate Python env** (browsergym pins an older Playwright
than browser-use):

```bash
pip install -r requirements-browsergym.txt   # browsergym-core, gymnasium (+ agentlab for studies)
python -m playwright install chromium
```

Every task is registered as a gym id `browsergym/miniweb.<annotator>.<task>`:

```python
import browsergym_miniweb            # registers all tasks
import gymnasium as gym
env = gym.make("browsergym/miniweb.Minh.e-commerce_224c4c")
```

`MiniWebTask` reuses `verify_task` verbatim; set `MINIWEB_URL` to a running MiniWeb server.

**AgentLab study** (`browsergym_miniweb/run_study.py` — starts/stops the server for you).
The agent is **visual by default** (screenshot + set-of-marks on the AXTree) and takes any
model the repo's LLM router knows — Claude, OpenAI, Gemini, or a local ollama model:

```bash
python -m browsergym_miniweb.run_study --model claude-sonnet-4-5 --tasks 10 --jobs 4
python -m browsergym_miniweb.run_study --model gemini-2.5-flash  --tasks all
python -m browsergym_miniweb.run_study --model gpt-4o            --tasks Minh/e-commerce_224c4c
python -m browsergym_miniweb.run_study --model ollama/qwen3.5:27b --tasks 3 --text   # local, no key
```

Keys per provider: `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY`; ollama needs
none (`OLLAMA_API_BASE` to point at a remote server). `--text` opts out of vision for
text-only models. Programmatic use: `make_benchmark(...)` + `miniweb_agent(model, visual=...)`
from `browsergym_miniweb.agentlab_study`.

**Offline sandbox**: every browser context is network-isolated — external navigations land on
MiniWeb's `/_blocked` page ("tasks can be completed without external sites") and bounce back
to the portal; external subresources (CDNs, fonts, tiles) are dropped. Watch it happen live
with the assistant (headful, chat-driven):

```bash
python run.py &            # MiniWeb on :8099
PYTHONPATH=. agentlab-assistant \
    --agent_config browsergym_miniweb.agentlab_study.MINIWEB_ASSISTANT_AGENT \
    --start_url http://localhost:8099/
# then ask the agent to visit an external site and watch it bounce to /_blocked
```

**Open the interactive run viewer** (Gradio — step through screenshot / AXTree / action / reward):

```bash
agentlab-xray            # http://localhost:7860  (tunnel the port if remote)
```

Full details, interface mapping, and version pins: **`docs/BROWSERGYM_AGENTLAB_MIGRATION.md`**.

---

## 6. Repo layout

```
app/            Flask app factory, per-site SQLite data layer (session-overlay isolation), admin/eval endpoints
sites/<id>/     Each mock site: routes.py, templates, site.json (brand + category)
helpers/        Generic utils — llm (model routing/tokens), geo, security, auth
evaluation/     run_agent_verify.py (single-task runner), run_study.py (model×task studies), verifiers.py,
                trajectory.py, agents.py (browser-use), server.py, xray.py (results inspector),
annotation/     Annotation + verifier-building UI, macro registry loaders
data/           annotations/ (tasks + verifiers), macros.yaml, macro_locations.yaml, backups/
browsergym_miniweb/   BrowserGym task wrapper + AgentLab wiring (browser-gym branch)
docs/           ARCHITECTURE.md, macro_system.md, BROWSERGYM_AGENTLAB_MIGRATION.md, thesis.md
```

Project rules live in **`CLAUDE.md`** (DB access, macro system, "never do" list).
