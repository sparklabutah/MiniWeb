# Meridian Chat (`team-chat-workspace`)

A Slack or Microsoft Teams-style workspace for the employees of the fictional
Meridian Systems. Users read and post in channels, reply in threads, react,
save and share messages, send direct messages, upload files and manage channel
membership.

- URL: `/sites/team-chat-workspace/` (simulated domain `meridianchat.work`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Workspace home: channel sidebar with sort, Create Channel and Follow Member forms, default channel view |
| `/channel/<channel_id>` | Channel: messages with in-channel search and a date filter, composer with file upload, per-message edit/delete/save/react, Follow, Invite, Share |
| `/threads`, `/thread/<thread_id>` | Threads across channels with channel dropdown and From/To dates; full thread with replies |
| `/members` | Member directory with a department dropdown and Block toggles |
| `/dms`, `/dm/<user_id>` | Direct-message hub and 1:1 conversations |
| `/search` | Message search with a channel dropdown |
| `/login` | Sign-in form |

JSON endpoints under `/api/` cover channels, messages, threads, reactions,
DMs, search, members, uploads, follow/join/save/block/invite/share and export.

## Interactions and macros

- Search messages: `search`
- Filter by channel, department or dates: `filter_by_dropdown`, `filter_by_date_range`
- Sort the channel list: `sort_by_form`
- Post a message, reply in a thread, send a DM: `message_from_free_text`
- Create a channel, invite a member: `create_by_form`
- Edit or delete your own message: `edit_by_form`, `delete_from_table`
- Follow a channel or member, save a message, block a member: `toggle_relationship`
- Upload a file to a channel, copy a channel link: `upload_file`, `share_by_form`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `team-chat-workspace`.

## Data

- Tables: `team_chat_workspace_channels`, `team_chat_workspace_messages`,
  `team_chat_workspace_threads`, `team_chat_workspace_reactions`,
  `team_chat_workspace_users`.
- Site user ids look like `tc-u001`. The session stores the shared root user
  id, which is mapped through `root_user_id`, so the global auto-login signs the
  user in as Alex Rivera (`tc-u001`).
- A channel message that mentions a meeting ("meeting", "standup", "sync",
  "let's meet", ...) emits a `booking` event that adds a calendar event.
  Logging in emits `signup`.
