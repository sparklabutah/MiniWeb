"""Drag-skewed mix (user 2026-10-03, queued 2026-10-07: "a training exp ... to bias the agent toward learning the drag
better"), the third same-size mix next to balanced.txt and skewed.txt (make_skillmix_lists.py): 1,200 trajectories with
every Drag & gesture trajectory of the pool (393 in the ~7K pool, 33%) and the rest spread evenly over the other five
action families and, within each, over its macros. Drawn from the ~7K pool (replay_v4 now; the 3.1K pool has only 309
drag trajectories), so the adapter trains on granite's rows/replay_v4 with --episode-ids drag_skewed.txt.

    python experiments/pools/make_drag_skewed.py      # -> experiments/pools/drag_skewed.txt, drag_skewed.json
"""
import collections, glob, json, os, random, sys
sys.path.insert(0, ".")
from datagen.viewer import FAMILIES
SEED, N, DRAG = 20261007, 1200, "Drag & gesture"
fam_of = {m: f for f, ms in FAMILIES.items() for m in ms}
pool = {d for d in os.listdir("data/webmix/replay_v4") if "~" not in d and not d.startswith(("chain-", "_"))
        and os.path.exists(f"data/webmix/replay_v4/{d}/rows.jsonl")}
by = collections.defaultdict(lambda: collections.defaultdict(list))        # family -> macro -> [task ids]
for p in sorted(glob.glob("data/datagen/runs/*/kept.jsonl")):
    for l in open(p):
        x = json.loads(l)
        if x["task_id"] in pool and fam_of.get(x["macro"]):
            by[fam_of[x["macro"]]][x["macro"]].append(x["task_id"])
rng = random.Random(SEED)


def draw(fam, k):
    """k trajectories of one family, spread evenly over its macros (round-robin over shuffled per-macro lists)."""
    lists = {m: rng.sample(sorted(set(v)), len(set(v))) for m, v in sorted(by[fam].items())}
    out = []
    while len(out) < k and any(lists.values()):
        for m in sorted(lists):
            if lists[m] and len(out) < k:
                out.append(lists[m].pop())
    assert len(out) == k, (fam, k, len(out))
    return out


drag = draw(DRAG, len({t for v in by[DRAG].values() for t in v}))
others = sorted(f for f in by if f != DRAG)
share = [(N - len(drag)) // len(others) + (i < (N - len(drag)) % len(others)) for i in range(len(others))]
ids = drag + [t for f, k in zip(others, share) for t in draw(f, k)]
assert len(ids) == N and len(set(ids)) == N
open("experiments/pools/drag_skewed.txt", "w").write("\n".join(ids) + "\n")
comp = collections.Counter(fam_of[m] for f in by for m, v in by[f].items() for t in set(v) if t in set(ids))
macros = collections.Counter(m for m, v in by[DRAG].items() for t in set(v) if t in set(ids))
json.dump({"seed": SEED, "n": N, "families": dict(comp), "drag_macros": dict(macros)},
          open("experiments/pools/drag_skewed.json", "w"), indent=1)
print("families:", dict(comp.most_common())); print("drag macros:", dict(macros.most_common()))
