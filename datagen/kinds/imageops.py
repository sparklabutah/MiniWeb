"""edit_by_image (image tools) — edit a picture with the page's image tools: set an operation's
inputs (crop box, size, contrast, vibrance …) and press its Apply button.

A control is one operation panel beside an image; its arguments are value sets for the panel's
inputs (LLM, cached; sliders snapped to their step). The check is recorded like every data-
changing kind (checks.state_check): the dry run applies the values twice in throw-away sessions
and keeps the data changes both agree on — the edited image itself compares by presence only,
the recorded operation and its parameters exactly.
"""
from __future__ import annotations

from datagen import browser as B
from datagen import formvalues as FV
from datagen.kinds import register
from datagen.kinds.tools import ToolKind, _snap


@register
class ImageOpKind(ToolKind):
    name = "imageop"
    macros = {"edit_by_image": "imageop"}
    oracle = True
    needs_probe = False

    def discover(self, scan, page, site):
        out = []
        for i, t in enumerate(scan.get("imgops") or []):
            fields = [dict(f, visible=True, label_css=None, checked=False) for f in t["fields"]
                      if f["type"] in ("number", "range", "text", "select")]
            if not fields:
                continue
            ctrl = {"kind": "imageop", "role": "imageop", "macro": "edit_by_image", "css": t["css"], "name": t["text"],
                    "id": "", "label": t["text"], "heading": t.get("heading") or scan.get("h1") or "", "op": t.get("op"),
                    "fields": fields, "submit": {"css": t["css"], "text": t["text"]}, "form": None,
                    "context": [f"image editor: {t['text']}"], "site_id": site, "page": page, "page_title": scan["title"]}
            out.append((("imageop", _sm()._pattern(page), t["text"]), ctrl))
        return out

    def serves(self, ctrl, macro):
        return macro == "edit_by_image"

    def element_key(self, ctrl):
        return f"IMAGEOP {_sm()._pattern(ctrl['page'])} {ctrl['submit'].get('text')}"

    def dry_run(self, t, base, b):
        return None                                  # the recorded (oracle) dry run

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
                page.locator(f["css"]).first.evaluate("(el, v) => { el.value = v; el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); }", _snap(f, v))
            else:
                page.fill(f["css"], str(v), timeout=5000)
        page.locator(ctrl["submit"]["css"]).first.click(timeout=5000)
        B.settle(page)
        new = B.session_log(ctx, base)[log_before:]
        muts = [e for e in new if isinstance(e.get("status"), int) and 200 <= e["status"] < 400
                and (e.get("method") or "GET").upper() != "GET"]
        e = (muts or [None])[-1]
        return (e, None, "click", new) if e else (None, None, None, new)

    def check(self, ctrl, arg, keep=None):
        return {"kind": "state", "pending": True}

    def forbidden(self, arg):
        return []

    def describe(self, ctrl):
        return {"type": f"an image tool: {ctrl['submit'].get('text')!r} with its settings", "label": ctrl["submit"].get("text"),
                "fields": [f.get("label") or f.get("name") for f in ctrl["fields"]], "choices": [],
                "note": "ask to apply this edit to the picture with every value given exactly"}

    def step_spec(self, step):
        lines = super().step_spec(step)
        lines[0] = (f"TARGET: the image tool {step['control']['submit'].get('text')!r}: set its inputs, then click "
                    f"css={step['control']['submit']['css']!r} (the edit is saved)")
        return lines


def _sm():
    from datagen import sitemap
    return sitemap
