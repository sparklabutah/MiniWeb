# FitTrack (`health-fitness-tracking`)

A personal health and fitness dashboard modeled on MyFitnessPal and Fitbit Web.
Users log and review workouts, keep a daily food diary, track daily stats
(steps, sleep, calories, water, weight) and manage fitness goals and targets.

- URL: `/sites/health-fitness-tracking/` (simulated domain `fitpulse.health`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Overview dashboard: daily charts, recent activity, calorie budget |
| `/workouts` | Activity log with Type dropdown and From/To dates |
| `/workout/<id>` | Workout detail: exercises and metrics |
| `/log-workout` | Log-workout form (date, type, duration, calories, notes) |
| `/nutrition` | Food diary by day (`?date=`), food search with servings and Log Food, remove entries |
| `/stats` | Trends: weekly/monthly summary with From/To range and charts |
| `/log-editor` | Daily Log Editor: inline-editable daily-stats grid with add row and Save Changes |
| `/goals` | Goals, Daily Targets sliders, "Days Above Threshold" computation, Verify Goals with a tolerance slider |
| `/login` | Sign-in form |

JSON endpoints under `/api/` cover workouts, daily stats, nutrition, goals,
food search, stats summaries, user settings and export (CSV or JSON).

## Interactions and macros

- Filter workouts by type or by a date range: `filter_by_dropdown`, `filter_by_date_range`
- Open a workout: `navigate_by_route`
- Log a workout or a food entry: `create_by_form`
- Remove a food entry: `delete_from_table`
- Edit daily-stat cells in the log editor: `edit_by_cell`
- Set daily targets with sliders: `configure_by_form`
- Count days above a slider threshold: `compute_by_tool`
- Read workout tables, trend summaries and goal verdicts: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `health-fitness-tracking`.

## Data

- Source: Zenodo fitness-tracker dataset (record 53894), plus synthetic data.
- Tables (`health_fitness_tracking_*`): `workouts`, `daily_stats`, `nutrition`,
  `goals`, `foods` (USDA-style food database), `users`.
- Login uses `session["user_id"]` (via `helpers.auth`), so the global
  auto-login signs in user 1.
- Logging a workout emits a `booking` event, which adds a calendar event in
  calendar-todo and sends a confirmation email. Signing in emits `signup`.
