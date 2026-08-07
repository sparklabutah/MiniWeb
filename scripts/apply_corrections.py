#!/usr/bin/env python3
"""Apply a corrections.json (exported from the migration-review artifact) onto the
migrated task.json files.

For each task in corrections["tasks"]:
  - disposition == "delete": quarantine the whole task dir under
    data/backups/deleted_<stamp>/ (recoverable, not rm), record in a manifest.
  - otherwise: overwrite macro_tags with the reviewed tags (base + op + span),
    recompute macros / macro_operations, set expected_outcome when present, and
    stamp macro_review = {status:"reviewed", by:"user"}.

Proposed new macros must already be registered in data/macros.yaml (guarded by
tests/test_macro_registry.py) — this script only asserts they resolve.

Run: PYTHONPATH=. ~/.conda/envs/miniweb/bin/python scripts/apply_corrections.py <corrections.json>
"""
import json
import glob
import pathlib
import shutil
import sys
import tarfile
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import annotation.macros as M

# why each task was deleted (policy: not deterministically gradeable)
DELETE_REASON = {
    "Farhan/flights-hotels_5b8f40": "degenerate — select-only, trivial existence+select",
    "Kenny/insurance-loans_500ea4": "degenerate — single dropdown select, incomplete task",
    "Minh/handwritten-notes-whiteboards_061a3c": "non-deterministic signal — free-form signature (draw a shape) can't be graded",
    "Minh/handwritten-notes-whiteboards_b3a21a": "non-deterministic signal — free-form signature (draw a shape) can't be graded",
    "Minh/remote-calls_707134": "noisy/messy trajectory",
    "Minh/transit-directions_b358d4": "redundant duplicate of transit-directions_41767c",
    "Kenny/calendar-todo_7cecde": "redundant duplicate of calendar-todo_b07459 (hardcodes event/334)",
    "Minh/code-editor-execution_8239f3": "messy/incomplete trajectory — never reaches FlowNet, no share submit",
    "hernan/qa-knowledge_839dc8": "noisy/unverifiable — 43 blank scrolls, never opened Newest tab",
    "hernan/weather_rating-review_59b200": "reviewer marked delete",
    "Kenny/job-sites_map-services_2faa44": "TODO/incomplete task (missing last macro step)",
    "Minh/handwritten-notes-whiteboards_65a0cc": "non-deterministic signal — free-form signature drawing",
    "Minh/project-homepages_09e45e": "reviewer marked delete (license not in any captured observation)",
}


def find_map():
    m = {}
    for f in glob.glob(str(ROOT / "data" / "annotations" / "*" / "*" / "task.json")):
        tid = "/".join(f.split("/")[-3:-1])
        m[tid.lower()] = f
    return m


def main():
    corr = json.load(open(sys.argv[1] if len(sys.argv) > 1 else ROOT / "corrections.json"))
    stamp = time.strftime("%Y%m%d_%H%M%S")
    bdir = ROOT / "data" / "backups"
    bdir.mkdir(exist_ok=True)
    files = sorted(glob.glob(str(ROOT / "data" / "annotations" / "*" / "*" / "task.json")))
    with tarfile.open(bdir / f"annotations_taskjson_pre_apply_{stamp}.tar.gz", "w:gz") as tf:
        for f in files:
            tf.add(f, arcname=str(pathlib.Path(f).relative_to(ROOT)))

    # assert any proposed macros are registered
    for nm in (corr.get("proposed", {}).get("macros") or []):
        assert M.is_canonical(nm), f"proposed macro {nm!r} not registered in data/macros.yaml"

    fmap = find_map()
    quarantine = bdir / f"deleted_{stamp}"
    deleted_manifest, retagged = [], 0

    for tid, rec in corr["tasks"].items():
        f = fmap.get(tid.lower())
        if not f:
            print(f"  ! MISSING {tid}"); continue
        tdir = pathlib.Path(f).parent

        if rec.get("disposition") == "delete":
            d = json.load(open(f))
            dest = quarantine / tid
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(tdir), str(dest))
            deleted_manifest.append({
                "id": tid, "reason": DELETE_REASON.get(tid, "marked for deletion"),
                "instruction": d.get("instruction", ""),
                "from": (d.get("macro_migration") or {}).get("from") or [],
            })
            print(f"  🗑 deleted {tid} -> {dest.relative_to(ROOT)}")
            continue

        # retag
        d = json.load(open(f))
        tags = []
        for t in rec["tags"]:
            base = M.canon(t["macro"])  # migrate retired names (e.g. reasoning_on_page -> report_information)
            assert M.is_canonical(base), f"{tid}: tag macro {t['macro']!r} -> {base!r} not canonical"
            tags.append({
                "macro": base, "op": t.get("op") or None,
                "span": t.get("span") if (isinstance(t.get("span"), list) and len(t["span"]) == 2) else None,
                "subtask": "", "from": "reviewed",
            })
        tags.sort(key=lambda x: (x["span"][0] if x["span"] else 1e9))
        d["macro_tags"] = tags
        d["macros"] = list(dict.fromkeys(t["macro"] for t in tags))
        ops = {}
        for t in tags:
            if t["op"] and t["macro"] not in ops:
                ops[t["macro"]] = t["op"]
        d["macro_operations"] = ops
        if "expected_outcome" in rec:
            d["expected_outcome"] = rec["expected_outcome"]
        d["macro_review"] = {"status": "reviewed", "by": "user", "at": stamp}
        # a reviewed task has nothing outstanding
        d["macro_migration"] = {"from": (d.get("macro_migration") or {}).get("from") or [], "dropped": []}
        json.dump(d, open(f, "w"), ensure_ascii=False, indent=1)
        retagged += 1
        print(f"  ✎ retagged {tid}: {d['macros']}")

    man = {"applied_at": stamp, "deleted": deleted_manifest,
           "retagged_count": retagged, "corrections_file": str(sys.argv[1] if len(sys.argv) > 1 else "corrections.json")}
    (bdir / f"apply_manifest_{stamp}.json").write_text(json.dumps(man, ensure_ascii=False, indent=1))
    # also drop a stable copy for the artifact builder
    (ROOT / "data" / "backups" / "last_apply_manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1))
    print(f"\napplied: {retagged} retagged, {len(deleted_manifest)} deleted (quarantined under {quarantine.name})")
    print(f"manifest: data/backups/apply_manifest_{stamp}.json")


if __name__ == "__main__":
    main()
