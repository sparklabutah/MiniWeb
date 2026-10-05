"""Listing filters beyond the <select>: option groups (radio/checkbox), filter chips (links),
date ranges, sliders and search boxes. Each narrows a listing with GET parameters, so the
backend check is the listing request carrying the argument (and, at the end, still carrying it).

    choice     radio / checkbox group              filter_by_options
    chips      a row of links setting one param     filter_by_options
    daterange  a From + To date pair               filter_by_date_range
    slider     <input type=range>                  filter_by_slider
    searchbox  a search text field                 search
"""
from __future__ import annotations

import calendar
import re
from datetime import date, timedelta
from urllib.parse import urlsplit

from datagen import browser as B
from datagen import checks
from datagen.kinds import register
from datagen.kinds.base import Kind, clip
from datagen.kinds.listing import SortLinkKind

_ALLISH = re.compile(r"^(|all|any|none|\*|default)$", re.I)


def _sm():
    from datagen import sitemap
    return sitemap


def _form_key(ctrl, page):
    f = ctrl.get("form")
    return urlsplit(f["action"]).path if f else _sm()._pattern(page)


def _get_form(i):
    """A control that can narrow a listing: in a GET form, or scripted outside any form."""
    return not i.get("form") or i["form"]["method"] == "get"


def find_carrier_all(entries, values):
    """The first accepted request carrying every value: (entry, {role: field}) or (None, None)."""
    sm = _sm()
    for e in entries:
        if not isinstance(e.get("status"), int) or not 200 <= e["status"] < 400:
            continue
        keys = {}
        for role, v in values.items():
            hit, k = sm.find_carrier([e], v)
            if not hit or k in keys.values():
                break
            keys[role] = k
        if len(keys) == len(values):
            return e, keys
    return None, None


def _press_apply(page, ctrl):
    """Click the control's own submit/apply button (privileged). True if one was clicked."""
    sub = (ctrl.get("form") or {}).get("submit") or ctrl.get("apply_hint") or ctrl.get("apply_button")
    if sub and sub.get("css") and page.locator(sub["css"]).count():
        page.locator(sub["css"]).first.click(timeout=5000)
        B.settle(page)
        return True
    return False


def _apply_lines(c):
    if c.get("apply") == "button" and c.get("apply_button"):
        b = c["apply_button"]
        return [f"APPLY: the filter does NOT apply by itself — afterwards click its button "
                f"css={b['css']!r} text={b['text']!r}"]
    return ["APPLY: the page updates by itself once the value is committed."]


APPLY_SNIPPET = '''if task["apply_css"]:
    btn = dom.one(css=task["apply_css"])
    if not btn.in_viewport:
        btn = act.scroll_into_view(btn)
    act.click(btn)
expect.backend()'''


class _GetKind(Kind):
    listing = True

    def view(self, ctrl):
        v = super().view(ctrl)
        v["options"] = [{k: o.get(k) for k in ("index", "value", "text", "css", "label_css", "visible", "href") if k in o}
                        for o in ctrl.get("options") or []][:60]
        return v

    def _apply_value(self, page, ctrl, arg, base, ctx, log_before, set_value):
        """set_value(page) makes the change; then the carrying request, else the apply button."""
        sm = _sm()
        set_value(page)
        B.settle(page, nav_grace=0.8)
        key = (ctrl.get("signature") or {}).get("param") or ctrl.get("name", "")
        new = B.session_log(ctx, base)[log_before:]
        e, k = sm.find_carrier(new, arg["value"], key)
        if e:
            return e, k, "auto", new
        if _press_apply(page, ctrl):
            new = B.session_log(ctx, base)[log_before:]
            e, k = sm.find_carrier(new, arg["value"], key)
            if e:
                return e, k, "button", new
        return None, None, None, new


# ── radio / checkbox groups ───────────────────────────────────────────────────

@register
class ChoiceKind(_GetKind):
    name = "choice"
    macros = {"filter_by_options": "filter"}
    chainable = True
    example = '''# example: tick one option of a radio/checkbox group, then apply if the filter has a button
el = dom.one(css=task["target_css"]) if task["target_visible"] else dom.one(css=task["label_css"])
if not el.in_viewport:
    el = act.scroll_into_view(el)
act.click(el)
''' + APPLY_SNIPPET

    def discover(self, scan, page, site):
        groups = {}
        for i in scan.get("inputs") or []:
            if i["type"] not in ("radio", "checkbox") or not _get_form(i):
                continue
            gk = (i["type"], i["name"] or i["group_label"], _form_key(i, page))
            if not gk[1]:
                continue
            groups.setdefault(gk, []).append(i)
        out = []
        for (typ, gname, fkey), items in groups.items():
            opts = [{"index": n, "value": i["value"], "text": i["option_text"], "css": i["css"],
                     "label_css": i["label_css"], "visible": i["visible"], "active": i["checked"]}
                    for n, i in enumerate(items)]
            if sum(1 for o in opts if o["text"] and not _ALLISH.match(o["value"] or "")) < 2:
                continue
            first = items[0]
            ctrl = {"kind": "choice", "input_type": typ, "role": "filter", "css": first["css"], "name": first["name"],
                    "apply_hint": first.get("apply_hint"),
                    "id": first["id"], "label": first["group_label"] or gname, "options": opts,
                    "selected_index": next((o["index"] for o in opts if o["active"]), -1) if typ == "radio" else -1,
                    "form": first["form"], "page": page, "page_title": scan["title"]}
            out.append((("choice", gname, fkey), ctrl))
        return out

    def arguments(self, ctrl):
        return [a for a in super().arguments(ctrl) if not _ALLISH.match(str(a["value"]))]

    def probe_argument(self, ctrl):
        args = self.arguments(ctrl)
        return args[len(args) // 2] if args else None

    def apply(self, page, ctrl, arg, base, ctx, log_before):
        opt = next((o for o in ctrl["options"] if o["index"] == arg["index"]), arg)

        def set_value(p):
            if opt.get("visible", True) and p.locator(opt["css"]).count():
                p.locator(opt["css"]).first.check(timeout=5000)
            else:
                p.locator(opt["label_css"]).first.click(timeout=5000)
        return self._apply_value(page, ctrl, arg, base, ctx, log_before, set_value)

    def describe(self, ctrl):
        what = "radio buttons (pick one)" if ctrl.get("input_type") == "radio" else "checkboxes"
        return {"type": f"a group of {what} filtering the listing", "label": ctrl.get("label") or "",
                "choices": [o["text"] for o in ctrl.get("options", [])][:12]}

    def step_spec(self, step):
        c, o = step["control"], step["option"]
        opt = next((x for x in c["options"] if x["index"] == o["index"]), o)
        typ = "radio button" if c.get("input_type") == "radio" else "checkbox"
        return [f"TARGET CONTROL: a group of {typ}s labelled {c.get('label')!r}",
                f"OPTION TO SELECT: the {typ} {o['text']!r} (input css={opt.get('css')!r}, its label "
                f"css={opt.get('label_css')!r}; the input itself is {'visible' if opt.get('visible', True) else 'hidden — click its label'})",
                "Leave the other options as they are."] + _apply_lines(c)

    def script_task(self, step):
        c, o = step["control"], step["option"]
        opt = next((x for x in c["options"] if x["index"] == o["index"]), o)
        b = c.get("apply_button") if c.get("apply") == "button" else None
        return {"subtask": step["subtask"], "option_text": o["text"], "option_value": o["value"],
                "target_css": opt.get("css"), "label_css": opt.get("label_css"),
                "target_visible": bool(opt.get("visible", True)), "apply_css": (b or {}).get("css"),
                "apply_text": (b or {}).get("text")}

    def locate(self, driver, step):
        t = self.script_task(step)
        return driver.query(css=t["target_css"] if t["target_visible"] else t["label_css"], limit=2)


# ── filter chips: links that set one filter parameter ────────────────────────

@register
class ChipsKind(SortLinkKind):
    name = "chips"
    macros = {"filter_by_options": "filter"}

    def discover(self, scan, page, site):
        sm = _sm()
        out = []
        for g in scan.get("linkgroups") or []:
            if sm.SORT_WORDS.search(g["key"]) or sm.NOT_FILTER.search(g["key"]):
                continue
            if g["path"].rstrip("/") != page.rstrip("/"):
                continue
            ctrl = {"kind": "chips", "css": "", "name": g["key"], "id": "", "label": g["key"].replace("_", " "),
                    "key": g["key"], "options": [{"index": i, **o} for i, o in enumerate(g["options"])],
                    "page": page, "page_title": scan["title"], "role": "filter"}
            out.append((("chips", g["key"], sm._pattern(page)), ctrl))
        return out

    def describe(self, ctrl):
        return {"type": "a row of filter links (chips) above the listing", "label": ctrl.get("label") or "",
                "choices": [o["text"] for o in ctrl.get("options", [])][:12]}

    def step_spec(self, step):
        c, o = step["control"], step["option"]
        return [f"TARGET CONTROL: a filter LINK (chip) with visible text {o['text']!r} (href sets "
                f"{c['signature']['param']}={o['value']})",
                "APPLY: clicking the chip filters the listing."]


# ── date ranges ──────────────────────────────────────────────────────────────

FROM = re.compile(r"(from|start|begin|since|after|min|earliest)", re.I)
TO = re.compile(r"(\bto\b|_to\b|until|end|before|max|latest)", re.I)


def _is_date(i):
    return i["type"] == "date" or (i["type"] == "text" and re.search(r"(yyyy|mm/dd|dd/mm|date)", i["placeholder"] + i["name"], re.I))


def _nice(d):
    return f"{calendar.month_name[d.month]} {d.day}, {d.year}"


def date_ranges(seen, limit=40):
    """Candidate [from, to] windows around dates that appear on the listing (so results exist):
    whole months, month halves and two-month spans; generic 2025–2026 months when none show."""
    days = sorted({date.fromisoformat(d) for d in seen if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d)})
    if not days:                                   # nothing dated on the page: whole months of 2025–2026
        return [(date(y, m, 1), date(y, m, calendar.monthrange(y, m)[1])) for y in (2025, 2026) for m in range(1, 13)][:limit]
    months = sorted({(d.year, d.month) for d in days})
    out = []
    for y, m in months:
        last = calendar.monthrange(y, m)[1]
        out.append((date(y, m, 1), date(y, m, last)))
        out.append((date(y, m, 1), date(y, m, 15)))
        out.append((date(y, m, 16), date(y, m, last)))
        ny, nm = (y + (m == 12), m % 12 + 1)
        out.append((date(y, m, 1), date(ny, nm, calendar.monthrange(ny, nm)[1])))
    for d in days[::max(1, len(days) // 8)]:
        out.append((d - timedelta(days=6), d))
    seen_pairs, res = set(), []
    for a, b in out:
        if (a, b) not in seen_pairs and a <= b:
            seen_pairs.add((a, b))
            res.append((a, b))
    return res[:limit]


@register
class DateRangeKind(_GetKind):
    name = "daterange"
    macros = {"filter_by_date_range": "filter"}
    chainable = True
    example = '''# example: fill a From/To date pair, then apply
for css, keys in ((task["from_css"], task["from_keys"]), (task["to_css"], task["to_keys"])):
    el = dom.one(css=css)                          # re-query each time: the page may reload
    if not el.in_viewport:
        el = act.scroll_into_view(el)
    if task["native_date"]:
        act.click(el, at=(0.12, 0.5))              # the month segment of a native date input
    else:
        act.click(el)
        act.press("Control+a")
    act.type(keys)                                 # native date input: MMDDYYYY digits
''' + APPLY_SNIPPET

    def discover(self, scan, page, site):
        forms = {}
        for i in scan.get("inputs") or []:
            if _is_date(i) and _get_form(i):
                forms.setdefault(_form_key(i, page), []).append(i)
        out = []
        for fkey, items in forms.items():
            frm = [i for i in items if FROM.search(i["name"] + " " + i["label"] + " " + i["id"])]
            to = [i for i in items if TO.search(i["name"] + " " + i["label"] + " " + i["id"]) and i not in frm]
            if not frm or not to:
                if len(items) == 2:
                    frm, to = [items[0]], [items[1]]
                else:
                    continue
            a, b = frm[0], to[0]
            ctrl = {"kind": "daterange", "role": "filter", "css": a["css"], "name": a["name"], "id": a["id"],
                    "apply_hint": a.get("apply_hint"),
                    "label": f"{a['label'] or 'From'} / {b['label'] or 'To'}",
                    "from": {k: a[k] for k in ("css", "name", "label", "type", "value")},
                    "to": {k: b[k] for k in ("css", "name", "label", "type", "value")},
                    "dates": scan.get("dates") or [], "form": a["form"], "page": page, "page_title": scan["title"]}
            out.append((("daterange", a["name"] or a["css"], fkey), ctrl))
        return out

    def arguments(self, ctrl):
        return [{"index": n, "value": f"{a.isoformat()}..{b.isoformat()}", "from": a.isoformat(), "to": b.isoformat(),
                 "text": f"{_nice(a)} to {_nice(b)}", "from_text": _nice(a), "to_text": _nice(b)}
                for n, (a, b) in enumerate(date_ranges(ctrl.get("dates") or []))]

    def probe_argument(self, ctrl):
        args = self.arguments(ctrl)
        return args[0] if args else None

    def view(self, ctrl):
        v = super().view(ctrl)
        v.update({k: ctrl.get(k) for k in ("from", "to", "param_to")})
        v.pop("options", None)
        v["n_options"] = 0
        return v

    def apply(self, page, ctrl, arg, base, ctx, log_before):
        page.fill(ctrl["from"]["css"], arg["from"], timeout=5000)
        page.fill(ctrl["to"]["css"], arg["to"], timeout=5000)
        page.locator(ctrl["to"]["css"]).first.dispatch_event("change")
        B.settle(page, nav_grace=0.8)
        new = B.session_log(ctx, base)[log_before:]
        e, keys = find_carrier_all(new, {"from": arg["from"], "to": arg["to"]})
        mode = "auto"
        if not e and _press_apply(page, ctrl):
            new = B.session_log(ctx, base)[log_before:]
            e, keys = find_carrier_all(new, {"from": arg["from"], "to": arg["to"]})
            mode = "button"
        if not e:
            return None, None, None, new
        ctrl["param_to"] = keys["to"]
        return e, keys["from"], mode, new

    def check(self, ctrl, arg, keep=None):
        sig = ctrl["signature"]
        return {"kind": "request", "method": sig["method"].upper(), "path": sig["path"],
                "params": {sig["param"]: arg["from"], ctrl.get("param_to") or sig.get("param_to"): arg["to"]},
                "keep": dict(keep or {}), "final": True}

    def dedup_value(self, arg):
        return arg["value"]

    def describe(self, ctrl):
        return {"type": "a From/To pair of date fields filtering the listing", "label": ctrl.get("label") or "",
                "choices": [], "note": "state both dates exactly as given (month name, day, year)"}

    def mentions(self, arg):
        return [arg["from_text"], arg["to_text"]]

    def step_spec(self, step):
        c, o = step["control"], step["option"]
        native = c["from"].get("type") == "date"
        how = ("native date inputs: click the LEFT part of the field (the month segment), then type the date as "
               "MMDDYYYY digits — no separators" if native else "text inputs: click, select all, type the date as shown")
        return [f"TARGET CONTROLS: 'From' date css={c['from']['css']!r} and 'To' date css={c['to']['css']!r}",
                f"DATES: from {o['from']} to {o['to']} ({o['text']})", f"HOW: {how}"] + _apply_lines(c)

    def script_task(self, step):
        c, o = step["control"], step["option"]
        native = c["from"].get("type") == "date"
        keys = lambda d: f"{d[5:7]}{d[8:10]}{d[0:4]}" if native else d
        b = c.get("apply_button") if c.get("apply") == "button" else None
        return {"subtask": step["subtask"], "from_css": c["from"]["css"], "to_css": c["to"]["css"],
                "from_value": o["from"], "to_value": o["to"], "from_keys": keys(o["from"]), "to_keys": keys(o["to"]),
                "native_date": native, "apply_css": (b or {}).get("css"), "apply_text": (b or {}).get("text")}

    def locate(self, driver, step):
        return driver.query(css=step["control"]["from"]["css"], limit=1) + driver.query(css=step["control"]["to"]["css"], limit=1)


# ── sliders ──────────────────────────────────────────────────────────────────

def _num(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _fmt(x):
    return str(int(x)) if float(x).is_integer() else f"{x:g}"


@register
class SliderKind(_GetKind):
    name = "slider"
    macros = {"filter_by_slider": "filter"}
    chainable = True
    # sliders are set with the pointer only (user, 2026-09-29): the executor clicks the track at the target's
    # position (on the student's 0-1000 grid, so the value is reachable by coordinates), reads the value and
    # corrects with another click; the arrow keys are forbidden (forbidden_keys)
    example = '''# example: set a range slider by clicking its track at the target position, never with keys
s = dom.one(css=task["target_css"])
if not s.in_viewport:
    s = act.scroll_into_view(s)
frac = float(task["to_fraction"])
for _ in range(3):
    act.click(s, at=(frac, 0.5))                 # the thumb jumps to where the track is clicked
    s = dom.one(css=task["target_css"])
    lo, hi = float(task["band"][0]), float(task["band"][1])
    if lo <= float(s.value) <= hi:
        break
    frac += (float(task["target"]) - float(s.value)) / (float(task["max"]) - float(task["min"]))
    frac = min(0.99, max(0.01, frac))
''' + APPLY_SNIPPET

    NO_KEYS = {"ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End"}

    def discover(self, scan, page, site):
        out = []
        for i in scan.get("inputs") or []:
            if i["type"] != "range" or not _get_form(i) or _num(i["min"]) is None or _num(i["max"]) is None:
                continue
            ctrl = {"kind": "slider", "role": "filter", "css": i["css"], "name": i["name"], "id": i["id"],
                    "apply_hint": i.get("apply_hint"),
                    "label": i["label"] or i["group_label"], "min": _num(i["min"]), "max": _num(i["max"]),
                    "step": _num(i["step"], 1.0) or 1.0, "value": _num(i["value"]), "form": i["form"], "page": page,
                    "page_title": scan["title"]}
            out.append((("slider", i["name"] or i["css"], _form_key(i, page)), ctrl))
        return out

    def arguments(self, ctrl):
        lo, hi, st = ctrl["min"], ctrl["max"], ctrl["step"]
        n = int(round((hi - lo) / st))
        if n < 2:
            return []
        picks = sorted({int(round(n * f)) for f in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)})
        cur = ctrl.get("value")
        out = []
        for k in picks:
            v = lo + k * st
            if cur is not None and abs(v - cur) < st / 2:
                continue
            out.append({"index": k, "value": _fmt(v), "text": _fmt(v)})
        return out

    def probe_argument(self, ctrl):
        args = self.arguments(ctrl)
        return args[len(args) // 2] if args else None

    def view(self, ctrl):
        v = super().view(ctrl)
        v.update({k: ctrl.get(k) for k in ("min", "max", "step", "value")})
        v.pop("options", None)
        v["n_options"] = 0
        return v

    def apply(self, page, ctrl, arg, base, ctx, log_before):
        def set_value(p):
            p.locator(ctrl["css"]).first.evaluate(
                "(el, v) => { el.value = v; el.dispatchEvent(new Event('input', {bubbles: true}));"
                " el.dispatchEvent(new Event('change', {bubbles: true})); }", arg["value"])
        return self._apply_value(page, ctrl, arg, base, ctx, log_before, set_value)

    def describe(self, ctrl):
        return {"type": "a range slider filtering the listing", "label": ctrl.get("label") or "",
                "range": [_fmt(ctrl["min"]), _fmt(ctrl["max"])], "choices": []}

    def forbidden_keys(self, step):
        return set(self.NO_KEYS)

    def dry_run(self, t, base, b):
        """Pointer-only feasibility: click the track where the target sits (on the 0-1000 grid the student
        acts on), adopt the value that click reaches as the target, and the values of the neighbouring grid
        points as the check's band (a sub-pixel difference is not a wrong answer). A mid-chain start is
        measured on the page its (GET filter) prefix leads to."""
        start_url = t["start"]["url"]
        if t["start"]["kind"] == "mid_chain":
            keep = t["start"].get("keep") or {}
            pre = ((t["start"].get("prefix") or {}).get("control") or {}).get("signature") or {}
            if pre.get("method") != "GET" or not keep:
                return False, "mid-chain slider after a prefix that is not a GET filter"
            from urllib.parse import urlencode
            start_url += ("&" if "?" in start_url else "?") + urlencode(keep)
        c, arg = t["control"], t["option"]
        ctx = B.new_context(b)
        page = ctx.new_page()
        try:
            self.setup(ctx, base, c, arg)
            B.goto_start(page, base + start_url)
            loc = page.locator(c["css"]).first
            loc.scroll_into_view_if_needed(timeout=5000)
            box = loc.bounding_box()
            if not box or box["width"] < 20:
                return False, "slider not visible"
            start = _num(loc.input_value())
            vw = page.viewport_size["width"]
            xn = round((box["x"] + self._frac(c, arg["value"]) * box["width"]) * 1000 / vw)
            y = box["y"] + box["height"] / 2
            n0 = len(B.session_log(ctx, base))

            def click_at(n):
                # a click on the thumb itself does not move it: park the thumb at the far end first, so every
                # measurement is the jump a click makes from elsewhere (as the executor and the student click)
                x = n * vw / 1000
                page.mouse.click(box["x"] + 2 if x > box["x"] + box["width"] / 2 else box["x"] + box["width"] - 2, y)
                page.mouse.click(x, y)
                B.settle(page)
                return _num(loc.input_value())
            # first, one click from the start state, as the executor and the student make it: a target under
            # the thumb's start position is unreachable by a click (2026-09-29: Max Price 9.5 of 10, thumb at 10)
            page.mouse.click(xn * vw / 1000, y)
            B.settle(page)
            first = _num(loc.input_value())
            if first is None:
                return False, "the slider has no readable value"
            if start is not None and abs(first - start) < c["step"] / 2:
                return False, "the target lies under the slider's thumb: a click there does not move it"
            vals = {n: click_at(n) for n in (xn - 1, xn + 1, xn)}     # ends on the target position
            v = vals[xn]
            if v is None:
                return False, "the slider has no readable value"
            lo, hi = min(first, *vals.values()), max(first, *vals.values())
            if start is not None and lo <= start <= hi:
                return False, "vacuous: the slider already sits at the target"
            new_arg = {**arg, "value": _fmt(v), "text": _fmt(v), "band": [_fmt(lo), _fmt(hi)],
                       "fraction": round((xn * vw / 1000 - box["x"]) / box["width"], 4)}
            e, k, mode, new = self._apply_value(page, c, new_arg, base, ctx, n0, lambda p: None)
            if not e:
                return False, "no request carried the value the pointer reached"
            chk = self.check(c, new_arg, keep=t["start"].get("keep"))
            key = next((p for p, val in chk.get("params", {}).items() if str(val) == _fmt(v)), None)
            if key and lo != hi:
                chk["params"][key] = {"value": [lo, hi], "mode": "between"}
            ok, detail = checks.evaluate(chk, B.session_log(ctx, base))
            if not ok:
                return False, "the reached value does not pass its own check: " + detail
            t["option"], t["check"] = new_arg, chk
            return True, detail
        except Exception as exc:
            return False, f"dry-run error {type(exc).__name__}: {str(exc)[:160]}"
        finally:
            ctx.close()

    def _frac(self, c, v):
        return round(min(0.98, max(0.02, (float(v) - c["min"]) / ((c["max"] - c["min"]) or 1))), 3)

    def step_spec(self, step):
        c, o = step["control"], step["option"]
        return [f"TARGET CONTROL: range slider css={c['css']!r} label={c.get('label')!r} "
                f"(min {_fmt(c['min'])}, max {_fmt(c['max'])}, step {_fmt(c['step'])}, now {c.get('value')})",
                f"SET IT TO: {o['value']} (accepted: {o.get('band', [o['value'], o['value']])[0]}"
                f"-{o.get('band', [o['value'], o['value']])[1]})",
                "HOW: click the slider's track where that value sits: at fraction (target - min)/(max - min) of its "
                "width (about " + str(o.get('fraction', self._frac(c, o['value']))) + "). Read the value; if it is off, "
                "click again a little left or right. Sliders are set with the pointer only: the keyboard is not "
                "allowed."] + _apply_lines(c)

    def script_task(self, step):
        c, o = step["control"], step["option"]
        b = c.get("apply_button") if c.get("apply") == "button" else None
        cur = c.get("value") if c.get("value") is not None else c["min"]
        return {"subtask": step["subtask"], "target_css": c["css"], "target": o["value"], "step": _fmt(c["step"]),
                "min": _fmt(c["min"]), "max": _fmt(c["max"]), "from_fraction": self._frac(c, cur),
                "to_fraction": o.get("fraction", self._frac(c, o["value"])),
                "band": o.get("band", [o["value"], o["value"]]), "apply_css": (b or {}).get("css"),
                "apply_text": (b or {}).get("text")}

    def locate(self, driver, step):
        return driver.query(css=step["control"]["css"], limit=1)


# ── search boxes ─────────────────────────────────────────────────────────────

SEARCH_NAME = re.compile(r"^(q|query|search|keyword|keywords|s|term|terms|search_query|kw|text)$", re.I)
STOP = set("the and for with from your this that into over under about more than what when where which while "
           "have has had are was were been being will would could should their there these those them they "
           "then than also only just very most much many some such each other another new all any".split())


GENERIC = set("category categories brand price rating status type date name title description details view "
              "more show filter filters sort search results total amount page home account settings".split())


def search_terms(items, limit=30):
    """Query candidates that match a listing item: 1–2 content words of item titles/cells."""
    out = []
    for h in items:
        words = [w for w in re.findall(r"[A-Za-z][A-Za-z'-]{3,}", h) if w.lower() not in STOP | GENERIC]
        if not words:
            continue
        out.append(words[0])
        if len(words) >= 2:
            out.append(f"{words[0]} {words[1]}")
    seen, res = set(), []
    for t in out:
        if t.lower() not in seen:
            seen.add(t.lower())
            res.append(t)
    return res[:limit]


@register
class SearchKind(_GetKind):
    name = "searchbox"
    macros = {"search": "search"}
    chainable = False
    example = '''# example: type a query into a search box and submit it
box = dom.one(css=task["target_css"])
if not box.in_viewport:
    box = act.scroll_into_view(box)
act.click(box)
if box.value:
    act.press("Control+a")
act.type(task["query"])
if task["apply_css"]:
    btn = dom.one(css=task["apply_css"])
    act.click(btn)
else:
    act.press("Enter")
expect.backend()'''

    def discover(self, scan, page, site):
        out = []
        for i in scan.get("inputs") or []:
            if i["type"] not in ("search", "text") or not _get_form(i) or not i["visible"]:
                continue
            if not (SEARCH_NAME.match(i["name"] or "") or re.search(r"search", i["placeholder"] + " " + i["label"], re.I)):
                continue
            terms = search_terms(scan.get("items") or [])
            if not terms:
                continue
            ctrl = {"kind": "searchbox", "role": "search", "css": i["css"], "name": i["name"], "id": i["id"],
                    "apply_hint": i.get("apply_hint"),
                    "label": i["label"] or i["placeholder"], "placeholder": i["placeholder"], "form": i["form"],
                    "options": [{"index": n, "value": t, "text": t} for n, t in enumerate(terms)],
                    "page": page, "page_title": scan["title"]}
            out.append((("searchbox", i["name"] or i["css"], _form_key(i, page)), ctrl))
        return out

    def apply(self, page, ctrl, arg, base, ctx, log_before):
        def set_value(p):
            p.fill(ctrl["css"], arg["value"], timeout=5000)
            if not (ctrl.get("form") or {}).get("submit"):
                p.locator(ctrl["css"]).first.press("Enter")
        e, k, mode, new = self._apply_value(page, ctrl, arg, base, ctx, log_before, set_value)
        if not e and not (ctrl.get("form") or {}).get("submit"):
            return None, None, None, new
        if not e:                                   # a form button exists but Enter may be enough
            page.locator(ctrl["css"]).first.press("Enter")
            B.settle(page)
            new = B.session_log(ctx, base)[log_before:]
            e, k = _sm().find_carrier(new, arg["value"], ctrl.get("name", ""))
            mode = "enter" if e else None
        return e, k, mode, new

    def describe(self, ctrl):
        return {"type": "a search box", "label": ctrl.get("label") or "", "choices": []}

    def step_spec(self, step):
        c, o = step["control"], step["option"]
        return [f"TARGET CONTROL: search field css={c['css']!r} placeholder={c.get('placeholder')!r}",
                f"QUERY TO TYPE: {o['value']!r} (exactly)",
                "SUBMIT: " + ("click the search button css=" + repr(c['apply_button']['css'])
                              if c.get("apply") == "button" and c.get("apply_button") else "press Enter")]

    def script_task(self, step):
        c, o = step["control"], step["option"]
        b = c.get("apply_button") if c.get("apply") == "button" else None
        return {"subtask": step["subtask"], "target_css": c["css"], "query": o["value"],
                "apply_css": (b or {}).get("css"), "apply_text": (b or {}).get("text")}

    def locate(self, driver, step):
        return driver.query(css=step["control"]["css"], limit=1)
