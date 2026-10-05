# Guide: toggle_relationship

Toggle a relationship status (such as following, subscribing, saving, joining, pinning, or blocking) for a specific user, post, tag, or item.

## Preconditions

- The target item, post, user profile, or conversation is visible on the screen or has been navigated to.

## Steps

1. Locate the interactive element (button, icon, or link) associated with the relationship action (e.g., 'Follow', 'Save', 'Join', 'Subscribe', 'Star', 'Pin', 'Block').
2. Click the element to toggle the relationship state.
3. If a confirmation dialog or form submission is triggered, confirm or submit the action.

## Watch for

- The button text or icon changes to reflect the new state (e.g., 'Follow' becomes 'Following', 'Save' becomes 'Saved', or an icon fills/highlights).
- A temporary toast notification or confirmation message appears confirming the action.

## Pitfalls

- Clicking the toggle button twice, which reverts the relationship back to its original state.
- Clicking a toggle on the wrong item when multiple similar items are displayed on the page.

## Variants

- **the action is tag-specific or item-specific on a feed** — Click the specific toggle button directly on the feed card (e.g., 'Subscribe #tag' or 'Star').
- **the action requires navigating to a detail page first** — Click the item or user link to open their detail page, then locate and click the relationship toggle button (e.g., 'Save Post', 'Favorite', 'Join Group').

## Done when

The toggle control displays the requested final state (e.g., 'Following', 'Unsubscribe', 'Pinned', or a filled star/heart icon).

_Distilled by gemini-3.5-flash on 2026-09-27 from 24 human demonstrations on train sites only._
