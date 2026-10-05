"""reveal_by_2fa — reveal a masked value (a full account number, a password) that the site shows
only after a one-time code is entered, then report it.

A control is a Reveal button on a page that shows masked values (dots in place of characters);
its arguments are the masked values. Nothing about the flow is hard-coded: the privileged dry
run clicks Reveal in a throw-away session, finds the one-time code in whatever message the site
just wrote (the session's data changes — an email, a chat message), enters it on the page that
asks for it, and reads what the masked element shows afterwards: that is the answer. The check
is an `answer` check whose evidence is the revealed value itself (visible only after a correct
code). The code differs every session, so the executor must fetch it from the message site with
act.open_url and read it off the page, as a person would.
"""
from __future__ import annotations

import json
import re
from urllib.parse import urlsplit

from datagen import browser as B
from datagen.kinds import register
from datagen.kinds.base import Kind

REVEAL = re.compile(r"\b(reveal|unmask|show (full|account|card|password|number|details))", re.I)
MASK = re.compile(r"[•●*]{3,}")
CODE = re.compile(r"(?<![\d#])(\d{6})(?!\d)")
CODE_INPUT = ("input[name=code], input[autocomplete=one-time-code], input[name*=code i], input[id*=code i], "
              "input[name*=pin i], input[id*=pin i], input[name*=otp i]")
SUBMIT = re.compile(r"^\s*(verify|confirm|submit|continue|unlock|reveal)\b", re.I)


def code_message(changes):
    """(code, site, row) of the message holding a fresh one-time code, from session data changes."""
    for c in changes or []:
        if c["op"] != "insert":
            continue
        blob = json.dumps(c.get("after") or {k: v[1] for k, v in c.get("changed", {}).items()}, ensure_ascii=False)
        if re.search(r"(code|pin|verification|otp)", blob, re.I):
            m = CODE.search(blob)
            if m:
                return m.group(1), c["site"], c.get("after") or {}
    return None


def code_home(site, row):
    """Where a person reads the message: a chat's conversation page when that conversation already
    exists (its id is stable), else the site's inbox/home — a conversation the site opened just now
    gets a new id in every session, so the agent finds it in the list."""
    cid = row.get("conversation_id")
    if cid:
        try:
            from app import db
            if db.get_item(site, "conversations", cid):
                return f"/sites/{site}/conversation/{cid}"
        except Exception:
            pass
    return f"/sites/{site}/"


@register
class RevealKind(Kind):
    name = "reveal"
    macros = {"reveal_by_2fa": "reveal"}
    needs_probe = False
    example = '''# example (the code is asked for on a separate page; when task["in_place"] is true a dialog asks for
# it instead: open the message site with act.open_url(task["code_home"], new_tab=True), read the code,
# act.switch_tab(0), and type it into the dialog's field)
# ask to reveal, fetch the one-time code from the message site, enter it, read the value
btn = dom.one(css=task["reveal_css"])
if not btn.in_viewport:
    btn = act.scroll_into_view(btn)
act.click(btn)
verify_path = dom.url().split("//", 1)[1].split("/", 1)[1]         # the page asking for the code
act.open_url(task["code_home"])
msg = dom.one(text=task["code_hint"])                              # the newest message with the code
digits = "".join(ch if ch.isdigit() else " " for ch in msg.text).split()
code = [d for d in digits if len(d) == 6][0]
act.open_url("/" + verify_path)
field = dom.one(css=task["code_input_css"])
act.click(field)
act.type(code)
act.click(dom.one(text=task["submit_text"], tag="button"))
value = dom.one(text=task["answer"])
if not value.in_viewport:
    act.scroll_into_view(value)
act.answer(task["answer"])
expect.backend()'''

    def discover(self, scan, page, site):
        masked = [m for m in scan.get("masked") or [] if MASK.search(m["text"])]
        if not masked:
            return []
        out = []
        for b in scan.get("buttons") or []:
            label = b["text"] or b["aria"]
            if not REVEAL.search(label) or b["region"] in ("nav", "header", "footer"):
                continue
            seen, opts = set(), []
            for m in masked:
                if m["text"] in seen:
                    continue
                seen.add(m["text"])
                opts.append({"index": len(opts), "value": m["text"], "text": m["text"], "item": m.get("item") or "",
                             "css": m["css"]})
            ctrl = {"kind": "reveal", "role": "reveal", "css": b["css"], "label": label, "name": "reveal", "id": "",
                    "options": opts[:20], "page": page, "page_title": scan["title"], "site_id": site}
            out.append((("reveal", _sm()._pattern(page), label), ctrl))
            break
        return out

    def arguments(self, ctrl):
        return [dict(o) for o in ctrl.get("options") or []]

    def element_key(self, ctrl):
        return f"REVEAL {_sm()._pattern(ctrl['page'])}"

    def view(self, ctrl):
        v = super().view(ctrl)
        v["options"] = ctrl.get("options") or []
        v["site_id"] = ctrl.get("site_id")
        return v

    def check(self, ctrl, arg, keep=None):
        return {"kind": "answer", "value": None, "alternatives": [], "evidence": [], "requires": None, "pending": True}

    def dry_run(self, t, base, b):
        """The whole flow, privileged: reveal -> the code from the message it sent -> enter it -> the
        masked element's new text. Fills the option (answer, code site, verify page) and the check."""
        c, o = t["control"], t["option"]
        ctx = B.new_context(b)
        page = ctx.new_page()
        try:
            B.goto_start(page, base + t["start"]["url"])
            before = B.session_changes(ctx, base) or []
            page.locator(c["css"]).first.click(timeout=5000)
            B.settle(page)
            verify = urlsplit(page.url)
            # the code is asked for in place (a dialog on this page): the agent reads the message in a
            # new tab and comes back to the dialog
            in_place = verify.path.rstrip("/") == urlsplit(base + t["start"]["url"]).path.rstrip("/")
            msg = code_message([x for x in B.session_changes(ctx, base) or [] if x not in before])
            if msg is None:
                return False, "no one-time code was sent in any message"
            code, site, row = msg
            field = page.locator(CODE_INPUT).locator("visible=true").first
            field.fill(code, timeout=5000)
            buttons = page.locator("button:visible, input[type=submit]:visible").filter(has_text=SUBMIT)
            submit_text = buttons.first.inner_text(timeout=3000).strip() if buttons.count() else ""
            (buttons.first if buttons.count() else field).click(timeout=5000) if buttons.count() else field.press("Enter")
            B.settle(page)
            if urlsplit(page.url).path.rstrip("/") != urlsplit(base + t["start"]["url"]).path.rstrip("/"):
                B.goto_start(page, base + t["start"]["url"])
            shown = page.locator(o["css"]).first.inner_text(timeout=5000).strip()
            if not shown or MASK.search(shown) or shown == o["text"]:
                return False, f"the value is still masked after the code: {shown!r}"
            # the text right before the code in the message ("Your VaultGuard verification PIN is:") finds it
            carrier = next((str(v) for v in row.values() if isinstance(v, str) and code in v), "")
            hint = carrier[:carrier.index(code)].strip()[-40:] if carrier else ""
            if len(hint) < 6:
                hint = next((w for w in ("Verification Code", "verification PIN", "PIN", "code") if w.lower() in
                             json.dumps(row, ensure_ascii=False).lower()), "code")
            o.update({"answer": shown, "code_site": site, "code_home": code_home(site, row), "code_hint": hint,
                      "verify_path": verify.path, "code_input_css": CODE_INPUT, "submit_text": submit_text or "Verify",
                      "in_place": in_place})
            t["check"] = {"kind": "answer", "value": shown, "alternatives": [], "evidence": [shown], "requires": None}
            return True, f"code via {site}; {o['text']} -> {shown}"
        finally:
            ctx.close()

    def open_urls(self, step):
        o = step["option"]
        return [f"/sites/{o['code_site']}/", o["verify_path"], step["control"]["page"].split("?")[0]]

    def describe(self, ctrl):
        return {"type": "a masked value the site reveals only after a one-time verification code",
                "label": ctrl.get("label") or "",
                "note": "ask for the full value of the named item (the masked text identifies it); the person "
                        "does not know the code: it arrives as a message on another site"}

    def say(self, ctrl, arg):
        return {"reveal": f"the full value shown masked as {arg['text']}", "item": arg.get("item"),
                "reply": "ask the assistant to tell the full value"}

    def mentions(self, arg):
        tail = re.sub(r".*[•●*]", "", arg["text"]).strip()
        return [tail] if tail else []

    def forbidden(self, arg):
        return [arg["answer"]] if arg.get("answer") else []

    def step_spec(self, step):
        c, o = step["control"], step["option"]
        if o.get("in_place"):
            return [f"REVEAL: click {c.get('label')!r} (css={c['css']!r}); a dialog on this page asks for a one-time code",
                    f"CODE: act.open_url({o['code_home']!r}, new_tab=True) — keep the dialog open in the first tab; "
                    f"the newest message mentioning {o['code_hint']!r} holds a 6-digit code (open its conversation "
                    f"from the list if needed, then read the digits off the page)",
                    f"BACK: act.switch_tab(0), click the dialog's code field (css={o['code_input_css']!r}, the visible "
                    f"one), type the code, click {o['submit_text']!r}",
                    f"ANSWER: the item shown as {o['text']!r} now reads {o['answer']!r} — make sure it is on screen, "
                    f"then act.answer({o['answer']!r})"]
        return [f"REVEAL: click {c.get('label')!r} (css={c['css']!r}); the site then asks for a one-time code "
                f"(page {o['verify_path']})",
                f"CODE: act.open_url({o['code_home']!r}) — the newest message mentioning {o['code_hint']!r} holds a "
                f"6-digit code (it changes every time: read it off the page); open the message if the list "
                f"does not show it",
                f"ENTER: act.open_url({o['verify_path']!r}), click the code field (css={o['code_input_css']!r}), type "
                f"the code, click {o['submit_text']!r}",
                f"ANSWER: back on {c['page']}, the item shown as {o['text']!r} now reads {o['answer']!r} — make sure it is "
                f"on screen, then act.answer({o['answer']!r})"]

    def script_task(self, step):
        c, o = step["control"], step["option"]
        return {"subtask": step["subtask"], "reveal_css": c["css"], "code_home": o["code_home"],
                "code_hint": o["code_hint"], "verify_path": o["verify_path"], "code_input_css": o["code_input_css"],
                "submit_text": o["submit_text"], "masked_text": o["text"], "answer": o["answer"],
                "in_place": bool(o.get("in_place")), "open_urls": self.open_urls(step)}

    def locate(self, driver, step):
        return driver.query(css=step["control"]["css"], limit=1)


def _sm():
    from datagen import sitemap
    return sitemap
