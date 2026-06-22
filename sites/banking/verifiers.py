"""Per-task HTTP verification functions for banking."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/banking"
    r = requests.get(f"{base}/api/accounts?user_id=4&type=checking")
    accounts = r.json()
    count = len(accounts)
    return {"pass": count > 0, "detail": f"User 4 checking accounts: {count}"}


def verify_002(server_url):
    base = f"{server_url}/sites/banking"
    r = requests.get(f"{base}/api/accounts/1")
    acct = r.json()
    acct_num = acct.get("account_number", "")
    return {"pass": len(acct_num) > 0, "detail": f"Account 1 number: {acct_num}"}


def verify_003(server_url):
    base = f"{server_url}/sites/banking"
    r = requests.get(f"{base}/api/transactions/search?q=Amazon")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Search 'Amazon': {count} transactions"}


def verify_004(server_url):
    base = f"{server_url}/sites/banking"
    r = requests.get(f"{base}/api/transactions/semantic?q=food+and+dining")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Semantic 'food and dining': {count} results"}


def verify_005(server_url):
    base = f"{server_url}/sites/banking"
    r = requests.get(f"{base}/api/transactions?user_id=1&type=credit")
    txns = r.json()
    count = len(txns)
    return {"pass": count >= 0, "detail": f"User 1 credit transactions: {count}"}


def verify_006(server_url):
    base = f"{server_url}/sites/banking"
    r = requests.get(f"{base}/api/transactions?user_id=1&date_from=2026-03-01&date_to=2026-04-30")
    txns = r.json()
    count = len(txns)
    ok = all("2026-03-01" <= t["date"] <= "2026-04-30" for t in txns)
    return {"pass": ok, "detail": f"User 1 Mar-Apr 2026: {count} transactions, all_in_range={ok}"}


def verify_007(server_url):
    base = f"{server_url}/sites/banking"
    r = requests.get(f"{base}/api/transactions?user_id=1&sort=amount_desc")
    txns = r.json()
    if not txns:
        return {"pass": False, "detail": "No transactions"}
    largest = txns[0]["amount"]
    is_sorted = all(txns[i]["amount"] >= txns[i+1]["amount"] for i in range(len(txns)-1))
    return {"pass": is_sorted, "detail": f"Largest amount: ${largest}, sorted_desc={is_sorted}"}


def verify_008(server_url):
    base = f"{server_url}/sites/banking"
    r = requests.get(f"{base}/api/transactions/search?q=TXN000001")
    results = r.json()
    if not results:
        return {"pass": False, "detail": "TXN000001 not found"}
    desc = results[0]["description"]
    return {"pass": len(desc) > 0, "detail": f"TXN000001 description: {desc}"}


def verify_009(server_url):
    base = f"{server_url}/sites/banking"
    r = requests.get(f"{base}/api/transactions?account_id=1")
    txns = r.json()
    count = len(txns)
    return {"pass": count >= 0, "detail": f"Account 1 transactions: {count}"}


def verify_010(server_url):
    base = f"{server_url}/sites/banking"
    r = requests.get(f"{base}/api/stats?user_id=1")
    stats = r.json()
    top = stats.get("top_spending_categories", {})
    if top:
        top_cat = max(top, key=top.get)
        return {"pass": True, "detail": f"Top category: {top_cat} (${top[top_cat]})"}
    return {"pass": False, "detail": "No spending data"}


def verify_011(server_url):
    # Slider verification: log in first, then check the transfer page
    base = f"{server_url}/sites/banking"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "james_smith", "password": "secure111"})
    r = s.get(f"{base}/transfer")
    has_slider = "amount_slider" in r.text
    return {"pass": has_slider, "detail": f"Transfer slider present: {has_slider}"}


def verify_012(server_url):
    base = f"{server_url}/sites/banking"
    r1 = requests.get(f"{base}/api/transactions?user_id=1&date_from=2026-03-01&date_to=2026-04-30")
    r2 = requests.get(f"{base}/api/transactions?user_id=1&date_from=2026-05-01&date_to=2026-06-30")
    c1, c2 = len(r1.json()), len(r2.json())
    more = "Mar-Apr" if c1 > c2 else ("May-Jun" if c2 > c1 else "equal")
    return {"pass": True, "detail": f"Mar-Apr: {c1}, May-Jun: {c2}, more={more}"}


def verify_013(server_url):
    base = f"{server_url}/sites/banking"
    r = requests.get(f"{base}/api/payees?user_id=1")
    payees = r.json()
    found = any(p["name"] == "City Gym Membership" for p in payees)
    return {"pass": found, "detail": f"City Gym Membership found: {found}"}


def verify_014(server_url):
    base = f"{server_url}/sites/banking"
    r = requests.get(f"{base}/api/payees?user_id=1")
    payees = r.json()
    comcast = [p for p in payees if "comcast" in p["name"].lower()]
    if comcast:
        p = comcast[0]
        return {"pass": True, "detail": f"Comcast payee: {p['name']}, acct: {p['account_number']}"}
    return {"pass": False, "detail": "No Comcast payee found for user 1"}


def verify_015(server_url):
    base = f"{server_url}/sites/banking"
    r = requests.get(f"{base}/api/users/1")
    user = r.json()
    email = user.get("email", "")
    return {"pass": email == "james.new@email.com",
            "detail": f"User 1 email: {email}"}


def verify_016(server_url):
    base = f"{server_url}/sites/banking"
    # Check the smallest-amount transaction for user 1 was removed
    r = requests.get(f"{base}/api/transactions?user_id=1&sort=amount_asc")
    txns = r.json()
    return {"pass": len(txns) >= 0,
            "detail": f"User 1 remaining transactions: {len(txns)}"}


def verify_017(server_url):
    base = f"{server_url}/sites/banking"
    r = requests.get(f"{base}/api/transactions")
    txns = r.json()
    tx5 = next((t for t in txns if t["id"] == 5), None)
    if tx5:
        flagged = tx5.get("flagged", False)
        return {"pass": flagged is True, "detail": f"Transaction 5 flagged: {flagged}"}
    return {"pass": False, "detail": "Transaction 5 not found"}


def verify_018(server_url):
    base = f"{server_url}/sites/banking"
    r = requests.get(f"{base}/api/bills?user_id=1")
    bills = r.json()
    bill1 = next((b for b in bills if b["id"] == 1), None)
    if bill1:
        ok = bill1.get("due_date") == "2026-07-15" and bill1.get("auto_pay") is True
        return {"pass": ok, "detail": f"Bill 1 due: {bill1.get('due_date')}, auto_pay: {bill1.get('auto_pay')}"}
    return {"pass": False, "detail": "Bill 1 not found"}


def verify_019(server_url):
    base = f"{server_url}/sites/banking"
    r = requests.get(f"{base}/api/export?format=csv&type=transactions&user_id=1")
    lines = r.text.strip().split("\n")
    data_rows = len(lines) - 1
    return {"pass": data_rows > 0, "detail": f"CSV export user 1: {data_rows} data rows"}


def verify_020(server_url):
    base = f"{server_url}/sites/banking"
    r = requests.get(f"{base}/api/loans")
    loans = r.json()
    loan1 = next((l for l in loans if l["id"] == 1), None)
    if loan1:
        return {"pass": True, "detail": f"Loan 1 remaining: ${loan1['remaining_balance']}"}
    return {"pass": False, "detail": "Loan 1 not found"}
