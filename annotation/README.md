# annotation/

The annotation + verifier-authoring tooling — a Flask blueprint served at
`/annotate` (login at `/annotate/login`). This is where humans record task
trajectories, tag them with macros, and build/review the per-task verifiers.

| File | Role |
|---|---|
| `app.py` | The `/annotate` blueprint: the **Annotate**, **Verifier Builder** (`/verify`), **Verifier Review** (`/verifiers`), **Coverage**, and **Graph** pages, plus their JSON APIs (suggest tags, suggest/run task verifier, macro registry CRUD, screenshots). |
| `storage.py` | File-based task storage — `data/annotations/<annotator>/<task_id>/` (`task.json`, `trajectory.json`, `verifier.json`, screenshots). `list_tasks`, `load_task`, `save_task`, trash/delete. |
| `macros.py` | The canonical macro registry loader (`data/macros.yaml`): base macros + reasoning ops, alias canonicalization (`canon`), descriptions. |
| `verifier_scaffold.py` | Universal per-task verifier **scaffolding** — every macro gets the same 3 canonical checks (page_visited + FE affordance + backend gate), all params OPEN, pinned by the annotator in the builder; plus the shared task-graph helpers (`scaffold_task`, `collect_open_slots`, `fill_open`, `inject_qa_leaf`, `refresh_expected`). |
| `macro_browser.py` | Read-only data for the **Macro Browser** (`/annotate/macro-browser`): every tagged macro instance with its gold span, and a task's actions paired with their screenshots (or a page outline when none was recorded). |
| `macro_locations.py` | Per-site macro→UI-location data (`data/macro_locations.yaml`) — drives coverage/sampling. |
| `site_affinities.py` | Cross-site event-flow groups (for multi-site task graphs). |
| `observations.py` | Save-time **trigger** for the observation-reconstruction pipeline. |
| `process_annotations.py`, `backfill_observations.py`, `repair_form_state.py` | The observation/trajectory reconstruction pipeline (runs at save time via `observations.py`, or standalone `python -m annotation.process_annotations` to catch up). Relocated here from `scripts/` because they're app runtime code. |

The macro model, review policy, and verifier design live in `docs/macro_system.md`
and the root `CLAUDE.md`.

The local [September macro review](../data/task_review_macros_2026-09-23/README.md)
documents all 407 tasks. The verifier page shows each task’s AI macro review,
distinct repeated instances, and whether span boundaries are historical.
