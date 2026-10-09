# WordRef Dictionary (`dictionaries-language-tools`)

An English dictionary in the style of Merriam-Webster / Dictionary.com, built
from Wiktionary entries. Users search words, browse A-Z, read definitions,
IPA pronunciations, word forms, examples, synonyms and antonyms, and save
words to a personal list.

- URL: `/sites/dictionaries-language-tools/` (simulated domain `wordwise.com`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Search box, word of the day, paginated results |
| `/browse/<letter>` | Words starting with a letter |
| `/word/<word>` | Word entry: IPA, part of speech, forms, senses, examples, synonyms; "Save Word" button when signed in |
| `/dashboard` | Saved words |
| `/login` | Sign-in form |

JSON endpoints under `/api/` provide word search (`q`, `pos`, `letter`), word details, synonyms, random word, word of the day and stats.

## Interactions and macros

- Look up a word: `search`
- Open a word from results or the A-Z browser: `navigate_by_route`
- Save / unsave a word: `toggle_relationship`
- Read definitions, pronunciation, examples and synonyms: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `dictionaries-language-tools`.

## Data

- Tables: `dictionaries_language_tools_entries` (Wiktionary entries),
  `dictionaries_language_tools_users`.
- Source: Wiktionary (https://en.wiktionary.org/).
- Login uses the shared `session["user_id"]`, so the global auto-login signs in user 1.
- Pronunciations are IPA text; there is no audio player or translation section.
