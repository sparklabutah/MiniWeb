Goal: at least 2000 tasks in total. Each tasks might require navigation among site (which we can count this time multiple time). Task should be rooted in macros, so macro centric construction

What we already have:
- roughly 30 websites implemented with actual dataset
- a verifier toolbox (not implemented, but should be easy to do). Verifiers are function that return true or false. A full task verifier is a boolean chain of multiple verifiers (WebArena)
    + Text
      > exact matching
      > fuzzy matching
      > must have
    + Backend
      > URL check
      > web state check


What we are doing in this doc: we are trying to come up with the best interface for human annotator to annotate the task in the shortest amount of time. We have a month, and we hope to get at least 2000 high quality web tasks.


Kenny and Farhan (PI) idea:
Interface
  + MiniWeb
  + trajectory outliner (how many macros, dependencies, note that this is not macro specific, users will assign macro to it)
  + verifier selection
  + goal input

How this work:
  + a small sample of macros and sample of website
  + user select macros and website based on the task they can design
  + sth run in the backend to prevent duplicate


Minh:
Interface
  + MiniWeb
  + Proposed task (LLM generated)
  + Macros lib by verbs
  + Verifiers selection

How this works
  + task show up
  + user record their trajectory try to solve that task
  + user mark when task is complete, and choose verifiers that combine to build a task completion verifier
  + user select relevant macro chain based on that task, we will see if this match what the LLM macros


Claude (AI contributor) — consolidated proposal incorporating Minh's feedback:

Interface: Split-screen annotator
  + LEFT: live MiniWeb site in an iframe (annotator interacts with the actual website)
  + RIGHT: annotation panel with 3 sections:

    Section 1 — Task instruction
      LLM-generated draft task is shown as a starting point (editable text field).
      Annotator MUST attempt the task in the iframe before proceeding — no rubber-stamping.
      Annotator edits the instruction if the LLM phrasing was unclear or wrong.
      The LLM also generates a hidden macro chain and expected answer (used for validation
      later, but the annotator doesn't see these to avoid biasing their walkthrough).

    Section 2 — Trajectory recording
      Browser extension auto-records the annotator's clicks/types/navigations as they solve
      the task in the iframe. This captures the reference trajectory automatically.
      Annotator can annotate each step with the corresponding macro from the macro library.
      After completing the task, annotator confirms the final answer they observed.

    Section 3 — Verifier builder (checkbox panel with live indicators)
      Shows a checklist of available verifier primitives for the current site.
      Each verifier has a live indicator light: green = currently true, red = currently false.
      This lets the annotator see in real-time which checks pass after their walkthrough.
      Annotator toggles which verifiers to include in the final task verifier:

        [x] 🟢 Text: agent answer contains "8"             (must_include)
        [x] 🟢 Text: agent answer exactly matches "8"      (exact_match)
        [ ] 🟢 Text: agent answer does NOT contain "error"  (must_exclude)
        [x] 🟢 Backend: GET /api/tools returns 8 items     (backend_state)
        [ ] 🔴 Backend: user cart is empty                  (negative check)

      Annotator can also add custom verifiers by filling in:
        type (dropdown) + endpoint/value (text fields) + negate (checkbox)

      Verifier config is stored as JSON — no Python code needed:
        {
          "checks": [
            {"type": "fuzzy_match", "expected": "8", "source": "agent_answer"},
            {"type": "backend_state", "method": "GET", "url": "/api/tools", "check": "len == 8"}
          ],
          "logic": "all"
        }
      Each primitive is ~10 lines of code in the harness. The harness chains them based on config.

Annotator workflow (per task, ~4 min):
  1. LLM task draft appears in the task panel. Annotator reads it.
  2. Annotator opens the site in the iframe and actually performs the task (auto-recorded).
  3. Annotator edits the task instruction if needed, confirms the answer they observed.
  4. Annotator selects macro chain from the macro library (compared to LLM's hidden proposal later for QC).
  5. Annotator toggles verifier checkboxes — live green/red indicators show which checks pass.
  6. Submit. Backend checks for duplicates (embedding similarity > 0.85 warns before saving).

Duplicate prevention + macro coverage:
  + Live embedding index (sentence-transformers) flags similar existing tasks on submit.
  + Dashboard shows macro coverage heatmap: which macros still need more tasks.
  + Annotators are guided to under-covered macros/sites to ensure balanced coverage.

Quality control:
  + Every task has a human trajectory walkthrough (mandatory — no accept-as-is shortcut).
  + Auto-validate on submit: run the recorded answer against the verifier config. If it fails, the task has a bug — annotator must fix before submitting.
  + Second annotator review for a random 20% sample.
  + Compare annotator's macro chain to LLM's hidden proposal — disagreements flag ambiguous tasks.

For the paper: "All 2000 tasks were written and verified by human annotators through
trajectory walkthroughs. LLM-generated drafts were used as starting points to accelerate
annotation, but every task was manually performed, edited, and verified by a human annotator."

Implementation priority:
  1. Verifier primitive library + JSON config harness (unblocks verifier selection UI)
  2. LLM task candidate generator (pre-generates drafts per site from routes + macros)
  3. Annotation UI (split-screen: iframe + panel with task/trajectory/verifier sections)
  4. Trajectory auto-recording (browser extension or proxy-based capture)
  5. Duplicate detection + macro coverage dashboard
  6. Second-annotator review queue

Estimated timeline:
  - Week 1: verifier library + LLM generator + basic UI
  - Week 2-3: annotation sprint (4 annotators × 40h = 160h → ~2400 tasks at 4 min/task)
  - Week 4: QC review, fix flagged tasks, finalize dataset
