"""Spreadsheet-style grids: change one cell (edit_by_cell). The argument is a cell and a new
value (numbers stay numbers, text cells get another short entry); the check is recorded by the
dry run (the stored cell change)."""
from __future__ import annotations

import random
import re

from datagen import browser as B
from datagen.kinds import register
from datagen.kinds.base import Kind

WORDS = ["Pending", "Approved", "Review", "Done", "Draft", "North", "South", "Q3", "Q4", "Blocked", "High", "Low"]


def _row_of(c):
    box = c.get("box") or [0, 0, 0, 0]
    return round((box[1] + box[3] / 2) / 12)          # cells of one visual row share their vertical centre


def _col_of(c):
    box = c.get("box") or [0, 0, 0, 0]
    return round((box[0] + box[2] / 2) / 12)


def _label_rows(cells):
    """Cells whose scan found no row header get their row's name: the leftmost cell of the same visual row with
    some words in it (a contact's name, an item's title). A row still unnamed stays "" (arguments skip it)."""
    rows = {}
    for c in cells:
        rows.setdefault(_row_of(c), []).append(c)
    good = lambda t: len(re.findall(r"[A-Za-z]", t or "")) >= 3
    out = []
    for c in cells:
        if not c["row"]:
            named = sorted((x for x in rows[_row_of(c)] if good(x["text"])), key=lambda x: (x.get("box") or [0])[0])
            c = dict(c, row=named[0]["text"].strip()[:60] if named else "")
        out.append(c)
    return out


@register
class GridCellKind(Kind):
    name = "gridcell"
    macros = {"edit_by_cell": "cell"}
    oracle = True
    example = '''# example: replace one cell's value and commit it with Enter
cell = dom.one(css=task["cell_css"])
if not cell.in_viewport:
    cell = act.scroll_into_view(cell)
act.double_click(cell) if task["double_click"] else act.click(cell)
act.press("Control+a")
act.type(task["value"])
act.press("Enter")
expect.backend()'''

    def discover(self, scan, page, site):
        cells = _label_rows([c for c in scan.get("cells") or [] if c["row"] or c["col"]])
        if len(cells) < 4:
            return []
        return [(("gridcell", page), {"kind": "gridcell", "role": "cell", "css": cells[0]["css"], "name": "grid", "id": "",
                                     "label": scan.get("h1") or scan["title"], "cells": cells[:60], "page": page,
                                     "page_title": scan["title"]})]

    def arguments(self, ctrl):
        rng, out = random.Random(ctrl["page"]), []
        for n, c in enumerate(_label_rows(ctrl["cells"])):     # site maps crawled before the row names
            cur = c["text"].replace(",", "")
            if re.fullmatch(r"-?\d+(\.\d+)?", cur):
                v = str(round(float(cur) * rng.uniform(0.5, 1.5) + rng.randint(1, 9), 2 if "." in cur else None))
                v = v[:-2] if v.endswith(".0") else v
            elif cur and len(cur) < 30:
                v = rng.choice([w for w in WORDS if w.lower() != cur.lower()])
            else:
                continue
            if not c["row"] and len({_row_of(x) for x in ctrl["cells"]}) > 1:
                continue            # no name for its row: the task could only say "row one" (2026-09-29)
            if not c["col"] and len({_col_of(x) for x in ctrl["cells"]}) > 1:
                continue            # no header for its column: "set 3 to Low"
            where = " / ".join(x for x in (c["row"], c["col"]) if x)
            out.append({"index": len(out), "value": f"{n}={v}", "cell": n, "new": v, "text": f"set {where} to {v}",
                        "where": where, "row": c["row"], "col": c["col"]})
        return out[:20]

    def probe_argument(self, ctrl):
        args = self.arguments(ctrl)
        return args[0] if args else None

    def element_key(self, ctrl):
        return f"GRID {ctrl['page']}"

    def view(self, ctrl):
        v = super().view(ctrl)
        v["cells"] = _label_rows(ctrl.get("cells") or [])
        v.pop("options", None)
        return v

    def apply(self, page, ctrl, arg, base, ctx, log_before):
        c = ctrl["cells"][arg["cell"]]
        loc = page.locator(c["css"]).first
        (loc.fill(arg["new"], timeout=5000) if c.get("input") else (loc.dblclick(timeout=5000), page.keyboard.press("Control+a"),
                                                                     page.keyboard.type(arg["new"])))
        page.keyboard.press("Enter")
        B.settle(page)
        new = B.session_log(ctx, base)[log_before:]
        muts = [e for e in new if (e.get("method") or "GET").upper() != "GET" and isinstance(e.get("status"), int)
                and 200 <= e["status"] < 400]
        return (muts[-1], None, "edit", new) if muts else (None, None, None, new)

    def check(self, ctrl, arg, keep=None):
        return {"kind": "state", "pending": True}

    def request_check(self, entry):
        body = entry.get("body") if isinstance(entry.get("body"), dict) else {}
        return {"kind": "request", "method": entry["method"].upper(), "path": entry["path"],
                "params": {k: v for k, v in body.items() if isinstance(v, (str, int, float))}, "keep": {}, "final": True}

    def describe(self, ctrl):
        return {"type": "a spreadsheet grid", "label": ctrl.get("label") or "", "choices": [],
                "note": "name the cell by its row and column labels and give the new value"}

    def mentions(self, arg):
        return [x for x in (arg["row"], arg["col"], arg["new"]) if x][:3]

    def step_spec(self, step):
        c, o = step["control"], step["option"]
        cell = c["cells"][o["cell"]]
        return [f"CELL: row {cell['row']!r}, column {cell['col']!r} (css={cell['css']!r}, now {cell['text']!r})",
                f"NEW VALUE: {o['new']!r} — select the cell's content, type the value, press Enter"]

    def script_task(self, step):
        c, o = step["control"], step["option"]
        cell = c["cells"][o["cell"]]
        return {"subtask": step["subtask"], "cell_css": cell["css"], "value": o["new"], "double_click": not cell.get("input")}

    def locate(self, driver, step):
        return driver.query(css=step["control"]["cells"][step["option"]["cell"]]["css"], limit=1)
