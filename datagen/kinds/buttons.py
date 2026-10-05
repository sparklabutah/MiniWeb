"""Buttons that change one item's state: toggles (follow, save, subscribe, join, add to cart…),
reactions (like, upvote, helpful…), deletes, play and join-meeting buttons.

A control is a FAMILY of same-label buttons on a page (every card's "Follow"); its arguments
are the family's instances, identified by the item they sit in. The backend check is not built
from a signature: the dry run clicks the instance in a throw-away session and records exactly
what changed in the site's data (checks.state_check) — an attempt must reproduce that change
and change nothing else in those collections. A button whose click changes no data but sends a
request (play counters, joins kept in the session) is checked on that request instead.
"""
from __future__ import annotations

import re

from datagen import browser as B
from datagen.kinds import register
from datagen.kinds.base import Kind

ROLES = [   # (role, label pattern) — first match wins
    ("copy", r"^(copy|copy link|copy code|copy url|copy address|copy to clipboard)\b"),
    ("share", r"^(share|share link|share post|share file|share snippet|share recipe|share this)\b"),
    ("cancel", r"^cancel (order|booking|reservation|meeting|appointment|subscription|ticket|trip|ride|flight|event|"
               r"request|registration|enrollment|class|session|transfer|payment)\b"),
    ("export", r"^(export|download|export csv|download csv|download pdf|csv|pdf|excel|json)\b"),
    ("rank", r"^(move (up|down|left|right|earlier|later|to (the )?(top|bottom|front|back))|move (item|slide|row|card|question) (up|down)|promote|demote)\b"),
    ("delete", r"^(delete|remove|trash|discard)\b"),
    ("react", r"^(like|unlike|liked|upvote|downvote|heart|love|clap|helpful|useful|funny|cool|agree|thumbs up|thumbs down)\b"),
    ("play", r"^(play|listen|resume|play episode|play now|start listening|watch now)\b"),
    ("join", r"^(join meeting|join call|join room|join now|join session|join class|join webinar)\b"),
    ("toggle", r"^(follow|unfollow|following|save|saved|unsave|bookmark|bookmarked|subscribe|subscribed|unsubscribe|"
               r"star|starred|unstar|pin|unpin|favorite|favourite|unfavorite|watch|watching|unwatch|wishlist|"
               r"add to (cart|wishlist|library|favorites|favourites|watchlist|playlist|list)|remove from (wishlist|library|favorites|watchlist|list)|"
               r"enroll|rsvp|attend|going|register|mute|unmute|block|unblock|archive|unarchive|mark as read|mark read|"
               r"mark unread|join|leave|accept|decline)\b"),
]
ROLE_MACRO = {"toggle": "toggle_relationship", "react": "feedback_by_react", "delete": "delete_from_table",
              "play": "play_by_playback", "join": "join_meeting", "copy": "copy_content", "export": "export",
              "share": "share_by_form", "cancel": "cancel_by_form", "rank": "edit_by_ranking"}
PER_PAGE = {"rank", "play", "cancel", "export", "join", "copy", "share"}
NEVER = re.compile(r"(log ?out|sign ?out|delete (my )?account|clear all|delete all|remove all|reset|empty (cart|trash))", re.I)


def family(text):
    """'♥ Like (12)' -> 'like'; 'Follow' -> 'follow'; 'Delete message' -> 'delete message'."""
    t = re.sub(r"[\d()\[\]{}|•·,:+#%]+", " ", str(text or "").lower())
    t = re.sub(r"[^\w\s'&-]", " ", t)
    return " ".join(t.split()[:4])


def role_of(fam):
    for role, pat in ROLES:
        if re.search(pat, fam):
            return role
    return None


def _page_item(scan, site, title=False):
    """The item a detail page is about: its <h1>, unless that is only the site's name in the header. With
    title=True (the last fallback, after the button's own item), the document title without the site-name part:
    'Upgrade the Playground - Lakeport Civic Hub' -> 'Upgrade the Playground'. 2026-09-29: a Copy button was
    named after the site's logo heading."""
    brand = (B.site_name(site) or "").strip().lower()
    h1 = (scan.get("h1") or "").strip()
    if not title:
        return h1 if h1.lower() != brand else ""
    parts = [x.strip() for x in re.split(r"\s+[-|\u2014\u2013:]\s+", scan.get("title") or "") if x.strip()]
    parts = [x for x in parts if x.lower() != brand]
    return parts[0] if parts else ""


@register
class ButtonKind(Kind):
    name = "button"
    macros = {m: r for r, m in ROLE_MACRO.items()}
    oracle = True               # the dry run records the check (checks.state_check)
    example = '''# example: click one item's button once (it toggles/acts immediately), confirm if asked
btn = dom.one(css=task["target_css"])
if not btn.in_viewport:
    btn = act.scroll_into_view(btn)
act.click(btn)
if task["confirm_text"]:
    ok = dom.one(text=task["confirm_text"], tag="button")    # the confirmation dialog's button
    act.click(ok)
expect.backend()'''

    def discover(self, scan, page, site):
        from annotation.macro_locations import MACRO_LOCATIONS
        site_macros = MACRO_LOCATIONS.get(site) or {}
        fams = {}
        for b in scan.get("buttons") or []:
            label = b["text"] if family(b["text"]) else b["aria"]      # icon buttons ("×", 🗑) name themselves in aria-label
            fam = family(label)
            if not fam or len(fam) > 40 or NEVER.search(label) or b["region"] in ("nav", "header", "footer"):
                continue
            if b.get("form") and b["form"].get("fields", 0) > 0:
                continue                     # a button of a form with fields: a form macro, not a toggle
            role = role_of(fam)
            if role is None:
                continue
            if role == "toggle" and fam.startswith("join") and "join_meeting" in site_macros and "toggle_relationship" not in site_macros:
                role = "join"
            fams.setdefault((fam, role), []).append(b)
        out = []
        for (fam, role), items in fams.items():
            opts, seen = [], set()
            for b in items:
                # a lone button acts on the page's own item (a detail page): its heading names it
                lone = len(items) == 1
                own = (b.get("item") or "").strip()
                own = "" if own.lower() == (B.site_name(site) or "").strip().lower() else own   # the scan's h1 fallback
                item = ((_page_item(scan, site) if lone else None) or own
                        or (_page_item(scan, site, title=True) if lone else None) or "").strip()
                if not item or item in seen:
                    continue
                seen.add(item)
                opts.append({"index": len(opts), "value": item, "text": item, "css": b["css"],
                             "button_text": b["text"] or b["aria"]})
            if not opts:
                continue
            ctrl = {"kind": "button", "role": role, "family": fam, "css": opts[0]["css"], "name": fam, "id": "",
                    "label": items[0]["text"] or items[0]["aria"], "options": opts[:40], "page": page,
                    "page_title": scan["title"]}
            # item actions on detail pages differ per page (each slide deck, article, meeting); list-page
            # families repeat on every listing page and are kept once per URL pattern
            where = page if role in PER_PAGE else _sm()._pattern(page)
            out.append((("button", fam, role, where), ctrl))
        return out

    def arguments(self, ctrl):
        # site maps crawled before 2026-09-29 named a lone button after the site's own heading (the scan's h1
        # fallback): rename it from the page title; among several items, a site-named one is unnamed: dropped
        page = ctrl.get("page") or ""
        site = page.split("/")[2] if page.startswith("/sites/") else ""
        brand = (B.site_name(site) or "").strip().lower() if site else ""
        opts = [dict(o) for o in ctrl.get("options") or []]
        if brand and len(opts) == 1 and str(opts[0]["value"]).strip().lower() == brand:
            name = _page_item({"title": ctrl.get("page_title")}, site, title=True)
            opts = [dict(opts[0], value=name, text=name)] if name else []
        elif brand:
            opts = [o for o in opts if str(o["value"]).strip().lower() != brand]
        return opts

    def probe_argument(self, ctrl):
        opts = ctrl.get("options") or []
        return opts[len(opts) // 2] if opts else None

    def view(self, ctrl):
        v = super().view(ctrl)
        v["family"] = ctrl.get("family")
        v["confirm"] = ctrl.get("confirm")
        v["confirm_text"] = ctrl.get("confirm_text")
        v["options"] = [{k: o.get(k) for k in ("index", "value", "text", "css", "button_text")} for o in ctrl.get("options") or []]
        return v

    def element_key(self, ctrl):
        sig = ctrl["signature"]
        where = ctrl["page"] if ctrl.get("role") in PER_PAGE else _sm()._pattern(sig["path"])
        return f"{sig['method']} {where} {ctrl.get('family')}"

    def dedup_value(self, arg):
        return arg["value"]

    def apply(self, page, ctrl, arg, base, ctx, log_before):
        page.once("dialog", lambda d: d.accept())
        page.locator(arg["css"]).first.click(timeout=5000)
        B.settle(page)
        mode = "none"
        conf = page.locator("dialog[open] button, [role=dialog] button, [role=alertdialog] button, .modal button, "
                            "[class*=modal] button, [class*=confirm] button").filter(
            has_text=re.compile(r"^\s*(delete|confirm|yes|ok|remove|continue|unfollow|leave)\b", re.I))
        try:
            if conf.count() and conf.first.is_visible():
                ctrl["confirm_text"] = conf.first.inner_text().strip()[:40]
                conf.first.click(timeout=5000)
                B.settle(page)
                mode = "modal"
        except Exception:
            pass
        ctrl["confirm"] = mode
        new = B.session_log(ctx, base)[log_before:]
        acc = [e for e in new if isinstance(e.get("status"), int) and 200 <= e["status"] < 400]
        muts = [e for e in acc if (e.get("method") or "GET").upper() != "GET"]
        api = [e for e in acc if "/api/" in (e.get("path") or "")]
        dls = [e for e in acc if "attachment" in str((e.get("response_headers") or {}).get("content-disposition", "")).lower()]
        clip = B.clipboard_writes(ctx, base) if ctrl.get("role") in ("copy", "share") else []
        e = (dls or muts or api or [None])[-1]
        if e is None and clip:                          # a copy button: no request, the clipboard is the evidence
            e = {"method": "GET", "path": ctrl["page"], "status": 200, "query": {}}
        return (e, None, "click", new) if e else (None, None, None, new)

    def check(self, ctrl, arg, keep=None):
        return {"kind": "state", "pending": True}     # recorded by the dry run

    def observed_check(self, ev, site, ctrl=None):
        role = (ctrl or {}).get("role")
        if role == "share" and ev.get("clipboard"):         # a Share button that copies the link
            return {"kind": "clipboard", "value": ev["clipboard"][-1]}
        if role == "copy":
            return {"kind": "clipboard", "value": ev["clipboard"][-1]} if ev.get("clipboard") else None
        if role == "export":
            dl = [e for e in ev["requests"] if "attachment" in str((e.get("response_headers") or {}).get("content-disposition", "")).lower()]
            e = (dl or ([x for x in ev["requests"] if (x.get("method") or "GET") == "GET"] if ev.get("downloads") else []) or [None])[-1]
            if e is None:
                return None
            return {"kind": "request", "method": "GET", "path": e["path"],
                    "params": {k: v for k, v in (e.get("query") or {}).items() if not re.search(r"(_ts|token|nonce)$", k)},
                    "keep": {}, "final": False}
        return super().observed_check(ev, site, ctrl)

    def request_check(self, entry):
        """Fallback when the click changes no stored data: the request it sent."""
        return {"kind": "request", "method": entry["method"].upper(), "path": entry["path"], "params": {},
                "keep": {}, "final": False}

    def describe(self, ctrl):
        what = {"toggle": "a toggle button", "react": "a reaction button", "delete": "a delete button",
                "play": "a play button", "join": "a join button", "copy": "a copy button",
                "export": "an export/download button", "share": "a share button",
                "cancel": "a cancel button", "rank": "a button that moves an item up/down in its order"}[ctrl["role"]]
        return {"type": f"{what} labelled {ctrl.get('label')!r}, one per item", "label": ctrl.get("label") or "",
                "choices": [o["text"] for o in ctrl.get("options", [])][:10],
                "note": "name the item by its visible title; say what to do to it (e.g. follow, like, delete, play)"}

    def say(self, ctrl, arg):
        return {"button": arg.get("button_text") or ctrl.get("label"), "item": arg["text"]}

    def mentions(self, arg):
        words = arg["text"].split()
        return [" ".join(words[:6])] if words else []

    def step_spec(self, step):
        c, o = step["control"], step["option"]
        lines = [f"TARGET: the {o.get('button_text') or c.get('label')!r} button of the item {o['text']!r} "
                 f"(css={o['css']!r}) — click it exactly ONCE (a second click undoes it)"]
        if c.get("confirm") == "modal":
            lines.append(f"CONFIRM: a confirmation dialog opens — click its {c.get('confirm_text', 'OK')!r} button")
        elif c["role"] == "delete":
            lines.append("CONFIRM: a browser confirm() may pop up; it is accepted automatically")
        return lines

    def script_task(self, step):
        c, o = step["control"], step["option"]
        return {"subtask": step["subtask"], "target_css": o["css"], "item_text": o["text"],
                "button_text": o.get("button_text") or c.get("label"),
                "confirm_text": c.get("confirm_text") if c.get("confirm") == "modal" else None}

    def locate(self, driver, step):
        return driver.query(css=step["option"]["css"], limit=1)


def _sm():
    from datagen import sitemap
    return sitemap
