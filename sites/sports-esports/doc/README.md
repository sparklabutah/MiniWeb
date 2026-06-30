# Sports / Esports

**Category**: Dynamic info / feeds
**Reviewer**: Minh
**Number of macros**: 23

## Data Source

Synthetic data inspired by TheSportsDB and real league structures. Six JSON files in `data_sources/sports-esports/`:
- `leagues.json` -- 6 leagues (NFL, NBA, MLB, MLS, EPL, Lakeport Esports League)
- `teams.json` -- 20 teams across all leagues, with win/loss/standing records
- `matches.json` -- 30 matches (live, final, scheduled) with scores and venues
- `players.json` -- 25 players with position-specific stats
- `users.json` -- 5 registered users with credentials
- `favorites.json` -- per-user favorite teams and players
- `comments.json` -- match comments (initially empty, populated by tasks)
- `subscriptions.json` -- league notification subscriptions (initially empty)

### Data Format

All files are JSON arrays of objects. Teams have `wins`, `losses`, `standing` fields.
Players have a `stats` dict with sport-specific keys (e.g., `passing_yards` for football,
`points_per_game` for basketball, `goals` for soccer, `kills`/`kd_ratio` for esports).

## Real-World Model

**ESPN / TheSportsDB / Flashscore** -- multi-sport scoreboard with live scores, standings tables,
player directories, and fan engagement features. Key UI elements:
- League pill navigation on homepage
- Live/recent/upcoming match cards on scoreboard
- Per-league standings tables (rank, W, L, Win%)
- Player search with league/team dropdown filters
- Team detail pages with roster and match history
- Match detail pages with scoreboard and player rosters
- Team comparison page with side-by-side stats
- Favorites system for teams and players
- Match comments and reactions
- League subscription notifications

## Target Macros

navigate_by_dropdown, navigate_by_route, navigate_by_ranking, search_by_query,
search_by_semantic, filter_by_dropdown, filter_by_date_range, sort_by_ranking,
extract_by_query, extract_from_table, extract_by_route, extract_by_extremum,
extract_by_slider, compute_from_table, compare_by_dropdown, verify_by_slider,
play_by_playback, post_from_free_text, react_by_toggle, follow_by_dropdown,
follow_by_toggle, subscribe_by_toggle, save_by_toggle

## Temporal Dynamics

Matches have `status` field (live/final/scheduled) to simulate real-time game progression.
Live matches include `quarter` and `clock` fields. The data snapshot represents a single
point in time during a multi-sport day. No active time simulation is needed -- the frozen
snapshot provides enough variety for task evaluation.

## Domain-Specific Notes

- Semantic search: keyword-overlap scoring across team names, cities, player names, positions
- Win percentage computed dynamically as `wins / (wins + losses)`
- Standings are per-league, ordered by the `standing` field
- Esports players have gamertags in quotes within their names (e.g., Alex 'Phantom' Kim)
- Comments and subscriptions are mutable state, reset from .pristine between eval runs
