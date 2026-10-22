"""Download MiniWebAgent's trained executors from the Hugging Face Hub into data/webmix/adapters/, under the names the
evaluator and scripts/reproduce.py use.

    python scripts/fetch_adapters.py          # MiniWebAgent's executor -> data/webmix/adapters/pooled_v4
    python scripts/fetch_adapters.py --all    # also the paper's other executors (task-centric, specialists, no-done)

Serve them with src/miniwebagent/scripts/serve.sh (LORA_MODULES=<name>=data/webmix/adapters/<name>).
"""
import argparse, os, shutil

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPO = "sparklabuofu/MiniWebAgent"
FILES = ["adapter_config.json", "adapter_model.safetensors", "train_log.jsonl", "training_meta.json"]
# folder in the repository -> local adapter name
MAIN = {"": "pooled_v4"}
ABLATIONS = {"ablations/task_centric": "taskgen_pooled", "ablations/no_done": "pooled_nodone",
             "ablations/specialists/drag": "drag_v5b", "ablations/specialists/io": "io_v5b",
             "ablations/specialists/select": "select_v5b", "ablations/specialists/rest": "rest_v5b",
             "ablations/specialists/reasoning": "reasoning_v4"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="also download the paper's other executors (2.3 GB)")
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "webmix", "adapters"))
    a = ap.parse_args()
    want = {**MAIN, **(ABLATIONS if a.all else {})}
    todo = {sub: name for sub, name in want.items()
            if not os.path.exists(os.path.join(a.out, name, "adapter_model.safetensors"))}
    for name in sorted(set(want.values()) - set(todo.values())):
        print(f"{name}: already present")
    if not todo:
        return
    from huggingface_hub import snapshot_download
    stage = os.path.join(a.out, "_download")
    snapshot_download(a.repo, local_dir=stage,
                      allow_patterns=[os.path.join(sub, f) if sub else f for sub in todo for f in FILES])
    for sub, name in todo.items():
        dst = os.path.join(a.out, name)
        os.makedirs(dst, exist_ok=True)
        for f in FILES:
            src = os.path.join(stage, sub, f)
            if os.path.exists(src):
                os.replace(src, os.path.join(dst, f))
        print(f"{name}: {os.path.relpath(dst, ROOT)}")
    shutil.rmtree(stage)


if __name__ == "__main__":
    main()
