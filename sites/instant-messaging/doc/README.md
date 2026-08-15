# Instant Messaging

**Category**: Communication
**Reviewer**: Farhan
**Number of macros**: 22

## Data Source

Synthesized JSON files representing Alex Rivera's messaging life: conversations with a best friend (Marcus Chen), sister (Elena Vasquez), dad (James Rivera), college friend (Sophie Lin), gym buddy (Daniel Okonkwo), recent date (Mia Torres), childhood friend / startup founder (Jake Morrison), and a neighborhood group chat (Maple Ln Neighbors).

Files in `data_sources/instant-messaging/`:
- `users.json` -- 8 user profiles (id, display_name, phone, email, status, about)
- `conversations.json` -- 8 conversations (7 direct, 1 group) with metadata (participants, message_count, pinned_count, muted)
- `messages.json` -- 96 messages across conversations with timestamps, read status, and optional media_id
- `media.json` -- 10 media attachments (images, audio, documents) with file metadata

### Data Format

**users.json**: Array of user objects. Fields: id (im-uNNN), root_user_id, display_name, phone, email, status (online/offline), last_seen, profile_photo, about.

**conversations.json**: Array of conversation objects. Fields: id (conv-NNN), type (direct/group), participants (user id list), participant_names, created, last_message (timestamp), message_count, pinned_count, muted. Group conversations additionally have name, group_photo, admin.

**messages.json**: Array of message objects. Fields: id (im-msg-NNN), conversation_id, sender_id, timestamp, text, read (boolean), media_id (nullable).

**media.json**: Array of media objects. Fields: id (media-NNN), conversation_id, sender_id, timestamp, type (image/audio/document), mime_type, file_name, file_path, file_size_bytes, caption, thumbnail_path.

### Sampling

Data is small enough to load entirely. num_data_points=-1 loads all records.

## Real-World Model

**WhatsApp Web / Telegram Desktop** -- Dark-themed split-pane messaging interface. Key UI elements:
- Left sidebar with conversation list sorted by recency, search bar at top
- Conversation items show avatar, contact name, last message preview, timestamp
- Main chat panel with message bubbles (sent right, received left), timestamps
- Chat header with contact name, status, action buttons (pin, search, block)
- Contacts page listing all contacts with status indicators
- Login page for user selection
- Group chat features: invite members, join via link

## Target Macros

navigate_by_semantic, navigate_by_dropdown, navigate_by_route, search_by_query, search_by_dropdown, filter_by_toggle, extract_by_query, extract_by_route, create_from_free_text, edit_by_form, delete_from_table, upload_by_upload, post_from_free_text, follow_by_toggle, join_by_route, share_by_dropdown, save_by_toggle, invite_by_form, report_by_form, block_by_toggle, message_from_free_text, authenticate_by_form

## Temporal Dynamics

Not applicable -- messaging data is a static snapshot of conversation history. No temporal simulation needed.

## Domain-Specific Notes

- Current user is always Alex Rivera (im-u001). All actions are performed from Alex's perspective.
- "post_from_free_text" and "message_from_free_text" both map to sending a new message in a conversation (create message via free text input).
- "create_from_free_text" maps to creating a new conversation.
- "follow_by_toggle" maps to pinning/unpinning a conversation (WhatsApp's pin feature).
- "save_by_toggle" maps to starring/unstarring an individual message.
- "search_by_dropdown" maps to searching within a specific conversation (selected via dropdown/navigation).
- "filter_by_toggle" filters conversation list by unread/starred/muted status.
- "share_by_dropdown" forwards a message to another conversation.
- "block_by_toggle" blocks/unblocks a contact.
- "invite_by_form" invites a user to a group conversation.
- "report_by_form" reports a message with a reason.
- "join_by_route" joins a group conversation via invite link.
- "upload_by_upload" sends a media attachment to a conversation.
- "navigate_by_semantic" performs fuzzy search across contacts and conversations.
