"""The day phase: the day t-1 agent attempts the day's tasks while a human watches and corrects it.

    python -m daynight.day --config <cfg> --day <t> [--model mock] [--human simulated|real|none] [--tasks N]

Writes `<out>/day_<t>/episodes.jsonl` (schema.Episode) and each episode's artifacts under `<out>/day_<t>/episodes/`.
With `probe.enabled`, the same agent also runs the fixed probe set with no human first (`probe.jsonl`). The loop
(daynight.loop) calls `run_day`; this CLI runs one day on its own, e.g. a session with a real human.
"""
from __future__ import annotations

import argparse
import asyncio
import json

from daynight import config as C
from daynight.human_sim import make_human
from daynight.schema import write_jsonl
from daynight.world import make_backend


def day0_agent(cfg):
    a = cfg["agent"]
    path = a.get("executor_path")
    if C.is_mock(cfg) and path and not (C.ROOT / path).exists():
        path = None                                  # the mock day-0 executor: world.initial_skills
    return {"planner": a["planner"], "executor": a["executor"], "executor_path": path, "version": a["version"],
            "day": 0}


def run_probe(cfg, day, backend, agent):
    tasks = backend.probe_tasks()
    if not cfg["probe"].get("enabled") or not tasks:
        return []
    d = C.day_dir(cfg, day)
    print(f"day {day}: probe, {len(tasks)} tasks, agent {agent['executor']}, no human", flush=True)
    eps = asyncio.run(backend.run_many(tasks, agent, None, day, d / "probe", workers=cfg["workers"]))
    write_jsonl(d / "probe.jsonl", eps)
    return eps


def run_day(cfg, day, backend, agent, human=None, n=None):
    tasks = backend.day_tasks(day, n or cfg["tasks_per_day"])
    d = C.day_dir(cfg, day)
    print(f"day {day}: {len(tasks)} tasks, agent {agent['executor']}, human {human.actor if human else 'none'}",
          flush=True)
    eps = asyncio.run(backend.run_many(tasks, agent, human, day, d / "episodes", workers=cfg["workers"]))
    write_jsonl(d / "episodes.jsonl", eps)
    return eps


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m daynight.day")
    ap.add_argument("--config", required=True)
    ap.add_argument("--day", type=int, required=True)
    ap.add_argument("--model", default=None, help="mock: the mock world and stand-ins (no browser, GPU or API key)")
    ap.add_argument("--human", default=None, choices=["simulated", "real", "none"])
    ap.add_argument("--tasks", type=int, default=None, help="tasks this day (default: tasks_per_day)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-probe", action="store_true")
    args = ap.parse_args(argv)
    cfg = C.load(args.config, model=args.model, out=args.out)
    if args.human:
        cfg["human"]["kind"] = args.human
    if args.no_probe:
        cfg["probe"]["enabled"] = False
    d = C.day_dir(cfg, args.day)
    if (d / "episodes.jsonl").exists():
        raise SystemExit(f"{d}/episodes.jsonl exists; pick another --day or --out (nothing is overwritten)")
    state = C.out_dir(cfg) / "state.json"
    agent = json.loads(state.read_text())["agent"] if state.exists() else day0_agent(cfg)
    backend = make_backend(cfg)
    run_probe(cfg, args.day, backend, agent)
    eps = run_day(cfg, args.day, backend, agent, make_human(cfg), n=args.tasks)
    ok = sum(bool(e.outcome and e.outcome.passed) for e in eps)
    print(f"day {args.day}: {ok}/{len(eps)} passed, {sum(len(e.interventions) for e in eps)} interventions -> "
          f"{d / 'episodes.jsonl'}", flush=True)


if __name__ == "__main__":
    main()
