import glob, json, pathlib
from evaluation.trajectory import synthesize_network_events
from evaluation.verifiers import verify_task
SF={"search","filter_by_dropdown","filter_by_options","filter_by_date_range"}
def start_path(d):
    tj=d/"trajectory.json"
    if tj.exists():
        for e in json.loads(tj.read_text()):
            u=e.get("url")
            if u and "/sites/" in u: return u[u.find("/sites/"):].split("?")[0]
    return "/sites/"
gfail=[]; gtot=0; sf_fixed=0; sf_tot=0
for tf in sorted(glob.glob("data/annotations/*/*/task.json")):
    d=pathlib.Path(tf).parent; vf=d/"verifier.json"
    if not vf.exists(): continue
    spec=json.load(open(vf)); t=json.load(open(tf)); gtot+=1
    gold=synthesize_network_events(json.loads((d/"trajectory.json").read_text()))
    a=(t.get("expected_answer") or "").strip()
    if not verify_task(spec,gold,a)["passed"]: gfail.append(f"{d.parent.name}/{d.name}")
    if spec.get("query_gated"):
        sp=start_path(d)
        pageload=[{"type":"network","method":"GET","url":sp,"status":200},
                  {"type":"action","action":"click","target":"link 'Home'"}]
        rep=verify_task(spec, pageload, a)
        for m in (spec.get("macros") or {}):
            if m in SF:
                sf_tot+=1; sf_fixed+= (rep["by_macro"].get(m) is False)
print(f"GOLD: {gtot-len(gfail)}/{gtot} pass  fails={gfail}")
print(f"page-load-only now FAILS search/filter: {sf_fixed}/{sf_tot} (should be all)")
