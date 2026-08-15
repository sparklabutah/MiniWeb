# annotation/

The annotation + verifier-authoring tooling — a Flask blueprint served at
`/annotate` (login at `/annotate/login`). This is where humans record task
trajectories, tag them with macros, and build/review the per-task verifiers.

| File | Role |
|---|---|
| `app.py` | The `/annotate` blueprint: the **Annotate**, **Verifier Builder** (`/verify`), **Verifier Review** (`/verifiers`), **Macro Templates**, **Coverage**, and **Graph** pages, plus their JSON APIs (suggest tags, suggest/run task verifier, macro registry CRUD, screenshots). |
| `storage.py` | File-based task storage — `data/annotations/<annotator>/<task_id>/` (`task.json`, `trajectory.json`, `verifier.json`, screenshots). `list_tasks`, `load_task`, `save_task`, trash/delete. |
| `macros.py` | The canonical macro registry loader (`data/macros.yaml`): base macros + reasoning ops, alias canonicalization (`canon`), descriptions. |
| `macro_templates.py` | Per-macro verifier **templates** (`data/macro_templates.yaml`) — AND/OR trees of check primitives with OPEN slots; `build_task_draft`, `collect_open_slots`, `fill_open`, `inject_qa_leaf`. |
| `macro_locations.py` | Per-site macro→UI-location data (`data/macro_locations.yaml`) — drives coverage/sampling. |
| `site_affinities.py` | Cross-site event-flow groups (for multi-site task graphs). |
| `observations.py` | Save-time **trigger** for the observation-reconstruction pipeline. |
| `process_annotations.py`, `backfill_observations.py`, `repair_form_state.py` | The observation/trajectory reconstruction pipeline (runs at save time via `observations.py`, or standalone `python -m annotation.process_annotations` to catch up). Relocated here from `scripts/` because they're app runtime code. |

The macro model, review policy, and verifier design live in `docs/macro_system.md`
and the root `CLAUDE.md`.
