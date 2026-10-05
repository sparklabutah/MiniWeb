"""The Kind interface (see datagen/kinds/__init__.py)."""
from __future__ import annotations

import re

from datagen import checks

_PLACEHOLDER = re.compile(r"^(all|any|none|select|choose|--|—|-|default|sort|all\s.*|any\s.*|select\s.*|choose\s.*)$", re.I)


def clip(s, n):
    s = str(s or "")
    return s if len(s) <= n else s[:n] + "…"


def prepare(ctx, base, ctrl):
    """Replay a control's recorded session preparation (unrecorded, privileged)."""
    prep = ctrl.get("prep") or {}
    if prep.get("add_to_cart"):
        from datagen import sitemap
        sitemap.add_to_cart(ctx, base, prep["add_to_cart"])


class Kind:
    name = ""                 # ctrl["kind"]
    macros: dict = {}         # macro -> role a control of this kind plays for it
    listing = False           # a GET control that narrows/orders a listing (site-map refine applies)
    chainable = False         # can be a preset / mid-chain companion of another control on its page
    needs_probe = True        # the site-map probe applies an argument to find the backend signature
    example = ""              # executor example script (a different page)

    # ── crawl time ──────────────────────────────────────────────────────────
    def discover(self, scan, page, site):
        """Controls of this kind in a read-only page scan: [(dedup key, ctrl)]."""
        return []

    def serves(self, ctrl, macro):
        """Can this control be the target of `macro` (default: its role is the macro's role)?"""
        role = self.macros.get(macro)
        return role is not None and role == ctrl.get("role", role)

    # ── sampling ────────────────────────────────────────────────────────────
    def arguments(self, ctrl):
        """Candidate arguments of a control: dicts with at least `value` and `text`."""
        out = []
        for o in ctrl.get("options") or []:
            v, t = str(o.get("value", "")).strip(), (o.get("text") or "").strip()
            if not v or not t or o.get("disabled") or o.get("active") or o["index"] == ctrl.get("selected_index", -1):
                continue
            if _PLACEHOLDER.match(t):
                continue
            out.append({"index": o["index"], "value": o["value"], "text": t, **({"href": o["href"]} if o.get("href") else {})})
        return out

    def static_probe(self, ctrl):
        """Kinds with needs_probe=False: mark the control usable (or not) without a browser."""
        ctrl["signature"] = {"method": "GET", "path": ctrl["page"].split("?")[0], "param": None}
        ctrl["usable"] = True

    def arguments_for(self, ctrl, macro):
        """The arguments of a control when it is the target of `macro` (default: all of them)."""
        return self.arguments(ctrl)

    def has_arguments(self, ctrl):
        """Cheap: can this control yield any argument (candidate listing must not generate them)."""
        return bool(self.arguments(ctrl))

    def probe_argument(self, ctrl):
        """The argument the site-map probe applies (a non-default one, from the middle)."""
        opts = [o for o in ctrl.get("options") or [] if str(o.get("value", "")).strip() and not o.get("disabled")
                and o["index"] != ctrl.get("selected_index", -1)]
        return opts[len(opts) // 2] if opts else None

    def dedup_value(self, arg):
        return str(arg["value"])

    def element_key(self, ctrl):
        """The control's backend identity "METHOD path param" (stable across re-crawls)."""
        s = ctrl["signature"]
        return " ".join(x for x in (s["method"], s["path"], s.get("param") or "") if x)

    def view(self, ctrl):
        """What later stages need to know about a control (no crawl noise)."""
        keep = ("control_id", "kind", "role", "css", "name", "id", "label", "placeholder", "page", "page_title",
                "apply", "signature", "selected_index", "opener", "prep")
        v = {k: ctrl.get(k) for k in keep if k in ctrl}
        v["apply_button"] = (((ctrl.get("form") or {}).get("submit") or ctrl.get("apply_hint"))
                             if ctrl.get("apply") == "button" else None)
        v["options"] = [{"index": o["index"], "value": o["value"], "text": o.get("text", "")}
                        for o in ctrl.get("options") or []][:60]
        v["n_options"] = len(ctrl.get("options") or [])
        return v

    def check(self, ctrl, arg, keep=None):
        return checks.build_check(ctrl["signature"], arg["value"], keep=keep)

    def observed_check(self, ev, site, ctrl=None):
        """Oracle kinds: the check from what a privileged run of the step produced —
        ev = {entry, requests, changes, clipboard, downloads}. Default: the data it changed,
        else the request it sent."""
        chk = checks.state_check(ev["changes"], site, ev["requests"])
        if chk is None and ev.get("entry") is not None and hasattr(self, "request_check"):
            chk = self.request_check(ev["entry"])
        return chk

    def changes_site(self, t):
        """The site whose data a step of this kind changes (the oracle records its changes)."""
        return t["site"]

    def open_urls(self, step):
        """Site paths the step may open through the address bar (act.open_url). Default: none."""
        return []

    def forbidden_keys(self, step):
        """Keys the executor may not press during this step (e.g. sliders are set by pointer only)."""
        return set()

    def files(self, step):
        """Files the step may upload: {path shown to the agent: absolute path}."""
        return {}

    # ── privileged setup before the start page (probe, dry run, every attempt) ─
    def setup(self, ctx, base, ctrl, arg=None):
        """Unrecorded session preparation, e.g. logged-out start, 2FA off. Default: the control's
        recorded preparation (an item in the cart for a checkout page)."""
        prepare(ctx, base, ctrl)

    # ── privileged application (probe, dry run) ─────────────────────────────
    def apply(self, page, ctrl, arg, base, ctx, log_before):
        """Apply `arg` with privileged Playwright calls. -> (carrier entry, param, apply mode, new entries)."""
        raise NotImplementedError

    # ── wording ─────────────────────────────────────────────────────────────
    def describe(self, ctrl):
        return {"type": self.name, "label": ctrl.get("label") or ctrl.get("placeholder") or "",
                "choices": [o["text"] for o in ctrl.get("options", [])][:12]}

    def mentions(self, arg):
        """Visible texts the instruction must mention."""
        return [arg["text"]]

    def forbidden(self, arg):
        """Texts the instruction must NOT contain (an answer it would give away)."""
        return []

    def dry_run(self, t, base, b):
        """A kind's own feasibility check -> (ok, detail), or None for the generic one."""
        return None

    def say(self, ctrl, arg):
        """What the suggester is told to ask for (the argument in words or as label: value)."""
        return arg["text"]

    # ── executor ────────────────────────────────────────────────────────────
    def step_spec(self, step):
        raise NotImplementedError

    def script_task(self, step):
        raise NotImplementedError

    def locate(self, driver, step):
        """Privileged lookup of the step's target on the live page: [(key, info)]."""
        return []
