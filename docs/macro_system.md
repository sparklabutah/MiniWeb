# Macro system (refined, v2)

The canonical registry is `data/macros.yaml` (loaded via `annotation/macros.py`).
A macro tag has **two axes**:

- a **base macro** — the physical interaction (e.g. `create_by_form`,
  `filter_by_slider`, `navigate_by_route`, `toggle_relationship`), grouped into
  families (`groups:` in the yaml); and
- an optional **reasoning operation** — what the agent had to figure out from the
  page: `read` (baseline / filler), `extremum`, `count`, `compute`, `compare`,
  `verify`. Every operation has a **deterministic check** so it can grade and
  reward, not just label.

Pure-reasoning tasks (no interaction) use the op-only base **`reasoning_on_page`**
carrying one operation — e.g. "what is the cheapest flight?" = `reasoning_on_page
. extremum`.

## The registry (`data/macros.yaml`)

- `groups:` — base-macro families, each with a `weight` and `desc`.
- `operations:` — the 6 reasoning ops, each `{weight, desc, check}`.
- `macros:` — the ~38 base macros. Each carries `group`, `description`,
  `example`, `span_start`/`span_end` (when the macro begins/ends in a
  trajectory, for annotators), and `aliases:` — the retired flat
  `verb_by_modality` names that fold into it, so `canon()` migrates old tags.

Everything derives from `annotation/macros.py`: `all_canonical()`,
`canon()`/`alias_map()`, `describe()`/`descriptions()`, `operations()`,
`groups()`, `category_weights()`/`weight()`. Do not duplicate macro facts
elsewhere — edit the registry.

## How this replaces the old model

The old flat taxonomy had **121 `verb_by_modality` macros** that conflated the
*outcome*, the *widget*, and reasoning into one name. The refined set separates
them: the widget/intent is the base macro (one per real interaction, with the
form/filter/etc. families collapsed by intent), and the reasoning is the operation
axis. 121 → **38 base macros + 6 operations**; every old name maps to a new base
via `aliases` (see `docs/macro_migration.csv`), with 31 deleted (too
compositional / too primitive / not a real interaction).

## Status / remaining wiring

Done: the registry, `annotation/macros.py` accessors, the drift test
(`tests/test_macro_registry.py`), and the migration map. Still to wire onto the
new vocabulary: `annotation/app.py` (coverage/sampling/persist the operation
axis), the annotation UI (two-axis picker in `annotate.html`), the recorded
task.json tags (`docs/macro_migration.csv` → a migration script), and
`annotation/macro_locations.py` (re-key to the new base names).
