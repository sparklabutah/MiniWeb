# evaluation/

Runs browser agents on the annotated MiniWeb tasks and grades them. The harness is
[browser-use](https://github.com/browser-use/browser-use). Grading (LLM macro judge by default,
per-task verifier alongside) is described in [docs/VERIFIER_DESIGN.md](../docs/VERIFIER_DESIGN.md).

Use the conda env: `~/.conda/envs/miniweb/bin/python` (written `python` below).
Gemini judge calls need Vertex credentials in `.env`.

## Files

| File | Role |
|---|---|
| `run_agent_verify.py` | One agent on one task: start a MiniWeb server, run the agent, collect the trajectory, grade it, write the artifacts. |
| `run_study.py` | A study from one config: N models x M tasks x repeats, with parallel workers, resume and a summary. |
| `agents.py` | `AgentRunner` protocol, `BrowserUseAgent`, `MockAgent` (no LLM, no browser), `ChatLLM` (routes the agent through `helpers.llm`), `build_agent(model)` factory and `MODEL_ALIASES`. |
| `macro_judge.py` | The LLM macro judge (default grader); also a CLI to judge a whole study. |
| `verifiers.py`, `evidence_checks.py` | The deterministic verifier: `verify_task` and the check types. |
| `trajectory.py` | `merge_server_log` (adds the server request log to the recorder stream), `filter_log_to_window`, `extract_final_reasoning`. |
| `server.py` | Start, wait for and stop a MiniWeb server on a port. |
| `xray.py` | Web viewer for result folders. |
| `action_vocabulary.py` | The canonical recorded action types. |
| `generate_fixtures.py` | Lists the real files of the simulated file system (`filesystem/`) that uploads use. |
| `configs/` | Study configs. `qwen35_4b_all_x3.json` is the current reference config. `example.yaml` uses the old `run_agent_verify --config` format and no longer runs. |
| `results/` | Run outputs (git-ignored). |

## One task

```bash
python evaluation/run_agent_verify.py --task-id crm_bf9346 --model mock --grader verifier   # pipeline smoke test, no LLM
python evaluation/run_agent_verify.py --task-id Minh/banking_357033 --model gemini-flash --obs visual
python evaluation/run_agent_verify.py --task-id Minh/qa-knowledge_471ddc --no-headless      # watch the browser
```

| Flag | Default | Meaning |
|---|---|---|
| `--task-id` | (required) | `<task_id>` or `<annotator>/<task_id>` |
| `--model` | `gemini-flash` | model id, an alias from `agents.MODEL_ALIASES`, or `mock` |
| `--obs` | `axtree` | `visual` = screenshots (`use_vision=True`); `axtree` / `html` = browser-use's text DOM |
| `--native-llm` | off | use browser-use's provider-native LLM class instead of `ChatLLM` |
| `--start-from` | `recorded` | `recorded` = first page of the human recording; `starting_url` = the task's field |
| `--grader` | `judge` | `judge` = macro judge decides, verifier reported; `verifier` = verifier only |
| `--port` | `8099` | server port |
| `--max-steps`, `--timeout` | `50`, `300` | step and wall-clock limits |
| `--no-headless` | off | show the browser |
| `--out` | `evaluation/results/agentverify_<task>_<model>_<time>/` | artifact folder |

What a run does:

1. Starts a fresh server. Tasks with `authenticate_by_form` start it with
   `MINIWEB_NO_AUTOLOGIN=1` so the agent begins logged out.
2. Picks the start page. A single-site task starts where the human recording started. A
   multi-site task starts at the portal home (`/`), and the prompt ends with the names and URLs
   of the apps involved (`app_directory`; recorded as `prompt_extra`).
3. Runs the agent, then pulls `/_admin/record` (recorder actions and observations) and
   `/_admin/log` (server requests) into one trajectory.
4. Grades with the verifier and, with `--grader judge`, the macro judge.
5. Writes `result.json`, `trajectory.json`, `server_log.json`, `verify_report.json`,
   `judge_report.json`, plus browser-use's `history.json`, `screenshots/` and `conversations/`.

## A study

```bash
python evaluation/run_study.py --config evaluation/configs/qwen35_4b_all_x3.json --dry-run   # print the plan
python evaluation/run_study.py --config evaluation/configs/qwen35_4b_all_x3.json --workers 8
python evaluation/run_study.py --summarize-only evaluation/results/qwen35_4b_all_x3
```

Config (YAML or JSON):

```yaml
name: qwen35_4b_all_x3
out: evaluation/results/qwen35_4b_all_x3
tasks: all                  # or ["Minh/banking_357033", "site:dating", ...]
exclude: []
resume: true                # skip episodes that already have result.json
repeats: 3
workers: 12                 # worker i uses port episode.port + i and every N-th episode
episode:
  max_steps: 30
  timeout: 1800
  obs: visual
  start_from: recorded
  headless: true
  port: 8200
  browser: ~/.cache/ms-playwright/chromium-1117/chrome-linux/chrome
  # grader: judge           # or verifier
models:
  - label: qwen3.5-4b
    provider: ollama        # openai | anthropic | gemini | ollama | huggingface | openai-compatible
    model: qwen3.5:4b-t2
    host: http://127.0.0.1:11435
    hosts: [http://127.0.0.1:11435, http://127.0.0.1:11436]   # optional; worker i uses hosts[i % n]
```

Episode defaults: `max_steps 30`, `timeout 600`, `obs visual`, `start_from recorded`,
`headless true`, `port 8099`. Model keys: `temperature`, `max_tokens`, `base_url`,
`api_key_env`. API keys come from `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`,
`GOOGLE_API_KEY` / `GEMINI_API_KEY`, `HF_TOKEN`.

Each episode lands in `<out>/<label>__<annotator>-<task_id>[__r<repeat>]/`. Workers log to
`<out>/worker_<i>.log`. The summary (overall pass rate, by chain length, by macro) is printed
and saved to `<out>/study_summary.json`.

To re-judge a finished study, see `macro_judge.py --results` in
[VERIFIER_DESIGN.md](../docs/VERIFIER_DESIGN.md#llm-macro-judge).

## Harness behaviour that affects results

- **Offline.** Chromium runs with `--host-resolver-rules=MAP * ~NOTFOUND , EXCLUDE localhost`;
  only the local server is reachable.
- **Pinned browser.** Set `episode.browser` or `MINIWEB_BROWSER`. Playwright's Chrome for
  Testing 149 never finishes loading http pages headless on the lab machine; Chromium build
  1117 works.
- **Clipboard.** Headless pages are never focused, so site Copy buttons failed.
  `BrowserUseAgent` grants clipboard permissions and emulates focus on every step.
- **Uploads.** browser-use's `upload_file` shortcut is removed. The agent clicks the file
  input and picks the file in MiniWeb's in-page file picker, as a person would.
- **Logs.** The server request log is stamped in UTC and filtered to the episode's time window.

Results from before these dates are not comparable for the affected tasks:

| Date | Change | Affected tasks |
|---|---|---|
| 2026-09-27 | recorder kept observations of pages over 64 KB | checks on large pages |
| 2026-09-27 | clipboard fix | copy tasks |
| 2026-09-28 | Leaflet served locally (maps were blank offline) | map-services pan/zoom, markers, routes |
| 2026-09-28 | uploads through the file picker | the 25 upload tasks |

Known gap: the recorder cannot tell a site Copy button from an agent writing the clipboard
itself with a script. Value checks and the judge catch most of these.

## Latest reference run

`evaluation/results/qwen35_4b_all_x3`: qwen3.5:4b (ollama), browser-use, visual, 376 tasks x 3,
re-graded 2026-09-27 (judge v3, `macro_judge_flash_v3.jsonl`):

| Grader | pass@1 | pass@3 | all 3 |
|---|---:|---:|---:|
| macro judge (gemini-3.5-flash) | 41.8% | 58.0% | 26.9% |
| verifier | 41.3% | 54.8% | 26.9% |

Episode-level agreement between the two: 92.4%. The run predates the 2026-09-28 map and upload
changes.

## X-Ray viewer

```bash
python evaluation/xray.py --port 8125
```

Browses `evaluation/results/<run>/<episode>/`: instruction, expected vs agent answer,
pass/fail, the verifier check tree from `verify_report.json`, step screenshots with the
actions taken, any `note.md`, and a feedback box saved to `feedback.md` in the episode folder.

## Other harnesses

- `webmix/evaluate.py` is the WebMix agent's MiniWeb evaluator (vLLM-served LoRA arms on the
  same browser-use harness). See `webmix/README.md`.
- `browsergym_miniweb/` runs the tasks under BrowserGym + AgentLab, verifier-only. See
  [docs/BROWSERGYM_AGENTLAB_MIGRATION.md](../docs/BROWSERGYM_AGENTLAB_MIGRATION.md).
