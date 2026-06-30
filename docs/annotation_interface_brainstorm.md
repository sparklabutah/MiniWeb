# Task Annotation Interface — Brainstorm

Goal: at least 2000 tasks in total. Each task might require navigation among sites (cross-site tasks count navigation time multiple times). Tasks should be rooted in macros — macro centric construction.

Timeline: we have a month. 2000 high quality web tasks, each with verifiers, macro labels, and reference trajectories.


## What we already have (implemented)

- 27 websites built with real datasets, all validated
- session-scoped data isolation (in-memory overlay, no Docker)
- browser-agent eval harness (browser-use + GPT-4o/Claude/Gemini)
- macro vocabulary (163 macros from 4 benchmarks)
- annotation interface at /annotate/ (same-origin as MiniWeb, 4-step wizard)
- verifier toolbox: AgentResponseEvaluator, BackendStateEvaluator, GroundingEvaluator
- typed normalizers: string, number, boolean, date, currency, string_list, url
- 1412 pre-generated task drafts across 27 sites (in annotation/generated/)
- task storage: annotation/tasks/<task_id>/ with task.json, trajectory.json, html/


## What still needs work

- task draft quality: current drafts are template-style ("What is the X of Y?"), need
  WebArena/Mind2Web-style natural instructions ("Find me a hotel in NYC under $200")
- macro labeling pipeline: auto-infer macros from trajectories post-hoc
- duplicate detection: embedding similarity check on submit
- screenshot capture: currently placeholder, needs html2canvas or server-side rendering
- cross-site task support in the annotation interface


---


## Verifier Toolbox

Reference: https://github.com/ServiceNow/webarena-verified (ServiceNow, 2025)

Implemented in annotation/evaluators.py. Declarative JSON configs, no Python per task.

Three verifier types:

  1. AgentResponseEvaluator — checks agent's text answer with typed normalization
  2. BackendStateEvaluator — checks site API state (mutations, counts, existence)
  3. GroundingEvaluator — verifies agent navigated the site (anti-cheating)

Each task's eval config is a list of evaluator blocks with AND/OR logic.
Annotators build this via the verifier checklist UI — never write JSON directly.


---


## Annotation Workflow (implemented)

4-step wizard at http://localhost:8080/annotate/

  Step 1: READ TASK
    Pre-generated draft is shown (from annotation/generated/<site>.json).
    Annotator reads the instruction. Can edit freely — drafts are starting
    points, not final. The instruction should be rewritten to sound like
    a real user request, not a database query.

    Good: "Find me the cheapest wireless headphones and add them to my cart"
    Bad: "What is the price of product ID 42?"

    Reference for task style: WebArena (Zhou et al., 2024) and Mind2Web
    (Deng et al., 2023) — tasks should be natural language instructions
    that a real person would give to an assistant. See examples:

    WebArena style:
      "Draft an email to the shop owner via their contact us form for a coupon as I am a student"
      "Create a private NodeJS repository called web_agent_nodejs using the right template"
      "Show me the route and driving time from the city where my customer Sophia Young lives to NYC"

    Mind2Web style:
      "Find used audi 100 sorted by best deal"
      "Find the highest rated fast responding phone repair shop for data recovery in Houston"
      "Find adults only, airfare included vacations in Mexico during the month of May"

  Step 2: RECORD TRAJECTORY
    Click "Start Recording". Navigate the site in the left iframe.
    System auto-captures every page navigation as an action/observation pair:
      - Action: the URL navigated to
      - Observation (3 types captured simultaneously):
        1. Raw HTML — document.outerHTML (first 5000 chars)
        2. Accessibility tree — headings, inputs, buttons, links, tables, body text
        3. Screenshot — placeholder (needs html2canvas integration)
    Click "Stop Recording" when done solving the task.
    Trajectory saved to annotation/tasks/<id>/trajectory.json (ax_tree only)
    and annotation/tasks/<id>/html/ (raw HTML per step).

  Step 3: TYPE ANSWER
    Annotator types the correct answer they observed.
    Selects answer type: string / number / boolean / list.
    Can add alternative acceptable answers (one per line).

  Step 4: SELECT VERIFIERS
    Auto-populated checklist based on answer + trajectory:
      [x] Answer match — pre-filled from step 3
      [x] Grounding — pre-filled from recorded URLs
      [ ] Backend count check — annotator fills endpoint + expected value
      [ ] Backend existence check — verify item exists after mutation
      [ ] Backend deletion check — verify item gone after deletion
    Each verifier shows live 🟢/🔴 indicator via "Test All" button.
    Annotator can add custom backend checks.

  Submit → task saved → auto-advance to next draft.


---


## Key Design Decisions

Macro labeling is NOT done by annotators:
  If annotators select macros from a visible list, they bias toward common
  macros they recognize and skip rare ones. This produces skewed coverage.
  Instead, macros are inferred post-hoc from recorded trajectories by an
  automated process (LLM-based or rule-based, looking at the URL sequence
  and action types). This is more objective and faster for annotators.

Task drafts are starting points, not final tasks:
  The pre-generated drafts (annotation/generated/) are template-based and
  need heavy rewriting by annotators. The draft gives structure (which site,
  what difficulty, what entities to reference) but the annotator rewrites
  the instruction in natural language. Drafts that can't be saved as real
  tasks should be skipped.

Observations are multi-modal:
  Each trajectory step captures raw HTML, accessibility tree, and screenshot.
  This mirrors what a browser agent would observe:
    - Raw HTML: what the page source looks like
    - AX tree: structured semantic content (what a screen reader would see)
    - Screenshot: visual rendering (what a vision model would see)
  All three are stored so we can experiment with different agent input modes.

Grounding verification prevents cheating:
  Without it, an LLM that memorized training data can "answer" questions
  about products, prices, or facts without ever opening the website.
  The GroundingEvaluator checks the agent's navigation trace — it must
  have visited the relevant pages to get credit.


---


## Proposals (historical context)


### Kenny and Farhan (PI) idea

Interface:
  + MiniWeb live in browser
  + trajectory outliner sidebar
  + verifier selection panel
  + goal/instruction text input

How it works:
  + annotator gets a small sample of macros and websites
  + annotator designs a task from scratch
  + annotator performs the task, outlines trajectory
  + annotator selects verifiers from checklist
  + backend tracks macro coverage and prevents duplicates

Strengths: fully human-driven, high creativity
Weaknesses: slower (blank page problem), coverage hard to balance


### Minh's idea

Interface:
  + MiniWeb live in browser
  + LLM-proposed task as starting point
  + verifier selection with live pass/fail indicators

How it works:
  + LLM pre-generates candidate tasks per site
  + annotator walks through the task (mandatory — no rubber-stamping)
  + annotator selects verifiers with live feedback
  + annotator edits instruction if LLM phrasing was wrong

Strengths: faster (draft beats blank page), live verifier feedback
Weaknesses: risk of lazy annotators — mitigated by mandatory walkthrough

Key insights from Minh:
  - Reviewers value human involvement — paper must honestly claim human authorship
  - If annotators select macros from a list, they bias toward familiar ones.
    Remove macro selection entirely — infer post-hoc from trajectories
  - Task instructions must be natural (WebArena/Mind2Web style), not template queries


### Implemented synthesis

Combines Minh's LLM-draft approach with WebArena-Verified's verifier architecture.
Runs as part of the MiniWeb Flask app (same origin, no cross-origin iframe issues).

4-step wizard: Task → Record → Answer → Verify
No macro selection (inferred post-hoc)
Auto-recording trajectory with 3 observation types
Declarative verifier configs with live testing
Pre-generated drafts with prev/next navigation
Task storage: lightweight metadata + separate HTML snapshots



---


## Macro-Chain-First Pipeline — Attempts and Lessons Learned

The original LLM-generated drafts (annotation/generated/) had three fatal problems:
too ambiguous, impossible to perform, not realistic. We attempted a macro-chain-first
pipeline to fix this. Here is a chronological record of what we tried, what worked,
and what still doesn't work.


### Attempt 1: Random macro chain sampling + agent walking

Idea:
  For a given website, randomly sample macro chains of length 1, 3, 5.
  Let a Claude Code agent walk each chain on the live site using a CLI tool
  (chain_walker_lib.py) that provides ax_tree observations at each step.
  If the agent completes all macros, the chain is valid. Then generate
  instructions from the valid trajectories.

Implementation:
  scripts/sample_macro_chains.py — sampled 1,375 chains across 27 sites
  scripts/chain_walker_lib.py — CLI for agents to interact with Flask test client
  scripts/instruction_gen_lib.py — CLI for agents to generate instructions
  scripts/prune_bad_chains.py — removes walks with wrong trajectory format

Results:
  - 1,332 valid chain walks (96.8% success)
  - 149/149 macros covered (100%)
  - ~50% of walks had bad trajectory format (agents wrote batch scripts
    instead of using the CLI, producing {"action": "POST /api/..."} instead
    of {"type": "action", "url": "..."}). Had to prune and re-walk.
  - After pruning + re-walking: 1,332 valid walks with correct format

Problem discovered: The randomly sampled macro chains produce INDEPENDENT subtasks,
not DEPENDENT ones. A chain like [filter_by_dropdown, export_by_dropdown, create_from_free_text]
generates "filter transactions, export CSV, add a payee" — three unrelated actions.


### Attempt 2: Coherent story wrapping

Idea:
  Keep the same random chains but rewrite instructions to wrap them in a
  coherent narrative. Instead of "Do A. Then B. Finally C." write
  "You're reviewing your budget. Filter by Groceries, export the results,
  and create a note for your records."

Result:
  Instructions SOUND coherent but the subtasks are still independent.
  "You're reviewing your budget" is a narrative wrapper, not a real
  dependency. Filtering groceries doesn't affect the export, and the
  export doesn't affect the note creation. Minh flagged this.


### Attempt 3: Dependency language injection

Idea:
  Rewrite instructions so each step explicitly references the previous
  step's result. "From the filtered results, export...", "Based on the
  export, create a note about..."

Result:
  The language suggests dependency but the dependency is ARTIFICIAL.
  Example: "Log in, save paper 5, then use the topic of paper 5 to
  search for 'machine learning optimization'" — saving paper 5 and
  searching for ML optimization are actually independent. The "use the
  topic" connection is forced and doesn't represent a real workflow.
  Minh flagged this as still not making sense.


### Attempt 4: Prune non-chainable chains

Idea:
  Classify macros as producers (search, filter, navigate), consumers
  (extract, compute, compare), and mutators (create, edit, delete).
  Only keep chains where a producer feeds into a consumer or mutator.
  Prune chains of independent mutators (save + follow + report).

Result:
  Pruned 290 non-chainable chains. 1,042 tasks remain.
  But even the "chainable" chains have artificial dependencies because
  the macros were RANDOMLY sampled. filter→sort→extract CAN chain
  naturally, but the specific randomly-sampled combination might not
  make sense for the site's data.


### Attempt 5: Cross-site chains via entity handoff + swap-test validation

Scope: this attempt targets CROSS-SITE task generation, not single-site. The
single-site dependency problem (Attempts 1–4) is set aside here; this addresses
how to construct tasks that genuinely require two (or more) sites.

Sampling (bridge-first, not chain-first):
  1. Define entity bridges once (universe schema work, not per-task): an entity
     type (restaurant, order, paper, listing) + the PRODUCER macro on site A whose
     terminal state yields that entity + the CONSUMER macro on site B that takes it
     as input. ~10 bridges total across the site universe.
  2. To sample a candidate: pick a bridge, grow a producer chain on A that
     terminates in the producer macro, grow a consumer chain on B that starts from
     the consumer macro. The bridge defines the legal cut; the chains fill each side.
     This guarantees the seam is a real handoff BY CONSTRUCTION, the same way
     goal-first guarantees single-site dependency.

Info carry-over via screenshot (the key mechanism):
  Problem: if the handoff is the raw backend entity (e.g. restaurant_id=42 from an
  API response), two failures follow — (a) the agent uses privileged info a real
  user never sees, and (b) the producing work on A becomes optional, because B can
  jump straight to the ID. Both collapse the task back to independence.

  Mechanism: at the end of the macro-A chain, the harness captures a SCREENSHOT of
  the final A page. The execution agent for macro B is given ONLY that screenshot
  as its starting reference — not the A-trajectory, not any API/JSON, not the entity
  ID. The agent must read the carried value off the rendered page exactly as a human
  user would, then act on B from there. This enforces:
    - no privileged/hidden info crosses the seam (only what was visually on screen),
    - the carried value is whatever a user could actually observe,
    - B genuinely starts from A's observable output.

Validation — do NOT prompt the agent to "be dependent":
  Instructing the B-agent to "use useful info from A" repeats Attempt 3's mistake:
  it makes the agent BEHAVE dependently rather than testing whether B actually
  REQUIRES A. A cooperative agent will reference A's output even when B doesn't need
  it. So dependency is tested structurally, by the harness, not by prompt.

  Two gates per candidate:
    Gate 1 — Resolution: give B only the A-screenshot handoff and run it.
      - B reaches its terminal state using the carried value → candidate proceeds.
      - B cannot proceed (consumer macro has no slot for that entity, or entity
        absent on B) → reject (broken bridge / not a real producer→consumer pair).
    Gate 2 — Swap test (the actual dependency test): re-run B's verifier with the
      entity A produced, and again with a DIFFERENT entity of the same type.
      - B passes EITHER way → A's output didn't matter → INDEPENDENT → reject
        (this is the errand-list case, caught mechanically, no trust in the agent).
      - B passes ONLY with A's specific entity → dependency is real → KEEP.
    The swap test is the cross-site analogue of "could these steps happen in any
    order"; it tests the TASK, not the agent's cooperativeness.

Answer-leak prevention (falls out of the above):
  The instruction must reference the carried entity by the PROPERTY used to find it
  ("book the highest-rated Italian place from the reviews site"), never by ID
  ("book restaurant 42"). An ID-referencing instruction trivially survives the swap
  test (43 works as well as 42), which flags it as not-genuinely-cross-site. The
  screenshot handoff reinforces this: there is no ID to leak, only the visible
  property.

Preconditions (non-negotiable for this attempt):
  - Shared canonical entity store: "restaurant 42" must be the SAME row on A and B,
    or the swap test cannot be constructed and the handoff cannot be validated.
  - B's verifier must be parameterized by the carried entity, so it can be re-run
    with a swapped entity for Gate 2.
  - Screenshot capture must be real (currently placeholder — see implementation
    priority #8); this attempt depends on it.

Logged failure taxonomy (paper-grade evidence of genuine dependency):
  Per candidate, record where it failed — bridge resolution (Gate 1), execution
  (B unsolvable), or swap test (Gate 2, B insensitive to A's output). Reporting
  "X% of naively-sampled cross-site chains fail the swap test" is the quantitative
  proof that distributing macros across sites does not create dependency — the
  measured version of the Attempts 1–4 lesson.

Status: design stage. Depends on shared entity store + screenshot capture +
entity-parameterized verifiers being in place before candidates can be validated.

## Annotation Interface — Current State (implemented)

Light-mode 4-step wizard at /annotate/. Major improvements since initial version:

  Auto-login:
    Sites default to user 1 via before_request hook (MINIWEB_NO_AUTOLOGIN=1 disables).
    Tasks with authenticate_by_form macro have requires_login=true flag — auto-login
    is skipped so the agent must log in explicitly.

  Persistent task instruction:
    The draft instruction is shown in a fixed blue bar between the step tabs and
    step content, always visible across all 4 steps.

  Admin verification API (/_admin/):
    /_admin/user/<site>/<user_id> — aggregated user data (profile, cart, saved items,
      transactions, etc.) across all data files. Checks user_id, author_id, seller_id, etc.
    /_admin/log — request history for current session (method, path, body, response).
      Filter by ?method=POST, ?path=transfer, ?last=10.
    /_admin/session — current Flask session state (user_id, verified, etc.)
    /_admin/data/<site>/<file> — raw data file access with ?key=val filtering,
      ?_id=N, ?_count=1, ?_field=name.
    /_admin/files/<site> — list available data files.
    All admin endpoints read through the data overlay (see agent's mutations).

  Verifier UI (Step 4):
    Auto-populated from admin API — no manual endpoint/method/field configuration.
    Three sections:
      1. Answer match — auto from Step 3 answer
      2. User state — fetched from /_admin/user, shows profile arrays (saved_papers,
         cart, wishlist) with contains comparison, and data counts with equals comparison.
         Uses session user_id (from /_admin/session), not hardcoded.
      3. Agent actions — fetched from /_admin/log, shows POST/PUT/DELETE mutations.
    "Test All" uses Flask internal dispatch with forwarded cookies (same data overlay
    session as the annotator's browser).
    Array profile fields use "contains" comparison (check specific item ID, not count).

  API Reference panel:
    Collapsible panel at bottom of right sidebar. Shows:
      - Verification endpoints (/_admin/user, /_admin/log, /_admin/session, data files)
      - Site API endpoints with auto-generated descriptions, method colors, params
    Click to copy endpoint path. Updates on site change.

  Skip with reason:
    Skip button opens modal requiring a reason:
      - Ambiguous task (instruction unclear)
      - Broken site (page errors, missing functionality)
      - Impossible task (thoroughly explored, can't be done)
    Saved to annotation/reported/<site>.json.

  Reset button:
    Index page shows "Reset All Human Annotations" when tasks exist.
    Requires typing "reset" to confirm. Only deletes annotation/tasks/
    (human reviews), not annotation/validated/ (pipeline drafts).

  Data separation:
    annotation/validated/ — pipeline-generated drafts (1,042 tasks, read-only source)
    annotation/tasks/ — human-reviewed tasks (grows as annotators submit)
    annotation/chain_runs/ — agent walk trajectories
    annotation/chains/ — sampled macro chains
    annotation/reported/ — skip reports from annotators

  Login normalization (scripts/normalize_task_instructions.py):
    Strips "Log in as X (password: Y)" from tasks that don't have auth macros.
    Tasks with authenticate_by_form/login_by_form keep login instructions.
    268 tasks flagged requires_login=true.

  Macro coverage tracking:
    _get_macro_coverage() counts only human-reviewed tasks (annotation/tasks/).
    selectedMacros from draft carry through on submit.


---


## Shared concerns

Duplicate prevention:
  + embedding similarity check on submit (not yet implemented)
  + warn if cosine similarity > 0.85 with existing task

Task instruction quality:
  + drafts must be rewritten by annotators to sound natural
  + reference: WebArena and Mind2Web task corpora in macros/datasets/
  + avoid: "How many X are there?" "What is the Y of Z?"
  + prefer: "Find me...", "Show me...", "I need to...", "Help me..."

Quality control:
  + mandatory trajectory walkthrough for every task
  + auto-validate: verifier config must pass with recorded answer
  + second annotator review for 20% random sample
  + per-annotator metrics: speed, acceptance rate

Cross-site tasks:
  + iframe can navigate between sites (same Flask app)
  + grounding verifier checks navigation across sites
  + eval config specifies "sites": ["crm", "email"]
  + naturally hard tasks (5+ macros)

For the paper:
  "All tasks were created and verified through human trajectory walkthroughs.
  LLM-generated drafts were used to accelerate annotation, but every task was
  manually performed, edited, and verified by a human annotator. Macro labels
  were inferred post-hoc from recorded trajectories to avoid annotator selection
  bias. Our evaluation framework adopts the typed evaluation pipeline from
  WebArena-Verified (ServiceNow, 2025), extended with grounding verification
  to ensure agents navigate the web rather than relying on internal knowledge."


---


## Implementation priority

  1. ✅ Verifier primitives + evaluator framework
  2. ✅ Annotation UI (4-step wizard, same-origin iframe)
  3. ✅ Trajectory recording (auto-capture with 3 observation types)
  4. ✅ Pre-generated task drafts (1412 across 27 sites)
  5. ✅ Task storage (directory per task: metadata + trajectory + HTML)
  6. 🔲 Task draft grounding validation (some drafts reference entities that don't exist
     on the page being queried — e.g., asking about a payee that's actually a merchant name.
     Annotators must validate each draft by walking through it. Impossible tasks should be
     skipped or rewritten. A future improvement: type-check entity placeholders against the
     specific data collection each template queries.)
  7. 🔲 Duplicate detection (embedding similarity)
  8. 🔲 Screenshot capture (html2canvas or server-side)
  9. 🔲 Post-hoc macro inference from trajectories
  10. 🔲 Cross-site task annotation support

Timeline:
  - Week 1: ✅ done — verifier framework, annotation UI, draft generator
  - Week 2-3: annotation sprint (4 annotators × 40h → ~2000 tasks at 4 min/task)
  - Week 4: QC review, macro inference, finalize dataset
