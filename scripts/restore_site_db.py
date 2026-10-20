"""Rebuild the MiniWeb site database (SQLite) and the sites' static images from the Hugging Face release
(site_db/, written by scripts/export_site_db.py). Run it once before serving the sites. The server reads data/miniweb.db,
data/static/ and data/media/ by default; if you write them elsewhere (--db, --static, --media), set MINIWEB_DB,
MINIWEB_DATA_STATIC and MINIWEB_MEDIA_DIR to match (.env.example).

    python scripts/restore_site_db.py                                  # downloads site_db/ from the Hub
    python scripts/restore_site_db.py --src path/to/site_db            # a local copy

The app creates its session tables itself on first start.
"""
import argparse, glob, json, os, re, sqlite3

import pyarrow.parquet as pq

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPO = "miniweb/MiniWeb"


def insert(con, table, path):
    pf = pq.ParquetFile(path)
    cols = pf.schema_arrow.names
    sql = f'INSERT INTO "{table}" ({", ".join(f"[{c}]" for c in cols)}) VALUES ({", ".join("?" * len(cols))})'
    n = 0
    for batch in pf.iter_batches(batch_size=20000):
        data = batch.to_pydict()
        con.executemany(sql, zip(*(data[c] for c in cols)))
        n += batch.num_rows
    return n


def drop_extra(con, o, keep):
    """Remove from an external-content full-text index the rows that the original index did not hold."""
    m = re.search(r"USING\s+fts5\s*\((.*)\)\s*$", o["sql"], re.I | re.S)
    args = [x.strip() for x in m.group(1).split(",")]
    cols = [x for x in args if "=" not in x]
    opt = dict(x.split("=", 1) for x in args if "=" in x)
    base = opt["content"].strip().strip("[]'\"")
    rid = opt.get("content_rowid", "rowid").strip().strip("[]'\"")
    name = o["name"]
    have = {r for (r,) in con.execute(f'SELECT id FROM "{name}_docsize"')}
    for r in sorted(have - keep):
        vals = con.execute(f'SELECT {", ".join(f"[{c}]" for c in cols)} FROM "{base}" WHERE [{rid}] = ?', (r,)).fetchone()
        if vals is not None:
            con.execute(f'INSERT INTO "{name}"("{name}", rowid, {", ".join(f"[{c}]" for c in cols)}) '
                        f'VALUES (\'delete\', ?, {", ".join("?" * len(cols))})', (r, *vals))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", help="a local site_db/ folder (default: download it from the Hub)")
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "miniweb.db"))
    ap.add_argument("--static", default=os.path.join(ROOT, "data", "static"))
    ap.add_argument("--media", default=os.path.join(ROOT, "data", "media"),
                    help="where to unpack the sites' external media (served at /media/...; MINIWEB_MEDIA_DIR)")
    ap.add_argument("--no-media", action="store_true",
                    help="skip the 8 GB of media: pages then load those images from their original links")
    a = ap.parse_args()
    src = a.src
    if not src:
        from huggingface_hub import snapshot_download
        src = os.path.join(snapshot_download(a.repo, repo_type="dataset", allow_patterns="site_db/*",
                                             ignore_patterns="site_db/media/*" if a.no_media else None), "site_db")
    if os.path.exists(a.db):
        raise SystemExit(f"{a.db} exists; move it away first")
    schema = json.load(open(os.path.join(src, "schema.json")))
    tables = json.load(open(os.path.join(src, "tables.json")))
    con = sqlite3.connect(a.db)
    con.execute("PRAGMA journal_mode=OFF"); con.execute("PRAGMA synchronous=OFF")
    # tables, then the full-text tables and the triggers that keep them in sync, then the rows, then the indexes
    for kind, virtual in (("table", False), ("table", True), ("trigger", None)):
        for o in schema:
            if o["type"] == kind and (virtual is None or o["virtual"] == virtual):
                con.execute(o["sql"])
    for t in tables:
        n = insert(con, t["table"], os.path.join(src, t["path"]))
        assert n == t["rows"], (t["table"], n, t["rows"])
    con.commit()
    for o in schema:                                   # rebuild every full-text index from its table
        if o["type"] == "table" and o.get("rebuild"):
            try:
                con.execute(f'INSERT INTO "{o["name"]}"("{o["name"]}") VALUES (\'rebuild\')')
            except sqlite3.Error as e:
                print(f"warning: could not rebuild {o['name']}: {e} (search falls back to LIKE)")
                continue
            if o.get("rowids"):                        # keep only the rows the original index held
                keep = set(pq.read_table(os.path.join(src, o["rowids"]))["rowid"].to_pylist())
                drop_extra(con, o, keep)
    for o in schema:
        if o["type"] == "index":
            con.execute(o["sql"])
    con.commit()
    con.close()
    st = pq.read_table(os.path.join(src, "static.parquet")).to_pydict()
    for p, b in zip(st["path"], st["bytes"]):
        out = os.path.join(a.static, p)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, "wb").write(b)
    n_media = 0
    if os.path.isfile(os.path.join(src, "media_manifest.parquet")) and not a.no_media:   # the media the pages show
        os.makedirs(a.media, exist_ok=True)
        for f in sorted(glob.glob(os.path.join(src, "media", "*.parquet"))):
            for batch in pq.ParquetFile(f).iter_batches(batch_size=500, columns=["path", "bytes"]):
                for p, b in zip(batch.column("path").to_pylist(), batch.column("bytes").to_pylist()):
                    out = os.path.join(a.media, p)
                    os.makedirs(os.path.dirname(out), exist_ok=True)
                    open(out, "wb").write(b)
                    n_media += 1
        m = pq.read_table(os.path.join(src, "media_manifest.parquet")).to_pylist()
        with open(os.path.join(a.media, "manifest.jsonl"), "w") as fh:
            for row in m:
                fh.write(json.dumps({"url": row["url"], "path": row["path"], "status": row["status"],
                                     "bytes": row["bytes"], "content_type": row["content_type"]}) + "\n")
    print(f"{a.db}: {len(tables)} tables, {sum(t['rows'] for t in tables):,} rows; {len(st['path'])} static files "
          f"in {a.static}; {n_media} media files in {a.media}")


if __name__ == "__main__":
    main()
