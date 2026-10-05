# sites/

The 65 mock websites MiniWeb serves. Each one is a Flask blueprint mounted at
`/sites/<site-id>/` that renders like a real product (bank, forum, shop, mail,
maps, ...) and reads and writes the shared SQLite database with per-session
isolation. Each site has its own page in `sites/<site-id>/doc/README.md`.

`sites/classifieds/` is not a site: it only holds avatar images, has no
`site.json`, and is never loaded.

## Layout of a site

| Path | Role |
|---|---|
| `site.json` | `id`, display `name`, `description`, `tags`. Its presence is what makes the directory a site. |
| `routes.py` | Defines the module-level `blueprint` with all pages and JSON endpoints. Holds a `SITE = "<site-id>"` constant for `app.db` calls. |
| `schema.py` | `TABLES`: collection name to `table_name`, `columns` and `indexes`, i.e. the definitions the database was built from. At runtime, table names come from the `site_registry` table in the DB. A few sites create extra tables on first use and register them with `db.register_table()`. |
| `templates/<site-id>/` | Jinja templates (namespaced by site id). |
| `static/` | Site assets, served at `/sites/<site-id>/static/`. |
| `doc/README.md` | What the site is, its pages, the interactions and macros it supports, and data notes. |
| other modules | Site-specific helpers, e.g. `dating/photos.py`, `insurance-loans/pdf.py`, `url-shorteners-qr/qr_encoder.py`, `design-creative/seed_assets.py`, `config/` folders. |

## How sites are registered

`app.register_site_blueprints()` scans `sites/*/site.json`, imports
`sites.<dir>.routes`, and mounts `blueprint` at `/sites/<id>`. Set
`MINIWEB_SITES=banking,email` to load only some sites. The site directory at `/`
and its search use the per-site maps in `app/__init__.py`: `SITE_CATEGORIES`,
`SITE_TYPES`, `SITE_DOMAINS` (the simulated domain shown in the browser chrome)
and `SITE_KEYWORDS`. A new site needs an entry in each.

To add a site: create `sites/<id>/` with `site.json`, `routes.py` (a
`blueprint` with `static_url_path="/static"` and templates under
`templates/<id>/`), create and register its tables, add the four map entries,
add its macros to `data/macro_locations.yaml`, and write `doc/README.md`.

## Tasks are not stored here

Sites carry no task files. Benchmark tasks live in
`data/annotations/<annotator>/<task_id>/` (`task.json`, `trajectory.json`,
`verifier.json`, screenshots). Which macros a site supports, and where in its
UI, is recorded in `data/macro_locations.yaml`.

## Train / held-out split

`data/datagen/site_split.json` fixes a site-level split for generated training
data: 52 training sites and 13 held-out (test) sites. The data-generation
pipeline (`datagen/split.py`) refuses to touch held-out sites. They are:

`comparison-aggregators`, `conference-review-submission`, `crm`,
`crowdfunding-donations`, `dating`, `flights-hotels`, `music`,
`petitions-voting-info`, `project-mgmt-issue-tracking`, `rating-review`,
`real-estate-buy-rent`, `url-shorteners-qr`, `weather`.

## Conventions

- **Data access.** Use `app.db` and do all filtering, sorting and pagination in
  SQL. Never load a whole collection into Python. Use `db.search()` for text
  search, `db.count()` for counts, and `db.next_id()` for new ids. Raw
  `db.execute()` reads only base tables; pass its rows through
  `db.merge_overlay()` to show this session's edits. See `app/README.md` and
  the root `CLAUDE.md`.
- **Writes are per session.** Every create, edit or delete goes to the session
  overlay, never to base tables, so parallel agents do not see each other's
  changes and `/_reset_data` restores the seeded state.
- **Static dates.** Seed data is a fixed snapshot in the past. Do not shift or
  rewrite dates. If a date filter or "upcoming" view would come up empty,
  anchor that site's UI to the dates in its data.
- **Deterministic data.** Seed data is generated offline and deterministically,
  and sites do not fetch live external data. The one model-backed site,
  `translation`, stores every output in its `translation_cache` table so
  repeat requests give the same text. One-off seed scripts in `scripts/`
  (`seed_email_archive.py`, `seed_dating_photos.py`,
  `seed_peerportal_assignments.py`, `seed_peerportal_deadlines.py`,
  `seed_real_estate_rentals.py`) are idempotent and must be re-run after a
  database rebuild.
- **One identity across sites.** The default user is Alex Rivera of Lakeport,
  WA (user 1, the auto-login user). Per-site user tables carry a
  `root_user_id` that links each account to the same person on other sites,
  so tasks can carry information from one site to another.
- **Login.** The app keeps login state per site. Sites that read
  `session["user_id"]` are auto-logged in as user 1. Sites with their own session
  key need an explicit login. Shared auth logic lives in `helpers.auth`
  (`current_user`, `browsing_user`), and `helpers.security.safe_next` guards
  `?next=` redirects.
- **Cross-site effects.** Use `app.events.emit()` (or `app.bridges`) for
  purchases, payments, bookings, sign-ups and messages, so the bank ledger,
  WebMail, calendar, messenger and password vault update. Payments go through
  `events.request_2fa()` and the shared `/verify-payment` page. Card charges go
  through `app.bank_charges.charge_card()`.
- **Files.** Uploads, downloads and exports go through the shared simulated
  file system (`file-explorer.js`, `/_fs/*`), so graders can see saved files at
  `/_admin/data/filesystem/files`.
- **No native dialogs.** Pages run inside a sandboxed iframe in the annotation
  tool. `alert`/`confirm` are shimmed, so do not rely on them for flow control.
