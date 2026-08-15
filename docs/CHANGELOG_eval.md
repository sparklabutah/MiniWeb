# MiniWeb — Eval & Harness Changelog

_Last updated: 2026-08-12_

Developer-facing changes to grading (`evaluation/verifiers.py`), the BrowserGym/
AgentLab harness (`browsergym_miniweb/`), and the run scripts. (Annotator-facing
changes live in `CHANGELOG_annotators.md`.)

---

## Grading — `evaluation/verifiers.py`

### Precision-first answer matching (`_match_answer`)
Rewrote answer matching to be conservative and deterministic, delegating only genuine
ambiguity to the LLM judge. Tiers, in order:
1. **Template-placeholder** pattern (e.g. `#ORD-{YYYYMMDD}-001`).
2. **Whole-word / phrase containment** — the expected value must appear on
   alphanumeric boundaries (lookaround-anchored, robust to trailing punctuation). So
   `"5"` no longer matches `"15"`, `"SkyLine"` no longer matches `"SkyLiner"`, `"cat"`
   no longer matches `"category"` — but `"Zero spam mails"` matches `"Zero spam mails"`.
3. **Tolerant numeric** — when the expected is a number/count (`_expected_number`:
   a bare number, a leading digit token, or a leading zero-word like "Zero"/"No"/"None").
   Matches **digit tokens only** (rounding/​separator/​unit tolerant); a word-only answer
   is left to the judge so a stray "no"/"one" in prose can't false-match.
4. **Task-aware LLM judge** (fuzzy) as the last resort.

Result: eliminates the substring/word false positives; **253/253 gold tasks still pass
deterministically (judge off)**, zero regressions.

### Task-aware fuzzy judge (`_judge_alignment`)
- `verify_task(spec, trajectory, answer, question="")` now takes the task instruction
  and makes it available to the judge (threaded via a `contextvars.ContextVar`, so no
  check signature changes and parallel grading stays isolated).
- The judge prompt was reworded from "does this text match the expected answer" to
  "given the **TASK**, does the agent's answer correctly answer it (equivalent to
  expected)" — so it resolves context-dependent equivalence (e.g. "no spam" vs "0").
- Callers updated to pass the instruction: `browsergym_miniweb/task.py` and
  `evaluation/run_agent_verify.py`.

### Judge availability
- The judge defaults to `gemini-3.5-flash` and now works via the project's Vertex creds
  (`GOOGLE_GENAI_USE_VERTEXAI` + `GOOGLE_CLOUD_PROJECT`), loaded from `.env` on `app`
  import. Previously the run process didn't load `.env`, so every fuzzy answer silently
  graded wrong (false negatives). Override with `VERIFIER_JUDGE_MODEL`.

## Harness — `browsergym_miniweb/`

### `report_answer` tool (`actions.py`)
A dedicated final-answer action, separate from `send_msg_to_user` (progress notes).
- Injected into the built-in `"chat"` subset (`register_report_answer()` in
  `__init__.py`) — the AgentLab args wrapper can't carry `custom_actions`.
- Emits a `[FINAL ANSWER] …` marker; grading reads the marked value directly.
- Documented to the agent (docstring + goal preamble).

### Agent-driven termination (`task.py::validate`)
BrowserGym only ends an episode when the task's `validate` returns `done`. Previously
`done = verifier passed`, so an agent that finished but didn't grade-pass spun until the
step cap. Now the **agent** ends the episode:
- `done = verifier passed OR agent finished`, where "finished" = called `report_answer`
  (preferred), or (fallback) engaged a site, messaged, then went idle for 3 steps.
- Grades at that point, pass **or** fail — no more wasted steps.
- `info["ended_by"]` = `verifier` / `report_answer` / `idle` (telemetry; an
  `ended_by="idle"`/`"report_answer"` with reward 0 is a false-negative shortlist).

### Multi-message answers (`_collect_answer`)
Grading now reads **all** the agent's messages joined (not just the last), so a
multi-part answer split across messages ("you have 0 spam" then "name updated") isn't
lost. `report_answer`, when used, takes precedence.

### Navigation = portal-only (no `goto`)
- Action subsets are `["chat","bid"]` — **no `nav`/`goto`**. The agent navigates via the
  portal's own UI (search bar, site tiles, tab bar), starting from the directory.
- The goal preamble orients the agent to the portal and does **not** instruct `goto`.
  (Earlier an interim preamble told the agent to `goto('/sites/...')`; BrowserGym's
  `goto` needs an absolute URL, so a relative path threw "invalid URL" and stalled weak
  models. Removed.)

## Run scripts / config

- **Model routing:** name local models `ollama/<name>` (e.g. `ollama/qwen3.5:27b`). A
  bare `qwen3.5:27b` resolves to the **groq** catch-all in `make_model_args` and fails
  on a missing key. Fixed in `scratchpad/bg_agentlab_run.py` and `bg_run_qa8.py`
  (which set `OLLAMA_API_BASE`).
- **Judge preflight:** the run launcher imports `app` (loads `.env`) and asserts the
  judge provider is configured *before* the run, so a dead judge aborts at startup
  instead of silently zeroing every fuzzy task.
- **Prompt budget:** `FLAGS_MINIWEB.max_prompt_tokens` 40k → **28k** to fit a local
  32k-context model (ollama `n_ctx=32768`); large-DOM tasks were overflowing and
  crashing the episode.

## Validation run (2026-08-12)

8 multi-site tasks, `ollama/qwen3.5:27b` via AgentLab:
- **All 8 completed cleanly** (`terminated`, none truncated) — termination working, no
  context-overflow crashes, no routing/key errors, judge live.
- **2/8 pass** (crm+calendar-todo, forums+news). Both answer paths validated: one passed
  via `report_answer`, one via the idle-termination + concatenated-message fallback.
- 2/8 reflects the weak local model, not the harness — the grading, termination,
  `report_answer`, and portal navigation all behaved correctly.
