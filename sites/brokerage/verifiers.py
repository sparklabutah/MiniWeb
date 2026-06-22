"""Per-task HTTP verification functions for brokerage."""
import requests


def _base(server_url):
    return f"{server_url}/sites/brokerage"


def verify_001(server_url):
    r = requests.get(f"{_base(server_url)}/api/tickers?type=crypto")
    tickers = r.json()
    count = len(tickers)
    return {"pass": count > 0, "detail": f"Crypto tickers: {count}"}


def verify_002(server_url):
    r = requests.get(f"{_base(server_url)}/api/tickers/AAPL")
    data = r.json()
    exchange = data.get("exchange", "")
    return {"pass": exchange == "NASDAQ", "detail": f"AAPL exchange: {exchange}"}


def verify_003(server_url):
    r = requests.get(f"{_base(server_url)}/api/rankings?metric=change_pct&direction=desc&limit=5")
    data = r.json()
    if not data:
        return {"pass": False, "detail": "No rankings returned"}
    top = data[0]["symbol"]
    return {"pass": len(top) > 0, "detail": f"Top gainer: {top}"}


def verify_004(server_url):
    r = requests.get(f"{_base(server_url)}/api/tickers/search?q=gold")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Search 'gold': {count} results"}


def verify_005(server_url):
    r = requests.get(f"{_base(server_url)}/api/tickers/semantic?q=artificial+intelligence+technology")
    results = r.json()
    syms = [t["symbol"] for t in results]
    return {"pass": r.status_code == 200, "detail": f"Semantic search results: {syms}"}


def verify_006(server_url):
    r = requests.get(f"{_base(server_url)}/api/tickers?sector=Financial+Services")
    tickers = r.json()
    count = len(tickers)
    return {"pass": count > 0, "detail": f"Financial Services: {count} tickers"}


def verify_007(server_url):
    r = requests.get(f"{_base(server_url)}/api/tickers?price_min=100&price_max=300")
    tickers = r.json()
    count = len(tickers)
    ok = all(100 <= t["current_price"] <= 300 for t in tickers)
    return {"pass": ok and count > 0, "detail": f"$100-$300 range: {count} tickers, all_in_range={ok}"}


def verify_008(server_url):
    r = requests.get(f"{_base(server_url)}/api/orders/1?date_from=2026-06-17&date_to=2026-06-19")
    orders = r.json()
    count = len(orders)
    return {"pass": count >= 0, "detail": f"Alice orders Jun 17-19: {count}"}


def verify_009(server_url):
    r = requests.get(f"{_base(server_url)}/api/tickers?sort=price_asc")
    tickers = r.json()
    if not tickers:
        return {"pass": False, "detail": "No tickers"}
    cheapest = tickers[0]["symbol"]
    prices = [t["current_price"] for t in tickers]
    is_sorted = all(prices[i] <= prices[i+1] for i in range(len(prices)-1))
    return {"pass": is_sorted, "detail": f"Cheapest: {cheapest}, sorted={is_sorted}"}


def verify_010(server_url):
    r = requests.get(f"{_base(server_url)}/api/portfolio/3")
    data = r.json()
    holdings = data.get("holdings", [])
    if not holdings:
        return {"pass": False, "detail": "No holdings for user 3"}
    top = max(holdings, key=lambda h: h["market_value"])
    return {"pass": True, "detail": f"Largest holding: {top['symbol']} (${top['market_value']})"}


def verify_011(server_url):
    r = requests.get(f"{_base(server_url)}/api/price_history/TSLA")
    data = r.json()
    daily = data.get("daily", [])
    if not daily:
        return {"pass": False, "detail": "No daily data for TSLA"}
    last_close = daily[-1]["close"]
    return {"pass": last_close > 0, "detail": f"TSLA last close: ${last_close}"}


def verify_012(server_url):
    r = requests.get(f"{_base(server_url)}/api/tickers?type=stock&sort=change_desc")
    tickers = r.json()
    if not tickers:
        return {"pass": False, "detail": "No stocks"}
    best = tickers[0]["symbol"]
    return {"pass": True, "detail": f"Best performing stock: {best} ({tickers[0]['change_pct']}%)"}


def verify_013(server_url):
    r = requests.get(f"{_base(server_url)}/api/portfolio/5")
    data = r.json()
    total = data.get("total_value", 0)
    return {"pass": total > 0, "detail": f"Eve's portfolio value: ${total}"}


def verify_014(server_url):
    r = requests.get(f"{_base(server_url)}/api/tickers/NVDA")
    data = r.json()
    price = data.get("current_price", 0)
    estimated = round(price * 50, 2)
    return {"pass": estimated > 0, "detail": f"50 NVDA at ${price} = ${estimated}"}


def verify_015(server_url):
    r = requests.get(f"{_base(server_url)}/api/compare?symbols=AAPL,MSFT,GOOGL")
    data = r.json()
    if len(data) < 3:
        return {"pass": False, "detail": f"Compare returned {len(data)}, expected 3"}
    best = max(data, key=lambda t: t["change_pct"])
    return {"pass": True, "detail": f"Best of AAPL/MSFT/GOOGL: {best['symbol']} ({best['change_pct']}%)"}


def verify_016(server_url):
    r = requests.get(f"{_base(server_url)}/api/options?underlying=TSLA&type=call")
    options = r.json()
    if not options:
        return {"pass": False, "detail": "No TSLA calls found"}
    iv_pct = round(options[0]["iv"] * 100, 0)
    return {"pass": iv_pct > 50, "detail": f"TSLA call IV: {iv_pct}%"}


def verify_017(server_url):
    base = _base(server_url)
    # Login
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "trader_alice", "password": "alpha123"})
    # Place order
    r = s.post(f"{base}/api/orders", json={
        "user_id": 1, "symbol": "GOOGL", "side": "buy",
        "order_type": "market", "quantity": 10
    })
    data = r.json()
    status = data.get("status", "")
    return {"pass": status == "filled", "detail": f"Order status: {status}"}


def verify_018(server_url):
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "investor_bob", "password": "beta456"})
    r = s.post(f"{base}/api/orders", json={
        "user_id": 2, "symbol": "AAPL", "side": "sell",
        "order_type": "limit", "quantity": 5, "price": 195.00
    })
    data = r.json()
    status = data.get("status", "")
    return {"pass": status == "open", "detail": f"Limit order status: {status}"}


def verify_019(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/orders/6/cancel")
    data = r.json()
    status = data.get("status", "")
    return {"pass": status == "cancelled", "detail": f"Order 6 status: {status}"}


def verify_020(server_url):
    base = _base(server_url)
    # Verify identity
    r1 = requests.post(f"{base}/api/verify_identity", json={"user_id": 4, "code": "628457"})
    d1 = r1.json()
    # Add MSFT to watchlist
    r2 = requests.post(f"{base}/api/watchlist/4/toggle", json={"symbol": "MSFT"})
    d2 = r2.json()
    # Set alert
    r3 = requests.post(f"{base}/api/watchlist/4/alert", json={"symbol": "MSFT", "condition": "above", "price": 450.00})
    d3 = r3.json()
    # Export stock CSV
    r4 = requests.get(f"{base}/api/export?format=csv&type=stock")
    lines = r4.text.strip().split("\n")
    data_rows = len(lines) - 1

    verified = d1.get("verified", False)
    wl_action = d2.get("action", "")
    alert_action = d3.get("action", "")

    all_ok = verified and data_rows > 0
    return {"pass": all_ok,
            "detail": f"verified={verified}, watchlist={wl_action}, alert={alert_action}, csv_rows={data_rows}"}
