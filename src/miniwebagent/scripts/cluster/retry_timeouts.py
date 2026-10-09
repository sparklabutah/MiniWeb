"""Set aside live-web episodes that ENDED because the model server timed out (2026-10-04): 72 browsers on one 24 GB GPU made
LLM calls exceed 75 s, and an agent whose last steps all time out stops with no answer. Rule (same for every run): planner
agents - the last 3 planner steps all failed with a timeout; single agents - the last 2 steps did. Such an episode is moved
to om2w/runs/_timeout_killed_20261004/<run>/<task> and its line is removed from the run's results_*.jsonl (backed up there),
so `live_comp.sh run` with the original arguments reruns exactly those episodes. Nothing is deleted."""
import glob, json, os, shutil, sys
O = os.path.join(os.environ["WEBMIX_ROOT"], "om2w", "runs"); AS = O + "/_timeout_killed_20261004"
SINGLE = {"webvoyager100_single_pooled", "om2w100_single_pooled"}


def killed(ep, single):
    hs = sorted(glob.glob(ep + ("/history*.json" if single else "/planner_history.json")))
    if not hs:
        return False
    try:
        h = json.load(open(hs[-1]))
    except Exception:
        return False
    h = h.get("history", h) if isinstance(h, dict) else h
    last = h[-2:] if single else h[-3:]
    return bool(last) and all(any("timed out" in str(x.get("error") or "") for x in (s.get("result") or [])) for s in last)


tot = 0
for run in sys.argv[1:]:
    d = f"{O}/{run}"
    ids = [os.path.basename(e) for e in sorted(glob.glob(d + "/*"))
           if os.path.isdir(e) and os.path.exists(e + "/result.json") and killed(e, run in SINGLE)]
    os.makedirs(f"{AS}/{run}/results_backup", exist_ok=True)
    gone = set(ids)
    for f in glob.glob(d + "/results_*.jsonl"):
        shutil.copy2(f, f"{AS}/{run}/results_backup/")
        keep = [line for line in open(f) if line.strip() and json.loads(line).get("task_id") not in gone]
        open(f, "w").write("".join(keep))
    for t in ids:
        shutil.move(f"{d}/{t}", f"{AS}/{run}/{t}")
    json.dump(ids, open(f"{AS}/{run}/ids.json", "w"))
    tot += len(ids)
    print(f"{run}: set aside {len(ids)} episodes", flush=True)
print("total", tot)
