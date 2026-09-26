# Task review labels

`task.json.ai_review` stores AI recommendations, reviewer/time, issues, changes, limitations and report paths. The authenticated `POST /annotate/api/task_quality/<annotator>/<task_id>` endpoint validates this payload and stamps hashes for the task's semantic fields, saved verifier macros and original recording. `GET` returns the current summary. Use recommendation `keep`, `repaired`, `needs_repair`, `suggest_delete`, or `unreviewed`. Human `review_tag` and `review` fields are preserved.

`verifier_runs.json` stores the latest result for each test source: `gold`, `walk`, `agent`, `empty`, `answer_only`. The existing `/annotate/api/run_task_verifier` endpoint records evidence only when the tested effective macros match the saved verifier. Run the saved spec by omitting `macros`; unsaved builder experiments return `evidence_saved: false`. Reconciliation includes the task's current QA leaf/expected-answer rules.

Results include semantic task/spec hashes, verifier engine hash and recording content hash. The interface marks changed inputs outdated. Runs stamp the engine version loaded by the executing process, so an old server cannot label its results as validation of newly edited source. Successful negative validation means the verifier rejects the input. Empty and answer-only rejection are basic checks, not evidence of comprehensive robustness. Original recording QA uses the expected answer stored on the task and does not independently establish answer accuracy.

Deletion recommendations retain task files and do not imply human rejection or automatic exclusion by evaluation runners. Choose the evaluation set explicitly. A saved walk passing also does not imply human approval, uniform task realism, or release readiness.

Review documents are available through an authenticated, read-only endpoint limited to report folders under `data/task_review_*`, `data/task_repairs_*`, `data/verifier_audit_*`, and `data/railway_pulls*`. Tokens and session cookies do not belong in those reports.

For incremental imports, use `MINIWEB_RECOVERY_TOKEN=... python scripts/pull_from_railway.py --new-only`. It backs up local annotations, stages and validates the remote archive, imports only missing task directories, retains the remote snapshot and writes a manifest. Existing directories are preserved, including partial local work. Default replacement mode remains available for intentionally restoring a remote snapshot.
