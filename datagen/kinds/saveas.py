"""save_by_form — save a file through the Save dialog: press an export/download control that opens
the file system's Save As dialog, choose the folder, name the file, and press Save.

A control is a Save-As link ([data-save-as]; app/static/file-explorer.js). Its arguments are
(folder, file stem) pairs; the file keeps the extension the site gives it. The simulated file
system stores saved files in the session overlay (site "filesystem", collection "files"), so
the check is recorded from that data change like any other write (checks.state_check): the dry
run saves twice in throw-away sessions and keeps what both runs agree on (path, name, type).
"""
from __future__ import annotations

import random
import re

from datagen import browser as B
from datagen.kinds import register
from datagen.kinds.base import Kind

FOLDERS = ("Documents", "Desktop", "Downloads")
STEMS = ("{what} export", "My {what}", "{what} backup", "{what} 2026", "{what} copy", "Shared {what}")


def _what(ctrl):
    t = re.sub(r"[^\w\s-]", " ", " ".join([ctrl.get("label") or "", ctrl.get("page_title") or ""])).split()
    words = [w for w in t if re.search(r"[A-Za-z]", w) and w.lower() not in ("export", "download", "save", "as", "all", "the", "to", "csv", "json",
                                                 "pdf", "svg", "file")][:2]
    return " ".join(words) or "data"


@register
class SaveAsKind(Kind):
    name = "saveas"
    macros = {"save_by_form": "saveas"}
    oracle = True
    needs_probe = False
    example = '''# example: open the Save dialog, pick the folder in its sidebar, name the file, save
act.click(dom.one(css=task["link_css"]))
act.wait(1)
act.click(dom.one(css=task["folder_css"], text=task["folder"]))
name = dom.one(css=task["name_css"])
act.click(name)
act.press("Control+a")
act.type(task["filename"])
act.click(dom.one(css=task["save_css"], text="Save"))
expect.backend()'''

    def discover(self, scan, page, site):
        out = []
        for i, a in enumerate(scan.get("saveas") or []):
            ctrl = {"kind": "saveas", "role": "saveas", "css": a["css"], "label": a["text"] or "Export", "name": "saveas",
                    "id": "", "href": a["href"], "page": page, "page_title": scan["title"], "site_id": site}
            out.append((("saveas", _sm()._pattern(page), re.sub(r"\d+", "N", a["href"])), ctrl))
        return out

    def arguments(self, ctrl):
        rng = random.Random(ctrl["page"] + ctrl.get("href", ""))
        what = _what(ctrl)
        combos = [(st.format(what=what), f) for st in STEMS for f in FOLDERS]
        rng.shuffle(combos)
        return [{"index": i, "value": f"{f}/{s}", "text": f"{s} in {f}", "folder": f, "stem": s}
                for i, (s, f) in enumerate(combos)]

    def probe_argument(self, ctrl):
        return self.arguments(ctrl)[0]

    def element_key(self, ctrl):
        return f"SAVEAS {_sm()._pattern(ctrl['page'])} {re.sub(r'[0-9]+', 'N', ctrl.get('href') or '')}"

    def view(self, ctrl):
        v = super().view(ctrl)
        v.pop("options", None)
        v.update({k: ctrl.get(k) for k in ("href", "site_id")})
        return v

    def changes_site(self, t):
        return "filesystem"

    def apply(self, page, ctrl, arg, base, ctx, log_before):
        page.locator(ctrl["css"]).first.click(timeout=5000)
        page.wait_for_timeout(600)
        got = [e for e in B.session_log(ctx, base)[log_before:] if (e.get("method") or "GET") == "GET"
               and (e.get("path") or "") == (ctrl.get("href") or "").split("?")[0]]
        if got and (not isinstance(got[-1].get("status"), int) or got[-1]["status"] >= 300):
            return None, None, None, B.session_log(ctx, base)[log_before:]      # the file itself is not served
        fname = page.locator("._fe-fname").first
        fname.wait_for(state="visible", timeout=8000)
        default = fname.input_value()
        ext = re.search(r"\.[A-Za-z0-9]{1,5}$", default or "")
        arg["filename"] = arg["stem"] + (ext.group(0) if ext else "")     # recorded for the executor and wording
        page.locator("._fe-fav").filter(has_text=arg["folder"]).first.click(timeout=5000)
        page.wait_for_timeout(400)
        fname.fill(arg["filename"], timeout=5000)
        page.locator("._fe-ok").filter(has_text="Save").first.click(timeout=5000)
        page.wait_for_timeout(800)
        B.settle(page)
        return {"method": "POST", "path": "/_fs/save", "status": 200, "query": {}}, None, "click", \
            B.session_log(ctx, base)[log_before:]

    def check(self, ctrl, arg, keep=None):
        return {"kind": "state", "pending": True}

    def observed_check(self, ev, site, ctrl=None):
        from datagen import checks
        chk = checks.state_check(ev["changes"], "filesystem", ev["requests"])
        if chk:
            names = [w["fields"].get("name") for w in chk["expect"] if w["fields"].get("name")]
            chk["typed"] = names[0] if names else None
        return chk

    def describe(self, ctrl):
        return {"type": f"a {ctrl.get('label')!r} control that opens a Save As dialog (folder + file name)",
                "label": ctrl.get("label") or "", "choices": [],
                "note": "say what to save (the export), the exact file name and the folder"}

    def say(self, ctrl, arg):
        return {"save": ctrl.get("label"), "file name": arg.get("filename") or arg["stem"], "folder": arg["folder"]}

    def mentions(self, arg):
        return [arg["stem"], arg["folder"]]

    def step_spec(self, step):
        c, o = step["control"], step["option"]
        return [f"OPEN: click {c.get('label')!r} (css={c['css']!r}); a Save As dialog opens",
                f"FOLDER: click {o['folder']!r} in the dialog's sidebar (css='._fe-fav')",
                f"NAME: replace the name in css='._fe-fname' with {o.get('filename')!r}",
                "SAVE: click the dialog's 'Save' button (css='._fe-ok')"]

    def script_task(self, step):
        c, o = step["control"], step["option"]
        return {"subtask": step["subtask"], "link_css": c["css"], "folder": o["folder"], "folder_css": "._fe-fav",
                "filename": o.get("filename"), "name_css": "._fe-fname", "save_css": "._fe-ok"}

    def locate(self, driver, step):
        return driver.query(css=step["control"]["css"], limit=1)


def _sm():
    from datagen import sitemap
    return sitemap
