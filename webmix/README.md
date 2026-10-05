# webmix — training and agents on MiniWeb data

`webmix` turns the kept `datagen` trajectories into training rows, trains LoRA adapters on
**Qwen3.5-4B**, serves them with vLLM, and runs them as a **planner agent with family
specialists**. One browser-use harness is used for training, replay and every benchmark:
MiniWeb, WebArena-Lite, WebVoyager and Online-Mind2Web.

Data generation is documented in [`datagen/README.md`](../datagen/README.md). Everything this
package writes goes under `data/webmix/`, which is gitignored.

## At a glance

| Step | Command | Output |
|---|---|---|
| 1. Replay kept trajectories into browser-use rows | `python -m webmix replay` | `data/webmix/replay_v4/<task>/rows.jsonl` |
| 2. Augment (recovery, chain) | `python -m webmix replay --augment …` | more episodes in the same dir |
| 3. Reasoning rows (rejection sampling on human tasks) | `python -m webmix.evaluate --human --human-split train --record-rows …` | `data/webmix/eval/rs_reasoning/` |
| 4. Train adapters | `python -m webmix.train` (webmix env) | `data/webmix/adapters/<name>/` |
| 5. Serve base + adapters | `bash webmix/serve.sh` | vLLM on `:8400` |
| 6. Evaluate | `webmix.evaluate` (MiniWeb), `webmix.wa` (WebArena-Lite), `webmix.om2w` + `webmix.om2w_judge` (live web) | `data/webmix/{eval,wa,om2w/runs}/` |
| 7. Inspect | `python -m webmix.eval_viewer` | `data/webmix/viewer/` |

### Environments

| Env | Used for | Notes |
|---|---|---|
| `miniweb` (`~/.conda/envs/miniweb`) | replay, evaluate, wa, om2w, judges | browser-use 0.13, Playwright, headless chromium-1117 |
| `webmix` (`~/.conda/envs/webmix`) | `webmix.train`, vLLM | torch, transformers, peft, vLLM, flash-linear-attention, wandb. Needs `LD_LIBRARY_PATH=$ENV/lib` (serve.sh sets it) |

The MiniWeb servers these tools start go through `datagen.browser.Servers`, so their `--ports`
must be in **8300–8320**. vLLM listens on 8400.

## The harness (`harness.py`)

- **Settings:** browser-use in flash mode (output = memory + action), one action per step,
  vision on. The observation is browser-use's DOM element list plus a 1280 × 800 screenshot.
- **Coordinates:** on a 0–1000 scale of the screenshot, the convention Qwen3.5 grounds in.
- **Custom actions:** `drag`, `draw` and `macro_done`, which ends one macro segment.
  Actions that are useless offline are removed (`EXCLUDED_ACTIONS`).
- **Step budget:** 40 steps (`MAX_STEPS`). The prompt shows it, so replay and evaluation must
  use the same value.
- **Network:** offline sessions resolve only MiniWeb (and the WebArena host). `make_session(online=True)`
  opens the live web with a desktop user agent. The browser runs in UTC, the timezone datagen
  recorded in.

## Families and adapters

Macros are grouped into visuomotor families (`datagen/viewer.py` `FAMILIES`). Each family is
served by one adapter (`evaluate.ADAPTER_OF_FAMILY`):

| Family | Macros (examples) | Adapter |
|---|---|---|
| Drag & gesture | sliders, drag-reorder, drawing / signing, map pan, playback scrub | `drag` |
| Discrete selection | dropdowns, filters, sort, ratings, reactions, toggles, delete, play | `select` |
| Out-of-page I/O | upload, export, copy, save-as, image edits, 2FA reveal | `io` |
| Text entry, Form transaction, Navigation | search, messages, cells, forms, sign-in, routes, cross-site carry | `rest` |
| Reasoning base | report_information, count_entries | `reasoning` (the base model when none is served) |

## 1. Replay (`replay.py`, `__main__.py`)

Replay turns each kept trajectory into a plan of browser-use actions, such as `input`,
`select_dropdown`, `scroll`, `drag`, `macro_done` and `done`. It runs that plan through a real
browser-use Agent whose model is scripted. browser-use builds its normal prompt every step,
and a stand-in client records the request and answers with the plan's next action. The
training rows are therefore the harness's exact prompts.

- **Memory:** the base model writes each step's memory (`--memory-model qwen35-4b`, served at
  `--memory-url`, default `http://127.0.0.1:8400/v1`), so the targets read like the model's own words.
- **Gate:** an episode's rows are kept only if the task's backend gate (`datagen.checks.gate`)
  passes on the replayed session.
- **Excluded data:** retired trajectories (`data/datagen/retired.json`) and the
  question-answering macros (`report_information`, `count_entries`) are not replayed.
- **Results and resume:** every result is appended to `results.jsonl`. Passed episodes are
  skipped unless `--redo` is set.
- **Output dir:** `webmix.REPLAY_DIR` (default `data/webmix/replay_v4`, override with
  `WEBMIX_REPLAY_DIR`). Training and the planner read the same variable.

Start the base model first (`bash webmix/serve.sh`). Then replay in shards, giving each shard
its own MiniWeb ports:

```bash
PY=~/.conda/envs/miniweb/bin/python
$PY -m webmix replay --workers 6 --ports 8310,8311 --shard 0/4 --memory-model qwen35-4b &
$PY -m webmix replay --workers 6 --ports 8312,8313 --shard 1/4 --memory-model qwen35-4b &
$PY -m webmix replay --workers 6 --ports 8314,8315 --shard 2/4 --memory-model qwen35-4b &
$PY -m webmix replay --workers 6 --ports 8318,8319 --shard 3/4 --memory-model qwen35-4b &
wait
```

Other flags: `--macros m1,m2`, `--tasks id1,id2`, `--limit N`, `--headful`.

## 2. Augment (`augment.py`)

Variants are built only from trajectories whose plain replay passed. They are graded by the
same gates and need no API calls, because the memory model is the local base model.

- `--augment recovery --share 0.35`: inject one mistake right before a correctable step, then
  the correction. The mistake is a near-miss of typed text, another option of the same
  dropdown, or a slider click a fifth of the track away. Training skips the mistake row and
  the replayed prefix before it. The next step's memory has to notice the mistake.
- `--augment chain --per-page 3`: two kept trajectories of one site as one episode, either on
  the same page or via the site's own home link. The memory model merges the two instructions,
  and the episode must pass both gates.

```bash
$PY -m webmix replay --workers 6 --ports 8310,8311 --memory-model qwen35-4b --augment recovery --share 0.35
$PY -m webmix replay --workers 6 --ports 8310,8311 --memory-model qwen35-4b --augment chain --per-page 3
```

## 3. Reasoning rows

Question answering is trained on human tasks, not synthetic ones. The base model attempts the
train-site human reasoning tasks 4 times at T = 0.7, and passing episodes are kept as rows:

```bash
$PY -m webmix.evaluate --human --human-split train --human-macros report_information,count_entries \
    --arm base --repeats 4 --temperature 0.7 --record-rows --record-family "Reasoning base" \
    --verifier-only --workers 8 --ports 8306,8307 --out data/webmix/eval/rs_reasoning
```

The rows directory `data/webmix/replay_rs/` contains symlinks to every `replay_v4` episode plus
the passing `rs_reasoning` episodes. Train the `reasoning` adapter with
`WEBMIX_REPLAY_DIR=data/webmix/replay_rs`.

## 4. Train (`train.py`)

- **Model:** LoRA on `Qwen/Qwen3.5-4B`, language model only. q/k/v/o on the full-attention
  layers and gate/up/down on every layer; no vision tower.
- **Optimizer:** AdamW with cosine LR and 3% warm-up. Batch 1 × `--grad-accum` (8 = the global
  batch in rows).
- **Validation:** about 5% of trajectories are held out by task hash for validation CE. A
  variant follows its source trajectory.
- **Loss:** rows of the adapter's own families get CE. With `--beta > 0`, rows of the other
  families are **KL anchor** rows (`--anchor-ratio` per CE row, redrawn every epoch). They use
  the k3 estimator on the action tokens against the reference model, which is the base with
  the adapter disabled.
- **Branch-then-specialize:** `--init-adapter DIR` starts from an existing adapter (same rank
  and alpha) and anchors the KL rows to a frozen copy of it instead of the base.
- **Data scaling:** `--frac F` trains on a fixed fraction of the generated episodes. Whole
  episodes are kept or dropped, chosen by hash, so the subsets are nested across fractions.
- **Other flags:** `--exclude-variants recovery,chain`, `--ce-on action`, `--limit` /
  `--max-steps` (smoke tests).
- **Logging and checkpoints:** runs log to wandb (`--wandb-project webmix-pilot`; `''`
  disables it) and to `train_log.jsonl`. Checkpoints are written every `--save-every` rows and
  at each epoch boundary. The final adapter and `webmix_meta.json` land in `--out` (default
  `data/webmix/adapters/<adapter>`).
- **Multi-GPU:** `torchrun --nproc_per_node N -m webmix.train …` takes the same flags and
  all-reduces the LoRA gradients.

`--adapter` takes one of these names: `pooled` (all families), `drag`, `io`, `select`, `rest`,
`reasoning` and `planner`. The last one trains on rows built by `webmix.planner build` for the
older screenshot planner.

The adapters behind the reported results (from their `webmix_meta.json`):

| Adapter | Recipe |
|---|---|
| `pooled_v4` | all families, 1 epoch, lr 1e-4, r 64 / α 128, no anchor (27.6K CE rows) |
| `drag_v5b`, `io_v5b`, `select_v5b`, `rest_v5b` | `--init-adapter pooled_v4`, lr 5e-5, β 0.1, anchor ratio 0.25, 1 epoch (drag 2), r 64 / α 128 |
| `reasoning_v4` | rejection-sampled rows, 3 epochs, lr 1e-4, β 0.1, anchor ratio 0.5, r 64 / α 128 |

```bash
TRAIN="env LD_LIBRARY_PATH=$HOME/.conda/envs/webmix/lib $HOME/.conda/envs/webmix/bin/python -m webmix.train"
A=data/webmix/adapters
$TRAIN --adapter pooled --epochs 1 --beta 0 --rank 64 --alpha 128 --out $A/pooled_v4
$TRAIN --adapter select --init-adapter $A/pooled_v4 --epochs 1 --lr 5e-5 --beta 0.1 --anchor-ratio 0.25 \
    --rank 64 --alpha 128 --out $A/select_v5b        # likewise drag (--epochs 2), io, rest
WEBMIX_REPLAY_DIR=data/webmix/replay_rs $TRAIN --adapter reasoning --epochs 3 --lr 1e-4 --beta 0.1 \
    --anchor-ratio 0.5 --rank 64 --alpha 128 --out $A/reasoning_v4
$TRAIN --adapter pooled --epochs 1 --beta 0 --rank 64 --alpha 128 --frac 0.1 --out $A/pooled_frac0.1   # data scaling
```

## 5. Serve (`serve.sh`)

`serve.sh` runs one vLLM server with the base model and any LoRA modules. A request selects
an adapter through the OpenAI `model` field: an adapter name, or `qwen35-4b` for the base.
Thinking is off.

| Variable | Default | |
|---|---|---|
| `MODEL` / `SERVED` | `Qwen/Qwen3.5-4B` / `qwen35-4b` | model and its served name |
| `PORT` | 8400 | |
| `LORA_MODULES` | – | `name=path` pairs, space- or comma-separated |
| `MAX_LORA_RANK` / `MAX_LORAS` | 16 / 4 | set 64 / 6 for the adapters above |
| `MAX_MODEL_LEN`, `GPU_UTIL`, `EAGER` | 32768, 0.85, 1 | `EAGER=1` skips CUDA-graph capture |
| `WEBMIX_ENV` | `~/.conda/envs/webmix` | |

```bash
M=$PWD/data/webmix/adapters
MAX_LORA_RANK=64 MAX_LORAS=6 LORA_MODULES="drag=$M/drag_v5b io=$M/io_v5b select=$M/select_v5b \
rest=$M/rest_v5b reasoning=$M/reasoning_v4 pooled_v4=$M/pooled_v4" bash webmix/serve.sh
```

## 6. The agent

### Planner agent (`planner_agent.py`)

The planner is itself a browser-use Agent on the live session. Every turn it sees the URL,
the interactive elements and the screenshot. It cannot click, type or navigate. Its tools are:

- `delegate(family, instruction)`: runs that family's specialist as its own browser-use
  episode on the same browser, then returns what the specialist did plus a page check.
- `scroll`.
- `done`: ends the task; its text is the answer.

The family definitions in its prompt are `planner.FAMILY_DEFS`.

- **Budget:** specialist site actions share the single agent's budget (40, or `--max-steps`
  on the live web). Each delegation runs at most 15 specialist steps (`--sub-cap`), and planner
  turns are capped separately.
- **Models:** the planner is `--planner-name`; in the reported runs it is the untrained base,
  `qwen35-4b`. Specialists come from `--adapters`. A family without its adapter falls back to
  `--fallback` (`pooled_v4`). Reasoning goes to `reasoning`, else to the base.

Versions live in `VERSIONS`, and every one is kept for reproducibility:

| Version | What it is |
|---|---|
| `v1`–`v5`, `v6c` | earlier iterations (prompt wording, flash output, site-action budget, specialist context) |
| **`v6`** | **the reported harness**: flash output, a page check (did the URL change) in each result, specialists see only their instruction, the budget counts site actions only, 25 planner turns, and an identical delegation on an unchanged page is refused |
| `v7` | v6 plus harness fixes: the budget fix (with *k* site actions left a specialist runs *k*+1 steps, because browser-use spends its last step on a forced `done`); the planner's own screenshots in the live-web trajectory; progress control (a step already tried on the same page state is refused, a warning after 3 delegations without progress, a forced `done` after 6, and a specialist is stopped after 3 actions that changed nothing); page-state diffs in every result plus a constraint checklist; a guard against invented credentials. It tied v6 on the MiniWeb dev sets (56 vs 57 of 120 tasks) |

Other arms in `webmix.evaluate`:
- `base`: the untrained model as one agent.
- `pooled`: one adapter for every step.
- `oracle`: the task's own family adapter, for single-macro validation.
- `planned`, `oracle_sub`, `planned_sub`: the older screenshot planner and subtask routers
  (`planner.py`), superseded by `agent_planner`.

## 7. Evaluate

### MiniWeb (`evaluate.py`)

- `--human`: the human-written tasks (`data/annotations/*/*/task.json`), started like
  `evaluation/run_agent_verify.py` and graded by each task's `verifier.json`.
  `--human-split test` (the default) gives the 63 tasks on the 13 held-out sites of
  `data/datagen/site_split.json`. `--human-split train` gives the 310 train-site tasks.
- **Dev sets** for agent development are two disjoint sets of 60 train-site tasks:
  `data/webmix/eval/pagent_devset.txt` and `pagent_devset2.txt` (comma-separated ids for
  `--task-ids`). The held-out 63 are used only to measure.
- `--tasks FILE`: generated single-macro tasks, graded by the datagen gate. Validation v2 is
  `data/webmix/valgen/val_v2.jsonl`: 115 tasks generated on the held-out sites with
  `datagen run --stop-after suggest`, never executed or trained on.
- **Grading:** `--verifier-only` grades with the backend check plus the task's verifier. The
  QA chain's last tier is an LLM, `gemini-3.5-flash-lite`; the flash macro judge is never used.
  Every episode saves `grade_inputs.json`, and `--regrade DIR` recomputes grades from those
  inputs.
- **Other flags:** `--repeats`, `--temperature`, `--timeout`, `--workers`, `--ports`.

### WebArena-Lite-v2 (`wa.py`)

- **Tasks:** ScaleCUA's 154 tasks with their evaluator, vendored in
  `data/webmix/wa_lite_v2/`. They run on four deployments, whose URL maps are in
  `wa_lite_v2/config/envs/webarena/init/`.
- **Execution:** each instance runs its share of the tasks in order. Logins are made fresh
  per task. `--split dev|test|all` selects a half from `data/webmix/wa/split_5050.json`.
- **Judge:** the fuzzy-match judge is `--judge` (default `gemini-3.5-flash-lite`, used for all
  reported arms). The benchmark's own judge is `gpt-4o-2024-11-20`. `--regrade` re-scores
  stored answers with another judge.
- **Resets:** `wa.py` does not reset the sites. Reset every instance before each full run
  through its token-gated reset API. The reset helper reads its credential from the
  environment, so never write it into a script or a file.

### Live web (`om2w.py`, `om2w_judge.py`)

`om2w.py` runs Online-Mind2Web (`--bench om2w`) or WebVoyager (`--bench webvoyager`) on the live
web. Each episode is saved in Online-Mind2Web's v1 trajectory layout: `<out>/<task>/result.json`
and `trajectory/<i>_full_screenshot.png`.

| Flag | Meaning |
|---|---|
| `--arm base|agent` | base single agent, or the planner agent (`--agent-version`, default v6) |
| `--tasks FILE`, `--task-ids a,b` | task file (default: the full benchmark), or a subset |
| `--max-steps N` | base: agent steps; agent: the specialists' site-action budget (default 40) |
| `--planner-turns N` | agent: planner-turn cap (default: the version's) |
| `--timeout S` | per-episode wall clock; a timed-out episode keeps the steps it took |
| `--pace-dir DIR`, `--pace-cooldown S` | at most one episode per website at a time across all runs on the node, `S` (120) seconds apart |
| `--workers N`, `--slot-range a:b` | worker processes; run only slots `a..b-1` here to split a run across nodes. Finished episodes are never re-run |

`om2w_judge.py` scores a run directory with the official judges. It reads `OPENAI_API_KEY`
from the environment or `.env`.

- **Online-Mind2Web:** the vendored official WebJudge (`data/webmix/om2w/official/`;
  `PATCHES.md` lists the o-series API changes). It uses `o4-mini`, mode
  `WebJudge_Online_Mind2Web_eval` and score threshold 3, and writes to `<run>_webjudge/`.
- **WebVoyager:** the official `auto_eval.py` prompts with the last 15 screenshots,
  max_tokens 1000, seed 42 and temperature 0. A run with no answer scores 0. The judge model
  is `gpt-4o`, because the official `gpt-4-vision-preview` is retired. Output goes to
  `<run>_wvjudge/`.

### Normalized live-web task sets

The reported live-web numbers leave out impossible tasks, and sites that block our network:

| File | Tasks | Definition |
|---|---|---|
| `data/webmix/webvoyager/WebVoyager_reduced_536.jsonl` | 536 of 643 | See below |
| `data/webmix/om2w/Online_Mind2Web_reduced_280.json` | 280 of 300 | See below |

How each set is built:

- **WebVoyager (536):**
  - Start from the 595 tasks that Fara-7B and MolmoWeb evaluate on
    (`webvoyager/filtered/`). This drops the 48 tasks they treat as impossible.
  - Remove the 43 Cambridge Dictionary tasks, because Cloudflare blocks our network on
    nearly every episode.
  - Remove the 16 tasks listed in `webvoyager/outdated_tasks_2026-10-02.json`. We ran them
    with the original 2023–24 text, which Fara's file had refreshed; they were found by text
    difference, not by results.
  - Texts come from our run file `WebVoyager_data_2026-10-01.jsonl`, where the Booking and
    Google Flights dates are moved forward; see `webvoyager/README.md`.
- **Online-Mind2Web (280):**
  - Remove the 20 tasks on the 9 sites in `om2w/blocked_sites_100step.json`. A site is set
    aside when, in at least half of its 100-step episodes pooled over the arms, the agent's
    final answer reports a network gate (Cloudflare, CAPTCHA, access denied, human
    verification).
  - Only whole sites are removed, never single episodes. There is no published impossible-task
    list for this benchmark.

## Results

These compare **MiniWeb v5** (planner agent v6 + `*_v5b` specialists + `reasoning_v4`) with the
untrained Qwen3.5-4B as a single agent, in the same harness:

| Benchmark | Protocol | Base | MiniWeb v5 |
|---|---|---|---|
| MiniWeb held-out | 63 human tasks on 13 held-out sites, 3 runs, 40 steps, task verifiers | 37.0% | 51.3% |
| WebArena-Lite-v2 | 154 tasks, 3 runs, 40 steps | 27.1% | 34.2% (paired permutation p = 0.019) |
| WebVoyager | normalized 536, 1 run, 100 steps, GPT-4o auto_eval | 45.5% | 69.2% |
| Online-Mind2Web | normalized 280, 1 run, 100 steps, WebJudge o4-mini | 17.9% | 26.1% |

## Reproduce

These commands assume the server from step 5 is running.

```bash
PY=~/.conda/envs/miniweb/bin/python
AG="--agent-version v6 --planner-name qwen35-4b --adapters drag,io,select,rest,reasoning --fallback pooled_v4 --timeout 2400"

# MiniWeb held-out (63 tasks); dev: add --human-split train --task-ids $(cat data/webmix/eval/pagent_devset.txt)
$PY -m webmix.evaluate --human --arm agent_planner $AG --verifier-only --workers 6 --ports 8306,8307 --out data/webmix/eval/heldout_v5
$PY -m webmix.evaluate --human --arm base --verifier-only --workers 6 --ports 8306,8307 --out data/webmix/eval/heldout_base

# WebArena-Lite-v2 (reset all instances first)
$PY -m webmix.wa --router planner_agent $AG --arm agent_v5 --split all --instances 1,2,3,4 --out data/webmix/wa/agent_v5_s1
$PY -m webmix.wa --arm base --model qwen35-4b --split all --instances 1,2,3,4 --out data/webmix/wa/base_s1

# WebVoyager (normalized), 100-step budget
$PY -m webmix.om2w --bench webvoyager --tasks data/webmix/webvoyager/WebVoyager_reduced_536.jsonl --arm agent \
    --max-steps 100 --planner-turns 60 --timeout 7200 --workers 24 --out data/webmix/om2w/runs/wv100_v5
$PY -m webmix.om2w --bench webvoyager --tasks data/webmix/webvoyager/WebVoyager_reduced_536.jsonl --arm base \
    --max-steps 100 --timeout 7200 --workers 24 --out data/webmix/om2w/runs/wv100_base
$PY -m webmix.om2w_judge data/webmix/om2w/runs/wv100_v5 --bench webvoyager

# Online-Mind2Web (normalized), 100-step budget, paced
$PY -m webmix.om2w --tasks data/webmix/om2w/Online_Mind2Web_reduced_280.json --arm agent --max-steps 100 \
    --planner-turns 60 --timeout 7200 --pace-dir /tmp/om2w_pace --workers 12 --out data/webmix/om2w/runs/om2w100_v5
$PY -m webmix.om2w_judge data/webmix/om2w/runs/om2w100_v5 --workers 4

# browse runs
$PY -m webmix.eval_viewer && (cd data/webmix && python3 -m http.server 8766 --bind 127.0.0.1)   # http://localhost:8766/viewer/
```

The live-web agent arm's defaults are already `--planner-name qwen35-4b --adapters
drag,io,select,rest,reasoning --fallback pooled_v4`.

The shell scripts in `data/webmix/*.sh` are the launchers of the recorded runs:
- `post_v4.sh`: replay + augment.
- `post_rs.sh`, `post_reasoning.sh`: reasoning rows and the reasoning adapter.
- `post_v5b.sh`, `run_wa_v5b.sh`: v5 on MiniWeb and WebArena.
- `run_v7_dev.sh`: v7 vs v6 on the dev sets.
- `fetch_base.sh`: fetch and judge the live-web base runs.

Multi-GPU training and the live-web runs ran on a 4 × A800 cluster node. The wrapper scripts
there (`train.sh`, `eval.sh`, `branch.sh`, `live_comp.sh`, `live_launch*.sh`) wrap the same
commands.

## `data/webmix/`

| Path | Contents |
|---|---|
| `replay_v4/` | current training rows (plain + recovery + chain episodes, `results.jsonl`) |
| `replay_rs/` | `replay_v4` + rejection-sampled reasoning episodes (symlinks) |
| `replay/`, `replay_templated/`, `replay_mem_px/`, `replay_v4s*/` | earlier row sets |
| `adapters/` | trained adapters (`*_v4`, `*_v5b`, `pooled_v4`, `reasoning_v4`, planners) |
| `eval/` | MiniWeb runs (`seeds/` = the repeated held-out runs), dev-set id files |
| `valgen/` | the validation-task datagen tree (`val_v2.jsonl`) |
| `wa/`, `wa_lite_v2/` | WebArena runs (`wa/seeds/`), the split, the vendored benchmark |
| `om2w/`, `webvoyager/` | live-web task files, official judges, exclusion lists, runs (`om2w/runs/`) |
| `planner/` | rows for the trained screenshot planners |
| `viewer/`, `logs/`, `*.sh` | eval viewer, logs, launchers |

## Tests

`tests/test_webmix_replay.py`, `tests/test_webmix_augment.py` and
`tests/test_webmix_evaluate.py` cover the pure parts: plan building, augmentation and routing.
