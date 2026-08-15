# Translation (LinguaBridge Translator)

**Category**: Utilities
**Reviewer**: Kenny
**Number of macros**: 7

## Data Source

Rule-based machine translation using built-in word-swap dictionaries for 9 language pairs (English to/from Spanish, French, German, Italian, Portuguese, Japanese, Chinese, Korean, Arabic). User data (history, saved translations, glossaries, settings) stored in JSON files under data_sources/translation/.

### Data Format

- `users.json` -- array of user objects: id, username, password, name, email
- `languages.json` -- array of supported languages: code, name, native_name
- `history.json` -- array of translation records: id, user_id, source_lang, target_lang, source_text, translated_text, timestamp
- `saved.json` -- array of saved/bookmarked translations: id, user_id, source_lang, target_lang, source_text, translated_text, label
- `glossaries.json` -- array of custom glossaries: id, user_id, name, source_lang, target_lang, entries (array of {source, target})
- `settings.json` -- dict keyed by user_id string, each value has: auto_detect, formal_mode, auto_pronounce (booleans)

## Real-World Model

**Google Translate / DeepL / Linguee** -- text translation utility with language dropdowns, translation history, saved phrases, custom glossaries, audio playback, file upload for batch translation, and image-based OCR translation.

## Target Macros

navigate_by_route, extract_by_query, extract_by_semantic, configure_by_toggle, export_by_dropdown, upload_by_upload, translate_by_query

## Temporal Dynamics

Not applicable -- translation is a stateless utility. History and saved translations accumulate over time but the translation engine itself is static.

## Domain-Specific Notes

- Translation uses a word-swap approach: each word is looked up in a dictionary for the given language pair. Unknown words pass through unchanged.
- Reverse dictionaries are auto-generated so e.g. Spanish-to-English works from the English-to-Spanish dictionary.
- User glossaries override built-in dictionaries (higher priority).
- Language detection is keyword-based: counts matches against known words per language.
- Audio playback is a placeholder (no real TTS); the API returns metadata about what would be spoken.
- Image OCR translation is a placeholder; it accepts image uploads and returns a mock OCR extraction.
- File upload translates each line of a .txt file independently.
- Export supports JSON, CSV, and plain text formats for translation history.
