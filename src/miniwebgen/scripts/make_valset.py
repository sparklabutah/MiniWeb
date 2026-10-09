"""The generated single-primitive test tasks of the held-out sites (paper: "103 generated single-primitive tasks from 13
held-out sites"; 115 tasks, 103 of well-covered primitives). MiniWebGen's sampling and phrasing on the held-out sites,
stopped before execution: never executed, never trained on.

    python src/miniwebgen/scripts/make_valset.py [--print]

Runs in its own datagen tree (MINIWEB_DATAGEN_DIR=data/webmix/valgen, whose split lists the 13 held-out sites as the sites
to generate on): v2_slider (filter_by_slider, up to 8 tasks) and v2_rest (every other supported macro, up to 6 each),
merged into data/webmix/valgen/val_v2.jsonl. The arguments are those the paper's runs recorded in
data/webmix/valgen/runs/<run>/run.json when present.
"""
import ast
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
VALGEN = ROOT / "data" / "webmix" / "valgen"
COMMON = {"stop_after": "suggest", "mid_chain_share": 0.0, "preset_share": 0.0, "workers": 4, "servers": 2, "ports": [8316, 8317]}
RUNS = {"v2_slider": {"macros": ["filter_by_slider"], "n": 8, "propose_site_cap": 4},
        "v2_rest": {"macros": None, "n": 6, "propose_site_cap": 3}}      # None: every supported macro but the slider


def run_args(run_id):
    saved = VALGEN / "runs" / run_id / "run.json"
    if saved.exists():
        a = json.loads(saved.read_text())
    else:
        sys.path.insert(0, str(ROOT / "src"))
        from miniwebgen import kinds
        a = {**COMMON, **RUNS[run_id], "run_id": run_id}
        if a["macros"] is None:
            a["macros"] = sorted(set(kinds.supported_macros()) - {"filter_by_slider"})
    m = a["macros"]
    m = ast.literal_eval(m) if isinstance(m, str) else m
    argv = ["-m", "miniwebgen", "run", "--run-id", run_id, "--macros", *m, "--n", str(a["n"]),
            "--propose-site-cap", str(a["propose_site_cap"]), "--per-site-cap", str(a.get("per_site_cap", 2)),
            "--mid-chain-share", str(a.get("mid_chain_share", 0.0)), "--preset-share", str(a.get("preset_share", 0.0)),
            "--stop-after", a.get("stop_after") or "suggest", "--workers", str(a.get("workers", 4)),
            "--servers", str(a.get("servers", 2)), "--ports", *[str(p) for p in a.get("ports") or COMMON["ports"]],
            "--seed", str(a.get("seed", 0))]
    return argv


def main():
    env = {**os.environ, "MINIWEB_DATAGEN_DIR": str(VALGEN),
           "PYTHONPATH": os.pathsep.join(filter(None, [str(ROOT / "src"), os.environ.get("PYTHONPATH")]))}
    for run_id in RUNS:
        cmd = [sys.executable, *run_args(run_id)]
        print("MINIWEB_DATAGEN_DIR=data/webmix/valgen python", " ".join(cmd[1:]), flush=True)
        if "--print" not in sys.argv:
            subprocess.run(cmd, cwd=ROOT, env=env, check=True)
    if "--print" in sys.argv:
        return
    rows = [json.loads(line) for run in RUNS for line in (VALGEN / "runs" / run / "tasks.jsonl").read_text().split("\n")
            if line.strip()]
    (VALGEN / "val_v2.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    print(len(rows), "test tasks -> data/webmix/valgen/val_v2.jsonl")


if __name__ == "__main__":
    main()
