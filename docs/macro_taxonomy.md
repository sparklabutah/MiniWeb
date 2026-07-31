# Macro Taxonomy — the two-layer model

This is the design of record for how MiniWeb represents macros. It replaces the
flat `verb_by_modality` taxonomy, which conflated three separate things into one
label: the **outcome**, the **widget**, and an implied **difficulty**.

## The problem with the flat taxonomy

A name like `select_by_dropdown` jammed together:
- what the task *commits* (its outcome),
- which *widget* the agent operated, and
- an assumed difficulty (encoded as a hand-set category weight).

Two failure modes followed:
1. **Input-primitive macros that aren't tasks.** `select_by_dropdown`,
   `create_by_dropdown`, `edit_by_dropdown`, `configure_by_*`, `select_by_radio`
   describe a widget action that is *inert until a commit*. A task cannot exist
   with one alone — it always rides with a `submit_form`-style commit. Sampling
   them as standalone tasks produces contrived tasks (a driver of N/A + skip
   reports).
2. **Difficulty asserted, not measured.** Per-category weights (spatial 5.0,
   reasoning 8.0, …) were applied per-macro while categories had wildly
   different macro counts, so the effective task distribution never matched the
   documented target — and for a DOM/a11y-tree agent the categories barely
   predict success anyway.

## The model: factor `verb × modality` into two layers

- **Layer 1 — Task macros.** What the task *commits*, grouped by interaction
  **archetype**. Small and clean.
- **Layer 2 — Interaction primitives.** Which *widgets* the agent operated,
  **derived from the trajectory** (not annotated). This is the axis on which
  *visual* agents actually differ.

The `_by_<modality>` half of every current name migrates from Layer 1 to Layer 2.

### Layer 1 — commit archetypes

Defined in `annotation/macros.py` (`archetype()`, `ARCHETYPES`, `by_archetype()`),
derived from each macro's verb. The archetype answers the **commit test**: does
the interaction author-and-commit content, refine a view, or act on an existing
item?

| archetype | what it commits | folds into | example verbs |
|---|---|---|---|
| `form_write` | author content into fields and commit | `submit_form` | submit, create, edit, register, apply, post, upload, pay, book |
| `query` | operate a control → re-present a listing (no mutation) | `filter_by_query` | filter, search, sort |
| `one_shot_mutate` | act on an existing item + confirm | `delete_from_table` | delete, cancel |
| `boolean_mutate` | flip a boolean relationship | `toggle_status` | follow, save, subscribe, join, block, react |
| `read_reason` | produce an answer by reading/reasoning | — | extract, compute, compare, verify |
| `media` | play / capture media | — | play, record |
| `navigate` | move between pages (not sampled) | `navigate_by_route` | navigate |
| `input_primitive` | select a value with no standalone outcome | (host commit) | select |

Key correction to a common intuition: **only `create` (the form_write family)
collapses into `submit_form`.** `filter`/`sort` are *reads* (a changed view, not
a mutation) and `delete` is a *one-shot mutation with no form fill* — different
interactions, different verification, so they stay distinct.

### Layer 2 — interaction primitives

Defined in `annotation/macros.py`. A closed, **difficulty-ranked**
vocabulary, derived from the recorder's action stream
(`evaluation/action_vocabulary.py`): `type→text-field`, `select→dropdown`,
`change→slider|date-range|number`, `check→radio|checkbox`, `drag→drag`,
`click→button|link|toggle|chip|table-cell`.

Ranked low→high by **visual perceptual-motor demand**:

```
link · button · radio · chip · checkbox · dropdown · toggle ·
text-field · table-cell · number · date-range · slider · drag
```

`interactions_for(trajectory)` returns the set a task exercises;
`peak_difficulty(trajectory)` returns its hardest primitive. Because human and
agent trajectories share the exact action vocabulary, the **same** derivation
scores both — so you get a per-primitive DOM-vs-visual pass-rate gap for free,
with no annotation UI and no per-annotator burden.

## Why visual agents make this the right cut

For a DOM/a11y-tree agent a slider, a dropdown, and a radio are all "a node with
a role" — it emits `set value`/`select`/`click` and the interaction type barely
predicts success. For a **visual** agent each is a distinct perceptual-motor
problem (estimate a pixel position for a slider vs. click one of three visible
radios), so Layer 2 *is* the difficulty. The headline artifact becomes a matrix:

```
task-macro (Layer 1) × interaction primitive (Layer 2) × agent modality → success rate
```

and the DOM-vs-visual gap per primitive (flat for dropdowns/radios, wide for
sliders/date-pickers/tables) justifies the taxonomy empirically instead of by
assertion. Difficulty is thus the perceptual-motor rank of Layer 2, not a weight.

## What is implemented (additive, non-destructive)

Done now, without touching the macro vocabulary, site mappings, or the 202
recorded tasks' ground truth:
- Layer 1 archetype classification (`annotation/macros.py`).
- Layer 2 primitive vocabulary + trajectory derivation (`annotation/macros.py`).
- Drift guards (`tests/test_macro_registry.py`): archetype coverage, closed
  primitive vocabulary, derivation closure.

## The deferred collapse migration (NOT yet applied)

Physically collapsing the vocabulary — deleting the input-primitive macros,
renaming task macros to drop `_by_modality`, and re-tagging every site mapping,
verifier template, and recorded task — is a **benchmark-ground-truth migration**.
It is context-dependent (`select_by_dropdown` is `submit_form` inside a form but
part of `filter` when it drives a listing), so it must be done deliberately and
verified per macro, not scripted blindly. It is intentionally left as the next
step. When done it should:
1. Demote the `input_primitive` macros (and the widget half of every form_write
   macro) to Layer-2 interaction tags on their host task.
2. Keep the self-committing macros (`filter`, `sort`, `toggle_status`, `delete`)
   as Layer-1 task macros, dropping the `_by_modality` suffix.
3. Move `compute`/`compare`/`extract` fully into `read_reason`.
4. Replace category weights with the Layer-2 difficulty rank.
