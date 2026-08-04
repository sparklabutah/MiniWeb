#!/usr/bin/env python3
"""Build FTS5 full-text search indexes on existing miniweb.db tables.

Does NOT rebuild or modify any data — only creates search indexes.
Safe to run anytime.

Usage:
    python scripts/build_fts.py
    python scripts/build_fts.py --db /path/to/miniweb.db
    python scripts/build_fts.py --force   # rebuild even if indexes exist
"""

import argparse
import os
import pathlib
import sqlite3
import time

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
DB_PATH = os.environ.get("MINIWEB_DB", str(PROJECT_ROOT / "miniweb.db"))

MIN_ROWS = 10  # skip tiny tables


def build_fts_indexes(db_path, force=False):
    conn = sqlite3.connect(db_path, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-256000")

    print(f"Building FTS5 indexes on {db_path}")
    t0 = time.time()
    fts_count = 0
    skipped = 0

    try:
        registry = conn.execute(
            "SELECT site, collection, table_name, pk_column FROM site_registry"
        ).fetchall()
    except sqlite3.OperationalError:
        print("  No site_registry found — nothing to index")
        conn.close()
        return

    for row in registry:
        table_name, pk_col = row[2], row[3]
        fts_table = f"fts_{table_name}"

        # Skip if already exists
        if not force:
            try:
                existing = conn.execute(
                    f"SELECT COUNT(*) FROM [{fts_table}]"
                ).fetchone()[0]
                if existing > 0:
                    skipped += 1
                    continue
            except sqlite3.OperationalError:
                pass

        # Get TEXT columns
        try:
            col_info = conn.execute(f"PRAGMA table_info([{table_name}])").fetchall()
        except sqlite3.OperationalError:
            continue

        text_cols = [c[1] for c in col_info
                     if "TEXT" in (c[2] or "").upper() and c[1] != pk_col]
        if not text_cols:
            continue

        try:
            row_count = conn.execute(
                f"SELECT COUNT(*) FROM [{table_name}]"
            ).fetchone()[0]
        except sqlite3.OperationalError:
            continue
        if row_count < MIN_ROWS:
            continue

        col_list = ", ".join(text_cols[:8])
        try:
            conn.execute(f"DROP TABLE IF EXISTS [{fts_table}]")
            conn.execute(
                f"CREATE VIRTUAL TABLE [{fts_table}] USING fts5("
                f"{col_list}, content=[{table_name}], content_rowid={pk_col})"
            )
            conn.execute(
                f"INSERT INTO [{fts_table}]([{fts_table}]) VALUES('rebuild')"
            )
            conn.commit()
            fts_count += 1
            print(f"  {table_name}: {row_count:,} rows, {len(text_cols)} text cols")
        except sqlite3.OperationalError as e:
            print(f"  SKIP {table_name}: {e}")

    elapsed = time.time() - t0
    print(f"\nBuilt {fts_count} FTS5 indexes, skipped {skipped} existing ({elapsed:.1f}s)")
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=DB_PATH, help=f"Database path (default: {DB_PATH})")
    parser.add_argument("--force", action="store_true", help="Rebuild existing indexes")
    args = parser.parse_args()
    build_fts_indexes(args.db, force=args.force)
