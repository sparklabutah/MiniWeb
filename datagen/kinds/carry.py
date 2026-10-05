"""carry_info_cross_site — read a value on one site and use it on another: find it in a record set
on site A (a table or a list of cards), then search for it on site B.

A control is a record set on A (as for report_information). Its arguments pair a value from a
record (its name or one of its fields, copied verbatim) with a search box on ANOTHER train site
where looking it up makes sense; an LLM proposes the pairs from the records and the search boxes
the site maps know (cached), code validates them. The check is B's search request carrying the
exact value, AND the value must have been on screen on A in a recorded screenshot (evidence), so
the trajectory really carries it across. The executor reads it on A, opens B with act.open_url,
and searches.
"""
from __future__ import annotations

import hashlib
import json

from datagen import browser as B
from datagen import checks, config
from datagen.kinds import qa, register
from datagen.kinds.base import Kind

CACHE = config.DATAGEN_DIR / "carry_pairs"
PAIR_SYSTEM = ("You design realistic two-website tasks: a person reads a value on one website and looks it up on "
               "another. Given records shown on site A and the search boxes of other websites, propose pairs where "
               "searching B for the value is something a real person would plausibly do (e.g. an author seen in a "
               "news list -> search a book store; a city in a transit table -> search a map; a product in an order "
               "table -> search a shop). Use only values given, copied exactly; prefer names over numbers. "
               "Reply ONLY JSON.")


def _targets(own_site):
    """Search boxes on other train sites: [{site, name, placeholder, ctrl}]."""
    from datagen import kinds, sitemap
    from datagen.split import train_sites
    out = []
    for s in train_sites():
        if s == own_site:
            continue
        sm = sitemap.load(s)
        for c in (sm or {}).get("controls", []):
            if c.get("kind") == "searchbox" and c.get("usable") and c.get("signature"):
                out.append({"site": s, "name": B.site_name(s), "placeholder": c.get("placeholder") or c.get("label") or "",
                            "ctrl": {k: v for k, v in kinds.of(c).view(c).items() if k not in ("options", "n_options")}})
                break
    return out


# page chrome the record extraction sometimes returns as a "record" (column headers, badges, sort labels):
# looking one of these up on another site is not a task a person has (2026-09-30: "Date", "SPONSORED", "Sort:")
UI_WORDS = {"date", "name", "status", "sort", "filter", "search", "total", "type", "category", "price", "title",
            "author", "tags", "tag", "description", "actions", "action", "edit", "delete", "view", "details", "more",
            "sponsored", "featured", "new", "all", "none", "other", "yes", "no", "weight", "height", "amount",
            "value", "time", "id", "results", "items", "confirmed", "tentative", "pending", "active", "open", "closed"}


def junk_value(v, record=""):
    """A value no person would carry to another site: UI chrome, a header, a status badge."""
    v = (v or "").strip()
    w = v.lower().rstrip(":")
    if v.endswith(":") or w in UI_WORDS or w.rstrip("s") in UI_WORDS:
        return True
    if " " not in v and v.isupper() and not any(ch.isdigit() for ch in v):      # SPONSORED, WEIGHT
        return True
    if (record or "").strip().lower().rstrip(":") in UI_WORDS:                   # the "record" is a column header
        return True
    return False


def pairs(ctrl, recs, entity, model=None, force=False):
    key = hashlib.sha1(json.dumps([ctrl["page"], ctrl.get("fingerprint")]).encode()).hexdigest()[:16]
    path = CACHE / ctrl["site_id"] / f"{key}.json"
    if path.exists() and not force:
        return json.loads(path.read_text())
    from helpers.llm import call_llm
    targets = _targets(ctrl["site_id"])
    prompt = json.dumps({"site_a": B.site_name(ctrl["site_id"]), "page_a": ctrl.get("page_title"), "items": entity,
                         "records": [{"name": r["name"], **r["fields"]} for r in recs[:25]],
                         "search_boxes": [{"site": t["site"], "website": t["name"], "placeholder": t["placeholder"]}
                                          for t in targets],
                         "output": {"pairs": [{"value": "exact value from a record", "record": "that record's name",
                                               "site": "site id of the search box", "why": "short reason"}]},
                         "n_pairs": 6}, ensure_ascii=False)
    try:
        got = json.loads(call_llm(prompt, system=PAIR_SYSTEM, json_mode=True, model=model or config.MODEL_SUGGEST,
                                  max_tokens=4000, temperature=0.6) or "")
    except Exception:
        got = {}
    got = got if isinstance(got, dict) else {"pairs": got}
    by_site = {t["site"]: t for t in targets}
    names = {r["name"]: r for r in recs}
    out = []
    for p in got.get("pairs") or []:
        v, rec, site = str(p.get("value") or "").strip(), names.get(str(p.get("record") or "").strip()), p.get("site")
        if not rec or site not in by_site or not (3 <= len(v) <= 60):
            continue
        if not any(v in s for s in [rec["name"], *rec["fields"].values()]):   # verbatim (a part of) the record
            continue
        if junk_value(v, rec["name"]):
            continue
        out.append({"value": v, "record": rec["name"], "site": site, "why": str(p.get("why") or "")[:160],
                    "target": by_site[site]["ctrl"]})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    return out


@register
class CarryKind(Kind):
    name = "carry"
    macros = {"carry_info_cross_site": "carry"}
    needs_probe = False
    example = '''# example: find the value on this site, then look it up on the other site
el = dom.one(text=task["value"])
if not el.in_viewport:
    el = act.scroll_into_view(el)
act.open_url(task["target_home"])               # the other website's front page (its address is in the task)
if task["target_page"] != task["target_home"]:   # reach the search page the way a person would: by its link
    link = dom.one(css=f'a[href="{task["target_page"]}"]')
    if not link.in_viewport:
        link = act.scroll_into_view(link)
    act.click(link)
box = dom.one(css=task["target_css"])
act.click(box)
act.type(task["value"])
if task["apply_css"]:
    act.click(dom.one(css=task["apply_css"]))
else:
    act.press("Enter")
expect.backend()'''

    def discover(self, scan, page, site):
        out = []
        for key, ctrl in qa.QAKind().discover(scan, page, site):
            ctrl = dict(ctrl, kind="carry", role="carry")
            out.append((("carry",) + tuple(key[1:]), ctrl))
        return out

    def static_probe(self, ctrl):
        super().static_probe(ctrl)
        ctrl["usable"] = bool(ctrl.get("records") or ctrl.get("cards"))

    def arguments(self, ctrl):
        recs, entity = qa.QAKind()._records(ctrl)
        if not recs:
            return []
        return [{"index": i, "value": f"{p['site']}|{p['value']}", "text": p["value"], **p}
                for i, p in enumerate(pairs(ctrl, recs, entity))]

    def has_arguments(self, ctrl):
        return bool(ctrl.get("records") or ctrl.get("cards"))

    def element_key(self, ctrl):
        return f"CARRY {_sm()._pattern(ctrl['page'])} {ctrl['css']}"

    def dedup_value(self, arg):
        return arg["value"]

    def view(self, ctrl):
        return qa.QAKind().view(ctrl) | {"kind": "carry", "role": "carry"}

    def check(self, ctrl, arg, keep=None):
        chk = checks.build_check(arg["target"]["signature"], arg["text"], final=False)
        chk["evidence"] = [arg["text"]]
        return chk

    def dry_run(self, t, base, b):
        """The value is on A's live page, and searching B for it sends the checked request."""
        from datagen import kinds
        o = t["option"]
        ctx = B.new_context(b)
        page = ctx.new_page()
        try:
            B.goto_start(page, base + t["start"]["url"])
            if checks._norm(o["text"]) not in checks._norm(page.inner_text("body")):
                return False, f"{o['text']!r} is not on the live page of {t['site']}"
            tgt = o["target"]
            B.goto_start(page, base + tgt["page"])
            n0 = len(B.session_log(ctx, base))
            ctrl = tgt | {"form": {"submit": tgt.get("apply_button")}}
            kinds.get("searchbox").apply(page, ctrl, {"value": o["text"]}, base, ctx, n0)
            ok, detail = checks.evaluate({k: v for k, v in t["check"].items() if k != "evidence"}, B.session_log(ctx, base))
            return (True, f"{t['site']} -> {o['site']}: {detail}") if ok else (False, "search on B failed: " + detail)
        finally:
            ctx.close()

    def open_urls(self, step):
        # only the other website's FRONT page, whose address the instruction gives (2026-09-29: the executor had
        # jumped straight to a deep page only it knew, so the student learned to guess URLs and hit 404s)
        return [_home(step["option"]["site"])]

    def describe(self, ctrl):
        return {"type": "a value read on this site and looked up on another website",
                "label": ctrl.get("label") or "",
                "note": "say where to find the value (which list/item on this site) WITHOUT stating the value "
                        "itself unless it is the item's name, then which website to search it on"}

    def say(self, ctrl, arg):
        return {"find_on_this_site": f"{arg['text']!r}, in the item {arg['record']!r}",
                "then_search_on": f"{B.site_name(arg['site'])} (at {_home(arg['site'])})", "why": arg.get("why"),
                "note": "give the other website's name AND its address exactly as written here"}

    def mentions(self, arg):
        return ([arg["record"]] if len(arg["record"]) <= 80 else []) + [_home(arg["site"])]

    def step_spec(self, step):
        o = step["option"]
        tgt = o["target"]
        b = tgt.get("apply_button") if tgt.get("apply") == "button" else None
        return [f"READ: on this page, the value {o['text']!r} (of {o['record']!r}) — bring it on screen",
                f"GO: act.open_url({_home(o['site'])!r}) ({B.site_name(o['site'])}'s front page, the address the task "
                f"gives)" + (f", then click the link to {tgt['page']!r} (css a[href=...]) to reach its search box"
                             if tgt["page"].split("?")[0] != _home(o["site"]) else ""),
                f"SEARCH: type {o['text']!r} exactly into css={tgt['css']!r} and "
                + (f"click css={b['css']!r}" if b else "press Enter")]

    def script_task(self, step):
        o = step["option"]
        tgt = o["target"]
        b = tgt.get("apply_button") if tgt.get("apply") == "button" else None
        return {"subtask": step["subtask"], "value": o["text"], "record": o["record"], "target_page": tgt["page"],
                "target_home": _home(o["site"]),
                "target_css": tgt["css"], "apply_css": (b or {}).get("css"), "open_urls": self.open_urls(step)}

    def locate(self, driver, step):
        return driver.query(text=step["option"]["text"], limit=1)


def _home(site):
    return f"/sites/{site}/"


def _sm():
    from datagen import sitemap
    return sitemap
