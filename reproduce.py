"""Reproduce the paper: one entry point for its runs, adapters, figures and tables (registry: experiments/paper.yaml).

    python reproduce.py status                      # every run the paper reads: present, complete?
    python reproduce.py show planner_pooled         # the commands behind an arm (server, runs, grading)
    python reproduce.py show rq1                    # the ten RQ1 agents
    python reproduce.py run pooled --bench heldout --seed 1 [--execute]
    python reproduce.py train pooled_v4 [--gpus 0,1,2,3] [--execute]
    python reproduce.py figures [--only rq3] [--no-copy]   # regenerate every figure/table, copy into the paper

`run` and `train` print their commands unless --execute is given. Runs assume the model server is up
(`python reproduce.py show <arm>` prints its webmix/serve.sh line); MiniWeb runs start their own app servers.
Run folders the paper reads come from the figure configs (docs/figures/tables/tables_config.yaml `runs:` and the
others); experiments/paper.yaml says how each is made.
"""
import argparse
import glob
import json
import os
import shlex
import shutil
import subprocess
import sys

import yaml

ROOT = os.path.dirname(os.path.abspath(__file__))
REG = os.path.join(ROOT, "experiments", "paper.yaml")
TABLES = os.path.join(ROOT, "docs", "figures", "tables", "tables_config.yaml")
PY = sys.executable
LIVE_WORKERS = 24          # at most 24 browsers per model server (more made LLM calls time out, Supp.)


def load():
    reg = yaml.safe_load(open(REG))
    named = yaml.safe_load(open(TABLES)).get("runs", {})
    benches = {**reg["benchmarks"], **reg.get("extra_benchmarks", {})}
    return reg, named, benches


def arm_runs(reg, named, arm):
    """{benchmark: [run folders]} the paper reads for an arm: tables_config's named runs, then the registry's own."""
    out = {b: list(v) for b, v in (named.get(arm) or {}).items()}
    out.update({b: list(v) for b, v in (reg["arms"][arm].get("runs") or {}).items()})
    return out


def raw_dir(bench, run):
    """The episode folder of a live-web run (the paper reads the judged copy, <run>_wvjudge / _webjudge)."""
    for suf in ("_wvjudge", "_webjudge"):
        if run.endswith(suf):
            return run[: -len(suf)]
    return run


# ── status ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def done(kind, run):
    """Finished (graded) episodes in a run folder, or None when it is missing."""
    p = os.path.join(ROOT, run)
    if not os.path.isdir(p):
        return None
    if kind in ("miniweb", "webarena"):
        f = next((os.path.join(p, n) for n in ("results_regraded.jsonl", "results.jsonl")
                  if os.path.exists(os.path.join(p, n))), None)
        return 0 if f is None else len({json.loads(l)["task_id"] for l in open(f) if l.strip()})
    if kind == "webvoyager":
        return len(glob.glob(os.path.join(p, "*--*.json")))
    if kind == "om2w":
        ids = set()
        for f in glob.glob(os.path.join(p, "WebJudge*auto_eval_results.json")):
            ids |= {json.loads(l).get("task_id") for l in open(f) if l.strip()}
        return len(ids)
    raise ValueError(kind)


def status(args):
    reg, named, benches = load()
    bad = 0
    print(f"{'arm':16s} {'bench':9s} runs (finished / tasks)")
    for arm in reg["arms"]:
        for b, runs in arm_runs(reg, named, arm).items():
            if b not in benches:
                continue
            cells = []
            for r in runs:
                n = done(benches[b]["kind"], r)
                ok = n is not None and n >= benches[b]["n"]
                bad += not ok
                cells.append(f"{'' if ok else '!'}{'missing' if n is None else n}")
            print(f"{arm:16s} {b:9s} {', '.join(cells)}  (of {benches[b]['n']})")
    for group in ("browser_use", "own_loop"):
        for m in reg["rq1"][group]:
            run = f"data/webmix/eval/{m['run']}"
            n = done("miniweb", run)
            j = os.path.join(ROOT, run, "judge.jsonl")
            nj = sum(1 for l in open(j) if l.strip()) if os.path.exists(j) else 0
            ok = n is not None and n >= 376 and nj >= 375
            bad += not ok
            print(f"{'rq1':16s} {m['served']:9s} {'' if ok else '!'}{n} graded, {nj} judged  (of 376)")
    for a, spec in reg["adapters"].items():
        ok = os.path.exists(os.path.join(ROOT, "data", "webmix", "adapters", a, "adapter_model.safetensors"))
        bad += not ok
        print(f"{'adapter':16s} {a:16s} {'present' if ok else '! missing'}")
    print(f"\n{'all present and complete' if not bad else f'{bad} item(s) marked ! are missing or incomplete'}")
    return 1 if bad else 0


# ── commands ────────────────────────────────────────────────────────────────────────────────────────────────────────
def server_cmd(reg, loras):
    s = reg["server"]
    env = {"MODEL": s["model"], "SERVED": s["served"], "PORT": s["port"], **s.get("env", {})}
    if loras:
        env["LORA_MODULES"] = " ".join(f"{a}=data/webmix/adapters/{a}" for a in loras)
    return " ".join(f"{k}={shlex.quote(str(v))}" for k, v in env.items()) + " bash webmix/serve.sh"


def run_cmds(reg, benches, arm, bench, out, name):
    """[commands] that produce one run folder of an arm on a benchmark (run, then grade where needed)."""
    a, b = reg["arms"][arm], benches[bench]
    cfg = reg["configs"][a["config"]]
    kind = "live" if b["kind"] in ("webvoyager", "om2w") else b["kind"]
    ex = a["executor"]
    fmt = {"executor": ex, "adapters": a.get("adapters", "none"), "name": name,
           "arm_flag": "base" if ex == reg["server"]["served"] else f"pooled --pooled-name {ex}"}
    vllm = f"--vllm http://127.0.0.1:{reg['server']['port']}/v1"
    if kind == "miniweb":
        return [f"python {b['runner']} {cfg['miniweb'].format(**fmt)} {vllm} --ports 8300,8301 --out {out}"]
    if kind == "webarena":
        return ["bash experiments/webarena/ready.sh 1 2 3 4   # reset the four WebArena instances",
                f"python {b['runner']} {cfg['webarena'].format(**fmt)} {vllm} --out {out}"]
    raw = raw_dir(bench, out)
    base = benches[b.get("base", bench)]
    return [f"python {b['runner']} {cfg['live'].format(**fmt)} {vllm} --workers {LIVE_WORKERS} --out {raw}",
            f"python {base['judge'].format(run=raw)}   # -> {base['judged'].format(run=raw)}"]


def show(args):
    reg, named, benches = load()
    if args.arm == "rq1":
        return show_rq1(reg)
    if args.arm not in reg["arms"]:
        sys.exit(f"unknown arm {args.arm!r}; arms: {', '.join(reg['arms'])}, or rq1")
    a = reg["arms"][args.arm]
    loras = a.get("server_loras", []) + ([a["executor"]] if a["executor"] != reg["server"]["served"] else [])
    print(f"# {a.get('label', args.arm)}\n# model server (webmix env):\n{server_cmd(reg, loras)}\n")
    for b, runs in arm_runs(reg, named, args.arm).items():
        if args.bench and b != args.bench:
            continue
        print(f"# {b}: {benches[b].get('about', '')}")
        for i, r in enumerate(runs, 1):
            name = os.path.basename(raw_dir(b, r))
            for c in run_cmds(reg, benches, args.arm, b, raw_dir(b, r), name):
                print(c)
        print()
    for d in reg.get("deviations", []):
        if args.arm in d or a.get("label", "") in d:
            print("# deviation:", d)


def show_rq1(reg):
    print("# RQ1: ten untrained agents on all 376 MiniWeb tasks (Tab. 2). Browser-use agents (webmix.evaluate):")
    for m in reg["rq1"]["browser_use"]:
        env = {"MODEL": m["model"], "SERVED": m["served"], "PORT": 8400, **m.get("server_env", {})}
        print(" ".join(f"{k}={shlex.quote(str(v))}" for k, v in env.items()) + " bash webmix/serve.sh")
        print(f"python -m webmix.evaluate --human --human-split all --arm base --base-name {m['served']} --verifier-only "
              f"--workers {m.get('workers', 6)}" + (f" --timeout {m['timeout']}" if m.get("timeout") else "") +
              f" --vllm http://127.0.0.1:8400/v1 --ports 8300,8301 --out data/webmix/eval/{m['run']}")
    print("\n# Own-loop agents: prepare the tasks, run the agent's released loop, grade with the task verifiers:")
    for m in reg["rq1"]["own_loop"]:
        out = f"data/webmix/eval/{m['run']}"
        print(f"python -m webmix.fara_rq1 prep --out {out} --split all")
        print(f"#   {m['model']} via {m['loop']} (experiments/cluster/ownloop.sh)")
        print(f"python -m webmix.fara_rq1 grade --out {out} --arm {m['served']}")
    print("\n# VLM judge for every RQ1 run (judge.jsonl):")
    print("python -m webmix.judge_runs --runs " + " ".join(m["run"] for g in ("browser_use", "own_loop")
                                                         for m in reg["rq1"][g]) + " --parallel 4")


def run(args):
    reg, named, benches = load()
    runs = arm_runs(reg, named, args.arm).get(args.bench)
    if not runs:
        sys.exit(f"the paper reads no {args.bench} runs of {args.arm}")
    if not 1 <= args.seed <= len(runs):
        sys.exit(f"{args.arm} on {args.bench} has {len(runs)} run(s)")
    out = raw_dir(args.bench, runs[args.seed - 1])
    if args.out:
        out = args.out
    cmds = run_cmds(reg, benches, args.arm, args.bench, out, os.path.basename(out))
    for c in cmds:
        print(c)
        if args.execute and not c.lstrip().startswith("#"):
            subprocess.run(c.replace("python ", f"{shlex.quote(PY)} ", 1).split("#")[0], shell=True, cwd=ROOT, check=True)


def train(args):
    reg = yaml.safe_load(open(REG))
    a = reg["adapters"].get(args.adapter)
    if a is None:
        sys.exit(f"unknown adapter; adapters: {', '.join(reg['adapters'])}")
    if a.get("pool"):
        rows = os.path.join("data", "webmix", "rows", f"{args.adapter}_view")
        build = (f"mkdir -p {rows} && while read d; do ln -sfn \"$PWD/data/webmix/replay_v4/$d\" {rows}/$d; "
                 f"done < {a['pool']}")
    else:
        rows, build = a["rows_dir"], a.get("build", "")
    gpus = args.gpus or ",".join(str(i) for i in range(a["gpus"]))
    n = len(gpus.split(","))
    cmd = (f"CUDA_VISIBLE_DEVICES={gpus} WEBMIX_REPLAY_DIR={rows} torchrun --standalone --nproc_per_node {n} "
           f"-m webmix.train --out data/webmix/adapters/{args.adapter} {reg['recipe']} {a.get('args', '')}").strip()
    if n != a["gpus"]:
        print(f"# note: the paper's {args.adapter} trained on {a['gpus']} GPU(s); --grad-accum is the global batch, so "
              f"{n} GPU(s) keep the recipe (each rank sees a different share of the shuffled rows)")
    for c in [build, cmd]:
        if c:
            print(c)
            if args.execute:
                subprocess.run(c, shell=True, cwd=ROOT, check=True)


# ── figures ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def figures(args):
    reg = yaml.safe_load(open(REG))
    paper = os.path.join(ROOT, args.paper or reg["paper_dir"])
    for f in reg["figures"]:
        cmd = f["cmd"]
        if args.only and args.only not in cmd:
            continue
        print(f"$ python {cmd}", flush=True)
        r = subprocess.run([PY] + shlex.split(cmd), cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            print(r.stdout[-2000:], r.stderr[-2000:])
            sys.exit(f"failed: {cmd}")
        for src, dst in (f.get("copy") or {}).items():
            if args.no_copy or not os.path.isdir(paper):
                continue
            s, d = os.path.join(ROOT, src), os.path.join(paper, dst)
            if os.path.isdir(s):
                shutil.copytree(s, d, dirs_exist_ok=True)
            else:
                os.makedirs(os.path.dirname(d), exist_ok=True)
                shutil.copy(s, d)
            print(f"  -> {os.path.relpath(d, ROOT)}")
    if not os.path.isdir(paper) and not args.no_copy:
        print(f"(no paper source at {os.path.relpath(paper, ROOT)}: outputs left in docs/figures/)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="every run and adapter the paper reads: present and complete?")
    p = sub.add_parser("show", help="the commands behind an arm (or 'rq1')")
    p.add_argument("arm")
    p.add_argument("--bench")
    p = sub.add_parser("run", help="one run of an arm on a benchmark")
    p.add_argument("arm")
    p.add_argument("--bench", required=True)
    p.add_argument("--seed", type=int, default=1, help="which of the paper's runs (1-based)")
    p.add_argument("--out", help="write here instead of the paper's run folder")
    p.add_argument("--execute", action="store_true")
    p = sub.add_parser("train", help="train an adapter")
    p.add_argument("adapter")
    p.add_argument("--gpus")
    p.add_argument("--execute", action="store_true")
    p = sub.add_parser("figures", help="regenerate every figure and table, copy them into the paper source")
    p.add_argument("--only", help="only generators whose command contains this")
    p.add_argument("--paper", help="paper source folder (default: paper_dir of experiments/paper.yaml)")
    p.add_argument("--no-copy", action="store_true")
    args = ap.parse_args()
    return {"status": status, "show": show, "run": run, "train": train, "figures": figures}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main() or 0)
