# Remote Calls (CallHub)

**Category**: Communication
**Reviewer**: Farhan
**Number of macros**: 19

## Data Source

Synthetic meeting/call data for a fictional company (Meridian Systems). Users, meetings, recordings, and call logs are stored as JSON in data_sources/remote-calls/.

### Data Format

Four JSON files, each an array of objects:

- `users.json` -- 8 users with id (rc-u-XXX), root_user_id, display_name, email, username, plan, timezone, status
- `meetings.json` -- 18 meetings with id (mtg-XXX), title, host_id, participants (list of user ids), date (ISO w/ tz), duration_minutes, type (work/personal), recording_available, status (scheduled/completed/cancelled)
- `recordings.json` -- 6 recordings with id (rec-XXX), meeting_id, title, recorded_by, date, duration_minutes, file_size_mb, format, transcript_available, access (team/organization), views
- `call_log.json` -- 25 calls with id (call-XXX), caller_id, callee_id, type (audio/video), date, duration_seconds, status (completed/missed), note

Additionally, `messages.json` and `settings.json` are created at runtime for chat messages and user settings respectively.

### Sampling

Data is fully synthetic and small (8 users, 18 meetings, 6 recordings, 25 calls). No sampling needed; all records are loaded.

## Real-World Model

**Zoom / Microsoft Teams / Google Meet** -- corporate video conferencing platform. Key UI elements:
- Dashboard with upcoming meetings, recent meetings, recent calls
- Meetings list page with filters (status, type, participant, date range, search)
- Meeting detail page with participant list, recording link, share toggle, invite form, chat
- Recordings list with search and playback
- Call log with filters (type, status, contact, date range)
- Schedule meeting form
- Join by meeting code
- User settings page (camera, mic, background, notifications)

## Target Macros

navigate_by_route, search_by_query, search_by_semantic, filter_by_dropdown, filter_by_date_range, extract_by_query, extract_from_table, extract_by_route, submit_by_query, select_by_dropdown, configure_by_dropdown, play_by_playback, export_by_dropdown, share_by_toggle, invite_by_form, message_from_free_text, book_by_form, cancel_by_form, join_by_code

## Temporal Dynamics

Not applicable -- meeting/call data is a synthetic snapshot of a two-week period. No temporal simulation needed.

## Domain-Specific Notes

- Semantic search: simple keyword-overlap matching over meeting titles, types, statuses, and participant display names
- Authentication: session-based login via username; any non-empty password accepted (MiniWeb convention)
- Share toggle: generates/revokes a share link for a meeting (share_link_active flag)
- Play recording: increments view count on POST to /api/recordings/<id>/play
- Meeting chat: stored in messages.json keyed by meeting_id
- Join by code: meeting ID serves as the join code (e.g., "mtg-005")
- Cancel: sets meeting status to "cancelled" (cannot cancel completed meetings)
- Export: supports CSV and JSON for meetings, calls, and recordings
