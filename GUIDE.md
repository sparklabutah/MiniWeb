# Using MiniWeb

MiniWeb is three things you can use separately:

- **A benchmark**: 65 websites you host yourself and 376 human-written tasks whose graders check every interaction
  skill (primitive) separately, so a run tells you which skills an agent lacks, not only how many tasks it solved.
- **A dataset**: the tasks with their human demonstrations, 3,128 generated practice trajectories, and the training data
  of MiniWebAgent, on the Hugging Face Hub ([miniweb/MiniWeb](https://huggingface.co/datasets/miniweb/MiniWeb)).
- **A framework**: MiniWebGen, which generates verified practice data for any primitive in any amount, and MiniWebAgent,
  which trains an executor on it and composes the skills with a planner.

This guide covers the common jobs. [REPRODUCE.md](REPRODUCE.md) reproduces the paper.

- [Set up](#set-up)
- [Host MiniWeb](#host-miniweb)
- [Run the 376 tasks](#run-the-376-tasks)
- [Read the per-skill results](#read-the-per-skill-results)
- [Choose a grader](#choose-a-grader)
- [Generate more data](#generate-more-data)
- [Train and evaluate an executor](#train-and-evaluate-an-executor)
- [Use the dataset directly](#use-the-dataset-directly)

## Set up

Follow steps 1 to 3 of the [README](README.md#get-started): install, download the data, write `.env`. In short:

```bash
conda env create -f environment.yml && conda activate miniweb && python -m playwright install chromium
python scripts/restore_site_db.py     # the sites: data/miniweb.db, data/static/, data/media/
python scripts/fetch_tasks.py         # the tasks: data/annotations/, data/webmix/valgen/val_v2.jsonl
```

The sites run without any API key. The VLM judge and MiniWebGen call Gemini (`GEMINI_API_KEY`, or Vertex with
`GOOGLE_GENAI_USE_VERTEXAI` and `GOOGLE_CREDENTIALS_JSON`); `src/helpers/llm.py` routes other providers.

## Host MiniWeb

### On your machine

```bash
python run.py                                   # all 65 sites on http://localhost:8080
PORT=8300 python run.py                         # another port
MINIWEB_SITES=e-commerce,email python run.py    # only some sites (faster start)
```

`/` lists the sites; `/sites/<site>/` opens one. Each site is its own app (WebMail, SecureBank, Lakeport Real
Estate, ...), and they share one fictional world: a payment in SecureBank sends a receipt to WebMail, a booking lands
in CalendarTodo.

### As a service

```bash
gunicorn run:app --bind 0.0.0.0:8080 --workers 2 --timeout 120          # what the Procfile runs
docker build -t miniweb . && docker run -p 8080:8080 -v "$PWD/data:/app/data" \
    -e MINIWEB_DB=/app/data/miniweb.db miniweb
```

The image copies the repository, `data/` included when it is there; add `data/` to `.dockerignore` to keep the image
small and mount the folder as above.

| Variable | Default | Meaning |
|---|---|---|
| `MINIWEB_DB` | `data/miniweb.db` | the site database, where `restore_site_db.py` writes it; the server stops if it is missing or empty |
| `MINIWEB_DATA_STATIC` | `data/static` | the sites' own images |
| `MINIWEB_MEDIA_DIR` | `data/media` | the copy of external media; without it, pages load images from their original hosts |
| `MINIWEB_SITES` | all | comma-separated sites to load |
| `MINIWEB_NO_AUTOLOGIN` | off | `1`: visitors start logged out (by default they are user 1) |
| `MINIWEB_ANNOTATORS`, `MINIWEB_ANNOTATIONS_DIR` | | logins and task folder of the annotation tool at `/annotate/` |
| `MINIWEB_MACRO_DIR` | `data` | where the macro registry lives; point it at persistent storage on a deployment, since annotators can add macros |

### Many agents on one server

The base tables never change. Every browser session (cookie) writes to its own overlay, so any number of agents can
use one server at once without seeing each other's changes, and a new session starts from the original data. Within a
session:

| Endpoint | Use |
|---|---|
| `GET /_admin/session-flags?logout=1` | start logged out (for tasks that ask the agent to log in); `?disable_2fa=1` skips payment 2FA |
| `GET /_reset_data` | drop this session's changes and logs |
| `GET /_admin/record` | the actions and observations the injected recorder captured, in the human trajectory schema |
| `GET /_admin/log` | the session's request log |
| `GET /_admin/changes?site=<site>` | the session's data changes against the base tables |
| `GET /_admin/data/<site>/<collection>?<field>=<value>` | read a collection as this session sees it |

The graders use exactly these: they read what the agent did from the request log and the data changes, not from the
agent's own report. Full list: [src/miniweb/app/README.md](src/miniweb/app/README.md).

## Run the 376 tasks

Pick the path that matches your agent. All three grade with the same verifiers and judge.

### A model served with an OpenAI-compatible API (vLLM, ...)

The agent runs in the [browser-use](https://github.com/browser-use/browser-use) harness: screenshot plus indexed
elements in, one action out, up to 40 steps. The evaluator starts its own MiniWeb servers on `--ports`.

```bash
MODEL=Qwen/Qwen3.5-4B SERVED=qwen35-4b PORT=8400 bash src/miniwebagent/scripts/serve.sh   # vLLM env; or any OpenAI-compatible server
python -m miniwebagent.evaluate --human --human-split all --arm base --base-name qwen35-4b \
    --vllm http://127.0.0.1:8400/v1 --ports 8300,8301 --workers 6 --out runs/qwen35-4b
```

- `--human-split test` runs only the 63 tasks of the 13 held-out sites; `train` the 310 on training sites.
- `--human-macros filter_by_slider,sign_by_freeformdrawing` keeps tasks that use one of these primitives;
  `--task-ids a,b` runs given tasks; `--limit 20` a quick sample; `--resume` continues a run.
- `--tasks data/webmix/valgen/val_v2.jsonl` runs the 115 generated single-primitive tasks of the held-out sites instead.

### A hosted model (Gemini, GPT, Claude, Ollama)

```bash
# one task, with a live browser window
python src/miniweb/evaluation/run_agent_verify.py --task-id crm_bf9346 --model gpt-4o --obs visual --no-headless

# many models x many tasks: write a study config, then
python src/miniweb/evaluation/run_study.py --config my_study.json --workers 8
```

A study config lists models (provider, model name, host) and tasks (`"all"` or ids), with episode settings and repeats;
[src/miniweb/evaluation/configs/](src/miniweb/evaluation/configs/) has an example. The study writes
`study_summary.json` with success overall, per chain length and per primitive.

### Your own agent

Use MiniWeb as an environment and hand back what happened:

```bash
python -m miniweb.evaluation.fara_rq1 prep --out runs/my_agent --split all    # -> runs/my_agent/tasks.json
```

`tasks.json` gives each task's `prompt` and `start` URL (with `{BASE}` standing for your server, e.g.
`http://localhost:8080`) and whether it `needs_login`. For each task, in a fresh browser session:

1. open `{BASE}/_admin/session-flags`, adding `?logout=1` when `needs_login` is true;
2. open `start` and let your agent work on `prompt`;
3. in the same session, fetch `{BASE}/_admin/record` and `{BASE}/_admin/log` (JSON lists);
4. save `runs/my_agent/<task_id>/session.json`:
   `{"task_id": ..., "base": "<BASE>", "answer": "<the agent's final answer or null>", "record": [...], "log": [...]}`.

Then grade:

```bash
python -m miniweb.evaluation.fara_rq1 grade --out runs/my_agent --split all --arm my_agent
```

[src/miniweb/evaluation/ownloop_runner.py](src/miniweb/evaluation/ownloop_runner.py) does exactly this for UI-TARS and
MolmoWeb, and `fara_runner.py` for Fara; copy one as a starting point.

## Read the per-skill results

A run folder holds `results.jsonl` (each task's verdict and the verifier's verdict per primitive) and, once judged,
`judge.jsonl` (the VLM judge's verdict and reason per primitive):

```bash
python src/miniweb/evaluation/judge_runs.py --runs runs/qwen35-4b      # add the judge's per-primitive verdicts
python scripts/skill_report.py runs/qwen35-4b                           # success per skill family
python scripts/skill_report.py runs/qwen35-4b --by primitive            # per primitive, weakest first
python scripts/skill_report.py runs/qwen35-4b --failures 20 --family "Drag & gesture"   # why they failed
python scripts/skill_report.py runs/model_a runs/model_b                # several runs, one after the other
```

```
runs/qwen35-4b: 376 tasks
  task success, judge      39.4%  (376 judged)
  task success, verifiers  36.2%  (376 graded)
  instances passed by family             n   judge  verifier
  Drag & gesture                        18   16.7%     22.2%
  Discrete selection                   221   39.8%     38.2%
  ...
```

The 7 families are navigation, text entry, discrete selection, form transaction, out-of-page I/O, drag & gesture and
reasoning. Task success compounds over a task's primitives (a task of n primitives succeeds about as often as the
per-primitive rate to the n-th power), so the weakest family is usually where to invest.

## Choose a grader

Every task has two graders:

- **The task verifier** (`verifier.json`, `src/miniweb/evaluation/verifiers.py`): deterministic checks per primitive
  against the server's request log and data changes, plus answer checks (regex, exact, then an LLM tier for answers
  that must be compared by meaning).
- **The VLM judge** (`src/miniweb/evaluation/macro_judge.py`, Gemini 3.5 Flash): reads each primitive's rubric, the
  agent's actions and screenshots, the request log, and the human demonstration of that primitive as a reference, and
  gives a verdict with a reason.

How often each agrees with a human label, on 120 audited agent episodes (the paper's supplementary material; tasks
weighted by how common each pair of verdicts is):

| | Task-level accuracy | Per-primitive accuracy (245) | Drag & gesture primitives (23) |
|---|---|---|---|
| VLM judge | 92.2% (κ 0.84) | 89.6% | 92.3% |
| Task verifiers | 88.9% (κ 0.77) | 87.3% | 98.4% |
| Two humans, for comparison | 91.4% (κ 0.83) | | |

Which to use:

- **Reporting task success or per-skill profiles**: the judge, with the verifier alongside (the default of
  `run_agent_verify.py`; `judge_runs.py` adds it to any run).
- **Low cost, exact repeatability, or high throughput**: the verifier alone (`--verifier-only`,
  `--grader verifier`). Its action checks are deterministic; only answers that must be compared by meaning go to an
  LLM (Gemini 3.5 Flash-Lite), and without a key those answers fail until a `--regrade`. It is stricter than the
  judge: when it fails an episode the judge passes, the human sided with the judge 34 times out of 36.
- **Drag & gesture primitives**: the verifier is the more accurate of the two.
- **A reward for RL**: the verifier. When it passes an episode it is almost always right (about 99% of its passes are
  real), and it misses about a quarter of real successes. Add a check that the session's data changes contain nothing
  the task did not ask for, since the verifiers check that the required change happened, not that nothing else did,
  and hand-check a sample of passing rollouts as training goes.

`python -m miniwebagent.evaluate --regrade runs/<run> ...` recomputes a run's grades from its saved inputs, without
running the agent again.

## Generate more data

MiniWebGen turns the human demonstrations into practice: for a primitive, it picks a site and control from privileged
site maps, writes a task and a short script that acts only through mouse and keyboard, runs it, and keeps it only if
the server shows the change the task asked for. A kept trajectory costs about $0.04 (Gemini 3.5 Flash).

### Once: site maps

```bash
python -m miniwebgen sitemap --workers 8 --servers 4           # crawl the 52 training sites, find each primitive's controls
```

The train/test split (`data/datagen/site_split.json`) and the per-primitive guides (`data/datagen/guides/`) ship with
the repository. Generation only ever uses the 52 training sites.

### A given number of trajectories

```bash
python -m miniwebgen run --run-id more_forms --macros create_by_form edit_by_form \
    --target 200 --workers 12 --servers 6 --attempts 3 --no-judge
```

`--target` is the number of kept trajectories per primitive, counting earlier runs, so you can raise it and run again.
Useful knobs: `--per-site-cap` (kept trajectories per site per primitive, for site diversity), `--attempts` (scripts
tried per task), `--no-judge` (keep on the deterministic backend check alone; drop it to also have the flash judge
confirm). Kept trajectories land in `data/datagen/runs/<run-id>/`; `python -m miniwebgen yield --run-id more_forms`
shows the yield and `python -m miniwebgen view` writes a browsable viewer.

### More data for one skill family

Give `--macros` the family's primitives:

```bash
python -c "from miniwebgen.viewer import FAMILIES; print(*FAMILIES)"                      # the 7 families
python -m miniwebgen run --run-id more_drag --target 300 --workers 12 --servers 6 --no-judge \
    --macros $(python -c "from miniwebgen.viewer import FAMILIES; print(*FAMILIES['Drag & gesture'])")
```

`data/macros.yaml` describes every primitive (its description, an example, and the rubric the judge uses), and
`data/final_set.yaml` lists the 37 the benchmark reports.

### Into training rows

A kept trajectory becomes training rows by replaying it through the agent's harness, where the base model writes each
step's memory, so the rows have exactly the prompts the agent sees at test time:

```bash
python -m miniwebgen replay --tasks @my_ids.txt --memory-model qwen35-4b --memory-url http://127.0.0.1:8400/v1 \
    --workers 8 --ports 8300,8301                            # -> data/webmix/replay_v4/<trajectory>/rows.jsonl
python -m miniwebgen replay --augment recovery --share 0.35 ...   # variants with an injected, corrected mistake
python -m miniwebgen replay --augment chain ...                   # two trajectories of one site as one episode
```

`python scripts/generate_data.py` prints the full sequence the paper ran (split, site maps, guides, generation runs,
replay, variants, test tasks, task-centric data, release), and `--run --steps ...` runs chosen steps.

## Train and evaluate an executor

MiniWebAgent's trained executor is on the Hub ([miniweb/MiniWebAgent](https://huggingface.co/miniweb/MiniWebAgent)):
`python scripts/fetch_adapters.py` puts it in `data/webmix/adapters/pooled_v4` (`--all` adds the paper's other
executors). To train your own:

```bash
python scripts/fetch_training_data.py           # the paper's 4,614 training episodes, from the Hub
WEBMIX_REPLAY_DIR=data/webmix/replay_v4 torchrun --standalone --nproc_per_node 4 -m miniwebagent.train \
    --adapter pooled --out data/webmix/adapters/my_executor --epochs 1 --lr 1e-4 --rank 64 --alpha 128 --grad-accum 8
```

`--rows-dir` trains on other rows (for example your own generated ones), `--episode-ids <file>` on a subset, `--frac`
on a fraction; `--grad-accum` is the global batch (rows per update), whatever the GPU count. Training logs to Weights &
Biases unless you pass `--wandb-project ''`. Serve the adapter next to the base model and evaluate MiniWebAgent, the planner with your executor:

```bash
MODEL=Qwen/Qwen3.5-4B SERVED=qwen35-4b PORT=8400 MAX_LORA_RANK=64 \
    LORA_MODULES=my_executor=data/webmix/adapters/my_executor bash src/miniwebagent/scripts/serve.sh
python -m miniwebagent.evaluate --human --arm agent_planner --agent-version v6 --planner-name qwen35-4b \
    --adapters none --fallback my_executor --vllm http://127.0.0.1:8400/v1 --ports 8300,8301 --out runs/my_agent
```

`--arm pooled --pooled-name my_executor` runs the trained model as a single agent instead. The executor learns
single primitives; on whole tasks it needs the planner, which splits the task into primitive-level instructions.

## Use the dataset directly

Every table loads with `datasets`, screenshots as images:

```python
from datasets import load_dataset
import json

tasks = load_dataset("miniweb/MiniWeb", "tasks", split="test")             # 63 held-out tasks
t = tasks[0]
print(t["instruction"], t["primitives"])
verifier = json.loads(t["verifier"])                                          # nested fields are JSON text

demo = load_dataset("miniweb/MiniWeb", "demonstrations", split="test")      # one row per recorded event
steps = load_dataset("miniweb/MiniWeb", "training_steps", split="train", streaming=True)
row = next(iter(steps))
messages, target, image = json.loads(row["messages"]), row["target"], row["image"]   # prompt, action, screenshot
```

`training_steps` is in the agent harness's chat format: `messages` holds the system prompt and the user turn (task,
memory, page state, with the screenshot as an image part pointing at `image`), and `target` the step's memory and
action. Train on rows with `is_target` true; `validation` marks the 5% held out for validation loss. The dataset card
documents every table and column.
