"""Forms: fill fields and submit (create, edit, configure, share, pay, book, checkout, cancel,
sign in, message, review, typed signature, translate, directions, join by code …).

A control is one form (a <form>, or a scripted panel's fields sharing an Apply/Submit button);
its role — which macro it serves — comes from the submit label, the action path and the page
heading. Arguments are value sets (datagen/formvalues.py): an LLM proposes them once per form,
sign-in forms use the site's real accounts. The check is recorded by the dry run: the data the
submission changes (checks.state_check), else — sign-in, a translation — the request it sent
with the entered values.
"""
from __future__ import annotations

import hashlib
import json
import re

from datagen import browser as B
from datagen import formvalues as FV
from datagen.kinds import register
from datagen.kinds.base import Kind

# (macro, pattern over "submit text | action path | heading | page title"), first match wins
ROLES = [
    ("authenticate_by_form", r"\b(log ?in|sign ?in)\b"),
    ("checkout_by_form", r"\b(checkout|check out|place (your )?order|complete (purchase|order)|buy now|promo|coupon|"
                         r"redeem|discount code)\b"),
    ("pay_by_form", r"\b(pay|payment|transfer|send money|pay bill)\b"),
    ("share_by_form", r"\b(share|invite)\b"),
    ("book_by_form", r"\b(book|reserve|reservation|appointment)\b"),
    ("cancel_by_form", r"\bcancel\b"),
    ("translate_by_query", r"\btranslat"),
    ("get_nav_route", r"\b(directions|route|navigate)\b"),
    ("join_meeting", r"\bjoin\b"),
    ("sign_by_text", r"\b(sign|signature|adopt)\b"),
    ("feedback_by_text", r"\b(review|feedback)\b"),
    ("message_from_free_text", r"\b(send|reply|message|comment|chat)\b"),
    ("configure_by_form", r"\b(settings|preferences|configure|notification)\b"),
    ("edit_by_form", r"\b(update|save changes|edit)\b"),
    ("create_by_form", r"\b(create|add|new|post|publish|submit|save|register|apply|compose|schedule|upload)\b"),
]
FORM_MACROS = [m for m, _ in ROLES]
TEXTY = {"text", "email", "number", "tel", "url", "password", "search", "textarea", "time", "month", "week"}
SKIP_FORM = re.compile(r"(log ?out|sign ?out|delete (my )?account|search)", re.I)
MAX_FIELDS = 12


def role_of(blob, site_macros):
    """The form's macro. `blob` is "submit | action | heading | title": the most specific part that
    names a role decides (a Translation site's export form is an export, not a translation)."""
    for part in str(blob).split(" | "):
        hits = [m for m, pat in ROLES if re.search(pat, part, re.I)]
        if hits:
            listed = [m for m in hits if m in site_macros]
            return (listed or hits)[0]
    return None


def _fields(inputs, selects):
    """Form fields from the scan: radio groups become one field with options."""
    out, radios = [], {}
    for i in inputs:
        t = i["type"]
        if t in ("hidden", "submit", "button", "image", "reset", "file"):
            continue
        if t == "radio":
            radios.setdefault(i["name"] or i["css"], []).append(i)
            continue
        f = {"css": i["css"], "type": "date" if t == "date" else ("checkbox" if t == "checkbox" else ("range" if t == "range" else
             ("textarea" if t == "textarea" else ("text" if t not in TEXTY else t)))),
             "name": i["name"], "label": i["label"] or i["option_text"] or i["placeholder"], "placeholder": i["placeholder"],
             "value": i["value"], "checked": i["checked"], "min": i["min"], "max": i["max"], "label_css": i["label_css"],
             "visible": i["visible"]}
        out.append(f)
    for name, group in radios.items():
        out.append({"css": group[0]["css"], "type": "radio", "name": group[0]["name"],
                    "label": group[0]["group_label"] or name, "value": next((g["value"] for g in group if g["checked"]), ""),
                    "options": [{"index": n, "value": g["value"], "text": g["option_text"] or g["value"], "css": g["css"],
                                 "label_css": g["label_css"], "visible": g["visible"]} for n, g in enumerate(group)]})
    for s in selects:
        out.append({"css": s["css"], "type": "select", "name": s["name"], "label": s["label"] or s["placeholder"],
                    "value": next((o["text"] for o in s["options"] if o["index"] == s["selected_index"]), ""),
                    "options": [{"index": o["index"], "value": o["value"], "text": o["text"]} for o in s["options"]
                                if not o.get("disabled")]})
    return out


@register
class FormKind(Kind):
    name = "form"
    macros = {m: m for m in FORM_MACROS}
    oracle = True
    example = '''# example: fill each field as given, then submit the form
for f in task["fields"]:
    el = dom.one(css=f["css"]) if f["visible"] else dom.one(css=f["label_css"])
    if not el.in_viewport:
        el = act.scroll_into_view(el)
    if f["type"] == "select":
        act.click(el)                                  # opens the native option list
        act.type(f["option_text"])                     # type-ahead to the option
        act.press("Enter")
    elif f["type"] in ("radio", "checkbox"):
        act.click(el)
    elif f["type"] == "date":
        act.click(el, at=(0.12, 0.5))                  # month segment of a native date input
        act.type(f["keys"])                            # MMDDYYYY
    else:
        act.click(el)
        if el.value:
            act.press("Control+a")                     # replace what is there
        act.type(f["value"])
btn = dom.one(css=task["submit_css"])
if not btn.in_viewport:
    btn = act.scroll_into_view(btn)
act.click(btn)
expect.backend()'''

    def discover(self, scan, page, site):
        from annotation.macro_locations import MACRO_LOCATIONS
        site_macros = MACRO_LOCATIONS.get(site) or {}
        groups = {}
        for i in scan.get("inputs") or []:
            host = (i.get("form") or {}).get("css") or ((i.get("apply_hint") or {}).get("css") and "hint:" + i["apply_hint"]["css"])
            if host:
                groups.setdefault(host, {"inputs": [], "selects": [], "form": i.get("form"), "hint": i.get("apply_hint")})["inputs"].append(i)
        for s in scan.get("selects") or []:
            host = (s.get("form") or {}).get("css") or ((s.get("apply_hint") or {}).get("css") and "hint:" + s["apply_hint"]["css"])
            if host:
                groups.setdefault(host, {"inputs": [], "selects": [], "form": s.get("form"), "hint": s.get("apply_hint")})["selects"].append(s)
        out = []
        for host, g in groups.items():
            form = g["form"]
            submit = (form or {}).get("submit") or g["hint"]
            if not submit or any(i["type"] == "file" for i in g["inputs"]):
                continue                                # no submit, or an upload (upload_file's own kind)
            fields = _fields(g["inputs"], g["selects"])
            if not fields or len(fields) > MAX_FIELDS:
                continue
            method = (form or {}).get("method", "post")
            blob = " | ".join([submit.get("text") or "", (form or {}).get("action", ""), scan.get("h1") or "", scan["title"]])
            if SKIP_FORM.search(submit.get("text") or ""):
                continue
            # a GET form's role must come from its own submit label or action, never the page title
            role = role_of(blob if method != "get" else " | ".join(blob.split(" | ")[:2]), site_macros)
            if role is None:
                continue
            if method == "get" and role not in ("translate_by_query", "get_nav_route", "join_meeting", "authenticate_by_form"):
                continue                                # GET forms narrow listings: the filter kinds' job
            if role == "authenticate_by_form" and not any(f["type"] == "password" for f in fields):
                continue
            ctrl = {"kind": "form", "role": role, "macro": role, "css": fields[0]["css"], "name": host, "id": "",
                    "label": scan.get("h1") or scan["title"], "heading": scan.get("h1") or "", "fields": fields,
                    "submit": {"css": submit["css"], "text": submit.get("text") or ""}, "form": form,
                    "context": (scan.get("items") or [])[:25], "site_id": site, "page": page, "page_title": scan["title"]}
            out.append((("form", role, host, _sm()._pattern(page)), ctrl))
        return out

    # ── arguments: value sets ──────────────────────────────────────────────
    def arguments(self, ctrl):
        site = ctrl.get("site_id") or ctrl["page"].split("/")[2]
        if ctrl["role"] == "authenticate_by_form":
            return [self._login_arg(ctrl, a, n) for n, a in enumerate(FV.accounts(site)[:8])]
        sets = ctrl.get("value_sets")
        want = ctrl.get("_k") or FV.K
        if sets is None or (len(sets) < want and ctrl.get("_topped_up") != want):
            ctrl["_topped_up"] = None                          # (a saved map may carry an older size)
            sets = FV.value_sets(ctrl, site, k=want)          # cached; tops up older, smaller caches
            ctrl["value_sets"], ctrl["_topped_up"] = sets, want
        out = []
        for n, s in enumerate(sets):
            vals = _changed(ctrl, s["values"])
            if vals:
                out.append(self._arg(ctrl, vals, s.get("summary", ""), n))
        return out

    def has_arguments(self, ctrl):
        if ctrl["role"] == "authenticate_by_form":
            return bool(FV.accounts(ctrl.get("site_id") or ctrl["page"].split("/")[2]))
        return ctrl.get("value_sets") != []          # unknown until generated: assume yes

    def _login_arg(self, ctrl, acct, n):
        vals = {}
        for f in ctrl["fields"]:
            if f["type"] == "password":
                vals[FV.field_key(f)] = acct["password"]
            elif f["type"] in ("text", "email") and not vals.get("_login"):
                # "Email or Username" fields take the username: several sites look sign-ins up by it only
                mail = f["type"] == "email" or ("mail" in (f["name"] or "").lower() and "user" not in (f["name"] or "").lower())
                use = acct["email"] if mail and acct["email"] else acct["login"]
                vals[FV.field_key(f)] = use
                vals["_login"] = use
        vals.pop("_login", None)
        return self._arg(ctrl, vals, f"sign in as {acct['login']}", n)

    def _arg(self, ctrl, values, summary, n):
        h = hashlib.sha1(json.dumps(values, sort_keys=True).encode()).hexdigest()[:10]
        return {"index": n, "value": h, "text": summary or ", ".join(values.values())[:80], "values": values}

    def probe_argument(self, ctrl):
        args = self.arguments(ctrl)
        return args[0] if args else None

    def element_key(self, ctrl):
        action = (ctrl.get("form") or {}).get("action") or ctrl["page"]
        return f"FORM {ctrl['role']} {_sm()._pattern(re.sub(r'^https?://[^/]+', '', action))}"

    def dedup_value(self, arg):
        return arg["value"]

    def view(self, ctrl):
        v = super().view(ctrl)
        v.update({k: ctrl.get(k) for k in ("fields", "submit", "heading", "macro")})
        v.pop("options", None)
        return v

    def setup(self, ctx, base, ctrl, arg=None):
        from datagen.kinds.base import prepare
        prepare(ctx, base, ctrl)
        if ctrl["role"] == "authenticate_by_form":         # 2FA codes are their own macro (reveal_by_2fa)
            B.session_flags(ctx, base, logout=True, disable_2fa=True)
        elif ctrl["role"] in ("pay_by_form", "checkout_by_form", "book_by_form"):
            B.session_flags(ctx, base, disable_2fa=True)

    # ── privileged fill + submit ───────────────────────────────────────────
    def apply(self, page, ctrl, arg, base, ctx, log_before):
        page.once("dialog", lambda d: d.accept())
        for f in ctrl["fields"]:
            v = arg["values"].get(FV.field_key(f))
            if v is None:
                continue
            if f["type"] == "select":
                o = FV.option_for(f, v)
                if o:
                    page.select_option(f["css"], value=o["value"], timeout=5000)
            elif f["type"] == "radio":
                o = FV.option_for(f, v)
                if o:
                    loc = page.locator(o["css"]).first
                    loc.scroll_into_view_if_needed(timeout=3000)
                    loc.check(timeout=5000, force=True)
            elif f["type"] == "checkbox":
                want = str(v).strip().lower() in ("1", "true", "yes", "on", "checked")
                loc = page.locator(f["css"]).first
                loc.scroll_into_view_if_needed(timeout=3000)
                loc.set_checked(want, timeout=5000, force=True)
            elif f["type"] == "range":
                page.locator(f["css"]).first.evaluate("(el, v) => { el.value = v; el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); }", v)
            else:
                page.fill(f["css"], v, timeout=5000)
        page.locator(ctrl["submit"]["css"]).first.click(timeout=5000)
        B.settle(page)
        new = B.session_log(ctx, base)[log_before:]
        if ctrl["role"] == "authenticate_by_form" and _still_signed_out(page, ctrl):
            return None, None, None, new             # rejected credentials re-render the form (often with a 200)
        acc = [e for e in new if isinstance(e.get("status"), int) and 200 <= e["status"] < 400]
        muts = [e for e in acc if (e.get("method") or "GET").upper() != "GET"]
        gets = [e for e in acc if (e.get("method") or "GET").upper() == "GET" and any(
            _sm().find_carrier([e], v)[0] for v in arg["values"].values())]
        e = (muts or gets or [None])[-1]
        return (e, None, "submit", new) if e else (None, None, None, new)

    def check(self, ctrl, arg, keep=None):
        return {"kind": "state", "pending": True}

    def request_check(self, entry):
        """No data change (sign-in, translation): the request, with the entered values it carries."""
        fields = {}
        fields.update(entry.get("query") or {})
        if isinstance(entry.get("body"), dict):
            fields.update({k: v for k, v in entry["body"].items() if isinstance(v, (str, int, float))})
        secret = re.compile(r"(csrf|token|nonce|_ts$|timestamp)", re.I)
        return {"kind": "request", "method": entry["method"].upper(), "path": entry["path"],
                "params": {k: v for k, v in fields.items() if not secret.search(k) and str(v).strip()}, "keep": {},
                "final": False}

    # ── wording ────────────────────────────────────────────────────────────
    def describe(self, ctrl):
        return {"type": f"a form ({ctrl.get('heading') or ctrl.get('page_title')})", "label": ctrl["submit"].get("text"),
                "fields": [f.get("label") or f.get("name") for f in ctrl["fields"]], "choices": [],
                "note": "state every value to enter exactly as given (quote free text); do not add values"}

    def say(self, ctrl, arg):
        lab = {FV.field_key(f): (f.get("label") or f.get("name") or "field") for f in ctrl["fields"]}
        return {lab.get(k, k): _human(v) for k, v in arg["values"].items()}

    def mentions(self, arg):
        out = []
        for v in arg["values"].values():
            v = _human(str(v))
            words = v.split()
            if not words:
                continue
            out.append(v if len(words) <= 6 else " ".join(words[:6]))
        return out

    def _field_task(self, f, v):
        t = {"css": f["css"], "type": f["type"], "value": str(v), "visible": bool(f.get("visible", True)),
             "label_css": f.get("label_css"), "label": f.get("label")}
        if f["type"] in ("select", "radio"):
            o = FV.option_for(f, v) or {}
            t.update(option_text=o.get("text", str(v)), option_index=o.get("index"))
            if f["type"] == "radio" and o.get("css"):
                t.update(css=o["css"], label_css=o.get("label_css"), visible=bool(o.get("visible", True)))
        if f["type"] == "date" and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(v)):
            t["keys"] = f"{v[5:7]}{v[8:10]}{v[0:4]}"
        return t

    def step_spec(self, step):
        c, o = step["control"], step["option"]
        lines = [f"TARGET: the form {c.get('heading') or c.get('page_title')!r}, submit button css={c['submit']['css']!r} "
                 f"text={c['submit'].get('text')!r}", "FIELDS TO FILL (leave all others as they are):"]
        for f in c["fields"]:
            v = o["values"].get(FV.field_key(f))
            if v is not None:
                lines.append(f"  - {f.get('label') or f.get('name')!r} ({f['type']}, css={f['css']!r}) = {v!r}")
        return lines

    def script_task(self, step):
        c, o = step["control"], step["option"]
        fields = [self._field_task(f, o["values"][FV.field_key(f)]) for f in c["fields"]
                  if FV.field_key(f) in o["values"]]
        return {"subtask": step["subtask"], "fields": fields, "submit_css": c["submit"]["css"],
                "submit_text": c["submit"].get("text")}

    def locate(self, driver, step):
        return driver.query(css=step["control"]["submit"]["css"], limit=1)


def _changed(ctrl, values):
    """Only what the step changes: an edit/settings form's value set repeats the fields it leaves
    as they are; those are neither entered nor worded (the check records what really changed)."""
    cur = {FV.field_key(f): str(f.get("value") or "").strip() for f in ctrl["fields"]}
    return {k: v for k, v in values.items() if str(v).strip() != cur.get(k, None)}


def _still_signed_out(page, ctrl):
    """After a sign-in submit: the same page still asks for a password, or shows an error."""
    try:
        if page.locator("input[type=password]:visible").count() and _sm()._pattern(page.url.split("?")[0].replace(
                re.match(r"^https?://[^/]+", page.url).group(0), "")) == _sm()._pattern(ctrl["page"]):
            return True
        return bool(page.get_by_text(re.compile(r"(invalid|incorrect|wrong) (username|password|credentials|email)", re.I)).count())
    except Exception:
        return False


def _human(v):
    """ISO dates in words (the executor still types the digits)."""
    import calendar
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", str(v))
    return f"{calendar.month_name[int(m[2])]} {int(m[3])}, {m[1]}" if m and 1 <= int(m[2]) <= 12 else str(v)


def _sm():
    from datagen import sitemap
    return sitemap
