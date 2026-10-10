# data/

The MiniWeb database, the recorded human tasks, the macro registry, and the workspaces of the
data-generation and training pipelines.

`.gitignore` excludes everything here (`data/*`) except a short allow-list, the files in the first table.

## Tracked in git

| Path | Contents |
|---|---|
| `macros.yaml` | The canonical macro registry: base macros, reasoning operations, aliases. The single source of truth, loaded by `src/miniweb/annotation/macros.py` |
| `macro_locations.yaml` | Per-site macro → UI location map (coverage, sampling, the generator's split) |
| `final_set.yaml` | The paper's final set: 37 primitives and 376 tasks (by id). It locks the annotation tool to them |
| `sites.yaml` | The 65 sites: domain, split (52 train, 13 held out), hub, data source and license |
| `datagen/site_split.json`, `datagen/guides/` | MiniWebGen's inputs: the train/test site split, fixed before any generation, and one guide per primitive |

## Local data (not in git)

| Path | Contents |
|---|---|
| `miniweb.db` | The per-site SQLite database every site reads and writes through `miniweb.app.db`, rebuilt from the Hub by `scripts/restore_site_db.py` (`MINIWEB_DB` moves it). It was modified after the build: **never re-run `build_db.py`** |
| `annotations/` | The human tasks, `<author>/<task_id>/`: `task.json`, `verifier.json`, `trajectory.json`, `screenshots/`, the verification walk; rebuilt from the Hub by `scripts/fetch_tasks.py` (`MINIWEB_ANNOTATIONS_DIR` moves it) |
| `static/` | The sites' own images (`generated/`, `avatars/`, `thumbnails/`), served at `/static/<sub>/…`; restored by `scripts/restore_site_db.py` (`MINIWEB_DATA_STATIC` moves it) |
| `media/` | A copy of the external media the sites' pages show (images that site data links to, map tiles) with `manifest.jsonl`, served at `/media/…`; restored by `scripts/restore_site_db.py`, rebuilt from the original hosts by `scripts/fetch_site_media.py` (`MINIWEB_MEDIA_DIR` moves it) |
| `datagen/` | MiniWebGen's workspace besides the tracked inputs: site maps, caches, `runs/<run>/`, `retired.json`, the viewer. See [`src/miniwebgen/README.md`](../src/miniwebgen/README.md) (`MINIWEB_DATAGEN_DIR` moves it) |
| `webmix/` | Replayed training rows, adapters, evaluation runs, benchmark task sets and judges, the task-centric data (`taskgen/`). See [`src/miniwebagent/README.md`](../src/miniwebagent/README.md) (`WEBMIX_REPLAY_DIR` points training at other rows) |
| `grader_audit/` | The grader audit: sampled agent episodes, the grader key and the labels (`src/miniweb/scripts/build_grader_audit.py`, `grader_audit_report.py`) |
| `release/` | The consolidated data release that `scripts/build_release.py` writes (`miniweb-v1/`) and its Hugging Face version (`miniweb-v1-hf/`, `scripts/build_hf_dataset.py` and `scripts/export_site_db.py`) |

Tools create a few more folders when they run: `backups/` and `railway_pulls/` (`src/miniweb/scripts/pull_from_railway.py`),
and review packets (`task_review_*/`, `task_repairs_*/`, `verifier_audit_*/`) that the annotation tool serves read-only.
None of them is needed to run the sites, the evaluations or the pipelines.

## Notes

- **Macro YAMLs in production:** annotators register new macros by writing to `macros.yaml`.
  On a deployment, point both YAMLs at a persistent volume with `MINIWEB_MACRO_DIR`, or per
  file with `MINIWEB_MACROS` and `MINIWEB_MACRO_LOCATIONS`. A fresh volume is seeded from the
  copies in this directory.
- **`datagen/retired.json`** is hand-written but not tracked. Back it up with the runs it refers to.
- **After a database rebuild,** re-run the runtime seed scripts in `src/miniweb/scripts/` (`seed_*.py`).
