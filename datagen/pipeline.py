"""CLI + orchestration for the macro data pipeline.

    python -m datagen split [--force]                      # stage 0: persist the train/test site split
    python -m datagen sitemap [--sites a b] [--force]      # privileged site maps (train sites only)
    python -m datagen guide --macros filter_by_dropdown    # stage 1 (cached per macro)
    python -m datagen run --run-id slice1 --macros filter_by_dropdown sort_by_form --n 16
                                                           # stages 2-5 + trajectories + exports + yield log
                                                           # (stage 6 thoughts only with --thoughts <style>)
    python -m datagen thoughts --run-id slice1 --style browser_use   # stage 6 later, from saved screenshots
    python -m datagen export --run-id slice1 --thought-style none --coord-mode normalized --coord-scale 1000
    python -m datagen upgrade --run-id slice1              # v1 trajectories -> v2; backfill elements.json (no LLM)
    python -m datagen yield --run-id slice1                # print the yield log
    python -m datagen audit --run-id slice1                # (re)write the judge-audit pages
    python -m datagen judge-controls --run-id slice1       # empty / swapped / wrong-option negatives

Each `run` stage writes its output under data/datagen/runs/<run-id>/ and is skipped when
that output exists (delete the file or pass --redo <stage> to recompute), so a run can be
resumed after an interruption.
"""
from __future__ import annotations

import argparse
import json
import math
import queue
import sys
import threading
import time
from collections import Counter
from pathlib import Path

from datagen import browser as B
from datagen import config

STAGES = ("sample", "suggest", "execute", "filter", "finalize", "thoughts", "export")
THOUGHT_STYLES = ("none", "browser_use", "short")


def _jl_write(path, rows):
    Path(path).write_text("".join(json.dumps(r, ensure_ascii=False, default=str) + "\n" for r in rows))


def _jl_read(path):
    p = Path(path)
    return [json.loads(x) for x in p.read_text().split("\n") if x.strip()] if p.exists() else []


def _log_to(run_dir):
    lock = threading.Lock()
    f = open(Path(run_dir) / "run.log", "a")

    def log(msg):
        line = f"{time.strftime('%H:%M:%S')} {msg}"
        with lock:
            print(line, flush=True)
            f.write(line + "\n")
            f.flush()
    return log


def _sites_for(macros, train):
    """Sites whose site maps a run needs: those listing one of the macros, and every site for a macro no
    site lists (sampler.candidate_sites then takes any site whose map has a control serving it)."""
    from annotation.macro_locations import MACRO_LOCATIONS
    unlisted = {m for m in macros if not any(m in (MACRO_LOCATIONS.get(s) or {}) for s in train)}
    return [s for s in train if unlisted or any(m in (MACRO_LOCATIONS.get(s) or {}) for m in macros)]


# ── stages ────────────────────────────────────────────────────────────────────

def stage_sample(run_dir, macros, n, train, sitemaps, bases, args, log):
    from datagen import sampler
    from datagen.filter import kept_keys
    exclude, prior = kept_keys(exclude_run=run_dir.name)
    feasible, infeasible, spare, dropped_sites, caps = [], [], [], {}, {}
    for m in macros:
        n_m, cap_m = n, args.propose_site_cap
        if getattr(args, "target", None):
            # a per-macro kept target: what earlier runs kept counts toward it, and the per-site cap
            # opens up for macros only a few train sites host (cap = ceil(target / sites))
            sites = len(sampler.candidate_sites(m, train, sitemaps)[0]) or 1
            have = sum(c for (mm, _s), c in prior.items() if mm == m)
            need = max(0, args.target - have)
            cap_m = max(args.per_site_cap, math.ceil(args.target / sites))
            n_m = math.ceil(need * args.overshoot)
            caps[m] = {"target": args.target, "have": have, "need": need, "sites": sites, "site_cap": cap_m, "n": n_m}
            log(f"target {m}: have {have}, need {need}, {sites} sites -> site cap {cap_m}, sampling {n_m}")
            # macros served by few forms/tools: enough value sets per control to reach the target
            vctrls = [c for cs in sampler.candidate_sites(m, train, sitemaps)[0].values() for c in cs
                      if c.get("kind") in ("form", "tool", "imageop")]
            for c in vctrls:
                c["_k"] = min(60, max(12, math.ceil(n_m * 1.5 / len(vctrls))))
            if n_m == 0:
                continue
        f, i, d, sp = sampler.sample(m, n_m, train=train, sitemaps=sitemaps, bases=bases, workers=args.workers,
                                 seed=args.seed, per_site_cap=cap_m,
                                 mid_chain_share=args.mid_chain_share, preset_share=args.preset_share,
                                 exclude_keys=exclude, log=log,
                                 prior_site_counts={s: c for (mm, s), c in prior.items() if mm == m},
                                 fill=bool(getattr(args, "target", None)))
        if m in caps and f:                 # the filter keeps what the sampler chose, fill included
            per = {}
            for t in f:
                per[t["site"]] = per.get(t["site"], 0) + 1
            caps[m]["site_cap"] = max(caps[m]["site_cap"], max(prior.get((m, s), 0) + c for s, c in per.items()))
        feasible += f
        infeasible += i
        spare += sp
        dropped_sites[m] = d
    _jl_write(run_dir / "params.jsonl", feasible)
    _jl_write(run_dir / "infeasible.jsonl", infeasible)
    _jl_write(run_dir / "spare.jsonl", spare)
    (run_dir / "sites_dropped.json").write_text(json.dumps(dropped_sites, indent=1))
    (run_dir / "caps.json").write_text(json.dumps(caps, indent=1))


def stage_suggest(run_dir, args, log):
    from concurrent.futures import ThreadPoolExecutor
    from datagen.suggester import make_task
    params = _jl_read(run_dir / "params.jsonl")
    with ThreadPoolExecutor(args.workers) as pool:
        tasks = list(pool.map(lambda t: make_task(t, run_dir.name), params))
    bad = [p["param_id"] for p, t in zip(params, tasks) if t is None]
    tasks = [t for t in tasks if t]
    _jl_write(run_dir / "tasks.jsonl", tasks)
    (run_dir / "suggest_failed.json").write_text(json.dumps(bad))
    log(f"suggest: {len(tasks)} tasks ({len(bad)} tuples without valid wording)")


def stage_execute(run_dir, bases, args, log):
    from datagen.executor import execute_task
    from datagen.guides import guide_text, load_guide
    tasks = _jl_read(run_dir / "tasks.jsonl")
    macros = {t["macro"] for t in tasks} | {t["start"]["prefix"]["macro"] for t in tasks if t["start"].get("prefix")}
    guides = {m: guide_text(load_guide(m)) for m in macros}
    ep = run_dir / "episodes"
    todo = queue.Queue()
    for i, t in enumerate(tasks):
        if not (ep / t["task_id"] / "summary.json").exists():
            todo.put((i, t))
    log(f"execute: {todo.qsize()} tasks to run ({len(tasks) - todo.qsize()} already done)")

    def worker(w):
        with B.browser() as b:
            while True:
                try:
                    i, t = todo.get_nowait()
                except queue.Empty:
                    return
                try:
                    recs = execute_task(t, bases[w % len(bases)], b, ep, guides, attempts=args.attempts, log=log)
                except Exception as exc:          # harness failure: record, move on
                    log(f"  {t['task_id']}: harness error {type(exc).__name__}: {exc}")
                    continue
                (ep / t["task_id"]).mkdir(parents=True, exist_ok=True)
                (ep / t["task_id"] / "summary.json").write_text(json.dumps(
                    {"task_id": t["task_id"], "attempts": [{k: r.get(k) for k in
                     ("attempt", "ok", "executed", "error", "dir", "duration_s")} for r in recs]}, indent=1))
    threads = [threading.Thread(target=worker, args=(w,), daemon=True) for w in range(args.workers)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()


def _executions(run_dir, tasks):
    out = {}
    for t in tasks:
        d = run_dir / "episodes" / t["task_id"]
        recs = []
        for a in sorted(d.glob("a*/attempt.json"), key=lambda p: int(p.parent.name[1:])):
            r = json.loads(a.read_text())
            r["dir"] = str(a.parent.relative_to(config.ROOT))
            recs.append(r)
        out[t["task_id"]] = recs
    return out


def stage_filter(run_dir, args, log):
    from datagen.filter import run_filter
    tasks = _jl_read(run_dir / "tasks.jsonl")
    caps = json.loads((run_dir / "caps.json").read_text()) if (run_dir / "caps.json").exists() else {}
    kept, surplus, failures, judged = run_filter(tasks, _executions(run_dir, tasks), run_dir.name,
                                                 per_site_cap=args.per_site_cap, workers=args.workers, log=log,
                                                 caps=caps, use_judge=not getattr(args, "no_judge", False))
    _jl_write(run_dir / "judged.jsonl", judged)
    _jl_write(run_dir / "kept.jsonl", kept)
    _jl_write(run_dir / "surplus.jsonl", surplus)
    _jl_write(run_dir / "failure_pool.jsonl", failures)


def stage_finalize(run_dir, args, log):
    """Kept attempts -> student-neutral accepted/<task>/ (trajectory.json, screenshots, elements.json). No LLM."""
    from datagen import trajectory as T
    tasks = {t["task_id"]: t for t in _jl_read(run_dir / "tasks.jsonl")}
    kept = _jl_read(run_dir / "kept.jsonl")
    n = 0
    for row in kept:
        out = run_dir / "accepted" / row["task_id"]
        if (out / "trajectory.json").exists():
            continue
        adir = config.ROOT / row["dir"]
        T.build(tasks[row["task_id"]], json.loads((adir / "attempt.json").read_text()), adir, out)
        n += 1
    log(f"finalize: {n} new trajectories ({len(kept)} kept)")


def stage_thoughts(run_dir, style, workers=4, force=False, log=print):
    """Stage 6 (optional): thoughts/<style>.json for every accepted trajectory lacking it."""
    from concurrent.futures import ThreadPoolExecutor
    from datagen import trajectory as T
    from datagen.reasoning import write_thoughts
    dirs = [p.parent for p in sorted((run_dir / "accepted").glob("*/trajectory.json"))]
    todo = [d for d in dirs if force or not T.thoughts_path(d, style).exists()]

    def one(d):
        try:
            write_thoughts(d, style=style, force=force)
            return d.name, None
        except Exception as exc:
            return d.name, f"{type(exc).__name__}: {exc}"
    with ThreadPoolExecutor(workers) as pool:
        res = list(pool.map(one, todo))
    failed = [{"task_id": tid, "stage": "thoughts", "style": style, "reason": "thoughts_fail", "detail": err}
              for tid, err in res if err]
    if failed:
        pool_rows = _jl_read(run_dir / "failure_pool.jsonl")
        known = {(r["task_id"], r.get("stage"), r.get("style")) for r in pool_rows}
        _jl_write(run_dir / "failure_pool.jsonl",
                  pool_rows + [f for f in failed if (f["task_id"], "thoughts", style) not in known])
    log(f"thoughts[{style}]: {len(todo) - len(failed)} written, {len(failed)} failed, "
        f"{len(dirs) - len(todo)} already had them")


def stage_export(run_dir, macros, log, thought_style="none", coord=None):
    from datagen.export import export_audit, export_training
    p, n, skipped = export_training(run_dir, coord=coord, thought_style=thought_style)
    log(f"export: {n} trajectories -> {p.relative_to(config.ROOT)}" + (f" (skipped {skipped})" if skipped else ""))
    for m in macros:
        a, k = export_audit(run_dir, m, thought_style=None if thought_style == "none" else thought_style)
        log(f"audit: {k} {m} trajectories -> {a.relative_to(config.ROOT)}")


# ── yield log ─────────────────────────────────────────────────────────────────

def yield_log(run_dir):
    run_dir = Path(run_dir)
    params, infeas = _jl_read(run_dir / "params.jsonl"), _jl_read(run_dir / "infeasible.jsonl")
    spare = _jl_read(run_dir / "spare.jsonl")
    tasks = _jl_read(run_dir / "tasks.jsonl")
    execs = _executions(run_dir, tasks)
    judged, kept = _jl_read(run_dir / "judged.jsonl"), _jl_read(run_dir / "kept.jsonl")
    surplus, fails = _jl_read(run_dir / "surplus.jsonl"), _jl_read(run_dir / "failure_pool.jsonl")
    accepted = {p.parent.name for p in (run_dir / "accepted").glob("*/trajectory.json")}
    thoughts = Counter(p.stem for p in (run_dir / "accepted").glob("*/thoughts/*.json"))
    macros = sorted({t["macro"] for t in params + infeas})
    out = {}
    for m in macros:
        mt = [t for t in tasks if t["macro"] == m]
        recs = [execs.get(t["task_id"], []) for t in mt]
        out[m] = {
            "proposed": sum(1 for t in params + infeas + spare if t["macro"] == m),
            "feasible (dry run)": sum(1 for t in params + spare if t["macro"] == m),
            "used": sum(1 for t in params if t["macro"] == m),
            "tasks (worded)": len(mt),
            "executed": sum(1 for r in recs if any(a.get("executed") for a in r)),
            "passed backend": sum(1 for r in recs if any(a.get("ok") for a in r)),
            "passed judge": sum(1 for j in judged if j["macro"] == m and j["judge"]["passed"]),
            "kept (dedup + site cap)": sum(1 for k in kept if k["macro"] == m),
            "final (trajectory written)": sum(1 for k in kept if k["macro"] == m and k["task_id"] in accepted),
            "thoughts by style": {st: sum(1 for k in kept if k["macro"] == m and
                                          (run_dir / "accepted" / k["task_id"] / "thoughts" / f"{st}.json").exists())
                                  for st in sorted(thoughts)},
            "attempts": sum(len(r) for r in recs),
            "first-attempt successes": sum(1 for r in recs if r and r[0].get("ok")),
            "start kinds kept": dict(Counter(k["start_kind"] for k in kept if k["macro"] == m)),
            "sites kept": len({k["site"] for k in kept if k["macro"] == m}),
            "surplus": dict(Counter(s["dropped"] for s in surplus if s["macro"] == m)),
            "failure reasons": dict(Counter(f["reason"] for f in fails if _macro_of(f, tasks) == m)),
        }
    (run_dir / "yield.json").write_text(json.dumps(out, indent=1))
    return out


def _macro_of(row, tasks):
    if row.get("macro"):
        return row["macro"]
    return next((t["macro"] for t in tasks if t["task_id"] == row.get("task_id")), None)


def print_yield(y):
    for m, r in y.items():
        chain = " → ".join(f"{k} {r[k]}" for k in ("proposed", "feasible (dry run)", "used", "tasks (worded)", "executed",
                                                    "passed backend", "passed judge", "kept (dedup + site cap)",
                                                    "final (trajectory written)"))
        print(f"{m}: {chain}")
        print(f"    attempts {r['attempts']}, first-attempt successes {r['first-attempt successes']}, "
              f"sites kept {r['sites kept']}, start kinds {r['start kinds kept']}, surplus {r['surplus']}")
        print(f"    failure reasons {r['failure reasons']}; thoughts by style {r.get('thoughts by style', {})}")


# ── commands ──────────────────────────────────────────────────────────────────

def cmd_run(args):
    from datagen import guides, sitemap, split
    sp = split.ensure_split()
    train = sp["train"]
    run_dir = config.RUNS_DIR / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    log = _log_to(run_dir)
    (run_dir / "run.json").write_text(json.dumps({**vars(args), "split_created": sp["created"],
                                                  "coord": config.COORD, "viewport": config.VIEWPORT}, indent=1,
                                                 default=str))
    from datagen import kinds
    unsupported = [m for m in args.macros if not kinds.serving(m)]
    if unsupported:
        raise SystemExit(f"no control kind serves {unsupported} yet (datagen/kinds/)")
    # guides for the run's macros and for every macro a mid-chain prefix step may demonstrate
    for m in sorted(set(args.macros) | {kinds.macro_of({"kind": k.name, "role": r})
                                        for k in kinds.all_kinds() if k.chainable for r in set(k.macros.values())}):
        guides.write_guide(m, train)
    redo = set(args.redo or [])
    with B.Servers(n=args.servers, ports=args.ports) as srv:
        bases = srv.bases
        sites = _sites_for(args.macros, train)
        missing = [s for s in sites if not sitemap.path_for(s).exists()]
        if missing:
            sitemap.build_many(missing, bases, workers=args.workers, log=log)
        sitemaps = {s: sitemap.load(s) for s in sites}
        if "sample" in redo or not (run_dir / "params.jsonl").exists():
            stage_sample(run_dir, args.macros, args.n, train, sitemaps, bases, args, log)
        if "suggest" in redo or not (run_dir / "tasks.jsonl").exists():
            stage_suggest(run_dir, args, log)
        if args.stop_after == "suggest":
            return
        stage_execute(run_dir, bases, args, log)
    if "filter" in redo or not (run_dir / "kept.jsonl").exists():
        stage_filter(run_dir, args, log)
    stage_finalize(run_dir, args, log)
    if args.thoughts != "none":
        stage_thoughts(run_dir, args.thoughts, workers=args.workers, log=log)
    stage_export(run_dir, args.macros, log, thought_style=args.thoughts)
    y = yield_log(run_dir)
    print_yield(y)


def cmd_upgrade(run_dir, rebackfill=False):
    """Bring an older run to the current layout without re-running anything:
    accepted v1 trajectories -> v2 (embedded thoughts move verbatim to thoughts/<style>.json),
    and elements.json backfilled from the logged targets for every attempt and kept trajectory."""
    from datagen import elements
    from datagen import trajectory as T
    run_dir = Path(run_dir)
    tasks = {t["task_id"]: t for t in _jl_read(run_dir / "tasks.jsonl")}
    kept = {k["task_id"]: k for k in _jl_read(run_dir / "kept.jsonl")}
    migrated = backfilled = 0
    for a in sorted((run_dir / "episodes").glob("*/a*/attempt.json")):
        if a.parent.parent.name not in tasks:
            continue
        cur = elements.load_attempt(a.parent)
        if cur is None or (rebackfill and cur.get("source") == "backfill"):   # never overwrite recorded ones
            elements.backfill_attempt(a.parent, tasks[a.parent.parent.name])
            backfilled += 1
    states = Counter()
    for p in sorted((run_dir / "accepted").glob("*/trajectory.json")):
        d = p.parent
        migrated += T.migrate_v1(d)
        row = kept.get(d.name)
        stale = (d / "elements.json").exists() and rebackfill and \
            json.loads((d / "elements.json").read_text()).get("source") == "backfill"
        if row and (stale or not (d / "elements.json").exists()):
            doc = elements.load_attempt(config.ROOT / row["dir"])
            if doc:
                (d / "elements.json").write_text(json.dumps(elements.for_trajectory(doc, T.load(d)), indent=1,
                                                            ensure_ascii=False, default=str))
        if (d / "elements.json").exists():
            e = json.loads((d / "elements.json").read_text())
            states["complete" if e.get("complete") else "partial"] += 1
        else:
            states["none"] += 1
    print(f"{run_dir.name}: migrated {migrated} trajectories to v2, backfilled elements for {backfilled} attempts; "
          f"accepted elements.json: {dict(states)}")
    return states


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m datagen", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("split", help="build/persist the train/test site split")
    s.add_argument("--force", action="store_true")
    s = sub.add_parser("sitemap", help="crawl + probe train sites")
    s.add_argument("--sites", nargs="*")
    s.add_argument("--macros", nargs="*", default=None)
    s.add_argument("--force", action="store_true")
    s.add_argument("--kinds", nargs="*", help="only (re)discover + probe these control kinds, merged into the maps")
    s.add_argument("--max-pages", type=int, default=None, help="pages crawled per site (default 30)")
    s.add_argument("--per-pattern", type=int, default=None, help="pages crawled per URL pattern (default 2)")
    s.add_argument("--max-depth", type=int, default=None, help="link depth from the site root (default 2)")
    s.add_argument("--workers", type=int, default=4)
    s.add_argument("--servers", type=int, default=1)
    s.add_argument("--ports", type=int, nargs="*")
    s = sub.add_parser("guide", help="write the guide for macros (stage 1)")
    s.add_argument("--macros", nargs="+", default=None)
    s.add_argument("--force", action="store_true")
    s = sub.add_parser("run", help="stages 2-6 for a batch")
    s.add_argument("--run-id", required=True)
    s.add_argument("--macros", nargs="+", default=None)
    s.add_argument("--n", type=int, default=16, help="feasible tuples per macro")
    s.add_argument("--workers", type=int, default=4)
    s.add_argument("--servers", type=int, default=2)
    s.add_argument("--ports", type=int, nargs="*")
    s.add_argument("--attempts", type=int, default=3)
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--propose-site-cap", type=int, default=2, help="tuples proposed per site per macro")
    s.add_argument("--per-site-cap", type=int, default=2, help="kept trajectories per site per macro")
    s.add_argument("--target", type=int, default=None,
                   help="kept trajectories per macro (counting earlier runs); sets --n and opens the per-site cap "
                        "to ceil(target / candidate sites) per macro")
    s.add_argument("--overshoot", type=float, default=1.25, help="with --target: feasible tuples per missing trajectory")
    s.add_argument("--mid-chain-share", type=float, default=0.3)
    s.add_argument("--preset-share", type=float, default=0.15)
    s.add_argument("--thoughts", default="none", choices=THOUGHT_STYLES,
                   help="stage 6 thought style to generate (default none: add later with `thoughts`)")
    s.add_argument("--redo", nargs="*", choices=STAGES)
    s.add_argument("--stop-after", choices=["suggest"])
    s.add_argument("--no-judge", action="store_true",
                   help="keep trajectories on the deterministic backend gate alone (no flash judge)")
    s = sub.add_parser("thoughts", help="stage 6 later: add thoughts of a style to a run's kept trajectories")
    s.add_argument("--run-id", required=True)
    s.add_argument("--style", required=True, choices=[x for x in THOUGHT_STYLES if x != "none"])
    s.add_argument("--workers", type=int, default=4)
    s.add_argument("--force", action="store_true", help="regenerate even if thoughts/<style>.json exists")
    s = sub.add_parser("export", help="write the training export with student-specific choices")
    s.add_argument("--run-id", required=True)
    s.add_argument("--thought-style", default="none", choices=THOUGHT_STYLES)
    s.add_argument("--coord-mode", default=config.COORD.get("mode", "normalized"), choices=["normalized", "pixel"])
    s.add_argument("--coord-scale", type=int, default=config.COORD.get("scale", 1000))
    s.add_argument("--resolution", type=int, nargs=2, metavar=("W", "H"),
                   help="pixel mode: the screenshot size the student sees (default: recording viewport)")
    s.add_argument("--out", help="output path (default runs/<id>/export/train[.<style>].jsonl)")
    s = sub.add_parser("upgrade", help="migrate v1 trajectories to v2 and backfill elements.json (no LLM, no browser)")
    s.add_argument("--run-id", required=True)
    s.add_argument("--rebackfill", action="store_true", help="regenerate backfilled (never recorded) elements.json")
    s = sub.add_parser("yield", help="print a run's yield log")
    s.add_argument("--run-id", required=True)
    s = sub.add_parser("judge-controls", help="negative controls for the judge on a run's kept tasks")
    s.add_argument("--run-id", required=True)
    s.add_argument("--n", type=int, default=12)
    s = sub.add_parser("audit", help="(re)write a run's audit pages")
    s.add_argument("--run-id", required=True)
    s.add_argument("--n", type=int, default=30)
    sub.add_parser("view", help="one browsable viewer of every kept trajectory across runs (data/datagen/viewer/)")
    args = ap.parse_args(argv)
    if getattr(args, "macros", "unset") is None:       # default: every macro some control kind serves
        from datagen import kinds
        args.macros = kinds.supported_macros()

    if args.cmd == "split":
        from datagen.split import ensure_split
        sp = ensure_split(force=args.force)
        print(f"{config.SPLIT_PATH}: {len(sp['train'])} train / {len(sp['test'])} test")
        for m, d in sp["target_detail"].items():
            print(f"  {m}: {len(d['train_sites'])} train sites, {len(d['test_sites'])} test sites "
                  f"({len(d['test_sites_with_human_tasks'])} with human tasks)")
    elif args.cmd == "sitemap":
        from datagen import sitemap, split
        train = split.ensure_split()["train"]
        sites = args.sites or _sites_for(args.macros, train)
        with B.Servers(n=args.servers, ports=args.ports) as srv:
            depth = {k: v for k, v in (("max_pages", args.max_pages), ("per_pattern", args.per_pattern),
                                        ("max_depth", args.max_depth)) if v}
            sitemap.build_many(sites, srv.bases, workers=args.workers, force=args.force, only=args.kinds, depth=depth)
    elif args.cmd == "guide":
        from datagen import guides, split
        train = split.ensure_split()["train"]
        for m in args.macros:
            guides.write_guide(m, train, force=args.force)
            print(config.GUIDES_DIR / f"{m}.md")
    elif args.cmd == "run":
        cmd_run(args)
    elif args.cmd == "thoughts":
        run_dir = config.RUNS_DIR / args.run_id
        stage_thoughts(run_dir, args.style, workers=args.workers, force=args.force, log=_log_to(run_dir))
    elif args.cmd == "export":
        from datagen.export import export_training
        coord = ({"mode": "normalized", "scale": args.coord_scale} if args.coord_mode == "normalized"
                 else {"mode": "pixel", "resolution": args.resolution})
        p, n, skipped = export_training(config.RUNS_DIR / args.run_id, coord=coord, thought_style=args.thought_style,
                                        out=args.out)
        print(f"{n} trajectories -> {p}" + (f" (skipped {skipped})" if skipped else ""))
    elif args.cmd == "upgrade":
        cmd_upgrade(config.RUNS_DIR / args.run_id, rebackfill=args.rebackfill)
    elif args.cmd == "yield":
        print_yield(yield_log(config.RUNS_DIR / args.run_id))
    elif args.cmd == "judge-controls":
        from datagen.judge import controls
        run_dir = config.RUNS_DIR / args.run_id
        r = controls(run_dir, n=args.n)
        (run_dir / "judge_controls.json").write_text(json.dumps(r, indent=1))
        for k, v in r.items():
            print(f"{k}: judge passed {v['passed']}/{v['n']} (a sound judge passes none)")
    elif args.cmd == "view":
        from datagen.viewer import write_viewer
        path, n = write_viewer()
        print(f"{n} trajectories -> {path}\nserve: cd {config.DATAGEN_DIR} && python3 -m http.server 8765  "
              f"then open http://localhost:8765/viewer/")
    elif args.cmd == "audit":
        from datagen.export import export_audit
        run_dir = config.RUNS_DIR / args.run_id
        for m in sorted({json.loads(x)["macro"] for x in (run_dir / "kept.jsonl").read_text().split("\n") if x}):
            print(export_audit(run_dir, m, n=args.n))


if __name__ == "__main__":
    sys.exit(main())
