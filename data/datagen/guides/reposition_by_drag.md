# Guide: reposition_by_drag

Reposition an element on a board or canvas by dragging and dropping it to a new location.

## Preconditions

- The element to be moved is visible on the screen.
- The target destination or column is visible, or can be scrolled into view.

## Steps

1. Locate the element that needs to be moved.
2. Click and hold the left mouse button on the element.
3. Drag the element to the desired target position or column.
4. Release the mouse button to drop the element and commit the move.

## Watch for

- The element follows the cursor during the drag operation.
- Visual indicators (such as highlighted drop zones or shifting adjacent elements) showing where the element will land.

## Pitfalls

- Releasing the mouse button outside of a valid drop zone, which may cause the element to snap back to its original position.
- Accidentally clicking a text field or link within the element instead of grabbing the element itself.

## Variants

- **The target destination is off-screen** — Scroll the canvas or board to bring the destination into view before starting the drag, or drag the element toward the edge of the screen to trigger auto-scrolling.

## Done when

The element remains in its new position or column after the mouse button is released.

_Distilled by gemini-3.5-flash on 2026-09-27 from 1 human demonstrations on train sites only._
