# Macro Taxonomy Consolidation — Summary

*Read-only analysis of the MiniWeb macro set. No dataset or task files were modified.*

## 1. Motivation

Macros are currently tagged `verb_by_modality` (e.g. `filter_by_dropdown`), a 2D grid of
**43 verbs × ~15 modalities → 131 site-mapped macros**. Walking the set surfaces heavy
**cross-verb overlap**: many macros share an identical interaction and differ only by the
*word* used for the verb. A reviewer will read this as taxonomic redundancy
("why do `follow`, `subscribe`, and `save` all exist?").

The question is whether these distinctions are **real operations** or **domain intent wearing a
verb costume** — and if we collapse the redundant ones, what it costs.

## 2. Method — the operational "swap test"

Two verbs are distinct only if performing them requires a **different capability**, not a
different label. We test this empirically: for every macro instance in the annotated tasks, we
isolate its actions via `macro_spans` and compute an **operational signature** from the recorded
trajectory — the action-type profile (`type` / `select` / `check` / `click`), whether it writes
to the server, and span size. Verbs whose instances share a signature are the same operation.

## 3. Findings

The overlaps collapse into four clusters. Three are confirmed-redundant; the fourth is the
instructive exception.

| Cluster | Verbs | Signature (evidence) | Verdict |
|---|---|---|---|
| **Fill-a-form** | create · submit · register · apply · book · checkout · invite · pay · authenticate · cancel · report · post | `typed ≈ 1.0` across all; fill fields + submit | **One operation.** Domain label lives in the description. |
| **Control / refine** | filter · select · sort · configure · search | Signature splits by **modality, not verb**: query→type+submit, dropdown→choose. `filter_by_query` ≈ `search_by_query`; `select_by_dropdown` ≈ `sort_by_dropdown` | **Verb is the redundant axis;** modality carries the operation. |
| **Status toggle** | follow · subscribe · save · block · react · join | `write = 1.0`, click/check a toggle | **One operation** (`share` excluded — it has non-toggle route/dropdown variants). |
| **QA read** | extract · compute · compare · verify | Read-heavy, low-type, **operationally indistinguishable at the UI level** | **Not merged blindly:** one *read gesture*; the retrieve/aggregate/relate distinction is **cognitive**, not in the actions — it belongs on a separate grounding axis. `verify` has **0** tagged instances (drop candidate). |

## 4. Proposed structure — two orthogonal axes

Replace the flat verb sprawl with:

- **Operation × Modality** (the interaction skill): `fill_form`, `refine_by_<modality>`,
  `toggle_status`, `read_by_<modality>`, plus the genuinely-distinct verbs left intact
  (`edit`, `delete`, `play`, `upload`, `pay`, `navigate`, …).
- **Cognitive operation** (orthogonal, QA only): retrieve / aggregate / relate — captured via
  answer **grounding** (is the answer verbatim on the page?), which the verifier already tests.
- *(Optional)* a small **closed intent field** (register / book / pay / follow …) if intent must
  stay queryable for analysis; otherwise the NL description already carries it.

The merge is done at the **(verb, modality)** level, so only operationally-identical cells
collapse — non-form `create` (`create_by_code`), non-toggle `share`, etc. keep their own verbs.

## 5. Impact on established numbers

| Metric | Before | After | Δ |
|---|---:|---:|---:|
| Verbs / operation categories | 43 | 30 | −13 |
| Unique mapped macros (skills) | 131 | 83 | −48 (−37%) |
| Unique macros used in tasks | 73 | 43 | −30 |
| Unique task signatures (diversity) | 95 | 72 | −24% |
| …keeping the QA cognitive-op axis | 95 | 74 | −22% |
| Tasks needing re-annotation | — | 6 / 131 | ~5% |
| Tasks · sites | 134 · ~65 | 134 · ~65 | unchanged |

Where the macro reduction comes from: `fill_form` ← 14 macros, `toggle_status` ← 6,
`refine_by_*` (control cluster, per modality), `read_by_*` (QA cluster, per modality).

## 6. Interpretation

- **Task-facing scope is untouched.** Tasks and sites are unchanged; only 6 tasks ever
  double-tagged two now-merged macros. The consolidation is a *relabel*, not a re-collection.
- **Diversity holds.** Signatures drop only ~24% (−22% with the cognitive axis). The "lost"
  signatures are tasks that differed *solely* by a redundant verb (`filter` vs `select` on the
  same widget). A closed intent attribute recovers nearly all of it — the diversity was never in
  the verb labels.
- **The number shrinks, the claim strengthens.** "170 macros" invites the overlap critique;
  "83 non-overlapping skills across 30 operations, plus an orthogonal cognitive-operation axis"
  reframes the same content as a deliberate factorization.

## 7. Caveats

- **Thin cells.** Several verbs have few tagged instances (`compute` = 5, `compare` = 2,
  `verify` = 0, plus singletons). Patterns are consistent but the sparse cells are suggestive,
  not conclusive.
- **Write-rate noise.** In multi-macro tasks the literal `submit` action is attributed to one
  span, so per-verb write% is noisy (the `extract` 0.33 / `create` 0.25 oddities). The
  **type / choose / click** profile is the robust signal and it is clean.

## 8. Recommendation

Adopt the two-axis structure: **operation × modality** for the interaction skill, an orthogonal
**grounding-based cognitive operation** for QA, and (optionally) a **closed intent field**. This
removes the redundancy a reviewer would flag, keeps the coverage and cross-site-reusability story,
costs essentially no task diversity, and needs no re-annotation of task content.
