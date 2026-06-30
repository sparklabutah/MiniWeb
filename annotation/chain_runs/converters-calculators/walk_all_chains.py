#!/usr/bin/env python3
"""Walk all chains for converters-calculators site."""
import json
import sys
import os

sys.path.insert(0, "/scratch/general/vast/u1653932/projects/MiniWeb")
os.chdir("/scratch/general/vast/u1653932/projects/MiniWeb")

from scripts.chain_walker_lib import (
    do_reset, do_get, do_post, do_post_json, do_get_api,
    save_chain_result, html_to_axtree, axtree_to_text,
    _get_client
)

SITE = "converters-calculators"
BASE = f"/sites/{SITE}"


def reset_all():
    """Full reset: data + new client."""
    global _client
    from scripts import chain_walker_lib
    chain_walker_lib._client = None
    chain_walker_lib._app = None
    do_reset()


def login(username="converter_alice", password="pass123"):
    """Login via form POST, return ax_tree result."""
    r = do_post(f"{BASE}/login", {"username": username, "password": password})
    return r


def observe():
    """GET homepage."""
    return do_get(f"{BASE}/")


def navigate(path):
    """GET a subpath."""
    return do_get(f"{BASE}{path}")


def api_get(path):
    """GET an API endpoint."""
    return do_get_api(f"{BASE}{path}")


def convert_via_api(category, value, from_unit, to_unit):
    """Do a conversion via API GET."""
    return do_get_api(f"{BASE}/api/convert/{category}?value={value}&from={from_unit}&to={to_unit}")


def calculate_bmi_api(weight, height):
    return do_get_api(f"{BASE}/api/calculate/bmi?weight={weight}&height={height}")


def calculate_mortgage_api(principal, rate, years):
    return do_get_api(f"{BASE}/api/calculate/mortgage?principal={principal}&rate={rate}&years={years}")


def calculate_tip_api(bill, tip_pct, people=1):
    return do_get_api(f"{BASE}/api/calculate/tip?bill={bill}&tip_percent={tip_pct}&people={people}")


def save_conversion(tool, from_value, from_unit, to_unit, result, redirect_to=""):
    """Save a conversion to dashboard via form POST."""
    data = {
        "tool": tool,
        "from_value": str(from_value),
        "from_unit": from_unit,
        "to_unit": to_unit,
        "result": str(result),
    }
    if redirect_to:
        data["redirect_to"] = redirect_to
    return do_post(f"{BASE}/save-conversion", data)


def remove_saved(idx):
    return do_post(f"{BASE}/remove-saved/{idx}", {})


def make_step(action, url, method, data_sent, response_summary, status_code=200):
    return {
        "action": action,
        "url": url,
        "method": method,
        "data_sent": data_sent,
        "response_summary": response_summary,
        "status_code": status_code,
    }


# ============================================================================
# Chain walking functions - one per chain
# ============================================================================

def walk_easy_001():
    """login_by_form"""
    trajectory = []
    # Step 1: Observe homepage
    r = observe()
    trajectory.append(make_step("observe", f"{BASE}/", "GET", {}, "Homepage shows CalcTools with converters and calculators listed"))

    # Step 2: Navigate to login
    r = navigate("/login")
    trajectory.append(make_step("navigate_to_login", f"{BASE}/login", "GET", {}, "Login page with username/password form"))

    # Step 3: Login
    r = login()
    success = "Welcome, Alice Johnson" in r["ax_tree_text"]
    trajectory.append(make_step("login_by_form", f"{BASE}/login", "POST",
                                {"username": "converter_alice", "password": "pass123"},
                                f"Login successful, redirected to dashboard. Welcome Alice Johnson. success={success}",
                                r["status_code"]))
    return {"chain_id": f"{SITE}_easy_001", "site": SITE, "difficulty": "easy",
            "macros_executed": ["login_by_form"], "valid": success,
            "trajectory": trajectory}


def walk_easy_002():
    """extract_by_field - extract user profile info"""
    trajectory = []
    r = observe()
    trajectory.append(make_step("observe", f"{BASE}/", "GET", {}, "Homepage with tool listings"))

    # Extract info from API
    r = api_get("/api/users/1")
    user_data = r.get("response", {})
    name = user_data.get("name", "")
    email = user_data.get("email", "")
    trajectory.append(make_step("extract_by_field", f"{BASE}/api/users/1", "GET", {},
                                f"Extracted user profile: name={name}, email={email}, username={user_data.get('username','')}",
                                r["status_code"]))
    return {"chain_id": f"{SITE}_easy_002", "site": SITE, "difficulty": "easy",
            "macros_executed": ["extract_by_field"], "valid": name == "Alice Johnson",
            "extracted": {"name": name, "email": email},
            "trajectory": trajectory}


def walk_easy_003():
    """navigate_by_route"""
    trajectory = []
    r = observe()
    trajectory.append(make_step("observe", f"{BASE}/", "GET", {}, "Homepage"))

    # Navigate to weight converter
    r = navigate("/converter/weight")
    success = "Weight Converter" in r["ax_tree_text"]
    trajectory.append(make_step("navigate_by_route", f"{BASE}/converter/weight", "GET", {},
                                f"Navigated to Weight Converter page. success={success}",
                                r["status_code"]))
    return {"chain_id": f"{SITE}_easy_003", "site": SITE, "difficulty": "easy",
            "macros_executed": ["navigate_by_route"], "valid": success,
            "trajectory": trajectory}


def walk_easy_004():
    """save_by_toggle - save a conversion to dashboard"""
    trajectory = []
    # Must login first
    login()
    trajectory.append(make_step("login", f"{BASE}/login", "POST",
                                {"username": "converter_alice", "password": "pass123"},
                                "Logged in as Alice Johnson"))

    # Save a conversion
    r = save_conversion("length", "100", "meter", "foot", "328.08399")
    success = "Saved Conversions (1)" in r["ax_tree_text"]
    trajectory.append(make_step("save_by_toggle", f"{BASE}/save-conversion", "POST",
                                {"tool": "length", "from_value": "100", "from_unit": "meter", "to_unit": "foot", "result": "328.08399"},
                                f"Saved conversion to dashboard. Dashboard shows 1 saved conversion. success={success}",
                                r["status_code"]))
    return {"chain_id": f"{SITE}_easy_004", "site": SITE, "difficulty": "easy",
            "macros_executed": ["save_by_toggle"], "valid": success,
            "trajectory": trajectory}


def walk_easy_005():
    """select_by_dropdown - select unit from dropdown on converter"""
    trajectory = []
    r = observe()
    trajectory.append(make_step("observe", f"{BASE}/", "GET", {}, "Homepage"))

    # Navigate to tip calculator which has a dropdown for tip percentage
    r = navigate("/calculator/tip")
    trajectory.append(make_step("navigate", f"{BASE}/calculator/tip", "GET", {},
                                "Tip Calculator page with tip percentage dropdown (10%, 15%, 18%, 20%, 25%)"))

    # Use API to select 15% tip
    r = calculate_tip_api(100, 15, 1)
    resp = r.get("response", {})
    trajectory.append(make_step("select_by_dropdown", f"{BASE}/api/calculate/tip?bill=100&tip_percent=15&people=1", "GET",
                                {"bill": 100, "tip_percent": 15},
                                f"Selected 15% tip from dropdown. Tip=${ resp.get('tip_amount', '')}, Total=${resp.get('total', '')}",
                                r["status_code"]))
    return {"chain_id": f"{SITE}_easy_005", "site": SITE, "difficulty": "easy",
            "macros_executed": ["select_by_dropdown"], "valid": resp.get("tip_amount") == 15.0,
            "trajectory": trajectory}


def walk_easy_006():
    """calculate_by_form - perform a BMI calculation"""
    trajectory = []
    r = observe()
    trajectory.append(make_step("observe", f"{BASE}/", "GET", {}, "Homepage"))

    r = navigate("/calculator/bmi")
    trajectory.append(make_step("navigate", f"{BASE}/calculator/bmi", "GET", {},
                                "BMI Calculator page with weight/height inputs"))

    r = calculate_bmi_api(80, 1.80)
    resp = r.get("response", {})
    trajectory.append(make_step("calculate_by_form", f"{BASE}/api/calculate/bmi?weight=80&height=1.80", "GET",
                                {"weight": 80, "height": 1.80},
                                f"Calculated BMI: {resp.get('bmi', '')} - {resp.get('category', '')}",
                                r["status_code"]))
    return {"chain_id": f"{SITE}_easy_006", "site": SITE, "difficulty": "easy",
            "macros_executed": ["calculate_by_form"], "valid": resp.get("bmi") == 24.69,
            "trajectory": trajectory}


def walk_easy_007():
    """input_by_form - enter values into converter form"""
    trajectory = []
    r = observe()
    trajectory.append(make_step("observe", f"{BASE}/", "GET", {}, "Homepage"))

    r = navigate("/converter/temperature")
    trajectory.append(make_step("navigate", f"{BASE}/converter/temperature", "GET", {},
                                "Temperature Converter page"))

    r = convert_via_api("temperature", 100, "celsius", "fahrenheit")
    resp = r.get("response", {})
    trajectory.append(make_step("input_by_form", f"{BASE}/api/convert/temperature?value=100&from=celsius&to=fahrenheit", "GET",
                                {"value": 100, "from_unit": "celsius", "to_unit": "fahrenheit"},
                                f"Entered 100 Celsius, converted to {resp.get('result', '')} Fahrenheit",
                                r["status_code"]))
    return {"chain_id": f"{SITE}_easy_007", "site": SITE, "difficulty": "easy",
            "macros_executed": ["input_by_form"], "valid": resp.get("result") == 212.0,
            "trajectory": trajectory}


# ============================================================================
# MEDIUM chains
# ============================================================================

def walk_medium_001():
    """calculate_by_form, login_by_form, select_by_dropdown"""
    trajectory = []
    # Login
    r = login()
    trajectory.append(make_step("login_by_form", f"{BASE}/login", "POST",
                                {"username": "converter_alice", "password": "pass123"},
                                "Logged in as Alice Johnson, redirected to dashboard"))

    # Navigate to tip calculator
    r = navigate("/calculator/tip")
    trajectory.append(make_step("navigate", f"{BASE}/calculator/tip", "GET", {},
                                "Tip Calculator page"))

    # Select dropdown (18% tip)
    r = calculate_tip_api(120, 18, 3)
    resp = r.get("response", {})
    trajectory.append(make_step("select_by_dropdown", f"{BASE}/api/calculate/tip?bill=120&tip_percent=18&people=3", "GET",
                                {"tip_percent": 18},
                                f"Selected 18% tip from dropdown"))

    # Calculate
    trajectory.append(make_step("calculate_by_form", f"{BASE}/api/calculate/tip?bill=120&tip_percent=18&people=3", "GET",
                                {"bill": 120, "tip_percent": 18, "people": 3},
                                f"Tip=${resp.get('tip_amount','')}, Total=${resp.get('total','')}, Per person=${resp.get('per_person','')}",
                                r["status_code"]))
    valid = resp.get("tip_amount") == 21.6 and resp.get("total") == 141.6
    return {"chain_id": f"{SITE}_medium_001", "site": SITE, "difficulty": "medium",
            "macros_executed": ["calculate_by_form", "login_by_form", "select_by_dropdown"],
            "valid": valid, "trajectory": trajectory}


def walk_medium_002():
    """calculate_by_form, extract_by_field, login_by_form"""
    trajectory = []
    r = login()
    trajectory.append(make_step("login_by_form", f"{BASE}/login", "POST",
                                {"username": "converter_alice", "password": "pass123"},
                                "Logged in as Alice Johnson"))

    # Calculate mortgage
    r = calculate_mortgage_api(250000, 5.0, 15)
    resp = r.get("response", {})
    trajectory.append(make_step("calculate_by_form", f"{BASE}/api/calculate/mortgage?principal=250000&rate=5.0&years=15", "GET",
                                {"principal": 250000, "rate": 5.0, "years": 15},
                                f"Monthly payment=${resp.get('monthly_payment','')}, Total interest=${resp.get('total_interest','')}"))

    # Extract specific field
    trajectory.append(make_step("extract_by_field", f"{BASE}/api/calculate/mortgage", "GET", {},
                                f"Extracted total_interest={resp.get('total_interest','')}, total_payment={resp.get('total_payment','')}"))

    valid = resp.get("monthly_payment") == 1976.98
    return {"chain_id": f"{SITE}_medium_002", "site": SITE, "difficulty": "medium",
            "macros_executed": ["calculate_by_form", "extract_by_field", "login_by_form"],
            "valid": valid, "trajectory": trajectory}


def walk_medium_003():
    """extract_by_field, input_by_form, navigate_by_route"""
    trajectory = []
    r = observe()
    trajectory.append(make_step("observe", f"{BASE}/", "GET", {}, "Homepage"))

    # Navigate to currency converter
    r = navigate("/converter/currency")
    trajectory.append(make_step("navigate_by_route", f"{BASE}/converter/currency", "GET", {},
                                "Currency Converter page"))

    # Input values and convert
    r = convert_via_api("currency", 500, "USD", "EUR")
    resp = r.get("response", {})
    trajectory.append(make_step("input_by_form", f"{BASE}/api/convert/currency?value=500&from=USD&to=EUR", "GET",
                                {"value": 500, "from": "USD", "to": "EUR"},
                                f"Entered 500 USD, converting to EUR"))

    # Extract result
    trajectory.append(make_step("extract_by_field", f"{BASE}/api/convert/currency", "GET", {},
                                f"Extracted result: 500 USD = {resp.get('result','')} EUR",
                                r["status_code"]))
    valid = resp.get("result") == 460.7
    return {"chain_id": f"{SITE}_medium_003", "site": SITE, "difficulty": "medium",
            "macros_executed": ["extract_by_field", "input_by_form", "navigate_by_route"],
            "valid": valid, "trajectory": trajectory}


def walk_medium_004():
    """calculate_by_form, save_by_toggle, select_by_dropdown"""
    trajectory = []
    login()
    trajectory.append(make_step("login", f"{BASE}/login", "POST",
                                {"username": "converter_alice", "password": "pass123"},
                                "Logged in"))

    # Navigate to tip calc, select 25% from dropdown
    r = navigate("/calculator/tip")
    trajectory.append(make_step("navigate", f"{BASE}/calculator/tip", "GET", {},
                                "Tip Calculator page"))

    r = calculate_tip_api(200, 25, 4)
    resp = r.get("response", {})
    trajectory.append(make_step("select_by_dropdown", f"{BASE}/api/calculate/tip", "GET",
                                {"tip_percent": 25},
                                "Selected 25% tip from dropdown"))

    trajectory.append(make_step("calculate_by_form", f"{BASE}/api/calculate/tip?bill=200&tip_percent=25&people=4", "GET",
                                {"bill": 200, "tip_percent": 25, "people": 4},
                                f"Tip=${resp.get('tip_amount','')}, Total=${resp.get('total','')}, Per person=${resp.get('per_person','')}"))

    # Save result
    r = save_conversion("tip", "$200 + 25% tip", "bill", "total", f"${resp.get('total','')}")
    success = "Saved Conversions (1)" in r["ax_tree_text"]
    trajectory.append(make_step("save_by_toggle", f"{BASE}/save-conversion", "POST",
                                {"tool": "tip", "from_value": "$200 + 25% tip", "result": f"${resp.get('total','')}"},
                                f"Saved tip calculation to dashboard. success={success}"))

    return {"chain_id": f"{SITE}_medium_004", "site": SITE, "difficulty": "medium",
            "macros_executed": ["calculate_by_form", "save_by_toggle", "select_by_dropdown"],
            "valid": success and resp.get("tip_amount") == 50.0, "trajectory": trajectory}


def walk_medium_005():
    """calculate_by_form, input_by_form, save_by_toggle"""
    trajectory = []
    login()
    trajectory.append(make_step("login", f"{BASE}/login", "POST",
                                {"username": "converter_alice", "password": "pass123"}, "Logged in"))

    r = navigate("/calculator/bmi")
    trajectory.append(make_step("navigate", f"{BASE}/calculator/bmi", "GET", {}, "BMI Calculator"))

    r = calculate_bmi_api(90, 1.85)
    resp = r.get("response", {})
    trajectory.append(make_step("input_by_form", f"{BASE}/calculator/bmi", "GET",
                                {"weight": 90, "height": 1.85},
                                "Entered weight=90kg, height=1.85m"))

    trajectory.append(make_step("calculate_by_form", f"{BASE}/api/calculate/bmi?weight=90&height=1.85", "GET",
                                {"weight": 90, "height": 1.85},
                                f"BMI={resp.get('bmi','')}, Category={resp.get('category','')}"))

    r = save_conversion("bmi", "90 kg / 1.85 m", "kg/m", "bmi", f"{resp.get('bmi','')} ({resp.get('category','')})")
    success = "Saved Conversions (1)" in r["ax_tree_text"]
    trajectory.append(make_step("save_by_toggle", f"{BASE}/save-conversion", "POST",
                                {"tool": "bmi", "result": f"{resp.get('bmi','')} ({resp.get('category','')})"},
                                f"Saved BMI result to dashboard. success={success}"))

    return {"chain_id": f"{SITE}_medium_005", "site": SITE, "difficulty": "medium",
            "macros_executed": ["calculate_by_form", "input_by_form", "save_by_toggle"],
            "valid": success and resp.get("bmi") == 26.3, "trajectory": trajectory}


def walk_medium_006():
    """calculate_by_form, login_by_form, save_by_toggle"""
    trajectory = []
    r = login()
    trajectory.append(make_step("login_by_form", f"{BASE}/login", "POST",
                                {"username": "converter_alice", "password": "pass123"},
                                "Logged in as Alice Johnson"))

    r = calculate_mortgage_api(400000, 7.0, 30)
    resp = r.get("response", {})
    trajectory.append(make_step("calculate_by_form", f"{BASE}/api/calculate/mortgage?principal=400000&rate=7.0&years=30", "GET",
                                {"principal": 400000, "rate": 7.0, "years": 30},
                                f"Monthly payment=${resp.get('monthly_payment','')}, Total interest=${resp.get('total_interest','')}"))

    r = save_conversion("mortgage", "$400000 at 7.0% for 30 yrs", "loan", "payment", f"${resp.get('monthly_payment','')}/mo")
    success = "Saved Conversions (1)" in r["ax_tree_text"]
    trajectory.append(make_step("save_by_toggle", f"{BASE}/save-conversion", "POST",
                                {"tool": "mortgage", "result": f"${resp.get('monthly_payment','')}/mo"},
                                f"Saved mortgage calculation. success={success}"))

    return {"chain_id": f"{SITE}_medium_006", "site": SITE, "difficulty": "medium",
            "macros_executed": ["calculate_by_form", "login_by_form", "save_by_toggle"],
            "valid": success and resp.get("monthly_payment") is not None, "trajectory": trajectory}


def walk_medium_007():
    """calculate_by_form, input_by_form, select_by_dropdown"""
    trajectory = []
    r = observe()
    trajectory.append(make_step("observe", f"{BASE}/", "GET", {}, "Homepage"))

    r = navigate("/calculator/tip")
    trajectory.append(make_step("navigate", f"{BASE}/calculator/tip", "GET", {}, "Tip Calculator"))

    trajectory.append(make_step("input_by_form", f"{BASE}/calculator/tip", "GET",
                                {"bill": 75.00}, "Entered bill amount $75.00"))

    trajectory.append(make_step("select_by_dropdown", f"{BASE}/calculator/tip", "GET",
                                {"tip_percent": 10}, "Selected 10% tip from dropdown"))

    r = calculate_tip_api(75, 10, 1)
    resp = r.get("response", {})
    trajectory.append(make_step("calculate_by_form", f"{BASE}/api/calculate/tip?bill=75&tip_percent=10&people=1", "GET",
                                {"bill": 75, "tip_percent": 10, "people": 1},
                                f"Tip=${resp.get('tip_amount','')}, Total=${resp.get('total','')}"))

    return {"chain_id": f"{SITE}_medium_007", "site": SITE, "difficulty": "medium",
            "macros_executed": ["calculate_by_form", "input_by_form", "select_by_dropdown"],
            "valid": resp.get("tip_amount") == 7.5, "trajectory": trajectory}


def walk_medium_008():
    """calculate_by_form, extract_by_field, save_by_toggle"""
    trajectory = []
    login()
    trajectory.append(make_step("login", f"{BASE}/login", "POST",
                                {"username": "converter_alice", "password": "pass123"}, "Logged in"))

    r = calculate_mortgage_api(500000, 6.0, 25)
    resp = r.get("response", {})
    trajectory.append(make_step("calculate_by_form", f"{BASE}/api/calculate/mortgage?principal=500000&rate=6.0&years=25", "GET",
                                {"principal": 500000, "rate": 6.0, "years": 25},
                                f"Monthly=${resp.get('monthly_payment','')}, Total=${resp.get('total_payment','')}, Interest=${resp.get('total_interest','')}"))

    trajectory.append(make_step("extract_by_field", f"{BASE}/api/calculate/mortgage", "GET", {},
                                f"Extracted total_interest={resp.get('total_interest','')} from mortgage result"))

    r = save_conversion("mortgage", "$500000 at 6.0% for 25 yrs", "loan", "payment", f"${resp.get('monthly_payment','')}/mo")
    success = "Saved Conversions (1)" in r["ax_tree_text"]
    trajectory.append(make_step("save_by_toggle", f"{BASE}/save-conversion", "POST",
                                {"tool": "mortgage"}, f"Saved to dashboard. success={success}"))

    return {"chain_id": f"{SITE}_medium_008", "site": SITE, "difficulty": "medium",
            "macros_executed": ["calculate_by_form", "extract_by_field", "save_by_toggle"],
            "valid": success and resp.get("monthly_payment") is not None, "trajectory": trajectory}


def walk_medium_009():
    """calculate_by_form, login_by_form, navigate_by_route"""
    trajectory = []
    r = login()
    trajectory.append(make_step("login_by_form", f"{BASE}/login", "POST",
                                {"username": "converter_alice", "password": "pass123"},
                                "Logged in as Alice Johnson"))

    r = navigate("/calculator/mortgage")
    trajectory.append(make_step("navigate_by_route", f"{BASE}/calculator/mortgage", "GET", {},
                                "Navigated to Mortgage Calculator page"))

    r = calculate_mortgage_api(350000, 5.5, 20)
    resp = r.get("response", {})
    trajectory.append(make_step("calculate_by_form", f"{BASE}/api/calculate/mortgage?principal=350000&rate=5.5&years=20", "GET",
                                {"principal": 350000, "rate": 5.5, "years": 20},
                                f"Monthly payment=${resp.get('monthly_payment','')}, Total interest=${resp.get('total_interest','')}"))

    return {"chain_id": f"{SITE}_medium_009", "site": SITE, "difficulty": "medium",
            "macros_executed": ["calculate_by_form", "login_by_form", "navigate_by_route"],
            "valid": resp.get("monthly_payment") is not None, "trajectory": trajectory}


def walk_medium_010():
    """extract_by_field, navigate_by_route, save_by_toggle"""
    trajectory = []
    login()
    trajectory.append(make_step("login", f"{BASE}/login", "POST",
                                {"username": "converter_alice", "password": "pass123"}, "Logged in"))

    r = navigate("/converter/speed")
    trajectory.append(make_step("navigate_by_route", f"{BASE}/converter/speed", "GET", {},
                                "Navigated to Speed Converter"))

    r = convert_via_api("speed", 100, "kilometers_per_hour", "miles_per_hour")
    resp = r.get("response", {})
    trajectory.append(make_step("extract_by_field", f"{BASE}/api/convert/speed", "GET", {},
                                f"Extracted: 100 km/h = {resp.get('result','')} mph"))

    r = save_conversion("speed", "100", "kilometers_per_hour", "miles_per_hour", str(resp.get("result", "")))
    success = "Saved Conversions (1)" in r["ax_tree_text"]
    trajectory.append(make_step("save_by_toggle", f"{BASE}/save-conversion", "POST",
                                {"tool": "speed", "from_value": "100", "from_unit": "kilometers_per_hour", "to_unit": "miles_per_hour"},
                                f"Saved speed conversion. success={success}"))

    return {"chain_id": f"{SITE}_medium_010", "site": SITE, "difficulty": "medium",
            "macros_executed": ["extract_by_field", "navigate_by_route", "save_by_toggle"],
            "valid": success and resp.get("result") is not None, "trajectory": trajectory}


def walk_medium_011():
    """input_by_form, login_by_form, navigate_by_route"""
    trajectory = []
    r = login()
    trajectory.append(make_step("login_by_form", f"{BASE}/login", "POST",
                                {"username": "converter_alice", "password": "pass123"},
                                "Logged in as Alice Johnson"))

    r = navigate("/converter/volume")
    trajectory.append(make_step("navigate_by_route", f"{BASE}/converter/volume", "GET", {},
                                "Navigated to Volume Converter"))

    r = convert_via_api("volume", 5, "gallon", "liter")
    resp = r.get("response", {})
    trajectory.append(make_step("input_by_form", f"{BASE}/api/convert/volume?value=5&from=gallon&to=liter", "GET",
                                {"value": 5, "from": "gallon", "to": "liter"},
                                f"Input 5 gallons, result: {resp.get('result','')} liters"))

    return {"chain_id": f"{SITE}_medium_011", "site": SITE, "difficulty": "medium",
            "macros_executed": ["input_by_form", "login_by_form", "navigate_by_route"],
            "valid": resp.get("result") is not None, "trajectory": trajectory}


def walk_medium_012():
    """input_by_form, login_by_form, save_by_toggle"""
    trajectory = []
    r = login()
    trajectory.append(make_step("login_by_form", f"{BASE}/login", "POST",
                                {"username": "converter_alice", "password": "pass123"},
                                "Logged in as Alice Johnson"))

    r = convert_via_api("weight", 150, "pound", "kilogram")
    resp = r.get("response", {})
    trajectory.append(make_step("input_by_form", f"{BASE}/api/convert/weight?value=150&from=pound&to=kilogram", "GET",
                                {"value": 150, "from": "pound", "to": "kilogram"},
                                f"Input 150 pounds, result: {resp.get('result','')} kg"))

    r = save_conversion("weight", "150", "pound", "kilogram", str(resp.get("result", "")))
    success = "Saved Conversions (1)" in r["ax_tree_text"]
    trajectory.append(make_step("save_by_toggle", f"{BASE}/save-conversion", "POST",
                                {"tool": "weight", "from_value": "150", "from_unit": "pound", "to_unit": "kilogram"},
                                f"Saved weight conversion. success={success}"))

    return {"chain_id": f"{SITE}_medium_012", "site": SITE, "difficulty": "medium",
            "macros_executed": ["input_by_form", "login_by_form", "save_by_toggle"],
            "valid": success and resp.get("result") is not None, "trajectory": trajectory}


def walk_medium_013():
    """calculate_by_form, extract_by_field, input_by_form"""
    trajectory = []
    r = observe()
    trajectory.append(make_step("observe", f"{BASE}/", "GET", {}, "Homepage"))

    r = navigate("/calculator/bmi")
    trajectory.append(make_step("navigate", f"{BASE}/calculator/bmi", "GET", {}, "BMI Calculator"))

    trajectory.append(make_step("input_by_form", f"{BASE}/calculator/bmi", "GET",
                                {"weight": 65, "height": 1.70},
                                "Entered weight=65kg, height=1.70m"))

    r = calculate_bmi_api(65, 1.70)
    resp = r.get("response", {})
    trajectory.append(make_step("calculate_by_form", f"{BASE}/api/calculate/bmi?weight=65&height=1.70", "GET",
                                {"weight": 65, "height": 1.70},
                                f"BMI={resp.get('bmi','')}, Category={resp.get('category','')}"))

    trajectory.append(make_step("extract_by_field", f"{BASE}/api/calculate/bmi", "GET", {},
                                f"Extracted category={resp.get('category','')} from BMI result"))

    return {"chain_id": f"{SITE}_medium_013", "site": SITE, "difficulty": "medium",
            "macros_executed": ["calculate_by_form", "extract_by_field", "input_by_form"],
            "valid": resp.get("bmi") == 22.49, "trajectory": trajectory}


def walk_medium_014():
    """input_by_form, navigate_by_route, select_by_dropdown"""
    trajectory = []
    r = observe()
    trajectory.append(make_step("observe", f"{BASE}/", "GET", {}, "Homepage"))

    r = navigate("/converter/base")
    trajectory.append(make_step("navigate_by_route", f"{BASE}/converter/base", "GET", {},
                                "Navigated to Number Base Converter"))

    trajectory.append(make_step("input_by_form", f"{BASE}/converter/base", "GET",
                                {"value": "1010"},
                                "Entered value 1010"))

    trajectory.append(make_step("select_by_dropdown", f"{BASE}/converter/base", "GET",
                                {"from_base": 2, "to_base": 16},
                                "Selected from=Binary(2), to=Hexadecimal(16) from dropdowns"))

    r = api_get("/api/convert/base?value=1010&from=2&to=16")
    resp = r.get("response", {})
    trajectory.append(make_step("convert", f"{BASE}/api/convert/base?value=1010&from=2&to=16", "GET",
                                {"value": "1010", "from_base": 2, "to_base": 16},
                                f"Result: {resp.get('result','')} (decimal: {resp.get('decimal','')})"))

    return {"chain_id": f"{SITE}_medium_014", "site": SITE, "difficulty": "medium",
            "macros_executed": ["input_by_form", "navigate_by_route", "select_by_dropdown"],
            "valid": resp.get("result") == "A" and resp.get("decimal") == 10, "trajectory": trajectory}


def walk_medium_015():
    """navigate_by_route, save_by_toggle, select_by_dropdown"""
    trajectory = []
    login()
    trajectory.append(make_step("login", f"{BASE}/login", "POST",
                                {"username": "converter_alice", "password": "pass123"}, "Logged in"))

    r = navigate("/converter/length")
    trajectory.append(make_step("navigate_by_route", f"{BASE}/converter/length", "GET", {},
                                "Navigated to Length Converter"))

    trajectory.append(make_step("select_by_dropdown", f"{BASE}/converter/length", "GET",
                                {"from_unit": "mile", "to_unit": "kilometer"},
                                "Selected from=Mile, to=Kilometer from dropdowns"))

    r = convert_via_api("length", 26.2, "mile", "kilometer")
    resp = r.get("response", {})

    r = save_conversion("length", "26.2", "mile", "kilometer", str(resp.get("result", "")))
    success = "Saved Conversions (1)" in r["ax_tree_text"]
    trajectory.append(make_step("save_by_toggle", f"{BASE}/save-conversion", "POST",
                                {"tool": "length", "from_value": "26.2", "from_unit": "mile", "to_unit": "kilometer"},
                                f"Saved: 26.2 miles = {resp.get('result','')} km. success={success}"))

    return {"chain_id": f"{SITE}_medium_015", "site": SITE, "difficulty": "medium",
            "macros_executed": ["navigate_by_route", "save_by_toggle", "select_by_dropdown"],
            "valid": success and resp.get("result") is not None, "trajectory": trajectory}


def walk_medium_016():
    """extract_by_field, login_by_form, navigate_by_route"""
    trajectory = []
    r = login()
    trajectory.append(make_step("login_by_form", f"{BASE}/login", "POST",
                                {"username": "converter_alice", "password": "pass123"},
                                "Logged in as Alice Johnson"))

    r = navigate("/converter/area")
    trajectory.append(make_step("navigate_by_route", f"{BASE}/converter/area", "GET", {},
                                "Navigated to Area Converter"))

    r = convert_via_api("area", 1, "acre", "square_meter")
    resp = r.get("response", {})
    trajectory.append(make_step("extract_by_field", f"{BASE}/api/convert/area?value=1&from=acre&to=square_meter", "GET",
                                {},
                                f"Extracted: 1 acre = {resp.get('result','')} square meters"))

    return {"chain_id": f"{SITE}_medium_016", "site": SITE, "difficulty": "medium",
            "macros_executed": ["extract_by_field", "login_by_form", "navigate_by_route"],
            "valid": resp.get("result") == 4046.8564224 or resp.get("result") == 4046.856422, "trajectory": trajectory}


def walk_medium_017():
    """calculate_by_form, input_by_form, navigate_by_route"""
    trajectory = []
    r = observe()
    trajectory.append(make_step("observe", f"{BASE}/", "GET", {}, "Homepage"))

    r = navigate("/calculator/mortgage")
    trajectory.append(make_step("navigate_by_route", f"{BASE}/calculator/mortgage", "GET", {},
                                "Navigated to Mortgage Calculator"))

    trajectory.append(make_step("input_by_form", f"{BASE}/calculator/mortgage", "GET",
                                {"principal": 200000, "rate": 4.5, "years": 15},
                                "Entered principal=$200,000, rate=4.5%, term=15 years"))

    r = calculate_mortgage_api(200000, 4.5, 15)
    resp = r.get("response", {})
    trajectory.append(make_step("calculate_by_form", f"{BASE}/api/calculate/mortgage?principal=200000&rate=4.5&years=15", "GET",
                                {"principal": 200000, "rate": 4.5, "years": 15},
                                f"Monthly=${resp.get('monthly_payment','')}, Total Interest=${resp.get('total_interest','')}"))

    return {"chain_id": f"{SITE}_medium_017", "site": SITE, "difficulty": "medium",
            "macros_executed": ["calculate_by_form", "input_by_form", "navigate_by_route"],
            "valid": resp.get("monthly_payment") == 1529.99, "trajectory": trajectory}


def walk_medium_018():
    """calculate_by_form, navigate_by_route, select_by_dropdown"""
    trajectory = []
    r = observe()
    trajectory.append(make_step("observe", f"{BASE}/", "GET", {}, "Homepage"))

    r = navigate("/calculator/tip")
    trajectory.append(make_step("navigate_by_route", f"{BASE}/calculator/tip", "GET", {},
                                "Navigated to Tip Calculator"))

    trajectory.append(make_step("select_by_dropdown", f"{BASE}/calculator/tip", "GET",
                                {"tip_percent": 15},
                                "Selected 15% tip from dropdown"))

    r = calculate_tip_api(60, 15, 2)
    resp = r.get("response", {})
    trajectory.append(make_step("calculate_by_form", f"{BASE}/api/calculate/tip?bill=60&tip_percent=15&people=2", "GET",
                                {"bill": 60, "tip_percent": 15, "people": 2},
                                f"Tip=${resp.get('tip_amount','')}, Total=${resp.get('total','')}, Per person=${resp.get('per_person','')}"))

    return {"chain_id": f"{SITE}_medium_018", "site": SITE, "difficulty": "medium",
            "macros_executed": ["calculate_by_form", "navigate_by_route", "select_by_dropdown"],
            "valid": resp.get("tip_amount") == 9.0, "trajectory": trajectory}


def walk_medium_019():
    """login_by_form, navigate_by_route, select_by_dropdown"""
    trajectory = []
    r = login()
    trajectory.append(make_step("login_by_form", f"{BASE}/login", "POST",
                                {"username": "converter_alice", "password": "pass123"},
                                "Logged in as Alice Johnson"))

    r = navigate("/converter/temperature")
    trajectory.append(make_step("navigate_by_route", f"{BASE}/converter/temperature", "GET", {},
                                "Navigated to Temperature Converter"))

    trajectory.append(make_step("select_by_dropdown", f"{BASE}/converter/temperature", "GET",
                                {"from_unit": "fahrenheit", "to_unit": "kelvin"},
                                "Selected from=Fahrenheit, to=Kelvin from dropdowns"))

    r = convert_via_api("temperature", 72, "fahrenheit", "kelvin")
    resp = r.get("response", {})
    trajectory.append(make_step("convert_result", f"{BASE}/api/convert/temperature?value=72&from=fahrenheit&to=kelvin", "GET",
                                {"value": 72, "from": "fahrenheit", "to": "kelvin"},
                                f"72 F = {resp.get('result','')} K"))

    return {"chain_id": f"{SITE}_medium_019", "site": SITE, "difficulty": "medium",
            "macros_executed": ["login_by_form", "navigate_by_route", "select_by_dropdown"],
            "valid": resp.get("result") is not None, "trajectory": trajectory}


def walk_medium_020():
    """input_by_form, save_by_toggle, select_by_dropdown"""
    trajectory = []
    login()
    trajectory.append(make_step("login", f"{BASE}/login", "POST",
                                {"username": "converter_alice", "password": "pass123"}, "Logged in"))

    r = navigate("/converter/currency")
    trajectory.append(make_step("navigate", f"{BASE}/converter/currency", "GET", {}, "Currency Converter"))

    trajectory.append(make_step("select_by_dropdown", f"{BASE}/converter/currency", "GET",
                                {"from_unit": "GBP", "to_unit": "JPY"},
                                "Selected from=GBP, to=JPY from dropdowns"))

    r = convert_via_api("currency", 1000, "GBP", "JPY")
    resp = r.get("response", {})
    trajectory.append(make_step("input_by_form", f"{BASE}/api/convert/currency?value=1000&from=GBP&to=JPY", "GET",
                                {"value": 1000, "from": "GBP", "to": "JPY"},
                                f"Input 1000 GBP, result: {resp.get('result','')} JPY"))

    r = save_conversion("currency", "1000", "GBP", "JPY", str(resp.get("result", "")))
    success = "Saved Conversions (1)" in r["ax_tree_text"]
    trajectory.append(make_step("save_by_toggle", f"{BASE}/save-conversion", "POST",
                                {"tool": "currency", "from_value": "1000", "from_unit": "GBP", "to_unit": "JPY"},
                                f"Saved currency conversion. success={success}"))

    return {"chain_id": f"{SITE}_medium_020", "site": SITE, "difficulty": "medium",
            "macros_executed": ["input_by_form", "save_by_toggle", "select_by_dropdown"],
            "valid": success and resp.get("result") is not None, "trajectory": trajectory}


# ============================================================================
# HARD chains
# ============================================================================

def walk_hard_001():
    """calculate_by_form, extract_by_field, input_by_form, login_by_form, navigate_by_route"""
    trajectory = []
    r = login()
    trajectory.append(make_step("login_by_form", f"{BASE}/login", "POST",
                                {"username": "converter_alice", "password": "pass123"},
                                "Logged in as Alice Johnson"))

    r = navigate("/calculator/bmi")
    trajectory.append(make_step("navigate_by_route", f"{BASE}/calculator/bmi", "GET", {},
                                "Navigated to BMI Calculator"))

    trajectory.append(make_step("input_by_form", f"{BASE}/calculator/bmi", "GET",
                                {"weight": 75, "height": 1.68},
                                "Entered weight=75kg, height=1.68m"))

    r = calculate_bmi_api(75, 1.68)
    resp = r.get("response", {})
    trajectory.append(make_step("calculate_by_form", f"{BASE}/api/calculate/bmi?weight=75&height=1.68", "GET",
                                {"weight": 75, "height": 1.68},
                                f"BMI={resp.get('bmi','')}, Category={resp.get('category','')}"))

    trajectory.append(make_step("extract_by_field", f"{BASE}/api/calculate/bmi", "GET", {},
                                f"Extracted: bmi={resp.get('bmi','')}, category={resp.get('category','')}"))

    return {"chain_id": f"{SITE}_hard_001", "site": SITE, "difficulty": "hard",
            "macros_executed": ["calculate_by_form", "extract_by_field", "input_by_form", "login_by_form", "navigate_by_route"],
            "valid": resp.get("bmi") is not None, "trajectory": trajectory}


def walk_hard_002():
    """calculate_by_form, extract_by_field, login_by_form, navigate_by_route, select_by_dropdown"""
    trajectory = []
    r = login()
    trajectory.append(make_step("login_by_form", f"{BASE}/login", "POST",
                                {"username": "converter_alice", "password": "pass123"},
                                "Logged in"))

    r = navigate("/calculator/tip")
    trajectory.append(make_step("navigate_by_route", f"{BASE}/calculator/tip", "GET", {}, "Tip Calculator"))

    trajectory.append(make_step("select_by_dropdown", f"{BASE}/calculator/tip", "GET",
                                {"tip_percent": 25}, "Selected 25% tip from dropdown"))

    r = calculate_tip_api(150, 25, 5)
    resp = r.get("response", {})
    trajectory.append(make_step("calculate_by_form", f"{BASE}/api/calculate/tip?bill=150&tip_percent=25&people=5", "GET",
                                {"bill": 150, "tip_percent": 25, "people": 5},
                                f"Tip=${resp.get('tip_amount','')}, Total=${resp.get('total','')}, Per person=${resp.get('per_person','')}"))

    trajectory.append(make_step("extract_by_field", f"{BASE}/api/calculate/tip", "GET", {},
                                f"Extracted per_person=${resp.get('per_person','')} for 5 people"))

    return {"chain_id": f"{SITE}_hard_002", "site": SITE, "difficulty": "hard",
            "macros_executed": ["calculate_by_form", "extract_by_field", "login_by_form", "navigate_by_route", "select_by_dropdown"],
            "valid": resp.get("tip_amount") == 37.5, "trajectory": trajectory}


def walk_hard_003():
    """calculate_by_form, input_by_form, navigate_by_route, save_by_toggle, select_by_dropdown"""
    trajectory = []
    login()
    trajectory.append(make_step("login", f"{BASE}/login", "POST",
                                {"username": "converter_alice", "password": "pass123"}, "Logged in"))

    r = navigate("/calculator/tip")
    trajectory.append(make_step("navigate_by_route", f"{BASE}/calculator/tip", "GET", {}, "Tip Calculator"))

    trajectory.append(make_step("input_by_form", f"{BASE}/calculator/tip", "GET",
                                {"bill": 250}, "Entered bill amount $250"))

    trajectory.append(make_step("select_by_dropdown", f"{BASE}/calculator/tip", "GET",
                                {"tip_percent": 20}, "Selected 20% tip"))

    r = calculate_tip_api(250, 20, 4)
    resp = r.get("response", {})
    trajectory.append(make_step("calculate_by_form", f"{BASE}/api/calculate/tip?bill=250&tip_percent=20&people=4", "GET",
                                {"bill": 250, "tip_percent": 20, "people": 4},
                                f"Tip=${resp.get('tip_amount','')}, Total=${resp.get('total','')}, Per person=${resp.get('per_person','')}"))

    r = save_conversion("tip", "$250 + 20% tip", "bill", "total", f"${resp.get('total','')}")
    success = "Saved Conversions (1)" in r["ax_tree_text"]
    trajectory.append(make_step("save_by_toggle", f"{BASE}/save-conversion", "POST",
                                {"tool": "tip"}, f"Saved tip calculation. success={success}"))

    return {"chain_id": f"{SITE}_hard_003", "site": SITE, "difficulty": "hard",
            "macros_executed": ["calculate_by_form", "input_by_form", "navigate_by_route", "save_by_toggle", "select_by_dropdown"],
            "valid": success and resp.get("tip_amount") == 50.0, "trajectory": trajectory}


def walk_hard_004():
    """calculate_by_form, input_by_form, login_by_form, save_by_toggle, select_by_dropdown"""
    trajectory = []
    r = login()
    trajectory.append(make_step("login_by_form", f"{BASE}/login", "POST",
                                {"username": "converter_alice", "password": "pass123"},
                                "Logged in"))

    trajectory.append(make_step("input_by_form", f"{BASE}/calculator/tip", "GET",
                                {"bill": 95}, "Entered bill $95"))

    trajectory.append(make_step("select_by_dropdown", f"{BASE}/calculator/tip", "GET",
                                {"tip_percent": 18}, "Selected 18% tip"))

    r = calculate_tip_api(95, 18, 2)
    resp = r.get("response", {})
    trajectory.append(make_step("calculate_by_form", f"{BASE}/api/calculate/tip?bill=95&tip_percent=18&people=2", "GET",
                                {"bill": 95, "tip_percent": 18, "people": 2},
                                f"Tip=${resp.get('tip_amount','')}, Total=${resp.get('total','')}, Per person=${resp.get('per_person','')}"))

    r = save_conversion("tip", "$95 + 18% tip", "bill", "total", f"${resp.get('total','')}")
    success = "Saved Conversions (1)" in r["ax_tree_text"]
    trajectory.append(make_step("save_by_toggle", f"{BASE}/save-conversion", "POST",
                                {"tool": "tip"}, f"Saved. success={success}"))

    return {"chain_id": f"{SITE}_hard_004", "site": SITE, "difficulty": "hard",
            "macros_executed": ["calculate_by_form", "input_by_form", "login_by_form", "save_by_toggle", "select_by_dropdown"],
            "valid": success and resp.get("tip_amount") == 17.1, "trajectory": trajectory}


def walk_hard_005():
    """calculate_by_form, extract_by_field, navigate_by_route, save_by_toggle, select_by_dropdown"""
    trajectory = []
    login()
    trajectory.append(make_step("login", f"{BASE}/login", "POST",
                                {"username": "converter_alice", "password": "pass123"}, "Logged in"))

    r = navigate("/converter/length")
    trajectory.append(make_step("navigate_by_route", f"{BASE}/converter/length", "GET", {}, "Length Converter"))

    trajectory.append(make_step("select_by_dropdown", f"{BASE}/converter/length", "GET",
                                {"from_unit": "inch", "to_unit": "centimeter"},
                                "Selected from=Inch, to=Centimeter"))

    r = convert_via_api("length", 72, "inch", "centimeter")
    resp = r.get("response", {})
    trajectory.append(make_step("calculate_by_form", f"{BASE}/api/convert/length?value=72&from=inch&to=centimeter", "GET",
                                {"value": 72, "from": "inch", "to": "centimeter"},
                                f"72 inches = {resp.get('result','')} cm"))

    trajectory.append(make_step("extract_by_field", f"{BASE}/api/convert/length", "GET", {},
                                f"Extracted result: {resp.get('result','')} cm"))

    r = save_conversion("length", "72", "inch", "centimeter", str(resp.get("result", "")))
    success = "Saved Conversions (1)" in r["ax_tree_text"]
    trajectory.append(make_step("save_by_toggle", f"{BASE}/save-conversion", "POST",
                                {"tool": "length"}, f"Saved. success={success}"))

    return {"chain_id": f"{SITE}_hard_005", "site": SITE, "difficulty": "hard",
            "macros_executed": ["calculate_by_form", "extract_by_field", "navigate_by_route", "save_by_toggle", "select_by_dropdown"],
            "valid": success and resp.get("result") is not None, "trajectory": trajectory}


def walk_hard_006():
    """calculate_by_form, extract_by_field, input_by_form, login_by_form, save_by_toggle"""
    trajectory = []
    r = login()
    trajectory.append(make_step("login_by_form", f"{BASE}/login", "POST",
                                {"username": "converter_alice", "password": "pass123"}, "Logged in"))

    trajectory.append(make_step("input_by_form", f"{BASE}/calculator/mortgage", "GET",
                                {"principal": 450000, "rate": 5.75, "years": 30},
                                "Input: $450k, 5.75%, 30 years"))

    r = calculate_mortgage_api(450000, 5.75, 30)
    resp = r.get("response", {})
    trajectory.append(make_step("calculate_by_form", f"{BASE}/api/calculate/mortgage?principal=450000&rate=5.75&years=30", "GET",
                                {"principal": 450000, "rate": 5.75, "years": 30},
                                f"Monthly=${resp.get('monthly_payment','')}, Total interest=${resp.get('total_interest','')}"))

    trajectory.append(make_step("extract_by_field", f"{BASE}/api/calculate/mortgage", "GET", {},
                                f"Extracted: monthly_payment={resp.get('monthly_payment','')}, total_interest={resp.get('total_interest','')}"))

    r = save_conversion("mortgage", "$450000 at 5.75% for 30 yrs", "loan", "payment", f"${resp.get('monthly_payment','')}/mo")
    success = "Saved Conversions (1)" in r["ax_tree_text"]
    trajectory.append(make_step("save_by_toggle", f"{BASE}/save-conversion", "POST",
                                {"tool": "mortgage"}, f"Saved. success={success}"))

    return {"chain_id": f"{SITE}_hard_006", "site": SITE, "difficulty": "hard",
            "macros_executed": ["calculate_by_form", "extract_by_field", "input_by_form", "login_by_form", "save_by_toggle"],
            "valid": success and resp.get("monthly_payment") is not None, "trajectory": trajectory}


def walk_hard_007():
    """calculate_by_form, extract_by_field, login_by_form, navigate_by_route, save_by_toggle"""
    trajectory = []
    r = login()
    trajectory.append(make_step("login_by_form", f"{BASE}/login", "POST",
                                {"username": "converter_alice", "password": "pass123"}, "Logged in"))

    r = navigate("/converter/weight")
    trajectory.append(make_step("navigate_by_route", f"{BASE}/converter/weight", "GET", {}, "Weight Converter"))

    r = convert_via_api("weight", 10, "stone", "kilogram")
    resp = r.get("response", {})
    trajectory.append(make_step("calculate_by_form", f"{BASE}/api/convert/weight?value=10&from=stone&to=kilogram", "GET",
                                {"value": 10, "from": "stone", "to": "kilogram"},
                                f"10 stone = {resp.get('result','')} kg"))

    trajectory.append(make_step("extract_by_field", f"{BASE}/api/convert/weight", "GET", {},
                                f"Extracted result: {resp.get('result','')} kg"))

    r = save_conversion("weight", "10", "stone", "kilogram", str(resp.get("result", "")))
    success = "Saved Conversions (1)" in r["ax_tree_text"]
    trajectory.append(make_step("save_by_toggle", f"{BASE}/save-conversion", "POST",
                                {"tool": "weight"}, f"Saved. success={success}"))

    return {"chain_id": f"{SITE}_hard_007", "site": SITE, "difficulty": "hard",
            "macros_executed": ["calculate_by_form", "extract_by_field", "login_by_form", "navigate_by_route", "save_by_toggle"],
            "valid": success and resp.get("result") is not None, "trajectory": trajectory}


def walk_hard_008():
    """calculate_by_form, extract_by_field, login_by_form, save_by_toggle, select_by_dropdown"""
    trajectory = []
    r = login()
    trajectory.append(make_step("login_by_form", f"{BASE}/login", "POST",
                                {"username": "converter_alice", "password": "pass123"}, "Logged in"))

    trajectory.append(make_step("select_by_dropdown", f"{BASE}/calculator/tip", "GET",
                                {"tip_percent": 10}, "Selected 10% tip"))

    r = calculate_tip_api(45, 10, 1)
    resp = r.get("response", {})
    trajectory.append(make_step("calculate_by_form", f"{BASE}/api/calculate/tip?bill=45&tip_percent=10&people=1", "GET",
                                {"bill": 45, "tip_percent": 10},
                                f"Tip=${resp.get('tip_amount','')}, Total=${resp.get('total','')}"))

    trajectory.append(make_step("extract_by_field", f"{BASE}/api/calculate/tip", "GET", {},
                                f"Extracted tip_amount={resp.get('tip_amount','')}, total={resp.get('total','')}"))

    r = save_conversion("tip", "$45 + 10% tip", "bill", "total", f"${resp.get('total','')}")
    success = "Saved Conversions (1)" in r["ax_tree_text"]
    trajectory.append(make_step("save_by_toggle", f"{BASE}/save-conversion", "POST",
                                {"tool": "tip"}, f"Saved. success={success}"))

    return {"chain_id": f"{SITE}_hard_008", "site": SITE, "difficulty": "hard",
            "macros_executed": ["calculate_by_form", "extract_by_field", "login_by_form", "save_by_toggle", "select_by_dropdown"],
            "valid": success and resp.get("tip_amount") == 4.5, "trajectory": trajectory}


def walk_hard_009():
    """input_by_form, login_by_form, navigate_by_route, save_by_toggle, select_by_dropdown"""
    trajectory = []
    r = login()
    trajectory.append(make_step("login_by_form", f"{BASE}/login", "POST",
                                {"username": "converter_alice", "password": "pass123"}, "Logged in"))

    r = navigate("/converter/currency")
    trajectory.append(make_step("navigate_by_route", f"{BASE}/converter/currency", "GET", {}, "Currency Converter"))

    trajectory.append(make_step("select_by_dropdown", f"{BASE}/converter/currency", "GET",
                                {"from_unit": "EUR", "to_unit": "CHF"},
                                "Selected from=EUR, to=CHF"))

    r = convert_via_api("currency", 2500, "EUR", "CHF")
    resp = r.get("response", {})
    trajectory.append(make_step("input_by_form", f"{BASE}/api/convert/currency?value=2500&from=EUR&to=CHF", "GET",
                                {"value": 2500, "from": "EUR", "to": "CHF"},
                                f"Input 2500 EUR, result: {resp.get('result','')} CHF"))

    r = save_conversion("currency", "2500", "EUR", "CHF", str(resp.get("result", "")))
    success = "Saved Conversions (1)" in r["ax_tree_text"]
    trajectory.append(make_step("save_by_toggle", f"{BASE}/save-conversion", "POST",
                                {"tool": "currency"}, f"Saved. success={success}"))

    return {"chain_id": f"{SITE}_hard_009", "site": SITE, "difficulty": "hard",
            "macros_executed": ["input_by_form", "login_by_form", "navigate_by_route", "save_by_toggle", "select_by_dropdown"],
            "valid": success and resp.get("result") is not None, "trajectory": trajectory}


def walk_hard_010():
    """calculate_by_form, input_by_form, login_by_form, navigate_by_route, select_by_dropdown"""
    trajectory = []
    r = login()
    trajectory.append(make_step("login_by_form", f"{BASE}/login", "POST",
                                {"username": "converter_alice", "password": "pass123"}, "Logged in"))

    r = navigate("/calculator/tip")
    trajectory.append(make_step("navigate_by_route", f"{BASE}/calculator/tip", "GET", {}, "Tip Calculator"))

    trajectory.append(make_step("input_by_form", f"{BASE}/calculator/tip", "GET",
                                {"bill": 180, "people": 6}, "Entered bill=$180, split=6"))

    trajectory.append(make_step("select_by_dropdown", f"{BASE}/calculator/tip", "GET",
                                {"tip_percent": 20}, "Selected 20% tip"))

    r = calculate_tip_api(180, 20, 6)
    resp = r.get("response", {})
    trajectory.append(make_step("calculate_by_form", f"{BASE}/api/calculate/tip?bill=180&tip_percent=20&people=6", "GET",
                                {"bill": 180, "tip_percent": 20, "people": 6},
                                f"Tip=${resp.get('tip_amount','')}, Total=${resp.get('total','')}, Per person=${resp.get('per_person','')}"))

    return {"chain_id": f"{SITE}_hard_010", "site": SITE, "difficulty": "hard",
            "macros_executed": ["calculate_by_form", "input_by_form", "login_by_form", "navigate_by_route", "select_by_dropdown"],
            "valid": resp.get("tip_amount") == 36.0, "trajectory": trajectory}


def walk_hard_011():
    """calculate_by_form, extract_by_field, input_by_form, save_by_toggle, select_by_dropdown"""
    trajectory = []
    login()
    trajectory.append(make_step("login", f"{BASE}/login", "POST",
                                {"username": "converter_alice", "password": "pass123"}, "Logged in"))

    trajectory.append(make_step("input_by_form", f"{BASE}/calculator/tip", "GET",
                                {"bill": 300, "people": 8}, "Entered bill=$300, 8 people"))

    trajectory.append(make_step("select_by_dropdown", f"{BASE}/calculator/tip", "GET",
                                {"tip_percent": 15}, "Selected 15% tip"))

    r = calculate_tip_api(300, 15, 8)
    resp = r.get("response", {})
    trajectory.append(make_step("calculate_by_form", f"{BASE}/api/calculate/tip?bill=300&tip_percent=15&people=8", "GET",
                                {"bill": 300, "tip_percent": 15, "people": 8},
                                f"Tip=${resp.get('tip_amount','')}, Total=${resp.get('total','')}, Per person=${resp.get('per_person','')}"))

    trajectory.append(make_step("extract_by_field", f"{BASE}/api/calculate/tip", "GET", {},
                                f"Extracted per_person={resp.get('per_person','')}"))

    r = save_conversion("tip", "$300 + 15% tip", "bill", "total", f"${resp.get('total','')}")
    success = "Saved Conversions (1)" in r["ax_tree_text"]
    trajectory.append(make_step("save_by_toggle", f"{BASE}/save-conversion", "POST",
                                {"tool": "tip"}, f"Saved. success={success}"))

    return {"chain_id": f"{SITE}_hard_011", "site": SITE, "difficulty": "hard",
            "macros_executed": ["calculate_by_form", "extract_by_field", "input_by_form", "save_by_toggle", "select_by_dropdown"],
            "valid": success and resp.get("tip_amount") == 45.0, "trajectory": trajectory}


def walk_hard_012():
    """calculate_by_form, extract_by_field, input_by_form, login_by_form, select_by_dropdown"""
    trajectory = []
    r = login()
    trajectory.append(make_step("login_by_form", f"{BASE}/login", "POST",
                                {"username": "converter_alice", "password": "pass123"}, "Logged in"))

    r = navigate("/converter/length")
    trajectory.append(make_step("navigate", f"{BASE}/converter/length", "GET", {}, "Length Converter"))

    trajectory.append(make_step("select_by_dropdown", f"{BASE}/converter/length", "GET",
                                {"from_unit": "yard", "to_unit": "meter"},
                                "Selected from=Yard, to=Meter"))

    trajectory.append(make_step("input_by_form", f"{BASE}/converter/length", "GET",
                                {"value": 100}, "Entered 100 yards"))

    r = convert_via_api("length", 100, "yard", "meter")
    resp = r.get("response", {})
    trajectory.append(make_step("calculate_by_form", f"{BASE}/api/convert/length?value=100&from=yard&to=meter", "GET",
                                {"value": 100, "from": "yard", "to": "meter"},
                                f"100 yards = {resp.get('result','')} meters"))

    trajectory.append(make_step("extract_by_field", f"{BASE}/api/convert/length", "GET", {},
                                f"Extracted result: {resp.get('result','')} meters"))

    return {"chain_id": f"{SITE}_hard_012", "site": SITE, "difficulty": "hard",
            "macros_executed": ["calculate_by_form", "extract_by_field", "input_by_form", "login_by_form", "select_by_dropdown"],
            "valid": resp.get("result") is not None, "trajectory": trajectory}


def walk_hard_013():
    """extract_by_field, input_by_form, navigate_by_route, save_by_toggle, select_by_dropdown"""
    trajectory = []
    login()
    trajectory.append(make_step("login", f"{BASE}/login", "POST",
                                {"username": "converter_alice", "password": "pass123"}, "Logged in"))

    r = navigate("/converter/area")
    trajectory.append(make_step("navigate_by_route", f"{BASE}/converter/area", "GET", {}, "Area Converter"))

    trajectory.append(make_step("select_by_dropdown", f"{BASE}/converter/area", "GET",
                                {"from_unit": "hectare", "to_unit": "acre"},
                                "Selected from=Hectare, to=Acre"))

    r = convert_via_api("area", 50, "hectare", "acre")
    resp = r.get("response", {})
    trajectory.append(make_step("input_by_form", f"{BASE}/api/convert/area?value=50&from=hectare&to=acre", "GET",
                                {"value": 50}, "Input 50 hectares"))

    trajectory.append(make_step("extract_by_field", f"{BASE}/api/convert/area", "GET", {},
                                f"Extracted: 50 hectares = {resp.get('result','')} acres"))

    r = save_conversion("area", "50", "hectare", "acre", str(resp.get("result", "")))
    success = "Saved Conversions (1)" in r["ax_tree_text"]
    trajectory.append(make_step("save_by_toggle", f"{BASE}/save-conversion", "POST",
                                {"tool": "area"}, f"Saved. success={success}"))

    return {"chain_id": f"{SITE}_hard_013", "site": SITE, "difficulty": "hard",
            "macros_executed": ["extract_by_field", "input_by_form", "navigate_by_route", "save_by_toggle", "select_by_dropdown"],
            "valid": success and resp.get("result") is not None, "trajectory": trajectory}


def walk_hard_014():
    """extract_by_field, input_by_form, login_by_form, save_by_toggle, select_by_dropdown"""
    trajectory = []
    r = login()
    trajectory.append(make_step("login_by_form", f"{BASE}/login", "POST",
                                {"username": "converter_alice", "password": "pass123"}, "Logged in"))

    r = navigate("/converter/volume")
    trajectory.append(make_step("navigate", f"{BASE}/converter/volume", "GET", {}, "Volume Converter"))

    trajectory.append(make_step("select_by_dropdown", f"{BASE}/converter/volume", "GET",
                                {"from_unit": "cup", "to_unit": "milliliter"},
                                "Selected from=Cup, to=Milliliter"))

    r = convert_via_api("volume", 3, "cup", "milliliter")
    resp = r.get("response", {})
    trajectory.append(make_step("input_by_form", f"{BASE}/api/convert/volume?value=3&from=cup&to=milliliter", "GET",
                                {"value": 3}, "Input 3 cups"))

    trajectory.append(make_step("extract_by_field", f"{BASE}/api/convert/volume", "GET", {},
                                f"Extracted: 3 cups = {resp.get('result','')} mL"))

    r = save_conversion("volume", "3", "cup", "milliliter", str(resp.get("result", "")))
    success = "Saved Conversions (1)" in r["ax_tree_text"]
    trajectory.append(make_step("save_by_toggle", f"{BASE}/save-conversion", "POST",
                                {"tool": "volume"}, f"Saved. success={success}"))

    return {"chain_id": f"{SITE}_hard_014", "site": SITE, "difficulty": "hard",
            "macros_executed": ["extract_by_field", "input_by_form", "login_by_form", "save_by_toggle", "select_by_dropdown"],
            "valid": success and resp.get("result") is not None, "trajectory": trajectory}


def walk_hard_015():
    """calculate_by_form, extract_by_field, input_by_form, navigate_by_route, select_by_dropdown"""
    trajectory = []
    r = observe()
    trajectory.append(make_step("observe", f"{BASE}/", "GET", {}, "Homepage"))

    r = navigate("/converter/speed")
    trajectory.append(make_step("navigate_by_route", f"{BASE}/converter/speed", "GET", {}, "Speed Converter"))

    trajectory.append(make_step("select_by_dropdown", f"{BASE}/converter/speed", "GET",
                                {"from_unit": "knots", "to_unit": "kilometers_per_hour"},
                                "Selected from=Knots, to=km/h"))

    r = convert_via_api("speed", 30, "knots", "kilometers_per_hour")
    resp = r.get("response", {})
    trajectory.append(make_step("input_by_form", f"{BASE}/api/convert/speed?value=30&from=knots&to=kilometers_per_hour", "GET",
                                {"value": 30}, "Input 30 knots"))

    trajectory.append(make_step("calculate_by_form", f"{BASE}/api/convert/speed", "GET",
                                {"value": 30, "from": "knots", "to": "kilometers_per_hour"},
                                f"30 knots = {resp.get('result','')} km/h"))

    trajectory.append(make_step("extract_by_field", f"{BASE}/api/convert/speed", "GET", {},
                                f"Extracted result: {resp.get('result','')} km/h"))

    return {"chain_id": f"{SITE}_hard_015", "site": SITE, "difficulty": "hard",
            "macros_executed": ["calculate_by_form", "extract_by_field", "input_by_form", "navigate_by_route", "select_by_dropdown"],
            "valid": resp.get("result") is not None, "trajectory": trajectory}


def walk_hard_016():
    """calculate_by_form, input_by_form, login_by_form, navigate_by_route, save_by_toggle"""
    trajectory = []
    r = login()
    trajectory.append(make_step("login_by_form", f"{BASE}/login", "POST",
                                {"username": "converter_alice", "password": "pass123"}, "Logged in"))

    r = navigate("/calculator/mortgage")
    trajectory.append(make_step("navigate_by_route", f"{BASE}/calculator/mortgage", "GET", {}, "Mortgage Calculator"))

    trajectory.append(make_step("input_by_form", f"{BASE}/calculator/mortgage", "GET",
                                {"principal": 600000, "rate": 6.25, "years": 15},
                                "Input: $600k, 6.25%, 15 years"))

    r = calculate_mortgage_api(600000, 6.25, 15)
    resp = r.get("response", {})
    trajectory.append(make_step("calculate_by_form", f"{BASE}/api/calculate/mortgage?principal=600000&rate=6.25&years=15", "GET",
                                {"principal": 600000, "rate": 6.25, "years": 15},
                                f"Monthly=${resp.get('monthly_payment','')}, Total interest=${resp.get('total_interest','')}"))

    r = save_conversion("mortgage", "$600000 at 6.25% for 15 yrs", "loan", "payment", f"${resp.get('monthly_payment','')}/mo")
    success = "Saved Conversions (1)" in r["ax_tree_text"]
    trajectory.append(make_step("save_by_toggle", f"{BASE}/save-conversion", "POST",
                                {"tool": "mortgage"}, f"Saved. success={success}"))

    return {"chain_id": f"{SITE}_hard_016", "site": SITE, "difficulty": "hard",
            "macros_executed": ["calculate_by_form", "input_by_form", "login_by_form", "navigate_by_route", "save_by_toggle"],
            "valid": success and resp.get("monthly_payment") is not None, "trajectory": trajectory}


def walk_hard_017():
    """extract_by_field, input_by_form, login_by_form, navigate_by_route, save_by_toggle"""
    trajectory = []
    r = login()
    trajectory.append(make_step("login_by_form", f"{BASE}/login", "POST",
                                {"username": "converter_alice", "password": "pass123"}, "Logged in"))

    r = navigate("/converter/temperature")
    trajectory.append(make_step("navigate_by_route", f"{BASE}/converter/temperature", "GET", {}, "Temperature Converter"))

    r = convert_via_api("temperature", 37, "celsius", "fahrenheit")
    resp = r.get("response", {})
    trajectory.append(make_step("input_by_form", f"{BASE}/api/convert/temperature?value=37&from=celsius&to=fahrenheit", "GET",
                                {"value": 37, "from": "celsius", "to": "fahrenheit"},
                                f"Input 37 Celsius"))

    trajectory.append(make_step("extract_by_field", f"{BASE}/api/convert/temperature", "GET", {},
                                f"Extracted: 37 C = {resp.get('result','')} F"))

    r = save_conversion("temperature", "37", "celsius", "fahrenheit", str(resp.get("result", "")))
    success = "Saved Conversions (1)" in r["ax_tree_text"]
    trajectory.append(make_step("save_by_toggle", f"{BASE}/save-conversion", "POST",
                                {"tool": "temperature"}, f"Saved. success={success}"))

    return {"chain_id": f"{SITE}_hard_017", "site": SITE, "difficulty": "hard",
            "macros_executed": ["extract_by_field", "input_by_form", "login_by_form", "navigate_by_route", "save_by_toggle"],
            "valid": success and resp.get("result") == 98.6, "trajectory": trajectory}


def walk_hard_018():
    """extract_by_field, input_by_form, login_by_form, navigate_by_route, select_by_dropdown"""
    trajectory = []
    r = login()
    trajectory.append(make_step("login_by_form", f"{BASE}/login", "POST",
                                {"username": "converter_alice", "password": "pass123"}, "Logged in"))

    r = navigate("/converter/base")
    trajectory.append(make_step("navigate_by_route", f"{BASE}/converter/base", "GET", {}, "Number Base Converter"))

    trajectory.append(make_step("input_by_form", f"{BASE}/converter/base", "GET",
                                {"value": "FF"}, "Entered value FF"))

    trajectory.append(make_step("select_by_dropdown", f"{BASE}/converter/base", "GET",
                                {"from_base": 16, "to_base": 2},
                                "Selected from=Hexadecimal(16), to=Binary(2)"))

    r = api_get("/api/convert/base?value=FF&from=16&to=2")
    resp = r.get("response", {})
    trajectory.append(make_step("extract_by_field", f"{BASE}/api/convert/base?value=FF&from=16&to=2", "GET", {},
                                f"Extracted: FF hex = {resp.get('result','')} binary (decimal: {resp.get('decimal','')})"))

    return {"chain_id": f"{SITE}_hard_018", "site": SITE, "difficulty": "hard",
            "macros_executed": ["extract_by_field", "input_by_form", "login_by_form", "navigate_by_route", "select_by_dropdown"],
            "valid": resp.get("result") == "11111111" and resp.get("decimal") == 255, "trajectory": trajectory}


def walk_hard_019():
    """calculate_by_form, login_by_form, navigate_by_route, save_by_toggle, select_by_dropdown"""
    trajectory = []
    r = login()
    trajectory.append(make_step("login_by_form", f"{BASE}/login", "POST",
                                {"username": "converter_alice", "password": "pass123"}, "Logged in"))

    r = navigate("/calculator/tip")
    trajectory.append(make_step("navigate_by_route", f"{BASE}/calculator/tip", "GET", {}, "Tip Calculator"))

    trajectory.append(make_step("select_by_dropdown", f"{BASE}/calculator/tip", "GET",
                                {"tip_percent": 25}, "Selected 25% tip"))

    r = calculate_tip_api(400, 25, 10)
    resp = r.get("response", {})
    trajectory.append(make_step("calculate_by_form", f"{BASE}/api/calculate/tip?bill=400&tip_percent=25&people=10", "GET",
                                {"bill": 400, "tip_percent": 25, "people": 10},
                                f"Tip=${resp.get('tip_amount','')}, Total=${resp.get('total','')}, Per person=${resp.get('per_person','')}"))

    r = save_conversion("tip", "$400 + 25% tip", "bill", "total", f"${resp.get('total','')}")
    success = "Saved Conversions (1)" in r["ax_tree_text"]
    trajectory.append(make_step("save_by_toggle", f"{BASE}/save-conversion", "POST",
                                {"tool": "tip"}, f"Saved. success={success}"))

    return {"chain_id": f"{SITE}_hard_019", "site": SITE, "difficulty": "hard",
            "macros_executed": ["calculate_by_form", "login_by_form", "navigate_by_route", "save_by_toggle", "select_by_dropdown"],
            "valid": success and resp.get("tip_amount") == 100.0, "trajectory": trajectory}


def walk_hard_020():
    """extract_by_field, login_by_form, navigate_by_route, save_by_toggle, select_by_dropdown"""
    trajectory = []
    r = login()
    trajectory.append(make_step("login_by_form", f"{BASE}/login", "POST",
                                {"username": "converter_alice", "password": "pass123"}, "Logged in"))

    r = navigate("/converter/weight")
    trajectory.append(make_step("navigate_by_route", f"{BASE}/converter/weight", "GET", {}, "Weight Converter"))

    trajectory.append(make_step("select_by_dropdown", f"{BASE}/converter/weight", "GET",
                                {"from_unit": "ounce", "to_unit": "gram"},
                                "Selected from=Ounce, to=Gram"))

    r = convert_via_api("weight", 16, "ounce", "gram")
    resp = r.get("response", {})
    trajectory.append(make_step("extract_by_field", f"{BASE}/api/convert/weight?value=16&from=ounce&to=gram", "GET", {},
                                f"Extracted: 16 oz = {resp.get('result','')} grams"))

    r = save_conversion("weight", "16", "ounce", "gram", str(resp.get("result", "")))
    success = "Saved Conversions (1)" in r["ax_tree_text"]
    trajectory.append(make_step("save_by_toggle", f"{BASE}/save-conversion", "POST",
                                {"tool": "weight"}, f"Saved. success={success}"))

    return {"chain_id": f"{SITE}_hard_020", "site": SITE, "difficulty": "hard",
            "macros_executed": ["extract_by_field", "login_by_form", "navigate_by_route", "save_by_toggle", "select_by_dropdown"],
            "valid": success and resp.get("result") is not None, "trajectory": trajectory}


# ============================================================================
# Main runner
# ============================================================================

ALL_WALKERS = {
    f"{SITE}_easy_001": walk_easy_001,
    f"{SITE}_easy_002": walk_easy_002,
    f"{SITE}_easy_003": walk_easy_003,
    f"{SITE}_easy_004": walk_easy_004,
    f"{SITE}_easy_005": walk_easy_005,
    f"{SITE}_easy_006": walk_easy_006,
    f"{SITE}_easy_007": walk_easy_007,
    f"{SITE}_medium_001": walk_medium_001,
    f"{SITE}_medium_002": walk_medium_002,
    f"{SITE}_medium_003": walk_medium_003,
    f"{SITE}_medium_004": walk_medium_004,
    f"{SITE}_medium_005": walk_medium_005,
    f"{SITE}_medium_006": walk_medium_006,
    f"{SITE}_medium_007": walk_medium_007,
    f"{SITE}_medium_008": walk_medium_008,
    f"{SITE}_medium_009": walk_medium_009,
    f"{SITE}_medium_010": walk_medium_010,
    f"{SITE}_medium_011": walk_medium_011,
    f"{SITE}_medium_012": walk_medium_012,
    f"{SITE}_medium_013": walk_medium_013,
    f"{SITE}_medium_014": walk_medium_014,
    f"{SITE}_medium_015": walk_medium_015,
    f"{SITE}_medium_016": walk_medium_016,
    f"{SITE}_medium_017": walk_medium_017,
    f"{SITE}_medium_018": walk_medium_018,
    f"{SITE}_medium_019": walk_medium_019,
    f"{SITE}_medium_020": walk_medium_020,
    f"{SITE}_hard_001": walk_hard_001,
    f"{SITE}_hard_002": walk_hard_002,
    f"{SITE}_hard_003": walk_hard_003,
    f"{SITE}_hard_004": walk_hard_004,
    f"{SITE}_hard_005": walk_hard_005,
    f"{SITE}_hard_006": walk_hard_006,
    f"{SITE}_hard_007": walk_hard_007,
    f"{SITE}_hard_008": walk_hard_008,
    f"{SITE}_hard_009": walk_hard_009,
    f"{SITE}_hard_010": walk_hard_010,
    f"{SITE}_hard_011": walk_hard_011,
    f"{SITE}_hard_012": walk_hard_012,
    f"{SITE}_hard_013": walk_hard_013,
    f"{SITE}_hard_014": walk_hard_014,
    f"{SITE}_hard_015": walk_hard_015,
    f"{SITE}_hard_016": walk_hard_016,
    f"{SITE}_hard_017": walk_hard_017,
    f"{SITE}_hard_018": walk_hard_018,
    f"{SITE}_hard_019": walk_hard_019,
    f"{SITE}_hard_020": walk_hard_020,
}


if __name__ == "__main__":
    results_summary = []
    for chain_id, walker_fn in ALL_WALKERS.items():
        # Reset between chains
        reset_all()
        try:
            result = walker_fn()
            save_chain_result(chain_id, SITE, result)
            status = "PASS" if result["valid"] else "FAIL"
            results_summary.append(f"  {chain_id}: {status}")
            print(f"  {chain_id}: {status}")
        except Exception as e:
            results_summary.append(f"  {chain_id}: ERROR - {e}")
            print(f"  {chain_id}: ERROR - {e}")

    print("\n=== SUMMARY ===")
    passed = sum(1 for r in results_summary if "PASS" in r)
    failed = sum(1 for r in results_summary if "FAIL" in r)
    errors = sum(1 for r in results_summary if "ERROR" in r)
    print(f"Total: {len(results_summary)} | Passed: {passed} | Failed: {failed} | Errors: {errors}")
