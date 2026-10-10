"""Export the site database to Parquet for the Hugging Face release: one file per table of the 65 sites, the schema,
and the sites' static images. scripts/restore_site_db.py rebuilds the SQLite database from them.

Left out: session state (session_overlay, session_collection_replaced, sessions, event_log, which hold the writes of
every evaluation episode), the full-text indexes and the shadow tables SQLite keeps for them (rebuilt on restore),
and the tables of retired sites that are not among the 65.

    python scripts/export_site_db.py --db $MINIWEB_DB --static data/static --out data/release/miniweb-v1-hf/site_db
"""
import argparse, json, os, re, sqlite3

import pyarrow as pa
import pyarrow.parquet as pq
import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SHADOW = ("_data", "_idx", "_content", "_docsize", "_config")
BATCH = 20000


def arrow_type(decl):
    """SQLite affinity of a declared type -> an Arrow type (column affinity rules, sqlite.org/datatype3.html)."""
    d = (decl or "").upper()
    if "INT" in d:
        return pa.int64()
    if any(k in d for k in ("CHAR", "CLOB", "TEXT")):
        return pa.string()
    if "BLOB" in d or not d:
        return None                                      # decided from the values
    if any(k in d for k in ("REAL", "FLOA", "DOUB")):
        return pa.float64()
    return None                                          # NUMERIC: decided from the values


def export_table(con, table, path):
    cols = con.execute(f'PRAGMA table_info("{table}")').fetchall()
    names = [c[1] for c in cols]
    types = {c[1]: arrow_type(c[2]) for c in cols}
    # a column whose stored values do not all fit its declared type (SQLite is dynamically typed) becomes text, or
    # binary if it holds blobs; untyped columns take the type of their values
    for n in names:
        kinds = {k for (k,) in con.execute(f'SELECT DISTINCT typeof("{n}") FROM "{table}"')} - {"null"}
        want = types[n]
        if "blob" in kinds:
            types[n] = pa.binary() if kinds == {"blob"} else pa.string()
        elif want is None or (want == pa.int64() and kinds - {"integer"}) or \
                (want == pa.float64() and kinds - {"real", "integer"}):
            types[n] = pa.int64() if kinds == {"integer"} else pa.float64() if kinds <= {"real", "integer"} and kinds \
                else pa.string()
    schema = pa.schema([(n, types[n]) for n in names])
    cast = {n: (str if types[n] == pa.string() else None) for n in names}
    cur = con.execute(f'SELECT * FROM "{table}"')
    writer, rows = pq.ParquetWriter(path, schema, compression="zstd"), 0
    while True:
        chunk = cur.fetchmany(BATCH)
        if not chunk:
            break
        data = {n: [None if r[i] is None else (cast[n](r[i]) if cast[n] else r[i]) for r in chunk]
                for i, n in enumerate(names)}
        writer.write_table(pa.table(data, schema=schema))
        rows += len(chunk)
    if rows == 0:
        writer.write_table(pa.table({n: [] for n in names}, schema=schema))
    writer.close()
    return rows


def export_media(media_dir, out, shard_mb=480):
    """The local copy of the sites' external media (scripts/fetch_site_media.py): Parquet shards of (url, path,
    content_type, bytes) under media/, and the manifest of every URL tried (status included) as media_manifest.parquet."""
    rows = [json.loads(line) for line in open(os.path.join(media_dir, "manifest.jsonl"))]
    pq.write_table(pa.table({k: [r.get(k) for r in rows] for k in ("url", "path", "bytes", "content_type")} |
                            {"status": [str(r.get("status")) for r in rows]}),
                   os.path.join(out, "media_manifest.parquet"))
    have = [r for r in rows if r.get("path") and os.path.isfile(os.path.join(media_dir, r["path"]))]
    os.makedirs(os.path.join(out, "media"), exist_ok=True)
    schema = pa.schema([("url", pa.string()), ("path", pa.string()), ("content_type", pa.string()), ("bytes", pa.binary())])
    shard, size, buf, files = 0, 0, [], 0
    def flush():
        nonlocal shard, size, buf
        if buf:
            pq.write_table(pa.Table.from_pylist(buf, schema=schema),
                           os.path.join(out, "media", f"media-{shard:05d}.parquet"), compression="zstd")
            shard, size, buf = shard + 1, 0, []
    for r in have:
        data = open(os.path.join(media_dir, r["path"]), "rb").read()
        buf.append({"url": r["url"], "path": r["path"], "content_type": r.get("content_type"), "bytes": data})
        size += len(data); files += 1
        if size > shard_mb * 2 ** 20:
            flush()
    flush()
    print(f"media: {files} files in {shard} shards; manifest of {len(rows)} URLs")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.environ.get("MINIWEB_DB"))
    ap.add_argument("--static", default=os.path.join(ROOT, "data", "static"))
    ap.add_argument("--sites", default=os.path.join(ROOT, "data", "sites.yaml"))
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "release", "miniweb-v1-hf", "site_db"))
    ap.add_argument("--media", default=os.path.join(ROOT, "data", "media"),
                    help="the local media copy to pack (scripts/fetch_site_media.py); skipped if absent")
    ap.add_argument("--media-only", action="store_true")
    a = ap.parse_args()
    if a.media_only:
        export_media(a.media, a.out)
        return
    con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    sites = [s["id"] for s in yaml.safe_load(open(a.sites))["sites"]]
    prefixes = sorted(((s, s.replace("-", "_") + "_") for s in sites), key=lambda kv: -len(kv[1]))
    owner = lambda t: next((s for s, p in prefixes if t.startswith(p)), None)  # noqa: E731
    master = con.execute("SELECT type, name, tbl_name, sql FROM sqlite_master WHERE sql IS NOT NULL").fetchall()
    virtual = {n for t, n, _, s in master if t == "table" and s.upper().startswith("CREATE VIRTUAL")}
    shadow = {v + suf for v in virtual for suf in SHADOW}
    external = {n for t, n, _, s in master if n in virtual and re.search(r"content\s*=\s*\[?\w", s, re.I)
                and not re.search(r"content\s*=\s*''", s, re.I)}
    keep = {n for t, n, _, s in master if t == "table" and n not in shadow and n != "sqlite_sequence"
            and (owner(n) or n in ("filesystem_files", "site_registry"))
            and not (n in virtual and n.startswith("fts_") and owner(n[4:]) is None)}
    keep -= {n for n in keep if n.startswith("fts_") and owner(n[4:]) is None}
    # the full-text index of a kept table is rebuilt from its table; a full-text table with its own content is exported
    fts_of_kept = {n for n in virtual if n.startswith("fts_") and owner(n[4:])}
    data_tables = sorted((keep - fts_of_kept - (external & virtual)) | {"site_registry", "filesystem_files"})
    os.makedirs(a.out, exist_ok=True)
    order = {"table": 0, "index": 1, "trigger": 2}
    schema = []
    for t, n, tbl, s in sorted(master, key=lambda r: (order.get(r[0], 3), r[1])):
        base = tbl if t in ("index", "trigger") else n
        if base in keep or base in fts_of_kept:
            if t == "table" or base not in shadow:
                schema.append({"type": t, "name": n, "table": tbl, "sql": s, "virtual": n in virtual,
                               "rebuild": n in virtual and n in external})
    # some full-text indexes were built before rows were added to their tables and never updated; record which rows
    # such an index holds, so the restore can drop the others and search behaves exactly as when the tasks were made
    for o in schema:
        if o["type"] == "table" and o["rebuild"]:
            m = re.search(r"content\s*=\s*\[?(\w+)\]?", o["sql"], re.I)
            held = [r for (r,) in con.execute(f'SELECT id FROM "{o["name"]}_docsize" ORDER BY id')]
            if len(held) != con.execute(f'SELECT COUNT(*) FROM "{m.group(1)}"').fetchone()[0]:
                path = os.path.join(a.out, "fts_rowids", f'{o["name"]}.parquet')
                os.makedirs(os.path.dirname(path), exist_ok=True)
                pq.write_table(pa.table({"rowid": pa.array(held, pa.int64())}), path)
                o["rowids"] = os.path.relpath(path, a.out)
    json.dump(schema, open(os.path.join(a.out, "schema.json"), "w"), indent=1)
    manifest = []
    for t in data_tables:
        site = owner(t) or "_shared"
        d = os.path.join(a.out, "tables", site)
        os.makedirs(d, exist_ok=True)
        if t == "site_registry":
            path = os.path.join(d, f"{t}.parquet")
            rows = [r for r in con.execute("SELECT site, collection, table_name, pk_column FROM site_registry")
                    if r[2] in keep]
            pq.write_table(pa.table({k: [r[i] for r in rows] for i, k in
                                     enumerate(("site", "collection", "table_name", "pk_column"))}), path)
            n = len(rows)
        else:
            n = export_table(con, t, os.path.join(d, f"{t}.parquet"))
        manifest.append({"table": t, "site": site, "rows": n, "path": f"tables/{site}/{t}.parquet"})
        print(f"{t}: {n}", flush=True)
    json.dump(manifest, open(os.path.join(a.out, "tables.json"), "w"), indent=1)
    # the sites' static images (generated pictures, avatars, thumbnails), served from /static/<sub>/...
    files = [os.path.join(dp, f) for dp, _, fs in os.walk(a.static) for f in fs]
    pq.write_table(pa.table({"path": [os.path.relpath(f, a.static) for f in files],
                             "bytes": [open(f, "rb").read() for f in files]}), os.path.join(a.out, "static.parquet"))
    print(f"{len(data_tables)} tables, {sum(m['rows'] for m in manifest)} rows; {len(files)} static files; "
          f"schema of {len(schema)} objects")
    if os.path.isfile(os.path.join(a.media, "manifest.jsonl")):
        export_media(a.media, a.out)


if __name__ == "__main__":
    main()
