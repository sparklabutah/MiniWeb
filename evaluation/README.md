# evaluation/

The browser-agent evaluation harness — launch an agent against a task, capture
its trajectory, and grade it.

| File | Role |
|---|---|
| `run_agent_verify.py` | **The canonical runner.** Runs a browser-use agent against an annotated task and grades its trajectory against the task's macro `verifier.json`. Flags: `--model` (any id/alias or `mock`), `--obs visual\|axtree`, `--grade verifier\|judge\|both`, `--native-llm`, `--start-from recorded\|starting_url`. Reports per-macro PASS/FAIL + LLM token usage. |
| `run_eval.py` | Site-based batch eval: runs `sites/<site>/tasks.json` with a parallel worker pool, grades with the per-site `sites/<site>/verifiers.py` state checkers (or `--judge`). |
| `agents.py` | `AgentRunner` protocol; `BrowserUseAgent` (browser-use wrapper), `MockAgent` (no LLM/browser), `ChatLLM` (routes the agent's LLM through `helpers.llm`), and **`build_agent(model)`** — the single shared factory every runner uses. |
| `verifiers.py` | `verify_task(spec, trajectory, answer)` + the `Check` primitives (`action_included`, `request_made`, `page_visited`, `qa_answer`, `answer_grounded`, `reasoning_contains`). Grades a macro verifier tree against a trajectory. Deterministic (`qa_answer` uses substring `contains` mode). |
| `trajectory.py` | `synthesize_network_events` — reconstruct GET navs / dropped POSTs from actions so grading sees the full request stream. |
| `judge.py` | `judge_task` — LLM-as-judge on `expected_outcome` (via `helpers.llm`); used by `--grade judge`. |
| `tasks.py` | Task loading/filtering + `run_task` (the run-then-grade unit for `run_eval`). |
| `server.py` | Start/stop the MiniWeb server for a run. |
| `action_vocabulary.py` | The canonical action-type list (shared with the verifier check schema). |
| `generate_fixtures.py` | Real files the agent can attach to `<input type=file>`. |

Grade an agent on a task:
```
python evaluation/run_agent_verify.py --task-id job-sites_3c5414 --model gemini-3.1-pro-preview --grade both
python evaluation/run_agent_verify.py --task-id crm_bf9346 --model mock          # pipeline smoke test
```

## Config mode — a matrix of agents × tasks
Run several models over several tasks in one shot:
```
python evaluation/run_agent_verify.py --config evaluation/configs/example.yaml
```
```yaml
agents:
  - {model: gemini-3.1-pro-preview, obs: visual}
  - {model: gpt-5, obs: axtree}
  - {model: ollama/llama3.3, label: llama-local}
tasks:
  - Minh/job-sites_3c5414
  - "site:banking"           # expands to every annotated banking task
grade: verifier              # + max_steps/timeout/headless defaults; agents may override
```
Prints a pass/fail matrix + per-agent pass rate and token totals, and writes `results.json`
to `evaluation/results/config_<ts>/`. See `evaluation/configs/example.yaml`.
