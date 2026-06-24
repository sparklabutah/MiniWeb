"""Per-task reference solutions via Flask test client for converters-calculators."""
import json


def solve_001(client, base="/sites/converters-calculators"):
    r = client.get(f"{base}/api/units/length")
    data = json.loads(r.data)
    return str(len(data.get("units", {})))


def solve_002(client, base="/sites/converters-calculators"):
    r = client.get(f"{base}/api/convert/length?value=5&from=mile&to=kilometer")
    data = json.loads(r.data)
    return str(data.get("result"))


def solve_003(client, base="/sites/converters-calculators"):
    r = client.get(f"{base}/api/convert/weight?value=150&from=pound&to=kilogram")
    data = json.loads(r.data)
    return str(data.get("result"))


def solve_004(client, base="/sites/converters-calculators"):
    r = client.get(f"{base}/api/convert/temperature?value=100&from=celsius&to=fahrenheit")
    data = json.loads(r.data)
    return str(data.get("result"))


def solve_005(client, base="/sites/converters-calculators"):
    r = client.get(f"{base}/api/convert/currency?value=100&from=USD&to=EUR")
    data = json.loads(r.data)
    return str(data.get("result"))


def solve_006(client, base="/sites/converters-calculators"):
    r = client.get(f"{base}/api/calculate/bmi?weight=70&height=1.75")
    data = json.loads(r.data)
    return f"bmi={data.get('bmi')}, category={data.get('category')}"


def solve_007(client, base="/sites/converters-calculators"):
    r = client.get(f"{base}/api/calculate/tip?bill=85.50&tip_percent=18&people=1")
    data = json.loads(r.data)
    return str(data.get("total"))


def solve_008(client, base="/sites/converters-calculators"):
    r = client.get(f"{base}/api/tools")
    tools = json.loads(r.data)
    return str(len(tools))


def solve_009(client, base="/sites/converters-calculators"):
    r = client.get(f"{base}/api/calculate/mortgage?principal=300000&rate=6.5&years=30")
    data = json.loads(r.data)
    return str(data.get("monthly_payment"))


def solve_010(client, base="/sites/converters-calculators"):
    r = client.get(f"{base}/api/convert/volume?value=2.5&from=gallon&to=liter")
    data = json.loads(r.data)
    return str(data.get("result"))


def solve_011(client, base="/sites/converters-calculators"):
    r = client.get(f"{base}/api/convert/area?value=1&from=acre&to=square_meter")
    data = json.loads(r.data)
    return str(data.get("result"))


def solve_012(client, base="/sites/converters-calculators"):
    r = client.get(f"{base}/api/convert/speed?value=100&from=kilometers_per_hour&to=miles_per_hour")
    data = json.loads(r.data)
    return str(data.get("result"))


def solve_013(client, base="/sites/converters-calculators"):
    r = client.get(f"{base}/api/convert/base?value=255&from=10&to=16")
    data = json.loads(r.data)
    return data.get("result")


def solve_014(client, base="/sites/converters-calculators"):
    r = client.get(f"{base}/api/convert/currency?value=1000&from=JPY&to=GBP")
    data = json.loads(r.data)
    return str(data.get("result"))


def solve_015(client, base="/sites/converters-calculators"):
    r = client.get(f"{base}/api/convert/temperature?value=0&from=kelvin&to=fahrenheit")
    data = json.loads(r.data)
    return str(data.get("result"))


def solve_016(client, base="/sites/converters-calculators"):
    r = client.get(f"{base}/api/calculate/tip?bill=200&tip_percent=20&people=4")
    data = json.loads(r.data)
    return str(data.get("per_person"))


def solve_017(client, base="/sites/converters-calculators"):
    r = client.get(f"{base}/api/tools?category=converter")
    tools = json.loads(r.data)
    return str(len(tools))


def solve_018(client, base="/sites/converters-calculators"):
    # Login
    client.post(f"{base}/api/login",
                data=json.dumps({"username": "converter_alice", "password": "pass123"}),
                content_type="application/json")
    # Convert 10 feet to meters
    r = client.get(f"{base}/api/convert/length?value=10&from=foot&to=meter")
    conv = json.loads(r.data)
    # Save to history
    r = client.post(f"{base}/api/users/1/history",
                    data=json.dumps({
                        "tool": "length", "from_value": "10", "from_unit": "foot",
                        "to_unit": "meter", "result": str(conv.get("result", ""))
                    }),
                    content_type="application/json")
    data = json.loads(r.data)
    return str(data.get("total_saved", 0))


def solve_019(client, base="/sites/converters-calculators"):
    # Login
    client.post(f"{base}/api/login",
                data=json.dumps({"username": "calc_bob", "password": "pass456"}),
                content_type="application/json")
    # Save first: 100 USD to EUR
    r1 = client.get(f"{base}/api/convert/currency?value=100&from=USD&to=EUR")
    c1 = json.loads(r1.data)
    client.post(f"{base}/api/users/2/history",
                data=json.dumps({
                    "tool": "currency", "from_value": "100", "from_unit": "USD",
                    "to_unit": "EUR", "result": str(c1.get("result", ""))
                }),
                content_type="application/json")
    # Save second: 72 F to Celsius
    r2 = client.get(f"{base}/api/convert/temperature?value=72&from=fahrenheit&to=celsius")
    c2 = json.loads(r2.data)
    r = client.post(f"{base}/api/users/2/history",
                    data=json.dumps({
                        "tool": "temperature", "from_value": "72", "from_unit": "fahrenheit",
                        "to_unit": "celsius", "result": str(c2.get("result", ""))
                    }),
                    content_type="application/json")
    data = json.loads(r.data)
    return str(data.get("total_saved", 0))


def solve_020(client, base="/sites/converters-calculators"):
    r = client.get(f"{base}/api/calculate/mortgage?principal=500000&rate=7.25&years=15")
    data = json.loads(r.data)
    return str(data.get("total_interest"))
