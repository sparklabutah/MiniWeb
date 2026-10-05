"""python -m webmix replay [--limit N] [--macros m1,m2] [--tasks id1,id2] [--workers 6] [--ports 8310,8311] [--shard k/n]
                         [--augment recovery|chain]

Replays kept datagen trajectories through the browser-use harness; passing episodes write
<REPLAY_DIR>/<task_id>/{rows.jsonl, episode.json, step_*.png} (webmix.REPLAY_DIR, data/webmix/replay_v4);
every result is appended to <REPLAY_DIR>/results.jsonl (already-passed episodes are skipped unless --redo).
--augment replays variants of the trajectories whose plain replay passed (webmix.augment): recovery (one
injected, corrected mistake; --share of them) or chain (two same-page trajectories as one episode).
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import random
from pathlib import Path
import sys
import time
from collections import Counter

from datagen import browser as B
from datagen import config
from datagen.viewer import _kept_rows
from webmix import replay as R


# question answering is trained on human trajectories only (user, 2026-09-29): the synthetic answers came
# from a script that already knew them
NOT_REPLAYED = {"report_information", "count_entries"}


def _passed(out_dir=None):
    res_path = Path(out_dir or R.OUT_DIR) / "results.jsonl"
    done = set()
    if res_path.exists():
        for line in res_path.read_text().split("\n"):
            if line.strip():
                x = json.loads(line)
                if x.get("ok"):
                    done.add(x["task_id"])
    return done


def _selected(args):
    kept = _kept_rows()
    items = []
    for tid, r in kept.items():
        d = config.RUNS_DIR / r["run"] / "accepted" / tid
        if not (d / "trajectory.json").exists() or not (d / "elements.json").exists():
            continue
        if args.macros and r["macro"] not in args.macros:
            continue
        if not args.macros and r["macro"] in NOT_REPLAYED:
            continue
        if args.tasks and tid not in args.tasks:
            continue
        items.append((tid, d))
    items.sort()
    random.Random(0).shuffle(items)
    done = set() if args.redo else _passed()
    if args.augment:
        from webmix import augment as A
        plain = _passed(args.plain_from)
        items = [x for x in items if x[0] in plain]          # variants of trajectories that replay cleanly
        if args.ids_file:                                    # e.g. the 3.1K set that trained MiniWebAgent's executor
            keep = set(Path(args.ids_file).read_text().split())
            items = [x for x in items if x[0] in keep]
        if args.augment == "taskchain":                      # review round 1, A2: task-centric episodes
            chains = A.task_chain_candidates(items, lengths=tuple(int(v) for v in args.chain_lengths.split(",")),
                                             n_chains=args.n_chains, max_uses=args.max_uses)
            items = [(A.chain_id(c, "tchain"),
                      (lambda c: lambda base, hl: A.replay_chain(c, base, headless=hl, always_home=True,
                                                                 variant="taskchain"))(c)) for c in chains]
        elif args.augment == "recovery":
            pick = lambda tid: int(hashlib.sha1(f"rec:{tid}".encode()).hexdigest(), 16) % 1000 < args.share * 1000  # noqa: E731
            items = [(tid + "~rec", (lambda d: lambda base, hl: R.replay_one(d, base, headless=hl, variant="recovery"))(d))
                     for tid, d in items if pick(tid)]
        else:
            pairs = A.chain_candidates(items, per_page=args.per_page) + A.home_chain_candidates(items, per_second=args.per_page)
            items = list({A.chain_id(p): (A.chain_id(p), (lambda p: lambda base, hl: A.replay_chain(p, base, headless=hl))(p))
                          for p in pairs}.values())
    else:
        items = [(tid, (lambda d: lambda base, hl: R.replay_one(d, base, headless=hl))(d)) for tid, d in items]
    items = [x for x in items if x[0] not in done]
    if args.shard:                              # k/n: this process takes every n-th trajectory from k
        k, n = (int(v) for v in args.shard.split("/"))
        items = items[k::n]
    return items[:args.limit] if args.limit else items


async def _run(items, bases, workers, headless):
    q = asyncio.Queue()
    for i, it in enumerate(items):
        q.put_nowait((i, it))
    R.OUT_DIR.mkdir(parents=True, exist_ok=True)
    res_path = R.OUT_DIR / "results.jsonl"
    tally, t0 = Counter(), time.time()

    async def worker(w):
        base = bases[w % len(bases)]
        while not q.empty():
            i, (tid, job) = q.get_nowait()
            res = await job(base, headless)
            tally["ok" if res["ok"] else "fail"] += 1
            with open(res_path, "a") as f:
                f.write(json.dumps(res) + "\n")
            print(f"[{sum(tally.values())}/{len(items)}] {'OK  ' if res['ok'] else 'FAIL'} {tid} "
                  f"{res.get('steps')} steps {res.get('duration_s')}s {res.get('error') or ''}"[:260], flush=True)

    await asyncio.gather(*(worker(w) for w in range(workers)))
    print(f"done: {dict(tally)} in {round(time.time() - t0)}s", flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m webmix")
    sub = ap.add_subparsers(dest="cmd", required=True)
    rp = sub.add_parser("replay")
    rp.add_argument("--limit", type=int, default=0)
    rp.add_argument("--macros", type=lambda s: set(s.split(",")), default=None)
    rp.add_argument("--tasks", type=lambda s: set((open(s[1:]).read() if s.startswith("@") else s).strip().split(",")),
                    default=None, help="comma-separated ids, or @file holding them (one argument tops out at 128 KB)")
    rp.add_argument("--workers", type=int, default=4)
    rp.add_argument("--ports", type=lambda s: [int(p) for p in s.split(",")], default=[8310, 8311])
    rp.add_argument("--headful", action="store_true")
    rp.add_argument("--redo", action="store_true")
    rp.add_argument("--shard", default=None, help="k/n: one of n processes (each with its own --ports)")
    rp.add_argument("--memory-model", default=None, help="served model that writes each step's memory (e.g. qwen35-4b)")
    rp.add_argument("--memory-url", default="http://127.0.0.1:8400/v1")
    rp.add_argument("--augment", choices=["recovery", "chain", "taskchain"], default=None)
    rp.add_argument("--plain-from", default=None, help="--augment: the replay dir whose results.jsonl lists the plain "
                    "replays that passed (default: this replay dir)")
    rp.add_argument("--ids-file", default=None, help="--augment: only trajectories listed here (one task id per line)")
    rp.add_argument("--chain-lengths", default="2,3,4", help="--augment taskchain: parts per episode")
    rp.add_argument("--n-chains", type=int, default=2400, help="--augment taskchain: episodes to build")
    rp.add_argument("--max-uses", type=int, default=2, help="--augment taskchain: episodes a trajectory may join")
    rp.add_argument("--share", type=float, default=0.35, help="--augment recovery: share of trajectories to vary")
    rp.add_argument("--per-page", type=int, default=3,
                    help="--augment chain: pairs per start page, and first parts per home-page second part")
    args = ap.parse_args(argv)
    if args.cmd == "replay":
        if args.memory_model:
            R.configure_memory(args.memory_url, args.memory_model)
        items = _selected(args)
        print(f"{len(items)} trajectories to replay", flush=True)
        with B.Servers(ports=args.ports) as srv:
            asyncio.run(_run(items, srv.bases, args.workers, not args.headful))


if __name__ == "__main__":
    sys.exit(main())
