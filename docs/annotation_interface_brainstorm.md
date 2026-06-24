# Task Annotation Interface — Brainstorm

Goal: at least 2000 tasks in total. Each task might require navigation among sites (cross-site tasks count navigation time multiple times). Tasks should be rooted in macros — macro centric construction.

Timeline: we have a month. 2000 high quality web tasks, each with verifiers, macro labels, and reference trajectories.


## What we already have

- ~30 websites implemented with real datasets
- session-scoped data isolation (no Docker needed, in-memory overlay)
- browser-agent eval harness that runs agents against tasks
- macro vocabulary (163 macros from 4 benchmarks)
- 20 construction-time validation tasks per site (scaffolding, not final benchmark tasks)


## What we need to build

- a verifier toolbox that doesn't require writing Python per task
- an annotation interface where humans can create tasks fast
- a way to record reference trajectories during annotation
- duplicate detection + macro coverage tracking
- grounding verification — proof that agents actually navigated the site, not just answered from memory


---


## Verifier Toolbox

Reference: https://github.com/ServiceNow/webarena-verified (ServiceNow, 2025)

We adopt WebArena-Verified's approach: verifiers are declarative JSON configs, not Python functions. The eval harness interprets them at runtime.

Three verifier types:

  1. AgentResponseEvaluator
     Checks the agent's final text answer against expected values.
     Uses typed normalization so "8", "8.0", "$8", "eight" all match when type is "number".
     Supports alternatives: expected can be ["107", "one hundred and seven"].

  2. BackendStateEvaluator
     Calls site APIs after task completion, checks state changed correctly.
     For mutation tasks: "add to cart" → GET /api/cart → check item is there.
     For extraction tasks: cross-validate agent's answer against API response.
     Comparison operators: equals, contains, not_contains, greater_than, less_than,
     length_equals, exists, not_exists.

  3. GroundingEvaluator (inspired by WebArena-Verified's NetworkEventEvaluator)
     Verifies the agent actually visited the right pages — didn't just guess from memory.
     Checks the browser's navigation trace (URL history) during task execution.
     Example: task says "look up the price on the product page" → verify agent actually
     visited /sites/e-commerce/product/42, not just returned a number from training data.

     This is critical for benchmark integrity. Without it, a model that memorized WebShop
     product data could "pass" e-commerce tasks without ever opening the site.

     What it checks:
       - agent visited required URLs during the task
       - visits happened in the right order (searched before extracting)
       - agent came FROM the right page (referer check — navigated via the UI, not URL bar)
       - for mutation tasks: the right POST/PUT/DELETE request was made

Typed normalizers (what we need):
  string, number, boolean, date, currency, string_list, url

Task eval config format (per task, stored in JSON):
  {
    "eval": [
      {"evaluator": "AgentResponseEvaluator", "type": "number", "expected": "107"},
      {"evaluator": "BackendStateEvaluator", "endpoint": "GET /api/products?q=wireless", "field": "length", "comparison": "equals", "expected": 107},
      {"evaluator": "GroundingEvaluator", "required_urls": ["/sites/e-commerce/"], "required_actions": ["search"]}
    ],
    "eval_logic": "all"
  }

Each eval block is independent. The task passes only when all blocks pass (or any, configurable).
Annotators build this config through the UI — they never write JSON directly.


---


## Annotation Interface Proposals


### Kenny and Farhan (PI) idea

Interface:
  + MiniWeb live in browser
  + trajectory outliner sidebar (how many steps, dependencies between steps)
  + verifier selection panel
  + goal/instruction text input

How it works:
  + annotator gets a small sample of macros and a sample of websites
  + annotator picks macros and a website, then designs a task that exercises those macros
  + annotator performs the task, outlines the trajectory step by step
  + annotator selects which verifiers apply from a checklist
  + backend runs duplicate detection to prevent overlapping tasks
  + backend tracks macro coverage so annotators prioritize gaps

Strengths: fully human-driven, high creativity, annotator understands the task deeply
Weaknesses: slower (blank page problem), requires annotators to know the macro vocabulary,
  harder to ensure coverage balance without strong guidance


### Minh's idea

Interface:
  + MiniWeb live in browser
  + LLM-proposed task shown as starting point (annotator doesn't just accept it — must walk through)
  + macro library organized by verbs (annotator picks relevant macros)
  + verifier selection panel with live pass/fail indicators

How it works:
  + LLM pre-generates candidate tasks per site (from routes.py + macro list)
  + candidate task shows up. annotator reads it
  + annotator opens the site and actually tries to solve the task — trajectory is auto-recorded
  + annotator marks when the task is complete
  + annotator selects verifiers by toggling checkboxes. each checkbox has a live green/red indicator
    showing whether that check currently passes. annotators can include negative verifiers too
    (checks that should FAIL — e.g., "deleted item should NOT exist")
  + annotator selects relevant macro chain. later compared to LLM's hidden proposal for QC
  + annotator edits the task instruction if the LLM phrasing was wrong or unclear

Strengths: faster (draft beats blank page), trajectory recorded automatically, live verifier
  feedback means annotator catches bugs immediately
Weaknesses: risk of annotator laziness if they just rubber-stamp LLM drafts — mitigated by
  mandatory trajectory walkthrough (no "accept as-is" button)

Key insight from Minh: reviewers value human involvement. The paper must honestly say every
task was performed by a human. The LLM is a productivity tool for drafting, not a replacement.

Key insight from Minh on macro labeling: if annotators select macros from a visible list,
they will be biased toward familiar/common macros and ignore rare ones. Solution: annotators
do NOT label macros during annotation. Macros are inferred post-hoc from the recorded
trajectory by a separate automated process (LLM or rule-based). This also speeds up
annotation (one fewer step) and produces more objective macro labels.


### Claude's synthesis (combining both + WebArena-Verified verifier design)

Interface: split-screen annotator
  + LEFT: live MiniWeb site in an iframe. annotator actually uses the site here.
     browser extension auto-records all clicks/types/navigations as the trajectory.
     for cross-site tasks, annotator navigates between sites within the same iframe.
  + RIGHT: annotation panel with 4 sections:

    Section 1 — Task instruction
      LLM draft shown as editable text. annotator reads it, tries it in the iframe,
      then edits. the LLM also generates a hidden macro chain + expected answer
      (annotator doesn't see these — used for QC comparison later).

    Section 2 — Trajectory viewer
      live feed of recorded actions as annotator works in the iframe.
      each action shows: timestamp, action type (click/type/navigate), target element, URL.
      annotator can tag each action with a macro from a dropdown. (Minh: No, a macro can be a subsequence of actions)
      after completing the task, annotator types the final answer they observed.

    Section 3 — Verifier builder
      based on the WebArena-Verified evaluator architecture.
      three tabs, one per evaluator type:

      Tab A: Answer Check (AgentResponseEvaluator)
        expected answer field (pre-filled from annotator's answer in Section 2)
        type dropdown: string / number / boolean / date / currency / list
        alternatives field: add multiple acceptable answers
        🟢/🔴 live indicator

      Tab B: Backend Check (BackendStateEvaluator)
        endpoint field: GET /sites/email/api/folders/sent/count
        field path: .count
        comparison dropdown: equals / contains / not_contains / greater_than / exists / not_exists
        expected value field
        [+ Add another check] button for chaining
        🟢/🔴 live indicator per check

      Tab C: Grounding Check (GroundingEvaluator)
        auto-populated from the recorded trajectory in Section 2
        shows which URLs the annotator visited — these become the "required navigation" list
        annotator toggles which visits are required vs incidental:
          [x] /sites/e-commerce/          (required — agent must visit the site)
          [x] /sites/e-commerce/product/42 (required — agent must view this product)
          [ ] /sites/e-commerce/cart        (incidental — happened to visit but not required)
        for mutation tasks, shows POST/PUT/DELETE requests that were made:
          [x] POST /sites/e-commerce/cart/add  (required — agent must add to cart)
        this prevents agents from answering from internal knowledge without navigating

      all three tabs contribute to the final eval config.
      logic toggle: [x] ALL must pass  [ ] ANY must pass

    Section 4 — Macro chain
      macro library sidebar organized by verb category
      annotator drags macros into an ordered chain
      compared to LLM's hidden chain after submission for QC

Annotator workflow (~4-5 min per task):
  1. LLM draft appears. annotator reads it
  2. annotator performs the task in the iframe (auto-recorded)
  3. annotator types the answer they found, edits the instruction if needed
  4. answer auto-fills into the Answer Check verifier
  5. trajectory auto-fills into the Grounding Check verifier (annotator toggles required/incidental)
  6. annotator adds Backend Check verifiers if the task involves mutations
  7. annotator labels the macro chain
  8. submit — backend validates (all verifiers must pass with the recorded answer), checks duplicates

Why the grounding check matters:
  current LLMs have been trained on tons of web data. GPT-4o might "know" that Amazon sells
  wireless headphones for $29.99 without ever opening the e-commerce site. The grounding
  evaluator catches this — if the agent didn't visit /sites/e-commerce/product/42, it fails
  even if the answer is correct. This is the difference between "the agent can navigate" and
  "the agent can guess." For a web agent benchmark, we need to measure navigation, not memory.

  WebArena-Verified does this via HAR (HTTP Archive) network traces from the browser.
  We can do the same — browser-use already captures navigation events. The annotation
  interface just needs to let the annotator mark which navigations are essential.


---


## Shared concerns across all proposals

Duplicate prevention:
  + live embedding index (sentence-transformers) flags similar tasks on submit
  + if cosine similarity > 0.85 with existing task, show warning before saving
  + annotators can still override if the tasks are genuinely different

Macro coverage dashboard:
  + shows heatmap: which macros × which sites have enough tasks
  + annotators are guided to under-covered areas first
  + target: every macro exercised by at least 10 tasks across 3+ sites

Quality control:
  + every task has a mandatory human trajectory walkthrough
  + auto-validate on submit: verifier config must pass with recorded answer
  + second annotator reviews 20% random sample
  + annotator macro chain compared to LLM hidden chain — disagreements flagged
  + track per-annotator speed, acceptance rate, and disagreement rate

Cross-site tasks:
  + some tasks span 2-3 sites (e.g., "look up contact in CRM, email them")
  + annotation interface supports this — iframe can navigate between sites
  + grounding verifier checks navigation across multiple sites
  + eval config specifies "sites": ["crm", "email"] so harness knows what's involved
  + these are harder tasks (5+ macros), naturally fall into "hard" difficulty tier

For the paper:
  "All tasks were created and verified through human trajectory walkthroughs.
  LLM-generated drafts were used to accelerate annotation, but every task was
  manually performed, edited, and verified by a human annotator. Our evaluation
  framework adopts the typed evaluation pipeline from WebArena-Verified
  (ServiceNow, 2025), extended with grounding verification to ensure agents
  navigate the web rather than relying on internal knowledge."


---
