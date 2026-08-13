"""Real AgentLab GenericAgent run against MiniWeb via BrowserGym (browser-gym branch).

Drives qwen3.5:27b (local, via ollama's OpenAI-compatible endpoint) through AgentLab's
GenericAgent on a MiniWeb task; our MiniWebTask.validate() grades it. Proves the full
make_study -> run -> grade loop end to end.
"""
import os, sys, pathlib
sys.path.insert(0, ".")
os.chdir(pathlib.Path(__file__).resolve().parent.parent)

PORT = 8124
os.environ["MINIWEB_URL"] = f"http://localhost:{PORT}"
# route AgentLab's OpenAI client at the local ollama server
# local ollama (no API key). NOTE: the model MUST be named "ollama/<name>" below —
# a bare name like "qwen3.5:27b" resolves to the groq catch-all and fails on a
# missing key.
os.environ["OLLAMA_API_BASE"] = "http://localhost:11434"

# The verifier's fuzzy answer check uses an LLM judge (default gemini-3.5-flash).
# Importing app loads .env (Gemini/Vertex creds); fail FAST if the judge is not
# reachable, so a misconfig aborts here instead of silently scoring every fuzzy
# answer as wrong (false negatives) across the whole run.
import app  # noqa: F401  — triggers .env autoload
from helpers.llm import _provider_configured, resolve_provider
JUDGE = os.environ.setdefault("VERIFIER_JUDGE_MODEL", "gemini-3.5-flash")
assert _provider_configured(resolve_provider(JUDGE)), (
    f"verifier judge {JUDGE!r} not configured — set Gemini/Vertex creds in .env "
    "(GOOGLE_GENAI_USE_VERTEXAI + GOOGLE_CLOUD_PROJECT, or GEMINI_API_KEY), "
    "or override VERIFIER_JUDGE_MODEL")
print(f"verifier judge ready: {JUDGE} ({resolve_provider(JUDGE)})")

sys.path.insert(0, "evaluation")
from server import start_server, stop_server, wait_for_server
from browsergym_miniweb import ALL_TASK_IDS
from browsergym_miniweb.agentlab_study import make_benchmark, miniweb_agent
from agentlab.experiments.study import make_study

TASKS = ALL_TASK_IDS
site = TASKS[0].split("/")[1].rsplit("_", 1)[0]
print("running AgentLab GenericAgent(qwen3.5:27b) on:", TASKS)

proc = start_server(PORT)
assert wait_for_server(PORT, site_id=site, timeout=60), "server boot"
try:
    bench = make_benchmark(TASKS, max_steps=50, headless=True)
    agent = miniweb_agent("ollama/qwen3.5:27b", max_total_tokens=32000)
    study = make_study(agent_args=[agent], benchmark=bench, ignore_dependencies=True)
    study.run(n_jobs=1, parallel_backend="sequential", n_relaunch=1)

    # results
    try:
        res = study.get_results()
        df = res[0] if isinstance(res, tuple) else res
        cols = [c for c in ("env_args.task_name", "cum_reward", "n_steps", "err_msg") if c in df.columns]
        print("\n=== AgentLab results ===")
        print(df[cols].to_string() if cols else df.to_string())
    except Exception as e:
        print("results read err:", e)
        print("study dir:", getattr(study, "dir", "?"))
    print("\nAgentLab run complete.")
finally:
    stop_server(proc)
