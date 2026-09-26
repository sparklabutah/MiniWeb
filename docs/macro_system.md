# Macro system (refined, v2)

The canonical registry is `data/macros.yaml` (loaded via `annotation/macros.py`).
A macro tag has **two axes**:

- a **base macro** — the physical interaction (e.g. `create_by_form`,
  `filter_by_slider`, `toggle_relationship`), grouped into
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
- `operations:` — the 7 reasoning ops, each `{weight, desc, check}`.
- `macros:` — the current base macros (including proposed entries). Each carries `group`, `description`,
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
axis. The original consolidation produced 39 base macros; the live registry now includes
additional proposed entries and seven operations. Retained old aliases map to a new base
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


## Dataset annotation conventions

Tags follow **annotator Minh's convention**, derived from Minh's original human tags:
[`data/task_review_macros_minh_2026-09-26/RULEBOOK.md`](../data/task_review_macros_minh_2026-09-26/RULEBOOK.md)
(it supersedes the navigation-folding rule of the 2026-09-23 AI review). In short:

- Tag each interaction the current instruction requires, once; repeats get instance IDs
  (`search#2`). Graphs, positions, operations, subtasks and spans use those IDs; saved
  verifier trees stay keyed by base macro.
- `navigate_by_route` when reaching the page matters: the destination is the deliverable,
  is chosen by reasoning (carries the op), is a named section where the answer is read or
  the work happens, is a found item opened to read it, or is a category/tab/index link.
  Never for site switches or for opening an item only to act on it.
- Email = `create_by_form` (+ `upload_file`); chat/DM = `message_from_free_text`; stock
  trade or bill = `pay_by_form`; save/star/follow/cart/wishlist/install/report =
  `toggle_relationship`; like = `feedback_by_react`; review text = `feedback_by_text`.
- A requested answer gets a terminal `report_information` with an op: "how many items"
  = `count`, a displayed stat = `read`, yes/no = `verify`. Intermediate reasoning rides
  on the macro it drives; a max/min reached by a sort control is `sort_by_form` + `read`.
- Spans are **1-based inclusive** action indices of the gold recording
  (`macro_span_source`). AI macro review is separate from the human review decision.
- Browse every span of one macro across tasks at `/annotate/macro-browser`.
