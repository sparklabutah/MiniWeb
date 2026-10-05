"""InSTA trajectories -> WebMix training rows, for the RQ4 matched-size task-centric baseline (EXPERIMENT_PLAN 4.3).

Source: btrabucco/insta-150k-v2-sft (Hugging Face; the InSTA authors' SFT set, 181,923 per-step chat examples, text
only). Each example is one agent step: system + up to 3 (user, assistant) turns, the last assistant turn being the step's
action. Examples are stored in trajectory order, so a trajectory is a run of examples starting at a 3-message one.
A user turn is "You are currently viewing <url>. Here is the viewport rendered in markdown:\n\n<markdown>\n\n<task>",
where interactive elements are marked "[id: N] <label> <role>"; an assistant turn is free-text reasoning followed by
```json {"action_key", "action_kwargs", "target_element_id"}```.

Mapping to our rows (the exact request browser-use sends in our harness + the flash-mode reply, webmix/replay.py):
- system: our harness's system prompt, verbatim (copied from a replay_v4 row; it carries our action schema).
- user: our template (<user_request> / <agent_history> / <agent_state> / <browser_state> / <step_info>), with the
  task wrapped as in webmix.harness.instruction, the full history of earlier steps (InSTA's reasoning as Memory plus a
  browser-use-style Result line), and InSTA's markdown turned into our element list ("[N]<a />\n\tlabel"). There is no
  screenshot: InSTA observations are text only, so these rows are text-only (ours carry one screenshot per step).
- target: {"memory": <InSTA reasoning without the JSON block>, "action": [<our action>]}:
    click -> click(index) | fill -> input(index, text, clear) | select_option -> select_dropdown(index, text)
    scroll -> scroll(down, pages = |dy| / 800) | goto -> navigate(url) | go_back -> go_back | stop -> done(text, success)
  hover, set_checked, horizontal scrolls and index 0 have no faithful equivalent: their trajectories are dropped.
- Only trajectories that end in stop with a non-empty answer are kept (the released SFT set has no judge labels; it is
  the authors' own filtered training set). A seeded sample of them is written until the row count reaches --target-rows
  (27,646 = the MiniWeb 3.1K pool, matched on training steps).

    python scripts/insta_to_rows.py --inputs 'data/webmix/insta/raw/sft_train-*.parquet' --out data/webmix/insta/rows_27k
    python scripts/insta_to_rows.py --inputs ... --limit 3000 --dry-run      # parse + report only
Train like any pool: WEBMIX_REPLAY_DIR=<out> python -m webmix.train --adapter pooled ...
"""
import argparse
import collections
import glob
import hashlib
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OBS_RE = re.compile(r"^You are currently viewing (\S+?)\. Here is the viewport rendered in markdown:\n\n(.*)\n\n(.+?)\s*$", re.S)
ACT_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.S)
TAIL_RE = re.compile(r"\n*(Here is my action|My action is|Action)\s*:?\s*$", re.I)   # lead-in left after the JSON block
ELEM_RE = re.compile(r"\[id: (\d+)\]\s*")
ROLES = {"link": "a", "button": "button", "input": "input type=text", "dropdown": "select", "checkbox": "input type=checkbox",
         "image": "img", "radio": "input type=radio", "textbox": "input type=text", "combobox": "select"}
ROLE_RE = re.compile(r"\b(link|button|input|dropdown|checkbox|image|radio|textbox|combobox)\b[.,;:)]*")
PAGE_PX = 800          # our viewport height: InSTA scroll deltas (px) -> browser-use pages
TODAY = "2025-03-01"   # InSTA's collection period; our rows show their own recording date
FAMILY = {"click": "Navigation", "goto": "Navigation", "go_back": "Navigation", "scroll": "Navigation",
          "fill": "Text entry", "select_option": "Discrete selection", "stop": "Reasoning base"}


class Unmappable(Exception):
    pass


def read_examples(patterns, limit=0):
    import pyarrow.parquet as pq
    n = 0
    for f in sorted(p for pat in patterns for p in glob.glob(pat)):
        for batch in pq.ParquetFile(f).iter_batches(batch_size=4096, columns=["messages"]):
            for r in batch.to_pylist():
                yield r["messages"]
                n += 1
                if limit and n >= limit:
                    return


def trajectories(examples):
    """Per-step examples (stored in order) -> lists of steps; a 3-message example starts a trajectory."""
    cur = []
    for msgs in examples:
        if len(msgs) == 3 and cur:
            yield cur
            cur = []
        user, asst = msgs[-2]["content"], msgs[-1]["content"]
        m = OBS_RE.match(user)
        a = ACT_RE.search(asst)
        step = {"url": m.group(1) if m else None, "markdown": m.group(2) if m else "", "task": m.group(3) if m else None,
                "reasoning": TAIL_RE.sub("", ACT_RE.sub("", asst).strip()).strip()}
        try:
            step["act"] = json.loads(a.group(1)) if a else None
        except ValueError:
            step["act"] = None
        cur.append(step)
    if cur:
        yield cur


def parse_markdown(md, force=None):
    """InSTA viewport markdown -> (our element-list text, {id: (tag, label)}, title). `force` = {id: tag} for the
    step's fill / select_option target, whose element type the action itself establishes."""
    lines, elems = [], {}
    title = ELEM_RE.split(md.split("\n", 1)[0], 1)[0].strip()[:80]
    for raw in md.split("\n"):
        parts = ELEM_RE.split(raw)          # [text, id, rest, id, rest, ...]
        if parts[0].strip():
            lines.append(parts[0].strip())
        for i in range(1, len(parts), 2):
            eid, rest = int(parts[i]), parts[i + 1]
            m = ROLE_RE.search(rest)
            if m:
                label, tag, after = rest[:m.start()].strip(), ROLES[m.group(1)], rest[m.end():].strip()
            else:
                label, tag, after = rest.strip(), "div", ""
            tag = (force or {}).get(eid, tag)
            elems[eid] = (tag, label)
            lines.append(f"[{eid}]<{tag} />" + (f"\n\t{label}" if label else ""))
            if after:
                lines.append(after)
    return "\n".join(lines), elems, title


def forced_tags(act):
    key, eid = (act or {}).get("action_key"), (act or {}).get("target_element_id")
    return {eid: "input type=text"} if key == "fill" else {eid: "select"} if key == "select_option" else {}


def map_action(act, step, prev_url):
    """InSTA action -> (our action dict, browser-use-style result line)."""
    if not act:
        raise Unmappable("unparsed")
    key, kw, eid = act.get("action_key"), act.get("action_kwargs") or {}, act.get("target_element_id")
    _, elems, _ = parse_markdown(step["markdown"], forced_tags(act))
    tag, label = elems.get(eid, ("element", ""))
    if key in ("click", "fill", "select_option") and not (isinstance(eid, int) and eid >= 1):
        raise Unmappable(f"{key}:index")
    if key == "click":
        return {"click": {"index": eid, "coordinate_x": None, "coordinate_y": None}}, \
            f'Clicked {tag.split()[0]} "{label[:40]}"' if label else f"Clicked element {eid}"
    if key == "fill":
        v = str(kw.get("value", ""))
        return {"input": {"index": eid, "text": v, "clear": True}}, f"Typed '{v}'"
    if key == "select_option":
        v = str(kw.get("label", ""))
        return {"select_dropdown": {"index": eid, "text": v}}, f"Selected dropdown option '{v}' at index {eid}"
    if key == "scroll":
        dx, dy = float(kw.get("delta_x") or 0), float(kw.get("delta_y") or 0)
        if not dy or dx:
            raise Unmappable("scroll:horizontal")
        pages = max(0.1, round(abs(dy) / PAGE_PX, 2))
        return {"scroll": {"down": dy > 0, "pages": pages, "index": None}}, \
            f"Scrolled {'down' if dy > 0 else 'up'} {pages} pages"
    if key == "goto":
        u = str(kw.get("url", ""))
        if not u:
            raise Unmappable("goto:url")
        return {"navigate": {"url": u, "new_tab": False}}, f"Navigated to {u}"
    if key == "go_back":
        return {"go_back": {"description": None}}, "Navigated back" + (f" to {prev_url}" if prev_url else "")
    if key == "stop":
        ans = str(kw.get("answer") or "").strip()
        if not ans:
            raise Unmappable("stop:no_answer")
        return {"done": {"text": ans, "success": True}}, None
    raise Unmappable(key or "none")


def user_message(task, start_url, history, step, n, tab):
    elements, elems, title = parse_markdown(step["markdown"], forced_tags(step["act"]))
    links = sum(1 for t, _ in elems.values() if t == "a")
    hist = "Agent initialized\n" + "".join(f"<step>\n{mem}\nResult\n{res}\n" for mem, res in history)
    return (f"<user_request>\nYou are interacting with a web application at {start_url}. Your task: {task}\n</user_request>\n\n"
            f"<agent_history>\n{hist}</agent_history>\n\n"
            "<agent_state>\n<file_system>\n\n</file_system>\n<todo_contents>\n[empty todo.md, fill it when applicable]\n"
            "</todo_contents>\n</agent_state>\n"
            f"<browser_state>\n<page_stats>{links} links, {len(elems)} interactive, 0 iframes, 0 shadow(open), "
            f"0 shadow(closed), {len(elems)} total elements</page_stats>\n"
            f"Current tab: {tab}\nAvailable tabs:\nTab {tab}: {step['url']} - {title}\n\n"
            f"Interactive elements:\n[Start of page]\n{elements}\n[End of page]\n</browser_state>\n"
            f"<step_info>Step{n} maximum:40\nToday:{TODAY}</step_info>\n")


def unresolved(step):
    """An indexed action whose target is not in this step's element list (InSTA's agent acted on an id its own
    viewport markdown does not show; ~5% of indexed steps)."""
    a = step["act"] or {}
    return a.get("action_key") in ("click", "fill", "select_option") and \
        a.get("target_element_id") not in parse_markdown(step["markdown"], forced_tags(a))[1]


def convert(traj, system, drop_unresolved=False):
    """One InSTA trajectory -> (task_id, episode, rows) or raise Unmappable."""
    task, start = traj[0]["task"], traj[0]["url"]
    if not task or not start or any(s["url"] is None for s in traj):
        raise Unmappable("observation")
    if not traj[-1]["act"] or traj[-1]["act"].get("action_key") != "stop":
        raise Unmappable("no_stop")
    if drop_unresolved and any(unresolved(s) for s in traj):
        raise Unmappable("unresolved_target")
    tid = "insta-" + hashlib.md5(f"{start}|{task}".encode()).hexdigest()[:12]
    tab = hashlib.md5(tid.encode()).hexdigest()[:4].upper()
    rows, history, prev_url = [], [], None
    for i, s in enumerate(traj):
        action, result = map_action(s["act"], s, prev_url)
        mem = s["reasoning"]
        rows.append({"task_id": tid, "step": i, "segment": 1, "macro": "insta", "family": FAMILY[s["act"]["action_key"]],
                     "op": s["act"]["action_key"], "resolved": "insta", "memory_by": "insta",
                     "messages": [{"role": "system", "content": system},
                                  {"role": "user", "content": user_message(task, start, history, s, i + 1, tab)}],
                     "target": json.dumps({"memory": mem, "action": [action]}, ensure_ascii=False)})
        history.append((mem, result))
        prev_url = s["url"]
    episode = {"task_id": tid, "source": "btrabucco/insta-150k-v2-sft", "instruction": task, "start_url": start,
               "steps": len(rows), "actions": [s["act"]["action_key"] for s in traj],
               "unresolved_targets": sum(unresolved(s) for s in traj)}
    return tid, episode, rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--inputs", nargs="+", default=[str(ROOT / "data/webmix/insta/raw/sft_train-*.parquet")])
    ap.add_argument("--out", default=str(ROOT / "data/webmix/insta/rows_27k"))
    ap.add_argument("--target-rows", type=int, default=27646, help="rows to keep (MiniWeb 3.1K pool: 27,646)")
    ap.add_argument("--seed", type=int, default=20261003)
    ap.add_argument("--limit", type=int, default=0, help="read only the first N examples (dry runs)")
    ap.add_argument("--dry-run", action="store_true", help="parse, map and report; write nothing")
    ap.add_argument("--system-from", default=None, help="a replay rows.jsonl whose system prompt is copied")
    ap.add_argument("--drop-unresolved", action="store_true",
                    help="drop trajectories with an indexed action on an id missing from its observation")
    a = ap.parse_args(argv)
    src = a.system_from or sorted(glob.glob(str(ROOT / "data/webmix/replay_v4/*/rows.jsonl")))[0]
    system = json.loads(open(src).readline())["messages"][0]["content"]

    kept, drops = [], collections.Counter()
    steps_kept, steps_dropped = collections.Counter(), collections.Counter()
    n_traj = 0
    for traj in trajectories(read_examples(a.inputs, a.limit)):
        n_traj += 1
        keys = [(s["act"] or {}).get("action_key", "unparsed") for s in traj]
        try:
            kept.append(convert(traj, system, a.drop_unresolved))
            steps_kept.update(keys)
        except Unmappable as e:
            drops[str(e)] += 1
            steps_dropped.update(keys)
    rng = random.Random(a.seed)
    rng.shuffle(kept)
    chosen, total, seen = [], 0, set()
    for item in kept:
        if total >= a.target_rows:
            break
        if item[0] in seen:              # the same task on the same start page twice: keep one
            continue
        seen.add(item[0])
        chosen.append(item)
        total += len(item[2])
    report = {"trajectories_read": n_traj, "eligible": len(kept), "dropped": dict(drops.most_common()),
              "steps_in_eligible": dict(steps_kept.most_common()), "steps_in_dropped": dict(steps_dropped.most_common()),
              "selected_trajectories": len(chosen), "selected_rows": total, "target_rows": a.target_rows,
              "mean_steps_selected": round(total / max(len(chosen), 1), 2), "seed": a.seed,
              "unresolved_target_steps_selected": sum(ep["unresolved_targets"] for _, ep, _ in chosen)}
    print(json.dumps(report, indent=1))
    if a.dry_run:
        return report
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for tid, ep, rows in chosen:
        d = out / tid
        d.mkdir(exist_ok=True)
        (d / "episode.json").write_text(json.dumps(ep, ensure_ascii=False, indent=1))
        (d / "rows.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    (out / "_report.json").write_text(json.dumps(report, indent=1))
    print(f"wrote {len(chosen)} trajectories, {total} rows -> {out}")
    return report


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
