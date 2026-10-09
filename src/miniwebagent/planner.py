"""The family descriptions the planner agent and the router use.

FAMILY_DEFS defines each visuomotor family for the planner agent (miniwebagent.planner_agent): its prompt lists them, and
its delegate action picks one. FAMILY_HINTS is the short form the oracle router's done-gating note quotes
(miniwebagent.evaluate.router_note). The screenshot planner and the subtask routers that also lived here were removed on
2026-10-06 (archived in MiniWeb-archive/cleanup-20261006/removed_legacy_routing.py).
"""
from __future__ import annotations

FAMILY_HINTS = {
    "Drag & gesture": "dragging, sliders, drawing or signing on a canvas, reordering by drag, panning/zooming a map, scrubbing media",
    "Discrete selection": "clicking choices: filters, dropdowns, sorting, date ranges, ratings, reactions, toggles (follow, save), deleting rows, playing media",
    "Text entry": "typing free text: search, messages, comments, spreadsheet cells, calculators, translation, code, typed signatures",
    "Form transaction": "filling and submitting a multi-field form: create, edit, book, pay, check out, sign in, share, cancel, configure, compare",
    "Navigation": "moving to a page: following menus or links, routes/directions, joining a meeting, carrying information to another site",
    "Out-of-page I/O": "moving data in or out of the page: upload, export/download, copy to clipboard, save a file, image editing, a code from another app",
    "Reasoning base": "reading the page to report an answer: find, count, compare or compute values",
}


# The family definitions (user, 2026-09-30: "a prompted planner ... explain and define each family in the prompt").
# Written once, before any WebArena run with them, and not tuned on WebArena.
FAMILY_DEFS = {
    "Navigation": "getting to the page where the work happens: opening a menu, tab, section or link, opening an item's "
                  "own page from a list, going back. The step is finished when that page is open.",
    "Text entry": "typing into one text field and submitting it: a search box, a message or comment, a cell, a calculator. "
                  "Searching for an item by name, number or keyword is Text entry.",
    "Discrete selection": "choosing among options already on the page: dropdowns, checkboxes, radio buttons, sort orders, "
                          "filter chips, date ranges, ratings, reactions, toggles (follow, save, like), deleting a row, "
                          "playing media.",
    "Form transaction": "filling in several fields of one form and submitting it to create or change something: posting, "
                        "creating, editing, booking, paying, checking out, signing in, sharing, configuring.",
    "Drag & gesture": "an action that needs the pointer dragged: a slider handle, drag-and-drop, reordering by drag, "
                      "drawing or signing, panning or zooming a map by drag. Only when the task needs a drag.",
    "Out-of-page I/O": "moving data into or out of the page: exporting or downloading a file, uploading a file, copying to "
                       "the clipboard, saving or printing.",
    "Reasoning base": "reading what is on the screen and answering: finding, counting, comparing or computing values and "
                      "reporting the result. It does not change anything on the site; it may scroll to read.",
}
