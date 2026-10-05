# BrowserGym + AgentLab harness

`browsergym_miniweb/` registers every MiniWeb task as a
[BrowserGym](https://github.com/ServiceNow/BrowserGym) environment and runs it with
[AgentLab](https://github.com/ServiceNow/AgentLab)'s `GenericAgent`, so MiniWeb can be scored with
the same harness as WebArena and WorkArena.

It is a secondary harness. The main one is browser-use (`evaluation/run_study.py`, see
`evaluation/README.md`). The BrowserGym package was last changed on 2026-08-16, so it grades
with the **verifier only** (no macro judge) and lacks the September browser-use harness fixes
(clipboard focus, uploads through the file picker, the app list in multi-site prompts).

## Install

`requirements-browsergym.txt`: `browsergym-core==0.14.2`, `gymnasium==1.3.0`, `agentlab==0.4.2`.
browsergym-core pins `playwright==1.44`. The `miniweb` conda env currently has these installed
next to browser-use.

## Run

```bash
cd /home/u1653932/Documents/MiniWeb
~/.conda/envs/miniweb/bin/python -m browsergym_miniweb.run_study --model claude-sonnet-4-5 --tasks 3
~/.conda/envs/miniweb/bin/python -m browsergym_miniweb.run_study --model ollama/qwen3.5:27b \
    --tasks Minh/e-commerce_224c4c --max-steps 25 --no-headless
~/.conda/envs/miniweb/bin/python -m browsergym_miniweb.run_study --tasks all --jobs 4
```

| Flag | Default | Meaning |
|---|---|---|
| `--model` | `helpers.llm` `DEFAULT_MODEL` (`$LLM_MODEL`) | `claude-*`, `gpt-*`, `gemini-*` or `ollama/<name>` |
| `--tasks` | `1` | `all`, a count (first N), or comma-separated `annotator/task_id` |
| `--max-steps` | `15` | step limit per episode |
| `--headless` / `--no-headless` | headless | show the browser |
| `--text` | off | text-only agent (AXTree, no screenshot or set-of-marks) |
| `--port` | `8124` | the MiniWeb server the runner starts and stops |
| `--jobs` | `1` | parallel episodes (`ray` backend when above 1) |

Gym ids are `browsergym/miniweb.<annotator>.<task_id>`, registered on `import browsergym_miniweb`
for every task with a `verifier.json`. Point tasks at a server with `MINIWEB_URL` (default
`http://localhost:8099`).

## How it works

| File | Role |
|---|---|
| `__init__.py` | registers the gym ids; forces Chromium offline (`--host-resolver-rules`); routes external page loads to MiniWeb's `/_blocked` page and aborts external subresources; adds `report_answer` and `finish_task` to the `chat` action subset |
| `task.py` | `MiniWebTask`: `setup` resets the session (`/_reset_data`, with `?no_autologin=1` for `authenticate_by_form` tasks) and opens the start page; `validate` fetches this session's trajectory through the page and runs `verify_task` |
| `actions.py` | `report_answer(answer)` and `finish_task()`, marked `[FINAL ANSWER]` / `[TASK COMPLETE]` |
| `agentlab_study.py` | `make_benchmark` (action subsets `chat` + `bid`, no `nav`/`goto`), `miniweb_agent` (`GenericAgentArgs` with `FLAGS_MINIWEB`: AXTree + screenshot + set-of-marks, 28k prompt tokens), model routing |
| `run_study.py` | the CLI above; owns the server lifecycle |

- **Start page**: a multi-site task starts at the portal home `/`; a single-site task starts
  where the human recording started.
- **Navigation**: through the portal's own UI (search box, site tiles, tab bar); there is no
  `goto` action.
- **Session isolation**: one server serves many parallel environments. `/_admin/record`,
  `/_admin/log` and `/_admin/beacon` are fetched with the browser's own cookie, so each episode
  sees only its own session.
- **Ending an episode**: the episode ends when the verifier passes or the agent calls
  `finish_task` / `report_answer`; otherwise BrowserGym truncates at the step limit. The graded
  answer is the `report_answer` value, or else all the agent's messages joined.
- **Reward** is 1.0 when the verifier passes. `info` carries `by_macro` (per-macro pass/fail)
  and `ended_by` (`verifier` or `agent`).

To watch the offline sandbox bounce external visits to `/_blocked`:

```bash
agentlab-assistant --agent_config browsergym_miniweb.agentlab_study.MINIWEB_ASSISTANT_AGENT \
    --start_url http://localhost:8099/
```
