# Migrating MiniWeb to BrowserGym + AgentLab

Guide to porting the MiniWeb benchmark onto [BrowserGym](https://github.com/ServiceNow/BrowserGym)
(ServiceNow's Gym-style web-agent environment, the harness behind WebArena / WorkArena /
MiniWoB) and running it with [AgentLab](https://github.com/ServiceNow/AgentLab).

**Goal:** make MiniWeb results directly comparable to the standard web-agent benchmarks by
evaluating with the same harness and the same reference agent (AgentLab `GenericAgent`).

**TL;DR effort:** ~1 week for a proof-of-concept on a task subset; ~2–3 weeks for a solid,
reproducible port of all 254 tasks. Much less than a WebArena-class integration because
MiniWeb needs no Docker, already runs a single server with per-session isolation, captures
its own trajectory server-side, and ships a harness-agnostic verifier.

---

## 1. Why MiniWeb ports easily

BrowserGym's task contract is three methods on `AbstractBrowserTask`:

```python
setup(page)                       -> (goal: str, info: dict)          # navigate + prepare
validate(page, chat_messages)     -> (reward: float, done: bool,      # called each step
                                       message: str, info: dict)
teardown()                        -> None                              # optional cleanup
```

MiniWeb already has the three pieces that make other adapters heavy:

| BrowserGym needs | MiniWeb already has |
|---|---|
| A reachable web server per task | One Flask app serving all 66 sites, **no Docker**, with `session_overlay` isolation so many episodes share it (`evaluation/server.py::start_server`) |
| A way to know if the task succeeded | `evaluation/verifiers.py::verify_task(spec, trajectory, answer)` — pure sync Python, grades the **trajectory**, harness-independent |
| A start state per episode | `/_reset_data` (GET) session reset + `resolve_start_url()` / `recorded_start_url()` in `run_agent_verify.py` |
| Trajectory capture | Server-side `/_admin/log` (network), `/_admin/record` (recorder actions+observations), `/_admin/beacon` (UI beacons) — captured regardless of who drives the browser |

Three recent changes de-risk the port specifically:
- **Backend-gated verifier** (`evaluation/verifier_archetypes.py`): the graded signal is the
  server-side backend request, with frontend affordance only *advisory*. So grading is correct
  even if a different harness's clicks don't fire `recorder.js` beacons identically.
- **Offline mode** (`--host-resolver-rules` in `evaluation/agents.py` / `computer_use.py`).
- **Per-task session reset** (`/_reset_data`, session-scoped → parallel-safe).

---

## 2. Architecture mapping

```
BrowserGym env (one browser context)  ─┐
   │  page.goto(<origin>/_reset_data)   │  fresh session_id (cookie _data_overlay_sid)
   │  page.goto(start_url)              │  → isolated session_overlay
   ▼                                    │
MiniWeb Flask server  ─────────────────┘  (one process, many parallel sessions)
   │  records /_admin/{log,record,beacon} per session
   ▼
validate(): fetch THIS session's trajectory → synthesize_network_events → verify_task
```

One MiniWeb server can back **many** parallel AgentLab envs because state is per-session.

---

## 3. Implementation

### 3.1 The task class (`browsergym-miniweb` package)

```python
# browsergym/miniweb/src/browsergym/miniweb/task.py  (sketch)
import json, pathlib
from browsergym.core.task import AbstractBrowserTask
from evaluation.verifiers import verify_task
from evaluation.trajectory import synthesize_network_events

ANNOTATIONS = pathlib.Path("data/annotations")

class MiniWebTask(AbstractBrowserTask):
    def __init__(self, seed=None, task_id=None, base_url=None):
        super().__init__(seed)
        self.task_id = task_id                       # e.g. "Minh/e-commerce_224c4c"
        self.base = (base_url or os.environ["MINIWEB_URL"]).rstrip("/")
        tdir = ANNOTATIONS / task_id
        self.task = json.loads((tdir / "task.json").read_text())
        self.verifier = json.loads((tdir / "verifier.json").read_text())

    def setup(self, page):
        # 1) reset this session (session-scoped, parallel-safe)
        page.goto(f"{self.base}/_reset_data")
        # 2) resolve where recording started (first observation URL, mapped to local base)
        start_url = _resolve_start_url(self.base, self.task, self.verifier)
        page.goto(start_url)
        goal = self.task["instruction"]
        return goal, {"task_id": self.task_id}

    def validate(self, page, chat_messages):
        # pull THIS session's trajectory via the browser (carries the session cookie)
        traj = _fetch_session_trajectory(page, self.base)     # see 3.2
        answer = _last_assistant_message(chat_messages)
        report = verify_task(self.verifier, traj, answer)
        done = report["passed"] or _agent_signalled_done(chat_messages)
        reward = 1.0 if report["passed"] else 0.0
        # expose the per-macro breakdown (MiniWeb's differentiator) in info
        return reward, done, "", {"by_macro": report["by_macro"]}

    def teardown(self):
        pass    # server is shared; nothing per-task to tear down
```

### 3.2 The validation bridge (reuse everything)

`run_agent_verify.build_trajectory(base)` already assembles the trajectory from the three
admin endpoints and runs `synthesize_network_events`. It currently fetches with `?all=1`
(**all** sessions) because the native runner uses one-server-per-task. For BrowserGym's
shared server you need a **session-scoped** fetch — do it *through the page* so the browser's
`_data_overlay_sid` cookie selects the right session:

```python
def _fetch_session_trajectory(page, base):
    # page.request carries the browser context cookies → server returns THIS session only
    rec = page.request.get(f"{base}/_admin/record").json().get("entries", [])
    log = page.request.get(f"{base}/_admin/log").json().get("entries", [])
    bcn = page.request.get(f"{base}/_admin/beacon").json().get("entries", [])
    traj = _assemble(rec, log, bcn)          # same shape as build_trajectory()
    return synthesize_network_events(traj)
```

> Required tweak (~1 day): make the non-`?all` `/_admin/{log,record,beacon}` return only the
> caller's session. `_request_logs` / `_action_beacons` are already keyed by session id, so
> this is a small change in `app/__init__.py`.

### 3.3 Task registration (gym IDs)

```python
# browsergym/miniweb/src/browsergym/miniweb/__init__.py  (sketch)
from browsergym.core.registration import register_task
import glob, pathlib

for tf in sorted(glob.glob("data/annotations/*/*/task.json")):
    d = pathlib.Path(tf).parent
    if not (d / "verifier.json").exists():
        continue
    task_id = f"{d.parent.name}/{d.name}"           # "Minh/e-commerce_224c4c"
    gym_id = task_id.replace("/", ".")
    # NOTE: register_task auto-prepends "browsergym/" — do NOT include it yourself.
    # Signature (browsergym-core 0.14.3):
    #   register_task(id, task_class, task_kwargs={}, default_task_kwargs={},
    #                 nondeterministic=True, ...)
    register_task(f"miniweb.{gym_id}", MiniWebTask,
                  task_kwargs={"task_id": task_id})
```

Result: `gym.make("browsergym/miniweb.Minh.e-commerce_224c4c")`.

### 3.4 AgentLab benchmark object

The `Benchmark` object lives in **browsergym** (`bgym`), not AgentLab — AgentLab's
`make_study(benchmark=...)` accepts a `bgym.Benchmark` object (or a string name in
`DEFAULT_BENCHMARKS`). Build a `Benchmark` whose `env_args_list` enumerates the 254 gym IDs.

```python
# confirmed against browsergym-experiments 0.14.3 / agentlab 0.4.2
from browsergym.experiments.benchmark import Benchmark        # aka bgym.Benchmark
from browsergym.experiments.loop import EnvArgs
from browsergym.core.action.highlevel import HighLevelActionSetArgs  # confirm exact path

miniweb_benchmark = Benchmark(
    name="miniweb",
    high_level_action_set_args=HighLevelActionSetArgs(subsets=["bid"]),   # bid-based actions
    is_multi_tab=False,
    supports_parallel_seeds=True,
    env_args_list=[EnvArgs(task_name=f"browsergym/miniweb.{tid.replace('/', '.')}",
                           max_steps=30)
                   for tid in ALL_TASK_IDS],
    backends=[],   # see note below
)
```

`Benchmark` fields (0.14.3): `name`, `high_level_action_set_args`, `is_multi_tab`,
`supports_parallel_seeds`, `env_args_list: list[EnvArgs]`, `backends: list[BenchmarkBackend]`,
`task_metadata: Optional[pd.DataFrame]` (cols `task_name`, `depends_on`). Helper methods
`subset_from_list/glob/task_ratio(...)` let you slice sub-benchmarks (e.g. a per-site split).

> **`backends` note:** the field is an enum of platforms (`miniwob`, `webarena`, …) AgentLab
> uses for setup/dependency checks. Two options: (a) run with `make_study(...,
> ignore_dependencies=True)` and leave `backends=[]`, or (b) add a `miniweb` backend value in
> browsergym. Start with (a). Provide `task_metadata` if you want AgentLab's dependency/parallel
> handling.

Then run — note `make_study(agent_args, benchmark, ...)` (agent first). Standardize on a
**modern** model: AgentLab 0.4.2 ships presets only up to `AGENT_GPT5_MINI`, so pin a current
GPT (e.g. gpt-5.5) with a custom `GenericAgentArgs` — model names pass straight to the OpenAI
API, no local registry gate:

```python
from agentlab.experiments.study import make_study
from agentlab.agents.generic_agent.agent_configs import GenericAgentArgs, FLAGS_GPT_4o
from agentlab.llm.chat_api import OpenAIModelArgs

# The reference config your leaderboard reports on — pin the exact model.
AGENT_GPT_5_5 = GenericAgentArgs(
    chat_model_args=OpenAIModelArgs(
        model_name="gpt-5.5",     # ← current model, not the dated 4o
        max_new_tokens=2000,      # default is 100 — far too low for CoT + an action; raise it
        temperature=0.0,
    ),
    flags=FLAGS_GPT_4o,           # reuse a tuned obs/prompt flag set (rename is cosmetic), or define your own
)

study = make_study(agent_args=[AGENT_GPT_5_5],
                   benchmark=miniweb_benchmark,
                   ignore_dependencies=True,
                   parallel_servers=None)   # one shared MiniWeb server handles parallel envs
study.run(n_jobs=8)
```

`FLAGS_GPT_4o` is just the *observation/prompt flag set* (AXTree pruning, CoT, action history,
etc.), independent of the model — reuse it with any model or fork your own `GenericPromptFlags`.
For a quick mini baseline, `from agentlab.agents.generic_agent import AGENT_GPT5_MINI` is ready
to use.

`make_study(agent_args, benchmark, logging_level, logging_level_stdout, suffix, comment,
ignore_dependencies=False, parallel_servers=None)`. `parallel_servers` is for
WebArena-style one-instance-per-worker — MiniWeb doesn't need it (per-session isolation on one
server), so leave it `None`.

---

## 4. Server & session management

- **One shared server** (recommended): start `evaluation/server.py::start_server` once, set
  `MINIWEB_URL`, run N parallel envs. Per-session overlay isolation keeps them separate.
  Verified this session: a fresh session does not see another session's mutations.
- **Offline**: BrowserGym launches its own Chromium — add the same
  `--host-resolver-rules=MAP * ~NOTFOUND , EXCLUDE localhost` flag to BrowserGym's browser
  launch args so the agent can't reach the outside web.
- **Reset**: `setup()` hits `/_reset_data` (GET) — session-scoped, so it's safe under parallel
  envs. Do **not** call `db.reset_all()` mid-run (it wipes every session).
- **DB hygiene**: overlays accumulate across episodes (harmless, isolated). Run
  `db.reset_all()` only when no eval is active.

---

## 5. Observation & action space

No custom space needed — MiniWeb sites are plain HTML, so BrowserGym's defaults work:
- **Observation**: AXTree / HTML / screenshot (the field-standard obs; cleaner for LLMs than
  raw DOM). This replaces browser-use's own DOM serialization.
- **Action**: BrowserGym's bid-based `HighLevelActionSet` (`click(bid)`, `fill(bid, text)`, …),
  optionally coordinate actions. The verifier keys off action *kind* + the **backend request**,
  so bid actions grade fine as long as real clicks/typing reach the server.

---

## 6. Risks & mitigations

| Risk | Mitigation |
|---|---|
| **Frontend beacons** — `recorder.js` may not capture every BrowserGym-driven action | The verifier is **backend-gated** (frontend is advisory); backend requests are captured server-side regardless. Grading stays correct. Verify beacon parity on a sample. |
| **Session scoping** — `?all=1` mixes sessions on a shared server | Add session-scoped `/_admin/*` (small change; logs already keyed by sid) and fetch via `page.request`. |
| **Answer mapping** — `report_information` tasks need the agent's final answer | Map `verify_task(answer=chat_messages[-1])`; AgentLab agents emit a final `send_msg_to_user`. |
| **Sync vs async** — BrowserGym task API is sync Playwright | `verify_task` / `synthesize_network_events` are sync — no change. Only the trajectory fetch moves to `page.request`. |
| **Two harnesses** — native `run_agent_verify` + BrowserGym | They share `verify_task`, so grading can't drift. Keep native for fast iteration, BrowserGym for standard reporting. |
| **AgentLab `Benchmark` API drift** | Pin to a specific AgentLab version; confirm `Benchmark` / `EnvArgs` signatures before building. |

---

## 7. Phased plan

1. **PoC (≈1 wk):** `MiniWebTask` + registry for ~10 tasks; session-scoped admin fetch;
   run one gym env manually; confirm `verify_task` parity vs `run_agent_verify` on those tasks.
2. **Full port (≈1 wk):** register all 254; AgentLab `Benchmark`; offline flag on BrowserGym;
   parallel envs on one server.
3. **Parity + hardening (≈3–5 days):** run all 254 through AgentLab `GenericAgent`, reconcile
   pass/fail against the native runner, fix beacon/scoping gaps, document the standard config.

---

## 8. Which agent to report with

`browser-use` (current harness) vs AgentLab `GenericAgent`:

- `browser-use` is a **product-grade agent** — often a stronger *task-completer* out of the
  box (multi-action, tuned DOM handling), but its loop is opaque/hard to ablate and its scores
  only compare to other browser-use runs.
- AgentLab `GenericAgent` is the **research reference** — standardized AXTree obs + bid actions,
  published prompt ablations, reproducible studies, xray debugging. It's the agent the field
  cites for WebArena/WorkArena.

For a benchmark you want *comparable* numbers, report with **AgentLab `GenericAgent`** (+ 1–2
LLM backends) so "model X scores N% on MiniWeb" means the same thing as a WebArena score.
Keep `browser-use` as the internal capability ceiling / fast-iteration harness. The gap between
the two is itself a useful datapoint.

**MiniWeb's differentiator survives the port:** `verify_task`'s `by_macro` output (exposed in
`validate()`'s `info`) becomes a **per-skill reward breakdown** — skill decomposition that no
existing BrowserGym benchmark offers.

---

## 9. Pinned versions & confirmed APIs (as of 2026-08)

Build against these exact versions — the APIs below are confirmed from their source.

| Package | Version | `requires_python` |
|---|---|---|
| `browsergym` / `browsergym-core` | **0.14.3** | `>3.10` / `>3.9` |
| `browsergym-experiments` (`Benchmark`, `EnvArgs`) | **0.14.3** | — |
| `agentlab` | **0.4.2** | `>=3.11,<3.13` |
| Python | **3.11** | matches the `miniweb` conda env (3.11.15) ✓ |

Confirmed interfaces:
- **`AbstractBrowserTask`** (browsergym-core): `setup(page) -> (goal: str, info: dict)`,
  `validate(page, chat_messages) -> (reward: float, done: bool, message: str, info: dict)`,
  `teardown() -> None`. Class attrs: `viewport` (1280×720), `slow_mo` (1000ms), `timeout`
  (5000ms), `locale`, `timezone_id`. Uses **sync** Playwright.
- **`register_task(id, task_class, task_kwargs={}, default_task_kwargs={}, nondeterministic=True, …)`**
  — auto-prepends `"browsergym/"` to `id` (do NOT include it yourself).
- **`bgym.Benchmark`** lives in `browsergym.experiments.benchmark` (fields listed in §3.4);
  `EnvArgs` in `browsergym.experiments.loop`.
- **`make_study(agent_args, benchmark, …, ignore_dependencies=False, parallel_servers=None)`**
  (agentlab) — `benchmark` accepts a `bgym.Benchmark` or a name in `DEFAULT_BENCHMARKS`.

Still to confirm against your install (not blockers, just paths/values):
- Exact import path of `HighLevelActionSetArgs` (action-set config) in 0.14.3.
- Whether to add a `miniweb` `BenchmarkBackend` enum value or run with `ignore_dependencies=True`.
- The `GenericAgent` config you'll standardize on — pin a **current** model via
  `OpenAIModelArgs(model_name="gpt-5.5", max_new_tokens≈2000)` (not the dated `AGENT_4o` preset;
  0.4.2's newest OpenAI preset is only `AGENT_GPT5_MINI`), plus its WebArena number under that
  same model so your reported baseline is precise.

---

## Post-PoC cleanup (2026-08-12)

What the cleanup pass changed (see `browsergym_miniweb/`):

- **Start URL**: multi-site tasks now start on the **portal directory `/`** — crossing
  sites is part of the task, so neither site's deep page is a fair start. Single-site
  tasks still start where the human recording began (`_start_url` in `task.py`).
- **Offline sandbox is now visible, not a DNS dead end**: in addition to the Chromium
  `--host-resolver-rules` flag, every browser context (patched at `Browser.new_context`,
  so it also covers `agentlab-assistant`'s openended task) routes external *document*
  navigations to MiniWeb's **`/_blocked`** page ("external pages not allowed, tasks are
  completable inside MiniWeb", 3s auto-redirect to the portal) and aborts external
  subresources. Verify visually: run `agentlab-assistant` against a running server and
  ask the agent to visit any external site.
- **Model-agnostic agent, visual by default**: `miniweb_agent(model)` routes via
  `helpers.llm.resolve_provider` — Anthropic/OpenAI native args, Gemini/Ollama/Groq via
  LiteLLM — with `FLAGS_MINIWEB` (the tuned AXTree flag set + screenshot + SOM; the old
  `AGENT_4o` preset was just a name, nothing gpt-specific). `visual=False` for text-only
  models. The `OPENAI_BASE_URL` ollama hack is gone.
- **Runner**: `python -m browsergym_miniweb.run_study --model … --tasks …` owns the
  server lifecycle (replaces `scratchpad/bg_agentlab_run.py`).
- **Auth tasks**: `MiniWebTask.setup` resets with `/_reset_data?no_autologin=1` when the
  verifier contains `authenticate_by_form`, so the session starts logged out even on a
  shared server (per-session equivalent of `MINIWEB_NO_AUTOLOGIN`).
- **Pins**: aligned to the installed `browsergym-core==0.14.2`; `agentlab==0.4.2` is a
  real dependency now (imported at module top level).

Known offline casualty (pre-existing, affects every harness): **map-services** loads
Leaflet from unpkg and basemap tiles from carto CDNs — offline, the map never renders,
so pan/zoom/marker tasks there are not completable. Fix is to vendor Leaflet + tiles
locally (out of scope for this pass).
