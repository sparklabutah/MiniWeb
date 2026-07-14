"""Resample wikis_articles with clean, real Wikipedia content.

WHY: the existing 50,000 rows are the alphabetically-first entries of the
ZIM dump — 93.7% are year/date stubs ("1925-26 Allsvenskan"), the rest are
punctuation titles ("!!", "!!!"). No article starts with a letter. Content
also carries ZIM nav-bar debris ("• \n • \n ## ") and mid-markup truncation.
That is why the site reads as nonsense.

WHAT: fetch a proper random sample via the Wikipedia API (plain-text
extracts, no HTML), filtered for quality, into a NEW table
wikis_articles_clean, then swap it in. The old table is kept as
wikis_articles_zim so nothing is destroyed.

Quality filters: namespace 0 only, no disambiguation/list/index pages,
>= MIN_CHARS of prose, has a real intro sentence.

Usage:
    python scripts/resample_wiki_articles.py --target 20000
    python scripts/resample_wiki_articles.py --target 500 --dry-run
"""
import argparse
import json
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request

API = "https://en.wikipedia.org/w/api.php"
UA = "MiniWeb-Research/1.0 (dataset for agent benchmark; contact: mhpham26@colby.edu)"
MIN_CHARS = 400
BATCH = 20          # titles per API call (extracts cap at 20)


def api_get(params):
    params = {**params, "format": "json", "formatversion": "2"}
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read())
        except Exception as e:
            if attempt == 3:
                raise
            time.sleep(1.5 * (attempt + 1))
    return {}


BAD_TITLE = re.compile(
    r"\(disambiguation\)|^List of |^Index of |^Timeline of |^Outline of |"
    r"^Glossary of |\(surname\)|\(given name\)|^\d{3,4}(–\d{2,4})? ", re.I)


def is_good(title, extract):
    if not extract or len(extract) < MIN_CHARS:
        return False
    if BAD_TITLE.search(title):
        return False
    low = extract.lower()
    if "may refer to" in low[:400] or "commonly refers to" in low[:400]:
        return False
    # needs real prose: at least a few sentences
    if extract.count(". ") < 2:
        return False
    return True


def clean(text):
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    # drop empty section headers left by the API
    text = re.sub(r"\n==+ *[^=\n]* *==+\n(?=\n*==)", "\n", text)
    return text.strip()


def fetch_random_batch(n):
    """Random articles with plain-text extracts."""
    data = api_get({
        "action": "query",
        "generator": "random",
        "grnnamespace": 0,
        "grnlimit": n,
        "prop": "extracts",
        "explaintext": 1,
        "exsectionformat": "plain",
        # The API caps exlimit at 1 for FULL-text extracts, so batches would
        # return one article per call. exintro lifts the cap to 20/call, and
        # intro sections are exactly what we want: clean, self-contained prose.
        "exintro": 1,
        "exlimit": "max",
    })
    out = []
    for p in data.get("query", {}).get("pages", []):
        title = p.get("title", "")
        extract = clean(p.get("extract") or "")
        if is_good(title, extract):
            out.append((title, extract))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/trimmed_miniweb.db")
    ap.add_argument("--target", type=int, default=20000)
    ap.add_argument("--delay", type=float, default=0.15)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db = sqlite3.connect(args.db, timeout=120)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS wikis_articles_clean
                  (row_id INTEGER PRIMARY KEY, title TEXT, path TEXT, content TEXT)""")
    have = {r[0] for r in db.execute("SELECT title FROM wikis_articles_clean")}
    print(f"already have {len(have)} clean articles; target {args.target}")

    t0 = time.time()
    kept = len(have)
    rows = []
    while kept < args.target:
        try:
            batch = fetch_random_batch(BATCH)
        except Exception as e:
            print("  api error, backing off:", str(e)[:80])
            time.sleep(5)
            continue
        for title, extract in batch:
            if title in have:
                continue
            have.add(title)
            kept += 1
            rows.append((title, "A/" + title.replace(" ", "_"), extract))
        if len(rows) >= 200:
            if not args.dry_run:
                db.executemany(
                    "INSERT INTO wikis_articles_clean (title, path, content) VALUES (?,?,?)", rows)
                db.commit()
            rows = []
            rate = kept / max(1, time.time() - t0)
            eta = (args.target - kept) / max(rate, 0.01) / 60
            print(f"  {kept:,}/{args.target:,} kept  ({rate:.1f}/s, ETA {eta:.0f}m)")
        time.sleep(args.delay)

    if rows and not args.dry_run:
        db.executemany("INSERT INTO wikis_articles_clean (title, path, content) VALUES (?,?,?)", rows)
        db.commit()

    n = db.execute("SELECT COUNT(*) FROM wikis_articles_clean").fetchone()[0]
    print(f"done: {n:,} clean articles in {(time.time()-t0)/60:.1f} min")
    if args.dry_run:
        print("(dry run — nothing written)")
        return

    # sanity sample
    for r in db.execute("SELECT title, SUBSTR(content,1,90) FROM wikis_articles_clean LIMIT 3"):
        print("  •", r[0], "—", r[1].replace("\n", " "))
    print("\nNOT swapped yet. To activate:")
    print("  python scripts/resample_wiki_articles.py --swap")


def swap(db_path):
    """Point the site at the clean table; keep the old one as _zim."""
    db = sqlite3.connect(db_path, timeout=120)
    n = db.execute("SELECT COUNT(*) FROM wikis_articles_clean").fetchone()[0]
    if n < 100:
        print("refusing to swap: clean table too small")
        return
    db.execute("ALTER TABLE wikis_articles RENAME TO wikis_articles_zim")
    db.execute("ALTER TABLE wikis_articles_clean RENAME TO wikis_articles")
    db.commit()
    print(f"swapped: wikis_articles now has {n:,} clean articles "
          f"(old corpus preserved as wikis_articles_zim)")


if __name__ == "__main__":
    if "--swap" in sys.argv:
        swap("data/trimmed_miniweb.db")
    else:
        main()
