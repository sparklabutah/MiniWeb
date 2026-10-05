# DocEdit (`documents`)

A Google Docs-style document editor. Users create, edit, share, star, move and
trash documents, browse folders, view and restore past revisions, and edit a
document's data grid cell by cell.

- URL: `/sites/documents/` (simulated domain `meridianflow.com`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Document list with search, From/To date filters, sort dropdown, folder sidebar, Upload File |
| `/new` | New-document form (title, owner, folder, content) |
| `/editor/<id>` | Editor: title and body, star, share form (user + permission), move to folder, revision list with restore |
| `/view/<id>` | Read-only view with revision history and a Delete (to trash) button |
| `/document/<id>/version/<rev>` | Content of one past revision |
| `/document/<id>/table` | Inline-editable data grid for the document |
| `/folder/<id>` | Documents in one folder |
| `/starred`, `/trash` | Starred documents; trash with restore and permanent delete |
| `/login` | Sign-in form |

JSON endpoints under `/api/` create, update, star, trash, share, move, delete and export documents.

## Interactions and macros

- Search documents: `search`
- Filter the list by date range: `filter_by_date_range`
- Sort by last modified, date created or title: `sort_by_form`
- Create a document, share it with a user: `create_by_form`
- Edit a document's title and body: `edit_by_form`
- Write translated text into a document: `translate_by_query`
- Star or unstar a document: `toggle_relationship`
- Upload a file as a new document: `upload_file`
- Trash or permanently delete a document: `delete_from_table`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `documents`.

## Data

- Tables: `documents_documents`, `documents_folders`, `documents_revisions`, `documents_users`.
- Login reads `session["user_id"]`, so the global auto-login signs in as user 1.
- Creating or uploading a document emits `file_created`, which adds the file
  to cloud storage and sends a notification email. Logging in emits `signup`
  (password-vault entry and welcome email).
