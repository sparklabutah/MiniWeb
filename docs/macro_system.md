# Macro system (refined, v2)

The canonical registry is `data/macros.yaml` (loaded via `annotation/macros.py`).
A macro tag has **two axes**:

- a **base macro** — the physical interaction (e.g. `create_by_form`,
  `filter_by_slider`, `navigate_by_route`, `toggle_relationship`), grouped into
  families (`groups:` in the yaml); and
- an optional **reasoning operation** — what the agent had to figure out from the
  page: `read` (displayed as "read/memorize"; baseline / filler), `extremum`,
  `count`, `compute`, `compare`, `verify`. Every operation has a **deterministic
  check** so it can grade and reward, not just label.

Reasoning the agent must **output to the human** (the answer/report) uses the
op-only base **`report_information`** carrying one operation — e.g. "what is the
cheapest flight?" = `report_information.extremum`. This replaced the old
`reasoning_on_page` (now an alias). **Intermediate** reasoning is never its own
tag: its operation folds onto the base macro it is part of (a macro carries one
op). Op meanings: `read` (UI label "read/memorize")=info is on the page; `extremum`=get max/min;
`count`=count; `compute`=compute a new value from on-page values; `compare`=compare
two on-page values; `verify`=compare an on-page value against a value in the
instruction.

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
axis. 121 → **39 base macros + 6 operations**; every old name maps to a new base
via `aliases`, with the rest deleted (too compositional / too primitive / not a
real interaction).

## Wiring

The two-axis model is wired throughout: `annotation/macros.py` accessors, the
drift test (`tests/test_macro_registry.py`), the annotation UI (per-node
reasoning-op picker + add/propose-macro panel in `annotate.html`), `annotation/
app.py` (persists `macro_operations`, registers proposed macros to the registry),
and `data/macro_locations.yaml` (per-site UI locations, canonical-macro-keyed;
loaded via `annotation/macro_locations.py`). Annotators can propose new macros
from the UI (saved to `data/macros.yaml` under the `unassigned` group) and
download the full set as CSV from the Macro Template Builder.
