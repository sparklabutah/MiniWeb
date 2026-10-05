"""Flash macro judge on webmix.evaluate / webmix.fara_rq1 run folders (RQ1 per-skill analysis, 2026-10-02).

evaluation.macro_judge reads run_study result folders (result.json + trajectory.json). Our runs keep the same merged
trajectory in <run>/<task_id>/grade_inputs.json ({"traj", "answer"}), so this feeds those to macro_judge.grade unchanged.
Screenshots for `visual` criteria come from <episode>/history.json + screenshots/ (browser-use runs); for Fara's own loop
(no history.json) the episode's last fara/screenshot_*_post.png is used as the final frame, and for the other own-loop
runs (webmix/ownloop_runner.py) the last screens/step_*.png.

    python -m webmix.judge_runs --runs rq1_qwen35_4b_all,rq1_qwen35_9b_all --parallel 3
writes data/webmix/eval/<run>/judge.jsonl (one line per episode; a rerun resumes).
"""
import argparse
import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from evaluation import macro_judge as MJ
from webmix.evaluate import human_tasks

EVAL = Path("data/webmix/eval")
_orig_frames = MJ.agent_frames


def _frames(episode_dir, page=None, limit=2):
    got = _orig_frames(episode_dir, page, limit)
    if got:
        return got
    shots = sorted(Path(episode_dir).glob("fara/screenshot_*_post.png"),
                   key=lambda p: int(re.search(r"screenshot_(\d+)_post", p.name).group(1)))
    if not shots:
        shots = sorted(Path(episode_dir).glob("screens/step_*.png"))
    return [(len(shots), None, shots[-1])] if shots else []


MJ.agent_frames = _frames


def judge_run(run, by_id, parallel):
    d = EVAL / run
    out = d / "judge.jsonl"
    done = {json.loads(l)["task_id"] for l in out.read_text().splitlines() if l.strip()} if out.exists() else set()
    eps = [p.parent for p in sorted(d.glob("*/grade_inputs.json")) if p.parent.name in by_id and p.parent.name not in done]
    verdict = {}
    for f in ("results_regraded.jsonl", "results.jsonl"):
        if (d / f).exists():
            for l in (d / f).read_text().splitlines():
                if l.strip():
                    r = json.loads(l)
                    verdict[r["task_id"]] = bool(r.get("ok"))
            break
    lock = threading.Lock()

    def one(ep):
        g = json.loads((ep / "grade_inputs.json").read_text())
        t = by_id[ep.name]
        try:
            res = MJ.grade(t["key"], g.get("traj") or [], g.get("answer") or "", episode_dir=ep)
        except Exception as e:
            res = {"passed": None, "error": f"{type(e).__name__}: {str(e)[:200]}", "instances": {}}
        row = {"run": run, "task_id": ep.name, "key": t["key"], "verifier": verdict.get(ep.name), **res}
        with lock, open(out, "a") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        return row

    with ThreadPoolExecutor(parallel) as pool:
        rows = list(pool.map(one, eps))
    n = len(done) + len(rows)
    print(f"{run}: {n} episodes judged ({len(rows)} new) -> {out}", flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--parallel", type=int, default=3)
    a = ap.parse_args(argv)
    by_id = {t["task_id"]: t for t in human_tasks(split="all")}
    runs = a.runs.split(",")
    with ThreadPoolExecutor(len(runs)) as pool:
        list(pool.map(lambda r: judge_run(r, by_id, a.parallel), runs))


if __name__ == "__main__":
    main()
