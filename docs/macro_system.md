# Macro system

Every task is tagged with **macro instances**. Each tag has two parts:

- a **base macro**: the interaction the agent performs, such as `create_by_form`,
  `filter_by_slider` or `toggle_relationship`;
- an optional **reasoning operation**: what the agent has to work out on the page
  while doing it, such as `extremum` or `count`.

A tag is written `base.op`, for example `delete_from_table.extremum` (delete the oldest item)
or `report_information.count` (tell the user how many items match).

## The registry

`data/macros.yaml` is the single source of truth. Code reads it through
`annotation/macros.py`. Edit the YAML, never a copy of its facts in code or docs.

| Section | Contents |
|---|---|
| `groups` | 10 macro families, each with a `weight` and `desc` |
| `operations` | the 7 reasoning operations, each with `weight`, `label`, `desc`, `check`, `rubric` |
| `rubric_principles` | 10 grading rules shared by every macro, used by the LLM macro judge |
| `macros` | the 46 base macros |

Each base macro has `group`, `description`, `example`, `span_start` / `span_end` (where an
instance begins and ends in a recording), `warning` (design notes shown to annotators),
`aliases` (retired names that map to it) and `rubric` (see below).

### Groups

| Group | Base macros | Examples |
|---|---:|---|
| `form` | 11 | `create_by_form`, `edit_by_form`, `pay_by_form`, `checkout_by_form`, `authenticate_by_form`, `sort_by_form` |
| `filter` | 4 | `filter_by_dropdown`, `filter_by_options`, `filter_by_slider`, `filter_by_date_range` |
| `search` | 3 | `search`, `search_by_pan_zoom`, `search_by_playback` |
| `navigate` | 1 | `navigate_by_route` |
| `relationship` | 1 | `toggle_relationship` |
| `feedback` | 3 | `feedback_by_react`, `feedback_by_star`, `feedback_by_text` |
| `media` | 1 | `play_by_playback` |
| `content` | 16 | `upload_file`, `message_from_free_text`, `delete_from_table`, `export`, `edit_by_cell`, `copy_content` |
| `reasoning` | 1 | `report_information` |
| `unassigned` | 5 | `save_by_form`, `reveal_by_2fa`, `carry_info_cross_site`, `edit_by_textbox`, `count_entries` |

`unassigned` holds macros proposed from the annotation UI that have no family yet.

To list every macro with its group:

```bash
~/.conda/envs/miniweb/bin/python -c "from annotation import macros as M; [print(M.group_of(m), m) for m in M.all_canonical()]"
```

### Reasoning operations

| Op | Meaning |
|---|---|
| `read` | the information is shown on the page; find and read it (UI label "read/memorize") |
| `extremum` | find the max or min among on-page items without a sort control |
| `count` | count the on-page items that match a condition |
| `compute` | compute a new value from values on the page |
| `compare` | compare two values on the page with each other |
| `verify` | compare a value on the page with a value given in the instruction |
| `spatial` | reason about where something is: pan/zoom, nearest to a point, the right field to sign, a timestamp to scrub to |

### Answers to the user: `report_information`

When the instruction asks the agent to tell the user something, the task ends with
`report_information`, carrying exactly one operation ("how many open tickets?" =
`report_information.count`). It is the only op-only macro (`op_only: true`) and the only
macro in the `reasoning` group. It replaced the retired `reasoning_on_page`, which is now one
of its aliases.

Reasoning that only drives a later step is never its own tag: its operation goes on the
macro it drives (`pay_by_form.verify` for "pay it if the balance is over $100").

### Aliases

Old names (the earlier flat `verb_by_modality` set) are listed under each macro's `aliases`.
`macros.canon(name)` maps any old name to its base macro, so old task files still load.
The registry has 78 aliases.

### Judge rubrics

Each macro's `rubric` tells the LLM macro judge (`evaluation/macro_judge.py`) how to grade one
instance: `done` (what completes it), `evidence` (what proves it), `must_match` (what must equal
the reference), `may_differ` (what may vary) and `fail_if` (common false passes). Macros whose
result is visual (15 macros: signatures, drag/reorder and ranking, image edits, map view,
player state, stars and reactions, sliders, toggles, grid cells and text boxes, compare views)
and the `spatial` operation also have a `visual`
field; for those the judge also looks at screenshots. Concrete targets are not in the rubric:
they come from the task's gold recording. Macros registered from the UI without a rubric get a
generic one. See [VERIFIER_DESIGN.md](VERIFIER_DESIGN.md) for how the judge uses them.

### Accessors (`annotation/macros.py`)

`all_canonical()`, `canon()`, `alias_map()`, `entry()`, `describe()` / `descriptions()`,
`groups()`, `group_of()`, `category_weights()` / `weight()`, `operations()` /
`operation_names()`, `rubric()`, `op_rubric()`, `rubric_principles()` and
`register_macro()`. `_MACRO_DESCRIPTIONS` and `_canon` in `annotation/app.py` are derived
from these.

## Per-site locations: `data/macro_locations.yaml`

Maps each site to the macros it supports and where they are in its UI
(`site -> macro -> [location, ...]`), keyed by base macro name. The annotation tool uses it
for coverage counts and task sampling. `annotation/macro_locations.py` only loads the file;
edit the YAML.

## Adding macros from the UI

On the annotate page, **+ Add macro -> Propose a new macro** (name, description, span start,
span end). When the task is saved, `register_macro()` appends the macro to `data/macros.yaml`
under `unassigned`. Download the current set as CSV from `/annotate/api/macro_sheet.csv`.

## Where the YAML files live (deployment)

Annotators write to `macros.yaml`, so on a server both files must be on a persistent volume.

| Variable | Effect |
|---|---|
| `MINIWEB_MACRO_DIR` | directory holding both `macros.yaml` and `macro_locations.yaml` |
| `MINIWEB_MACROS` | exact path of `macros.yaml` (overrides the directory) |
| `MINIWEB_MACRO_LOCATIONS` | exact path of `macro_locations.yaml` (overrides the directory) |

Unset, both default to the repo's `data/`. A missing file in a new directory is seeded from the
repo copy.

## Tests

`tests/test_macro_registry.py` checks that every macro has a group and description, that the
operation set is exactly the 7 above, that aliases resolve without colliding, that
`report_information` is op-only and owns `reasoning_on_page`, and that every macro and operation
has a complete judge rubric.

```bash
~/.conda/envs/miniweb/bin/python -m pytest -q tests/test_macro_registry.py
```

## Tagging conventions

The full rulebook is
[`data/task_review_macros_minh_2026-09-26/RULEBOOK.md`](../data/task_review_macros_minh_2026-09-26/RULEBOOK.md).
It follows annotator Minh's original tags and replaces the 2026-09-23 AI review's conventions.
The main rules:

- **Tag what the gold recording does.** Split the recording at each macro's `span_start` /
  `span_end`. Every completed instance is one tag; repeats get instance IDs (`search`,
  `search#2`). Abandoned attempts are not tagged.
- **Required vs incidental.** `task.json` `macro_required` marks the instances the instruction
  asks for. Incidental instances stay tagged, but their verifier checks are advisory: reported,
  never failing the task.
- **Spans** are 1-based, inclusive action indices into the gold `trajectory.json`. A span starts
  at the navigation that opens the macro (`pay_by_form` starts at the "Pay Now" click). The
  exceptions are `navigate_by_route` and the final `report_information`.
- **`navigate_by_route`** only when reaching the page matters: the page is the deliverable, it
  is chosen by reasoning (and carries the op), it is the named section where the answer is read
  or the work happens, it is a found item opened to read it, or it is a category/tab/index link.
  Never for switching sites, and never for opening an item only to act on it.
- **Common mappings.** Send an email = `create_by_form` (+ `upload_file` for attachments);
  chat or DM = `message_from_free_text`; stock trade or bill = `pay_by_form`;
  save/star/follow/cart/wishlist/install/report = `toggle_relationship`; like =
  `feedback_by_react`; written review = `feedback_by_text`.
- **Operations.** "How many items" = `count` (even if the site prints "N results"); a single
  displayed stat = `read`; yes/no = `verify`; a max/min reached with a sort control =
  `sort_by_form` + `report_information.read`.
- Do not use `count_entries`, `carry_info_cross_site` or `edit_by_textbox`; `save_by_form`
  (download a stored file) and `reveal_by_2fa` are in use.

Task metadata: `macros` lists one base name per instance; `macro_instances` gives the instance
IDs; `macro_operations`, `macro_spans`, `macro_subtasks`, `macro_required` and the graph edges
are keyed by instance ID. Saved verifier trees stay keyed by base macro.

Browse every span of one macro across all tasks in the Macro Browser at
`/annotate/macro-browser`.
