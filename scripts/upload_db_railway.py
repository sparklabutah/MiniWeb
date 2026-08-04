"""Upload the SQLite DB to a MiniWeb deployment via the /recovery/db endpoint.

Chunked and resumable: if the connection drops, re-run the same command and it
continues from where the server got to. The server validates the finished file
(SQLite header + readable schema) and atomically renames it over the live DB,
then restarts so all workers reopen the new file. Works even while the
deployed app's current DB is corrupt (the app boots in recovery mode).

Requires MINIWEB_RECOVERY_TOKEN to be set on the Railway service.

Usage:
  python scripts/upload_db_railway.py --url https://<app>.up.railway.app \
      --token <MINIWEB_RECOVERY_TOKEN> [--db data/trimmed_miniweb.db] [--chunk-mb 32]
"""
import argparse
import os
import sys
import time
import urllib.error
import urllib.request
import json


def api(url, token, method="GET", path="/recovery/db", body=None, timeout=300):
    req = urllib.request.Request(url.rstrip("/") + path, data=body, method=method,
                                 headers={"X-Recovery-Token": token,
                                          "Content-Type": "application/octet-stream"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True, help="Base URL of the deployment")
    ap.add_argument("--token", default=os.environ.get("MINIWEB_RECOVERY_TOKEN", ""))
    ap.add_argument("--db", default="data/trimmed_miniweb.db")
    ap.add_argument("--annotations", action="store_true",
                    help="Upload data/annotations (task dirs) instead of the DB. "
                    "Tars <annotator>/<task_id> dirs, uploads, and the server "
                    "replaces those task dirs in its ANNOTATIONS_DIR (additive; "
                    "tasks absent from the archive are untouched).")
    ap.add_argument("--annotations-dir", default="data/annotations")
    ap.add_argument("--prune", action="store_true",
                    help="With --annotations: also move remote tasks that no "
                    "longer exist locally into the server's .trash, so local "
                    "deletions propagate and deployed task counts stay true.")
    ap.add_argument("--chunk-mb", type=int, default=32)
    ap.add_argument("--no-restart", action="store_true",
                    help="Don't restart the remote app after replacing the DB")
    ap.add_argument("--fresh", action="store_true",
                    help="Discard any partial remote upload and start from 0")
    args = ap.parse_args()
    if not args.token:
        sys.exit("No token: pass --token or set MINIWEB_RECOVERY_TOKEN")

    target = "annotations" if args.annotations else "db"
    if args.annotations:
        # tar the task dirs (skip any nested 'annotations' duplicate dir)
        import tarfile
        import tempfile
        src = args.annotations_dir
        fd, tar_path = tempfile.mkstemp(suffix=".tar.gz")
        os.close(fd)
        n = 0
        manifest = []
        with tarfile.open(tar_path, "w:gz") as tf:
            for annotator in sorted(os.listdir(src)):
                adir = os.path.join(src, annotator)
                # skip files, the legacy nested 'annotations' snapshot, and
                # dot-dirs (.trash holds deleted/replaced task generations)
                if (not os.path.isdir(adir) or annotator == "annotations"
                        or annotator.startswith(".")):
                    continue
                for task_id in sorted(os.listdir(adir)):
                    tdir = os.path.join(adir, task_id)
                    if os.path.isdir(tdir):
                        tf.add(tdir, arcname=f"{annotator}/{task_id}")
                        manifest.append(f"{annotator}/{task_id}")
                        n += 1
            if args.prune:
                import io as _io
                blob = json.dumps(manifest).encode()
                info = tarfile.TarInfo("_manifest.json")
                info.size = len(blob)
                tf.addfile(info, _io.BytesIO(blob))
        print(f"packed {n} task dirs -> {tar_path} "
              f"({os.path.getsize(tar_path) / 1e6:.1f} MB)")
        args.db = tar_path

    size = os.path.getsize(args.db)
    status = api(args.url, args.token)
    key = "annotations_tmp_size" if args.annotations else "tmp_size"
    offset = 0 if args.fresh else status.get(key, 0)
    if offset > size:
        offset = 0
    print(f"remote db_healthy={status.get('db_healthy')} | local {size/1e9:.2f} GB | "
          f"resuming at {offset/1e9:.2f} GB")

    chunk = args.chunk_mb * 1024 * 1024
    t0 = time.time()
    with open(args.db, "rb") as f:
        f.seek(offset)
        while offset < size:
            data = f.read(chunk)
            for attempt in range(5):
                try:
                    r = api(args.url, args.token, "POST",
                            f"/recovery/db?offset={offset}&target={target}",
                            body=data)
                    break
                except (urllib.error.URLError, OSError) as e:
                    if attempt == 4:
                        raise
                    print(f"  retry {attempt + 1} at offset {offset}: {e}")
                    time.sleep(2 ** attempt)
                    # re-sync offset with the server after a failure
                    offset = api(args.url, args.token).get(key, offset)
                    f.seek(offset)
                    data = f.read(chunk)
            offset = r["tmp_size"]
            done = offset / size
            rate = offset / max(time.time() - t0, 1) / 1e6
            print(f"  {done * 100:5.1f}%  ({offset / 1e9:.2f} GB, {rate:.1f} MB/s)",
                  flush=True)

    if args.annotations:
        prune_q = "?prune=1" if args.prune else ""
        r = api(args.url, args.token, "POST", f"/recovery/annotations/complete{prune_q}")
        print("server:", r)
        if r.get("pruned_to_trash"):
            print(f"pruned {len(r['pruned_to_trash'])} remote tasks to server trash:")
            for t in r["pruned_to_trash"]:
                print("  -", t)
        os.unlink(args.db)
        return

    restart = "0" if args.no_restart else "1"
    r = api(args.url, args.token, "POST", f"/recovery/db/complete?restart={restart}")
    print("server:", r)
    if r.get("replaced"):
        print("DB replaced." + (" App is restarting with the new file."
                                if r.get("restarting") else ""))


if __name__ == "__main__":
    main()
