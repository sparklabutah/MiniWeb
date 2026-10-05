"""Score Online-Mind2Web episodes (webmix.om2w) with the benchmark's own WebJudge, as its authors require: o4-mini,
mode WebJudge_Online_Mind2Web_eval, score threshold 3. The official evaluator (OSU-NLP-Group/Online-Mind2Web, MIT,
commit in data/webmix/om2w/official/COMMIT) is vendored unchanged; the OpenAI key comes from .env through the
environment, never a command line (the official script takes it as an argument).

    python -m webmix.om2w_judge data/webmix/om2w/runs/base --workers 16
"""
import argparse
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
OFFICIAL = ROOT / "data" / "webmix" / "om2w" / "official" / "src"


def judge_webvoyager(run_dir, model_name, img_num=15, workers=16):
    """WebVoyager episodes, judged exactly as the official evaluation/auto_eval.py (vendored in data/webmix/webvoyager):
    its SYSTEM_PROMPT/USER_PROMPT, the last `img_num` screenshots (15, evaluation/run_eval.sh), max_tokens 1000, seed 42,
    temperature 0, verdict 'NOT SUCCESS' -> 0 / 'SUCCESS' -> 1 / neither -> None, and no answer -> 0 without a call.
    Only the model differs: the official gpt-4-vision-preview is retired. -> {"tasks", "success", "rate"}; per-task
    labels in <run>_wvjudge."""
    import json
    import re
    from concurrent.futures import ThreadPoolExecutor
    from openai import OpenAI
    sys.path.insert(0, str(ROOT / "data" / "webmix" / "webvoyager"))
    import auto_eval as official                                 # noqa: E402  (official prompts + encode_image)
    client = OpenAI()
    out = Path(str(run_dir) + "_wvjudge")
    out.mkdir(parents=True, exist_ok=True)
    dirs = sorted(d for d in Path(run_dir).iterdir() if d.is_dir() and (d / "result.json").exists())

    def one(d):
        dest = out / f"{d.name}.json"
        if dest.exists():
            return json.loads(dest.read_text())
        r = json.loads((d / "result.json").read_text())
        answer = (r.get("final_result_response") or "").strip()
        shots = sorted((d / "trajectory").glob("*.png"), key=lambda p: int(re.findall(r"\d+", p.name)[0]))[-img_num:]
        if not answer:                                           # official: no ANSWER action -> 0, no call
            res = {"task_id": d.name, "predicted_label": 0, "response": "no answer"}
        else:
            prompt = official.USER_PROMPT.replace("<task>", r["task"]).replace("<answer>", answer).replace(
                "<num>", str(img_num))
            imgs = [{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{official.encode_image(p)}"}}
                    for p in shots]
            messages = [{"role": "system", "content": official.SYSTEM_PROMPT},
                        {"role": "user", "content": [{"type": "text", "text": prompt}] + imgs
                         + [{"type": "text", "text": "Your verdict:\n"}]}]
            for attempt in range(6):
                try:
                    text = client.chat.completions.create(model=model_name, messages=messages, max_tokens=1000,
                                                          seed=42, temperature=0).choices[0].message.content
                    break
                except Exception as e:                           # noqa: BLE001  (rate limits: retry, as official)
                    text = f"ERROR {type(e).__name__}: {e}"
                    time.sleep(10 * (attempt + 1))
            label = 0 if "NOT SUCCESS" in text else 1
            if "SUCCESS" not in text:
                label = None
            res = {"task_id": d.name, "predicted_label": label, "response": text}
        if not str(res["response"]).startswith("ERROR"):
            dest.write_text(json.dumps(res, ensure_ascii=False))
        return res
    with ThreadPoolExecutor(workers) as ex:
        labels = [x["predicted_label"] for x in ex.map(one, dirs)]
    ok = sum(1 for x in labels if x == 1)
    summary = {"tasks": len(labels), "success": ok, "rate": round(ok / max(1, len(labels)), 4),
               "no_verdict": sum(1 for x in labels if x is None), "judge": model_name, "img_num": img_num}
    (out / "summary.json").write_text(json.dumps(summary))
    print(json.dumps(summary))
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m webmix.om2w_judge")
    ap.add_argument("run_dir")
    ap.add_argument("--bench", default="om2w", choices=["om2w", "webvoyager"])
    ap.add_argument("--model", default=None, help="default: o4-mini (om2w, WebJudge), gpt-4o (webvoyager)")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--threshold", type=int, default=3)
    ap.add_argument("--img-num", type=int, default=15, help="webvoyager: final screenshots attached (official 15)")
    a = ap.parse_args(argv)
    from webmix.wa import _load_openai_env
    _load_openai_env()
    sys.path.insert(0, str(OFFICIAL))
    if a.bench == "webvoyager":
        return judge_webvoyager(a.run_dir, a.model or "gpt-4o", a.img_num, a.workers)
    a.model = a.model or "o4-mini"
    import run as official                                       # noqa: E402  (the vendored src/run.py)
    run_dir = Path(a.run_dir)
    n = sum(1 for d in run_dir.iterdir() if d.is_dir() and (d / "result.json").exists())
    args = SimpleNamespace(mode="WebJudge_Online_Mind2Web_eval", model=a.model, trajectories_dir=str(run_dir),
                           api_key=None, output_path=str(run_dir) + "_webjudge", score_threshold=a.threshold)
    Path(args.output_path).mkdir(parents=True, exist_ok=True)
    official.parallel_eval(args, max(1, min(a.workers, n)))
    return summarize_webjudge(args.output_path, n)


def summarize_webjudge(out_dir, n_tasks=None):
    """The official run appends one line per judged task and skips judged ones on a rerun (so a partial batch judged
    early is not paid for again), and prints only that invocation's rate: count every judged task instead."""
    import json
    labels = {}
    for f in Path(out_dir).glob("*_auto_eval_results.json"):
        for line in f.read_text().split("\n"):
            if line.strip():
                r = json.loads(line)
                labels[r["task_id"]] = r.get("evaluation_results", r).get("predicted_label")
    ok = sum(1 for v in labels.values() if v == 1)
    summary = {"judged": len(labels), "tasks": n_tasks or len(labels), "success": ok,
               "rate": round(ok / max(1, len(labels)), 4)}
    (Path(out_dir) / "summary.json").write_text(json.dumps(summary))
    print(json.dumps(summary))
    return summary


if __name__ == "__main__":
    main()
