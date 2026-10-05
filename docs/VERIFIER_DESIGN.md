# Grading: verifiers and the macro judge

Every agent episode is graded twice:

| Grader | Code | Role |
|---|---|---|
| **LLM macro judge** | `evaluation/macro_judge.py` | the default; decides `passed` |
| **Per-task verifier** | `verifier.json` + `evaluation/verifiers.py::verify_task` | always runs; reported as `verifier_passed`; decides when the judge cannot grade or with `--grader verifier` |

The judge became the default on 2026-09-27. In an audit of 128 judge-vs-verifier
disagreements, the verifier was wrong about twice as often as the judge, mostly because of
over-specified checks. Report judge numbers first, verifier numbers alongside.

## Per-task verifier

### File format

Each task folder `data/annotations/<annotator>/<task_id>/` holds a `verifier.json`:

```json
{
  "task_id": "podcasts-audiobooks_2bcc19",
  "macros": {
    "search":           { "op": "AND", "checks": [ ... ] },
    "play_by_playback": { "op": "AND", "checks": [ ... ] }
  },
  "built_by": "ai-builder-v2", "saved_at": "...", "saved_by": "codex-review"
}
```

`macros` maps each base macro to a check tree. A node is either a group
`{"op": "AND"|"OR", "checks": [...]}` (nested freely) or a leaf `{"type": ..., ...}`.
Repeated instances of one macro share its base-macro key. Other top-level keys
(`built_by`, `archetype_v2`, `report_info_fuzzy`, `query_gated`, `extracted_fields`, ...) record
provenance only; the engine ignores them.

A parameter written `{"open": true}` is not asserted and matches anything. A fresh scaffold
is all open, so it passes any trajectory until values are pinned.

### How `verify_task` decides

```python
from evaluation.verifiers import verify_task
report = verify_task(spec, trajectory, answer="...", question=instruction)
report["passed"], report["by_macro"], report["advisory_macros"], report["macros"]
```

- The trajectory is the recorder stream (`action`, `observation`, `network` events) merged
  with the server request log (`evaluation/trajectory.py::merge_server_log`). Requests count
  only if a witness recorded them; nothing is inferred from clicks.
- A task passes when every gating macro's tree passes.
- **Advisory checks** (`"advisory": true`) are evaluated and reported but never change the
  result. A group whose children are all advisory falls back to gating on all of them, so it
  cannot pass vacuously.
- **Advisory macros**: a macro whose root node is advisory is incidental (performed in the
  recording but not asked for by the instruction; see `macro_required` in `task.json`). It is
  listed in `advisory_macros` and does not gate. If every macro is advisory, all of them gate.
- A check with an unknown type, or one that raises, fails with a reason; it never crashes
  grading.
- `question` (the instruction) is passed to the LLM answer judge.

### Check types

Registered in `CHECKS` (`evaluation/verifiers.py`); the evidence checks live in
`evaluation/evidence_checks.py`.

| Type | Passes when | Typical use |
|---|---|---|
| `request_made` | a recorded request matches `method`, `url`, `status`, `body_fields`, `body_contains`, `response_fields`, `response_headers` | the backend gate of almost every macro |
| `request_sequence` | ordered requests match, with values captured from one step reused in the next (`{{name}}`) | create X, then share that new X |
| `request_count` | the number of matching requests is within `min`/`max` | exactly once; forbidden actions |
| `request_id_set` | the set of resource IDs changed is exactly the expected set | single-item deletes (no collateral deletes) |
| `observation_matches` | the last recorded observation of a page contains `text` / `pattern` / `html_pattern` | final on-page state |
| `qa_answer` | the agent's answer matches `expected` or an `alternatives` entry | `report_information` |
| `answer_matches` | same answer chain, without the leaf/chained logic | older QA checks |
| `answer_grounded` | the page the agent answered from is `url` and contains `text` | rare |
| `reasoning_contains` | the agent's final reasoning contains the expected value | chained (unreported) values |
| `action_included` | an action with this `action`, `target`, `value` is recorded | UI affordance; usually advisory |
| `page_visited` | some recorded URL matches `url` | `navigate_by_route` |
| `download_received` | a completed browser download was recorded (optional hash) | exports, file saves |
| `form_grid_append`, `image_matches`, `image_changed`, `design_matches`, `playback_span`, `calendar_target`, `python_extension` | site-specific evidence (grid rows, saved image bytes, drawing changed, design geometry, play interval, calendar counts, program extension) | a few tasks each |

`request_made` details that matter:

- **URL**: a path (`/sites/...`) must equal the request path and carry every query parameter
  listed; `re:<regex>` is searched case-insensitively, so an ID or slug can vary; anything else
  matches as a substring.
- **Status**: a pinned success status on a non-GET request accepts any 2xx/3xx (the same
  accepted form answers 200 or 302), except a redirect to a sign-in page. GET status stays
  exact.
- **`final_view`** (regex for a listing path): only the last GET to that listing counts, so
  "show X sorted by Y" requires the view the agent left the page in.
- **`last_for_resource`**: only the last successful request for the resource counts, so a
  like followed by an unlike fails.

### Answer grading

`qa_answer` and `answer_matches` go through `_grade_answer`. The first tier that accepts wins:

1. **regex**: `pattern` fully matches the reply or one line of it
2. **exact**: the reply equals the expected value or an alternative (case and whitespace ignored)
3. **precise**: `_match_answer` fast paths (URL paths, a single matching number with unit
   check, the complete value on word boundaries)
4. **judge**: a task-aware LLM judge (`VERIFIER_JUDGE_MODEL`, default `gemini-3.5-flash`),
   best of 3 votes (`JUDGE_VOTES`); a tie fails

Some answers fail without the judge: an empty reply, a leading denial ("the answer is not
..."), a different single number or URL, a conflicting yes/no, the expected value explicitly
negated.

For `qa_answer`, `leaf` comes from the task graph (`verifier_scaffold.inject_qa_leaf`): a
terminal macro grades the reported answer (an empty answer fails); a chained macro grades the
agent's reasoning instead.

The LLM tiers need Gemini credentials in `.env` (Vertex: `GOOGLE_GENAI_USE_VERTEXAI`,
`GOOGLE_CLOUD_PROJECT`). Without them every judge-tier answer fails as "LLM unavailable".

### Building a verifier

Verifiers are built per task in the **Verifier Builder** (`/annotate/verify`). There is no
per-macro template library (it was retired on 2026-09-08).

1. **Scaffold**: `annotation/verifier_scaffold.py::scaffold_task` gives every macro the same
   three checks, all open: `page_visited`, an advisory `action_included` (UI affordance) and
   `request_made` (the backend gate). `report_information` also gets a `qa_answer` seeded
   from the task's expected answer.
2. **Pin**: the annotator pins the values the instruction dictates, grounded in the gold
   requests shown in the builder, and sets the advisory flags. **Suggest with AI**
   (`/annotate/api/suggest_task_verifier`, gemini-3.5-flash) can pre-fill open values from the
   recording. The builder warns before saving a macro that asserts nothing.
3. **Validate**: run the saved spec against the recordings (below).

Design rules:

- **Trust the backend call.** Gate on the request the gold recording actually sent (its real
  method and endpoint), with the values the instruction names. Leave incidental values open.
- **UI checks are advisory** unless the macro is the mechanism being tested (search bar,
  slider, dropdown).
- **Client-only macros** (`compute_by_tool`, `copy_content`, `sign_by_freeformdrawing`,
  `reposition_by_drag`, `search_by_pan_zoom`, ...) gate on the observable outcome: a saved
  result, a clipboard write, an observation of the final state.

### Validation gates

`/annotate/api/run_task_verifier` (body `{task_id, annotator, which}`) runs the saved spec
against one source and stores the result in `verifier_runs.json` next to the task:

| Source | Expected | Input |
|---|---|---|
| `gold` | pass | the original recording + its server log; the answer is the task's expected answer |
| `walk` | pass | `verification_walk.json`, a fresh re-recording (the reference when the gold recording predates the current instruction) |
| `empty` | fail | no events, no answer |
| `answer_only` | fail | no events, the correct answer |
| `agent` | (info) | `evaluation/results/recorded_<task_id>/` |

A task's verifier is accepted when it passes its gold recording or its fresh walk and rejects
both `empty` and `answer_only`. Each stored run records hashes of the task, the spec, the
grading engine and the recording (`annotation/quality.py`); the builder and Task Review mark a
run **Outdated** when any of them changes. Results are saved only for the saved spec; unsaved
builder experiments return `evidence_saved: false`.

As of 2026-10-02 all 376 tasks have a verifier. Their stored runs: 218 pass gold, 191 pass a
fresh walk, every task passes one of the two, and all 376 reject `empty` and `answer_only`.
All stored runs are currently marked Outdated because the grading engine was edited after they
were recorded. Refresh them in the Verifier Builder sandbox (**Run Gold + Walk**, then the
Empty and Answer-only sources); Task Review re-runs gold and walk whenever a task is opened.

For a deeper offline audit:

```bash
~/.conda/envs/miniweb/bin/python scripts/audit_task_verifiers.py --output <dir> [--only <substr>] [--judge]
```

It replays saved evidence and adds negative probes (unrelated activity, missing / denied /
uncertain / wrong answers, mutations answering 500, undoing a toggle) plus diagnostic
ablations (no network, no actions, no observations). Without `--judge`, judge-dependent
comparisons are left unresolved.

## LLM macro judge

`evaluation/macro_judge.py` judges each macro instance of a task on its own.

**Inputs per instance**

- **Rubric**: `rubric_principles` + the macro's `rubric` + its operation's rubric, from
  `data/macros.yaml` (see [macro_system.md](macro_system.md)).
- **Reference**: the gold recording's span for that instance (actions, requests the site
  received during it, the page it ended on). When the gold recording fails its verifier but
  the fresh walk passes, the whole walk is the reference instead.
- **Evidence**: a filtered digest of the graded episode (all actions, requests without static
  files and admin calls, the final page) and the agent's final answer. `report_information`
  instances also get the expected answer.
- **Screenshots** for rubrics with `visual` criteria, when the run saved them: the gold span's
  end frame plus the agent's last frame on that page and its final frame, scaled to at most
  1280 px. Images are supported for Gemini models only.

**Verdict**

- Model: `MACRO_JUDGE_MODEL`, default `gemini-3.5-flash`.
- Best of 3: two calls in parallel, a third only on a split; failed calls abstain; a tie fails.
- The reply must first name `agent_target` and `reference_target` (endpoint and IDs/values
  copied from the requests) and `extra_targets`. A different ID, a list holding different
  records, or a value the site does not use fails; another route to the same records passes;
  other items deleted/cancelled the same way fail.
- The episode passes when every **required** instance (`macro_required`) passes.

**Commands**

```bash
# judge every finished episode of a study (resumable with --jsonl)
~/.conda/envs/miniweb/bin/python evaluation/macro_judge.py \
    --results evaluation/results/qwen35_4b_all_x3 --jsonl evaluation/results/qwen35_4b_all_x3/macro_judge.jsonl
# sanity probes: walk should pass, empty and answer-only should fail
~/.conda/envs/miniweb/bin/python evaluation/macro_judge.py --controls 25
```

`--parallel N` sets how many episodes are judged at once (default 3). Without `--jsonl`, rows
go to `--out` (default `evaluation/results/macro_judge_trial.json`).

## In an agent run

`evaluation/run_agent_verify.py::run_and_grade(grader="judge")` (CLI `--grader`, study config
`episode.grader`) runs both graders after each episode and writes to `result.json`:

| Field | Meaning |
|---|---|
| `passed` | the judge's verdict, or the verifier's if the judge could not grade |
| `grader` | `judge:<model>` or `verifier` |
| `verifier_passed`, `by_macro` | the verifier's verdict |
| `judge_passed`, `judge_by_macro` | the judge's verdict per instance |

The judge's full report goes to `judge_report.json` and the verifier's to
`verify_report.json`. `--grader verifier` skips the judge (no LLM calls except the answer tier).
