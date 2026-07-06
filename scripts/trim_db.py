#!/usr/bin/env python3
"""Trim the MiniWeb SQLite database for deployment.

Copies the DB and caps large tables to reduce size from ~18GB to ~3-4GB.
Rebuilds FTS indexes and VACUUMs at the end.

Usage:
    python scripts/trim_db.py                          # default: ./miniweb_trimmed.db
    python scripts/trim_db.py --output /path/to/out.db
    python scripts/trim_db.py --source /path/to/src.db
"""

import argparse
import os
import shutil
import sqlite3
import sys
import time

# Tables to trim: (table_name, target_rows, order_by_for_keep)
# order_by determines which rows to keep (top N by that ordering)
TRIM_TARGETS = [
    ("qa_knowledge_questions", 100_000, "score DESC"),
    ("qa_knowledge_answers", 100_000, None),  # handled specially: keep answers for kept questions
    ("forums_posts", 50_000, "score DESC"),
    ("forums_comments", 100_000, None),  # keep for kept posts
    ("forums_reddit_users", 50_000, "karma DESC"),
    ("academic_paper_db_papers", 100_000, "update_date DESC"),
    ("flights_hotels_flights", 50_000, "RANDOM()"),
    ("flights_hotels_hotels", 50_000, "RANDOM()"),
    ("health_fitness_tracking_foods", 100_000, "RANDOM()"),
    ("job_sites_jobs", 100_000, "RANDOM()"),
    ("real_estate_buy_rent_listings_raw", 100_000, "RANDOM()"),
    ("podcasts_audiobooks_ratings_raw", 50_000, "RANDOM()"),
    ("classifieds_listings", 100_000, "RANDOM()"),
    ("comparison_aggregators_phones", 10_000, "RANDOM()"),
    ("software_marketplace_app_reviews", 20_000, "RANDOM()"),
    ("version_control_issues_raw", 30_000, "RANDOM()"),
    ("version_control_merge_requests_raw", 30_000, "RANDOM()"),
    ("version_control_notes_raw", 50_000, "RANDOM()"),
    ("wikis_articles", 50_000, "RANDOM()"),
    ("books_comics_chapters", 30_000, "RANDOM()"),
    ("podcasts_audiobooks_books_raw", 50_000, "RANDOM()"),
]


def get_count(conn, table):
    try:
        return conn.execute(f"SELECT COUNT(*) FROM [{table}]").fetchone()[0]
    except Exception:
        return 0


def trim_table(conn, table, target, order_by):
    current = get_count(conn, table)
    if current <= target:
        print(f"  {table}: {current:,} rows (already under {target:,}, skip)")
        return 0

    deleted = current - target
    print(f"  {table}: {current:,} -> {target:,} ({deleted:,} to delete)...", end=" ", flush=True)

    # Create temp table with rows to keep, then swap
    conn.execute(f"""
        CREATE TABLE _trim_temp AS
        SELECT * FROM [{table}] ORDER BY {order_by} LIMIT {target}
    """)
    conn.execute(f"DROP TABLE [{table}]")
    conn.execute(f"ALTER TABLE _trim_temp RENAME TO [{table}]")
    conn.commit()
    print("done")
    return deleted


def trim_dependent(conn, parent_table, child_table, fk_column, parent_pk="id", target=None):
    """Trim child table to only keep rows referencing existing parent rows."""
    current = get_count(conn, child_table)
    print(f"  {child_table}: {current:,} rows, trimming to match {parent_table}...", end=" ", flush=True)

    conn.execute(f"""
        CREATE TABLE _trim_temp AS
        SELECT c.* FROM [{child_table}] c
        INNER JOIN [{parent_table}] p ON c.[{fk_column}] = p.[{parent_pk}]
        {f'LIMIT {target}' if target else ''}
    """)
    conn.execute(f"DROP TABLE [{child_table}]")
    conn.execute(f"ALTER TABLE _trim_temp RENAME TO [{child_table}]")
    conn.commit()
    after = get_count(conn, child_table)
    print(f"{after:,} remaining")
    return current - after


def rebuild_fts(conn):
    """Drop and skip FTS tables — they'll be rebuilt on first search."""
    fts_tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'fts_%'"
    ).fetchall()
    dropped = 0
    for (name,) in fts_tables:
        try:
            conn.execute(f"DROP TABLE [{name}]")
            dropped += 1
        except Exception:
            pass
    conn.commit()
    print(f"  Dropped {dropped} FTS tables (will rebuild on first search)")


def clean_overlays(conn):
    """Clear session overlay data."""
    for table in ["session_overlay", "sessions"]:
        try:
            conn.execute(f"DELETE FROM [{table}]")
            print(f"  Cleared {table}")
        except Exception:
            pass
    conn.commit()


def main():
    parser = argparse.ArgumentParser(description="Trim MiniWeb database for deployment")
    parser.add_argument("--source", default=None, help="Source DB path (default: follows miniweb.db symlink)")
    parser.add_argument("--output", default="./miniweb_trimmed.db", help="Output DB path")
    args = parser.parse_args()

    # Find source DB
    source = args.source
    if not source:
        # Follow symlink
        link = os.path.join(os.path.dirname(__file__), "..", "miniweb.db")
        source = os.path.realpath(link)
    if not os.path.exists(source):
        print(f"Source DB not found: {source}")
        sys.exit(1)

    output = args.output
    source_size = os.path.getsize(source) / (1024**3)
    print(f"Source: {source} ({source_size:.1f} GB)")
    print(f"Output: {output}")

    # Copy DB
    print(f"\nCopying database...", flush=True)
    t0 = time.time()
    shutil.copy2(source, output)
    print(f"  Copied in {time.time()-t0:.0f}s")

    # Open and trim
    conn = sqlite3.connect(output)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA cache_size=-65536")

    total_deleted = 0

    print("\n--- Trimming large tables ---")
    for table, target, order_by in TRIM_TARGETS:
        if order_by is None:
            continue  # handled as dependent
        total_deleted += trim_table(conn, table, target, order_by)

    print("\n--- Trimming dependent tables ---")
    total_deleted += trim_dependent(conn, "qa_knowledge_questions", "qa_knowledge_answers",
                                     "question_id", target=100_000)
    total_deleted += trim_dependent(conn, "forums_posts", "forums_comments",
                                     "post_id", target=100_000)

    print("\n--- Cleaning up ---")
    rebuild_fts(conn)
    clean_overlays(conn)

    print("\n--- VACUUM ---")
    t0 = time.time()
    conn.execute("VACUUM")
    print(f"  VACUUM completed in {time.time()-t0:.0f}s")

    conn.close()

    output_size = os.path.getsize(output) / (1024**3)
    print(f"\nResult: {output} ({output_size:.1f} GB)")
    print(f"Reduction: {source_size:.1f} GB -> {output_size:.1f} GB ({(1-output_size/source_size)*100:.0f}% smaller)")


if __name__ == "__main__":
    main()
