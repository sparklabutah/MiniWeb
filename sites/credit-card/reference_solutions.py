"""Per-task reference solutions via Flask test client for credit-card."""
import json


def solve_001(client, base="/sites/credit-card"):
    r = client.get(f"{base}/api/accounts/1")
    user = json.loads(r.data)
    return str(user["current_balance"])


def solve_002(client, base="/sites/credit-card"):
    r = client.get(f"{base}/api/transactions?user_id=2")
    txns = json.loads(r.data)
    return str(len(txns))


def solve_003(client, base="/sites/credit-card"):
    r = client.get(f"{base}/api/accounts/3")
    user = json.loads(r.data)
    return str(user["credit_limit"])


def solve_004(client, base="/sites/credit-card"):
    r = client.get(f"{base}/api/transactions?user_id=1&category=Groceries")
    txns = json.loads(r.data)
    return str(len(txns))


def solve_005(client, base="/sites/credit-card"):
    r = client.get(f"{base}/api/accounts/4")
    user = json.loads(r.data)
    return user["card_number_last4"]


def solve_006(client, base="/sites/credit-card"):
    r = client.get(f"{base}/api/transactions?user_id=5&category=Travel")
    txns = json.loads(r.data)
    total = sum(t["amount"] for t in txns)
    return f"{total:.2f}"


def solve_007(client, base="/sites/credit-card"):
    r = client.get(f"{base}/api/statements?user_id=1")
    stmts = json.loads(r.data)
    total_interest = sum(s["interest"] for s in stmts)
    return f"{total_interest:.2f}"


def solve_008(client, base="/sites/credit-card"):
    r = client.get(f"{base}/api/transactions?disputed=true")
    txns = json.loads(r.data)
    return str(len(txns))


def solve_009(client, base="/sites/credit-card"):
    r = client.get(f"{base}/api/spending?user_id=2")
    data = json.loads(r.data)
    by_cat = data.get("by_category", {})
    if by_cat:
        top_cat = max(by_cat, key=by_cat.get)
        return top_cat
    return "None"


def solve_010(client, base="/sites/credit-card"):
    r = client.get(f"{base}/api/rewards?user_id=3")
    data = json.loads(r.data)
    return str(data.get("total_earned_from_transactions", 0))


def solve_011(client, base="/sites/credit-card"):
    r = client.get(f"{base}/api/transactions?sort=amount_desc")
    txns = json.loads(r.data)
    if txns:
        return txns[0]["merchant"]
    return "None"


def solve_012(client, base="/sites/credit-card"):
    r = client.get(f"{base}/api/payments?user_id=5")
    payments = json.loads(r.data)
    total = sum(p["amount"] for p in payments)
    return f"{total:.2f}"


def solve_013(client, base="/sites/credit-card"):
    r = client.get(f"{base}/api/transactions?user_id=1&date_from=2025-01-20&date_to=2025-01-31")
    txns = json.loads(r.data)
    return str(len(txns))


def solve_014(client, base="/sites/credit-card"):
    r = client.get(f"{base}/api/stats")
    data = json.loads(r.data)
    return f"{data['total_spend']:.2f}"


def solve_015(client, base="/sites/credit-card"):
    client.post(f"{base}/api/login",
                json={"username": "sarah_miller", "password": "cardpass1"})
    r = client.post(f"{base}/api/payments",
                    json={"user_id": 1, "amount": 200.0, "method": "bank_transfer"})
    data = json.loads(r.data)
    return data.get("status", "")


def solve_016(client, base="/sites/credit-card"):
    r = client.post(f"{base}/api/transactions/5/dispute")
    data = json.loads(r.data)
    return data.get("action", "")


def solve_017(client, base="/sites/credit-card"):
    client.post(f"{base}/api/settings",
                json={"user_id": 4, "card_frozen": True})
    r = client.get(f"{base}/api/accounts/4")
    user = json.loads(r.data)
    return str(user.get("card_frozen"))


def solve_018(client, base="/sites/credit-card"):
    client.post(f"{base}/api/settings",
                json={"user_id": 5, "email": "aisha.new@email.com", "autopay_enabled": True})
    r = client.get(f"{base}/api/accounts/5")
    user = json.loads(r.data)
    return f"email={user['email']}, autopay={user['autopay_enabled']}"


def solve_019(client, base="/sites/credit-card"):
    r = client.post(f"{base}/api/rewards/redeem",
                    json={"user_id": 1, "points": 5000})
    data = json.loads(r.data)
    return f"credit=${data.get('credit_amount')}, remaining={data.get('remaining_points')}"


def solve_020(client, base="/sites/credit-card"):
    client.post(f"{base}/api/payments",
                json={"user_id": 2, "amount": 500.0, "method": "bank_transfer"})
    r = client.get(f"{base}/api/accounts/2")
    user = json.loads(r.data)
    return str(user["current_balance"])
