"""Generate the paper's data, step by step: MiniWebGen's trajectories, the training episodes and pool, the generated test
tasks of the held-out sites, the task-centric comparison data, and the release.

    python scripts/generate_data.py                       # list the steps and print every command (nothing runs)
    python scripts/generate_data.py --run --steps generate,replay,augment
    python scripts/generate_data.py --run                 # everything, in order

Steps (each is resumable: the underlying commands skip what already exists):

  split      the train/test site split, fixed before anything is generated (data/datagen/site_split.json, tracked)
  sitemap    MiniWebGen's privileged site maps: crawl the training sites, find each primitive's controls, probe the request
             each control sends (data/datagen/sitemap/)
  guides     one guide per primitive, distilled from the human demonstration spans on training sites
             (data/datagen/guides/, tracked)
  generate   the paper's generation runs (scripts/paper.yaml, data.runs), each with the arguments it recorded in
             data/datagen/runs/<run>/run.json: sample -> suggest -> execute -> backend gate -> kept trajectories
  replay     every kept trajectory replayed through the agent harness into training rows (data/webmix/replay_v4/), the
             base model writing each step's memory: 4 shards, then one pass that retries failures
  augment    the variants: recovery (an injected, corrected mistake; 35% of trajectories) and chain (two trajectories
             of one site as one episode)
  pool       the paper's training pool: the frozen id lists scripts/pools/pool3k_plain_ids.txt (3,128 trajectories) and
             pool3k_dirs.txt (4,614 episodes); `python scripts/reproduce.py train pooled_v4` builds its folder
  valset     the 115 generated single-primitive test tasks of the held-out sites (src/miniwebgen/scripts/make_valset.py)
  taskgen    the task-centric comparison data: proposed goal-level tasks on the training sites, attempted by the base
             model, judged, and selected to the same step budget (src/miniwebgen/taskgen.py)
  release    the consolidated, split-labelled, anonymized data folder (scripts/build_release.py)

The LLM stages need Gemini credentials in .env; replay, taskgen's attempts and the release's grading need a served base
model (src/miniwebagent/scripts/serve.sh, port 8400). MiniWebGen's servers use ports 8300-8320 only.
"""
import argparse
import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "data" / "datagen" / "runs"
PY = "python"
RUN_FLAGS = {"n": "--n", "workers": "--workers", "servers": "--servers", "attempts": "--attempts", "seed": "--seed",
             "propose_site_cap": "--propose-site-cap", "per_site_cap": "--per-site-cap", "target": "--target",
             "overshoot": "--overshoot", "mid_chain_share": "--mid-chain-share", "preset_share": "--preset-share",
             "thoughts": "--thoughts", "stop_after": "--stop-after"}


def generation_run(run_id, template):
    """The command a generation run recorded (run.json), or the registry's template for a run not on this machine."""
    f = RUNS / run_id / "run.json"
    if not f.exists():
        return template.replace("<id>", run_id)
    a = json.loads(f.read_text())
    macros = a.get("macros")
    macros = ast.literal_eval(macros) if isinstance(macros, str) else macros
    argv = [PY, "-m", "miniwebgen", "run", "--run-id", run_id]
    if macros:
        argv += ["--macros", *macros]
    for k, flag in RUN_FLAGS.items():
        if a.get(k) is not None and not (k == "thoughts" and a[k] == "none"):
            argv += [flag, str(a[k])]
    if a.get("ports"):
        argv += ["--ports", *[str(p) for p in a["ports"]]]
    if a.get("no_judge"):
        argv.append("--no-judge")
    return " ".join(argv)


def steps():
    reg = yaml.safe_load((ROOT / "scripts" / "paper.yaml").read_text())["data"]
    replay = reg["replay"].split("#")[0].strip()
    return [
        ("split", [f"{PY} -m miniwebgen split"]),
        ("sitemap", [f"{PY} -m miniwebgen sitemap --workers 4"]),
        ("guides", [f"{PY} -m miniwebgen guide"]),
        ("generate", [generation_run(r, reg["generate"]) for r in reg["runs"]]),
        ("replay", [" & ".join(replay.replace("k/4", f"{k}/4") + f" --ports {8310 + 2 * k},{8311 + 2 * k}" for k in range(4))
                    + " & wait",                                       # 4 shards side by side, each with its own servers
                    replay.replace(" --shard k/4", "")]),               # then once more: retries the failures
        ("augment", [c.split("#")[0].strip() + " --memory-model qwen35-4b" for c in reg["augment"]]),
        ("pool", ["wc -l scripts/pools/pool3k_plain_ids.txt scripts/pools/pool3k_dirs.txt",
                  f"{PY} scripts/reproduce.py train pooled_v4"]),
        ("valset", [f"{PY} src/miniwebgen/scripts/make_valset.py"]),
        ("taskgen", [f"{PY} -m miniwebgen.taskgen propose --out data/webmix/taskgen/tasks.jsonl --per-site 140",
                     f"{PY} -m miniwebagent.evaluate --tasks data/webmix/taskgen/tasks.jsonl --arm base --record-rows "
                     f"--max-steps 30 --timeout 900 --workers 12 --ports 8300,8301 --out data/webmix/taskgen/runs/v1",
                     "cp data/webmix/taskgen/tasks.jsonl data/webmix/taskgen/runs/v1/tasks.jsonl",
                     f"{PY} -m miniwebgen.taskgen judge data/webmix/taskgen/runs/v1 --workers 16",
                     f"{PY} -m miniwebgen.taskgen rows data/webmix/taskgen/runs/v1 --out data/webmix/taskgen/rows_27k"]),
        ("release", [f"{PY} scripts/build_release.py"]),
    ]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--steps", default=None, help="comma-separated steps (default: all, in order)")
    ap.add_argument("--run", action="store_true", help="run the commands (default: print them)")
    a = ap.parse_args()
    all_steps = steps()
    names = [n for n, _ in all_steps]
    want = a.steps.split(",") if a.steps else names
    unknown = set(want) - set(names)
    if unknown:
        sys.exit(f"unknown steps {sorted(unknown)}; steps: {', '.join(names)}")
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, [str(ROOT / "src"), os.environ.get("PYTHONPATH")]))}
    for name, cmds in all_steps:
        if name not in want:
            continue
        print(f"\n## {name}", flush=True)
        for c in cmds:
            print(f"  {c}", flush=True)
            if a.run:
                subprocess.run(c.replace(f"{PY} ", f"{sys.executable} ", -1) if c.startswith(PY) else c,
                               shell=True, cwd=ROOT, env=env, check=True)


if __name__ == "__main__":
    main()
