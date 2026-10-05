# app/

The Flask application that serves every MiniWeb site from one process, plus
the shared data layer and the `/_admin` endpoints that graders and the eval
harness read.

Start it with `run.py` (`~/.conda/envs/miniweb/bin/python run.py`, port
`$PORT`/`$FLASK_RUN_PORT`, default 8080). Production runs `gunicorn run:app`
(see `Procfile` and `Dockerfile`).

## Modules

| Path | Role |
|---|---|
| `__init__.py` | `create_app()`: loads `.env`, opens the DB, registers every blueprint, session handling, `/_admin` endpoints and script injection (details below). Also holds the site metadata maps (`SITE_CATEGORIES`, `SITE_TYPES`, `SITE_DOMAINS`, `SITE_KEYWORDS`) and `discover_sites()`. |
| `db.py` | Per-site SQLite access with session-overlay isolation (see below). |
| `events.py` | Cross-site event bus: `emit(event, **kw)`, `@on(event)` handler registration, the `event_log` table, and the 2FA helpers `request_2fa()` / `verify_2fa()`. |
| `handlers/` | `@on` handlers that turn events into records on other sites: banking debits (`purchase`, `payment`, `trade`, `account_reveal`), WebMail messages, calendar events (`booking`), instant messages (`message`), cloud-storage files (`file_created`), password-vault entries (`signup`). `email_handler._add_email()` is also called directly by many sites. |
| `bridges.py` | Thin wrappers over `emit()` (`on_purchase`, `on_payment`, `on_booking`, ...). |
| `bank_charges.py` | `charge_card(...)`: validates a card against `banking_cc_users` and posts the charge to `banking_cc_transactions` in the overlay. Used by sites that take card payments. |
| `ads.py` | `product_ads(n, seed, sources)`: in-network ad cards built from real MiniWeb content (e-commerce, auctions, video, books). Exposed to every template as a Jinja global; markup in `templates/ads/_product_ads.html`. |
| `vfs.py` | Simulated Finder-style file system served at `/_fs/*` (see below). |
| `playback.py` | Deterministic "what's on screen" timelines for the shared media player, served at `/_player/timeline?key=&duration=`. Short spans carry facts that are visible only while the playhead is inside them. |
| `portal/` | The site directory at `/` with `/api/sites` and `/api/search`. |
| `llm.py` | Compatibility shim that re-exports `helpers.llm` (`call_llm`, `LLMClient`, `list_models`, ...). New code should import `helpers.llm`. |
| `static/` | Shared assets: the injected scripts, the media player (`player.js`/`player.css`), brand fonts (`brand-fonts.css`, `fonts/`), shared site stylesheets, and `vendor/leaflet/` (a local copy of Leaflet used by the map-services pages, so maps work offline). |

## Request lifecycle

- **Site blueprints.** `register_site_blueprints()` imports `sites/<id>/routes.py`
  for every `sites/*/site.json` and mounts its `blueprint` at `/sites/<id>`.
  `MINIWEB_SITES=a,b` loads only those sites (faster dev startup). The
  annotation tool is mounted at `/annotate`.
- **Per-site login state.** Before a `/sites/<id>/` request the app loads that
  site's saved `session["_uid_<id>"]` into `session["user_id"]`, and saves it
  back afterwards, so logging in on one site never leaks into another.
- **Auto-login.** On `/sites/*` requests, a site with no login state of its own
  gets `session["user_id"] = 1` unless `session["_no_autologin"]` is set (or the
  process runs with `MINIWEB_NO_AUTOLOGIN=1`). Sites that keep their own session
  key (for example `weather_user_id`) are not affected and need an explicit login.
- **2FA for payments.** Sites call `events.request_2fa(event, return_url, **kw)`.
  It emails a 6-digit code to the user's WebMail inbox, stores the pending
  transaction in `session["_pending_2fa"]` and sends the browser to
  `/verify-payment`. A correct code (valid for 10 minutes) emits the event. With
  `session["_disable_2fa"]` set, the event runs at once.
- **Script injection.** Every HTML 200 response under `/sites/` gets, before
  `</body>`: `dialog-shim.js` (in-page `alert`/`confirm`), a broken-image
  placeholder script, `recorder.js` (action, network and observation recorder),
  `file-explorer.js` (file picker and save dialogs backed by `/_fs`),
  `export-feedback.js` (download toasts), the shared media player,
  `miniweb-share.js` (cross-site Share dialog), and a per-site logo font.
- **Request log.** Every `/sites/` request is logged per session (method, path,
  query, form/JSON body, uploaded-file hashes, JSON response, `Location` header,
  UTC timestamp), capped at 500 entries.

## Admin and grading endpoints

None of these require auth. Reads go through the caller's session overlay, so a
grader in the same session sees the agent's changes.

| Endpoint | Purpose |
|---|---|
| `GET /_admin/data/<site>/<collection>` | Rows of a collection. Query args filter by field equality; `_id=` returns one row, `_field=` one column, `_count=1` a count. |
| `GET /_admin/files/<site>` | Collections registered for a site. |
| `GET /_admin/user/<site>/<id>` | A user's profile plus rows that reference them. |
| `GET /_admin/changes?site=` | This session's effective changes versus the base tables (`db.session_changes`). |
| `GET /_admin/log` | The request log (`?method=`, `?path=`, `?last=N`, `?all=1` for every session). `POST /_admin/log/clear` clears it. |
| `POST`/`GET /_admin/beacon` | UI action beacons from `recorder.js`. |
| `POST`/`GET /_admin/record` | The recorder's action and observation stream in the human `trajectory.json` schema, for runs without an annotation parent window (`?all=1`, `?clear=1`). |
| `GET /_admin/events` | This session's cross-site event log. |
| `GET /_admin/session` | Non-private session keys. |
| `GET /_admin/session-flags` | `?disable_2fa=1` sets `_disable_2fa`; `?logout=1` logs out and sets `_no_autologin`. |
| `GET`/`POST /_reset_data` | Drops this session's overlay, logs and session state (keeps annotator login and `_disable_2fa`). `?no_autologin=1` starts the new session logged out. |
| `GET /_overlay_stats` | Overlay statistics. |
| `GET /_blocked` | Landing page for blocked external navigations during offline evals. |
| `/recovery/*` | Token-gated (`MINIWEB_RECOVERY_TOKEN`, header `X-Recovery-Token`) upload and download of the DB, annotations and macro YAMLs on a deployment. Returns 404 when the token is unset. |

## Data layer (`db.py`)

All site data lives in per-site SQLite tables (`<site>_<collection>`, for
example `banking_transactions`) in the file named by `MINIWEB_DB`. The project
`.env` points it at `data/trimmed_miniweb.db`; without it the default is
`miniweb.db` at the repo root. The `site_registry` table maps
`(site, collection)` to a table name and primary key.

**Session overlay.** Writes never touch base tables. `save_item`, `delete_item`
and `save_collection` write to `session_overlay` (and
`session_collection_replaced`), keyed by `session["_data_overlay_sid"]`. Reads
merge the overlay on top of the base table, so parallel agents stay isolated and
`/_reset_data` restores a pristine state.

| Function | Use |
|---|---|
| `query(site, coll, where=, sort=, limit=, offset=)` | Filtered, sorted, paginated read (`sort="-created_at"` for descending). |
| `get_item(site, coll, id)` | One row by primary key. |
| `count(site, coll, where=)` | Count without loading rows. |
| `search(site, coll, q, where=, limit=, offset=)` | FTS5/BM25 full-text search (falls back to `LIKE` when no FTS index exists). |
| `execute(sql, params, fetch="all"\|"one"\|"val")` | Raw SQL. Reads base tables only. |
| `merge_overlay(site, coll, rows, match=, sort=, limit=)` | Applies the session's edits to rows fetched with `execute()`. |
| `save_item` / `delete_item` / `save_collection` | Upsert, delete, or replace a whole (small) collection in the overlay. |
| `next_id(site, coll)` | Next integer id, counting both the base table and this session's overlay. Use it for creates; a base-table `MAX(id)` alone hands out the same id twice in one session. |
| `register_table(site, coll, table)` | Registers a table a site creates at runtime. |
| `session_changes()`, `reset_session()`, `get_stats()` | Grading and maintenance helpers. |

Rules for site code (also in the root `CLAUDE.md`):

- Every query on a large table filters, sorts and paginates in SQL (`WHERE`,
  `ORDER BY`, `LIMIT`). Never load a whole collection and filter in Python.
- `query()` without `limit` is only for tables known to stay under 100 rows.
- Text search uses `db.search()`, not `LIKE`.
- Counts use `db.count()` or `SELECT COUNT(*)`, never `len(db.query(...))`.
- Raw `execute()` misses this session's edits; pass its rows through
  `merge_overlay()` when the page must show them.

## Simulated file system (`vfs.py`)

`file-explorer.js` gives every site a Finder-style file dialog. The base tree is
the real `filesystem/` directory at the repo root (`MINIWEB_VFS_DIR` overrides),
rescanned on each request. Files a session downloads, saves or uploads are
stored in the overlay as site `filesystem`, collection `files`, so graders read
them at `/_admin/data/filesystem/files`. Endpoints: `/_fs/list`, `/_fs/file`,
`/_fs/download`, `POST /_fs/save`, `POST /_fs/upload`.

## Environment variables

| Variable | Effect |
|---|---|
| `MINIWEB_DB` | SQLite file path. |
| `MINIWEB_SITES` | Comma-separated subset of sites to load. |
| `MINIWEB_NO_AUTOLOGIN` | Disable auto-login for the whole process. |
| `MINIWEB_VFS_DIR` | Base directory for the simulated file system. |
| `MINIWEB_DATA_STATIC` | Directory for generated images served at `/static/{generated,avatars,thumbnails}/` (default `data/static/`). |
| `MINIWEB_DATA_SOURCES` | Raw source-data directory still read by a few sites (forms-surveys, visual-how-to-guides). |
| `MINIWEB_RECOVERY_TOKEN` | Enables the `/recovery/*` endpoints. |
| `SECRET_KEY` | Flask session key. |
