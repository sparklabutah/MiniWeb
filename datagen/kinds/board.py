"""reposition_by_drag — move an element on a freeform board (a whiteboard's sticky note) into another
region (under another column heading) by dragging it.

A control is a board: a container of absolutely placed elements. Headings are its short bold
labels ("To Do", "In Progress", "Done"); they split the board into columns. Its arguments pair an
element with a column it is not in. The drop point is below everything already in that column.
The dry run drags it there with the mouse in a throw-away session and records the request that
saved the move; the check is that request with the position as a RANGE — anywhere inside the
target column, below its heading — so a person's slightly different drop still counts, and
`final` makes a later move out of the column fail.
"""
from __future__ import annotations

from datagen import browser as B
from datagen import checks
from datagen.kinds import register
from datagen.kinds.base import Kind


def columns(items):
    """Headings sorted left to right, each with its x span (to the next heading)."""
    heads = sorted([i for i in items if i["bold"] and 0 < len(i["text"]) <= 25 and "type-sticky" not in i["cls"]],
                   key=lambda i: i["x"])
    out = []
    for n, h in enumerate(heads):
        right = heads[n + 1]["x"] if n + 1 < len(heads) else h["x"] + max(260, h["w"] + 160)
        out.append({"text": h["text"], "left": h["x"] - 10, "right": right - 10, "top": h["y"] + h["h"]})
    return out


def column_of(item, cols):
    cx = item["x"] + item["w"] / 2
    return next((c for c in cols if c["left"] <= cx < c["right"] and item["y"] >= c["top"] - 5), None)


@register
class BoardKind(Kind):
    name = "board"
    macros = {"reposition_by_drag": "board"}
    needs_probe = False
    example = '''# example: drag the element by its middle to the drop point inside the target column
el = dom.one(css=task["item_css"], text=task["item_text"])
board = dom.one(css=task["board_css"])
act.drag(el, board, at_source=(0.5, 0.5), at_target=task["drop_at"])
expect.backend()'''

    def discover(self, scan, page, site):
        out = []
        for i, bd in enumerate(scan.get("boards") or []):
            cols = columns(bd["items"])
            movable = [it for it in bd["items"] if it["text"] and not (it["bold"] and len(it["text"]) <= 25
                                                                         and "type-sticky" not in it["cls"])]
            if len(cols) < 2 or not movable:
                continue
            ctrl = {"kind": "board", "role": "board", "css": bd["css"], "box": bd["box"], "items": bd["items"],
                    "label": scan.get("h1") or scan["title"], "name": "board", "id": "", "page": page,
                    "page_title": scan["title"], "site_id": site}
            out.append((("board", page, i), ctrl))              # each board has its own notes
        return out

    def arguments(self, ctrl):
        items, cols = ctrl["items"], columns(ctrl["items"])
        out = []
        for it in items:
            if not it["text"] or (it["bold"] and len(it["text"]) <= 25 and "type-sticky" not in it["cls"]):
                continue
            here = column_of(it, cols)
            for c in cols:
                if here and c["text"] == here["text"]:
                    continue
                inside = [o for o in items if o is not it and c["left"] <= o["x"] + o["w"] / 2 < c["right"] and o["y"] >= c["top"] - 5]
                y = max([c["top"]] + [o["y"] + o["h"] for o in inside]) + 20
                x = c["left"] + 10 + max(0, (c["right"] - c["left"] - it["w"]) / 2 - 10)
                if y + it["h"] > ctrl["box"][3] - 5:
                    continue
                out.append({"index": len(out), "value": f"{it['text']}->{c['text']}", "text": it["text"],
                            "item_css": it["css"], "column": c["text"], "col": c, "drop": [round(x), round(y)],
                            "size": [it["w"], it["h"]], "from": [it["x"], it["y"]]})
        return out[:30]

    def element_key(self, ctrl):
        return f"BOARD {ctrl['page']}"

    def view(self, ctrl):
        v = super().view(ctrl)
        v.pop("options", None)
        v.update({k: ctrl.get(k) for k in ("box", "site_id")})
        return v

    def check(self, ctrl, arg, keep=None):
        return {"kind": "request", "pending": True}

    def dry_run(self, t, base, b):
        c, o = t["control"], t["option"]
        ctx = B.new_context(b)
        page = ctx.new_page()
        try:
            B.goto_start(page, base + t["start"]["url"])
            el = page.locator(o["item_css"]).filter(has_text=o["text"]).first
            el.scroll_into_view_if_needed(timeout=5000)
            eb, bb = el.bounding_box(), page.locator(c["css"]).first.bounding_box()
            n0 = len(B.session_log(ctx, base))
            sx, sy = eb["x"] + eb["width"] / 2, eb["y"] + eb["height"] / 2
            tx, ty = sx + (o["drop"][0] - o["from"][0]), sy + (o["drop"][1] - o["from"][1])
            page.mouse.move(sx, sy)
            page.mouse.down()
            for k in range(1, 16):
                page.mouse.move(sx + (tx - sx) * k / 15, sy + (ty - sy) * k / 15)
            page.mouse.up()
            page.wait_for_timeout(600)
            B.settle(page)
            puts = [e for e in B.session_log(ctx, base)[n0:] if (e.get("method") or "").upper() in ("PUT", "POST", "PATCH")
                    and isinstance(e.get("body"), dict) and {"x", "y"} <= set(e["body"])]
            if not puts:
                return False, "dragging the element saved no position"
            e = puts[-1]
            col = o["col"]
            chk = {"kind": "request", "method": e["method"].upper(), "path": e["path"], "keep": {}, "final": True,
                   "params": {"x": {"value": [max(0, round(col["left"])), round(col["right"] - o["size"][0] / 2)], "mode": "between"},
                              "y": {"value": [round(col["top"]), round(c["box"][3])], "mode": "between"}}}
            ok, detail = checks.evaluate(chk, B.session_log(ctx, base))
            if not ok:
                return False, "the privileged drop is not inside the column: " + detail
            t["check"] = chk
            o["drop_at"] = [round((tx - bb["x"]) / bb["width"], 4), round((ty - bb["y"]) / bb["height"], 4)]
            return True, f"{o['text']!r} -> {o['column']!r}: {detail}"
        finally:
            ctx.close()

    def describe(self, ctrl):
        return {"type": "a board of sticky notes under column headings (drag to move)", "label": ctrl.get("label") or "",
                "note": "ask to move the named note to the named column"}

    def say(self, ctrl, arg):
        return {"move": arg["text"], "to column": arg["column"], "board": ctrl.get("label")}

    def mentions(self, arg):
        return [" ".join(arg["text"].split()[:6]), arg["column"]]

    def step_spec(self, step):
        c, o = step["control"], step["option"]
        return [f"DRAG: the element {o['text']!r} (css={o['item_css']!r}) by its middle",
                f"DROP: on the board (css={c['css']!r}) at box fraction {tuple(o['drop_at'])} — under {o['column']!r}"]

    def script_task(self, step):
        c, o = step["control"], step["option"]
        return {"subtask": step["subtask"], "item_css": o["item_css"], "item_text": o["text"], "board_css": c["css"],
                "drop_at": o["drop_at"], "column": o["column"]}

    def locate(self, driver, step):
        return driver.query(css=step["option"]["item_css"], limit=1)


def _sm():
    from datagen import sitemap
    return sitemap
