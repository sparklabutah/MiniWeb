# FitTrack - Health & Fitness Tracking Dashboard

## Domain
FitTrack is a personal health and fitness tracking web application modeled after MyFitnessPal and Fitbit Web Dashboard. It targets active individuals who want to log workouts, track daily health stats (steps, sleep, weight, water intake), monitor nutrition/macros, and set fitness goals.

## Data Sources
- **users.json** - User profiles with connected devices, fitness goals, and activity levels (5 users)
- **workouts.json** - Workout log entries with type, duration, calories, heart rate, exercises, location (70 entries)
- **daily_stats.json** - Daily health metrics: steps, distance, calories burned, active minutes, sleep, water, weight (90 entries)
- **nutrition.json** - Meal log with calories and macronutrient breakdown (30 entries)
- **goals.json** - Fitness goals per user with categories, targets, and progress notes (5 user records)

## Real-World Model
Modeled after **MyFitnessPal** (nutrition tracking, food search) crossed with **Fitbit Web Dashboard** (activity stats, workout logs, goal tracking, device integration).

## Key Features
- Dashboard with today's stats, weekly overview, recent workouts, active goals, nutrition summary
- Workout log with filtering by type (dropdown) and date range; detailed per-workout view
- Nutrition log grouped by date with daily macro totals
- Goals page with progress tracking
- Stats page with weekly/monthly aggregate views
- Workout replay timeline (synthesized from workout data)
- Daily stats playback animation (time-series)
- Data export (CSV/JSON) for workouts, stats, nutrition
- User settings with configurable daily targets (sliders)
- Search across workouts and meals (text and semantic)

## Temporal Dynamics
Daily stats represent time-series data. The site supports date-range filtering and playback animation of metrics over time. No real-time simulation needed since data represents historical tracking.
