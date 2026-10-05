"""Significance tests behind the paper's comparisons, from the same run lists as the tables (tables_config.yaml).

Benchmarks with seeds (MiniWeb, WebArena-Lite): each task's success is averaged over the seeds of an arm, then a paired
permutation test over tasks (random sign flips of the per-task differences, two-sided). Live-web sets (one run per
arm): exact McNemar test on the discordant tasks.

    python docs/figures/tables/paper_stats.py [--config docs/figures/tables/tables_config.yaml]
"""
import argparse, math, os, random, statistics as st, sys
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))
from results import task_outcomes, primitive_filter, _records  # noqa: E402

# (benchmark, arm A, arm B, optional task filter on ids) -- B is compared against A
COMPARISONS = [
    ("single", "base", "pooled"), ("single", "planner", "agent"), ("single", "base", "agent"),
    ("heldout", "base", "pooled"), ("heldout", "base", "planner"), ("heldout", "base", "agent"),
    ("heldout", "planner", "agent"), ("heldout", "pooled", "agent"),
    ("heldout", "planner", "planner_pooled"), ("heldout", "planner_pooled", "agent"), ("heldout", "pooled", "planner_pooled"),
    ("wa", "base", "planner"), ("wa", "base", "agent"), ("wa", "planner", "agent"), ("wa", "base", "pooled"),
    ("wa", "base", "agent", "no_reddit_gitlab"),
    ("wv", "base", "planner"), ("wv", "base", "agent"), ("wv", "planner", "agent"), ("wv", "planner_pooled", "agent"), ("wv", "planner", "planner_pooled"), ("wv", "base", "pooled"),
    ("om2w", "base", "planner"), ("om2w", "base", "agent"), ("om2w", "planner", "agent"), ("om2w", "base", "pooled"), ("om2w", "planner", "planner_pooled"), ("om2w", "planner_pooled", "agent"), ("om2w", "base", "planner_pooled"),
    # 2026-10-04: MiniWebAgent defaults to the planner + one pooled adapter (planner_pooled)
    ("single", "base", "planner_pooled"), ("single", "planner", "planner_pooled"), ("single", "planner_pooled", "pooled"),
    ("heldout", "base", "planner_pooled"), ("wa", "base", "planner_pooled"), ("wa", "planner", "planner_pooled"),
    ("wa", "planner_pooled", "agent"), ("wa", "base", "planner_pooled", "no_reddit_gitlab"), ("wv", "base", "planner_pooled"),
]


def per_task(bench, runs, flt=None):
    """{task: mean success over the arm's seeds}, over the tasks every seed has."""
    outs = [task_outcomes(bench["kind"], r, bench.get("tasks"), primitive_filter(bench.get("primitives"))) for r in runs]
    ids = set.intersection(*(set(o) for o in outs))
    if flt:
        ids = {i for i in ids if flt(i)}
    return {i: st.mean(o[i] for o in outs) for i in ids}


def permutation(a, b, n=100000, seed=0):
    ids = sorted(set(a) & set(b))
    d = [b[i] - a[i] for i in ids]
    obs = abs(sum(d))
    rng = random.Random(seed)
    hits = sum(abs(sum(x if rng.random() < 0.5 else -x for x in d)) >= obs - 1e-12 for _ in range(n))
    return len(ids), 100 * st.mean(a[i] for i in ids), 100 * st.mean(b[i] for i in ids), (hits + 1) / (n + 1)


def mcnemar(a, b):
    ids = sorted(set(a) & set(b))
    up = sum(1 for i in ids if b[i] > a[i]); down = sum(1 for i in ids if b[i] < a[i])
    k, m = min(up, down), up + down
    p = min(1.0, 2 * sum(math.comb(m, j) for j in range(k + 1)) / 2 ** m) if m else 1.0
    return len(ids), 100 * st.mean(a[i] for i in ids), 100 * st.mean(b[i] for i in ids), p, up, down


def no_reddit_gitlab(run):
    """WebArena-Lite tasks outside the two sites whose data two MiniWeb training sites reuse (Reddit, GitLab)."""
    sites = {k: set(r.get("sites") or []) for k, r in _records(run).items()}
    return lambda i: not ({"reddit", "gitlab"} & sites.get(i, set()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(HERE, "tables_config.yaml"))
    cfg = yaml.safe_load(open(ap.parse_args().config))
    benches, runs = cfg["benchmarks"], cfg["runs"]
    for c in COMPARISONS:
        bk, a, b = c[:3]
        ra, rb = (runs.get(a) or {}).get(bk), (runs.get(b) or {}).get(bk)
        if not ra or not rb:
            print(f"{bk:8s} {a:>14s} vs {b:<14s}  (missing runs)")
            continue
        flt = no_reddit_gitlab(ra[0]) if len(c) > 3 else None
        pa, pb = per_task(benches[bk], ra, flt), per_task(benches[bk], rb, flt)
        tag = f"{bk}{'*' if flt else ''}"
        if len(ra) == 1 and len(rb) == 1 and benches[bk]["kind"] in ("webvoyager", "om2w"):
            n, ma, mb, p, up, down = mcnemar(pa, pb)
            print(f"{tag:8s} {a:>14s} vs {b:<14s} n={n:4d}  {ma:5.1f} -> {mb:5.1f} ({mb - ma:+5.1f})  McNemar p={p:.2g} (+{up}/-{down})")
        else:
            n, ma, mb, p = permutation(pa, pb)
            print(f"{tag:8s} {a:>14s} vs {b:<14s} n={n:4d}  {ma:5.1f} -> {mb:5.1f} ({mb - ma:+5.1f})  permutation p={p:.2g}")


if __name__ == "__main__":
    main()
