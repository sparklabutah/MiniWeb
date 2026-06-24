"""Per-task HTTP verification functions for credit-card."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/credit-card"
    r = requests.get(f"{base}/api/accounts/1")
    user = r.json()
    balance = user.get("current_balance")
    return {"pass": balance is not None and balance > 0, "detail": f"Sarah's balance: ${balance}"}


def verify_002(server_url):
    base = f"{server_url}/sites/credit-card"
    r = requests.get(f"{base}/api/transactions?user_id=2")
    txns = r.json()
    count = len(txns)
    return {"pass": count > 0, "detail": f"James has {count} transactions"}


def verify_003(server_url):
    base = f"{server_url}/sites/credit-card"
    r = requests.get(f"{base}/api/accounts/3")
    user = r.json()
    limit = user.get("credit_limit")
    return {"pass": limit == 25000.0, "detail": f"Maria's credit limit: ${limit}"}


def verify_004(server_url):
    base = f"{server_url}/sites/credit-card"
    r = requests.get(f"{base}/api/transactions?user_id=1&category=Groceries")
    txns = r.json()
    count = len(txns)
    return {"pass": count > 0, "detail": f"User 1 grocery transactions: {count}"}


def verify_005(server_url):
    base = f"{server_url}/sites/credit-card"
    r = requests.get(f"{base}/api/accounts/4")
    user = r.json()
    last4 = user.get("card_number_last4")
    return {"pass": last4 == "3387", "detail": f"Kevin's last 4 digits: {last4}"}


def verify_006(server_url):
    base = f"{server_url}/sites/credit-card"
    r = requests.get(f"{base}/api/transactions?user_id=5&category=Travel")
    txns = r.json()
    total = sum(t["amount"] for t in txns)
    return {"pass": total > 0, "detail": f"Aisha travel spend: ${total:.2f}"}


def verify_007(server_url):
    base = f"{server_url}/sites/credit-card"
    r = requests.get(f"{base}/api/statements?user_id=1")
    stmts = r.json()
    total_interest = sum(s["interest"] for s in stmts)
    return {"pass": total_interest > 0, "detail": f"Sarah total interest: ${total_interest:.2f}"}


def verify_008(server_url):
    base = f"{server_url}/sites/credit-card"
    r = requests.get(f"{base}/api/transactions?disputed=true")
    txns = r.json()
    count = len(txns)
    return {"pass": count >= 0, "detail": f"Disputed transactions: {count}"}


def verify_009(server_url):
    base = f"{server_url}/sites/credit-card"
    r = requests.get(f"{base}/api/spending?user_id=2")
    data = r.json()
    by_cat = data.get("by_category", {})
    if by_cat:
        top_cat = max(by_cat, key=by_cat.get)
        return {"pass": True, "detail": f"James top category: {top_cat} (${by_cat[top_cat]:.2f})"}
    return {"pass": False, "detail": "No spending data"}


def verify_010(server_url):
    base = f"{server_url}/sites/credit-card"
    r = requests.get(f"{base}/api/rewards?user_id=3")
    data = r.json()
    earned = data.get("total_earned_from_transactions", 0)
    return {"pass": earned > 0, "detail": f"Maria rewards earned: {earned}"}


def verify_011(server_url):
    base = f"{server_url}/sites/credit-card"
    r = requests.get(f"{base}/api/transactions?sort=amount_desc")
    txns = r.json()
    if txns:
        top = txns[0]
        return {"pass": True, "detail": f"Most expensive: {top['merchant']} ${top['amount']:.2f}"}
    return {"pass": False, "detail": "No transactions"}


def verify_012(server_url):
    base = f"{server_url}/sites/credit-card"
    r = requests.get(f"{base}/api/payments?user_id=5")
    payments = r.json()
    total = sum(p["amount"] for p in payments)
    return {"pass": total > 0, "detail": f"Aisha total payments: ${total:.2f}"}


def verify_013(server_url):
    base = f"{server_url}/sites/credit-card"
    r = requests.get(f"{base}/api/transactions?user_id=1&date_from=2025-01-20&date_to=2025-01-31")
    txns = r.json()
    count = len(txns)
    ok = all(t["date"] >= "2025-01-20" and t["date"] <= "2025-01-31" for t in txns)
    return {"pass": ok and count > 0, "detail": f"Sarah Jan 20-31 transactions: {count}, in_range={ok}"}


def verify_014(server_url):
    base = f"{server_url}/sites/credit-card"
    r = requests.get(f"{base}/api/stats")
    data = r.json()
    total = data.get("total_spend", 0)
    return {"pass": total > 0, "detail": f"Platform total spend: ${total:.2f}"}


def verify_015(server_url):
    base = f"{server_url}/sites/credit-card"
    # Check that a payment was made by user 1
    r = requests.get(f"{base}/api/payments?user_id=1")
    payments = r.json()
    # Look for a $200 payment
    found = any(p["amount"] == 200.0 for p in payments)
    return {"pass": found, "detail": f"$200 payment found for user 1: {found}"}


def verify_016(server_url):
    base = f"{server_url}/sites/credit-card"
    r = requests.get(f"{base}/api/transactions/5")
    txn = r.json()
    disputed = txn.get("disputed", False)
    return {"pass": disputed, "detail": f"Transaction 5 disputed: {disputed}"}


def verify_017(server_url):
    base = f"{server_url}/sites/credit-card"
    r = requests.get(f"{base}/api/accounts/4")
    user = r.json()
    frozen = user.get("card_frozen", False)
    return {"pass": frozen, "detail": f"Kevin's card frozen: {frozen}"}


def verify_018(server_url):
    base = f"{server_url}/sites/credit-card"
    r = requests.get(f"{base}/api/accounts/5")
    user = r.json()
    email_ok = user.get("email") == "aisha.new@email.com"
    autopay_ok = user.get("autopay_enabled") is True
    return {"pass": email_ok and autopay_ok,
            "detail": f"Email={user.get('email')}, autopay={user.get('autopay_enabled')}"}


def verify_019(server_url):
    base = f"{server_url}/sites/credit-card"
    r = requests.get(f"{base}/api/accounts/1")
    user = r.json()
    # After redeeming 5000 points, should have original - 5000
    pts = user.get("rewards_points", 0)
    expected = 48320 - 5000
    return {"pass": pts == expected, "detail": f"Sarah points after redeem: {pts} (expected {expected})"}


def verify_020(server_url):
    base = f"{server_url}/sites/credit-card"
    r = requests.get(f"{base}/api/accounts/2")
    user = r.json()
    balance = user.get("current_balance")
    expected = round(6814.33 - 500.0, 2)
    return {"pass": balance == expected,
            "detail": f"James balance after $500 payment: ${balance} (expected ${expected})"}
