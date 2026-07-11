"""Brokerage Platform — stock/crypto/options/futures trading dashboard.

Temporal simulation with deterministic price walks, trading-hours awareness,
portfolio management, order placement, watchlists, and options chain.
Dynamic price simulation cycles through historical daily data based on
wall-clock time so prices appear to change throughout the day.
"""
import json
import pathlib
import random
from collections import Counter
from datetime import datetime, timedelta

from flask import (Blueprint, Response, abort, jsonify, redirect, render_template,
                   request, session, url_for)
from app import db
from app.events import emit

SITE = "brokerage"
SITE_DIR = pathlib.Path(__file__).resolve().parent
CONFIG_FILE = SITE_DIR / "config" / "config.json"

blueprint = Blueprint(
    "brokerage",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)

# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def _load_tickers():
    return db.query(SITE, "tickers")

def _load_price_history():
    """Load price history as a dict keyed by uppercase symbol.

    The DB stores this as a single row with one column per symbol,
    each containing JSON-encoded price data.
    """
    rows = db.query(SITE, "price_history")
    if not rows:
        return {}
    row = rows[0]
    result = {}
    for col, val in row.items():
        if col == "row_id" or col == "id":
            continue
        if val is not None:
            try:
                result[col.upper()] = json.loads(val) if isinstance(val, str) else val
            except (json.JSONDecodeError, TypeError):
                pass
    return result

def _load_options():
    return db.query(SITE, "options")

def _load_users():
    return db.query(SITE, "users")

def _save_users(users):
    db.save_collection(SITE, "users", users)

def _load_portfolios(user_id=None):
    where = {"user_id": user_id} if user_id is not None else None
    return db.query(SITE, "portfolios", where=where)

def _save_portfolios(portfolios):
    db.save_collection(SITE, "portfolios", portfolios)

def _load_orders(user_id=None):
    where = {"user_id": user_id} if user_id is not None else None
    return db.query(SITE, "orders", where=where, sort="-created_at")

def _save_orders(orders):
    db.save_collection(SITE, "orders", orders)

def _load_watchlists(user_id=None):
    where = {"user_id": user_id} if user_id is not None else None
    return db.query(SITE, "watchlists", where=where)

def _save_watchlists(watchlists):
    db.save_collection(SITE, "watchlists", watchlists)

# ---------------------------------------------------------------------------
# Temporal simulation
# ---------------------------------------------------------------------------

def _get_sim_clock():
    """Return the simulated current time.

    Maps real wall-clock time into a simulated trading day so prices change
    on every page load. The last trading day's intraday data (9:30-16:00,
    13 half-hour intervals) is mapped to the current real time:
    - Real minutes within the hour map to a position in the trading day
    - This means each page load shows a different simulated time/price

    Override with ?sim_tick=N to jump to a specific 30-min interval.
    """
    # Find the last trading day (stocks) with intraday data
    ph = _load_price_history()
    stock_dates = set()
    for sym, sym_data in ph.items():
        intraday = sym_data.get("intraday", [])
        if not intraday:
            continue
        # Only consider stock-like symbols (skip crypto which trades weekends)
        for pt in intraday:
            if datetime.strptime(pt["date"], "%Y-%m-%d").weekday() < 5:
                stock_dates.add(pt["date"])
    if stock_dates:
        sim_date = datetime.strptime(max(stock_dates), "%Y-%m-%d")
    else:
        config = _load_config()
        sim_date = datetime.strptime(config.get("sim_start_date", "2026-06-16"), "%Y-%m-%d")

    # Check for explicit tick override
    try:
        tick = int(request.args.get("sim_tick", -1))
    except (ValueError, RuntimeError):
        tick = -1

    if tick >= 0:
        # Each tick = 30 min from 9:30 AM
        hour = 9 + (tick * 30 + 30) // 60
        minute = (tick * 30 + 30) % 60
        if hour > 16:
            hour, minute = 16, 0
        return sim_date.replace(hour=hour, minute=minute, second=0)

    # Default: map real wall-clock time into trading day
    # Trading day = 9:30 to 16:00 = 390 minutes = 13 intervals of 30 min
    now = datetime.now()
    # Use real minutes + seconds to get a position in 0..389
    real_minutes = now.hour * 60 + now.minute
    # Map 0-1439 (full day) into 0-389 (trading day)
    trading_minute = int((real_minutes / 1440) * 390)
    sim_hour = 9 + (trading_minute + 30) // 60
    sim_minute = (trading_minute + 30) % 60
    if sim_hour > 16 or (sim_hour == 16 and sim_minute > 0):
        sim_hour, sim_minute = 16, 0
    if sim_hour < 9 or (sim_hour == 9 and sim_minute < 30):
        sim_hour, sim_minute = 9, 30

    return sim_date.replace(hour=sim_hour, minute=sim_minute, second=0)

def _is_market_open(ticker_type):
    """Check if market is open for this ticker type at sim time."""
    sim_time = _get_sim_clock()
    if ticker_type == "crypto":
        return True  # 24/7
    weekday = sim_time.weekday()
    if weekday >= 5:  # Sat/Sun
        return False
    hour, minute = sim_time.hour, sim_time.minute
    time_val = hour * 60 + minute
    return 9 * 60 + 30 <= time_val <= 16 * 60

def _get_current_price(symbol):
    """Get the current price for a symbol.

    Prefers the dynamic simulated price (which cycles through daily data
    based on wall-clock time). Falls back to intraday sim-clock lookup,
    then daily close.
    """
    # Prefer the dynamic simulated price
    sim = _get_simulated_price(symbol)
    if sim:
        return sim["price"]

    ph = _load_price_history()
    if symbol not in ph:
        return None
    sim_time = _get_sim_clock()
    sim_time_str = sim_time.strftime("%H:%M")

    intraday = ph[symbol].get("intraday", [])

    # Find the latest date that has intraday data for THIS symbol
    sym_dates = sorted(set(pt["date"] for pt in intraday))
    if not sym_dates:
        # No intraday data at all — use daily close
        daily = ph[symbol].get("daily", [])
        return daily[-1]["close"] if daily else None

    # Use the last available date for this symbol
    target_date = sym_dates[-1]

    # Find the closest price point at or before sim time on target date
    best_price = None
    best_time = ""
    for point in intraday:
        if point["date"] == target_date and point.get("time", "") <= sim_time_str:
            if point["time"] > best_time:
                best_time = point["time"]
                best_price = point.get("price", point.get("close"))

    if best_price is not None:
        return best_price

    # If sim_time is before market open, use first point of the day
    day_points = [p for p in intraday if p["date"] == target_date]
    if day_points:
        return day_points[0].get("price", day_points[0].get("close"))

    # Final fallback to daily close
    daily = ph[symbol].get("daily", [])
    if not daily:
        return None
    for d in reversed(daily):
            return d["close"]
    return daily[-1]["close"]

def _get_price_change(symbol):
    """Get price change and percentage change: current price vs previous close."""
    ph = _load_price_history()
    if symbol not in ph:
        return 0, 0
    current = _get_current_price(symbol)
    if current is None:
        return 0, 0
    daily = ph[symbol].get("daily", [])
    if len(daily) < 2:
        return 0, 0
    # Compare current intraday price vs previous day's close
    sim_time = _get_sim_clock()
    sim_date_str = sim_time.strftime("%Y-%m-%d")
    prev_close = None
    for d in daily:
        if d["date"] < sim_date_str:
            prev_close = d["close"]
    if prev_close is None:
        prev_close = daily[0]["open"]
    change = round(current - prev_close, 2)
    pct = round((change / prev_close) * 100, 2) if prev_close else 0
    return change, pct

# ---------------------------------------------------------------------------
# Dynamic price simulation
# ---------------------------------------------------------------------------

def _get_simulated_price(symbol):
    """Get a simulated current price by cycling through daily price history.

    Uses wall-clock time (hour * 60 + minute) modulo len(daily_data) to pick
    a data point from the historical daily array.  This makes the displayed
    price change every minute as the index advances through the history,
    giving the appearance of a live market even though the underlying data
    is static.

    Returns a dict with keys: price, prev_close, change, change_pct,
    direction ('up' or 'down'), day_high, day_low, day_open, volume,
    and sparkline_prices (list of recent close prices for mini-chart).
    Returns None if no daily data exists for the symbol.
    """
    ph = _load_price_history()
    if symbol not in ph:
        return None
    daily = ph[symbol].get("daily", [])
    if not daily:
        return None

    now = datetime.now()
    minute_of_day = now.hour * 60 + now.minute  # 0-1439
    idx = minute_of_day % len(daily)
    prev_idx = (idx - 1) % len(daily)

    current_day = daily[idx]
    prev_day = daily[prev_idx]

    # Use the close price as the "current" price; also incorporate a
    # sub-minute interpolation between open and close based on seconds
    # so that even reloads within the same minute show slight movement.
    t_frac = now.second / 60.0
    price = round(current_day["open"] + (current_day["close"] - current_day["open"]) * t_frac, 4)

    prev_close = prev_day["close"]
    change = round(price - prev_close, 4)
    change_pct = round((change / prev_close) * 100, 2) if prev_close else 0.0

    # Build sparkline data: take all daily close prices, rotated so the
    # current index is the last element, giving a "trailing" view.
    sparkline = []
    n = len(daily)
    for i in range(n):
        sparkline.append(daily[(idx - n + 1 + i) % n]["close"])

    return {
        "price": price,
        "prev_close": prev_close,
        "change": change,
        "change_pct": change_pct,
        "direction": "up" if change >= 0 else "down",
        "day_high": current_day["high"],
        "day_low": current_day["low"],
        "day_open": current_day["open"],
        "volume": current_day["volume"],
        "sparkline_prices": sparkline,
        "data_date": current_day["date"],
    }

# ---------------------------------------------------------------------------
# Enrichment helpers
# ---------------------------------------------------------------------------

def _enrich_ticker(t):
    """Add current_price, change, change_pct, market_open, and sim data to a ticker dict."""
    sym = t["symbol"]
    sim = _get_simulated_price(sym)
    if sim:
        price = sim["price"]
        change = sim["change"]
        pct = sim["change_pct"]
    else:
        price = _get_current_price(sym)
        change, pct = _get_price_change(sym)
    return {
        **t,
        "current_price": price or t["base_price"],
        "change": change,
        "change_pct": pct,
        "direction": sim["direction"] if sim else ("up" if change >= 0 else "down"),
        "day_high": sim["day_high"] if sim else None,
        "day_low": sim["day_low"] if sim else None,
        "day_open": sim["day_open"] if sim else None,
        "volume": sim["volume"] if sim else None,
        "sparkline_prices": sim["sparkline_prices"] if sim else [],
        "market_open": _is_market_open(t["type"]),
    }

def _enrich_holding(h, tickers_map):
    """Add current_price, market_value, gain/loss, and price change to a holding."""
    sym = h["symbol"]
    t = tickers_map.get(sym, {})
    sim = _get_simulated_price(sym)
    if sim:
        current_price = sim["price"]
        price_change = sim["change"]
        price_change_pct = sim["change_pct"]
        direction = sim["direction"]
    else:
        current_price = _get_current_price(sym) or t.get("base_price", 0)
        price_change, price_change_pct = _get_price_change(sym)
        direction = "up" if price_change >= 0 else "down"
    shares = h["shares"]
    avg_cost = h["avg_cost"]
    market_value = round(shares * current_price, 2)
    cost_basis = round(shares * avg_cost, 2)
    gain = round(market_value - cost_basis, 2)
    gain_pct = round((gain / cost_basis) * 100, 2) if cost_basis else 0
    return {
        **h,
        "name": t.get("name", sym),
        "type": t.get("type", "stock"),
        "current_price": current_price,
        "market_value": market_value,
        "cost_basis": cost_basis,
        "gain": gain,
        "gain_pct": gain_pct,
        "price_change": price_change,
        "price_change_pct": price_change_pct,
        "direction": direction,
    }

# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def _search_tickers(tickers, query):
    if not query:
        return tickers
    q = query.lower().strip()
    results = []
    for t in tickers:
        text = f"{t['symbol']} {t['name']} {t['sector']} {t['type']}".lower()
        if q in text:
            results.append(t)
    return results

def _semantic_search(tickers, query):
    """Keyword-weighted search across ticker fields."""
    if not query:
        return tickers
    terms = query.lower().split()
    scored = []
    for t in tickers:
        text = f"{t['symbol']} {t['name']} {t['sector']} {t['type']} {t.get('exchange','')}".lower()
        score = sum(1 for term in terms if term in text)
        if score > 0:
            scored.append((t, score))
    scored.sort(key=lambda x: -x[1])
    return [t for t, _ in scored]

# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    tickers = [_enrich_ticker(t) for t in _load_tickers()]
    # Sort by market cap descending by default
    tickers.sort(key=lambda t: -(t.get("market_cap_b") or 0))
    sectors = sorted(set(t["sector"] for t in tickers))
    types = sorted(set(t["type"] for t in tickers))

    # Query params
    q = request.args.get("q", "").strip()
    sec = request.args.get("sector", "").strip()
    typ = request.args.get("type", "").strip()
    sort = request.args.get("sort", "market_cap").strip()
    price_min = request.args.get("price_min", "").strip()
    price_max = request.args.get("price_max", "").strip()

    results = list(tickers)
    if q:
        results = _search_tickers(results, q)
    if sec:
        results = [t for t in results if t["sector"] == sec]
    if typ:
        results = [t for t in results if t["type"] == typ]
    if price_min:
        try:
            results = [t for t in results if t["current_price"] >= float(price_min)]
        except ValueError:
            pass
    if price_max:
        try:
            results = [t for t in results if t["current_price"] <= float(price_max)]
        except ValueError:
            pass

    if sort == "price_asc":
        results.sort(key=lambda t: t["current_price"])
    elif sort == "price_desc":
        results.sort(key=lambda t: -t["current_price"])
    elif sort == "change_desc":
        results.sort(key=lambda t: -t["change_pct"])
    elif sort == "change_asc":
        results.sort(key=lambda t: t["change_pct"])
    elif sort == "name":
        results.sort(key=lambda t: t["name"].lower())
    elif sort == "market_cap":
        results.sort(key=lambda t: -(t.get("market_cap_b") or 0))

    user = None
    portfolio_value = 0
    portfolio_change = 0
    portfolio_change_pct = 0
    watchlist_symbols = []
    watchlist_tickers = []

    if "user_id" in session:
        users = _load_users()
        user = next((u for u in users if u["id"] == session["user_id"]), None)

        if user:
            # Portfolio summary for hero display
            portfolios = _load_portfolios(user_id=user["id"])
            if portfolios:
                portfolio = portfolios[0]
                tickers_map = {t["symbol"]: t for t in tickers}
                enriched = [_enrich_holding(h, tickers_map) for h in portfolio["holdings"]]
                portfolio_value = round(sum(h["market_value"] for h in enriched), 2)
                total_cost = round(sum(h["cost_basis"] for h in enriched), 2)
                portfolio_change = round(portfolio_value - total_cost, 2)
                portfolio_change_pct = round((portfolio_change / total_cost) * 100, 2) if total_cost else 0

            # Watchlist for sidebar
            watchlists = _load_watchlists(user_id=user["id"])
            if watchlists:
                wl = watchlists[0]
                watchlist_symbols = wl.get("symbols", [])
                tickers_map_full = {t["symbol"]: t for t in tickers}
                watchlist_tickers = [tickers_map_full[s] for s in watchlist_symbols if s in tickers_map_full]

    sim_time = _get_sim_clock()

    return render_template("brokerage/index.html",
                           tickers=results, sectors=sectors, types=types,
                           q=q, sec=sec, typ=typ, sort=sort,
                           price_min=price_min, price_max=price_max,
                           user=user, sim_time=sim_time,
                           portfolio_value=portfolio_value,
                           portfolio_change=portfolio_change,
                           portfolio_change_pct=portfolio_change_pct,
                           watchlist_symbols=watchlist_symbols,
                           watchlist_tickers=watchlist_tickers)


@blueprint.route("/ticker/<symbol>")
def ticker_detail(symbol):
    tickers = _load_tickers()
    ticker = next((t for t in tickers if t["symbol"] == symbol.upper()), None)
    if ticker is None:
        abort(404)
    ticker = _enrich_ticker(ticker)
    ph = _load_price_history()
    history = ph.get(symbol.upper(), {"daily": [], "intraday": []})

    # Options for this ticker
    options = [o for o in _load_options() if o["underlying"] == symbol.upper()]

    # Related tickers (same sector, excluding current)
    related_tickers = [
        _enrich_ticker(t) for t in tickers
        if t["sector"] == ticker["sector"] and t["symbol"] != ticker["symbol"]
    ][:5]

    user = None
    watchlist_symbols = []
    if "user_id" in session:
        users = _load_users()
        user = next((u for u in users if u["id"] == session["user_id"]), None)
        if user:
            watchlists = _load_watchlists(user_id=user["id"])
            if watchlists:
                watchlist_symbols = watchlists[0].get("symbols", [])

    return render_template("brokerage/ticker.html",
                           ticker=ticker, history=history, options=options,
                           related_tickers=related_tickers,
                           user=user, sim_time=_get_sim_clock(),
                           watchlist_symbols=watchlist_symbols)


@blueprint.route("/portfolio")
def portfolio_page():
    if "user_id" not in session:
        return render_template("brokerage/login.html", error=None, user=None, sim_time=_get_sim_clock())
    user_id = session["user_id"]
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        return render_template("brokerage/login.html", error=None, user=None, sim_time=_get_sim_clock())

    portfolios = _load_portfolios(user_id=user_id)
    portfolio = portfolios[0] if portfolios else {"user_id": user_id, "holdings": []}
    tickers_map = {t["symbol"]: t for t in _load_tickers()}
    enriched = [_enrich_holding(h, tickers_map) for h in portfolio["holdings"]]
    total_value = round(sum(h["market_value"] for h in enriched), 2)
    total_gain = round(sum(h["gain"] for h in enriched), 2)
    total_cost = round(sum(h["cost_basis"] for h in enriched), 2)
    total_gain_pct = round((total_gain / total_cost) * 100, 2) if total_cost else 0

    # Daily P&L: sum of (shares * price_change) for each holding
    daily_pnl = round(sum(
        h["shares"] * h["price_change"] for h in enriched
    ), 2)

    return render_template("brokerage/portfolio.html",
                           user=user, holdings=enriched,
                           total_value=total_value, total_gain=total_gain,
                           total_gain_pct=total_gain_pct,
                           daily_pnl=daily_pnl,
                           sim_time=_get_sim_clock())


@blueprint.route("/orders")
def orders_page():
    if "user_id" not in session:
        return render_template("brokerage/login.html", error=None, user=None, sim_time=_get_sim_clock())
    user_id = session["user_id"]
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        return render_template("brokerage/login.html", error=None, user=None, sim_time=_get_sim_clock())

    user_orders = _load_orders(user_id=user_id)
    status_filter = request.args.get("status", "").strip()
    if status_filter:
        user_orders = [o for o in user_orders if o["status"] == status_filter]
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    if date_from:
        user_orders = [o for o in user_orders if o["created_at"] >= date_from]
    if date_to:
        user_orders = [o for o in user_orders if o["created_at"] <= date_to + "T23:59:59"]
    user_orders.sort(key=lambda o: o["created_at"], reverse=True)

    return render_template("brokerage/orders.html",
                           user=user, orders=user_orders,
                           status_filter=status_filter,
                           date_from=date_from, date_to=date_to,
                           sim_time=_get_sim_clock())


@blueprint.route("/watchlist")
def watchlist_page():
    if "user_id" not in session:
        return render_template("brokerage/login.html", error=None, user=None, sim_time=_get_sim_clock())
    user_id = session["user_id"]
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        return render_template("brokerage/login.html", error=None, user=None, sim_time=_get_sim_clock())

    watchlists = _load_watchlists(user_id=user_id)
    wl = watchlists[0] if watchlists else {"user_id": user_id, "symbols": [], "alerts": []}
    tickers_map = {t["symbol"]: _enrich_ticker(t) for t in _load_tickers()}
    watched = [tickers_map[s] for s in wl["symbols"] if s in tickers_map]

    return render_template("brokerage/watchlist.html",
                           user=user, watched=watched, alerts=wl["alerts"],
                           sim_time=_get_sim_clock())


@blueprint.route("/options")
def options_page():
    options = _load_options()
    underlying = request.args.get("underlying", "").strip().upper()
    opt_type = request.args.get("type", "").strip()

    if underlying:
        options = [o for o in options if o["underlying"] == underlying]
    if opt_type:
        options = [o for o in options if o["type"] == opt_type]

    underlyings = sorted(set(o["underlying"] for o in _load_options()))
    tickers_map = {t["symbol"]: _enrich_ticker(t) for t in _load_tickers()}

    user = None
    if "user_id" in session:
        users = _load_users()
        user = next((u for u in users if u["id"] == session["user_id"]), None)

    return render_template("brokerage/options.html",
                           options=options, underlyings=underlyings,
                           underlying=underlying, opt_type=opt_type,
                           tickers_map=tickers_map, user=user,
                           sim_time=_get_sim_clock())


@blueprint.route("/compare")
def compare_page():
    symbols_str = request.args.get("symbols", "")
    tickers = [_enrich_ticker(t) for t in _load_tickers()]
    selected = []
    if symbols_str:
        syms = [s.strip().upper() for s in symbols_str.split(",") if s.strip()]
        selected = [t for t in tickers if t["symbol"] in syms]
    ph = _load_price_history()

    user = None
    if "user_id" in session:
        users = _load_users()
        user = next((u for u in users if u["id"] == session["user_id"]), None)

    return render_template("brokerage/compare.html",
                           tickers=tickers, selected=selected,
                           price_history=ph, user=user,
                           sim_time=_get_sim_clock())


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("brokerage/login.html", error=None, user=None, sim_time=_get_sim_clock())


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return render_template("brokerage/login.html",
                               error="Invalid username or password", user=None, sim_time=_get_sim_clock())
    session["user_id"] = user["id"]
    emit("signup", user_id=user["id"], site_name="brokerage", username=request.form.get("username", ""), password=request.form.get("password", ""), email="")
    return redirect(url_for("brokerage.portfolio_page"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return render_template("brokerage/login.html", error=None, user=None, sim_time=_get_sim_clock())


@blueprint.route("/trade")
def trade_page():
    symbol = request.args.get("symbol", "").strip().upper()
    tickers = [_enrich_ticker(t) for t in _load_tickers()]
    ticker = next((t for t in tickers if t["symbol"] == symbol), None) if symbol else None

    user = None
    if "user_id" in session:
        users = _load_users()
        user = next((u for u in users if u["id"] == session["user_id"]), None)

    return render_template("brokerage/trade.html",
                           ticker=ticker, tickers=tickers, user=user,
                           sim_time=_get_sim_clock())


@blueprint.route("/trade", methods=["POST"])
def trade_submit():
    """Form-based order placement."""
    if "user_id" not in session:
        return redirect(url_for("brokerage.login_page"))
    user_id = session["user_id"]
    symbol = request.form.get("symbol", "").strip().upper()
    side = request.form.get("side", "buy").strip()
    order_type = request.form.get("order_type", "market").strip()
    quantity = request.form.get("quantity", "0")
    price = request.form.get("price", "")
    account_type = request.form.get("account_type", "checking")
    time_in_force = request.form.get("time_in_force", "day")
    if time_in_force not in ("day", "gtc"):
        time_in_force = "day"

    try:
        quantity = float(quantity)
    except (TypeError, ValueError):
        quantity = 0

    if not symbol or not quantity:
        return redirect(url_for("brokerage.trade_page", symbol=symbol))

    tickers = _load_tickers()
    ticker = next((t for t in tickers if t["symbol"] == symbol), None)
    if not ticker:
        return redirect(url_for("brokerage.trade_page"))

    if not _is_market_open(ticker["type"]):
        return redirect(url_for("brokerage.trade_page", symbol=symbol))

    orders = _load_orders()
    new_id = max((o["id"] for o in orders), default=0) + 1
    current_price = _get_current_price(symbol) or ticker["base_price"]

    limit_price = None
    if price:
        try:
            limit_price = float(price)
        except (TypeError, ValueError):
            limit_price = None

    sim_time = _get_sim_clock()
    new_order = {
        "id": new_id,
        "user_id": user_id,
        "symbol": symbol,
        "side": side,
        "order_type": order_type,
        "time_in_force": time_in_force,
        "quantity": quantity,
        "price": limit_price,
        "filled_price": current_price if order_type == "market" else None,
        "status": "filled" if order_type == "market" else "open",
        "created_at": sim_time.isoformat(),
        "filled_at": sim_time.isoformat() if order_type == "market" else None,
    }
    orders.append(new_order)
    _save_orders(orders)

    if order_type == "market":
        portfolios = _load_portfolios()
        portfolio = next((p for p in portfolios if p["user_id"] == user_id), None)
        if not portfolio:
            portfolio = {"user_id": user_id, "holdings": []}
            portfolios.append(portfolio)

        holding = next((h for h in portfolio["holdings"] if h["symbol"] == symbol), None)
        if side == "buy":
            if holding:
                total_cost = holding["shares"] * holding["avg_cost"] + quantity * current_price
                holding["shares"] += quantity
                holding["avg_cost"] = round(total_cost / holding["shares"], 2)
            else:
                portfolio["holdings"].append({
                    "symbol": symbol,
                    "shares": quantity,
                    "avg_cost": current_price,
                })
        elif side == "sell":
            if holding:
                holding["shares"] = round(holding["shares"] - quantity, 6)
                if holding["shares"] <= 0:
                    portfolio["holdings"].remove(holding)

        users = _load_users()
        user = next((u for u in users if u["id"] == user_id), None)
        if user:
            cost = quantity * current_price
            if side == "buy":
                user["buying_power"] = round(user["buying_power"] - cost, 2)
                user["cash_balance"] = round(user["cash_balance"] - cost, 2)
            else:
                user["buying_power"] = round(user["buying_power"] + cost, 2)
                user["cash_balance"] = round(user["cash_balance"] + cost, 2)
            _save_users(users)

        _save_portfolios(portfolios)

        emit("trade", user_id=user_id, symbol=symbol, side=side, quantity=quantity, price=current_price, account_type=account_type)
        emit("message", from_user_id=user_id, to_user_id=user_id, text=f"Trade executed: {side.upper()} {quantity} {symbol} @ ${current_price}", source_site="brokerage")

    return redirect(url_for("brokerage.orders_page"))


@blueprint.route("/watchlist/toggle", methods=["POST"])
def form_watchlist_toggle():
    """Form-based watchlist toggle."""
    if "user_id" not in session:
        return redirect(url_for("brokerage.login_page"))
    user_id = session["user_id"]
    symbol = request.form.get("symbol", "").strip().upper()
    if not symbol:
        return redirect(url_for("brokerage.watchlist_page"))

    watchlists = _load_watchlists()
    wl = next((w for w in watchlists if w["user_id"] == user_id), None)
    if not wl:
        wl = {"user_id": user_id, "symbols": [], "alerts": []}
        watchlists.append(wl)

    if symbol in wl["symbols"]:
        wl["symbols"].remove(symbol)
    else:
        wl["symbols"].append(symbol)
    _save_watchlists(watchlists)
    return redirect(url_for("brokerage.watchlist_page"))


@blueprint.route("/orders/<int:order_id>/cancel", methods=["POST"])
def form_cancel_order(order_id):
    """Form-based order cancellation."""
    orders = _load_orders()
    order = next((o for o in orders if o["id"] == order_id), None)
    if order and order["status"] == "open":
        order["status"] = "cancelled"
        _save_orders(orders)
    return redirect(url_for("brokerage.orders_page"))


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/tickers")
def api_tickers():
    tickers = [_enrich_ticker(t) for t in _load_tickers()]
    q = request.args.get("q", "").strip()
    sec = request.args.get("sector", "").strip()
    typ = request.args.get("type", "").strip()
    sort = request.args.get("sort", "market_cap").strip()
    price_min = request.args.get("price_min", type=float)
    price_max = request.args.get("price_max", type=float)

    if q:
        tickers = _search_tickers(tickers, q)
    if sec:
        tickers = [t for t in tickers if t["sector"] == sec]
    if typ:
        tickers = [t for t in tickers if t["type"] == typ]
    if price_min is not None:
        tickers = [t for t in tickers if t["current_price"] >= price_min]
    if price_max is not None:
        tickers = [t for t in tickers if t["current_price"] <= price_max]

    if sort == "price_asc":
        tickers.sort(key=lambda t: t["current_price"])
    elif sort == "price_desc":
        tickers.sort(key=lambda t: -t["current_price"])
    elif sort == "change_desc":
        tickers.sort(key=lambda t: -t["change_pct"])
    elif sort == "change_asc":
        tickers.sort(key=lambda t: t["change_pct"])
    elif sort == "name":
        tickers.sort(key=lambda t: t["name"].lower())
    elif sort == "market_cap":
        tickers.sort(key=lambda t: -(t.get("market_cap_b") or 0))

    return jsonify(tickers)


@blueprint.route("/api/tickers/<symbol>")
def api_ticker(symbol):
    tickers = _load_tickers()
    ticker = next((t for t in tickers if t["symbol"] == symbol.upper()), None)
    if ticker is None:
        abort(404)
    return jsonify(_enrich_ticker(ticker))


@blueprint.route("/api/tickers/search")
def api_search():
    q = request.args.get("q", "").strip()
    tickers = [_enrich_ticker(t) for t in _load_tickers()]
    return jsonify(_search_tickers(tickers, q))


@blueprint.route("/api/tickers/semantic")
def api_semantic_search():
    q = request.args.get("q", "").strip()
    tickers = [_enrich_ticker(t) for t in _load_tickers()]
    return jsonify(_semantic_search(tickers, q))


@blueprint.route("/api/price_history/<symbol>")
def api_price_history(symbol):
    ph = _load_price_history()
    if symbol.upper() not in ph:
        abort(404)
    date = request.args.get("date", "").strip()
    data = ph[symbol.upper()]
    if date:
        data = {
            "daily": [d for d in data["daily"] if d["date"] == date],
            "intraday": [d for d in data["intraday"] if d["date"] == date],
        }
    return jsonify(data)


@blueprint.route("/api/options")
def api_options():
    options = _load_options()
    underlying = request.args.get("underlying", "").strip().upper()
    opt_type = request.args.get("type", "").strip()
    min_strike = request.args.get("min_strike", type=float)
    max_strike = request.args.get("max_strike", type=float)
    sort = request.args.get("sort", "").strip()

    if underlying:
        options = [o for o in options if o["underlying"] == underlying]
    if opt_type:
        options = [o for o in options if o["type"] == opt_type]
    if min_strike is not None:
        options = [o for o in options if o["strike"] >= min_strike]
    if max_strike is not None:
        options = [o for o in options if o["strike"] <= max_strike]

    if sort == "strike_asc":
        options.sort(key=lambda o: o["strike"])
    elif sort == "strike_desc":
        options.sort(key=lambda o: -o["strike"])
    elif sort == "premium_desc":
        options.sort(key=lambda o: -o["premium"])
    elif sort == "volume_desc":
        options.sort(key=lambda o: -o["volume"])
    elif sort == "iv_desc":
        options.sort(key=lambda o: -o["iv"])

    return jsonify(options)


@blueprint.route("/api/sectors")
def api_sectors():
    tickers = [_enrich_ticker(t) for t in _load_tickers()]
    sectors = {}
    for t in tickers:
        sec = t["sector"]
        if sec not in sectors:
            sectors[sec] = {"name": sec, "count": 0, "avg_change_pct": 0, "total_change": 0}
        sectors[sec]["count"] += 1
        sectors[sec]["total_change"] += t["change_pct"]
    for s in sectors.values():
        s["avg_change_pct"] = round(s["total_change"] / s["count"], 2) if s["count"] else 0
        del s["total_change"]
    return jsonify(sorted(sectors.values(), key=lambda s: s["name"]))


@blueprint.route("/api/market_status")
def api_market_status():
    sim_time = _get_sim_clock()
    return jsonify({
        "sim_time": sim_time.isoformat(),
        "stock_market_open": _is_market_open("stock"),
        "crypto_market_open": _is_market_open("crypto"),
        "futures_market_open": _is_market_open("futures"),
    })


@blueprint.route("/api/stats")
def api_stats():
    tickers = [_enrich_ticker(t) for t in _load_tickers()]
    sec = request.args.get("sector", "").strip()
    typ = request.args.get("type", "").strip()
    if sec:
        tickers = [t for t in tickers if t["sector"] == sec]
    if typ:
        tickers = [t for t in tickers if t["type"] == typ]
    if not tickers:
        return jsonify({"count": 0})
    prices = [t["current_price"] for t in tickers]
    changes = [t["change_pct"] for t in tickers]
    return jsonify({
        "count": len(tickers),
        "avg_price": round(sum(prices) / len(prices), 2),
        "max_price": max(prices),
        "min_price": min(prices),
        "avg_change_pct": round(sum(changes) / len(changes), 2),
        "best_performer": max(tickers, key=lambda t: t["change_pct"])["symbol"],
        "worst_performer": min(tickers, key=lambda t: t["change_pct"])["symbol"],
        "sectors": dict(Counter(t["sector"] for t in tickers)),
        "types": dict(Counter(t["type"] for t in tickers)),
    })


@blueprint.route("/api/compare")
def api_compare():
    symbols_str = request.args.get("symbols", "")
    syms = [s.strip().upper() for s in symbols_str.split(",") if s.strip()]
    tickers = [_enrich_ticker(t) for t in _load_tickers()]
    selected = [t for t in tickers if t["symbol"] in syms]
    return jsonify(selected)


@blueprint.route("/api/export")
def api_export():
    fmt = request.args.get("format", "json").lower()
    typ = request.args.get("type", "").strip()
    sec = request.args.get("sector", "").strip()
    tickers = [_enrich_ticker(t) for t in _load_tickers()]
    if typ:
        tickers = [t for t in tickers if t["type"] == typ]
    if sec:
        tickers = [t for t in tickers if t["sector"] == sec]

    if fmt == "csv":
        lines = ["symbol,name,type,sector,current_price,change,change_pct"]
        for t in tickers:
            name = t["name"].replace('"', '""')
            lines.append(f'{t["symbol"]},"{name}",{t["type"]},{t["sector"]},{t["current_price"]},{t["change"]},{t["change_pct"]}')
        return Response("\n".join(lines), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=tickers.csv"})
    return jsonify(tickers)


# ---------------------------------------------------------------------------
# User / Auth API
# ---------------------------------------------------------------------------

@blueprint.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return jsonify({"error": "Invalid credentials"}), 401
    session["user_id"] = user["id"]
    # Honor the annotation-mode Skip-2FA toggle (session["_disable_2fa"]):
    # tells the login page whether to show the verify-identity step.
    return jsonify({"user_id": user["id"], "username": user["username"],
                    "two_factor_required": not session.get("_disable_2fa")})


@blueprint.route("/api/verify_identity", methods=["POST"])
def api_verify_identity():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    code = data.get("code", "").strip()
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        return jsonify({"error": "User not found"}), 404
    if user.get("two_factor_code") != code:
        return jsonify({"error": "Invalid verification code", "verified": False}), 400
    # Mark as verified
    user["verified"] = True
    _save_users(users)
    return jsonify({"verified": True, "user_id": user_id})


@blueprint.route("/api/users/<int:user_id>")
def api_user(user_id):
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    return jsonify({k: v for k, v in user.items() if k not in ("password", "two_factor_code")})


# ---------------------------------------------------------------------------
# Portfolio API
# ---------------------------------------------------------------------------

@blueprint.route("/api/portfolio/<int:user_id>")
def api_portfolio(user_id):
    portfolios = _load_portfolios(user_id=user_id)
    portfolio = portfolios[0] if portfolios else {"user_id": user_id, "holdings": []}
    tickers_map = {t["symbol"]: t for t in _load_tickers()}
    enriched = [_enrich_holding(h, tickers_map) for h in portfolio["holdings"]]
    total_value = round(sum(h["market_value"] for h in enriched), 2)
    total_cost = round(sum(h["cost_basis"] for h in enriched), 2)
    total_gain = round(total_value - total_cost, 2)
    total_gain_pct = round((total_gain / total_cost) * 100, 2) if total_cost else 0
    return jsonify({
        "user_id": user_id,
        "holdings": enriched,
        "total_value": total_value,
        "total_cost": total_cost,
        "total_gain": total_gain,
        "total_gain_pct": total_gain_pct,
    })


# ---------------------------------------------------------------------------
# Orders API
# ---------------------------------------------------------------------------

@blueprint.route("/api/orders/<int:user_id>")
def api_user_orders(user_id):
    user_orders = _load_orders(user_id=user_id)
    status = request.args.get("status", "").strip()
    if status:
        user_orders = [o for o in user_orders if o["status"] == status]
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    if date_from:
        user_orders = [o for o in user_orders if o["created_at"] >= date_from]
    if date_to:
        user_orders = [o for o in user_orders if o["created_at"] <= date_to + "T23:59:59"]
    user_orders.sort(key=lambda o: o["created_at"], reverse=True)
    return jsonify(user_orders)


@blueprint.route("/api/orders", methods=["POST"])
def api_place_order():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    symbol = data.get("symbol", "").strip().upper()
    side = data.get("side", "").strip()
    order_type = data.get("order_type", "market").strip()
    quantity = data.get("quantity", 0)
    price = data.get("price")
    account_type = data.get("account_type", "checking")

    if not user_id or not symbol or not side or not quantity:
        return jsonify({"error": "Missing required fields"}), 400

    # Validate ticker exists
    tickers = _load_tickers()
    ticker = next((t for t in tickers if t["symbol"] == symbol), None)
    if not ticker:
        return jsonify({"error": f"Unknown symbol: {symbol}"}), 400

    # Check market hours
    if not _is_market_open(ticker["type"]):
        return jsonify({"error": f"Market closed for {symbol}"}), 400

    orders = _load_orders()
    new_id = max((o["id"] for o in orders), default=0) + 1
    current_price = _get_current_price(symbol) or ticker["base_price"]

    sim_time = _get_sim_clock()
    new_order = {
        "id": new_id,
        "user_id": user_id,
        "symbol": symbol,
        "side": side,
        "order_type": order_type,
        "quantity": quantity,
        "price": price,
        "filled_price": current_price if order_type == "market" else None,
        "status": "filled" if order_type == "market" else "open",
        "created_at": sim_time.isoformat(),
        "filled_at": sim_time.isoformat() if order_type == "market" else None,
    }
    orders.append(new_order)
    _save_orders(orders)

    # If market order filled, update portfolio
    if order_type == "market":
        portfolios = _load_portfolios()
        portfolio = next((p for p in portfolios if p["user_id"] == user_id), None)
        if not portfolio:
            portfolio = {"user_id": user_id, "holdings": []}
            portfolios.append(portfolio)

        holding = next((h for h in portfolio["holdings"] if h["symbol"] == symbol), None)
        if side == "buy":
            if holding:
                total_cost = holding["shares"] * holding["avg_cost"] + quantity * current_price
                holding["shares"] += quantity
                holding["avg_cost"] = round(total_cost / holding["shares"], 2)
            else:
                portfolio["holdings"].append({
                    "symbol": symbol,
                    "shares": quantity,
                    "avg_cost": current_price,
                })
        elif side == "sell":
            if holding:
                holding["shares"] = round(holding["shares"] - quantity, 6)
                if holding["shares"] <= 0:
                    portfolio["holdings"].remove(holding)

        # Update buying power
        users = _load_users()
        user = next((u for u in users if u["id"] == user_id), None)
        if user:
            cost = quantity * current_price
            if side == "buy":
                user["buying_power"] = round(user["buying_power"] - cost, 2)
                user["cash_balance"] = round(user["cash_balance"] - cost, 2)
            else:
                user["buying_power"] = round(user["buying_power"] + cost, 2)
                user["cash_balance"] = round(user["cash_balance"] + cost, 2)
            _save_users(users)

        _save_portfolios(portfolios)

        emit("trade", user_id=user_id, symbol=symbol, side=side, quantity=quantity, price=current_price, account_type=account_type)

    return jsonify(new_order)


@blueprint.route("/api/orders/<int:order_id>/cancel", methods=["POST"])
def api_cancel_order(order_id):
    orders = _load_orders()
    order = next((o for o in orders if o["id"] == order_id), None)
    if not order:
        return jsonify({"error": "Order not found"}), 404
    if order["status"] != "open":
        return jsonify({"error": "Can only cancel open orders"}), 400
    order["status"] = "cancelled"
    _save_orders(orders)
    return jsonify(order)


# ---------------------------------------------------------------------------
# Watchlist API
# ---------------------------------------------------------------------------

@blueprint.route("/api/watchlist/<int:user_id>")
def api_watchlist(user_id):
    watchlists = _load_watchlists(user_id=user_id)
    wl = watchlists[0] if watchlists else {"user_id": user_id, "symbols": [], "alerts": []}
    tickers_map = {t["symbol"]: _enrich_ticker(t) for t in _load_tickers()}
    watched = [tickers_map[s] for s in wl["symbols"] if s in tickers_map]
    return jsonify({"symbols": wl["symbols"], "tickers": watched, "alerts": wl["alerts"]})


@blueprint.route("/api/watchlist/<int:user_id>/toggle", methods=["POST"])
def api_watchlist_toggle(user_id):
    data = request.get_json(silent=True) or {}
    symbol = data.get("symbol", "").strip().upper()
    if not symbol:
        return jsonify({"error": "symbol required"}), 400

    watchlists = _load_watchlists()
    wl = next((w for w in watchlists if w["user_id"] == user_id), None)
    if not wl:
        wl = {"user_id": user_id, "symbols": [], "alerts": []}
        watchlists.append(wl)

    if symbol in wl["symbols"]:
        wl["symbols"].remove(symbol)
        action = "removed"
    else:
        wl["symbols"].append(symbol)
        action = "added"
    _save_watchlists(watchlists)
    return jsonify({"action": action, "symbol": symbol, "total": len(wl["symbols"])})


@blueprint.route("/api/watchlist/<int:user_id>/alert", methods=["POST"])
def api_set_alert(user_id):
    data = request.get_json(silent=True) or {}
    symbol = data.get("symbol", "").strip().upper()
    condition = data.get("condition", "").strip()  # "above" or "below"
    price = data.get("price")

    if not symbol or not condition or price is None:
        return jsonify({"error": "symbol, condition, price required"}), 400

    watchlists = _load_watchlists()
    wl = next((w for w in watchlists if w["user_id"] == user_id), None)
    if not wl:
        wl = {"user_id": user_id, "symbols": [], "alerts": []}
        watchlists.append(wl)

    wl["alerts"].append({"symbol": symbol, "condition": condition, "price": price})
    _save_watchlists(watchlists)
    return jsonify({"action": "alert_set", "symbol": symbol, "condition": condition, "price": price})


@blueprint.route("/api/prices/live")
def api_prices_live():
    """Return current prices with small random fluctuations applied.

    Each call applies a tiny random walk (+/- $0.01 to $0.50) to the base
    simulated price, giving the illusion of a live-ticking market feed.
    Returns a dict keyed by symbol with price, change, change_pct, direction.
    """
    symbols = request.args.get("symbols", "").strip()
    tickers = _load_tickers()
    if symbols:
        sym_set = {s.strip().upper() for s in symbols.split(",") if s.strip()}
        tickers = [t for t in tickers if t["symbol"] in sym_set]

    result = {}
    for t in tickers:
        sym = t["symbol"]
        sim = _get_simulated_price(sym)
        if sim:
            base_price = sim["price"]
            prev_close = sim["prev_close"]
        else:
            base_price = _get_current_price(sym) or t["base_price"]
            ph = _load_price_history()
            daily = ph.get(sym, {}).get("daily", [])
            prev_close = daily[-2]["close"] if len(daily) >= 2 else base_price

        # Apply a small random fluctuation scaled to the price magnitude
        # For a $200 stock: tick in range ~$0.01 to $0.50
        # For a $0.50 crypto: tick in range ~$0.0001 to $0.005
        magnitude = max(base_price * 0.002, 0.01)  # 0.2% of price or $0.01 min
        tick = random.uniform(-magnitude, magnitude)
        live_price = round(base_price + tick, 4)
        if live_price <= 0:
            live_price = round(base_price, 4)

        change = round(live_price - prev_close, 4)
        change_pct = round((change / prev_close) * 100, 2) if prev_close else 0.0

        result[sym] = {
            "price": live_price,
            "change": change,
            "change_pct": change_pct,
            "direction": "up" if change >= 0 else "down",
        }

    return jsonify(result)


@blueprint.route("/api/rankings")
def api_rankings():
    """Return tickers ranked by a given metric."""
    metric = request.args.get("metric", "change_pct").strip()
    direction = request.args.get("direction", "desc").strip()
    limit = request.args.get("limit", type=int, default=10)
    tickers = [_enrich_ticker(t) for t in _load_tickers()]

    key_map = {
        "change_pct": lambda t: t["change_pct"],
        "price": lambda t: t["current_price"],
        "market_cap": lambda t: t.get("market_cap_b") or 0,
    }
    key_fn = key_map.get(metric, key_map["change_pct"])
    reverse = direction == "desc"
    tickers.sort(key=key_fn, reverse=reverse)
    return jsonify(tickers[:limit])
