# Verifier Design (archetype_v2)

*The authoritative, dated statement lives in `evaluation/verifier_archetypes.py`'s
module docstring ("settled 2026-08-10"); this doc expands it into the full
pipeline, the check vocabulary, and the grading contract.*

## 1. What a verifier is

Every annotated task has a `verifier.json` next to its `task.json`. It is a tree of
**checks** grouped under `AND`/`OR`, organized **per macro** (`{"macros": {<macro>:
<tree>}, ...}`). At grade time (`evaluation/verifiers.py::verify_task`) the tree is
evaluated against the agent's run — its **actions** (`action_included`), the
**network requests** it caused (`request_made`), the **pages it reached**
(`page_visited`), and its **final answer** (`qa_answer` / `report_information`) —
plus backend state via `/_admin/data/<site>/<collection>` (`record_exists`,
`record_absent`, `count_equals`). Grading is deterministic and rendering-independent.

## 2. The archetype: backend gate (hard) + frontend (advisory)

A macro verifier has **two parts**:

- **BACKEND GATE — hard.** The request the macro's action produces reached the
  server carrying the values the *task* dictated (e.g. the `POST /login` with the
  right credentials; the settings PUT with the chosen value). **This decides
  pass/fail.**
- **FRONTEND — advisory.** The right affordance was used (form typed + submitted,
  slider dragged, dropdown selected). **Reported but does NOT gate** — a valid
  alternate UI path must not fail a task whose outcome is correct. Advisory checks
  carry `"advisory": true`.

Shape (what a form macro looks like):

```
{ "op": "AND", "checks": [
    { "op": "OR", "advisory": true, "label": "affordance used",
      "checks": [ {type: action_included, action: type ...},
                  {type: action_included, action: click ...},
                  {type: action_included, action: submit ...} ] },
    { "type": "request_made", "method": "POST", "url": ".../login",
      "body_fields": {...}, "label": "backend gate" }
] }
```

**Client-only macros** (`compute_by_tool`, `edit_by_image`, `sign_by_freeformdrawing`,
`reposition_by_drag`, `edit_by_ranking`, `copy_content`, `play_by_playback`,
`search_by_pan_zoom`, `filter_by_slider`) have no reliable server mutation, so their
**gate is the on-page OUTCOME** (the computed value / a save call / the reached
state) and the affordance stays advisory.

`report_information` gates on the reported answer being correct; `navigate_by_route`
keeps its `page_visited` check as-is (it *is* the gate — no restructure).

### Macro → archetype map (`evaluation/verifier_archetypes.py`)
- **FORM** (gate = the mutation): create/edit/compare/pay/checkout/book/cancel/
  configure/authenticate/share/sort `_by_form`, feedback_by_star/text, get_nav_route.
- **FILTER**: filter_by_dropdown / _date_range / _options.
- **TOGGLE**: toggle_relationship, feedback_by_react.
- **SEARCH**: search.
- **CONTENT_BACKEND** (gate = the content call): message_from_free_text, upload_file,
  join_meeting, export, delete_from_table, translate_by_query,
  write_executable_program, edit_by_cell.
- **CLIENT_ONLY**: see list above.
- **REPORT**: report_information.
- **SKIP** (kept as-is): navigate_by_route.

## 3. Check vocabulary (primitives)

| type | gates on | notes |
|---|---|---|
| `request_made` | a network request (method/url/body_fields/status) | the usual **backend gate** |
| `action_included` | an agent action (action=type/click/submit/…, target, value) | usually **advisory** |
| `page_visited` | the agent reached a URL | weak signal; kept only for navigate |
| `qa_answer` | the agent's final answer matches | report/QA tasks |
| `answer_grounded` | the answer is grounded in on-page data | report tasks |
| `record_exists` / `record_absent` / `count_equals` | backend collection state via `/_admin/data/...` | strong backend truth |

Groups: `{"op": "AND"|"OR", "checks": [...]}`, arbitrarily nested. `"advisory": true`
marks a non-gating check.

## 4. Top-level flags (the "v2 corrections")

- `archetype_v2: true` — built/restructured into the two-part archetype form above.
- `report_info_fuzzy: true` — the report answer is matched fuzzily (precision-first:
  placeholder pattern → whole-word/phrase containment → numeric-tolerant → a
  **task-aware LLM judge** as last resort, `evaluation/verifiers.py::_judge_alignment`),
  not exact string match.
- `query_gated: true` — grading is gated on the query/filter the task specified.

A verifier **without** these flags is the pre-correction form: flatter, all checks
blocking, `page_visited`-heavy, exact answer match. (That is what a fresh server
download shipped; the corrected set carries all three.)

## 5. Generation pipeline (how `verifier.json` is produced)

`verifier.json` is **generated from the macro templates**, then transformed:

1. **Templates** — `data/macro_templates.yaml`: a human-authored per-macro verifier
   *skeleton* with `{open: true}` placeholders, already in archetype shape
   (FE-affordance OR-group AND backend request). Managed by
   `annotation/macro_templates.py` (load/save; the annotation "Macro Templates" page).
2. **Assemble + fill** — `annotation/macro_templates.py::build_task_draft(macros)`
   selects each task macro's template and fills the OPEN params from the task's
   **grounded values** (the annotator's recorded trajectory + expected answer) and an
   LLM pass (`built_by: "claude-judgement-fill"` / `"build_verifiers.py (per-occurrence,
   deterministic grounding)"`).
3. **Archetype restructure** — `evaluation/verifier_archetypes.py::restructure(tree,
   macro)` rebuilds the value-grounded tree into the two-part archetype form by the
   macro→archetype map and stamps `archetype_v2: true`. It does **not** invent
   values — it reorganizes the grounded tree.
4. **Correction passes** — applied on top, each snapshotted in `data/backups/` as
   `verifiers_pre_<pass>_<ts>.tar.gz`: **relax** (relaxed matching), **afford**
   (advisory front-end), **fuzzy** (`report_info_fuzzy`), **queryfix** (`query_gated`),
   **extraction**. These set the flags in §4.

**Reproducibility caveat:** the historical builder scripts (`build_verifiers.py`,
`build_new_verifiers.py`) and the one-off correction passes are **not checked into the
repo** — only their *outputs* (`verifier.json`), the templates, the archetype module,
and the `pre_*` backup tarballs survive. Regenerating from templates alone reproduces
stages 1–3 but not the exact stage-4 flags unless the pass logic is reconstructed. This
is why corrected verifiers are **migrated**, not regenerated, when a download regresses
them (see §7).

## 6. Grading contract (`evaluation/verifiers.py`)

- `verify_task(spec, trajectory, answer, question="")` evaluates the macro trees.
- Answer matching order (precision-first, `_match_answer`): placeholder pattern →
  whole-word/phrase containment (lookaround around the alnum core) → numeric-tolerant
  → task-aware fuzzy judge (`_judge_alignment`, `VERIFIER_JUDGE_MODEL`, default via
  Vertex; **requires `.env` creds** or every fuzzy answer silently fails).
- Advisory checks are evaluated and reported but never flip pass/fail.
- **Acceptance gate:** a task's verifier must **PASS against the annotator's recorded
  reference trajectory** before the task is accepted (auto-validation). Any new
  verifier must clear this.

## 7. Operational notes

- **New tasks** get a verifier by running stages 1–4 (or the reconstructed builder)
  against the annotated trajectory, then validating it grade-passes the reference walk.
- **Do not regenerate** corrected verifiers from a server that lacks the v2 passes —
  migrate the corrected `verifier.json` over instead (the corrected set = `archetype_v2`
  + advisory + fuzzy + query-gated; a plain download is the weaker pre-correction form).

## Files
- `data/macro_templates.yaml` — per-macro verifier templates (source of truth for shape).
- `annotation/macro_templates.py` — template load/save + `build_task_draft` (fill).
- `evaluation/verifier_archetypes.py` — archetype map + `restructure()` (the design).
- `evaluation/verifiers.py` — the runtime grader (`verify_task`, matching, fuzzy judge).
- `data/backups/verifiers_pre_*.tar.gz` — snapshots before each correction pass.
