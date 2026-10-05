"""Element side file — what every recorded action targeted. PRIVILEGED: it sits next to a
trajectory for analysis/debugging and is never exported (export.py never reads it).

    episodes/<task>/a<n>/elements.json   every attempt (kept or failure pool), by recording index
    accepted/<task>/elements.json        aligned with trajectory.json: `history[k]` <-> history[k],
                                         `steps[k]` <-> steps[k] (same `i` and `screenshot`)

One entry per step (FORMAT datagen.elements/v1):
    i, span, screenshot, type        recording index, prefix|target, frame before the action, action type
    element                          the targeted element, or for key/type the focused one:
        role_in_action               target | focused | scroll_at | scroll_target | drag_source
        selector                     the dom query the script used to find it ({css, text, tag}), if any
        css_path                     unique CSS path computed at action time
        tag, role, accessible_name (ARIA: aria-labelledby/aria-label/<label>/alt/title/text),
        label, context_label (a short heading/label just before it, when not programmatic),
        text (trimmed), id, name, type
        box                          [x, y, w, h] viewport pixels just before the action
    url                              page URL before the action
    point                            the actual (jittered) mouse point, or null
    scroll                           {window: [sx, sy], container: {css_path, scroll_top, scroll_left} | null}
    at_point                         element under `point` when it is not the target itself (else null)
    select                           for <select> targets: {before, after: {index, value, label}, reloaded}
    drag                             {start, end, end_point, waypoints} for drags
Top level: format, complete (false for backfills), missing (what a backfill could not recover),
source (recorded | backfill).
"""
from __future__ import annotations

import json
from pathlib import Path

FORMAT = "datagen.elements/v1"
_CTX_KEYS = ("element", "url", "point", "scroll", "at_point", "select", "drag")


def entries_from_steps(steps):
    out = []
    for s in steps:
        ctx = s.get("el") or {}
        out.append({"i": s["i"], "span": s.get("span", "target"), "screenshot": s["screenshot"], "type": s["type"],
                    **{k: ctx.get(k) for k in _CTX_KEYS}})
    return out


def write_attempt(attempt_dir, steps):
    """elements.json for one executed attempt (written by the executor)."""
    doc = {"format": FORMAT, "source": "recorded", "complete": True, "missing": [],
           "steps": entries_from_steps(steps)}
    (Path(attempt_dir) / "elements.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False, default=str))
    return doc


def for_trajectory(attempt_doc, traj):
    """Split an attempt's element entries into history/steps aligned with trajectory.json."""
    by_i = {e["i"]: e for e in attempt_doc["steps"]}
    out = {"format": FORMAT, "id": traj["id"], "source": attempt_doc.get("source"),
           "complete": attempt_doc.get("complete", False), "missing": attempt_doc.get("missing", [])}
    for part in ("history", "steps"):
        rows = []
        for st in traj[part]:
            e = dict(by_i.get(st["i"]) or {"i": st["i"], "missing": True})
            e["screenshot"] = st["screenshot"]            # the trajectory's own frame path
            rows.append(e)
        out[part] = rows
    return out


# ── backfill from what older runs logged (no browser, no LLM) ────────────────

MISSING_V0 = [
    "selector: the script's dom query was not logged — css_path is inferred from the task spec only where the "
    "logged tag/name/id/text unambiguously match the target control or its apply button, else null",
    "scroll: window/container scroll position was not logged",
    "at_point: the element under the jittered click point was not logged (the hit-test only guaranteed it was the "
    "target or its descendant)",
    "accessible_name: approximated by the logged label (or text for non-selects); context_label for a select "
    "comes from the site map's label of the matched control",
    "element for scroll steps: the scroll target was not logged (element is null)",
    "element for key/type steps: the focused element was not logged — inferred as the <select> clicked just before "
    "in the same span, else null",
    "select before/after: inferred — before from the select's logged text at the opening click, after (on the "
    "committing Enter) from the task spec, confirmed against the server log",
    "text: logged trimmed to 80 characters",
]


def _span_spec(task, span):
    if span == "prefix" and task["start"].get("prefix"):
        pre = task["start"]["prefix"]
        return pre["control"], pre["option"]
    return task["control"], task["option"]


def _opt_by_label(ctrl, label):
    for o in ctrl.get("options") or []:
        if (o.get("text") or "").strip() == (label or "").strip():
            return {"index": o["index"], "value": o["value"], "label": o["text"]}
    return {"index": None, "value": None, "label": label} if label else None


def _confirmed(entries, param, value):
    return any(str((e.get("query") or {}).get(param, "")).strip().casefold() == str(value).strip().casefold()
               or (isinstance(e.get("body"), dict) and str(e["body"].get(param, "")).strip().casefold()
                   == str(value).strip().casefold()) for e in entries)


def _infer_css(tgt, ctrl):
    tag = tgt.get("tag")
    if tag == "select" and ctrl.get("kind") == "select":
        css = ctrl.get("css") or ""
        if (tgt.get("id") and tgt["id"] in css) or (tgt.get("name") and tgt["name"] in css) or \
                (tgt.get("label") and tgt.get("label") == ctrl.get("label")):
            return css
    b = ctrl.get("apply_button") if ctrl.get("apply") == "button" else None
    if b and tag in ("button", "input") and (tgt.get("text") or "").strip() == (b.get("text") or "").strip():
        return b.get("css")
    return None


def backfill_attempt(attempt_dir, task):
    """Best-effort elements.json from an attempt recorded before element capture existed.
    Uses only attempt.json (logged targets, points, urls, drag paths), the task spec and the
    server log. complete=false; `missing` lists what could not be recovered."""
    d = Path(attempt_dir)
    rec = json.loads((d / "attempt.json").read_text())
    log = json.loads((d / "server_log.json").read_text()) if (d / "server_log.json").exists() else []
    rows, last_select = [], {}
    for s in rec.get("steps", []):
        span = s.get("span", "target")
        ctrl, option = _span_spec(task, span)
        tgt = s.get("target") or {}
        row = {"i": s["i"], "span": span, "screenshot": s["screenshot"], "type": s["type"],
               "element": None, "url": s.get("url"), "point": [s["x"], s["y"]] if "x" in s and s["type"] != "key" else None,
               "scroll": None, "at_point": None, "select": None, "drag": None}
        if tgt:
            css = _infer_css(tgt, ctrl)
            is_select = tgt.get("tag") == "select"       # a select's logged text is its selected option, not a name
            row["element"] = {"role_in_action": "scroll_target" if s["type"] == "scroll" else "target",
                              "selector": None, "css_path": css, "css_path_inferred": bool(css),
                              "tag": tgt.get("tag"), "role": tgt.get("role") or "",
                              "accessible_name": tgt.get("label") or ("" if is_select else tgt.get("text") or ""),
                              "label": tgt.get("label") or "",
                              "context_label": (ctrl.get("label") or "") if (is_select and css == ctrl.get("css")) else "",
                              "text": tgt.get("text") or "",
                              "id": tgt.get("id") or "", "name": tgt.get("name") or "", "type": "",
                              "box": tgt.get("box") or []}
            if tgt.get("tag") == "select" and s["type"] in ("click", "double_click"):
                row["select"] = {"before": _opt_by_label(ctrl, tgt.get("text")), "after": None, "inferred": True}
                last_select[span] = (row["element"], s.get("url"))
            elif s["type"] in ("click", "double_click"):
                last_select.pop(span, None)
        elif s["type"] in ("key", "type") and span in last_select and last_select[span][1] == s.get("url"):
            el = dict(last_select[span][0], role_in_action="focused", inferred=True)
            row["element"] = el
            if s["type"] == "key" and s.get("key") == "Enter":
                param = (ctrl.get("signature") or {}).get("param")
                row["select"] = {"before": None, "after": {"index": option["index"], "value": option["value"],
                                                           "label": option["text"]},
                                 "inferred": True, "confirmed_by_server_log": bool(param and _confirmed(log, param, option["value"]))}
                last_select.pop(span, None)
        if s["type"] == "drag":
            row["drag"] = {"start": row["element"], "end": None, "end_point": [s.get("x2"), s.get("y2")],
                           "waypoints": s.get("path") or []}
        rows.append(row)
    doc = {"format": FORMAT, "source": "backfill", "complete": False, "missing": MISSING_V0, "steps": rows}
    (d / "elements.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False, default=str))
    return doc


def load_attempt(attempt_dir):
    p = Path(attempt_dir) / "elements.json"
    return json.loads(p.read_text()) if p.exists() else None
