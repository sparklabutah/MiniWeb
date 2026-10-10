# Reproducing the paper

Every number in the paper comes from a run folder: one agent configuration ("arm") on one benchmark, one folder per
run. `scripts/paper.yaml` lists, for each arm, the run folders the paper reads, how each is made and the number the
paper reports; `scripts/reproduce.py` prints or runs the commands and compares your runs with the paper.

```bash
python scripts/reproduce.py show planner_pooled     # MiniWebAgent: model server, run and grading commands per benchmark
python scripts/reproduce.py run planner_pooled --bench heldout --seed 1 --execute
python scripts/reproduce.py table                   # every arm x benchmark: your mean next to the paper's number
```

For using MiniWeb beyond the paper (your own agent, more data, other graders), see [GUIDE.md](GUIDE.md).

- [What you need](#what-you-need)
- [Data and checkpoints](#data-and-checkpoints)
- [Where each result comes from](#where-each-result-comes-from)
- [Tab. 3: MiniWebAgent and its baselines](#tab-3-miniwebagent-and-its-baselines)
- [Tab. 2: skill profiles of ten agents](#tab-2-skill-profiles-of-ten-agents)
- [Training the executors](#training-the-executors)
- [Regenerating the data](#regenerating-the-data)
- [How close to expect](#how-close-to-expect)

## What you need

**Environments.** `scripts/envs/` pins the three the paper used (`pip list --format=freeze`):

| Environment | Used for |
|---|---|
| `miniweb` (Python 3.11, `scripts/envs/miniweb.txt`) | the sites, the agent harness (browser-use), the graders, MiniWebGen; Playwright 1.44 with Chromium build 1117 |
| `webmix` (Python 3.12, `scripts/envs/webmix.txt`) | vLLM 0.30 serving (`src/miniwebagent/scripts/serve.sh`) and LoRA training |
| `fara` (Python 3.11, `scripts/envs/fara.txt`) | only Fara1.5-4B's own agent loop in Tab. 2 |

`requirements.txt` is the minimal install for the sites; the pinned files are what produced the paper's numbers.

`serve.sh` looks for the vLLM environment at `$WEBMIX_ENV` (default `~/.conda/envs/webmix`).

**API keys** (in `.env`, see the [README](README.md#3-configure)):

- `GEMINI_API_KEY` (or Vertex): the VLM judge (Gemini 3.5 Flash), the verifiers' last answer tier and WebArena-Lite's
  fuzzy matches (Gemini 3.5 Flash-Lite), MiniWebGen.
- `OPENAI_API_KEY`: the live-web judges, as their benchmarks prescribe (WebVoyager: GPT-4o; Online-Mind2Web: WebJudge
  with o4-mini).

**Benchmarks.** MiniWeb needs nothing else: each run starts its own servers on ports 8300-8320. WebArena-Lite needs four
WebArena deployments and ScaleCUA's 154-task release with its evaluator in `data/webmix/wa_lite_v2/` (setup:
[src/miniwebagent/README.md](src/miniwebagent/README.md#webarena-lite-v2-wapy)). WebVoyager and Online-Mind2Web need
a browser and network access; their task sets are in `scripts/benchmarks/` (536 and 280 tasks; Supp. "Live-web
evaluation sets" explains the normalization).

**Compute and cost**, as measured on the paper's runs:

| Stage | Hardware | Time | API cost |
|---|---|---|---|
| MiniWeb held-out run (63 tasks), verifiers | 1 GPU | about 1 h | -- |
| Skill profile of one agent (376 tasks), VLM judge | 1 GPU | about 5 h | $0.045 per episode |
| WebArena-Lite run (154 tasks) | RTX 5090, 4 site instances | about 3 h | under $1 |
| WebVoyager run (536 tasks, 100 steps) | 24 or 40 GB GPUs | 10-15 GPU-h | $26 (GPT-4o judge) |
| Online-Mind2Web run (280 tasks, 100 steps) | 24 or 40 GB GPUs | 10-15 GPU-h | $92 (WebJudge, o4-mini) |
| Executor training, 27.6K steps | 4 x A800 | 5.6 h (22 GPU-h) | -- |
| Trajectory generation (MiniWebGen) | API calls | -- | $0.04 per kept trajectory |

MiniWeb and WebArena-Lite fit on one 32 GB GPU. On the live web, keep to 24 concurrent browsers per model server:
more made model calls time out and episodes end early.

## Data and checkpoints

```bash
python scripts/restore_site_db.py              # the sites: database, images, media
python scripts/fetch_tasks.py                  # the 376 human tasks and the 115 generated single-primitive test tasks
python scripts/fetch_adapters.py --all         # the paper's trained executors -> data/webmix/adapters/
```

To retrain the executors instead of downloading them:

```bash
python scripts/fetch_training_data.py                                # MiniWebGen's 4,614 episodes -> data/webmix/replay_v4/
python scripts/fetch_training_data.py --table task_centric_steps     # the task-centric comparison data
```

Everything comes from the Hugging Face Hub: the data from
[miniweb/MiniWeb](https://huggingface.co/datasets/miniweb/MiniWeb), the checkpoints from
[miniweb/MiniWebAgent](https://huggingface.co/miniweb/MiniWebAgent).

## Where each result comes from

| Result | Runs | Commands |
|---|---|---|
| Tab. 2, Fig. 5-6: skill profiles of ten untrained agents on the 376 tasks | `rq1` | `reproduce.py show rq1`, then `judge_runs.py` and `skill_report.py` |
| Tab. 3: Qwen3.5-4B as a single agent or a planner, untrained or trained, on four benchmarks | arms `base`, `pooled`, `planner`, `planner_pooled`, `taskcentric` | `reproduce.py show/run <arm>`, `reproduce.py table` |
| Fig. 7: practice per skill family on the 103 generated single-primitive tasks | `base`, `pooled` on `single` | `skill_report.py` on those runs |
| Supp.: every configuration (the specialists, the no-`done` control) | arms `agent`, `nodone` | `reproduce.py show/run <arm>`, `reproduce.py table` |
| Sec. 4.2: primitive success inside the held-out tasks (43.9% to 44.8% trained alone, 48.9% to 62.1% with the planner) | each arm's `heldout` runs | `skill_report.py --all-primitives`: the verifier column of "all instances", mean over the three runs |
| Supp.: grader agreement and demonstration checks | `rq1` runs, the human recordings | `python -m miniweb.evaluation.grader_agreement --parallel 4` |
| Supp.: compute | -- | the table above |

The benchmarks, as `reproduce.py` names them: `single` (the 103 generated single-primitive tasks of well-covered
primitives on the 13 held-out sites), `heldout` (the 63 human tasks of those sites), `wa` (WebArena-Lite, 154), `wv`
(WebVoyager, 536), `om2w` (Online-Mind2Web, 280).

## Tab. 3: MiniWebAgent and its baselines

Start the model server the arm needs (in the vLLM environment), then make its runs:

```bash
python scripts/reproduce.py show planner_pooled
```

```
# MiniWebAgent (planner + trained executor)
# model server (webmix env):
MODEL=Qwen/Qwen3.5-4B SERVED=qwen35-4b PORT=8400 MAX_LORA_RANK=64 MAX_LORAS=8 LORA_MODULES=pooled_v4=data/webmix/adapters/pooled_v4 bash src/miniwebagent/scripts/serve.sh

# heldout: human tasks of the 13 held-out sites (data/datagen/site_split.json)
python -m miniwebagent.evaluate --human --arm agent_planner --agent-version v6 --timeout 2400 --planner-name qwen35-4b --adapters none --fallback pooled_v4 --verifier-only --workers 6 --vllm http://127.0.0.1:8400/v1 --ports 8300,8301 --out data/webmix/eval/pagent_pooled_s1
...
```

`reproduce.py run <arm> --bench <bench> --seed <k> --execute` runs one of them into the paper's folder name, so that
`table` finds it (`--out` writes elsewhere). MiniWeb and WebArena-Lite runs are repeated three times (`--seed 1..3`)
and the paper reports their mean; the live-web benchmarks have one run each. A WebArena-Lite run first resets the four
instances (`src/miniwebagent/scripts/webarena/ready.sh`, which reads `WA_HOST` and `WA_RESET_TOKEN`); a live-web run is
followed by its judge, which `run` also executes.

```bash
for s in 1 2 3; do python scripts/reproduce.py run planner_pooled --bench heldout --seed $s --execute; done
python scripts/reproduce.py run planner_pooled --bench wv --execute
python scripts/reproduce.py table
```

```
Task success (%): reproduced = mean over the runs present (k of n runs), paper = the paper's number.

                                                          single             heldout                  wa                  wv                om2w
Single agent, untrained                        55.3 (3/3) | 55.3   37.0 (3/3) | 37.0   27.1 (3/3) | 27.1   45.5 (1/1) | 45.5   17.9 (1/1) | 17.9
...
MiniWebAgent (planner + trained executor)      71.5 (3/3) | 71.5   54.5 (3/3) | 54.5   36.4 (3/3) | 36.4   65.5 (1/1) | 65.5   33.9 (1/1) | 33.9
```

(This is `table` on the paper's own run folders; yours fill in as they finish.) `python scripts/reproduce.py status`
lists which runs are present and complete.

The arms and their executors:

| Arm | Agent | Executor adapter |
|---|---|---|
| `base` | single agent, untrained | none |
| `pooled` | single agent, trained | `pooled_v4` |
| `planner` | planner, untrained executor | none |
| `planner_pooled` | **MiniWebAgent** | `pooled_v4` |
| `taskcentric` | planner, executor trained on task-centric trajectories | `taskgen_pooled` |
| `agent` | planner, family specialists (Supp.) | `drag_v5b`, `io_v5b`, `select_v5b`, `rest_v5b`, `reasoning_v4` |
| `nodone` | single agent trained without the final `done` steps (Supp.) | `pooled_nodone` |

The planner is always the untrained Qwen3.5-4B. Where a run did not follow the protocol exactly, `scripts/paper.yaml`
(`deviations:`) records it, for example the trained single agent's WebVoyager run at 40 steps.

## Tab. 2: skill profiles of ten agents

```bash
python scripts/reproduce.py show rq1
```

prints, for each of the ten agents, its model server and how it runs: the four general models in the browser-use
harness (`python -m miniwebagent.evaluate --human --human-split all --arm base --base-name <served> --verifier-only`),
the six web agents in their own released loops (`python -m miniweb.evaluation.fara_rq1 prep`, the agent's loop in
`src/miniweb/evaluation/fara_runner.py` or `ownloop_runner.py`, then `fara_rq1 grade`). Each run folder is
`data/webmix/eval/rq1_<agent>_all`. Then judge it and read the profile:

```bash
python src/miniweb/evaluation/judge_runs.py --runs data/webmix/eval/rq1_qwen35_4b_all --parallel 4   # -> judge.jsonl
python scripts/skill_report.py data/webmix/eval/rq1_qwen35_4b_all
```

```
data/webmix/eval/rq1_qwen35_4b_all: 376 tasks
  task success, judge      39.4%  (376 judged)
  task success, verifiers  36.2%  (376 graded)
  instances passed by family             n   judge  verifier
  Drag & gesture                        18   16.7%     22.2%
  Discrete selection                   221   39.8%     38.2%
  Text entry                           144   37.5%     34.3%
  Form transaction                     183   38.3%     39.4%
  Navigation                            78   53.8%     57.1%
  Out-of-page I/O                       56   28.6%     27.3%
  Reasoning base                       122   60.7%     53.3%
```

The judge columns are Tab. 2's row for Qwen3.5-4B. `--by primitive` breaks it down per primitive, and `--failures N`
lists failed instances with the judge's reason.

## Training the executors

```bash
python scripts/reproduce.py train pooled_v4 --execute        # MiniWebAgent's executor
python scripts/reproduce.py train taskgen_pooled --execute   # the task-centric executor of Tab. 3
python scripts/reproduce.py train pooled_nodone --execute    # the no-done control
```

`train` builds the training folder from the paper's pool (`scripts/pools/pool3k_dirs.txt`: 3,128 generated
trajectories, 857 chains and 629 recoveries, 27,646 training steps) and runs the recipe on 4 GPUs: LoRA rank 64,
alpha 128, learning rate 1e-4, one epoch, 8 steps per update. `--gpus 0,1` trains on other GPUs with the same global
batch. Training logs to Weights & Biases; set `WANDB_MODE=disabled` to turn it off. The family specialists of the
supplement are released as checkpoints; their settings are in each one's `training_meta.json` on the Hub.

## Regenerating the data

```bash
python scripts/generate_data.py                            # every step and its exact commands (nothing runs)
python scripts/generate_data.py --run --steps generate     # MiniWebGen's generation runs, with their recorded arguments
```

The steps: the site split, MiniWebGen's site maps and per-primitive guides, the 14 generation runs, the replay into
training episodes (the base model writes each step's memory), the recovery and chain variants, the training pool, the
generated test tasks of the held-out sites, the task-centric comparison data, and the release. Generation samples
anew, so a rerun gives a different pool of the same recipe; the paper's pool is fixed by the id lists in
`scripts/pools/`, and the released `training_steps` table is exactly that pool.

## How close to expect

- **MiniWeb and WebArena-Lite** use greedy decoding, but vLLM batching makes runs differ: the paper's three runs of an
  arm have a standard error of 1-3 points (Supp. "All configurations"). Expect a single run within a few points of the
  mean.
- **The live web** changes: sites redesign, prices and availability move, and some sites block automated browsers.
  The paper's live-web runs were made in autumn 2026; expect drift that grows with time.
- **The VLM judge** is a hosted model, so its verdicts can shift slightly as the provider updates it. The task
  verifiers are deterministic except for answers compared by meaning.
- **Not in the repository**: the scripts that draw the paper's figures, the paper's own run folders (episodes and
  screenshots) and the labels of the human grader audit. `reproduce.py table` and `skill_report.py` give the numbers
  behind the figures; `reproduce.py figures` needs the figure scripts.
