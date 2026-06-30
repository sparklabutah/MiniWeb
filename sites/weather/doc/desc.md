This website is a weather service for Lakeport, WA and surrounding PNW locations, similar to Weather.com or AccuWeather. It provides current conditions, 7-day forecasts, hourly forecasts, historical data, and weather alerts.

Data source: data_sources/weather/ — current.json (current conditions), forecast.json (7-day forecast), hourly.json (24-hour hourly), historical.json (30 days historical), locations.json (10 saved locations), alerts.json (3 weather alerts), users.json.

Real-world model: Weather.com / AccuWeather / Dark Sky. Card-based layout with current conditions prominently displayed, forecast grid below, and alert banners.

Temporal dynamics: Weather is inherently dynamic. The current implementation uses a static snapshot but could be extended with a time-step ticker that shifts the forecast window forward. For now, data represents a frozen moment in late June 2026.

Domain-specific notes: Lakeport, WA is a fictional PNW city (~55k pop). June weather is 60-75°F, partly cloudy with occasional rain. The site supports metric/imperial toggle, location search, and proximity-based nearby weather. Alert severity levels: Minor, Moderate, Severe.
