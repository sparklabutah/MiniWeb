"""write_executable_program — write a small program in an on-page code editor and run it.

A control is a code editor (a textarea) with a Run button. Its arguments are programming tasks
for that site (LLM, cached): what the program must print, a reference solution and optional
stdin. The dry run types the reference into the editor in a throw-away session, runs it, and
records the run request and what the server answered; the check is that request answering the
same output with exit code 0 — any program that prints it passes, not only the reference.
"""
from __future__ import annotations

import hashlib
import json
import re

from datagen import browser as B
from datagen import config
from datagen.kinds import register
from datagen.kinds.base import Kind

CACHE = config.DATAGEN_DIR / "programs"
RUN = re.compile(r"^\W*(run|execute)(\s+code|\s+program|\s+▶)?\s*$", re.I)
SYSTEM = ("You write short programming exercises a user of an online Python playground might do. Each has a "
          "one-sentence description of exactly what the program prints (precise enough that the output is "
          "determined: say the format, separators, and order), a SHORT reference solution in plain Python 3 "
          "(no imports, no files, 2-8 lines, 4-space indents, no tabs, no comments), and optional stdin lines "
          "the program reads with input(). Vary topics: arithmetic, strings, loops, lists, simple algorithms. "
          "Reply ONLY JSON.")


def exercises(site, k=60, model=None, force=False):
    """Exercises for a site's editor (cached; topped up in batches of 20 to k, never repeating)."""
    path = CACHE / f"{site}.json"
    out = [] if force or not path.exists() else json.loads(path.read_text())
    for _ in range(6):
        if len(out) >= k:
            break
        more = _batch(min(20, k - len(out)), [e["description"] for e in out], model)
        if not more:
            break
        seen = {e["code"] for e in out}
        out += [e for e in more if e["code"] not in seen]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    return out


def _batch(k, avoid, model=None):
    from helpers.llm import call_llm
    raw = call_llm(json.dumps({"n": k, "already_have_do_not_repeat": avoid[-60:],
                               "output": {"exercises": [{"description": "…", "code": "…", "stdin": ""}]}}),
                   system=SYSTEM, json_mode=True, model=model or config.MODEL_SUGGEST, max_tokens=8000, temperature=0.9)
    try:
        got = json.loads(raw or "")
    except ValueError:
        got = {}
    got = got if isinstance(got, dict) else {"exercises": got}
    out = []
    for e in got.get("exercises") or []:
        code = str(e.get("code") or "").replace("\t", "    ").strip("\n")
        if not code or "import" in code or "open(" in code or len(code) > 600 or code.count("\n") > 10:
            continue
        out.append({"description": str(e.get("description") or "")[:300], "code": code,
                    "stdin": str(e.get("stdin") or "")[:200]})
    return out


@register
class ProgramKind(Kind):
    name = "program"
    macros = {"write_executable_program": "program"}
    needs_probe = False
    example = '''# example: replace the editor's content with the program, give it its input, run it
ed = dom.one(css=task["editor_css"])
if not ed.in_viewport:
    ed = act.scroll_into_view(ed)
act.click(ed)
act.press("Control+a")
act.press("Backspace")
act.type(task["code"])
if task["stdin"] and task["stdin_css"]:
    box = dom.one(css=task["stdin_css"])
    if not box.in_viewport:
        box = act.scroll_into_view(box)
    act.click(box)
    act.type(task["stdin"])
run = dom.one(css=task["run_css"])
if not run.in_viewport:
    run = act.scroll_into_view(run)
act.click(run)
expect.backend()'''

    def discover(self, scan, page, site):
        areas = [i for i in scan.get("inputs") or [] if i["type"] == "textarea" and i.get("visible")]
        run = next((b for b in scan.get("buttons") or [] if RUN.match(b["text"] or b["aria"] or "")), None)
        if not areas or not run:
            return []
        stdin = next((a for a in areas if re.search(r"stdin|standard input|input\(\)",
                                                     " ".join([a["id"], a["name"], a["placeholder"], a["label"]]), re.I)), None)
        editor = next((a for a in areas if a is not stdin and re.search(r"code|editor|source|python|program",
                       " ".join([a["id"], a["name"], a["placeholder"], a["label"]]), re.I)), None)
        if editor is None:
            return []
        ctrl = {"kind": "program", "role": "program", "css": editor["css"], "run_css": run["css"],
                "run_text": run["text"], "stdin_css": stdin["css"] if stdin else None, "label": "code editor",
                "name": "editor", "id": editor["id"], "page": page, "page_title": scan["title"], "site_id": site}
        return [(("program", _sm()._pattern(page)), ctrl)]

    def arguments(self, ctrl):
        return [{"index": i, "value": hashlib.sha1(e["code"].encode()).hexdigest()[:10], "text": e["description"], **e}
                for i, e in enumerate(exercises(ctrl["site_id"]))]

    def has_arguments(self, ctrl):
        return True

    def element_key(self, ctrl):
        return f"PROGRAM {_sm()._pattern(ctrl['page'])}"

    def view(self, ctrl):
        v = super().view(ctrl)
        v.pop("options", None)
        v.update({k: ctrl.get(k) for k in ("run_css", "run_text", "stdin_css", "site_id")})
        return v

    def check(self, ctrl, arg, keep=None):
        return {"kind": "request", "pending": True}

    def dry_run(self, t, base, b):
        c, o = t["control"], t["option"]
        ctx = B.new_context(b)
        page = ctx.new_page()
        try:
            B.goto_start(page, base + t["start"]["url"])
            n0 = len(B.session_log(ctx, base))
            page.fill(c["css"], o["code"], timeout=5000)
            if o.get("stdin") and c.get("stdin_css"):
                page.fill(c["stdin_css"], o["stdin"], timeout=5000)
            page.locator(c["run_css"]).first.click(timeout=5000)
            B.settle(page)
            page.wait_for_timeout(500)
            runs = [e for e in B.session_log(ctx, base)[n0:] if (e.get("method") or "").upper() == "POST"
                    and isinstance(e.get("response"), dict) and "stdout" in e["response"]]
            if not runs:
                return False, "running the program sent no request answering its output"
            r = runs[-1]["response"]
            if r.get("returncode") not in (0, None) or not str(r.get("stdout") or "").strip():
                return False, f"the reference does not run cleanly: rc={r.get('returncode')} {str(r.get('stderr'))[:80]!r}"
            o["stdout"] = r["stdout"]
            t["check"] = {"kind": "request", "method": "POST", "path": runs[-1]["path"], "params": {}, "keep": {},
                          "final": False, "response": {"stdout": r["stdout"], "returncode": r.get("returncode", 0)}}
            return True, f"prints {r['stdout'][:60]!r}"
        finally:
            ctx.close()

    def describe(self, ctrl):
        return {"type": "an online Python code editor with a Run button", "label": ctrl.get("run_text") or "Run",
                "note": "ask for a program that does what the description says and to run it; give the stdin lines "
                        "if any; do not paste the code"}

    def say(self, ctrl, arg):
        return {"program": arg["description"], **({"stdin": arg["stdin"]} if arg.get("stdin") else {}),
                "then": "run it"}

    def mentions(self, arg):
        return []

    def step_spec(self, step):
        c, o = step["control"], step["option"]
        return [f"EDITOR: textarea css={c['css']!r} — select all, delete, then type this program exactly:\n{o['code']}",
                *( [f"STDIN: type {o['stdin']!r} into css={c['stdin_css']!r}"] if o.get("stdin") and c.get("stdin_css") else []),
                f"RUN: click css={c['run_css']!r}; the program must print {o.get('stdout', '')[:200]!r}"]

    def script_task(self, step):
        c, o = step["control"], step["option"]
        return {"subtask": step["subtask"], "editor_css": c["css"], "code": o["code"], "stdin": o.get("stdin") or "",
                "stdin_css": c.get("stdin_css"), "run_css": c["run_css"]}

    def locate(self, driver, step):
        return driver.query(css=step["control"]["css"], limit=1)


def _sm():
    from datagen import sitemap
    return sitemap
