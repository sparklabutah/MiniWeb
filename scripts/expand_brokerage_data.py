"""Expand brokerage synthetic data (options chains only).

The brokerage site sits at 4,722 total rows. The only safe expansion surface
is `brokerage_options`:

- `brokerage_tickers` must not change (task answers depend on sector market-cap
  sums, the robotics-fund extremum, and the bullish screener returning NVDA).
- `brokerage_orders` must not change for the main user (History-page min/max
  filled-price answer "(184.70, 542.80)"; "cancel any stop loss order" task).
  We add no orders at all.
- `brokerage_price_data` is keyed one-row-per-symbol (symbol PK, JSON blob),
  so extending price history would require UPDATEs (forbidden: insert-only)
  or new symbols (forbidden: no new tickers).

This script adds one further monthly expiry (2026-11-20, the third Friday of
November) to the option chains of the 30 alphabetically-first "small-chain"
underlyings (the 42-row chains that currently end at 2026-10-16). Each new
chain reuses that underlying's existing 7-strike ladder with call+put rows,
so filtered chain views grow modestly (42 -> 56 rows). No task references
options data, and no existing row is modified.

Insert-only; deterministic (seeded RNG); inserted ids recorded in
data/backups/brokerage-expansion-2026-07-20/inserted_ids.json for rollback.

Usage: ~/.conda/envs/miniweb/bin/python scripts/expand_brokerage_data.py [--dry-run]
"""
import json
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "trimmed_miniweb.db"
TODAY = "2026-07-20"
NEW_EXPIRY = "2026-11-20"  # third Friday of November 2026
N_UNDERLYINGS = 30

rng = random.Random(20260720)


def main():
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.row_factory = sqlite3.Row

    # Small-chain underlyings: currently 42 rows (3 expiries x 7 strikes x 2
    # types), latest expiry 2026-10-16. Take the first 30 alphabetically.
    unders = [r[0] for r in db.execute(
        "SELECT underlying FROM brokerage_options "
        "GROUP BY underlying HAVING COUNT(*) = 42 AND MAX(expiry) = '2026-10-16' "
        "ORDER BY underlying LIMIT ?", (N_UNDERLYINGS,))]

    next_id = db.execute("SELECT MAX(id) + 1 FROM brokerage_options").fetchone()[0]
    already = db.execute("SELECT COUNT(*) FROM brokerage_options WHERE expiry = ?",
                         (NEW_EXPIRY,)).fetchone()[0]
    if already:
        print(f"expiry {NEW_EXPIRY} already present ({already} rows); aborting")
        return

    new_rows = []
    for und in unders:
        base_price = db.execute(
            "SELECT base_price FROM brokerage_tickers WHERE symbol = ?",
            (und,)).fetchone()[0]
        # Reuse the underlying's existing strike ladder (same for all expiries).
        strikes = [r[0] for r in db.execute(
            "SELECT DISTINCT strike FROM brokerage_options "
            "WHERE underlying = ? AND expiry = '2026-10-16' ORDER BY strike",
            (und,))]
        for strike in strikes:
            intrinsic_call = max(0.0, base_price - strike)
            intrinsic_put = max(0.0, strike - base_price)
            for typ in ("call", "put"):
                intrinsic = intrinsic_call if typ == "call" else intrinsic_put
                # Longer-dated than 2026-10-16: a bit more time value, noisy
                # greeks in the same ranges the existing generator used.
                time_value = rng.uniform(0.4, 3.2) * (0.5 + base_price / 200.0)
                premium = round(max(0.05, intrinsic * rng.uniform(0.55, 1.0)
                                    + time_value), 2)
                moneyness = (base_price - strike) / max(base_price, 1e-6)
                if typ == "call":
                    delta = round(min(0.99, max(0.02, 0.5 + moneyness * 2.2
                                                + rng.uniform(-0.12, 0.12))), 2)
                else:
                    delta = round(-min(0.99, max(0.02, 0.5 - moneyness * 2.2
                                                 + rng.uniform(-0.12, 0.12))), 2)
                new_rows.append({
                    "id": next_id,
                    "underlying": und,
                    "type": typ,
                    "strike": strike,
                    "expiry": NEW_EXPIRY,
                    "premium": premium,
                    "iv": round(rng.uniform(0.16, 0.82), 2),
                    "delta": delta,
                    "gamma": round(rng.uniform(0.003, 0.045), 3),
                    "theta": round(-rng.uniform(0.025, 0.1), 3),
                    "vega": round(rng.uniform(0.09, 0.4), 3),
                    "open_interest": rng.randint(800, 16000),
                    "volume": rng.randint(200, 9000),
                })
                next_id += 1

    print(f"options: +{len(new_rows)} "
          f"({len(unders)} underlyings x 7 strikes x 2 types, expiry {NEW_EXPIRY})")
    if dry:
        for r in new_rows[:4]:
            print(" ", json.dumps(r))
        return

    bdir = ROOT / "data" / "backups" / f"brokerage-expansion-{TODAY}"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "inserted_ids.json").write_text(json.dumps(
        {"options": [r["id"] for r in new_rows]}, indent=1))

    cols = list(new_rows[0].keys())
    db.executemany(
        f"INSERT INTO brokerage_options ({', '.join(cols)}) "
        f"VALUES ({', '.join('?' * len(cols))})",
        [[r[c] for c in cols] for r in new_rows])
    # Sync the content-linked FTS index.
    db.execute("INSERT INTO fts_brokerage_options(fts_brokerage_options) "
               "VALUES('rebuild')")
    db.commit()
    print(f"inserted; rollback ids at {bdir}/inserted_ids.json")


if __name__ == "__main__":
    main()
