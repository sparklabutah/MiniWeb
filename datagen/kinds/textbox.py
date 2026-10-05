"""edit_by_textbox — add a text box to a design and style it: click Add Text, write the text, set its
size in the properties panel, and save the design.

A control is a design editor page with an Add Text tool and a Save button. Its arguments are
(text, size) pairs. The properties panel only appears once a text box exists, so the privileged
dry run finds its fields after adding one (the text field holds the new box's placeholder text,
the size field is the number input labelled size) and records them in the argument; the check
is recorded from the data change the save makes (checks.state_check), run twice for stability.
"""
from __future__ import annotations

import random
import re

from datagen import browser as B
from datagen.kinds import register
from datagen.kinds.base import Kind

ADD_TEXT = re.compile(r"^\W*(add )?text( box)?\W*$|^\W*add text\b", re.I)
SAVE = re.compile(r"^\W*save( design| project| changes)?\W*$", re.I)
TEXTS = ["Grand Opening", "Summer Sale 40% Off", "Save the Date", "Thank You!", "New Arrivals", "Join Us Friday",
         "Limited Edition", "Coming Soon", "Happy Birthday", "Book Now"]
SIZES = ["32", "40", "48", "56", "64", "72"]
FIELDS_JS = r"""
(defaultText) => {
  const vis = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 1 && r.height > 1 && s.display !== 'none' && s.visibility !== 'hidden'; };
  const sel = el => el.id ? '#' + CSS.escape(el.id) : (el.name ? `input[name="${el.name}"]` : null);
  const labelOf = el => ((el.labels && el.labels[0] && el.labels[0].innerText) || (el.previousElementSibling && el.previousElementSibling.innerText) ||
                         (el.parentElement && el.parentElement.innerText) || el.id || '').toLowerCase();
  const ins = [...document.querySelectorAll('input, textarea')].filter(vis);
  const text = ins.find(i => (i.type === 'text' || i.tagName === 'TEXTAREA') && (i.value === defaultText || /\btext\b|content/.test(labelOf(i))));
  const size = ins.find(i => i.type === 'number' && /size/.test(labelOf(i) + ' ' + i.id));
  return {text: text ? sel(text) : null, size: size ? sel(size) : null, size_value: size ? size.value : null};
}
"""


@register
class TextboxKind(Kind):
    name = "textbox"
    macros = {"edit_by_textbox": "textbox"}
    oracle = True
    needs_probe = False
    example = '''# example: add a text box, type its text and size in the properties panel, then save
act.click(dom.one(css=task["add_css"]))
field = dom.one(css=task["text_css"])
act.click(field)
act.press("Control+a")
act.type(task["text"])
size = dom.one(css=task["size_css"])
act.click(size)
act.press("Control+a")
act.type(task["size"])
btn = dom.one(css=task["save_css"])
if not btn.in_viewport:
    btn = act.scroll_into_view(btn)
act.click(btn)
expect.backend()'''

    def discover(self, scan, page, site):
        btns = scan.get("buttons") or []
        add = next((b for b in btns if ADD_TEXT.search(b["text"] or "") or ADD_TEXT.search(b["aria"] or "")), None)
        save = next((b for b in btns if SAVE.match(b["text"] or "")), None)
        if not add or not save:
            return []
        ctrl = {"kind": "textbox", "role": "textbox", "css": add["css"], "add_css": add["css"], "save_css": save["css"],
                "save_text": save["text"], "label": scan.get("h1") or scan["title"], "name": "textbox", "id": "",
                "page": page, "page_title": scan["title"], "site_id": site}
        return [(("textbox", _sm()._pattern(page)), ctrl)]

    def arguments(self, ctrl):
        rng = random.Random(ctrl["page"])
        pairs = [(t, s) for t in TEXTS for s in SIZES]
        rng.shuffle(pairs)
        return [{"index": i, "value": f"{t}|{s}", "text": t, "size": s} for i, (t, s) in enumerate(pairs)]

    def probe_argument(self, ctrl):
        return self.arguments(ctrl)[0]

    def element_key(self, ctrl):
        return f"TEXTBOX {_sm()._pattern(ctrl['page'])}"

    def dedup_value(self, arg):
        return arg["value"]

    def view(self, ctrl):
        v = super().view(ctrl)
        v.pop("options", None)
        v.update({k: ctrl.get(k) for k in ("add_css", "save_css", "save_text", "site_id")})
        return v

    def apply(self, page, ctrl, arg, base, ctx, log_before):
        page.locator(ctrl["add_css"]).first.click(timeout=5000)
        B.settle(page)
        found = page.evaluate(FIELDS_JS, "Double-click to edit")
        if not found.get("text") or not found.get("size"):
            return None, None, None, B.session_log(ctx, base)[log_before:]
        arg.update(text_css=found["text"], size_css=found["size"])       # recorded for the executor
        page.fill(found["text"], arg["text"], timeout=5000)
        page.fill(found["size"], arg["size"], timeout=5000)
        page.locator(found["size"]).first.press("Tab")
        page.locator(ctrl["save_css"]).filter(has_text=ctrl.get("save_text") or "Save").first.click(timeout=5000)
        B.settle(page)
        new = B.session_log(ctx, base)[log_before:]
        muts = [e for e in new if isinstance(e.get("status"), int) and 200 <= e["status"] < 400
                and (e.get("method") or "GET").upper() != "GET"]
        e = (muts or [None])[-1]
        return (e, None, "click", new) if e else (None, None, None, new)

    def check(self, ctrl, arg, keep=None):
        return {"kind": "state", "pending": True}

    def request_check(self, entry):
        return {"kind": "request", "method": entry["method"].upper(), "path": entry["path"], "params": {}, "keep": {},
                "final": False}

    def describe(self, ctrl):
        return {"type": "a design editor: add a text box, set its text and font size, save the design",
                "label": ctrl.get("label") or "", "choices": [],
                "note": "say the exact text and the font size; name the design"}

    def say(self, ctrl, arg):
        return {"add text box": arg["text"], "font size": arg["size"], "in the design being edited": ctrl.get("label")}

    def mentions(self, arg):
        return [arg["text"], arg["size"]]

    def step_spec(self, step):
        c, o = step["control"], step["option"]
        return [f"ADD: click the Add Text tool css={c['add_css']!r}; a text box appears and its properties panel opens",
                f"TEXT: in the text field css={o.get('text_css')!r} replace the content with {o['text']!r}",
                f"SIZE: in the size field css={o.get('size_css')!r} replace the number with {o['size']!r}",
                f"SAVE: click css={c['save_css']!r} text={c.get('save_text')!r}"]

    def script_task(self, step):
        c, o = step["control"], step["option"]
        return {"subtask": step["subtask"], "add_css": c["add_css"], "text_css": o.get("text_css"), "size_css": o.get("size_css"),
                "text": o["text"], "size": o["size"], "save_css": c["save_css"]}

    def locate(self, driver, step):
        return driver.query(css=step["control"]["add_css"], limit=1)


def _sm():
    from datagen import sitemap
    return sitemap
