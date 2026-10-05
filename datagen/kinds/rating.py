"""Star ratings (feedback_by_star): a 1–5 rating control — a range slider or a radio/button
row — inside a rating form on an item's page. The argument is the rating; the check is the
data change the submitted rating makes (recorded by the dry run, like buttons)."""
from __future__ import annotations

import re

from datagen import browser as B
from datagen.kinds import register
from datagen.kinds.base import Kind
from datagen.kinds.filters import SliderKind, _num, _fmt

RATING = re.compile(r"(rating|rate|stars?|score)", re.I)


@register
class RatingKind(Kind):
    name = "rating"
    macros = {"feedback_by_star": "star"}
    oracle = True
    example = '''# example: set a rating slider to N stars, then submit the rating form
s = dom.one(css=task["target_css"])
if not s.in_viewport:
    s = act.scroll_into_view(s)
act.drag(s, s, at_source=(task["from_fraction"], 0.5), at_target=(task["to_fraction"], 0.5))
s = dom.one(css=task["target_css"])
diff = round((float(task["target"]) - float(s.value)) / float(task["step"]))
if diff:
    cur = (float(s.value) - float(task["min"])) / (float(task["max"]) - float(task["min"]))
    act.click(s, at=(min(0.98, max(0.02, cur)), 0.5))
    for _ in range(abs(diff)):
        act.press("ArrowRight" if diff > 0 else "ArrowLeft")
btn = dom.one(css=task["submit_css"])
if not btn.in_viewport:
    btn = act.scroll_into_view(btn)
act.click(btn)
expect.backend()'''

    def discover(self, scan, page, site):
        out = []
        for i in scan.get("inputs") or []:
            if i["type"] != "range" or not RATING.search(" ".join([i["name"], i["label"], i["group_label"], i["id"]])):
                continue
            lo, hi = _num(i["min"]), _num(i["max"])
            if lo is None or hi is None or hi > 10 or hi - lo < 2:
                continue
            sub = (i.get("form") or {}).get("submit") or i.get("apply_hint")
            if not sub:
                continue
            ctrl = {"kind": "rating", "role": "star", "css": i["css"], "name": i["name"], "id": i["id"],
                    "label": i["label"] or "Rating", "min": lo, "max": hi, "step": _num(i["step"], 1.0) or 1.0,
                    "value": _num(i["value"]), "form": i["form"], "apply_hint": i.get("apply_hint"),
                    "submit": sub, "item": scan.get("h1") or scan["title"], "page": page, "page_title": scan["title"]}
            out.append((("rating", i["name"] or i["css"], page), ctrl))
        return out

    def arguments(self, ctrl):
        lo, hi, st = ctrl["min"], ctrl["max"], ctrl["step"] or 1
        vals = [lo + k * st for k in range(int(round((hi - lo) / st)) + 1)]
        return [{"index": n, "value": _fmt(v), "text": f"{_fmt(v)} stars" if v != 1 else "1 star", "item": ctrl.get("item")}
                for n, v in enumerate(vals) if v >= 1 and (ctrl.get("value") is None or abs(v - ctrl["value"]) > st / 2)]

    def probe_argument(self, ctrl):
        args = self.arguments(ctrl)
        return args[len(args) // 2] if args else None

    def dedup_value(self, arg):
        return f"{arg.get('item')}:{arg['value']}"

    def element_key(self, ctrl):
        return f"RATE {ctrl['page']}"

    def view(self, ctrl):
        v = super().view(ctrl)
        v.update({k: ctrl.get(k) for k in ("min", "max", "step", "value", "submit", "item")})
        v.pop("options", None)
        return v

    def apply(self, page, ctrl, arg, base, ctx, log_before):
        page.locator(ctrl["css"]).first.evaluate(
            "(el, v) => { el.value = v; el.dispatchEvent(new Event('input', {bubbles: true}));"
            " el.dispatchEvent(new Event('change', {bubbles: true})); }", arg["value"])
        page.locator(ctrl["submit"]["css"]).first.click(timeout=5000)
        B.settle(page)
        new = B.session_log(ctx, base)[log_before:]
        muts = [e for e in new if (e.get("method") or "GET").upper() != "GET" and isinstance(e.get("status"), int)
                and 200 <= e["status"] < 400]
        return (muts[-1], None, "submit", new) if muts else (None, None, None, new)

    def check(self, ctrl, arg, keep=None):
        return {"kind": "state", "pending": True}

    def request_check(self, entry):
        return {"kind": "request", "method": entry["method"].upper(), "path": entry["path"], "params": {},
                "keep": {}, "final": False}

    def describe(self, ctrl):
        return {"type": "a 1–5 star rating control on the item's page", "label": ctrl.get("label") or "",
                "item": ctrl.get("item"), "choices": [],
                "note": "name the item and the number of stars"}

    def say(self, ctrl, arg):
        return {"rating": arg["text"], "item": arg.get("item")}

    def mentions(self, arg):
        words = (arg.get("item") or "").split()
        return [arg["value"]] + ([" ".join(words[:5])] if words else [])

    def step_spec(self, step):
        c, o = step["control"], step["option"]
        return [f"TARGET: the rating slider css={c['css']!r} (min {_fmt(c['min'])}, max {_fmt(c['max'])}, now {c.get('value')})"
                f" on the page of {c.get('item')!r}",
                f"SET IT TO: {o['value']} ({o['text']}), then submit with the button css={c['submit']['css']!r} "
                f"text={c['submit'].get('text')!r}"]

    def script_task(self, step):
        c, o = step["control"], step["option"]
        frac = lambda v: round(min(0.98, max(0.02, (float(v) - c["min"]) / ((c["max"] - c["min"]) or 1))), 3)
        cur = c.get("value") if c.get("value") is not None else c["min"]
        return {"subtask": step["subtask"], "target_css": c["css"], "target": o["value"], "step": _fmt(c["step"] or 1),
                "min": _fmt(c["min"]), "max": _fmt(c["max"]), "from_fraction": frac(cur), "to_fraction": frac(o["value"]),
                "submit_css": c["submit"]["css"]}

    def locate(self, driver, step):
        return driver.query(css=step["control"]["css"], limit=1)
