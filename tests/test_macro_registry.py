"""Drift guard for the refined two-axis macro registry (data/macros.yaml, v2).

A tag is a base macro (physical interaction) + an optional reasoning operation.
This checks the registry is internally consistent; the per-site location and
template cross-checks are re-enabled once those are migrated to the new names.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import annotation.macros as R  # noqa: E402


def test_base_macros_complete():
    """Every base macro carries a group + description, and the group has a weight."""
    weights = R.category_weights()
    for m in R.all_canonical():
        e = R.entry(m)
        assert e.get("group"), f"{m} missing group"
        assert e.get("description"), f"{m} missing description"
        assert e["group"] in weights, f"{m} group {e['group']!r} has no weight"


def test_operations_closed_and_weighted():
    """The reasoning operations are a small closed vocab, each with a check."""
    ops = R.operations()
    assert set(ops) == {"read", "extremum", "count", "compute", "compare", "verify", "spatial"}, \
        f"operation vocabulary drifted: {sorted(ops)}"
    for op, info in ops.items():
        assert info.get("desc") and info.get("check"), f"operation {op} missing desc/check"


def test_aliases_resolve_and_dont_collide():
    """Aliases point at a real base macro, never shadow one, and canon is stable."""
    canon = set(R.all_canonical())
    for alias, target in R.alias_map().items():
        assert alias not in canon, f"alias {alias} also a base macro name"
        assert target in canon, f"alias {alias} -> {target} which is not a base macro"
        assert R.canon(alias) == target, f"canon({alias}) != {target}"
        assert R.canon(target) == target, f"canon of base {target} not idempotent"


def test_report_information_is_op_only():
    """report_information is the reasoning output base (replaces reasoning_on_page)."""
    e = R.entry("report_information")
    assert e.get("op_only") is True and e.get("group") == "reasoning"
    assert R.canon("reasoning_on_page") == "report_information"



def test_judge_rubrics_complete():
    """Every assigned macro and every operation carries a judge rubric; unassigned
    (UI-registered) macros fall back to the generic rubric."""
    for m in R.all_canonical():
        r = R.rubric(m)
        assert r.get("done") and r.get("fail_if") and r.get("must_match"), f"{m} rubric incomplete"
        if R.group_of(m) != "unassigned":
            assert R.entry(m).get("rubric"), f"{m} has no rubric in data/macros.yaml"
    for op in R.operations():
        assert R.op_rubric(op).get("done") and R.op_rubric(op).get("fail_if"), f"operation {op} rubric incomplete"
    assert R.rubric_principles().get("evidence_order")
    for m in R.all_canonical():                      # optional screenshot criteria for the vision judge
        visual = R.rubric(m).get("visual")
        assert visual is None or (isinstance(visual, list) and visual and all(isinstance(v, str) and v for v in visual)), m
    assert R.rubric("sign_by_freeformdrawing").get("visual") and R.op_rubric("spatial").get("visual")
    assert R.rubric("reasoning_on_page") == R.rubric("report_information")      # alias-resolved


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("all registry drift checks passed")
