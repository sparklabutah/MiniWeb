"""Online-Mind2Web (300 tasks on 136 live websites; osunlp/Online-Mind2Web) and WebVoyager (643 tasks on 15 live
sites; --bench webvoyager) through the WebMix browser-use harness.

    python -m webmix.om2w --arm base --model qwen35-4b --out data/webmix/om2w/runs/base --workers 12
    python -m webmix.om2w --arm agent --agent-version v6 --out data/webmix/om2w/runs/agent_v4spec --workers 12

Each task starts on its specified website (the benchmark's rule), in a browser with the live web reachable
(harness.make_session(online=True); MiniWeb and WebArena stay offline). An episode is saved in the benchmark's v1
trajectory layout -- <out>/<task_id>/result.json (task, factual action_history without agent text, thoughts,
final_result_response) and trajectory/<i>_full_screenshot.png -- for the official WebJudge (o4-mini), run locally
afterwards (no API keys on the cluster). Arms: `base`, the untrained model as one agent; `agent`, the planner agent
(webmix.planner_agent) delegating to the family specialists served under drag/io/select/rest/reasoning on --vllm.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

from webmix import harness as H

ROOT = Path(__file__).resolve().parent.parent
TASKS = ROOT / "data" / "webmix" / "om2w" / "Online_Mind2Web.json"
NOT_ACTIONS = {"done", "macro_done"}               # the answer goes to final_result_response, not the action history


WEBVOYAGER = ROOT / "data" / "webmix" / "webvoyager" / "WebVoyager_data_2026-10-01.jsonl"   # dates updated, see README


def load_tasks(path=None, bench="om2w"):
    """Online-Mind2Web's tasks, or WebVoyager's (643 tasks on 15 live sites, MinorJerry/WebVoyager) in the same shape:
    task_id, confirmed_task, website, level (WebVoyager: the site name)."""
    if bench == "webvoyager":
        rows = [json.loads(line) for line in Path(path or WEBVOYAGER).read_text().split("\n") if line.strip()]
        return [{"task_id": r["id"], "confirmed_task": r["ques"], "website": r["web"], "level": r["web_name"]}
                for r in rows]
    return json.loads(Path(path or TASKS).read_text())


def _element(el):
    """'<tag attr="...">' for an interacted element (the benchmark's action-history style)."""
    if el is None:
        return ""
    tag = getattr(el, "node_name", None) or "element"
    attrs = getattr(el, "attributes", None) or {}
    keep = {k: v for k, v in attrs.items() if k in ("id", "aria-label", "name", "placeholder", "title", "href", "role",
                                                    "type", "value", "alt") and v}
    name = getattr(el, "ax_name", None)
    text = " ".join(f'{k}="{str(v)[:80]}"' for k, v in keep.items())
    return f"<{str(tag).lower()}{' ' + text if text else ''}>{' ' + str(name)[:80] if name else ''}"


def _action_line(name, params, el):
    params = params or {}
    if name in ("click", "dropdown_options"):
        if el is None:
            x, y = params.get("coordinate_x"), params.get("coordinate_y")
            if x or y:                                   # a coordinate click (0-1000 screen scale): no element
                return f"CLICK at ({x}, {y}) of 1000"
            return f"<element index={params.get('index')}> -> CLICK"     # no element matched the index
        return f"{_element(el)} -> CLICK"
    if name == "input":
        return f"{_element(el)} -> TYPE: {params.get('text', '')}"
    if name == "select_dropdown":
        return f"{_element(el)} -> SELECT: {params.get('text', '')}"
    if name == "navigate":
        return f"NAVIGATE -> {params.get('url', '')}"
    if name == "scroll":
        return f"SCROLL {'DOWN' if params.get('down', True) else 'UP'}"
    if name == "send_keys":
        return f"KEYS: {params.get('keys', '')}"
    if name == "go_back":
        return "GO BACK"
    if name in ("drag", "draw"):
        return f"{name.upper()} {json.dumps(params)[:120]}"
    return f"{name.upper()} {json.dumps(params)[:120]}"


PLANNER_SKIP = {"delegate"}                          # the specialists' own actions are recorded instead


def _ordered_steps(hists, planner_hist=None):
    """The histories' steps in order. With the planner agent's own history (v7, 2026-10-02) its steps are merged in by
    start time: each planner turn's screenshot is what it looked at before delegating, and its scrolls are how it read
    an answer, so the judge sees the page the answer came from (before v7: specialist screenshots only)."""
    if planner_hist is None:
        return [st for h in hists for st in h.history]
    steps = [(st, False) for h in hists for st in h.history] + [(st, True) for st in planner_hist.history]
    key = lambda x: (getattr(getattr(x[0], "metadata", None), "step_start_time", None) or 0.0)   # noqa: E731
    return [(st, True) if is_p else st for st, is_p in sorted(steps, key=key)]


def trajectory(hists, planner_hist=None):
    """-> (action lines, thoughts, screenshot paths) over one or more browser-use histories, in order (with the
    planner's own steps merged in when planner_hist is given)."""
    actions, thoughts, shots = [], [], []
    for item in _ordered_steps(hists, planner_hist):
        st, planner = item if isinstance(item, tuple) else (item, False)
        state = getattr(st, "state", None)
        sp = getattr(state, "screenshot_path", None)
        if sp and Path(sp).exists():
            shots.append(sp)
        mo = st.model_output
        if mo is None:
            continue
        els = list(getattr(state, "interacted_element", None) or [])
        for k, a in enumerate(mo.action or []):
            d = a.model_dump(exclude_none=True)
            name = next(iter(d), "")
            if name in NOT_ACTIONS or (planner and name in PLANNER_SKIP):
                continue
            actions.append(_action_line(name, d.get(name), els[k] if k < len(els) else None))
            thoughts.append(str(getattr(mo, "next_goal", None) or getattr(mo, "memory", None) or "")[:400])
    return actions, thoughts, shots


def pick_model(args):
    from webmix.evaluate import sub_model
    margs = SimpleNamespace(adapters=set(args.adapters.split(",")) - {"none", ""}, fallback=args.fallback,
                            base_name=args.model, reasoning_to_fallback=False, alias="")
    return lambda fam: sub_model(fam, margs)


async def run_task(task, args, out_dir):
    from browser_use import Agent
    t0 = time.time()
    tid = task["task_id"]
    ep = out_dir / tid
    (ep / "trajectory").mkdir(parents=True, exist_ok=True)
    res = {"task_id": tid, "arm": args.arm, "website": task["website"], "level": task.get("level")}
    bs = H.make_session(online=True)
    hists, answer, planner_hist = [], None, None
    box, agent = {}, None                          # what ran so far, kept when the safety timeout cuts an episode
    try:
        await bs.start()
        await H.enable_clipboard(bs)
        await H.goto(bs, task["website"])
        if args.arm == "agent":
            from webmix.planner_agent import run_planner_agent
            hist, trace, ph = await asyncio.wait_for(
                run_planner_agent(bs, task["confirmed_task"], task["website"], pick_model(args), args.vllm,
                                  args.planner_name, temperature=args.temperature, version=args.agent_version,
                                  expose=box, budget=args.max_steps, turns=args.planner_turns),
                timeout=args.timeout)
            hists, answer = hist.hists, hist.final_result()
            planner_hist = ph
            ph.save_to_file(ep / "planner_history.json")
            (ep / "subtasks.json").write_text(json.dumps({"trace": trace}, indent=1, default=str, ensure_ascii=False))
        else:
            agent = Agent(task=H.instruction(task["confirmed_task"], task["website"]),
                          llm=H.make_llm(args.model, base_url=args.vllm, temperature=args.temperature),
                          browser_session=bs, tools=H.make_tools(), max_failures=3, **H.AGENT_KWARGS)
            H.use_normalized_coordinates(bs)
            h = await asyncio.wait_for(agent.run(max_steps=args.max_steps,
                                                 on_step_start=lambda a: H.enable_clipboard(bs, a)),
                                       timeout=args.timeout)
            hists, answer = [h], h.final_result()
        try:                                       # the final state, after the last action
            final_png = await bs.take_screenshot()
        except Exception:
            final_png = None
    except asyncio.TimeoutError:
        # 2026-10-01: a timed-out episode used to lose its whole trajectory (0 steps saved), so the judge saw nothing;
        # keep the steps taken (the planner agent's finished and running specialists, or the base agent's history)
        res["error"], final_png = "timeout", None
        team = box.get("team")
        if team is not None:
            hists = list(team.hists) + ([team.current.history] if team.current is not None else [])
            if box.get("planner") is not None:
                planner_hist = box["planner"].history
        elif agent is not None:
            hists = [agent.history]
        try:
            final_png = await bs.take_screenshot()
        except Exception:
            final_png = None
    except Exception as e:
        res["error"], final_png = f"{type(e).__name__}: {str(e)[:300]}", None
    finally:
        try:
            await bs.kill()
        except Exception:
            pass
    from webmix.planner_agent import VERSIONS as _PV
    record_planner = args.arm == "agent" and _PV.get(args.agent_version, {}).get("v7")
    actions, thoughts, shots = trajectory(hists, planner_hist if record_planner else None)
    for i, sp in enumerate(shots):
        shutil.copy(sp, ep / "trajectory" / f"{i}_full_screenshot.png")
    if final_png:
        (ep / "trajectory" / f"{len(shots)}_full_screenshot.png").write_bytes(final_png)
    (ep / "result.json").write_text(json.dumps({
        "task_id": tid, "task": task["confirmed_task"], "final_result_response": answer or "",
        "action_history": actions, "thoughts": thoughts}, indent=1, ensure_ascii=False))
    for i, h in enumerate(hists):
        try:
            h.save_to_file(ep / f"history_{i}.json")
        except Exception:
            pass
    res.update(steps=sum(len(h.history) for h in hists), actions=len(actions), screenshots=len(shots) + bool(final_png),
               answer=(answer or "")[:500], duration_s=round(time.time() - t0, 1))
    return res


def _domain(url):
    import re
    return re.sub(r"^https?://(www\.)?", "", url).split("/")[0].lower()


class Pacer:
    """Polite pacing (2026-10-01, user: "pace OM2W"): at most one episode per website at a time across every run on
    this node (an flock per domain in a node-local dir), and `cooldown` seconds between the end of one episode on a site
    and the start of the next. Bot checks rose with request volume from one IP; every arm is paced the same way."""

    def __init__(self, lock_dir, cooldown):
        self.dir, self.cooldown = Path(lock_dir), cooldown
        self.dir.mkdir(parents=True, exist_ok=True)
        self.held = None

    def try_acquire(self, dom):
        import fcntl
        f = open(self.dir / f"{dom}.lock", "a+")
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            f.close()
            return False
        stamp = self.dir / f"{dom}.last"
        if stamp.exists() and time.time() - stamp.stat().st_mtime < self.cooldown:
            fcntl.flock(f, fcntl.LOCK_UN)
            f.close()
            return False
        self.held = f
        return True

    def release(self, dom):
        import fcntl
        (self.dir / f"{dom}.last").touch()
        if self.held is not None:
            fcntl.flock(self.held, fcntl.LOCK_UN)
            self.held.close()
            self.held = None


def worker(args):
    out_dir = Path(args.out)
    tasks = load_tasks(args.tasks, args.bench)
    if args.task_ids:
        tasks = [t for t in tasks if t["task_id"] in args.task_ids]
    tasks = [t for k, t in enumerate(tasks) if k % args.n_workers == args.slot]
    if args.limit:
        tasks = tasks[:args.limit]
    res_path = out_dir / f"results_{args.slot}.jsonl"
    # every slot file, not just this slot's: the worker count may change between launches and a run may be split
    # across nodes (--slot-range), so a finished episode is never re-run (2026-10-01)
    done = {json.loads(line)["task_id"] for f in out_dir.glob("results_*.jsonl")
            for line in f.read_text().split("\n") if line.strip()}
    pending = [t for t in tasks if t["task_id"] not in done]
    pacer = Pacer(args.pace_dir, args.pace_cooldown) if args.pace_dir else None
    while pending:
        if pacer:                                  # the first task whose site is free and cooled down
            t = next((x for x in pending if pacer.try_acquire(_domain(x["website"]))), None)
            if t is None:
                time.sleep(15)
                continue
        else:
            t = pending[0]
        pending.remove(t)
        try:
            res = asyncio.run(run_task(t, args, out_dir))
        finally:
            if pacer:
                pacer.release(_domain(t["website"]))
        with open(res_path, "a") as f:
            f.write(json.dumps(res, default=str) + "\n")
        print(f"[w{args.slot}] {t['task_id']} {t.get('level')} {res.get('steps')} steps {res['duration_s']}s "
              f"{res.get('error') or ''}", flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m webmix.om2w")
    ap.add_argument("--arm", required=True, choices=["base", "agent"])
    ap.add_argument("--model", default="qwen35-4b", help="the base model's served name")
    ap.add_argument("--vllm", default="http://127.0.0.1:8400/v1")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--agent-version", default="v6")
    ap.add_argument("--planner-name", default="qwen35-4b")
    ap.add_argument("--adapters", default="drag,io,select,rest,reasoning")
    ap.add_argument("--fallback", default="pooled_v4")
    ap.add_argument("--max-steps", type=int, default=H.MAX_STEPS,
                    help="base: agent steps; agent: the specialists' site-action budget")
    ap.add_argument("--planner-turns", type=int, default=None, help="agent: planner-turn cap (default: the version's)")
    ap.add_argument("--pace-dir", default=None, help="node-local dir of per-site locks shared by every run (pacing)")
    ap.add_argument("--pace-cooldown", type=int, default=120, help="seconds between episodes on one site")
    ap.add_argument("--bench", default="om2w", choices=["om2w", "webvoyager"])
    ap.add_argument("--tasks", default=None, help="task file (default: the benchmark's)")
    ap.add_argument("--task-ids", type=lambda s: set(s.split(",")), default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", required=True)
    ap.add_argument("--slot-range", default=None, help="a:b = run only slots a..b-1 of --workers here (split a run "
                                                         "across nodes; the other node runs the rest)")
    ap.add_argument("--slot", type=int, default=None)          # internal: one worker
    ap.add_argument("--n-workers", type=int, default=1)
    args = ap.parse_args(argv)
    if args.slot is not None:
        return worker(args)
    Path(args.out).mkdir(parents=True, exist_ok=True)
    base = [sys.executable, "-m", "webmix.om2w"] + [a for a in (argv or sys.argv[1:])]
    procs = []
    lo, hi = (int(x) for x in args.slot_range.split(":")) if args.slot_range else (0, args.workers)
    for slot in range(lo, hi):
        log = open(Path(args.out) / f"worker_{slot}.log", "a")
        procs.append(subprocess.Popen(base + ["--slot", str(slot), "--n-workers", str(args.workers)], stdout=log,
                                      stderr=subprocess.STDOUT, cwd=str(ROOT)))
    for p in procs:
        p.wait()
    n = sum(len([x for x in f.read_text().split("\n") if x.strip()]) for f in Path(args.out).glob("results_*.jsonl"))
    print(f"{n} episodes in {args.out}")


if __name__ == "__main__":
    main()
