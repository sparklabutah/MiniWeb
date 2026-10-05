# Guide: count_entries

Count and return the total number of matching entries displayed in a list, table, or grid on the page.

## Preconditions

- A webpage containing a list, table, or grid of entries is fully loaded on the screen.

## Steps

1. Scan the page to locate the main container holding the list, table, or grid of entries.
2. If a specific condition or filter is required, locate and apply the corresponding filter controls (e.g., dropdowns, text search, checkboxes) and wait for the list to update.
3. Look near the top or bottom of the list for a status label or summary text indicating the total count (e.g., 'Showing 1-10 of 150', 'Total: 42 items').
4. If a summary text is present and accurate to the condition, record this number as the final count.
5. If no summary text is available, manually count the visible entries matching the criteria from top to bottom.
6. If the entries span multiple pages and no global total is displayed, navigate through each page using the pagination controls, counting the entries on each page to calculate the cumulative total.

## Watch for

- A loading spinner or dimmed list indicating that filters are being applied or new pages are loading.
- The summary text updating its numbers after a filter is applied.

## Pitfalls

- Counting table header rows, empty placeholder rows, or footer elements as actual entries.
- Only counting the visible entries on the first page when additional pages of entries exist.
- Counting duplicate entries if the list fails to refresh properly after applying a filter.

## Variants

- **A 'Select All' checkbox is available at the top of the list** — Click the 'Select All' checkbox and look for a temporary banner or tooltip that displays the total number of selected items (e.g., 'All 125 items selected'), then deselect them.
- **The page uses infinite scroll instead of pagination** — Scroll down to the bottom of the container repeatedly until no more new items load, then count the total visible entries.

## Done when

The final count of matching entries has been identified and recorded.

_Written by gemini-3.5-flash on 2026-09-27 from the macro registry (no human demonstration on a train site)._
