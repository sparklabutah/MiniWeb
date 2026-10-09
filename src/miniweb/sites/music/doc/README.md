# SoundWave (`music`)

A Spotify-style music streaming site with a dark theme and a persistent
bottom player. Users browse artists, albums and tracks, play music, like
tracks and albums, follow and subscribe to artists, build playlists and share.

- URL: `/sites/music/` (simulated domain `soundwave.fm`)
- Data split: held-out (test) site

## Pages

| Route | Page |
|---|---|
| `/` | Home: featured artists, new releases, popular tracks |
| `/browse`, `/genre/<name>` | Artists and albums, filtered by genre pills |
| `/artist/<id>` | Artist: top tracks, discography, Follow, More menu, Share, Subscribe |
| `/album/<id>` | Album track list with like buttons |
| `/track/<id>` | Track detail: Play, Like, Add to Playlist dropdown, Share |
| `/playlists`, `/playlist/<id>` | The user's playlists and one playlist's tracks |
| `/playlists/create` | New playlist form (name, description, visibility) |
| `/library` | Liked songs, saved albums and followed artists tabs |
| `/search?q=`, `/search/<query>` | Search results split into artists, albums and tracks |
| `/login` | Sign-in form |

JSON endpoints under `/api/` cover the catalog, playlists, likes, follows, playback state (`/api/play`, `/api/play/date_range`, `/api/playback`) and shares.

## Interactions and macros

- Search the catalog from the header: `search`
- Narrow Browse by genre (registered as `filter_by_dropdown`; the page uses genre pills): `filter_by_dropdown`
- Open artists, albums and tracks: `navigate_by_route`
- Create a playlist, add a track to a playlist: `create_by_form`
- Play a track in the bottom player: `play_by_playback`
- Like a track or album, follow or subscribe to an artist: `toggle_relationship`
- Share a track or artist through the MiniWeb share dialog: `share_by_form`
- Read search results and catalog details: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `music`.

## Data

- Tables: `music_artists`, `music_albums`, `music_tracks` (MusicBrainz-style
  catalog), `music_playlists`, `music_library`, `music_users`, plus
  `music_playback`, `music_subscriptions` and `music_shares`, which the site
  creates on first use.
- Playback is simulated state (queue, position, volume); no real audio streams.
- Login reads `session["user_id"]`, so the global auto-login signs in as user 1.
- Logging in emits `signup` (password-vault entry and welcome email).
