# CalcTools (`converters-calculators`)

A free unit-converter and calculator site modeled on Calculator.net. It offers
length, weight, temperature, currency, volume, area, speed and number-base
converters plus BMI, mortgage and tip calculators. Signed-in users can save
results and see their conversion history.

- URL: `/sites/converters-calculators/` (simulated domain `convertall.tools`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Tool directory: unit-converter and calculator cards, history export link |
| `/converter/<tool>` | Converter (`length`, `weight`, `temperature`, `currency`, `volume`, `area`, `speed`, `base`): value, from/to unit dropdowns, result and a save form |
| `/calculator/<tool>` | Calculator (`bmi`, `mortgage`, `tip`): inputs, result and a save form |
| `/dashboard` | Saved conversions and conversion history |
| `/login` | Sign-in form |

Conversions run server-side through JSON endpoints (`/api/convert/<category>`,
`/api/calculate/<tool>`); `/api/export` downloads the history as JSON or CSV.

## Interactions and macros

- Open a converter or calculator from the directory: `navigate_by_route`
- Enter a value, pick units and run Convert/Calculate: `compute_by_tool`
- Save a result to the dashboard: `create_by_form`
- Read results, unit lists and saved conversions: `report_information`
- Find a tool through the category links: `search`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `converters-calculators`.

## Data

- Tables: `converters_calculators_conversions` (unit definitions and USD-based
  exchange rates), `converters_calculators_history`, `converters_calculators_users`.
- Results are computed with deterministic formulas; currency rates are fixed.
- Login uses `session["user_id"]`, so the global auto-login signs in user 1.
- No cross-site effects.
