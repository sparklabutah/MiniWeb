# Prompt: Derive macros from tasks

Read first: `docs/macros_def.md` (what a macro is), `docs/labeling_policy.md` (reviewer
rules + ledger). Work from the templated `task_general` form.

## Per task
Think about what the agent must actually do, then decompose on the **intent axis** into
`verb_qualifier-modality` macros. Apply **no-skip composition** (rarely only 2 macros):
include navigate → search → filter → sort → open-item → extract steps that occur.
Never emit UI mechanics (clicks/keystrokes); collapse fixed-order mechanical runs into
their intent parent.

## Vocabulary — assemble a pair, or propose
A macro = **one verb × one modality**. `macros/verbs_modalities.csv` holds the two flat
lists (verbs, modalities) separately.
- **Assemble**: pick a verb + a modality from the registry → that's the macro (reuse its
  row in `macros/all_macros.csv` if the pair already exists).
- **Propose**: if no verb or modality fits, add a row (`status=proposed`) to
  `verbs_modalities.csv`, then pair it. Never invent silently or mint a near-duplicate; if
  unsure it's a duplicate, flag it.

## Outputs
1. **Per-task CSV** (`macros/webarena_macros.csv`): `task_general, macro_set, macro_sequence`
   — set = dedup unordered; sequence = ordered, may repeat. The sequence never changes
   how a macro is individuated.
2. **`macros/all_macros.csv`** — one row per unique macro:
   `macro_name, verb, qualifier_modality, type(interaction|navigation|cognitive),
   semantic_description, terminal_state, example_task, status`.
3. **`macros/verbs_modalities.csv`** — keep the verb/modality registry in sync.

## Process
Do the first 10 tasks, stop, and summarize (macro_set per task + new vocab) for review.
After the granularity is confirmed, batch the rest, reusing names.
