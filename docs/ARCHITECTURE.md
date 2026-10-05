# Architecture

MiniWeb has five parts. They all share one Flask app and one SQLite database:

```
                       agents / annotators / datagen executor (Chromium)
                                        |  HTTP
  +-------------------------------------v--------------------------------------+
  | Flask app (run.py -> app.create_app)                                        |
  |   /                portal             /annotate/*   annotation tool          |
  |   /sites/<site>/*  65 site blueprints /_admin/*     request log, recorder,   |
  |   /_fs/*           simulated files                  data changes, flags      |
  |   /verify-payment  2FA                /_player/*    media timelines          |
  |        | app.db (reads merge base + overlay; writes go to the overlay)       |
  +--------v---------------------------------------------------------------------+
  | SQLite: per-site base tables  +  session_overlay (one sid per browser session)|
  +-------------------------------------------------------------------------------+
        ^ verifier.json / trajectories           ^ verified trajectories
        |                                        |
  annotation/ -> data/annotations/        datagen/ -> data/datagen/runs/
        |                                        |
  evaluation/ (run_agent_verify, run_study,   webmix/ (replay -> rows -> LoRA train
   verifiers, macro_judge)                     -> vLLM -> planner agent -> evals)
```

Package-level details are in each package's `README.md`. This page explains how the parts
connect.

## Web app (`app/`, `sites/`)

`run.py` calls `app.create_app()`, which:

1. Loads `.env` from the repo root and opens the database at `MINIWEB_DB`.
2. Mounts the portal at `/`, and each implemented site in `sites/*/site.json` at
   `/sites/<site>/`. There are 65 sites; `MINIWEB_SITES=a,b` mounts only some of them.
3. Mounts the annotation blueprint at `/annotate`, the file system at `/_fs`, and the admin
   and grading endpoints under `/_admin`.
4. Installs the request hooks:
   - **Per-site login.** Each site keeps its own `session["_uid_<site>"]`, so logging in or
     out on one site does not affect another.
   - **Auto-login.** A `/sites/*` request with no login state for that site gets
     `user_id = 1`. A session flag (`_no_autologin`) or `MINIWEB_NO_AUTOLOGIN=1` turns this
     off for login tasks.
   - **Payment 2FA.** Sites call `events.request_2fa()`. It emails a 6-digit code to the
     user's WebMail inbox and sends the browser to `/verify-payment`. The session flag
     `_disable_2fa` skips this step.
   - **Script injection.** Every HTML page under `/sites/` gets these scripts before
     `</body>`: `dialog-shim.js`, `recorder.js`, `file-explorer.js`, `export-feedback.js`,
     the shared media player, `miniweb-share.js`, and a per-site logo font.
   - **Request log.** Every `/sites/` request is logged per session with its method, path,
     query, body, status, response and UTC timestamp.

A site is a blueprint: `routes.py` (pages and JSON APIs), `schema.py` (its tables),
`templates/<site>/`, `site.json` and `doc/README.md`. Sites are linked through an event bus:
`app/events.py` emits an event, and handlers in `app/handlers/` turn it into records on other
sites. For example, a purchase adds a bank debit and a confirmation email, and a booking adds
a calendar event.

## Data layer (`app/db.py`)

- **One SQLite file** with per-site tables named `<site>_<collection>`, such as
  `banking_transactions`. `site_registry` maps (site, collection) to a table and its primary
  key. Large text collections have FTS5 indexes that `db.search()` uses.
- **Session overlay.** The first data access in a browser session assigns it an overlay id
  (`session["_data_overlay_sid"]`). Writes (`save_item`, `delete_item`, `save_collection`) go
  to `session_overlay` under that id and never touch base tables. Reads merge the overlay into
  the base rows. As a result:
  - many agents can run against one server in parallel without seeing each other's changes;
  - `/_reset_data` returns a session to the pristine dataset;
  - `db.session_changes()`, served at `/_admin/changes`, lists exactly what a session inserted,
    updated or deleted. Graders and the datagen gate compare this list.
- **Query rules.** Filter, sort and paginate in SQL; never load a whole table into Python.
  The full rules are in [AGENTS.md](../AGENTS.md).
- **Simulated file system** (`app/vfs.py`). A Finder-style explorer whose base home
  directory is `filesystem/` on disk. Downloads, saves and uploads from any site are stored in
  the overlay under `filesystem/files`, so verifiers can check them through
  `/_admin/data/filesystem/files`.

## Recording

Graders and the training pipeline all read the same three streams for a session:

| Stream | Source | Endpoint |
|---|---|---|
| Actions and observations (clicks, typing, selects, URL, page snapshot) | `recorder.js` in the page | `/_admin/record`, `/_admin/beacon` |
| Server requests (method, path, query, body, response, redirect target) | Flask request hook | `/_admin/log` |
| Data changes against the base tables | `db.session_changes()` | `/_admin/changes` |

`evaluation/trajectory.py` assembles these into a trajectory in the same schema as a human
recording (`trajectory.json`).

## Annotation (`annotation/`)

The `/annotate` blueprint is where humans record tasks, tag macro spans, and build verifiers.
Tasks are stored as files under `data/annotations/<annotator>/<task_id>/`: `task.json`,
`trajectory.json`, `verifier.json`, `verifier_runs.json` and `screenshots/`. The macro
vocabulary comes from `data/macros.yaml` through `annotation/macros.py`. New verifiers start
from the same scaffold for every macro (`annotation/verifier_scaffold.py`), and each one is
validated against its gold recording and against negative probes (`annotation/quality.py`).
The Macro Browser and Task Review pages are read-only views over the same files. See
[macro_system.md](macro_system.md) and [VERIFIER_DESIGN.md](VERIFIER_DESIGN.md).

## Evaluation (`evaluation/`)

`run_agent_verify.py` runs one task:

1. It starts a fresh server.
2. It starts the agent (browser-use, any model routed by `helpers/llm.py`) on the task's
   recorded start page. The browser can reach localhost only.
3. It pulls the three streams above and builds the trajectory.
4. It grades the trajectory twice:
   - `verifiers.verify_task`: deterministic, with a pass/fail per macro;
   - `macro_judge.grade`: one LLM verdict per macro instance against the gold span
     (gemini-3.5-flash, best of 3 votes).

`run_study.py` runs that loop over N models × M tasks × repeats with parallel workers.
`xray.py` is a web viewer for the results.

## Training data (`datagen/`)

A per-macro pipeline that runs only on the 52 training sites:

1. Fix the site split.
2. Crawl the sites and probe each control's backend signature.
3. Sample parameters.
4. Write the task instruction and its expected backend check.
5. A coding LLM with full DOM access writes a script, and a restricted wrapper executes it. It
   records screenshots and pixel actions.
6. Keep an attempt only if the backend gate passes (`datagen/checks.py::gate`): the expected
   backend effect is seen (a request carrying the value, a recorded data change, or the
   computed answer) AND the `verify_task` spec built for the task passes. An optional LLM
   judge adds a second check; `--no-judge` turns it off.

What a macro's controls look like is defined in `datagen/kinds/`. The full-DOM information
never enters the training data. See [datagen/README.md](../datagen/README.md).

## WebMix (`webmix/`)

- **Harness** (`harness.py`): one browser-use setup shared by every arm and by replay. Each
  step sees a DOM element list and a screenshot at 1280×800. Actions include clicks by
  element index or by coordinate, plus `drag`, `draw` and `macro_done`.
- **Replay** (`replay.py`, `python -m webmix replay`): runs each kept datagen trajectory
  through the harness with a scripted model. This records browser-use's exact prompt and the
  reply for every step as training rows. A row is kept only if the backend gate passes again.
  `augment.py` adds two variants: recovery (an injected mistake, then the fix) and chain (two
  macros in one episode).
- **Training** (`train.py`): LoRA adapters on Qwen3.5-4B, one per skill family plus a pooled
  adapter. On other families' rows a KL anchor keeps each adapter close to its reference.
  Training runs in the `webmix` env; multi-GPU runs use `torchrun`.
- **Serving** (`serve.sh`): one vLLM server for the base model and all adapters. Each request
  picks an adapter by model name.
- **Agent** (`planner_agent.py`): a browser-use planner on the untrained base model. It sees
  the page but cannot act on it. Its tool `delegate(family, instruction)` runs that family's
  specialist on the same browser, and its `done` action ends the task with an answer.
- **Evaluations:** `evaluate.py` (MiniWeb held-out tasks, graded by their verifiers), `wa.py`
  (WebArena-Lite-v2), and `om2w.py` + `om2w_judge.py` (Online-Mind2Web and WebVoyager on the
  live web, graded by the official judges).

The protocols and results are in [RESEARCH.md](RESEARCH.md).

## Ports

| Port | Used by |
|---|---|
| 8080 | `python run.py` (`PORT` / `FLASK_RUN_PORT`) |
| per config | `run_study.py` workers: the config's `episode.port` + worker index |
| 8300–8320 | datagen servers |
| 8310, 8311 / 8318, 8319 | default MiniWeb servers for `webmix replay` / `webmix.evaluate` |
| 8400 | vLLM (`webmix/serve.sh`) |

## Deployment

`Procfile` and `Dockerfile` run `gunicorn run:app`. Annotators add macros by writing to the
macro YAMLs, so a deployment points `MINIWEB_MACRO_DIR` at a persistent volume. A fresh volume
is seeded from the repo copies. When `MINIWEB_RECOVERY_TOKEN` is set, `/recovery/*` accepts a
token-gated upload that replaces the database or the annotations. `scripts/pull_from_railway.py`
and `scripts/upload_db_railway.py` sync with the hosted instance.
