"""Converters & Calculators -- utility site modeled after Calculator.net.

Data interpreter: reads conversions.json for unit definitions and exchange
rates. All conversions computed server-side with deterministic formulas.
"""
import json
import math
import pathlib

from flask import Blueprint, Response, abort, jsonify, redirect, render_template, request, session, url_for

from app import db

SITE = "converters-calculators"
SITE_DIR = pathlib.Path(__file__).resolve().parent
blueprint = Blueprint(
    "converters-calculators",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data interpreter -- reads conversions.json
# ---------------------------------------------------------------------------

_conversions = None


def _load_conversions():
    global _conversions
    if _conversions is None:
        rows = db.query(SITE, "conversions")
        if rows:
            row = rows[0]
            # Reconstruct the original dict from the flattened row
            _conversions = {}
            for key in ("length", "weight", "temperature", "currency", "volume", "area", "speed"):
                val = row.get(key)
                if val is not None:
                    if isinstance(val, str):
                        _conversions[key] = json.loads(val)
                    else:
                        _conversions[key] = val
        else:
            _conversions = {}
    return _conversions


# ---------------------------------------------------------------------------
# Tool catalog
# ---------------------------------------------------------------------------

TOOLS = [
    {"id": "length", "name": "Length Converter", "category": "converter",
     "description": "Convert between meters, feet, inches, miles, kilometers, yards, and more.",
     "icon": "ruler"},
    {"id": "weight", "name": "Weight Converter", "category": "converter",
     "description": "Convert between kilograms, pounds, ounces, grams, stones, and tons.",
     "icon": "balance-scale"},
    {"id": "temperature", "name": "Temperature Converter", "category": "converter",
     "description": "Convert between Celsius, Fahrenheit, and Kelvin.",
     "icon": "thermometer"},
    {"id": "currency", "name": "Currency Converter", "category": "converter",
     "description": "Convert between USD, EUR, GBP, JPY, CAD, AUD, CHF, and CNY.",
     "icon": "dollar-sign"},
    {"id": "volume", "name": "Volume Converter", "category": "converter",
     "description": "Convert between liters, gallons, cups, milliliters, and fluid ounces.",
     "icon": "flask"},
    {"id": "area", "name": "Area Converter", "category": "converter",
     "description": "Convert between square meters, square feet, acres, and hectares.",
     "icon": "vector-square"},
    {"id": "speed", "name": "Speed Converter", "category": "converter",
     "description": "Convert between km/h, mph, m/s, knots, and ft/s.",
     "icon": "tachometer"},
    {"id": "base", "name": "Number Base Converter", "category": "converter",
     "description": "Convert numbers between decimal, binary, octal, and hexadecimal.",
     "icon": "hashtag"},
    {"id": "bmi", "name": "BMI Calculator", "category": "calculator",
     "description": "Calculate Body Mass Index from weight and height.",
     "icon": "heartbeat"},
    {"id": "mortgage", "name": "Mortgage Calculator", "category": "calculator",
     "description": "Calculate monthly mortgage payments, total interest, and amortization.",
     "icon": "home"},
    {"id": "tip", "name": "Tip Calculator", "category": "calculator",
     "description": "Calculate tip amount and total bill, with split options.",
     "icon": "receipt"},
]


# ---------------------------------------------------------------------------
# Conversion functions
# ---------------------------------------------------------------------------

def _convert_unit(category, value, from_unit, to_unit):
    """Generic conversion for ratio-based categories (length, weight, volume, area, speed)."""
    data = _load_conversions()
    cat = data.get(category)
    if not cat or "units" not in cat:
        return None
    units = cat["units"]
    if from_unit not in units or to_unit not in units:
        return None
    base_value = value * units[from_unit]["to_base"]
    result = base_value / units[to_unit]["to_base"]
    return result


def convert_length(value, from_unit, to_unit):
    return _convert_unit("length", value, from_unit, to_unit)


def convert_weight(value, from_unit, to_unit):
    return _convert_unit("weight", value, from_unit, to_unit)


def convert_volume(value, from_unit, to_unit):
    return _convert_unit("volume", value, from_unit, to_unit)


def convert_area(value, from_unit, to_unit):
    return _convert_unit("area", value, from_unit, to_unit)


def convert_speed(value, from_unit, to_unit):
    return _convert_unit("speed", value, from_unit, to_unit)


def convert_temperature(value, from_unit, to_unit):
    """Temperature conversion using exact formulas."""
    if from_unit == to_unit:
        return value
    # Convert to Celsius first
    if from_unit == "celsius":
        c = value
    elif from_unit == "fahrenheit":
        c = (value - 32) * 5 / 9
    elif from_unit == "kelvin":
        c = value - 273.15
    else:
        return None
    # Convert from Celsius to target
    if to_unit == "celsius":
        return c
    elif to_unit == "fahrenheit":
        return c * 9 / 5 + 32
    elif to_unit == "kelvin":
        return c + 273.15
    return None


def convert_currency(value, from_currency, to_currency):
    """Currency conversion using stored exchange rates (all rates relative to USD)."""
    data = _load_conversions()
    rates = data.get("currency", {}).get("rates", {})
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()
    if from_currency not in rates or to_currency not in rates:
        return None
    usd_value = value / rates[from_currency]
    result = usd_value * rates[to_currency]
    return result


def calculate_bmi(weight_kg, height_m):
    """BMI = weight(kg) / height(m)^2."""
    if height_m <= 0:
        return None
    bmi = weight_kg / (height_m ** 2)
    if bmi < 18.5:
        category = "Underweight"
    elif bmi < 25:
        category = "Normal weight"
    elif bmi < 30:
        category = "Overweight"
    else:
        category = "Obese"
    return {"bmi": round(bmi, 2), "category": category}


def calculate_mortgage(principal, annual_rate_pct, years):
    """Monthly mortgage payment using standard amortization formula.
    M = P * [r(1+r)^n] / [(1+r)^n - 1]
    """
    if principal <= 0 or annual_rate_pct < 0 or years <= 0:
        return None
    if annual_rate_pct == 0:
        monthly = principal / (years * 12)
        return {
            "monthly_payment": round(monthly, 2),
            "total_payment": round(principal, 2),
            "total_interest": 0.0,
        }
    r = annual_rate_pct / 100 / 12  # monthly rate
    n = years * 12  # total payments
    monthly = principal * (r * (1 + r) ** n) / ((1 + r) ** n - 1)
    total = monthly * n
    interest = total - principal
    return {
        "monthly_payment": round(monthly, 2),
        "total_payment": round(total, 2),
        "total_interest": round(interest, 2),
    }


def calculate_tip(bill_amount, tip_percent, num_people=1):
    """Calculate tip and per-person split."""
    if bill_amount < 0 or tip_percent < 0 or num_people < 1:
        return None
    tip = bill_amount * tip_percent / 100
    total = bill_amount + tip
    per_person = total / num_people
    return {
        "tip_amount": round(tip, 2),
        "total": round(total, 2),
        "per_person": round(per_person, 2),
    }


def convert_number_base(value_str, from_base, to_base):
    """Convert number between bases (2, 8, 10, 16)."""
    valid_bases = {2, 8, 10, 16}
    if from_base not in valid_bases or to_base not in valid_bases:
        return None
    try:
        decimal_val = int(value_str.strip(), from_base)
    except (ValueError, TypeError):
        return None
    if to_base == 2:
        result = bin(decimal_val)[2:]
    elif to_base == 8:
        result = oct(decimal_val)[2:]
    elif to_base == 10:
        result = str(decimal_val)
    elif to_base == 16:
        result = hex(decimal_val)[2:].upper()
    else:
        return None
    return {"decimal": decimal_val, "result": result}


# ---------------------------------------------------------------------------
# Users (mutable state)
# ---------------------------------------------------------------------------

def _load_users():
    return db.query(SITE, "users")


def _save_users(users):
    db.save_collection(SITE, "users", users)


def _get_user(user_id):
    return db.get_item(SITE, "users", user_id)


# ---------------------------------------------------------------------------
# Helper: format result for display
# ---------------------------------------------------------------------------

def _fmt(value):
    """Format a numeric result for display: use up to 6 decimal places, strip trailing zeros."""
    if value is None:
        return "N/A"
    if isinstance(value, float):
        # Round to 6 decimal places then strip trailing zeros
        formatted = f"{value:.6f}".rstrip("0").rstrip(".")
        return formatted
    return str(value)


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    converters = [t for t in TOOLS if t["category"] == "converter"]
    calculators = [t for t in TOOLS if t["category"] == "calculator"]
    return render_template("converters-calculators/index.html",
                           converters=converters, calculators=calculators,
                           tools=TOOLS, user=user)


@blueprint.route("/converter/<tool_id>")
def converter_page(tool_id):
    data = _load_conversions()
    tool = next((t for t in TOOLS if t["id"] == tool_id), None)
    if not tool:
        abort(404)

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    if tool_id == "base":
        return render_template("converters-calculators/base_converter.html",
                               tool=tool, user=user)

    if tool_id in data:
        cat_data = data[tool_id]
        if tool_id == "currency":
            units = {k: {"name": k, "symbol": k} for k in cat_data.get("rates", {}).keys()}
        else:
            units = cat_data.get("units", {})
    else:
        units = {}

    return render_template("converters-calculators/converter.html",
                           tool=tool, units=units, category=tool_id, user=user)


@blueprint.route("/calculator/<tool_id>")
def calculator_page(tool_id):
    tool = next((t for t in TOOLS if t["id"] == tool_id and t["category"] == "calculator"), None)
    if not tool:
        abort(404)
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("converters-calculators/calculator.html",
                           tool=tool, user=user)


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("converters-calculators/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return render_template("converters-calculators/login.html",
                               error="Invalid username or password")
    session["user_id"] = user["id"]
    return redirect(url_for("converters-calculators.dashboard"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("converters-calculators.index"))


@blueprint.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("converters-calculators.login_page"))
    user = _get_user(session["user_id"])
    if not user:
        return redirect(url_for("converters-calculators.login_page"))
    return render_template("converters-calculators/dashboard.html", user=user)


# ---------------------------------------------------------------------------
# Form-based mutation routes
# ---------------------------------------------------------------------------

@blueprint.route("/save-conversion", methods=["POST"])
def form_save_conversion():
    if "user_id" not in session:
        return redirect(url_for("converters-calculators.login_page"))
    users = _load_users()
    user = next((u for u in users if u["id"] == session["user_id"]), None)
    if not user:
        return redirect(url_for("converters-calculators.login_page"))

    conversion = {
        "tool": request.form.get("tool", ""),
        "from_value": request.form.get("from_value", ""),
        "from_unit": request.form.get("from_unit", ""),
        "to_unit": request.form.get("to_unit", ""),
        "result": request.form.get("result", ""),
    }
    saved = user.setdefault("saved_conversions", [])
    saved.append(conversion)
    history = user.setdefault("history", [])
    history.append(conversion)
    _save_users(users)

    redirect_to = request.form.get("redirect_to", "")
    if redirect_to:
        return redirect(redirect_to)
    return redirect(url_for("converters-calculators.dashboard"))


@blueprint.route("/remove-saved/<int:idx>", methods=["POST"])
def form_remove_saved(idx):
    if "user_id" not in session:
        return redirect(url_for("converters-calculators.login_page"))
    users = _load_users()
    user = next((u for u in users if u["id"] == session["user_id"]), None)
    if not user:
        return redirect(url_for("converters-calculators.login_page"))
    saved = user.get("saved_conversions", [])
    if 0 <= idx < len(saved):
        saved.pop(idx)
    _save_users(users)
    return redirect(url_for("converters-calculators.dashboard"))


# ---------------------------------------------------------------------------
# API routes -- Conversions
# ---------------------------------------------------------------------------

@blueprint.route("/api/convert/length")
def api_convert_length():
    value = request.args.get("value", type=float)
    from_unit = request.args.get("from", "").strip()
    to_unit = request.args.get("to", "").strip()
    if value is None:
        return jsonify({"error": "value is required"}), 400
    result = convert_length(value, from_unit, to_unit)
    if result is None:
        return jsonify({"error": "Invalid units"}), 400
    return jsonify({"value": value, "from": from_unit, "to": to_unit,
                    "result": round(result, 6)})


@blueprint.route("/api/convert/weight")
def api_convert_weight():
    value = request.args.get("value", type=float)
    from_unit = request.args.get("from", "").strip()
    to_unit = request.args.get("to", "").strip()
    if value is None:
        return jsonify({"error": "value is required"}), 400
    result = convert_weight(value, from_unit, to_unit)
    if result is None:
        return jsonify({"error": "Invalid units"}), 400
    return jsonify({"value": value, "from": from_unit, "to": to_unit,
                    "result": round(result, 6)})


@blueprint.route("/api/convert/temperature")
def api_convert_temperature():
    value = request.args.get("value", type=float)
    from_unit = request.args.get("from", "").strip()
    to_unit = request.args.get("to", "").strip()
    if value is None:
        return jsonify({"error": "value is required"}), 400
    result = convert_temperature(value, from_unit, to_unit)
    if result is None:
        return jsonify({"error": "Invalid units"}), 400
    return jsonify({"value": value, "from": from_unit, "to": to_unit,
                    "result": round(result, 6)})


@blueprint.route("/api/convert/currency")
def api_convert_currency():
    value = request.args.get("value", type=float)
    from_curr = request.args.get("from", "").strip()
    to_curr = request.args.get("to", "").strip()
    if value is None:
        return jsonify({"error": "value is required"}), 400
    result = convert_currency(value, from_curr, to_curr)
    if result is None:
        return jsonify({"error": "Invalid currencies"}), 400
    return jsonify({"value": value, "from": from_curr.upper(), "to": to_curr.upper(),
                    "result": round(result, 2)})


@blueprint.route("/api/convert/volume")
def api_convert_volume():
    value = request.args.get("value", type=float)
    from_unit = request.args.get("from", "").strip()
    to_unit = request.args.get("to", "").strip()
    if value is None:
        return jsonify({"error": "value is required"}), 400
    result = convert_volume(value, from_unit, to_unit)
    if result is None:
        return jsonify({"error": "Invalid units"}), 400
    return jsonify({"value": value, "from": from_unit, "to": to_unit,
                    "result": round(result, 6)})


@blueprint.route("/api/convert/area")
def api_convert_area():
    value = request.args.get("value", type=float)
    from_unit = request.args.get("from", "").strip()
    to_unit = request.args.get("to", "").strip()
    if value is None:
        return jsonify({"error": "value is required"}), 400
    result = convert_area(value, from_unit, to_unit)
    if result is None:
        return jsonify({"error": "Invalid units"}), 400
    return jsonify({"value": value, "from": from_unit, "to": to_unit,
                    "result": round(result, 6)})


@blueprint.route("/api/convert/speed")
def api_convert_speed():
    value = request.args.get("value", type=float)
    from_unit = request.args.get("from", "").strip()
    to_unit = request.args.get("to", "").strip()
    if value is None:
        return jsonify({"error": "value is required"}), 400
    result = convert_speed(value, from_unit, to_unit)
    if result is None:
        return jsonify({"error": "Invalid units"}), 400
    return jsonify({"value": value, "from": from_unit, "to": to_unit,
                    "result": round(result, 6)})


@blueprint.route("/api/convert/base")
def api_convert_base():
    value_str = request.args.get("value", "").strip()
    from_base = request.args.get("from", type=int)
    to_base = request.args.get("to", type=int)
    if not value_str or from_base is None or to_base is None:
        return jsonify({"error": "value, from (base), and to (base) are required"}), 400
    result = convert_number_base(value_str, from_base, to_base)
    if result is None:
        return jsonify({"error": "Invalid input or base"}), 400
    return jsonify({"value": value_str, "from_base": from_base, "to_base": to_base,
                    "result": result["result"], "decimal": result["decimal"]})


# ---------------------------------------------------------------------------
# API routes -- Calculators
# ---------------------------------------------------------------------------

@blueprint.route("/api/calculate/bmi")
def api_calculate_bmi():
    weight = request.args.get("weight", type=float)
    height = request.args.get("height", type=float)
    if weight is None or height is None:
        return jsonify({"error": "weight (kg) and height (m) are required"}), 400
    result = calculate_bmi(weight, height)
    if result is None:
        return jsonify({"error": "Invalid input"}), 400
    return jsonify(result)


@blueprint.route("/api/calculate/mortgage")
def api_calculate_mortgage():
    principal = request.args.get("principal", type=float)
    rate = request.args.get("rate", type=float)
    years = request.args.get("years", type=int)
    if principal is None or rate is None or years is None:
        return jsonify({"error": "principal, rate (%), and years are required"}), 400
    result = calculate_mortgage(principal, rate, years)
    if result is None:
        return jsonify({"error": "Invalid input"}), 400
    return jsonify(result)


@blueprint.route("/api/calculate/tip")
def api_calculate_tip():
    bill = request.args.get("bill", type=float)
    tip_pct = request.args.get("tip_percent", type=float)
    people = request.args.get("people", 1, type=int)
    if bill is None or tip_pct is None:
        return jsonify({"error": "bill and tip_percent are required"}), 400
    result = calculate_tip(bill, tip_pct, people)
    if result is None:
        return jsonify({"error": "Invalid input"}), 400
    return jsonify(result)


# ---------------------------------------------------------------------------
# API routes -- Tools and Units
# ---------------------------------------------------------------------------

@blueprint.route("/api/tools")
def api_tools():
    category = request.args.get("category", "").strip()
    if category:
        filtered = [t for t in TOOLS if t["category"] == category]
        return jsonify(filtered)
    return jsonify(TOOLS)


@blueprint.route("/api/units/<category>")
def api_units(category):
    data = _load_conversions()
    if category not in data:
        return jsonify({"error": "Unknown category"}), 404
    cat_data = data[category]
    if category == "currency":
        return jsonify({"name": cat_data["name"], "units": cat_data["rates"],
                        "rates_date": cat_data.get("rates_date", "")})
    return jsonify({"name": cat_data["name"], "units": cat_data.get("units", {})})


# ---------------------------------------------------------------------------
# API routes -- Users
# ---------------------------------------------------------------------------

@blueprint.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return jsonify({"error": "Invalid credentials"}), 401
    session["user_id"] = user["id"]
    return jsonify({"user_id": user["id"], "username": user["username"]})


@blueprint.route("/api/users/<int:user_id>")
def api_user(user_id):
    user = _get_user(user_id)
    if not user:
        abort(404)
    return jsonify({k: v for k, v in user.items() if k != "password"})


@blueprint.route("/api/users/<int:user_id>/history", methods=["POST"])
def api_save_history(user_id):
    data = request.get_json(silent=True) or {}
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    entry = {
        "tool": data.get("tool", ""),
        "from_value": str(data.get("from_value", "")),
        "from_unit": data.get("from_unit", ""),
        "to_unit": data.get("to_unit", ""),
        "result": str(data.get("result", "")),
    }
    history = user.setdefault("history", [])
    history.append(entry)
    saved = user.setdefault("saved_conversions", [])
    saved.append(entry)
    _save_users(users)
    return jsonify({"action": "saved", "total_saved": len(saved),
                    "total_history": len(history)})


@blueprint.route("/api/users/<int:user_id>/history", methods=["GET"])
def api_get_history(user_id):
    user = _get_user(user_id)
    if not user:
        abort(404)
    return jsonify(user.get("history", []))


@blueprint.route("/api/export")
def api_export():
    """Export conversion history as JSON or CSV."""
    fmt = request.args.get("format", "json").lower()
    user_id = request.args.get("user_id", type=int)

    users = _load_users()
    if user_id:
        users = [u for u in users if u["id"] == user_id]

    all_history = []
    for u in users:
        for entry in u.get("history", []):
            row = dict(entry)
            row["user_id"] = u["id"]
            row["user_name"] = u.get("name", "")
            all_history.append(row)

    if fmt == "csv":
        lines = ["user_id,user_name,tool,from_value,from_unit,to_unit,result"]
        for h in all_history:
            lines.append(f'{h["user_id"]},"{h.get("user_name", "")}","{h.get("tool", "")}","{h.get("from_value", "")}","{h.get("from_unit", "")}","{h.get("to_unit", "")}","{h.get("result", "")}"')
        return Response("\n".join(lines), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=conversions.csv"})
    return jsonify(all_history)
