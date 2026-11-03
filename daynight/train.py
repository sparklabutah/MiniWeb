"""The night's training trigger: a rows folder for day t, the webmix.train command, and serving the new adapter.

    python -m daynight.train build-rows --config <cfg> --day <t>     # <out>/rows/day_<t>/: links to rows dirs

Day t's rows folder links every episode this experiment has replayed so far (<out>/replay/) plus, against forgetting,
`train.replay_mix` episodes of the paper's pool (`train.replay_pool`, default data/webmix/replay_v4) per new episode,
drawn with a fixed seed. Training is webmix.train unchanged (`train.recipe`, default the *_v5b branch recipe):
`--init-adapter` = day t-1's adapter, so its KL rows anchor to yesterday's executor. The adapter lands in
<out>/adapters/day_<t>/ and is served as `<train.served_prefix><t>`.

The loop never starts or stops a model server: it prints the serve line and waits until the adapter is listed by the
server (`wait_for_adapter`).
"""
from __future__ import annotations

import argparse
import json
import os
import random
import shlex
import time
import urllib.request
from pathlib import Path

from daynight import config as C
from daynight.propose import replay_dir


def rows_dir(cfg, day):
    return C.out_dir(cfg) / "rows" / f"day_{day}"


def adapter_dir(cfg, day):
    return C.out_dir(cfg) / "adapters" / f"day_{day}"


def served_name(cfg, day):
    return f"{cfg['train']['served_prefix']}{day}"


def _episodes(d):
    d = Path(d)
    return sorted(p.parent for p in d.glob("*/rows.jsonl") if not p.parent.name.startswith("_")) if d.exists() else []


def build_rows(cfg, day):
    """-> manifest {"new", "own", "mixed", "dir"}. Idempotent (existing links are kept)."""
    out = rows_dir(cfg, day)
    out.mkdir(parents=True, exist_ok=True)
    prev = rows_dir(cfg, day - 1) / "manifest.json"
    seen = set(json.loads(prev.read_text())["own"]) if prev.exists() else set()
    own = [p for p in _episodes(replay_dir(cfg))]
    pool_dir = Path(cfg["train"]["replay_pool"])
    pool_dir = pool_dir if pool_dir.is_absolute() else C.ROOT / pool_dir
    pool = _episodes(pool_dir)
    k = min(len(pool), round(cfg["train"]["replay_mix"] * len(own)))
    mixed = random.Random(f"{cfg['seed']}:mix:{day}").sample(pool, k) if k else []
    for src in own + mixed:
        dst = out / src.name
        if not dst.exists() and not dst.is_symlink():
            dst.symlink_to(src.resolve())
    man = {"dir": str(out), "own": [p.name for p in own], "new": [p.name for p in own if p.name not in seen],
           "mixed": [p.name for p in mixed], "pool": str(pool_dir), "pool_found": bool(pool)}
    (out / "manifest.json").write_text(json.dumps(man, indent=1))
    return man


def train_command(cfg, day, init_adapter):
    t = cfg["train"]
    env = os.path.expanduser(cfg["envs"]["webmix_env"])
    gpus = str(t["gpus"])
    n = len(gpus.split(","))
    init = f"--init-adapter {shlex.quote(str(init_adapter))} " if init_adapter else ""
    return (f"CUDA_VISIBLE_DEVICES={gpus} LD_LIBRARY_PATH={env}/lib {env}/bin/torchrun --standalone "
            f"--nproc_per_node {n} -m webmix.train {t['recipe']} {init}"
            f"--rows-dir {shlex.quote(str(rows_dir(cfg, day)))} --out {shlex.quote(str(adapter_dir(cfg, day)))} "
            f"--seed {cfg['seed']} --wandb-project ''")


def serve_command(cfg, day):
    return (f"MAX_LORA_RANK=64 MAX_LORAS=4 LORA_MODULES=\"{served_name(cfg, day)}={adapter_dir(cfg, day)}\" "
            f"bash webmix/serve.sh")


def served_models(vllm):
    with urllib.request.urlopen(vllm.rstrip("/") + "/models", timeout=10) as r:
        return {m["id"] for m in json.loads(r.read().decode()).get("data", [])}


def wait_for_adapter(vllm, name, timeout=6 * 3600, every=30):
    """Block until the server lists `name` (the user (re)starts it with serve_command). -> True when served."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if name in served_models(vllm):
                return True
        except OSError:
            pass
        time.sleep(every)
    return False


def adapter_ready(path):
    p = Path(path)
    return (p / "webmix_meta.json").exists() and any(p.glob("adapter_*"))


# ── mock training ──────────────────────────────────────────────────────────────────────────────────────────────────

def mock_train(cfg, day, init_adapter, manifest):
    """A fake adapter: skills.json = yesterday's skills, raised for every macro practiced tonight (more episodes, more
    gain) and slightly lowered for the others (less with a KL anchor, beta > 0)."""
    from daynight.world import MockBackend, load_skills
    macros = MockBackend(cfg).macros
    skills = load_skills(init_adapter, macros, cfg["seed"])
    practiced = {}
    for name in manifest["new"]:
        ep = json.loads((replay_dir(cfg) / name / "episode.json").read_text())
        practiced[ep["macro"]] = practiced.get(ep["macro"], 0) + 1
    anchored = " --beta 0" not in f" {cfg['train']['recipe']}"
    for m in skills:
        if m in practiced:
            skills[m] += (1 - skills[m]) * 0.5 * min(1.0, practiced[m] / 20)
        else:
            skills[m] -= 0.005 if anchored else 0.02
        skills[m] = round(max(0.05, min(0.97, skills[m])), 3)
    out = adapter_dir(cfg, day)
    out.mkdir(parents=True, exist_ok=True)
    (out / "skills.json").write_text(json.dumps(skills, indent=1, sort_keys=True))
    (out / "adapter_mock.txt").write_text("mock adapter: no weights\n")
    (out / "webmix_meta.json").write_text(json.dumps(
        {"mock": True, "day": day, "init_adapter": str(init_adapter) if init_adapter else None,
         "practiced": practiced, "rows_dir": manifest["dir"], "command": train_command(cfg, day, init_adapter)},
        indent=1))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m daynight.train")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build-rows", help="link day t's training rows folder")
    b.add_argument("--config", required=True)
    b.add_argument("--day", type=int, required=True)
    b.add_argument("--model", default=None)
    args = ap.parse_args(argv)
    cfg = C.load(args.config, model=args.model)
    man = build_rows(cfg, args.day)
    print(f"{man['dir']}: {len(man['own'])} episodes of this experiment ({len(man['new'])} new) + "
          f"{len(man['mixed'])} from {man['pool']}" + ("" if man["pool_found"] else " (pool not found)"))


if __name__ == "__main__":
    main()
