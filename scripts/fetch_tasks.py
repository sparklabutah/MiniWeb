"""Rebuild the human tasks in the layout the evaluators read (data/annotations/<author>/<task_id>/) from the Hugging
Face release (the `tasks` and `demonstrations` tables). Each task gets task.json and verifier.json as evaluated, its
recording (trajectory.json with page snapshots, screenshots/, server_log.json, beacon_log.json), the reviewer's
verification walk (verification_walk.json) and verifier_runs.json, which tells the VLM judge which of the two to use
as its reference (the walk where the recording no longer passes the reviewed verifier).

    python scripts/fetch_tasks.py                                 # from the Hub
    python scripts/fetch_tasks.py --src data/release/miniweb-v1-hf  # from a local copy of the release
    python scripts/fetch_tasks.py --out data/annotations          # (the default; MINIWEB_ANNOTATIONS_DIR moves it)
"""
import argparse, glob, json, os

import pyarrow.parquet as pq

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPO = "sparklabuofu/MiniWeb"


def load(v):
    return None if v is None else json.loads(v)


def unflatten(v):
    """The release stores nested fields as JSON text: back to the value (plain strings stay strings)."""
    if isinstance(v, str) and v[:1] in "{[":
        try:
            return json.loads(v)
        except ValueError:
            return v
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", help="a local copy of the release (default: download the two tables from the Hub)")
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--out", default=os.environ.get("MINIWEB_ANNOTATIONS_DIR", os.path.join(ROOT, "data", "annotations")))
    ap.add_argument("--valset", default=os.path.join(ROOT, "data", "webmix", "valgen", "val_v2.jsonl"),
                    help="where to write the generated single-primitive test tasks")
    a = ap.parse_args()
    src = a.src
    if not src:
        from huggingface_hub import snapshot_download
        src = snapshot_download(a.repo, repo_type="dataset", allow_patterns=["data/tasks/*", "data/demonstrations/*", "data/single_primitive_test_tasks/*"])
    tasks = {}
    for f in sorted(glob.glob(os.path.join(src, "data", "tasks", "*.parquet"))):
        for r in pq.read_table(f).to_pylist():
            tasks[r["task_id"]] = r
    folder = {}
    for tid, r in tasks.items():
        d = os.path.join(a.out, r["author"] or "unknown", tid)
        os.makedirs(os.path.join(d, "screenshots"), exist_ok=True)
        folder[tid] = d
        for name, col in (("task.json", "task"), ("verifier.json", "verifier"), ("server_log.json", "server_log"),
                          ("beacon_log.json", "beacon_log"), ("verification_walk.json", "verification_walk")):
            v = load(r[col])
            if v is not None:
                json.dump(v, open(os.path.join(d, name), "w"), indent=1, ensure_ascii=False)
        prov = load(r["provenance"]) or {}
        status = (prov.get("demonstration") or {}).get("status")
        walk = load(r["verification_walk"]) is not None
        json.dump({"runs": {"gold": {"passed": status == "valid"}, "walk": {"passed": walk} if walk else {}}},
                  open(os.path.join(d, "verifier_runs.json"), "w"), indent=1)
    events = {}
    cols = ["task_id", "event_index", "type", "record", "html", "axtree", "screenshot"]
    for f in sorted(glob.glob(os.path.join(src, "data", "demonstrations", "*.parquet"))):
        for batch in pq.ParquetFile(f).iter_batches(batch_size=200, columns=cols):
            for r in batch.to_pylist():
                d = folder.get(r["task_id"])
                if d is None:
                    continue
                shot = r["screenshot"]
                if shot and shot.get("bytes"):
                    rec = load(r["record"]) or {}
                    rel = rec.get("screenshot") if isinstance(rec.get("screenshot"), str) else f"screenshots/{shot['path']}"
                    open(os.path.join(d, rel), "wb").write(shot["bytes"])
                if r["type"] == "screenshot":
                    continue                              # a capture no recorded event points to: the file is enough
                rec = load(r["record"]) or {}
                if r["html"] is not None:
                    rec["snapshot"] = r["html"]
                if r["axtree"] is not None:
                    try:
                        rec["axtree"] = json.loads(r["axtree"])
                    except ValueError:
                        rec["axtree"] = r["axtree"]
                events.setdefault(r["task_id"], []).append((r["event_index"], rec))
    for tid, evs in events.items():
        json.dump([e for _, e in sorted(evs, key=lambda x: x[0])], open(os.path.join(folder[tid], "trajectory.json"), "w"),
                  ensure_ascii=False)
    print(f"{len(tasks)} tasks in {a.out} ({len(events)} with a recording)")
    # the generated single-primitive test tasks of the held-out sites, as the file the evaluator reads (--tasks)
    rows = [r for f in sorted(glob.glob(os.path.join(src, "data", "single_primitive_test_tasks", "*.parquet")))
            for r in pq.read_table(f).to_pylist()]
    if rows:
        os.makedirs(os.path.dirname(a.valset), exist_ok=True)
        with open(a.valset, "w") as fh:
            for r in rows:
                fh.write(json.dumps({k: unflatten(v) for k, v in r.items()}, ensure_ascii=False) + "\n")
        print(f"{len(rows)} generated single-primitive test tasks in {a.valset}")


if __name__ == "__main__":
    main()
