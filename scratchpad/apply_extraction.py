"""Apply the LLM-extracted task-relevant body_fields to the restructured verifiers,
gold-gated: a macro's new body_fields is kept ONLY if the task still passes its own
gold trajectory. Otherwise that macro reverts to its prior body_fields.
"""
import glob, json, pathlib, sys
sys.path.insert(0, ".")
from evaluation.trajectory import synthesize_network_events
from evaluation.verifiers import verify_task

# 1) merge all batch outputs
extract = {}
for f in sorted(glob.glob("scratchpad/extract_out/batch_*.json")):
    try:
        d = json.load(open(f))
    except Exception as e:
        print("SKIP bad json", f, e); continue
    for tid, macros in d.items():
        extract.setdefault(tid, {}).update(macros)
print(f"extraction covers {len(extract)} tasks")


def req_leaves(node, out):
    if not isinstance(node, dict):
        return
    if node.get("op") in ("AND", "OR"):
        for c in node.get("checks", []):
            req_leaves(c, out)
    elif node.get("type") == "request_made":
        out.append(node)


def to_bf(spec_bf):
    """extracted {field:{value,mode}} -> engine body_fields (same shape, _field_match reads it)."""
    if not spec_bf:
        return None  # open: drop the body_fields assertion
    return {k: {"value": v.get("value", ""), "mode": v.get("mode", "auto")}
            if isinstance(v, dict) else v for k, v in spec_bf.items()}


kept = reverted = notraj = 0
for tf in sorted(glob.glob("data/annotations/*/*/task.json")):
    d = pathlib.Path(tf).parent
    tid = d.name
    if tid not in extract:
        continue
    vf = d / "verifier.json"
    spec = json.load(open(vf))
    task = json.load(open(tf))
    traj = synthesize_network_events(json.loads((d / "trajectory.json").read_text())) \
        if (d / "trajectory.json").exists() else []
    ans = (task.get("expected_answer") or "").strip()
    macros = spec.get("macros") or {}
    changed = False
    for macro, payload in extract[tid].items():
        if macro not in macros:
            continue
        leaves = []
        req_leaves(macros[macro], leaves)
        if not leaves:
            continue
        new_bf = to_bf(payload.get("body_fields"))
        # snapshot old body_fields to revert if gold breaks
        old = [lf.get("body_fields") for lf in leaves]
        for lf in leaves:
            if new_bf is None:
                lf.pop("body_fields", None)
            else:
                lf["body_fields"] = new_bf
        # gold-gate
        if verify_task(spec, traj, ans)["passed"]:
            kept += 1; changed = True
        else:
            for lf, ob in zip(leaves, old):
                if ob is None:
                    lf.pop("body_fields", None)
                else:
                    lf["body_fields"] = ob
            reverted += 1
    if changed:
        spec["extracted_fields"] = True
        vf.write_text(json.dumps(spec, indent=1, ensure_ascii=False))

print(f"kept {kept} macro-field-sets, reverted {reverted} (gold would break)")
