# helpers/

Small, project-agnostic utilities. Nothing here imports Flask blueprints, site
code or macro logic, so any part of the repo can use them. Import the module you
need, for example `from helpers.llm import LLMClient`.

| Module | Provides |
|---|---|
| `llm.py` | One client for every LLM provider, with token accounting (below). |
| `auth.py` | `current_user(get_user, session_keys=("user_id",))` returns the signed-in user or `None`. `browsing_user(get_user, session_keys=..., fallback=1)` returns `(user, is_logged_in)` and falls back to a browse-only user. Many sites' `_get_current_user` / `_get_browsing_user` wrappers delegate here. |
| `security.py` | `safe_next(value)`: returns `value` only if it is a same-site relative path (blocks open redirects through `?next=`). |
| `geo.py` | `haversine(lat1, lng1, lat2, lng2, unit="km"\|"mi")`: great-circle distance. Used by map-services, transit-directions and weather. |
| `term.py` | ANSI styles for CLI output (`BOLD`, `DIM`, `GREEN`, `RED`, `YELLOW`, `CYAN`, `RESET`), disabled when stdout is not a TTY or `NO_COLOR` is set, plus `badge(passed)` for a PASS/FAIL marker. |

## llm.py

`LLMClient` maps a model name to a provider and calls that provider's official
SDK. `complete()` returns the response text, or `None` on any failure.

```python
from helpers.llm import LLMClient, call_llm

client = LLMClient("gemini-3.5-flash", temperature=0.2, max_tokens=800)
text = client.complete("Summarize this.", system="Be terse.", json_mode=False)
client.usage.as_dict()       # {'prompt', 'completion', 'total', 'calls'} for this client
LLMClient.GLOBAL.as_dict()   # running totals for the whole process

text = call_llm("Hello", model="claude-sonnet-5")   # one-shot shortcut
```

Routing (`resolve_provider`): exact match in the `MODELS` registry first, then
by prefix.

| Provider | Model names | Configuration |
|---|---|---|
| anthropic | `claude-*` | `ANTHROPIC_API_KEY` |
| openai | `gpt-*`, `o1*`, `o3*`, `o4*`, `chatgpt*` | `OPENAI_API_KEY` |
| gemini | `gemini-*` | `GEMINI_API_KEY` or `GOOGLE_API_KEY`; or Vertex AI with `GOOGLE_GENAI_USE_VERTEXAI=1`, `GOOGLE_CREDENTIALS_JSON` (service-account JSON), `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION` (default `global`) |
| ollama | `ollama/<model>` or `ollama:<model>` | `OLLAMA_HOST` (default `http://localhost:11434`) |
| groq | anything else | `GROQ_API_KEY` (OpenAI-compatible endpoint) |

Other details:

- The default model is `$LLM_MODEL`, else `gemini-2.5-flash`.
- Configuration values are read from the environment, falling back to the
  project `.env` (multi-line quoted values such as `GOOGLE_CREDENTIALS_JSON`
  work).
- `complete(..., images=[bytes or path, ...])` sends images before the prompt.
  Only Gemini supports this; other providers return `None` instead of
  answering without the images.
- `list_models(configured_only=False)` returns
  `{provider: {"configured": bool, "models": [...]}}`.
- `app/llm.py` re-exports this module for older `from app.llm import call_llm`
  callers.
