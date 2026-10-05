"""Out-of-page I/O: upload a file from the user's file system (upload_file).

The argument is a file from the simulated file system (the same tree the eval agents get),
matching the input's `accept`, plus values for the form's other fields when it has any. The
executor clicks the input (or the button/label that opens it) and picks the file in the file
chooser — `act.upload`. The check is recorded by the dry run (the data the upload changes,
else the request that carried the file)."""
from __future__ import annotations

import os
import re

from datagen import browser as B
from datagen import formvalues as FV
from datagen.kinds import register
from datagen.kinds.base import Kind
from datagen.kinds.forms import FormKind, _fields

KINDS_BY_ACCEPT = [("image", r"\.(png|jpe?g|gif|webp|bmp|svg)$"), ("pdf", r"\.pdf$"), ("audio", r"\.(mp3|wav|m4a|ogg)$"),
                   ("video", r"\.(mp4|mov|webm)$"), ("csv", r"\.(csv|xlsx?)$"), ("text", r"\.(txt|md|docx?|rtf)$")]


def _vfs():
    from evaluation.generate_fixtures import VFS_DIR, ensure_fixtures
    return VFS_DIR, ensure_fixtures()


def files_for(accept, limit=12):
    """{path shown to the agent: absolute path} of fixture files the input accepts."""
    root, paths = _vfs()
    acc = (accept or "").lower()
    out = {}
    for p in paths:
        rel = os.path.relpath(p, root)
        name = rel.lower()
        ok = not acc or any(
            (a.startswith(".") and name.endswith(a)) or (a.endswith("/*") and re.search(dict(KINDS_BY_ACCEPT).get(a[:-2], "$^"), name))
            or (a in name) for a in [x.strip() for x in acc.split(",") if x.strip()])
        if ok:
            out[rel] = p
        if len(out) >= limit:
            break
    return out


@register
class UploadKind(Kind):
    name = "upload"
    macros = {"upload_file": "upload"}
    oracle = True
    example = '''# example: choose a file for an upload control, fill the rest, submit
trig = dom.one(css=task["trigger_css"])
if not trig.in_viewport:
    trig = act.scroll_into_view(trig)
act.click(trig)                                     # MiniWeb's file dialog (a Finder window) opens
act.wait(1)
act.click(dom.one(css="._fe-fav", text=task["folders"][0]))       # the file's folder in the sidebar
for sub in task["folders"][1:]:
    act.double_click(dom.one(css="._fe-item", text=sub))         # deeper folders
act.click(dom.one(css="._fe-item", text=task["name"]))          # the file
act.click(dom.one(css="._fe-ok", text="Open"))
act.wait(1)
for f in task["fields"]:
    el = dom.one(css=f["css"])
    if not el.in_viewport:
        el = act.scroll_into_view(el)
    act.click(el)
    if el.value:
        act.press("Control+a")
    act.type(f["value"])
if task["submit_css"]:
    btn = dom.one(css=task["submit_css"])
    if not btn.in_viewport:
        btn = act.scroll_into_view(btn)
    act.click(btn)
expect.backend()'''

    def discover(self, scan, page, site):
        out = []
        for i in scan.get("inputs") or []:
            if i["type"] != "file" or not i.get("trigger"):
                continue
            host = (i.get("form") or {}).get("css")
            others = [x for x in scan.get("inputs") or [] if x is not i and host and (x.get("form") or {}).get("css") == host
                      and x["type"] in ("text", "textarea", "email", "number")]
            sub = (i.get("form") or {}).get("submit") or i.get("apply_hint")
            ctrl = {"kind": "upload", "role": "upload", "css": i["css"], "name": i["name"], "id": i["id"],
                    "label": i["label"] or i["trigger"]["text"] or "file", "accept": i.get("accept") or "",
                    "trigger": i["trigger"], "submit": sub, "fields": _fields(others, [])[:4], "macro": "upload_file",
                    "heading": scan.get("h1") or "", "context": (scan.get("items") or [])[:15], "site_id": site,
                    "page": page, "page_title": scan["title"]}
            out.append((("upload", i["name"] or i["css"], page), ctrl))
        return out

    def arguments(self, ctrl):
        files = list(files_for(ctrl.get("accept")))
        if not files:
            return []
        sets = [{}]
        if ctrl.get("fields"):
            if ctrl.get("value_sets") is None:
                ctrl["value_sets"] = FV.value_sets(ctrl | {"submit": ctrl.get("submit") or {"text": "Upload"}},
                                                   ctrl.get("site_id") or ctrl["page"].split("/")[2])
            sets = [s["values"] for s in ctrl["value_sets"]] or [{}]
        return [{"index": n, "value": f"{f}|{n}", "text": f, "file": f, "values": sets[n % len(sets)]}
                for n, f in enumerate(files[:8])]

    def has_arguments(self, ctrl):
        return bool(files_for(ctrl.get("accept"), limit=1))

    def probe_argument(self, ctrl):
        args = self.arguments(ctrl)
        return args[0] if args else None

    def element_key(self, ctrl):
        return f"UPLOAD {ctrl['page']} {ctrl.get('name') or ctrl['css']}"

    def view(self, ctrl):
        v = super().view(ctrl)
        v.update({k: ctrl.get(k) for k in ("accept", "trigger", "submit", "fields", "heading")})
        v.pop("options", None)
        return v

    def files(self, step):
        return {step["option"]["file"]: files_for(step["control"].get("accept"), limit=500).get(step["option"]["file"])}

    def apply(self, page, ctrl, arg, base, ctx, log_before):
        page.set_input_files(ctrl["css"], files_for(ctrl.get("accept"), limit=500)[arg["file"]], timeout=5000)
        for f in ctrl.get("fields") or []:
            v = (arg.get("values") or {}).get(FV.field_key(f))
            if v is not None:
                page.fill(f["css"], v, timeout=5000)
        if ctrl.get("submit"):
            page.locator(ctrl["submit"]["css"]).first.click(timeout=5000)
        B.settle(page)
        new = B.session_log(ctx, base)[log_before:]
        muts = [e for e in new if (e.get("method") or "GET").upper() != "GET" and isinstance(e.get("status"), int)
                and 200 <= e["status"] < 400]
        return (muts[-1], None, "upload", new) if muts else (None, None, None, new)

    def check(self, ctrl, arg, keep=None):
        return {"kind": "state", "pending": True}

    def request_check(self, entry):
        files = [f.get("filename") for f in (entry.get("body") or {}).get("_files", [])] if isinstance(entry.get("body"), dict) else []
        return {"kind": "request", "method": entry["method"].upper(), "path": entry["path"], "params": {}, "keep": {},
                "final": False, **({"files": files} if files else {})}

    def describe(self, ctrl):
        return {"type": "a file upload control", "label": ctrl.get("label") or "", "choices": [],
                "note": "name the file by its path as given (folder/name) and what the upload is for"}

    def say(self, ctrl, arg):
        return {"file": arg["file"], **{f.get("label") or f.get("name"): v for f in ctrl.get("fields") or []
                                        for k, v in (arg.get("values") or {}).items() if FV.field_key(f) == k}}

    def mentions(self, arg):
        return [os.path.basename(arg["file"])] + [str(v) if len(str(v).split()) <= 6 else " ".join(str(v).split()[:6])
                                                  for v in (arg.get("values") or {}).values()]

    def step_spec(self, step):
        c, o = step["control"], step["option"]
        parts = o["file"].split("/")
        lines = [f"FILE TO UPLOAD: {o['file']!r} — click the control css={c['trigger']['css']!r} "
                 f"({c['trigger'].get('text')!r}); MiniWeb's file dialog (a Finder window, css '._fe-overlay') opens",
                 f"PICK: click {parts[0]!r} in its sidebar (css '._fe-fav'), open subfolders {parts[1:-1]} by "
                 f"double-clicking them (css '._fe-item'), click the file {parts[-1]!r} (css '._fe-item'), then "
                 f"click 'Open' (css '._fe-ok'). (act.upload is only for a native file chooser.)"]
        for f in c.get("fields") or []:
            v = (o.get("values") or {}).get(FV.field_key(f))
            if v is not None:
                lines.append(f"  then field {f.get('label') or f.get('name')!r} css={f['css']!r} = {v!r}")
        lines.append(f"SUBMIT: click css={c['submit']['css']!r} text={c['submit'].get('text')!r}" if c.get("submit")
                     else "SUBMIT: choosing the file uploads it (no button)")
        return lines

    def script_task(self, step):
        c, o = step["control"], step["option"]
        fields = [{"css": f["css"], "value": str(o["values"][FV.field_key(f)])} for f in c.get("fields") or []
                  if FV.field_key(f) in (o.get("values") or {})]
        parts = o["file"].split("/")
        return {"subtask": step["subtask"], "file": o["file"], "files": [o["file"]], "trigger_css": c["trigger"]["css"],
                "folders": parts[:-1] or ["Documents"], "name": parts[-1],
                "fields": fields, "submit_css": (c.get("submit") or {}).get("css")}

    def locate(self, driver, step):
        return driver.query(css=step["control"]["trigger"]["css"], limit=1)
