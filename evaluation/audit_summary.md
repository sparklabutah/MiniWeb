# Full Verifier & Trajectory Audit — 2026-08-16

Every current task (287, excluding `.trash`) was audited: verifier design vs its own
gold trajectory, gate-value grounding, and eval-run failure attribution
(`qwen35_27_all_600`, browser-use × qwen3.5:27b, 600s). Per-task analysis lives in
`data/annotations/<annotator>/<task_id>/note.md`. Machine pre-audit data:
`evaluation/audit_pre.json` (gold-pass + per-macro results + eval join per task).

## Verdict tally (287 tasks)

| Verdict | Count | Meaning |
|---|---|---|
| VERIFIER_OK | **195** (68%) | gate sound, gold passes, grading trustworthy |
| RECORDING_GAP | **53** (18%) | gate fine; gold trajectory missing the network event |
| VERIFIER_SUSPECT | **35** (12%) | defective gate (fabricated pin / wrong surface / vacuous) |
| TASK_BROKEN | **4** (1.4%) | instruction or expected answer unsatisfiable |

## TASK_BROKEN (fix or delete)

1. `Kenny/weather_edaccd` — expected "66"; DB says Wednesday high is 70. Data drifted between rebuilds.
2. `Minh/conference-review-submission_74ad80` — required upload `notes.txt` missing/renamed in VFS; site also walls agents at its own login (`conf_review_uid` not covered by auto-login).
3. `Minh/tax-filing-dmv-permits_ed6515` — expected answer arithmetically wrong.
4. `Minh/health-fitness-tracking_84a8c8` — task.json expects "6", verifier pins "3"; DB confirms 3.
   (Also: `Minh/cloud-dev-consoles_5028b8` — marked SUSPECT but instruction references Aug 13 data
   that doesn't exist; logs end 2026-06-26 and no 18:00-19:00 window anywhere has >10 WARN. Treat as broken.)

## Systemic root causes (ranked by blast radius)

1. **Recorder misses native HTML `<form>` POSTs** (→ most of the 53 RECORDING_GAPs).
   fetch/XHR is captured as `network`; classic form submits appear only as FE `submit`
   actions. Gold trajectories therefore fail sound backend gates. Same disease class as
   the eval-side query-drop fixed in `e8ecd8e` — fix belongs in `recorder.js`/gold
   re-recording, not in 53 verifiers. In every checked case the eval run proved the
   gate satisfiable.
2. **Auto-login vs `authenticate_by_form`** — annotators are auto-logged-in, so gold
   demos never POST credentials; auth gates fail on gold by construction
   (agency-portals_f8f9f5, dating_08335d, qa-knowledge_070bed, ai-chatbots_fb9d8b,
   email_fa155e, conference-review_380bcb…). Re-record with `_no_autologin`.
3. **Legacy LLM-fill fabricated pins** (`built_by: claude-judgement-fill+relaxed`) —
   values in neither instruction nor gold: `podcasts-audiobooks_cde5f2` (speed=0.5),
   `auctions_5a5f77` ($50 vs instruction's $52), `calendar-todo_b07459` (event title),
   `music_94c9a5` (wrong album id/type). The deterministic rebuilt gates in
   `scripts/build_verifier.py` never pin body_fields, so rebuilds fix these — but under-
   constrain (see task-conditioned selectivity discussion): pin what the instruction
   constrains, at gold-observed values.
4. **Wrong-surface gates** — checks on the GET/compose/FE-click instead of the mutation:
   health-portals_8fec2e (compose not send), code-editor_a6a45e + team-chat_abec04
   (GET not POST), forums_2a6d3d (FE delete click), crm_calendar-todo_3a5e33 (FE-only
   export), version-control_7143f4 (generic page GET).
5. **Stale file-picker upload gates** predating the VFS migration (`df851bc`):
   dating_f7f282, agency-portals_email_d51395 — rebuild against `/_fs/upload` flow.
6. **Vacuous/unfalsifiable gates** — dictionaries-language-tools_881010 (open-URL
   page_visited only), crowdfunding-donations_1ee169 (request_made with no url/method/body).

## Eval-run false attributions corrected during audit

- `comparison-aggregators_51adb4` — NOT agent capability: PhoneCompare slider bug
  (default `price_max=2000&battery_min=0` silently dropped spec-incomplete phones;
  fixed 2026-08-15 post-run). Re-run expected to pass.
- `crm_calendar-todo_3a5e33` — agent DID export (`GET /api/export?format=csv`); FE-only
  click gate caused the false negative.

## Tooling caveat

The pre-audit "ungrounded" heuristic (audit_pre.json) string-matches `re:`-prefixed
regex pins literally, producing ~50% false positives; auditors re-verified every flag
against the real `RequestMade` logic — the per-note "Gate grounding" line is the
trusted judgment, not the raw flag.

## Recommended action order

1. Fix `recorder.js` to capture native form POSTs; re-record (or synthesize from action
   log) the 53 RECORDING_GAP golds — restores the gold-pass invariant cheaply.
2. Rebuild the 35 SUSPECT gates (backend-gated, instruction-constrained pins grounded
   in gold; kill fabricated values).
3. Fix/delete the 4-5 broken tasks.
4. Re-record auth-gated golds with `_no_autologin`.
5. NOTE: `scripts/pull_from_railway.py` REPLACES `data/annotations/` wholesale — commit
   the note.md files to git before any pull, or they will be lost.
