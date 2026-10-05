# datagen — synthetic macro trajectories

`datagen` generates verified training trajectories for every macro in the registry. Each
trajectory is one macro (or a short chain) performed on a MiniWeb train site, recorded as
**screenshots + pixel actions**. A student model learns to act from these pixels.

The executor is a coding LLM with privileged DOM access. It writes a script against a restricted
action wrapper, so it does not have to perceive the page to act. Privileged information (site
map, DOM, backend state, guides) decides which tasks are made and how they are executed, but it
never enters a training trajectory. Failed attempts are kept separately as negatives.

## What humans provide

Every human input is fixed before a run starts:

| Input | Where |
|---|---|
| The websites and their data | `sites/`, `data/trimmed_miniweb.db` |
| The macro registry, and where each macro lives on each site | `data/macros.yaml`, `data/macro_locations.yaml` |
| What a macro's target looks like on a page | control-kind code, `datagen/kinds/` |
| Human demonstrations: annotated recordings on train sites, summarized once per macro into a guide | `data/annotations/` → `data/datagen/guides/` |
| The train/test site split | `data/datagen/site_split.json` |

Nobody curates anything inside a run. Each keep or drop decision comes from the deterministic
backend gate (plus the LLM judge unless `--no-judge` is set), dedup and the per-site caps.
The one hand-maintained list that affects outputs is `retired.json` (see
[Retired trajectories](#retired-trajectories)).

## One command

```bash
PY=~/.conda/envs/miniweb/bin/python
$PY -m datagen run --run-id myrun --target 100 --no-judge --workers 12 --servers 6
```

Without `--macros`, the run covers every macro that some control kind serves. That is all
46 registry macros: `$PY -c "from datagen import kinds; print(len(kinds.supported_macros()))"`.
`run` first builds anything that is missing: the site split, the guides for the run's macros
(and for macros a mid-chain prefix may demonstrate), and the site maps of the sites it needs.
It then runs the stages below, writes the exports and prints the yield log.

To resume an interrupted run, run the same command again. Each stage is skipped when its
output exists, and `--redo <stage>` recomputes one stage. A new `--run-id` with the same
`--target` tops each macro up: earlier runs' kept trajectories count toward the target and
their dedup keys are excluded from sampling.

Requirements:
- Gemini credentials in `.env` for the LLM stages. All stages default to `gemini-3.5-flash`;
  override per stage with `DATAGEN_MODEL_GUIDE`, `_SUGGEST`, `_EXECUTOR` or `_REASON`.
- The headless Chromium in `config.CHROME`: `chromium-1117`, overridable with `DATAGEN_CHROME`.

## Stages

`runs/` means `data/datagen/runs/`.

| # | Stage | Module | Output |
|---|---|---|---|
| 0 | Train/test **site** split, decided once before anything is generated | `split.py` | `data/datagen/site_split.json` (52 train / 13 test sites) |
| – | Privileged site map: crawl train sites, find controls, probe each control's backend signature | `sitemap.py` | `data/datagen/sitemap/<site>.json` |
| 1 | Guide: up to 24 human demonstrations of one macro (train sites) → a site-agnostic procedure | `guides.py` | `data/datagen/guides/<macro>.{json,md}` |
| 2 | Sample (site, target control, argument, start state); stratified, capped, deduped, dry-run validated | `sampler.py` | `runs/<id>/params.jsonl`, `infeasible.jsonl`, `spare.jsonl`, `caps.json` |
| 3 | Suggest: an NL instruction around the sampled parameters, plus the expected backend check | `suggester.py`, `checks.py` | `runs/<id>/tasks.jsonl` |
| 4 | Execute: the LLM writes a script for the restricted wrapper; screenshots and pixel actions are recorded (up to `--attempts` tries) | `executor.py`, `actions.py`, `driver.py` | `runs/<id>/episodes/<task>/a<n>/` |
| 5 | Filter: backend gate (+ judge), dedup, per-site cap, `--target`; failures go to the failure pool | `filter.py`, `judge.py` | `kept.jsonl`, `surplus.jsonl`, `failure_pool.jsonl`, `judged.jsonl` |
| – | Finalize: kept attempt → student-neutral trajectory + element side file (no LLM) | `trajectory.py`, `elements.py` | `runs/<id>/accepted/<task>/` |
| 6 | Thoughts (**optional, off by default**): a VLM writes one thought per step in a given style | `reasoning.py` | `accepted/<task>/thoughts/<style>.json` |
| – | Export (student choices are applied here), audit pages, yield log | `export.py`, `pipeline.py` | `export/train[.<style>].jsonl`, `audit/<macro>.html`, `yield.json` |

## `run` options

| Flag | Default | Meaning |
|---|---|---|
| `--macros m1 m2 …` | all supported | macros to generate |
| `--target N` | – | kept trajectories per macro, counting earlier runs. Sets the sample size to `ceil(missing × --overshoot)` (default 1.25). Opens the per-site cap to `ceil(N / candidate sites)`, then fills any remaining gap from sites that have more candidates. Forms, tools and image ops get more value sets per control (up to 60) |
| `--n N` | 16 | feasible tuples per macro (without `--target`) |
| `--no-judge` | off | keep on the deterministic backend gate alone, with no LLM judge |
| `--propose-site-cap`, `--per-site-cap` | 2, 2 | tuples proposed / trajectories kept per site per macro |
| `--mid-chain-share`, `--preset-share` | 0.3, 0.15 | share of non-fresh start states |
| `--attempts` | 3 | executor attempts per task |
| `--thoughts {none,browser_use,short}` | none | generate stage-6 thoughts during the run |
| `--redo STAGE …` | – | recompute `sample`, `suggest`, `execute`, `filter`, `finalize`, `thoughts` or `export` |
| `--stop-after suggest` | – | make tasks without executing them (used for validation sets) |
| `--workers`, `--servers`, `--ports` | 4, 2, 8300… | parallel browsers and MiniWeb servers |

`run` starts its own MiniWeb servers on ports **8300–8320 only**, reusing a server that is
already up on one of them. Other ports are refused; 8200–8211 belong to evaluation runs.
`MINIWEB_DATAGEN_DIR` moves the whole `data/datagen/` tree elsewhere. For example, WebMix
generates its held-out validation tasks into `data/webmix/valgen/`, whose split lists the
held-out sites as "train".

## Other subcommands

```bash
$PY -m datagen split [--force]                   # build or load the persisted site split
$PY -m datagen sitemap --workers 4               # crawl + probe the train sites the macros need
$PY -m datagen sitemap --kinds board reveal      # re-discover just these kinds, merged into the maps
$PY -m datagen sitemap --sites banking --force --max-pages 80 --per-pattern 8 --max-depth 3   # crawl deeper
$PY -m datagen guide --macros search [--force]   # stage 1 (cached per macro)
$PY -m datagen thoughts --run-id myrun --style browser_use     # stage 6 later, from saved screenshots
$PY -m datagen export --run-id myrun --thought-style none --coord-mode normalized --coord-scale 1000
$PY -m datagen export --run-id myrun --coord-mode pixel --resolution 1280 800
$PY -m datagen yield --run-id myrun              # proposed → feasible → worded → executed → backend → judge → kept → final
$PY -m datagen audit --run-id myrun [--n 30]     # judge-audit pages per macro
$PY -m datagen judge-controls --run-id myrun     # judge negatives: empty / swapped / wrong-option evidence
$PY -m datagen upgrade --run-id myrun            # migrate v1 trajectories to v2, backfill elements.json (no LLM)
$PY -m datagen view                              # data/datagen/viewer/: every kept trajectory, by family and macro
cd data/datagen && python3 -m http.server 8765   # then open http://localhost:8765/viewer/
```

## Control kinds (`datagen/kinds/`)

Every stage is macro-generic. The macro-specific part is a **control kind**: one class per
control type, which declares `macros = {macro: role}`. The registry imports every module in the
package. `tests/test_datagen_kinds.py` checks that every canonical macro in `data/macros.yaml`
has a kind, so adding a macro means adding or extending a kind.

A kind implements the following hooks (base class in `kinds/base.py`):
- **Required:**
  - `discover`: find its controls in a read-only page scan.
  - `arguments`: the argument space.
  - `apply`: privileged Playwright application in a throw-away session, used for the probe and the dry run.
  - `check`: the expected backend check.
  - `describe` / `say` / `mentions`: what the suggester writes and must mention.
  - `step_spec` / `script_task` / `locate` / `example`: the executor's prompt.
- **Optional:**
  - `setup`: unrecorded session preparation, e.g. a logged-out start or 2FA off.
  - `files`: what `act.upload` may pick.
  - `open_urls`: paths `act.open_url` may open.
  - `element_key` / `dedup_value`: dedup identity.
  - `serves` / `arguments_for`: one control serving several macros.
  - `needs_probe=False` + `static_probe`: no backend probe at crawl time.
  - `dry_run`: the kind's own feasibility run, which may fill in the argument and the check.
  - `changes_site`, `forbidden`: e.g. the answer must not appear in the instruction.

| Module | Kinds | Macros | Check |
|---|---|---|---|
| `listing.py` | `select`, `link` | filter_by_dropdown, sort_by_form | GET carrying the option |
| `filters.py` | `choice`, `chips`, `daterange`, `slider`, `searchbox` | filter_by_options, filter_by_date_range, filter_by_slider, search | GET carrying the value(s); sliders as a band, reached by pointer clicks |
| `nav.py` | `navlink` | navigate_by_route | GET of the destination |
| `compare.py` | `compare` | compare_by_form | GET carrying the choice |
| `buttons.py` | `button` (by label) | toggle_relationship, feedback_by_react, delete_from_table, play_by_playback, join_meeting, copy_content, export, share_by_form, cancel_by_form, edit_by_ranking | recorded data changes, request, clipboard or download |
| `rating.py` | `rating` | feedback_by_star | recorded |
| `forms.py` | `form` (role from submit label, action, heading) | create / edit / configure / share / pay / checkout / book / cancel / authenticate _by_form, message_from_free_text, feedback_by_text, sign_by_text, translate_by_query, get_nav_route, join_meeting | recorded |
| `io.py` | `upload` | upload_file | recorded |
| `gesture.py` | `dragorder`, `canvas` | edit_by_ranking, reposition_by_drag, sign_by_freeformdrawing, edit_by_image | recorded |
| `grid.py` | `gridcell` | edit_by_cell | recorded |
| `qa.py` | `qa` (a table or repeated cards) | report_information (op: read / extremum / count / compute / compare / verify), count_entries | answer computed in code |
| `playback.py` | `player` | search_by_playback | answer from the deterministic timeline |
| `reveal.py` | `reveal` | reveal_by_2fa | value shown after the one-time code |
| `carry.py` | `carry` (record on site A, search box on site B) | carry_info_cross_site | B's search request + value seen on A |
| `tools.py` | `tool` (Convert / Calculate panel) | compute_by_tool | the tool's request carrying the inputs |
| `imageops.py` | `imageop` | edit_by_image | recorded |
| `textbox.py` | `textbox` | edit_by_textbox | recorded |
| `saveas.py` | `saveas` (`[data-save-as]` dialog) | save_by_form | recorded (file-system overlay) |
| `mapview.py` | `mapview` (Leaflet map) | search_by_pan_zoom | answer (popup address) + a map drag |
| `program.py` | `program` (code editor + Run) | write_executable_program | run request answering the reference's output |
| `board.py` | `board` (stickies under column headings) | reposition_by_drag | the move request, position inside the target column |

## Checks, gate and judge

**Probed checks.** The expected check is built from the control's probed signature, not by
an LLM: it is the request the site receives when the argument is applied
(`checks.build_check`). The check passes when an accepted request carries the target value,
plus any state that must survive (`keep`, for preset and mid-chain starts), and the last
request to that endpoint still does.

**Recorded (oracle) checks.** For steps that change data, the dry run performs the step twice,
each time in a fresh session. It records the session's effective changes against the base tables
(`/_admin/changes`, `app.db.session_changes`) and keeps only the fields both runs agree on. An
attempt passes when it makes each recorded change and nothing else in those collections.
Steps that change no data are checked on the request, the clipboard text or the download.
Form values come from `formvalues.py`: an LLM proposes value sets per form, which are cached;
sign-in forms use the site's own accounts.

**Answer steps.** Macros that report to the human end with `act.answer(text)`. The expected
answer is computed in code from table cells, a timeline or page data, never by an LLM. Every
`evidence` string must have been visible in the viewport in one of the recorded screenshots.

**The gate.** `checks.gate` = the check above AND the same expectation run as an
`evaluation/verifiers.py` spec through `verify_task`. Both must pass. The dry run also requires
that the check FAILS on the start state, so no task can be passed without doing anything.

**The judge** (`judge.py`) reuses `evaluation/macro_judge.py`: its prompt, rubric, evidence
digest and best-of-3 voting. The reference is the task specification instead of a human span.
With the judge on, a trajectory is kept only if the gate AND the judge pass. `--no-judge`
keeps on the gate alone. `judge-controls` re-judges kept tasks against evidence that must
fail, to check that the judge is not a rubber stamp.

## The executor's action wrapper (`actions.py`)

The script can reach only three objects:

- `dom`: privileged, read-only queries to find targets (boxes, labels, options, URL).
- `act`: mouse and keyboard at jittered points inside the boxes of **visible, on-screen,
  hit-testable** elements that `dom` returned. Scrolling is its own recorded action
  (`act.scroll_into_view`), and keys are allow-listed. Navigation is limited to
  `act.open_url(path, new_tab=False)`, which accepts only the paths the kind allows, and
  `act.switch_tab(i)`.
- `expect.backend()`: the script ends by asserting the expected evidence. The harness then
  re-checks it independently.

`validate_script` rejects imports, dunder access, while loops, class definitions and any
Playwright/JS escape hatch (`page`, `evaluate`, `goto`, `fill`, `locator`, …). Violations raise
`PolicyViolation`, a `BaseException`, so a script's `except Exception` cannot swallow it.

Native `<select>` menus are operated with the keyboard after clicking them open. Headless
chromium-1117 draws the open list, but mouse clicks do not reach it.

## Outputs

`data/datagen/` holds:

| Path | Contents |
|---|---|
| `site_split.json`, `guides/` | versioned inputs (not gitignored) |
| `sitemap/<site>.json` | privileged site maps |
| `formvalues/`, `qa_records/`, `programs/`, `carry_pairs/` | per-kind caches |
| `runs/<id>/` | one run (layout below) |
| `retired.json` | superseded kept trajectories (see below) |
| `viewer/` | output of `datagen view` |

A run directory `runs/<id>/` contains:
- `run.json`: the arguments.
- `run.log`.
- `params.jsonl` and `tasks.jsonl`.
- `episodes/<task>/a<n>/`: every attempt.
- `kept.jsonl`, `surplus.jsonl`, `failure_pool.jsonl` and `judged.jsonl`.
- `accepted/<task>/`, `export/`, `audit/` and `yield.json`.

An accepted trajectory (`accepted/<task>/`) has three parts:

- `trajectory.json` (`datagen.trajectory/v2`): the instruction, `history` (the steps of a
  preceding macro for mid-chain starts) and `steps`, each `{i, screenshot, action}` in
  recording-viewport pixels (1280 × 800). It carries no thoughts and no coordinate convention.
- `thoughts/<style>.json`: optional, one file per style, aligned with the steps.
  `export --thought-style` picks a style and skips trajectories that lack it.
- `elements.json`: the **privileged element side file**, one entry per step. Each entry gives
  the targeted element (selector, role, accessible name, label, box), page URL, scroll
  position, the jittered point and select values before and after. It is never exported, and
  `tests/test_datagen.py` enforces that. Schema: `elements.py`.

The student's choices are applied only at export: the thought style and the coordinate
convention (normalized 0–1000 by default, or pixels at `--resolution W H`).

## Diversity and the split

- Only train sites are touched (`split.assert_train`). The split is a seeded greedy set cover
  over a ~20% test budget. Every macro on ≥ 4 sites gets a test site, and every macro keeps at
  least max(3, 60%) of its sites in train.
- The sampler round-robins across the train sites that support a macro, takes the least-used
  control first and draws options without replacement. The filter applies a second per-site
  cap on what is kept.
- Dedup key: `(site, target element, argument)`. The element is the control's backend identity
  `METHOD path param`, which is stable across re-crawls.
- Start states: `fresh`; `preset` (another filter already set through the start URL);
  `mid_chain` (a preceding filter or sort on the same page is executed first, and its steps
  become `history`).

## Retired trajectories

`data/datagen/retired.json` lists kept trajectories that later generator fixes superseded, plus
individual task-quality defects. It has the form `{"runs": {run: [macro, …]}, "task_ids": […]}`.
The files stay on disk. `filter.kept_keys` drops them from `--target` counting and from dedup,
and `viewer._kept_rows` drops them from the viewer and from the WebMix replay. The list is
written by hand between runs. A fresh run with the current code does not need it.

## From trajectories to training data

Kept trajectories are student-neutral. `export` writes generic JSONL. For the WebMix agents,
`python -m webmix replay` re-plays every kept trajectory through the browser-use harness,
producing that harness's exact prompts as training rows. That step, the augmentations,
LoRA training and the benchmarks are covered in [`webmix/README.md`](../webmix/README.md).
The replay skips `report_information` and `count_entries`: question answering is trained on
rejection-sampled human tasks instead.
