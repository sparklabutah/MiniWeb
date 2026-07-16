"""The canonical action vocabulary — the single source of truth for action types.

Every recorded action, human or agent, is emitted by `postAction(...)` in
app/static/recorder.js. Because browser_use drives Chrome over CDP, the agent's
clicks/typing fire the same DOM listeners, so agent and human trajectories share
this exact vocabulary. `tab_switch` is the one exception: it comes from
browser_use's multi-tab handling, not a DOM event.

This module is the authority for:
  * which action strings exist (the `select` dropdown in the template builder),
  * which ones a verifier template may fix its `action` on (ASSERTABLE),
  * the per-action semantics a template author needs to get it right.

Selectors are deliberately NOT part of this model. Recorded selectors are
ambiguous (a click may log the <div> or the <a> inside it), so interaction
checks match on action + target + value only. See evaluation/verifiers.py.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# The vocabulary. Order is the order the picker should show.
#   emitted_by : "recorder" (a postAction call) | "agent" (browser_use only)
#   value      : "always" | "sometimes" | "none"  — is a value/text carried?
#   signal     : "high" | "medium" | "low" | "noise" — how much a check can trust it
#   assertable : may a template fix its `action` on this? (excludes noise/nav/plumbing)
#   fires_on   : the DOM gesture, for the author
#   note       : the gotcha, if any
# ---------------------------------------------------------------------------

ACTIONS = {
    "type": {
        "emitted_by": "recorder", "value": "always", "signal": "high",
        "assertable": True,
        "fires_on": "text entered in <input>/<textarea> (buffered, flushed on next click/submit/nav)",
        "extra": ("text",),
        "note": "Carries the typed text in `text`. One `type` per field, not per keystroke.",
    },
    "select": {
        "emitted_by": "recorder", "value": "always", "signal": "high",
        "assertable": True,
        "fires_on": "<select> option chosen (change event, relabelled)",
        "extra": ("value", "option_text"),
        "note": "A dropdown ALSO fires `click`; assert `select` and ignore the incidental click.",
    },
    "change": {
        "emitted_by": "recorder", "value": "always", "signal": "high",
        "assertable": True,
        "fires_on": "<input type=range|date|number> committed",
        "extra": ("value",),
        "note": "Sliders/date/number only. Text inputs emit `type`, not `change`.",
    },
    "check": {
        "emitted_by": "recorder", "value": "none", "signal": "medium",
        "assertable": True,
        "fires_on": "checkbox / radio toggled",
        "extra": ("checked",),
        "note": "State is in `checked` (bool), not `value`. Also fires `click`; assert `check`.",
    },
    "submit": {
        "emitted_by": "recorder", "value": "none", "signal": "high",
        "assertable": True,
        "fires_on": "form submission",
        "extra": ("url", "method", "formData"),
        "note": "Carries the payload in `formData` — a client-side source for Mutate field "
                "checks, independent of (and OR-able with) the network request body.",
    },
    "drag": {
        "emitted_by": "recorder", "value": "none", "signal": "low",
        "assertable": True,
        "fires_on": "drag gesture (reordering, div-drawn sliders)",
        "extra": ("from_x", "from_y", "to_x", "to_y"),
        "note": "Coordinates only, no semantic value. Target does all the work.",
    },
    "keypress": {
        "emitted_by": "recorder", "value": "none", "signal": "low",
        "assertable": True,
        "fires_on": "Enter / Escape / Tab keydown only",
        "extra": ("key",),
        "note": "Not general typing (that's `type`). Usually Enter to submit a search.",
    },
    "click": {
        "emitted_by": "recorder", "value": "sometimes", "signal": "low",
        "assertable": True,
        "fires_on": "generic activation — links, buttons, toggles",
        "extra": ("href", "value", "option_text", "x", "y", "button"),
        "note": "Overloaded and the most common action. No selector, so a click check "
                "leans entirely on `target`. Use only when nothing higher-signal fits.",
    },
    "scroll": {
        "emitted_by": "recorder", "value": "none", "signal": "noise",
        "assertable": False,
        "fires_on": "page/element scroll (debounced)",
        "extra": ("scroll_top",),
        "note": "Incidental. Never a verification target.",
    },
    "navigate": {
        "emitted_by": "recorder", "value": "none", "signal": "noise",
        "assertable": False,
        "fires_on": "URL change (pathname/search)",
        "extra": ("url", "from_url"),
        "note": "Not sampled as a macro (navigate_by_route). Use page_visited for URL checks.",
    },
    "tab_switch": {
        "emitted_by": "agent", "value": "none", "signal": "noise",
        "assertable": False,
        "fires_on": "agent switching browser tabs (browser_use, not a DOM event)",
        "extra": (),
        "note": "Agent plumbing. Present in agent runs only; not a task requirement.",
    },
}

# The picker list (all of them), and the subset a template may fix `action` on.
ALL_ACTIONS = list(ACTIONS.keys())
ASSERTABLE_ACTIONS = [a for a, m in ACTIONS.items() if m["assertable"]]

# High/medium-signal interactions — the ones an author should reach for first.
PRIMARY_ACTIONS = [a for a, m in ACTIONS.items()
                   if m["assertable"] and m["signal"] in ("high", "medium")]


def is_assertable(action: str) -> bool:
    """True if a verifier template may fix its `action` on this type."""
    return ACTIONS.get(action, {}).get("assertable", False)


def signal(action: str) -> str:
    """'high' | 'medium' | 'low' | 'noise' | '' (unknown)."""
    return ACTIONS.get(action, {}).get("signal", "")


if __name__ == "__main__":
    # `python -m evaluation.action_vocabulary` — print the table.
    print(f"{'action':12}{'by':10}{'value':11}{'signal':8}{'assert':8}fires_on")
    for a, m in ACTIONS.items():
        print(f"{a:12}{m['emitted_by']:10}{m['value']:11}{m['signal']:8}"
              f"{'yes' if m['assertable'] else 'no':8}{m['fires_on']}")
    print(f"\nassertable: {ASSERTABLE_ACTIONS}")
    print(f"primary:    {PRIMARY_ACTIONS}")
