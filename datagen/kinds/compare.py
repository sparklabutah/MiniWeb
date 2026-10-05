"""Compare pickers (compare_by_form): <select>s on a compare page choosing the items shown
side by side. Like a listing select, the backend check is the GET carrying the choice."""
from __future__ import annotations

from datagen.kinds import register
from datagen.kinds.listing import SelectKind


@register
class CompareKind(SelectKind):
    name = "compare"
    macros = {"compare_by_form": "compare"}
    listing = False              # a compare page is not a listing (refine() would drop it)
    chainable = True

    def discover(self, scan, page, site):
        if "compare" not in page.lower() and "compare" not in (scan.get("title") or "").lower():
            return []
        out = []
        for s in scan.get("selects") or []:
            if s["multiple"] or len(s["options"]) < 3 or (s["form"] and s["form"]["method"] == "post"):
                continue
            s = dict(s, page=page, page_title=scan["title"], kind="compare", role="compare")
            out.append((("compare", s["name"] or s["css"], page), s))
        return out

    def check(self, ctrl, arg, keep=None):
        chk = super().check(ctrl, arg, keep=keep)
        chk["multi"] = True          # the compared set: the chosen value may sit among others (ids=a,b)
        return chk

    def describe(self, ctrl):
        # the backend only sees the compared set (ids=a,b), not which column holds an item, so the instruction
        # must not name a column ("App 2"): picking it in the other column is equally correct (2026-09-29)
        return {"type": "a picker on a compare page that adds one item to the comparison; do NOT say which "
                        "column/picker (e.g. never 'App 1'/'App 2'), only which item to compare",
                "label": "", "choices": [o["text"] for o in ctrl.get("options", [])][:12]}

    def forbidden(self, arg):
        return ["App 1", "App 2", "first picker", "second picker", "left column", "right column"]
