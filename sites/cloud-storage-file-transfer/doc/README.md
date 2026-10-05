# MeridianCloud (`cloud-storage-file-transfer`)

A cloud-drive and file-transfer portal in the style of Google Drive / Dropbox,
holding a software team's workspace at Meridian Systems. Users browse a folder
tree, search and filter files, star, rename, move, trash and download them,
share files with teammates and send file transfers via share links.

- URL: `/sites/cloud-storage-file-transfer/` (simulated domain `meridiancloud.com`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | File browser: search, type filter, sort, From/To dates, bulk select + delete, new folder and upload modals |
| `/?view=starred\|recent\|shared\|trash` | Sidebar views (`/starred`, `/recent`, `/shared`, `/trash` redirect here) |
| `/folder/<id>` | Folder contents and subfolders |
| `/file/<id>` | File detail: metadata, rename, move to folder, star, share / invite, download, transfers |
| `/transfers`, `/transfers/new` | Sent transfers and the "Send files" form |
| `/transfers/<id>/sent` | Sender confirmation with the copyable share link |
| `/t/<id>/<token>` | Recipient download page for a transfer link |
| `/login` | Sign-in form |

JSON endpoints under `/api/` cover files, folders, shares, transfers, search, storage usage/quota, export and settings.

## Interactions and macros

- Search files ("Search in Drive"): `search`
- Filter by file type, sort the list, filter by date range: `filter_by_dropdown`, `sort_by_form`, `filter_by_date_range`
- Open folders and files: `navigate_by_route`
- Create a folder, invite a collaborator: `create_by_form`
- Share a file with permission controls: `share_by_form`
- Star / unstar files: `toggle_relationship`
- Trash or permanently delete files (single or bulk): `delete_from_table`
- Upload a file through the upload modal: `upload_file`
- Download a file: `export`
- Read file metadata, sharing and transfer records; sign in: `report_information`, `authenticate_by_form`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `cloud-storage-file-transfer`.

## Data

- Tables: `cloud_storage_file_transfer_files`, `_folders`, `_shares`,
  `_transfers`, `_users` (all prefixed `cloud_storage_file_transfer_`).
- Login uses the shared `session["user_id"]`, so the global auto-login signs in user 1.
- Logging in emits `signup` (password-vault entry + email); sharing a file
  emails the recipient through WebMail.
- Other sites' `file_created` events add files here
  (`app/handlers/cloud_storage_handler.py`, ids from 90001).
- Upload is simulated: the modal records name, type and size, not real bytes.
  Downloads serve deterministic content generated from the file's metadata.
