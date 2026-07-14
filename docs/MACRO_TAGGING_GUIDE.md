# Macro Tagging Guide

This guide is for human annotators tagging action trajectories with macro labels in the MiniWeb annotation interface.

## What is a Macro?

A macro is a **primitive UI skill** — a single atomic interaction pattern that an agent must perform. Examples: dragging a slider, filling a form, selecting from a dropdown. Each macro has a name like `filter_by_slider` (verb + modality).

## The Mindset: a Three-Way Contract

Every task is a contract between three parties, and every bad task is a disagreement between two of them:

- **The instruction** — everything the agent is told. If the rubric will check a mechanism ("used the slider", "clicked the week arrows"), the instruction MUST state it. An agent can't be failed for not following a rule it never saw.
- **The environment** — what's actually possible. Confirm every sampled macro is doable on the site before you record (mark N/A if not).
- **The verifier** — what gets checked. Default to **outcome checks** (state/backend); check mechanisms only when the instruction states them; never contradict the instruction (a task that says "January 2025" with a rubric expecting March auto-fails every correct agent).

**Golden rule: after building verifiers, run them against your own recorded trajectory. If your own demonstration doesn't pass your rubric, no agent ever will — fix the task before saving.**

## Writing the Instruction

- Write it **in your own words**. The ✨ LLM suggestion is a non-copyable reference on purpose — phrasing diversity is part of dataset quality.
- Keep the **specific values** (names, amounts, dates, IDs) — those are the task parameters. Vary the phrasing, not the facts.
- If the task requires a specific UI mechanism, **say so in the instruction** ("using the slider"). Leaving an equivalent path open (a typable field next to the slider) then becomes a deliberate constraint-following test — that's good task design, not a bug.
- For judgment tasks ("like profiles matching Alex's interests"), don't let the rubric pin exact choices the instruction doesn't force. Either constrain the instruction until one answer is forced, or list acceptable alternatives.

## Tagging Workflow

1. **Record** your trajectory by performing the task in the iframe
2. **Stop recording** — you'll see the action timeline in the sidebar
3. Click **Tag Range** — select the first and last action of a macro
4. Click the macro chip to assign the range
5. Repeat for each macro
6. For QA macros (extract/compute), type the answer in the blue input field AND tag the range where the answer is visible

## Span Boundary Decision Tree

### Where does the span START?

```
Is there a button/link that initiates this macro's specific flow?
(e.g., "Checkout" button, "Compose" button, "New Post" button)
│
├─ YES → Start at that click (it's the entry action)
│
└─ NO → Start at the first interaction with the macro's UI element
         (first field click, first dropdown open, first slider touch)


What about scrolling to find the element?
├─ Scrolling to reveal the form/element → EXCLUDE (setup, not interaction)
└─ Scrolling AS the interaction (infinite scroll) → INCLUDE

What about clicking into a field before typing?
└─ INCLUDE — the click focuses the input, it's part of the interaction

What about navigation clicks between pages during the macro?
├─ Navigating to a page that IS the macro's form → INCLUDE
│   (clicking "Checkout" → checkout page → fill form → submit)
└─ Navigating to get to the area where the macro lives → EXCLUDE
    (clicking "Settings" in navbar to find the slider)
```

### Where does the span END?

```
Does the macro have a submit/apply/save/confirm action?
│
├─ YES → End at that click (include it)
│   ├─ Form submit button → include the click AND the submit event
│   ├─ "Apply Filters" button → include it
│   └─ "Save" / "Confirm" → include it
│
└─ NO (toggle, instant action) → End at the click itself
    (like/bookmark/follow — one click, span is 1-2 actions)


What about the page reload/redirect after submit?
└─ EXCLUDE — the reload is a consequence, not part of the macro

What about scrolling after submit to verify the result?
└─ EXCLUDE — verification is separate from the interaction

What about error → retry cycles?
├─ Tag only the SUCCESSFUL attempt
└─ If the error + correction is part of the natural flow
    (e.g., typing wrong date, correcting it) → INCLUDE both
```

### Special Cases

```
QA macros (extract/compute):
  Where does the answer become visible?
  ├─ Already on the page → span = the page state where answer is shown
  ├─ Need to sort/filter first → span covers the sort/filter actions
  └─ Need to navigate to detail page → span starts at the click that opens it

Multi-page macros (checkout flow across pages):
  └─ Span covers ALL pages of the flow, from first page to final submit

Toggle macros (save, follow, react):
  └─ Span is just the click (1 action) or click + confirmation (2 actions)

2FA / verify-payment steps:
  └─ INCLUDE in the span — entering the code is part of completing the
      payment/trade. (The Skip-2FA toolbar toggle removes these steps;
      leave it OFF when verification IS the task, e.g. verify_identity_by_code.)

Uploads (upload_by_upload etc.):
  └─ Use the fake file picker's canonical filenames (photo.jpg, letter.docx,
      notes.txt, data.csv, ...). Agents get real fixture files with exactly
      these names and contents — a made-up filename makes the task
      impossible for them.
```

### Overlapping Spans

Spans CAN overlap when:
- A reasoning macro (`extract_by_extremum`) encompasses the entire workflow including sub-macros (`filter_by_date_range`, `select_by_dropdown`)
- The extract/compute macro covers the same actions as the interaction that produces the data

## Macro Selection Decision Tree

```
What is the user trying to accomplish?
│
├─ Finding/reading information? → EXTRACT or COMPUTE
│   ├─ Just reading what's on the page? → extract_by_route
│   ├─ Need to search/filter first to find it? → the search/filter is a SEPARATE macro
│   ├─ Need to calculate/derive the answer? → compute_by_*
│   └─ Comparing two or more items? → compare_by_*
│
├─ Changing a setting/filter/view? → How?
│   ├─ Dropdown/select → filter_by_dropdown / sort_by_dropdown / select_by_dropdown
│   ├─ Slider/range input → filter_by_slider / configure_by_slider
│   ├─ Date picker → filter_by_date_range / select_by_date_range
│   ├─ Toggle/checkbox → filter_by_toggle / configure_by_toggle
│   └─ Typing a query → filter_by_query / search_by_query
│
├─ Creating something new? → create_by_form
│   (new post, new listing, new event, new account = register_by_form)
│
├─ Submitting/sending something? → What?
│   ├─ A message → message_from_free_text
│   ├─ A review/comment → post_from_free_text
│   ├─ An application/claim → submit_by_form / apply_by_form
│   └─ Contact form → submit_by_form
│
├─ Buying/paying/booking? → What?
│   ├─ Completing a purchase → checkout_by_form
│   ├─ Making a payment → pay_by_form
│   ├─ Reserving/booking → book_by_form
│   └─ Adding to cart (not buying yet) → add_by_button
│
├─ Editing existing data? → edit_by_form / edit_by_dropdown
│
├─ Deleting something? → delete_from_table
│
├─ Social action? → What?
│   ├─ Like/upvote → react_by_toggle
│   ├─ Save/bookmark → save_by_toggle
│   ├─ Follow/subscribe → follow_by_toggle / subscribe_by_toggle
│   ├─ Share → share_by_dropdown (menu) or share_by_toggle (button)
│   └─ Block/report → block_by_toggle / report_by_form
│
├─ Uploading a file? → upload_by_upload
│
├─ Playing media? → play_by_playback / play_by_dropdown
│
└─ Logging in? → authenticate_by_form
```

## Macro Categories & Priority

Priorities below are updated with **measured agent evidence** (Gemini Flash browser-agent eval, July 2026): the categories are human-difficulty labels, and human difficulty ≠ agent difficulty. Agents passed 84% of text_input tasks but 0% of table-macro tasks — so tables and multi-macro chains discriminate hardest.

### Tables (TOP priority — agents scored 0/8)

The failure is not clicking tables — it's **selecting the right row by a data property** ("the account with the oldest password", "the 3rd production instance"). Design more of these.

| Macro | Description | Span tip |
|-------|-------------|----------|
| `extract_from_table` | Read a value from the right row | Span where the row/value is visible + QA answer |
| `navigate_from_table` | Open a row's detail page | The row click (verify the URL actually changed) |
| `select_from_table` / `delete_from_table` | Act on the right row | Row selection → action → confirm |
| `compare_from_table` | Compare rows | Span covers reading both rows + QA answer |

### Spatial Control (high priority — agents pass ~56%)

| Macro | Description | Span tip |
|-------|-------------|----------|
| `filter_by_slider` | Adjust a range slider | Include ALL intermediate `change` events as slider moves |
| `filter_by_date_range` | Set date range inputs | Include date field clicks + typing + submit |
| `rate_by_slider` | Set a star/slider rating | Click/drag on rating control |
| `configure_by_slider` | Adjust a settings slider | Drag slider + save |
| `compute_by_slider` | Compute by adjusting inputs | Set slider values + read result |
| `select_by_date_range` | Pick dates for booking | Select check-in/check-out dates |

### Reasoning (high priority — requires understanding)

| Macro | Description | Span tip |
|-------|-------------|----------|
| `extract_by_route` | Extract info from a page | Span where answer is visible + use QA answer field |
| `extract_by_extremum` | Find min/max value | Span covers filter/sort that reveals answer + QA answer |
| `extract_by_ranking` | Extract item at a rank | Span covers sort action + QA answer |
| `compute_by_extremum` | Compute a min/max | Span covers relevant actions + QA answer |

### State Change (medium priority)

| Macro | Description | Span tip |
|-------|-------------|----------|
| `create_by_form` | Fill out a creation form | First field click → submit button |
| `submit_by_form` | Submit a filled form | First field → submit |
| `edit_by_form` | Edit existing data | Click edit → modify → save |
| `delete_from_table` | Delete an item | Click delete → confirm |
| `checkout_by_form` | Complete checkout | Entry button → payment fields → place order |
| `pay_by_form` | Make a payment | Amount + method → submit |

### Media (medium priority)

| Macro | Description | Span tip |
|-------|-------------|----------|
| `upload_by_upload` | Upload a file | Click file input → select from picker |
| `play_by_playback` | Use playback controls | Click play/pause/seek |
| `export_by_dropdown` | Export in a format | Select format → download |

### Text Input (lowest priority — agents pass ~84–100% of these)

Plain search/post/message tasks are saturated; only annotate them as parts of longer chains.

| Macro | Description | Span tip |
|-------|-------------|----------|
| `search_by_query` | Type a search query | Click search box → type → submit |
| `post_from_free_text` | Write and post | Click textarea → type → post |
| `message_from_free_text` | Send a message | Click input → type → send |

### Simple Select (lower priority)

| Macro | Description | Span tip |
|-------|-------------|----------|
| `filter_by_dropdown` | Select from dropdown | Open dropdown → select option → apply |
| `save_by_toggle` | Bookmark/save | Just the click (1-2 actions) |
| `follow_by_toggle` | Follow/unfollow | Just the click |
| `react_by_toggle` | Like/upvote | Just the click |

## Expected Outcome Guidelines

After tagging, write what should be verifiable in the "Expected Outcome" field:

**Good outcomes** (specific, checkable):
- "Admin API: GET /_admin/data/crm/activities should contain new row with contact_id=5425, type=call"
- "Filter applied: page shows only items under $50"
- "POST request to /login with status 200"

**Bad outcomes** (vague):
- "Task completed successfully"
- "The form was submitted"
- "User navigated correctly"

Include **admin API checks** for state-changing macros — this lets the judge verify the mutation actually happened in the database, not just that a button was clicked.

### Rules that keep outcomes verifiable at eval time

1. **Mechanism checks require instruction wording.** "Must be a drag action" is only valid if the instruction says "using the slider". Otherwise write the outcome ("max price filter = $150,000 is applied") and let any mechanism count.
2. **Never hardcode dynamic values.** Brokerage prices/gainers reshuffle every minute; cloud metrics and service health are time-simulated. Verify *properties* ("results sorted descending by change_pct at check time"), not literal tickers or numbers you saw while recording.
3. **Never hardcode generated IDs or counters.** New-record IDs (e.g. `i-user000000000016`) depend on what ran before. Verify by `record_exists` on the record's *content* (name, type, region) and match reported IDs by pattern (`i-user\d+`).
4. **Itemize multi-part tasks.** One line per required part — agents commonly complete n−1 of n, and itemized rubrics make the failure attributable.
5. **List alternatives** when more than one answer/wording is defensible; the judge honors them.

## When a Macro Can't Be Done

- **The site has no UI for it** → mark the macro **N/A** on its node. Two independent N/A reports retire the site↔macro mapping — this is real signal, use it.
- **The macro exists but this prompt combination doesn't work** → **Skip** with a reason in the details box.
- **The site is broken** (error page, missing data) → file site feedback from the review page so it lands in `data/reviews/`, then skip.
