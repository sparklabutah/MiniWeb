# sites/

The ~66 mock websites the benchmark runs against — each a self-contained Flask
blueprint (banking, forums, e-commerce, email, job-sites, …). They render like
real apps but read/write a shared trimmed dataset with per-session isolation.

## Anatomy of a site (`sites/<site>/`)
| Item | Role |
|---|---|
| `routes.py` | The Flask blueprint: pages + JSON APIs. Auth via the shared `helpers.auth` (`_get_current_user`/`_get_browsing_user` wrappers). |
| `schema.py` | Table definitions registered into the site registry (`db.register_table`). A collection used with `db.query`/`save_collection` MUST have a real base table here, or overlay writes are invisible on read. |
| `templates/`, `static/` | Jinja templates + assets. |
| `site.json` | Site metadata (name, description). |
| `tasks.json` | Site-local eval tasks (used by `evaluation/run_eval.py`). |
| `generate_data.py` | (some sites) deterministic synthetic-data generation for the site's tables. |

## Data rules (enforced — see root `CLAUDE.md`)
- All data is in per-site SQLite tables in `data/trimmed_miniweb.db`, accessed via `app.db`.
- **Never** load whole collections into Python: every query needs `WHERE` + `LIMIT` + `ORDER BY` at the SQL level. Use `db.search()` (FTS5) for text search, `db.count()` for counts.
- Mutations go to the per-session overlay, so parallel agents stay isolated.

## Conventions
- Auth helpers delegate to `helpers.auth`; geo/redirect helpers to `helpers.geo`/`helpers.security`.
- Two sites keep bespoke auth on purpose (`live`, `multimedia-posting`) — don't "unify" them.
- Dates in seed data are intentionally static/past; fix date-filter UX per-site, never shift dates.
