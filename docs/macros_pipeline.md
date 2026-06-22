# Master Directive: Automated Macro Extraction Pipeline

**System Context:**
You are an autonomous orchestrator managing a multi-stage data extraction pipeline. You are connected to a local SQLite database (`macros.db`). The schema is pre-defined with strict relational constraints: `verbs` and `modifiers` registries only accept `status IN ('seed', 'established', 'proposed')`.

**Your Goal:** Read task datasets (e.g., WebArena, Mind2Web), extract a unified macro action space *without letting processing order bias the result*, execute database updates directly, facilitate a human-in-the-loop deduplication phase, and finally plot an order-free discovery curve.

**Two invariants that govern the whole pipeline (do not violate):**
1. **Independence during proposal.** A worker proposing macros may read ONLY the frozen `seed`/`established` vocabulary. It must NEVER read another worker's `proposed` entries. All proposals from all workers/datasets meet for the first time in Phase 2.
2. **Order-freeness of all reported numbers.** No coverage claim or curve may depend on the order tasks or datasets were processed. Anything order-sensitive is averaged over many random orderings.

**Execution Strategy:**
You must split this workload and delegate to sub-agents or separate context-sessions as needed. Do not attempt to process all tasks in a single continuous loop. Track your state and process in batches. Every DB write happens inside a transaction with the matching state update, so a crash never leaves a half-processed batch.

Execute the following phases sequentially.

---

## Phase 0: Read and Understand
Please read and understand the following, by priority:
- docs/macros_def.md — **authoritative.** This is the frozen, reviewed definition; the whole pipeline inherits its axis decision (intent, not mechanics), its closed `verb` set, and its closed `modifier` (qualifier-modality) vocabulary.
- docs/MiniWeb_brainstorm.pdf (loosely — for understanding project intent only; the macro definition in macros_def.md overrides anything here).

Confirm that `macros.db` is seeded BEFORE Phase 1: the `seed` verbs and modifiers must come from the taxonomy backbone + blind brainstorm in macros_def.md, so the vocabulary's origin is NOT any dataset. Do not start Phase 1 against an empty registry.

---

## Phase 1: The Proposer (Independent Task Analysis & Extraction)

Delegate this to a worker or workers, in batches (e.g., 20 tasks per batch). Track which task IDs are processed.

**Objective:** Iterate through unprocessed tasks in `webarena_tasks` and `mind2web_tasks` and emit, per task, the macros involved — proposing new vocabulary only when the frozen vocab genuinely cannot express the intent.

**Independence rule (critical):**
* Take a READ-ONLY snapshot of `seed` + `established` verbs/modifiers at the start of the batch. Match against THIS snapshot only.
* Workers must NOT query or reuse each other's `proposed` entries. Write all proposals to a **per-worker staging table** (`staging_proposals`), tagged with `worker_id` and source dataset. Nothing proposed is visible to any other worker.

For each task:
* Read the task (use the `task_general` / templated form, not concrete instances — identical templates share a macro set).
* Reason step-by-step about the required web interactions, on the **intent axis**. Collapse fixed-order UI mechanics (locate_search_bar → type → submit) into their parent intent macro. Do not emit mechanics as macros. (See macros_def.md "What is NOT a macro".)
* **Matching logic:**
  * If a required macro maps semantically to a `seed`/`established` `(verb, modifier)` tuple in the snapshot, USE those IDs.
  * If the intent is expressible by an existing `verb` but needs a `modifier` not in the snapshot, stage a **proposed modifier** (`status='proposed'`).
  * If the intent needs a `verb` not in the snapshot, this is a **loud, rare event**: stage a **proposed verb**, set a `needs_verb_review` flag, and surface it to the orchestrator. Verb proposals are human-gated in Phase 2 and should be the exception — the verb set is meant to saturate small. A flood of verb proposals means the seed was too thin (see Phase 1.5).
* **Execution:** Within ONE transaction per task: INSERT staged proposals into `staging_proposals`, INSERT the per-task macro assignment into `staging_macro_{dataset}_tasks`, and mark the task processed. Do NOT write to the live `verbs`/`modifiers`/`macros` registries in this phase.

Continue batching until all tasks are processed.

### Phase 1.5: Seed-adequacy gate
Before merging, count accepted-shaped proposals. If one dataset generated a disproportionate flood of new modifiers/verbs, the `seed` vocab was too thin. Expand the seed from the taxonomy/brainstorm and **regenerate ALL datasets against the expanded seed** (symmetric — privileges no dataset). Only proceed to Phase 2 once proposal volume is sane.

---

## Phase 2: Deduplicator (Provenance-Blind, Human-in-the-Loop Merge)

You must act as an interactive terminal assistant for this phase. Do not automate the final decisions here. This is the ONLY place proposals from different workers/datasets meet.

**Objective:** Collapse the staged proposals into a clean, frozen action space without macro explosion — provenance-blind, so no dataset's proposals are privileged by processing order.

* **Pool & strip provenance:** Load ALL `staging_proposals` from ALL workers and datasets into one set. Strip `worker_id` and dataset tags before review so the human cannot (and need not) consider origin. Overlap/origin is never an input to the merge.
* **Pre-cluster before asking the human (do NOT present one word at a time):** Embed each proposed term and cluster by semantic similarity against each other AND against `established` items. Present the human with **groups**, not isolated words — e.g. "6 proposals resemble `search`: [list]. Suggest: merge all into `search` / split into N / keep K as new."
* **Interaction Loop (per cluster):**
  * Print the cluster, your semantic analysis, and a suggested action.
  * Prompt: `(M)erge all into [suggestion], (S)plit (specify groups), (A)ccept listed as new, or (D)rop?`
  * Pause and wait for human terminal input.
  * `needs_verb_review` clusters are always shown explicitly and never auto-suggested as merges.
* **Execution — registry promotion AND macro-level dedup, in ONE transaction per decision:**
  Merging two registry entries can map two distinct `(verb, modifier)` macros onto the SAME tuple. This is a macro-level dedup, NOT a simple ID swap. For each merge, in a single transaction:
  1. Repoint references: UPDATE `staging_macro_*` (and `macros`) rows from the dropped ID to the kept ID.
  2. Detect resulting duplicate macros: any `(verb, modifier)` tuple that now appears more than once.
  3. Merge those duplicate macros: repoint all junction rows to the surviving macro_id.
  4. Only now DELETE the orphaned registry entry. Verify no FK/uniqueness violation before COMMIT; ROLLBACK on conflict and re-present to the human.
  * `(A)`: UPDATE status `proposed` → `established`.
  * `(D)`: drop the proposal and its staged assignments.
* **Output:** a fully `established` registry and a finalized macro table. Snapshot this as an immutable artifact (`frozen_vocab.json`) — Phase 3 reads the snapshot, never the live DB.

---

## Phase 3: The Auditor (Symmetric Relabeling & Coverage Audit)

Delegate this to a pool of analytical workers capable of parallel execution.

**Objective:** Produce the benchmark coverage AUDIT: relabel every task symmetrically
against the final frozen vocabulary, then characterize the macro inventory — per-dataset
coverage, overlap, redundancy, concentration, and tail growth. This phase DESCRIBES the
inventory; it does not test a hypothesis. Do not frame outputs as pass/fail on saturation,
and do not tell workers what the curves are for (worker prompts contain the labeling
instructions only — no mention of curves, coverage, or saturation).

* **Preparation:** Combine all tasks from all datasets into a single unified list.
* **State Management:** Load the frozen `established` dictionary from `frozen_vocab.json`
  as an **immutable in-memory snapshot** passed to every worker. Workers do not read the
  live DB (no Phase-2 edit can race a Phase-3 read).
* **Symmetric Relabeling (this is the point of the phase):** Phase-1 assignments were made
  against per-worker snapshots that predate the merge; they are NOT comparable across
  datasets. Remove them. Every task — all datasets — is relabeled here (and updated in the DB)
  against the SAME frozen union, so per-dataset numbers are measured identically.
  * For each task, the worker assigns the macro sequence using **ONLY** the frozen
    dictionary. If a task's intent is genuinely inexpressible, the worker emits
    `OFF_VOCAB` with a free-text `unmet_intent` label (these should be rare after a
    full-data Phase 1/2; a non-trivial residue means the merge dropped something — route
    back to Phase 2).
  * Record per task: the macro SET, the macro SEQUENCE (separate fields), and the source
    dataset. Collect in memory; write one consolidated results artifact, not row-by-row.
