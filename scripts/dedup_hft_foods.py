#!/usr/bin/env python
"""De-duplicate the health-fitness-tracking `foods` reference table.

The USDA import has many near-duplicate descriptions ("ALMOND BUTTER, ALMOND",
plurals, word-order variants, "... NS as to fat", etc.). This collapses them:

  Level 1 — bag-of-words: normalize each description (lowercase, strip
            punctuation, drop stopwords, singularize, unique+sort tokens) and
            collapse rows whose token *set* is identical.
  Level 2 — edit distance: sort the surviving signatures and, within a sliding
            window of near neighbours, merge pairs that are still near-duplicates
            (high token Jaccard, or small normalized Levenshtein distance).

For each duplicate cluster the "best" row is kept (has calories, has macros,
shortest/cleanest description). Backs up the full table first, deletes the
losers from the base table, and rebuilds the FTS index. Idempotent.
"""
import csv
import pathlib
import re
import sqlite3
import sys
from datetime import date

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app import create_app
import app.db as adb

create_app()
DB = adb._DB_PATH
TABLE = "health_fitness_tracking_foods"
FTS = "fts_health_fitness_tracking_foods"

STOP = {"the", "a", "an", "of", "with", "and", "in", "for", "to", "by", "or",
        "ns", "as", "w", "wo", "on", "at"}
WORD = re.compile(r"[a-z0-9]+")


def singular(t):
    if len(t) <= 3:
        return t
    if t.endswith("ies"):
        return t[:-3] + "y"
    if t.endswith(("ses", "xes", "zes", "ches", "shes")):
        return t[:-2]
    if t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    return t


def tokens(desc):
    toks = [singular(t) for t in WORD.findall((desc or "").lower())]
    toks = [t for t in toks if t and t not in STOP]
    return tuple(sorted(set(toks)))


def lev(a, b):
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if abs(la - lb) > 6:            # too different to be a near-dup
        return max(la, lb)
    prev = list(range(lb + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * lb
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
        prev = cur
    return prev[lb]


def jaccard(a, b):
    sa, sb = set(a), set(b)
    u = sa | sb
    return len(sa & sb) / len(u) if u else 0.0


def score(row):
    """Higher is a better representative: has cal, has macros, shorter desc."""
    cal = row["calories"] or 0
    macros = (row["protein"] or 0) + (row["carbs"] or 0) + (row["fat"] or 0)
    return (1 if cal > 0 else 0, 1 if macros > 0 else 0,
            -len(row["description"] or ""), -row["fdc_id"])


def main():
    conn = sqlite3.connect(DB, timeout=120)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    rows = cur.execute(
        "SELECT fdc_id, description, category, calories, protein, fat, carbs, fiber, "
        "sodium, serving_size FROM " + TABLE).fetchall()
    n0 = len(rows)
    print(f"Loaded {n0} foods.")

    # --- backup ---
    bdir = ROOT / "data" / "backups"
    bdir.mkdir(parents=True, exist_ok=True)
    bpath = bdir / f"hft-foods-backup-{date(2026, 8, 2).isoformat()}.csv"
    with open(bpath, "w", newline="") as fh:
        wri = csv.writer(fh)
        wri.writerow(rows[0].keys())
        wri.writerows([tuple(r) for r in rows])
    print(f"Backed up full table -> {bpath}")

    # --- Level 1: bag-of-words exact collapse ---
    groups = {}
    for r in rows:
        groups.setdefault(tokens(r["description"]), []).append(r)
    reps = []                      # one representative per token-set group
    l1_removed = 0
    for key, grp in groups.items():
        best = max(grp, key=score)
        reps.append((key, best))
        l1_removed += len(grp) - 1
    print(f"Level 1 (bag-of-words): {len(reps)} unique token-sets "
          f"({l1_removed} exact duplicates collapsed).")

    # --- Level 2: sorted-neighbourhood edit-distance merge ---
    reps.sort(key=lambda kv: " ".join(kv[0]))
    parent = list(range(len(reps)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    sigs = [" ".join(k) for k, _ in reps]
    W = 12
    for i in range(len(reps)):
        ti = reps[i][0]
        for j in range(i + 1, min(i + 1 + W, len(reps))):
            tj = reps[j][0]
            jac = jaccard(ti, tj)
            if jac >= 0.80:
                union(i, j)
            elif jac >= 0.55:                       # borderline -> edit-distance check
                m = max(len(sigs[i]), len(sigs[j]))
                if m and 1 - lev(sigs[i], sigs[j]) / m >= 0.86:
                    union(i, j)

    clusters = {}
    for idx in range(len(reps)):
        clusters.setdefault(find(idx), []).append(idx)

    keep_ids = set()
    l2_removed = 0
    samples = []
    for members in clusters.values():
        best_idx = max(members, key=lambda idx: score(reps[idx][1]))
        keep_ids.add(reps[best_idx][1]["fdc_id"])
        if len(members) > 1:
            l2_removed += len(members) - 1
            if len(samples) < 12:
                samples.append([reps[m][1]["description"] for m in members])
    print(f"Level 2 (edit distance): merged {l2_removed} more near-duplicates.")

    keep = len(keep_ids)
    remove_ids = [r["fdc_id"] for r in rows if r["fdc_id"] not in keep_ids]
    print(f"\nKeeping {keep} foods; removing {len(remove_ids)} duplicates "
          f"({100*len(remove_ids)/n0:.1f}% of the table).")
    print("\nSample merged clusters (kept one of each):")
    for s in samples:
        print("  •", " | ".join(x[:38] for x in s[:4]))

    # --- delete + rebuild FTS ---
    for k in range(0, len(remove_ids), 5000):
        chunk = remove_ids[k:k + 5000]
        cur.execute(f"DELETE FROM {TABLE} WHERE fdc_id IN ({','.join('?'*len(chunk))})", chunk)
    conn.commit()
    try:
        cur.execute(f"INSERT INTO {FTS}({FTS}) VALUES('rebuild')")
        conn.commit()
    except sqlite3.Error as e:
        print("  (foods FTS rebuild note:", e, ")")
    final = cur.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0]
    conn.close()
    print(f"\nDone. foods table: {n0} -> {final} rows. FTS rebuilt.")


if __name__ == "__main__":
    main()
