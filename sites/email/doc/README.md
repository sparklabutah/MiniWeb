# WebMail (`email`)

A Gmail/Outlook-style webmail client. Users read folders, search, compose with
attachments, star, label, move, delete, block senders and report messages. It
is also the inbox every other MiniWeb site writes to: order confirmations,
notifications and 2FA codes all arrive here.

- URL: `/sites/email/` (simulated domain `lakeportmail.com`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Folder view (`?folder=inbox`, `sent`, `drafts`, `trash`, `spam`) with From/To dates, sort (Date, Subject, From), star and trash per row, bulk actions |
| `/message/<id>` | Message: headers, body, attachments; star, mark read/unread, label, move to folder, delete, block sender, report |
| `/compose` | Compose form (To, Cc, Subject, body, Attach); `?reply_to=` and `?forward=` prefill it |
| `/search` | Search results (`q`) scoped by a folder dropdown |
| `/contacts` | Contact list |
| `/login` | Sign-in form |

JSON endpoints under `/api/` cover messages, folders and counts, contacts,
search, stats and export (`/api/export`, JSON or CSV).

## Interactions and macros

- Search mail and scope it to a folder: `search`, `filter_by_dropdown`
- Filter a folder by date range: `filter_by_date_range`
- Sort the message list: `sort_by_form`
- Open folders and messages: `navigate_by_route`
- Compose or reply: `create_by_form`; attach a file: `upload_file`
- Label a message or move it to a folder: `edit_by_form`, `configure_by_form`
- Star a message or block its sender: `toggle_relationship`
- Mark read/unread: `filter_by_options`
- Delete messages: `delete_from_table`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `email`.

## Data

- Source: the Enron email corpus (CMU / Kaggle) as background mail.
- Tables: `email_emails` (Enron and seeded archive mail), `email_sent_messages`
  (Alex Rivera's authored mail, composed mail and cross-site notifications),
  `email_email_state` (read/star/folder state), `email_users`.
- `scripts/seed_email_archive.py` adds dated 2023-2026 emails that reference
  real records on banking, flights-hotels, insurance-loans, e-commerce and
  calendar-todo, for cross-site search tasks. Re-run it after a DB rebuild and
  restart the server (the corpus is cached per process).
- Other sites deliver mail through `app/handlers/email_handler._add_email`;
  this includes the 6-digit codes for `/verify-payment` 2FA.
- Login uses `session["user_id"]`, so the global auto-login signs in user 1
  (Alex Rivera). Signing in emits a `signup` event.
