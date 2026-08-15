# Health & fitness tracking

**Category**: Health
**Reviewer**: Farhan
**Number of macros**: 26

## Data Source

https://zenodo.org/records/53894

## Target Macros

navigate_by_dropdown, navigate_by_route, search_by_query, search_by_semantic, filter_by_dropdown, filter_by_date_range, sort_by_ranking, extract_by_dropdown, extract_from_table, extract_by_route, extract_by_date_range, compute_by_dropdown, compute_by_extremum, compute_by_slider, compare_by_date_range, verify_by_slider, create_from_free_text, create_by_checkbox, submit_by_query, edit_by_form, delete_from_table, select_from_table, configure_by_slider, play_by_dropdown, play_by_playback, export_by_dropdown

## Site Description

FitTrack is a personal health and fitness tracking dashboard modeled after MyFitnessPal / Fitbit Web. It serves active individuals who want to log workouts, track daily health metrics (steps, sleep, weight, water intake), monitor nutrition/macros, and manage fitness goals.

### Data files in data/
- **users.json** -- User profiles with connected devices, fitness goals, activity levels
- **workouts.json** -- Workout log entries (type, duration, calories, heart rate, exercises, location)
- **daily_stats.json** -- Daily health metrics (steps, distance, calories, active minutes, sleep, water, weight)
- **nutrition.json** -- Meal log with calories and macronutrient breakdown
- **goals.json** -- Per-user fitness goals with categories, targets, progress

### How macros map to UI
- **navigate_by_dropdown**: User profile selector in nav
- **navigate_by_route**: Click workout to view detail page
- **search_by_query**: Text search across workouts and meals
- **search_by_semantic**: Keyword-overlap relevance search on workouts
- **filter_by_dropdown**: Filter workouts by type dropdown
- **filter_by_date_range**: Filter workouts/stats by date range
- **sort_by_ranking**: Sort workouts by date/duration/calories/heart_rate
- **extract_by_dropdown**: Get aggregate stats for a workout type
- **extract_from_table**: Compare multiple workouts side-by-side
- **extract_by_route**: View single workout details
- **extract_by_date_range**: Get daily stats for a date range
- **compute_by_dropdown**: Aggregate workout statistics by type
- **compute_by_extremum**: Find workout with max/min metric
- **compute_by_slider**: Count days above a threshold
- **compare_by_date_range**: Compare two date windows of stats
- **verify_by_slider**: Check if goal target is met with tolerance
- **create_from_free_text**: Log a new workout or meal via form
- **create_by_checkbox**: Create workout from checkbox-selected exercises
- **submit_by_query**: Search-and-submit a meal by description
- **edit_by_form**: Update workout or goal details
- **delete_from_table**: Delete a workout or meal entry
- **select_from_table**: Select workouts for comparison
- **configure_by_slider**: Set daily step/calorie/water targets
- **play_by_dropdown**: Replay workout timeline by type
- **play_by_playback**: Animate daily stats time-series
- **export_by_dropdown**: Export data as CSV or JSON

### Temporal dynamics
Daily stats represent historical time-series data. Date-range filtering and playback animation support temporal exploration. No real-time simulation required.
