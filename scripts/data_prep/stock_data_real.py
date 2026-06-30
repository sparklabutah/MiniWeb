#!/usr/bin/env python3
"""
Replace synthesized stock/crypto prices with real historical data.

For 108 stocks: uses yfinance to fetch ~30 trading days of real OHLCV data.
For 50 crypto: uses CoinGecko free API for 30-day market_chart data.
Falls back to existing data if API calls fail.

Usage:
    python scripts/data_prep/stock_data_real.py
"""

import json
import os
import shutil
import time
import sys
from datetime import datetime, timedelta
from pathlib import Path

import yfinance as yf

# Force unbuffered stdout for progress visibility
sys.stdout.reconfigure(line_buffering=True)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DATA_DIR = Path("/scratch/general/vast/u1653932/data_sources/stock-crypto-prices")
PRISTINE_DIR = DATA_DIR / ".pristine"

ASSETS_FILE = DATA_DIR / "assets.json"
PRICE_HISTORY_FILE = DATA_DIR / "price_history.json"
SECTORS_FILE = DATA_DIR / "sectors.json"


# ---------------------------------------------------------------------------
# CoinGecko symbol -> id mapping for our 50 cryptos
# ---------------------------------------------------------------------------
CRYPTO_COINGECKO_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "USDT": "tether",
    "BNB": "binancecoin",
    "USDC": "usd-coin",
    "XRP": "ripple",
    "SOL": "solana",
    "TRX": "tron",
    "DOGE": "dogecoin",
    "ADA": "cardano",
    "LINK": "chainlink",
    "XLM": "stellar",
    "XMR": "monero",
    "BCH": "bitcoin-cash",
    "LTC": "litecoin",
    "HBAR": "hedera-hashgraph",
    "SUI": "sui",
    "SHIB": "shiba-inu",
    "NEAR": "near",
    "AVAX": "avalanche-2",
    "UNI": "uniswap",
    "TAO": "bittensor",
    "WLD": "worldcoin-wld",
    "MNT": "mantle",
    "ONDO": "ondo-finance",
    "CRO": "crypto-com-chain",
    "DAI": "dai",
    "LEO": "leo-token",
    "ZEC": "zcash",
    "PAXG": "pax-gold",
    "XAUT": "tether-gold",
    "HYPE": "hyperliquid",
    "USDE": "ethena-usde",
    "SPOT": None,  # conflicts with Spotify stock ticker -- skip
    "FIGR_HELOC": None,
    "USDS": None,
    "RAIN": None,
    "WBT": "whitebit",
    "CC": None,
    "USD1": None,
    "GRAM": "the-open-network",
    "LAB": None,
    "M": None,
    "USYC": None,
    "USDG": None,
    "PYUSD": "paypal-usd",
    "BUIDL": None,
    "USDY": None,
    "WLFI": None,
    "ASTER": None,
    "RLUSD": None,
}

# How many trading days of history to keep
TARGET_DAYS = 30


def load_json(path):
    with open(path) as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)
    print(f"  Saved {path.name} ({len(data)} records)")


# ---------------------------------------------------------------------------
# Stock processing via yfinance
# ---------------------------------------------------------------------------
def fetch_stock_data(symbol: str, retries: int = 2):
    """Fetch ~2 months of daily data for a stock, return last 30 trading days."""
    for attempt in range(retries):
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="2mo")
            if df.empty:
                print(f"    WARNING: No data for {symbol}")
                return None
            # Take last TARGET_DAYS rows
            df = df.tail(TARGET_DAYS).copy()
            df.index = df.index.tz_localize(None)  # remove timezone
            return df
        except Exception as e:
            print(f"    Attempt {attempt+1} failed for {symbol}: {e}")
            time.sleep(2)
    return None


def process_stocks(assets, old_price_history):
    """Update stock assets and price history with real yfinance data."""
    stocks = [a for a in assets if a["type"] == "stock"]
    stock_ids = {a["id"] for a in stocks}
    symbols = [a["symbol"] for a in stocks]

    print(f"\nProcessing {len(stocks)} stocks...")

    # Batch download: yfinance supports multi-ticker download
    # Process in batches of 20 to avoid rate limits
    BATCH_SIZE = 20
    all_data = {}  # symbol -> DataFrame

    for batch_start in range(0, len(symbols), BATCH_SIZE):
        batch_symbols = symbols[batch_start : batch_start + BATCH_SIZE]
        batch_str = " ".join(batch_symbols)
        print(f"  Batch {batch_start // BATCH_SIZE + 1}: {batch_str[:80]}...")

        try:
            df_all = yf.download(batch_str, period="2mo", group_by="ticker",
                                 progress=False, threads=True)
            if df_all.empty:
                print("    WARNING: Empty batch result, falling back to individual")
                for sym in batch_symbols:
                    result = fetch_stock_data(sym)
                    if result is not None:
                        all_data[sym] = result
                    time.sleep(0.5)
                continue

            for sym in batch_symbols:
                try:
                    if len(batch_symbols) == 1:
                        sym_df = df_all.copy()
                        # Flatten multi-level columns if present
                        if hasattr(sym_df.columns, 'nlevels') and sym_df.columns.nlevels > 1:
                            sym_df.columns = sym_df.columns.get_level_values(0)
                    else:
                        # Try ticker-level access (works for both old and new yfinance)
                        if hasattr(df_all.columns, 'nlevels') and df_all.columns.nlevels > 1:
                            sym_df = df_all.xs(sym, level='Ticker', axis=1).copy() if 'Ticker' in df_all.columns.names else df_all[sym].copy()
                        else:
                            sym_df = df_all[sym].copy()

                    sym_df = sym_df.dropna(subset=["Close"])
                    if sym_df.empty:
                        print(f"    WARNING: No data for {sym} in batch")
                        continue
                    sym_df = sym_df.tail(TARGET_DAYS)
                    sym_df.index = sym_df.index.tz_localize(None) if sym_df.index.tz else sym_df.index
                    all_data[sym] = sym_df
                except (KeyError, TypeError):
                    print(f"    WARNING: Could not extract {sym} from batch")
        except Exception as e:
            print(f"    Batch download failed: {e}")
            for sym in batch_symbols:
                result = fetch_stock_data(sym)
                if result is not None:
                    all_data[sym] = result
                time.sleep(0.5)

        time.sleep(1)  # pause between batches

    # Now update the assets and build price history
    new_price_history = []
    ph_id = 1
    updated_count = 0
    skipped_count = 0

    for asset in assets:
        if asset["type"] != "stock":
            continue

        sym = asset["symbol"]
        df = all_data.get(sym)

        if df is None or df.empty:
            print(f"  SKIP {sym}: keeping existing data")
            skipped_count += 1
            # Keep existing price history for this asset
            existing = [p for p in old_price_history if p["asset_id"] == asset["id"]]
            for p in existing:
                p_copy = dict(p)
                p_copy["id"] = ph_id
                new_price_history.append(p_copy)
                ph_id += 1
            continue

        updated_count += 1

        # Build price history entries from the dataframe
        rows = []
        for date_idx, row in df.iterrows():
            entry = {
                "id": ph_id,
                "asset_id": asset["id"],
                "date": date_idx.strftime("%Y-%m-%d"),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            }
            rows.append(entry)
            ph_id += 1
        new_price_history.extend(rows)

        # Update asset summary fields from the most recent data
        last_row = df.iloc[-1]
        prev_row = df.iloc[-2] if len(df) >= 2 else df.iloc[-1]

        current_price = round(float(last_row["Close"]), 2)
        open_price = round(float(last_row["Open"]), 2)
        high_24h = round(float(last_row["High"]), 2)
        low_24h = round(float(last_row["Low"]), 2)
        volume_24h = int(last_row["Volume"])

        prev_close = float(prev_row["Close"])
        change_24h = round(((current_price - prev_close) / prev_close) * 100, 2) if prev_close else 0.0

        # 7-day change: use close from ~7 trading days ago
        if len(df) >= 6:
            close_7d_ago = float(df.iloc[-6]["Close"])
            change_7d = round(((current_price - close_7d_ago) / close_7d_ago) * 100, 2)
        else:
            change_7d = 0.0

        # 30-day change: first vs last
        close_30d_ago = float(df.iloc[0]["Close"])
        change_30d = round(((current_price - close_30d_ago) / close_30d_ago) * 100, 2) if close_30d_ago else 0.0

        # All-time high/low from the window (keep existing ATH/ATL if they're more extreme)
        window_high = round(float(df["High"].max()), 2)
        window_low = round(float(df["Low"].min()), 2)

        asset["current_price"] = current_price
        asset["open_price"] = open_price
        asset["high_24h"] = high_24h
        asset["low_24h"] = low_24h
        asset["volume_24h"] = volume_24h
        asset["change_pct_24h"] = change_24h
        asset["change_pct_7d"] = change_7d
        asset["change_pct_30d"] = change_30d
        # Keep existing ATH/ATL but update if our window has more extreme values
        if window_high > asset.get("all_time_high", 0):
            asset["all_time_high"] = window_high
        if window_low < asset.get("all_time_low", float("inf")):
            asset["all_time_low"] = window_low

        # Keep existing market_cap (individual fast_info lookups are too slow)

    print(f"  Updated {updated_count} stocks, skipped {skipped_count}")
    return new_price_history, ph_id


# ---------------------------------------------------------------------------
# Crypto processing via CoinGecko
# ---------------------------------------------------------------------------
def fetch_crypto_coingecko(coin_id: str):
    """Fetch 30-day OHLC from CoinGecko free API."""
    import urllib.request
    import urllib.error

    # Use market_chart for daily prices
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days=30&interval=daily"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        return data
    except urllib.error.HTTPError as e:
        if e.code == 429:
            print(f"    Rate limited on {coin_id}, waiting 60s...")
            time.sleep(60)
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode())
                return data
            except Exception:
                return None
        print(f"    HTTP error {e.code} for {coin_id}")
        return None
    except Exception as e:
        print(f"    Error fetching {coin_id}: {e}")
        return None


def fetch_crypto_ohlc(coin_id: str):
    """Fetch 30-day OHLC candles from CoinGecko."""
    import urllib.request
    import urllib.error

    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc?vs_currency=usd&days=30"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        return data  # list of [timestamp, open, high, low, close]
    except Exception as e:
        print(f"    OHLC error for {coin_id}: {e}")
        return None


def process_cryptos(assets, old_price_history, ph_id_start):
    """Update crypto assets with CoinGecko data where possible."""
    cryptos = [a for a in assets if a["type"] == "crypto"]
    print(f"\nProcessing {len(cryptos)} crypto assets via CoinGecko...")

    new_price_history = []
    ph_id = ph_id_start
    updated_count = 0
    skipped_count = 0
    rate_limited = False

    for asset in cryptos:
        sym = asset["symbol"]
        coin_id = CRYPTO_COINGECKO_IDS.get(sym)

        if coin_id is None or rate_limited:
            # No mapping or rate limited -- keep existing data
            skipped_count += 1
            existing = [p for p in old_price_history if p["asset_id"] == asset["id"]]
            for p in existing:
                p_copy = dict(p)
                p_copy["id"] = ph_id
                new_price_history.append(p_copy)
                ph_id += 1
            continue

        print(f"  Fetching {sym} ({coin_id})...")

        # Try OHLC endpoint first (gives us proper candles)
        ohlc_data = fetch_crypto_ohlc(coin_id)
        market_data = fetch_crypto_coingecko(coin_id)

        if ohlc_data is None and market_data is None:
            print(f"    SKIP {sym}: no data available (possibly rate limited)")
            rate_limited = True
            skipped_count += 1
            existing = [p for p in old_price_history if p["asset_id"] == asset["id"]]
            for p in existing:
                p_copy = dict(p)
                p_copy["id"] = ph_id
                new_price_history.append(p_copy)
                ph_id += 1
            continue

        # Build daily candles from OHLC data
        if ohlc_data and len(ohlc_data) > 0:
            # OHLC data: group by date, take daily candle
            daily_candles = {}
            for candle in ohlc_data:
                ts, o, h, l, c = candle
                date_str = datetime.utcfromtimestamp(ts / 1000).strftime("%Y-%m-%d")
                if date_str not in daily_candles:
                    daily_candles[date_str] = {"open": o, "high": h, "low": l, "close": c}
                else:
                    dc = daily_candles[date_str]
                    dc["high"] = max(dc["high"], h)
                    dc["low"] = min(dc["low"], l)
                    dc["close"] = c  # last candle's close

            # Get volumes from market_chart if available
            daily_volumes = {}
            if market_data and "total_volumes" in market_data:
                for ts, vol in market_data["total_volumes"]:
                    date_str = datetime.utcfromtimestamp(ts / 1000).strftime("%Y-%m-%d")
                    daily_volumes[date_str] = int(vol)

            sorted_dates = sorted(daily_candles.keys())[-TARGET_DAYS:]
            rows = []
            for date_str in sorted_dates:
                dc = daily_candles[date_str]
                entry = {
                    "id": ph_id,
                    "asset_id": asset["id"],
                    "date": date_str,
                    "open": round(dc["open"], 2),
                    "high": round(dc["high"], 2),
                    "low": round(dc["low"], 2),
                    "close": round(dc["close"], 2),
                    "volume": daily_volumes.get(date_str, 0),
                }
                rows.append(entry)
                ph_id += 1
            new_price_history.extend(rows)

            # Update asset fields
            if rows:
                last = rows[-1]
                asset["current_price"] = last["close"]
                asset["open_price"] = last["open"]
                asset["high_24h"] = last["high"]
                asset["low_24h"] = last["low"]
                asset["volume_24h"] = last["volume"]

                if len(rows) >= 2:
                    prev_close = rows[-2]["close"]
                    asset["change_pct_24h"] = round(
                        ((last["close"] - prev_close) / prev_close) * 100, 2
                    ) if prev_close else 0.0
                if len(rows) >= 6:
                    close_7d = rows[-6]["close"]
                    asset["change_pct_7d"] = round(
                        ((last["close"] - close_7d) / close_7d) * 100, 2
                    ) if close_7d else 0.0
                close_30d = rows[0]["close"]
                asset["change_pct_30d"] = round(
                    ((last["close"] - close_30d) / close_30d) * 100, 2
                ) if close_30d else 0.0

                window_high = max(r["high"] for r in rows)
                window_low = min(r["low"] for r in rows)
                if window_high > asset.get("all_time_high", 0):
                    asset["all_time_high"] = window_high
                if window_low < asset.get("all_time_low", float("inf")):
                    asset["all_time_low"] = window_low

            updated_count += 1
        else:
            # Fallback: use market_chart prices only
            if market_data and "prices" in market_data:
                prices = market_data["prices"]
                volumes = market_data.get("total_volumes", [])

                # Build daily entries
                daily = {}
                for ts, price in prices:
                    date_str = datetime.utcfromtimestamp(ts / 1000).strftime("%Y-%m-%d")
                    if date_str not in daily:
                        daily[date_str] = {"open": price, "high": price, "low": price, "close": price}
                    else:
                        daily[date_str]["close"] = price
                        daily[date_str]["high"] = max(daily[date_str]["high"], price)
                        daily[date_str]["low"] = min(daily[date_str]["low"], price)

                daily_volumes = {}
                for ts, vol in volumes:
                    date_str = datetime.utcfromtimestamp(ts / 1000).strftime("%Y-%m-%d")
                    daily_volumes[date_str] = int(vol)

                sorted_dates = sorted(daily.keys())[-TARGET_DAYS:]
                rows = []
                for date_str in sorted_dates:
                    dc = daily[date_str]
                    entry = {
                        "id": ph_id,
                        "asset_id": asset["id"],
                        "date": date_str,
                        "open": round(dc["open"], 2),
                        "high": round(dc["high"], 2),
                        "low": round(dc["low"], 2),
                        "close": round(dc["close"], 2),
                        "volume": daily_volumes.get(date_str, 0),
                    }
                    rows.append(entry)
                    ph_id += 1
                new_price_history.extend(rows)

                if rows:
                    last = rows[-1]
                    asset["current_price"] = last["close"]
                    asset["open_price"] = last["open"]
                    asset["high_24h"] = last["high"]
                    asset["low_24h"] = last["low"]
                    asset["volume_24h"] = last["volume"]

                updated_count += 1
            else:
                skipped_count += 1
                existing = [p for p in old_price_history if p["asset_id"] == asset["id"]]
                for p in existing:
                    p_copy = dict(p)
                    p_copy["id"] = ph_id
                    new_price_history.append(p_copy)
                    ph_id += 1

        time.sleep(6)  # CoinGecko free tier: ~10-15 req/min

    print(f"  Updated {updated_count} cryptos, skipped {skipped_count}")
    return new_price_history, ph_id


# ---------------------------------------------------------------------------
# Sector stats update
# ---------------------------------------------------------------------------
def update_sectors(assets, sectors):
    """Recompute sector asset_count and avg_change_pct from updated assets."""
    sector_map = {}
    for asset in assets:
        sector_name = asset["sector"]
        if sector_name not in sector_map:
            sector_map[sector_name] = []
        sector_map[sector_name].append(asset["change_pct_24h"])

    for sector in sectors:
        name = sector["name"]
        if name in sector_map:
            changes = sector_map[name]
            sector["asset_count"] = len(changes)
            sector["avg_change_pct"] = round(sum(changes) / len(changes), 2) if changes else 0.0

    return sectors


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("Stock-Crypto Real Data Updater")
    print("=" * 60)

    # Load existing data
    assets = load_json(ASSETS_FILE)
    old_price_history = load_json(PRICE_HISTORY_FILE)
    sectors = load_json(SECTORS_FILE)

    print(f"Loaded {len(assets)} assets, {len(old_price_history)} price history entries")

    # Process stocks
    stock_ph, next_ph_id = process_stocks(assets, old_price_history)

    # Process cryptos
    crypto_ph, final_ph_id = process_cryptos(assets, old_price_history, next_ph_id)

    # Combine price histories: stock entries + crypto entries
    all_price_history = stock_ph + crypto_ph
    print(f"\nTotal price history entries: {len(all_price_history)}")

    # Update sectors
    sectors = update_sectors(assets, sectors)

    # Save
    print("\nSaving updated data...")
    save_json(ASSETS_FILE, assets)
    save_json(PRICE_HISTORY_FILE, all_price_history)
    save_json(SECTORS_FILE, sectors)

    # Copy to .pristine
    print("\nCopying to .pristine/...")
    PRISTINE_DIR.mkdir(parents=True, exist_ok=True)
    for fname in ["assets.json", "price_history.json", "sectors.json",
                   "users.json", "watchlists.json"]:
        src = DATA_DIR / fname
        dst = PRISTINE_DIR / fname
        if src.exists():
            shutil.copy2(src, dst)
            print(f"  Copied {fname}")

    # Verification summary
    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)
    final_assets = load_json(ASSETS_FILE)
    final_ph = load_json(PRICE_HISTORY_FILE)
    stocks = [a for a in final_assets if a["type"] == "stock"]
    cryptos = [a for a in final_assets if a["type"] == "crypto"]
    print(f"Assets: {len(final_assets)} total ({len(stocks)} stocks, {len(cryptos)} crypto)")
    print(f"Price history: {len(final_ph)} entries")
    from collections import Counter
    c = Counter(p["asset_id"] for p in final_ph)
    print(f"Assets with history: {len(c)}")
    vals = list(c.values())
    print(f"Entries per asset: min={min(vals)}, max={max(vals)}")

    # Spot-check a few stocks
    for sym in ["AAPL", "MSFT", "GOOGL"]:
        a = next((x for x in final_assets if x["symbol"] == sym), None)
        if a:
            entries = [p for p in final_ph if p["asset_id"] == a["id"]]
            print(f"\n{sym}: price=${a['current_price']}, "
                  f"24h={a['change_pct_24h']}%, "
                  f"history={len(entries)} entries "
                  f"({entries[0]['date']} to {entries[-1]['date']})")

    print("\nDone!")


if __name__ == "__main__":
    main()
