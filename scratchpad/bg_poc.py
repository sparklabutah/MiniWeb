"""BrowserGym MiniWeb PoC harness (browser-gym branch).

Proves: (1) grade parity — MiniWeb's verifier reused via the BrowserGym bridge grades
gold trajectories the same as the native runner; (2) real-browser end-to-end — a
MiniWebTask boots against a live server, captures its session-scoped trajectory, and
validate() returns a proper grade; (3) the tasks register + boot under gym.make.
"""
import glob, json, os, sys, pathlib
sys.path.insert(0, ".")
os.chdir(pathlib.Path(__file__).resolve().parent.parent)

PORT = 8123
os.environ["MINIWEB_URL"] = f"http://localhost:{PORT}"

sys.path.insert(0, "evaluation")
from server import start_server, stop_server, wait_for_server
from evaluation.verifiers import verify_task
from evaluation.trajectory import synthesize_network_events

# a handful of tasks with gold trajectories
TASKS = []
for tf in sorted(glob.glob("data/annotations/*/*/task.json")):
    d = pathlib.Path(tf).parent
    if (d / "verifier.json").exists() and (d / "trajectory.json").exists():
        TASKS.append(f"{d.parent.name}/{d.name}")
    if len(TASKS) >= 10:
        break

print(f"PoC over {len(TASKS)} tasks\n")

# ── (1) grade parity: gold trajectory graded via verify_task should pass ──────────
print("=== (1) grade parity (gold → verify_task) ===")
npass = 0
for tid in TASKS:
    d = pathlib.Path("data/annotations") / tid
    task = json.load(open(d / "task.json"))
    spec = json.load(open(d / "verifier.json"))
    gold = synthesize_network_events(json.loads((d / "trajectory.json").read_text()))
    rep = verify_task(spec, gold, (task.get("expected_answer") or "").strip())
    npass += rep["passed"]
    print(f"  {'PASS' if rep['passed'] else 'FAIL'}  {tid}")
print(f"  parity: {npass}/{len(TASKS)} gold trajectories pass\n")

# ── boot server ───────────────────────────────────────────────────────────────
proc = start_server(PORT)
assert wait_for_server(PORT, site_id=TASKS[0].split("/")[1].split("_")[0], timeout=60), "server boot"
try:
    # ── (2) real-browser end-to-end via the task class ──────────────────────────
    print("=== (2) real-browser end-to-end (MiniWebTask.setup/validate) ===")
    from playwright.sync_api import sync_playwright
    import browsergym_miniweb  # registers tasks
    from browsergym_miniweb.task import MiniWebTask, fetch_session_trajectory

    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True, args=[
            "--no-sandbox", "--host-resolver-rules=MAP * ~NOTFOUND , EXCLUDE localhost"])
        page = b.new_page()
        tid = TASKS[0]
        t = MiniWebTask(task_id=tid)
        goal, info = t.setup(page)
        print(f"  setup: goal ends with instruction? {goal.endswith(t.task['instruction'])}  |  url={page.url.split('/sites/')[-1][:40]}")
        # simulate a bit of agent navigation so the session records something
        page.goto(t.base + f"/sites/{tid.split('/')[1].split('_')[0]}/")
        traj = fetch_session_trajectory(page, t.base)
        n_net = sum(1 for e in traj if e.get("type") == "network")
        print(f"  session-scoped trajectory captured: {len(traj)} events ({n_net} network) — non-empty={len(traj) > 0}")
        reward, done, msg, vinfo = t.validate(page, [{"role": "assistant", "message": t.expected}])
        print(f"  validate() -> reward={reward} done={done} types_ok={isinstance(reward, float) and isinstance(done, bool)}")
        print(f"  by_macro: {vinfo['by_macro']}")
        b.close()

    # ── (3) gym registration + boot ─────────────────────────────────────────────
    print("\n=== (3) gym registration + boot ===")
    import gymnasium as gym
    gym_id = "browsergym/miniweb." + TASKS[0].replace("/", ".")
    registered = gym_id in gym.registry
    print(f"  {gym_id} registered? {registered}  (total miniweb ids: {sum(1 for k in gym.registry if k.startswith('browsergym/miniweb.'))})")
    env = gym.make(gym_id, headless=True)
    obs, env_info = env.reset()
    goal_in_obs = obs.get("goal") or (obs.get("chat_messages") and str(obs["chat_messages"]))
    print(f"  gym.make + reset OK  |  goal present in obs: {bool(goal_in_obs)}")
    env.close()
    print("\nPoC complete.")
finally:
    stop_server(proc)
