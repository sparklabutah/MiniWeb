"""InSTA's tasks regenerated through our harness (user, 2026-10-07: "regen InSTA trajectories by rerunning it through
our harness with the 4B web executor, treat its trajectory as a guide and use the same approach we did for web gen").

The matched-size comparison of Sec. 4.4 trains one executor on our generated data and one on InSTA's released SFT
trajectories, which differ from ours in more than what they practice: another agent made them, in another harness, and
they are text only. Here InSTA's tasks are run again by the base Qwen3.5-4B (user's choice) in our browser-use harness,
with screenshots, on the live sites, with InSTA's own trajectory as a privileged guide: its steps, as actions on named
elements, are appended to the task while acting (never its final answer, which the agent must read off the page).
As MiniWebGen keeps privileged inputs out of trajectories, the guide is stripped from every recorded prompt
(webmix.om2w --hint-field hint --record-rows). Episodes are gated by the WebVoyager judge's prompt with Gemini 3.5
Flash-Lite (user's choice), and kept ones are selected to the same step count as our data (27,646).

    python -m webmix.insta_regen tasks [--out data/webmix/insta/regen/tasks.json]
    python -m webmix.om2w --arm base --bench om2w --tasks data/webmix/insta/regen/tasks.json --hint-field hint \\
        --record-rows --max-steps 40 --workers 12 --out <run dir>                                   # (granite)
    python -m webmix.om2w_judge <run dir> --bench webvoyager --model gemini-3.5-flash-lite --suffix _gate
    python -m webmix.insta_regen rows <run dir> [<run dir> ...] [--out data/webmix/insta/regen/rows_27k]
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import copy
import importlib.util
import json
import random
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

from webmix import replay as R

ROOT = Path(__file__).resolve().parent.parent
REGEN = ROOT / "data" / "webmix" / "insta" / "regen"
ARM_ROWS = ROOT / "data" / "webmix" / "insta" / "rows_27k"           # the current InSTA arm (text-only conversion)
TARGET_ROWS = 27646                                                 # our 3.1K pool's training steps
HINT_HEAD = ("Hint (from an earlier successful attempt at this task; the pages may have changed since, so check each "
             "step against the page and adapt; do not mention this hint):")
TAG_WORDS = {"a": "link", "button": "button", "input": "text field", "textarea": "text box", "select": "dropdown",
             "img": "image", "li": "item", "option": "option", "label": "label"}
LEAK = re.compile(r"\bhint\b|earlier (successful )?attempt|previous (successful )?attempt|suggested steps", re.I)
# What may not appear in a rewritten memory, an answer or a prompt's history: the hint itself or its header's phrase.
# "previous attempt" alone is the agent's own earlier step (30 of the 32 sample drops under LEAK were that).
LEAK_STRICT = re.compile(r"\bhint\b|earlier successful attempt", re.I)


def _converter():
    """scripts/insta_to_rows.py: InSTA's parser (trajectories, viewport markdown, its Unmappable rule)."""
    spec = importlib.util.spec_from_file_location("insta_to_rows", ROOT / "scripts" / "insta_to_rows.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _step_line(C, step):
    act = step["act"] or {}
    key, kw, eid = act.get("action_key"), act.get("action_kwargs") or {}, act.get("target_element_id")
    _, elems, _ = C.parse_markdown(step["markdown"], C.forced_tags(act))
    tag, label = elems.get(eid, ("element", ""))
    kind = TAG_WORDS.get(tag.split()[0], "element")
    what = f'the {kind} "{label[:60]}"' if label else f"the {kind}"
    if key == "click":
        return f"Click {what}."
    if key == "fill":
        return f'Type "{kw.get("value", "")}" into {what}.'
    if key == "select_option":
        return f'Choose "{kw.get("label", "")}" in {what}.'
    if key == "scroll":
        return "Scroll " + ("down." if float(kw.get("delta_y") or 0) > 0 else "up.")
    if key == "goto":
        return f"Go to {kw.get('url', '')}."
    if key == "go_back":
        return "Go back to the previous page."
    if key == "stop":
        return "Read the answer off the page and finish with it."
    return None


def build_tasks(out, seed=20261007):
    """-> tasks.json in webmix.om2w's shape (task_id, confirmed_task, website, level) plus hint, max_steps, in_arm:
    every InSTA trajectory our converter accepts, the current arm's 3,691 first (the same tasks, so only the
    trajectories change), then the rest of the shard in a fixed shuffle (top-up when fewer pass the gate)."""
    C = _converter()
    arm = {p.name for p in ARM_ROWS.glob("insta-*")}
    tasks, seen = [], set()
    for traj in C.trajectories(C.read_examples([str(p) for p in sorted((ROOT / "data/webmix/insta/raw").glob(
            "sft_train-*.parquet"))])):
        try:
            tid, ep, rows = C.convert(traj, "")
        except C.Unmappable:
            continue
        if tid in seen or not str(ep["start_url"]).startswith(("http://", "https://")):
            continue                                                # 402 trajectories have no parsed start URL
        seen.add(tid)
        lines = [x for x in (_step_line(C, s) for s in traj) if x]
        tasks.append({"task_id": tid, "confirmed_task": ep["instruction"], "website": ep["start_url"],
                      "level": "insta", "source": "btrabucco/insta-150k-v2-sft",
                      "hint": HINT_HEAD + "\n" + "\n".join(f"{i + 1}. {x}" for i, x in enumerate(lines)),
                      "insta_steps": len(traj), "max_steps": min(40, 2 * len(traj) + 6), "in_arm": tid in arm})
    first = [t for t in tasks if t["in_arm"]]
    rest = [t for t in tasks if not t["in_arm"]]
    random.Random(seed).shuffle(rest)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(first + rest, ensure_ascii=False))
    print(f"wrote {len(first) + len(rest)} tasks ({len(first)} of the arm's {len(arm)}, {len(rest)} more) -> {out}")


def _texts(messages, fn):
    """messages with fn applied to every text (string contents and text parts)."""
    out = copy.deepcopy(messages)
    for m in out:
        c = m.get("content")
        if isinstance(c, str):
            m["content"] = fn(c)
        elif isinstance(c, list):
            for part in c:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    part["text"] = fn(part["text"])
    return out


def _inline(messages, d):
    """Saved messages (screenshots by file name, as webmix.train reads them) -> sendable ones (data URLs)."""
    out = copy.deepcopy(messages)
    for m in out:
        for part in m.get("content") if isinstance(m.get("content"), list) else []:
            u = (part.get("image_url") or {}).get("url") if isinstance(part, dict) else None
            if u and not u.startswith("data:"):
                part["image_url"]["url"] = "data:image/png;base64," + base64.b64encode((d / u).read_bytes()).decode()
    return out


async def rewrite(ep_rows):
    """One kept episode's rows with every memory written again by the base model from the hint-free prompt, as
    MiniWebGen's replay writes them (2026-10-07: the acting model mentioned the hint in 131 of 177 kept sample
    episodes); each new memory replaces the old one in the later steps' history. -> rows, or None (dropped)."""
    rows = [json.loads(l) for l in (ep_rows / "rows.jsonl").read_text().split("\n") if l.strip()]
    subs, out = [], []
    for t, r in enumerate(rows):
        msgs = _texts(r["messages"], lambda x: _sub_all(x, subs))
        tgt = json.loads(r["target"])
        act = (tgt.get("action") or [{}])[0]
        if "done" in act and LEAK_STRICT.search(json.dumps(act, ensure_ascii=False)):
            return None                                             # the answer itself mentions the hint
        mem, _ = await R.write_memory(_inline(msgs, ep_rows), act, {"op": "step"}, first=t == 0)
        if not mem or LEAK_STRICT.search(mem):
            return None
        if tgt.get("memory"):
            subs.append((tgt["memory"], mem))
        tgt["memory"] = mem
        out.append({**r, "messages": msgs, "target": json.dumps(tgt, ensure_ascii=False),
                    "memory_by": R.MEMORY_LLM.get("model")})
    if any(LEAK_STRICT.search(json.dumps(r["messages"][1:], ensure_ascii=False)) for r in out):
        return None                                                 # an old memory left in some step's history
    return out


def _sub_all(text, subs):
    for old, new in subs:
        text = text.replace(old, new)
    return text


def build_rows(run_dirs, out, target=TARGET_ROWS, suffix="_gate", workers=24):
    """Kept episodes -> <out>/<task>/{rows.jsonl, step_*.png, episode.json}, in tasks.json order until `target` rows.
    Kept: the gate says SUCCESS, rows were recorded, no hint text is left in a prompt, and every memory rewrites
    cleanly (rewrite)."""
    order = {t["task_id"]: i for i, t in enumerate(json.loads((REGEN / "tasks.json").read_text()))}
    why, pool = Counter(), []
    for rd in map(Path, run_dirs):
        gate = Path(str(rd) + suffix)
        for ep in sorted(d for d in rd.iterdir() if d.is_dir() and (d / "result.json").exists()):
            g = gate / f"{ep.name}.json"
            if not g.exists():
                why["not judged"] += 1
                continue
            if json.loads(g.read_text()).get("predicted_label") != 1:
                why["gate: not success"] += 1
                continue
            rows_f, meta_f = ep / "rows" / "rows.jsonl", ep / "rows" / "episode.json"
            if not rows_f.exists() or not rows_f.read_text().strip():
                why["no rows"] += 1
                continue
            if json.loads(meta_f.read_text()).get("hint_left"):
                why["hint left in a prompt"] += 1
                continue
            pool.append((order.get(ep.name, 10 ** 9), ep))
    pool.sort(key=lambda x: x[0])
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)

    async def run():
        total, n, i, sem = 0, 0, 0, asyncio.Semaphore(workers)

        async def one(ep):
            async with sem:
                try:
                    return ep, await rewrite(ep / "rows")
                except Exception as e:                              # noqa: BLE001
                    return ep, e
        while total < target and i < len(pool):
            batch = [ep for _, ep in pool[i:i + workers * 2]]
            i += len(batch)
            for ep, rows in await asyncio.gather(*(one(ep) for ep in batch)):
                if not isinstance(rows, list):
                    why["rewrite failed" if rows is None else f"rewrite error: {type(rows).__name__}"] += 1
                    continue
                if total >= target:
                    break
                d = out / ep.name
                d.mkdir(parents=True, exist_ok=True)
                for img in (ep / "rows").glob("step_*.png"):
                    shutil.copy(img, d / img.name)
                shutil.copy(ep / "rows" / "episode.json", d / "episode.json")
                (d / "rows.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
                total, n = total + len(rows), n + 1
            print(f"  {n} episodes, {total} rows ({i} of {len(pool)} candidates tried)", flush=True)
        return total, n, i
    total, n, tried = asyncio.run(run())
    report = {"kept_candidates": len(pool), "tried": tried, "selected_trajectories": n, "selected_rows": total,
              "target_rows": target, "dropped": dict(why.most_common()), "short_by": max(0, target - total)}
    (out / "_report.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m webmix.insta_regen")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("tasks")
    t.add_argument("--out", default=str(REGEN / "tasks.json"))
    r = sub.add_parser("rows")
    r.add_argument("run_dirs", nargs="+")
    r.add_argument("--out", default=str(REGEN / "rows_27k"))
    r.add_argument("--target", type=int, default=TARGET_ROWS)
    r.add_argument("--suffix", default="_gate")
    r.add_argument("--workers", type=int, default=24, help="episodes rewritten at once")
    r.add_argument("--memory-model", default="qwen35-4b")
    r.add_argument("--memory-url", default="http://127.0.0.1:8400/v1")
    a = ap.parse_args(argv)
    if a.cmd == "tasks":
        return build_tasks(a.out)
    R.configure_memory(a.memory_url, a.memory_model)
    return build_rows(a.run_dirs, a.out, a.target, a.suffix, a.workers)


if __name__ == "__main__":
    sys.exit(main())
