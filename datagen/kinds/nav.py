"""Navigation: open a named page by clicking a link or menu item (navigate_by_route).

The argument is a destination the start page links to; the backend proof is the GET of the
destination path. Links with side effects (logout, delete, toggles, downloads) are skipped."""
from __future__ import annotations

import re

from datagen import browser as B
from datagen.kinds import register
from datagen.kinds.base import Kind

PER_PAGE = 12


def _sm():
    from datagen import sitemap
    return sitemap


@register
class NavLinkKind(Kind):
    name = "navlink"
    macros = {"navigate_by_route": "navigate"}
    example = '''# example: open a page by clicking its link (this step IS navigation)
link = dom.one(css=task["target_css"])
if not link.in_viewport:
    link = act.scroll_into_view(link)
act.click(link)
expect.backend()'''

    def discover(self, scan, page, site):
        sm = _sm()
        here = sm._pattern(page)
        seen, opts = set(), []
        for a in scan.get("anchors") or []:
            pat = sm._pattern(a["path"])
            if sm.SKIP.search(a["path"] + a.get("search", "")) or pat == here or pat in seen:
                continue
            if len(a["text"]) > 50 or not any(ch.isalpha() for ch in a["text"]):
                continue
            seen.add(pat)
            opts.append({"index": len(opts), "value": a["path"], "text": re.sub(r"^\W+|\W+$", "", a["text"]),
                         "css": a["css"], "region": a["region"]})
            if len(opts) >= PER_PAGE:
                break
        if len(opts) < 2:
            return []
        ctrl = {"kind": "navlink", "role": "navigate", "css": "", "name": "", "id": "", "label": scan["title"],
                "options": opts, "page": page, "page_title": scan["title"]}
        return [(("navlink", here), ctrl)]

    def probe_argument(self, ctrl):
        opts = ctrl.get("options") or []
        return opts[len(opts) // 2] if opts else None

    def arguments(self, ctrl):
        return [dict(o) for o in ctrl.get("options") or [] if o.get("text")]

    def view(self, ctrl):
        v = super().view(ctrl)
        v["options"] = [{k: o.get(k) for k in ("index", "value", "text", "css", "region")} for o in ctrl.get("options") or []]
        return v

    def apply(self, page, ctrl, arg, base, ctx, log_before):
        loc = page.locator(arg["css"]) if arg.get("css") else page.locator(f'a[href^="{arg["value"]}"]')
        loc.first.click(timeout=5000)
        B.settle(page)
        new = B.session_log(ctx, base)[log_before:]
        want = arg["value"].rstrip("/")
        e = next((x for x in new if (x.get("method") or "GET").upper() == "GET" and isinstance(x.get("status"), int)
                  and 200 <= x["status"] < 400 and (x.get("path") or "").rstrip("/") == want), None)
        return (e, "route", "click", new) if e else (None, None, None, new)

    def check(self, ctrl, arg, keep=None):
        return {"kind": "request", "method": "GET", "path": arg["value"], "params": {}, "keep": {}, "final": False}

    def element_key(self, ctrl):
        return "NAV"                      # each destination counts once per site, whatever the start page

    def dedup_value(self, arg):
        return _sm()._pattern(arg["value"])

    def describe(self, ctrl):
        return {"type": "links and menu items on the page", "label": ctrl.get("page_title") or "",
                "choices": [o["text"] for o in ctrl.get("options", [])][:12],
                "note": "the instruction asks to open the destination page by its visible name"}

    def step_spec(self, step):
        o = step["option"]
        return [f"TARGET: the link {o['text']!r} (css={o.get('css')!r}, in the {o.get('region', 'main')} area) "
                f"that opens {o['value']}",
                "NAVIGATION: this step IS navigating — clicking the link and letting the new page load completes it."]

    def script_task(self, step):
        o = step["option"]
        return {"subtask": step["subtask"], "link_text": o["text"], "target_css": o.get("css"), "destination": o["value"]}

    def locate(self, driver, step):
        o = step["option"]
        return driver.query(css=o["css"], limit=1) if o.get("css") else driver.query(text=o["text"], tag="a", limit=2)
