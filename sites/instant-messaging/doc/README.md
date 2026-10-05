# QuickChat (`instant-messaging`)

A WhatsApp Web / Telegram-style messenger: a dark split-pane view with the
conversation list on the left and the chat on the right, plus a contacts page.
The user is Alex Rivera (`im-u001`), chatting with friends, family and a
neighborhood group.

- URL: `/sites/instant-messaging/` (simulated domain `quickchat.app`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Conversation list: search, sort (Recent, Name, Unread), From/To date filter, pin toggles |
| `/conversation/<conv_id>` | Chat: send, edit, delete and star messages, attach a file, share link, Join Group on group invites |
| `/message/<user_id>` | Opens (or creates) a direct chat with a contact |
| `/contacts`, `/contact/<user_id>` | Contacts with add-by-username and Block toggles; contact detail with an edit form |
| `/join/<conv_id>` | Invite link that joins a group chat |
| `/login` | Sign-in form |

JSON endpoints under `/api/` cover conversations, messages (search, edit, star,
report, share), contacts (block), media, upload, pin, invite and export.

## Interactions and macros

- Send a message: `message_from_free_text`, `create_by_form`
- Add a contact by username: `create_by_form`
- Edit or delete a sent message: `edit_by_form`, `delete_from_table`
- Search chats, sort the list, filter it by date: `search`, `sort_by_form`, `filter_by_date_range`
- Pin a chat, star a message, block a contact: `toggle_relationship`
- Attach a file in a chat: `upload_file`
- Copy a chat link: `share_by_form`
- Join a group chat from its invite: `join_meeting`
- Read messages and search results: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `instant-messaging`.

## Data

- Tables: `instant_messaging_conversations`, `instant_messaging_messages`,
  `instant_messaging_media`, `instant_messaging_users`. User ids look like
  `im-u001`; conversation ids like `conv-001`.
- Login uses the site's own `session["im_user_id"]`. A site-level hook mirrors
  the global auto-login and signs in `im-u001` unless `_no_autologin` or
  `MINIWEB_NO_AUTOLOGIN` is set.
- Other sites post here through the `message` event
  (`app/handlers/im_handler.py`), for example brokerage trade notices, and the
  shared Share dialog (`miniweb-share.js`) can send a page link to a chat.
- Uploaded media is stored inline in the session overlay (2 MB cap).
- Logging in emits `signup` (password-vault entry and welcome email).
