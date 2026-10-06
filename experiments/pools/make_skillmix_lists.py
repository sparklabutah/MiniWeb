"""Skill-mix ablation lists (EXPERIMENT_PLAN 2.2, 2026-10-02). From the training pool (replay_v4 trajectories with their
datagen macro), draw two same-size subsets of 1,200 trajectories: balanced = 200 per action family, spread evenly over
each family's macros; skewed = 70/30, two families (one seeded random draw, user: "just select random") get 420 each,
the other four 90 each. The heavy pair is drawn among families with at least 420 trajectories (a
smaller family cannot supply 420; 2026-10-02: Drag & gesture has 309, Navigation 262). Writes balanced.txt, skewed.txt (task ids) and lists.json (composition)."""
import collections, glob, json, os, random, sys
sys.path.insert(0, ".")
from datagen.viewer import FAMILIES
SEED, N, OUT = 20261002, 1200, "data/webmix/skillmix"
fam_of = {m: f for f, ms in FAMILIES.items() for m in ms}
pool = {d for d in os.listdir("data/webmix/replay_v4") if "~" not in d and glob.glob(f"data/webmix/replay_v4/{d}/*")}
by = collections.defaultdict(lambda: collections.defaultdict(list))        # family -> macro -> [task ids]
for p in sorted(glob.glob("data/datagen/runs/*/kept.jsonl")):
    for l in open(p):
        x = json.loads(l)
        if x["task_id"] in pool and fam_of.get(x["macro"]):
            by[fam_of[x["macro"]]][x["macro"]].append(x["task_id"])
fams = sorted(by)                                                          # the 6 action families in the pool
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
eligible = [f for f in fams if sum(len(set(v)) for v in by[f].values()) >= 420]
heavy = sorted(rng.sample(eligible, 2))
balanced = [t for f in fams for t in draw(f, N // len(fams))]
skewed = [t for f in fams for t in draw(f, 420 if f in heavy else 90)]
assert len(balanced) == len(skewed) == N
open(f"{OUT}/balanced.txt", "w").write("\n".join(balanced) + "\n")
open(f"{OUT}/skewed.txt", "w").write("\n".join(skewed) + "\n")
comp = lambda ids: dict(collections.Counter(fam_of[m] for f in by for m, v in by[f].items() for t in v if t in set(ids)))
json.dump({"seed": SEED, "n": N, "families": fams, "over_weighted": heavy, "balanced": comp(balanced), "skewed": comp(skewed)},
          open(f"{OUT}/lists.json", "w"), indent=1)
print("over-weighted:", heavy); print("balanced:", comp(balanced)); print("skewed:", comp(skewed))
