# LinguaBridge Translate (`translation`)

A Google Translate / DeepL-style translator with source and target language
dropdowns, translation history, saved translations, custom glossaries and
user settings.

- URL: `/sites/translation/` (simulated domain `linguabridge.app`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Translator: source text, source (with Detect) and target language dropdowns, swap, save, recent history |
| `/history` | Translation history with search |
| `/saved` | Saved translations with delete |
| `/glossaries`, `/glossary/<id>` | Glossary list with create form; glossary entries with add-entry and Delete Glossary |
| `/settings` | Auto-detect, formal mode and auto-pronounce checkboxes; export (JSON/CSV/TXT) |
| `/login` | Sign-in form |

The translate form posts to `/translate`. JSON endpoints under `/api/` cover
translate, detect, languages, history, saved, glossaries, settings, export,
upload and image translation.

## Interactions and macros

- Translate text between two chosen languages: `translate_by_query`
- Toggle translation settings: `configure_by_form`
- Export translation history: `export`
- Move between Translate, History and Saved: `navigate_by_route`
- Read translations and saved items: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `translation`.

## Data

- Tables: `translation_languages` (11 languages), `translation_history`,
  `translation_saved`, `translation_glossaries`, `translation_settings`,
  `translation_users`.
- Login reads `session["user_id"]` (via `helpers.auth`), so the global
  auto-login signs in user 1.
- Translation engine: the local NLLB-200 model (`models/nllb200-600M-ct2`,
  override with `MINIWEB_NLLB_MODEL`; fetch it with
  `scripts/fetch_translation_model.py`) is tried first. Requests that use a
  glossary go to the configured LLM first. Each result is stored in the
  `translation_cache` base table, so the same request always returns the same
  text. If neither engine is available, a word-by-word dictionary answers, and
  that answer is not cached.
- The site has no cross-site effects.
