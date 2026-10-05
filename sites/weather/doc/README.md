# Lakeport Weather (`weather`)

A local weather portal for the fictional city of Lakeport, WA and nearby Pacific
Northwest stations, modeled on weather.gov and Weather Underground. It shows
current conditions, forecasts, a multi-year history archive and active alerts,
and lets a signed-in user keep a list of saved locations.

- URL: `/sites/weather/` (simulated domain `lakeportweather.com`)
- Data split: held-out (test) site

## Pages

| Route | Page |
|---|---|
| `/` | Current conditions, 7-day summary, location search, past-weather lookup, two-location compare |
| `/forecast` | 7-day forecast table (`?location=`), with an "extended details" switch |
| `/hourly` | 24-hour forecast cards |
| `/history` | Historical table; defaults to the latest 30 days, `date_from`/`date_to` select a range |
| `/alerts` | Active alerts with severity toggles and per-alert subscribe switches |
| `/locations` | Saved locations: add, quick-save by name, remove, station and nearby search (login required) |
| `/login` | Sign-in form |

The pages are backed by JSON endpoints under `/api/` (`current`, `forecast`,
`hourly`, `historical`, `alerts`, `locations`, `search`, `nearby`, `compare`,
`users/<id>/settings`, `users/<id>/subscribe`).

## Interactions and macros

- Look up a station by name on the home page or the Locations page: `search`
- Pick a history date range: `filter_by_date_range`
- Switch F/C units, toggle alert severities: `filter_by_options`
- Add a saved location: `create_by_form`
- Save or remove a location, subscribe to an alert type: `toggle_relationship`
- Read forecast, hourly, history and compare tables: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `weather`.

## Data

- Tables: `weather_current`, `weather_forecast`, `weather_hourly`,
  `weather_historical`, `weather_alerts`, `weather_locations`, `weather_users`.
- Dates are a fixed snapshot and are never shifted. The history page anchors
  its default range to the newest archived day.
- Login uses the site's own `session["weather_user_id"]`, so the global
  auto-login does not sign the user in here. Saving locations and subscribing
  need an explicit login.
- Subscribing to an alert type sends a confirmation email to the WebMail inbox
  (`app/handlers/email_handler._add_email`).
