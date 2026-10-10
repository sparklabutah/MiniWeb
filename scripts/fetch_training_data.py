"""Rebuild the training episodes the executor is trained on (one folder per episode: rows.jsonl, the step screenshots,
episode.json) from the Hugging Face release, in the layout `python -m miniwebagent.train` reads.

    python scripts/fetch_training_data.py                     # MiniWebGen's episodes -> data/webmix/replay_v4/
    python scripts/fetch_training_data.py --table task_centric_steps --out data/webmix/taskgen/rows_27k
    python scripts/fetch_training_data.py --src data/release/miniweb-v1-hf   # from a local copy of the release

Rows that are not training targets (a recovery episode's injected mistake and its replayed prefix) are written with
"inject": true, which the trainer skips, as in the original episodes.
"""
import argparse, glob, json, os

import pyarrow.parquet as pq

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPO = "miniweb/MiniWeb"
OUT = {"training_steps": os.path.join("data", "webmix", "replay_v4"),
       "task_centric_steps": os.path.join("data", "webmix", "taskgen", "rows_27k")}
COLS = ["episode", "variant", "parts", "task_id", "step", "segment", "primitive", "family", "op", "resolved",
        "memory_by", "messages", "target", "is_target", "image"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", choices=list(OUT), default="training_steps")
    ap.add_argument("--src", help="a local copy of the release (default: download the table from the Hub)")
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--out")
    a = ap.parse_args()
    out = a.out or os.path.join(ROOT, OUT[a.table])
    src = a.src
    if not src:
        from huggingface_hub import snapshot_download
        src = snapshot_download(a.repo, repo_type="dataset", allow_patterns=[f"data/{a.table}/*"])
    files = sorted(glob.glob(os.path.join(src, "data", a.table, "*.parquet")))
    episodes, rows = {}, 0
    handles = {}
    try:
        for f in files:
            for batch in pq.ParquetFile(f).iter_batches(batch_size=200, columns=COLS):
                for r in batch.to_pylist():
                    d = os.path.join(out, r["episode"])
                    if r["episode"] not in episodes:
                        os.makedirs(d, exist_ok=True)
                        episodes[r["episode"]] = r["parts"]
                        parts = r["parts"] if r["variant"] == "chain" else None   # only chains list their parts, as the originals
                        json.dump({"task_id": r["task_id"], "variant": r["variant"], "parts": parts},
                                  open(os.path.join(d, "episode.json"), "w"))
                        handles[r["episode"]] = open(os.path.join(d, "rows.jsonl"), "w")
                    img = r["image"]
                    if img and img.get("bytes"):
                        open(os.path.join(d, img["path"]), "wb").write(img["bytes"])
                    row = {"task_id": r["task_id"], "step": r["step"], "segment": r["segment"], "macro": r["primitive"],
                           "family": r["family"], "op": r["op"], "resolved": r["resolved"], "memory_by": r["memory_by"],
                           "messages": json.loads(r["messages"]) if r["messages"] else None, "target": r["target"]}
                    if not r["is_target"]:
                        row["inject"] = True
                    handles[r["episode"]].write(json.dumps(row, ensure_ascii=False) + "\n")
                    rows += 1
    finally:
        for h in handles.values():
            h.close()
    print(f"{len(episodes)} episodes, {rows} rows -> {out}")


if __name__ == "__main__":
    main()
