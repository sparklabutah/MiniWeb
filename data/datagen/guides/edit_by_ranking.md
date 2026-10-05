# Guide: edit_by_ranking

Reorder a list of items to match a target ranking and commit the new order.

## Preconditions

- A list of reorderable items is visible on the screen.
- Ranking controls (such as drag handles, up/down arrows, numeric inputs, or action menus) are present next to or on the items.

## Steps

1. Identify the target order for the items in the list.
2. Locate the first item that needs to be moved.
3. Use the item's ranking control to move it to its correct position relative to the other items.
4. Repeat the movement process for any remaining out-of-order items until the entire list matches the target order.
5. Locate and click the save, apply, or commit button if the list does not automatically save the new order.

## Watch for

- The item visually shifting to its new position in the list.
- Other items dynamically adjusting their positions to accommodate the moved item.
- A 'Save' or 'Apply' button becoming active or highlighted after a change is made.

## Pitfalls

- Forgetting to click the 'Save' or 'Apply' button after reordering, causing the changes to be lost.
- Accidentally dropping an item into the wrong slot during drag-and-drop, which can cascade and disrupt the order of other items.
- Moving items too quickly before the interface has finished updating from the previous move, leading to lag or incorrect placement.

## Variants

- **the UI uses drag-and-drop handles** — Click and hold the drag handle (often represented by a grid, dots, or hamburger icon), drag the item vertically to the target position, and release the mouse button.
- **the UI uses up/down arrow buttons** — Click the 'Up' or 'Down' arrow buttons next to the item repeatedly until the item reaches the desired position.
- **the UI uses numeric rank inputs** — Click into the rank input field next to the item, type the target position number, and press Enter or click outside the field to apply.
- **the UI uses an action or context menu** — Click the options menu (often three dots) on the item, select the move option (e.g., 'Move Up', 'Move Down', or 'Move to Position'), and specify the destination.

## Done when

The list displays the items in the exact requested order, and any save or commit buttons are successfully clicked, disabled, or replaced by a success confirmation.

_Written by gemini-3.5-flash on 2026-09-27 from the macro registry (no human demonstration on a train site)._
