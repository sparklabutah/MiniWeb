# Experiment plan: Toward Generalist Web Agents with Skill-Centric Scaling

Working plan for the paper, aligned with the RQ design in [RESEARCH.md](RESEARCH.md) (your edit
of 2026-10-02). Edit freely, then hand it back to be executed section by section.

- **DECISION:** a choice that is yours. The proposed default follows; change it or tick the box.
- **NEW CODE:** something that has to be written before the step can run.
- **Status** is as of 2026-10-02 12:45 MDT. GPU hours are wall-clock hours on one GPU.
  Costs use the measured [unit costs](#unit-costs).

**Claim:** MiniWeb shows which skills web agents lack, its verified synthetic data fixes them,
and the gains carry over to real websites with far less training data than task-centric agents.

---

## 0. Settled since the last draft

| Item | Decision |
|---|---|
| Harness | **v6** stays. The fixed v7 re-test tied: 58 vs 57 of 120 on the dev sets, 10 vs 9 discordant tasks, 11% fewer steps (`eval/dev*_pagent_v7fix2`). |
| Second model | **Fara1.5-4B** (`microsoft/Fara1.5-4B`, MIT). It is built on Qwen3.5-4B, our base, so Fara1.5 vs MiniWeb is task-centric vs skill-centric training on the **same base model**. Fara1.5-9B exists for the 9B arms. MolmoWeb-4B (Apache 2.0, different base) is the fallback. |
| Data | **Sites frozen** (sites, database, macro registry, human tasks). RQ4 may **generate more training data** on the frozen sites with the existing pipeline. Pool subsets and external corpora (InSTA, MolmoWebMix) are allowed. |
| Baseline arm | Every comparison gets a **planner + untrained** arm, so the training gain is separated from the planner gain (see 0.1). |
| Skewed-mix agent | Evaluated on MiniWeb and WebArena-Lite. On the live web only if the budget allows (~$118 per arm). |
| Training pool for RQ4 | The **existing pool** is the base of the curve (nested subsets; its 3.1K point is the main model's data). New data is **generated on top** of it; the pipeline skips tasks already in the pool. No fresh from-scratch regeneration. |
| Retired trajectories | `data/datagen/retired.json` matches today's generator rules: all 49 retired trajectories still in the runs are rejected by today's checks (audit 2026-10-02, `retired_check.py`). 4 `export` trajectories (0.13%) that today's rules would also reject stay in the pool by decision. |

### 0.1 Why the planner + untrained arm is needed

The untrained baselines reported so far ran as a **single browser-use agent**. MiniWeb's arm is
the **planner agent + trained specialists**, so each reported gain mixes the planner with the training.

| Benchmark | Untrained, single agent | Untrained, planner | MiniWeb (planner + v5) |
|---|---|---|---|
| MiniWeb held-out (63) | 37.0% (3 seeds) | 39.7% (2 seeds, `eval/seeds/pagent_v6_baseexec_s*`) | 51.3% (3 seeds) |
| WebArena-Lite | 27.1% (3 seeds) | **to run** | 34.2% (3 seeds) |
| WebVoyager (536) | 45.5% | **to run** | 69.2% |
| Online-Mind2Web (280) | 17.9% | **to run** | 26.1% |

These runs need no new code. They use the planner agent with no adapters and the base model as
every executor, the same flags as `pagent_v6_baseexec`:

```bash
PY=~/.conda/envs/miniweb/bin/python
AGB="--agent-version v6 --timeout 2400 --planner-name qwen35-4b --adapters none --fallback qwen35-4b"
$PY -m webmix.evaluate --human --arm agent_planner $AGB --verifier-only --workers 6 --ports 8306,8307 \
    --out data/webmix/eval/seeds/pagent_v6_baseexec_s3                      # MiniWeb seed 3
for s in 1 2 3; do                                                         # WebArena-Lite (reset instances; SPARK_PW set)
  $PY -m webmix.wa --router planner_agent $AGB --arm agent_base_s$s --split all --instances 1,2,3,4 \
      --out data/webmix/wa/seeds/agent_base_s$s
done
$PY -m webmix.om2w --bench webvoyager --tasks data/webmix/webvoyager/WebVoyager_reduced_536.jsonl --arm agent \
    --adapters none --fallback qwen35-4b --max-steps 100 --planner-turns 60 --timeout 7200 --workers 24 \
    --out data/webmix/om2w/runs/webvoyager100_agent_base
$PY -m webmix.om2w --tasks data/webmix/om2w/Online_Mind2Web_reduced_280.json --arm agent --adapters none \
    --fallback qwen35-4b --max-steps 100 --planner-turns 60 --timeout 7200 --pace-dir /tmp/om2w_pace \
    --workers 12 --out data/webmix/om2w/runs/om2w100_agent_base
```

Cost: MiniWeb ~1 h; WebArena-Lite 3 × ~3 h (5090); live web ~1 day of granite + $118 judging.

- [x] **DECISION** (default taken): deck and teaser wording until these runs exist. Proposed: "same model and browser
  harness; the untrained model runs as a single agent".

---

## Fixed setup

| Item | Value | Where |
|---|---|---|
| Sites | 65 synthetic websites; 52 train, 13 held out | `sites/`, `data/datagen/site_split.json` |
| Skills | 46 base macros, 7 skill families, 7 reasoning ops | `data/macros.yaml`, `datagen/viewer.py::FAMILIES` |
| Human tasks | 376: 63 on held-out sites (test), 310 on train sites (dev), 3 span both | `data/annotations/*/*/task.json` |
| Single-macro validation | 115 generated tasks on held-out sites, never trained on | `data/webmix/valgen/val_v2.jsonl` |
| Current training pool | 3,128 verified trajectories (14 datagen runs, 44 macros, 52 train sites) + 857 chain + 629 recovery variants = 27,646 steps | `data/webmix/replay_v4/` |
| Pool by family | Discrete selection 742 · Form transaction 705 · Text entry 649 · Out-of-page I/O 461 · Drag & gesture 309 · Navigation 262 trajectories. Per macro: min 8, median 77, max 100 | |
| Models | Qwen3.5-4B, Qwen3.5-9B, Fara1.5-4B (Fara1.5-9B optional) | |
| Agent | planner agent v6 + v5 family specialists (branch-then-specialize from `pooled_v4`) + `reasoning_v4` | `webmix/planner_agent.py` |
| MiniWeb grading | flash macro judge (figures) and deterministic verifier (reported alongside) | `evaluation/macro_judge.py`, `evaluation/verifiers.py` |
| Live-web sets | WebVoyager 536 and Online-Mind2Web 280 normalized (full sets secondary), 100 steps | [RESEARCH.md § Protocols](RESEARCH.md#protocols) |

---

## Running Fara1.5 in our setup (shared by RQ1–RQ4)

Decided 2026-10-02: Fara1.5 appears in two forms.

1. **Fara1.5 as released, in its own loop** (RQ1 benchmark, RQ3 calibration). It reads screenshots
   and acts with pixel coordinates, so it runs in Microsoft's reference agent loop pointed at MiniWeb
   (and at WebArena-Lite and WebVoyager for RQ3). **NEW CODE** (~0.5–1 day): a thin wrapper with a
   start URL in and answer, steps and history out. MiniWeb grading reads the server's request log
   for the session, so the wrapper needs no grading code. Calibration: its published scores are
   WebVoyager 80.8 and Online-Mind2Web 57.3.
2. **Fara1.5 weights in our harness** (RQ2, RQ3 "Fara1.5 + MiniWeb"). Fara1.5-4B has the same
   architecture as Qwen3.5-4B, so our LoRA training starts from its weights instead
   (`WEBMIX_BASE_MODEL=microsoft/Fara1.5-4B webmix.train ...`) on our existing rows, and it is
   served with `MODEL=microsoft/Fara1.5-4B webmix/serve.sh`. No data conversion. This compares the
   same MiniWeb data and the same harness, starting from a plain base model or from one already
   trained on task-centric data. Caveat to state: in our harness Fara1.5 acts through element
   indices, not its native pixel interface, so this tests its weights rather than Fara-the-agent.

Optional, only if a reviewer asks: fine-tuning Fara1.5 in its native pixel format. Over half our
actions name elements by index (click 24%, type 16%, dropdown 5%; coordinate clicks 5%), and the
rows don't store element boxes, so this needs a re-replay with box logging (~1 day of compute +
~1 day of code), a two-click mapping for dropdowns, and Fara's exact prompt format.

---

## RQ1. Which skills do web agents lack?

**Design:** Qwen3.5-4B, Qwen3.5-9B and Fara1.5-4B, untrained (Fara1.5 as released), single agent,
on all 376 human tasks, **1 run** each. Report the failure rate per macro family and per
reasoning op.

| Model | Runner | Status |
|---|---|---|
| Qwen3.5-4B | `webmix.evaluate --arm base` | held-out done (3 seeds); dev + cross tasks to run. The old-harness run `evaluation/results/qwen35_4b_all_x3` exists but uses another harness. |
| Qwen3.5-9B | `webmix.evaluate --arm base`, 9B served | not started |
| Fara1.5-4B (as released) | its own loop (Fara section, 1): `webmix/fara_runner.py` + `webmix/fara_rq1.py` | running (5090) |
| Fara1.5-4B weights in our harness | `webmix.evaluate --arm base --base-name fara15-4b` (same harness as the Qwen rows; also RQ2's untrained Fara1.5 cell) | queued (grn023 GPU0) |
| MolmoWeb-4B | optional | — |

- **NEW CODE** (small): `webmix.evaluate --human-split all` (today `test|train` leaves out the 3
  cross-split tasks).
- **Step budget:** 40 site actions for every model.
- **Statistics:** with 1 run, report family rates with Wilson intervals. Show a macro only when it
  has at least 15 instances; pool the smaller ones into "other" within their family.
- **Output, Fig. 1:** a bar plot of per-family success rate for every baseline on MiniWeb (judge),
  with per-op bars as a second panel.
- **Cost:** ~5 h per model (Qwen), ~8 h for Fara1.5 (pixel loop, estimate). Judge ~$17 per model
  (376 × $0.045), verifier ~$1.

---

## RQ2. Does training on MiniWeb fix them?

### 2.1 The 2×2 per model

| | single agent | planner agent |
|---|---|---|
| **untrained** | Qwen: `--arm base` · Fara1.5 weights, our harness (`--base-name` = Fara1.5) | Qwen: planner, no adapters (0.1) · planner with Fara1.5 weights as every executor |
| **MiniWeb-trained** | Qwen: `--arm pooled` · Fara1.5 + MiniWeb LoRA (init swap) | Qwen: v5 specialists · planner with the Fara1.5 + MiniWeb LoRA |

For Fara1.5, "untrained" means **as released**, already trained on task-centric data. So its row
asks whether MiniWeb adds to task-centric training: a complementarity result.

| Cell, 4B | Status |
|---|---|
| single, untrained | done, 3 seeds (37.0) |
| single, trained (`pooled_v4`) | done, 3 seeds (`eval/human_pooled_v4`, `eval/seeds/pooled_v4_s2,s3`) |
| planner, untrained | 2 seeds (39.7); seed 3 in section 0.1 |
| planner, trained (v5) | done, 3 seeds (51.3) |
| 9B, all cells | not started |
| Fara1.5-4B (weights in our harness), all cells | not started; needs the Fara1.5 + MiniWeb LoRA (~5.6 A800-h) |

- **Evaluation:** held-out 63 × 3 seeds and validation 115 × 1 seed per cell.
- **Training recipes:**
  - Qwen3.5-9B: the 4B recipe. The 4B stack took ~52 GPU-h on the A800s (pooled 22 on 4 GPUs;
    rest 14 on 2 GPUs; select 6.2; drag 4.5; io 3.5; reasoning 1.5), so expect ~100 GPU-h for 9B.
  - [x] **DECISION** (default taken): a pooled-only 9B first (~42 A800 GPU-h), with specialists only if
    budget allows. Inside the planner, pooled scored the same as the specialists on 4B (34/63).
  - Fara1.5-4B + MiniWeb: one pooled LoRA starting from Fara1.5's weights on our existing rows,
    the same hyperparameters as `pooled_v4` (1 epoch, lr 1e-4, rank 64/alpha 128). Check: confirm that Fara1.5 accepts a LoRA
    at this rank in vLLM.
- **Analysis (your "need more analysis on skill break down"):**
  - Gain per family and per macro: trained − untrained, with bootstrap CIs over tasks and seeds.
  - Does training fix the gaps: RQ1 failure rate vs RQ2 gain per family (scatter, Spearman ρ).
  - Data share vs gain: pool trajectories per family vs gain.
- **Output, Fig. 2:** bar plot of all four 2×2 cells per model on the MiniWeb test set (3 seeds,
  judge), with per-family panels.

### 2.2 Skewed vs balanced skill mix

Same-size mixes from the pool. Train one pooled adapter per mix; evaluate in the planner with
that adapter for every step.

- **Size:** 1,200 trajectories per mix (Navigation has 262 and Drag & gesture 309, so both mixes can be built).
- **Balanced:** 200 per action family, spread evenly over each family's macros.
- **Skewed:** 70/30. Two families get 420 each; the other four get 90 each.
- [x] **DECISION:** which families to over-weight. Proposed: (c) the most common families
  (Discrete selection, Form transaction), a "natural skew", plus one random draw. Alternatives:
  (a) 3 random draws, averaged; (b) the families WebArena-Lite needs least **ANSWER** Just select random. → One seeded random draw of the two over-weighted families.
- **NEW CODE:** `webmix.train --episode-ids FILE` (variants follow their parents) and a seeded
  script that writes both id lists.
- **Evaluation:** MiniWeb held-out 63 + validation 115 (per family) and WebArena-Lite × 3 seeds.
  Live web optional.
- **Cost:** training ~2.1 h per mix (A800); WebArena-Lite 6 × ~3 h; MiniWeb ~2 h per mix; ~$0 API.

---

## RQ3. Do the gains carry over to real websites?

| Benchmark | Set | Grading | Runs |
|---|---|---|---|
| WebArena-Lite-v2 | 154 tasks | official evaluators; fuzzy-match by gemini-3.5-flash-lite | 3 seeds |
| WebVoyager | 536 normalized (643 full, secondary) | GPT-4o, last 15 screenshots | 1 |
| Online-Mind2Web | 280 normalized (300 full, secondary) | WebJudge, o4-mini | 1 |

**Arms (main table):**

| Arm | WebArena-Lite | Live web | Status |
|---|---|---|---|
| Qwen3.5-4B single, untrained | ✓ | ✓ | done |
| Qwen3.5-4B planner, untrained | ✓ | ✓ | section 0.1 |
| Qwen3.5-4B MiniWeb (planner + v5) | ✓ | ✓ | done |
| Qwen3.5-4B skewed mix (planner) | ✓ | optional | after 2.2 |
| Qwen3.5-9B single, untrained / MiniWeb (planner) | ✓ | ✓ | after 2.1 |
| Fara1.5-4B as released | ✓ | WebVoyager only (calibration against its published 80.8) | needs the Fara runner |
| Fara1.5-4B + MiniWeb (our harness, planner) | ✓ | ✓ | after 2.1 |
| Published agents (Fara-7B, Fara1.5, MolmoWeb, …) | — | reported numbers | done |

Cut on 2026-10-02: no 9B planner + untrained arm in RQ3, since the 4B rows already show the planner's share. It stays as a MiniWeb cell of the RQ2 2×2.

- Published-agent baseline set: the union of Fara-7B Table 9 and MolmoWeb Table 4, auto-judged
  numbers only, next to our normalized scores, with the differences stated (task set, judge, step
  cap, browser).
- [x] **DECISION:** 3-run averaging on the live web. Proposed: 1 run per arm; 3 runs only for the
  final 4B and 9B MiniWeb arms if the budget allows. **ANSWER** 1 run only
- **Output:** the main table. Columns: WebArena-Lite, WebVoyager, Online-Mind2Web
  (normalized; full in the appendix). Rows: the arms above plus published agents.
- **Cost:** live runs ~12 h each; WebVoyager $26, Online-Mind2Web $92. New RQ3 live runs: 5 WebVoyager
  (4B planner untrained, 9B ×2, Fara1.5 ×2) + 4 Online-Mind2Web (4B planner untrained, 9B ×2,
  Fara1.5 + MiniWeb) ≈ $500. WebArena-Lite ~$0.

---

## RQ4. Does it scale with data?

Goal: a scaling curve that stands up next to Fara's and MolmoWeb's, evaluated on WebArena-Lite and
WebVoyager, 4B at every size. (9B points cut on 2026-10-02: 9B is in the main table only.)

### 4.1 Generate more data (sites frozen)

- **How:** the existing pipeline on the train sites, raising the per-macro target. `--target`
  counts earlier runs, so the pool grows to N kept trajectories per macro:
  ```bash
  python -m datagen.pipeline run --run-id scale300a --target 300 --no-judge --workers 12 --servers 6
  python -m webmix replay --workers 6 --ports 8310,8311 --memory-model qwen35-4b   # new trajectories only
  python -m webmix replay --augment recovery && python -m webmix replay --augment chain
  ```
- **Yield caveat:** some macros yield little (play_by_playback 8, edit_by_ranking 9, cancel_by_form
  11, join_meeting 11), and their sites can't change, so a larger pool is skewed toward the
  high-yield macros. Report the per-family composition of every point.
- **Sizes:** 100, 300, 1K and 3.1K (the current pool, nested subsets), plus ~10K (new data,
  `--target 300`; it yields fewer where macros cap out). The new data is generated up front.
- **Cost:** generation ~$0.04 per kept trajectory, ~$280 for +7K. Replay ~1 day on the 5090 per
  ~5K trajectories (estimate; measure on the first run). Training scales with rows: pooled 5.6 h
  (A800) at 27.6K steps, so ~18 h at ~10K trajectories.

### 4.1b Caveat to state (measured 2026-10-02)

The current pool has 3.2 trajectories per distinct (site, control): 983 controls for 3,128
trajectories. The median macro is supported on 2.5 sites. New data on the frozen sites mostly adds
new parameter values on the same controls, so the curve may flatten past ~3K trajectories.
Report the per-family composition and the number of distinct controls at every point.

### 4.2 The curve

- **Recipe per point:** a pooled adapter in the planner (cheap). Optional: the specialist stack
  at the endpoints.
- **Evaluation per point:** WebArena-Lite × 3 seeds and WebVoyager 536. Online-Mind2Web at the endpoints.
- **Overlay:** Fara-7B Fig. 7 (read off the plot) and MolmoWeb Table 5a (earlier mix, 30-step
  cap), with Fara1.5's final point if its data size is published. Training steps on the x-axis;
  state the confounds (base model, harness, step cap, browser). Fara1.5 shares our base model, so
  it is the cleanest overlay point.
- **Output, Fig. 3:** the scaling plot (WebVoyager; WebArena-Lite as a second panel).
- **Cost:** 5 points × (WebArena-Lite 3 × ~3 h + WebVoyager ~12 h + $26) + Online-Mind2Web at the
  two ends (2 × $92). Training ~20 A800-h: 100/300/1K ~2.5 h, 10K ~18 h; 3.1K reuses `pooled_v4`.

### 4.3 Task-centric vs skill-centric at matched size

Train the same Qwen3.5-4B, same recipe, on a task-centric corpus of the same size as a MiniWeb
point; evaluate on WebArena-Lite × 3 and WebVoyager.

- **InSTA** (arXiv 2502.06776): ~150K trajectories, 2.2M action steps over 150K real websites,
  synthetic (LLM-generated tasks, judge-filtered).
- **MolmoWebMix** (optional second corpus): 30K human trajectories (Apache 2.0).
- [x] **DECISION:** match on training steps (proposed; ~1,900 InSTA trajectories ≈ 27.6K steps) or
  on trajectories (3,128). Matching at the 10K point is also possible after 4.1. **ANSWER** You decide which one is best → **Match on training steps** (27.6K, ~1,900 InSTA trajectories). Equal steps means equal training compute, and steps are the x-axis of the scaling plot. The matched MiniWeb arm is then the full-pool pooled adapter (the 3.1K curve point), so it needs no extra training. Report the trajectory counts as well.
- **NEW CODE:** `scripts/insta_to_rows.py` (and one for MolmoWebMix): map their observations and
  actions to our rows. Drop unmappable steps and report how many.
- **Cost:** conversion ~1 day; training ~3 h per corpus; evaluation as one curve point.

---

## Results and figures (from RESEARCH.md)

| Figure | Content | From |
|---|---|---|
| Fig. 1 | Per-family success rate of every baseline on MiniWeb (judge) | RQ1 |
| Fig. 2 | All 2×2 cells per model on the MiniWeb test set (3 seeds, judge) | RQ2.1 |
| Table 1 | Main transfer table | RQ3 |
| Fig. 3 | Scaling plot with the published curves | RQ4 |
| Ablations | Skewed vs balanced (2.2), matched-size InSTA (4.3), and whatever RQ1–4 suggest | |

---

## Execution order

| # | Step | Needs | Where | Time |
|---|---|---|---|---|
| 1 | Planner + untrained 4B: MiniWeb seed 3, WebArena-Lite ×3, WebVoyager, Online-Mind2Web | — | 5090 + granite | ~1–2 days |
| 2 | Small code: `--human-split all`, `--episode-ids`, the skew id lists | — | — | ~2 h |
| 3 | RQ1 Qwen3.5-4B on dev + cross tasks; validation 115 for the four 4B cells | 2 | 5090 | ~6 h |
| 4 | Fara1.5 own-loop wrapper (RQ1/RQ3 benchmark) | — | — | ~0.5–1 day |
| 5 | Skewed vs balanced: 2 trainings, MiniWeb + WebArena-Lite | 2 | granite + 5090 | ~1.5 days |
| 6 | RQ4 data generation (+7K) and replay | — | 5090 | ~2–3 days |
| 7 | 9B: serving check, pooled training, RQ1/2/3 arms | decision 2.1 | granite | ~3 days |
| 8 | Fara1.5-4B: RQ1, the 2×2, RQ3 arms | 4 | 5090 + granite | ~3 days |
| 9 | RQ4 curve points + InSTA baseline | 6 | granite + 5090 | ~4 days |

Steps 1, 2 and 4 can start now in parallel. Granite still holds two idle allocations
(jobs 2089214, 2087055).

## Schedule and cost on 8 × A800 + 4 × H200

Revised 2026-10-02 after three cuts: no 9B planner + untrained arm, no 9B scaling points, and
Fara1.5 as released on WebVoyager only.

### Training

Measured throughput: **~0.37 rows/s per A800** (`select_v5b` 0.35 and `rest_v5b` 0.37 per GPU; `pooled_v4`
ran on 4 GPUs, 1.38 rows/s in total). An earlier version of this table treated `pooled_v4`'s 5.6 h of
wall-clock time as single-GPU time and was ~3.7× too low (corrected 2026-10-02 15:00).

| Adapter | Rows | A800 GPU-h | Status |
|---|---|---|---|
| RQ4 4B: 100, 300, 1K trajectories | 647 / ~2K / 7,021 | ~0.5 / ~1.5 / ~5.3 | running on grn023 (done ~20:30) |
| Fara1.5-4B + MiniWeb pooled (init swap) | 27,646 | ~21 | running on grn023 GPU2 (done ~noon Oct 3) |
| Skewed and balanced mixes (1,200 trajectories each) | ~10.6K each | ~8 each | queued on grn023 (done overnight) |
| Qwen3.5-9B pooled | 27,646 | ~42 (9B ≈ half the 4B rate) | after the granite downtime (H200) |
| RQ4 4B: ~10K trajectories | ~88K | ~66 | after the new data and the downtime |
| InSTA, matched on steps | 27,646 | ~21 | after the InSTA conversion |
| RQ4 4B 3.1K point | — | 0 (reuses `pooled_v4`) | done |
| **Total** | | **~173 A800 GPU-h** | ~44 in this granite window, ~129 after |

After the downtime the remaining ~129 A800 GPU-h is ~65 H200-h (H200 ≈ 2× A800, estimate), about
16 h on the 4 H200 with multi-GPU runs for the 10K and 9B adapters. Training stays off the critical
path (WebArena-Lite). Cloud-rate equivalent (assumed): ~$260–520; $0 on our allocation.

### Evaluation

| Workload | Runs | Time | API cost |
|---|---|---|---|
| WebArena-Lite (3 seeds per arm): 4B planner untrained; skewed + balanced; RQ4 4B × 5 points; InSTA; 9B × 2 arms; Fara1.5 × 2 arms | 39 runs | ~3 h each on the 4 WebArena instances = **~117 h** (5090) | < $5 |
| Live web, WebVoyager: 4B planner untrained; 9B × 2; Fara1.5 × 2; RQ4 × 5 points; InSTA | 11 runs | ~12 h each | $286 |
| Live web, Online-Mind2Web: 4B planner untrained; 9B × 2; Fara1.5 + MiniWeb; RQ4 × 2 ends | 6 runs | ~12 h each | $552 |
| MiniWeb: RQ1 (4B dev + cross, 9B, Fara1.5); RQ2 cells (4B seed 3; 9B and Fara1.5 × 4 cells × 3 seeds; validation 115 × 14); ablation | ~45 runs | ~70 A800-h | ~$170 (judge) |
| RQ4 data: generate +7K trajectories, replay + recovery/chain | 1 | ~1–2 days CPU; replay ~36 A800-h | $280 |

The 17 live runs need ~200 A800-h of vLLM time, or ~100 when two arms share a GPU. Cloud-rate
equivalent of all A800 time (~200–310 h, assumed ~$1.5–2/h): ~$300–620; $0 on our allocation.

### Where each workload runs

| Hardware | Workloads |
|---|---|
| **4 × H200** | All 8 trainings; Fara1.5 serving if it needs the memory |
| **8 × A800** | vLLM for the live-web runs, MiniWeb evaluations, replay of the new data |
| **Local 5090** | WebArena-Lite: it runs against the 4 self-hosted WebArena instances, which the cluster cannot reach |

### Bottlenecks (not GPUs)

1. **WebArena-Lite instances:** 39 runs × 3 h on 4 instances ≈ 5 days nonstop, the critical path.
   With 4 more WebArena instances it is ~2.5 days.
2. **Live-web concurrency per IP:** ~4 runs at once. 17 runs ≈ 2 days, or ~1 day if the H200
   node has its own egress IP.
3. **Engineering:** the Fara1.5 own-loop wrapper (~0.5–1 day) and the InSTA conversion (~1 day) gate their arms.
   Both are built while the other runs go.

### Wall-clock plan

| Days | Runs |
|---|---|
| 0 | WebArena-Lite queue starts (5090); 4B planner untrained live (2 A800); MiniWeb 4B runs; data generation. H200: 9B pooled, skewed + balanced, RQ4 100/300/1K. Code: `--human-split all`, `--episode-ids`. |
| 1–2 | 9B MiniWeb and live arms; RQ4 small-point WebVoyager runs; InSTA conversion, training and WebVoyager; replay of the new data (4 A800). |
| 2–3 | H200: RQ4 10K adapter (~9 h). Fara1.5 + MiniWeb training (init swap, ~3 h). Fara1.5 own-loop wrapper done. |
| 3–4 | Fara1.5 MiniWeb and live arms; RQ4 10K live runs. |
| 4–5 | WebArena-Lite queue finishes; reruns of failed episodes; figures. |

**Total: ~5 days with the current 4 WebArena instances (+1–2 days of buffer for reruns), or ~3–4
days with 8 instances.**

### Cost summary

| Item | Cost |
|---|---|
| Live-web judging (11 WebVoyager + 6 Online-Mind2Web runs) | ~$840 |
| MiniWeb macro judge (~3,000 episodes) + validation (~1,600) | ~$170 |
| RQ4 data generation (+7K trajectories) | ~$280 |
| WebArena-Lite fuzzy-match judge | < $5 |
| **Total API** | **~$1,300** (approved ~$1.4–1.5K) |
| GPU time at cloud rates (assumed) | ~$370–720; $0 on our allocation |

## Unit costs

Measured on our runs.

| Unit | Cost |
|---|---|
| MiniWeb held-out 63, one run | ~1 h (5090) |
| MiniWeb all 376, one model | ~5 h |
| WebArena-Lite 154, one run | ~3 h (5090, 4 instances) |
| Live web, one arm at 100 steps | ~10–15 h granite |
| Flash macro judge | ~$0.045 per episode; validation episode ~$0.02 |
| Deterministic verifier | ~$0 (< $1 per run) |
| WebVoyager judge (GPT-4o) | ~$26 per 536-task run |
| Online-Mind2Web WebJudge (o4-mini) | ~$92 per 280-task run |
| Data generation | ~$0.04 per kept trajectory |
| 4B pooled adapter, current pool | ~21 GPU-h on one A800 (0.37 rows/s per GPU), 5.6 h on 4; scales with rows |
| 4B full specialist stack | ~52 GPU-h (A800): pooled 22 (4 GPUs × 5.6 h), rest 14, select 6.2, drag 4.5, io 3.5, reasoning 1.5 |

## Rules

- No tuning on WebArena, Online-Mind2Web or WebVoyager: settings are chosen on MiniWeb dev only.
- Sites, macro registry and human tasks stay frozen. New trajectories only through
  `datagen.pipeline` with the existing kinds, for RQ4.
- No bot-protection evasion on the live web; the same pacing for every arm.
- MiniWeb results report the deterministic verifier and the macro judge side by side.
- Every training run logs to wandb (project `webmix-pilot`).

## Sources

- InSTA: arXiv [2502.06776](https://arxiv.org/abs/2502.06776)
- Fara1.5-4B: <https://huggingface.co/microsoft/Fara1.5-4B>
- MolmoWeb: <https://huggingface.co/allenai/MolmoWeb-8B> and its 4B sibling
