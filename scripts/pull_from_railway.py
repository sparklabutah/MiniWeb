"""Pull annotations + the 2 macro YAMLs down from a MiniWeb Railway deployment.

Backs up the current LOCAL data/annotations + macro YAMLs (timestamped tarball
under data/backups/), then downloads and REPLACES them with the deployment's
copies, served by the token-gated GET /recovery/{annotations,macros}/download
endpoints.

Usage:
  MINIWEB_RECOVERY_TOKEN=<token> python scripts/pull_from_railway.py
  python scripts/pull_from_railway.py --url https://<app>.up.railway.app --token <token>

Options:
  --url         deployment base URL (default $MINIWEB_RAILWAY_URL or the prod URL)
  --token       recovery token (default $MINIWEB_RECOVERY_TOKEN)
  --no-backup   skip the local backup (not recommended)
  --annotations-only / --macros-only   pull just one of the two
  --new-only    import new task directories, preserve existing local work;
                retain the remote snapshot and a difference manifest
"""
import argparse
import glob
import hashlib
import json
import os
import pathlib
import shutil
import sys
import tarfile
import tempfile
import time
import urllib.request

REPO = pathlib.Path(__file__).resolve().parent.parent
DATA = REPO / "data"
ANN = DATA / "annotations"
MACRO_YAMLS = ["macros.yaml", "macro_locations.yaml"]
BACKUP_DIR = DATA / "backups"
DEFAULT_URL = os.environ.get("MINIWEB_RAILWAY_URL",
                             "https://miniweb-production.up.railway.app")


def _download(base, token, path, dest):
    req = urllib.request.Request(base.rstrip("/") + path,
                                 headers={"X-Recovery-Token": token})
    with urllib.request.urlopen(req, timeout=1200) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f, length=1 << 20)


def _safe_extract(tar_path, dest):
    """Validate the archive fully (truncated gzip raises), then extract."""
    with tarfile.open(tar_path, "r:gz") as tar:
        members = tar.getmembers()                 # forces a full parse
        for m in members:                          # reject path traversal
            if (m.name.startswith("/") or ".." in pathlib.PurePosixPath(m.name).parts
                    or not (m.isfile() or m.isdir())):
                raise ValueError(f"unsafe path in archive: {m.name}")
        tar.extractall(dest)
    return len(members)


def _backup(ts):
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    bak = BACKUP_DIR / f"pull_backup_{ts}.tar.gz"
    with tarfile.open(bak, "w:gz") as tar:
        if ANN.exists():
            tar.add(ANN, arcname="annotations")
        for y in MACRO_YAMLS:
            p = DATA / y
            if p.exists():
                tar.add(p, arcname=y)
    try:
        shown = bak.relative_to(REPO)
    except ValueError:
        shown = bak
    print(f"✓ backed up local annotations + macro YAMLs -> {shown} "
          f"({bak.stat().st_size // 1024} KB)")


def _tree_hashes(directory):
    result = {}
    for p in sorted(directory.rglob("*")):
        if p.is_file():
            with p.open("rb") as stream:
                result[str(p.relative_to(directory))] = hashlib.file_digest(stream, "sha256").hexdigest()
    return result


def _import_new(snapshot, destination):
    """Existing directories are never overwritten, including partial local work."""
    manifest = {"new": [], "unchanged": [], "existing_differences": [], "local_only": [], "trashed_locally": []}
    remote_keys = set()
    for metadata in sorted(snapshot.glob("*/*/task.json")):
        relative = metadata.parent.relative_to(snapshot)
        if any(part.startswith(".") for part in relative.parts):
            continue
        key = str(relative)
        remote_keys.add(key)
        # A task deleted locally (moved to .trash/<annotator>/<task_id>-<stamp>) stays deleted.
        if any((destination / ".trash" / relative.parent).glob(glob.escape(relative.name) + "-*")):
            manifest["trashed_locally"].append(key)
            continue
        # Validate new metadata before copying any files for this task.
        task = json.loads(metadata.read_text())
        if not isinstance(task, dict) or task.get("task_id") != relative.name:
            raise ValueError(f"Invalid task metadata: {key}")
        target = destination / relative
        if target.exists():
            local, remote = _tree_hashes(target), _tree_hashes(metadata.parent)
            changed = [p for p in sorted(local.keys() | remote.keys()) if local.get(p) != remote.get(p)]
            if changed:
                manifest["existing_differences"].append({"key": key, "files": changed})
            else:
                manifest["unchanged"].append(key)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            # Stage on the same filesystem; expose only complete task directories.
            with tempfile.TemporaryDirectory(prefix=".import-", dir=target.parent) as staging:
                ready = pathlib.Path(staging) / relative.name
                shutil.copytree(metadata.parent, ready)
                ready.rename(target)
            manifest["new"].append(key)
    manifest["local_only"] = sorted(str(p.parent.relative_to(destination))
        for p in destination.glob("*/*/task.json")
        if str(p.parent.relative_to(destination)) not in remote_keys and
        not any(part.startswith(".") for part in p.relative_to(destination).parts))
    return manifest


def _pull_annotations(base, token, new_only=False, ts=None):
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        _download(base, token, "/recovery/annotations/download", tmp_path)
        # Extract and validate BEFORE touching local, including archive links.
        DATA.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".railway-pull-", dir=DATA) as staging:
            snapshot = pathlib.Path(staging) / "annotations"
            snapshot.mkdir()
            _safe_extract(tmp_path, snapshot)
            if new_only:
                run = DATA / "railway_pulls" / (ts or time.strftime("%Y%m%d_%H%M%S"))
                run.mkdir(parents=True, exist_ok=False)
                snapshot.rename(run / "remote_annotations")
                manifest = _import_new(run / "remote_annotations", ANN)
                manifest.update({"source": base, "mode": "new-only", "snapshot": str(run / "remote_annotations")})
                (run / "manifest.json").write_text(json.dumps(manifest, indent=2))
                print(f"✓ imported {len(manifest['new'])} new tasks; preserved "
                      f"{len(manifest['existing_differences'])} differing local tasks. Manifest: {run / 'manifest.json'}")
            else:
                if ANN.exists():
                    shutil.rmtree(ANN)
                snapshot.rename(ANN)
    finally:
        os.remove(tmp_path)
    tasks = sum(1 for _ in ANN.glob("*/*/task.json"))
    print(f"✓ pulled annotations -> data/annotations ({tasks} tasks)")


def _pull_macros(base, token):
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        _download(base, token, "/recovery/macros/download", tmp_path)
        with tarfile.open(tmp_path, "r:gz") as t:
            names = [m.name for m in t.getmembers()]
        _safe_extract(tmp_path, DATA)
    finally:
        os.remove(tmp_path)
    print(f"✓ pulled macro YAMLs -> data/ ({', '.join(names)})")


def main():
    ap = argparse.ArgumentParser(description="Pull annotations + macro YAMLs from Railway.")
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--token", default=os.environ.get("MINIWEB_RECOVERY_TOKEN", ""))
    ap.add_argument("--no-backup", action="store_true")
    ap.add_argument("--annotations-only", action="store_true")
    ap.add_argument("--macros-only", action="store_true")
    ap.add_argument("--new-only", action="store_true", help="Preserve existing tasks; implies --annotations-only")
    args = ap.parse_args()
    if args.new_only and args.macros_only:
        ap.error("--new-only cannot be combined with --macros-only")

    if not args.token:
        sys.exit("No token: set MINIWEB_RECOVERY_TOKEN or pass --token")
    print(f"Pulling from {args.url}")

    ts = time.strftime("%Y%m%d_%H%M%S")
    if not args.no_backup:
        _backup(ts)

    if not args.macros_only:
        _pull_annotations(args.url, args.token, new_only=args.new_only, ts=ts)
    if not (args.annotations_only or args.new_only):
        _pull_macros(args.url, args.token)
    print("Done.")


if __name__ == "__main__":
    main()
