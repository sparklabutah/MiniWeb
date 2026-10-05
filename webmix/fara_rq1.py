"""RQ1 with Fara1.5 as released (2026-10-02): prepare the MiniWeb human tasks for webmix/fara_runner.py (which runs in the
fara venv) and grade what it saved, exactly as webmix.evaluate grades human tasks. The other own-loop baselines
(webmix/ownloop_runner.py: UI-TARS-1.5, MolmoWeb; 2026-10-03) save the same session.json and grade with --arm.

    python -m webmix.fara_rq1 prep  --out data/webmix/eval/rq1_fara15_4b_all [--split all]
    /home/u1653932/venvs/fara/bin/python webmix/fara_runner.py --tasks <out>/tasks.json --out <out> --bases ... --endpoint ...
    python -m webmix.fara_rq1 grade --out data/webmix/eval/rq1_fara15_4b_all [--split all] [--arm fara15]

prep writes tasks.json with {BASE} placeholders: the start page and prompt of webmix.evaluate.prepare_human (a multi-site
task starts at the portal home with the app directory appended). grade turns each session.json into the usual
grade_inputs.json (merge_server_log of the recorder stream and request log) + results.jsonl, then grades with
webmix.evaluate.grade_human (the full QA tier chain).
"""
import argparse
import json
from pathlib import Path

from webmix.evaluate import grade_human, human_tasks


def prep(out, split):
    from evaluation.run_agent_verify import app_directory, resolve_start_url
    rows = []
    for t in human_tasks(split=split):
        if len(t["sites"]) > 1:
            start, prompt = "{BASE}/", t["instruction"] + app_directory("{BASE}", t["sites"])
        else:
            start, prompt = resolve_start_url("{BASE}", t["start_hint"], t["site"]), t["instruction"]
        rows.append({"task_id": t["task_id"], "needs_login": bool(t["needs_login"]), "start": start, "prompt": prompt})
    out.mkdir(parents=True, exist_ok=True)
    (out / "tasks.json").write_text(json.dumps(rows, indent=1))
    print(f"{len(rows)} tasks -> {out / 'tasks.json'}")


def grade(out, split, arm="fara15"):
    from evaluation.trajectory import merge_server_log
    by_id = {t["task_id"]: t for t in human_tasks(split=split)}
    n = ok_n = 0
    with open(out / "results.jsonl", "w") as f:
        for sj in sorted(out.glob("*/session.json")):
            s = json.loads(sj.read_text())
            tid = s["task_id"]
            if tid not in by_id:
                continue
            traj = merge_server_log([e for e in s.get("record") or [] if e.get("type") != "network"], s.get("log") or [])
            (sj.parent / "grade_inputs.json").write_text(json.dumps({"base": s["base"], "traj": traj, "answer": s["answer"]},
                                                                   default=str))
            try:
                ok, detail = grade_human(by_id[tid], traj, s["answer"])
            except Exception as e:
                ok, detail = False, f"grade error {type(e).__name__}: {str(e)[:200]}"
            n += 1
            ok_n += bool(ok)
            f.write(json.dumps({"task_id": tid, "arm": arm, "ok": bool(ok), "detail": detail, "answer": s["answer"],
                                "status": s.get("status"), "error": s.get("error"), "seconds": s.get("seconds"),
                                "macro": by_id[tid].get("macro"), "site": by_id[tid].get("site")}, default=str) + "\n")
    print(f"{arm}: {ok_n}/{n} = {100 * ok_n / max(n, 1):.1f}%")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["prep", "grade"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--split", default="all", choices=["test", "train", "all"])
    ap.add_argument("--arm", default="fara15", help="grade: the arm name written to results.jsonl")
    a = ap.parse_args(argv)
    if a.cmd == "prep":
        prep(Path(a.out), a.split)
    else:
        grade(Path(a.out), a.split, a.arm)


if __name__ == "__main__":
    main()
