# Documentation index

Start with the root [README.md](../README.md) for what MiniWeb is and how to run it.

## Project docs (`docs/`)

| Doc | Read it for |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | How the app, sites, data layer and overlay, recorder, annotation, evaluation, datagen and WebMix fit together |
| [RESEARCH.md](RESEARCH.md) | Paper claim, research questions, current results, evaluation protocols (normalization, grading) |
| [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md) | Working experiment plan for the paper (RQ1–RQ4): arms, commands, decisions, compute and cost |
| [figures/teaser/](figures/teaser/) | Paper Fig. 1 (single column): `capture.py` takes the site screenshots from a local server, `make_teaser.py` builds `teaser.pdf`/`.png` |
| [figures/construction/](figures/construction/) | Construction figure as a tree (skills → websites → tasks) on the SnapLink example task, with its segmented demo and a real Qwen3.5-4B per-primitive verdict: `construction.pdf` (single column) and `construction_2col.pdf` (double column, all 46 primitives listed); `capture.py` + `make_construction.py` |
| [DATA_LICENSES.md](DATA_LICENSES.md) | License audit of the 21 public-data sources behind the sites (stated license, upstream terms, release implications) |
| [macro_system.md](macro_system.md) | Macros and reasoning operations, the registry `data/macros.yaml`, per-site locations, tagging conventions |
| [VERIFIER_DESIGN.md](VERIFIER_DESIGN.md) | Per-task verifiers, the LLM macro judge, validation gates |
| [BROWSERGYM_AGENTLAB_MIGRATION.md](BROWSERGYM_AGENTLAB_MIGRATION.md) | The secondary BrowserGym + AgentLab harness (`browsergym_miniweb/`) |
| [KNOWN_ISSUES.md](KNOWN_ISSUES.md) | Known site and data bugs and repo hygiene items (recorded, not fixed, while the dataset is frozen) |
| [CHANGELOG.md](CHANGELOG.md) | What changed and when. The only place for history. |

## Package READMEs

| Package | Contents |
|---|---|
| [app/](../app/README.md) | Flask app, `app.db` and session overlays, `/_admin` grading endpoints, injected scripts, simulated file system |
| [sites/](../sites/README.md) | Site anatomy and conventions. Each site also has `sites/<site>/doc/README.md`. |
| [annotation/](../annotation/README.md) | `/annotate` tool: recording, Verifier Builder, Task Review, Macro Browser |
| [evaluation/](../evaluation/README.md) | Agent runner, studies, verifiers, macro judge, results viewer |
| [datagen/](../datagen/README.md) | Per-macro training-data pipeline and control kinds |
| [webmix/](../webmix/README.md) | Replay, augmentation, LoRA training, vLLM serving, planner agent, benchmark runs |
| [helpers/](../helpers/README.md) | LLM routing and token accounting, geo, auth, security |
| [data/](../data/README.md) | What lives under `data/` and what is tracked |
| [tests/](../tests/README.md) | Test suite and what each file guards |
| [method/hyperWeb/](../method/hyperWeb/README.md) | Separate sub-project with its own docs |

## Rules for contributors and coding agents

- [CLAUDE.md](../CLAUDE.md): the always-loaded core rules (data access, macro registry, never-do list)
- [AGENTS.md](../AGENTS.md): working conventions for coding agents
- [CONTRIBUTING.md](../CONTRIBUTING.md): how to record tasks, change sites or macros, and send code changes

## Local files (not tracked by git)

`refined_macro_set.csv` and the two `.pptx` decks are older snapshots and may be out of date.
`data/macros.yaml` is the authoritative macro list, and RESEARCH.md has the current numbers.
