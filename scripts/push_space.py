"""Upload the public demo to a Hugging Face Docker Space. The upload holds the repository's files as they are in the
working tree (tracked, plus new files git does not ignore), with deploy/space/Dockerfile and deploy/space/README.md as
the Space's Dockerfile and README. The Space then builds the image and runs deploy/space/start.sh.

    python scripts/push_space.py sparklabuofu/MiniWeb-demo --dry-run    # list what would change
    python scripts/push_space.py sparklabuofu/MiniWeb-demo              # creates the Space when it does not exist

Needs a token that can write to the namespace (`huggingface-cli login`, or HF_TOKEN).
"""
import argparse, os, subprocess

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OVERRIDES = {"Dockerfile": "deploy/space/Dockerfile", "README.md": "deploy/space/README.md"}


def local_files():
    out = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout
    files = {f: f for f in out.split("\0") if f and os.path.isfile(os.path.join(ROOT, f))}
    files.update(OVERRIDES)                              # path in the Space -> path here
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("space", help="the Space, e.g. sparklabuofu/MiniWeb-demo")
    ap.add_argument("--private", action="store_true", help="when creating the Space")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    from huggingface_hub import CommitOperationAdd, CommitOperationDelete, HfApi
    api = HfApi()
    files = local_files()
    try:
        remote = set(api.list_repo_files(a.space, repo_type="space"))
    except Exception:
        remote = set()
    stale = sorted(remote - set(files) - {".gitattributes"})
    print(f"{len(files)} files to upload, {len(stale)} to delete from {a.space}")
    if a.dry_run:
        for f in stale:
            print("  delete", f)
        return
    api.create_repo(a.space, repo_type="space", space_sdk="docker", private=a.private, exist_ok=True)
    ops = [CommitOperationAdd(path_in_repo=k, path_or_fileobj=os.path.join(ROOT, v)) for k, v in sorted(files.items())]
    ops += [CommitOperationDelete(path_in_repo=f) for f in stale]
    info = api.create_commit(a.space, repo_type="space", operations=ops, commit_message="Update the demo")
    print(info.commit_url)


if __name__ == "__main__":
    main()
