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
    ap.add_argument("--chunk-mb", type=int, default=32)
    ap.add_argument("--no-restart", action="store_true",
                    help="Don't restart the remote app after replacing the DB")
    ap.add_argument("--fresh", action="store_true",
                    help="Discard any partial remote upload and start from 0")
    args = ap.parse_args()
    if not args.token:
        sys.exit("No token: pass --token or set MINIWEB_RECOVERY_TOKEN")

    size = os.path.getsize(args.db)
    status = api(args.url, args.token)
    offset = 0 if args.fresh else status.get("tmp_size", 0)
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
                            f"/recovery/db?offset={offset}", body=data)
                    break
                except (urllib.error.URLError, OSError) as e:
                    if attempt == 4:
                        raise
                    print(f"  retry {attempt + 1} at offset {offset}: {e}")
                    time.sleep(2 ** attempt)
                    # re-sync offset with the server after a failure
                    offset = api(args.url, args.token).get("tmp_size", offset)
                    f.seek(offset)
                    data = f.read(chunk)
            offset = r["tmp_size"]
            done = offset / size
            rate = offset / max(time.time() - t0, 1) / 1e6
            print(f"  {done * 100:5.1f}%  ({offset / 1e9:.2f} GB, {rate:.1f} MB/s)",
                  flush=True)

    restart = "0" if args.no_restart else "1"
    r = api(args.url, args.token, "POST", f"/recovery/db/complete?restart={restart}")
    print("server:", r)
    if r.get("replaced"):
        print("DB replaced." + (" App is restarting with the new file."
                                if r.get("restarting") else ""))


if __name__ == "__main__":
    main()
