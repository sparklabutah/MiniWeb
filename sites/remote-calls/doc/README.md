# CallHub (`remote-calls`)

A Zoom, Teams or Google Meet-style video-calling platform for the fictional
company Meridian Systems. Users schedule and join meetings, watch recordings
and read transcripts, review their call log, and chat inside a simulated call
room.

- URL: `/sites/remote-calls/` (simulated domain `meetwave.app`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Dashboard: upcoming and recent meetings, recent calls |
| `/meetings` | Meetings table with title search, status/type/participant dropdowns and a From/To range |
| `/meeting/<id>` | Meeting detail: participants, recording link, Share (copy link), invite by email, Cancel Meeting |
| `/meeting/<id>/call` | Simulated in-call room: mic, camera and chat controls, Leave |
| `/recordings`, `/recording/<id>` | Recording list with search; recording detail with a player |
| `/recording/<id>/transcript` | Full transcript |
| `/call-log` | Call history with type/status/contact dropdowns and a From/To range |
| `/schedule` | Schedule a Meeting form (title, date and time, duration, type, participant checkboxes, file attachment) |
| `/join` | Join by meeting code (for example `mtg-005`) |
| `/settings` | Notification sound, background and language settings |
| `/login` | Sign-in form |

JSON endpoints under `/api/` cover meetings, search, recordings and playback,
call log, sharing, invites, meeting chat, join, settings and export.

## Interactions and macros

- Search meetings or recordings: `search`
- Filter meetings or calls by dropdowns or dates: `filter_by_dropdown`, `filter_by_date_range`
- Schedule a meeting: `book_by_form`, `create_by_form`, with an attachment via `upload_file`
- Invite someone by email: `create_by_form`
- Join a meeting by code: `join_meeting`
- Chat in the call room: `message_from_free_text`
- Cancel a meeting, copy its share link: `cancel_by_form`, `share_by_form`
- Play a recording (reveals exact runtime, resolution and chapters): `play_by_playback`
- Change settings: `configure_by_form`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `remote-calls`.

## Data

- Tables: `remote_calls_users`, `remote_calls_meetings`,
  `remote_calls_recordings`, `remote_calls_call_log`, `remote_calls_messages`.
- Site user ids look like `rc-u-001`. The session stores the shared root user
  id, which is mapped to the site user through `root_user_id`, so the global
  auto-login signs the user in as Alex Rivera.
- Scheduling a meeting calls `on_booking`, which adds a calendar event and
  sends a booking email.
