"""Per-macro verification functions for converters-calculators.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/converters-calculators"


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/tools")
    tools = r.json()
    ok = isinstance(tools, list) and len(tools) > 0
    return {"pass": ok, "detail": f"Tools list: {len(tools)} tools"}


def verify_macro_select_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/convert/length?value=1&from=mile&to=kilometer")
    data = r.json()
    ok = data.get("result") is not None
    return {"pass": ok, "detail": f"Length convert result: {data.get('result')}"}


def verify_macro_input_by_form(server_url):
    r = requests.get(f"{_base(server_url)}/api/convert/weight?value=100&from=kilogram&to=pound")
    data = r.json()
    ok = data.get("result") is not None
    return {"pass": ok, "detail": f"Weight convert result: {data.get('result')}"}


def verify_macro_calculate_by_form(server_url):
    r = requests.get(f"{_base(server_url)}/api/calculate/bmi?weight=70&height=1.75")
    data = r.json()
    ok = "bmi" in data and "category" in data
    return {"pass": ok, "detail": f"BMI: {data.get('bmi')}, category: {data.get('category')}"}


def verify_macro_extract_by_field(server_url):
    r = requests.get(f"{_base(server_url)}/api/calculate/mortgage?principal=200000&rate=5.0&years=30")
    data = r.json()
    ok = "monthly_payment" in data and "total_interest" in data
    return {"pass": ok,
            "detail": f"Mortgage fields: monthly=${data.get('monthly_payment')}, interest=${data.get('total_interest')}"}


def verify_macro_login_by_form(server_url):
    s = requests.Session()
    r = s.post(f"{_base(server_url)}/api/login",
               json={"username": "converter_alice", "password": "pass123"})
    data = r.json()
    ok = data.get("user_id") == 1
    return {"pass": ok, "detail": f"Login: user_id={data.get('user_id')}"}


def verify_macro_save_by_toggle(server_url):
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login",
           json={"username": "math_dan", "password": "pass321"})
    r = s.post(f"{_base(server_url)}/api/users/4/history", json={
        "tool": "length", "from_value": "1", "from_unit": "meter",
        "to_unit": "foot", "result": "3.28084"
    })
    data = r.json()
    ok = data.get("action") == "saved" and data.get("total_saved", 0) >= 1
    return {"pass": ok, "detail": f"Save to history: total_saved={data.get('total_saved')}"}
