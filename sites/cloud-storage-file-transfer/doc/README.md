# Cloud storage / file transfer

**Category**: Productivity
**Reviewer**: Reaz
**Number of macros**: 25

## Data Source

GitLab-derived synthetic dataset representing a software engineering team's cloud workspace at Meridian Systems. Five JSON files:

- `files.json` — 40 files with metadata (name, path, size, type, owner, folder, starred, trashed)
- `folders.json` — 15 folders in a tree hierarchy (Projects, Personal, Shared, Archives with subfolders)
- `users.json` — 5 team members with credentials, roles, storage quotas
- `shares.json` — 12 share records linking files to users with permission levels (view/edit/admin)
- `transfers.json` — 10 file transfer records with status, expiry, download counts

### Data Format

**files.json** — Each record has: `id`, `name`, `path`, `size_bytes`, `type` (document/image/spreadsheet/presentation/archive/code), `mime_type`, `owner_id`, `created_at`, `modified_at`, `shared_with` (list of user IDs), `folder_id`, `starred` (bool), `is_trashed` (bool).

**folders.json** — Each record: `id`, `name`, `parent_id` (null for root), `owner_id`, `created_at`, `color`.

**users.json** — Each record: `id`, `username`, `password`, `name`, `email`, `role`, `avatar_color`, `storage_quota_gb`, `storage_used_bytes`.

**shares.json** — Each record: `id`, `file_id`, `shared_by`, `shared_with` (user ID or null for link-share), `permission`, `created_at`, `link`.

**transfers.json** — Each record: `id`, `file_id`, `sender_id`, `recipient_email`, `status` (active/completed/expired), `created_at`, `expires_at`, `download_count`.

## Real-World Model

**Google Drive / Dropbox / OneDrive** — cloud file storage UI. Key elements:
- File browser with table/list view showing name, owner, size, modified date
- Folder tree navigation with breadcrumbs
- Search bar with keyword and semantic/fuzzy search
- File type and date range filters
- Starred files, recent files, trash views
- File detail page with sharing, transfer, and metadata
- Storage usage dashboard with quota visualization
- Share files with users or via link, set permissions (view/edit/admin)
- File transfers to external recipients
- User authentication and settings

## Target Macros

navigate_from_table, navigate_by_route, search_by_query, search_by_semantic, filter_by_dropdown, filter_by_date_range, sort_by_ranking, extract_by_semantic, extract_by_dropdown, extract_by_route, compute_by_slider, create_from_free_text, edit_by_dropdown, edit_by_form, edit_by_drag, delete_from_table, configure_by_toggle, export_by_dropdown, upload_from_table, upload_by_route, share_by_query, share_by_dropdown, save_by_toggle, invite_by_form, authenticate_by_form

## Temporal Dynamics

Not applicable -- cloud storage is not inherently time-varying. Data is a static snapshot of files, shares, and transfers. No temporal simulation needed.

## Domain-Specific Notes

- File types span document, image, spreadsheet, presentation, archive, and code
- Folder hierarchy: 4 root folders (Projects, Personal, Shared, Archives) with nested subfolders
- Storage quotas per user (50 GB each); compute_by_slider lets users explore quota scenarios
- Shares support three permission levels: view, edit, admin
- Transfers have statuses (active, completed, expired) and download counts
- Semantic search scores files by weighted keyword matching across name, path, type, and MIME type
- Login uses username/password from users.json (e.g., alex.chen / meridian111)
