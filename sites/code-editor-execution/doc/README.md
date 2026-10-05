# CodeRunner (`code-editor-execution`)

An online Python IDE modeled after the GeeksforGeeks IDE: a gallery of example
snippets, an in-browser editor that really runs Python, and a dashboard of
saved snippets.

- URL: `/sites/code-editor-execution/` (simulated domain `codeforge.dev`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Snippet gallery with search |
| `/snippet/<id>` | Snippet detail with code, Share and Save/Unsave |
| `/editor` | Editor (`?snippet_id=` pre-fills code): Run Code, stdin, font-size slider, Share Snippet |
| `/dashboard` | Saved snippets and run history (login required) |
| `/upload` | Create a snippet (title, code, description, category, difficulty) |
| `/export` | CSV/JSON download of all snippets or one category |
| `/settings` | Editor preferences: font size, tab size, theme |
| `/login` | Sign-in form |
| `/s/<token>` | Share link that opens the snippet in the editor |

JSON endpoints under `/api/` cover snippets, categories, execute, share,
export and user settings and history.

## Interactions and macros

- Search the gallery: `search`
- Open a snippet from the gallery or dashboard: `navigate_by_route`
- Write code in the editor and run it: `create_by_form`, `edit_by_form`
- Change the editor font size: `configure_by_form`
- Share a snippet link: `share_by_form`
- Read saved snippets on the dashboard: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `code-editor-execution`.

## Data

- Tables: `code_editor_execution_snippets`, `code_editor_execution_users`.
- Login uses `session["user_id"]`, so the global auto-login signs in user 1.
- Code runs for real in a Python subprocess with a 5-second timeout. Imports
  of dangerous modules (`os`, `sys`, `subprocess`, `socket`, ...) are rejected.
- Export links use `data-save-as`, so downloads go through the simulated file
  explorer's Save As dialog.
- Logging in emits `signup` (password-vault entry and welcome email).
