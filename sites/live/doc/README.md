# PulseLive (`live`)

A Twitch-style live-streaming platform. Viewers browse live and past streams, watch with a seekable player and live
chat, follow and subscribe to channels, cheer and redeem channel points, and
browse clips.

- URL: `/sites/live/` (simulated domain `livestream.tv`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Stream browser: search plus Category, Status, Streamer and Sort By dropdowns, live chat preview |
| `/stream/<id>` | Player with seek bar and "Jump to" time, live chat, Cheer dropdown, Follow, Share, Report |
| `/channel/<user_id>` | Channel: past streams, clips, Follow/Subscribe, gift subs, channel-point rewards with Redeem |
| `/clips`, `/clip/<id>` | Clip gallery (search, channel dropdown) and clip detail |
| `/subscriptions` | Your active subscriptions |
| `/login`, `/register` | Sign-in and sign-up forms |

JSON endpoints under `/api/` cover streams, search, chat, clips, channels
(follow, subscribe, gift, redeem), playback state, shares, reports and stats.

## Interactions and macros

- Search streams; filter by category, status, streamer or clip channel: `search`, `filter_by_dropdown`
- Sort streams (Most Viewed, Newest, Oldest, Longest): `sort_by_form`
- Open a stream, a channel or the clips page: `navigate_by_route`
- Seek or jump to a timestamp in the player: `play_by_playback`
- Post a chat message or register an account: `create_by_form`
- Cheer channel points: `pay_by_form`; redeem a reward: `checkout_by_form`
- Follow or subscribe to a channel: `toggle_relationship`
- Share a stream: `share_by_form`; sign in: `authenticate_by_form`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `live`.

## Data

- Tables (`live_*`): `streams`, `chat_messages`, `clips`, `channel_points`,
  `follows`, `subscriptions`, `users`.
- Auth is site-specific on purpose: login uses `session["live_user_id"]`, so
  the global auto-login does not apply. Logged-out visitors browse as the
  first user; follow, subscribe, chat and redeem need an explicit login.
- The stream and home pages poll `/api/chat/live` without end. That has hung
  browser-agent harnesses that wait for the network to go idle.
- Registering emits a `signup` event (password-vault entry and welcome email).
