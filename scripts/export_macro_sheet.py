#!/usr/bin/env python
"""Regenerate docs/MiniWeb_Macro_Sheet.csv from the canonical registry.

The sheet is a HUMAN-READABLE EXPORT, never edited by hand — that hand-editing
is exactly what let its old `status` column drift out of sync with the alias
map. Run after changing data/macros.yaml:  python scripts/export_macro_sheet.py
"""
import csv
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import annotation.macros as R  # noqa: E402
import annotation.app as A  # noqa: E402
from annotation.storage import list_tasks  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "MiniWeb_Macro_Sheet.csv")


def main():
    # canonical site mapping + task usage
    canon_sites = {}
    for site, macros in A._canonical_macro_locations().items():
        for m in macros:
            canon_sites.setdefault(m, set()).add(site)
    task_ct = Counter()
    for t in list_tasks():
        for m in t.get("macros", []):
            task_ct[R.canon(m)] += 1

    weights = R.category_weights()
    rows = []
    for m in R.all_canonical():
        e = R.entry(m)
        rows.append({
            "macro": m,
            "verb": e.get("verb", ""),
            "modality": e.get("modality", ""),
            "difficulty": e.get("category", ""),
            "weight": weights.get(e.get("category", ""), ""),
            "sites_mapped": len(canon_sites.get(m, ())),
            "tasks_using": task_ct.get(m, 0),
            "aliases": " ".join(e.get("aliases", []) or []),
            "description": e.get("description", ""),
            "example": e.get("example", ""),
        })
    # sort by difficulty weight (hardest first), then name
    rows.sort(key=lambda r: (-(r["weight"] or 0), r["macro"]))

    cols = ["macro", "verb", "modality", "difficulty", "weight", "sites_mapped",
            "tasks_using", "aliases", "description", "example"]
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {OUT} ({len(rows)} canonical macros)")


if __name__ == "__main__":
    main()
