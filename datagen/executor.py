"""Stage 4 — executor. A coding LLM writes a script against the restricted wrapper
(datagen/actions.py API_DOC) using the macro guide and privileged DOM facts; the harness
runs it in a fresh session and records only screenshots + pixel actions.

Per attempt (fresh browser context = fresh Flask session):
    goto start URL (the only navigation)  ->  [prefix step script]  ->  target step script
    -> final screenshot -> backend gate (checks.gate over the session request log)
A failed attempt (policy violation, script error, gate failure) is kept with its reason —
it is a DPO negative — and the next attempt's prompt carries the error and the page state.
"""
from __future__ import annotations

import json
import random
import re
import time
import traceback
from pathlib import Path

from datagen import browser as B
from datagen import checks, config, elements, kinds
from datagen.actions import (API_DOC, Act, ActionError, Dom, Expect, PolicyViolation, Recorder, Session,
                             run_script)
from datagen.driver import PlaywrightDriver

SYSTEM = ("You are a browser-automation engineer. You write short, robust Python scripts that complete one "
          "UI step using ONLY the API below. The script's actions are recorded as a demonstration, so act "
          "like a careful human: scroll to things before using them, one purposeful action at a time, no "
          "unnecessary clicks.\n\n" + API_DOC)

def _clip(s, n):
    s = str(s or "")
    return s if len(s) <= n else s[:n] + "…"


def step_spec(step):
    lines = [f"MACRO: {step['macro']}", f"STEP: {step['subtask']}", f"(full task: {step['instruction']})"]
    op = step["control"].get("opener")
    if op:
        lines.append(f"OPEN FIRST: the control is revealed by clicking css={op['css']!r} text={op.get('text')!r} "
                     f"(a dialog, tab or panel) — click it, then re-query the control (task['opener_css'])")
    lines += kinds.of(step["control"]).step_spec(step)
    lines.append(f"BACKEND PROOF checked by expect.backend(): {checks.describe(step['check'])}")
    return "\n".join(lines)


def script_task(step):
    """The `task` dict a script sees: the exact targets, so selectors are never re-typed."""
    t = kinds.of(step["control"]).script_task(step)
    if step["control"].get("opener"):
        t["opener_css"] = step["control"]["opener"]["css"]
    return t


def page_state(driver, step):
    """Privileged facts about the live page for the prompt."""
    facts = [f"URL: {driver.url()}", f"VIEWPORT: {driver.viewport()[0]}x{driver.viewport()[1]}"]
    try:
        hits = kinds.of(step["control"]).locate(driver, step)
        for _k, info in hits[:2]:
            vw, vh = driver.viewport()
            b = info.get("box") or [0, 0, 0, 0]
            on = info.get("visible") and b[1] >= 0 and b[1] + b[3] <= vh
            facts.append(f"TARGET NOW: <{info['tag']}> visible={info.get('visible')} on_screen={bool(on)} "
                         f"box=({b[0]:.0f},{b[1]:.0f},{b[2]:.0f},{b[3]:.0f})"
                         + (f" selected={info.get('selected_text')!r}" if info["tag"] == "select" else ""))
        if not hits:
            facts.append("TARGET NOW: not found with that selector/text — inspect the outline")
    except Exception as exc:
        facts.append(f"TARGET NOW: lookup failed ({exc})")
    facts.append("PAGE OUTLINE (first elements):\n" + _clip(driver.outline(60), 3500))
    return "\n".join(facts)


def _code(raw):
    m = re.search(r"```(?:python)?\s*\n(.*?)```", raw or "", re.S)
    return (m.group(1) if m else (raw or "")).strip()


def write_script(step, guide_txt, state, feedback=None, model=config.MODEL_EXECUTOR):
    from helpers.llm import call_llm
    example = kinds.of(step["control"]).example
    prompt = (f"GUIDE for {step['macro']} (distilled from human demonstrations):\n{guide_txt}\n\n"
              f"{step_spec(step)}\n\nLIVE PAGE:\n{state}\n\nEXAMPLE (different page):\n```python\n{example}\n```\n")
    if feedback:
        prompt += f"\nA PREVIOUS ATTEMPT FAILED:\n{feedback}\nFix the cause.\n"
    prompt += (f"\nThe script receives task = {json.dumps(script_task(step), ensure_ascii=False)}\n"
               "Use task[...] for selectors/texts verbatim — never rewrite a selector. After any action that may "
               "reload the page (committing a choice, clicking Apply/a link), re-query elements with dom.one(...) "
               "before using them again.\nWrite the script now, in one ```python block. End it with expect.backend().")
    raw = call_llm(prompt, system=SYSTEM, model=model, max_tokens=8000, temperature=0.3)
    return _code(raw)


def _step_of(task, which):
    if which == "prefix":
        pre = task["start"]["prefix"]
        return {"macro": pre["macro"], "subtask": task.get("prefix_subtask") or "", "instruction": task["instruction"],
                "control": pre["control"], "option": pre["option"], "check": pre["check"]}
    return {"macro": task["macro"], "subtask": task["subtask"], "instruction": task["instruction"],
            "control": task["control"], "option": task["option"], "check": task["check"]}


def run_attempt(task, base, b, out_dir, n, guides, feedback=None, model=config.MODEL_EXECUTOR, log=print):
    """One attempt in a fresh session. Returns the attempt record (also written to disk)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(f"{task['task_id']}:{n}")
    ctx = B.new_context(b)
    page = ctx.new_page()
    vp = config.VIEWPORT
    driver = PlaywrightDriver(page, vp)
    rec = Recorder(out_dir, vp)
    logs, entries = [], []
    record = {"attempt": n, "task_id": task["task_id"], "ok": False, "executed": False, "stage": None,
              "error": None, "scripts": {}, "t0": time.time()}
    try:
        kinds.of(task["control"]).setup(ctx, base, task["control"], task["option"])
        B.goto_start(page, base + task["start"]["url"])
        record["start_url"] = page.url
        which_steps = (["prefix"] if task["start"]["kind"] == "mid_chain" else []) + ["target"]
        for which in which_steps:
            step = _step_of(task, which)
            rec.span = which
            record["stage"] = which
            state = page_state(driver, step)
            fb = (feedback or {}).get(which)
            code = write_script(step, guides[step["macro"]], state, feedback=fb, model=model)
            record["scripts"][which] = code
            (out_dir / f"{which}.py").write_text(code)
            if not code:
                raise RuntimeError("the LLM returned no script")
            session = Session(driver, rec, rng, max_actions=30, time_budget=180)
            chk = step["check"]
            session.files = kinds.of(step["control"]).files(step)
            session.upload_input = step["control"]["css"] if step["control"]["kind"] == "upload" else None
            session.open_urls = kinds.of(step["control"]).open_urls(step)
            session.forbidden_keys = kinds.of(step["control"]).forbidden_keys(step)
            expect = Expect(session, lambda chk=chk: checks.evaluate(
                chk, B.session_log(ctx, base), B.session_changes(ctx, base) if _needs_changes(chk) else None,
                B.clipboard_writes(ctx, base) if chk.get("kind") == "clipboard" else None, rec.answer, rec.seen))
            run_script(code, act=Act(session), dom=Dom(session), expect=expect, task=script_task(step),
                       log=lambda m: logs.append(f"[{which}] {m}"))
        record["executed"] = True
        record["stage"] = "backend"
    except PolicyViolation as exc:
        record["error"] = f"policy violation: {exc}"
    except AssertionError as exc:
        record["error"] = f"assertion failed: {str(exc)[:400]}"
    except ActionError as exc:
        record["error"] = f"action refused: {exc}"
    except Exception as exc:
        tb = traceback.extract_tb(exc.__traceback__)
        where = next((f"script line {f.lineno}" for f in reversed(tb) if f.filename == "<executor-script>"), "")
        record["error"] = f"{type(exc).__name__}: {str(exc)[:300]} {where}".strip()
    finally:
        try:
            record["final_screenshot"] = rec.final(driver.screenshot())
            record["final_url"] = driver.page.url
            html = driver.page.content()
            (out_dir / "final.html").write_text(html[:400000])
        except Exception:
            pass
        entries = B.session_log(ctx, base)
        changes = B.session_changes(ctx, base)
        records = B.session_record(ctx, base)
        record["dialogs"], record["downloads"] = driver.dialogs, driver.downloads
        try:
            ctx.close()
        except Exception:
            pass
    (out_dir / "server_log.json").write_text(json.dumps(entries, indent=1, default=str))
    (out_dir / "data_changes.json").write_text(json.dumps(changes, indent=1, default=str))
    clip = [e.get("value") for e in records if e.get("action") == "clipboard_write"]
    copies = [{"type": "action", "action": "clipboard_write", "target": "", "value": v} for v in clip]
    ok, detail, report = checks.gate(task["check"], task["verifier"], entries, action_events(rec.steps) + copies,
                                     changes, clip, rec.answer, rec.seen)
    record["answer"] = rec.answer
    record["backend"] = {"ok": ok, "detail": detail, "verify_task": report.get("by_macro")}
    record["ok"] = bool(record["executed"] and ok)
    if record["executed"] and not ok:
        record["error"] = f"backend check failed: {detail}"
    record["steps"] = rec.steps
    elements.write_attempt(out_dir, rec.steps)          # privileged element side file (every attempt)
    record["logs"] = logs[-50:]
    record["duration_s"] = round(time.time() - record.pop("t0"), 1)
    (out_dir / "attempt.json").write_text(json.dumps(record, indent=1, default=str))
    return record


def _needs_changes(chk):
    return chk.get("kind") == "state" or (chk.get("kind") == "answer" and (chk.get("requires") or {}).get("kind") == "state")


def action_events(steps):
    """Recorded pixel actions as human-schema action events (for verify_task / the judge digest)."""
    out = []
    for s in steps:
        tgt = s.get("target") or {}
        desc = f"{tgt.get('tag', '')} '{tgt.get('label') or tgt.get('text') or tgt.get('name') or ''}'".strip()
        ev = {"type": "action", "action": s["type"], "target": desc if tgt else "", "url": s.get("url"),
              "timestamp": s.get("t")}
        if s["type"] == "type":
            ev["value"] = s["text"]
        elif s["type"] == "key":
            ev["value"] = s["key"]
        elif s["type"] == "scroll":
            ev["value"] = f"dy={s.get('dy')}"
        elif s["type"] == "answer":
            ev["value"] = s["text"]
        out.append(ev)
    return out


def execute_task(task, base, b, episodes_dir, guides, attempts=3, model=config.MODEL_EXECUTOR, log=print):
    """Up to `attempts` fresh attempts; stops at the first that passes the backend gate."""
    tdir = Path(episodes_dir) / task["task_id"]
    records, feedback = [], None
    for n in range(1, attempts + 1):
        rec = run_attempt(task, base, b, tdir / f"a{n}", n, guides, feedback=feedback, model=model, log=log)
        rec["dir"] = str((tdir / f"a{n}").relative_to(config.ROOT))
        records.append(rec)
        log(f"  {task['task_id']} a{n}: {'OK' if rec['ok'] else 'FAIL'} "
            f"({len(rec['steps'])} actions, {rec['duration_s']}s) {rec.get('error') or ''}"[:220])
        if rec["ok"]:
            break
        stage = rec.get("stage") if rec.get("stage") in ("prefix", "target") else "target"
        prev = rec["scripts"].get(stage, "")
        feedback = {stage: f"error: {rec.get('error')}\nscript was:\n```python\n{prev}\n```\n"
                           f"actions it recorded: {[s['type'] for s in rec['steps'] if s.get('span') == stage]}"}
    return records
