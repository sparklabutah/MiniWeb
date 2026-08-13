"""AgentLab run on the 8 multi-site ("QA") tasks — end-to-end test of the
report_answer tool + task-aware judge + agent-driven termination.
"""
import os, sys, pathlib, glob, gzip, pickle, re, json
sys.path.insert(0, ".")
os.chdir(pathlib.Path(__file__).resolve().parent.parent)

PORT = 8124
os.environ["MINIWEB_URL"] = f"http://localhost:{PORT}"
os.environ["OLLAMA_API_BASE"] = "http://localhost:11434"   # local ollama (no API key)

# judge preflight (loads .env → Vertex/Gemini creds); fail fast if not reachable
import app  # noqa: F401
from helpers.llm import _provider_configured, resolve_provider
JUDGE = os.environ.setdefault("VERIFIER_JUDGE_MODEL", "gemini-3.5-flash")
assert _provider_configured(resolve_provider(JUDGE)), f"judge {JUDGE!r} not configured"
print(f"verifier judge ready: {JUDGE}")

sys.path.insert(0, "evaluation")
from server import start_server, stop_server, wait_for_server
from browsergym_miniweb.agentlab_study import make_benchmark, miniweb_agent
from agentlab.experiments.study import make_study

TASKS = [
    "Farhan/ai-chatbots_academic-paper-db_a408d0",
    "Farhan/banking_email_e9591f",
    "Farhan/business-company_video_82df62",
    "Farhan/crm_calendar-todo_3a5e33",
    "Minh/translation_team-chat-workspace_2b6dff",
    "hernan/e-commerce_spreadsheets-slides_13f2ed",
    "hernan/forums_news_6d4105",
    "hernan/real-estate-buy-rent_email_fce595",
]
print("running on", len(TASKS), "multi-site tasks")

proc = start_server(PORT)
assert wait_for_server(PORT, site_id="banking", timeout=60), "server boot"
try:
    bench = make_benchmark(TASKS, max_steps=30, headless=True)
    agent = miniweb_agent("ollama/qwen3.5:27b", max_total_tokens=32000)
    study = make_study(agent_args=[agent], benchmark=bench, ignore_dependencies=True)
    study.run(n_jobs=1, parallel_backend="sequential", n_relaunch=1)
    sdir = str(getattr(study, "dir", ""))
    print("\nSTUDY_DIR:", sdir)

    # per-episode analysis: reward, steps, how it ended, did it use report_answer
    print("\n=== RESULTS (multi-site) ===")
    print(f"{'task':52s} {'reward':>6} {'steps':>5} {'end':>10} {'report_answer':>13}")
    rewards = []
    for ep in sorted(glob.glob(f"{sdir}/*banking_email*") + glob.glob(f"{sdir}/*")):
        si = pathlib.Path(ep) / "summary_info.json"
        if not si.exists():
            continue
        info = json.loads(si.read_text())
        name = pathlib.Path(ep).name.split("_on_")[-1]
        steps = sorted(glob.glob(f"{ep}/step_*.pkl.gz"), key=lambda p: int(re.search(r"step_(\d+)", p).group(1)))
        used_tool = False
        for sp in steps:
            try:
                with gzip.open(sp, "rb") as f:
                    a = getattr(pickle.load(f), "action", "") or ""
                if "report_answer(" in a:
                    used_tool = True; break
            except Exception:
                pass
        r = info.get("cum_reward", 0.0)
        rewards.append(r)
        end = "terminated" if info.get("terminated") else ("truncated" if info.get("truncated") else "?")
        print(f"{name[:52]:52s} {r:>6.1f} {info.get('n_steps','?'):>5} {end:>10} {str(used_tool):>13}")
    if rewards:
        print(f"\nSUCCESS RATE: {sum(1 for r in rewards if r>=1.0)}/{len(rewards)}  "
              f"({100*sum(1 for r in rewards if r>=1.0)//len(rewards)}%)")
    print("\nrun complete.")
finally:
    stop_server(proc)
