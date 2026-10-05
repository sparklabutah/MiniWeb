"""Score the verifier and the VLM judge against the grader-audit labels (scripts/build_grader_audit.py).

A human task label is pass when every primitive is labeled pass, fail when any is labeled fail, unsure otherwise;
unsure labels are left out. Task-level accuracy is estimated for the full population of judged RQ1 episodes by
weighting each stratum (both pass, both fail, judge only, verifier only) by its size there, with a stratified
bootstrap 95% interval. Primitive-level accuracy is reported per family, unweighted. Cases with two labelers give
the inter-labeler agreement and Cohen's kappa.

    python scripts/grader_audit_report.py --url https://miniweb-production.up.railway.app   # token: MINIWEB_RECOVERY_TOKEN
    python scripts/grader_audit_report.py --labels labels.json [--primary Minh]
"""
import argparse, json, os, random, sys, urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from datagen.viewer import FAMILIES  # noqa: E402

OUT = ROOT / "data/grader_audit"
FAM = {m: f for f, ms in FAMILIES.items() for m in ms}


def fetch(url, token):
    req = urllib.request.Request(url.rstrip("/") + "/recovery/grader_audit/labels", headers={"X-Recovery-Token": token})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def task_label(prims):
    vals = set(prims.values())
    return "fail" if "fail" in vals else "pass" if vals == {"pass"} else "unsure"


def kappa(a, b):
    n = len(a)
    if not n:
        return float("nan"), float("nan")
    po = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return po, (po - pe) / (1 - pe) if pe < 1 else float("nan")


def weighted_acc(rows, pop, grader):
    """Population accuracy of a grader: per-stratum accuracy weighted by the stratum's population share."""
    by = defaultdict(list)
    for r in rows:
        by[r["stratum"]].append(r[grader] == r["human"])
    tot = sum(pop[s] for s in by)
    return sum(pop[s] / tot * sum(v) / len(v) for s, v in by.items()), {s: (sum(v), len(v)) for s, v in by.items()}


def bootstrap(rows, pop, grader, reps=2000, seed=0):
    rng, by = random.Random(seed), defaultdict(list)
    for r in rows:
        by[r["stratum"]].append(r)
    accs = []
    for _ in range(reps):
        sample = [x for s in by.values() for x in (rng.choice(s) for _ in s)]
        accs.append(weighted_acc(sample, pop, grader)[0])
    accs.sort()
    return accs[int(0.025 * reps)], accs[int(0.975 * reps) - 1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="deployment to fetch labels from (token in MINIWEB_RECOVERY_TOKEN)")
    ap.add_argument("--labels", help="a labels JSON list instead (as /annotate/api/grader_audit/labels.json gives)")
    ap.add_argument("--primary", help="labeler whose labels are scored (default: the one with most labels)")
    args = ap.parse_args()
    key = json.loads((OUT / "key.json").read_text())
    pop, cases = key["population"], key["cases"]
    labels = fetch(args.url, os.environ.get("MINIWEB_RECOVERY_TOKEN", "")) if args.url else json.load(open(args.labels))
    (OUT / "labels.json").write_text(json.dumps(labels, indent=1, ensure_ascii=False))
    by_labeler = defaultdict(dict)
    for r in labels:
        if r["case_id"] in cases:
            by_labeler[r["labeler"]][r["case_id"]] = r
    if not by_labeler:
        sys.exit("no labels yet")
    primary = args.primary or max(by_labeler, key=lambda k: len(by_labeler[k]))
    lab = by_labeler[primary]
    rep = {"primary": primary, "labelers": {k: len(v) for k, v in by_labeler.items()}, "n_cases": len(cases)}

    tasks, inst = [], []
    for cid, r in lab.items():
        k = cases[cid]
        h = task_label(r["primitives"])
        if h != "unsure":
            tasks.append({"stratum": k["stratum"], "human": h == "pass", "judge": k["judge"], "verifier": k["verifier"]})
        for i, v in r["primitives"].items():
            if v != "unsure":
                inst.append({"family": FAM.get(i.split("#")[0], "?"), "human": v == "pass",
                             "judge": k["judge_instances"].get(i), "verifier": k["verifier_instances"].get(i)})
    rep["tasks_scored"], rep["tasks_unsure"] = len(tasks), len(lab) - len(tasks)
    for g in ("judge", "verifier"):
        acc, per = weighted_acc(tasks, pop, g)
        lo, hi = bootstrap(tasks, pop, g)
        rep[f"{g}_task_accuracy"] = {"population_weighted": acc, "ci95": [lo, hi],
                                     "per_stratum": {s: f"{a}/{n}" for s, (a, n) in per.items()}}
        fam = defaultdict(lambda: [0, 0])
        for x in inst:
            if x[g] is not None:
                fam[x["family"]][0] += x[g] == x["human"]
                fam[x["family"]][1] += 1
        rep[f"{g}_primitive_accuracy"] = {f: f"{a}/{n} ({100 * a / n:.1f}%)" for f, (a, n) in sorted(fam.items())}
    # who is right on the disagreements: the share of each disagreement stratum the human sides with the judge
    for s in ("judge_only", "verifier_only"):
        rows = [t for t in tasks if t["stratum"] == s]
        rep[f"{s}_human_pass"] = f"{sum(t['human'] for t in rows)}/{len(rows)}"

    others = [k for k in by_labeler if k != primary]
    agree = {}
    for o in others:
        a, b = [], []
        for cid in set(lab) & set(by_labeler[o]):
            for i, v in lab[cid]["primitives"].items():
                w = by_labeler[o][cid]["primitives"].get(i)
                if "unsure" not in (v, w) and w is not None:
                    a.append(v == "pass")
                    b.append(w == "pass")
        po, kp = kappa(a, b)
        agree[o] = {"primitives": len(a), "agree": po, "kappa": kp}
    rep["inter_labeler"] = agree
    (OUT / "report.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
