"""Generate deterministic price_history.json for the brokerage site.
Run once to produce the data file, then delete this script or keep for reference.
"""
import json
import random
import pathlib

DATA_DIR = pathlib.Path(__file__).resolve().parent

def generate():
    rng = random.Random(42)
    tickers = json.loads((DATA_DIR / "tickers.json").read_text())

    # 5 trading days: Mon Jun 16 - Fri Jun 20, 2026
    trading_dates = ["2026-06-16", "2026-06-17", "2026-06-18", "2026-06-19", "2026-06-20"]
    # Intraday times: 09:30 to 16:00 in 30-min intervals = 14 points
    intraday_times = []
    for h in range(9, 16):
        for m in [0, 30]:
            t = f"{h:02d}:{m:02d}"
            if h == 9 and m == 0:
                continue  # skip 09:00, start at 09:30
            intraday_times.append(t)
    intraday_times.append("16:00")
    # That gives us: 09:30, 10:00, 10:30, ..., 15:30, 16:00

    # Crypto trades 24/7, so we have different intraday schedule
    crypto_times = [f"{h:02d}:00" for h in range(0, 24, 2)]  # every 2 hours

    # Weekend days for crypto
    all_dates = ["2026-06-14", "2026-06-15"] + trading_dates + ["2026-06-21", "2026-06-22"]  # Sat-Sun before + Mon-Fri + Sat-Sun after

    price_history = {}

    for ticker in tickers:
        sym = ticker["symbol"]
        bp = ticker["base_price"]
        is_crypto = ticker["type"] == "crypto"
        volatility = 0.03 if is_crypto else 0.012 if ticker["type"] == "futures" else 0.008

        dates_to_use = all_dates if is_crypto else trading_dates
        times_to_use = crypto_times if is_crypto else intraday_times

        daily_data = []
        intraday_data = []
        current_price = bp

        for date in dates_to_use:
            day_open = current_price
            day_high = day_open
            day_low = day_open
            day_prices = []

            for t in times_to_use:
                change_pct = rng.gauss(0, volatility / len(times_to_use)**0.5)
                current_price = round(current_price * (1 + change_pct), 4 if bp < 1 else 2)
                if current_price <= 0:
                    current_price = round(bp * 0.01, 4 if bp < 1 else 2)
                day_high = max(day_high, current_price)
                day_low = min(day_low, current_price)
                day_prices.append(current_price)

                vol = rng.randint(1000, 500000) if not is_crypto else rng.randint(100, 50000)
                intraday_data.append({
                    "date": date,
                    "time": t,
                    "price": current_price,
                    "volume": vol
                })

            day_close = current_price
            day_vol = sum(p["volume"] for p in intraday_data if p["date"] == date)
            daily_data.append({
                "date": date,
                "open": round(day_open, 4 if bp < 1 else 2),
                "high": round(day_high, 4 if bp < 1 else 2),
                "low": round(day_low, 4 if bp < 1 else 2),
                "close": round(day_close, 4 if bp < 1 else 2),
                "volume": day_vol
            })

        price_history[sym] = {
            "daily": daily_data,
            "intraday": intraday_data
        }

    (DATA_DIR / "price_history.json").write_text(json.dumps(price_history, indent=2))
    print(f"Generated price_history.json with {len(price_history)} tickers")

if __name__ == "__main__":
    generate()
