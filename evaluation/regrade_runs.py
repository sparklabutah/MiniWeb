"""Offline re-grade of past browser-use runs after the build_trajectory query fix.

No agents are re-run. Each run already saved everything we need:
  - server_log.json   : the RAW request log (query dict intact)
  - trajectory.json    : the assembled trajectory (actions/observations correct;
                         network URLs were the lossy, query-stripped version)
  - result.json        : agent_answer, instruction, annotator, task_id, historical pass

For each run we rebuild the trajectory the way the FIXED build_trajectory does
(actions/observations kept, network taken from server_log WITH the query), then
grade both the buggy (saved) and the fixed trajectory with the SAME current
verifier.json — so a FAIL->PASS flip is attributable to the fix, not verifier drift.

Usage:
    python evaluation/regrade_runs.py [--results evaluation/results] [--out regrade_diff.json]
"""
import argparse
import glob
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlencode

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))                       # for `import app`
sys.path.insert(0, str(REPO / "evaluation"))        # for trajectory / verifiers
from trajectory import synthesize_network_events   # noqa: E402
from verifiers import verify_task                   # noqa: E402

ANN = REPO / "data" / "annotations"


def rebuild_fixed(saved_traj, server_log):
    """Mirror the FIXED build_trajectory from saved artifacts."""
    traj = [e for e in saved_traj if e.get("type") != "network"]
    for e in server_log:
        url = e.get("path", "")
        query = e.get("query") or {}
        if query:
            url = url + "?" + urlencode(query)
        traj.append({
            "type": "network", "method": e.get("method"), "url": url,
            "status": e.get("status"), "requestBody": e.get("body"),
        })
    return synthesize_network_events(traj)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=str(REPO / "evaluation" / "results"))
    ap.add_argument("--out", default=str(REPO / "evaluation" / "regrade_diff.json"))
    args = ap.parse_args()

    from app import create_app
    app = create_app()
    rows = []
    skipped = []
    with app.test_request_context():
        for d in sorted(glob.glob(os.path.join(args.results, "*", "*", ""))):
            need = [os.path.join(d, f) for f in ("trajectory.json", "server_log.json", "result.json")]
            if not all(os.path.exists(p) for p in need):
                skipped.append((os.path.basename(d.rstrip("/")), "missing artifact"))
                continue
            res = json.load(open(os.path.join(d, "result.json")))
            ann, tid = res.get("annotator"), res.get("task_id")
            vf = ANN / (ann or "") / (tid or "") / "verifier.json"
            if not vf.exists():
                skipped.append((f"{ann}/{tid}", "no verifier.json"))
                continue
            verifier = json.loads(vf.read_text())
            saved = json.load(open(os.path.join(d, "trajectory.json")))
            log = json.load(open(os.path.join(d, "server_log.json")))
            ans = res.get("agent_answer", "") or ""
            instr = res.get("instruction", "")

            base_rep = verify_task(verifier, saved, ans, instr)           # buggy traj
            fixed_rep = verify_task(verifier, rebuild_fixed(saved, log), ans, instr)  # fixed traj

            rows.append({
                "run": os.path.basename(d.rstrip("/")),
                "task": f"{ann}/{tid}",
                "historical_pass": res.get("passed"),
                "baseline_pass": base_rep["passed"],   # saved traj + current verifier
                "fixed_pass": fixed_rep["passed"],      # fixed traj + current verifier
                "by_macro_baseline": base_rep.get("by_macro"),
                "by_macro_fixed": fixed_rep.get("by_macro"),
            })

    recovered = [r for r in rows if r["baseline_pass"] is False and r["fixed_pass"] is True]
    regressed = [r for r in rows if r["baseline_pass"] is True and r["fixed_pass"] is False]
    # macro-level recoveries even when the whole task didn't flip
    macro_recovered = []
    for r in rows:
        b, f = r["by_macro_baseline"] or {}, r["by_macro_fixed"] or {}
        for m in f:
            if f.get(m) and not b.get(m):
                macro_recovered.append((r["task"], m))

    print(f"regraded {len(rows)} runs ({len(skipped)} skipped)")
    print(f"\nTASK-LEVEL  FAIL->PASS (recovered by fix): {len(recovered)}")
    for r in recovered:
        print("   +", r["task"])
    print(f"TASK-LEVEL  PASS->FAIL (regressions): {len(regressed)}")
    for r in regressed:
        print("   -", r["task"])
    print(f"\nMACRO-LEVEL recoveries (a macro flipped fail->pass): {len(macro_recovered)}")
    for task, m in macro_recovered:
        print(f"   + {task}  [{m}]")

    Path(args.out).write_text(json.dumps({
        "summary": {"regraded": len(rows), "skipped": len(skipped),
                    "task_recovered": len(recovered), "task_regressed": len(regressed),
                    "macro_recovered": len(macro_recovered)},
        "recovered": [r["task"] for r in recovered],
        "regressed": [r["task"] for r in regressed],
        "macro_recovered": macro_recovered,
        "rows": rows, "skipped": skipped,
    }, indent=1, default=str))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
