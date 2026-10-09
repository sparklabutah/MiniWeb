# Lakeport Sports Hub (`sports-esports`)

A multi-sport scoreboard in the style of ESPN / Flashscore covering the NFL,
NBA, MLB, MLS, Premier League and a local esports league. It shows live,
final and scheduled matches, standings, team and player pages, a team
comparison tool, match highlights, comments and a favorites list.

- URL: `/sites/sports-esports/` (simulated domain `lakeportsports.com`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Scoreboard with league pills and match cards |
| `/league/<id>` | League standings, with a subscribe toggle |
| `/standings` | Standings table (Rank, Team, W, L, Win%) with a "Min Wins" slider |
| `/team/<id>` | Team roster, record and match history, with a favorite toggle |
| `/match/<id>` | Match score, rosters and comment form |
| `/match/<id>/highlights` | Highlight video in the shared mini-player |
| `/players`, `/player/<id>` | Player search with league/team dropdowns; player stats |
| `/compare` | Team A vs Team B comparison table |
| `/favorites` | Favorite teams and players: search and add/remove, matches filtered by From/To dates |
| `/login` | Sign-in form |

JSON endpoints under `/api/` cover leagues, teams, matches, players, standings, search, compare, favorites, comments and subscriptions.

## Interactions and macros

- Search players, or teams and players on the Favorites page: `search`
- Filter players by league or team: `filter_by_dropdown`
- Filter standings with the "Min Wins" slider: `filter_by_slider`
- Filter favorite teams' matches by date: `filter_by_date_range`
- Open matches, teams and players: `navigate_by_route`
- Favorite a team or player, subscribe to a league: `toggle_relationship`, `feedback_by_react`
- Comment on a match: `create_by_form`
- Play a match highlight: `play_by_playback`
- Read standings, rosters, stats and comparisons: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `sports-esports`.

## Data

- Tables: `sports_esports_leagues`, `sports_esports_teams`,
  `sports_esports_matches`, `sports_esports_players`,
  `sports_esports_favorites`, `sports_esports_users`.
- The data is a frozen snapshot of one match day. Match `status`
  (live / final / scheduled), quarter and clock never advance.
- Login goes through `helpers.auth` on `session["user_id"]`, so the global
  auto-login signs in user 1.
- Match comments and league subscriptions are saved to `comments` and
  `subscriptions` collections that have no base table, so `db.query` cannot
  read them back. Graders see those writes only in the request log.
