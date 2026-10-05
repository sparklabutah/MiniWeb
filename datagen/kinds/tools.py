"""compute_by_tool — use an on-page tool (a unit converter, a calculator, a statistics panel) to
compute a result: set its inputs, press Convert / Calculate / Compute, and the page shows the
result without saving anything.

A control is a tool panel found by its button and the inputs around it (outside any form that
saves). Its arguments are value sets for those inputs (LLM, cached — as for forms; slider values
snapped to their step). The dry run applies a set in a throw-away session and records the request
the tool sent with those values (the check, like a translation or route query) and the result it
showed (for the wording and the judge's reference).
"""
from __future__ import annotations

import re

from datagen import browser as B
from datagen import formvalues as FV
from datagen.kinds import register
from datagen.kinds.forms import FormKind


def _snap(f, v):
    """A slider value on its grid (the browser would snap it anyway)."""
    try:
        lo, hi = float(f.get("min") or 0), float(f.get("max") or 100)
        step = float(f.get("step") or 1)
        x = min(hi, max(lo, round((float(v) - lo) / step) * step + lo))
        return str(int(x)) if x == int(x) else str(x)
    except (TypeError, ValueError):
        return v


@register
class ToolKind(FormKind):
    name = "tool"
    macros = {"compute_by_tool": "tool"}
    oracle = False
    needs_probe = False
    example = '''# example: set each input of the tool, press its button (sliders: click near the value, then arrow keys)
for f in task["fields"]:
    el = dom.one(css=f["css"])
    if not el.in_viewport:
        el = act.scroll_into_view(el)
    if f["type"] == "select":
        act.click(el)
        act.type(f["option_text"])
        act.press("Enter")
    elif f["type"] == "range":
        act.click(el, at=(f["frac"], 0.5))
        for _ in range(80):
            cur = float(dom.refresh(el).value)
            if abs(cur - float(f["value"])) < 1e-9:
                break
            act.press("ArrowRight" if cur < float(f["value"]) else "ArrowLeft")
    else:
        act.click(el)
        if el.value:
            act.press("Control+a")
        act.type(f["value"])
btn = dom.one(css=task["submit_css"])
if not btn.in_viewport:
    btn = act.scroll_into_view(btn)
act.click(btn)
expect.backend()'''

    def discover(self, scan, page, site):
        out = []
        for i, t in enumerate(scan.get("tools") or []):
            fields = [dict(f, visible=True, label_css=None, checked=False) for f in t["fields"]
                      if f["type"] not in ("checkbox", "radio", "file")]
            if not fields:
                continue
            ctrl = {"kind": "tool", "role": "tool", "macro": "compute_by_tool", "css": t["css"], "name": t["text"],
                    "id": "", "label": t.get("heading") or scan.get("h1") or scan["title"], "heading": t.get("heading") or "",
                    "fields": fields, "submit": {"css": t["css"], "text": t["text"]}, "result_css": t.get("result_css"),
                    "form": None, "context": (scan.get("items") or [])[:15], "site_id": site, "page": page,
                    "page_title": scan["title"]}
            out.append((("tool", _sm()._pattern(page), t["text"], i), ctrl))
        return out

    def serves(self, ctrl, macro):
        return macro == "compute_by_tool"

    def static_probe(self, ctrl):
        super().static_probe(ctrl)

    def arguments(self, ctrl):
        site = ctrl.get("site_id") or ctrl["page"].split("/")[2]
        sets = ctrl.get("value_sets")
        want = ctrl.get("_k") or FV.K
        if sets is None or (len(sets) < want and ctrl.get("_topped_up") != want):
            ctrl["_topped_up"] = None                          # (a saved map may carry an older size)
            sets = FV.value_sets(ctrl, site, k=want)          # cached; tops up older, smaller caches
            ctrl["value_sets"], ctrl["_topped_up"] = sets, want
        by = {FV.field_key(f): f for f in ctrl["fields"]}
        out = []
        for n, s in enumerate(sets):
            vals = {k: (_snap(by[k], v) if by[k]["type"] == "range" else v) for k, v in s["values"].items() if k in by}
            out.append(self._arg(ctrl, vals, s.get("summary", ""), n))
        return out

    def has_arguments(self, ctrl):
        return ctrl.get("value_sets") != []

    def element_key(self, ctrl):
        return f"TOOL {_sm()._pattern(ctrl['page'])} {ctrl['submit'].get('text')}"

    def view(self, ctrl):
        v = super().view(ctrl)
        v["result_css"] = ctrl.get("result_css")
        v["site_id"] = ctrl.get("site_id")
        return v

    def setup(self, ctx, base, ctrl, arg=None):
        return None

    def apply(self, page, ctrl, arg, base, ctx, log_before):
        for f in ctrl["fields"]:
            v = arg["values"].get(FV.field_key(f))
            if v is None:
                continue
            if f["type"] == "select":
                o = FV.option_for(f, v)
                if o:
                    page.select_option(f["css"], value=o["value"], timeout=5000)
            elif f["type"] == "range":
                page.locator(f["css"]).first.evaluate("(el, v) => { el.value = v; el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); }", v)
            else:
                page.fill(f["css"], str(v), timeout=5000)
        page.locator(ctrl["submit"]["css"]).first.click(timeout=5000)
        B.settle(page)
        new = B.session_log(ctx, base)[log_before:]
        acc = [e for e in new if isinstance(e.get("status"), int) and 200 <= e["status"] < 400]
        carriers = [e for e in acc if any(_sm().find_carrier([e], str(v))[0] for v in arg["values"].values())]
        e = (carriers or [None])[-1]
        return (e, None, "click", new) if e else (None, None, None, new)

    def check(self, ctrl, arg, keep=None):
        return {"kind": "request", "pending": True}

    def dry_run(self, t, base, b):
        """Apply the values in a throw-away session: the request the tool sent carrying them is the
        check; the result it shows goes into the option (wording, judge reference)."""
        c, o = t["control"], t["option"]
        ctx = B.new_context(b)
        page = ctx.new_page()
        try:
            B.goto_start(page, base + t["start"]["url"])
            n0 = len(B.session_log(ctx, base))
            e, _k, _m, _new = self.apply(page, c, o, base, ctx, n0)
            if e is None:
                return False, "the tool sent no request carrying the entered values (client-side only?)"
            chk = self.request_check(e)
            chk["params"] = {k: v for k, v in chk["params"].items() if not re.search(r"(^|_)(user_?id|uid)$", k)}
            result = ""
            if c.get("result_css"):
                try:
                    result = page.locator(c["result_css"]).first.inner_text(timeout=3000).strip()[:120]
                except Exception:
                    result = ""
            if not result or re.search(r"\berror\b", result, re.I):
                return False, f"the tool showed no result ({result!r})"
            t["check"] = chk
            o["result"] = result
            return True, f"{chk['method']} {chk['path']} {chk['params']} -> {result!r}"
        finally:
            ctx.close()

    def describe(self, ctrl):
        return {"type": f"an on-page tool ({ctrl.get('heading') or ctrl.get('page_title')}) with a "
                        f"{ctrl['submit'].get('text')!r} button",
                "label": ctrl["submit"].get("text"),
                "fields": [f.get("label") or f.get("name") for f in ctrl["fields"]], "choices": [],
                "note": "say what to compute with every value given exactly; do not state the result"}

    def forbidden(self, arg):
        r = str(arg.get("result") or "").strip()
        return [r] if r and re.search(r"\d", r) and len(r) >= 3 else []

    def _field_task(self, f, v):
        t = super()._field_task(f, v)
        if f["type"] == "range":
            try:
                lo, hi = float(f.get("min") or 0), float(f.get("max") or 100)
                t["frac"] = round(min(0.98, max(0.02, (float(v) - lo) / (hi - lo))), 3)
            except (TypeError, ValueError, ZeroDivisionError):
                t["frac"] = 0.5
        return t

    def step_spec(self, step):
        lines = super().step_spec(step)
        lines[0] = (f"TARGET: the tool {step['control'].get('heading') or step['control'].get('page_title')!r}: set the "
                    f"inputs, then click its button css={step['control']['submit']['css']!r} "
                    f"text={step['control']['submit'].get('text')!r} (nothing is saved; the result appears on the page)")
        if any(f["type"] == "range" for f in step["control"]["fields"]):
            lines.append("SLIDERS: click the track near the value (field 'frac'), then ArrowRight/ArrowLeft until the "
                         "slider's value is exact")
        return lines


def _sm():
    from datagen import sitemap
    return sitemap
