# daynight — day/night continual learning for web agents

During the **day**, a human gives tasks and the day t-1 agent attempts them. When the agent goes wrong, the human
sends a correction or takes over. Every episode is logged. At **night**, a meta-train agent reads the logs and
localizes the failures. It works out what each correction meant, scores the traces and finds the weak macros. It
then asks MiniWebGen for practice on those macros, and the executor is trained into the day t agent.

| Question | Measured by |
|---|---|
| RQ1: does the meta agent understand human feedback? | `intent` accuracy against the labels of the interventions (error type, macro, step ±2) |
| RQ2: does one night improve the day t-1 agent? | probe success and autonomous success, day t vs day t-1 |
| RQ3: does it keep improving over many days? | the same metrics over days, plus interventions per episode |

Version 1 runs on MiniWeb sites (clean traces, real graders) with a simulated or a real human. The night trains with
SFT only. Environment changes and the choice of training method are stubs with fixed interfaces (`stubs.py`). Real
websites come later, as a transfer test.

## Run it

```bash
PY=~/.conda/envs/miniweb/bin/python      # any Python 3.11 with PyYAML is enough for the mock runs

# dry run: the whole loop on the mock world, in under a second. No browser, server, GPU or API key.
$PY -m daynight.loop --config daynight/configs/v1_mock.yaml
$PY -m daynight.metrics --config daynight/configs/v1_mock.yaml       # the table over days
$PY -m daynight.loop --config daynight/configs/v1_sim.yaml --model mock --out data/daynight/v1_sim_mock

# the real loop: MiniWebAgent on vLLM (start it first: webmix/README.md, step 5), a simulated human on Gemini
$PY -m daynight.loop --config daynight/configs/v1_sim.yaml                    # stops after night 1's plan
bash data/daynight/v1_sim/day_1/night_plan.sh                                 # generate, replay, train
$PY -m daynight.loop --config data/daynight/v1_sim/config.yaml --resume       # serve the new adapter, then day 2
$PY -m daynight.loop --config data/daynight/v1_sim/config.yaml --resume --execute   # or: run every night itself

# one day with you as the human (headful browser + this terminal; see takeover.py)
$PY -m daynight.day --config daynight/configs/v1_sim.yaml --day 1 --human real --tasks 5 --out data/daynight/me
$PY -m daynight.day --config daynight/configs/v1_mock.yaml --day 1 --human real --tasks 2   # try the interface
```

What each kind of run needs:
- **Mock runs:** nothing beyond the repo.
- **Real days:** the miniweb env, the database and annotations, chromium-1117, and the vLLM server. The simulated
  human also needs Gemini credentials in `.env`.
- **Real nights:** Gemini (MiniWebGen's LLM stages, which are a paid API), the base model on vLLM (to write the replay
  memories) and a GPU for `webmix.train`.

Without `--execute`, the loop never runs a paid or GPU step: it writes `night_plan.sh` and stops. The loop never
starts or stops a model server. It prints the `serve.sh` line for the new adapter, and with `--execute` it waits
until the server lists it.

## The loop

```
day t    probe (fixed tasks, no human) and day tasks (with the human), both by the day t-1 agent
         -> day_<t>/probe.jsonl, episodes.jsonl
night t  meta agent: analysis.jsonl (per episode), summary.json (per macro)
         proposals.json: weak macros -> MiniWebGen targets (+ env changes [], training plan "sft")
         night_plan.sh: datagen run per macro -> webmix replay -> rows folder -> webmix.train --init-adapter day t-1
         -> adapters/day_<t>/, served as dn<t>
day N+1  the last agent runs the probe once more
```

**Tasks.**
- Day tasks are the annotated human tasks on the training sites (310), shuffled with `seed` and split into disjoint
  daily batches of `tasks_per_day`.
- The probe is the 63 held-out tasks (`probe.split: test`). Every day's agent runs them with no human.
- Night data comes from MiniWebGen, which only ever generates on training sites.

**Agent.** MiniWebAgent as `webmix.evaluate --arm agent_planner` runs it: the untrained `qwen35-4b` planner, agent
version `v6`, and the day's executor as the specialist for every non-reasoning family. Reasoning steps go to the base
model. Day 0's executor is `pooled_v4`.

**Human.** After every planner turn that delegated a step, the human sees the step and decides: continue, send a
message, or take over.
- A message reaches the planner through browser-use's follow-up mechanism (`Agent.add_new_task`). A message after
  the agent's own `done` runs the planner again.
- A takeover stops the agent (`Agent.stop()`).
- The **simulated human** (`human_sim.py`) is an LLM that knows the instruction, the gold macros and subtasks, and
  the per-macro progress on the trace so far. That progress comes from the task's verifier run on the partial trace,
  with reasoning macros left out until the end. It sends at most `human.max_messages` messages and then takes over.
  A simulated takeover ends the episode, because it cannot act. Every intervention carries a ground-truth label:
  error type, macro and step.
- The **real human** (`takeover.py`) finishes a takeover in the browser. MiniWeb's page recorder logs their actions,
  and they are saved in `Intervention.human_actions`. A real human can label the error type, which is optional.

**Grading.** The task's own verifier runs on the session's recorder stream and server log, with the same LLM tier for
answer checks as `webmix.evaluate`. A real human's actions count toward the final state.

**Meta agent** (`meta.py`). It sees `meta.digest(episode)`: the steps, the human's messages and actions, and the
verifier's per-macro result. It never sees `Step.oracle` or the labels.
- `LLMMetaAgent` makes one call per episode that failed or needed help.
- `RuleMetaAgent` uses keyword rules, for the mock runs and as the fallback when an LLM reply is unusable.
- The summary counts, per macro, the episodes in trouble: the macro failed, or the meta agent blamed it.

**Proposals** (`propose.py`). Macros are ranked by how many episodes were in trouble, then by rate. Question
answering (`report_information`, `count_entries`) is skipped, because WebMix never replays it into rows. The top
`meta.weak_macros` share `propose.trajectories_per_night`, with at least `min_per_macro` each.

**Isolation (the dataset is frozen).**
- The experiment's MiniWebGen tree is `<out>/datagen/` (`MINIWEB_DATAGEN_DIR`). It holds links to the shared split,
  guides, site maps and caches in `data/datagen/`, and its own `runs/`.
- Replayed rows go to `<out>/replay/` (`WEBMIX_REPLAY_DIR`), and adapters to `<out>/adapters/`.
- Nothing writes to `data/datagen/runs/`, `data/webmix/replay_v4/` or `data/webmix/adapters/`.
- One exception: datagen writes a guide or site map only when it is missing, and it would write into the linked
  shared dir. All 46 guides exist.
- Each night's run `d<t>_<macro>` asks for `--target` = that macro's kept trajectories so far + tonight's target.
  Datagen counts earlier runs toward the target and excludes their dedup keys, so every night adds new trajectories.

**Training** (`train.py`). `rows/day_<t>/` links every episode this experiment has replayed so far, plus
`train.replay_mix` episodes per new episode from `replay_v4`, against forgetting. `webmix.train` runs unchanged with
`train.recipe` (default: the `*_v5b` branch recipe, β 0.1, anchor ratio 0.25, r 64 / α 128, lr 5e-5) and
`--init-adapter` = yesterday's adapter. Its KL rows therefore anchor to the day t-1 executor.

## Files

| File | Role |
|---|---|
| `schema.py` | the episode log (`Episode`, `Step`, `Intervention`, `Label`, `Outcome`), `Analysis`, `Proposal`, `ERROR_TYPES`, JSONL |
| `config.py` | YAML over `DEFAULTS`; `--model mock` switches to the mock world |
| `world.py` | the backend interface and `MockBackend` (tasks from the tracked registry, a skill-table agent) |
| `miniweb.py` | `MiniWebBackend`: real tasks, MiniWebAgent with the human hook, verifier grading |
| `day.py` | the day runner and its CLI |
| `human_sim.py` | the human interface (`View`, `Decision`), `LLMSimulatedHuman`, `MockSimulatedHuman` |
| `takeover.py` | `TerminalHuman`: the real human's terminal controller |
| `meta.py` | the meta-train agent: `digest`, `LLMMetaAgent`, `RuleMetaAgent`, `summarize` |
| `propose.py` | weak macros -> proposals -> MiniWebGen and replay commands; the mock generator |
| `train.py` | rows folder, `webmix.train` command, serve line, adapter wait; the mock trainer |
| `stubs.py` | `propose_env_changes`, `choose_method` (v1: none, SFT) |
| `metrics.py` | per-day metrics and the table over days |
| `loop.py` | the loop, with resumable state |
| `configs/` | `v1_sim.yaml` (the real experiment), `v1_mock.yaml` (the dry run) |

## Outputs (`data/daynight/<name>/`, gitignored)

| Path | Contents |
|---|---|
| `config.yaml`, `state.json` | the resolved config; the loop's position (day, phase, current agent) |
| `day_<t>/episodes.jsonl`, `probe.jsonl` | the day's episodes; artifacts in `episodes/<task>/` and `probe/<task>/` |
| `day_<t>/analysis.jsonl`, `summary.json`, `proposals.json`, `night_plan.sh` | the night's reading and plan |
| `day_<t>/metrics.json`, `metrics.jsonl` | one row per day (`metrics.py` lists the fields) |
| `datagen/`, `replay/`, `rows/day_<t>/`, `adapters/day_<t>/` | the night's data and adapters |

## Mock world

Tasks are built from `data/macro_locations.yaml` and the site split. Each task has 1–3 of a site's macros, with
reasoning last. The agent succeeds on each macro with the probability in its adapter's `skills.json`. Day 0's skills
are a fixed draw between 0.30 and 0.90.
- When it fails, it makes the family's typical error 70% of the time, and stops early before a later macro now and
  then.
- The mock human intervenes exactly at those deviations. A fifth of its messages are vague ("No, not like that.").
- A correction raises the retry's success chance.
- Mock training raises the practiced macros' skills in proportion to the night's replayed episodes. It lowers the
  others slightly, and less with a KL anchor.

These numbers show that the loop works end to end. They are not results.

## Known gaps

- **Not run with a browser yet.** `miniweb.py` is written against the webmix and browser-use APIs, but only the mock
  path ran here. Check these on the lab machine with one task first (`daynight.day --tasks 1`):
  - **Message injection:** `Agent.add_new_task` must exist in browser-use 0.13. If it does not, `inject_message`
    raises and the episode records the error.
  - **The planner hook:** the planner's `on_step_end` hook.
  - **Takeover capture:** the recorder slice that captures a real human's takeover actions.
- **Screenshots:** episode folders keep the specialist histories (`history_<i>.json`), but their screenshots are not
  copied out of browser-use's temp dir. `webmix.evaluate` has the same gap for the planner arm.
- **Simulated takeover:** it ends the episode. The simulated human does not finish the task, so it adds no
  corrective actions; only a real human's takeover does.
- **Not yet used for training:** human corrections are logged, but no training rows are built from them. v1 trains
  on MiniWebGen practice only.
