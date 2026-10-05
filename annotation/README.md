# annotation/

The annotation tool: a Flask blueprint served at `/annotate` where people record tasks on the
MiniWeb sites, tag them with macros, build each task's verifier and review the result.

Related docs: [docs/macro_system.md](../docs/macro_system.md) (macros and tagging rules),
[docs/VERIFIER_DESIGN.md](../docs/VERIFIER_DESIGN.md) (verifiers and the macro judge).

## Login

Log in at `/annotate/login`. Accounts come from `MINIWEB_ANNOTATORS="user1:pass1,user2:pass2"`;
when unset, the local defaults in `_DEFAULT_ANNOTATORS` (`annotation/app.py`) apply. Every other
`/annotate/*` route needs `session["annotator_authenticated"]`: pages redirect to the login,
`/annotate/api/*` returns a JSON 401. Only `/annotate/login`, `/annotate/api/auto_login` and
`/annotate/api/auto_logout` are open.

## Final-set lock

`data/final_set.yaml` (written by `scripts/make_final_set.py`) holds the paper's 37 primitives and 376 tasks. With
`locked: true` the tool is read-only: write routes return 403, macro registration is refused, the task list shows
only the final tasks and the macro pickers only the final primitives. Sessions and the Grader Audit labels stay
open. `MINIWEB_UNLOCK=1` lifts the lock (the tests set it in `tests/conftest.py`).

## Pages

| Route | Page |
|---|---|
| `/annotate/` | Home: links to every page and per-macro task counts, least covered first. |
| `/annotate/task` | **Annotate**: record and tag a new task. `?rerecord=<task_id>&annotator=<name>` opens a saved task to re-record it in place. |
| `/annotate/verify` | **Verifier Builder**: task list with quality pills, the task's recording, and the verifier editor and sandbox. |
| `/annotate/task-review` | **Task Review**: review queues and a before/now comparison of each task. |
| `/annotate/macro-browser` | **Macro Browser**: step through every recorded span of one macro across tasks, or every macro of one task. |
| `/annotate/grader-audit` | **Grader Audit**: blind labels (pass/fail/unsure per primitive) of sampled agent episodes, to check the verifier and the judge. |
| `/annotate/review` | Website review: browse each site and leave feedback. |
| `/annotate/graph` | Site affinity graph for cross-site task flows. |
| `/annotate/playback` | Playback Facts: the facts hidden in each video/audio player and when they are visible (JSON at `/annotate/api/playback_facts`). |
| `/annotate/accounts` | Seeded login accounts for every site. |

## Recording and tagging a task (`/annotate/task`)

1. The page samples sites and macros to cover, weighted by current coverage
   (`data/macro_locations.yaml`). The site-count selector (Auto / 1 / 2 / 3) forces the number
   of sites (`/annotate/api/prompt?n_sites=N`).
2. Set login and 2FA for the session (auto-login is on by default; `authenticate_by_form`
   tasks must start logged out), then **Start Recording** and do the task in the embedded site.
   `app/static/recorder.js` records actions and observations; the server logs every request.
3. **Stop Recording**, then tag each macro instance: its span on the timeline, its reasoning
   operation, its subtask, and the edges between instances. **+ Add macro** browses the full
   registry or proposes a new macro (saved to `data/macros.yaml` under `unassigned`).
   **Infer macros from instruction (LLM)** drafts a macro chain from a written instruction.
4. Write the instruction and the expected answer, then save. A task with two or more macros
   must connect every macro in the graph.

Tag following the rulebook linked from [docs/macro_system.md](../docs/macro_system.md#tagging-conventions).

## Building the verifier (`/annotate/verify`)

Open a task, then in the verifier panel:

- **Suggest with AI** fills the open values of the scaffold from the recording
  (`/annotate/api/suggest_task_verifier`).
- Pin the values the instruction dictates (grounded in the gold requests shown), set advisory
  flags, and **Save** (`/annotate/api/task_verifier/<annotator>/<task_id>`).
- Test in the sandbox: **Run** against Gold, Verification walk, Empty, Answer-only or Agent
  attempt, or **Run Gold + Walk**. Results of the saved spec are stored in
  `verifier_runs.json`.
- **Re-record** replaces the original recording (stamps `rerecorded_by` / `rerecorded_at`).

## Task Review (`/annotate/task-review`)

Queues: **To review**, **Reviewed**, **All tasks**. A human tag set before the task's last AI
correction does not count, so the task returns to To review until its corrected version is
tagged. Each queue lists the most urgent first: needs a decision, then original recording
outdated, then tags or answer changed, then reworded. These reasons show as chips, along with
who made each recording (`rerecorded_by`, and `verification_walk_by` for the fresh walk;
`codex-review` and `claude-review` are AI reviewers, `quality.AI_ACTORS`).

For each task the page shows the instruction, answer, tags and verifier **now** next to
**before** (from `before_review.json`), the recording, and the gold and walk check results
(re-run on open). Decisions: **Verified** or **Stale** (saved as `review_tag` with reviewer,
time and note), **Re-record**, or **Delete** (moves the task to `data/annotations/.trash/`).

`before_review.json` freezes the task and verifier as they were before any correction. It is
written once: backfilled for the September 2026 reviews, otherwise captured on the first edit
through the API (`/annotate/api/update_task_field` other than `review_tag`, or a verifier save).

## AI reviews and verifier evidence (`quality.py`)

AI findings are kept apart from human decisions:

- `task.json` `ai_review`: recommendation (`keep`, `repaired`, `needs_repair`,
  `suggest_delete`, `unreviewed`), note, issues, changes, limitations, documents, reviewer and
  time, plus hashes of the task's semantic fields, its saved verifier and its recording. Write it
  with `POST /annotate/api/task_quality/<annotator>/<task_id>` (validated); `GET` returns the
  current summary. If any hash changes, the review shows as outdated (Stale). Human
  `review_tag` and `review` fields are never touched.
- `verifier_runs.json`: the latest result per source (`gold`, `walk`, `agent`, `empty`,
  `answer_only`) with hashes of the task, spec, grading engine and recording. A changed input
  marks the run Outdated. A run is stored only when it tests the saved spec.

A passing gold or walk run shows agreement with that recording, not human approval. A
`suggest_delete` recommendation does not remove the task and evaluation runners do not skip it.

Review reports under `data/task_review_*`, `data/task_repairs_*`, `data/verifier_audit_*` and
`data/railway_pulls*` can be read through `/annotate/api/review_document?path=...` (read-only;
`.md`, `.json`, `.csv`). Do not put tokens or session cookies in them.

## Files

| File | Role |
|---|---|
| `app.py` | The blueprint: pages and their JSON APIs. |
| `storage.py` | Task storage under `data/annotations/<annotator>/<task_id>/` (override with `MINIWEB_ANNOTATIONS_DIR`): `save_task`, `load_task`, `list_tasks`, `trash_task`, `get_stats`. |
| `macros.py` | Loader and accessors for the macro registry `data/macros.yaml`. |
| `macro_locations.py` | Loader for `data/macro_locations.yaml`. |
| `verifier_scaffold.py` | Verifier scaffold (`scaffold_task`, `default_scaffold`), open-slot helpers (`collect_open_slots`, `fill_open`), task-graph helpers (`inject_qa_leaf`, `refresh_expected`). |
| `quality.py` | AI recommendations, versioned verifier evidence and hashes (above). |
| `review_mode.py` | Data for Task Review: queues, urgency, before/now diff, `before_review.json`. |
| `macro_browser.py` | Data for the Macro Browser: every tagged instance with its gold span, and a task's actions paired with screenshots (or a page outline). Spans are 1-based inclusive action indices. |
| `final_set.py` | The final-set lock (above). |
| `grader_audit.py` | Grader Audit cases (`<annotations>/.grader_audit/<case>/`, built by `scripts/build_grader_audit.py`, uploaded with `scripts/upload_db_railway.py --grader-audit data/grader_audit/cases`) and labels (`<annotations>/.grader_audit_labels/<labeler>.jsonl`, last label wins; scored by `scripts/grader_audit_report.py`). |
| `site_affinities.py` | Cross-site groups used to sample multi-site tasks, and per-site login defaults. |
| `observations.py` | Starts observation completion in a background thread when a task is saved. |
| `process_annotations.py` | The observation pipeline: repair form state, then derive axtree and full-page screenshots. |
| `repair_form_state.py`, `backfill_observations.py` | The two stages of that pipeline. |
| `floor_config.json`, `proposed_edges.csv` | Coverage floor K and saved cross-site graph edges. |

### Task folder

| File | Contents |
|---|---|
| `task.json` | instruction, sites, macros and their instance metadata, expected answer, `ai_review`, `review_tag` |
| `trajectory.json` | the gold recording: actions, observations, network events |
| `server_log.json`, `beacon_log.json` | the server request log (filtered to the recording's time window) and UI beacons |
| `screenshots/` | one screenshot per observation |
| `verifier.json` | the task's verifier |
| `verifier_runs.json` | stored verifier results per source |
| `verification_walk.json` | an optional fresh re-recording |
| `before_review.json` | the task as it was before correction |

## Commands

```bash
# complete missing observations for tasks saved elsewhere (starts its own app unless --base-url)
~/.conda/envs/miniweb/bin/python -m annotation.process_annotations [--annotator Minh] [--watch 60]

# import new tasks from the Railway deployment, keeping local work
MINIWEB_RECOVERY_TOKEN=... ~/.conda/envs/miniweb/bin/python scripts/pull_from_railway.py --new-only
```

The script first backs up local data to `data/backups/pull_backup_<timestamp>.tar.gz`.
`--new-only` then imports only task folders that do not exist locally, keeps the remote snapshot
under `data/railway_pulls/<timestamp>/` and writes a manifest. Without it the pull **replaces**
local annotations and both macro YAMLs with the deployment's copies.
