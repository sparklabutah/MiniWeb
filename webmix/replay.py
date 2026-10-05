"""Replay kept datagen trajectories through the browser-use harness to record training rows.

A trajectory's recorded pixel actions become a plan of browser-use actions (`build_plan`, pure):
click on a field + (Ctrl+A) + typing -> input(index, text); click on a <select> + the keys that chose
the option -> select_dropdown(index, text); key -> send_keys; scroll -> scroll(pages); drag / draw
-> the harness's custom actions; go-to / new tab / switch tab -> navigate / switch; every macro
segment ends with macro_done, the episode with done(text = the answer, if any).

The plan runs in a real browser-use Agent whose model is scripted (`Replayer`): browser-use builds
its normal prompt each step (DOM element list + screenshot + history), ChatOpenAI serializes it
exactly as it would for vLLM (schema in the system prompt), and a stand-in client records that
request and answers with the plan's next action. Element indices are resolved against the live
selector map at that moment (the recorded element's css path, its nearest indexed ancestor or
descendant); an element browser-use did not index, a canvas, a slider or a spot inside a widget is
clicked by viewport coordinates, re-projected from where the recorded point sat in the element's box.

An episode's rows are kept only if the task's backend check passes on the replayed session
(datagen.checks.gate: the same gate the trajectory passed when it was recorded).
"""
from __future__ import annotations

import asyncio
import base64
import copy
import json
import re
import shutil
import time
from pathlib import Path
from types import SimpleNamespace

from datagen import checks, config
from datagen.viewer import FAMILY_OF
from webmix import REPLAY_DIR
from webmix import harness as H

OUT_DIR = REPLAY_DIR

TEXT_INPUT_TYPES = {"", "text", "email", "password", "search", "tel", "url", "number"}
# browser-use's input() assigns these directly (ISO values), so typed keystrokes are translated
DIRECT_TYPES = {"date", "time", "datetime-local", "month", "week", "color", "range"}
CLICK_TAGS = {"a", "button", "input", "select", "textarea", "label", "summary", "option", "details"}
CLICK_ROLES = {"button", "link", "tab", "menuitem", "checkbox", "radio", "switch", "option", "treeitem",
               "menuitemcheckbox", "menuitemradio", "combobox", "textbox"}


class Unsupported(Exception):
    pass


# ── plan (pure) ───────────────────────────────────────────────────────────────

def _css(el):
    return (el or {}).get("css_path") or ""


def _is_text_field(el):
    if not el:
        return False
    tag = (el.get("tag") or "").lower()
    if tag == "textarea":
        return True
    if tag == "input":
        return (el.get("type") or "").lower() in TEXT_INPUT_TYPES
    return (el.get("role") or "") == "textbox"


def _typed(el, text, select_all):
    """The op for text typed into `el`: input(), except for browser-use's directly-assigned types: a date
    typed as Chrome's MMDDYYYY keystrokes becomes its ISO value; other keystrokes stay keystrokes."""
    ty = ((el or {}).get("type") or "").lower() if (el or {}).get("tag") == "input" else ""
    if ty == "date":
        m = re.fullmatch(r"(\d{2})(\d{2})(\d{4})", text)
        if m:
            return {"op": "input", "el": el, "text": f"{m.group(3)}-{m.group(1)}-{m.group(2)}", "select_all": True}
    if ty in DIRECT_TYPES:
        return {"op": "keys", "text": text}
    return {"op": "input", "el": el, "text": text, "select_all": select_all}


def _label(el):
    if not el:
        return "the page"
    s = (el.get("accessible_name") or el.get("label") or el.get("text") or el.get("name") or el.get("tag") or "")
    s = re.sub(r"\s+", " ", str(s)).strip()[:60]
    return f'"{s}"' if s else (el.get("tag") or "element")


def _path(url):
    """A recorded absolute URL (old datagen port) -> path + query, re-based at replay time."""
    m = re.match(r"^https?://[^/]+(/.*)?$", url or "")
    return (m.group(1) or "/") if m else (url or "/")


def _pairs(traj, elements):
    """[(segment, macro, action, element record)] in episode order."""
    out = []
    for seg, (tkey, ekey, macro) in enumerate((("history", "history", traj.get("history_macro")),
                                              ("steps", "steps", traj["macro"]))):
        recs = {r["i"]: r for r in elements.get(ekey) or []}
        for s in traj.get(tkey) or []:
            out.append((seg, macro, s["action"], recs.get(s["i"])))
    return out


def build_plan(traj, elements):
    """-> list of ops (dicts with 'op', 'segment', 'macro', ...), ending in macro_done(s) + done."""
    pairs = _pairs(traj, elements)
    ops, answer, i, n = [], None, 0, len(pairs)

    def el_of(k):
        r = pairs[k][3] or {}
        return r.get("element")

    def add(seg, macro, **op):
        ops.append({"segment": seg, "macro": macro, **op})

    while i < n:
        seg, macro, a, rec = pairs[i]
        rec = rec or {}
        t, el = a["type"], rec.get("element")
        same_seg = lambda k: k < n and pairs[k][0] == seg          # noqa: E731
        if t == "click":
            tag = (el or {}).get("tag", "").lower()
            if tag == "select":
                after, typed, j = (rec.get("select") or {}).get("after"), "", i + 1
                while same_seg(j) and pairs[j][2]["type"] in ("key", "type") and _css(el_of(j)) == _css(el):
                    after = ((pairs[j][3] or {}).get("select") or {}).get("after") or after
                    typed += pairs[j][2].get("text") or ""
                    j += 1
                if after or typed:
                    add(seg, macro, op="select", el=el, text=(after or {}).get("label") or typed)
                    i = j
                    continue
            if _is_text_field(el) or ((el or {}).get("type") or "").lower() == "date":
                j, select_all = i + 1, False
                if same_seg(j) and pairs[j][2]["type"] == "key" and pairs[j][2].get("key") == "Control+a":
                    select_all, j = True, j + 1
                text, k = "", j
                while same_seg(k) and pairs[k][2]["type"] == "type" and _css(el_of(k)) in ("", _css(el)):
                    text += pairs[k][2].get("text") or ""
                    k += 1
                if k > j:
                    add(seg, macro, **_typed(el, text, select_all))
                    i = k
                    continue
            add(seg, macro, op="click", el=el, point=[a["x"], a["y"]], button=a.get("button") or "left")
        elif t == "key":
            if a.get("key") == "Control+a" and same_seg(i + 1) and pairs[i + 1][2]["type"] == "type":
                fel = el_of(i + 1) or el
                text, k = "", i + 1
                while same_seg(k) and pairs[k][2]["type"] == "type":
                    text += pairs[k][2].get("text") or ""
                    k += 1
                add(seg, macro, **_typed(fel, text, True))
                i = k
                continue
            add(seg, macro, op="key", key=a["key"])
        elif t == "type":
            text, k = "", i
            while same_seg(k) and pairs[k][2]["type"] == "type":
                text += pairs[k][2].get("text") or ""
                k += 1
            add(seg, macro, **_typed(el, text, False))
            i = k
            continue
        elif t == "scroll":
            nxt = (pairs[i + 1][3] or {}).get("scroll") if i + 1 < n else None
            add(seg, macro, op="scroll", dx=a.get("dx", 0), dy=a.get("dy", 0), point=[a.get("x"), a.get("y")],
                container=(rec.get("scroll") or {}).get("container"), after=nxt)
        elif t == "drag":
            d = rec.get("drag") or {}
            add(seg, macro, op="drag", el=d.get("start") or el, start=[a["x"], a["y"]], end=[a["x2"], a["y2"]],
                end_el=d.get("end"))
        elif t == "draw":
            add(seg, macro, op="draw", el=el, strokes=a["strokes"])
        elif t == "goto":
            add(seg, macro, op="navigate", url=_path(a["url"]), new_tab=False)
        elif t == "new_tab":
            add(seg, macro, op="navigate", url=_path(a["url"]), new_tab=True)
        elif t == "switch_tab":
            add(seg, macro, op="switch", index=a["index"])
        elif t == "answer":
            answer = a.get("text") or ""
        else:                                   # upload (pre-Finder recordings), hover, double_click
            raise Unsupported(f"action type {t!r}")
        i += 1
    # macro_done closes each segment (a reading task answered off the start page is one empty
    # segment); done ends the episode
    out = []
    for op in ops:
        if out and out[-1]["segment"] != op["segment"]:
            out.append({"op": "macro_done", "segment": out[-1]["segment"], "macro": out[-1]["macro"]})
        out.append(op)
    last = out[-1] if out else ({"segment": pairs[-1][0], "macro": pairs[-1][1]} if pairs and answer is not None else None)
    if last:
        out.append({"op": "macro_done", "segment": last["segment"], "macro": last["macro"]})
        out.append({"op": "done", "segment": last["segment"], "macro": last["macro"],
                    "text": answer if answer is not None else "Done.", "answer": answer})
    return out


def memory_for(op, action):
    """A short, deterministic flash-mode `memory` for the step (no model-written thoughts yet)."""
    k = op["op"]
    if k == "click":
        return f"Click {_label(op.get('el'))}."
    if k == "input":
        return f'Type "{op["text"]}" into {_label(op.get("el"))}.'
    if k == "select":
        return f'Choose "{op["text"]}" in {_label(op.get("el"))}.'
    if k == "key":
        return f"Press {action.get('send_keys', {}).get('keys', op.get('key'))}."
    if k == "keys":
        return f'Type "{op["text"]}".'
    if k == "scroll":
        return "Scroll down to see more." if action.get("scroll", {}).get("down", True) else "Scroll back up."
    if k == "drag":
        return f"Drag {_label(op.get('el'))}."
    if k == "draw":
        return f"Draw on {_label(op.get('el'))}."
    if k == "navigate":
        return f"Open {op['url']}" + (" in a new tab." if op.get("new_tab") else ".")
    if k == "switch":
        return "Switch to the other tab."
    if k == "macro_done":
        return "This step of the task is finished."
    if k == "done":
        return f"The answer is {op['answer']}." if op.get("answer") is not None else "The task is complete."
    return ""


# ── live resolution ───────────────────────────────────────────────────────────

_RECT = """(css) => {
  let e; try { e = document.querySelector(css); } catch (x) { return null; }
  if (!e) return null;
  const r = e.getBoundingClientRect();
  return {x: r.x, y: r.y, w: r.width, h: r.height, value: ('value' in e) ? String(e.value) : null,
          tag: e.tagName.toLowerCase(), type: (e.getAttribute('type') || '').toLowerCase()};
}"""

_RANGE_STATE = """(css) => {
  let e; try { e = document.querySelector(css); } catch (x) { return null; }
  if (!e) return null;
  const r = e.getBoundingClientRect();
  return {x: r.x, y: r.y + r.height / 2, w: r.width, min: e.min || '0', max: e.max || '100', value: e.value};
}"""

_OPTIONS = """(css) => {
  let e; try { e = document.querySelector(css); } catch (x) { return null; }
  return e && e.options ? [...e.options].filter(o => !o.disabled).map(o => (o.label || o.text || '').trim()) : null;
}"""
_HOME_LINK = """(home) => {
  const norm = p => (p || '/').replace(/\\/+$/, '') || '/';
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < innerHeight; };
  const a = [...document.querySelectorAll('a[href]')].find(a => {
    try { const u = new URL(a.href, location.href); return u.origin === location.origin && norm(u.pathname) === home && vis(a); }
    catch (x) { return false; } });
  if (!a) return null;
  const path = [];
  for (let e = a; e && e.nodeType === 1 && e !== document.documentElement; e = e.parentElement) {
    if (e.id && document.querySelectorAll('#' + CSS.escape(e.id)).length === 1) { path.unshift('#' + CSS.escape(e.id)); break; }
    let i = 1; for (let s = e.previousElementSibling; s; s = s.previousElementSibling) if (s.tagName === e.tagName) i++;
    path.unshift(e.tagName.toLowerCase() + ':nth-of-type(' + i + ')');
  }
  return path.join(' > ');
}"""
_PLACEHOLDER_OPT = re.compile(r"^(all\b|any\b|select\b|choose\b|--|none$|-$)", re.I)

_SCROLL_STATE = """(css) => {
  let c = null; try { c = css ? document.querySelector(css) : null; } catch (x) {}
  return {sy: window.scrollY, sx: window.scrollX, ct: c ? c.scrollTop : null, cl: c ? c.scrollLeft : null};
}"""


# ── model-written memory (replaces the templated memory) ────────────────────────
# The templated memory ("Click \"Search\".") taught the adapter to stop reasoning in its memory field: it
# lost track of progress (a slider pressed past its value until the step limit) and answered WebArena
# questions tersely after little exploration (pooled run, 2026-09-28). The base model now writes each step's
# memory itself, given the exact prompt it would see and the correct action (rationalization), so the rows
# keep its own reasoning style. The memory re-enters browser-use's history, as it would at inference.

MEMORY_LLM = {}          # {"client": AsyncOpenAI, "model": served name} when configured

MEMORY_ASK = ("(Annotation request, not a task step.) You are about to take this next action; it has NOT been executed "
              "yet:\n{action}\n"
              "Write the `memory` you would output together with it, from the moment just before executing it: {judge}"
              "what you must remember to finish the task: values set or read so far, what is done and what is left; "
              "then the immediate next goal, which is what this action is about to do. Never describe this action as "
              "already done, and state only facts you can read on the current screen or in the history. 1-4 sentences "
              "of plain text, no JSON; do not say that the action was given to you or that anything is not executed yet.{hint}")
# recovery episodes: the step after an injected mistake (the model must notice it on the screen)
# sliders: the memory shows the geometry that puts the click there (2026-09-30: pooled_v4 clicked sliders by pointer
# but at memorized spots, then crept 4 units per click on held-out layouts; the executor's click point came from
# min/max/value and the track's box, which the memory never spelled out)
SLIDER_NOTE = (" The memory must show how this click point follows from what is visible: the slider's track spans about "
               "x={a}-{b} on the 0-1000 scale; its element lists min={mn}, max={mx}, and it now reads {cur}; the target "
               "{t} is {pct}% of the way from {mn} to {mx}, so x = {a} + {frac} x ({b} - {a}) = about {x}.{fix}")
SLIDER_FIX = " (The slider missed the target before: say what it reads now and how far the new click moves from the last one.)"
RECOVERY_HINT = (" The previous action was a mistake: {what}. Your memory must notice this from the current screen, "
                 "say what is wrong, and that this action corrects it.")
# the first step has no previous step: asking to judge it made the model write "The previous step was not
# executed yet." into 11% of the cycle-3 rows (2026-09-29)
JUDGE_PREVIOUS = "first, judge whether the PREVIOUS step worked, from the history and the current screen; then "
DONE_ASK = ("(Annotation request, not a task step.) Every requirement of the task is now met and your next action is "
            "`done`.{answer}\nReply with JSON only, both fields required: {{\"memory\": \"<1-3 sentences confirming "
            "from the current screen that the task is complete>\", \"final_message\": \"<one or two sentences to the user "
            "saying what was done{must}>\"}}")
RETRY_NOTE = "\nYour previous reply was unusable ({why}). Reply again, following the format exactly."
# sentences that talk about the annotation instead of the task
LEAK = re.compile(r"[^.!?]*\b(not (yet )?(been )?executed|not been executed|hasn'?t been executed|not executed yet|"
                  r"annotation|action (was |is )?(given|provided) to me|provided action)\b[^.!?]*[.!?]?\s*", re.I)


def configure_memory(base_url, model):
    from openai import AsyncOpenAI
    MEMORY_LLM.update(client=AsyncOpenAI(base_url=base_url, api_key="EMPTY"), model=model)


def _json_or_text(text):
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        return json.loads(t)
    except ValueError:
        return t


async def write_memory(messages, action, op, first=False, tries=3, hint=None, note=None):
    """-> (memory, final_message | None) written by the base model; (None, None) on failure. A reply that
    loses the answer, leaks the annotation request or is empty is asked again (up to `tries` times)."""
    if not MEMORY_LLM:
        return None, None
    done = op["op"] == "done"
    ans = op.get("answer")
    if done:
        ask = DONE_ASK.format(answer=f" The answer to report is: {ans}" if ans is not None else "",
                              must=", including the answer verbatim" if ans is not None else "")
    else:
        ask = MEMORY_ASK.format(action=json.dumps(action, ensure_ascii=False), judge="" if first else JUDGE_PREVIOUS,
                                hint=(RECOVERY_HINT.format(what=hint) if hint else "") + (note or ""))
    why, mem = None, None
    for k in range(tries):
        try:
            r = await MEMORY_LLM["client"].chat.completions.create(
                model=MEMORY_LLM["model"], temperature=0 if k == 0 else 0.7, max_completion_tokens=320,
                messages=list(messages) + [{"role": "user", "content": ask + (RETRY_NOTE.format(why=why) if why else "")}])
            out = _json_or_text(r.choices[0].message.content)
        except Exception:
            return mem, None
        if done:
            if not isinstance(out, dict):              # prose around the JSON: pull the fields out
                text = str(out)
                out = {f: (re.search(rf'"{f}"\s*:\s*"((?:[^"\\\\]|\\\\.)*)"', text) or [None, ""])[1]
                       for f in ("memory", "final_message")}
            mem = _clean(LEAK.sub("", str(out.get("memory") or ""))) or mem
            final = _clean(LEAK.sub("", str(out.get("final_message") or "")))
            if not final:
                why = "final_message was missing or empty"
            elif ans is not None and str(ans).strip().lower() not in final.lower():
                why = f"final_message must contain the answer verbatim: {ans}"
            else:
                return mem or None, final
            continue
        if isinstance(out, dict):
            out = out.get("memory") or ""
        mem = _clean(LEAK.sub("", str(out)))
        if mem:
            return mem, None
        why = "the memory was empty or talked about the annotation request instead of the task"
    return mem or None, None


def _clean(text):
    return re.sub(r"\s+", " ", text).strip()[:700]


class Replayer:
    """The scripted model: answers each browser-use request with the plan's next action."""

    def __init__(self, bs, base, plan, task_dir, rows_dir, traj, task):
        self.bs, self.base, self.plan, self.traj, self.task = bs, base, plan, traj, task
        self.cursor, self.queue = 0, []
        self.rows, self.seen, self.events, self.notes = [], [], [], []
        self.task_dir, self.rows_dir = task_dir, rows_dir
        self.answer = None
        self.response_format = None
        self.mistake = None           # what the last injected mistake did (recovery episodes)
        self.slider_clicks = 0

    # element -> (index | None, projected viewport point | None)
    async def _cdp(self):
        return await self.bs.get_or_create_cdp_session()

    async def _backend_chain(self, css, depth=4):
        if not css:
            return []
        cdp, ids = await self._cdp(), []
        for k in range(depth + 1):
            expr = (f"(() => {{ let e; try {{ e = document.querySelector({json.dumps(css)}); }} catch (x) {{ return null; }} "
                    f"for (let i = 0; i < {k}; i++) e = e && e.parentElement; return e; }})()")
            res = await cdp.cdp_client.send.Runtime.evaluate(params={"expression": expr}, session_id=cdp.session_id)
            oid = (res.get("result") or {}).get("objectId")
            if not oid:
                break
            d = await cdp.cdp_client.send.DOM.describeNode(params={"objectId": oid}, session_id=cdp.session_id)
            ids.append(d["node"]["backendNodeId"])
        return ids

    async def _box(self, backend_id):
        cdp = await self._cdp()
        try:
            m = await cdp.cdp_client.send.DOM.getBoxModel(params={"backendNodeId": backend_id}, session_id=cdp.session_id)
        except Exception:
            return None
        q = m["model"]["border"]
        xs, ys = q[0::2], q[1::2]
        return min(xs), min(ys), max(xs), max(ys)

    async def _index(self, el):
        """-> (index, node, how) of the recorded element in the current selector map, or (None, None, None)."""
        ids = await self._backend_chain(_css(el))
        if not ids:
            return None, None, None
        smap = await self.bs.get_selector_map()
        by_backend = {node.backend_node_id: (idx, node) for idx, node in smap.items()}
        for k, bid in enumerate(ids):
            if bid in by_backend:
                idx, node = by_backend[bid]
                return idx, node, "self" if k == 0 else f"ancestor{k}"
        for idx, node in smap.items():             # a wrapper whose indexed control is inside it
            p = node.parent_node
            for _ in range(3):
                if p is None:
                    break
                if p.backend_node_id == ids[0]:
                    return idx, node, "descendant"
                p = p.parent_node
        return None, None, None

    async def _project(self, el, point):
        """The recorded point, moved to where it now sits in the element's current box."""
        if not point or point[0] is None:
            return None
        box = (el or {}).get("box")
        now = await H.evaluate(self.bs, _RECT, _css(el)) if _css(el) else None
        if not box or not now or not box[2] or not box[3]:
            return [round(point[0]), round(point[1])]
        fx, fy = (point[0] - box[0]) / box[2], (point[1] - box[1]) / box[3]
        return [round(now["x"] + fx * now["w"]), round(now["y"] + fy * now["h"])]

    @staticmethod
    def _clickable(node):
        tag = (node.node_name or "").lower()
        attrs = node.attributes or {}
        if tag == "input" and (attrs.get("type") or "").lower() == "range":
            return False
        return tag in CLICK_TAGS or (attrs.get("role") or "") in CLICK_ROLES

    async def _click(self, op):
        el = op.get("el")
        pt = await self._project(el, op["point"])
        idx, node, how = await self._index(el)
        if idx is not None and op.get("button", "left") == "left" and self._clickable(node):
            box = await self._box(node.backend_node_id)
            if how == "self" or (pt and box and box[0] - 2 <= pt[0] <= box[2] + 2 and box[1] - 2 <= pt[1] <= box[3] + 2):
                return {"click": {"index": idx}}, f"index:{how}"
        if pt is None:
            raise Unsupported("click with no point")
        nx, ny = H.to_norm(*pt)
        return {"click": {"coordinate_x": nx, "coordinate_y": ny}}, "coords"

    async def resolve(self, op):
        """-> list of (action dict, how) for one plan op (usually one)."""
        k = op["op"]
        if k == "click":
            return [await self._click(op)]
        if k == "input":
            await self._live_code(op)
            idx, node, how = await self._index(op.get("el"))
            if idx is not None:
                now = await H.evaluate(self.bs, _RECT, _css(op["el"]))
                clear = op["select_all"] or not (now or {}).get("value")
                return [({"input": {"index": idx, "text": op["text"], "clear": bool(clear)}}, f"index:{how}")]
            if "+" in op["text"]:
                raise Unsupported("unindexed field and '+' in text")
            acts = [({"send_keys": {"keys": "Control+a"}}, "keys")] if op["select_all"] else []
            return acts + [({"send_keys": {"keys": op["text"]}}, "keys")]
        if k == "select":
            idx, node, how = await self._index(op.get("el"))
            if idx is None:
                raise Unsupported("select not indexed")
            if op.get("inject") and not op.get("text"):          # a wrong option, read off the live <select>
                labels = await H.evaluate(self.bs, _OPTIONS, _css(op["el"])) or []
                wrong = [x for x in labels if x and x != op["right"] and not _PLACEHOLDER_OPT.match(x)]
                if not wrong:
                    raise Unsupported("no other option to choose by mistake")
                op["text"] = wrong[len(op["right"]) % len(wrong)]
                self.mistake = f'it chose "{op["text"]}" instead of "{op["right"]}"'
            return [({"select_dropdown": {"index": idx, "text": op["text"]}}, f"index:{how}")]
        if k == "key":
            return [({"send_keys": {"keys": op["key"]}}, "keys")]
        if k == "keys":
            if "+" in op["text"]:
                raise Unsupported("'+' in typed keystrokes")
            return [({"send_keys": {"keys": op["text"]}}, "keys")]
        if k == "scroll":
            return [await self._scroll(op)]
        if k == "drag":
            s = await self._project(op["el"], op["start"])
            end_el = op.get("end_el") if op.get("end_el") and _css(op["end_el"]) != _css(op["el"]) else op["el"]
            e = await self._project(end_el, op["end"])
            (sx, sy), (ex, ey) = H.to_norm(*s), H.to_norm(*e)
            return [({"drag": {"start_x": sx, "start_y": sy, "end_x": ex, "end_y": ey}}, "coords")]
        if k == "draw":
            box = (op.get("el") or {}).get("box")
            now = await H.evaluate(self.bs, _RECT, _css(op["el"])) if box else None
            dx, dy = ((now["x"] - box[0], now["y"] - box[1]) if now else (0, 0))
            strokes = [[list(H.to_norm(p[0] + dx, p[1] + dy)) for p in s] for s in op["strokes"]]
            return [({"draw": {"strokes": strokes}}, "coords")]
        if k == "navigate":
            return [({"navigate": {"url": self.base + op["url"], "new_tab": bool(op.get("new_tab"))}}, "url")]
        if k == "switch":
            tabs = await self.bs.get_tabs()
            if op["index"] >= len(tabs):
                raise Unsupported(f"tab {op['index']} of {len(tabs)}")
            return [({"switch": {"tab_id": tabs[op["index"]].target_id[-4:]}}, "tab")]
        if k == "home":                           # chains: the site's own link to its home page
            css = await H.evaluate(self.bs, _HOME_LINK, f"/sites/{op['site']}")
            idx, node, how = await self._index({"css_path": css}) if css else (None, None, None)
            if idx is None:
                raise Unsupported("no indexed link to the site's home page")
            op["el"] = {"css_path": css, "tag": "a", "text": "home"}
            return [({"click": {"index": idx}}, f"index:{how}")]
        if k == "link":                           # task-centric chains (review round 1, A2): the site's own link to a page
            css = await H.evaluate(self.bs, _HOME_LINK, op["path"])
            idx, node, how = await self._index({"css_path": css}) if css else (None, None, None)
            if idx is None:
                raise Unsupported(f"no indexed link to {op['path']}")
            op["el"] = {"css_path": css, "tag": "a", "text": op["path"]}
            return [({"click": {"index": idx}}, f"index:{how}")]
        if k == "macro_done":
            return [({"macro_done": {}}, "")]
        if k == "done":
            return [({"done": {"text": op["text"]}}, "")]
        raise Unsupported(k)

    async def _live_code(self, op):
        """A one-time code differs every session: type the one this session was just sent."""
        if self.task["control"]["kind"] != "reveal" or not re.fullmatch(r"\d{6}", op["text"]):
            return
        from datagen.kinds.reveal import code_message
        changes = (await H.admin_get(self.bs, self.base, "/_admin/changes")).get("changes") or []
        hits = [m for m in (code_message([c]) for c in changes) if m]
        if not hits:
            raise Unsupported("no one-time code in this session's messages")
        op["text"] = hits[-1][0]

    async def _scroll(self, op):
        cont = op.get("container") or None
        css = (cont or {}).get("css_path") if isinstance(cont, dict) else None
        now = await H.evaluate(self.bs, _SCROLL_STATE, css or "")
        after = op.get("after") or {}
        delta = op["dy"]
        if css and isinstance(after.get("container"), dict) and after["container"].get("css_path") == css \
                and now and now.get("ct") is not None:
            delta = after["container"].get("scroll_top", now["ct"] + delta) - now["ct"]
        elif not css and after.get("window") and now:
            delta = after["window"][1] - now["sy"]
        pages = round(abs(delta) / H.VIEWPORT[1], 2) or round(abs(op["dy"]) / H.VIEWPORT[1], 2) or 0.5
        params = {"down": (delta if delta else op["dy"]) >= 0, "pages": pages}
        if css:
            idx, node, how = await self._index({"css_path": css})
            if idx is not None:
                params["index"] = idx
        return {"scroll": params}, "page" if "index" not in params else "index"

    # the stand-in OpenAI client's create()
    async def respond(self, messages, response_format):
        self.response_format = response_format
        try:
            txt = await H.evaluate(self.bs, _VISIBLE_TEXT)
            if isinstance(txt, str) and txt:
                self.seen.append(txt)
        except Exception:
            pass
        if not self.queue:
            if self.cursor >= len(self.plan):
                raise RuntimeError("plan exhausted but browser-use asked for another step")
            op = self.plan[self.cursor]
            self.cursor += 1
            self.queue = [(op, act, how) for act, how in await self.resolve(op)]
        op, action, how = self.queue.pop(0)
        if op["op"] == "done":
            self.answer = op.get("answer")
        if op.get("inject") and op.get("what"):
            self.mistake = op["what"]
        if not op.get("inject"):
            self._event(op, action)
        note = await self._slider_note(op, action) if op["op"] == "click" and not op.get("inject") else None
        memory, final = await write_memory(messages, action, op, first=not self.rows,
                                           hint=self.mistake if op.get("recover") else None, note=note)
        if final and "done" in action:
            action = {"done": {**action["done"], "text": final}}
        target = canonical({"memory": memory or memory_for(op, action), "action": [action]}, response_format)
        content = json.dumps(target, ensure_ascii=False)
        self.rows.append({"step": len(self.rows), "segment": op["segment"], "macro": op["macro"],
                          "family": FAMILY_OF.get(op["macro"] or "", "Other"), "op": op["op"], "resolved": how,
                          "memory_by": MEMORY_LLM.get("model") if memory else "template",
                          **({"final_by": MEMORY_LLM.get("model") if final else "template"} if op["op"] == "done" else {}),
                          **({"inject": "error"} if op.get("inject") else {}),
                          **({"aug_prefix": True} if op.get("aug_prefix") else {}),
                          "messages": self._save_images(messages, len(self.rows)), "target": content})
        return content

    async def _slider_note(self, op, action):
        """SLIDER_NOTE for a coordinate click on an <input type=range> of a slider task, else None."""
        el = op.get("el") or {}
        p = action.get("click") or {}
        c = self.task.get("control") or {}
        if (el.get("tag") or "").lower() != "input" or (el.get("type") or "").lower() != "range" \
                or p.get("coordinate_x") is None or c.get("kind") != "slider":
            return None
        now = await H.evaluate(self.bs, _RANGE_STATE, _css(el))
        if not now or not now.get("w"):
            return None
        (a, _), (b, _) = H.to_norm(now["x"], now["y"]), H.to_norm(now["x"] + now["w"], now["y"])
        mn, mx, t = float(now["min"]), float(now["max"]), float((self.task.get("option") or {}).get("value"))
        frac = (t - mn) / ((mx - mn) or 1)
        fmt = lambda v: str(int(v)) if float(v).is_integer() else f"{v:g}"          # noqa: E731
        self.slider_clicks += 1
        return SLIDER_NOTE.format(a=a, b=b, mn=fmt(mn), mx=fmt(mx), cur=fmt(float(now["value"])), t=fmt(t),
                                  pct=round(100 * frac), frac=f"{frac:.2f}", x=p["coordinate_x"],
                                  fix=SLIDER_FIX if self.slider_clicks > 1 else "")

    def _event(self, op, action):
        """Human-schema action events for the verifier (evaluation.verifiers action checks)."""
        name, p = next(iter(action.items()))
        ev = {"type": "action", "action": {"input": "type", "send_keys": "key", "select_dropdown": "select"}.get(name, name),
              "target": _label(op.get("el")) if op.get("el") else "", "timestamp": time.time()}
        if name == "input":
            ev["value"] = p["text"]
        elif name == "send_keys":
            ev["value"] = p["keys"]
            if op["op"] == "input":
                ev["action"] = "type"
        elif name == "select_dropdown":
            ev["value"] = p["text"]
        elif name == "done" and op.get("answer") is not None:
            ev["action"], ev["value"] = "answer", op["answer"]
        self.events.append(ev)

    def _save_images(self, messages, step):
        return save_images(messages, self.rows_dir, step)


def save_images(messages, rows_dir, step):
    """OpenAI-format messages with their base64 screenshots written next to rows.jsonl (step_NNN.png), referenced
    by file name (the row format webmix.train reads)."""
    msgs = copy.deepcopy(messages)
    n = 0
    for m in msgs:
        content = m.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            url = ((part.get("image_url") or {}).get("url") if isinstance(part, dict) else None) or ""
            mm = re.match(r"data:image/(\w+);base64,(.*)$", url, re.S)
            if not mm:
                continue
            ext = "jpg" if mm.group(1) in ("jpeg", "jpg") else mm.group(1)
            name = f"step_{step:03d}" + (f"_{n}" if n else "") + f".{ext}"
            (Path(rows_dir) / name).write_bytes(base64.b64decode(mm.group(2)))
            part["image_url"]["url"] = name
            n += 1
    return msgs


def canonical(target, response_format):
    """The target exactly as guided decoding must produce it: browser-use sends a strict schema, so
    every property of an action is required (index AND coordinate_x/y on a click, success and
    files_to_display on done ...), in schema order. Missing values take the schema default, else null."""
    schema = ((response_format or {}).get("json_schema") or {}).get("schema") or {}
    variants = {}
    for it in (((schema.get("properties") or {}).get("action") or {}).get("items") or {}).get("anyOf") or []:
        (name, body), = it["properties"].items()
        variants[name] = body.get("properties") or {}
    out = []
    for a in target["action"]:
        (name, params), = a.items()
        props = variants.get(name)
        if props is None:
            out.append(a)
            continue
        out.append({name: {k: params[k] if k in params else v.get("default") for k, v in props.items()}})
    return {"memory": target["memory"], "action": out}


def canonicalize_rows(ep_dir):
    """Rewrite an episode's recorded targets in canonical form (rows recorded before `canonical`)."""
    ep_dir = Path(ep_dir)
    rf = json.loads((ep_dir / "episode.json").read_text())["response_format"]
    rows = [json.loads(l) for l in (ep_dir / "rows.jsonl").read_text().split("\n") if l.strip()]
    for r in rows:
        r["target"] = json.dumps(canonical(json.loads(r["target"]), rf), ensure_ascii=False)
    (ep_dir / "rows.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


from datagen.driver import _VISIBLE_TEXT  # noqa: E402  (the viewport-text JS the datagen recorder uses)


def _stand_in_client(replayer):
    async def create(model=None, messages=None, response_format=None, **params):
        content = await replayer.respond(messages, response_format)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content), finish_reason="stop")],
                               usage=None)
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


def replay_llm(replayer):
    """ChatOpenAI exactly as the eval configures it, with the network client swapped for the script."""
    llm = H.make_llm("replay", base_url="http://127.0.0.1:9/v1")
    llm._verified_api_keys = True
    client = _stand_in_client(replayer)
    llm.get_client = lambda: client
    return llm


# ── one episode ───────────────────────────────────────────────────────────────

_TASKS: dict = {}


def load_task(run, task_id):
    if run not in _TASKS:
        rows = {}
        for line in (config.RUNS_DIR / run / "tasks.jsonl").read_text().split("\n"):
            if line.strip():
                t = json.loads(line)
                rows[t["task_id"]] = t
        _TASKS[run] = rows
    return _TASKS[run][task_id]


def _rebase(task, base):
    """Values recorded with the datagen server's origin (a copied link, older verifiers) -> this server's."""
    return json.loads(re.sub(r"https?://(?:localhost|127\.0\.0\.1):\d+", base, json.dumps(task)))


def load_part(task_dir, base):
    """One kept trajectory, ready to replay: its trajectory, elements and task (re-based at `base`)."""
    task_dir = Path(task_dir)
    traj = json.loads((task_dir / "trajectory.json").read_text())
    elements = json.loads((task_dir / "elements.json").read_text())
    run = task_dir.parent.parent.name
    task = _rebase(load_task(run, traj["id"]), base)
    task["check"] = checks.relax_recorded_dates(task["check"], [task["instruction"], json.dumps(task.get("option"))])
    return {"dir": task_dir, "traj": traj, "elements": elements, "run": run, "task": task}


async def replay_one(task_dir, base, out_root=OUT_DIR, headless=True, log=print, variant=None):
    """Replay one kept trajectory (variant "recovery": with one injected, corrected mistake).
    -> result dict; rows written to out_root/<id>/ only if it passes."""
    part = load_part(task_dir, base)
    tid = part["traj"]["id"]
    spec = {"id": tid, "variant": variant, "parts": [part], "instruction": part["task"]["instruction"]}
    try:
        spec["plan"] = build_plan(part["traj"], part["elements"])
        if variant == "recovery":
            from webmix.augment import inject_mistake
            spec["id"] = tid + "~rec"
            spec["plan"] = inject_mistake(spec["plan"], part["task"], seed=tid)
    except Unsupported as e:
        return {"task_id": spec["id"], "run": part["run"], "macro": part["traj"]["macro"], "site": part["traj"]["site"],
                "variant": variant, "ok": False, "error": f"unsupported: {e}", "steps": 0}
    return await replay_episode(spec, base, out_root, headless, log)


async def replay_episode(spec, base, out_root=OUT_DIR, headless=True, log=print):
    """Run spec["plan"] under spec["instruction"] from the first part's start page; the episode passes when
    every part's own gate passes on the session. spec: {id, variant, parts: [load_part], instruction, plan}."""
    from browser_use import Agent

    parts, plan, eid = spec["parts"], spec["plan"], spec["id"]
    first = parts[0]
    traj, task, run = first["traj"], first["task"], first["run"]
    res = {"task_id": eid, "run": run, "macro": traj["macro"], "site": traj["site"], "ok": False,
           "error": None, "steps": 0, **({"variant": spec["variant"]} if spec.get("variant") else {}),
           **({"parts": [p["traj"]["id"] for p in parts]} if len(parts) > 1 else {})}
    out = Path(out_root) / eid
    tmp = Path(out_root) / "_tmp" / eid
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True, exist_ok=True)
    bs = H.make_session(headless=headless)
    t0 = time.time()
    try:
        await bs.start()
        await H.enable_clipboard(bs)
        await H.prepare(bs, base, task)
        rp = Replayer(bs, base, plan, first["dir"], tmp, traj, task)
        agent = Agent(task=H.instruction(spec["instruction"], base + task["start"]["url"]), llm=replay_llm(rp),
                      browser_session=bs, tools=H.make_tools(), max_failures=2, **H.AGENT_KWARGS)
        H.use_normalized_coordinates(bs)
        hist = await asyncio.wait_for(agent.run(max_steps=H.MAX_STEPS, on_step_start=lambda a: H.enable_clipboard(bs, a)),
                                      timeout=60 + 15 * len(plan))
        res["steps"] = len(rp.rows)
        res["plan_len"] = len(plan)
        res["resolved"] = [r["resolved"] for r in rp.rows]
        errs = [e for e in hist.errors() if e]
        entries, changes, clip = await H.backend_state(bs, base)
        copies = [{"type": "action", "action": "clipboard_write", "target": "", "value": v} for v in clip]
        oks, details = [], []
        for p in parts:
            ok_p, detail_p, _ = checks.gate(p["task"]["check"], p["task"]["verifier"], entries, rp.events + copies,
                                            changes, clip, rp.answer, rp.seen)
            oks.append(bool(ok_p))
            details.append(str(detail_p))
        detail = " | ".join(details)
        res["ok"] = bool(all(oks) and rp.cursor >= len(plan) and not rp.queue)
        res["detail"] = detail[:300]
        if errs:
            res["action_errors"] = [str(e)[:200] for e in errs][:5]
        if not res["ok"] and not res["error"]:
            res["error"] = ("plan not finished" if rp.cursor < len(plan) else f"check failed: {detail}")[:300]
        meta = {"task_id": eid, "run": run, "site": traj["site"], "macro": traj["macro"],
                "history_macro": traj.get("history_macro"), "instruction": spec["instruction"],
                "start_url": task["start"]["url"], "response_format": rp.response_format}
        if spec.get("variant"):
            meta["variant"] = spec["variant"]
        if len(parts) > 1:
            meta["parts"] = [p["traj"]["id"] for p in parts]
            meta["macros"] = [p["traj"]["macro"] for p in parts]
        (tmp / "episode.json").write_text(json.dumps(meta, indent=1))
        with open(tmp / "rows.jsonl", "w") as f:
            for r in rp.rows:
                f.write(json.dumps({"task_id": eid, **r}, ensure_ascii=False) + "\n")
        if not res["ok"]:                       # kept apart for diagnosis, never trained on
            (tmp / "result.json").write_text(json.dumps({**res, "seen": rp.seen}, indent=1, default=str))
            out = Path(out_root) / "_failed" / eid
        else:
            shutil.rmtree(Path(out_root) / "_failed" / eid, ignore_errors=True)
        shutil.rmtree(out, ignore_errors=True)
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp.rename(out)
    except Unsupported as e:
        res["error"] = f"unsupported: {e}"
    except asyncio.TimeoutError:
        res["error"] = "timeout"
    except Exception as e:
        res["error"] = f"{type(e).__name__}: {str(e)[:300]}"
    finally:
        res["duration_s"] = round(time.time() - t0, 1)
        try:
            await bs.kill()
        except Exception:
            pass
        shutil.rmtree(tmp, ignore_errors=True)
    return res
