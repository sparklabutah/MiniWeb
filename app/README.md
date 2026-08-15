# app/

The core Flask application package — the server that hosts all the mock sites,
the shared data layer, and the admin/instrumentation endpoints the evaluation
harness reads.

| File | Role |
|---|---|
| `__init__.py` | `create_app()` — registers every site blueprint, the `/_admin/*` endpoints (`/record`, `/log`, `/beacon`, `/data`, …), the auto-login `before_request` (`session["user_id"]=1` on `/sites/*`), and the `after_request` that injects `recorder.js` / `file-picker.js` / `export-feedback.js`. |
| `db.py` | Per-site SQLite data access with **session-overlay** isolation. `query`/`get_item`/`count`/`search`/`save_item`/`save_collection`/`execute`. Reads merge the per-session overlay so parallel agents don't collide (see the DB rules in the root `CLAUDE.md`). |
| `llm.py` | Backward-compat shim → re-exports `helpers.llm` (`call_llm`, `list_models`, …). New code should use `helpers.llm` directly. |
| `events.py` | Cross-site event log (`_admin/events`) — the "X happened on site A" signals used for multi-site task flows. |
| `bank_charges.py` | `charge_card(...)` — validates a card against `banking_cc_users` and posts the charge to the session overlay; used by the sites that take card payments. |
| `bridges.py`, `ads.py` | Small cross-cutting helpers. |
| `handlers/` | Site-specific server logic that's too big for a route module — `banking_handler`, `email_handler`, `calendar_handler`, `im_handler`, `password_handler`, `cloud_storage_handler`. |

Data lives in per-site SQLite tables in `data/trimmed_miniweb.db`; **never** load
whole collections into Python (query with WHERE/LIMIT/ORDER BY — see `CLAUDE.md`).
