"""Day 1, night 1, day 2, ...: the continual learning loop.

    python -m daynight.loop --config daynight/configs/v1_mock.yaml                 # dry run, seconds, no GPU / keys
    python -m daynight.loop --config daynight/configs/v1_sim.yaml                  # real: stops at each night's plan
    python -m daynight.loop --config daynight/configs/v1_sim.yaml --resume         # ... after running night_plan.sh
    python -m daynight.loop --config daynight/configs/v1_sim.yaml --resume --execute   # runs the nights itself

Flags: --model mock (mock everything), --days N, --tasks-per-day N, --out DIR, --resume, --execute.

Each day t: the probe (fixed tasks, no human) and the day's tasks (with the human), both by the day t-1 agent. Each
night t: the meta agent's analyses and summary, the proposals, then generation, replay, training and serving of the
day t executor. After the last night, the last agent runs the probe once more (day N+1, probe only).

Real nights use MiniWebGen (Gemini: paid API), the replay (the base model on vLLM) and training (GPUs). Without
--execute the loop writes `<out>/day_<t>/night_plan.sh` and stops; run it, then --resume. With --execute it runs the
plan itself. Either way the loop never starts or stops a model server: it prints the serve line for the new adapter
and (with --execute) waits until the server lists it.

State is `<out>/state.json`; an existing experiment is never overwritten (use --resume or another --out).
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from dataclasses import asdict

import yaml

from daynight import config as C
from daynight import metrics as M
from daynight import propose as P
from daynight import stubs
from daynight import train as T
from daynight.day import day0_agent, run_day, run_probe
from daynight.human_sim import make_human
from daynight.meta import make_meta, summarize
from daynight.schema import read_episodes, write_jsonl
from daynight.world import make_backend


def _save(path, state):
    path.write_text(json.dumps(state, indent=1, default=str))


def night(cfg, t, state, meta, execute):
    """Analyze day t, propose, and (mock / --execute) generate + train. -> the next phase."""
    d = C.day_dir(cfg, t)
    eps = read_episodes(d / "episodes.jsonl")
    print(f"night {t}: analyzing {len(eps)} episodes ({meta.source})", flush=True)
    analyses = [meta.analyze(ep) for ep in eps]
    write_jsonl(d / "analysis.jsonl", analyses)
    summary = summarize(eps, analyses)
    (d / "summary.json").write_text(json.dumps(summary, indent=1))
    proposals = P.propose(summary, cfg, eps)
    plan = stubs.choose_method(summary, cfg)
    (d / "proposals.json").write_text(json.dumps(
        {"proposals": [asdict(p) for p in proposals],
         "env_changes": [asdict(x) for x in stubs.propose_env_changes(summary, cfg)],
         "training": asdict(plan)}, indent=1))
    print(f"night {t}: {summary['notes']}", flush=True)
    for p in proposals:
        print(f"  propose {p.macro}: {p.target} trajectories (weakness {p.weakness}; {p.rationale})", flush=True)
    if not proposals:
        print(f"night {t}: nothing to practice; the day {t} agent is the day {t - 1} agent", flush=True)
        state["next_agent"] = dict(state["agent"], day=t)
        return "serve"

    P.seed_datagen_dir(cfg)
    cfg_path = C.out_dir(cfg) / "config.yaml"
    py = os.path.expanduser(cfg["envs"]["miniweb_python"])
    steps = P.night_commands(cfg, t, proposals) + [
        ("rows", f"{py} -m daynight.train build-rows --config {shlex.quote(str(cfg_path))} --day {t}"),
        ("train", T.train_command(cfg, t, state["agent"].get("executor_path")))]
    script = ["#!/usr/bin/env bash", f"# night {t} of {cfg['name']}"
              + (" (mock: the loop ran stand-ins of these steps; this is what a real night runs)" if C.is_mock(cfg)
                 else ""), "set -euo pipefail", f"cd {shlex.quote(str(C.ROOT))}"]
    script += [f"# {stage}\n{cmd}" for stage, cmd in steps]
    script += [f"# then serve the new executor (the loop waits for it):\n# {T.serve_command(cfg, t)}"]
    (d / "night_plan.sh").write_text("\n".join(script) + "\n")
    state["next_agent"] = {"planner": state["agent"]["planner"], "executor": T.served_name(cfg, t),
                           "executor_path": str(T.adapter_dir(cfg, t)), "version": state["agent"]["version"], "day": t}

    if C.is_mock(cfg):
        made = P.mock_generate(cfg, t, proposals)
        man = T.build_rows(cfg, t)
        T.mock_train(cfg, t, state["agent"].get("executor_path"), man)
        print(f"night {t}: mock generation {made}, trained {T.adapter_dir(cfg, t)}", flush=True)
        return "serve"
    if not execute:
        print(f"night {t}: plan written to {d / 'night_plan.sh'}\n  run it, then: python -m daynight.loop --config "
              f"{cfg_path} --resume", flush=True)
        return "planned"
    for stage, cmd in steps:
        print(f"night {t}: {stage}\n  $ {cmd}", flush=True)
        if stage == "rows":
            T.build_rows(cfg, t)
        else:
            subprocess.run(cmd, shell=True, cwd=C.ROOT, check=True)
    return "serve"


def serve(cfg, t, state, execute):
    """-> True once the day t agent is usable (mock: always)."""
    nxt = state["next_agent"]
    if C.is_mock(cfg) or nxt["executor"] == state["agent"]["executor"]:
        return True
    if not T.adapter_ready(nxt["executor_path"]):
        print(f"night {t}: no trained adapter in {nxt['executor_path']} yet (run {C.day_dir(cfg, t)}/night_plan.sh)",
              flush=True)
        return False
    vllm, name = cfg["agent"]["vllm"], nxt["executor"]
    try:
        if name in T.served_models(vllm):
            return True
    except OSError:
        pass
    print(f"night {t}: serve the new executor, keeping the base model served:\n  {T.serve_command(cfg, t)}", flush=True)
    if not execute:
        print("  then run the loop again with --resume", flush=True)
        return False
    print(f"  waiting until {vllm} lists {name} ...", flush=True)
    return T.wait_for_adapter(vllm, name)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m daynight.loop")
    ap.add_argument("--config", required=True)
    ap.add_argument("--model", default=None, help="mock: the mock world and stand-ins for every model")
    ap.add_argument("--days", type=int, default=None)
    ap.add_argument("--tasks-per-day", type=int, default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--resume", action="store_true", help="continue the experiment in --out")
    ap.add_argument("--execute", action="store_true",
                    help="real nights: run generation (paid API), replay and training (GPU) instead of stopping")
    args = ap.parse_args(argv)
    cfg = C.load(args.config, model=args.model, days=args.days, tasks_per_day=args.tasks_per_day, out=args.out)
    out = C.out_dir(cfg)
    sp = out / "state.json"
    if sp.exists() and not args.resume:
        sys.exit(f"{out} already holds an experiment; --resume it or pick another --out (nothing is overwritten)")
    out.mkdir(parents=True, exist_ok=True)
    if not (out / "config.yaml").exists() or not args.resume:
        (out / "config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    state = json.loads(sp.read_text()) if sp.exists() else {"day": 1, "phase": "day", "agent": day0_agent(cfg)}
    _save(sp, state)
    backend, human, meta = make_backend(cfg), make_human(cfg), make_meta(cfg)
    print(f"{cfg['name']}: {cfg['backend']} backend, human {cfg['human']['kind']}, days {state['day']}..{cfg['days']}, "
          f"out {out}", flush=True)

    while state["day"] <= cfg["days"]:
        t = state["day"]
        if state["phase"] == "day":
            run_probe(cfg, t, backend, state["agent"])
            run_day(cfg, t, backend, state["agent"], human)
            state["phase"] = "night"
            _save(sp, state)
        if state["phase"] == "night":
            state["phase"] = night(cfg, t, state, meta, args.execute)
            _save(sp, state)
        if state["phase"] == "planned":
            state["phase"] = "serve"
            _save(sp, state)
        if state["phase"] == "serve":
            if not serve(cfg, t, state, args.execute):
                _save(sp, state)
                return
            state.update(agent=state.pop("next_agent"), day=t + 1, phase="day")
            _save(sp, state)
            M.collect(cfg)

    if state["phase"] == "day":                      # the last night's agent, once more on the probe
        run_probe(cfg, state["day"], backend, state["agent"])
        state["phase"] = "done"
        _save(sp, state)
    print(M.table(M.collect(cfg)), flush=True)
    print(f"metrics: {out / 'metrics.jsonl'}", flush=True)


if __name__ == "__main__":
    main()
