# TradeVista (`brokerage`)

A Robinhood-style trading app (listed as "Brokerage Platform" in `site.json`) for stocks,
index funds, crypto, options and futures. Users browse securities, view ticker
charts, place and cancel orders, manage a watchlist and move cash in and out.

- URL: `/sites/brokerage/` (simulated domain `tradepulse.com`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Markets home: search, "All Securities" table with sector/type filters, sort and max-price slider |
| `/ticker/<symbol>` | Ticker detail: price chart with period buttons, fundamentals, watchlist button |
| `/trade` | Order form: symbol, side, shares, order type, "Pay With" account |
| `/portfolio` | Holdings with P&L, cash deposit and withdraw (login required) |
| `/orders` | Order history with status and From/To date filters, cancel for open orders (login required) |
| `/watchlist` | Watchlist table (login required) |
| `/options` | Options chain with underlying and type filters |
| `/compare` | Side-by-side ticker comparison |
| `/login` | Sign-in form |

JSON endpoints under `/api/` cover tickers, price history, options, orders,
watchlist, funds, rankings and export.

## Interactions and macros

- Search tickers from the top bar: `search`
- Filter securities by sector, type or order status: `filter_by_dropdown`
- Limit securities by price: `filter_by_slider`
- Sort securities (market cap, price, gainers, name): `sort_by_form`
- Filter order history by date: `filter_by_date_range`
- Place an order: `create_by_form`; choose the paying account: `pay_by_form`
- Cancel an open order: `cancel_by_form`
- Add or remove a ticker from the watchlist: `toggle_relationship`
- Read holdings, orders, options chains and comparisons: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `brokerage`.

## Data

- Tables: `brokerage_tickers`, `brokerage_price_history`, `brokerage_price_data`,
  `brokerage_options`, `brokerage_orders`, `brokerage_portfolios`,
  `brokerage_watchlists`, `brokerage_users`.
- Login uses `session["user_id"]`, so the global auto-login signs in user 1.
- Prices are simulated: the wall-clock time is mapped into the last trading day
  in the price history (9:30-16:00), so quotes change between page loads.
  `?sim_tick=N` pins a 30-minute interval. Stock orders are rejected outside
  simulated market hours; crypto trades at any time. Settings are in
  `sites/brokerage/config/config.json`.
- A filled order emits `trade` (a debit on the banking account for buys) and
  `message` (a trade notice in instant messaging). Deposits and withdrawals
  also send a `message`. Logging in emits `signup` (password-vault entry and
  welcome email).
