"""Grader agreement for the paper (Sec. 3.1, 2026-10-03): the deterministic verifier vs the flash macro judge, and both
against human ground truth.

A. Agent episodes (the RQ1 runs in webmix.rq1_analysis.RUNS): task-level agreement of judge and verifier, Cohen's kappa.
B. Human ground truth, on VALID gold recordings only (user, 2026-10-03): an annotator's recording (trajectory.json + the
   session's server log) that is not tagged stale (outdated against the current site / data) and that the task's current
   verifier accepts, i.e. complete, current evidence of the task. Older recordings that miss the graded request (early
   recorder versions dropped some form POSTs) or predate a task edit are not valid witnesses. On each valid recording:
     positive   the recording with the annotator's answer                                    (should pass)
     near-miss  the same recording cut just before its last required macro instance, no answer (should fail)
     empty      no actions, no answer                                                         (should fail)
   The verifier accepts every positive by construction (validity uses it); the judge's acceptance is measured, and both
   graders are measured on the negatives. The judge's reference comes from the same recording, so its positives are an
   easy case; the near-misses are the informative part.

    python -m webmix.grader_agreement [--parallel 4]
writes data/webmix/eval/grader_agreement.json; judge verdicts are cached in data/webmix/eval/grader_agreement_judge.jsonl.
"""
import argparse
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from webmix.evaluate import grade_human, human_tasks

EVAL = Path("data/webmix/eval")
ANN = Path("data/annotations")
OUT, CACHE = EVAL / "grader_agreement.json", EVAL / "grader_agreement_judge.jsonl"


def kappa(a, b):
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return po, (po - pe) / (1 - pe) if pe < 1 else float("nan")


def agent_agreement():
    """Judge vs verifier on every judged RQ1 episode."""
    from webmix.rq1_analysis import RUNS
    per, J, V = {}, [], []
    for name, run in RUNS.items():
        f = EVAL / run / "judge.jsonl"
        if not f.exists():
            continue
        j, v = [], []
        for line in f.read_text().splitlines():
            r = json.loads(line) if line.strip() else {}
            if r.get("passed") is not None and r.get("verifier") is not None:
                j.append(bool(r["passed"]))
                v.append(bool(r["verifier"]))
        po, k = kappa(j, v)
        per[name] = {"n": len(j), "agree": po, "kappa": k, "judge_only": sum(a and not b for a, b in zip(j, v)),
                     "verifier_only": sum(b and not a for a, b in zip(j, v))}
        J += j
        V += v
    po, k = kappa(J, V)
    return {"per_model": per, "all": {"n": len(J), "agree": po, "kappa": k,
                                      "judge_only": sum(a and not b for a, b in zip(J, V)),
                                      "verifier_only": sum(b and not a for a, b in zip(J, V))}}


def _ts(e):
    from evaluation.macro_judge import _parse_ts
    return _parse_ts(e.get("timestamp"))


def _aligned_times(traj):
    """{id(event): time} on the actions' clock. Browser actions carry UTC ('Z'); server-log requests carry the server's
    local time with no zone (e.g. 6 h behind in MDT), so each recording's zone-less events are shifted by the whole-hour
    offset that puts most of them inside the span of its actions."""
    import datetime as dt
    t = {id(e): _ts(e) for e in traj}
    acts = [t[id(e)] for e in traj if e.get("type") == "action" and t[id(e)]]
    naive = [e for e in traj if t[id(e)] and not any(z in str(e.get("timestamp")) for z in ("Z", "+"))]
    if not acts or not naive:
        return t
    lo, hi, pad = min(acts), max(acts), dt.timedelta(seconds=60)
    best = max(range(-14, 15), key=lambda h: (sum(lo - pad <= t[id(e)] + dt.timedelta(hours=h) <= hi + pad for e in naive),
                                              -abs(h)))
    for e in naive:
        t[id(e)] += dt.timedelta(hours=best)
    return t


def near_miss(task, traj):
    """The recording cut just before the first action of its last required macro instance (by span start)."""
    spans, req = task.get("macro_spans") or {}, task.get("macro_required") or {}
    insts = [i for i in task.get("macro_instances") or []
             if req.get(i, True) and isinstance(spans.get(i), list) and len(spans[i]) == 2]
    if not insts:
        return None, None
    last = max(insts, key=lambda i: spans[i][0])
    actions = [e for e in traj if e.get("type") == "action"]
    start = spans[last][0]
    if not 1 <= start <= len(actions):
        return None, None
    cut_event = actions[start - 1]
    times = _aligned_times(traj)
    cut_pos, cut_ts = next(n for n, e in enumerate(traj) if e is cut_event), times[id(cut_event)]
    keep = []
    for n, e in enumerate(traj):
        ts = times[id(e)]
        if (ts < cut_ts) if (ts is not None and cut_ts is not None) else (n < cut_pos):
            keep.append(e)
    return keep, last


def main(argv=None):
    from annotation.app import _load_test_trajectory
    from evaluation import macro_judge as MJ
    ap = argparse.ArgumentParser()
    ap.add_argument("--parallel", type=int, default=4)
    args = ap.parse_args(argv)
    tasks = {t["task_id"]: t for t in human_tasks(split="all")}

    # B1. valid gold recordings
    valid, excluded = [], {"stale": 0, "verifier_rejects_recording": 0}
    for f in sorted(ANN.glob("*/*/task.json")):
        t = json.loads(f.read_text())
        if t["task_id"] not in tasks:
            continue
        ann = f.parent.parent.name
        if ((t.get("review_tag") or {}).get("tag")) == "stale":
            excluded["stale"] += 1
            continue
        traj, answer, _ = _load_test_trajectory(ann, t["task_id"], "gold")
        if not grade_human(tasks[t["task_id"]], traj or [], answer)[0]:
            excluded["verifier_rejects_recording"] += 1
            continue
        valid.append((ann, t, traj, answer))
    print(f"valid gold recordings: {len(valid)} of {len(tasks)} (excluded {excluded})", flush=True)

    # B2. cases: positive / near-miss / empty, graded by the verifier (cheap) and the judge (cached)
    cases = []
    for ann, t, traj, answer in valid:
        key, tid = f"{ann}/{t['task_id']}", t["task_id"]
        cases.append({"key": key, "task_id": tid, "kind": "positive", "truth": True, "traj": traj, "answer": answer})
        cut, inst = near_miss(t, traj)
        if cut is not None:
            cases.append({"key": key, "task_id": tid, "kind": "near_miss", "truth": False, "traj": cut, "answer": "",
                          "cut_before": inst})
        cases.append({"key": key, "task_id": tid, "kind": "empty", "truth": False, "traj": [], "answer": ""})
    for c in cases:
        c["verifier"] = grade_human(tasks[c["task_id"]], c["traj"], c["answer"])[0]
    done = {}
    if CACHE.exists():
        for line in CACHE.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                done[(r["key"], r["kind"])] = r["judge"]
    lock = threading.Lock()

    def judge(c):
        if (c["key"], c["kind"]) in done:
            return done[(c["key"], c["kind"])]
        try:
            v = bool(MJ.grade(c["key"], c["traj"], c["answer"])["passed"])
        except Exception as e:                      # an unanswered judge call stays out of the counts
            print(f"judge error {c['key']} {c['kind']}: {type(e).__name__}: {str(e)[:120]}", flush=True)
            return None
        with lock, open(CACHE, "a") as fh:
            fh.write(json.dumps({"key": c["key"], "kind": c["kind"], "judge": v}) + "\n")
        return v
    with ThreadPoolExecutor(args.parallel) as pool:
        for c, v in zip(cases, pool.map(judge, cases)):
            c["judge"] = v

    def rates(kind):
        cs = [c for c in cases if c["kind"] == kind]
        out = {"n": len(cs)}
        for g in ("verifier", "judge"):
            got = [c[g] for c in cs if c[g] is not None]
            out[g + "_pass"] = sum(got) / len(got) if got else None
            out[g + "_n"] = len(got)
        return out
    human = {k: rates(k) for k in ("positive", "near_miss", "empty")}
    for g in ("verifier", "judge"):
        cs = [c for c in cases if c[g] is not None]
        human[g + "_accuracy"] = sum(c[g] == c["truth"] for c in cs) / len(cs)
        neg = [c for c in cs if not c["truth"] and c["kind"] == "near_miss"]
        human[g + "_near_miss_rejected"] = sum(not c[g] for c in neg) / len(neg) if neg else None
    res = {"agent_episodes": agent_agreement(), "human_ground_truth": {"valid_recordings": len(valid),
           "tasks": len(tasks), "excluded": excluded, **human},
           "near_miss_accepted": [{"task_id": c["task_id"], "cut_before": c.get("cut_before"), "verifier": c["verifier"],
                                   "judge": c["judge"]} for c in cases if c["kind"] == "near_miss" and (c["verifier"] or c["judge"])]}
    OUT.write_text(json.dumps(res, indent=1))
    a = res["agent_episodes"]["all"]
    print(f"A. agent episodes: n={a['n']} agree {100 * a['agree']:.1f}% kappa {a['kappa']:.2f} "
          f"(judge-only pass {a['judge_only']}, verifier-only pass {a['verifier_only']})")
    h = res["human_ground_truth"]
    for k in ("positive", "near_miss", "empty"):
        r = h[k]
        print(f"B. {k:9s} n={r['n']:3d}  verifier pass {100 * r['verifier_pass']:.1f}%  judge pass "
              f"{100 * r['judge_pass']:.1f}% (n={r['judge_n']})")
    print(f"   accuracy vs human labels: verifier {100 * h['verifier_accuracy']:.1f}%  judge {100 * h['judge_accuracy']:.1f}%")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
