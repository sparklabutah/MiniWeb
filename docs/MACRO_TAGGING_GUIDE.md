# Macro Tagging Guide

This guide is for human annotators tagging action trajectories with macro labels in the MiniWeb annotation interface.

## What is a Macro?

A macro is a **primitive UI skill** — a single atomic interaction pattern that an agent must perform. Examples: dragging a slider, filling a form, selecting from a dropdown. Each macro has a name like `filter_by_slider` (verb + modality).

## Tagging Workflow

1. **Record** your trajectory by performing the task in the iframe
2. **Stop recording** — you'll see the action timeline in the sidebar
3. Click **Tag Range** — select the first and last action of a macro
4. Click the macro chip to assign the range
5. Repeat for each macro
6. For QA macros (extract/compute), type the answer in the blue input field instead of tagging

## Tagging Rules

### What to tag

- Tag the **action range** where the macro's interaction happens
- Include the **submit/confirm** action at the end (click "Filter", "Submit", "Save")
- Include **intermediate steps** (typing into fields, selecting options, adjusting sliders)

### What NOT to tag

- **Navigation clicks** at the start (clicking nav links to get to the right page) — the agent starts on the target page
- **Scrolling** to find elements — unless scrolling IS the interaction (e.g., infinite scroll to load content)
- **Accidental clicks** or corrections — tag the successful attempt, not failed ones

### Overlapping spans

Spans CAN overlap when:
- A reasoning macro (`extract_by_extremum`) encompasses the entire workflow including sub-macros (`filter_by_date_range`, `select_by_dropdown`)
- The extract/compute macro covers the same actions as the interaction that produces the data

### QA macros (action range should contains the answer)

For these macros, use the **blue answer input** on the macro node:
- `extract_by_query` — "What is the total balance?"
- `extract_by_extremum` — "What is the cheapest flight?"
- `extract_by_ranking` — "What is the #1 trending video?"
- `compute_by_extremum` — "What is the min/max price?"
- `compare_from_table` — "Which has the better rating?"
- `verify_from_free_text` — "Is the author mentioned by name?"

Type the expected answer directly. The tagged action range should contain the expected answer. The macro is considered success if the agent answer correctly while staying in this action range.

## Macro Categories

### Spatial Control (highest priority — hardest for agents)

These involve precision interaction with spatial UI elements.

| Macro | Description | What to tag |
|-------|-------------|-------------|
| `filter_by_slider` | Adjust a range slider | Drag/input on the slider + click Apply/Filter |
| `filter_by_date_range` | Set date range inputs | Click date field + type/select dates + submit |
| `rate_by_slider` | Set a star/slider rating | Click/drag on rating control |
| `configure_by_slider` | Adjust a settings slider | Drag slider + save |
| `compute_by_slider` | Compute by adjusting inputs | Set slider values + read result |
| `select_by_date_range` | Pick dates for booking | Select check-in/check-out dates |
| `create_by_drag` | Create by dragging elements | Drag actions on canvas |
| `react_by_gesture` | Swipe/gesture interaction | Swipe or gesture actions |

**Tagging tip**: Include ALL the intermediate `change` events that happen while dragging a slider — these show the slider moving through values.

### Reasoning (high priority — requires understanding)

These require the agent to read, understand, and produce an answer.

| Macro | Description | What to tag |
|-------|-------------|-------------|
| `extract_by_route` | Extract info from a page | Use QA answer field |
| `extract_by_extremum` | Find min/max value | Tag the filter/sort actions that reveal the answer, use QA answer |
| `extract_by_ranking` | Extract item at a rank | Tag sort action, use QA answer |
| `compute_by_extremum` | Compute a min/max | Tag relevant actions, use QA answer |
| `compare_by_route` | Compare across pages | Tag navigation between items |

**Tagging tip**: For extract/compute macros, the span should cover the actions that make the answer visible (sorting, filtering). The actual answer goes in the QA answer field.

### State Change (medium priority — form interactions)

These create, modify, or delete data.

| Macro | Description | What to tag |
|-------|-------------|-------------|
| `create_by_form` | Fill out a creation form | First field click → submit button click |
| `submit_by_form` | Submit a filled form | First field → submit |
| `edit_by_form` | Edit existing data | Click edit → modify fields → save |
| `delete_from_table` | Delete an item | Click delete → confirm |
| `checkout_by_form` | Complete checkout | Payment fields → place order |
| `pay_by_form` | Make a payment | Amount + method → submit |
| `book_by_form` | Make a booking/reservation | Date/details → book |

**Tagging tip**: Start the span at the first field interaction, not at navigation. Include the final submit/save click.

### Media (medium priority)

| Macro | Description | What to tag |
|-------|-------------|-------------|
| `upload_by_upload` | Upload a file | Click file input → select file (from simulated picker) |
| `play_by_playback` | Use playback controls | Click play/pause/seek |
| `play_by_dropdown` | Play from a selection | Select track/episode → play |
| `export_by_dropdown` | Export in a format | Select format → download |

**Tagging tip**: For uploads, the file picker popup is part of the interaction — tag from the click on the file input through the file selection.

### Text Input (lower priority)

| Macro | Description | What to tag |
|-------|-------------|-------------|
| `search_by_query` | Type a search query | Click search box → type → submit/enter |
| `search_by_semantic` | Natural language search | Same as search_by_query |
| `post_from_free_text` | Write and post content | Click textarea → type → post |
| `message_from_free_text` | Send a message | Click input → type → send |
| `edit_by_query` | Edit by typing new values | Click field → type new value |

**Tagging tip**: Include the `type` and `keypress` events, not just the final `submit`. The typing IS the interaction.

### Simple Select (lower priority)

| Macro | Description | What to tag |
|-------|-------------|-------------|
| `filter_by_dropdown` | Select from dropdown | Click dropdown → select option → apply filter |
| `select_by_dropdown` | Choose an option | Click dropdown → select |
| `sort_by_dropdown` | Sort via dropdown | Click sort dropdown → select order |
| `save_by_toggle` | Bookmark/save toggle | Click star/bookmark button |
| `follow_by_toggle` | Follow/unfollow | Click follow button |
| `react_by_toggle` | Like/upvote | Click like/heart button |
| `subscribe_by_toggle` | Subscribe toggle | Click subscribe button |

**Tagging tip**: For toggles, the span is usually just 1-2 actions (click the button). For dropdowns, include the click to open + the option selection + any apply button.

### Trivial (minimal tagging — rarely sampled)

| Macro | Description | Notes |
|-------|-------------|-------|
| `navigate_by_route` | Click a nav link | **NOT sampled** — don't tag these |
| `authenticate_by_form` | Log in | Username + password + sign in |
| `register_by_form` | Create account | Fill registration form + submit |

## Common Mistakes

1. **Tagging navigation as a macro** — Don't. The agent starts on the target page.
2. **Forgetting the submit action** — Always include the final button click that triggers the form submission.
3. **Tagging too broadly** — A span of [1, 45] for a single `submit_by_form` is too wide. Tag only the form-filling actions.
4. **Not using QA answer fields** — For extract/compute macros, type the answer instead of faking scroll actions.
5. **Missing intermediate slider events** — Slider interactions generate multiple `change` events as the value moves. Include all of them.
6. **Tagging duplicate actions** — If you typed something wrong and retyped, tag only the correct attempt.

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
