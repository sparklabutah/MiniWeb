This website simulates a music streaming service (Spotify-style). The interface lets users browse artists, albums, and tracks, create playlists, manage a personal library, and control playback. The front end should emulate Spotify's layout: dark theme, sidebar navigation, and card-based content.

Data source: data_sources/music/ (artists.json, albums.json, tracks.json, playlists.json, library.json, users.json, playback.json, shares.json, subscriptions.json)
Searching method: keyword match and lightweight semantic (keyword-overlap) scoring across artist names, album titles, track titles, genres, and bios.
