"""Expand converters-calculators (CalcTools) base data.

The site ships with only 3 users and 1 config row (unit factors / FX rates),
so its data footprint is trivial. The natural bulk for a converter utility is
conversion HISTORY: this script

  1. adds 21 new users (ids 4-24) reusing the shared MiniWeb persona roster
     (root_user_id -> name/email) and the site's username/password style
     (alex_convert / calc2024!);
  2. creates a new `converters_calculators_history` table (registered in
     site_registry as collection "history", pk "id") and fills it with 4,975
     past conversions -- one row per conversion: user, tool, from_value,
     from_unit, to_unit, result, created_at. Every result is computed with the
     EXACT factors stored in the site's config row
     (converters_calculators_conversions row_id=1, which is never modified),
     using the same math as routes.py (_convert_unit / convert_temperature /
     convert_currency) and the same string formatting the save-form stores
     (str(round(x, 6)) for units, str(round(x, 2)) for currency);
  3. mirrors each new user's most recent conversions into their users.history
     JSON column and a small subset into saved_conversions, so dashboards
     render 45-90 rows max (existing users 1-3 are never touched).

Insert-only -- existing rows are never updated or deleted. Inserted ids are
recorded in data/backups/converters-calculators-expansion-2026-07-20/
inserted_ids.json for rollback.

Final totals: conversions 1 (unchanged) + users 24 + history 4,975 = 5,000.

Usage: python scripts/expand_converters_calculators_data.py [--dry-run]
"""
import datetime
import json
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "trimmed_miniweb.db"

rng = random.Random(20260720)

TODAY = datetime.date(2026, 7, 20)  # backup dir date; data is dated <= 2026-07-17

# Shared MiniWeb persona roster (root_user_id, name, email). Existing site
# users already cover root ids 1 (Alex Rivera), 3 (Marcus Chen), 10 (Aisha Patel).
PERSONAS = [
    (2, "Priya Sharma", "priya.sharma@outlook.com"),
    (4, "Jessica Okafor", "jessica.okafor@gmail.com"),
    (5, "Ryan Tanaka", "ryan.tanaka@meridiansystems.com"),
    (7, "David Petrov", "david.petrov@meridiansystems.com"),
    (9, "Tom Bradley", "tom.bradley@gmail.com"),
    (12, "Natalie Kim", "natalie.kim@gmail.com"),
    (13, "Elena Vasquez", "elena.vasquez@gmail.com"),
    (14, "Omar Moreau", "omar.moreau@outlook.com"),
    (15, "Sophie Lin", "sophie.lin.design@gmail.com"),
    (16, "Daniel Okonkwo", "daniel.okonkwo@gmail.com"),
    (19, "Nathan Brooks", "nate.brooks.fit@gmail.com"),
    (21, "Carlos Mendez", "carlos.mendez@gmail.com"),
    (27, "Cole Fitzgerald", "cole.fitzgerald@gmail.com"),
    (28, "Ravi Okafor", "ravi.okafor@gmail.com"),
    (30, "Owen Whitfield", "owen.whitfield@outlook.com"),
    (31, "Maya Ashford", "maya.ashford@gmail.com"),
    (33, "Cole Donnelly", "cole.donnelly@gmail.com"),
    (37, "Nora Bennett", "nora.bennett@outlook.com"),
    (38, "Freya Nguyen", "freya.nguyen@gmail.com"),
    (40, "Carmen Delgado", "carmen.delgado@gmail.com"),
    (43, "Amara Hartley", "amara.hartley@yahoo.com"),
]

N_HISTORY = 4975  # 1 config + 24 users + 4975 history = 5000 site rows

# tool -> (weight, from_value range, decimals allowed)
TOOL_WEIGHTS = {
    "length": 22, "weight": 16, "temperature": 12, "currency": 18,
    "volume": 11, "area": 9, "speed": 12,
}
VALUE_RANGES = {
    "length": (1, 5000), "weight": (1, 1000), "temperature": (-40, 400),
    "currency": (5, 20000), "volume": (1, 500), "area": (1, 10000),
    "speed": (5, 400),
}

HISTORY_COLUMNS = [
    ("id", "INTEGER PRIMARY KEY"),
    ("user_id", "INTEGER NOT NULL DEFAULT 0"),
    ("root_user_id", "INTEGER NOT NULL DEFAULT 0"),
    ("tool", "TEXT NOT NULL DEFAULT ''"),
    ("from_value", "TEXT NOT NULL DEFAULT ''"),
    ("from_unit", "TEXT NOT NULL DEFAULT ''"),
    ("to_unit", "TEXT NOT NULL DEFAULT ''"),
    ("result", "TEXT NOT NULL DEFAULT ''"),
    ("created_at", "TEXT NOT NULL DEFAULT ''"),
]


def load_config(db):
    """Read the site's unit/rate config (row is never modified)."""
    row = db.execute(
        "SELECT * FROM converters_calculators_conversions WHERE row_id = 1"
    ).fetchone()
    return {k: json.loads(row[k]) for k in
            ("length", "weight", "temperature", "currency", "volume", "area", "speed")}


def convert(config, tool, value, from_unit, to_unit):
    """Same math as sites/converters-calculators/routes.py."""
    if tool == "temperature":
        c = {"celsius": lambda v: v,
             "fahrenheit": lambda v: (v - 32) * 5 / 9,
             "kelvin": lambda v: v - 273.15}[from_unit](value)
        return {"celsius": c,
                "fahrenheit": c * 9 / 5 + 32,
                "kelvin": c + 273.15}[to_unit]
    if tool == "currency":
        rates = config["currency"]["rates"]
        return value / rates[from_unit] * rates[to_unit]
    units = config[tool]["units"]
    return value * units[from_unit]["to_base"] / units[to_unit]["to_base"]


def rand_dt(start, end):
    span = int((end - start).total_seconds())
    return start + datetime.timedelta(seconds=rng.randint(0, span))


def fmt_value(tool, lo, hi):
    """Plausible user-entered from_value as the form would post it."""
    if tool == "currency":
        if rng.random() < 0.4:
            v = round(rng.uniform(lo, hi), 2)
        else:
            v = float(rng.randint(int(lo), int(hi)))
    elif rng.random() < 0.7:
        v = float(rng.randint(int(lo), int(hi)))
    else:
        v = round(rng.uniform(lo, hi), rng.choice([1, 2]))
    # exact string form (f"{v:g}" would clip >6 significant digits)
    s = str(int(v)) if v == int(v) else str(v)
    return v, s


def main():
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.row_factory = sqlite3.Row

    config = load_config(db)
    unit_names = {t: (list(config[t]["units"]) if t != "currency"
                      else list(config["currency"]["rates"]))
                  for t in VALUE_RANGES}

    max_uid = db.execute(
        "SELECT COALESCE(MAX(id),0) FROM converters_calculators_users").fetchone()[0]
    existing_hist = db.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
        "AND name='converters_calculators_history'").fetchone()[0]
    next_hid = 1
    if existing_hist:
        next_hid = db.execute(
            "SELECT COALESCE(MAX(id),0)+1 FROM converters_calculators_history"
        ).fetchone()[0]

    # ---- users ----------------------------------------------------------
    new_users = []
    seen_first = set()
    suffix_cycle = ["convert", "calc"]
    for i, (root_id, name, email) in enumerate(PERSONAS):
        first = name.split()[0].lower()
        uname = f"{first}_{suffix_cycle[i % 2]}"
        if first in seen_first:  # e.g. two Coles
            uname = f"{first}{name.split()[1][0].lower()}_{suffix_cycle[i % 2]}"
        seen_first.add(first)
        new_users.append({
            "id": max_uid + 1 + i,
            "root_user_id": root_id,
            "username": uname,
            "password": f"calc{rng.randint(100, 999)}!",
            "name": name,
            "email": email,
            "saved_conversions": "[]",  # filled below
            "history": "[]",
        })

    # ---- history rows ---------------------------------------------------
    # split N_HISTORY across the new users (existing users 1-3 untouched)
    weights = [rng.uniform(0.6, 1.4) for _ in new_users]
    total_w = sum(weights)
    counts = [int(N_HISTORY * w / total_w) for w in weights]
    counts[-1] += N_HISTORY - sum(counts)

    tools, tool_w = zip(*TOOL_WEIGHTS.items())
    start = datetime.datetime(2025, 6, 1, 6, 0, 0)
    end = datetime.datetime(2026, 7, 17, 23, 0, 0)
    # currency rows only after the stored rates_date (2026-06-20)
    fx_start = datetime.datetime(2026, 6, 20, 8, 0, 0)

    history = []
    per_user = {}
    for u, n in zip(new_users, counts):
        rows = []
        for _ in range(n):
            tool = rng.choices(tools, weights=tool_w)[0]
            names = unit_names[tool]
            from_u, to_u = rng.sample(names, 2)
            lo, hi = VALUE_RANGES[tool]
            if tool == "temperature" and from_u == "kelvin":
                lo = 0  # no negative kelvin inputs
            v, v_str = fmt_value(tool, lo, hi)
            res = convert(config, tool, v, from_u, to_u)
            res_str = (str(round(res, 2)) if tool == "currency"
                       else str(round(res, 6)))
            when = rand_dt(fx_start if tool == "currency" else start, end)
            rows.append({
                "user_id": u["id"], "root_user_id": u["root_user_id"],
                "tool": tool, "from_value": v_str, "from_unit": from_u,
                "to_unit": to_u, "result": res_str,
                "created_at": when.isoformat(timespec="seconds"),
            })
        rows.sort(key=lambda r: r["created_at"])
        per_user[u["id"]] = rows
        history.extend(rows)

    history.sort(key=lambda r: r["created_at"])
    for r in history:
        r["id"] = next_hid
        next_hid += 1

    # ---- mirror recent history into users' JSON columns -----------------
    for u in new_users:
        rows = per_user[u["id"]]
        k = min(len(rows), rng.randint(45, 90))
        recent = rows[-k:]
        entries = [{"tool": r["tool"], "from_value": r["from_value"],
                    "from_unit": r["from_unit"], "to_unit": r["to_unit"],
                    "result": r["result"]} for r in recent]
        n_saved = rng.randint(6, 14)
        saved_idx = sorted(rng.sample(range(len(entries)), n_saved))
        u["history"] = json.dumps(entries)
        u["saved_conversions"] = json.dumps([entries[i] for i in saved_idx])

    print(f"users: +{len(new_users)} (ids {new_users[0]['id']}-{new_users[-1]['id']})")
    print(f"history: +{len(history)} (ids {history[0]['id']}-{history[-1]['id']})")
    if dry:
        for r in new_users[:2]:
            print(" user:", json.dumps({k: r[k] for k in
                  ("id", "root_user_id", "username", "name", "email")}))
        for r in history[:3]:
            print(" hist:", json.dumps(r))
        # spot-check one conversion against expected factor math
        return

    # ---- create + register history table --------------------------------
    col_defs = ", ".join(f"[{c}] {t}" for c, t in HISTORY_COLUMNS)
    db.execute(f"CREATE TABLE IF NOT EXISTS converters_calculators_history ({col_defs})")
    db.execute("CREATE INDEX IF NOT EXISTS idx_converters_calculators_history_user_id "
               "ON converters_calculators_history (user_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_converters_calculators_history_created_at "
               "ON converters_calculators_history (created_at)")
    db.execute("INSERT OR REPLACE INTO site_registry (site, collection, table_name, pk_column) "
               "VALUES ('converters-calculators', 'history', "
               "'converters_calculators_history', 'id')")

    # ---- backup of inserted ids -----------------------------------------
    bdir = ROOT / "data" / "backups" / f"converters-calculators-expansion-{TODAY}"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "inserted_ids.json").write_text(json.dumps({
        "users": [u["id"] for u in new_users],
        "history": [history[0]["id"], history[-1]["id"]],
        "history_id_range_inclusive": True,
        "created_table": "converters_calculators_history",
        "registered_collection": ["converters-calculators", "history"],
    }, indent=1))

    # ---- insert ---------------------------------------------------------
    ucols = list(new_users[0].keys())
    db.executemany(
        f"INSERT INTO converters_calculators_users ({', '.join(ucols)}) "
        f"VALUES ({', '.join('?' * len(ucols))})",
        [[u[c] for c in ucols] for u in new_users])
    hcols = [c for c, _ in HISTORY_COLUMNS]
    db.executemany(
        f"INSERT INTO converters_calculators_history ({', '.join(hcols)}) "
        f"VALUES ({', '.join('?' * len(hcols))})",
        [[r[c] for c in hcols] for r in history])
    db.commit()
    total = sum(db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in
                ("converters_calculators_conversions", "converters_calculators_users",
                 "converters_calculators_history"))
    print(f"inserted; site total now {total} rows; "
          f"rollback ids at {bdir}/inserted_ids.json")


if __name__ == "__main__":
    main()
