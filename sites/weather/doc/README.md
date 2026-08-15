# Weather

**Category**: Dynamic info / feeds
**Reviewer**: Minh
**Number of macros**: 15

## Data Source

OpenMeteo-inspired synthetic data for Lakeport, WA (fictional Pacific Northwest city).

## Target Macros

navigate_by_query, navigate_by_date_range, navigate_by_pan_zoom, search_by_query, search_by_proximity, filter_by_toggle, extract_by_dropdown, extract_by_toggle, extract_from_table, extract_by_date_range, compare_by_query, verify_by_slider, configure_by_slider, subscribe_by_toggle, save_by_query

## Site Description

Lakeport Weather is a local weather portal serving the fictional city of Lakeport, WA and surrounding PNW locations. It provides current conditions, 7-day forecasts, hourly forecasts, 30-day historical data, weather alerts, and saved-location management. Modeled after weather.gov and Weather Underground.

### Data files (data_sources/weather/)

- **current.json** -- Current conditions (temp, humidity, wind, UV, etc.)
- **forecast.json** -- 7-day forecast array
- **hourly.json** -- 24-hour hourly forecast array
- **historical.json** -- 30 days of historical weather records
- **locations.json** -- 10 PNW cities with lat/lng coordinates
- **alerts.json** -- 3 active weather alerts (Wind Advisory, Air Quality, Flood Watch)
- **users.json** -- 5 user accounts with saved locations, subscriptions, settings

### Temporal / dynamic behavior

The site simulates a weather portal snapshot frozen at 2026-06-27. Historical data covers the prior 30 days. Forecast data covers the next 7 days. Alerts are active and time-bounded.

### Key pages

| Route | Purpose |
|-------|---------|
| `/` | Current conditions + 7-day summary |
| `/forecast` | Extended 7-day forecast table |
| `/hourly` | 24-hour hourly forecast cards |
| `/history` | 30-day historical table with stats |
| `/alerts` | Active weather alerts |
| `/locations` | Saved locations management (login required) |
| `/login` | User authentication |

### Key API endpoints

| Endpoint | Macro support |
|----------|--------------|
| `GET /api/current?location=...` | navigate_by_query |
| `GET /api/current/units?units=metric` | filter_by_toggle |
| `GET /api/forecast?location=...&days=N` | navigate_by_query, extract_by_dropdown |
| `GET /api/forecast/extended?extended=true` | extract_by_toggle |
| `GET /api/hourly` | extract_from_table |
| `GET /api/historical?date_from=...&date_to=...` | extract_by_date_range, navigate_by_date_range |
| `GET /api/history/date/YYYY-MM-DD` | navigate_by_date_range |
| `GET /api/search?q=...` | search_by_query |
| `GET /api/nearby?lat=...&lng=...&radius=...` | search_by_proximity |
| `GET /api/compare?locations=A,B` | compare_by_query |
| `GET /api/alerts` | extract_from_table |
| `GET /api/alerts/filter?severity=...` | filter_by_toggle |
| `GET /api/locations/all` | navigate_by_pan_zoom |
| `GET /api/verify_temp?temp_f=...` | verify_by_slider |
| `POST /api/users/N/settings` | configure_by_slider |
| `POST /api/users/N/subscribe` | subscribe_by_toggle |
| `POST /api/users/N/save_location` | save_by_query |
| `POST /api/login` | authenticate_by_form |
