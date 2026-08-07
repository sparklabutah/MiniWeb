#!/usr/bin/env python3
"""Migrate recorded task.json tags from the flat 121-macro model to the refined
two-axis model (base macro + optional reasoning operation).

For every data/annotations/<ann>/<task>/task.json (additive + backed up):
  - each old macro name resolves to a NEW base macro (+ operation when the map
    carries one, e.g. extract_by_extremum -> reasoning_on_page.extremum);
  - `macro_tags` (authoritative) = ONE entry per original tagged span:
    {macro, op, span, subtask, from}. Each annotator span is preserved exactly
    and NOT merged — so a base that occurs twice (e.g. two form submissions)
    stays two tags with their own spans. `macros` = deduped base names,
    `macro_operations` = {base: op} (summaries). `macro_spans`/`macro_subtasks`
    are deprecated (emptied) in favour of `macro_tags`.
  - deleted-but-actually-reasoning extract/compute tags recover to
    reasoning_on_page + an instruction-inferred op; other DELETE verdicts drop
    into `macro_migration.dropped` for a human re-tag (originals in `.from`).

Uses docs/macro_migration.csv (+ old sub-aliases + new-base identity).
Run: PYTHONPATH=. ~/.conda/envs/miniweb/bin/python scripts/migrate_macros_to_v2.py
"""
import csv
import glob
import json
import pathlib
import sys
import tarfile
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import annotation.macros as M

# old -> new (base or base.op) ; '' target means DELETE
MAP, DELETE = {}, set()
for row in csv.DictReader(open(ROOT / "docs" / "macro_migration.csv")):
    if row["note"] == "DELETE" or not row["new"]:
        DELETE.add(row["old_macro"])
    else:
        MAP[row["old_macro"]] = row["new"]
# old sub-aliases (were aliases in the *old* registry, not top-level 121)
MAP.update({
    "invite_by_form": "create_by_form", "submit_by_form": "create_by_form",
    "apply_by_form": "create_by_form", "create_by_query": "create_by_form",
    "create_from_free_text": "create_by_form", "register_by_form": "create_by_form",
    "post_from_free_text": "create_by_form", "share_by_query": "share_by_form",
    "subscribe_by_toggle": "toggle_relationship", "follow_by_toggle": "toggle_relationship",
    "save_by_toggle": "toggle_relationship", "navigate_by_sidebar": "navigate_by_route",
})


import re
# deleted-but-actually-reasoning macros: recover to reasoning_on_page + an op
# inferred from the instruction, instead of dropping.
RECOVER = {"extract_by_query", "extract_by_route", "extract_by_dropdown",
           "extract_by_date_range", "extract_by_semantic", "extract_by_ranking",
           "extract_by_toggle", "extract_by_code", "compute_by_dropdown", "compute_by_route"}
_COUNT = re.compile(r"\b(how many|number of|count)\b", re.I)
_COMPUTE = re.compile(r"\b(combined|total|sum|average|mean|difference between|convert|how much)\b", re.I)
_EXT = re.compile(r"\b(highest|lowest|oldest|newest|latest|cheapest|priciest|most|least|"
                  r"biggest|smallest|largest|longest|shortest|best|worst|top|greatest|fewest)\b", re.I)


def infer_op(instr):
    if _COUNT.search(instr):
        return "count"
    if _COMPUTE.search(instr):
        return "compute"
    if _EXT.search(instr):
        return "extremum"
    return "read"


def resolve(old, instr=""):
    """(base, op|None, disposition)."""
    if M.is_canonical(old):
        return old, None, "identity"
    if old in MAP:
        base, _, op = MAP[old].partition(".")
        return base, (op or None), "mapped"
    if old in RECOVER:
        return "reasoning_on_page", infer_op(instr), "recovered"
    if old in DELETE:
        return None, None, "deleted"
    return None, None, "unknown"


def main():
    files = sorted(glob.glob(str(ROOT / "data" / "annotations" / "*" / "*" / "task.json")))
    stamp = time.strftime("%Y%m%d_%H%M%S")
    bdir = ROOT / "data" / "backups"; bdir.mkdir(exist_ok=True)
    with tarfile.open(bdir / f"annotations_taskjson_pre_v2migrate_{stamp}.tar.gz", "w:gz") as tf:
        for f in files:
            tf.add(f, arcname=str(pathlib.Path(f).relative_to(ROOT)))

    n = flagged = emptied = 0
    for f in files:
        d = json.load(open(f))
        old_macros = d.get("macros") or []
        spans = d.get("macro_spans") or {}
        subs = d.get("macro_subtasks") or {}
        edges = d.get("macro_edges") or []

        instr = d.get("instruction") or ""
        remap = {}
        dropped = []
        # macro_tags: one entry PER original tagged span (preserves repeats and
        # each annotator span exactly — no merging). This is the authoritative
        # per-occurrence tagging in the two-axis model.
        tags = []
        for om in old_macros:
            base, op, _disp = resolve(om, instr)
            remap[om] = base
            if base is None:
                dropped.append(om)
                continue
            sp = spans.get(om)
            tags.append({
                "macro": base,
                "op": op,
                "span": list(sp) if (isinstance(sp, list) and len(sp) == 2) else None,
                "subtask": subs.get(om, ""),
                "from": om,
            })
        # keep the tags in trajectory order where a span exists
        tags.sort(key=lambda t: (t["span"][0] if t["span"] else 1e9))

        new_macros = list(dict.fromkeys(t["macro"] for t in tags))
        new_ops = {}
        for t in tags:
            if t["op"] and t["macro"] not in new_ops:
                new_ops[t["macro"]] = t["op"]
        # re-key edges to base names (dedup; base-level graph)
        new_edges, seen = [], set()
        for e in edges:
            a, b = remap.get(e.get("from")), remap.get(e.get("to"))
            if a and b and a != b and (a, b) not in seen:
                seen.add((a, b)); new_edges.append({"from": a, "to": b})

        d["macros"] = new_macros
        d["macro_operations"] = new_ops
        d["macro_tags"] = tags
        d["macro_edges"] = new_edges
        d["macro_migration"] = {"from": old_macros, "dropped": dropped}
        # deprecated by macro_tags (kept empty so stale readers don't get a
        # lossy merged span)
        d["macro_spans"] = {}
        d["macro_subtasks"] = {}
        if dropped:
            flagged += 1
        if not new_macros:
            emptied += 1
        json.dump(d, open(f, "w"), ensure_ascii=False, indent=1)
        n += 1

    from collections import Counter
    base_hist = Counter(b for f in files for b in (json.load(open(f)).get("macros") or []))
    op_hist = Counter(o for f in files for o in (json.load(open(f)).get("macro_operations") or {}).values())
    print(f"migrated {n} task.json")
    print(f"  tasks with a dropped (deleted-macro) tag -> needs re-tag: {flagged}")
    print(f"  tasks left with NO macros (only deleted): {emptied}")
    print(f"  operation instances: {dict(op_hist)}")
    print(f"  top new base macros: {dict(base_hist.most_common(10))}")


if __name__ == "__main__":
    main()
