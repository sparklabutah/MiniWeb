"""Listing controls that narrow or order a listing with a GET parameter:
a native <select> (filter_by_dropdown, sort_by_form) and a row of sort links (sort_by_form)."""
from __future__ import annotations

from urllib.parse import urlencode, urlsplit

from datagen import browser as B
from datagen.kinds import register
from datagen.kinds.base import Kind, clip


def _sm():
    from datagen import sitemap      # late: sitemap imports the kinds registry
    return sitemap


@register
class SelectKind(Kind):
    name = "select"
    macros = {"filter_by_dropdown": "filter", "sort_by_form": "sort"}
    listing = True
    chainable = True
    example = '''# example: choose an option in a <select>, then press its Apply button if it has one
sel = dom.one(css=task["target_css"])            # use the given selector verbatim
if not sel.in_viewport:
    sel = act.scroll_into_view(sel)
act.click(sel)                                   # opens the option list
cur = [o["index"] for o in sel.options if o["selected"]][0]
target = task["option_index"]
if abs(target - cur) <= 6:
    for _ in range(abs(target - cur)):
        act.press("ArrowDown" if target > cur else "ArrowUp")
else:
    act.type(task["option_text"])
act.press("Enter")
sel = dom.one(css=task["target_css"])            # re-query: the page may have reloaded
assert sel.selected_text == task["option_text"], sel.selected_text
if task["apply_css"]:
    btn = dom.one(css=task["apply_css"])
    if not btn.in_viewport:
        btn = act.scroll_into_view(btn)
    act.click(btn)
expect.backend()'''

    def discover(self, scan, page, site):
        sm = _sm()
        out = []
        for s in scan.get("selects") or []:
            if s["multiple"] or len(s["options"]) < 2:
                continue
            if s["form"] and s["form"]["method"] == "post":
                continue           # a create/edit form, not a listing control
            if sm.NOT_FILTER.search(s["name"] or s["id"] or "") and not sm.SORT_WORDS.search(s["name"] + s["id"]):
                continue
            s = dict(s, page=page, page_title=scan["title"])
            s["role"] = sm._role(s)
            key = ("select", s["role"], s["name"] or s["css"],
                   urlsplit(s["form"]["action"]).path if s["form"] else sm._pattern(page))
            out.append((key, s))
        return out

    def apply(self, page, ctrl, arg, base, ctx, log_before):
        sm = _sm()
        key = ctrl.get("key") or (ctrl.get("signature") or {}).get("param", "")
        page.select_option(ctrl["css"], value=arg["value"], timeout=5000)
        B.settle(page, nav_grace=0.8)
        new = B.session_log(ctx, base)[log_before:]
        e, k = sm.find_carrier(new, arg["value"], key or ctrl.get("name", ""))
        if e:
            return e, k, "auto", new
        sub = (ctrl.get("form") or {}).get("submit")
        if sub and page.locator(sub["css"]).count():
            page.locator(sub["css"]).first.click(timeout=5000)
            B.settle(page)
            new = B.session_log(ctx, base)[log_before:]
            e, k = sm.find_carrier(new, arg["value"], key or ctrl.get("name", ""))
            if e:
                return e, k, "button", new
        return None, None, None, new

    def describe(self, ctrl):
        return {"type": "a select menu (sort control)" if ctrl["role"] == "sort" else "a select menu (filter)",
                "label": ctrl.get("label") or ctrl.get("placeholder") or "",
                "choices": [o["text"] for o in ctrl.get("options", [])][:12]}

    def step_spec(self, step):
        c, o = step["control"], step["option"]
        opts = " | ".join(f"{x['index']}:{clip(x['text'], 40)}" for x in c.get("options", [])[:40])
        more = f" … ({c['n_options']} options total)" if c.get("n_options", 0) > 40 else ""
        lines = [f"TARGET CONTROL: native <select>  css={c['css']!r}  label={c.get('label') or c.get('placeholder')!r}",
                 f"OPTION TO CHOOSE: {o['text']!r} (index {o['index']}, value {o['value']!r})",
                 f"OPTIONS IN ORDER: {opts}{more}"]
        if c.get("apply") == "button" and c.get("apply_button"):
            b = c["apply_button"]
            lines.append(f"APPLY: the form does NOT submit by itself — after choosing, click its button "
                         f"css={b['css']!r} text={b['text']!r}")
        else:
            lines.append("APPLY: the page updates by itself as soon as the option is committed (Enter).")
        return lines

    def script_task(self, step):
        c, o = step["control"], step["option"]
        b = c.get("apply_button") if c.get("apply") == "button" else None
        return {"subtask": step["subtask"], "option_text": o["text"], "option_index": o["index"],
                "option_value": o["value"], "target_css": c["css"], "apply_css": (b or {}).get("css"),
                "apply_text": (b or {}).get("text")}

    def locate(self, driver, step):
        return driver.query(css=step["control"]["css"], limit=2)


@register
class SortLinkKind(Kind):
    name = "link"
    macros = {"sort_by_form": "sort"}
    listing = True
    chainable = True
    example = '''# example: click a sort link
link = dom.one(text=task["link_text"], tag="a")
if not link.in_viewport:
    link = act.scroll_into_view(link)
act.click(link)
expect.backend()'''

    def discover(self, scan, page, site):
        sm = _sm()
        out = []
        for g in scan.get("links") or []:
            if g["path"].rstrip("/") != page.rstrip("/"):
                continue           # sort links must re-sort THIS listing
            ctrl = {"kind": "link", "css": "", "name": g["key"], "id": "", "label": "", "key": g["key"],
                    "options": [{"index": i, **o} for i, o in enumerate(g["options"])],
                    "page": page, "page_title": scan["title"], "role": "sort"}
            out.append((("link", "sort", g["key"], sm._pattern(page)), ctrl))
        return out

    def apply(self, page, ctrl, arg, base, ctx, log_before):
        sm = _sm()
        key = ctrl.get("key") or (ctrl.get("signature") or {}).get("param", "")
        loc = page.locator(f'a[href="{arg["href"]}"]') if arg.get("href") else page.locator("a[href='#never']")
        if not loc.count():          # hrefs carry the current filters once some are applied
            loc = page.locator(f'a[href*="{urlencode({key: arg["value"]})}"]')
        loc.first.click(timeout=5000)
        B.settle(page)
        new = B.session_log(ctx, base)[log_before:]
        e, k = sm.find_carrier(new, arg["value"], key)
        return e, k, "click", new

    def describe(self, ctrl):
        return {"type": "a row of sort links above the listing", "label": ctrl.get("label") or "",
                "choices": [o["text"] for o in ctrl.get("options", [])][:10]}

    def step_spec(self, step):
        c, o = step["control"], step["option"]
        return [f"TARGET CONTROL: a sort LINK with visible text {o['text']!r} (href contains "
                f"{c['signature']['param']}={o['value']})",
                "APPLY: clicking the link re-sorts the listing."]

    def script_task(self, step):
        o = step["option"]
        return {"subtask": step["subtask"], "option_text": o["text"], "option_index": o["index"],
                "option_value": o["value"], "link_text": o["text"], "apply_css": None}

    def locate(self, driver, step):
        return driver.query(text=step["option"]["text"], tag="a", limit=3)

    def dedup_value(self, arg):
        return str(arg["value"])
