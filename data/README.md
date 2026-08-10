# data/

Runtime data and the dataset. **Most of this directory is gitignored** (`data/*`)
— only the static config the app deploys with is tracked: `reviews/`,
`macros.yaml`, `macro_locations.yaml`, and this README.

| Item | Contents | Tracked? |
|---|---|---|
| `trimmed_miniweb.db` | The per-site SQLite dataset every site reads/writes (via `app.db`). Modified post-build — **do not** re-run `build_db.py`. | no |
| `macros.yaml` | The canonical macro registry (base macros + reasoning ops + aliases). Source of truth loaded by `annotation/macros.py`. | **yes** |
| `macro_locations.yaml` | Per-site macro→UI-location map (drives coverage/sampling). | **yes** |
| `macro_templates.yaml` | Per-macro verifier templates (AND/OR check trees). | no |
| `annotations/` | Recorded tasks: `<annotator>/<task_id>/` with `task.json`, `trajectory.json`, `verifier.json`, screenshots. | no |
| `annotations-bak/` | Backup snapshot of the annotations. | no |
| `backups/` | Timestamped tarballs of task/verifier state taken before each migration/relaxation pass. | no |
| `reviews/` | Per-site free-form review feedback. | **yes** |
| `enwikinews/`, `academic-paper-db.json`, `site_feedbacks/`, `static/` | Source/aux data for specific sites. | no |

**Persistence (deploy):** point the macro YAMLs at a persistent volume via
`MINIWEB_MACRO_DIR` (or per-file `MINIWEB_MACROS` / `MINIWEB_MACRO_LOCATIONS`);
a fresh volume auto-seeds from the repo's bundled copies.

The data-prep / seed / build scripts that populate these tables were archived to
`../MiniWeb-archive/cleanup-20260810/scripts/` (re-run from there after a DB rebuild).
