"""Pointer gestures: reorder a list by dragging (edit_by_ranking, reposition_by_drag) and
draw on a canvas (sign_by_freeformdrawing). Checks are recorded by the dry run (the order or
drawing the site stores); a drawing's pixels differ per run, so only what both dry runs agree
on (e.g. "signed", the document it belongs to) is kept."""
from __future__ import annotations

import math
import random
import re

from datagen import browser as B
from datagen.kinds import register
from datagen.kinds.base import Kind


def _sm():
    from datagen import sitemap
    return sitemap


def _muts(ctx, base, log_before):
    new = B.session_log(ctx, base)[log_before:]
    muts = [e for e in new if (e.get("method") or "GET").upper() != "GET" and isinstance(e.get("status"), int)
            and 200 <= e["status"] < 400]
    return (muts[-1] if muts else None), new


@register
class DragOrderKind(Kind):
    name = "dragorder"
    macros = {"edit_by_ranking": "rank", "reposition_by_drag": "reposition"}
    oracle = True
    example = '''# example: drag one list item onto another's position, then save the order if asked
src = dom.one(css=task["source_css"])
if not src.in_viewport:
    src = act.scroll_into_view(src)
dst = dom.one(css=task["target_css"])
act.drag(src, dst)
if task["save_css"]:
    btn = dom.one(css=task["save_css"])
    if not btn.in_viewport:
        btn = act.scroll_into_view(btn)
    act.click(btn)
expect.backend()'''

    def discover(self, scan, page, site):
        from annotation.macro_locations import MACRO_LOCATIONS
        listed = MACRO_LOCATIONS.get(site) or {}
        role = "rank" if "edit_by_ranking" in listed or "reposition_by_drag" not in listed else "reposition"
        out = []
        for lst in scan.get("dragLists") or []:
            items = [it for it in lst["items"] if it["text"]]
            if len(items) < 3:
                continue
            ctrl = {"kind": "dragorder", "role": role, "css": lst["css"], "name": lst["css"], "id": "",
                    "label": scan.get("h1") or scan["title"], "items": items, "save": lst.get("save"),
                    "page": page, "page_title": scan["title"]}
            out.append((("dragorder", lst["css"], page), ctrl))
        return out

    def arguments(self, ctrl):
        items, out = ctrl["items"], []
        for i in range(len(items)):
            for j in (0, len(items) - 1, i + 2, i - 2):
                if 0 <= j < len(items) and j != i and len(out) < 16:
                    where = "to the top" if j == 0 else ("to the bottom" if j == len(items) - 1 else
                                                          f"{'below' if j > i else 'above'} '{items[j]['text']}'")
                    out.append({"index": len(out), "value": f"{i}->{j}", "src": i, "dst": j,
                                "text": f"move '{items[i]['text']}' {where}", "item": items[i]["text"],
                                "anchor": items[j]["text"]})
        return out

    def probe_argument(self, ctrl):
        args = self.arguments(ctrl)
        return args[0] if args else None

    def element_key(self, ctrl):
        return f"DRAG {ctrl['page']} {ctrl['css']}"

    def view(self, ctrl):
        v = super().view(ctrl)
        v.update({k: ctrl.get(k) for k in ("items", "save")})
        v.pop("options", None)
        return v

    def apply(self, page, ctrl, arg, base, ctx, log_before):
        page.drag_and_drop(ctrl["items"][arg["src"]]["css"], ctrl["items"][arg["dst"]]["css"], timeout=5000)
        B.settle(page)
        if ctrl.get("save"):
            page.locator(ctrl["save"]["css"]).first.click(timeout=5000)
            B.settle(page)
        e, new = _muts(ctx, base, log_before)
        return (e, None, "drag", new) if e else (None, None, None, new)

    def check(self, ctrl, arg, keep=None):
        return {"kind": "state", "pending": True}

    def request_check(self, entry):
        body = entry.get("body") if isinstance(entry.get("body"), dict) else {}
        return {"kind": "request", "method": entry["method"].upper(), "path": entry["path"],
                "params": {k: v for k, v in body.items() if isinstance(v, (str, int, float, list))}, "keep": {}, "final": True}

    def describe(self, ctrl):
        return {"type": "a list you reorder by dragging items", "label": ctrl.get("label") or "",
                "choices": [it["text"] for it in ctrl["items"]][:12]}

    def mentions(self, arg):
        return [" ".join(arg["item"].split()[:6])]

    def step_spec(self, step):
        c, o = step["control"], step["option"]
        return [f"DRAG: the item {o['item']!r} (css={c['items'][o['src']]['css']!r}) onto the position of "
                f"{o['anchor']!r} (css={c['items'][o['dst']]['css']!r}) — {o['text']}",
                f"SAVE: click css={c['save']['css']!r}" if c.get("save") else "SAVE: the new order is kept on drop"]

    def script_task(self, step):
        c, o = step["control"], step["option"]
        return {"subtask": step["subtask"], "source_css": c["items"][o["src"]]["css"],
                "target_css": c["items"][o["dst"]]["css"], "save_css": (c.get("save") or {}).get("css")}

    def locate(self, driver, step):
        return driver.query(css=step["control"]["items"][step["option"]["src"]]["css"], limit=1)


def signature_strokes(seed, n=None):
    """A handwritten-looking signature: 2–4 strokes of loops and waves, as box fractions."""
    rng = random.Random(seed)
    strokes = []
    x0 = rng.uniform(0.08, 0.15)
    for _s in range(n or rng.randint(2, 4)):
        pts, width = [], rng.uniform(0.15, 0.3)
        amp, freq, base = rng.uniform(0.08, 0.2), rng.uniform(1.5, 3.5), rng.uniform(0.4, 0.6)
        for k in range(rng.randint(14, 26)):
            t = k / 20
            pts.append((round(min(0.95, x0 + t * width), 3),
                        round(min(0.92, max(0.08, base + amp * math.sin(t * freq * math.pi) + rng.gauss(0, 0.01))), 3)))
        strokes.append(pts)
        x0 = min(0.8, pts[-1][0] + rng.uniform(0.02, 0.06))
    return strokes


SHAPES = ("a circle", "a star", "an arrow pointing right", "a check mark", "a box", "a wavy underline", "a triangle",
          "a smiley face")
SIGN_CONTEXT = re.compile(r"\b(sign|signature|signed|consent|initials|adopt)", re.I)


def shape_strokes(shape, seed):
    """Strokes (box fractions) for a simple sketch, placed and sized at random."""
    rng = random.Random(seed)
    cx, cy, r = rng.uniform(0.3, 0.7), rng.uniform(0.35, 0.65), rng.uniform(0.12, 0.22)
    circle = lambda cx, cy, r, n=24, a0=0.0, a1=2 * math.pi: [
        (round(cx + r * math.cos(a0 + (a1 - a0) * k / n), 3), round(cy + r * math.sin(a0 + (a1 - a0) * k / n), 3)) for k in range(n + 1)]
    poly = lambda pts: [(round(x, 3), round(y, 3)) for x, y in pts]
    if shape == "a circle":
        return [circle(cx, cy, r)]
    if shape == "a star":
        pts = [(cx + r * math.cos(-math.pi / 2 + k * 4 * math.pi / 5), cy + r * math.sin(-math.pi / 2 + k * 4 * math.pi / 5)) for k in range(6)]
        return [poly(pts)]
    if shape == "an arrow pointing right":
        return [poly([(cx - r, cy), (cx + r, cy)]), poly([(cx + r * 0.6, cy - r * 0.4), (cx + r, cy), (cx + r * 0.6, cy + r * 0.4)])]
    if shape == "a check mark":
        return [poly([(cx - r, cy), (cx - r * 0.3, cy + r * 0.7), (cx + r, cy - r * 0.8)])]
    if shape == "a box":
        return [poly([(cx - r, cy - r), (cx + r, cy - r), (cx + r, cy + r), (cx - r, cy + r), (cx - r, cy - r)])]
    if shape == "a wavy underline":
        return [[(round(cx - r * 1.5 + 3 * r * k / 20, 3), round(cy + 0.04 * math.sin(k * math.pi / 3), 3)) for k in range(21)]]
    if shape == "a triangle":
        return [poly([(cx, cy - r), (cx + r, cy + r), (cx - r, cy + r), (cx, cy - r)])]
    face = circle(cx, cy, r)
    return [face, circle(cx - r * 0.35, cy - r * 0.3, r * 0.08, 8), circle(cx + r * 0.35, cy - r * 0.3, r * 0.08, 8),
            circle(cx, cy + r * 0.05, r * 0.5, 12, 0.2 * math.pi, 0.8 * math.pi)]


@register
class CanvasKind(Kind):
    name = "canvas"
    # signature pads sign a document; any other drawing canvas edits the image it holds
    macros = {"sign_by_freeformdrawing": "draw", "edit_by_image": "sketch"}
    oracle = True
    example = '''# example: draw a signature on the canvas, then press the button that keeps it
pad = dom.one(css=task["canvas_css"])
if not pad.in_viewport:
    pad = act.scroll_into_view(pad)
act.draw(pad, task["strokes"])
btn = dom.one(css=task["save_css"], text=task["save_text"])
if not btn.in_viewport:
    btn = act.scroll_into_view(btn)
act.click(btn)
expect.backend()'''

    def discover(self, scan, page, site):
        out = []
        for c in scan.get("canvases") or []:
            if not c.get("save"):
                continue
            blob = " ".join([page, scan.get("h1") or "", scan["title"], c["save"].get("text") or "", c["css"]])
            role = "draw" if SIGN_CONTEXT.search(blob) else "sketch"
            out.append((("canvas", c["css"], page),
                        {"kind": "canvas", "role": role, "css": c["css"], "name": c["css"], "id": "", "save": c["save"],
                         "label": scan.get("h1") or scan["title"], "item": scan.get("h1") or scan["title"], "page": page,
                         "page_title": scan["title"]}))
        return out

    def arguments(self, ctrl):
        if ctrl.get("role") == "sketch":                  # each shape at three places / sizes
            return [{"index": 3 * k + v, "value": f"shape{k}.{v}", "text": s, "strokes": shape_strokes(s, f"{ctrl['page']}:{k}:{v}"),
                     "item": ctrl.get("item")} for k, s in enumerate(SHAPES) for v in range(3)]
        return [{"index": k, "value": f"sig{k}", "text": "a handwritten signature", "strokes": signature_strokes(f"{ctrl['page']}:{k}"),
                 "item": ctrl.get("item")} for k in range(20)]

    def probe_argument(self, ctrl):
        return self.arguments(ctrl)[0]

    def element_key(self, ctrl):
        return f"CANVAS {ctrl['page']}"

    def view(self, ctrl):
        v = super().view(ctrl)
        v.update({k: ctrl.get(k) for k in ("save", "item")})
        v.pop("options", None)
        return v

    def apply(self, page, ctrl, arg, base, ctx, log_before):
        box = page.locator(ctrl["css"]).first.bounding_box()
        for st in arg["strokes"]:
            page.mouse.move(box["x"] + st[0][0] * box["width"], box["y"] + st[0][1] * box["height"])
            page.mouse.down()
            for fx, fy in st[1:]:
                page.mouse.move(box["x"] + fx * box["width"], box["y"] + fy * box["height"], steps=2)
            page.mouse.up()
        save = page.locator(ctrl["save"]["css"])
        if ctrl["save"].get("text"):
            save = save.filter(has_text=ctrl["save"]["text"])
        save.first.click(timeout=5000)
        B.settle(page)
        e, new = _muts(ctx, base, log_before)
        return (e, None, "draw", new) if e else (None, None, None, new)

    def check(self, ctrl, arg, keep=None):
        return {"kind": "state", "pending": True}

    def request_check(self, entry):
        return {"kind": "request", "method": entry["method"].upper(), "path": entry["path"], "params": {}, "keep": {},
                "final": False}

    def describe(self, ctrl):
        if ctrl.get("role") == "sketch":
            return {"type": "a drawing canvas (draw with the mouse), kept with its save button", "label": ctrl.get("label") or "",
                    "choices": [], "note": "ask to draw the given shape on the named note/board and save it"}
        return {"type": "a signature pad (draw with the mouse)", "label": ctrl.get("label") or "", "choices": [],
                "note": "ask to sign the named document by drawing a signature"}

    def say(self, ctrl, arg):
        if ctrl.get("role") == "sketch":
            return {"draw": arg["text"], "on": arg.get("item")}
        return {"sign": arg.get("item")}

    def mentions(self, arg):
        words = arg["text"].split()
        return [words[1]] if str(arg.get("value", "")).startswith("shape") and len(words) > 1 else []

    def step_spec(self, step):
        c = step["control"]
        what = step["option"]["text"] if c.get("role") == "sketch" else "a signature"
        return [f"DRAW: {what} on the canvas css={c['css']!r} with act.draw(el, task['strokes'])",
                f"KEEP IT: click css={c['save']['css']!r} text={c['save'].get('text')!r}"]

    def script_task(self, step):
        c, o = step["control"], step["option"]
        return {"subtask": step["subtask"], "canvas_css": c["css"], "strokes": o["strokes"], "save_css": c["save"]["css"],
                "save_text": c["save"].get("text") or None}

    def locate(self, driver, step):
        return driver.query(css=step["control"]["css"], limit=1)
