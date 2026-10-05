# data/

The MiniWeb database, the recorded human tasks, the macro registry, and the workspaces of the
data-generation and training pipelines.

`.gitignore` excludes everything here (`data/*`) except a short allow-list:

- **Tracked in git:** `macros.yaml`, `macro_locations.yaml` and this README.
- **Versioned but not yet committed:** `datagen/site_split.json` and `datagen/guides/`. They
  are pipeline inputs, so `.gitignore` lets them through.

Everything else is local data or generated output.

| Path | Contents | Git |
|---|---|---|
| `macros.yaml` | The canonical macro registry: base macros, reasoning operations, aliases. The single source of truth, loaded by `annotation/macros.py` | tracked |
| `macro_locations.yaml` | Per-site macro → UI location map (coverage, sampling, the datagen split) | tracked |
| `trimmed_miniweb.db` | The per-site SQLite dataset every site reads and writes through `app.db` (~36 GB). `.env` points `MINIWEB_DB` at it; without that, `app.db` falls back to `miniweb.db` at the repo root. It was modified after the build: **never re-run `build_db.py`** | ignored |
| `annotations/` | Recorded human tasks, `<annotator>/<task_id>/`: `task.json`, `trajectory.json`, `verifier.json`, `screenshots/` and review files. These are the real tasks (`MINIWEB_ANNOTATIONS_DIR` overrides the location) | ignored |
| `datagen/` | The synthetic-trajectory pipeline's workspace: split, guides, site maps, caches, `runs/`, `retired.json`, viewer. See [`datagen/README.md`](../datagen/README.md) | `site_split.json` + `guides/` versioned; the rest ignored |
| `webmix/` | Replayed training rows, adapters, evaluation runs, benchmark files and judges, live-web task sets, launchers. See [`webmix/README.md`](../webmix/README.md) | ignored |
| `static/` | Generated images (`generated/`, `avatars/`, `thumbnails/`), served at `/static/<sub>/…` (`MINIWEB_DATA_STATIC` overrides) | ignored |
| `backups/` | Timestamped backups taken before migrations and Railway pulls: annotation and verifier tarballs, and a few database snapshots | ignored |
| `railway_pulls/<timestamp>/` | Remote snapshots and difference manifests from `scripts/pull_from_railway.py --new-only` | ignored |
| `task_review_*/`, `task_repairs_*/`, `verifier_audit_*/` | Review and audit packets for task, macro and verifier passes. The annotation tool serves them read-only (`/annotate/api/review_document`) | ignored |
| `macro_templates.yaml`, `academic-paper-db.json` | Leftovers: the retired macro templates, and an early feedback note. No code reads them | ignored |

## Notes

- **Macro YAMLs in production:** annotators register new macros by writing to `macros.yaml`.
  On a deployment, point both YAMLs at a persistent volume with `MINIWEB_MACRO_DIR`, or per
  file with `MINIWEB_MACROS` and `MINIWEB_MACRO_LOCATIONS`. A fresh volume is seeded from the
  copies in this directory.
- **`data/datagen/retired.json`** is hand-written but gitignored. Back it up with the runs it
  refers to.
- **After a database rebuild,** re-run the runtime seed scripts in `scripts/` (`seed_*.py`).
  The older build and seed scripts are archived in `../MiniWeb-archive/cleanup-20260810/scripts/`.
- **Moving the big trees:** `MINIWEB_DATAGEN_DIR` moves `data/datagen/`, and
  `WEBMIX_REPLAY_DIR` points WebMix at another set of training rows.
