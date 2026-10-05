# SoundShelf (`podcasts-audiobooks`)

A podcast and audiobook app in the style of Apple Podcasts and Audible.
Users discover shows, play episodes, subscribe to and follow podcasts, buy
audiobooks into their library, like and save items, and write reviews.

- URL: `/sites/podcasts-audiobooks/` (simulated domain `podstream.fm`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Discover: trending podcasts, top audiobooks, recent episodes |
| `/podcasts` | All podcasts, filtered by category tabs |
| `/podcast/<id>` | Podcast detail: episodes, Subscribe, Follow, review form |
| `/episode/<id>` | Episode player: play/pause, speed select, Like, Save |
| `/audiobooks` | Audiobooks with genre tabs, min-rating and max-duration sliders |
| `/audiobook/<id>` | Audiobook detail: Buy, Like, review form with rating slider |
| `/library` | Subscriptions, saved episodes and purchased audiobooks |
| `/search?q=` | Results across podcasts, episodes and audiobooks |
| `/login` | Sign-in form |

JSON endpoints under `/api/` cover the catalog, library actions, playback speed/progress, reviews, stats and export.

## Interactions and macros

- Search podcasts, episodes and audiobooks: `search`
- Filter podcasts by category or audiobooks by genre (registered as `filter_by_dropdown`; the pages use tabs): `filter_by_dropdown`
- Filter audiobooks by minimum rating and maximum duration: `filter_by_slider`
- Play an episode and change speed: `play_by_playback`
- Subscribe to or follow a podcast, save an episode: `toggle_relationship`
- Like an episode or audiobook: `feedback_by_react`
- Write a review with a rating slider: `create_by_form`, `feedback_by_star`
- Read search results and details: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `podcasts-audiobooks`.

## Data

- Tables: `podcasts_audiobooks_podcasts`, `_episodes`, `_audiobooks`,
  `_library`, `_reviews`, `_users`, plus raw source tables `_books_raw` and
  `_ratings_raw`.
- Buying an audiobook adds it to the library; no payment or banking entry is made.
- Login reads `session["user_id"]`, so the global auto-login signs in as user 1.
  Logging in emits `signup` (password-vault entry and welcome email).
