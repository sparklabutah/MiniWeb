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
  6. 🔲 Task draft quality improvement (LLM rewriter for natural instructions)
  7. 🔲 Duplicate detection (embedding similarity)
  8. 🔲 Screenshot capture (html2canvas or server-side)
  9. 🔲 Post-hoc macro inference from trajectories
  10. 🔲 Cross-site task annotation support

Timeline:
  - Week 1: ✅ done — verifier framework, annotation UI, draft generator
  - Week 2-3: annotation sprint (4 annotators × 40h → ~2000 tasks at 4 min/task)
  - Week 4: QC review, macro inference, finalize dataset
