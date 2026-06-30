#!/usr/bin/env python3
"""Extract a random sample of 1M Wikipedia articles from the 95GB ZIM file.

Run on a CHPC compute node (needs RAM + fast I/O):

    # Interactive
    srun --ntasks=1 --mem=16G --time=2:00:00 --account=kmarino --partition=notchpeak \
        python scripts/extract_wiki_sample.py

    # Or batch
    sbatch --ntasks=1 --mem=16G --time=2:00:00 --account=kmarino --partition=notchpeak \
        --wrap="cd /scratch/general/vast/u1653932/projects/MiniWeb && python scripts/extract_wiki_sample.py"

Options:
    --target 1000000    # number of articles (default 1M)
    --target 100000     # smaller sample for testing
"""

import argparse
import html as html_mod
import os
import pathlib
import random
import re
import sqlite3
import time

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
DB_PATH = os.environ.get("MINIWEB_DB", str(PROJECT_ROOT / "miniweb.db"))
ZIM_PATH = "/scratch/general/vast/u1653932/data_sources/wiki/wikipedia_en_all_maxi_2022-05.zim"
BATCH_SIZE = 5000


def strip_html(h):
    """Strip HTML to clean readable text."""
    t = re.sub(r'<script[^>]*>.*?</script>', '', h, flags=re.DOTALL)
    t = re.sub(r'<style[^>]*>.*?</style>', '', t, flags=re.DOTALL)
    t = re.sub(r'<br\s*/?>', '\n', t)
    t = re.sub(r'<p[^>]*>', '\n', t)
    t = re.sub(r'<h[1-6][^>]*>', '\n## ', t)
    t = re.sub(r'</h[1-6]>', '\n', t)
    t = re.sub(r'<li[^>]*>', '\n• ', t)
    t = re.sub(r'<[^>]+>', '', t)
    t = re.sub(r'\n\s*\n\s*\n', '\n\n', t)
    t = re.sub(r'  +', ' ', t)
    return html_mod.unescape(t).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", type=int, default=1_000_000,
                        help="Number of articles to extract (default: 1,000,000)")
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--zim", default=ZIM_PATH)
    parser.add_argument("--max-len", type=int, default=5000,
                        help="Max chars per article (default: 5000)")
    parser.add_argument("--min-len", type=int, default=200,
                        help="Min chars per article (default: 200)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    t0 = time.time()

    print(f"Opening ZIM: {args.zim}")
    print(f"Target: {args.target:,} articles")
    print(f"DB: {args.db}")

    from libzim.reader import Archive
    zim = Archive(args.zim)
    total = zim.entry_count
    print(f"ZIM has {total:,} entries ({time.time()-t0:.0f}s)")

    # Oversample 3x, sort for sequential I/O
    sample_n = min(args.target * 3, total)
    print(f"Generating {sample_n:,} random indices...")
    indices = sorted(random.sample(range(total), sample_n))
    print(f"Indices ready ({time.time()-t0:.0f}s)")

    conn = sqlite3.connect(args.db, timeout=120)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-512000")  # 512MB cache

    conn.execute("DELETE FROM wikis_articles")
    conn.commit()
    print("Cleared old articles, starting extraction...")

    count = 0
    batch = []
    seen = set()
    skipped = 0

    for idx in indices:
        if count >= args.target:
            break
        try:
            entry = zim._get_entry_by_id(idx)
            if not entry.path.startswith('A/'):
                skipped += 1
                continue

            title = entry.title
            if not title or title in seen or '(disambiguation)' in title:
                skipped += 1
                continue

            content_bytes = bytes(entry.get_item().content)
            try:
                html_content = content_bytes.decode('utf-8')
            except (UnicodeDecodeError, ValueError):
                skipped += 1
                continue

            if '<html' not in html_content[:500]:
                skipped += 1
                continue

            text = strip_html(html_content)
            if len(text) < args.min_len:
                skipped += 1
                continue
            if len(text) > args.max_len:
                text = text[:args.max_len]

            seen.add(title)
            count += 1
            batch.append((count, title, entry.path.replace('A/', ''), text))

            if len(batch) >= BATCH_SIZE:
                conn.executemany(
                    "INSERT INTO wikis_articles (row_id, title, path, content) VALUES (?,?,?,?)",
                    batch)
                batch.clear()
                conn.commit()

                elapsed = time.time() - t0
                rate = count / elapsed
                eta = (args.target - count) / rate if rate > 0 else 0
                print(f"  {count:,} / {args.target:,} "
                      f"({elapsed:.0f}s, {rate:.0f}/s, ETA {eta/60:.0f}min, "
                      f"skip {skipped:,})", flush=True)

        except Exception:
            skipped += 1

    if batch:
        conn.executemany(
            "INSERT INTO wikis_articles (row_id, title, path, content) VALUES (?,?,?,?)",
            batch)
    conn.commit()

    elapsed = time.time() - t0
    print(f"\n=== Extracted {count:,} articles in {elapsed:.0f}s ({elapsed/60:.1f}min) ===")
    print(f"Skipped: {skipped:,}")

    # Rebuild FTS
    print("Rebuilding FTS index (this may take a few minutes)...")
    ft0 = time.time()
    conn.execute("DROP TABLE IF EXISTS fts_wikis_articles")
    conn.execute("""CREATE VIRTUAL TABLE fts_wikis_articles
        USING fts5(title, content, content=wikis_articles, content_rowid=row_id)""")
    conn.execute("INSERT INTO fts_wikis_articles(fts_wikis_articles) VALUES('rebuild')")
    conn.commit()
    print(f"FTS rebuilt in {time.time()-ft0:.0f}s")

    # Stats
    print("\nLetter distribution (top 15):")
    for r in conn.execute("""
        SELECT UPPER(SUBSTR(title,1,1)) as ch, COUNT(*) as c
        FROM wikis_articles GROUP BY ch ORDER BY c DESC LIMIT 15
    """).fetchall():
        print(f"  {r[0]}: {r[1]:,}")

    print("\nRandom sample titles:")
    for r in conn.execute("SELECT title FROM wikis_articles ORDER BY RANDOM() LIMIT 15").fetchall():
        print(f"  {r[0]}")

    print(f"\nDB size: {os.path.getsize(args.db) / 1024**3:.2f} GB")
    conn.close()


if __name__ == "__main__":
    main()
