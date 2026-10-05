# tests/

Unit tests for the grading, annotation, data-generation and WebMix code. Run
them from the repo root with the `miniweb` conda env:

```bash
PYTHONPATH=. ~/.conda/envs/miniweb/bin/python -m pytest tests/ -q
PYTHONPATH=. ~/.conda/envs/miniweb/bin/python -m pytest tests/test_macro_registry.py -q   # one file
```

The whole suite runs in a few seconds. No test needs a running MiniWeb server,
a browser, network access or an LLM key: LLM calls are patched with
`unittest.mock`, file-system state goes to temporary directories, and the
annotation API tests use Flask's in-process test client. The `localhost` URLs in
some tests are plain strings, not live requests.

## Files

| File | Covers |
|---|---|
| `test_macro_registry.py` | Drift guard for `data/macros.yaml` via `annotation/macros.py`: every base macro has a group and description, operations are closed and weighted, aliases resolve without collisions, `report_information` is op-only, judge rubrics are complete. Run it after editing the registry. |
| `test_macro_tagging.py` | `annotation/verifier_scaffold.py`: macro span indexing, repeated macro instances, and which instance is the terminal QA leaf. |
| `test_macro_browser.py` | `annotation/macro_browser.py`: repeated instances stay separate, invalid spans are reported as missing, actions are 1-based with frames, path traversal is rejected. |
| `test_review_mode.py` | `annotation/review_mode.py` (Task Review queues): the first edit freezes the original, tag versus wording changes land in the right queue, re-verifying clears a task, urgent tasks sort first. |
| `test_annotation_quality.py` | `annotation/quality.py` evidence and review state, the task-quality and run-verifier APIs (auth, no recording for draft specs, path guards), the filtered CSV export, and `scripts/pull_from_railway.py` (new-only import, unsafe archives refused). |
| `test_macro_judge.py` | `evaluation/macro_judge.py`, the default grader: replies name the agent and reference targets before the verdict, a split vote is settled by a third call, and the harness falls back to the verifier when the judge is unavailable. |
| `test_repair_verifiers.py` | `evaluation/verifiers.py::verify_task` regressions from task repairs: strict field matching, resource binding, uploads and exports checked by bytes, sequences and final state, playback, judge voting and abstention. |
| `test_verifier_audit.py` | Adversarial verifier cases: no implicit numeric tolerance, punctuation and case in literals, follow vs unfollow, undone toggles, answer parsing, judge input requirements. |
| `test_verifier_hardening.py` | Wrong-file, mixed-batch and superseded-state cases: export digests checked on real bytes, only the last design save counts, exact delete sets. |
| `test_datagen.py` | `datagen/` core logic: the executor's action policy (script sandbox, hidden, off-screen, occluded, stale or forged targets, allowed keys, action budget), coordinates, jitter and drag paths, backend checks and their agreement with `verify_task`, sampler stratification, caps and dedup, the filter, the site split, thoughts and training export (no privileged or element data in exports). |
| `test_datagen_kinds.py` | `datagen/kinds/` control kinds (forms, buttons, filters, sliders, date ranges, grids, maps, playback, signatures, clipboard, QA) and the state and request checks built from a dry run. |
| `test_webmix_replay.py` | `webmix/replay.py::build_plan`: recorded datagen pixel actions become a browser-use action plan. |
| `test_webmix_augment.py` | `webmix/augment.py`: recovery variants (an injected, then corrected mistake) and chain variants (two trajectories in one episode). |
| `test_webmix_evaluate.py` | `webmix/evaluate.py` routing: the planner-routed arm switches adapters at each `macro_done`, gates a premature `done`, and falls back when an adapter is not loaded. |

## Beyond unit tests

Task verifiers are also checked against recorded evidence.
`scripts/audit_task_verifiers.py --output <file>` runs every task's
`verifier.json` offline through `evaluation/verifiers.py::verify_task`: it must
pass the task's saved trajectory and fail probes such as an empty trajectory,
the answer alone, unrelated activity, a missing, denied or wrong answer, and an
undone final state. The annotation tool stores per-task verifier results in
`verifier_runs.json`.
