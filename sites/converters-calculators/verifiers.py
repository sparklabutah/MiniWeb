"""Per-task HTTP verification functions for converters-calculators."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/converters-calculators"
    r = requests.get(f"{base}/api/units/length")
    data = r.json()
    count = len(data.get("units", {}))
    return {"pass": count == 8, "detail": f"Length units count: {count}"}


def verify_002(server_url):
    base = f"{server_url}/sites/converters-calculators"
    r = requests.get(f"{base}/api/convert/currency?value=100&from=USD&to=EUR")
    data = r.json()
    result = data.get("result")
    expected = 92.14
    return {"pass": result == expected, "detail": f"100 USD to EUR: {result} (expected {expected})"}


def verify_003(server_url):
    base = f"{server_url}/sites/converters-calculators"
    r = requests.get(f"{base}/api/convert/length?value=5&from=mile&to=kilometer")
    data = r.json()
    result = data.get("result")
    expected = 8.04672
    return {"pass": result == expected, "detail": f"5 miles to km: {result} (expected {expected})"}


def verify_004(server_url):
    base = f"{server_url}/sites/converters-calculators"
    r = requests.get(f"{base}/api/convert/temperature?value=100&from=celsius&to=fahrenheit")
    data = r.json()
    result = data.get("result")
    return {"pass": result == 212.0, "detail": f"100 C to F: {result} (expected 212.0)"}


def verify_005(server_url):
    base = f"{server_url}/sites/converters-calculators"
    r = requests.get(f"{base}/api/tools")
    tools = r.json()
    count = len(tools)
    return {"pass": count == 11, "detail": f"Total tools: {count}"}


def verify_006(server_url):
    base = f"{server_url}/sites/converters-calculators"
    r = requests.get(f"{base}/api/tools?category=calculator")
    tools = r.json()
    count = len(tools)
    return {"pass": count == 3, "detail": f"Calculator tools: {count}"}


def verify_007(server_url):
    base = f"{server_url}/sites/converters-calculators"
    r = requests.get(f"{base}/api/convert/weight?value=10&from=pound&to=kilogram")
    data = r.json()
    result = data.get("result")
    expected = 4.535924
    return {"pass": result == expected, "detail": f"10 lb to kg: {result} (expected {expected})"}


def verify_008(server_url):
    base = f"{server_url}/sites/converters-calculators"
    r = requests.get(f"{base}/api/calculate/mortgage?principal=300000&rate=6.5&years=30")
    data = r.json()
    monthly = data.get("monthly_payment")
    return {"pass": monthly == 1896.20, "detail": f"Mortgage monthly: ${monthly} (expected $1896.20)"}


def verify_009(server_url):
    base = f"{server_url}/sites/converters-calculators"
    r = requests.get(f"{base}/api/calculate/bmi?weight=85&height=1.80")
    data = r.json()
    bmi = data.get("bmi")
    cat = data.get("category")
    return {"pass": bmi == 26.23 and cat == "Overweight",
            "detail": f"BMI: {bmi} ({cat})"}


def verify_010(server_url):
    base = f"{server_url}/sites/converters-calculators"
    r = requests.get(f"{base}/api/calculate/tip?bill=85.50&tip_percent=18&people=3")
    data = r.json()
    pp = data.get("per_person")
    return {"pass": pp == 33.63, "detail": f"Per person: ${pp} (expected $33.63)"}


def verify_011(server_url):
    base = f"{server_url}/sites/converters-calculators"
    r = requests.get(f"{base}/api/convert/base?value=255&from=10&to=16")
    data = r.json()
    result = data.get("result")
    return {"pass": result == "FF", "detail": f"255 decimal to hex: {result}"}


def verify_012(server_url):
    base = f"{server_url}/sites/converters-calculators"
    r = requests.get(f"{base}/api/convert/volume?value=2&from=gallon&to=liter")
    data = r.json()
    result = data.get("result")
    expected = 7.570824
    return {"pass": result == expected, "detail": f"2 gallons to liters: {result} (expected {expected})"}


def verify_013(server_url):
    base = f"{server_url}/sites/converters-calculators"
    r = requests.get(f"{base}/api/convert/speed?value=100&from=kilometers_per_hour&to=miles_per_hour")
    data = r.json()
    result = data.get("result")
    # 100 * 0.277777778 / 0.44704 = 62.137119
    return {"pass": result is not None and abs(result - 62.137119) < 0.01,
            "detail": f"100 km/h to mph: {result}"}


def verify_014(server_url):
    base = f"{server_url}/sites/converters-calculators"
    r = requests.get(f"{base}/api/convert/area?value=1&from=acre&to=square_meter")
    data = r.json()
    result = data.get("result")
    expected = 4046.856422
    return {"pass": result is not None and abs(result - expected) < 0.01,
            "detail": f"1 acre to sq meters: {result} (expected ~{expected})"}


def verify_015(server_url):
    base = f"{server_url}/sites/converters-calculators"
    # Login
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "converter_alice", "password": "pass123"})
    # Convert via API
    r = s.get(f"{base}/api/convert/length?value=5&from=mile&to=kilometer")
    conv = r.json()
    # Save to history
    r = s.post(f"{base}/api/users/1/history", json={
        "tool": "length", "from_value": "5", "from_unit": "mile",
        "to_unit": "kilometer", "result": str(conv.get("result", ""))
    })
    data = r.json()
    total = data.get("total_saved", 0)
    return {"pass": total >= 1, "detail": f"User 1 saved conversions: {total}"}


def verify_016(server_url):
    base = f"{server_url}/sites/converters-calculators"
    r = requests.get(f"{base}/api/calculate/mortgage?principal=500000&rate=7.25&years=15")
    data = r.json()
    interest = data.get("total_interest")
    return {"pass": interest is not None and interest > 0,
            "detail": f"$500k mortgage total interest: ${interest}"}


def verify_017(server_url):
    base = f"{server_url}/sites/converters-calculators"
    r1 = requests.get(f"{base}/api/convert/temperature?value=0&from=kelvin&to=celsius")
    r2 = requests.get(f"{base}/api/convert/temperature?value=0&from=kelvin&to=fahrenheit")
    c = r1.json().get("result")
    f = r2.json().get("result")
    return {"pass": c == -273.15 and f == -459.67,
            "detail": f"0K = {c}C, {f}F"}


def verify_018(server_url):
    base = f"{server_url}/sites/converters-calculators"
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "calc_bob", "password": "pass456"})
    # Save 3 conversions
    conversions = [
        {"tool": "currency", "from_value": "100", "from_unit": "USD", "to_unit": "EUR", "result": "92.14"},
        {"tool": "length", "from_value": "5", "from_unit": "mile", "to_unit": "kilometer", "result": "8.04672"},
        {"tool": "temperature", "from_value": "100", "from_unit": "celsius", "to_unit": "fahrenheit", "result": "212"},
    ]
    for conv in conversions:
        s.post(f"{base}/api/users/2/history", json=conv)
    r = s.get(f"{base}/api/users/2")
    user = r.json()
    count = len(user.get("saved_conversions", []))
    return {"pass": count >= 3, "detail": f"User 2 saved conversions: {count}"}


def verify_019(server_url):
    base = f"{server_url}/sites/converters-calculators"
    # 1000 JPY -> USD
    r1 = requests.get(f"{base}/api/convert/currency?value=1000&from=JPY&to=USD")
    usd = r1.json().get("result")
    # USD -> EUR
    r2 = requests.get(f"{base}/api/convert/currency?value={usd}&from=USD&to=EUR")
    eur = r2.json().get("result")
    return {"pass": eur is not None and eur > 0,
            "detail": f"1000 JPY -> ${usd} USD -> {eur} EUR"}


def verify_020(server_url):
    base = f"{server_url}/sites/converters-calculators"
    # Binary to decimal
    r1 = requests.get(f"{base}/api/convert/base?value=11111111&from=2&to=10")
    dec = r1.json().get("result")
    # Binary to hex
    r2 = requests.get(f"{base}/api/convert/base?value=11111111&from=2&to=16")
    hex_val = r2.json().get("result")
    return {"pass": dec == "255" and hex_val == "FF",
            "detail": f"11111111 binary = {dec} decimal, {hex_val} hex"}
