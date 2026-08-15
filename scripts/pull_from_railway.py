"""Pull annotations + the 3 macro YAMLs down from a MiniWeb Railway deployment.

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
"""
import argparse
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
MACRO_YAMLS = ["macros.yaml", "macro_locations.yaml", "macro_templates.yaml"]
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
            if m.name.startswith("/") or ".." in pathlib.PurePosixPath(m.name).parts:
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


def _pull_annotations(base, token):
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        _download(base, token, "/recovery/annotations/download", tmp_path)
        # Validate BEFORE touching local, so a bad download never destroys data.
        with tarfile.open(tmp_path, "r:gz") as t:
            t.getmembers()
        if ANN.exists():
            shutil.rmtree(ANN)
        ANN.mkdir(parents=True, exist_ok=True)
        _safe_extract(tmp_path, ANN)
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
    args = ap.parse_args()

    if not args.token:
        sys.exit("No token: set MINIWEB_RECOVERY_TOKEN or pass --token")
    print(f"Pulling from {args.url}")

    ts = time.strftime("%Y%m%d_%H%M%S")
    if not args.no_backup:
        _backup(ts)

    if not args.macros_only:
        _pull_annotations(args.url, args.token)
    if not args.annotations_only:
        _pull_macros(args.url, args.token)
    print("Done.")


if __name__ == "__main__":
    main()
