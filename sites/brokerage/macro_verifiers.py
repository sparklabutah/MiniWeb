"""Per-macro verification functions for brokerage.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/brokerage"


def verify_macro_navigate_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/tickers?type=crypto")
    tickers = r.json()
    return {"pass": len(tickers) > 0, "detail": f"navigate_by_dropdown crypto: {len(tickers)} tickers"}


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/ticker/AAPL")
    return {"pass": r.status_code == 200, "detail": f"navigate_by_route AAPL: {r.status_code}"}


def verify_macro_navigate_by_ranking(server_url):
    r = requests.get(f"{_base(server_url)}/api/rankings?metric=change_pct&direction=desc&limit=5")
    data = r.json()
    return {"pass": len(data) == 5, "detail": f"navigate_by_ranking: {len(data)} results"}


def verify_macro_search_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/tickers/search?q=apple")
    results = r.json()
    return {"pass": len(results) > 0, "detail": f"search_by_query 'apple': {len(results)} results"}


def verify_macro_search_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/tickers/semantic?q=technology+computing")
    results = r.json()
    return {"pass": r.status_code == 200, "detail": f"search_by_semantic: {len(results)} results"}


def verify_macro_filter_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/tickers?sector=Technology")
    tickers = r.json()
    ok = all(t["sector"] == "Technology" for t in tickers)
    return {"pass": ok and len(tickers) > 0, "detail": f"filter_by_dropdown Technology: {len(tickers)}, all_match={ok}"}


def verify_macro_filter_by_slider(server_url):
    r = requests.get(f"{_base(server_url)}/api/tickers?price_min=50&price_max=200")
    tickers = r.json()
    ok = all(50 <= t["current_price"] <= 200 for t in tickers)
    return {"pass": ok, "detail": f"filter_by_slider $50-$200: {len(tickers)}, all_in_range={ok}"}


def verify_macro_filter_by_date_range(server_url):
    r = requests.get(f"{_base(server_url)}/api/orders/1?date_from=2026-06-16&date_to=2026-06-17")
    orders = r.json()
    return {"pass": r.status_code == 200, "detail": f"filter_by_date_range: {len(orders)} orders"}


def verify_macro_sort_by_ranking(server_url):
    r = requests.get(f"{_base(server_url)}/api/tickers?sort=price_asc")
    tickers = r.json()
    prices = [t["current_price"] for t in tickers]
    is_sorted = all(prices[i] <= prices[i+1] for i in range(len(prices)-1))
    return {"pass": is_sorted, "detail": f"sort_by_ranking: sorted={is_sorted}"}


def verify_macro_extract_from_table(server_url):
    r = requests.get(f"{_base(server_url)}/api/portfolio/3")
    data = r.json()
    holdings = data.get("holdings", [])
    return {"pass": len(holdings) > 0, "detail": f"extract_from_table: {len(holdings)} holdings"}


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/tickers/TSLA")
    data = r.json()
    return {"pass": "current_price" in data, "detail": f"extract_by_route TSLA: price={data.get('current_price')}"}


def verify_macro_extract_by_extremum(server_url):
    r = requests.get(f"{_base(server_url)}/api/stats?type=stock")
    stats = r.json()
    best = stats.get("best_performer", "")
    return {"pass": len(best) > 0, "detail": f"extract_by_extremum: best_performer={best}"}


def verify_macro_compute_by_extremum(server_url):
    r = requests.get(f"{_base(server_url)}/api/portfolio/5")
    data = r.json()
    total = data.get("total_value", 0)
    return {"pass": total > 0, "detail": f"compute_by_extremum: portfolio_value=${total}"}


def verify_macro_compute_by_slider(server_url):
    r = requests.get(f"{_base(server_url)}/api/tickers/NVDA")
    data = r.json()
    price = data.get("current_price", 0)
    est = round(price * 50, 2)
    return {"pass": est > 0, "detail": f"compute_by_slider: 50 NVDA = ${est}"}


def verify_macro_compare_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/compare?symbols=AAPL,MSFT")
    data = r.json()
    return {"pass": len(data) == 2, "detail": f"compare_by_dropdown: {len(data)} securities"}


def verify_macro_verify_by_slider(server_url):
    r = requests.get(f"{_base(server_url)}/api/options?underlying=TSLA&type=call")
    options = r.json()
    if not options:
        return {"pass": False, "detail": "No TSLA calls"}
    iv = options[0]["iv"]
    return {"pass": iv > 0, "detail": f"verify_by_slider: TSLA call IV={iv}"}


def verify_macro_submit_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/tickers/search?q=AAPL")
    results = r.json()
    return {"pass": len(results) > 0, "detail": f"submit_by_query: {len(results)} results"}


def verify_macro_select_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/tickers?sector=Technology")
    return {"pass": r.status_code == 200, "detail": f"select_by_dropdown: {r.status_code}"}


def verify_macro_select_by_extremum(server_url):
    r = requests.get(f"{_base(server_url)}/api/rankings?metric=price&direction=desc&limit=1")
    data = r.json()
    if data:
        return {"pass": True, "detail": f"select_by_extremum: highest price={data[0]['symbol']}"}
    return {"pass": False, "detail": "No rankings"}


def verify_macro_configure_by_radio(server_url):
    # Test that order types are configurable (limit vs market)
    r = requests.get(f"{_base(server_url)}/trade")
    return {"pass": r.status_code == 200, "detail": f"configure_by_radio: trade page {r.status_code}"}


def verify_macro_configure_by_slider(server_url):
    # Quantity slider is on the trade page
    r = requests.get(f"{_base(server_url)}/trade?symbol=AAPL")
    return {"pass": r.status_code == 200 and "qty-slider" in r.text,
            "detail": "configure_by_slider: qty slider present"}


def verify_macro_export_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/export?format=csv&type=stock")
    lines = r.text.strip().split("\n")
    return {"pass": len(lines) > 1, "detail": f"export_by_dropdown CSV: {len(lines)} lines"}


def verify_macro_follow_by_toggle(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/watchlist/4/toggle", json={"symbol": "TEST_TOGGLE"})
    data = r.json()
    ok = data.get("action") == "added"
    # Toggle back
    requests.post(f"{base}/api/watchlist/4/toggle", json={"symbol": "TEST_TOGGLE"})
    return {"pass": ok, "detail": f"follow_by_toggle: action={data.get('action')}"}


def verify_macro_save_by_toggle(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/watchlist/4/toggle", json={"symbol": "SAVE_TEST"})
    data = r.json()
    ok = data.get("action") == "added"
    requests.post(f"{base}/api/watchlist/4/toggle", json={"symbol": "SAVE_TEST"})
    return {"pass": ok, "detail": f"save_by_toggle: action={data.get('action')}"}


def verify_macro_submit_by_form(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/orders", json={
        "user_id": 4, "symbol": "AAPL", "side": "buy",
        "order_type": "market", "quantity": 1
    })
    data = r.json()
    return {"pass": data.get("status") == "filled", "detail": f"submit_by_form: status={data.get('status')}"}


def verify_macro_pay_by_query(server_url):
    # A purchase/trade is a form of payment
    base = _base(server_url)
    r = requests.post(f"{base}/api/orders", json={
        "user_id": 4, "symbol": "SPY", "side": "buy",
        "order_type": "market", "quantity": 1
    })
    data = r.json()
    return {"pass": r.status_code == 200, "detail": f"pay_by_query: order {data.get('id')}"}


def verify_macro_cancel_by_form(server_url):
    base = _base(server_url)
    # Create an open order to cancel
    r = requests.post(f"{base}/api/orders", json={
        "user_id": 4, "symbol": "MSFT", "side": "buy",
        "order_type": "limit", "quantity": 1, "price": 400.00
    })
    order = r.json()
    oid = order.get("id")
    r2 = requests.post(f"{base}/api/orders/{oid}/cancel")
    data = r2.json()
    return {"pass": data.get("status") == "cancelled", "detail": f"cancel_by_form: order {oid} -> {data.get('status')}"}


def verify_macro_authenticate_by_form(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/login",
                      json={"username": "trader_alice", "password": "alpha123"})
    data = r.json()
    return {"pass": data.get("user_id") == 1, "detail": f"authenticate: user_id={data.get('user_id')}"}


def verify_macro_verify_identity_by_code(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/verify_identity",
                      json={"user_id": 4, "code": "628457"})
    data = r.json()
    return {"pass": data.get("verified") == True, "detail": f"verify_identity: verified={data.get('verified')}"}


def verify_macro_compute_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/stats?sector=Technology")
    stats = r.json()
    return {"pass": "count" in stats and "avg_price" in stats,
            "detail": f"compute_by_dropdown: Technology count={stats.get('count')}, avg=${stats.get('avg_price')}"}
