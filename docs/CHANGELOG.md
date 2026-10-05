# Changelog

The changes that matter (features, protocol and grading changes, data decisions), newest
first. Reference docs describe the current state; this file is the only place for history.
Earlier per-topic changelogs are archived in
`~/Documents/MiniWeb-archive/cleanup-20261002/docs/`.

## 2026-09-28 to 10-02 (working tree, uncommitted)

- **Maps work offline.** map-services loads Leaflet 1.9.4 from `app/static/vendor/leaflet/`
  instead of unpkg, which the offline eval browser could not reach. Before this, map tasks
  (pan/zoom, markers, routes) could not be completed in any browser-use run. Map tiles are still
  external, so offline maps show markers on a blank background.
- **browser-use uploads through MiniWeb's file picker.** The `upload_file` shortcut is removed
  and file inputs are clickable (`evaluation/agents.py`). In the qwen3.5:4b run, 47 of 75
  upload episodes had used the shortcut. Upload-task results before this date are not
  comparable.
- **Synthetic data and WebMix.** `datagen/` generates gate-checked trajectories for every
  registry macro (output in `data/datagen/`). `webmix/` ports WebMix (one LoRA per
  interaction family) onto MiniWeb: replay into browser-use rows, training, vLLM serving, and
  `webmix/evaluate.py` for evaluation. Both are documented in their own READMEs.

## 2026-09-27: macro judge becomes the default grader

- **Grading default.** `run_agent_verify --grader judge` (default; study config
  `episode.grader`): the LLM macro judge (`evaluation/macro_judge.py`, gemini-3.5-flash,
  best of 3, screenshots for `visual` rubrics) decides `passed`; the verifier is reported as
  `verifier_passed` and decides when the judge is down. Reason: in 128 audited
  judge-vs-verifier disagreements the verifier was wrong about twice as often, mostly from
  over-specified checks.
- **Judge names the target.** Replies carry `agent_target`, `reference_target` and
  `extra_targets` before the verdict. On the audited discrete-selection cases the judge went
  from 6/14 to 12-13/14 correct.
- **Verifier engine.** A pinned success status on a non-GET request accepts any 2xx/3xx
  (sign-in redirects still fail). New `request_id_set` exact-set guard on the 14 single-item
  deletes (agents deleted extra items in 16 of 51 delete episodes). `request_made.final_view`
  for "show X sorted/filtered" tasks. An input logged as `change` matches a `type` check;
  `re:` URLs match case-insensitively. 70 discrete-selection verifiers fixed, gated on
  gold/walk.
- **Judge rubric principles** in `data/macros.yaml`: `no_collateral`,
  `server_over_screenshot`; `final_state` covers what was changed; a route the instruction
  names beats `outcome_over_path`.
- **Recorder.** Observations over 64 KB were dropped (browser keepalive limit): 183 of 1128
  episodes had none. Keepalive is now used only under 60 KB.
- **Clipboard.** Headless pages are unfocused, so every site Copy button failed (0/24
  episodes on the 8 clipboard-gated tasks). The agent now gets clipboard permission and focus
  emulation on every step: 5/24 pass on rerun.
- **Result (qwen3.5:4b, 376 tasks x 3):** judge pass@1 41.8%, pass@3 58.0%; verifier 41.3%,
  54.8%; episode agreement 92.4%.
- Old August eval runs (`qwen35_27_all_600`, `gemini35flash_all_600`) archived to
  `cleanup-20260927`: their tasks were rewritten and their verifiers rebuilt since.

## 2026-09-26: tagging convention, task cleanup, review tooling (commit 3dd2c50)

- **Tagging follows Minh's original tags**
  ([RULEBOOK](../data/task_review_macros_minh_2026-09-26/RULEBOOK.md)), replacing the
  2026-09-23 AI review's conventions: 167 of 412 tasks changed tags.
- **Tag what the recording does.** Every task re-segmented from its gold recording by
  `span_start`/`span_end`; repeats get instance IDs; `macro_required` marks what the
  instruction asks for; incidental instances get advisory checks that never fail the task
  (`verify_task` skips advisory macros). Spans start at the navigation that opens the macro.
- **36 tasks deleted** (all AI `suggest_delete`, at the user's request) and moved to
  `data/annotations/.trash/` (`deleted_2026-09-26.json`). **376 tasks remain.**
- **Answer grading** (`_grade_answer`): one chain for every QA check, regex -> exact ->
  precise -> LLM judge, with the judge voting best of 3. 34 checks had failed correct answers
  wrapped in an agent's summary.
- **Evidence checks** (`evaluation/evidence_checks.py`): request sequences with captured IDs,
  request counts and ID sets, final-page observations, downloads, saved images and designs,
  playback spans, and more.
- **Review tooling.** `annotation/quality.py` (AI recommendations and hashed verifier evidence,
  kept apart from human decisions), Macro Browser (`/annotate/macro-browser`), Task Review
  (`/annotate/task-review`, `before_review.json`). `pull_from_railway.py --new-only` imports
  new tasks without overwriting local work (5 new tasks pulled).
- **Harness.** Server request-log timestamps are UTC (local runs had dropped every request).
  Browser pinned to Chromium build 1117 (`episode.browser` / `MINIWEB_BROWSER`). Multi-site
  prompts list the apps and their URLs (qwen3.5:4b had passed 0/15 multi-site episodes by
  guessing addresses). `run_study.py --workers N`.

## 2026-09-22 to 09-23: full task review

- All 404 tasks reviewed: 402 instructions revised; recommendations stored in `ai_review`
  (keep / repaired / needs_repair / suggest_delete). Reports in `data/task_review_2026-09-22/`
  and `data/task_repairs_2026-09-22/`.
- Verifier audit and hardening: 113 + 11 verifiers amended, 4,006 negative probes with no
  unexpected acceptance, 36 deletion candidates queued (`data/verifier_audit_2026-09-23/`,
  `data/verifier_audit_hardening_2026-09-23/`).
- AI macro-tag review of 407 tasks (`data/task_review_macros_2026-09-23/`), superseded on
  09-26.
- Site fixes so tasks can be completed and verified: real file bytes on uploads, binary
  exports, complete filtered counts, deterministic sorting.

## 2026-09-08

- Per-macro verifier template library retired (`macro_templates.yaml`, the Macro Templates
  page). Every macro scaffolds the same three checks in the Verifier Builder
  (`annotation/verifier_scaffold.py`). Templates archived in
  `MiniWeb-archive/macro-templates-retired-2026-09-08/`.

## 2026-08-20 to 08-22

- **Playback info streams** (`app/playback.py`): each video/audio player shows 2-3
  deterministic facts only during short spans, found by scrubbing (`search_by_playback`); 8
  sites. Promo codes from them redeem at the e-commerce checkout. Lookup page
  `/annotate/playback`.
- Sites: PeerPortal redesigned like OpenReview with real deadlines; WebMail drops its in-memory
  corpus cache and gains a 2023-2026 archive anchored to other sites' data; LinguaBridge uses
  local NLLB-200 with every translation frozen in `translation_cache`; SheetDeck exports real
  `.xlsx`/`.pptx`; ForumHub "every thread locked" bug fixed; SecureBank reveal-by-2FA.
- Annotation: site-count selector, **Infer macros from instruction** (reverse annotation),
  "verified by" pills in the builder.

## 2026-08-12 to 08-19

- **BrowserGym/AgentLab harness** (`browsergym_miniweb/`, merged 08-19): `report_answer`
  action, agent-ended episodes, portal-only navigation, offline sandbox.
- **Answer matching**: precise whole-word / numeric tiers before a task-aware LLM judge; the
  judge gets the instruction and works with the Vertex credentials in `.env`.
- New macros `edit_by_cell` and `sign_by_text`; new operation `spatial`. Editable grids on 8
  sites, signing flows on 3 sites, a Form 1040 filing flow.
- 08-15: universal simulated file explorer (`app/vfs.py`); legacy site-based eval removed
  (`run_eval`, `sites/*/tasks.json`); pull-from-Railway sync; reseed scripts.
- 08-16: server-log evidence filtered to the recording's time window. **Audit of 287
  verifiers** against a qwen3.5:27b run: 195 sound, 53 recording gaps, 35 suspect, 4 broken
  tasks. Main causes: the recorder cannot see native form POSTs (the server request log is now
  merged in as the witness), auto-login makes gold recordings skip the login request (record
  login tasks logged out), and some LLM-filled pins named values the instruction never stated
  (pin only what the instruction constrains).

## 2026-08-09 to 08-11: per-task verifiers

- `verifier.json` per task, one check tree per macro, graded by `verify_task`.
- **Backend gate + advisory frontend**: the server request decides; UI affordance checks are
  reported but do not gate. Client-only macros gate on the visible outcome.
- Search and filter gates keep their query parameters; report answers matched fuzzily; a
  terminal QA check with an empty answer fails.
- 08-10 cleanup: `helpers/` package for generic utilities (LLM client, geo, auth);
  `evaluation/run_agent_verify.py` is the single runner; one-time `scripts/` archived to
  `MiniWeb-archive/cleanup-20260810/`.

## 2026-08-06 to 08-07: two-axis macro registry

- `data/macros.yaml` v2: base macro + reasoning operation. The 121 flat `verb_by_modality`
  macros collapsed into 39 base macros (now 46) with aliases; `report_information` replaces
  `reasoning_on_page`. All recorded tags migrated. Per-site locations moved to
  `data/macro_locations.yaml`.

## 2026-07-03 to 08-05: annotation system and site depth

- 07-03 to 07-09: annotation tool rebuilt (macro graph, span tagging, coverage-aware
  sampling); Railway deployment.
- 07-14: per-site session isolation. 07-15: first verifier system (templates, task builder,
  sandbox).
- 07-20 to 07-21: bulk data expansion (38 sites to ~5,000 rows); one observation per action
  with real screenshots; DB and annotation recovery endpoints.
- 08-02 to 08-05: site redesigns and feature fixes, in-network ads, real per-location weather,
  map viewport persistence.

## 2026-06-22 to 06-29: platform

- 12, then 27, then 65 sites on one Flask app with a cross-site event bus, FTS5 search and a
  session data overlay; first annotation interface and evaluation harness.
