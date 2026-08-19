# helpers/

Generic, project-agnostic utilities. Everything here is standalone and reusable
— no Flask blueprints, no site/macro domain logic — so the rest of the project
can be restructured around it. Import the specific module you need.

| Module | What it provides |
|---|---|
| `llm.py` | `LLMClient` — one client that routes any model to its provider (anthropic / openai / gemini / ollama / groq) via the official SDK, returns text, and tracks token usage (per-call `client.usage`, process-wide `LLMClient.GLOBAL`). Plus `MODELS` (current models per provider), `resolve_provider`, `call_llm` (one-shot), `list_models`. Gemini here uses Vertex + a service account (`GOOGLE_GENAI_USE_VERTEXAI` + `GOOGLE_CREDENTIALS_JSON`). |
| `geo.py` | `haversine(lat1, lng1, lat2, lng2, unit="km"\|"mi")` — great-circle distance. |
| `term.py` | Terminal styling for CLI output: ANSI constants (`BOLD`, `DIM`, `GREEN`, `RED`, …) that auto-disable when stdout isn't a tty or `NO_COLOR` is set, plus `badge(passed)`. |
| `security.py` | `safe_next(value)` — same-site relative-redirect guard (blocks open redirects). |
| `auth.py` | `current_user(get_user, session_keys=...)` and `browsing_user(get_user, session_keys=..., fallback=...)` — the shared session-auth logic the per-site `_get_current_user`/`_get_browsing_user` wrappers delegate to. |

`app/llm.py` is a thin backward-compat shim re-exporting `helpers.llm` (many callers
still `from app.llm import call_llm`).
