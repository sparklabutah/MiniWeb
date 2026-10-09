# Reproducing the paper

`python scripts/reproduce.py` is the one entry point; `scripts/paper.yaml` is its registry.

| Command | What it does |
|---|---|
| `python scripts/reproduce.py status` | Checks every run, RQ1 run and adapter the paper reads: present, and complete for its benchmark. |
| `python scripts/reproduce.py show <arm>` | Prints the model-server line and the run + grading commands behind every run of an arm. Arms: `base`, `pooled`, `planner`, `planner_pooled` (MiniWebAgent), `taskcentric` (the task-centric executor of Tab. 3), `agent` (specialists), `nodone` (stop-early control); `rq1` for the ten RQ1 agents. |
| `python scripts/reproduce.py run <arm> --bench <b> --seed <k> [--execute]` | One run (benchmarks: `single`, `heldout`, `wa`, `wv`, `om2w`). Prints unless `--execute`. |
| `python scripts/reproduce.py train <adapter> [--execute]` | Builds the adapter's training folder from its id list and prints the `torchrun` line with the paper's recipe. |
| `python scripts/reproduce.py figures [--only <name>]` | Regenerates every figure and table into `docs/figures/` and copies them into the paper source. |

## What lives where

- **Which runs the paper reads.** The figure configs: the named runs of `docs/figures/tables/tables_config.yaml` (one
  list per benchmark; figures report the mean over the list), `docs/figures/rq1/rq1_config.yaml`,
  `docs/figures/rq3/data_config.yaml`. `paper.yaml` adds runs that only the supplement reads.
- **How each run is made.** `paper.yaml`: the model server, the agent configuration per benchmark kind, the arms, the
  RQ1 agents, the adapters and their training recipe, the data pipeline, and the protocol deviations as they ran.
- **The training data.** `scripts/pools/`: `pool3k_plain_ids.txt` (the 3,128 generated trajectories),
  `pool3k_dirs.txt` (the 4,614 replayed episodes of the 27.6K-step set: plain, chains, recoveries).
  `data/webmix/replay_v4` holds them, so an adapter is trained on a folder of symlinks to its list
  (`scripts/reproduce.py train` builds it). The task-centric executor trains on `data/webmix/taskgen/rows_27k`.
- **Cluster wrappers.** `src/miniwebagent/scripts/cluster/`: `train.sh`, `eval.sh` (MiniWeb), `live.sh` (WebVoyager,
  Online-Mind2Web), `ownloop.sh` (RQ1 own-loop agents), `retry_timeouts.py` (sets aside live-web episodes ended by
  model-server timeouts, for a rerun), `opencua/` (OpenCUA-7B tokenizer + vLLM plugin). Set `WEBMIX_ROOT` (see
  `cluster/env.sh`). The cluster holds no API keys: MiniWeb runs are re-graded with `miniwebagent.evaluate --regrade` and
  live-web runs judged with `miniwebagent.om2w_judge` where the keys are.
- **WebArena-Lite.** `src/miniwebagent/scripts/webarena/ready.sh` resets the four instances and waits until every site serves
  (`WA_RESET_TOKEN`, `WA_HOST`).

## Environments

`scripts/envs/` pins the three environments the paper's runs used (`pip list --format=freeze`):

- `miniweb.txt` (Python 3.11): the app, annotation tool, MiniWebGen, the browser-use harness, grading, figures.
  Playwright 1.44 with Chromium build 1117.
- `miniwebagent.txt` (Python 3.12): vLLM 0.30 serving (`src/miniwebagent/scripts/serve.sh`) and LoRA training (torch 2.13, transformers
  5.17, peft 0.21).
- `fara.txt` (Python 3.11): Fara1.5-4B's released loop (`microsoft/fara` at a675d6d).

The repo's `requirements.txt` is the minimal install for running the app; these files are what produced the numbers.

## Grading

- MiniWeb: the task verifiers (`src/miniweb/evaluation/verifiers.py`); their answer checks fall back to Gemini 3.5 Flash-Lite
  (`miniwebagent.evaluate.QA_MODEL`) when the regex, exact and precise matchers cannot decide. RQ1 also uses the VLM judge
  (`python -m miniweb.evaluation.judge_runs`, Gemini 3.5 Flash).
- WebArena-Lite: the benchmark's evaluators; the fuzzy answer matches of 43 tasks use Gemini 3.5 Flash-Lite instead of
  GPT-4o (`miniwebagent.wa --judge`).
- WebVoyager: its GPT-4o judge; Online-Mind2Web: WebJudge (o4-mini) (`python -m miniwebagent.om2w_judge`).
