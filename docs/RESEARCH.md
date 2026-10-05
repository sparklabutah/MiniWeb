# Research: claims, questions, results, protocols

**Working title:** *Toward Generalist Web Agents with Skill-Centric Scaling*

**Claim:** MiniWeb shows which skills web agents lack. Its verified synthetic data fixes those
skills, and the gains carry over to real websites with 36–80× less training data than
comparable agents.

The dataset is frozen: the sites, the database, the macro registry, the human tasks and the
training pool. Every number below comes from that fixed artifact. Improvements now come only
from the agent harness.

## Fixed setup

| Item | Definition | Source |
|---|---|---|
| Sites | 65 synthetic websites. Split by site, once, before any data was generated: 52 training, 13 held-out (seed 7, test fraction 0.2) | `data/datagen/site_split.json` |
| Human tasks | 376 tasks with a recording and a verifier each | `data/annotations/*/*/` |
| Test set | the 63 human tasks whose primary site is held out | `webmix.evaluate --human` |
| Development set | the 310 human tasks that touch only training sites. The 3 others start on a training site but also use a held-out site, and are in neither set. | `--human-split train` |
| Single-macro validation | 115 generated tasks on the held-out sites, never executed or trained on, graded by the backend gate | `data/webmix/valgen/val_v2.jsonl` |
| Skills | 46 base macros in 10 groups + 7 reasoning operations. For WebMix the macros fall into 7 skill families: Navigation, Text entry, Discrete selection, Form transaction, Drag & gesture, Out-of-page I/O, Reasoning | `data/macros.yaml`, `datagen/viewer.py::FAMILIES` |
| Training pool | 3,128 datagen trajectories that passed the backend gate, from 14 non-retired runs (44 macros, 52 training sites, none held out), replayed through the WebMix harness, plus 857 chain and 629 recovery variants made from them: 4,614 episodes = 27,646 training steps (27.6K). Generation cost about $0.04 per kept trajectory (measured on run `scale100a`: 1,490 kept for ~$55) | `data/webmix/replay_v4/`, `ce_rows` in `data/webmix/adapters/pooled_v4/webmix_meta.json` |
| Base model | Qwen3.5-4B. A 9B model is planned. | `webmix/train.py` |

## The WebMix agent

- **Planner:** a browser-use agent running the untrained base model. It sees the URL, the
  element list and a screenshot, but it cannot act on the page. Its tool
  `delegate(family, instruction)` runs one specialist as a short episode on the same browser,
  and its `done` action ends the task with an answer (`webmix/planner_agent.py`, version `v6`).
- **Specialists (v5):** LoRA adapters (rank 64), trained branch-then-specialize. First a
  `pooled_v4` adapter learns from all families. Each family adapter then starts from it and
  trains on its own rows, with a KL anchor to `pooled_v4` on the other families' rows. The
  adapters are `drag`, `io`, `select` and `rest` (`*_v5b`); `rest` covers Text entry, Form
  transaction and Navigation. The `reasoning` adapter (`reasoning_v4`) was trained on the base
  model's own successful episodes (rejection sampling) on development-set reasoning tasks.
  `pooled_v4` handles any family without its own adapter.
- **Budget:** 40 site actions on MiniWeb and WebArena-Lite. On the live web: 100 site actions
  and 60 planner turns.

## Research questions

| RQ | Question | Design |
|---|---|---|
| RQ1 | Which skills do web agents lack? | Qwen3.5-4B, 9B, Molmo-web 4B or Fara 4B (depending on which one is more accessible) on all 376 human tasks, 1 seed (enough data so no need for 2). . Report the failure rate per macro family and per reasoning operation. |
| RQ2 | Does training on MiniWeb fix them? | Molmoweb 4B or Fara 4B, 4B and 9B: base vs MiniWeb-trained × single agent vs planner (2×2). Also test with skewed distribution trained version, and show that agent trained on skewed distribution performs suboptimally on the benchmarks. Measure on the 63 test tasks and the 115 single-macro validation tasks, with the gain per macro, over 3 seeds. |
| RQ3 | Do the gains transfer to real websites? | WebArena-Lite-v2 (3 seeds), WebVoyager and Online-Mind2Web (normalized and full sets). Compare with published agents; skewed agent, MolmoWeb4B or Fara 4B, 4B, 9B base and fine-tuned. |
| RQ4 | Does it scale with data? | Generate some more data and train on them. Goal is to have an interesting scaling curve when plotted with Fara and MolmoWeb. Evaluate on WebArena-Lite and WebVoyager. Overlay the curve on the published task-centric scaling curves (Fara-7B Fig. 7, MolmoWeb Table 5a); 4B at every size, 9B at the endpoints. Confounds to state: the untrained 4B already scores ~46% on WebVoyager, and the harness, step cap and browser differ. Also add 4B trained on same corpus size but from InSTA instead? (task centric vs skill centric) |

## Results
Fig 1 barplot of all baseline and per family SR on MiniWeb (judge)
Fig 2 barplot of all baseline pre and post train on MiniWeb test set (3 seeds, judge)
RQ3 Main table, you know this
RQ4, scaling plot yyou know this

Ablation:
- generate from the data we have after running through RQ1-4

## Protocols

### MiniWeb

- Each episode starts on the recorded start page of its task. Login tasks start logged out;
  cross-site tasks start at the portal home with a directory of the apps. The browser can
  reach localhost only. Viewport 1280×800, timezone UTC.
- WebMix runs are graded by the task's own `verifier.json` (`--verifier-only`). The verifier
  checks the session's recorder stream and server log. Free-text answers go through regex,
  then exact match, then precise match, then an LLM tier.
- The per-macro skill profile for RQ1 also uses the macro judge (`evaluation/macro_judge.py`):
  gemini-3.5-flash, one judgment per macro instance against the gold span, best of 3 votes
  (stops at 2 agreeing). The task passes when every required instance passes.

```bash
python -m webmix.evaluate --human --verifier-only --arm base --out <dir>
python -m webmix.evaluate --human --verifier-only --arm agent_planner --agent-version v6 --timeout 2400 \
    --planner-name qwen35-4b --adapters drag,io,select,rest,reasoning --fallback pooled_v4 --out <dir>
python evaluation/run_study.py --config evaluation/configs/qwen35_4b_all_x3.json   # RQ1: all 376 tasks, 3 repeats
```

### WebArena-Lite-v2

- 154 tasks from ScaleCUA's WebArenaLiteV2, run on four self-hosted instances. Every instance
  is reset before every run, and each instance runs its share of tasks in order.
- Graded by the benchmark's evaluator on the final page and the `done` answer. Fuzzy-match
  answers are judged by gemini-3.5-flash-lite, our default; the benchmark's own judge is
  gpt-4o-2024-11-20.
- `--split dev` / `--split test` (`data/webmix/wa/split_5050.json`) separate development runs
  from the final comparison. Reported numbers use `--split all`.

### Live web (WebVoyager, Online-Mind2Web)

- `webmix.om2w` (`--bench webvoyager` or `om2w`). Each task starts on its own website, in a
  browser with live internet access. Budget: 100 steps.
- WebVoyager is judged with the official `auto_eval.py` prompts and the last 15 screenshots,
  using gpt-4o (the original judge model is retired). Online-Mind2Web is judged with the
  official WebJudge (o4-mini, score threshold 3). An episode the judge skips counts as failed.
- The task files are the official ones. For WebVoyager, the explicit 2023/2024 dates on
  Booking and Google Flights tasks were moved forward
  (`data/webmix/webvoyager/date_updates_2026-10-01.json`).

**Normalization.** The headline numbers leave out tasks that no agent can complete from our
network:

| Set | Steps | File |
|---|---|---|
| WebVoyager 643 → 536 | Drop the 48 impossible tasks that Fara and MolmoWeb also drop (595 left). Drop Cambridge Dictionary, which blocks our network on almost every episode (43 tasks, 552 left). Drop 16 tasks whose text Fara's file had refreshed but we ran in the original wording. | `data/webmix/webvoyager/WebVoyager_reduced_536.jsonl` |
| Online-Mind2Web 300 → 280 | Drop the 20 tasks on 9 sites that gate our network | `data/webmix/om2w/Online_Mind2Web_reduced_280.json`, `blocked_sites_100step.json` |

The rules:

- A site is set aside when, in at least half of its episodes, the agent's final answer reports
  a network gate (Cloudflare, CAPTCHA, access denied, press-and-hold, human verification).
  Episodes are pooled over both arms.
- A CAPTCHA at a login or sign-up step does not count.
- Whole sites are removed, never single episodes.
- Outdated tasks were found by diffing their text against Fara's refreshed file, never by
  looking at results.
- Location defaults (the IP is in Salt Lake City) are not excluded.

Full-set numbers are reported next to the normalized ones.

## Reproducing the training pool

```bash
python -m datagen.pipeline run --run-id <id> --target N --no-judge   # verified trajectories per macro
python -m webmix replay --workers 6 --ports 8310,8311 --memory-model qwen35-4b
python -m webmix replay --augment recovery
python -m webmix.train --adapter pooled --rank 64 --alpha 128 --epochs 1 --beta 0 --out data/webmix/adapters/pooled_v4
python -m webmix.train --adapter select --init-adapter data/webmix/adapters/pooled_v4 --rank 64 --alpha 128 \
    --lr 5e-5 --anchor-ratio 0.25 --epochs 1 --out data/webmix/adapters/select_v5b   # drag: --epochs 2
```

Training runs in the `webmix` env, and every run logs to wandb (project `webmix-pilot`). Each
adapter's arguments and row counts are saved in its `webmix_meta.json`.
