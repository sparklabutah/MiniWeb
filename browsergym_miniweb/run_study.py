"""Run an AgentLab study over MiniWeb tasks (server lifecycle included).

Usage (from the repo root):
    python -m browsergym_miniweb.run_study --model claude-sonnet-4-5 --tasks 3
    python -m browsergym_miniweb.run_study --model ollama/qwen3.5:27b \\
        --tasks Minh/e-commerce_224c4c --max-steps 25 --no-headless
    python -m browsergym_miniweb.run_study --tasks all --jobs 4

--tasks accepts 'all', a count (first N), or comma-separated ids
(annotator/task_id). Vision (screenshot + SOM) is the default; --text opts out.
"""
import argparse
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
os.environ["AGENTLAB_EXP_ROOT"] = "/scratch/general/vast/u1653932/agentlab_results"

def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default=None,
                    help="claude-* | gpt-* | gemini-* | ollama/<name> "
                         "(default: helpers.llm DEFAULT_MODEL / $LLM_MODEL)")
    ap.add_argument("--tasks", default="1",
                    help="'all', a count, or comma-separated annotator/task ids (default: 1)")
    ap.add_argument("--max-steps", type=int, default=15)
    ap.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--text", action="store_true",
                    help="text-only agent (AXTree, no screenshots)")
    ap.add_argument("--port", type=int, default=8124)
    ap.add_argument("--jobs", type=int, default=1)
    args = ap.parse_args()

    os.chdir(ROOT)
    for p in (str(ROOT), str(ROOT / "evaluation")):
        if p not in sys.path:
            sys.path.insert(0, p)
    os.environ["MINIWEB_URL"] = f"http://localhost:{args.port}"

    from server import start_server, stop_server, wait_for_server
    from browsergym_miniweb import ALL_TASK_IDS
    from browsergym_miniweb.agentlab_study import make_benchmark, miniweb_agent
    from agentlab.experiments.study import make_study

    if args.tasks == "all":
        tasks = ALL_TASK_IDS
    elif args.tasks.isdigit():
        tasks = ALL_TASK_IDS[:int(args.tasks)]
    else:
        tasks = [t.strip() for t in args.tasks.split(",") if t.strip()]
    unknown = [t for t in tasks if t not in ALL_TASK_IDS]
    if unknown:
        raise SystemExit(f"unknown task ids: {unknown}")

    agent_kw = {"visual": not args.text}
    if args.model:
        agent_kw["model_name"] = args.model
    agent = miniweb_agent(**agent_kw)
    print(f"model={agent.chat_model_args.model_name}  visual={not args.text}  "
          f"tasks={len(tasks)}  max_steps={args.max_steps}")

    site = tasks[0].split("/")[1].rsplit("_", 1)[0]
    proc = start_server(args.port)
    if not wait_for_server(args.port, site_id=site, timeout=90):
        stop_server(proc)
        raise SystemExit(f"MiniWeb server did not start on port {args.port}")
    try:
        bench = make_benchmark(tasks, max_steps=args.max_steps, headless=args.headless)
        study = make_study(agent_args=[agent], benchmark=bench, ignore_dependencies=True)
        study.run(n_jobs=args.jobs,
                  parallel_backend="sequential" if args.jobs == 1 else "ray",
                  n_relaunch=1)
        try:
            res = study.get_results()
            df = res[0] if isinstance(res, tuple) else res
            cols = [c for c in ("env_args.task_name", "cum_reward", "n_steps", "err_msg")
                    if c in df.columns]
            print("\n=== AgentLab results ===")
            print(df[cols].to_string() if cols else df.to_string())
        except Exception as e:
            print("results read error:", e)
            print("study dir:", getattr(study, "dir", "?"))
    finally:
        stop_server(proc)


if __name__ == "__main__":
    main()
