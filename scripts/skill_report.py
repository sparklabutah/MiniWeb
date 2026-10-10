"""Per-skill results of MiniWeb runs: task success, then the share of primitive instances passed per skill family and
per primitive, by the VLM judge and by the task verifiers, and optionally the failed instances with the judge's reason.

A run is an output folder of `python -m miniwebagent.evaluate --out <run>`: results.jsonl (or results_regraded.jsonl)
holds each task's verifier verdicts, judge.jsonl the judge's (python src/miniweb/evaluation/judge_runs.py --runs <run>).

    python scripts/skill_report.py runs/my_agent
    python scripts/skill_report.py runs/agent_a runs/agent_b --by primitive
    python scripts/skill_report.py runs/my_agent --failures 20 --family "Drag & gesture"
"""
import argparse, ast, collections, json, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from miniwebgen.viewer import FAMILIES  # noqa: E402

FAMILY = {m: f for f, ms in FAMILIES.items() for m in ms}
ORDER = list(FAMILIES)
FINAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "final_set.yaml")


def final_primitives():
    """The paper's 37 primitives (data/final_set.yaml); instances of the 9 dropped ones are left out by default."""
    import yaml
    return set(yaml.safe_load(open(FINAL))["primitives"]) if os.path.exists(FINAL) else None


def rows(path):
    return [json.loads(line) for line in open(path) if line.strip()] if os.path.exists(path) else []


def load(run):
    res = rows(os.path.join(run, "results_regraded.jsonl")) or rows(os.path.join(run, "results.jsonl"))
    verifier = {}
    for r in res:
        d = r.get("detail")
        d = ast.literal_eval(d) if isinstance(d, str) and d.startswith("{") else (d if isinstance(d, dict) else {})
        verifier[r["task_id"]] = (bool(r.get("ok")), {k: bool(v) for k, v in d.items()})
    judge = {}
    for r in rows(os.path.join(run, "judge.jsonl")):
        inst = {k: (bool(v.get("passed")), v.get("why", "")) for k, v in (r.get("instances") or {}).items()}
        judge[r["task_id"]] = (bool(r.get("passed")), inst)
    return verifier, judge


def pct(a, n):
    return f"{100 * a / n:5.1f}%" if n else "    -"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--by", choices=["family", "primitive"], default="family")
    ap.add_argument("--failures", type=int, default=0, help="list this many failed instances (judge's reason)")
    ap.add_argument("--family", help="with --failures: only this family")
    ap.add_argument("--all-primitives", action="store_true",
                    help="also count the 9 primitives dropped from the final set (the paper's tables leave them out)")
    a = ap.parse_args()
    keep = None if a.all_primitives else final_primitives()
    for run in a.runs:
        verifier, judge = load(run)
        tasks = sorted(set(verifier) | set(judge))
        print(f"\n{run}: {len(tasks)} tasks")
        if judge:
            print(f"  task success, judge     {pct(sum(p for p, _ in judge.values()), len(judge))}  ({len(judge)} judged)")
        if verifier:
            print(f"  task success, verifiers {pct(sum(p for p, _ in verifier.values()), len(verifier))}  ({len(verifier)} graded)")
        stat = collections.defaultdict(lambda: [0, 0, 0, 0])     # key -> judge pass, judge n, verifier pass, verifier n
        fails = []
        for t in tasks:
            for inst, (ok, why) in (judge.get(t, (None, {}))[1]).items():
                m = inst.split("#")[0]
                if keep and m not in keep:
                    continue
                key = FAMILY.get(m, "Other") if a.by == "family" else m
                stat[key][0] += ok; stat[key][1] += 1
                if not ok:
                    fails.append((t, inst, FAMILY.get(m, "Other"), why))
            for inst, ok in (verifier.get(t, (None, {}))[1]).items():
                m = inst.split("#")[0]
                if keep and m not in keep:
                    continue
                key = FAMILY.get(m, "Other") if a.by == "family" else m
                stat[key][2] += ok; stat[key][3] += 1
        keys = [k for k in ORDER if k in stat] + sorted(k for k in stat if k not in ORDER) if a.by == "family" else \
            sorted(stat, key=lambda k: (stat[k][0] / stat[k][1]) if stat[k][1] else 2)
        print(f"  {'instances passed by ' + a.by:34s} {'n':>5s}  {'judge':>6s}  {'verifier':>8s}")
        for k in keys:
            jp, jn, vp, vn = stat[k]
            print(f"  {k:34s} {max(jn, vn):5d}  {pct(jp, jn):>6s}  {pct(vp, vn):>8s}")
        jp, jn, vp, vn = (sum(v[i] for v in stat.values()) for i in range(4))
        print(f"  {'all instances':34s} {max(jn, vn):5d}  {pct(jp, jn):>6s}  {pct(vp, vn):>8s}")
        if a.failures:
            shown = [f for f in fails if not a.family or f[2] == a.family][:a.failures]
            print(f"\n  failed instances{' (' + a.family + ')' if a.family else ''}: {len(shown)} shown")
            for t, inst, fam, why in shown:
                print(f"  - {t} / {inst} [{fam}]: {why[:160]}")


if __name__ == "__main__":
    main()
