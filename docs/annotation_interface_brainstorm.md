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


---

## Verifier Architecture (adopted from WebArena-Verified)

Reference: https://github.com/ServiceNow/webarena-verified (ServiceNow, 2025)

WebArena-Verified redesigned WebArena's evaluation to be more rigorous and structured.
Their key insight: separate the **evaluation pipeline** into four clean steps, and use
**typed normalization** so that "8", "8.0", "eight", "$8.00" all compare correctly
when the expected type is "number".

### WebArena-Verified's four-step evaluation:

  1. **Get actual value** — extract from agent response or network trace
  2. **Get expected value** — from task config (with alternatives support)
  3. **Normalize both** — schema-driven type conversion (string, number, currency,
     date, URL, boolean, coordinates, etc.)
  4. **Compare normalized values** — recursive structural matching with assertions

Their type registry includes specialized normalizers for: string, number, boolean,
currency, date, duration, distance, URL, coordinates, full_address, location_name,
month, base64_string, json_string, markdown_string, string_list, empty.

Each type knows how to normalize messy real-world values. For example:
  - NormalizedCurrency("$1,234.56") == NormalizedCurrency("1234.56")
  - NormalizedDate("Jan 15, 2025") == NormalizedDate("2025-01-15")
  - NormalizedURL("http://site.com/page/") == NormalizedURL("http://site.com/page")

### What we adopt for MiniWeb:

We adopt the four-step pipeline and typed normalization, but simplify for our context
(MiniWeb is simpler than WebArena — no Docker, no network traces, one Flask app).

**MiniWeb evaluator types** (each ~10-30 lines of code):

  1. AgentResponseEvaluator — checks the agent's final text answer
     Uses typed comparison: if expected is "8" and schema says "number",
     then "There are 8 items" matches because 8 is extracted and compared as number.

  2. BackendStateEvaluator — checks site API state after task completion
     Calls GET/POST to site APIs, extracts values, compares with typed normalization.
     This is what our current verifiers.py files do, but declarative instead of imperative.

  3. URLEvaluator — checks the agent's final URL
     For navigation tasks: "Navigate to the settings page" → verify URL contains /settings.

**MiniWeb normalized types** (subset of WebArena-Verified, what we actually need):

  | Type | Normalizes | Example |
  |------|-----------|---------|
  | string | case, whitespace, articles | "The Product" → "product" |
  | number | comma, currency symbols, units | "$1,234" → 1234.0 |
  | boolean | yes/no/true/false/1/0 | "yes" → true |
  | date | various date formats | "Jan 15" → "2025-01-15" |
  | currency | symbol + amount | "$29.99" → 29.99 |
  | string_list | comma/newline separated | "a, b, c" → ["a","b","c"] |
  | url | trailing slashes, protocol | "http://x.com/" → "x.com" |

**Alternatives support** (directly from WebArena-Verified):
  Expected values can have alternatives: ["success", "ok", "completed"]
  means any of these is a valid answer. This handles ambiguous tasks where
  multiple answers are correct.

### Task evaluation config format:

Each task specifies its evaluators declaratively in JSON (no Python code per task):

```json
{
    "task_id": "e-commerce_042",
    "instruction": "How many wireless headphones are there?",
    "eval": [
        {
            "evaluator": "AgentResponseEvaluator",
            "expected": {"retrieved_data": "107"},
            "results_schema": {"type": "number"},
            "alternatives": ["107", "one hundred seven"]
        },
        {
            "evaluator": "BackendStateEvaluator",
            "method": "GET",
            "url": "/sites/e-commerce/api/products?q=wireless+headphones",
            "expected_field": "length",
            "expected_value": 107,
            "comparison": "equals"
        }
    ],
    "eval_logic": "all"
}
```

A task's `eval` is a list of evaluator configs. `eval_logic` is "all" (AND) or "any" (OR).
Each evaluator runs independently and produces assertions (pass/fail with detail messages).
The task passes only if the combined logic is satisfied.

### Comparison operators for BackendStateEvaluator:

  | Operator | Meaning | Example |
  |----------|---------|---------|
  | equals | exact match (after normalization) | count == 107 |
  | contains | substring/element present | response contains "wireless" |
  | not_contains | substring/element absent | response does NOT contain "error" |
  | greater_than | numeric comparison | price > 10 |
  | less_than | numeric comparison | price < 100 |
  | length_equals | array/string length | len(results) == 5 |
  | exists | field is present and non-null | user.cart exists |
  | not_exists | field is absent or null | document was deleted |

### What this means for the annotation interface:

The verifier builder in the annotation UI maps directly to this config:

  Annotator selects:
    1. Evaluator type (AgentResponse / BackendState / URL)
    2. For AgentResponse: expected answer + type (string/number/date/...)
    3. For BackendState: API endpoint + field + comparison + expected value
    4. For each: whether it's a positive or negative check

  The UI renders this as the checkbox panel with live green/red indicators.
  Behind the scenes, it's building the JSON eval config above.

  Annotator does NOT write code. They fill in fields and toggle checkboxes.
  The harness interprets the config at eval time using the four-step pipeline.


---

## Consolidated Annotation Interface Proposal

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
      Based on the WebArena-Verified evaluator architecture.
      Shows evaluator configs as a checklist, each with a live green/red indicator.

      Annotator builds the eval config by adding evaluator blocks:

        [+ Add Evaluator]

        Evaluator 1: AgentResponseEvaluator           🟢
          Type: number
          Expected: 107
          Alternatives: "107", "one hundred seven"

        Evaluator 2: BackendStateEvaluator             🟢
          Endpoint: GET /sites/e-commerce/api/products?q=wireless
          Field: length
          Comparison: equals
          Expected: 107

        Evaluator 3: BackendStateEvaluator             🟢
          Endpoint: GET /sites/e-commerce/api/products?q=wireless
          Field: [0].name
          Comparison: contains
          Expected: "wireless"

        Logic: [x] ALL must pass  [ ] ANY must pass

      Each evaluator block shows its current result (green/red) live after the
      annotator completes the task in the iframe.

Annotator workflow (per task, ~4 min):
  1. LLM task draft appears in the task panel. Annotator reads it.
  2. Annotator opens the site in the iframe and actually performs the task (auto-recorded).
  3. Annotator edits the task instruction if needed, confirms the answer they observed.
  4. Annotator selects macro chain from the macro library.
  5. Annotator builds eval config using the verifier builder (add evaluators, fill fields).
     Live indicators show which checks pass.
  6. Submit. Backend checks for duplicates (embedding similarity > 0.85 warns before saving).

Duplicate prevention + macro coverage:
  + Live embedding index (sentence-transformers) flags similar existing tasks on submit.
  + Dashboard shows macro coverage heatmap: which macros still need more tasks.
  + Annotators are guided to under-covered macros/sites to ensure balanced coverage.

Quality control:
  + Every task has a human trajectory walkthrough (mandatory).
  + Auto-validate on submit: run the eval config against the recorded answer. If it fails,
    the task has a bug — annotator must fix before submitting.
  + Second annotator review for a random 20% sample.
  + Compare annotator's macro chain to LLM's hidden proposal — disagreements flag ambiguous tasks.

For the paper: "All 2000 tasks were written and verified by human annotators through
trajectory walkthroughs. Our evaluation framework adopts the four-step typed evaluation
pipeline from WebArena-Verified (ServiceNow, 2025), extended with MiniWeb-specific
backend state checking and macro-annotated task composition."

Implementation priority:
  1. Typed normalizer library (string, number, boolean, date, currency, string_list, url)
  2. Evaluator framework (AgentResponseEvaluator, BackendStateEvaluator, URLEvaluator)
  3. LLM task candidate generator (pre-generates drafts per site from routes + macros)
  4. Annotation UI (split-screen: iframe + panel with task/trajectory/verifier builder)
  5. Trajectory auto-recording (browser extension or proxy-based capture)
  6. Duplicate detection + macro coverage dashboard

Estimated timeline:
  - Week 1: evaluator framework + normalizers + LLM generator + basic UI
  - Week 2-3: annotation sprint (4 annotators × 40h = 160h → ~2400 tasks at 4 min/task)
  - Week 4: QC review, fix flagged tasks, finalize dataset
