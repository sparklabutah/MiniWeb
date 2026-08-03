# Live (StreamHub)

**Category**: Streaming & media
**Reviewer**: Reaz
**Number of macros**: 20

## Data Source

Custom-generated JSON data in `data_sources/live/`.

### Data Files

- `streams.json` -- 12 streams across Software Development, Fitness & Health, Gaming, Just Chatting
- `users.json` -- 5 users: Alex Rivera (viewer), Marcus Chen (coding streamer), Nathan Brooks (fitness), Natalie Kim (coding), Jake Morrison (startup)
- `chat_messages.json` -- 40 chat messages across streams
- `clips.json` -- 8 clips from various streams
- `subscriptions.json` -- 10 active subscriptions
- `channel_points.json` -- 6 channel point rewards across 3 channels
- `follows.json` -- 10 follow relationships
- `shares.json` -- initially empty, populated by share actions
- `reports.json` -- initially empty, populated by report actions
- `playback_states.json` -- initially empty, populated by playback/join actions

### Sampling

All data loaded by default (`num_data_points: -1`). Data is small enough to serve entirely.

## Real-World Model

**Twitch.tv** -- dark-themed live streaming platform. Key UI elements:
- Stream browse page with category nav bar and filter/sort dropdowns
- Stream detail page with video player, chat panel, streamer info
- Channel pages with stream history, clips, follow/subscribe buttons
- Clip gallery for highlights
- Subscription management page
- Login/register forms

## Target Macros

navigate_by_semantic, navigate_by_dropdown, navigate_by_route, search_by_query, filter_by_dropdown, sort_by_dropdown, select_by_slider, play_by_timestamp, play_by_playback, post_from_free_text, follow_by_toggle, share_by_dropdown, report_by_form, subscribe_by_toggle, join_by_toggle, pay_by_dropdown, redeem_by_dropdown, authenticate_by_form, register_by_form

## Temporal Dynamics

Live streaming is inherently temporal, but for benchmark purposes the data is a static snapshot. Streams have status "live" or "completed" as fixed properties. No temporal simulation is needed -- the benchmark tests interaction patterns, not real-time video delivery.

## Domain-Specific Notes

- Semantic search uses keyword-overlap scoring across stream titles, categories, and tags
- Categories: Software Development, Fitness & Health, Gaming, Just Chatting
- Playback state tracks timestamp (seconds), speed, quality, volume per user per stream
- Channel points are a virtual currency; users start with 5000 points and spend on per-channel rewards
- Gift subscriptions are a separate action from self-subscribing, using a tier dropdown
- Chat messages are persisted and displayed chronologically
- Clips reference a specific stream and a timestamp_seconds within that stream
